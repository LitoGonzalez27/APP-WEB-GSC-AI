#!/usr/bin/env python3
"""
Test específico de la función create_user en staging
Simula exactamente lo que está haciendo el registro
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import secrets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_staging_db_connection():
    """Conectar a la base de datos de staging"""
    DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"❌ Error conectando: {e}")
        return None

def hash_password(password):
    """Función de hash (copiada de database.py original)"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + ':' + password_hash.hex()

def test_create_user_direct(email, name, google_id=None, picture=None, auto_activate=True):
    """Simula EXACTAMENTE la función create_user modificada"""
    conn = get_staging_db_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        
        print(f"\n🧪 TESTING CREATE_USER PARA: {email}")
        print("="*50)
        
        # 1. Verificar si el usuario ya existe
        print("1️⃣ Verificando si usuario existe...")
        cur.execute('SELECT id FROM users WHERE email = %s', (email,))
        existing = cur.fetchone()
        if existing:
            print(f"   ❌ Usuario ya existe con ID: {existing['id']}")
            return None
        else:
            print("   ✅ Usuario no existe, puede crear")
        
        # 2. Preparar datos del usuario
        print("2️⃣ Preparando datos...")
        password_hash = None  # No password for Google users
        is_active = auto_activate  # True para SaaS
        plan = 'free' if auto_activate else None
        print(f"   • is_active: {is_active}")
        print(f"   • plan: {plan}")
        print(f"   • google_id: {google_id}")
        
        # 3. Verificar si las columnas de billing existen (como en database.py)
        print("3️⃣ Verificando columnas de billing...")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name IN ('plan', 'quota_limit', 'quota_used')
        """)
        billing_columns = [row['column_name'] for row in cur.fetchall()]
        has_billing_columns = len(billing_columns) >= 3
        print(f"   • billing_columns encontradas: {billing_columns}")
        print(f"   • has_billing_columns: {has_billing_columns}")
        
        # 4. Ejecutar INSERT (como en database.py modificada)
        print("4️⃣ Ejecutando INSERT...")
        
        if has_billing_columns:
            print("   📝 Usando INSERT con campos de billing...")
            insert_query = '''
                INSERT INTO users (email, name, password_hash, google_id, picture, 
                                  role, is_active, plan, quota_limit, quota_used)
                VALUES (%s, %s, %s, %s, %s, 'user', %s, %s, 0, 0)
                RETURNING id, email, name, picture, role, is_active, created_at, plan
            '''
            insert_params = (email, name, password_hash, google_id, picture, is_active, plan)
        else:
            print("   📝 Usando INSERT sin campos de billing...")
            insert_query = '''
                INSERT INTO users (email, name, password_hash, google_id, picture, role, is_active)
                VALUES (%s, %s, %s, %s, %s, 'user', %s)
                RETURNING id, email, name, picture, role, is_active, created_at
            '''
            insert_params = (email, name, password_hash, google_id, picture, is_active)
        
        print(f"   💾 Query: {insert_query}")
        print(f"   📋 Params: {insert_params}")
        
        # Ejecutar la inserción
        cur.execute(insert_query, insert_params)
        user = cur.fetchone()
        
        if user:
            print(f"   ✅ INSERT exitoso!")
            print(f"   👤 Usuario retornado: {dict(user)}")
            
            # Confirmar transacción
            conn.commit()
            print(f"   💾 COMMIT exitoso")
            
            return dict(user)
        else:
            print(f"   ❌ INSERT retornó None")
            return None
        
    except Exception as e:
        print(f"   ❌ ERROR durante INSERT: {e}")
        print(f"   🔍 Tipo de error: {type(e).__name__}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def cleanup_test_user(email):
    """Limpiar usuario de test después de prueba"""
    conn = get_staging_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE email = %s', (email,))
        deleted = cur.rowcount
        conn.commit()
        if deleted > 0:
            print(f"🧹 Usuario test {email} eliminado")
    except Exception as e:
        print(f"⚠️ Error limpiando usuario test: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("🧪 TESTING CREATE_USER EN STAGING")
    print("="*60)
    
    # Test con datos similares a los del error
    test_email = "test-fase45@example.com"
    test_name = "Test Usuario Fase45"
    test_google_id = "123456789012345678901"
    test_picture = "https://example.com/picture.jpg"
    
    # Limpiar usuario test si existe
    cleanup_test_user(test_email)
    
    # Ejecutar test
    result = test_create_user_direct(
        email=test_email,
        name=test_name,
        google_id=test_google_id,
        picture=test_picture,
        auto_activate=True
    )
    
    print(f"\n🎯 RESULTADO FINAL:")
    print("="*30)
    if result:
        print(f"✅ SUCCESS: Usuario creado correctamente")
        print(f"   📋 Datos: {result}")
    else:
        print(f"❌ FAILURE: create_user retornó None")
    
    # Limpiar después del test
    cleanup_test_user(test_email)
    
    print(f"\n💡 SIGUIENTE PASO:")
    if result:
        print("   El problema NO está en create_user básico")
        print("   Revisar: constraints únicos, triggers, o auth.py")
    else:
        print("   El problema SÍ está en create_user")
        print("   Revisar: query SQL, permisos, o datos específicos")
