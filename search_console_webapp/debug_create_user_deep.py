#!/usr/bin/env python3
"""
Debug profundo de create_user para capturar la excepción exacta
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import secrets
import logging
import traceback

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
    """Función de hash (copiada de database.py)"""
    if not password:
        return None
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + ':' + password_hash.hex()

def create_user_debug(email, name, password=None, google_id=None, picture=None, auto_activate=True):
    """Copia EXACTA de create_user con debug máximo"""
    conn = get_staging_db_connection()
    if not conn:
        print("❌ No connection")
        return None
    
    try:
        cur = conn.cursor()
        
        print(f"\n🔍 DEBUGGING CREATE_USER STEP BY STEP")
        print("="*50)
        print(f"📧 Email: {email}")
        print(f"👤 Name: {name}")
        print(f"🔑 Google ID: {google_id}")
        print(f"🖼️ Picture: {picture}")
        print(f"✅ Auto activate: {auto_activate}")
        
        # 1. Verificar si el usuario ya existe
        print(f"\n1️⃣ Verificando usuario existente...")
        cur.execute('SELECT id FROM users WHERE email = %s', (email,))
        existing = cur.fetchone()
        if existing:
            print(f"   ❌ Usuario ya existe: {existing['id']}")
            logger.warning(f"Usuario con email {email} ya existe")
            return None
        print(f"   ✅ Usuario no existe")
        
        # 2. Preparar datos del usuario
        print(f"\n2️⃣ Preparando datos...")
        password_hash = hash_password(password) if password else None
        is_active = auto_activate
        plan = 'free' if auto_activate else None
        
        print(f"   🔐 Password hash: {'SET' if password_hash else 'None'}")
        print(f"   ✅ Is active: {is_active}")
        print(f"   📋 Plan: {plan}")
        
        # 3. Verificar columnas de billing
        print(f"\n3️⃣ Verificando columnas billing...")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name IN ('plan', 'quota_limit', 'quota_used')
        """)
        billing_columns = [row['column_name'] for row in cur.fetchall()]
        has_billing_columns = len(billing_columns) >= 3
        
        print(f"   📋 Billing columns: {billing_columns}")
        print(f"   ✅ Has billing: {has_billing_columns}")
        
        # 4. Preparar query
        print(f"\n4️⃣ Preparando INSERT...")
        
        if has_billing_columns:
            insert_query = '''
                INSERT INTO users (email, name, password_hash, google_id, picture, 
                                  role, is_active, plan, quota_limit, quota_used)
                VALUES (%s, %s, %s, %s, %s, 'user', %s, %s, 0, 0)
                RETURNING id, email, name, picture, role, is_active, created_at, plan
            '''
            insert_params = (email, name, password_hash, google_id, picture, is_active, plan)
            print(f"   📝 Query: INSERT con billing")
        else:
            insert_query = '''
                INSERT INTO users (email, name, password_hash, google_id, picture, role, is_active)
                VALUES (%s, %s, %s, %s, %s, 'user', %s)
                RETURNING id, email, name, picture, role, is_active, created_at
            '''
            insert_params = (email, name, password_hash, google_id, picture, is_active)
            print(f"   📝 Query: INSERT sin billing")
        
        print(f"   📋 Params: {insert_params}")
        
        # 5. Verificar tipos de datos
        print(f"\n5️⃣ Verificando tipos de datos...")
        for i, param in enumerate(insert_params):
            param_type = type(param).__name__
            param_len = len(str(param)) if param else 0
            print(f"   {i+1}. {param_type:<10} | len: {param_len:<3} | value: {str(param)[:50]}")
        
        # 6. Ejecutar INSERT
        print(f"\n6️⃣ Ejecutando INSERT...")
        
        try:
            # Test syntax first
            print(f"   🧪 Testing query syntax...")
            cur.mogrify(insert_query, insert_params)
            print(f"   ✅ Query syntax OK")
            
            # Execute actual insert
            print(f"   💾 Executing INSERT...")
            cur.execute(insert_query, insert_params)
            
            print(f"   📥 Fetching result...")
            user = cur.fetchone()
            
            if user:
                print(f"   ✅ User fetched: {dict(user)}")
                
                print(f"   💾 Committing transaction...")
                conn.commit()
                print(f"   ✅ Transaction committed")
                
                print(f"   🎯 Returning user dict...")
                result = dict(user)
                print(f"   📤 Final result: {result}")
                return result
            else:
                print(f"   ❌ Query returned None")
                return None
                
        except Exception as insert_error:
            print(f"   ❌ INSERT ERROR: {insert_error}")
            print(f"   🔍 Error type: {type(insert_error).__name__}")
            print(f"   📋 Error args: {insert_error.args}")
            print(f"   🔄 Traceback:")
            traceback.print_exc()
            raise insert_error
        
    except Exception as e:
        print(f"\n❌ OUTER ERROR: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        print(f"📋 Error args: {e.args}")
        print(f"🔄 Full traceback:")
        traceback.print_exc()
        
        logger.error(f"Error creando usuario: {e}")
        return None
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🔍 DEBUG PROFUNDO CREATE_USER")
    print("="*60)
    
    # Test con datos que están fallando
    test_email = "debug-test@example.com"
    test_name = "Debug Test User"
    test_google_id = "107199513026819931699"  # Similar al real
    test_picture = "https://lh3.googleusercontent.com/test-picture"
    
    result = create_user_debug(
        email=test_email,
        name=test_name,
        google_id=test_google_id,
        picture=test_picture,
        auto_activate=True
    )
    
    print(f"\n🎯 RESULTADO FINAL:")
    print("="*30)
    if result:
        print(f"✅ SUCCESS: {result}")
    else:
        print(f"❌ FAILURE: create_user retornó None")
    
    # Cleanup
    conn = get_staging_db_connection()
    if conn and result:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM users WHERE email = %s', (test_email,))
            conn.commit()
            print(f"🧹 Usuario test eliminado")
        except:
            pass
        conn.close()
