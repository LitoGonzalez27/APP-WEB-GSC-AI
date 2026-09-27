#!/usr/bin/env python3
"""
Simplificación de Roles - Versión Segura
========================================

Migra 'AI User' → 'user' para simplificar el sistema.
Los permisos de AI ahora dependen del plan de pago, no del rol.
"""

import os
import psycopg2

def safe_migrate_roles():
    """Migración segura de roles"""
    print("🔄 SIMPLIFICACIÓN DE ROLES (AI User → user)")
    print("=" * 50)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL no configurada")
        return False
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("✅ Conexión establecida")
        
        # 1. CONTAR USUARIOS Y ROLES ANTES
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
        roles_before = dict(cur.fetchall())
        
        print(f"📊 Total usuarios: {total_users}")
        print("📊 Roles ANTES:")
        for role, count in roles_before.items():
            print(f"   {role}: {count} usuarios")
        
        # 2. MIGRAR AI USER → USER
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'AI User'")
        ai_users = cur.fetchone()[0]
        
        if ai_users > 0:
            print(f"\n🔧 Migrando {ai_users} usuarios 'AI User' → 'user'...")
            
            cur.execute("""
                UPDATE users 
                SET role = 'user' 
                WHERE role = 'AI User'
            """)
            
            migrated = cur.rowcount
            print(f"   ✅ {migrated} usuarios migrados")
        else:
            print("\n ℹ️ No hay usuarios 'AI User' para migrar")
        
        # 3. VERIFICAR RESULTADOS
        cur.execute("SELECT COUNT(*) FROM users")
        total_after = cur.fetchone()[0]
        
        cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
        roles_after = dict(cur.fetchall())
        
        print(f"\n📊 Total usuarios DESPUÉS: {total_after}")
        print("📊 Roles DESPUÉS:")
        for role, count in roles_after.items():
            print(f"   {role}: {count} usuarios")
        
        # 4. VERIFICAR INTEGRIDAD
        if total_users != total_after:
            print("❌ CRÍTICO: Número de usuarios cambió!")
            conn.rollback()
            return False
        
        # 5. ASIGNAR PLANES BETA A USUARIOS ESPECÍFICOS
        print("\n🧪 Configurando beta testers...")
        
        # Admin y ex-AI Users → plan premium para testing
        cur.execute("""
            UPDATE users 
            SET 
                plan = 'premium',
                current_plan = 'premium',
                billing_status = 'beta',
                quota_limit = 2950,
                quota_used = 0
            WHERE role = 'admin' 
            OR email = 'seo@digitalsca.com'
        """)
        
        beta_count = cur.rowcount
        print(f"   ✅ {beta_count} beta testers configurados (plan premium)")
        
        # 6. MOSTRAR DISTRIBUCIÓN FINAL
        cur.execute("""
            SELECT 
                role,
                plan,
                billing_status,
                COUNT(*) 
            FROM users 
            GROUP BY role, plan, billing_status 
            ORDER BY role, plan
        """)
        
        distribution = cur.fetchall()
        print("\n📋 DISTRIBUCIÓN FINAL:")
        for role, plan, status, count in distribution:
            print(f"   {role} + {plan} ({status}): {count} usuarios")
        
        # 7. COMMIT FINAL
        conn.commit()
        conn.close()
        
        print("\n🎉 SIMPLIFICACIÓN DE ROLES COMPLETADA!")
        print("✅ Todos los usuarios preservados")
        print("✅ Sistema simplificado: user, admin")
        print("✅ Funcionalidades AI por plan, no por rol")
        print("✅ Beta testers configurados")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False

if __name__ == "__main__":
    safe_migrate_roles()
