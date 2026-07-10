"""
Adapter del canal LLMs (módulo LLM Monitoring: ChatGPT, Claude, Gemini, Perplexity).

Lee los snapshots diarios (llm_monitoring_snapshots, una fila por LLM y día)
y los agrega a métricas de canal: mention rate (visibilidad), share of voice,
sentimiento y desglose por LLM y por competidor.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from database import db_conn
from services.utils import normalize_search_console_url
from ai_summary.services.adapters.base import (
    empty_channel, window_bounds, ranking_days, split_windows, avg, delta, rounded
)

logger = logging.getLogger(__name__)

CHANNEL = 'llm'

PROVIDER_LABELS = {
    'openai': 'ChatGPT',
    'anthropic': 'Claude',
    'google': 'Gemini',
    'perplexity': 'Perplexity',
}


def get_channel_summary(project_id: int, period: str = '30') -> Dict:
    summary = empty_channel(CHANNEL)
    summary['project_id'] = project_id

    previous_start, current_start, end = window_bounds(period)

    with db_conn() as conn:
        if not conn:
            summary['reason'] = 'error'
            return summary
        cur = conn.cursor()

        cur.execute("""
            SELECT name, brand_domain, selected_competitors, competitor_domains, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()
        if not project:
            return summary
        summary['project_name'] = project['name']

        cur.execute("""
            SELECT snapshot_date, llm_provider, total_queries, total_mentions,
                   mention_rate, share_of_voice, avg_position,
                   positive_mentions, neutral_mentions, negative_mentions,
                   total_competitor_mentions, competitor_breakdown
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
              AND snapshot_date > %s AND snapshot_date <= %s
            ORDER BY snapshot_date ASC
        """, (project_id, previous_start, end))
        rows = cur.fetchall()

    previous, current = split_windows(rows, 'snapshot_date', current_start)
    mention_rate = _weighted_rate(current, 'mention_rate') if current else None
    # mention_rate None con filas presentes = snapshots parciales/corruptos:
    # el canal no puede puntuar y el frontend lo trata como sin datos.
    if not current or mention_rate is None:
        summary['reason'] = 'no_data'
        return summary
    sov = _weighted_rate(current, 'share_of_voice')
    position = avg([r['avg_position'] for r in current])

    summary.update({
        'available': True,
        'reason': None,
        'visibility_pct': rounded(mention_rate),
        'visibility_delta': delta(mention_rate, _weighted_rate(previous, 'mention_rate')),
        'avg_position': rounded(position),
        'position_delta': delta(position, avg([r['avg_position'] for r in previous])),
        'timeseries': _daily_series(current),
        'last_date': current[-1]['snapshot_date'].isoformat(),
        'competitors': _competitor_sov(project, current),
        'extras': {
            'share_of_voice': rounded(sov),
            'sov_delta': delta(sov, _weighted_rate(previous, 'share_of_voice')),
            'sentiment': _sentiment_distribution(current),
            'by_llm': _by_llm(current),
            # Ventana anterior por proveedor: necesaria para calcular el
            # delta del score cuando la marca pondera LLMs individualmente
            'by_llm_previous': _by_llm(previous) if previous else {},
        },
    })
    return summary


# ----------------------------------------------------------------------
# Agregaciones
# ----------------------------------------------------------------------

def _weighted_rate(rows: List[Dict], field: str) -> Optional[float]:
    """Media de un porcentaje ponderada por queries analizadas ese día/LLM."""
    total_weight = 0
    weighted_sum = 0.0
    for r in rows:
        if r[field] is None:
            continue
        weight = r['total_queries'] or 0
        total_weight += weight
        weighted_sum += float(r[field]) * weight
    if not total_weight:
        return avg([r[field] for r in rows])
    return weighted_sum / total_weight


def _daily_series(rows: List[Dict]) -> List[Dict]:
    """Mention rate diario agregando todos los LLMs (ponderado por queries)."""
    by_date = defaultdict(list)
    for r in rows:
        by_date[r['snapshot_date']].append(r)
    return [
        {'date': day.isoformat(), 'value': rounded(_weighted_rate(day_rows, 'mention_rate'))}
        for day, day_rows in sorted(by_date.items())
    ]


