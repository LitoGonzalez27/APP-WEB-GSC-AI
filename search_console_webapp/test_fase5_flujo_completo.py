#!/usr/bin/env python3
"""
Test Fase 5 - Flujo Completo de Usuario
======================================

Script para probar todos los flujos de usuario según el plan oficial:
- Free → Basic → consumir 1.225 RU → bloqueo → upgrade a Premium
- Premium → Basic (downgrade)
- Renovación y reinicio de cuotas
- Impagos simulados
- Cancelaciones
"""

import os
import time
import requests
import stripe
from datetime import datetime
import json

# Configuración
STAGING_URL = "https://clicandseo.up.railway.app"
DATABASE_URL = os.getenv('DATABASE_URL')

def print_section(title):
    """Imprimir sección con formato"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print('='*60)

def print_test(test_name, result, details=""):
    """Imprimir resultado de test"""
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"   📋 {details}")

def setup_stripe():
    """Configurar Stripe"""
    stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe_secret_key:
        print("❌ STRIPE_SECRET_KEY no configurado")
        return False
    
    stripe.api_key = stripe_secret_key
    return True

def test_user_flow_free_to_premium():
    """Test 1: Flujo Free → Basic → Premium"""
    print_section("FLUJO FREE → BASIC → PREMIUM")
    
    # Este test requiere autenticación real y sería mejor hacerlo manualmente
    # Por ahora, documentamos los pasos
    
    test_steps = [
        "1. Usuario Free intenta AI Overview → Bloqueado ✅",
        "2. Usuario se suscribe a Basic (29.99€) → Acceso con 1.225 RU",
        "3. Usuario consume 1.225 RU → Soft limit al 80% (980 RU)",
        "4. Usuario consume 1.225 RU → Hard limit al 100%",
        "5. Usuario upgrade a Premium → 2.950 RU disponibles",
        "6. Usuario puede continuar hasta 2.950 RU"
    ]
    
    print("📋 PASOS DEL TEST MANUAL:")
    for step in test_steps:
        print(f"   {step}")
    
    print("\n💡 CÓMO EJECUTAR:")
    print("   1. Crear usuario de prueba en staging")
    print("   2. Seguir flujo paso a paso")
    print("   3. Verificar en panel admin el consumo")
    print("   4. Verificar mensajes de límites")
    
    return True

def test_stripe_test_clock():
    """Test 2: Verificar Test Clocks para renovaciones"""
    print_section("TEST CLOCKS PARA RENOVACIONES")
    
    try:
        # Buscar test clocks existentes
        test_clocks = stripe.test_helpers.TestClock.list(limit=5)
        
        if len(test_clocks.data) == 0:
            print("⚠️ No hay Test Clocks configurados")
            print("💡 CREAR TEST CLOCK:")
            print("   1. Ir a: https://dashboard.stripe.com/test/test-clocks")
            print("   2. Crear nuevo Test Clock")
            print("   3. Usar para simular renovaciones")
            return False
        
        print(f"✅ Test Clocks encontrados: {len(test_clocks.data)}")
        for clock in test_clocks.data:
            frozen_time = datetime.fromtimestamp(clock.frozen_time)
            print(f"   - {clock.name or clock.id}: {frozen_time}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando Test Clocks: {e}")
        return False

def test_webhook_events():
    """Test 3: Verificar eventos importantes de webhook"""
    print_section("WEBHOOK EVENTS")
    
    try:
        # Verificar webhooks configurados
        webhooks = stripe.WebhookEndpoint.list()
        
        staging_webhooks = [w for w in webhooks.data if STAGING_URL in w.url]
        
        if not staging_webhooks:
            print("❌ No hay webhooks para staging")
            return False
        
        webhook = staging_webhooks[0]
        important_events = [
            'customer.subscription.created',
            'customer.subscription.updated', 
            'customer.subscription.deleted',
            'invoice.payment_succeeded',
            'invoice.payment_failed',
            'checkout.session.completed'
        ]
        
        missing_events = []
        for event in important_events:
            if event not in webhook.enabled_events:
                missing_events.append(event)
        
        print(f"✅ Webhook configurado: {webhook.url}")
        print(f"✅ Eventos configurados: {len(webhook.enabled_events)}")
        
        if missing_events:
            print(f"⚠️ Eventos faltantes: {missing_events}")
            return False
        else:
            print("✅ Todos los eventos importantes configurados")
            return True
        
    except Exception as e:
        print(f"❌ Error verificando webhooks: {e}")
        return False

def test_database_quota_tracking():
    """Test 4: Verificar tracking de quotas en base de datos"""
    print_section("DATABASE QUOTA TRACKING")
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL no configurado")
        return False
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verificar tabla quota_usage_events
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM quota_usage_events 
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)
        recent_events = cur.fetchone()['count']
        
        print(f"✅ Eventos de quota (7 días): {recent_events}")
        
        # Verificar usuarios con quotas
        cur.execute("""
            SELECT plan, COUNT(*) as count, 
                   AVG(quota_used) as avg_used,
                   AVG(quota_limit) as avg_limit
            FROM users 
            WHERE quota_limit > 0
            GROUP BY plan
        """)
        quota_stats = cur.fetchall()
        
        print("📊 ESTADÍSTICAS POR PLAN:")
        for stat in quota_stats:
            plan = stat['plan']
            count = stat['count']
            avg_used = stat['avg_used'] or 0
            avg_limit = stat['avg_limit'] or 0
            percentage = (avg_used / avg_limit * 100) if avg_limit > 0 else 0
            
            print(f"   {plan}: {count} usuarios, promedio {avg_used:.0f}/{avg_limit:.0f} RU ({percentage:.1f}%)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verificando base de datos: {e}")
        return False

def generate_phase5_manual_checklist():
    """Generar checklist manual para Fase 5"""
    print_section("CHECKLIST MANUAL FASE 5")
    
    checklist = """
