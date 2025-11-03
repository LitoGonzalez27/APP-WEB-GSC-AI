#!/usr/bin/env python3
"""
Inspecciona la estructura de tablas de AI Mode para entender cómo limpiarlas
"""

import psycopg2

DB_CONFIG = {
    'host': 'switchyard.proxy.rlwy.net',
    'port': 18167,
    'database': 'railway',
    'user': 'postgres',
    'password': 'HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS'
}

def inspect_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("  📋 ESTRUCTURA DE TABLAS AI MODE")
    print("="*80)
    
    # 1. Ver todas las tablas que empiezan con ai_mode
    print("\n1️⃣ Tablas AI Mode disponibles:")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'ai_mode%'
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    for t in tables:
        print(f"   • {t[0]}")
    
    # 2. Estructura de ai_mode_projects
    print("\n2️⃣ Estructura de ai_mode_projects:")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'ai_mode_projects'
        ORDER BY ordinal_position
    """)
    
    cols = cur.fetchall()
    for col, dtype in cols:
        print(f"   • {col}: {dtype}")
    
    # 3. Buscar proyecto Laserum
    print("\n3️⃣ Buscando proyecto Laserum:")
    cur.execute("""
        SELECT * FROM ai_mode_projects 
        WHERE site_url ILIKE '%laserum%' 
        LIMIT 1
    """)
    
    project = cur.fetchone()
    if project:
        print(f"   ✅ Proyecto encontrado")
        # Mostrar columnas
        col_names = [desc[0] for desc in cur.description]
        for i, col in enumerate(col_names):
            print(f"      {col}: {project[i]}")
    else:
        print(f"   ⚠️  No se encontró proyecto Laserum en AI Mode")
    
    # 4. Estructura de ai_mode_snapshots
    print("\n4️⃣ Estructura de ai_mode_snapshots:")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'ai_mode_snapshots'
        ORDER BY ordinal_position
    """)
    
    cols = cur.fetchall()
    for col, dtype in cols:
        print(f"   • {col}: {dtype}")
    
    # 5. Ver si hay snapshots recientes
    print("\n5️⃣ Snapshots recientes de AI Mode:")
    cur.execute("""
        SELECT snapshot_date, COUNT(*) 
        FROM ai_mode_snapshots 
        WHERE snapshot_date >= '2025-10-20'
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
    """)
    
    snapshots = cur.fetchall()
    if snapshots:
        for snap_date, count in snapshots:
            print(f"   📸 {snap_date}: {count} snapshots")
    else:
        print(f"   ℹ️  No hay snapshots recientes")
    
    # 6. Buscar tabla de keywords
    print("\n6️⃣ Buscando tabla de keywords AI Mode:")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND (table_name LIKE '%ai_mode%keyword%' OR table_name LIKE '%ai_mode%result%')
        ORDER BY table_name
    """)
    
    kw_tables = cur.fetchall()
    if kw_tables:
        for t in kw_tables:
            print(f"   • {t[0]}")
            
            # Ver estructura
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{t[0]}'
                ORDER BY ordinal_position
                LIMIT 10
            """)
            
            cols = cur.fetchall()
            for col, dtype in cols[:5]:  # Solo primeras 5 columnas
                print(f"      - {col}: {dtype}")
    else:
        print(f"   ℹ️  No hay tablas de keywords/results específicas")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    inspect_tables()



