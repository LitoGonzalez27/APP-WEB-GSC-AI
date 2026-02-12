#!/usr/bin/env python3
"""
Migración: permitir prompts con longitud mínima 1 (antes >= 10).
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
            DROP CONSTRAINT IF EXISTS llm_monitoring_queries_query_text_check;
        """)
        cur.execute("""
            ALTER TABLE llm_monitoring_queries
            ADD CONSTRAINT llm_monitoring_queries_query_text_check
            CHECK (char_length(query_text) >= 1);
        """)
        conn.commit()
        print("✅ Constraint actualizado: query_text length >= 1")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en migración: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
