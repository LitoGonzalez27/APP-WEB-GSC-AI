"""
Adapter del canal Google AI Overview (módulo Manual AI).

Lee los snapshots diarios (manual_ai_snapshots) para métricas y deltas,
y reutiliza StatisticsService para el ranking de dominios/competidores.
"""

import logging
from typing import Dict

from database import get_db_connection
from ai_summary.services.adapters.base import (
    empty_channel, window_bounds, split_windows, avg, delta, rounded
)

logger = logging.getLogger(__name__)

CHANNEL = 'ai_overview'


def get_channel_summary(project_id: int, days: int = 30) -> Dict:
    summary = empty_channel(CHANNEL)
    summary['project_id'] = project_id

    previous_start, current_start, today = window_bounds(days)

    conn = get_db_connection()
    if not conn:
        summary['reason'] = 'error'
        return summary
    try:
        cur = conn.cursor()

        cur.execute("SELECT name FROM manual_ai_projects WHERE id = %s", (project_id,))
        project = cur.fetchone()
        if not project:
            return summary
        summary['project_name'] = project['name']

        cur.execute("""
            SELECT snapshot_date, visibility_percentage, avg_position,
                   keywords_with_ai, total_keywords, domain_mentions
            FROM manual_ai_snapshots
            WHERE project_id = %s
              AND snapshot_date > %s AND snapshot_date <= %s
            ORDER BY snapshot_date ASC
        """, (project_id, previous_start, today))
        rows = cur.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    previous, current = split_windows(rows, 'snapshot_date', current_start)
    if not current:
        summary['reason'] = 'no_data'
        return summary

    visibility = avg([r['visibility_percentage'] for r in current])
    position = avg([r['avg_position'] for r in current])
    aio_weight = avg([
        (r['keywords_with_ai'] / r['total_keywords'] * 100)
        for r in current if r['total_keywords']
    ])

    summary.update({
        'available': True,
        'reason': None,
        'visibility_pct': rounded(visibility),
        'visibility_delta': delta(visibility, avg([r['visibility_percentage'] for r in previous])),
        'avg_position': rounded(position),
        'position_delta': delta(position, avg([r['avg_position'] for r in previous])),
        'timeseries': [
            {'date': r['snapshot_date'].isoformat(),
             'value': rounded(float(r['visibility_percentage'] or 0))}
            for r in current
        ],
        'last_date': current[-1]['snapshot_date'].isoformat(),
        'extras': {
            'aio_weight_pct': rounded(aio_weight),
            'keywords_with_ai': current[-1]['keywords_with_ai'],
            'total_keywords': current[-1]['total_keywords'],
        },
    })

    summary['competitors'] = _get_competitors(project_id, days)
    return summary


def _get_competitors(project_id: int, days: int) -> list:
    """Top dominios en AIO: el propio, los competidores marcados y los mayores 'other'."""
    try:
        from manual_ai.services.statistics_service import StatisticsService
        ranking = StatisticsService().get_project_global_domains_ranking(project_id, days) or []
    except Exception as e:
        logger.warning(f"AI Overview competitors unavailable for project {project_id}: {e}")
        return []

    tracked = [d for d in ranking if d.get('domain_type') in ('project', 'competitor')]
    others = [d for d in ranking if d.get('domain_type') == 'other'][:3]
    return [
        {
            'domain': d.get('detected_domain'),
            'visibility_pct': rounded(d.get('visibility_percentage')),
            'avg_position': rounded(d.get('avg_position')),
            'rank': d.get('rank'),
            'is_brand': d.get('domain_type') == 'project',
            'is_selected_competitor': d.get('domain_type') == 'competitor',
        }
        for d in tracked + others
    ]
