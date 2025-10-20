#!/usr/bin/env python3
"""
Script para analizar diferencias entre staging y producción
específicamente para tablas relacionadas con AI Mode
"""
import psycopg2
from psycopg2 import sql
import json
from datetime import datetime

# Conexiones
STAGING_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"
PRODUCTION_URL = "postgresql://postgres:HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS@switchyard.proxy.rlwy.net:18167/railway"

def get_connection(url, db_name):
    """Conectar a la base de datos"""
    try:
        conn = psycopg2.connect(url)
        print(f"✅ Conexión exitosa a {db_name}")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a {db_name}: {e}")
        return None

def get_all_tables(conn):
    """Obtener todas las tablas de la BD"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables

def get_table_structure(conn, table_name):
    """Obtener estructura completa de una tabla"""
    cursor = conn.cursor()
    
    # Obtener columnas
    cursor.execute("""
        SELECT 
            column_name, 
            data_type, 
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    
    columns = []
    for row in cursor.fetchall():
        columns.append({
            'name': row[0],
            'type': row[1],
            'length': row[2],
            'nullable': row[3],
            'default': row[4]
        })
    
    # Obtener constraints
    cursor.execute("""
        SELECT
            con.conname as constraint_name,
            con.contype as constraint_type,
            pg_get_constraintdef(con.oid) as definition
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public'
        AND rel.relname = %s;
    """, (table_name,))
    
    constraints = []
    for row in cursor.fetchall():
        constraints.append({
            'name': row[0],
            'type': row[1],
            'definition': row[2]
        })
    
    # Obtener índices
    cursor.execute("""
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename = %s;
    """, (table_name,))
    
    indexes = []
    for row in cursor.fetchall():
        indexes.append({
            'name': row[0],
            'definition': row[1]
        })
    
    cursor.close()
    
    return {
        'columns': columns,
        'constraints': constraints,
        'indexes': indexes
    }

def get_table_row_count(conn, table_name):
    """Obtener número de filas en una tabla"""
    try:
        cursor = conn.cursor()
        cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(
            sql.Identifier(table_name)
        ))
        count = cursor.fetchone()[0]
        cursor.close()
        return count
    except Exception as e:
        return f"Error: {e}"

def identify_ai_mode_tables(tables):
    """Identificar tablas relacionadas con AI Mode"""
    ai_keywords = [
        'ai_mode', 
        'manual_ai', 
        'ai_analysis',
        'topic_clusters',
        'competitors',
        'snapshots',
        'ai_'
    ]
    
    ai_tables = []
    for table in tables:
        for keyword in ai_keywords:
            if keyword in table.lower():
                ai_tables.append(table)
                break
    
    return sorted(ai_tables)

