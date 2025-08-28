#!/usr/bin/env python3
"""
VERIFICACIÓN MIGRACIÓN ENTERPRISE QUOTAS
=======================================

Verifica que la migración de custom quotas se aplicó correctamente
"""

import os
import psycopg2
import psycopg2.extras

def connect_db():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL no está configurado")
    
    return psycopg2.connect(database_url)

def verify_schema():
    """Verifica la estructura de la base de datos"""
    
    conn = connect_db()
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            print("🔍 VERIFICACIÓN SCHEMA POST-ENTERPRISE MIGRATION")
            print("=" * 50)
            
            # 1. Verificar columnas custom_quota
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name LIKE 'custom_quota%'
                ORDER BY column_name;
            """)
            
            columns = cur.fetchall()
            expected_columns = [
                'custom_quota_assigned_by',
                'custom_quota_assigned_date', 
                'custom_quota_limit',
                'custom_quota_notes'
            ]
            
            found_columns = [col['column_name'] for col in columns]
            
            print(f"📝 Columnas custom_quota:")
            for expected in expected_columns:
                if expected in found_columns:
                    col_info = next(col for col in columns if col['column_name'] == expected)
                    print(f"   ✅ {expected}: {col_info['data_type']} (nullable: {col_info['is_nullable']})")
                else:
                    print(f"   ❌ {expected}: NO ENCONTRADA")
            
            # 2. Verificar constraints de plan
            cur.execute("""
                SELECT 
                    tc.constraint_name, 
                    cc.check_clause
                FROM information_schema.table_constraints tc
                JOIN information_schema.check_constraints cc 
                ON tc.constraint_name = cc.constraint_name
                WHERE tc.table_name = 'users' 
                AND tc.constraint_name LIKE '%plan%'
                ORDER BY tc.constraint_name;
            """)
            
            constraints = cur.fetchall()
            print(f"\n📋 Constraints de plan:")
            
            plan_constraint_found = False
            current_plan_constraint_found = False
            
            for constraint in constraints:
                name = constraint['constraint_name']
                clause = constraint['check_clause']
                print(f"   - {name}: {clause}")
                
                if 'enterprise' in clause.lower():
                    if 'current_plan' in name:
                        current_plan_constraint_found = True
                    elif 'plan' in name:
                        plan_constraint_found = True
            
            if plan_constraint_found and current_plan_constraint_found:
                print("   ✅ Constraints incluyen 'enterprise' correctamente")
            else:
                print("   ❌ Constraints no incluyen 'enterprise'")
            
            # 3. Verificar datos de usuarios
            cur.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN plan = 'free' THEN 1 END) as free_users,
                    COUNT(CASE WHEN plan = 'basic' THEN 1 END) as basic_users,
                    COUNT(CASE WHEN plan = 'premium' THEN 1 END) as premium_users,
                    COUNT(CASE WHEN plan = 'enterprise' THEN 1 END) as enterprise_users,
                    COUNT(CASE WHEN custom_quota_limit IS NOT NULL THEN 1 END) as users_with_custom_quota
                FROM users;
            """)
            
            stats = cur.fetchone()
            print(f"\n📊 Estadísticas de usuarios:")
            print(f"   Total: {stats['total_users']}")
            print(f"   Free: {stats['free_users']}")
            print(f"   Basic: {stats['basic_users']}")
            print(f"   Premium: {stats['premium_users']}")
            print(f"   Enterprise: {stats['enterprise_users']}")
            print(f"   Con custom quota: {stats['users_with_custom_quota']}")
            
            # 4. Verificar estructura completa de tabla users
            cur.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position;
            """)
            
            all_columns = cur.fetchall()
            print(f"\n📋 Estructura completa tabla 'users' ({len(all_columns)} columnas):")
            
            billing_columns = ['plan', 'current_plan', 'quota_limit', 'quota_used', 'quota_reset_date', 
                             'subscription_status', 'subscription_id', 'customer_id']
            custom_quota_columns = ['custom_quota_limit', 'custom_quota_notes', 
                                  'custom_quota_assigned_by', 'custom_quota_assigned_date']
            
            for col in all_columns:
                name = col['column_name']
                if name in billing_columns:
                    print(f"   💳 {name}: {col['data_type']}")
                elif name in custom_quota_columns:
                    print(f"   🎯 {name}: {col['data_type']}")
                else:
                    print(f"   📝 {name}: {col['data_type']}")
            
            print("\n✅ VERIFICACIÓN COMPLETADA")
            return True
            
    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    verify_schema()
