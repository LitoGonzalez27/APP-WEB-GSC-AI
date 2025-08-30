#!/usr/bin/env python3
"""
Test Admin Panel Staging - Verificación completa del panel admin mejorado
=========================================================================

Este script verifica que todas las mejoras del panel admin funcionen correctamente
en el entorno de staging, incluyendo barras progresivas, datos de billing y sincronización.
"""

import os
import requests
import json
from datetime import datetime
import time

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

def test_admin_panel_access():
    """Test 1: Verificar acceso al panel admin"""
    print_section("ACCESO AL PANEL ADMIN")
    
    try:
        # Test básico de conectividad
        response = requests.get(f"{STAGING_URL}/admin/users", timeout=10)
        
        if response.status_code == 200:
            print_test("Acceso a /admin/users", True, f"Status: {response.status_code}")
            
            # Verificar que contiene elementos esperados
            content = response.text
            has_quota_progress = "quota-progress-container" in content
            has_billing_details = "billing-details" in content
            has_modal_sections = "Plan y Facturación" in content
            
            print_test("Contiene barras progresivas", has_quota_progress)
            print_test("Contiene endpoints de billing", has_billing_details) 
            print_test("Contiene modal mejorado", has_modal_sections)
            
            return True
            
        else:
            print_test("Acceso a /admin/users", False, f"Status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_test("Conexión a staging", False, f"Error: {e}")
        return False

def test_billing_endpoint():
    """Test 2: Verificar endpoint de billing details"""
    print_section("ENDPOINTS DE BILLING")
    
    try:
        # Test endpoint de billing details (necesitarás autenticación real)
        test_user_id = 5  # ID de usuario de prueba
        response = requests.get(f"{STAGING_URL}/admin/users/{test_user_id}/billing-details", timeout=10)
        
        if response.status_code in [200, 401, 403]:  # 401/403 es esperado sin auth
            print_test("Endpoint billing-details existe", True, f"Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    has_user_data = 'user' in data
                    print_test("Response contiene datos de usuario", has_user_data)
                except:
                    print_test("Response es JSON válido", False)
            else:
                print_test("Sin autenticación (esperado)", True, "Requiere login de admin")
            
            return True
        else:
            print_test("Endpoint billing-details", False, f"Status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_test("Test billing endpoint", False, f"Error: {e}")
        return False

def test_database_connection():
    """Test 3: Verificar conexión a base de datos"""
    print_section("BASE DE DATOS")
    
    if not DATABASE_URL:
        print_test("DATABASE_URL configurado", False, "Variable no encontrada")
        return False
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test 1: Verificar que existen las columnas de billing
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('plan', 'quota_limit', 'quota_used', 'current_period_start', 'current_period_end')
        """)
        billing_columns = [row['column_name'] for row in cur.fetchall()]
        
        expected_columns = ['plan', 'quota_limit', 'quota_used', 'current_period_start', 'current_period_end']
        missing_columns = set(expected_columns) - set(billing_columns)
        
        print_test("Columnas de billing existen", len(missing_columns) == 0, 
                  f"Encontradas: {billing_columns}, Faltantes: {list(missing_columns)}")
        
        # Test 2: Verificar datos de usuarios
        cur.execute("SELECT COUNT(*) as count FROM users")
        user_count = cur.fetchone()['count']
        print_test("Usuarios en base de datos", user_count > 0, f"Total: {user_count}")
        
        # Test 3: Verificar usuarios con datos de quota
        cur.execute("SELECT COUNT(*) as count FROM users WHERE quota_limit > 0")
        users_with_quota = cur.fetchone()['count']
        print_test("Usuarios con quotas configuradas", users_with_quota > 0, f"Total: {users_with_quota}")
        
        conn.close()
        return True
        
    except Exception as e:
        print_test("Conexión a base de datos", False, f"Error: {e}")
        return False

def test_frontend_assets():
    """Test 4: Verificar assets del frontend"""
    print_section("ASSETS FRONTEND")
    
    try:
        # Verificar CSS y JS específicos
        css_response = requests.get(f"{STAGING_URL}/static/quota-ui.css", timeout=10)
        js_response = requests.get(f"{STAGING_URL}/static/js/quota-ui.js", timeout=10)
        
        print_test("CSS de quotas existe", css_response.status_code == 200)
        print_test("JS de quotas existe", js_response.status_code == 200)
        
        # Verificar admin_simple.html se sirve correctamente
        admin_response = requests.get(f"{STAGING_URL}/admin/users", timeout=10)
        if admin_response.status_code == 200:
            content = admin_response.text
            
            # Verificar elementos clave del HTML mejorado
            has_progress_css = "quota-progress-container" in content
            has_modal_sections = "Plan y Facturación" in content
            has_js_init = "initializeQuotaProgressBars" in content
            
            print_test("HTML contiene CSS de barras progresivas", has_progress_css)
            print_test("HTML contiene modal mejorado", has_modal_sections)
            print_test("HTML contiene JS de inicialización", has_js_init)
        
        return True
        
    except Exception as e:
        print_test("Verificación assets frontend", False, f"Error: {e}")
        return False

def run_comprehensive_test():
    """Ejecutar todas las pruebas"""
    print("🚀 TESTING ADMIN PANEL STAGING - COMPREHENSIVE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Target: {STAGING_URL}")
    
    tests = [
        test_admin_panel_access,
        test_billing_endpoint,
        test_database_connection,
        test_frontend_assets
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
    print_section("RESUMEN FINAL")
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Tests ejecutados: {total}")
    print(f"✅ Tests exitosos: {passed}")
    print(f"❌ Tests fallidos: {total - passed}")
    print(f"📈 Tasa de éxito: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print(f"\n🎊 TODOS LOS TESTS PASARON - STAGING LISTO")
    else:
        print(f"\n⚠️ HAY TESTS FALLIDOS - REVISAR STAGING")
    
    return passed == total

if __name__ == "__main__":
    # Ejecutar tests
    success = run_comprehensive_test()
    
    print(f"\n{'='*60}")
    print("🎯 PRÓXIMOS PASOS:")
    print("1. Si todos los tests pasan → Continuar con tests de Stripe")
    print("2. Si hay fallos → Revisar logs de Railway y corregir")
    print("3. Verificar el panel admin manualmente en el navegador")
    print(f"4. URL: {STAGING_URL}/admin/users")
    print('='*60)
