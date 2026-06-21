"""
Seed de DEMO para la comparación histórica de AI Overview (solo STAGING).

Crea (idempotente) un proyecto Manual AI autocontenido bajo el owner indicado,
con keywords, 2 competidores y 7 fechas de análisis repartidas en 90 días, con
un relato claro de keywords ganadas / perdidas / mantenidas tanto para el
dominio del proyecto como para los competidores. Rellena manual_ai_results
(con ai_analysis_data.references_found) y manual_ai_global_domains, de modo que
TODO el dashboard (charts, rankings, tabla y el nuevo modal "See historic")
quede poblado.

SEGURIDAD: aborta si el host de la BD parece producción (switchyard). Pensado
para ejecutarse con la DATABASE_PUBLIC_URL de staging (caboose).

Uso:
    DATABASE_URL="$STAGING_PUBLIC_URL" python3 scripts_seed_historical_demo.py
"""

import os
import re
import json
from datetime import date, timedelta
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

OWNER_USER_ID = 5
PROJECT_NAME = "Demo · Histórico AI Overview"
PROJECT_DOMAIN = "asana.com"
COUNTRY = "US"
COMPETITORS = ["monday.com", "trello.com"]

# Fechas (offset de días hacia atrás desde hoy), de más antigua a más reciente
TODAY = date.today()
OFFSETS = [89, 60, 29, 14, 6, 3, 0]
DATES = [TODAY - timedelta(days=o) for o in OFFSETS]  # index 0..6 (viejo→nuevo)

# Dominios genéricos (no rastreados) para enriquecer rankings de dominios/URLs
GENERIC = ["g2.com", "wikipedia.org"]

