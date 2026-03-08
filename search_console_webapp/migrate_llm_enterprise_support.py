#!/usr/bin/env python3
"""
Migración: Soporte Enterprise para LLM Monitoring
===================================================
1. Amplía constraint queries_per_llm de 60 a 5000
2. Añade columna custom_llm_prompts_limit a users
3. Añade columna custom_llm_monthly_units_limit a users

Estas columnas permiten al admin asignar límites personalizados
de prompts y unidades mensuales LLM a usuarios Enterprise,
independientes del custom_quota_limit (que es para RU generales).

Idempotente: se puede ejecutar múltiples veces sin problemas.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL no configurado")
        return 1

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()

        print("=" * 60)
        print("🚀 MIGRACIÓN: SOPORTE ENTERPRISE PARA LLM MONITORING")
        print("=" * 60)
        print()

        # ─────────────────────────────────────────────
        # PASO 1: Ampliar constraint queries_per_llm
        # ─────────────────────────────────────────────
        print("📋 [1/3] Ampliando constraint queries_per_llm a 5000...")

        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            DROP CONSTRAINT IF EXISTS llm_monitoring_projects_queries_per_llm_check;
        """)
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD CONSTRAINT llm_monitoring_projects_queries_per_llm_check
            CHECK (queries_per_llm BETWEEN 5 AND 5000);
        """)
        print("   ✅ Constraint actualizado: queries_per_llm BETWEEN 5 AND 5000")

        # ─────────────────────────────────────────────
        # PASO 2: Columna custom_llm_prompts_limit
        # ─────────────────────────────────────────────
        print("📋 [2/3] Añadiendo columna custom_llm_prompts_limit a users...")

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS custom_llm_prompts_limit INTEGER DEFAULT NULL;
        """)
        print("   ✅ Columna custom_llm_prompts_limit añadida (o ya existía)")

        # ─────────────────────────────────────────────
        # PASO 3: Columna custom_llm_monthly_units_limit
        # ─────────────────────────────────────────────
        print("📋 [3/3] Añadiendo columna custom_llm_monthly_units_limit a users...")

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS custom_llm_monthly_units_limit INTEGER DEFAULT NULL;
        """)
        print("   ✅ Columna custom_llm_monthly_units_limit añadida (o ya existía)")

        conn.commit()

        # ─────────────────────────────────────────────
        # VERIFICACIÓN
        # ─────────────────────────────────────────────
        print()
        print("🔍 Verificando migración...")

        # Verificar constraint
        cur.execute("""
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'llm_monitoring_projects'::regclass
              AND conname LIKE '%queries_per_llm%'
        """)
        constraint = cur.fetchone()
        if constraint:
            print(f"   ✅ Constraint: {constraint['conname']} → {constraint['definition']}")
        else:
            print("   ⚠️ Constraint no encontrado (puede estar con otro nombre)")

        # Verificar columnas
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'users'
              AND column_name IN ('custom_llm_prompts_limit', 'custom_llm_monthly_units_limit')
            ORDER BY column_name
        """)
        columns = cur.fetchall()
        for col in columns:
            print(f"   ✅ Columna: {col['column_name']} ({col['data_type']})")

        if len(columns) < 2:
            print("   ⚠️ Faltan columnas. Revisa errores arriba.")

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
    raise SystemExit(main())
