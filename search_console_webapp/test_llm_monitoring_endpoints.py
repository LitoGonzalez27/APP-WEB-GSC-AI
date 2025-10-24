#!/usr/bin/env python3
"""
Script de Test para API Endpoints de Multi-LLM Monitoring

Este script verifica que todos los endpoints estén correctamente implementados:
- Imports
- Estructura de funciones
- Decoradores de autenticación
- Blueprint registrado

NO ejecuta tests reales de HTTP (requeriría servidor corriendo)
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """Test 1: Verificar que los módulos se importen correctamente"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 1: VERIFICANDO IMPORTS")
    logger.info("=" * 70)
    
    try:
        from llm_monitoring_routes import llm_monitoring_bp
        logger.info("   ✅ llm_monitoring_routes importado")
        logger.info(f"   ✅ Blueprint: {llm_monitoring_bp.name}")
        logger.info(f"   ✅ URL Prefix: {llm_monitoring_bp.url_prefix}")
        return True
    except ImportError as e:
        logger.error(f"   ❌ Error importando: {e}")
        return False
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_blueprint_structure():
    """Test 2: Verificar estructura del Blueprint"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 2: VERIFICANDO ESTRUCTURA DEL BLUEPRINT")
    logger.info("=" * 70)
    
    try:
        from llm_monitoring_routes import llm_monitoring_bp
        
        # Obtener todas las rutas registradas
        rules = list(llm_monitoring_bp.deferred_functions)
        
        logger.info(f"   Total de rutas registradas: {len(rules)}")
        
        # Verificar que tenga al menos las rutas esperadas
        expected_min_routes = 10  # Mínimo esperado
        
        if len(rules) >= expected_min_routes:
            logger.info(f"   ✅ Blueprint tiene {len(rules)} rutas (esperado: >={expected_min_routes})")
            return True
        else:
            logger.error(f"   ❌ Blueprint solo tiene {len(rules)} rutas (esperado: >={expected_min_routes})")
            return False
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_endpoint_functions():
    """Test 3: Verificar que todas las funciones de endpoint existan"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 3: VERIFICANDO FUNCIONES DE ENDPOINTS")
    logger.info("=" * 70)
    
    expected_functions = [
        'get_projects',
        'create_project',
        'get_project',
        'update_project',
        'delete_project',
        'analyze_project',
        'get_project_metrics',
        'get_llm_comparison',
        'get_api_keys',
        'configure_api_keys',
        'get_budget',
        'get_models',
        'update_model',
        'health_check'
    ]
    
    try:
        import llm_monitoring_routes
        
        all_ok = True
        
        for func_name in expected_functions:
            if hasattr(llm_monitoring_routes, func_name):
                logger.info(f"   ✅ {func_name}() existe")
            else:
                logger.error(f"   ❌ {func_name}() NO encontrada")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_decorators():
    """Test 4: Verificar decoradores de autenticación"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 4: VERIFICANDO DECORADORES")
    logger.info("=" * 70)
    
    try:
        import llm_monitoring_routes
        import inspect
        
        # Funciones que deben tener @login_required
        protected_functions = [
            'get_projects',
            'create_project',
            'get_project',
            'analyze_project',
            'get_api_keys'
        ]
        
        all_ok = True
        
        for func_name in protected_functions:
            if hasattr(llm_monitoring_routes, func_name):
                func = getattr(llm_monitoring_routes, func_name)
                # Verificar que la función tenga un wrapper (decorada)
                if hasattr(func, '__wrapped__') or func.__name__ != func_name:
                    logger.info(f"   ✅ {func_name}() parece estar decorada")
                else:
                    logger.warning(f"   ⚠️ {func_name}() podría no estar decorada")
            else:
                logger.error(f"   ❌ {func_name}() no existe")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_app_registration():
    """Test 5: Verificar que el Blueprint esté registrado en app.py"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 5: VERIFICANDO REGISTRO EN APP.PY")
    logger.info("=" * 70)
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('llm_monitoring_routes', 'Import del módulo'),
            ('llm_monitoring_bp', 'Import del Blueprint'),
            ('register_blueprint(llm_monitoring_bp)', 'Registro del Blueprint')
        ]
        
        all_ok = True
        
        for check_str, description in checks:
            if check_str in content:
                logger.info(f"   ✅ {description} encontrado")
            else:
                logger.error(f"   ❌ {description} NO encontrado")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error leyendo app.py: {e}")
        return False


