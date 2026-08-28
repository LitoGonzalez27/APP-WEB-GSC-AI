#!/usr/bin/env python3
"""
Reparación del histórico contaminado por enlaces google.com/goto.

Entre julio y agosto de 2026 SerpAPI devolvió tandas de SERPs con los enlaces
sin resolver (google.com/goto?url=<token>). Los payloads guardados en
``manual_ai_results.ai_analysis_data`` y ``ai_mode_results.raw_ai_mode_data``
conservan esos enlaces, así que los rankings históricos (que se calculan en
request-time desde el JSON guardado) pierden esas fuentes.

Este script repara los datos IN PLACE sin repetir ningún análisis (cero coste
SerpAPI): resuelve cada enlace goto con la misma cadena que usa la ingesta
(token → HTTP 302 de Google → metadata de la referencia) vía
``services.google_redirects.resolve_payload_redirects``.

Para manual_ai_results además re-evalúa el MÉTODO OFICIAL de detección del
dominio (``urls_match(ref_link, dominio_del_proyecto)``) sobre los enlaces ya
resueltos, y SOLO en una dirección: un ``domain_is_ai_source`` que era False
puede pasar a True (falso negativo causado por el goto); nunca al revés.

Uso:
    # Dry-run (no escribe nada): resumen de lo que cambiaría
    DATABASE_URL=postgresql://... python3 repair_goto_history.py

    # Aplicar los cambios
    DATABASE_URL=postgresql://... python3 repair_goto_history.py --apply

    # Acotar
    python3 repair_goto_history.py --table manual_ai --from 2026-08-01 --project 33
"""

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("repair_goto_history")

os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
if not os.environ["DATABASE_URL"]:
    sys.exit("Define DATABASE_URL con la BD a reparar (usa la de staging para probar primero).")

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

from services.google_redirects import resolve_payload_redirects  # noqa: E402
from services.utils import urls_match  # noqa: E402


def _recheck_domain_detection(data: dict, project_domain: str) -> bool:
    """
    Método oficial de services/ai_analysis.py sobre los links ya resueltos:
    si una referencia coincide ahora con el dominio del proyecto y la fila
    decía False, corrige el falso negativo. Devuelve True si cambió algo.
    """
    if not project_domain or data.get("domain_is_ai_source"):
        return False
    references = (data.get("debug_info") or {}).get("references_found") or []
    for ref in references:
        link = ref.get("link", "") if isinstance(ref, dict) else ""
        if link and urls_match(link, project_domain):
            data["domain_is_ai_source"] = True
            data["domain_ai_source_position"] = (ref.get("index") or 0) + 1
            data["domain_ai_source_link"] = link
            debug = data.setdefault("debug_info", {})
            debug["detection_method"] = "goto_repair_official_references"
            return True
    return False


def repair_table(conn, table: str, json_col: str, args) -> None:
    filters = [f"{json_col}::text LIKE '%%/goto?%%'"]
    params = []
    if args.date_from:
        filters.append("analysis_date >= %s")
        params.append(args.date_from)
    if args.date_to:
        filters.append("analysis_date <= %s")
        params.append(args.date_to)
    if args.project:
        filters.append("project_id = %s")
        params.append(args.project)

    join = ""
    select_domain = "NULL AS project_domain"
    if table == "manual_ai_results":
        join = "JOIN manual_ai_projects p ON p.id = t.project_id"
        select_domain = "p.domain AS project_domain"

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"""
        SELECT t.id, t.project_id, t.analysis_date, t.{json_col} AS payload, {select_domain}
        FROM {table} t {join}
        WHERE {' AND '.join(filters)}
        ORDER BY t.analysis_date, t.id
        """,
        params,
    )
    rows = cur.fetchall()
    logger.info(f"[{table}] {len(rows)} filas con enlaces goto")

    totals = {"via_token": 0, "via_http": 0, "via_metadata": 0, "unresolved": 0}
    updated = detection_fixed = 0

    for row in rows:
        data = row["payload"]
        if isinstance(data, str):
            data = json.loads(data)
        stats = resolve_payload_redirects(
            data, context=f"{table}#{row['id']} {row['analysis_date']}"
        )
        for key in totals:
            totals[key] += stats.get(key, 0)

        changed = stats["redirects"] > stats["unresolved"]
        if table == "manual_ai_results":
            if _recheck_domain_detection(data, row["project_domain"]):
                detection_fixed += 1
                changed = True

        if not changed:
            continue
        updated += 1
        if args.apply:
            write_cur = conn.cursor()
            write_cur.execute(
                f"UPDATE {table} SET {json_col} = %s WHERE id = %s",
                (json.dumps(data), row["id"]),
            )

    if args.apply:
        conn.commit()
    action = "actualizadas" if args.apply else "se actualizarían (dry-run)"
    logger.info(
        f"[{table}] {updated} filas {action} — enlaces: {totals['via_token']} por token, "
        f"{totals['via_http']} por HTTP, {totals['via_metadata']} por metadata, "
        f"{totals['unresolved']} sin resolver; detección de dominio corregida "
        f"(False→True): {detection_fixed}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Escribir los cambios (por defecto: dry-run)")
    parser.add_argument("--table", choices=["manual_ai", "ai_mode", "all"], default="all")
    parser.add_argument("--from", dest="date_from", help="analysis_date mínima (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="analysis_date máxima (YYYY-MM-DD)")
    parser.add_argument("--project", type=int, help="Limitar a un project_id")
    args = parser.parse_args()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    if not args.apply:
        conn.set_session(readonly=True)
    try:
        if args.table in ("manual_ai", "all"):
            repair_table(conn, "manual_ai_results", "ai_analysis_data", args)
        if args.table in ("ai_mode", "all"):
            repair_table(conn, "ai_mode_results", "raw_ai_mode_data", args)
    finally:
        conn.close()
    if not args.apply:
        logger.info("Dry-run terminado. Repite con --apply para escribir los cambios.")


if __name__ == "__main__":
    main()
