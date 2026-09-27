#!/usr/bin/env python3
"""
Migración: actualizar límite de queries_per_llm a 60
"""

import os
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
        # Eliminar constraint anterior si existe (nombre por defecto)
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            DROP CONSTRAINT IF EXISTS llm_monitoring_projects_queries_per_llm_check;
        """)
        # Crear nuevo constraint con límite 60
        cur.execute("""
            ALTER TABLE llm_monitoring_projects
            ADD CONSTRAINT llm_monitoring_projects_queries_per_llm_check
            CHECK (queries_per_llm BETWEEN 5 AND 60);
        """)
        conn.commit()
        print("✅ Constraint actualizado: queries_per_llm BETWEEN 5 AND 60")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en migración: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