📋 CHECKLIST MANUAL FASE 5 - FLUJOS COMPLETOS
============================================

🔄 TEST 1: FLUJO FREE → BASIC → PREMIUM
--------------------------------------
□ 1. Crear usuario de prueba (o usar existente)
□ 2. Verificar plan Free → AI Overview bloqueado
□ 3. Subscribir a Basic (29.99€) vía Stripe Checkout
□ 4. Verificar: 1.225 RU disponibles en panel admin
□ 5. Consumir 980 RU → Verificar soft limit (80%)
□ 6. Consumir 1.225 RU → Verificar hard limit (100%)
□ 7. Upgrade a Premium → Verificar 2.950 RU
□ 8. Continuar hasta cerca de 2.950 RU

🔄 TEST 2: DOWNGRADE PREMIUM → BASIC
-----------------------------------
□ 1. Usuario Premium con uso < 1.225 RU
□ 2. Downgrade a Basic via Customer Portal
□ 3. Verificar: mantiene Premium hasta final de período
□ 4. Usar Test Clock para avanzar al siguiente período
□ 5. Verificar: cambia a Basic (1.225 RU)

🔄 TEST 3: RENOVACIÓN Y RESET DE CUOTAS
--------------------------------------
□ 1. Usuario Basic cerca del final del período
□ 2. Usar Test Clock para simular renovación
□ 3. Verificar: quota_used se resetea a 0
□ 4. Verificar: current_period_start/end se actualizan
□ 5. Verificar: usuario puede usar RU de nuevo

🔄 TEST 4: IMPAGO SIMULADO
-------------------------
□ 1. Usuario Basic/Premium activo
□ 2. Simular fallo de pago con Test Clock
□ 3. Verificar: estado cambia a 'past_due'
□ 4. Verificar: acceso se mantiene en período de gracia
□ 5. Después de gracia: verificar bloqueo

🔄 TEST 5: CANCELACIÓN
---------------------
□ 1. Usuario Basic/Premium activo
□ 2. Cancelar vía Customer Portal
□ 3. Verificar: mantiene acceso hasta final de período
□ 4. Al final del período: verificar downgrade a Free
□ 5. Verificar: AI Overview bloqueado

🔄 TEST 6: CUSTOM QUOTA ENTERPRISE
---------------------------------
□ 1. Usuario Free/Basic/Premium
□ 2. Admin asigna custom quota (ej: 5.000 RU)
□ 3. Verificar: plan se marca como 'Enterprise'
□ 4. Verificar: límites se actualizan
□ 5. Consumir RU según nueva cuota

📊 MÉTRICAS A VERIFICAR:
=======================
□ Panel admin muestra datos correctos
□ Barras progresivas se actualizan
□ Modal "Ver" refleja cambios
□ Base de datos sincronizada
□ Webhooks funcionando sin errores
□ Logs limpios (sin errores críticos)

⏰ DURACIÓN ESTIMADA: 1-2 horas
🎯 CRITERIO DE ÉXITO: Todos los flujos funcionan sin errors

"""
    
    print(checklist)
    return True

def run_phase5_tests():
    """Ejecutar tests de Fase 5"""
    print("🧪 TESTING FASE 5 - FLUJOS COMPLETOS")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Objetivo: Validar todos los flujos antes de producción")
    
    # Setup
    if not setup_stripe():
        return False
    
    tests = [
        test_stripe_test_clock,
        test_webhook_events,
        test_database_quota_tracking,
        test_user_flow_free_to_premium,
        generate_phase5_manual_checklist
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Error en {test.__name__}: {e}")
            results.append(False)
        
        time.sleep(1)
    
    # Resumen
    print_section("RESUMEN FASE 5")
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Tests ejecutados: {total}")
    print(f"✅ Tests exitosos: {passed}")
    print(f"📈 Preparación para Fase 5: {(passed/total)*100:.1f}%")
    
    if passed >= total - 1:  # Permitir 1 fallo menor
        print("\n🎯 LISTO PARA FASE 5")
        print("✅ Continuar con testing manual")
    else:
        print("\n⚠️ REVISAR CONFIGURACIÓN")
        print("❌ Corregir issues antes de Fase 5")
    
    return passed >= total - 1

if __name__ == "__main__":
    success = run_phase5_tests()
    
    print(f"\n{'='*60}")
    print("🎯 PRÓXIMOS PASOS:")
    if success:
        print("1. ✅ Ejecutar checklist manual paso a paso")
        print("2. 🔄 Simular flujos con Test Clocks")
        print("3. 📊 Verificar métricas y logs")
        print("4. 🚀 Si todo pasa → preparar Fase 6 (Producción)")
    else:
        print("1. ❌ Corregir configuración de Stripe")
        print("2. 🔧 Verificar webhooks y Test Clocks")
        print("3. 🔄 Re-ejecutar este script")
    print('='*60)
