#!/usr/bin/env python3
"""
Migración: Límites por módulo para usuarios Enterprise
=======================================================
Añade a `users` cinco columnas opcionales (NULL = sin override) que permiten
al admin acotar, por usuario Enterprise, el número de proyectos por módulo
y el tamaño de cada proyecto en Manual AI y AI Mode:

    custom_manual_ai_max_projects     INTEGER  -- máx. proyectos Manual AI
    custom_manual_ai_keywords_limit   INTEGER  -- máx. keywords por proyecto Manual AI
    custom_ai_mode_max_projects       INTEGER  -- máx. proyectos AI Mode
    custom_ai_mode_keywords_limit     INTEGER  -- máx. prompts por proyecto AI Mode
    custom_llm_max_projects           INTEGER  -- máx. proyectos LLM Monitoring

Complementa a `custom_quota_limit` (RU), `custom_llm_prompts_limit` y
`custom_llm_monthly_units_limit` (ver migrate_enterprise_quotas.py y
migrate_llm_enterprise_support.py). Solo se aplican cuando plan='enterprise'
(ver enterprise_limits.py).

ULTRA-SEGURO: solo ADD COLUMN IF NOT EXISTS con DEFAULT NULL. Idempotente.

Uso:
    DATABASE_URL=postgres://... python3 migrate_enterprise_module_limits.py
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


COLUMNS = [
    'custom_manual_ai_max_projects',
    'custom_manual_ai_keywords_limit',
    'custom_ai_mode_max_projects',
    'custom_ai_mode_keywords_limit',
    'custom_llm_max_projects',
]


def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL no configurado")
        return 1

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        print("=" * 60)
        print("🚀 MIGRACIÓN: LÍMITES POR MÓDULO PARA ENTERPRISE")
        print("=" * 60)

        for i, col in enumerate(COLUMNS, 1):
            print(f"📋 [{i}/{len(COLUMNS)}] Añadiendo columna {col}...")
            cur.execute(f"""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS {col} INTEGER DEFAULT NULL;
            """)
            print("   ✅ OK (o ya existía)")

        conn.commit()

        print()
        print("🔍 Verificando migración...")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'users'
              AND column_name = ANY(%s)
            ORDER BY column_name
        """, (COLUMNS,))
        found = {row['column_name'] for row in cur.fetchall()}
        missing = set(COLUMNS) - found
        for col in sorted(found):
            print(f"   ✅ Columna: {col}")
        if missing:
            print(f"   ❌ Faltan columnas: {sorted(missing)}")
            return 1

        print()
        print("=" * 60)
        print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        return 0

    except Exception as e:
        conn.rollback()
        print(f"❌ Error en migración: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
