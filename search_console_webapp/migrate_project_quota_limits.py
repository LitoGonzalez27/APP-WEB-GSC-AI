#!/usr/bin/env python3
"""
Migración: Cuota y ciclo por PROYECTO
=====================================
Añade a las tablas de proyectos de los 3 módulos las columnas que permiten al
admin poner un tope de consumo propio por proyecto y una frecuencia de
análisis por proyecto (ver project_quota.py y CLAUDE-enterprise-agencias.md):

    manual_ai_projects.monthly_ru_limit             INTEGER NULL
    ai_mode_projects.monthly_ru_limit               INTEGER NULL
    llm_monitoring_projects.monthly_units_limit     INTEGER NULL
    llm_monitoring_projects.analysis_frequency_days INTEGER DEFAULT 1

(`analysis_frequency_days` ya existía en manual_ai_projects y ai_mode_projects
desde migrate_analysis_frequency_fields.py.)

Además crea un índice de expresión en quota_usage_events para que el cálculo
de consumo por proyecto (metadata->>'project_id') sea barato.

ULTRA-SEGURO: solo ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS. Idempotente.

Uso:
    DATABASE_URL=postgres://... python3 migrate_project_quota_limits.py
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


STATEMENTS = [
    ("manual_ai_projects.monthly_ru_limit",
     "ALTER TABLE manual_ai_projects ADD COLUMN IF NOT EXISTS monthly_ru_limit INTEGER DEFAULT NULL"),
    ("ai_mode_projects.monthly_ru_limit",
     "ALTER TABLE ai_mode_projects ADD COLUMN IF NOT EXISTS monthly_ru_limit INTEGER DEFAULT NULL"),
    ("llm_monitoring_projects.monthly_units_limit",
     "ALTER TABLE llm_monitoring_projects ADD COLUMN IF NOT EXISTS monthly_units_limit INTEGER DEFAULT NULL"),
    ("llm_monitoring_projects.analysis_frequency_days",
     "ALTER TABLE llm_monitoring_projects ADD COLUMN IF NOT EXISTS analysis_frequency_days INTEGER DEFAULT 1"),
    ("idx_quota_events_project",
     "CREATE INDEX IF NOT EXISTS idx_quota_events_project "
     "ON quota_usage_events (user_id, source, (metadata->>'project_id'), timestamp)"),
]

EXPECTED = {
    'manual_ai_projects': ['monthly_ru_limit', 'analysis_frequency_days'],
    'ai_mode_projects': ['monthly_ru_limit', 'analysis_frequency_days'],
    'llm_monitoring_projects': ['monthly_units_limit', 'analysis_frequency_days'],
}


def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL no configurado")
        return 1

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        print("=" * 60)
        print("🚀 MIGRACIÓN: CUOTA Y CICLO POR PROYECTO")
        print("=" * 60)

        for i, (label, sql) in enumerate(STATEMENTS, 1):
            print(f"📋 [{i}/{len(STATEMENTS)}] {label}...")
            cur.execute(sql)
            print("   ✅ OK (o ya existía)")
        conn.commit()

        print()
        print("🔍 Verificando migración...")
        ok = True
        for table, cols in EXPECTED.items():
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = ANY(%s)
            """, (table, cols))
            found = {r['column_name'] for r in cur.fetchall()}
            missing = set(cols) - found
            for c in sorted(found):
                print(f"   ✅ {table}.{c}")
            if missing:
                ok = False
                print(f"   ❌ {table}: faltan {sorted(missing)}")
        if not ok:
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
