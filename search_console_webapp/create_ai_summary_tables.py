#!/usr/bin/env python3
"""
Script para crear las tablas del sistema AI Visibility Summary
SEGURO: Solo crea tablas nuevas, no modifica nada existente

La tabla ai_brand_links vincula proyectos de los tres módulos de IA
(Manual AI / AI Overview, AI Mode y LLM Monitoring) bajo una misma "marca"
para poder mostrar un panel de resumen unificado por marca.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_ai_summary_tables():
    """Crear las tablas necesarias para el panel AI Visibility Summary"""

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False

    try:
        cur = conn.cursor()

        logger.info("🚀 Creando tablas para AI Visibility Summary...")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_brand_links (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                brand_name VARCHAR(255) NOT NULL,
                brand_domain VARCHAR(255) NOT NULL,
                manual_ai_project_id INTEGER REFERENCES manual_ai_projects(id) ON DELETE SET NULL,
                ai_mode_project_id INTEGER REFERENCES ai_mode_projects(id) ON DELETE SET NULL,
                llm_project_id INTEGER REFERENCES llm_monitoring_projects(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                -- Constraints
                UNIQUE(user_id, brand_domain),
                CHECK (char_length(brand_name) >= 1),
                CHECK (char_length(brand_domain) >= 3),
                -- Una marca debe tener al menos un módulo vinculado
                CHECK (
                    manual_ai_project_id IS NOT NULL
                    OR ai_mode_project_id IS NOT NULL
                    OR llm_project_id IS NOT NULL
                )
            )
        """)
        logger.info("✅ Tabla ai_brand_links creada")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_brand_links_user
            ON ai_brand_links(user_id)
        """)
        logger.info("✅ Índices de ai_brand_links creados")

        conn.commit()
        logger.info("🎉 Tablas de AI Visibility Summary creadas correctamente")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error creando tablas de AI Summary: {e}")
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    success = create_ai_summary_tables()
    sys.exit(0 if success else 1)
