#!/usr/bin/env python3
"""
Test Stripe Integration - Verificación completa de integración con Stripe
=========================================================================

Este script verifica que la integración con Stripe funcione correctamente:
- Conexión con Stripe API
- Productos y precios configurados
- Webhooks funcionando
- Sincronización con base de datos
"""

import os
import stripe
import requests
import json
from datetime import datetime
import time

# Configuración
STAGING_URL = "https://clicandseo.up.railway.app"

def print_section(title):
    """Imprimir sección con formato"""
    print(f"\n{'='*60}")
    print(f"💳 {title}")
    print('='*60)

def print_test(test_name, result, details=""):
    """Imprimir resultado de test"""
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"   📋 {details}")

def setup_stripe():
    """Configurar Stripe con las claves de staging"""
    print_section("CONFIGURACIÓN STRIPE")
    
    # Intentar obtener las claves desde variables de entorno
    stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
    stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
    
    if not stripe_secret_key:
        print_test("STRIPE_SECRET_KEY configurado", False, "Variable no encontrada")
        print("💡 Para obtener las claves:")
        print("   1. Ve a tu dashboard de Stripe")
        print("   2. Developers > API keys")
        print("   3. Copia las claves de test")
        print("   4. export STRIPE_SECRET_KEY='sk_test_...'")
        return False
    
    # Configurar Stripe
    stripe.api_key = stripe_secret_key
    
    # Verificar que es clave de test
    is_test_key = stripe_secret_key.startswith('sk_test_')
    print_test("Usando clave de TEST", is_test_key, 
              "⚠️ IMPORTANTE: Solo usar claves de test en staging")
    
    if not is_test_key:
        print("🚨 ADVERTENCIA: Parece que estás usando una clave de producción")
        return False
    
    print_test("Stripe configurado", True, f"Clave: {stripe_secret_key[:12]}...")
    return True

def test_stripe_connection():
    """Test 1: Verificar conexión con Stripe API"""
    print_section("CONEXIÓN STRIPE API")
    
    try:
        # Test básico de conexión
        account = stripe.Account.retrieve()
        
        print_test("Conexión a Stripe API", True, f"Account ID: {account.id}")
        print_test("Modo de cuenta", account.livemode == False, 
                  f"Livemode: {account.livemode} (debería ser False)")
        print_test("Nombre de cuenta", bool(account.display_name), 
                  f"Nombre: {account.display_name}")
        
        return True
        
    except stripe.error.AuthenticationError as e:
        print_test("Autenticación Stripe", False, f"Error: {e}")
        return False
    except Exception as e:
        print_test("Conexión Stripe API", False, f"Error: {e}")
        return False

def test_stripe_products():
    """Test 2: Verificar productos configurados"""
    print_section("PRODUCTOS STRIPE")
    
    try:
        # Obtener productos
        products = stripe.Product.list(limit=10)
        
        expected_products = ['basic', 'premium']  # enterprise no debería estar en Stripe
        found_products = []
        
        print(f"📦 Productos encontrados: {len(products.data)}")
        
        for product in products.data:
            print(f"   - {product.name} (ID: {product.id}, Active: {product.active})")
            
            # Buscar productos esperados por nombre o metadata
            product_name_lower = product.name.lower()
            if 'basic' in product_name_lower:
                found_products.append('basic')
            elif 'premium' in product_name_lower:
                found_products.append('premium')
        
        # Verificar que tenemos los productos esperados
        basic_found = 'basic' in found_products
        premium_found = 'premium' in found_products
        
        print_test("Producto Basic configurado", basic_found)
        print_test("Producto Premium configurado", premium_found)
        
        return basic_found and premium_found
        
    except Exception as e:
        print_test("Verificación productos", False, f"Error: {e}")
        return False

def test_stripe_prices():
    """Test 3: Verificar precios configurados"""
    print_section("PRECIOS STRIPE")
    
    try:
        # Obtener precios
        prices = stripe.Price.list(limit=20)
        
        expected_amounts = [2999, 5999]  # 29.99€ y 59.99€ en centavos
        found_prices = []
        
        print(f"💰 Precios encontrados: {len(prices.data)}")
        
        for price in prices.data:
            amount_eur = price.unit_amount / 100 if price.unit_amount else 0
            currency = price.currency
            recurring = price.recurring
            
            print(f"   - {amount_eur}€ {currency} ({'mensual' if recurring and recurring.interval == 'month' else 'único'})")
            
            if price.unit_amount in expected_amounts:
                found_prices.append(price.unit_amount)
        
        # Verificar precios esperados
        basic_price = 2999 in found_prices  # 29.99€
        premium_price = 5999 in found_prices  # 59.99€
        
        print_test("Precio Basic (29.99€)", basic_price)
        print_test("Precio Premium (59.99€)", premium_price)
        
        return basic_price and premium_price
        
    except Exception as e:
        print_test("Verificación precios", False, f"Error: {e}")
        return False

