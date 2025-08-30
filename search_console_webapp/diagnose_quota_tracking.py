#!/usr/bin/env python3
"""
Diagnóstico de Tracking de Quota
===============================

Script para diagnosticar problemas de tracking de consumo de tokens.
Específicamente para resolver el problema de cgonddb@gmail.com.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway')

def get_db_connection():
    """Obtiene conexión a la base de datos"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Error conectando a la base de datos: {e}")
        return None

def diagnose_user_quota(email):
    """Diagnostica el estado de quota de un usuario específico"""
    print(f"\n🔍 DIAGNÓSTICO DE QUOTA PARA: {email}")
    print("=" * 60)
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return
    
    cur = conn.cursor()
    
    try:
        # 1. Verificar que el usuario existe
        cur.execute('SELECT id, email, name, plan, quota_used, quota_limit FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        
        if not user:
            print(f"❌ Usuario {email} no encontrado")
            return
        
        user_dict = dict(user)
        print(f"✅ Usuario encontrado:")
        print(f"   ID: {user_dict['id']}")
        print(f"   Nombre: {user_dict['name']}")
        print(f"   Plan: {user_dict['plan']}")
        print(f"   Quota Usada: {user_dict['quota_used']}")
        print(f"   Quota Límite: {user_dict['quota_limit']}")
        
        # 2. Verificar si existe la tabla quota_usage_events
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'quota_usage_events'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("\n❌ Tabla quota_usage_events NO EXISTE")
            print("🔧 Creando tabla...")
            create_quota_table(cur)
            conn.commit()
        else:
            print("\n✅ Tabla quota_usage_events existe")
        
        # 3. Verificar eventos de uso en los últimos 7 días
        cur.execute("""
            SELECT 
                timestamp, ru_consumed, source, keyword, country_code, metadata
            FROM quota_usage_events 
            WHERE user_id = %s 
            AND timestamp >= NOW() - INTERVAL '7 days'
            ORDER BY timestamp DESC
            LIMIT 20
        """, (user_dict['id'],))
        
        events = cur.fetchall()
        
        if events:
            print(f"\n✅ Eventos de uso encontrados ({len(events)}):")
            for event in events:
                print(f"   📅 {event['timestamp']} - {event['ru_consumed']} RU - {event['source']} - {event['keyword']}")
        else:
            print(f"\n❌ NO hay eventos de uso en los últimos 7 días para el usuario {user_dict['id']}")
            print("   Esto indica que el tracking NO está funcionando")
        
        # 4. Verificar eventos totales del usuario
        cur.execute("""
            SELECT 
                COUNT(*) as total_events,
                COALESCE(SUM(ru_consumed), 0) as total_ru,
                MAX(timestamp) as last_event
            FROM quota_usage_events 
            WHERE user_id = %s
        """, (user_dict['id'],))
        
        totals = cur.fetchone()
        
        print(f"\n📊 RESUMEN TOTAL:")
        print(f"   Total eventos: {totals['total_events']}")
        print(f"   Total RU registradas: {totals['total_ru']}")
        print(f"   Último evento: {totals['last_event']}")
        
        # 5. Comparar quota_used vs eventos registrados
        if totals['total_ru'] != user_dict['quota_used']:
            print(f"\n⚠️  INCONSISTENCIA DETECTADA:")
            print(f"   quota_used en users: {user_dict['quota_used']}")
            print(f"   Total RU en events: {totals['total_ru']}")
            print(f"   Diferencia: {user_dict['quota_used'] - totals['total_ru']}")

    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
    finally:
        conn.close()

def create_quota_table(cur):
    """Crea la tabla quota_usage_events"""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS quota_usage_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            ru_consumed INTEGER DEFAULT 1,
            source VARCHAR(50),
            keyword VARCHAR(255),
            country_code VARCHAR(3),
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            metadata JSONB,
            
            -- Constraints
            CONSTRAINT chk_ru_consumed CHECK (ru_consumed > 0),
            CONSTRAINT chk_source CHECK (source IN ('ai_overview', 'manual_ai', 'serp_api'))
        )
    ''')
    
    # Crear índices
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_quota_events_user_date ON quota_usage_events(user_id, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_quota_events_source ON quota_usage_events(source)",
        "CREATE INDEX IF NOT EXISTS idx_quota_events_timestamp ON quota_usage_events(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_quota_events_user_month ON quota_usage_events(user_id, DATE_TRUNC('month', timestamp))"
    ]
    
    for index_sql in indices:
        try:
            cur.execute(index_sql)
        except Exception:
            pass

def test_quota_tracking():
    """Prueba el sistema de tracking de quota"""
    print(f"\n🧪 PRUEBA DE TRACKING DE QUOTA")
    print("=" * 40)
    
    # Import the function
    try:
        import sys
        sys.path.append('.')
        from database import track_quota_consumption
        
        # Test con usuario específico
        conn = get_db_connection()
        if not conn:
            print("❌ No se pudo conectar para prueba")
            return
        
        cur = conn.cursor()
        cur.execute('SELECT id FROM users WHERE email = %s', ('cgonddb@gmail.com',))
        user = cur.fetchone()
        
        if not user:
            print("❌ Usuario cgonddb@gmail.com no encontrado para prueba")
            return
        
        user_id = user['id']
        print(f"✅ Probando tracking para usuario ID: {user_id}")
        
        # Hacer prueba de tracking
        success = track_quota_consumption(
            user_id=user_id,
            ru_consumed=1,
            source='ai_overview',
            keyword='test keyword diagnostic',
            country_code='ES',
            metadata={'test': True, 'diagnostic': True}
        )
        
        if success:
            print("✅ Tracking de prueba EXITOSO")
            
            # Verificar que se registró
            cur.execute("""
                SELECT ru_consumed, keyword FROM quota_usage_events 
                WHERE user_id = %s AND keyword = 'test keyword diagnostic'
                ORDER BY timestamp DESC LIMIT 1
            """, (user_id,))
            
            test_event = cur.fetchone()
            if test_event:
                print(f"✅ Evento de prueba encontrado: {test_event['ru_consumed']} RU para '{test_event['keyword']}'")
            else:
                print("❌ Evento de prueba NO encontrado")
        else:
            print("❌ Tracking de prueba FALLÓ")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Error en prueba de tracking: {e}")

def check_all_users_quota():
    """Revisa el estado de quota de todos los usuarios"""
    print(f"\n👥 ESTADO DE QUOTA DE TODOS LOS USUARIOS")
    print("=" * 50)
    
    conn = get_db_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                u.id, u.email, u.name, u.plan, 
                COALESCE(u.quota_used, 0) as quota_used,
                COALESCE(u.quota_limit, 0) as quota_limit,
                COALESCE(events.total_ru, 0) as events_total_ru,
                COALESCE(events.event_count, 0) as event_count
            FROM users u
            LEFT JOIN (
                SELECT 
                    user_id,
                    SUM(ru_consumed) as total_ru,
                    COUNT(*) as event_count
                FROM quota_usage_events
                GROUP BY user_id
            ) events ON u.id = events.user_id
            WHERE u.plan IN ('basic', 'premium')
            ORDER BY u.quota_used DESC
        """)
        
        users = cur.fetchall()
        
        print(f"📊 Usuarios con planes de pago ({len(users)}):")
        for user in users:
            quota_percent = (user['quota_used'] / user['quota_limit'] * 100) if user['quota_limit'] > 0 else 0
            inconsistent = user['quota_used'] != user['events_total_ru']
            status = "⚠️ " if inconsistent else "✅"
            
            print(f"   {status} {user['email']}")
            print(f"      Plan: {user['plan']} | Quota: {user['quota_used']}/{user['quota_limit']} ({quota_percent:.1f}%)")
            print(f"      Events: {user['event_count']} | RU en eventos: {user['events_total_ru']}")
            if inconsistent:
                print(f"      ⚠️  INCONSISTENCIA: Diferencia de {user['quota_used'] - user['events_total_ru']} RU")
            print()
            
    except Exception as e:
        logger.error(f"Error revisando usuarios: {e}")
    finally:
        conn.close()

def main():
    """Función principal de diagnóstico"""
    print("🔧 DIAGNÓSTICO DE SISTEMA DE TRACKING DE QUOTA")
    print("=" * 60)
    
    # 1. Diagnosticar usuario específico
    diagnose_user_quota('cgonddb@gmail.com')
    
    # 2. Probar tracking
    test_quota_tracking()
    
    # 3. Revisar todos los usuarios
    check_all_users_quota()
    
    print("\n🏁 DIAGNÓSTICO COMPLETADO")
    print("\n📋 ACCIONES RECOMENDADAS:")
    print("1. Si la tabla no existía, ya fue creada")
    print("2. Si hay inconsistencias, ejecutar un análisis y verificar logs")
    print("3. Revisar los logs del servidor para errores de tracking")

if __name__ == "__main__":
    main()
