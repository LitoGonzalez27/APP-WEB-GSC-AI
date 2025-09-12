#!/usr/bin/env python3
"""
FASE 1 - Migración de Base de Datos para Sistema de Billing
==========================================================

Este script añade los campos necesarios para el sistema de billing y cuotas
SIN tocar datos existentes de usuarios.

SEGURO: Solo añade campos nuevos, no modifica ni elimina nada existente.

Uso:
    python migrate_billing_phase1.py

Entornos soportados:
    - Staging: Usa DATABASE_URL de Railway staging
    - Production: Usa DATABASE_URL de Railway production
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime

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

def count_users_before(conn):
    """Cuenta usuarios antes de la migración"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        logger.info(f"📊 Usuarios existentes antes de migración: {count}")
        return count
    except Exception as e:
        logger.error(f"❌ Error contando usuarios: {e}")
        return None

def add_billing_fields(conn):
    """Añade campos de billing a la tabla users"""
    logger.info("🔧 Añadiendo campos de billing a tabla users...")
    
    try:
        cur = conn.cursor()
        
        # Campos de billing con valores por defecto seguros
        billing_fields = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_status VARCHAR(20) DEFAULT 'active'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_limit INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_used INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_reset_date TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_id VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_period_start TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_period_end TIMESTAMPTZ",
            # Campos para downgrades diferidos (Opción B)
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_plan VARCHAR(20) DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_plan VARCHAR(20)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_plan_date TIMESTAMPTZ"
        ]
        
        for field_sql in billing_fields:
            cur.execute(field_sql)
            logger.info(f"   ✅ {field_sql}")
        
        # Añadir constraints para integridad de datos
        constraints = [
            "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_plan CHECK (plan IN ('free', 'basic', 'premium'))",
            "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_billing_status CHECK (billing_status IN ('active', 'past_due', 'canceled', 'beta'))",
            "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_current_plan CHECK (current_plan IN ('free', 'basic', 'premium'))",
            "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_pending_plan CHECK (pending_plan IN ('free', 'basic', 'premium'))",
            "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_quota_limit CHECK (quota_limit >= 0)",
            "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS chk_quota_used CHECK (quota_used >= 0)"
        ]
        
        for constraint_sql in constraints:
            try:
                cur.execute(constraint_sql)
                logger.info(f"   ✅ {constraint_sql}")
            except Exception as e:
                # Los constraints pueden fallar si ya existen, no es crítico
                logger.warning(f"   ⚠️ Constraint ya existe o falló: {e}")
        
        conn.commit()
        logger.info("✅ Campos de billing añadidos correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error añadiendo campos de billing: {e}")
        conn.rollback()
        return False

def create_quota_usage_table(conn):
    """Crea la tabla para registrar uso de RU"""
    logger.info("🔧 Creando tabla quota_usage_events...")
    
    try:
        cur = conn.cursor()
        
        # Tabla para tracking de uso
        cur.execute("""
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
        """)
        
        # Índices para performance
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_quota_events_user_date ON quota_usage_events(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_quota_events_source ON quota_usage_events(source)",
            "CREATE INDEX IF NOT EXISTS idx_quota_events_timestamp ON quota_usage_events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_quota_events_user_month ON quota_usage_events(user_id, DATE_TRUNC('month', timestamp))"
        ]
        
        for index_sql in indices:
            cur.execute(index_sql)
            logger.info(f"   ✅ {index_sql}")
        
        conn.commit()
        logger.info("✅ Tabla quota_usage_events creada correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creando tabla quota_usage_events: {e}")
        conn.rollback()
        return False