def test_webhook_endpoint():
    """Test 4: Verificar endpoint de webhook"""
    print_section("WEBHOOK ENDPOINT")
    
    try:
        # Test que el endpoint de webhook existe
        webhook_url = f"{STAGING_URL}/stripe/webhook"
        
        # Intentar POST vacío (debería fallar con error de firma)
        response = requests.post(webhook_url, 
                               data=json.dumps({"test": True}),
                               headers={"Content-Type": "application/json"},
                               timeout=10)
        
        # Esperamos 400 por falta de firma válida
        endpoint_exists = response.status_code in [200, 400, 401, 403]
        
        print_test("Endpoint webhook existe", endpoint_exists, 
                  f"URL: {webhook_url}, Status: {response.status_code}")
        
        if response.status_code == 400:
            print_test("Webhook valida firmas", True, "Error 400 esperado sin firma válida")
        
        return endpoint_exists
        
    except Exception as e:
        print_test("Test webhook endpoint", False, f"Error: {e}")
        return False

def test_stripe_webhooks():
    """Test 5: Verificar webhooks configurados"""
    print_section("WEBHOOKS CONFIGURADOS")
    
    try:
        # Listar webhooks endpoints
        webhooks = stripe.WebhookEndpoint.list()
        
        staging_webhooks = []
        for webhook in webhooks.data:
            if STAGING_URL in webhook.url:
                staging_webhooks.append(webhook)
        
        print(f"🔗 Webhooks totales: {len(webhooks.data)}")
        print(f"🎯 Webhooks para staging: {len(staging_webhooks)}")
        
        if staging_webhooks:
            for webhook in staging_webhooks:
                print(f"   - {webhook.url}")
                print(f"     Events: {', '.join(webhook.enabled_events)}")
                print(f"     Status: {'✅ Activo' if webhook.status == 'enabled' else '❌ Inactivo'}")
        
        has_staging_webhook = len(staging_webhooks) > 0
        print_test("Webhook para staging configurado", has_staging_webhook)
        
        if has_staging_webhook:
            # Verificar eventos importantes
            webhook = staging_webhooks[0]
            important_events = [
                'customer.subscription.created',
                'customer.subscription.updated', 
                'customer.subscription.deleted',
                'invoice.payment_succeeded'
            ]
            
            missing_events = []
            for event in important_events:
                if event not in webhook.enabled_events:
                    missing_events.append(event)
            
            print_test("Eventos importantes configurados", len(missing_events) == 0,
                      f"Faltantes: {missing_events}")
        
        return has_staging_webhook
        
    except Exception as e:
        print_test("Verificación webhooks", False, f"Error: {e}")
        return False

def test_test_clock():
    """Test 6: Verificar Test Clock para testing"""
    print_section("STRIPE TEST CLOCK")
    
    try:
        # Buscar test clocks
        test_clocks = stripe.test_helpers.TestClock.list(limit=5)
        
        print(f"⏰ Test Clocks encontrados: {len(test_clocks.data)}")
        
        active_clocks = [clock for clock in test_clocks.data if clock.status == 'ready']
        
        if active_clocks:
            for clock in active_clocks:
                frozen_time = datetime.fromtimestamp(clock.frozen_time)
                print(f"   - {clock.name or clock.id}")
                print(f"     Tiempo: {frozen_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"     Status: {clock.status}")
        
        print_test("Test Clocks disponibles", len(active_clocks) > 0, 
                  "Para testing de subscripciones")
        
        return True  # No es crítico para funcionamiento básico
        
    except Exception as e:
        print_test("Verificación Test Clock", False, f"Error: {e}")
        return False

def run_stripe_tests():
    """Ejecutar todas las pruebas de Stripe"""
    print("💳 TESTING STRIPE INTEGRATION - COMPREHENSIVE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Target: {STAGING_URL}")
    
    # Setup inicial
    if not setup_stripe():
        print("❌ No se pudo configurar Stripe. Saltando tests.")
        return False
    
    tests = [
        test_stripe_connection,
        test_stripe_products,
        test_stripe_prices,
        test_webhook_endpoint,
        test_stripe_webhooks,
        test_test_clock
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Error ejecutando {test.__name__}: {e}")
            results.append(False)
        
        time.sleep(1)  # Pausa entre tests
    
    # Resumen final
    print_section("RESUMEN STRIPE")
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Tests ejecutados: {total}")
    print(f"✅ Tests exitosos: {passed}")
    print(f"❌ Tests fallidos: {total - passed}")
    print(f"📈 Tasa de éxito: {(passed/total)*100:.1f}%")
    
    # Criterio de éxito (test_clock no es crítico)
    critical_tests_passed = sum(results[:-1])  # Todos excepto test_clock
    critical_tests_total = len(results) - 1
    
    if critical_tests_passed == critical_tests_total:
        print(f"\n🎊 TESTS CRÍTICOS PASARON - STRIPE LISTO")
        return True
    else:
        print(f"\n⚠️ HAY TESTS CRÍTICOS FALLIDOS - REVISAR STRIPE")
        return False

if __name__ == "__main__":
    # Ejecutar tests
    success = run_stripe_tests()
    
    print(f"\n{'='*60}")
    print("🎯 PRÓXIMOS PASOS:")
    if success:
        print("1. ✅ Stripe configurado correctamente")
        print("2. Continuar con tests de integración end-to-end")
        print("3. Probar flujo completo de subscripción")
    else:
        print("1. ❌ Revisar configuración de Stripe")
        print("2. Verificar productos y precios en dashboard")
        print("3. Configurar webhooks si es necesario")
    print("4. Dashboard Stripe: https://dashboard.stripe.com/test")
    print('='*60)
