"""Migration: add analysis_frequency_days to manual_ai_projects and ai_mode_projects.

Permite configurar, por proyecto, cada cuántos días lo analiza el cron
automático (1 = diario/cada tick del cron, comportamiento actual;
7 = semanal). El cron salta el proyecto si ya tiene resultados dentro
de la ventana de N días.

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


def migrate_analysis_frequency_fields():
    """Add analysis_frequency_days to manual_ai_projects and ai_mode_projects."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurado en el entorno.")
        return False

    conn = None
    try:
        conn = connect_db(database_url)
        conn.autocommit = False
        cur = conn.cursor()

        for table in ('manual_ai_projects', 'ai_mode_projects'):
            logger.info(f"🔄 Añadiendo analysis_frequency_days en {table}...")
            cur.execute(f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS analysis_frequency_days INTEGER DEFAULT 1;
            """)

        conn.commit()
        logger.info("✅ Migración analysis_frequency_days completada.")
        return True

    except Exception as e:
        logger.error(f"❌ Error en la migración: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    success = migrate_analysis_frequency_fields()
    raise SystemExit(0 if success else 1)
