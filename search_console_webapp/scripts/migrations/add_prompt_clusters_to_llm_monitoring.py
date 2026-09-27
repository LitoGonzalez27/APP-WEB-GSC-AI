#!/usr/bin/env python3
"""
Migración: prompt clusters para LLM Visibility Monitor
SEGURA: idempotente, solo crea si no existe.

Añade:
- llm_monitoring_projects.prompt_clusters  (JSONB) → lista canónica de clusters del proyecto
- llm_monitoring_queries.topic_cluster     (TEXT)  → cluster asignado a cada prompt
  (NULL = sin asignar → excluido de reportes de clusters)

Patrón consistente con `add_topic_clusters_field.py` (Manual AI).
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate():
    """Aplica migración de prompt_clusters al módulo LLM Visibility Monitor."""

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False

    try:
        cur = conn.cursor()

        logger.info("🚀 Iniciando migración prompt_clusters para LLM Monitoring...")

        # ─────────────────────────────────────────────────────────
        # 1. llm_monitoring_projects.prompt_clusters
        # ─────────────────────────────────────────────────────────
        logger.info("📋 [1/4] Añadiendo llm_monitoring_projects.prompt_clusters...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD COLUMN IF NOT EXISTS prompt_clusters JSONB
            DEFAULT '{"enabled": false, "clusters": []}'::jsonb
        """)
        logger.info("   ✅ prompt_clusters OK")

        logger.info("📋 [2/4] Creando índice GIN en prompt_clusters...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_monitoring_prompt_clusters
            ON llm_monitoring_projects USING GIN (prompt_clusters)
        """)
        logger.info("   ✅ idx_llm_monitoring_prompt_clusters OK")

        # ─────────────────────────────────────────────────────────
        # 2. llm_monitoring_queries.topic_cluster
        # ─────────────────────────────────────────────────────────
        logger.info("📋 [3/4] Añadiendo llm_monitoring_queries.topic_cluster...")
        cur.execute("""
            ALTER TABLE llm_monitoring_queries
            ADD COLUMN IF NOT EXISTS topic_cluster TEXT NULL
        """)
        logger.info("   ✅ topic_cluster OK")

        logger.info("📋 [4/4] Creando índice parcial en topic_cluster...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_queries_topic_cluster
            ON llm_monitoring_queries (project_id, topic_cluster)
            WHERE topic_cluster IS NOT NULL
        """)
        logger.info("   ✅ idx_llm_queries_topic_cluster OK")

        conn.commit()

        # ─────────────────────────────────────────────────────────
        # Verificación
        # ─────────────────────────────────────────────────────────
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'llm_monitoring_projects'
              AND column_name = 'prompt_clusters'
        """)
        proj_row = cur.fetchone()

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'llm_monitoring_queries'
              AND column_name = 'topic_cluster'
        """)
        query_row = cur.fetchone()

        if proj_row and query_row:
            logger.info(
                "✅ Verificación OK: "
                f"projects.prompt_clusters({proj_row['data_type']}) + "
                f"queries.topic_cluster({query_row['data_type']})"
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