def main():
    print("=" * 80)
    print("🔍 ANÁLISIS DE MIGRACIÓN AI MODE: STAGING → PRODUCCIÓN")
    print("=" * 80)
    print()
    
    # Conectar a staging
    print("📊 Conectando a STAGING...")
    staging_conn = get_connection(STAGING_URL, "STAGING")
    if not staging_conn:
        return
    
    print()
    
    # Conectar a producción
    print("📊 Conectando a PRODUCCIÓN...")
    prod_conn = get_connection(PRODUCTION_URL, "PRODUCCIÓN")
    if not prod_conn:
        staging_conn.close()
        return
    
    print()
    print("-" * 80)
    
    # Obtener todas las tablas
    print("\n📋 Obteniendo lista de tablas...")
    staging_tables = get_all_tables(staging_conn)
    prod_tables = get_all_tables(prod_conn)
    
    print(f"   STAGING: {len(staging_tables)} tablas")
    print(f"   PRODUCCIÓN: {len(prod_tables)} tablas")
    
    # Identificar tablas de AI Mode
    print("\n🤖 Identificando tablas de AI MODE...")
    staging_ai_tables = identify_ai_mode_tables(staging_tables)
    prod_ai_tables = identify_ai_mode_tables(prod_tables)
    
    print(f"   STAGING: {len(staging_ai_tables)} tablas de AI Mode")
    print(f"   PRODUCCIÓN: {len(prod_ai_tables)} tablas de AI Mode")
    
    # Tablas que existen en staging pero NO en producción
    new_tables = set(staging_ai_tables) - set(prod_ai_tables)
    
    # Tablas que existen en ambas
    common_tables = set(staging_ai_tables) & set(prod_ai_tables)
    
    # Tablas que existen en producción pero NO en staging
    only_in_prod = set(prod_ai_tables) - set(staging_ai_tables)
    
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE ANÁLISIS")
    print("=" * 80)
    
    # 1. Tablas nuevas en staging
    if new_tables:
        print(f"\n✨ TABLAS NUEVAS EN STAGING ({len(new_tables)}):")
        print("   (Estas se crearán en producción)")
        for table in sorted(new_tables):
            count = get_table_row_count(staging_conn, table)
            print(f"   - {table} ({count} filas)")
    else:
        print("\n✨ No hay tablas nuevas en staging")
    
    # 2. Tablas comunes
    if common_tables:
        print(f"\n🔄 TABLAS QUE EXISTEN EN AMBAS ({len(common_tables)}):")
        print("   (Compararemos su estructura)")
        for table in sorted(common_tables):
            staging_count = get_table_row_count(staging_conn, table)
            prod_count = get_table_row_count(prod_conn, table)
            print(f"   - {table}")
            print(f"     Staging: {staging_count} filas | Producción: {prod_count} filas")
    else:
        print("\n🔄 No hay tablas comunes")
    
    # 3. Tablas solo en producción
    if only_in_prod:
        print(f"\n⚠️  TABLAS SOLO EN PRODUCCIÓN ({len(only_in_prod)}):")
        print("   (Estas NO se tocarán)")
        for table in sorted(only_in_prod):
            count = get_table_row_count(prod_conn, table)
            print(f"   - {table} ({count} filas)")
    
    # Analizar estructuras de tablas comunes
    print("\n" + "=" * 80)
    print("🔍 ANÁLISIS DETALLADO DE ESTRUCTURAS")
    print("=" * 80)
    
    structural_differences = []
    
    for table in sorted(common_tables):
        print(f"\n📋 Analizando tabla: {table}")
        staging_structure = get_table_structure(staging_conn, table)
        prod_structure = get_table_structure(prod_conn, table)
        
        # Comparar columnas
        staging_cols = {col['name']: col for col in staging_structure['columns']}
        prod_cols = {col['name']: col for col in prod_structure['columns']}
        
        new_cols = set(staging_cols.keys()) - set(prod_cols.keys())
        missing_cols = set(prod_cols.keys()) - set(staging_cols.keys())
        
        if new_cols or missing_cols:
            structural_differences.append(table)
            
            if new_cols:
                print(f"   ✨ Columnas nuevas en staging: {', '.join(new_cols)}")
                for col in new_cols:
                    col_info = staging_cols[col]
                    print(f"      - {col}: {col_info['type']} (nullable: {col_info['nullable']})")
            
            if missing_cols:
                print(f"   ⚠️  Columnas en producción que NO están en staging: {', '.join(missing_cols)}")
        else:
            print(f"   ✅ Estructura idéntica")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("📝 RESUMEN EJECUTIVO")
    print("=" * 80)
    
    print(f"\n1️⃣  Tablas nuevas a crear en producción: {len(new_tables)}")
    if new_tables:
        for table in sorted(new_tables):
            print(f"    - {table}")
    
    print(f"\n2️⃣  Tablas con diferencias estructurales: {len(structural_differences)}")
    if structural_differences:
        for table in structural_differences:
            print(f"    - {table}")
    
    print(f"\n3️⃣  Tablas que ya existen y son idénticas: {len(common_tables) - len(structural_differences)}")
    
    print("\n" + "=" * 80)
    print("⚠️  TABLAS CRÍTICAS QUE NO SE TOCARÁN:")
    print("=" * 80)
    
    # Identificar tablas críticas de usuarios/proyectos
    critical_keywords = ['user', 'project', 'billing', 'payment', 'subscription', 'plan']
    critical_tables = []
    
    for table in prod_tables:
        for keyword in critical_keywords:
            if keyword in table.lower():
                critical_tables.append(table)
                break
    
    if critical_tables:
        for table in sorted(set(critical_tables)):
            count = get_table_row_count(prod_conn, table)
            print(f"   ✋ {table} ({count} filas) - SE PRESERVARÁ INTACTA")
    
    print("\n" + "=" * 80)
    print("✅ ANÁLISIS COMPLETADO")
    print("=" * 80)
    
    # Cerrar conexiones
    staging_conn.close()
    prod_conn.close()
    
    print("\n📌 SIGUIENTE PASO:")
    print("   Revisar este análisis y confirmar antes de crear el script de migración")

if __name__ == "__main__":
    main()

