#!/usr/bin/env python3
"""
Diagnóstico Simple Usuario - Solo base de datos
================================================

Diagnóstico simplificado sin dependencias de Stripe
para verificar estado del usuario en base de datos.
"""

import os
import sys
from database import get_db_connection

def diagnose_user_simple(email: str):
    """Diagnóstico simple del usuario en base de datos"""
    print(f"\n🔍 DIAGNÓSTICO SIMPLE PARA: {email}")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Error conectando a base de datos")
            return None
        
        cur = conn.cursor()
        cur.execute('''
            SELECT 
                id, email, name, role, is_active, 
                plan, billing_status, quota_limit, quota_used,
                stripe_customer_id, subscription_id,
                current_period_start, current_period_end,
                created_at, updated_at
            FROM users 
            WHERE email = %s
        ''', (email,))
        
        user = cur.fetchone()
        conn.close()
        
        if not user:
            print("❌ Usuario no encontrado en base de datos")
            return None
        
        user_dict = dict(user)
        
        print(f"📊 INFORMACIÓN DEL USUARIO:")
        print(f"   ID: {user_dict['id']}")
        print(f"   Email: {user_dict['email']}")
        print(f"   Nombre: {user_dict['name']}")
        print(f"   Rol: {user_dict['role']}")
        print(f"   Activo: {user_dict['is_active']}")
        print(f"   Plan: {user_dict.get('plan', 'N/A')}")
        print(f"   Billing Status: {user_dict.get('billing_status', 'N/A')}")
        print(f"   Quota Limit: {user_dict.get('quota_limit', 'N/A')}")
        print(f"   Quota Used: {user_dict.get('quota_used', 'N/A')}")
        print(f"   Stripe Customer ID: {user_dict.get('stripe_customer_id', 'N/A')}")
        print(f"   Subscription ID: {user_dict.get('subscription_id', 'N/A')}")
        print(f"   Período actual: {user_dict.get('current_period_start', 'N/A')} → {user_dict.get('current_period_end', 'N/A')}")
        print(f"   Creado: {user_dict['created_at']}")
        print(f"   Actualizado: {user_dict['updated_at']}")
        
        # Análisis
        plan = user_dict.get('plan', 'free')
        billing_status = user_dict.get('billing_status', 'inactive')
        stripe_customer_id = user_dict.get('stripe_customer_id')
        
        print(f"\n💡 ANÁLISIS:")
        print("-" * 30)
        
        if plan == 'free':
            print("🚨 PROBLEMA: Usuario sigue como Free después del pago")
        else:
            print(f"✅ Plan: {plan}")
        
        if billing_status != 'active':
            print(f"🚨 PROBLEMA: Billing status no activo: {billing_status}")
        else:
            print(f"✅ Billing Status: active")
        
        if not stripe_customer_id:
            print("🚨 PROBLEMA: No hay stripe_customer_id")
        else:
            print(f"✅ Stripe Customer ID: {stripe_customer_id}")
        
        return user_dict
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def manual_fix_user(email: str):
    """Corrección manual básica del usuario"""
    print(f"\n🔧 CORRECCIÓN MANUAL PARA: {email}")
    print("=" * 40)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar que el usuario existe y tiene stripe_customer_id
        cur.execute('SELECT id, stripe_customer_id FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        
        if not user:
            print("❌ Usuario no encontrado")
            return False
        
        user_dict = dict(user)
        user_id = user_dict['id']
        stripe_customer_id = user_dict.get('stripe_customer_id')
        
        if not stripe_customer_id:
            print("❌ Usuario no tiene stripe_customer_id - no se puede corregir automáticamente")
            return False
        
        print(f"🔄 Actualizando usuario ID {user_id}:")
        print(f"   Plan: free → basic")
        print(f"   Billing Status: → active")
        print(f"   Quota Limit: → 1225")
        print(f"   Quota Used: → 0")
        
        # Actualizar a plan básico
        cur.execute('''
            UPDATE users 
            SET 
                plan = 'basic',
                current_plan = 'basic',
                billing_status = 'active',
                quota_limit = 1225,
                quota_used = 0,
                updated_at = NOW()
            WHERE id = %s
        ''', (user_id,))
        
        rows_affected = cur.rowcount
        conn.commit()
        conn.close()
        
        if rows_affected > 0:
            print(f"✅ Usuario corregido exitosamente")
            print(f"   Plan activado: basic")
            print(f"   Quota disponible: 1225 RU")
            return True
        else:
            print(f"❌ No se pudo actualizar el usuario")
            return False
        
    except Exception as e:
        print(f"❌ Error en corrección manual: {e}")
        return False

def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print("Uso: python3 simple_user_diagnosis.py <email> [fix]")
        print("Ejemplos:")
        print("  python3 simple_user_diagnosis.py info@tucreditorapido.com")
        print("  python3 simple_user_diagnosis.py info@tucreditorapido.com fix")
        sys.exit(1)
    
    email = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else 'diagnose'
    
    # Diagnóstico
    user_info = diagnose_user_simple(email)
    
    if action == 'fix' and user_info:
        print(f"\n" + "="*50)
        print("🔧 EJECUTANDO CORRECCIÓN MANUAL")
        success = manual_fix_user(email)
        
        if success:
            print(f"\n✅ CORRECCIÓN COMPLETADA")
            print(f"Verifica el panel de admin para confirmar los cambios")
        else:
            print(f"\n❌ CORRECCIÓN FALLÓ")

if __name__ == "__main__":
    main()
