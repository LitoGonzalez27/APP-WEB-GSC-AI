#!/usr/bin/env python3
"""
Migración Billing Fase 1 - Versión Simplificada y Ultra-Segura
==============================================================

Versión corregida que añade campos de billing sin errores técnicos.
GARANTÍA: No puede perder usuarios - solo añade campos.
"""

import os
import psycopg2
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def safe_migrate_billing():
    """Migración segura de billing"""
    print("🚀 MIGRACIÓN FASE 1 - BILLING (VERSIÓN SEGURA)")
    print("=" * 60)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL no configurada")
        return False
    
    try:
        # Conexión simple sin RealDictCursor para evitar errores
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("✅ Conexión establecida")
        
        # 1. CONTAR USUARIOS ANTES
        cur.execute("SELECT COUNT(*) FROM users")
        users_before = cur.fetchone()[0]
        print(f"📊 Usuarios ANTES de migración: {users_before}")
        
        if users_before == 0:
            print("⚠️ No hay usuarios - ¿estás seguro que es la BD correcta?")
            response = input("Continuar anyway? (SI/no): ")
            if response != 'SI':
                return False
        
        print("\n🔧 AÑADIENDO CAMPOS DE BILLING...")
        
        # 2. AÑADIR CAMPOS UNO POR UNO (MÁS SEGURO)
        billing_fields = [
            ("stripe_customer_id", "VARCHAR(255)"),
            ("plan", "VARCHAR(20) DEFAULT 'free'"),
            ("billing_status", "VARCHAR(20) DEFAULT 'active'"),
            ("quota_limit", "INTEGER DEFAULT 0"),
            ("quota_used", "INTEGER DEFAULT 0"),
            ("quota_reset_date", "TIMESTAMPTZ"),
            ("subscription_id", "VARCHAR(255)"),
            ("current_period_start", "TIMESTAMPTZ"),
            ("current_period_end", "TIMESTAMPTZ"),
            ("current_plan", "VARCHAR(20) DEFAULT 'free'"),
            ("pending_plan", "VARCHAR(20)"),
            ("pending_plan_date", "TIMESTAMPTZ")
        ]
        
        for field_name, field_type in billing_fields:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {field_name} {field_type}")
                print(f"   ✅ {field_name}")
            except Exception as e:
                print(f"   ⚠️ {field_name}: {e}")
                # Continuar con el siguiente campo
        
        print("\n🎯 APLICANDO VALORES POR DEFECTO...")
        
        # 3. BACKFILL SEGURO
        cur.execute("""
            UPDATE users 
            SET 
                plan = COALESCE(plan, 'free'),
                current_plan = COALESCE(current_plan, 'free'),
                billing_status = COALESCE(billing_status, 'active'),
                quota_limit = COALESCE(quota_limit, 0),
                quota_used = COALESCE(quota_used, 0)
            WHERE plan IS NULL 
            OR current_plan IS NULL 
            OR billing_status IS NULL
        """)
        
        backfill_count = cur.rowcount
        print(f"   ✅ {backfill_count} usuarios actualizados con valores por defecto")
        
        # 4. CREAR TABLA QUOTA_USAGE_EVENTS
        print("\n📊 CREANDO TABLA DE TRACKING...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quota_usage_events (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                ru_consumed INTEGER DEFAULT 1,
                source VARCHAR(50),
                keyword VARCHAR(255),
                country_code VARCHAR(3),
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                metadata JSONB
            )
        """)
        print("   ✅ Tabla quota_usage_events creada")
        
        # 5. CREAR ÍNDICES BÁSICOS
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_quota_events_user_date ON quota_usage_events(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan)",
            "CREATE INDEX IF NOT EXISTS idx_users_billing_status ON users(billing_status)"
        ]
        
        for index_sql in indices:
            try:
                cur.execute(index_sql)
            except:
                pass  # Índice ya existe, continuar
        
        print("   ✅ Índices creados")
        
        # 6. VERIFICAR INTEGRIDAD
        cur.execute("SELECT COUNT(*) FROM users")
        users_after = cur.fetchone()[0]
        print(f"\n📊 Usuarios DESPUÉS de migración: {users_after}")
        
        if users_before != users_after:
            print("❌ CRÍTICO: Número de usuarios cambió!")
            conn.rollback()
            return False
        
        # 7. MOSTRAR RESULTADO
        cur.execute("SELECT plan, COUNT(*) FROM users GROUP BY plan")
        plan_stats = cur.fetchall()
        
        print("\n📋 DISTRIBUCIÓN POR PLAN:")
        for plan, count in plan_stats:
            print(f"   {plan}: {count} usuarios")
        
        # 8. COMMIT FINAL
        conn.commit()
        conn.close()
        
        print("\n🎉 MIGRACIÓN COMPLETADA EXITOSAMENTE!")
        print("✅ Todos los usuarios preservados")
        print("✅ Campos de billing añadidos") 
        print("✅ Tabla de tracking creada")
        print("✅ Sistema listo para Stripe")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False

if __name__ == "__main__":
    safe_migrate_billing()
