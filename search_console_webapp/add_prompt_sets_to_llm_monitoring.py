#!/usr/bin/env python3
"""
Migración: prompt sets (núcleo / tendencia / estacionales) para LLM Visibility Monitor
SEGURA: idempotente, solo crea si no existe.

Añade:
- llm_monitoring_projects.prompt_sets  (JSONB) → sets adicionales del proyecto con
  ventana estacional opcional. El set "núcleo" (core) es implícito y NO se guarda aquí.
  Shape: {"enabled": bool, "sets": [{"name": "Black Friday",
                                     "window": {"start": "11-15", "end": "12-02"}}]}
  La ventana se evalúa contra el día UTC (MM-DD), con soporte de wrap-around
  (p.ej. start 12-20, end 01-06). Un set sin "window" está siempre activo.
- llm_monitoring_queries.prompt_set    (TEXT)  → set asignado a cada prompt.
  NULL = núcleo (core). Igual semántica que topic_cluster: NULL es el default
  y no requiere backfill.

Patrón consistente con `add_prompt_clusters_to_llm_monitoring.py`.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate():
    """Aplica migración de prompt_sets al módulo LLM Visibility Monitor."""

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False

    try:
        cur = conn.cursor()

        logger.info("🚀 Iniciando migración prompt_sets para LLM Monitoring...")

        # ─────────────────────────────────────────────────────────
        # 1. llm_monitoring_projects.prompt_sets
        # ─────────────────────────────────────────────────────────
        logger.info("📋 [1/3] Añadiendo llm_monitoring_projects.prompt_sets...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD COLUMN IF NOT EXISTS prompt_sets JSONB
            DEFAULT '{"enabled": false, "sets": []}'::jsonb
        """)
        logger.info("   ✅ prompt_sets OK")

        # ─────────────────────────────────────────────────────────
        # 2. llm_monitoring_queries.prompt_set
        # ─────────────────────────────────────────────────────────
        logger.info("📋 [2/3] Añadiendo llm_monitoring_queries.prompt_set...")
        cur.execute("""
            ALTER TABLE llm_monitoring_queries
            ADD COLUMN IF NOT EXISTS prompt_set TEXT NULL
        """)
        logger.info("   ✅ prompt_set OK")

        logger.info("📋 [3/3] Creando índice parcial en prompt_set...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_queries_prompt_set
            ON llm_monitoring_queries (project_id, prompt_set)
            WHERE prompt_set IS NOT NULL
        """)
        logger.info("   ✅ idx_llm_queries_prompt_set OK")

        conn.commit()

        # ─────────────────────────────────────────────────────────
        # Verificación
        # ─────────────────────────────────────────────────────────
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'llm_monitoring_projects'
              AND column_name = 'prompt_sets'
        """)
        proj_row = cur.fetchone()

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'llm_monitoring_queries'
              AND column_name = 'prompt_set'
        """)
        query_row = cur.fetchone()

        if proj_row and query_row:
            logger.info(
                "✅ Verificación OK: "
                f"projects.prompt_sets({proj_row['data_type']}) + "
                f"queries.prompt_set({query_row['data_type']})"
            )
            return True

        logger.error("❌ Verificación falló — alguna columna no se creó")
        return False

    except Exception as e:
        logger.error(f"❌ Error en migración: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            try:
                cur.close()
            except Exception:
                pass
            conn.close()


if __name__ == '__main__':
    ok = migrate()
    sys.exit(0 if ok else 1)