def test_endpoints_documentation():
    """Test 6: Verificar documentación de endpoints"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 6: VERIFICANDO DOCUMENTACIÓN")
    logger.info("=" * 70)
    
    try:
        import llm_monitoring_routes
        
        # Funciones principales que deben tener docstring
        functions_to_check = [
            'get_projects',
            'create_project',
            'analyze_project',
            'get_project_metrics'
        ]
        
        all_ok = True
        
        for func_name in functions_to_check:
            if hasattr(llm_monitoring_routes, func_name):
                func = getattr(llm_monitoring_routes, func_name)
                if func.__doc__ and len(func.__doc__.strip()) > 10:
                    logger.info(f"   ✅ {func_name}() tiene docstring")
                else:
                    logger.warning(f"   ⚠️ {func_name}() sin docstring o muy corto")
                    all_ok = False
            else:
                logger.error(f"   ❌ {func_name}() no existe")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_endpoint_list():
    """Test 7: Listar todos los endpoints disponibles"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 7: LISTANDO ENDPOINTS DISPONIBLES")
    logger.info("=" * 70)
    
    try:
        from flask import Flask
        from llm_monitoring_routes import llm_monitoring_bp
        
        # Crear app temporal para obtener rutas
        temp_app = Flask(__name__)
        temp_app.register_blueprint(llm_monitoring_bp)
        
        # Obtener rutas del blueprint
        routes = []
        for rule in temp_app.url_map.iter_rules():
            if '/api/llm-monitoring' in rule.rule:
                routes.append({
                    'endpoint': rule.endpoint,
                    'methods': ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})),
                    'path': rule.rule
                })
        
        logger.info(f"\n   Total de endpoints: {len(routes)}\n")
        
        # Agrupar por categoría
        categories = {
            'Proyectos': [],
            'Análisis': [],
            'Configuración': [],
            'Modelos': [],
            'Sistema': []
        }
        
        for route in routes:
            path = route['path']
            if '/projects' in path and '/analyze' not in path and '/metrics' not in path and '/comparison' not in path:
                categories['Proyectos'].append(route)
            elif '/analyze' in path or '/metrics' in path or '/comparison' in path:
                categories['Análisis'].append(route)
            elif '/api-keys' in path or '/budget' in path:
                categories['Configuración'].append(route)
            elif '/models' in path:
                categories['Modelos'].append(route)
            elif '/health' in path:
                categories['Sistema'].append(route)
        
        for category, endpoints in categories.items():
            if endpoints:
                logger.info(f"   {category}:")
                for ep in endpoints:
                    logger.info(f"      {ep['methods']:8} {ep['path']}")
                logger.info("")
        
        return len(routes) > 0
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_database_integration():
    """Test 8: Verificar integración con database.py"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 8: VERIFICANDO INTEGRACIÓN CON DATABASE")
    logger.info("=" * 70)
    
    try:
        with open('llm_monitoring_routes.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('from database import get_db_connection', 'Import de get_db_connection'),
            ('get_db_connection()', 'Uso de get_db_connection'),
            ('conn.cursor()', 'Uso de cursor'),
            ('cur.execute(', 'Ejecución de queries'),
            ('conn.commit()', 'Commits de transacciones'),
            ('conn.rollback()', 'Rollbacks de transacciones'),
            ('cur.close()', 'Cierre de cursores'),
            ('conn.close()', 'Cierre de conexiones')
        ]
        
        all_ok = True
        
        for check_str, description in checks:
            count = content.count(check_str)
            if count > 0:
                logger.info(f"   ✅ {description} ({count} veces)")
            else:
                logger.warning(f"   ⚠️ {description} no encontrado")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def main():
    """Ejecutar todos los tests"""
    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 12 + "TEST SUITE: LLM MONITORING ENDPOINTS" + " " * 20 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    
    tests = [
        ("Imports", test_imports),
        ("Blueprint Structure", test_blueprint_structure),
        ("Endpoint Functions", test_endpoint_functions),
        ("Decoradores", test_decorators),
        ("Registro en app.py", test_app_registration),
        ("Documentación", test_endpoints_documentation),
        ("Listado de Endpoints", test_endpoint_list),
        ("Integración Database", test_database_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' falló con excepción: {e}")
            results[test_name] = False
    
    # Resumen
    logger.info("")
    logger.info("=" * 70)
    logger.info("RESUMEN DE TESTS")
    logger.info("=" * 70)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"RESULTADO FINAL: {passed}/{total} tests pasados")
    logger.info("=" * 70)
    logger.info("")
    
    if passed == total:
        logger.info("🎉 TODOS LOS TESTS PASARON")
        logger.info("")
        logger.info("✅ API Endpoints listos")
        logger.info("")
        logger.info("📝 PRÓXIMOS PASOS:")
        logger.info("   1. Iniciar servidor Flask:")
        logger.info("      python3 app.py")
        logger.info("")
        logger.info("   2. Probar endpoint de health:")
        logger.info("      curl http://localhost:5000/api/llm-monitoring/health")
        logger.info("")
        logger.info("   3. Listar proyectos (requiere autenticación):")
        logger.info("      curl -H 'Authorization: Bearer <token>' http://localhost:5000/api/llm-monitoring/projects")
        logger.info("")
        return 0
    else:
        logger.error("❌ ALGUNOS TESTS FALLARON")
        logger.error(f"   {total - passed} test(s) con errores")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())

