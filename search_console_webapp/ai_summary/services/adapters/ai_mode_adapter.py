"""
Adapter del canal Google AI Mode (módulo AI Mode Monitoring).

Lee los snapshots diarios (ai_mode_snapshots) para métricas y deltas,
y reutiliza el StatisticsService de AI Mode para el ranking de dominios.
"""

import logging
from typing import Dict

from database import db_conn
from ai_summary.services.adapters.base import (
    empty_channel, window_bounds, split_windows, avg, delta, rounded
)

logger = logging.getLogger(__name__)

CHANNEL = 'ai_mode'


def get_channel_summary(project_id: int, days: int = 30) -> Dict:
    summary = empty_channel(CHANNEL)
    summary['project_id'] = project_id

    previous_start, current_start, today = window_bounds(days)

    with db_conn() as conn:
        if not conn:
            summary['reason'] = 'error'
            return summary
        cur = conn.cursor()

        cur.execute("SELECT name, brand_name FROM ai_mode_projects WHERE id = %s", (project_id,))
        project = cur.fetchone()
        if not project:
            return summary
        summary['project_name'] = project['name']

        cur.execute("""
            SELECT snapshot_date, visibility_percentage, avg_position,
                   total_mentions, total_keywords
            FROM ai_mode_snapshots
            WHERE project_id = %s
              AND snapshot_date > %s AND snapshot_date <= %s
            ORDER BY snapshot_date ASC
        """, (project_id, previous_start, today))
        rows = cur.fetchall()

    previous, current = split_windows(rows, 'snapshot_date', current_start)
    visibility = avg([r['visibility_percentage'] for r in current])
    # visibility None con filas presentes = snapshots parciales/corruptos:
    # el canal no puede puntuar y el frontend lo trata como sin datos.
    if not current or visibility is None:
        summary['reason'] = 'no_data'
        return summary
    position = avg([r['avg_position'] for r in current])

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
            'brand_name': project['brand_name'],
            'total_mentions': current[-1]['total_mentions'],
            'total_keywords': current[-1]['total_keywords'],
        },
    })

    summary['competitors'] = _get_competitors(project_id, days)
    return summary


def _get_competitors(project_id: int, days: int) -> list:
    try:
        from ai_mode_projects.services.statistics_service import StatisticsService
        ranking = StatisticsService().get_project_global_domains_ranking(project_id, days) or []
    except Exception as e:
        logger.warning(f"AI Mode competitors unavailable for project {project_id}: {e}")
        return []

    tracked = [d for d in ranking if d.get('is_project_domain') or d.get('is_selected_competitor')]
    others = [
        d for d in ranking
        if not d.get('is_project_domain') and not d.get('is_selected_competitor')
    ][:3]
    return [
        {
            'domain': d.get('detected_domain'),
            'visibility_pct': rounded(d.get('visibility_percentage')),
            'avg_position': rounded(d.get('avg_position')),
            'rank': d.get('rank'),
            'is_brand': bool(d.get('is_project_domain')),
            'is_selected_competitor': bool(d.get('is_selected_competitor')),
        }
        for d in tracked + others
    ]
