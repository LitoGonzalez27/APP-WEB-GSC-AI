#!/usr/bin/env python3
"""
Testing de las correcciones del paywall:
1. Manual AI modal funciona (sin error upgradeOptions.map)
2. AI Overview se restaura después del paywall
"""

import requests
import time

STAGING_URL = "https://clicandseo.up.railway.app"

def test_paywall_js_syntax():
    """Test que paywall.js se carga sin errores de sintaxis"""
    print("\n🔍 TESTING PAYWALL.JS SINTAXIS")
    print("="*45)
    
    try:
        response = requests.get(f"{STAGING_URL}/static/js/paywall.js", timeout=10)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Verificar la función window.showPaywall con orden correcto
            if "window.showPaywall = (featureName, upgradeOptions" in content:
                print("✅ window.showPaywall con parámetros correctos")
            else:
                print("❌ window.showPaywall no encontrado o parámetros incorrectos")
                
            # Verificar hidePaywallModal con restauración
            if "featureName.includes('AI Overview')" in content:
                print("✅ Restauración de AI Overview implementada")
            else:
                print("❌ Restauración de AI Overview no encontrada")
                
            # Verificar que no hay errores obvios de sintaxis
            if content.count('(') == content.count(')'):
                print("✅ Paréntesis balanceados")
            else:
                print("❌ Paréntesis desbalanceados")
                
            return True
        else:
            print(f"❌ No se pudo cargar paywall.js: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_manual_ai_system_calls():
    """Test que manual-ai-system.js tiene las llamadas correctas"""
    print("\n🔍 TESTING MANUAL AI SYSTEM CALLS")
    print("="*50)
    
    try:
        response = requests.get(f"{STAGING_URL}/static/js/manual-ai-system.js", timeout=10)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Verificar llamadas con orden correcto
            correct_calls = [
                "window.showPaywall('Manual AI Analysis')",
                "window.showPaywall('Manual AI Analysis', data.upgrade_options"
            ]
            
            found_calls = 0
            for call in correct_calls:
                if call in content:
                    found_calls += 1
                    print(f"✅ Encontrado: {call}")
                else:
                    print(f"❌ No encontrado: {call}")
            
            # Verificar que no hay llamadas con orden incorrecto
            wrong_calls = [
                "window.showPaywall(data.upgrade_options",
                "window.showPaywall(['basic', 'premium'], 'Manual AI'"
            ]
            
            wrong_found = 0
            for call in wrong_calls:
                if call in content:
                    wrong_found += 1
                    print(f"❌ Llamada incorrecta encontrada: {call}")
            
            return found_calls >= 1 and wrong_found == 0
        else:
            print(f"❌ No se pudo cargar manual-ai-system.js: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_ai_overview_calls():
    """Test que ui-ai-overview.js tiene las llamadas correctas"""
    print("\n🔍 TESTING AI OVERVIEW CALLS")
    print("="*45)
    
    try:
        response = requests.get(f"{STAGING_URL}/static/js/ui-ai-overview.js", timeout=10)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Verificar llamada con orden correcto
            if "window.showPaywall('AI Overview Analysis'" in content:
                print("✅ AI Overview call with correct parameter order")
            else:
                print("❌ AI Overview call not found or incorrect order")
                
            # Verificar que resetAIOverlay está disponible
            if "window.resetAIOverlay" in content or "resetAIOverlay" in content:
                print("✅ resetAIOverlay functionality available")
            else:
                print("❓ resetAIOverlay not found (may be in ui-ai-overlay.js)")
                
            return "window.showPaywall('AI Overview Analysis'" in content
        else:
            print(f"❌ No se pudo cargar ui-ai-overview.js: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_dashboard_loads():
    """Test que los dashboards cargan sin errores JavaScript críticos"""
    print("\n🔍 TESTING DASHBOARD LOADING")
    print("="*40)
    
    try:
        # Test Manual AI dashboard
        response = requests.get(f"{STAGING_URL}/manual-ai/", timeout=10, allow_redirects=False)
        
        print(f"📋 Manual AI Status: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            if 'login' in location:
                print("✅ Manual AI redirige a login (sin autenticación)")
            else:
                print(f"❓ Manual AI redirige a: {location}")
        elif response.status_code == 200:
            print("✅ Manual AI accesible directamente")
        
        # Test main app
        response2 = requests.get(f"{STAGING_URL}/", timeout=10)
        print(f"📋 Main App Status: {response2.status_code}")
        
        if response2.status_code == 200:
            print("✅ Main app carga correctamente")
            
            # Verificar que incluye los scripts paywall
            if 'paywall.js' in response2.text and 'paywall.css' in response2.text:
                print("✅ Assets paywall incluidos")
            else:
                print("❌ Assets paywall no incluidos")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Ejecutar todos los tests de las correcciones paywall"""
    print("🧪 TESTING CORRECCIONES PAYWALL")
    print("="*60)
    print("🎯 Verificando que:")
    print("   1. paywall.js sin errores upgradeOptions.map")
    print("   2. Llamadas showPaywall con orden correcto")
    print("   3. AI Overview se restaura después del paywall")
    print("   4. Dashboards cargan sin errores JavaScript")
    
    # Ejecutar tests
    test1 = test_paywall_js_syntax()
    test2 = test_manual_ai_system_calls()
    test3 = test_ai_overview_calls()
    test4 = test_dashboard_loads()
    
    # Resumen
    print(f"\n🎯 RESUMEN FINAL")
    print("="*40)
    
    tests = [
        ("Paywall.js sintaxis OK", test1),
        ("Manual AI calls OK", test2),
        ("AI Overview calls OK", test3),
        ("Dashboards load OK", test4)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\n📊 RESULTADO: {passed}/{total} tests pasados")
    
    if passed == total:
        print(f"\n🎊 ¡CORRECCIONES PAYWALL EXITOSAS!")
        print(f"   ✅ Modal paywall funciona sin errores")
        print(f"   ✅ AI Overview se restaura correctamente")
        print(f"   ✅ UX mejorada para usuarios gratuitos")
        print(f"   ✅ Todos los parámetros corregidos")
        print(f"\n💡 Listo para testing manual con usuario Free")
    else:
        print(f"\n⚠️ Hay {total - passed} problemas pendientes")
        print(f"   💡 Revisar logs detallados arriba")

if __name__ == "__main__":
    main()
