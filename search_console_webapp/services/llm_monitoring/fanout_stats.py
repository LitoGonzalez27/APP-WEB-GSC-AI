"""
Métricas de query fan-out para el panel y las exportaciones de LLM Monitoring (P7).

Solo existen para proyectos con `search_mode='auto'`: con 'off' el panel, el modal y
las exportaciones siguen exactamente igual que antes (decisión de Carlos, 2026-09-14).

- `collect_fanout_metrics` es la única fuente de estas métricas: la usan el endpoint
  GET /projects/<id>/fanout, el Excel y el PDF, así que nunca pueden divergir.
- `aggregate_fanout` es pura (sin BD) para poder testearla.

Solo cuentan las respuestas con búsqueda activada desde la última activación del
proyecto (`search_enabled_at`): Perplexity ya guardaba fan-out en proyectos 'off' y
esas filas no forman parte de esta vista.
"""

from collections import Counter, defaultdict
from datetime import date
from typing import Dict, Iterable, List, Optional

from services.llm_providers.fanout_utils import host_matches_domain, normalize_domain
from services.llm_providers.web_search import is_search_enabled

PAGE_ACTIONS = ('open_page', 'find_in_page', 'fetch_url')

TOP_QUERIES_LIMIT = 100
TOP_PAGES_LIMIT = 25
VARIANTS_LIMIT = 5
PROMPTS_LIMIT = 5


def project_competitor_domains(project: Dict) -> List[str]:
    """Dominios de competidores del proyecto (estructura nueva o campos legacy)."""
    domains = [c.get('domain') for c in (project.get('selected_competitors') or []) if isinstance(c, dict)]
    domains += list(project.get('competitor_domains') or [])
    return [d for d in dict.fromkeys(normalize_domain(d) for d in domains) if d]


def _rate(part: int, total: int) -> Optional[float]:
    return round(part / total, 4) if total else None


def aggregate_fanout(results: Iterable[Dict], fanout_rows: Iterable[Dict], *,
                     prompt_texts: Dict[int, str], brand_domain: Optional[str],
                     competitor_domains: List[str]) -> Dict:
    """
    `results`: una fila por respuesta con búsqueda activada
        {id, llm_provider, query_id, search_used, search_calls, page_opens}.
    `fanout_rows`: filas de llm_monitoring_fanout_queries de esas respuestas
        {result_id, llm_provider, query_id, action, query_text, query_normalized, url, url_host, brand_in_sources}.
    """
    results = list(results)
    brand = normalize_domain(brand_domain)
    competitors = [normalize_domain(d) for d in competitor_domains if normalize_domain(d)]

    by_result_brand: Dict[int, Optional[bool]] = {}
    queries: Dict[str, Dict] = {}
    pages: Dict[str, Dict] = {}

    for row in fanout_rows:
        action = row.get('action')
        if action == 'search':
            key = row.get('query_normalized') or (row.get('query_text') or '').strip().lower()
            if not key:
                continue
            group = queries.setdefault(key, {
                'rows': 0, 'results': set(), 'providers': Counter(), 'variants': Counter(),
                'prompts': Counter(), 'brand_known': 0, 'brand_hits': 0,
            })
            group['rows'] += 1
            group['results'].add(row['result_id'])
            group['providers'][row['llm_provider']] += 1
            if row.get('query_text'):
                group['variants'][row['query_text']] += 1
            group['prompts'][row['query_id']] += 1
            if row.get('brand_in_sources') is not None:
                group['brand_known'] += 1
                group['brand_hits'] += int(bool(row['brand_in_sources']))
                previous = by_result_brand.get(row['result_id'])
                by_result_brand[row['result_id']] = bool(previous) or bool(row['brand_in_sources'])
        elif action in PAGE_ACTIONS and row.get('url'):
            page = pages.setdefault(row['url'], {'host': normalize_domain(row.get('url_host') or row['url']),
                                                 'count': 0, 'providers': Counter()})
            page['count'] += 1
            page['providers'][row['llm_provider']] += 1

    by_llm: Dict[str, Dict] = defaultdict(lambda: {'responses': 0, 'searched': 0, 'searches': 0, 'page_opens': 0,
                                                   'brand_known': 0, 'brand_hits': 0})
    for result in results:
        stats = by_llm[result['llm_provider']]
        stats['responses'] += 1
        if result.get('search_used'):
            stats['searched'] += 1
            stats['searches'] += int(result.get('search_calls') or 0)
            stats['page_opens'] += int(result.get('page_opens') or 0)
        if result['id'] in by_result_brand:
            stats['brand_known'] += 1
            stats['brand_hits'] += int(by_result_brand[result['id']])

    total_responses = len(results)
    top_queries = sorted(queries.items(), key=lambda kv: (-len(kv[1]['results']), -kv[1]['rows'], kv[0]))
    return {
        'responses': total_responses,
        'responses_with_search': sum(s['searched'] for s in by_llm.values()),
        'by_llm': [{
            'llm_provider': llm,
            'responses': s['responses'],
            'searched': s['searched'],
            'search_rate': _rate(s['searched'], s['responses']),
            'avg_searches': round(s['searches'] / s['searched'], 1) if s['searched'] else None,
            'avg_page_opens': round(s['page_opens'] / s['searched'], 1) if s['searched'] else None,
            # None si el proveedor no atribuye fuentes a cada búsqueda (Gemini)
            'brand_in_results_rate': _rate(s['brand_hits'], s['brand_known']) if s['brand_known'] else None,
        } for llm, s in sorted(by_llm.items())],
        'top_queries': [{
            'key': key,
            'query': group['variants'].most_common(1)[0][0] if group['variants'] else key,
            'count': group['rows'],
            'responses': len(group['results']),
            'share': _rate(len(group['results']), total_responses),
            'providers': dict(group['providers']),
            'brand_in_results_rate': _rate(group['brand_hits'], group['brand_known']) if group['brand_known'] else None,
            'variants': [{'query': q, 'count': n} for q, n in group['variants'].most_common(VARIANTS_LIMIT)],
            'variants_total': len(group['variants']),
            'prompts': [{'query_id': qid, 'prompt': prompt_texts.get(qid), 'count': n}
                        for qid, n in group['prompts'].most_common(PROMPTS_LIMIT)],
        } for key, group in top_queries[:TOP_QUERIES_LIMIT]],
        'top_queries_total': len(queries),
        'brand_pages': _page_list(pages, lambda host: bool(brand) and host_matches_domain(host, brand)),
        'competitor_pages': _page_list(
            pages, lambda host: any(host_matches_domain(host, d) for d in competitors),
            competitor_of=lambda host: next((d for d in competitors if host_matches_domain(host, d)), None),
        ),
    }


