#!/usr/bin/env python3
"""
test_mobile_detection.py - Script para probar la detección de dispositivos móviles
"""

import sys
import os
import re

# Agregar el directorio actual al path para importar el módulo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simular Flask request object para testing
class MockRequest:
    def __init__(self, user_agent, remote_addr='127.0.0.1'):
        self.user_agent = user_agent
        self.remote_addr = remote_addr
    
    @property
    def headers(self):
        return MockHeaders(self.user_agent)

class MockHeaders:
    def __init__(self, user_agent):
        self.user_agent = user_agent
    
    def get(self, key, default=''):
        if key == 'User-Agent':
            return self.user_agent
        return default

# Lista de User-Agents de prueba
TEST_USER_AGENTS = [
    # Móviles
    ("iPhone", "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"),
    ("Android Phone", "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"),
    ("Samsung Galaxy", "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"),
    ("Xiaomi", "Mozilla/5.0 (Linux; Android 11; Mi 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"),
    
    # Tablets
    ("iPad", "Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"),
    ("Android Tablet", "Mozilla/5.0 (Linux; Android 11; SM-T870) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Safari/537.36"),
    ("Kindle", "Mozilla/5.0 (Linux; Android 4.4.3; KFTHWI Build/KTU84M) AppleWebKit/537.36 (KHTML, like Gecko) Silk/47.1.79 like Chrome/47.0.2526.80 Safari/537.36"),
    
    # Desktop
    ("Chrome Windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
    ("Firefox Windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"),
    ("Safari Mac", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"),
    ("Edge Windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59"),
    
    # Casos especiales
    ("Opera Mini", "Opera/9.80 (J2ME/MIDP; Opera Mini/9.80 (S60; SymbOS; Opera Mobi/23.348; U; en) Presto/2.5.25 Version/10.54"),
    ("BlackBerry", "Mozilla/5.0 (BlackBerry; U; BlackBerry 9900; en) AppleWebKit/534.11+ (KHTML, like Gecko) Version/7.1.0.346 Mobile Safari/534.11+"),
    ("Windows Phone", "Mozilla/5.0 (compatible; MSIE 10.0; Windows Phone 8.0; Trident/6.0; IEMobile/10.0; ARM; Touch; NOKIA; Lumia 920)"),
]

def test_mobile_detection():
    """
    Prueba la detección de dispositivos móviles con diferentes User-Agents
    """
    print("🔍 Probando detección de dispositivos móviles...")
    print("=" * 80)
    
    # Importar el módulo después de configurar el mock
    import mobile_detector
    
    # Guardar el request original
    original_request = getattr(mobile_detector, 'request', None)
    
    results = []
    
    for device_name, user_agent in TEST_USER_AGENTS:
        # Simular el request de Flask
        mock_request = MockRequest(user_agent)
        mobile_detector.request = mock_request
        
        # Probar las funciones
        is_mobile = mobile_detector.is_mobile_device()
        is_tablet = mobile_detector.is_tablet_device()
        is_small_screen = mobile_detector.is_small_screen()
        should_block = mobile_detector.should_block_mobile_access()
        device_type = mobile_detector.get_device_type()
        
        # Determinar resultado esperado
        expected_block = device_name in ["iPhone", "Android Phone", "Samsung Galaxy", "Xiaomi", "Opera Mini", "BlackBerry", "Windows Phone"]
        
        # Determinar tipo esperado - tablets tienen prioridad
        if device_name in ["iPad", "Android Tablet", "Kindle"]:
            expected_type = "tablet"
        elif device_name in ["iPhone", "Android Phone", "Samsung Galaxy", "Xiaomi", "Opera Mini", "BlackBerry", "Windows Phone"]:
            expected_type = "mobile"
        else:
            expected_type = "desktop"
        
        # Verificar resultado
        test_passed = (should_block == expected_block) and (device_type == expected_type)
        
        results.append({
            'device_name': device_name,
            'is_mobile': is_mobile,
            'is_tablet': is_tablet,
            'should_block': should_block,
            'device_type': device_type,
            'expected_block': expected_block,
            'expected_type': expected_type,
            'test_passed': test_passed
        })
        
        # Mostrar resultado
        status = "✅ PASS" if test_passed else "❌ FAIL"
        print(f"{status} {device_name:<15} | Mobile: {is_mobile:<5} | Tablet: {is_tablet:<5} | Block: {should_block:<5} | Type: {device_type:<7}")
    
    # Restaurar el request original
    if original_request:
        mobile_detector.request = original_request
    
    # Mostrar resumen
    print("=" * 80)
    passed = sum(1 for r in results if r['test_passed'])
    total = len(results)
    print(f"📊 Resumen: {passed}/{total} pruebas pasaron ({passed/total*100:.1f}%)")
    
    # Mostrar fallos si los hay
    failed = [r for r in results if not r['test_passed']]
    if failed:
        print("\n❌ Pruebas fallidas:")
        for f in failed:
            print(f"  - {f['device_name']}: esperado block={f['expected_block']}, obtenido={f['should_block']}")
    
    print("\n✅ Pruebas completadas!")
    return passed == total

def test_specific_patterns():
    """
    Prueba patrones específicos de detección
    """
    print("\n🔍 Probando patrones específicos...")
    print("=" * 50)
    
    # Importar el módulo
    import mobile_detector
    
    # Patrones a probar
    patterns = [
        ("android", True, "Android genérico"),
        ("iphone", True, "iPhone"),
        ("mobile", True, "Mobile genérico"),
        ("tablet", False, "Tablet - no debe bloquear"),
        ("ipad", False, "iPad - no debe bloquear"),
        ("windows nt", False, "Windows Desktop"),
        ("macintosh", False, "Mac Desktop"),
        ("linux", False, "Linux Desktop genérico"),
        ("android mobile", True, "Android Mobile específico"),
        ("android tablet", False, "Android Tablet específico"),
    ]
    
    passed = 0
    total = len(patterns)
    
    for pattern, should_be_mobile, description in patterns:
        # Crear user agent con el patrón
        user_agent = f"Mozilla/5.0 (TestDevice; {pattern}) TestBrowser/1.0"
        
        # Simular request
        mock_request = MockRequest(user_agent)
        mobile_detector.request = mock_request
        
        # Probar detección
        is_mobile = mobile_detector.is_mobile_device()
        should_block = mobile_detector.should_block_mobile_access()
        
        # Verificar (para tablets, puede ser mobile pero no should_block)
        if "tablet" in pattern.lower() or "ipad" in pattern.lower():
            test_passed = not should_block  # Tablets no se bloquean
        else:
            test_passed = should_be_mobile == is_mobile
        
        if test_passed:
            passed += 1
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - esperado: {should_be_mobile}, obtenido: {is_mobile}")
    
    print(f"\n📊 Patrones: {passed}/{total} pasaron ({passed/total*100:.1f}%)")
    return passed == total

def main():
    """
    Función principal para ejecutar todas las pruebas
    """
    print("🚀 Iniciando pruebas de detección de dispositivos móviles")
    print("=" * 80)
    
    # Verificar que el módulo se puede importar
    try:
        import mobile_detector
        print("✅ Módulo mobile_detector importado correctamente")
    except ImportError as e:
        print(f"❌ Error importando mobile_detector: {e}")
        return False
    
    # Ejecutar pruebas
    test1_passed = test_mobile_detection()
    test2_passed = test_specific_patterns()
    
    # Resultado final
    print("\n" + "=" * 80)
    if test1_passed and test2_passed:
        print("🎉 ¡Todas las pruebas pasaron! La detección de dispositivos móviles funciona correctamente.")
        return True
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa la implementación.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 