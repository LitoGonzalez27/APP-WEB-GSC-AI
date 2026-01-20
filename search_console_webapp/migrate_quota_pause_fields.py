import os
import logging
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def connect_db(database_url):
    """Establece conexión a la base de datos."""
    if not database_url:
        raise ValueError("DATABASE_URL no está configurado.")
    return psycopg2.connect(database_url)


def migrate_quota_pause_fields():
    """Añade campos de pausa por cuota en users y proyectos."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurado en el entorno.")
        return False

    conn = None
    try:
        conn = connect_db(database_url)
        conn.autocommit = False
        cur = conn.cursor()

        logger.info("🔄 Añadiendo campos de pausa por cuota en users...")
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS ai_overview_paused_until TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS ai_overview_paused_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS ai_overview_paused_reason TEXT;
        """)

        logger.info("🔄 Añadiendo campos de pausa por cuota en ai_mode_projects...")
        cur.execute("""
            ALTER TABLE ai_mode_projects
            ADD COLUMN IF NOT EXISTS is_paused_by_quota BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS paused_until TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS paused_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS paused_reason TEXT;
        """)

        logger.info("🔄 Añadiendo campos de pausa por cuota en llm_monitoring_projects...")
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD COLUMN IF NOT EXISTS is_paused_by_quota BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS paused_until TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS paused_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS paused_reason TEXT;
        """)

        conn.commit()
        logger.info("🎉 Migración completada: campos de pausa disponibles.")
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
    if migrate_quota_pause_fields():
        logger.info("Script de migración ejecutado con éxito.")
    else:
        logger.error("Script de migración falló.")

