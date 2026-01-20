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


def migrate_add_trial_used():
    """Añade columna trial_used para controlar el uso de free trial."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurado en el entorno.")
        return False

    conn = None
    try:
        conn = connect_db(database_url)
        conn.autocommit = False
        cur = conn.cursor()

        logger.info("🔄 Añadiendo columna 'trial_used' en 'users' si no existe...")
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT FALSE;
        """)

        conn.commit()
        logger.info("🎉 Migración completada: trial_used disponible.")
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
    if migrate_add_trial_used():
        logger.info("Script de migración ejecutado con éxito.")
    else:
        logger.error("Script de migración falló.")

