#!/usr/bin/env python3
"""
Marca y repara resultados de Manual AI con AI Overview "collapsed" sin
contenido (ai_overview solo con page_token, sin text_blocks/references).

Contexto: hasta 2026-09 la expansión usaba engine=google + page_token, que
SerpAPI ignora, así que ~30% de los AIO se guardaban sin contenido
(has_ai_overview=True, domain_mentioned=False). Ver
manual_ai/services/analysis_service.py::_expand_collapsed_aio.

Modos (dry-run por defecto; --apply para escribir):

  mark       Añade ai_analysis_data.aio_expansion = {"status": "failed_legacy"}
             a todas las filas afectadas que no lo tengan. No cambia métricas:
             solo permite distinguirlas en consultas y en la UI.

  reanalyze  Vuelve a analizar las filas afectadas de HOY (--date debe ser la
             fecha del día: un page_token caduca en ~1 min y la SERP de un día
             pasado ya no se puede recuperar). Por fila: 2-4 llamadas SerpAPI.

Uso:
  python3 repair_collapsed_aio.py mark [--apply]
  python3 repair_collapsed_aio.py reanalyze --date 2026-09-26 [--project 26] [--apply]
"""

import argparse
import json
import logging
import sys
import time
from datetime import date

from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('repair_collapsed_aio')

COLLAPSED_WHERE = """
    has_ai_overview
    AND raw_serp_data->'ai_overview' ? 'page_token'
    AND NOT (raw_serp_data->'ai_overview' ? 'text_blocks')
    AND NOT (raw_serp_data->'ai_overview' ? 'references')
"""


def mark(apply: bool):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*) AS n FROM manual_ai_results
            WHERE {COLLAPSED_WHERE} AND NOT (ai_analysis_data ? 'aio_expansion')
        """)
        n = cur.fetchone()['n']
        logger.info(f"Filas collapsed sin marcar: {n}")
        if not apply:
            logger.info("Dry-run: no se escribe nada (usa --apply)")
            return
        cur.execute(f"""
            UPDATE manual_ai_results
            SET ai_analysis_data = COALESCE(ai_analysis_data, '{{}}'::jsonb)
                || jsonb_build_object('aio_expansion', jsonb_build_object(
                       'status', 'failed_legacy',
                       'error', 'expansion used engine=google (page_token ignored)'))
            WHERE {COLLAPSED_WHERE} AND NOT (ai_analysis_data ? 'aio_expansion')
        """)
        conn.commit()
        logger.info(f"Marcadas {cur.rowcount} filas")
    finally:
        conn.close()


def _replace_result(pid, kid, target_date, keyword, project, ai_result, serp_data, attempts=3):
    """DELETE + INSERT en una sola transacción: un corte nunca deja la keyword sin fila."""
    for attempt in range(1, attempts + 1):
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM manual_ai_results
                WHERE project_id = %s AND keyword_id = %s AND analysis_date = %s
            """, (pid, kid, target_date))
            cur.execute("""
                INSERT INTO manual_ai_results (
                    project_id, keyword_id, analysis_date, keyword, domain,
                    has_ai_overview, domain_mentioned, domain_position,
                    ai_elements_count, impact_score, raw_serp_data,
                    ai_analysis_data, country_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                pid, kid, target_date, keyword, project['domain'],
                ai_result.get('has_ai_overview', False),
                ai_result.get('domain_is_ai_source', False),
                ai_result.get('domain_ai_source_position'),
                ai_result.get('total_elements', 0),
                ai_result.get('impact_score', 0),
                json.dumps(serp_data), json.dumps(ai_result),
                project['country_code'],
            ))
            conn.commit()
            return
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
        finally:
            try:
                conn.close()
            except Exception:
                pass


def reanalyze(target_date: date, project_id, apply: bool):
    if target_date != date.today():
        sys.exit("reanalyze solo es válido para la fecha de hoy (la SERP de días pasados no se puede recuperar)")

    from manual_ai.services.analysis_service import AnalysisService
    from manual_ai.models.project_repository import ProjectRepository

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT project_id, keyword_id, keyword FROM manual_ai_results
            WHERE analysis_date = %s AND {COLLAPSED_WHERE}
              AND (%s::int IS NULL OR project_id = %s::int)
            ORDER BY project_id, keyword
        """, (target_date, project_id, project_id))
        rows = cur.fetchall()
    finally:
        conn.close()

    logger.info(f"Filas a re-analizar ({target_date}): {len(rows)} (coste estimado {2 * len(rows)}-{4 * len(rows)} llamadas SerpAPI)")
    if not apply:
        logger.info("Dry-run: no se llama a SerpAPI ni se escribe nada (usa --apply)")
        return

    service = AnalysisService()
    projects = {}
    stats = {'expanded': 0, 'refetched': 0, 'failed': 0, 'error': 0}
    for row in rows:
        pid, kid, keyword = row['project_id'], row['keyword_id'], row['keyword']
        if pid not in projects:
            projects[pid] = ProjectRepository.get_project_with_details(pid)
        project = projects[pid]
        try:
            ai_result, serp_data = service._analyze_keyword(keyword, project, kid)
        except Exception as e:
            stats['error'] += 1
            logger.warning(f"[{pid}] '{keyword}': error, se conserva la fila original: {e}")
            continue

        status = (ai_result.get('aio_expansion') or {}).get('status', 'refetched')
        try:
            _replace_result(pid, kid, target_date, keyword, project, ai_result, serp_data)
        except Exception as e:
            stats['error'] += 1
            logger.warning(f"[{pid}] '{keyword}': fallo al guardar, se conserva la fila original: {e}")
            continue
        stats[status] = stats.get(status, 0) + 1
        if ai_result.get('has_ai_overview'):
            try:
                service.domains_service.store_global_domains_detected(
                    project_id=pid, keyword_id=kid, keyword=keyword,
                    project_domain=project['domain'], ai_analysis_data=ai_result,
                    analysis_date=target_date, country_code=project['country_code'],
                    selected_competitors=project.get('selected_competitors', []),
                )
            except Exception as e:
                logger.warning(f"[{pid}] '{keyword}': fila guardada pero falló global_domains: {e}")
        logger.info(f"[{pid}] '{keyword}': {status}, mencionado={ai_result.get('domain_is_ai_source', False)}")

    logger.info(f"Resumen: {json.dumps(stats)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=['mark', 'reanalyze'])
    parser.add_argument('--date', type=date.fromisoformat, default=date.today())
    parser.add_argument('--project', type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    if args.mode == 'mark':
        mark(args.apply)
    else:
        reanalyze(args.date, args.project, args.apply)


if __name__ == '__main__':
    main()
