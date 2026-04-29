"""Migration: add quota-pause fields to manual_ai_projects.

Mirrors the columns already present on llm_monitoring_projects and
ai_mode_projects so manual_ai can support the same pause/resume/quota
flow.

Idempotent: uses IF NOT EXISTS for every ADD COLUMN.
"""

import os
import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def connect_db(database_url):
    if not database_url:
        raise ValueError("DATABASE_URL no está configurado.")
    return psycopg2.connect(database_url)


def migrate_manual_ai_quota_pause_fields():
    """Add quota-pause fields to manual_ai_projects."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurado en el entorno.")
        return False

    conn = None
    try:
        conn = connect_db(database_url)
        conn.autocommit = False
        cur = conn.cursor()

        logger.info("🔄 Añadiendo campos de pausa por cuota en manual_ai_projects...")
        cur.execute("""
            ALTER TABLE manual_ai_projects
            ADD COLUMN IF NOT EXISTS is_paused_by_quota BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS paused_until TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS paused_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS paused_reason TEXT;
        """)

        logger.info("🔄 Asegurando índice por (user_id, is_paused_by_quota)...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_manual_ai_projects_user_paused
            ON manual_ai_projects(user_id, is_paused_by_quota);
        """)

        conn.commit()
        logger.info("🎉 Migración completada: pausa por cuota disponible en Manual AI.")
        return True
    except Exception as exc:
        logger.error(f"❌ Error durante la migración: {exc}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    if migrate_manual_ai_quota_pause_fields():
        logger.info("Script de migración ejecutado con éxito.")
    else:
        logger.error("Script de migración falló.")
