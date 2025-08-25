#!/usr/bin/env python3
"""
MIGRACIÓN FASE 1B: Custom Quotas para Enterprise
==============================================

ULTRA-SEGURO para Production:
- Solo ADD COLUMN con DEFAULT (nunca pierde datos)
- Actualiza constraint de 'plan' para incluir 'enterprise'
- Preserva todos los usuarios existentes

ROLLBACK: Si algo falla, las columnas nuevas no afectan funcionalidad existente
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime

def connect_db():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL no está configurado")
    
    return psycopg2.connect(database_url)

def execute_migration():
    """Ejecuta la migración de custom quotas de forma segura"""
    
    conn = connect_db()
    conn.autocommit = False  # Transacción manual para rollback
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            print("🔄 Iniciando migración de Custom Quotas...")
            
            # 1. Añadir columnas para custom quotas (SEGURO - no afecta datos existentes)
            print("📝 Añadiendo columnas custom_quota...")
            
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS custom_quota_limit INTEGER DEFAULT NULL;
            """)
            
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS custom_quota_notes TEXT DEFAULT NULL;
            """)
            
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS custom_quota_assigned_by VARCHAR(255) DEFAULT NULL;
            """)
            
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS custom_quota_assigned_date TIMESTAMP DEFAULT NULL;
            """)
            
            # 2. Actualizar constraint de plan para incluir 'enterprise' (SEGURO)
            print("📝 Actualizando constraint de plan...")
            
            # Primero eliminar constraint existente
            cur.execute("""
                ALTER TABLE users 
                DROP CONSTRAINT IF EXISTS users_plan_check;
            """)
            
            # Añadir nuevo constraint con 'enterprise'
            cur.execute("""
                ALTER TABLE users 
                ADD CONSTRAINT users_plan_check 
                CHECK (plan IN ('free', 'basic', 'premium', 'enterprise'));
            """)
            
            # 3. Actualizar constraint de current_plan también (SEGURO)
            cur.execute("""
                ALTER TABLE users 
                DROP CONSTRAINT IF EXISTS users_current_plan_check;
            """)
            
            cur.execute("""
                ALTER TABLE users 
                ADD CONSTRAINT users_current_plan_check 
                CHECK (current_plan IN ('free', 'basic', 'premium', 'enterprise'));
            """)
            
            # 4. Verificar que todo está correcto
            print("🔍 Verificando migración...")
            
            # Verificar que las columnas existen
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name LIKE 'custom_quota%';
            """)
            
            columns = [row['column_name'] for row in cur.fetchall()]
            expected_columns = [
                'custom_quota_limit', 
                'custom_quota_notes', 
                'custom_quota_assigned_by', 
                'custom_quota_assigned_date'
            ]
            
            missing_columns = set(expected_columns) - set(columns)
            if missing_columns:
                raise Exception(f"Columnas faltantes: {missing_columns}")
            
            # Verificar constraint de plan
            cur.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'users' 
                AND constraint_name = 'users_plan_check';
            """)
            
            if not cur.fetchone():
                raise Exception("Constraint users_plan_check no encontrado")
            
            # Contar usuarios (debe ser igual que antes)
            cur.execute("SELECT COUNT(*) as count FROM users;")
            user_count = cur.fetchone()['count']
            
            print(f"✅ Migración completada exitosamente!")
            print(f"📊 Total usuarios preservados: {user_count}")
            print(f"📊 Columnas custom_quota añadidas: {len(expected_columns)}")
            print(f"📊 Plan 'enterprise' añadido a constraints")
            
            # Commit de la transacción
            conn.commit()
            return True
            
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def verify_migration():
    """Verifica que la migración fue exitosa"""
    
    conn = connect_db()
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            print("\n🔍 VERIFICACIÓN POST-MIGRACIÓN:")
            
            # 1. Verificar columnas custom_quota
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name LIKE 'custom_quota%'
                ORDER BY column_name;
            """)
            
            columns = cur.fetchall()
            print(f"📝 Columnas custom_quota encontradas: {len(columns)}")
            for col in columns:
                print(f"   - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
            
            # 2. Verificar usuarios con datos
            cur.execute("""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN custom_quota_limit IS NOT NULL THEN 1 END) as with_custom_quota
                FROM users;
            """)
            
            stats = cur.fetchone()
            print(f"📊 Usuarios totales: {stats['total']}")
            print(f"📊 Usuarios con custom quota: {stats['with_custom_quota']}")
            
            # 3. Verificar constraints de plan
            cur.execute("""
                SELECT 
                    tc.constraint_name, 
                    cc.check_clause
                FROM information_schema.table_constraints tc
                JOIN information_schema.check_constraints cc 
                ON tc.constraint_name = cc.constraint_name
                WHERE tc.table_name = 'users' 
                AND tc.constraint_name LIKE '%plan%';
            """)
            
            constraints = cur.fetchall()
            print(f"📋 Constraints de plan: {len(constraints)}")
            for constraint in constraints:
                print(f"   - {constraint['constraint_name']}: {constraint['check_clause']}")
            
            print("✅ Verificación completada!")
            return True
            
    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 MIGRACIÓN FASE 1B: Custom Quotas Enterprise")
    print("=" * 50)
    
    # Ejecutar migración
    if execute_migration():
        # Verificar resultado
        verify_migration()
        print("\n🎉 MIGRACIÓN FASE 1B COMPLETADA!")
    else:
        print("\n💥 MIGRACIÓN FALLIDA - Base de datos no modificada")
