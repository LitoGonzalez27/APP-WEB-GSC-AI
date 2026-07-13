"""
Migración: Añadir columna fetch_method a llm_url_content_analysis

Registra cómo se obtuvo el contenido de cada URL analizada:
    direct → fetch HTTP directo (ClicandseoBot)
    jina   → fallback vía Jina Reader (r.jina.ai) tras fallo del directo

Ejecutar en Railway (en CADA entorno — staging y production NO comparten BD):
    railway environment staging && railway run ... python3 migrate_add_fetch_method_url_analysis.py
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def migrate():
    """Añade la columna fetch_method (idempotente)"""

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False

    try:
        cur = conn.cursor()

        logger.info("=" * 70)
        logger.info("🔧 MIGRACIÓN: Añadir fetch_method a llm_url_content_analysis")
        logger.info("=" * 70)

        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'llm_url_content_analysis'
                AND column_name = 'fetch_method'
        """)

        if cur.fetchone():
            logger.info("ℹ️  La columna 'fetch_method' ya existe, nada que hacer")
            return True

        cur.execute("""
            ALTER TABLE llm_url_content_analysis
            ADD COLUMN fetch_method VARCHAR(20) NOT NULL DEFAULT 'direct'
        """)
        conn.commit()

        logger.info("✅ Columna 'fetch_method' añadida")
        logger.info("=" * 70)
        logger.info("✅ MIGRACIÓN COMPLETADA")
        logger.info("=" * 70)

        cur.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error en migración: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False


if __name__ == '__main__':
    success = migrate()
    exit(0 if success else 1)
