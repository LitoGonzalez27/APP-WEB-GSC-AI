#!/usr/bin/env python3
"""
Debug de conexión a base de datos
================================

Script para diagnosticar problemas de conexión antes de migrar.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def test_connection_debug():
    """Probar conexión con debug completo"""
    print("🔍 DEBUG DE CONEXIÓN A BASE DE DATOS")
    print("=" * 50)
    
    # Mostrar variables
    database_url = os.getenv('DATABASE_URL')
    app_env = os.getenv('APP_ENV', 'unknown')
    
    print(f"APP_ENV: {app_env}")
    print(f"DATABASE_URL configurada: {'SÍ' if database_url else 'NO'}")
    
    if database_url:
        # Ocultar password en el log
        safe_url = database_url.replace(database_url.split('@')[0].split(':')[-1], '***')
        print(f"URL (safe): {safe_url}")
    
    if not database_url:
        print("❌ DATABASE_URL no configurada")
        return False
    
    # Intentar conexión
    print("\n🔌 Intentando conectar...")
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        print("✅ Conexión establecida!")
        
        cur = conn.cursor()
        
        # Verificar base de datos
        cur.execute("SELECT current_database(), current_user, version()")
        db_info = cur.fetchone()
        print(f"📊 Base de datos: {db_info['current_database']}")
        print(f"👤 Usuario: {db_info['current_user']}")
        print(f"🐘 PostgreSQL: {db_info['version'].split(',')[0]}")
        
        # Listar tablas
        print("\n📋 Tablas existentes:")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        if tables:
            for table in tables:
                print(f"   - {table['table_name']}")
        else:
            print("   (No hay tablas)")
        
        # Si existe tabla users, mostrar info básica
        if any(table['table_name'] == 'users' for table in tables):
            print("\n👥 Información de tabla users:")
            cur.execute("SELECT COUNT(*) as count FROM users")
            user_count = cur.fetchone()['count']
            print(f"   Total usuarios: {user_count}")
            
            if user_count > 0:
                cur.execute("SELECT email, role, is_active FROM users LIMIT 3")
                sample_users = cur.fetchall()
                print("   Usuarios ejemplo:")
                for user in sample_users:
                    print(f"     - {user['email']} (role: {user['role']}, active: {user['is_active']})")
        
        conn.close()
        print("\n✅ Conexión cerrada correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print(f"Tipo de error: {type(e).__name__}")
        return False

if __name__ == "__main__":
    test_connection_debug()
