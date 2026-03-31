#!/usr/bin/env python3
"""
Migración: Smart Model Discovery v2

Añade:
1. Campos model_category, knowledge_cutoff, pending_approval, approval_token a llm_model_registry
2. Nueva tabla llm_model_changelog para historial de cambios de modelo
3. Datos de knowledge cutoff para modelos actuales

Ejecutar en staging: python migrate_llm_model_discovery_v2.py
"""

import sys
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection


def main():
    """Ejecutar migración Smart Model Discovery v2"""

    logger.info("=" * 70)
    logger.info("MIGRACIÓN: Smart Model Discovery v2")
    logger.info("=" * 70)

    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        sys.exit(1)

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ===================================
        # PASO 1: Nuevos campos en llm_model_registry
        # ===================================
        logger.info("\n📊 Paso 1: Añadiendo campos a llm_model_registry...")

        alterations = [
            ("model_category", "VARCHAR(30) DEFAULT 'chat'"),
            ("knowledge_cutoff", "VARCHAR(50)"),
            ("knowledge_cutoff_date", "DATE"),
            ("pending_approval", "BOOLEAN DEFAULT FALSE"),
            ("approval_token", "VARCHAR(128)"),
            ("approval_token_expires_at", "TIMESTAMP"),
            ("pre_switch_validated", "BOOLEAN DEFAULT FALSE"),
        ]

        for col_name, col_def in alterations:
            try:
                cur.execute(f"""
                    ALTER TABLE llm_model_registry
                    ADD COLUMN IF NOT EXISTS {col_name} {col_def}
                """)
                logger.info(f"   ✅ Columna {col_name} añadida")
            except Exception as e:
                logger.warning(f"   ⚠️ Columna {col_name}: {e}")

        # ===================================
        # PASO 2: Tabla llm_model_changelog
        # ===================================
        logger.info("\n📊 Paso 2: Creando tabla llm_model_changelog...")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_model_changelog (
                id SERIAL PRIMARY KEY,
                llm_provider VARCHAR(50) NOT NULL,
                old_model_id VARCHAR(100),
                new_model_id VARCHAR(100) NOT NULL,
                old_display_name VARCHAR(255),
                new_display_name VARCHAR(255),
                change_type VARCHAR(30) NOT NULL,
                changed_by VARCHAR(100),
                reason TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("   ✅ Tabla llm_model_changelog creada")

        # Índices
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_changelog_provider
            ON llm_model_changelog(llm_provider)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_changelog_date
            ON llm_model_changelog(created_at)
        """)
        logger.info("   ✅ Índices creados")

        # ===================================
        # PASO 3: Índice para approval_token
        # ===================================
        logger.info("\n📊 Paso 3: Creando índice para approval_token...")

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_approval_token
            ON llm_model_registry(approval_token)
            WHERE approval_token IS NOT NULL
        """)
        logger.info("   ✅ Índice parcial creado")

        # ===================================
        # PASO 4: Datos de knowledge cutoff para modelos actuales
        # ===================================
        logger.info("\n📊 Paso 4: Actualizando knowledge cutoff de modelos actuales...")

        cutoff_updates = [
            # (model_id_pattern, cutoff_text, cutoff_date, category)
            ('gpt-5.4', 'Aug 2025', '2025-08-31', 'chat'),
            ('gpt-5.3', 'Aug 2025', '2025-08-31', 'chat'),
            ('gpt-5', 'Jun 2025', '2025-06-30', 'chat'),
            ('claude-sonnet-4-6', 'May 2025', '2025-05-01', 'chat'),
            ('claude-sonnet-4-5-20250929', 'Apr 2025', '2025-04-01', 'chat'),
            ('gemini-3-flash-preview', 'Jan 2025', '2025-01-01', 'chat'),
            ('sonar-pro', 'Web-grounded (real-time)', None, 'chat'),
            ('sonar', 'Web-grounded (real-time)', None, 'chat'),
        ]

        for model_id, cutoff, cutoff_date, category in cutoff_updates:
            cur.execute("""
                UPDATE llm_model_registry
                SET knowledge_cutoff = %s,
                    knowledge_cutoff_date = %s,
                    model_category = %s,
                    updated_at = NOW()
                WHERE model_id = %s
            """, (cutoff, cutoff_date, category, model_id))
            if cur.rowcount > 0:
                logger.info(f"   ✅ {model_id}: cutoff={cutoff}, category={category}")

        # Marcar todos los modelos existentes sin categoría como 'chat'
        cur.execute("""
            UPDATE llm_model_registry
            SET model_category = 'chat'
            WHERE model_category IS NULL
        """)
        logger.info(f"   ✅ {cur.rowcount} modelos sin categoría marcados como 'chat'")

        conn.commit()

        # ===================================
        # VERIFICACIÓN
        # ===================================
        logger.info("\n" + "=" * 70)
        logger.info("VERIFICACIÓN")
        logger.info("=" * 70)

        cur.execute("""
            SELECT model_id, llm_provider, model_category, knowledge_cutoff,
                   is_current, pending_approval
            FROM llm_model_registry
            ORDER BY llm_provider, is_current DESC
        """)
        models = cur.fetchall()

        for m in models:
            status = "✅ CURRENT" if m['is_current'] else "  "
            pending = "⏳ PENDING" if m.get('pending_approval') else ""
            logger.info(f"   {status} {m['llm_provider']:12s} | {m['model_id']:35s} | "
                       f"cat={m.get('model_category', '?'):6s} | cutoff={m.get('knowledge_cutoff', 'N/A'):25s} {pending}")

        # Verificar tabla changelog
        cur.execute("SELECT COUNT(*) as cnt FROM llm_model_changelog")
        cnt = cur.fetchone()['cnt']
        logger.info(f"\n   📋 Changelog entries: {cnt}")

        logger.info("\n" + "=" * 70)
        logger.info("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 70)

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error en migración: {e}", exc_info=True)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
