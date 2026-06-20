#!/usr/bin/env python3
"""
Crea la tabla `ai_mode_global_domains` (ranking global de dominios/fuentes citadas
en Google AI Mode), gemela de `manual_ai_global_domains`.

Contexto: esta tabla la escribe `ai_mode_projects/services/domains_service.py` y la
lee `ai_mode_projects/services/_statistics/domains.py` (global domains ranking).
Nunca se incluyó en `create_ai_mode_tables.py`, por lo que en producción no existía
y la sección "media sources / global domains ranking" de AI Mode salía vacía (el
código lo toleraba con try/except). Se creó en prod el 2026-06-19 y se rellenó el
histórico desde `ai_mode_results.raw_ai_mode_data`.

Idempotente (CREATE TABLE IF NOT EXISTS). Uso:
    DATABASE_URL=... python3 create_ai_mode_global_domains_table.py
o en Railway:
    railway run --service <service> python3 create_ai_mode_global_domains_table.py
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("create_ai_mode_global_domains")

DDL = """
CREATE TABLE IF NOT EXISTS ai_mode_global_domains (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES ai_mode_projects(id) ON DELETE CASCADE,
    keyword_id INTEGER REFERENCES ai_mode_keywords(id) ON DELETE CASCADE,
    analysis_date DATE NOT NULL,
    keyword VARCHAR(500) NOT NULL,
    project_domain VARCHAR(255) NOT NULL,
    detected_domain VARCHAR(255) NOT NULL CHECK (char_length(detected_domain) >= 3),
    domain_position INTEGER NOT NULL CHECK (domain_position > 0),
    domain_title TEXT,
    domain_source_url TEXT,
    country_code VARCHAR(3) DEFAULT 'US',
    is_project_domain BOOLEAN DEFAULT FALSE,
    is_selected_competitor BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (project_id, keyword_id, analysis_date, detected_domain)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_ai_mode_global_domains_project_date ON ai_mode_global_domains (project_id, analysis_date)",
    "CREATE INDEX IF NOT EXISTS idx_ai_mode_global_domains_domain ON ai_mode_global_domains (detected_domain)",
    "CREATE INDEX IF NOT EXISTS idx_ai_mode_global_domains_competitor_flag ON ai_mode_global_domains (project_id, is_selected_competitor, analysis_date)",
]


def main():
    from database import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.error("No DB connection")
        sys.exit(1)
    try:
        cur = conn.cursor()
        cur.execute(DDL)
        for idx in INDEXES:
            cur.execute(idx)
        conn.commit()
        cur.execute("SELECT to_regclass('public.ai_mode_global_domains')")
        logger.info(f"✅ Tabla lista: {cur.fetchone()[0]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
