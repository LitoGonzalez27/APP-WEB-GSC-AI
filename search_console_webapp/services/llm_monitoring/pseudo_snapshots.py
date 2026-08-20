"""
Pseudo-snapshots — LLM Visibility Monitor

Los snapshots reales (llm_monitoring_snapshots) se agregan en el momento del
análisis sobre TODOS los prompts del proyecto, así que no pueden filtrarse
retroactivamente por prompt_set o cluster. Cuando el informe se pide con un
filtro activo, este módulo recalcula al vuelo, desde llm_monitoring_results,
filas con la MISMA forma que las de snapshots: los endpoints intercambian la
fuente y su lógica aguas abajo no cambia.

La matemática replica services/llm_monitoring/snapshot.py::_create_snapshot
(mention rate, SOV normal y ponderado por posición, breakdown de competidores,
sentimiento). Si se toca una, tocar la otra.
"""

import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Igual que snapshot.py: posiciones > 30 son falsos positivos (años, canales…)
MAX_VALID_POSITION = 30


def _weight_for_position(position):
    """Ponderación por posición — idéntica a snapshot.py::_calculate_weighted_mentions."""
    if position is None:
        return 1.0
    if position <= 3:
        return 2.0
    if position <= 5:
        return 1.5
    if position <= 10:
        return 1.2
    return 0.8


def _parse_competitors_mentioned(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def compute_snapshot_row(snapshot_date, llm_provider, llm_results):
    """
    Agrega los results de UN LLM en UNA fecha a una fila con la forma de
    llm_monitoring_snapshots. `llm_results` son dicts de BD con al menos:
    brand_mentioned, position_in_list, competitors_mentioned, sentiment,
    sentiment_score, cost_usd, tokens_used.
    """
    total_queries = len(llm_results)
    if total_queries == 0:
        return None

    mentions = [r for r in llm_results if r.get('brand_mentioned')]
    total_mentions = len(mentions)
    mention_rate = (total_mentions / total_queries) * 100

    positions = [
        r['position_in_list'] for r in llm_results
        if r.get('position_in_list') is not None
        and r['position_in_list'] <= MAX_VALID_POSITION
    ]
    avg_position = sum(positions) / len(positions) if positions else None

    # Competidores: breakdown normal y ponderado (1 mención por query)
    competitor_breakdown = defaultdict(int)
    weighted_competitor_breakdown = defaultdict(float)
    weighted_brand = 0.0
    for r in llm_results:
        weight = _weight_for_position(r.get('position_in_list'))
        if r.get('brand_mentioned'):
            weighted_brand += weight
        comp_mentions = _parse_competitors_mentioned(r.get('competitors_mentioned'))
        for comp, count in comp_mentions.items():
            try:
                mentioned = (count or 0) > 0
            except TypeError:
                mentioned = False
            if mentioned:
                competitor_breakdown[comp] += 1
                weighted_competitor_breakdown[comp] += weight

    total_competitor_mentions = sum(competitor_breakdown.values())
    total_all = total_mentions + total_competitor_mentions
    share_of_voice = (total_mentions / total_all * 100) if total_all > 0 else 0

    weighted_comp_total = sum(weighted_competitor_breakdown.values())
    weighted_total = weighted_brand + weighted_comp_total
    weighted_share_of_voice = (
        (weighted_brand / weighted_total * 100) if weighted_total > 0 else 0
    )

    positive = sum(1 for r in llm_results if r.get('sentiment') == 'positive')
    neutral = sum(1 for r in llm_results if r.get('sentiment') == 'neutral')
    negative = sum(1 for r in llm_results if r.get('sentiment') == 'negative')
    scores = [float(r['sentiment_score']) for r in llm_results if r.get('sentiment_score')]
    avg_sentiment_score = sum(scores) / len(scores) if scores else 0.5

    total_cost = sum(float(r.get('cost_usd') or 0) for r in llm_results)
    total_tokens = sum(int(r.get('tokens_used') or 0) for r in llm_results)
    response_times = [int(r['response_time_ms']) for r in llm_results if r.get('response_time_ms')]
    avg_response_time = (
        int(sum(response_times) / len(response_times)) if response_times else 0
    )

    return {
        # Misma forma (claves) que una fila de llm_monitoring_snapshots
        'id': None,
        'snapshot_date': snapshot_date,
        'llm_provider': llm_provider,
        'total_queries': total_queries,
        'total_mentions': total_mentions,
        'mention_rate': round(mention_rate, 2),
        'avg_position': round(avg_position, 2) if avg_position else None,
        'appeared_in_top3': sum(1 for p in positions if p <= 3),
        'appeared_in_top5': sum(1 for p in positions if p <= 5),
        'appeared_in_top10': sum(1 for p in positions if p <= 10),
        'total_competitor_mentions': total_competitor_mentions,
        'share_of_voice': round(share_of_voice, 2),
        'competitor_breakdown': dict(competitor_breakdown),
        'weighted_share_of_voice': round(weighted_share_of_voice, 2),
        'weighted_competitor_breakdown': {
            k: round(v, 2) for k, v in weighted_competitor_breakdown.items()
        },
        'positive_mentions': positive,
        'neutral_mentions': neutral,
        'negative_mentions': negative,
        'avg_sentiment_score': round(avg_sentiment_score, 2),
        'avg_response_time_ms': avg_response_time,
        'total_cost_usd': round(total_cost, 4),
        'total_tokens': total_tokens,
    }


def build_pseudo_snapshots(cur, project_id, query_ids, start_date, end_date=None,
                           enabled_llms=None, llm_provider=None):
    """
    Filas con forma de snapshot calculadas al vuelo para un subconjunto de
    prompts. Devuelve lista ordenada por (snapshot_date, llm_provider).

    query_ids vacío → []. end_date None → sin cota superior.
    """
    if not query_ids:
        return []

    sql = """
        SELECT r.analysis_date, r.llm_provider, r.brand_mentioned,
               r.position_in_list, r.competitors_mentioned,
               r.sentiment, r.sentiment_score, r.cost_usd, r.tokens_used,
               r.response_time_ms
        FROM llm_monitoring_results r
        WHERE r.project_id = %s
          AND r.query_id = ANY(%s)
          AND r.analysis_date >= %s
    """
    params = [project_id, list(query_ids), start_date]
    if end_date:
        sql += " AND r.analysis_date <= %s"
        params.append(end_date)
    if llm_provider:
        sql += " AND r.llm_provider = %s"
        params.append(llm_provider)
    elif enabled_llms:
        sql += " AND r.llm_provider = ANY(%s)"
        params.append(enabled_llms)
    cur.execute(sql, params)

    grouped = defaultdict(list)
    for row in cur.fetchall():
        grouped[(row['analysis_date'], row['llm_provider'])].append(row)

    rows = []
    for (snap_date, provider) in sorted(grouped.keys(), key=lambda k: (k[0], k[1])):
        computed = compute_snapshot_row(snap_date, provider, grouped[(snap_date, provider)])
        if computed:
            rows.append(computed)
    return rows
