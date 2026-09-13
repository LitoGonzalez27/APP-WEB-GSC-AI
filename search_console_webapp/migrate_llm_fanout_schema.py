#!/usr/bin/env python3
"""
Migración: esquema del query fan-out de LLM Monitoring (2026-09-13)

Solo añade (no borra ni reescribe datos):
1. llm_monitoring_projects.search_mode  ('off' | 'auto', por defecto 'off': la
   búsqueda web se activa proyecto a proyecto) y search_enabled_at (fecha del
   cambio de metodología, para marcarla en los gráficos).
2. llm_monitoring_results.search_queries JSONB (detalle por respuesta).
3. Tabla llm_monitoring_fanout_queries: una fila por sub-consulta o página
   abierta, para agregar sin recorrer JSONB. Se borra en cascada con su resultado.

En PostgreSQL ≥ 11 añadir una columna con DEFAULT constante no reescribe la
tabla: es instantáneo aunque llm_monitoring_results tenga decenas de miles de filas.

Idempotente. Ejecutar ANTES de desplegar el código que escribe estas columnas
(el engine además comprueba que existan y, si no, no escribe fan-out).

Uso:
    DATABASE_URL=... python3 migrate_llm_fanout_schema.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATEMENTS = [
    # Los ALTER piden un bloqueo exclusivo breve: si una transacción larga (p.ej.
    # el cron) lo retiene, mejor fallar a los 5 s y reintentar que dejar la app
    # esperando detrás de la migración.
    ("lock_timeout 5s", "SET LOCAL lock_timeout = '5s'"),
    ("search_mode en proyectos", """
        ALTER TABLE llm_monitoring_projects
        ADD COLUMN IF NOT EXISTS search_mode VARCHAR(10) NOT NULL DEFAULT 'off'
    """),
    ("CHECK de search_mode", """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'llm_monitoring_projects_search_mode_check'
            ) THEN
                ALTER TABLE llm_monitoring_projects
                ADD CONSTRAINT llm_monitoring_projects_search_mode_check
                CHECK (search_mode IN ('off', 'auto'));
            END IF;
        END $$
    """),
    ("search_enabled_at en proyectos", """
        ALTER TABLE llm_monitoring_projects
        ADD COLUMN IF NOT EXISTS search_enabled_at TIMESTAMPTZ
    """),
    ("search_queries en resultados", """
        ALTER TABLE llm_monitoring_results
        ADD COLUMN IF NOT EXISTS search_queries JSONB NOT NULL DEFAULT '[]'::jsonb
    """),
    ("tabla llm_monitoring_fanout_queries", """
        CREATE TABLE IF NOT EXISTS llm_monitoring_fanout_queries (
            id BIGSERIAL PRIMARY KEY,
            result_id INTEGER NOT NULL REFERENCES llm_monitoring_results(id) ON DELETE CASCADE,
            project_id INTEGER NOT NULL,
            query_id INTEGER NOT NULL,
            llm_provider VARCHAR(50) NOT NULL,
            analysis_date DATE NOT NULL,
            round SMALLINT NOT NULL,
            position SMALLINT NOT NULL,
            action VARCHAR(16) NOT NULL
                CHECK (action IN ('search', 'open_page', 'find_in_page', 'fetch_url')),
            query_text TEXT,
            query_normalized TEXT,
            query_cluster_id INTEGER,
            url TEXT,
            url_host TEXT,
            sources JSONB NOT NULL DEFAULT '[]'::jsonb,
            brand_in_sources BOOLEAN,
            competitor_hosts TEXT[] NOT NULL DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE (result_id, position)
        )
    """),
    ("índice por proyecto y fecha", """
        CREATE INDEX IF NOT EXISTS idx_fanout_project_date
        ON llm_monitoring_fanout_queries (project_id, analysis_date)
    """),
    ("índice de agrupación de sub-consultas", """
        CREATE INDEX IF NOT EXISTS idx_fanout_project_query
        ON llm_monitoring_fanout_queries (project_id, query_normalized)
        WHERE action = 'search'
    """),
    ("índice de páginas abiertas por dominio", """
        CREATE INDEX IF NOT EXISTS idx_fanout_project_host
        ON llm_monitoring_fanout_queries (project_id, url_host)
        WHERE url_host IS NOT NULL
    """),
]


def main():
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        sys.exit(1)
    try:
        cur = conn.cursor()
        for label, sql in STATEMENTS:
            cur.execute(sql)
            logger.info(f"   ✅ {label}")
        conn.commit()
        logger.info("✅ Esquema de fan-out listo")
    except Exception:
        conn.rollback()
        logger.exception("❌ Migración revertida")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
