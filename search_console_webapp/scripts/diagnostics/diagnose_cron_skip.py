#!/usr/bin/env python3
"""
Diagnosticar por qué el CRON está saltando el proyecto
"""

from database import get_db_connection

def diagnose():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("DIAGNÓSTICO: Por qué el CRON salta el proyecto AI Mode")
    print("="*80 + "\n")
    
    # 1. Ver configuración del proyecto
    cur.execute("""
        SELECT id, name, brand_name, is_active, user_id, country_code
        FROM ai_mode_projects
        WHERE id = 1
    """)
    project = cur.fetchone()
    
    print("📋 PROYECTO AI MODE (ID: 1):")
    if project:
        print(f"   Nombre: {project['name']}")
        print(f"   Brand: {project['brand_name']}")
        print(f"   Is Active: {project['is_active']}")
        print(f"   User ID: {project['user_id']}")
        print(f"   Country: {project['country_code']}")
    else:
        print("   ❌ Proyecto no encontrado")
        cur.close()
        conn.close()
        return
    
    print()
    
    # 2. Ver configuración del usuario
    cur.execute("""
        SELECT id, email, plan, billing_status
        FROM users
        WHERE id = %s
    """, (project['user_id'],))
    user = cur.fetchone()
    
    print(f"👤 USUARIO (ID: {project['user_id']}):")
    if user:
        print(f"   Email: {user['email']}")
        print(f"   Plan: '{user['plan']}'")
        print(f"   Billing Status: '{user['billing_status']}'")
    else:
        print("   ❌ Usuario no encontrado")
    
    print()
    
    # 3. Ver keywords activas
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN is_active = true THEN 1 END) as active
        FROM ai_mode_keywords
        WHERE project_id = 1
    """)
    kw_stats = cur.fetchone()
    
    print("🔑 KEYWORDS:")
    print(f"   Total: {kw_stats['total']}")
    print(f"   Activas: {kw_stats['active']}")
    print()
    
    # 4. Simular la query del CRON
    cur.execute("""
        SELECT p.id, p.name, p.brand_name as domain, p.country_code, p.user_id,
               COUNT(k.id) as keyword_count,
               p.is_active as project_active,
               COALESCE(u.plan, 'free') as user_plan,
               COALESCE(u.billing_status, '') as billing_status
        FROM ai_mode_projects p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN ai_mode_keywords k ON p.id = k.project_id AND k.is_active = true
        WHERE p.id = 1
        GROUP BY p.id, p.name, p.brand_name, p.country_code, p.user_id, p.is_active, u.plan, u.billing_status
    """)
    
    cron_result = cur.fetchone()
    
    print("="*80)
    print("EVALUACIÓN DEL CRON:")
    print("="*80 + "\n")
    
    if cron_result:
        print("Condiciones para que el CRON procese el proyecto:")
        print()
        
        # Condición 1: Proyecto activo
        cond1 = cron_result['project_active'] == True
        print(f"   1. Proyecto activo (is_active = true): {cond1}")
        if not cond1:
            print(f"      ❌ FALLO: is_active = {cron_result['project_active']}")
        else:
            print(f"      ✅ PASS")
        
        # Condición 2: Plan no gratuito
        cond2 = cron_result['user_plan'] != 'free'
        print(f"   2. Usuario con plan de pago (plan <> 'free'): {cond2}")
        if not cond2:
            print(f"      ❌ FALLO: plan = '{cron_result['user_plan']}'")
            print(f"      💡 SOLUCIÓN: Actualizar plan a 'basic', 'pro', o 'enterprise'")
        else:
            print(f"      ✅ PASS: plan = '{cron_result['user_plan']}'")
        
        # Condición 3: No cancelado
        cond3 = cron_result['billing_status'] not in ('canceled',)
        print(f"   3. Estado de facturación (billing_status NOT IN 'canceled'): {cond3}")
        if not cond3:
            print(f"      ❌ FALLO: billing_status = '{cron_result['billing_status']}'")
        else:
            print(f"      ✅ PASS: billing_status = '{cron_result['billing_status']}'")
        
        # Condición 4: Tiene keywords
        cond4 = cron_result['keyword_count'] > 0
        print(f"   4. Tiene keywords activas (count > 0): {cond4}")
        if not cond4:
            print(f"      ❌ FALLO: keyword_count = {cron_result['keyword_count']}")
        else:
            print(f"      ✅ PASS: keyword_count = {cron_result['keyword_count']}")
        
        print()
        print("="*80)
        
        if cond1 and cond2 and cond3 and cond4:
            print("✅ RESULTADO: El proyecto DEBERÍA ser procesado por el CRON")
        else:
            print("❌ RESULTADO: El proyecto será SALTADO por el CRON")
            print()
            print("🔧 ACCIONES REQUERIDAS:")
            if not cond1:
                print("   - Activar el proyecto: UPDATE ai_mode_projects SET is_active = true WHERE id = 1")
            if not cond2:
                print(f"   - Cambiar plan del usuario: UPDATE users SET plan = 'basic' WHERE id = {project['user_id']}")
            if not cond3:
                print(f"   - Actualizar billing_status: UPDATE users SET billing_status = 'active' WHERE id = {project['user_id']}")
            if not cond4:
                print("   - Activar keywords: UPDATE ai_mode_keywords SET is_active = true WHERE project_id = 1")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    diagnose()