# Perfiles por keyword: posición por fecha (None = no mencionado ese día).
# Índices alineados con DATES (0=hace 89d ... 6=hoy).
KEYWORDS = {
    "best project management software": {
        "asana.com":  [5, 5, 4, 4, 3, 2, 2],
        "monday.com": [3, 3, 2, 2, 2, 1, 1],
        "trello.com": [None]*7,
        "g2.com":     [1, 1, 1, 1, 1, 3, 3],
    },
    "task management tool": {
        "asana.com":  [2, 2, 3, 4, 5, 6, 6],
        "monday.com": [None, None, 4, 4, 3, 3, 2],
        "trello.com": [6, 6, 6, 5, 5, 5, 5],
    },
    "agile project tracking": {
        "asana.com":  [4, 4, 4, 4, 4, 4, 4],
        "monday.com": [None, None, None, 5, 5, 4, 4],
        "trello.com": [None]*7,
        "wikipedia.org": [2, 2, 2, 2, 2, 2, 2],
    },
    "team collaboration software": {
        "asana.com":  [3, 3, 3, None, None, None, None],
        "monday.com": [5, 5, 4, 4, 3, 3, 3],
        "trello.com": [None]*7,
    },
    "gantt chart online": {
        "asana.com":  [6, 6, None, None, None, None, None],
        "monday.com": [None]*7,
        "trello.com": [2, 2, 2, 3, 3, 3, 3],
    },
    "kanban board app": {
        "asana.com":  [None, None, None, None, 5, 4, 4],
        "monday.com": [None]*7,
        "trello.com": [4, 4, 4, 4, 4, 4, 4],
    },
    "workflow automation": {
        "asana.com":  [None, None, None, None, None, None, 3],
        "monday.com": [2, 2, 2, 2, 2, 2, 2],
        "trello.com": [None]*7,
        "g2.com":     [5, 5, 5, 5, 5, 5, 5],
    },
    "resource planning tool": {
        "asana.com":  [None, None, 5, 5, 4, None, None],
        "monday.com": [None]*7,
        "trello.com": [None]*7,
        "wikipedia.org": [3, 3, 3, 3, 3, 3, 3],
    },
}


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def url_for(domain, keyword):
    return f"https://www.{domain}/{slug(keyword)}"


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL no está configurada")
    host = urlparse(url).hostname or ""
    print(f"DB HOST: {host}")
    if "switchyard" in host and os.getenv("FORCE_PROD") != "1":
        raise SystemExit("ABORT: parece PRODUCCIÓN (switchyard). No se siembra.")

    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1) Proyecto (idempotente: si existe, limpiamos sus datos y reutilizamos id)
    cur.execute(
        "SELECT id FROM manual_ai_projects WHERE user_id = %s AND name = %s",
        (OWNER_USER_ID, PROJECT_NAME),
    )
    row = cur.fetchone()
    if row:
        project_id = row["id"]
        print(f"Proyecto demo existente id={project_id} → limpiando datos previos")
        cur.execute("DELETE FROM manual_ai_global_domains WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM manual_ai_results WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM manual_ai_snapshots WHERE project_id = %s", (project_id,))
        cur.execute("DELETE FROM manual_ai_keywords WHERE project_id = %s", (project_id,))
        cur.execute(
            """UPDATE manual_ai_projects
               SET domain=%s, country_code=%s, is_active=TRUE, selected_competitors=%s,
                   description=%s, updated_at=NOW()
               WHERE id=%s""",
            (PROJECT_DOMAIN, COUNTRY, json.dumps(COMPETITORS),
             "Proyecto de demostración para el modal de comparación histórica.", project_id),
        )
    else:
        cur.execute(
            """INSERT INTO manual_ai_projects
                 (user_id, name, description, domain, country_code, is_active, selected_competitors)
               VALUES (%s, %s, %s, %s, %s, TRUE, %s)
               RETURNING id""",
            (OWNER_USER_ID, PROJECT_NAME,
             "Proyecto de demostración para el modal de comparación histórica.",
             PROJECT_DOMAIN, COUNTRY, json.dumps(COMPETITORS)),
        )
        project_id = cur.fetchone()["id"]
        print(f"Proyecto demo creado id={project_id}")

    # 2) Keywords
    keyword_ids = {}
    for kw in KEYWORDS:
        cur.execute(
            """INSERT INTO manual_ai_keywords (project_id, keyword, is_active)
               VALUES (%s, %s, TRUE) RETURNING id""",
            (project_id, kw),
        )
        keyword_ids[kw] = cur.fetchone()["id"]
    print(f"Keywords insertadas: {len(keyword_ids)}")

    # 3) Resultados + dominios globales por (keyword, fecha)
    n_results = 0
    n_domains = 0
    for kw, profiles in KEYWORDS.items():
        kid = keyword_ids[kw]
        for i, d in enumerate(DATES):
            # Construir lista de (domain, position) presentes ese día
            present = []
            for domain, positions in profiles.items():
                pos = positions[i]
                if pos is not None:
                    present.append((domain, pos))
            present.sort(key=lambda x: x[1])  # por posición

            references = [{
                "link": url_for(domain, kw),
                "index": pos - 1,
                "title": f"{kw.title()} | {domain}",
                "source": domain,
            } for domain, pos in present]

            proj_pos = next((pos for domain, pos in present if domain == PROJECT_DOMAIN), None)
            domain_mentioned = proj_pos is not None

            ai_analysis_data = {
                "has_ai_overview": True,
                "domain_is_ai_source": domain_mentioned,
                "domain_ai_source_position": proj_pos,
                "debug_info": {"references_found": references},
            }

            cur.execute(
                """INSERT INTO manual_ai_results
                     (project_id, keyword_id, analysis_date, keyword, domain,
                      has_ai_overview, domain_mentioned, domain_position,
                      ai_elements_count, impact_score, raw_serp_data, ai_analysis_data, country_code)
                   VALUES (%s,%s,%s,%s,%s, TRUE,%s,%s, %s,%s,%s,%s,%s)""",
                (project_id, kid, d, kw, PROJECT_DOMAIN,
                 domain_mentioned, proj_pos,
                 len(references), (proj_pos and (10 - proj_pos) * 10) or 0,
                 json.dumps({}), json.dumps(ai_analysis_data), COUNTRY),
            )
            n_results += 1

            for domain, pos in present:
                cur.execute(
                    """INSERT INTO manual_ai_global_domains
                         (project_id, keyword_id, analysis_date, keyword, project_domain,
                          detected_domain, domain_position, domain_title, domain_source_url,
                          country_code, is_project_domain, is_selected_competitor)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (project_id, kid, d, kw, PROJECT_DOMAIN,
                     domain, pos, f"{kw.title()} | {domain}", url_for(domain, kw),
                     COUNTRY, domain == PROJECT_DOMAIN, domain in COMPETITORS),
                )
                n_domains += 1

    # 4) Snapshots por fecha (para coherencia del histórico de visibilidad)
    for d in DATES:
        cur.execute(
            """SELECT
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE has_ai_overview) AS with_ai,
                  COUNT(*) FILTER (WHERE domain_mentioned) AS mentions,
                  AVG(domain_position) FILTER (WHERE domain_mentioned) AS avg_pos
               FROM manual_ai_results WHERE project_id=%s AND analysis_date=%s""",
            (project_id, d),
        )
        agg = cur.fetchone()
        with_ai = agg["with_ai"] or 0
        mentions = agg["mentions"] or 0
        vis = (mentions / with_ai * 100) if with_ai else 0
        cur.execute(
            """INSERT INTO manual_ai_snapshots
                 (project_id, snapshot_date, total_keywords, active_keywords,
                  keywords_with_ai, domain_mentions, avg_position, visibility_percentage,
                  change_type)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'daily_analysis')
               ON CONFLICT (project_id, snapshot_date) DO UPDATE SET
                  keywords_with_ai=EXCLUDED.keywords_with_ai,
                  domain_mentions=EXCLUDED.domain_mentions,
                  avg_position=EXCLUDED.avg_position,
                  visibility_percentage=EXCLUDED.visibility_percentage""",
            (project_id, d, len(KEYWORDS), len(KEYWORDS), with_ai, mentions,
             agg["avg_pos"], round(vis, 2)),
        )

    conn.commit()
    print(f"OK · results={n_results} global_domains={n_domains} dates={len(DATES)}")
    print(f"Fechas: {DATES[0]} .. {DATES[-1]}")
    print(f"Proyecto demo id={project_id} owner={OWNER_USER_ID} ({PROJECT_DOMAIN})")
    conn.close()


if __name__ == "__main__":
    main()
