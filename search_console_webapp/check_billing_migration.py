#!/usr/bin/env python3
"""
Script de verificación para la migración de billing
==================================================

Verifica el estado de la migración sin hacer cambios.
Útil para comprobar que todo está correcto antes y después de la migración.

Uso:
    python check_billing_migration.py
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_connection():
    """Obtiene conexión usando DATABASE_URL del entorno"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurado")
        return None
    
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"❌ Error conectando: {e}")
        return None

def check_table_exists(conn, table_name):
    """Verifica si una tabla existe"""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """, (table_name,))
        
        return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Error verificando tabla {table_name}: {e}")
        return False

def check_column_exists(conn, table_name, column_name):
    """Verifica si una columna existe en una tabla"""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = %s 
                AND column_name = %s
            )
        """, (table_name, column_name))
        
        return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Error verificando columna {column_name} en {table_name}: {e}")
        return False

def get_user_stats(conn):
    """Obtiene estadísticas de usuarios"""
    try:
        cur = conn.cursor()
        
        # Total de usuarios
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        # Usuarios por plan (si la columna existe)
        plan_stats = {}
        if check_column_exists(conn, 'users', 'plan'):
            cur.execute("SELECT plan, COUNT(*) FROM users GROUP BY plan ORDER BY plan")
            plan_stats = dict(cur.fetchall())
        
        # Usuarios por billing_status (si la columna existe)
        status_stats = {}
        if check_column_exists(conn, 'users', 'billing_status'):
            cur.execute("SELECT billing_status, COUNT(*) FROM users GROUP BY billing_status ORDER BY billing_status")
            status_stats = dict(cur.fetchall())
        
        # Usuarios por rol (para verificar simplificación)
        cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role")
        role_stats = dict(cur.fetchall())
        
        return {
            'total_users': total_users,
            'plan_stats': plan_stats,
            'status_stats': status_stats,
            'role_stats': role_stats
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return None

def main():
    """Función principal de verificación"""
    logger.info("🔍 VERIFICANDO ESTADO DE MIGRACIÓN BILLING")
    logger.info("=" * 50)
    
    # Mostrar entorno
    app_env = os.getenv('APP_ENV', 'unknown')
    railway_env = os.getenv('RAILWAY_ENVIRONMENT', 'unknown')
    logger.info(f"🌍 Entorno: APP_ENV={app_env}, RAILWAY_ENVIRONMENT={railway_env}")
    
    # Conectar
    conn = get_database_connection()
    if not conn:
        return 1
    
    try:
        # Verificar tabla users
        logger.info("\n📋 Verificando tabla users...")
        if not check_table_exists(conn, 'users'):
            logger.error("❌ Tabla users no existe")
            return 1
        
        logger.info("✅ Tabla users existe")
        
        # Verificar campos de billing
        billing_fields = [
            'stripe_customer_id',
            'plan',
            'billing_status',
            'quota_limit',
            'quota_used',
            'quota_reset_date',
            'subscription_id',
            'current_period_start',
            'current_period_end',
            'current_plan',
            'pending_plan',
            'pending_plan_date'
        ]
        
        logger.info("\n🔧 Verificando campos de billing...")
        missing_fields = []
        for field in billing_fields:
            if check_column_exists(conn, 'users', field):
                logger.info(f"   ✅ {field}")
            else:
                logger.warning(f"   ❌ {field} - NO EXISTE")
                missing_fields.append(field)
        
        # Verificar tablas nuevas
        logger.info("\n📊 Verificando tablas de billing...")
        new_tables = ['quota_usage_events', 'subscriptions']
        for table in new_tables:
            if check_table_exists(conn, table):
                logger.info(f"   ✅ {table}")
            else:
                logger.warning(f"   ❌ {table} - NO EXISTE")
        
        # Estadísticas de usuarios
        logger.info("\n👥 Estadísticas de usuarios...")
        stats = get_user_stats(conn)
        if stats:
            logger.info(f"   Total usuarios: {stats['total_users']}")
            
            if stats['plan_stats']:
                logger.info("   Por plan:")
                for plan, count in stats['plan_stats'].items():
                    logger.info(f"     {plan}: {count}")
            
            if stats['status_stats']:
                logger.info("   Por estado billing:")
                for status, count in stats['status_stats'].items():
                    logger.info(f"     {status}: {count}")
            
            if stats['role_stats']:
                logger.info("   Por rol:")
                for role, count in stats['role_stats'].items():
                    logger.info(f"     {role}: {count}")
                
                # Verificar si hay roles obsoletos
                obsolete_roles = [role for role in stats['role_stats'].keys() 
                                if role not in ['user', 'admin']]
                if obsolete_roles:
                    logger.warning(f"   ⚠️  Roles obsoletos encontrados: {', '.join(obsolete_roles)}")
                    logger.warning("   Ejecuta: python migrate_roles_phase1b.py")
        
        # Resumen
        logger.info("\n📋 RESUMEN:")
        if missing_fields:
            logger.warning(f"⚠️  Migración INCOMPLETA - Faltan {len(missing_fields)} campos")
            logger.warning("   Campos faltantes: " + ", ".join(missing_fields))
            logger.info("   Ejecuta: python migrate_billing_phase1.py")
        else:
            logger.info("✅ Migración COMPLETA - Todos los campos existen")
            logger.info("🎯 Listo para Fase 2 - Variables de entorno")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error en verificación: {e}")
        return 1
        
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