def create_subscriptions_table(conn):
    """Crea tabla opcional para histórico de suscripciones"""
    logger.info("🔧 Creando tabla subscriptions (opcional)...")
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                stripe_subscription_id VARCHAR(255),
                plan VARCHAR(20),
                status VARCHAR(20),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                canceled_at TIMESTAMPTZ,
                period_start TIMESTAMPTZ,
                period_end TIMESTAMPTZ,
                metadata JSONB,
                
                -- Constraints
                CONSTRAINT chk_sub_plan CHECK (plan IN ('free', 'basic', 'premium')),
                CONSTRAINT chk_sub_status CHECK (status IN ('active', 'past_due', 'canceled', 'incomplete'))
            )
        """)
        
        # Índices
        cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)")
        
        conn.commit()
        logger.info("✅ Tabla subscriptions creada correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creando tabla subscriptions: {e}")
        conn.rollback()
        return False

def backfill_default_values(conn):
    """Rellena valores por defecto para usuarios existentes"""
    logger.info("🔧 Aplicando backfill con valores por defecto...")
    
    try:
        cur = conn.cursor()
        
        # Todos los usuarios empiezan en plan free
        cur.execute("""
            UPDATE users 
            SET 
                plan = 'free',
                current_plan = 'free',
                billing_status = 'active',
                quota_limit = 0,
                quota_used = 0
            WHERE plan IS NULL OR plan = ''
        """)
        
        updated_users = cur.rowcount
        logger.info(f"   ✅ {updated_users} usuarios actualizados con valores por defecto")
        
        # Marcar algunos usuarios como beta testers (solo en staging)
        app_env = os.getenv('APP_ENV', 'unknown')
        if app_env == 'staging':
            logger.info("🧪 Configurando beta testers en staging...")
            
            # Buscar admins o usuarios específicos para testing
            cur.execute("SELECT id, email, role FROM users WHERE role = 'admin' OR role = 'AI User' LIMIT 2")
            beta_users = cur.fetchall()
            
            for user in beta_users:
                cur.execute("""
                    UPDATE users 
                    SET 
                        plan = 'premium',
                        current_plan = 'premium',
                        billing_status = 'beta',
                        quota_limit = 2950,
                        quota_used = 0
                    WHERE id = %s
                """, (user['id'],))
                
                logger.info(f"   🧪 Beta tester configurado: {user['email']} (Plan Premium, 2950 RU)")
        
        conn.commit()
        logger.info("✅ Backfill completado correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en backfill: {e}")
        conn.rollback()
        return False

def add_billing_indices(conn):
    """Añade índices para optimizar consultas de billing"""
    logger.info("🔧 Añadiendo índices de billing...")
    
    try:
        cur = conn.cursor()
        
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan)",
            "CREATE INDEX IF NOT EXISTS idx_users_billing_status ON users(billing_status)",
            "CREATE INDEX IF NOT EXISTS idx_users_quota_reset ON users(quota_reset_date)",
            "CREATE INDEX IF NOT EXISTS idx_users_subscription_id ON users(subscription_id)"
        ]
        
        for index_sql in indices:
            cur.execute(index_sql)
            logger.info(f"   ✅ {index_sql}")
        
        conn.commit()
        logger.info("✅ Índices de billing añadidos correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error añadiendo índices: {e}")
        conn.rollback()
        return False

def count_users_after(conn):
    """Cuenta usuarios después de la migración y verifica integridad"""
    try:
        cur = conn.cursor()
        
        # Contar total
        cur.execute("SELECT COUNT(*) FROM users")
        total_count = cur.fetchone()[0]
        
        # Contar por plan
        cur.execute("SELECT plan, COUNT(*) FROM users GROUP BY plan ORDER BY plan")
        plan_stats = cur.fetchall()
        
        # Contar por billing_status
        cur.execute("SELECT billing_status, COUNT(*) FROM users GROUP BY billing_status ORDER BY billing_status")
        status_stats = cur.fetchall()
        
        logger.info(f"📊 Usuarios después de migración: {total_count}")
        logger.info("📊 Distribución por plan:")
        for plan, count in plan_stats:
            logger.info(f"   {plan}: {count} usuarios")
        
        logger.info("📊 Distribución por estado:")
        for status, count in status_stats:
            logger.info(f"   {status}: {count} usuarios")
        
        return total_count
        
    except Exception as e:
        logger.error(f"❌ Error contando usuarios después: {e}")
        return None

def main():
    """Función principal de migración"""
    logger.info("🚀 INICIANDO MIGRACIÓN FASE 1 - SISTEMA DE BILLING")
    logger.info("=" * 60)
    
    # Verificar entorno
    if not check_environment():
        return 1
    
    # Conectar a BD
    conn = get_database_connection()
    if not conn:
        return 1
    
    try:
        # Contar usuarios antes
        users_before = count_users_before(conn)
        if users_before is None:
            return 1
        
        # Ejecutar migraciones paso a paso
        steps = [
            ("Añadir campos de billing", add_billing_fields),
            ("Crear tabla quota_usage_events", create_quota_usage_table),
            ("Crear tabla subscriptions", create_subscriptions_table),
            ("Aplicar backfill", backfill_default_values),
            ("Añadir índices", add_billing_indices)
        ]
        
        for step_name, step_function in steps:
            logger.info(f"\n🔄 Ejecutando: {step_name}...")
            if not step_function(conn):
                logger.error(f"❌ Falló: {step_name}")
                return 1
            logger.info(f"✅ Completado: {step_name}")
        
        # Verificar integridad final
        users_after = count_users_after(conn)
        if users_after is None:
            return 1
        
        if users_before != users_after:
            logger.error(f"❌ CRÍTICO: Número de usuarios cambió! Antes: {users_before}, Después: {users_after}")
            return 1
        
        logger.info("\n🎉 MIGRACIÓN FASE 1 COMPLETADA EXITOSAMENTE")
        logger.info("=" * 60)
        logger.info("📋 Resumen:")
        logger.info(f"   • Usuarios preservados: {users_after}")
        logger.info("   • Campos de billing añadidos: 12")
        logger.info("   • Tablas nuevas creadas: 2 (quota_usage_events, subscriptions)")
        logger.info("   • Índices añadidos: 9")
        logger.info("   • Plan por defecto: free (0 RU)")
        logger.info("")
        logger.info("🎯 Próximo paso: Fase 2 - Configurar variables de entorno")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error general en migración: {e}")
        return 1
        
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
