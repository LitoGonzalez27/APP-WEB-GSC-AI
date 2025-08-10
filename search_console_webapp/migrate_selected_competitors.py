#!/usr/bin/env python3
"""
Migración mínima: agrega la columna selected_competitors (JSONB) a manual_ai_projects,
su constraint (máximo 4) y el índice GIN. Idempotente.

Usa la variable de entorno DATABASE_URL para conectarse a PostgreSQL.
"""

import os
import sys
import psycopg2


def main() -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL no está definido en el entorno")
        return 1

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # 1) Columna JSONB
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'manual_ai_projects' AND column_name = 'selected_competitors'
            """
        )
        if not cur.fetchone():
            print("➕ Añadiendo columna selected_competitors JSONB ...")
            cur.execute(
                """
                ALTER TABLE manual_ai_projects
                ADD COLUMN selected_competitors JSONB DEFAULT '[]'::jsonb
                """
            )
        else:
            print("✅ Columna selected_competitors ya existe")

        # 2) Constraint (máximo 4)
        cur.execute("SELECT 1 FROM pg_constraint WHERE conname = 'check_max_competitors'")
        if not cur.fetchone():
            print("➕ Añadiendo constraint check_max_competitors ...")
            cur.execute(
                """
                ALTER TABLE manual_ai_projects
                ADD CONSTRAINT check_max_competitors
                CHECK (jsonb_array_length(COALESCE(selected_competitors, '[]'::jsonb)) <= 4)
                """
            )
        else:
            print("✅ Constraint check_max_competitors ya existe")

        # 3) Índice GIN
        cur.execute(
            """
            SELECT 1 FROM pg_indexes WHERE indexname = 'idx_manual_ai_projects_competitors'
            """
        )
        if not cur.fetchone():
            print("➕ Creando índice idx_manual_ai_projects_competitors ...")
            cur.execute(
                """
                CREATE INDEX idx_manual_ai_projects_competitors
                ON manual_ai_projects USING GIN (selected_competitors)
                """
            )
        else:
            print("✅ Índice idx_manual_ai_projects_competitors ya existe")

        conn.commit()
        cur.close(); conn.close()
        print("🎉 Migración completada")
        return 0
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            cur.close(); conn.close()
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    sys.exit(main())

