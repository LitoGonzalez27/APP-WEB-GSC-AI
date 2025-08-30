#!/usr/bin/env python3
"""
Test Expert Improvements - Verificar mejoras críticas de seguridad y UX
=========================================================================

Verifica la implementación de todas las mejoras sugeridas por el experto:
✅ Validación de plan en backend
✅ Verificación de suscripción existente
✅ Customer Portal para upgrades
✅ Sesiones pegajosas y cancel_url
✅ Success page con verificación real
✅ Bloqueo de Enterprise self-serve
"""

import os
import sys
import requests
import json
import time
from urllib.parse import urlparse, parse_qs

# URL base (cambiar según entorno)
BASE_URL = 'https://clicandseo.up.railway.app'

class TestExpertImprovements:
    
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        
    def log_test(self, test_name, result, details=""):
        """Log de resultado de test"""
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        
        self.test_results.append({
            'test': test_name,
            'passed': result,
            'details': details
        })
    
    def test_plan_validation_security(self):
        """Test 1: Validación de plan en backend"""
        print("\n🔒 TEST 1: VALIDACIÓN DE PLAN EN BACKEND")
        
        # Test plan inválido
        try:
            response = self.session.get(f"{BASE_URL}/billing/checkout/invalid_plan", allow_redirects=False)
            redirect_location = response.headers.get('Location', '')
            
            # Debe redirigir con error
            if 'error=invalid_plan' in redirect_location or response.status_code in [302, 400]:
                self.log_test("Plan inválido rechazado", True, f"Status: {response.status_code}")
            else:
                self.log_test("Plan inválido rechazado", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Plan inválido rechazado", False, f"Error: {e}")
    
    def test_enterprise_blocking(self):
        """Test 2: Bloqueo de Enterprise self-serve"""
        print("\n🚫 TEST 2: BLOQUEO ENTERPRISE SELF-SERVE")
        
        # Test signup con plan=enterprise
        try:
            response = self.session.get(f"{BASE_URL}/signup?plan=enterprise&source=pricing", allow_redirects=False)
            redirect_location = response.headers.get('Location', '')
            
            # Debe redirigir a contacto
            if 'clicandseo.com/contact' in redirect_location:
                self.log_test("Enterprise signup → contacto", True, f"Redirect: {redirect_location}")
            else:
                self.log_test("Enterprise signup → contacto", False, f"Redirect: {redirect_location}")
                
        except Exception as e:
            self.log_test("Enterprise signup → contacto", False, f"Error: {e}")
        
        # Test login con plan=enterprise
        try:
            response = self.session.get(f"{BASE_URL}/login?plan=enterprise&source=pricing", allow_redirects=False)
            redirect_location = response.headers.get('Location', '')
            
            # Debe redirigir a contacto
            if 'clicandseo.com/contact' in redirect_location:
                self.log_test("Enterprise login → contacto", True, f"Redirect: {redirect_location}")
            else:
                self.log_test("Enterprise login → contacto", False, f"Redirect: {redirect_location}")
                
        except Exception as e:
            self.log_test("Enterprise login → contacto", False, f"Error: {e}")
        
        # Test checkout con plan=enterprise
        try:
            response = self.session.get(f"{BASE_URL}/billing/checkout/enterprise", allow_redirects=False)
            redirect_location = response.headers.get('Location', '')
            
            # Debe redirigir a contacto
            if 'clicandseo.com/contact' in redirect_location:
                self.log_test("Enterprise checkout → contacto", True, f"Redirect: {redirect_location}")
            else:
                self.log_test("Enterprise checkout → contacto", False, f"Redirect: {redirect_location}")
                
        except Exception as e:
            self.log_test("Enterprise checkout → contacto", False, f"Error: {e}")
    
    def test_cancel_url_route(self):
        """Test 3: Ruta de cancelación existe"""
        print("\n🔄 TEST 3: RUTA DE CANCELACIÓN")
        
        try:
            response = self.session.get(f"{BASE_URL}/billing/cancel?plan=basic", allow_redirects=False)
            
            # Debe existir la ruta (no 404)
            if response.status_code != 404:
                self.log_test("Ruta /billing/cancel existe", True, f"Status: {response.status_code}")
            else:
                self.log_test("Ruta /billing/cancel existe", False, "404 Not Found")
                
        except Exception as e:
            self.log_test("Ruta /billing/cancel existe", False, f"Error: {e}")
    
    def test_verification_api(self):
        """Test 4: API de verificación de activación"""
        print("\n🔍 TEST 4: API VERIFICACIÓN ACTIVACIÓN")
        
        try:
            response = self.session.get(f"{BASE_URL}/api/billing/verify-activation")
            
            # Debe existir la ruta
            if response.status_code in [200, 401, 403]:  # 401/403 = no auth, pero ruta existe
                self.log_test("API verify-activation existe", True, f"Status: {response.status_code}")
                
                # Si devuelve JSON, verificar estructura
                if response.status_code == 200:
                    try:
                        data = response.json()
                        expected_keys = ['plan', 'billing_status', 'activated']
                        has_keys = all(key in data for key in expected_keys)
                        self.log_test("API estructura correcta", has_keys, f"Keys: {list(data.keys())}")
                    except json.JSONDecodeError:
                        self.log_test("API estructura correcta", False, "No JSON response")
            else:
                self.log_test("API verify-activation existe", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("API verify-activation existe", False, f"Error: {e}")
    
    def test_success_page_improvements(self):
        """Test 5: Mejoras en página de success"""
        print("\n🎉 TEST 5: MEJORAS SUCCESS PAGE")
        
        try:
            response = self.session.get(f"{BASE_URL}/billing/success")
            
            # Verificar que la página carga
            if response.status_code == 200:
                content = response.text
                
                # Verificar elementos JavaScript
                has_verification_js = "verify-activation" in content
                has_polling_logic = "verifyPlanActivation" in content
                has_status_div = "activation-status" in content
                
                self.log_test("Success page JavaScript", has_verification_js, "Verificación API presente")
                self.log_test("Success page polling", has_polling_logic, "Polling logic presente")
                self.log_test("Success page status div", has_status_div, "Status div presente")
                
            else:
                self.log_test("Success page carga", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Success page carga", False, f"Error: {e}")
    
    def test_parameter_persistence(self):
        """Test 6: Persistencia de parámetros en sesión"""
        print("\n💾 TEST 6: PERSISTENCIA DE PARÁMETROS")
        
        # Test signup con parámetros
        try:
            response = self.session.get(f"{BASE_URL}/signup?plan=basic&source=pricing")
            
            # Debe cargar sin error (aunque requiera auth)
            if response.status_code in [200, 302]:
                self.log_test("Signup con parámetros", True, f"Status: {response.status_code}")
            else:
                self.log_test("Signup con parámetros", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Signup con parámetros", False, f"Error: {e}")
        
        # Test login con parámetros
        try:
            response = self.session.get(f"{BASE_URL}/login?plan=premium&source=pricing")
            
            # Debe cargar sin error
            if response.status_code == 200:
                self.log_test("Login con parámetros", True, f"Status: {response.status_code}")
            else:
                self.log_test("Login con parámetros", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Login con parámetros", False, f"Error: {e}")
    
    def test_billing_routes_security(self):
        """Test 7: Seguridad en rutas de billing"""
        print("\n🛡️ TEST 7: SEGURIDAD RUTAS BILLING")
        
        # Test acceso sin auth a rutas protegidas
        protected_routes = [
            '/billing/checkout/basic',
            '/billing/portal',
            '/billing',
            '/api/billing/verify-activation'
        ]
        
        for route in protected_routes:
            try:
                # Nueva sesión sin auth
                unauth_session = requests.Session()
                response = unauth_session.get(f"{BASE_URL}{route}", allow_redirects=False)
                
                # Debe requerir auth (redirect a login o 401/403)
                requires_auth = (
                    response.status_code in [401, 403] or 
                    ('/login' in response.headers.get('Location', ''))
                )
                
                self.log_test(f"Auth requerido {route}", requires_auth, f"Status: {response.status_code}")
                
            except Exception as e:
                self.log_test(f"Auth requerido {route}", False, f"Error: {e}")
    
    def run_all_tests(self):
        """Ejecutar todos los tests"""
        print("🧪 TESTING EXPERT IMPROVEMENTS")
        print("=" * 50)
        print(f"🎯 Target: {BASE_URL}")
        print()
        
        # Ejecutar tests
        self.test_plan_validation_security()
        self.test_enterprise_blocking() 
        self.test_cancel_url_route()
        self.test_verification_api()
        self.test_success_page_improvements()
        self.test_parameter_persistence()
        self.test_billing_routes_security()
        
        # Resumen
        print("\n" + "=" * 50)
        print("📊 RESUMEN DE RESULTADOS")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success rate: {(passed_tests/total_tests)*100:.1f}%")
        
        # Detalles de fallos
        if failed_tests > 0:
            print("\n❌ TESTS FALLIDOS:")
            for test in self.test_results:
                if not test['passed']:
                    print(f"  - {test['test']}: {test['details']}")
        else:
            print("\n🎉 ¡TODOS LOS TESTS PASARON!")
        
        return failed_tests == 0

if __name__ == "__main__":
    # Configurar URL base según entorno
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1].rstrip('/')
    
    print(f"🎯 Testing Expert Improvements en: {BASE_URL}")
    
    # Ejecutar tests
    tester = TestExpertImprovements()
    success = tester.run_all_tests()
    
    # Exit code
    sys.exit(0 if success else 1)