def _page_list(pages: Dict[str, Dict], include, competitor_of=None) -> List[Dict]:
    selected = [(url, page) for url, page in pages.items() if include(page['host'])]
    selected.sort(key=lambda kv: (-kv[1]['count'], kv[0]))
    return [{
        'url': url,
        'host': page['host'],
        'count': page['count'],
        'providers': dict(page['providers']),
        **({'competitor': competitor_of(page['host'])} if competitor_of else {}),
    } for url, page in selected[:TOP_PAGES_LIMIT]]


def collect_fanout_metrics(cur, project: Dict, *, start_date: date, end_date: date,
                           enabled_llms: Optional[List[str]] = None,
                           query_ids: Optional[List[int]] = None) -> Dict:
    """
    Métricas de fan-out del proyecto en el rango. Si el proyecto no tiene la búsqueda
    activada devuelve {'enabled': False} sin consultar nada más.
    """
    if not is_search_enabled(project.get('search_mode')) or not project.get('search_enabled_at'):
        return {'enabled': False}

    enabled_at = project['search_enabled_at']
    since = max(start_date, enabled_at.date() if hasattr(enabled_at, 'date') else enabled_at)
    conditions = [
        "r.project_id = %s", "r.analysis_date >= %s", "r.analysis_date <= %s",
        "COALESCE(r.has_error, FALSE) = FALSE", "r.execution_metadata->>'search_mode' = 'auto'",
    ]
    params: List = [project['id'], since, end_date]
    if enabled_llms is not None:
        conditions.append("r.llm_provider = ANY(%s)")
        params.append(list(enabled_llms))
    if query_ids is not None:
        conditions.append("r.query_id = ANY(%s)")
        params.append(list(query_ids))
    where = ' AND '.join(conditions)

    cur.execute(f"""
        SELECT r.id, r.llm_provider, r.query_id,
               (r.execution_metadata->>'search_used')::boolean AS search_used,
               NULLIF(r.execution_metadata->>'search_calls', '')::int AS search_calls,
               NULLIF(r.execution_metadata->>'page_opens', '')::int AS page_opens
        FROM llm_monitoring_results r
        WHERE {where}
    """, params)
    results = [dict(row) for row in cur.fetchall()]

    fanout_rows: List[Dict] = []
    prompt_texts: Dict[int, str] = {}
    if results:
        cur.execute(f"""
            SELECT f.result_id, f.llm_provider, f.query_id, f.action, f.query_text, f.query_normalized,
                   f.url, f.url_host, f.brand_in_sources
            FROM llm_monitoring_fanout_queries f
            JOIN llm_monitoring_results r ON r.id = f.result_id
            WHERE {where}
            ORDER BY f.result_id, f.position
        """, params)
        fanout_rows = [dict(row) for row in cur.fetchall()]
        cur.execute("SELECT id, query_text FROM llm_monitoring_queries WHERE id = ANY(%s)",
                    (sorted({r['query_id'] for r in results}),))
        prompt_texts = {row['id']: row['query_text'] for row in cur.fetchall()}

    metrics = aggregate_fanout(
        results, fanout_rows, prompt_texts=prompt_texts,
        brand_domain=project.get('brand_domain'),
        competitor_domains=project_competitor_domains(project),
    )
    return {
        'enabled': True,
        'search_enabled_at': enabled_at.isoformat() if hasattr(enabled_at, 'isoformat') else enabled_at,
        'period': {'start_date': since.isoformat(), 'end_date': end_date.isoformat()},
        **metrics,
    }


