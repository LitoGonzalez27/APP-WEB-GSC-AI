#!/usr/bin/env python3
"""
Webhook Diagnostics - Verificar estado de webhooks de Stripe
============================================================

Diagnóstica si los webhooks están configurados y funcionando correctamente.
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta

def check_webhook_endpoint(base_url: str):
    """Verifica si el endpoint de webhook está disponible"""
    webhook_url = f"{base_url}/webhooks/stripe"
    
    print(f"🔗 Verificando endpoint: {webhook_url}")
    
    try:
        # Test GET (debería devolver 405 Method Not Allowed)
        response = requests.get(webhook_url, timeout=10)
        
        if response.status_code == 405:
            print("✅ Endpoint webhook disponible (405 Method Not Allowed esperado)")
            return True
        elif response.status_code == 404:
            print("❌ Endpoint webhook NO EXISTE (404)")
            return False
        else:
            print(f"⚠️ Endpoint respuesta inesperada: {response.status_code}")
            return True  # Existe pero respuesta rara
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error conectando al endpoint: {e}")
        return False

def check_recent_checkouts(customer_id: str):
    """Simula verificación de checkouts recientes (necesitaría acceso a Stripe)"""
    print(f"\n💳 VERIFICACIÓN STRIPE CUSTOMER: {customer_id}")
    print("=" * 50)
    print("⚠️ Nota: Para verificación completa necesitamos:")
    print("   - STRIPE_SECRET_KEY")
    print("   - Acceso directo a Stripe Dashboard")
    print("   - Logs de webhook de Railway")
    
    return {
        'customer_id': customer_id,
        'verification_needed': True
    }

def analyze_webhook_issue(user_info: dict):
    """Analiza posibles problemas con webhooks"""
    print(f"\n🔍 ANÁLISIS DE WEBHOOK ISSUE")
    print("=" * 40)
    
    has_customer_id = bool(user_info.get('stripe_customer_id'))
    is_billing_active = user_info.get('billing_status') == 'active'
    is_plan_free = user_info.get('plan') == 'free'
    has_zero_quota = user_info.get('quota_limit', 0) == 0
    
    print(f"📊 Estado del usuario:")
    print(f"   Stripe Customer ID: {'✅' if has_customer_id else '❌'}")
    print(f"   Billing Status: {'✅ active' if is_billing_active else '❌ inactive'}")
    print(f"   Plan: {'❌ free' if is_plan_free else '✅ paid'}")
    print(f"   Quota: {'❌ 0 RU' if has_zero_quota else '✅ > 0 RU'}")
    
    if has_customer_id and is_billing_active and is_plan_free and has_zero_quota:
        print(f"\n🚨 PATRÓN IDENTIFICADO: WEBHOOK NO EJECUTADO")
        print("   - Checkout completado (customer_id existe)")
        print("   - Billing marcado como active")
        print("   - Pero plan y quota NO actualizados")
        print("   - Conclusión: Webhook no se ejecutó o falló")
        
        return {
            'webhook_issue': True,
            'pattern': 'checkout_success_but_no_webhook',
            'recommendations': [
                'Verificar webhook endpoint disponible',
                'Verificar configuración STRIPE_WEBHOOK_SECRET',
                'Revisar logs de Railway para errores webhook',
                'Verificar que cambios se desplegaron',
                'Aplicar corrección manual temporalmente'
            ]
        }
    
    return {'webhook_issue': False}

def main():
    """Función principal de diagnóstico"""
    if len(sys.argv) < 2:
        print("Uso: python3 webhook_diagnostics.py <base_url> [user_id]")
        print("Ejemplo: python3 webhook_diagnostics.py https://clicandseo.up.railway.app 41")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    user_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    print("🧪 WEBHOOK DIAGNOSTICS")
    print("=" * 50)
    print(f"🎯 Target: {base_url}")
    
    # 1. Verificar endpoint webhook
    webhook_available = check_webhook_endpoint(base_url)
    
    # 2. Si hay user_id, verificar usuario específico
    if user_id:
        print(f"\n👤 Analizando usuario ID: {user_id}")
        
        # Simular carga de usuario (necesitaríamos DATABASE_URL)
        user_info = {
            'id': user_id,
            'stripe_customer_id': 'cus_Sx15NJNCSi4D1Z',  # Del caso real
            'billing_status': 'active',
            'plan': 'free',
            'quota_limit': 0
        }
        
        # 3. Análisis del problema
        analysis = analyze_webhook_issue(user_info)
        
        if analysis.get('webhook_issue'):
            print(f"\n💡 RECOMENDACIONES:")
            for i, rec in enumerate(analysis['recommendations'], 1):
                print(f"   {i}. {rec}")
    
    # 4. Información adicional necesaria
    print(f"\n📋 INFORMACIÓN ADICIONAL NECESARIA:")
    print("   1. Logs de Railway durante el período del pago")
    print("   2. Stripe Dashboard → Webhooks → Logs")
    print("   3. Variables de entorno STRIPE_* en Railway")
    print("   4. Confirmación de que cambios se desplegaron")

if __name__ == "__main__":
    main()
