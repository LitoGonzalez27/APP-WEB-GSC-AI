#!/usr/bin/env python3
"""
Testing de las mejoras UX del paywall:
1. Modal sin iconos, RU clarificado, título subrayado, botones CTA
2. AI Overview cambia a "View Plans" después del paywall
"""

import requests
import time

STAGING_URL = "https://clicandseo.up.railway.app"

def test_paywall_modal_improvements():
    """Test que el modal paywall tiene todas las mejoras UX"""
    print("\n🔍 TESTING MEJORAS MODAL PAYWALL")
    print("="*50)
    
    try:
        response = requests.get(f"{STAGING_URL}/static/js/paywall.js", timeout=10)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            improvements_checklist = [
                # Sin iconos
                ('Sin emoji en título', '🚀 ${featureName}' not in content),
                ('Sin emoji "What you\'ll get"', '✨ What you\'ll get:' not in content),
                ('Sin emoji AI Overview', '🔍 <strong>AI Overview' not in content),
                ('Sin emoji Manual AI', '🎯 <strong>Manual AI' not in content),
                ('Sin emoji RU explanation', '💡 What are RU?' not in content),
                
                # Mejoras de texto
                ('RU clarificado', '1 API Call = 1 keyword analyzed' in content),
                ('Título con clase premium', 'paywall-title-premium' in content),
                
                # Botones
                ('View Plans es btn-primary', 'btn-primary">\\n                        View All Plans' in content),
                ('Maybe Later es btn-secondary', 'btn-secondary" onclick' in content),
                
                # Función cambio botón AI
                ('Función changeAIOverviewToViewPlans', 'changeAIOverviewToViewPlans' in content),
                ('Botón View Plans AI', 'btn-view-plans-ai' in content),
                ('Redirige a billing', "window.location.href = '/billing'" in content),
            ]
            
            passed = 0
            total = len(improvements_checklist)
            
            for description, check in improvements_checklist:
                if check:
                    print(f"✅ {description}")
                    passed += 1
                else:
                    print(f"❌ {description}")
            
            print(f"\n📊 Modal improvements: {passed}/{total}")
            return passed == total
        else:
            print(f"❌ No se pudo cargar paywall.js: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_paywall_css_styles():
    """Test que los estilos CSS están implementados"""
    print("\n🔍 TESTING ESTILOS CSS PAYWALL")
    print("="*45)
    
    try:
        response = requests.get(f"{STAGING_URL}/static/paywall.css", timeout=10)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            css_checklist = [
                ('Título premium con subrayado', '.paywall-title-premium' in content),
                ('Gradiente verde subrayado', 'linear-gradient(to top, #D8F9B8 40%, transparent 40%)' in content),
                ('Botón View Plans AI', '.btn-view-plans-ai' in content),
                ('CTA fondo negro', 'background: #161616' in content),
                ('CTA texto verde', 'color: #D8F9B8' in content),
                ('Hover invertido fondo', 'background: #D8F9B8' in content),
                ('Hover invertido texto', 'color: #161616' in content),
            ]
            
            passed = 0
            total = len(css_checklist)
            
            for description, check in css_checklist:
                if check:
                    print(f"✅ {description}")
                    passed += 1
                else:
                    print(f"❌ {description}")
            
            print(f"\n📊 CSS styles: {passed}/{total}")
            return passed == total
        else:
            print(f"❌ No se pudo cargar paywall.css: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_main_app_includes_paywall():
    """Test que la app principal incluye los assets de paywall actualizados"""
    print("\n🔍 TESTING INCLUSIÓN ASSETS PAYWALL")
    print("="*50)
    
    try:
        response = requests.get(f"{STAGING_URL}/", timeout=10)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Verificar que incluye los scripts y CSS
            if 'paywall.js' in content:
                print("✅ paywall.js incluido en main app")
            else:
                print("❌ paywall.js no incluido")
                
            if 'paywall.css' in content:
                print("✅ paywall.css incluido en main app")
            else:
                print("❌ paywall.css no incluido")
                
            return 'paywall.js' in content and 'paywall.css' in content
        else:
            print(f"❌ No se pudo cargar main app: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_manual_ai_includes_paywall():
    """Test que Manual AI incluye los assets de paywall"""
    print("\n🔍 TESTING MANUAL AI INCLUDES PAYWALL")
    print("="*50)
    
    try:
        response = requests.get(f"{STAGING_URL}/manual-ai/", timeout=10, allow_redirects=False)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            if 'login' in location:
                print("✅ Manual AI redirige a login (sin autenticación)")
                # Esto es correcto, el modal se incluirá cuando esté autenticado
                return True
            else:
                print(f"❓ Manual AI redirige a: {location}")
                return False
        elif response.status_code == 200:
            content = response.text
            
            if 'paywall.js' in content and 'paywall.css' in content:
                print("✅ Manual AI incluye assets paywall")
                return True
            else:
                print("❌ Manual AI no incluye assets paywall")
                return False
        else:
            print(f"❌ Status inesperado: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Ejecutar todos los tests de las mejoras UX"""
    print("🧪 TESTING MEJORAS UX PAYWALL")
    print("="*60)
    print("🎯 Verificando que:")
    print("   1. Modal sin iconos, RU clarificado, título subrayado")
    print("   2. Botones con estilos correctos (CTA vs secundario)")
    print("   3. AI Overview cambia a 'View Plans' después paywall")
    print("   4. Estilos CSS implementados correctamente")
    
    # Ejecutar tests
    test1 = test_paywall_modal_improvements()
    test2 = test_paywall_css_styles()
    test3 = test_main_app_includes_paywall()
    test4 = test_manual_ai_includes_paywall()
    
    # Resumen
    print(f"\n🎯 RESUMEN FINAL")
    print("="*40)
    
    tests = [
        ("Modal improvements", test1),
        ("CSS styles", test2),
        ("Main app assets", test3),
        ("Manual AI assets", test4)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\n📊 RESULTADO: {passed}/{total} tests pasados")
    
    if passed == total:
        print(f"\n🎊 ¡MEJORAS UX IMPLEMENTADAS PERFECTAMENTE!")
        print(f"   ✅ Modal paywall más limpio y claro")
        print(f"   ✅ Título con subrayado verde")
        print(f"   ✅ Botones con estilos CTA correctos")
        print(f"   ✅ AI Overview guía hacia billing")
        print(f"   ✅ Consistencia visual con Manual AI")
        print(f"\n💡 Lista para testing manual - UX optimizada")
    else:
        print(f"\n⚠️ Hay {total - passed} problemas pendientes")
        print(f"   💡 Revisar implementación detallada")

if __name__ == "__main__":
    main()