def response_search_detail(execution_metadata: Optional[Dict], search_queries: Optional[List[Dict]]) -> Optional[Dict]:
    """
    Bloque "How the model searched" del modal de una respuesta. None si la respuesta
    no se generó con la búsqueda activada (proyectos 'off' o filas anteriores).
    """
    metadata = execution_metadata or {}
    if not is_search_enabled(metadata.get('search_mode')):
        return None
    items = search_queries or []
    return {
        'used': bool(metadata.get('search_used')),
        'calls': int(metadata.get('search_calls') or 0),
        'page_opens': int(metadata.get('page_opens') or 0),
        'tool': metadata.get('search_tool'),
        'model_reported': metadata.get('model_reported'),
        'searches': [{'round': q.get('round'), 'query': q.get('query'), 'sources': q.get('sources') or []}
                     for q in items if q.get('action') == 'search'],
        'pages': [{'round': q.get('round'), 'action': q.get('action'), 'url': q.get('url'), 'pattern': q.get('query')}
                  for q in items if q.get('action') in PAGE_ACTIONS],
    }


LLM_LABELS = {'openai': 'ChatGPT', 'anthropic': 'Claude', 'google': 'Gemini', 'perplexity': 'Perplexity'}

def _pct(rate: Optional[float]) -> str:
    return '' if rate is None else f"{round(rate * 100)}%"


def _providers_text(providers: Dict[str, int]) -> str:
    return ', '.join(f"{LLM_LABELS.get(llm, llm)} {n}" for llm, n in sorted(providers.items(), key=lambda kv: -kv[1]))


def fanout_export_tables(metrics: Dict) -> Dict[str, List[List]]:
    """Filas (cabecera incluida) que comparten la hoja de Excel y la sección del PDF."""
    by_llm = [["Model", "Answers", "Searched the web", "Searches per answer", "Pages read per answer", "Your brand in results"]]
    for row in metrics.get('by_llm') or []:
        by_llm.append([
            LLM_LABELS.get(row['llm_provider'], row['llm_provider']), row['responses'],
            _pct(row['search_rate']), row['avg_searches'] if row['avg_searches'] is not None else '',
            row['avg_page_opens'] if row['avg_page_opens'] is not None else '',
            _pct(row['brand_in_results_rate']) or 'Not reported',
        ])
    queries = [["#", "Sub-query", "Answers", "% of answers", "Models", "Your brand in results", "Variants"]]
    for i, q in enumerate(metrics.get('top_queries') or [], 1):
        queries.append([i, q['query'], q['responses'], _pct(q['share']), _providers_text(q['providers']),
                        _pct(q['brand_in_results_rate']) or 'Not reported', q['variants_total']])
    pages = [["Owner", "URL", "Times read", "Models"]]
    for label, key in (("Your brand", 'brand_pages'), ("Competitor", 'competitor_pages')):
        for p in metrics.get(key) or []:
            owner = label if key == 'brand_pages' else f"Competitor ({p.get('competitor')})"
            pages.append([owner, p['url'], p['count'], _providers_text(p['providers'])])
    return {'by_llm': by_llm, 'queries': queries, 'pages': pages}
