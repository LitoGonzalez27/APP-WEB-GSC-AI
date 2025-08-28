#!/usr/bin/env python3
"""
Debug específico del problema Google OAuth en staging
Verifica usuarios duplicados y datos específicos que causan el fallo
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
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

def check_failed_emails():
    """Verificar los emails específicos que fallaron según los logs"""
    failed_emails = [
        "infokreativework@gmail.com",
        "cgonddb@gmail.com"
    ]
    
    conn = get_staging_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        print("\n🔍 VERIFICANDO EMAILS QUE FALLARON EN LOS LOGS")
        print("="*60)
        
        for email in failed_emails:
            print(f"\n📧 Verificando: {email}")
            print("-" * 40)
            
            # 1. Buscar por email
            cur.execute('SELECT id, email, google_id, is_active, plan, created_at FROM users WHERE email = %s', (email,))
            user_by_email = cur.fetchone()
            
            if user_by_email:
                print(f"   ❌ USUARIO YA EXISTE POR EMAIL!")
                print(f"      ID: {user_by_email['id']}")
                print(f"      Google ID: {user_by_email['google_id']}")
                print(f"      Active: {user_by_email['is_active']}")
                print(f"      Plan: {user_by_email['plan']}")
                print(f"      Creado: {user_by_email['created_at']}")
                print(f"   💡 ESTE ES EL PROBLEMA: Usuario duplicado")
            else:
                print(f"   ✅ Email no existe en BD")
        
        # 2. Mostrar todos los usuarios actuales
        print(f"\n👥 TODOS LOS USUARIOS ACTUALES:")
        print("-" * 40)
        cur.execute('''
            SELECT id, email, google_id, is_active, plan, created_at 
            FROM users 
            ORDER BY created_at DESC
        ''')
        all_users = cur.fetchall()
        
        for i, user in enumerate(all_users, 1):
            google_id_short = user['google_id'][:10] + "..." if user['google_id'] else "None"
            print(f"   {i:2d}. {user['email']:<25} | GoogleID: {google_id_short:<15} | Plan: {user['plan']:<10} | Active: {user['is_active']}")
        
        # 3. Verificar constraints únicos
        print(f"\n🔍 VERIFICANDO CONSTRAINTS ÚNICOS:")
        print("-" * 40)
        
        # Verificar constraint de email único
        cur.execute('''
            SELECT email, COUNT(*) as count 
            FROM users 
            GROUP BY email 
            HAVING COUNT(*) > 1
        ''')
        duplicate_emails = cur.fetchall()
        
        if duplicate_emails:
            print(f"   ❌ EMAILS DUPLICADOS encontrados:")
            for dup in duplicate_emails:
                print(f"      • {dup['email']}: {dup['count']} veces")
        else:
            print(f"   ✅ No hay emails duplicados")
        
        # Verificar constraint de google_id único
        cur.execute('''
            SELECT google_id, COUNT(*) as count 
            FROM users 
            WHERE google_id IS NOT NULL
            GROUP BY google_id 
            HAVING COUNT(*) > 1
        ''')
        duplicate_google_ids = cur.fetchall()
        
        if duplicate_google_ids:
            print(f"   ❌ GOOGLE_IDs DUPLICADOS encontrados:")
            for dup in duplicate_google_ids:
                print(f"      • {dup['google_id']}: {dup['count']} veces")
        else:
            print(f"   ✅ No hay Google IDs duplicados")
        
    except Exception as e:
        logger.error(f"❌ Error verificando: {e}")
    finally:
        if conn:
            conn.close()

def test_create_user_with_real_data():
    """Test create_user con los datos reales que están fallando"""
    
    # Datos similares a los que fallan en logs
    test_cases = [
        {
            'email': 'test-cgonddb@gmail.com',  # Similar al que falló
            'name': 'Carlos Test',
            'google_id': '107199513026819931699',  # Similar pattern
            'picture': 'https://lh3.googleusercontent.com/test'
        },
        {
            'email': 'test-infokreative@gmail.com',  # Similar al que falló
            'name': 'Info Test',
            'google_id': '207199513026819931699',  # Diferente ID
            'picture': 'https://lh3.googleusercontent.com/test2'
        }
    ]
    
    conn = get_staging_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        print(f"\n🧪 TESTING CREATE_USER CON DATOS REALES:")
        print("="*50)
        
        for i, test_data in enumerate(test_cases, 1):
            print(f"\n{i}️⃣ Test case {i}: {test_data['email']}")
            print("-" * 40)
            
            # Verificar si ya existe
            cur.execute('SELECT id FROM users WHERE email = %s OR google_id = %s', 
                       (test_data['email'], test_data['google_id']))
            existing = cur.fetchone()
            
            if existing:
                print(f"   ⚠️ Usuario ya existe, saltando test")
                continue
            
            # Importar create_user y probar
            try:
                sys.path.append('.')
                from database import create_user
                
                result = create_user(
                    email=test_data['email'],
                    name=test_data['name'],
                    google_id=test_data['google_id'],
                    picture=test_data['picture'],
                    auto_activate=True
                )
                
                if result:
                    print(f"   ✅ SUCCESS: Usuario creado ID {result['id']}")
                    # Limpiar después del test
                    cur.execute('DELETE FROM users WHERE id = %s', (result['id'],))
                    conn.commit()
                    print(f"   🧹 Usuario test eliminado")
                else:
                    print(f"   ❌ FAILURE: create_user retornó None")
                
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
                print(f"   🔍 Tipo: {type(e).__name__}")
        
    except Exception as e:
        logger.error(f"❌ Error en test: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🔍 DEBUG PROBLEMA GOOGLE OAUTH EN STAGING")
    print("="*60)
    
    check_failed_emails()
    test_create_user_with_real_data()
    
    print(f"\n🎯 CONCLUSIONES:")
    print("="*30)
    print("1. Si hay usuarios duplicados → ESTE ES EL PROBLEMA")
    print("2. Si no hay duplicados → problema en datos específicos OAuth")
    print("3. Si test manual funciona → problema en flujo OAuth timing")
