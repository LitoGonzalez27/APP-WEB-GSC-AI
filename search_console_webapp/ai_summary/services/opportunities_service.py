"""
Top opportunities del panel AI Visibility Summary: dónde está perdiendo
visibilidad la marca frente a competidores, en términos accionables.

- AIO: keywords con AI Overview donde la marca NO aparece pero un competidor
  seleccionado SÍ (manual_ai_results × manual_ai_global_domains).
- LLM: prompts donde los LLMs mencionan competidores pero no a la marca
  (llm_monitoring_results.competitors_mentioned).
"""

import logging
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from database import db_conn
from ai_summary.services.adapters.base import window_bounds

logger = logging.getLogger(__name__)

MAX_OPPORTUNITIES = 5
MAX_COMPETITORS_SHOWN = 3


def get_opportunities(brand: Dict, period: str = '30') -> Dict:
    """Oportunidades por canal para los proyectos vinculados de la marca."""
    _previous_start, current_start, end = window_bounds(period)
    result = {'aio': [], 'llm': []}

    if brand.get('manual_ai_project_id'):
        try:
            result['aio'] = _aio_opportunities(brand['manual_ai_project_id'], current_start, end)
        except Exception as e:
            logger.error(f"AIO opportunities failed for brand {brand.get('id')}: {e}")

    if brand.get('llm_project_id'):
        try:
            result['llm'] = _llm_opportunities(brand['llm_project_id'], current_start, end)
        except Exception as e:
            logger.error(f"LLM opportunities failed for brand {brand.get('id')}: {e}")

    return result


def _aio_opportunities(project_id: int, current_start, end) -> List[Dict]:
    """
    Keywords con AI Overview en las que la marca no fue citada pero al menos
    un competidor seleccionado sí, ordenadas por frecuencia en la ventana.
    """
    with db_conn() as conn:
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("""
            SELECT r.keyword,
                   COUNT(DISTINCT r.analysis_date) AS times_missed,
                   MAX(r.analysis_date) AS last_seen,
                   ARRAY_AGG(DISTINCT g.detected_domain) AS competitors
            FROM manual_ai_results r
            JOIN manual_ai_global_domains g
              ON g.project_id = r.project_id
             AND g.keyword_id = r.keyword_id
             AND g.analysis_date = r.analysis_date
            WHERE r.project_id = %s
              AND r.analysis_date > %s AND r.analysis_date <= %s
              AND r.has_ai_overview = TRUE
              AND r.domain_mentioned = FALSE
              AND g.is_selected_competitor = TRUE
            GROUP BY r.keyword
            ORDER BY times_missed DESC, last_seen DESC
            LIMIT %s
        """, (project_id, current_start, end, MAX_OPPORTUNITIES))
        return [{
            'keyword': r['keyword'],
            'times_missed': r['times_missed'],
            'last_seen': r['last_seen'].isoformat(),
            'competitors': sorted(r['competitors'] or [])[:MAX_COMPETITORS_SHOWN],
        } for r in cur.fetchall()]


def _llm_opportunities(project_id: int, current_start, end) -> List[Dict]:
    """
    Prompts donde los LLMs mencionan competidores y no a la marca, agregados
    por prompt con los competidores más citados.
    """
    with db_conn() as conn:
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("""
            SELECT query_text, competitors_mentioned
            FROM llm_monitoring_results
            WHERE project_id = %s
              AND analysis_date > %s AND analysis_date <= %s
              AND brand_mentioned = FALSE
              AND competitors_mentioned IS NOT NULL
              AND competitors_mentioned != '{}'::jsonb
        """, (project_id, current_start, end))
        rows = cur.fetchall()

    by_prompt = defaultdict(lambda: {'times': 0, 'competitors': Counter()})
    for r in rows:
        breakdown = r['competitors_mentioned']
        if not isinstance(breakdown, dict) or not breakdown:
            continue
        entry = by_prompt[r['query_text']]
        entry['times'] += 1
        for name, value in breakdown.items():
            entry['competitors'][name] += _as_int(value)

    ranked = sorted(by_prompt.items(), key=lambda item: -item[1]['times'])
    return [{
        'prompt': prompt,
        'times_missed': data['times'],
        'competitors': [name for name, _count in data['competitors'].most_common(MAX_COMPETITORS_SHOWN)],
    } for prompt, data in ranked[:MAX_OPPORTUNITIES]]


def _as_int(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dict):
        return _as_int(value.get('mentions') or value.get('count') or 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
