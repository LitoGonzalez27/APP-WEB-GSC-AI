#!/usr/bin/env python3
"""
Script de diagnóstico para el problema de registro en staging
Verifica el schema de la tabla users y las columnas de billing
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_staging_db_connection():
    """Conectar a la base de datos de staging"""
    # URL de staging desde Railway
    DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        logger.info("✅ Conectado a base de datos staging")
        return conn
    except Exception as e:
        logger.error(f"❌ Error conectando a staging: {e}")
        return None

def check_users_table_schema():
    """Verificar el schema completo de la tabla users"""
    conn = get_staging_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        print("\n" + "="*60)
        print("🔍 DIAGNÓSTICO TABLA USERS - STAGING")
        print("="*60)
        
        # 1. Verificar si la tabla existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            );
        """)
        table_exists = cur.fetchone()['exists']
        print(f"📋 Tabla 'users' existe: {'✅ SÍ' if table_exists else '❌ NO'}")
        
        if not table_exists:
            print("❌ ERROR: La tabla users no existe!")
            return False
        
        # 2. Obtener todas las columnas
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        
        print(f"\n📊 COLUMNAS ACTUALES ({len(columns)} total):")
        print("-" * 60)
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
            print(f"  • {col['column_name']:<25} {col['data_type']:<15} {nullable}{default}")
        
        # 3. Verificar columnas específicas de billing (Fase 1)
        billing_columns = ['plan', 'quota_limit', 'quota_used', 'billing_status', 'stripe_customer_id']
        print(f"\n🔍 VERIFICANDO COLUMNAS DE BILLING:")
        print("-" * 40)
        
        existing_columns = [col['column_name'] for col in columns]
        missing_billing = []
        
        for col in billing_columns:
            exists = col in existing_columns
            status = "✅ EXISTE" if exists else "❌ FALTA"
            print(f"  • {col:<20} {status}")
            if not exists:
                missing_billing.append(col)
        
        # 4. Diagnóstico del problema
        print(f"\n🎯 DIAGNÓSTICO:")
        print("-" * 30)
        
        if missing_billing:
            print(f"❌ PROBLEMA ENCONTRADO: Faltan {len(missing_billing)} columnas de billing")
            print(f"   Columnas faltantes: {', '.join(missing_billing)}")
            print(f"   💡 SOLUCIÓN: Ejecutar migración de Fase 1 en staging")
        else:
            print("✅ Todas las columnas de billing existen")
            print("   💡 El problema puede ser otro (constraints, permisos, etc.)")
        
        # 5. Contar usuarios existentes
        cur.execute("SELECT COUNT(*) as total FROM users")
        user_count = cur.fetchone()['total']
        print(f"\n👥 Usuarios existentes: {user_count}")
        
        # 6. Verificar últimos usuarios (si existen)
        if user_count > 0:
            cur.execute("""
                SELECT email, plan, is_active, created_at 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            recent_users = cur.fetchall()
            print(f"\n👤 ÚLTIMOS USUARIOS:")
            for user in recent_users:
                plan = user.get('plan', 'NULL')
                active = user.get('is_active', 'NULL')
                print(f"   • {user['email']} | plan: {plan} | active: {active}")
        
        return len(missing_billing) == 0
        
    except Exception as e:
        logger.error(f"❌ Error verificando schema: {e}")
        return False
    finally:
        if conn:
            conn.close()

def test_create_user_function():
    """Probar la función create_user con un usuario test"""
    conn = get_staging_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        print(f"\n🧪 TESTING FUNCIÓN CREATE_USER:")
        print("-" * 40)
        
        # Verificar lógica de detección de columnas
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name IN ('plan', 'quota_limit', 'quota_used')
        """)
        billing_columns = [row['column_name'] for row in cur.fetchall()]
        has_billing_columns = len(billing_columns) >= 3
        
        print(f"   Columnas billing encontradas: {billing_columns}")
        print(f"   has_billing_columns: {has_billing_columns}")
        
        if has_billing_columns:
            print("   ✅ Usaría INSERT con campos de billing")
        else:
            print("   ⚠️ Usaría INSERT sin campos de billing (compatibilidad)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing create_user: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🔍 INICIANDO DIAGNÓSTICO STAGING...")
    
    schema_ok = check_users_table_schema()
    test_create_user_function()
    
    print(f"\n" + "="*60)
    print("🎯 RESUMEN DIAGNÓSTICO")
    print("="*60)
    
    if schema_ok:
        print("✅ Schema parece correcto")
        print("💡 Problema puede ser: permisos, constraints, o lógica")
    else:
        print("❌ Schema tiene problemas")
        print("💡 ACCIÓN REQUERIDA: Ejecutar migración de Fase 1")
    
    print("\n🛠️ SIGUIENTE PASO:")
    print("   1. Si faltan columnas → ejecutar migrate_billing_simple.py")
    print("   2. Si schema OK → revisar lógica create_user en detail")
