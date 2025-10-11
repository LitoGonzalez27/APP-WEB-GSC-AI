"""Verificar qué tablas existen para AI Mode"""

import psycopg2

DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

tables_to_check = [
    'ai_mode_projects',
    'ai_mode_keywords', 
    'ai_mode_results',
    'ai_mode_events',
    'ai_mode_snapshots',
    'ai_mode_global_domains',
    'ai_mode_media_sources'
]

print("=" * 80)
print("VERIFICANDO TABLAS DE AI MODE")
print("=" * 80)

for table in tables_to_check:
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        )
    """, (table,))
    exists = cur.fetchone()[0]
    status = "✅ EXISTE" if exists else "❌ NO EXISTE"
    print(f"{status}: {table}")

print("=" * 80)

# Si ai_mode_results existe, verificar estructura de media_sources
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'ai_mode_results'
    ORDER BY ordinal_position
""")

print("\n📋 ESTRUCTURA DE ai_mode_results:")
for row in cur.fetchall():
    print(f"   • {row[0]} ({row[1]})")

cur.close()
conn.close()

