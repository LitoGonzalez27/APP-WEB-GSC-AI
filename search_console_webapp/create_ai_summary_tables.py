#!/usr/bin/env python3
"""
Script para crear las tablas del sistema AI Visibility Summary
SEGURO: Solo crea tablas nuevas, no modifica nada existente

La tabla ai_brand_links vincula proyectos de los tres módulos de IA
(Manual AI / AI Overview, AI Mode y LLM Monitoring) bajo una misma "marca"
para poder mostrar un panel de resumen unificado por marca.

Nota de diseño: la regla "una marca debe tener al menos un módulo vinculado"
se valida SOLO en la capa de aplicación (routes), nunca como CHECK en BD.
Un CHECK aquí combinado con los FK ON DELETE SET NULL haría fallar el
borrado de proyectos en los otros módulos cuando el proyecto borrado fuese
el único vínculo de una marca (el SET NULL violaría el CHECK y abortaría
el DELETE original). Una marca huérfana es válida: el panel la muestra sin
canales y el usuario puede revincularla o eliminarla.
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

                -- Constraints (la regla "al menos un vínculo" vive en routes,
                -- ver nota de diseño en el docstring del módulo)
                UNIQUE(user_id, brand_domain),
                CHECK (char_length(brand_name) >= 1),
                CHECK (char_length(brand_domain) >= 3)
            )
        """)
        logger.info("✅ Tabla ai_brand_links creada")

        # Histórico diario del AI Visibility Score por marca. Se escribe de
        # forma oportunista al ver el resumen (periodo 30d) y desde el cron
        # /api/cron/daily-snapshots; una fila por marca y día (upsert).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_brand_score_snapshots (
                id SERIAL PRIMARY KEY,
                brand_id INTEGER REFERENCES ai_brand_links(id) ON DELETE CASCADE,
                snapshot_date DATE NOT NULL,
                score DECIMAL(5,1) NOT NULL,
                aio_visibility DECIMAL(5,1),
                ai_mode_visibility DECIMAL(5,1),
                llm_visibility DECIMAL(5,1),
                channels_used TEXT[],
                created_at TIMESTAMP DEFAULT NOW(),

                UNIQUE(brand_id, snapshot_date),
                CHECK (score >= 0 AND score <= 100)
            )
        """)
        logger.info("✅ Tabla ai_brand_score_snapshots creada")

        # Las marcas se comparten con la infraestructura común de
        # colaboradores: ampliar el CHECK de module_name para admitir
        # 'ai_summary' en entornos donde las tablas ya existían con la
        # lista original de 3 módulos. Idempotente (DROP IF EXISTS + ADD).
        cur.execute("SELECT to_regclass('project_collaborators'), to_regclass('project_invitations')")
        if all(cur.fetchone()):
            for table in ('project_collaborators', 'project_invitations'):
                cur.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_module_name_check")
                cur.execute(f"""
                    ALTER TABLE {table} ADD CONSTRAINT {table}_module_name_check
                    CHECK (module_name IN ('llm_monitoring', 'manual_ai', 'ai_mode', 'ai_summary'))
                """)
            logger.info("✅ CHECK de module_name ampliado con 'ai_summary'")

        # Migraciones idempotentes para entornos donde la tabla ya existía
        # con el esquema inicial (2026-07-09):
        # 1. El CHECK "al menos un módulo" rompía el borrado de proyectos en
        #    los otros módulos (ver nota de diseño arriba).
        cur.execute("ALTER TABLE ai_brand_links DROP CONSTRAINT IF EXISTS ai_brand_links_check")
        # 2. idx_ai_brand_links_user era redundante: el UNIQUE(user_id,
        #    brand_domain) ya crea un índice con user_id como columna líder.
        cur.execute("DROP INDEX IF EXISTS idx_ai_brand_links_user")
        logger.info("✅ Migraciones idempotentes de ai_brand_links aplicadas")

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
