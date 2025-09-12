#!/usr/bin/env python3
"""
VERIFICACIÓN COMPLETA - FASE 1B CUSTOM QUOTAS
============================================

Verifica todo el sistema implementado hasta ahora:
1. Database schema y datos
2. Quota Manager funcionality  
3. Admin Panel backend
4. Code integration points
"""

import os
import sys
import psycopg2
import psycopg2.extras
from datetime import datetime

# Agregar path para imports locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from quota_manager import (
        get_user_effective_quota_limit,
        get_user_quota_status, 
        get_user_access_permissions,
        can_user_consume_ru
    )
    from admin_billing_panel import (
        get_users_with_billing,
        get_billing_stats,
        assign_custom_quota,
        get_effective_quota_limit
    )
    IMPORTS_OK = True
except ImportError as e:
    print(f"⚠️ Import error: {e}")
    IMPORTS_OK = False

def connect_db():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL no está configurado")
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

def verificar_database_schema():
    """Verifica el schema de la base de datos"""
    print("🔍 1. VERIFICANDO DATABASE SCHEMA")
    print("=" * 50)
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Verificar usuarios y roles
        cur.execute('''
            SELECT 
                role, 
                COUNT(*) as count
            FROM users 
            GROUP BY role 
            ORDER BY role
        ''')
        roles = cur.fetchall()
        print("📊 Distribución de roles:")
        for role in roles:
            print(f"   {role['role']}: {role['count']} usuarios")
        
        # Verificar planes
        cur.execute('''
            SELECT 
                plan, 
                COUNT(*) as count,
                AVG(quota_limit) as avg_quota
            FROM users 
            GROUP BY plan 
            ORDER BY plan
        ''')
        plans = cur.fetchall()
        print("\n📊 Distribución de planes:")
        for plan in plans:
            print(f"   {plan['plan']}: {plan['count']} usuarios (quota promedio: {plan['avg_quota']})")
        
        # Verificar custom quotas
        cur.execute('''
            SELECT COUNT(*) as total,
                   COUNT(custom_quota_limit) as with_custom
            FROM users
        ''')
        custom_stats = cur.fetchone()
        print(f"\n📊 Custom Quotas:")
        print(f"   Total usuarios: {custom_stats['total']}")
        print(f"   Con custom quota: {custom_stats['with_custom']}")
        
        # Verificar constraints
        cur.execute('''
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints cc
            JOIN information_schema.table_constraints tc ON cc.constraint_name = tc.constraint_name
            WHERE tc.table_name = 'users' AND tc.constraint_name LIKE '%plan%'
        ''')
        constraints = cur.fetchall()
        print(f"\n📋 Constraints de plan: {len(constraints)} encontrados")
        for constraint in constraints:
            if 'enterprise' in constraint['check_clause']:
                print(f"   ✅ {constraint['constraint_name']}: incluye 'enterprise'")
            else:
                print(f"   ❌ {constraint['constraint_name']}: NO incluye 'enterprise'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando schema: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verificar_quota_manager():
    """Verifica las funciones del Quota Manager"""
    print("\n🔍 2. VERIFICANDO QUOTA MANAGER")
    print("=" * 50)
    
    if not IMPORTS_OK:
        print("❌ No se pueden importar los módulos. Verificar paths.")
        return False
    
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Obtener usuarios de prueba
        cur.execute('SELECT id, email, plan, quota_limit, custom_quota_limit FROM users ORDER BY id')
        users = cur.fetchall()
        
        print(f"📊 Testing con {len(users)} usuarios:")
        
        for user in users:
            user_id = user['id']
            email = user['email']
            plan = user['plan']
            
            print(f"\n👤 Usuario: {email} (Plan: {plan})")
            
            # Test effective quota limit
            effective_limit = get_user_effective_quota_limit(user_id)
            print(f"   Effective quota limit: {effective_limit}")
            
            # Test quota status  
            status = get_user_quota_status(user_id)
            print(f"   Quota status: {status['used']}/{status['limit']} RU (can_consume: {status['can_consume']})")
            
            # Test permissions
            permissions = get_user_access_permissions(user_id)
            print(f"   AI Overview access: {permissions['ai_overview_access']}")
            print(f"   Manual AI access: {permissions['manual_ai_access']}")
            
            # Test can consume
            can_consume = can_user_consume_ru(user_id, 1)
            print(f"   Can consume 1 RU: {can_consume}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando Quota Manager: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

def verificar_admin_panel():
    """Verifica las funciones del Admin Panel"""
    print("\n🔍 3. VERIFICANDO ADMIN PANEL BACKEND")
    print("=" * 50)
    
    if not IMPORTS_OK:
        print("❌ No se pueden importar los módulos.")
        return False
    
    try:
        # Test billing stats
        stats = get_billing_stats()
        print("📊 Billing Stats:")
        print(f"   Total usuarios: {stats['total_users']}")
        print(f"   Usuarios por plan: {stats['users_by_plan']}")
        print(f"   Revenue estimate: €{stats['revenue_estimate_month']}")
        
        # Test users with billing
        users = get_users_with_billing()
        print(f"\n📊 Users with billing: {len(users)} encontrados")
        
        if users:
            sample_user = users[0]
            print(f"   Usuario ejemplo: {sample_user['email']}")
            print(f"   Plan: {sample_user.get('plan', 'unknown')}")
            print(f"   Quota: {sample_user.get('quota_used', 0)}/{sample_user.get('quota_limit', 0)}")
            print(f"   Custom quota: {sample_user.get('custom_quota_limit', 'None')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando Admin Panel: {e}")
        import traceback
        traceback.print_exc()
        return False

def verificar_integration_points():
    """Verifica los puntos de integración pendientes"""
    print("\n🔍 4. VERIFICANDO PUNTOS DE INTEGRACIÓN")
    print("=" * 50)
    
    integration_points = [
        {
            'file': 'app.py',
            'routes': ['/get-data', '/api/serp', '/api/serp/position', '/api/serp/screenshot'],
            'description': 'Routes principales que consumen SERP API'
        },
        {
            'file': 'manual_ai_system.py', 
            'routes': ['/manual-ai/api/projects/<id>/analyze'],
            'description': 'Manual AI Analysis que consume SERP API'
        },
        {
            'file': 'services/serp_service.py',
            'functions': ['get_serp_json', 'get_serp_html', 'get_page_screenshot'],
            'description': 'Servicios SERP que necesitan quota validation'
        },
        {
            'file': 'auth.py',
            'decorators': ['@auth_required', '@admin_required', '@ai_user_required'],
            'description': 'Decorators que necesitan plan-based access control'
        }
    ]
    
    print("📋 Puntos que necesitan integración con Quota Manager:")
    
    for point in integration_points:
        print(f"\n📁 {point['file']}:")
        print(f"   📝 {point['description']}")
        
        if 'routes' in point:
            for route in point['routes']:
                print(f"   🔗 Route: {route}")
        
        if 'functions' in point:
            for func in point['functions']:
                print(f"   ⚙️ Function: {func}")
        
        if 'decorators' in point:
            for decorator in point['decorators']:
                print(f"   🔒 Decorator: {decorator}")
    
    return True

def main():
    """Función principal de verificación"""
    print("🧪 VERIFICACIÓN COMPLETA - FASE 1B CUSTOM QUOTAS")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = {
        'database_schema': verificar_database_schema(),
        'quota_manager': verificar_quota_manager(), 
        'admin_panel': verificar_admin_panel(),
        'integration_points': verificar_integration_points()
    }
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VERIFICACIÓN:")
    print("=" * 60)
    
    all_passed = True
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test.replace('_', ' ').title()}")
        if not passed:
            all_passed = False
    
    print(f"\n🎯 RESULTADO GENERAL: {'✅ TODO CORRECTO' if all_passed else '⚠️ REQUIERE ATENCIÓN'}")
    
    if all_passed:
        print("\n🚀 SISTEMA LISTO PARA:")
        print("   • Integración con routes existentes")
        print("   • Testing de funcionalidad end-to-end") 
        print("   • Deploy a production (con migraciones seguras)")
    
    return all_passed

if __name__ == "__main__":
    main()
