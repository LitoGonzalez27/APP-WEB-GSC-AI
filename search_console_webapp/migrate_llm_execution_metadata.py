#!/usr/bin/env python3
"""
Migration: add execution_metadata and prompt_version columns to
llm_monitoring_results.

Context (2026-04-08): tras el upgrade de fidelidad locale de
services/llm_monitoring_service.py, necesitamos guardar auditoría
per-row de:
  - prompt_version: 'v2_system', 'v1_inline', etc. (versionado)
  - execution_metadata (JSONB): detalles completos del locale aplicado
    y la estrategia real del provider (system_user, system_user_geo,
    prepended_system, legacy_user_only), el modelo realmente usado,
    etc.

Safety guarantees:
  - Both columns are nullable, default NULL.
  - Existing rows are unaffected (no backfill). Las 5.633+ filas
    históricas quedan intactas con estos campos en NULL.
  - Idempotent: safe to run multiple times (uses IF NOT EXISTS).
  - Zero-downtime: ADD COLUMN IF NOT EXISTS with DEFAULT NULL is
    metadata-only in Postgres 11+ (no table rewrite, only a momentary
    ACCESS EXCLUSIVE lock of milliseconds).
  - The partial index is built with WHERE prompt_version IS NOT NULL,
    so on existing data it is created instantaneously empty and then
    populated incrementally on new inserts.
  - Reversión: NO dropear columnas en rollback. Dejarlas NULLables es
    benigno y preserva metadata de auditoría.

Running:
  # Staging:
  DATABASE_URL=<staging_dsn> python migrate_llm_execution_metadata.py

  # Production:
  DATABASE_URL=<prod_dsn> python migrate_llm_execution_metadata.py

Re-ejecutable sin efecto (idempotente).
"""

import logging
import sys

from database import get_db_connection

logger = logging.getLogger(__name__)


def migrate() -> int:
    """
    Run the migration.

    Returns:
        int: 0 on success, 1 on failure.
    """
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return 1

    try:
        cur = conn.cursor()

        # Paso 1: añadir columna execution_metadata (JSONB)
        logger.info("📊 Paso 1/3: añadiendo columna execution_metadata JSONB...")
        cur.execute("""
            ALTER TABLE llm_monitoring_results
            ADD COLUMN IF NOT EXISTS execution_metadata JSONB DEFAULT NULL
        """)
        logger.info("✅ execution_metadata JSONB asegurada")

        # Paso 2: añadir columna prompt_version (VARCHAR 20)
        logger.info("📊 Paso 2/3: añadiendo columna prompt_version VARCHAR(20)...")
        cur.execute("""
            ALTER TABLE llm_monitoring_results
            ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(20) DEFAULT NULL
        """)
        logger.info("✅ prompt_version VARCHAR(20) asegurada")

        # Paso 3: índice parcial sobre prompt_version para queries de auditoría.
        # WHERE prompt_version IS NOT NULL hace que el índice quede vacío
        # sobre filas históricas y se pueble solo con filas nuevas.
        logger.info("📊 Paso 3/3: creando índice parcial idx_llm_results_prompt_version...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_results_prompt_version
            ON llm_monitoring_results (prompt_version)
            WHERE prompt_version IS NOT NULL
        """)
        logger.info("✅ idx_llm_results_prompt_version asegurado")

        # Verificación: confirmar que las columnas existen
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'llm_monitoring_results'
              AND column_name IN ('execution_metadata', 'prompt_version')
            ORDER BY column_name
        """)
        rows = cur.fetchall()
        logger.info("🔍 Verificación post-migración:")
        for r in rows:
            if isinstance(r, dict):
                col = r.get('column_name')
                dt = r.get('data_type')
                nullable = r.get('is_nullable')
            else:
                col, dt, nullable = r
            logger.info(f"   - {col}: {dt} (nullable={nullable})")

        if len(rows) != 2:
            logger.error(
                f"❌ Se esperaban 2 columnas pero se encontraron {len(rows)}"
            )
            conn.rollback()
            return 1

        conn.commit()
        logger.info("🎉 Migración completada con éxito")
        return 0

    except Exception as e:
        logger.error(f"❌ Error en migración: {e}", exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return 1
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    logger.info("🚀 Iniciando migración: llm_monitoring_results metadata")
    exit_code = migrate()
    sys.exit(exit_code)
