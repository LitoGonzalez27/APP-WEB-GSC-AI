#!/usr/bin/env python3
"""
Migración: asegurar UNIQUE (project_id, query_text) en llm_monitoring_queries
para soportar ON CONFLICT en inserciones de prompts.
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
        cur.execute("""
            ALTER TABLE llm_monitoring_queries
            ADD CONSTRAINT llm_monitoring_queries_project_query_unique
            UNIQUE (project_id, query_text);
        """)
        conn.commit()
        print("✅ Constraint UNIQUE creado: (project_id, query_text)")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en migración: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
