#!/usr/bin/env python3
"""
FASE 1B - Migración de Roles Simplificada
=========================================

Este script simplifica los roles de:
  - user, admin, AI User
A:
  - user, admin

Migra usuarios con rol 'AI User' a 'user' para simplificar el sistema.
Los permisos de AI ahora dependen del plan de pago, no del rol.

SEGURO: No elimina usuarios, solo cambia roles.

Uso:
    python migrate_roles_phase1b.py
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_connection():
    """Obtiene conexión usando DATABASE_URL del entorno"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurado en el entorno")
        return None
    
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        logger.info("✅ Conexión a base de datos establecida")
        return conn
    except Exception as e:
        logger.error(f"❌ Error conectando a la base de datos: {e}")
        return None

def check_environment():
    """Verifica el entorno antes de ejecutar"""
    app_env = os.getenv('APP_ENV', 'unknown')
    railway_env = os.getenv('RAILWAY_ENVIRONMENT', 'unknown')
    
    logger.info(f"🌍 Entorno detectado: APP_ENV={app_env}, RAILWAY_ENVIRONMENT={railway_env}")
    
    if app_env == 'production' or railway_env == 'production':
        logger.warning("⚠️  EJECUTANDO EN PRODUCCIÓN")
        response = input("¿Estás seguro de que quieres ejecutar en producción? (escribe 'SI' para confirmar): ")
        if response != 'SI':
            logger.info("❌ Migración cancelada por el usuario")
            return False
    
    return True

def get_role_stats_before(conn):
    """Obtiene estadísticas de roles antes de la migración"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role")
        role_stats = cur.fetchall()
        
        logger.info("📊 Estadísticas de roles ANTES:")
        for role, count in role_stats:
            logger.info(f"   {role}: {count} usuarios")
        
        return dict(role_stats)
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas de roles: {e}")
        return None

def migrate_ai_users_to_users(conn):
    """Migra usuarios con rol 'AI User' a rol 'user'"""
    logger.info("🔧 Migrando 'AI User' → 'user'...")
    
    try:
        cur = conn.cursor()
        
        # Primero verificar cuántos AI Users hay
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'AI User'")
        ai_user_count = cur.fetchone()[0]
        
        if ai_user_count == 0:
            logger.info("   ℹ️ No hay usuarios con rol 'AI User' para migrar")
            return True
        
        logger.info(f"   🔄 Migrando {ai_user_count} usuarios 'AI User' → 'user'")
        
        # Migrar AI User → user
        cur.execute("""
            UPDATE users 
            SET role = 'user', updated_at = NOW()
            WHERE role = 'AI User'
        """)
        
        migrated_count = cur.rowcount
        conn.commit()
        
        logger.info(f"   ✅ {migrated_count} usuarios migrados correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error migrando roles: {e}")
        conn.rollback()
        return False

def update_role_constraint(conn):
    """Actualiza el constraint de roles para permitir solo 'user' y 'admin'"""
    logger.info("🔧 Actualizando constraints de roles...")
    
    try:
        cur = conn.cursor()
        
        # Eliminar constraint existente si existe
        cur.execute("""
            ALTER TABLE users 
            DROP CONSTRAINT IF EXISTS chk_user_role
        """)
        
        # Añadir nuevo constraint con solo user y admin
        cur.execute("""
            ALTER TABLE users 
            ADD CONSTRAINT chk_user_role 
            CHECK (role IN ('user', 'admin'))
        """)
        
        conn.commit()
        logger.info("   ✅ Constraint de roles actualizado")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error actualizando constraint: {e}")
        conn.rollback()
        return False

def get_role_stats_after(conn):
    """Obtiene estadísticas de roles después de la migración"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role")
        role_stats = cur.fetchall()
        
        logger.info("📊 Estadísticas de roles DESPUÉS:")
        for role, count in role_stats:
            logger.info(f"   {role}: {count} usuarios")
        
        return dict(role_stats)
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas finales: {e}")
        return None

def main():
    """Función principal de migración"""
    logger.info("🚀 INICIANDO MIGRACIÓN FASE 1B - SIMPLIFICACIÓN DE ROLES")
    logger.info("=" * 65)
    
    # Verificar entorno
    if not check_environment():
        return 1
    
    # Conectar a BD
    conn = get_database_connection()
    if not conn:
        return 1
    
    try:
        # Estadísticas antes
        stats_before = get_role_stats_before(conn)
        if stats_before is None:
            return 1
        
        # Ejecutar migración de roles
        if not migrate_ai_users_to_users(conn):
            return 1
        
        # Actualizar constraints
        if not update_role_constraint(conn):
            return 1
        
        # Estadísticas después
        stats_after = get_role_stats_after(conn)
        if stats_after is None:
            return 1
        
        # Verificar integridad
        total_before = sum(stats_before.values())
        total_after = sum(stats_after.values())
        
        if total_before != total_after:
            logger.error(f"❌ CRÍTICO: Número de usuarios cambió! Antes: {total_before}, Después: {total_after}")
            return 1
        
        logger.info("\n🎉 MIGRACIÓN DE ROLES COMPLETADA EXITOSAMENTE")
        logger.info("=" * 65)
        logger.info("📋 Resumen:")
        logger.info(f"   • Total usuarios preservados: {total_after}")
        logger.info(f"   • AI Users migrados a users: {stats_before.get('AI User', 0)}")
        logger.info("   • Nuevos roles permitidos: user, admin")
        logger.info("   • Los permisos de AI ahora dependen del plan de pago")
        logger.info("")
        logger.info("🎯 Sistema simplificado: funcionalidades por plan, no por rol")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error general en migración: {e}")
        return 1
        
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
