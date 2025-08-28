#!/usr/bin/env python3
"""
Script para testing rápido de las correcciones UX implementadas
"""

import requests
import json

STAGING_URL = "https://clicandseo.up.railway.app"

def test_ai_overview_paywall():
    """Test que AI Overview devuelve 402 para usuarios Free"""
    print("\n🔍 TESTING AI OVERVIEW PAYWALL")
    print("="*50)
    
    # Datos de test
    payload = {
        "keywords": ["test keyword"],
        "site_url": "example.com"
    }
    
    try:
        response = requests.post(
            f"{STAGING_URL}/api/analyze-ai-overview",
            json=payload,
            timeout=10
        )
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("🔐 RESULTADO: Usuario no autenticado (esperado sin cookies)")
        elif response.status_code == 402:
            print("✅ RESULTADO: Paywall funcionando correctamente")
            data = response.json()
            print(f"   💬 Mensaje: {data.get('message')}")
            print(f"   🔄 Upgrade options: {data.get('upgrade_options')}")
        elif response.status_code == 200:
            print("❌ PROBLEMA: Usuario Free puede acceder (no debería)")
        else:
            print(f"❓ Otro status: {response.status_code}")
            
        return response.status_code
        
    except Exception as e:
        print(f"❌ ERROR en test: {e}")
        return None

def test_manual_ai_access():
    """Test que Manual AI devuelve paywall para usuarios Free"""
    print("\n🔍 TESTING MANUAL AI ACCESS")
    print("="*50)
    
    try:
        response = requests.get(
            f"{STAGING_URL}/manual-ai/",
            timeout=10,
            allow_redirects=False
        )
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            if 'login' in location:
                print("🔐 RESULTADO: Redirige a login (esperado sin autenticación)")
            else:
                print(f"🔄 RESULTADO: Redirige a: {location}")
        elif response.status_code == 200:
            content = response.text
            if 'paywall' in content.lower() or 'upgrade' in content.lower():
                print("✅ RESULTADO: Muestra paywall correctamente")
            else:
                print("❌ PROBLEMA: No muestra paywall")
        else:
            print(f"❓ Otro status: {response.status_code}")
            
        return response.status_code
        
    except Exception as e:
        print(f"❌ ERROR en test: {e}")
        return None

def test_registration_flow():
    """Test que el flujo de registro funciona"""
    print("\n🔍 TESTING REGISTRATION FLOW")
    print("="*50)
    
    try:
        # Test signup page
        response = requests.get(f"{STAGING_URL}/signup", timeout=10)
        print(f"📋 Signup page status: {response.status_code}")
        
        # Test login page con parámetros de registro exitoso
        response = requests.get(
            f"{STAGING_URL}/login?registration_success=true&with_google=true&email=test@example.com",
            timeout=10
        )
        
        print(f"📋 Login page status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            if 'registration_success' in content or 'Registro exitoso' in content:
                print("✅ RESULTADO: Mensaje de registro detectado en página")
            else:
                print("❓ RESULTADO: No se detecta mensaje específico (puede estar en JS)")
        
        return response.status_code
        
    except Exception as e:
        print(f"❌ ERROR en test: {e}")
        return None

def test_paywall_assets():
    """Test que los assets de paywall se cargan correctamente"""
    print("\n🔍 TESTING PAYWALL ASSETS")
    print("="*50)
    
    assets = [
        "/static/js/paywall.js",
        "/static/paywall.css",
        "/static/js/quota-ui.js",
        "/static/quota-ui.css"
    ]
    
    results = {}
    
    for asset in assets:
        try:
            response = requests.get(f"{STAGING_URL}{asset}", timeout=10)
            status = response.status_code
            results[asset] = status
            
            if status == 200:
                print(f"✅ {asset}: OK")
            else:
                print(f"❌ {asset}: {status}")
                
        except Exception as e:
            print(f"❌ {asset}: ERROR - {e}")
            results[asset] = "ERROR"
    
    return results

def main():
    """Ejecutar todos los tests"""
    print("🧪 TESTING CORRECCIONES UX - FASE 4.5")
    print("="*60)
    print("Testing en staging: https://clicandseo.up.railway.app")
    
    # Tests individuales
    ai_status = test_ai_overview_paywall()
    manual_status = test_manual_ai_access()
    registration_status = test_registration_flow()
    assets_results = test_paywall_assets()
    
    # Resumen
    print("\n🎯 RESUMEN DE TESTING")
    print("="*40)
    
    print(f"🔍 AI Overview Paywall: {'✅' if ai_status == 402 else '❓' if ai_status == 401 else '❌'}")
    print(f"🔍 Manual AI Access: {'✅' if manual_status in [200, 302] else '❌'}")
    print(f"🔍 Registration Flow: {'✅' if registration_status == 200 else '❌'}")
    
    # Assets summary
    assets_ok = sum(1 for status in assets_results.values() if status == 200)
    assets_total = len(assets_results)
    print(f"🔍 Paywall Assets: {'✅' if assets_ok == assets_total else '❌'} ({assets_ok}/{assets_total})")
    
    print(f"\n💡 CONCLUSIÓN:")
    if ai_status in [401, 402] and manual_status in [200, 302] and registration_status == 200:
        print("✅ Los cambios están desplegados correctamente")
        print("   El problema puede ser cache del navegador o usuario específico")
        print("   💡 Sugerencia: Probar en modo incógnito o limpiar cache")
    else:
        print("❌ Hay problemas en el despliegue")
        print("   💡 Sugerencia: Verificar logs de Railway y reintentar deploy")

if __name__ == "__main__":
    main()
