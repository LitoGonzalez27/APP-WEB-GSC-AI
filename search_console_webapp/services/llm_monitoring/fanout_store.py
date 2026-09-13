"""
Persistencia del query fan-out de LLM Monitoring.

Cada respuesta con búsqueda guarda:
- `llm_monitoring_results.search_queries` (JSONB, detalle tal cual lo devuelve el provider)
- una fila por sub-consulta o página abierta en `llm_monitoring_fanout_queries`
  (para agregar por proyecto, prompt, proveedor o dominio sin recorrer JSONB).

Esquema: migrate_llm_fanout_schema.py. Si la migración aún no se ha ejecutado en
un entorno, `fanout_schema_available()` devuelve False y el engine sigue
guardando resultados como siempre, sin fan-out.
"""

import json
import logging
import threading
import time
from typing import Dict, Iterable, List, Optional

from psycopg2.extras import execute_values

from services.llm_providers.fanout_utils import (
    host_matches_domain,
    normalize_domain,
    normalize_query,
)

logger = logging.getLogger(__name__)

PAGE_ACTIONS = ('open_page', 'find_in_page', 'fetch_url')

SCHEMA_RECHECK_SECONDS = 300

_schema_lock = threading.Lock()
_schema_available = False
_schema_checked_at = 0.0


def fanout_schema_available(get_connection) -> bool:
    """
    ¿Existen ya las columnas/tabla del fan-out? El True se cachea para siempre; el
    False se vuelve a comprobar cada SCHEMA_RECHECK_SECONDS (tras migrar empieza a
    escribir sin reiniciar y, mientras falte, no se consulta el catálogo por tarea).
    """
    global _schema_available, _schema_checked_at
    if _schema_available:
        return True
    with _schema_lock:
        if _schema_available or time.monotonic() - _schema_checked_at < SCHEMA_RECHECK_SECONDS:
            return _schema_available
        _schema_checked_at = time.monotonic()
        conn = get_connection()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    to_regclass('public.llm_monitoring_fanout_queries') IS NOT NULL AS has_table,
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'llm_monitoring_results' AND column_name = 'search_queries'
                    ) AS has_column
            """)
            row = cur.fetchone()
            available = bool(row['has_table'] and row['has_column'])
        except Exception as e:
            logger.warning(f"No se pudo comprobar el esquema de fan-out: {e}")
            available = False
        finally:
            conn.close()
        _schema_available = available
        if not available:
            logger.warning("Esquema de fan-out ausente: ejecutar migrate_llm_fanout_schema.py")
        return available


def _matching_competitors(hosts: Iterable[str], competitor_domains: List[str]) -> List[str]:
    matched = []
    for domain in competitor_domains:
        if domain and any(host_matches_domain(host, domain) for host in hosts):
            matched.append(domain)
    return matched


def build_fanout_rows(search_queries: List[Dict], *, brand_domain: Optional[str],
                      competitor_domains: Optional[List[str]]) -> List[Dict]:
    """
    Filas de llm_monitoring_fanout_queries a partir del `search_queries` del provider.

    `brand_in_sources` solo tiene sentido si el proveedor atribuye resultados a
    cada búsqueda (OpenAI, Anthropic, Perplexity). Gemini devuelve las fuentes en
    una lista aparte: sus búsquedas llegan con `sources=[]` y quedan en NULL.
    """
    brand = normalize_domain(brand_domain)
    competitors = [d for d in (normalize_domain(c) for c in (competitor_domains or [])) if d]
    attributable = any(q.get('sources') for q in search_queries if q.get('action') == 'search')

    rows = []
    for position, item in enumerate(search_queries):
        action = item.get('action')
        sources = [s for s in (item.get('sources') or []) if s]
        source_hosts = [normalize_domain(s) for s in sources]

        if action == 'search':
            brand_in_sources = (
                any(host_matches_domain(h, brand) for h in source_hosts)
                if attributable and brand else None
            )
            url_host = None
            competitor_hosts = _matching_competitors(source_hosts, competitors)
        elif action in PAGE_ACTIONS:
            url_host = normalize_domain(item.get('url')) or None
            brand_in_sources = None
            competitor_hosts = _matching_competitors([url_host] if url_host else [], competitors)
        else:
            logger.debug(f"Acción de fan-out desconocida ignorada: {action}")
            continue

        rows.append({
            'round': int(item.get('round') or 0),
            'position': position,
            'action': action,
            'query_text': item.get('query'),
            'query_normalized': normalize_query(item.get('query')) or None,
            'url': item.get('url'),
            'url_host': url_host,
            'sources': sources,
            'brand_in_sources': brand_in_sources,
            'competitor_hosts': competitor_hosts,
        })
    return rows


def save_fanout(cur, *, result_id: int, task: Dict, search_queries: List[Dict]) -> int:
    """
    Reemplaza las filas de fan-out de un resultado (el UPSERT diario puede
    reescribir la misma fila). Usa el cursor/transacción del llamador.
    """
    cur.execute("DELETE FROM llm_monitoring_fanout_queries WHERE result_id = %s", (result_id,))
    rows = build_fanout_rows(
        search_queries,
        brand_domain=task.get('brand_domain'),
        competitor_domains=task.get('competitor_domains'),
    )
    if not rows:
        return 0
    execute_values(cur, """
        INSERT INTO llm_monitoring_fanout_queries (
            result_id, project_id, query_id, llm_provider, analysis_date,
            round, position, action, query_text, query_normalized,
            url, url_host, sources, brand_in_sources, competitor_hosts
        ) VALUES %s
    """, [(
        result_id, task['project_id'], task['query_id'], task['llm_name'], task['analysis_date'],
        r['round'], r['position'], r['action'], r['query_text'], r['query_normalized'],
        r['url'], r['url_host'], json.dumps(r['sources']), r['brand_in_sources'], r['competitor_hosts'],
    ) for r in rows])
    return len(rows)
