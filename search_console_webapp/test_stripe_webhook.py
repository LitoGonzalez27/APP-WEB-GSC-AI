#!/usr/bin/env python3
"""
TEST STRIPE WEBHOOK - FASE 3
============================

Script para probar que los webhooks de Stripe funcionan correctamente
en el entorno de staging.
"""

import json
import requests
import hmac
import hashlib
import time

def create_test_subscription_event():
    """Crea un evento de prueba de customer.subscription.created"""
    return {
        "id": "evt_test_webhook",
        "object": "event",
        "api_version": "2020-08-27",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "sub_test_123456789",
                "object": "subscription",
                "customer": "cus_test_123456789",
                "status": "active",
                "current_period_start": int(time.time()),
                "current_period_end": int(time.time() + 30*24*3600),  # +30 días
                "items": {
                    "object": "list",
                    "data": [
                        {
                            "id": "si_test_123456789",
                            "object": "subscription_item",
                            "price": {
                                "id": "price_1S0NxmGannDPRjwrLmmgtZGa",  # Tu Price ID Basic
                                "object": "price",
                                "product": "prod_basic_test"
                            },
                            "quantity": 1
                        }
                    ]
                }
            }
        },
        "livemode": False,
        "pending_webhooks": 1,
        "request": {
            "id": "req_test_123456789",
            "idempotency_key": None
        },
        "type": "customer.subscription.created"
    }

def create_stripe_signature(payload, secret):
    """Crea una firma válida de Stripe"""
    timestamp = str(int(time.time()))
    payload_string = payload.encode('utf-8')
    
    # Crear la cadena para firmar
    signed_payload = f"{timestamp}.{payload_string.decode('utf-8')}"
    
    # Crear la firma
    signature = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"t={timestamp},v1={signature}"

def test_webhook_endpoint():
    """Prueba el endpoint webhook con un evento simulado"""
    
    print("🧪 TESTING STRIPE WEBHOOK ENDPOINT")
    print("=" * 50)
    
    # Configuración
    webhook_url = "https://clicandseo.up.railway.app/webhooks/stripe"
    webhook_secret = "whsec_qhEi0vsXFss80X9mxepDI3LLD7IV68D"  # Tu webhook secret
    
    # Crear evento de prueba
    event = create_test_subscription_event()
    payload = json.dumps(event)
    
    print(f"📡 Enviando evento: {event['type']}")
    print(f"🎯 URL: {webhook_url}")
    print(f"📋 Customer: {event['data']['object']['customer']}")
    print(f"📋 Subscription: {event['data']['object']['id']}")
    
    # Crear firma
    signature = create_stripe_signature(payload, webhook_secret)
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'Stripe-Signature': signature,
        'User-Agent': 'Stripe/1.0 (+https://stripe.com/docs/webhooks)'
    }
    
    try:
        # Enviar request
        print("\n🚀 Enviando webhook...")
        response = requests.post(webhook_url, data=payload, headers=headers, timeout=30)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ WEBHOOK EXITOSO!")
            print("🎉 Tu integración Stripe funciona correctamente")
        else:
            print("❌ WEBHOOK FALLÓ")
            print("🔍 Revisa los logs de Railway para más detalles")
        
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        return False

def test_basic_connectivity():
    """Prueba conectividad básica al endpoint"""
    print("\n🔍 TESTING CONECTIVIDAD BÁSICA")
    print("=" * 50)
    
    try:
        # Test GET (debería dar 405)
        response = requests.get("https://clicandseo.up.railway.app/webhooks/stripe", timeout=10)
        
        if response.status_code == 405:
            print("✅ Endpoint webhook existe y responde")
            print("✅ Method Not Allowed (405) es correcto para GET")
            return True
        else:
            print(f"⚠️ Status inesperado: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        return False

def main():
    """Función principal de testing"""
    print("🧪 STRIPE WEBHOOK TESTING - FASE 3")
    print("=" * 60)
    
    # Test 1: Conectividad básica
    connectivity_ok = test_basic_connectivity()
    
    if not connectivity_ok:
        print("\n❌ Falló test de conectividad básica")
        return False
    
    # Test 2: Webhook simulado
    webhook_ok = test_webhook_endpoint()
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE TESTING:")
    print("=" * 60)
    print(f"🔗 Conectividad: {'✅ PASS' if connectivity_ok else '❌ FAIL'}")
    print(f"📡 Webhook: {'✅ PASS' if webhook_ok else '❌ FAIL'}")
    
    if connectivity_ok and webhook_ok:
        print("\n🎉 FASE 3 COMPLETAMENTE FUNCIONAL!")
        print("🚀 Listo para continuar con Fase 4")
    else:
        print("\n⚠️ Algunos tests fallaron")
        print("🔍 Revisa logs de Railway para debugging")
    
    return connectivity_ok and webhook_ok

if __name__ == "__main__":
    main()
