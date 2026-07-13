"""
Migración: Crear tabla llm_url_content_analysis

Almacena el resultado del análisis de contenido de las URLs citadas por los
LLMs (Top Mentioned URLs): si la página menciona/enlaza la marca del proyecto
o a sus competidores, con qué anchor texts, y la clasificación de oportunidad.

Ejecutar en Railway:
    railway run --service <service> python3 migrate_create_url_content_analysis.py
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def migrate():
    """Crea la tabla llm_url_content_analysis (idempotente)"""

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False

    try:
        cur = conn.cursor()

        logger.info("=" * 70)
        logger.info("🔧 MIGRACIÓN: Crear tabla llm_url_content_analysis")
        logger.info("=" * 70)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_url_content_analysis (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES llm_monitoring_projects(id) ON DELETE CASCADE,

                -- URL analizada. url_hash (sha256 hex) permite un UNIQUE seguro
                -- aunque la URL supere el límite de un índice btree sobre TEXT.
                url TEXT NOT NULL,
                url_hash CHAR(64) NOT NULL,

                -- Estado del análisis: pending | completed | error
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                http_status INTEGER,
                page_title TEXT,

                -- Presencia de la marca del proyecto en el contenido
                brand_mentioned BOOLEAN NOT NULL DEFAULT FALSE,
                brand_mention_count INTEGER NOT NULL DEFAULT 0,
                brand_linked BOOLEAN NOT NULL DEFAULT FALSE,
                brand_anchor_texts JSONB NOT NULL DEFAULT '[]'::jsonb,

                -- Competidores detectados:
                -- [{"name": ..., "domain": ..., "mentioned": bool,
                --   "mention_count": int, "linked": bool, "anchor_texts": [...]}]
                competitors_found JSONB NOT NULL DEFAULT '[]'::jsonb,

                -- Clasificación: mentioned | quick_win | competitor_page | no_mentions | error
                opportunity VARCHAR(20),
                error_reason TEXT,

                -- Cómo se obtuvo el contenido: direct | jina (fallback Reader)
                fetch_method VARCHAR(20) NOT NULL DEFAULT 'direct',

                fetched_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

                CONSTRAINT uq_url_content_analysis_project_url UNIQUE (project_id, url_hash)
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_content_analysis_project
            ON llm_url_content_analysis(project_id)
        """)

        conn.commit()

        # Verificar
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM information_schema.columns
            WHERE table_name = 'llm_url_content_analysis'
        """)
        result = cur.fetchone()
        logger.info(f"✅ Tabla llm_url_content_analysis lista ({result['count']} columnas)")

        logger.info("")
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