def _by_llm(rows: List[Dict]) -> Dict:
    by_provider = defaultdict(list)
    for r in rows:
        by_provider[r['llm_provider']].append(r)
    return {
        provider: {
            'label': PROVIDER_LABELS.get(provider, provider),
            'mention_rate': rounded(_weighted_rate(provider_rows, 'mention_rate')),
            'share_of_voice': rounded(_weighted_rate(provider_rows, 'share_of_voice')),
            'avg_position': rounded(avg([r['avg_position'] for r in provider_rows])),
        }
        for provider, provider_rows in sorted(by_provider.items())
    }


def _sentiment_distribution(rows: List[Dict]) -> Dict:
    positive = sum(r['positive_mentions'] or 0 for r in rows)
    neutral = sum(r['neutral_mentions'] or 0 for r in rows)
    negative = sum(r['negative_mentions'] or 0 for r in rows)
    total = positive + neutral + negative
    if not total:
        return {'positive': None, 'neutral': None, 'negative': None}
    return {
        'positive': round(positive / total * 100, 1),
        'neutral': round(neutral / total * 100, 1),
        'negative': round(negative / total * 100, 1),
    }


def _competitor_sov(project: Dict, rows: List[Dict]) -> List[Dict]:
    """
    Share of voice de marca vs competidores agregando competitor_breakdown
    del periodo. Los breakdowns usan nombres de competidor; se mapean a dominio
    con selected_competitors / competitor_domains del proyecto.
    """
    brand_mentions = sum(r['total_mentions'] or 0 for r in rows)
    competitor_mentions = defaultdict(int)

    for r in rows:
        breakdown = r['competitor_breakdown'] or {}
        if not isinstance(breakdown, dict):
            continue
        for name, value in breakdown.items():
            competitor_mentions[name] += _as_int(value)

    name_to_domain = _competitor_domain_map(project)
    total = brand_mentions + sum(competitor_mentions.values())
    if not total:
        return []

    entries = [{
        'domain': normalize_search_console_url(project.get('brand_domain') or '') or (project.get('brand_domain') or ''),
        'visibility_pct': round(brand_mentions / total * 100, 1),
        'mentions': brand_mentions,
        'is_brand': True,
        'is_selected_competitor': False,
    }]
    for name, mentions in competitor_mentions.items():
        entries.append({
            'domain': name_to_domain.get(name.lower(), name.lower()),
            'visibility_pct': round(mentions / total * 100, 1),
            'mentions': mentions,
            'is_brand': False,
            'is_selected_competitor': True,
        })

    entries.sort(key=lambda e: -(e['mentions'] or 0))
    for rank, entry in enumerate(entries, start=1):
        entry['rank'] = rank
    return entries


def _competitor_domain_map(project: Dict) -> Dict[str, str]:
    """
    Mapa nombre→dominio para resolver las claves de competitor_breakdown.
    Fuentes, de menor a mayor prioridad: competitor_domains legacy (se indexa
    por su primera etiqueta, p.ej. 'fortuneo' → fortuneo.com) y
    selected_competitors (estructura nueva con name+domain explícitos).
    """
    mapping = {}
    legacy_domains = project.get('competitor_domains') or []
    if isinstance(legacy_domains, list):
        for domain in legacy_domains:
            normalized = normalize_search_console_url(str(domain))
            if normalized:
                mapping[normalized.split('.')[0]] = normalized
    selected = project.get('selected_competitors') or []
    if isinstance(selected, list):
        for comp in selected:
            if isinstance(comp, dict) and comp.get('name') and comp.get('domain'):
                mapping[str(comp['name']).lower()] = normalize_search_console_url(comp['domain'])
    return mapping


def _as_int(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dict):
        # Algunos breakdowns históricos guardan {"mentions": N, ...}
        return _as_int(value.get('mentions') or value.get('count') or 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
