#!/usr/bin/env python3
"""
Verificación Completa - Fases 0 y 1
==================================

Script de verificación integral para confirmar que las Fases 0 y 1 
están correctamente implementadas antes de proceder con Fase 2.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

class PhaseVerifier:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.total_checks = 0
        
    def check(self, description, condition, error_msg=None, warning_msg=None):
        """Ejecutar una verificación y registrar resultado"""
        self.total_checks += 1
        print(f"  {'✅' if condition else '❌'} {description}")
        
        if condition:
            self.success_count += 1
        else:
            if error_msg:
                self.errors.append(f"{description}: {error_msg}")
            elif warning_msg:
                self.warnings.append(f"{description}: {warning_msg}")
            else:
                self.errors.append(description)
    
    def get_db_connection(self):
        """Obtener conexión a base de datos"""
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return None
        
        try:
            conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            self.errors.append(f"Database connection failed: {e}")
            return None

def verify_phase_0(verifier):
    """Verificar Fase 0 - Pre-flight y seguridad"""
    print("🚀 VERIFICANDO FASE 0 - PRE-FLIGHT Y SEGURIDAD")
    print("=" * 60)
    
    # 1. Variables de entorno
    print("\n📋 Variables de entorno:")
    app_env = os.getenv('APP_ENV')
    railway_env = os.getenv('RAILWAY_ENVIRONMENT')
    database_url = os.getenv('DATABASE_URL')
    
    verifier.check(
        "APP_ENV configurado", 
        app_env is not None,
        "Variable APP_ENV no está configurada"
    )
    
    verifier.check(
        "DATABASE_URL configurado", 
        database_url is not None,
        "Variable DATABASE_URL no está configurada"
    )
    
    if app_env:
        verifier.check(
            f"APP_ENV válido (actual: {app_env})",
            app_env in ['staging', 'production', 'development'],
            f"APP_ENV='{app_env}' no es válido. Debe ser: staging, production, development"
        )
    
    # 2. Entornos separados
    print("\n🌍 Separación de entornos:")
    if app_env == 'staging':
        verifier.check(
            "Estamos en STAGING (correcto para testing)",
            True
        )
    elif app_env == 'production':
        verifier.check(
            "Estamos en PRODUCTION",
            True,
            warning_msg="Asegúrate de no hacer testing en producción"
        )
    
    # 3. Políticas definidas (estas se verifican manualmente)
    print("\n📋 Políticas definidas (verificación manual):")
    print("  ℹ️  Downgrade policy: Opción B (mantener límites hasta próximo ciclo)")
    print("  ℹ️  UX messages: En inglés")
    print("  ℹ️  Planes: free (0 RU), basic (1,225 RU), premium (2,950 RU)")
    
    return True

def verify_phase_1(verifier):
    """Verificar Fase 1 - Migración de BD y roles"""
    print("\n🗃️  VERIFICANDO FASE 1 - MIGRACIÓN BD Y ROLES")
    print("=" * 60)
    
    conn = verifier.get_db_connection()
    if not conn:
        verifier.check("Conexión a base de datos", False, "No se pudo conectar")
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Verificar tabla users existe
        print("\n📊 Estructura de base de datos:")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        users_table_exists = cur.fetchone()[0]
        verifier.check("Tabla users existe", users_table_exists)
        
        if not users_table_exists:
            return False
        
        # 2. Contar usuarios
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        verifier.check(
            f"Usuarios preservados (encontrados: {user_count})",
            user_count > 0,
            "No se encontraron usuarios en la base de datos"
        )
        
        # 3. Verificar campos de billing
        print("\n💳 Campos de billing:")
        required_billing_fields = [
            'stripe_customer_id', 'plan', 'billing_status', 'quota_limit', 
            'quota_used', 'quota_reset_date', 'subscription_id', 
            'current_period_start', 'current_period_end', 'current_plan',
            'pending_plan', 'pending_plan_date'
        ]
        
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND table_schema = 'public'
        """)
        existing_columns = [row[0] for row in cur.fetchall()]
        
        for field in required_billing_fields:
            field_exists = field in existing_columns
            verifier.check(f"Campo {field}", field_exists)
        
        # 4. Verificar tabla quota_usage_events
        print("\n📈 Tabla de tracking:")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'quota_usage_events'
            )
        """)
        tracking_table_exists = cur.fetchone()[0]
        verifier.check("Tabla quota_usage_events existe", tracking_table_exists)
        
        # 5. Verificar roles simplificados
        print("\n🏷️  Roles simplificados:")
        cur.execute("SELECT DISTINCT role FROM users ORDER BY role")
        roles = [row[0] for row in cur.fetchall()]
        
        verifier.check(
            "Solo roles admin y user",
            set(roles).issubset({'admin', 'user'}),
            f"Roles encontrados: {roles}. Deberían ser solo: admin, user"
        )
        
        verifier.check(
            "No existe rol 'AI User'",
            'AI User' not in roles
        )
        
        # 6. Verificar distribución de planes
        print("\n📋 Distribución de planes:")
        cur.execute("SELECT plan, COUNT(*) FROM users GROUP BY plan ORDER BY plan")
        plan_distribution = cur.fetchall()
        
        plans_found = [row[0] for row in plan_distribution]
        valid_plans = {'free', 'basic', 'premium'}
        
        verifier.check(
            "Solo planes válidos",
            set(plans_found).issubset(valid_plans),
            f"Planes encontrados: {plans_found}. Deberían ser: {valid_plans}"
        )
        
        # Mostrar distribución actual
        for plan, count in plan_distribution:
            print(f"    {plan}: {count} usuarios")
        
        # 7. Verificar beta testers
        print("\n🧪 Beta testers:")
        cur.execute("SELECT COUNT(*) FROM users WHERE billing_status = 'beta'")
        beta_count = cur.fetchone()[0]
        
        verifier.check(
            "Beta testers configurados",
            beta_count > 0,
            warning_msg="No hay beta testers configurados"
        )
        
        if beta_count > 0:
            cur.execute("SELECT email, plan, quota_limit FROM users WHERE billing_status = 'beta'")
            beta_users = cur.fetchall()
            print(f"    Beta testers encontrados: {beta_count}")
            for user in beta_users:
                print(f"      - {user[0]} (plan: {user[1]}, quota: {user[2]})")
        
        # 8. Verificar integridad de datos
        print("\n🔍 Integridad de datos:")
        
        # Verificar que todos los usuarios tienen plan
        cur.execute("SELECT COUNT(*) FROM users WHERE plan IS NULL")
        users_without_plan = cur.fetchone()[0]
        verifier.check(
            "Todos los usuarios tienen plan asignado",
            users_without_plan == 0,
            f"{users_without_plan} usuarios sin plan asignado"
        )
        
        # Verificar que quota_limit es consistente con plan
        cur.execute("""
            SELECT plan, quota_limit, COUNT(*) 
            FROM users 
            GROUP BY plan, quota_limit 
            ORDER BY plan, quota_limit
        """)
        quota_consistency = cur.fetchall()
        
        print("    Consistencia quota_limit por plan:")
        expected_quotas = {'free': 0, 'basic': 1225, 'premium': 2950}
        for plan, quota, count in quota_consistency:
            expected = expected_quotas.get(plan, 'unknown')
            consistent = quota == expected
            symbol = "✅" if consistent else "⚠️"
            print(f"      {symbol} {plan}: {quota} RU ({count} usuarios) - esperado: {expected}")
        
        conn.close()
        return True
        
    except Exception as e:
        verifier.errors.append(f"Error verificando Fase 1: {e}")
        return False

def verify_admin_panel_access():
    """Verificar acceso al panel admin (verificación manual)"""
    print("\n👥 VERIFICACIÓN PANEL ADMIN (MANUAL)")
    print("=" * 60)
    print("  ℹ️  Para verificar el panel admin, por favor confirma:")
    print("     1. ¿Puedes acceder a /admin en tu aplicación?")
    print("     2. ¿Ves la tabla de usuarios con roles y estados?")
    print("     3. ¿Los usuarios tienen los roles correctos (admin/user)?")
    print("     4. ¿Puedes cambiar roles de usuarios?")
    print("  ")
    print("  📋 Panel billing (después de integrar las rutas):")
    print("     1. ¿Puedes acceder a /admin/billing?")
    print("     2. ¿Ves información de planes y cuotas?")
    print("     3. ¿Puedes cambiar planes manualmente?")

def main():
    """Función principal de verificación"""
    print("🔍 VERIFICACIÓN INTEGRAL - FASES 0 y 1")
    print("=" * 80)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Entorno: {os.getenv('APP_ENV', 'unknown')}")
    print("")
    
    verifier = PhaseVerifier()
    
    # Verificar Fase 0
    verify_phase_0(verifier)
    
    # Verificar Fase 1
    verify_phase_1(verifier)
    
    # Verificación manual del panel admin
    verify_admin_panel_access()
    
    # Resumen final
    print("\n📊 RESUMEN DE VERIFICACIÓN")
    print("=" * 80)
    print(f"✅ Verificaciones exitosas: {verifier.success_count}/{verifier.total_checks}")
    print(f"❌ Errores: {len(verifier.errors)}")
    print(f"⚠️  Advertencias: {len(verifier.warnings)}")
    
    if verifier.errors:
        print("\n❌ ERRORES ENCONTRADOS:")
        for i, error in enumerate(verifier.errors, 1):
            print(f"  {i}. {error}")
    
    if verifier.warnings:
        print("\n⚠️  ADVERTENCIAS:")
        for i, warning in enumerate(verifier.warnings, 1):
            print(f"  {i}. {warning}")
    
    # Determinar si están listos para Fase 2
    success_rate = verifier.success_count / verifier.total_checks if verifier.total_checks > 0 else 0
    
    if success_rate >= 0.9 and len(verifier.errors) == 0:
        print("\n🎉 VERIFICACIÓN EXITOSA - LISTO PARA FASE 2")
        print("   Todas las verificaciones críticas han pasado.")
        print("   Puedes proceder con confianza a la Fase 2.")
    elif success_rate >= 0.8:
        print("\n⚠️  VERIFICACIÓN PARCIAL - REVISAR ANTES DE FASE 2")
        print("   La mayoría de verificaciones han pasado, pero hay algunos problemas.")
        print("   Revisa los errores antes de continuar.")
    else:
        print("\n❌ VERIFICACIÓN FALLIDA - CORREGIR ANTES DE FASE 2")
        print("   Hay problemas críticos que deben resolverse.")
        print("   No procedas con Fase 2 hasta resolver estos problemas.")
    
    return len(verifier.errors) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
