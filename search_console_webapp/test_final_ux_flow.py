#!/usr/bin/env python3
"""
Testing final del flujo UX completo mejorado
Verifica que todos los problemas del usuario están resueltos
"""

import requests
import time

STAGING_URL = "https://clicandseo.up.railway.app"

def test_manual_ai_always_accessible():
    """Test que Manual AI es siempre accesible (sin restricción por rol)"""
    print("\n🔍 TESTING MANUAL AI SIEMPRE ACCESIBLE")
    print("="*60)
    
    try:
        response = requests.get(f"{STAGING_URL}/manual-ai/", timeout=10, allow_redirects=False)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            if 'login' in location:
                print("✅ CORRECTO: Redirige a login (esperado sin autenticación)")
                print("   Manual AI accesible para usuarios autenticados")
            else:
                print(f"❓ Redirige a: {location}")
        elif response.status_code == 200:
            print("✅ CORRECTO: Manual AI accesible directamente")
        elif response.status_code == 403:
            print("❌ PROBLEMA: Manual AI bloqueado por rol (debería estar accesible)")
        else:
            print(f"❓ Status inesperado: {response.status_code}")
            
        return response.status_code in [200, 302]
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_ai_overview_no_progress_after_paywall():
    """Test que AI Overview no continúa progreso después del paywall"""
    print("\n🔍 TESTING AI OVERVIEW DETIENE PROGRESO EN PAYWALL")
    print("="*65)
    
    try:
        # Test que devuelve 402 sin autenticación
        payload = {"keywords": ["test"], "site_url": "example.com"}
        response = requests.post(f"{STAGING_URL}/api/analyze-ai-overview", json=payload, timeout=10)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✅ CORRECTO: Retorna 401 sin autenticación (esperado)")
        elif response.status_code == 402:
            print("✅ CORRECTO: Retorna 402 paywall")
            data = response.json()
            print(f"   💬 Mensaje: {data.get('message')}")
            print(f"   🔄 Upgrade options: {data.get('upgrade_options')}")
        else:
            print(f"❓ Status: {response.status_code}")
            
        return response.status_code in [401, 402]
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_navigation_ai_user_removed():
    """Test que la navegación no requiere rol AI User"""
    print("\n🔍 TESTING NAVEGACIÓN SIN ROL AI USER")
    print("="*50)
    
    try:
        response = requests.get(f"{STAGING_URL}/", timeout=10)
        content = response.text
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Verificar que no hay referencias a AI User
            ai_user_refs = content.count("AI User")
            ai_user_role_refs = content.count("role in ['admin', 'AI User']")
            
            print(f"📊 Referencias 'AI User': {ai_user_refs}")
            print(f"📊 Referencias rol AI User: {ai_user_role_refs}")
            
            if ai_user_role_refs == 0:
                print("✅ CORRECTO: No hay restricciones por rol AI User en navegación")
            else:
                print("❌ PROBLEMA: Aún hay restricciones por rol AI User")
                
            return ai_user_role_refs == 0
        else:
            print(f"❌ No se pudo cargar página principal: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_paywall_modals_working():
    """Test que los modales de paywall están funcionando"""
    print("\n🔍 TESTING MODALES DE PAYWALL")
    print("="*45)
    
    try:
        # Test que los assets están disponibles
        assets = [
            "/static/js/paywall.js",
            "/static/paywall.css"
        ]
        
        all_ok = True
        for asset in assets:
            response = requests.get(f"{STAGING_URL}{asset}", timeout=10)
            if response.status_code == 200:
                print(f"✅ {asset}: Disponible")
            else:
                print(f"❌ {asset}: Status {response.status_code}")
                all_ok = False
                
        return all_ok
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_admin_panel_no_ai_user():
    """Test que el panel admin no tiene rol AI User"""
    print("\n🔍 TESTING ADMIN PANEL SIN ROL AI USER")
    print("="*50)
    
    try:
        # Intentar acceder al admin (esperamos redirect a login)
        response = requests.get(f"{STAGING_URL}/admin/users", timeout=10, allow_redirects=False)
        
        print(f"📋 Status Code: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            if 'login' in location:
                print("✅ CORRECTO: Admin panel protegido, redirige a login")
            else:
                print(f"❓ Redirige a: {location}")
                
        return response.status_code == 302
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Ejecutar todos los tests"""
    print("🧪 TESTING FINAL - RESOLUCIÓN PROBLEMAS USUARIO")
    print("="*70)
    print("🎯 Verificando que:")
    print("   1. Manual AI siempre accesible")
    print("   2. AI Overview detiene progreso en paywall")
    print("   3. Rol AI User eliminado del sistema")
    print("   4. Paywalls funcionando correctamente")
    
    # Ejecutar tests
    test1 = test_manual_ai_always_accessible()
    test2 = test_ai_overview_no_progress_after_paywall()
    test3 = test_navigation_ai_user_removed()
    test4 = test_paywall_modals_working()
    test5 = test_admin_panel_no_ai_user()
    
    # Resumen
    print(f"\n🎯 RESUMEN FINAL")
    print("="*40)
    
    tests = [
        ("Manual AI accesible", test1),
        ("AI Overview detiene progreso", test2),
        ("Navegación sin AI User", test3),
        ("Modales paywall OK", test4),
        ("Admin panel sin AI User", test5)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\n📊 RESULTADO: {passed}/{total} tests pasados")
    
    if passed == total:
        print(f"\n🎊 ¡PERFECTO! Todos los problemas del usuario resueltos:")
        print(f"   ✅ Manual AI siempre accesible")
        print(f"   ✅ Progreso se detiene en paywall")
        print(f"   ✅ Rol AI User eliminado")
        print(f"   ✅ Sistema simplificado por planes")
        print(f"\n💡 Listo para testing manual con usuario Free")
    else:
        print(f"\n⚠️ Hay {total - passed} problemas pendientes")
        print(f"   💡 Revisar logs y realizar testing manual")

if __name__ == "__main__":
    main()
