#!/usr/bin/env python3
"""
Script para agregar la columna operation_type a quota_usage_events
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_quota_events_table():
    """Agrega columna operation_type a quota_usage_events"""
    
    print("=" * 80)
    print("🔧 ARREGLANDO TABLA quota_usage_events")
    print("=" * 80)
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ No se pudo conectar a la base de datos")
            return False
        
        cur = conn.cursor()
        
        # 1. Verificar si la columna ya existe
        print("\n1️⃣ Verificando estructura actual...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'quota_usage_events'
            ORDER BY ordinal_position
        """)
        
        columns = [row[0] if isinstance(row, tuple) else row['column_name'] for row in cur.fetchall()]
        print(f"   Columnas actuales: {', '.join(columns)}")
        
        # 2. Agregar columna operation_type si no existe
        if 'operation_type' not in columns:
            print("\n2️⃣ Agregando columna operation_type...")
            cur.execute("""
                ALTER TABLE quota_usage_events 
                ADD COLUMN operation_type VARCHAR(50)
            """)
            print("   ✅ Columna operation_type agregada")
        else:
            print("\n2️⃣ La columna operation_type ya existe")
        
        # 3. Agregar columna created_at si no existe
        if 'created_at' not in columns:
            print("\n3️⃣ Agregando columna created_at...")
            cur.execute("""
                ALTER TABLE quota_usage_events 
                ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW()
            """)
            print("   ✅ Columna created_at agregada")
        else:
            print("\n3️⃣ La columna created_at ya existe")
        
        # 4. Migrar datos de 'source' a 'operation_type' si es necesario
        if 'source' in columns and 'operation_type' in columns:
            print("\n4️⃣ Migrando datos de 'source' a 'operation_type'...")
            cur.execute("""
                UPDATE quota_usage_events 
                SET operation_type = source 
                WHERE operation_type IS NULL AND source IS NOT NULL
            """)
            migrated = cur.rowcount
            print(f"   ✅ {migrated} registros migrados")
        
        # 5. Verificar estructura final
        print("\n5️⃣ Verificando estructura final...")
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'quota_usage_events'
            ORDER BY ordinal_position
        """)
        
        print("\n📋 Estructura final de quota_usage_events:")
        for row in cur.fetchall():
            if isinstance(row, dict):
                col_name = row['column_name']
                data_type = row['data_type']
                nullable = row['is_nullable']
            else:
                col_name, data_type, nullable = row
            print(f"   • {col_name:<20} {data_type:<20} (NULL: {nullable})")
        
        # 6. Commit
        conn.commit()
        
        print("\n" + "=" * 80)
        print("✅ TABLA ARREGLADA EXITOSAMENTE")
        print("=" * 80)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    fix_quota_events_table()

