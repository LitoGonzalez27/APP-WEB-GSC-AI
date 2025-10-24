#!/usr/bin/env python3
"""
Script de Test para Frontend de LLM Monitoring

Verifica que todos los archivos del frontend estén correctamente creados
"""

import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_files_exist():
    """Test 1: Verificar que los archivos existan"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 1: VERIFICANDO QUE LOS ARCHIVOS EXISTAN")
    logger.info("=" * 70)
    
    files = {
        'templates/llm_monitoring.html': 'Template HTML',
        'static/js/llm_monitoring.js': 'JavaScript',
        'static/llm-monitoring.css': 'CSS',
    }
    
    all_exist = True
    
    for file_path, description in files.items():
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            logger.info(f"   ✅ {description:20} {file_path} ({size:,} bytes)")
        else:
            logger.error(f"   ❌ {description:20} {file_path} NO ENCONTRADO")
            all_exist = False
    
    return all_exist


def test_html_structure():
    """Test 2: Verificar estructura del HTML"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 2: VERIFICANDO ESTRUCTURA DEL HTML")
    logger.info("=" * 70)
    
    try:
        with open('templates/llm_monitoring.html', 'r') as f:
            content = f.read()
        
        checks = [
            ('<!DOCTYPE html>', 'Declaración DOCTYPE'),
            ('LLM Visibility Monitor', 'Título'),
            ('Chart.js', 'Librería Chart.js'),
            ('Grid.js', 'Librería Grid.js'),
            ('llm-monitoring.css', 'CSS custom'),
            ('llm_monitoring.js', 'JavaScript custom'),
            ('projectsSection', 'Sección de proyectos'),
            ('metricsSection', 'Sección de métricas'),
            ('projectModal', 'Modal de proyecto'),
            ('analysisModal', 'Modal de análisis'),
        ]
        
        all_ok = True
        
        for check_str, description in checks:
            if check_str in content:
                logger.info(f"   ✅ {description}")
            else:
                logger.error(f"   ❌ {description} NO encontrado")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error leyendo HTML: {e}")
        return False


def test_javascript_functions():
    """Test 3: Verificar funciones JavaScript"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 3: VERIFICANDO FUNCIONES JAVASCRIPT")
    logger.info("=" * 70)
    
    try:
        with open('static/js/llm_monitoring.js', 'r') as f:
            content = f.read()
        
        functions = [
            'class LLMMonitoring',
            'loadProjects()',
            'createProject()',
            'loadMetrics(',
            'renderMentionRateChart(',
            'renderShareOfVoiceChart(',
            'analyzeProject()',
            'loadBudget()',
            'showProjectModal(',
            'saveProject()'
        ]
        
        all_ok = True
        
        for func in functions:
            if func in content:
                logger.info(f"   ✅ {func}")
            else:
                logger.error(f"   ❌ {func} NO encontrada")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error leyendo JavaScript: {e}")
        return False


def test_css_styles():
    """Test 4: Verificar estilos CSS"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 4: VERIFICANDO ESTILOS CSS")
    logger.info("=" * 70)
    
    try:
        with open('static/llm-monitoring.css', 'r') as f:
            content = f.read()
        
        styles = [
            '.project-card',
            '.kpi-card',
            '.chart-card',
            '.modal',
            '.btn-primary',
            '.form-group',
            '.progress-bar',
            '@media (max-width: 768px)',  # Responsive
        ]
        
        all_ok = True
        
        for style in styles:
            if style in content:
                logger.info(f"   ✅ {style}")
            else:
                logger.error(f"   ❌ {style} NO encontrado")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error leyendo CSS: {e}")
        return False


def test_route_in_app():
    """Test 5: Verificar ruta en app.py"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 5: VERIFICANDO RUTA EN APP.PY")
    logger.info("=" * 70)
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        checks = [
            ("@app.route('/llm-monitoring')", 'Decorador de ruta'),
            ('@login_required', 'Decorador de autenticación'),
            ('def llm_monitoring_page():', 'Función de ruta'),
            ("render_template('llm_monitoring.html'", 'Render template'),
        ]
        
        all_ok = True
        
        for check_str, description in checks:
            count = content.count(check_str)
            if count > 0:
                logger.info(f"   ✅ {description}")
            else:
                logger.error(f"   ❌ {description} NO encontrado")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error leyendo app.py: {e}")
        return False


def test_api_endpoints_integration():
    """Test 6: Verificar integración con API endpoints"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 6: VERIFICANDO INTEGRACIÓN CON API")
    logger.info("=" * 70)
    
    try:
        with open('static/js/llm_monitoring.js', 'r') as f:
            content = f.read()
        
        endpoints = [
            '/api/llm-monitoring/projects',
            '/api/llm-monitoring/projects/${projectId}',
            '/api/llm-monitoring/projects/${projectId}/metrics',
            '/api/llm-monitoring/projects/${projectId}/comparison',
            '/api/llm-monitoring/projects/${projectId}/analyze',
            '/api/llm-monitoring/budget',
        ]
        
        all_ok = True
        
        for endpoint in endpoints:
            # Normalizar la búsqueda para template strings
            search_str = endpoint.replace('${projectId}', '${')
            if search_str in content:
                logger.info(f"   ✅ {endpoint}")
            else:
                logger.warning(f"   ⚠️ {endpoint} podría no estar usado")
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_responsive_design():
    """Test 7: Verificar diseño responsive"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 7: VERIFICANDO DISEÑO RESPONSIVE")
    logger.info("=" * 70)
    
    try:
        with open('static/llm-monitoring.css', 'r') as f:
            content = f.read()
        
        # Verificar media queries
        media_queries = content.count('@media')
        
        if media_queries > 0:
            logger.info(f"   ✅ {media_queries} media query(ies) encontrada(s)")
            
            # Verificar breakpoints comunes
            if 'max-width: 768px' in content:
                logger.info(f"   ✅ Breakpoint mobile (768px)")
            
            return True
        else:
            logger.warning("   ⚠️ No se encontraron media queries")
            return False
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_chart_integration():
    """Test 8: Verificar integración de Chart.js"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 8: VERIFICANDO INTEGRACIÓN DE CHART.JS")
    logger.info("=" * 70)
    
    try:
        with open('templates/llm_monitoring.html', 'r') as f:
            html_content = f.read()
        
        with open('static/js/llm_monitoring.js', 'r') as f:
            js_content = f.read()
        
        checks = [
            (html_content, 'chart.js', 'Librería Chart.js en HTML'),
            (html_content, 'canvas id="chartMentionRate"', 'Canvas para Mention Rate'),
            (html_content, 'canvas id="chartShareOfVoice"', 'Canvas para Share of Voice'),
            (js_content, 'new Chart(', 'Uso de Chart.js'),
            (js_content, "'bar'", 'Gráfico de barras'),
            (js_content, "'pie'", 'Gráfico de pie'),
        ]
        
        all_ok = True
        
        for content, check_str, description in checks:
            if check_str in content:
                logger.info(f"   ✅ {description}")
            else:
                logger.error(f"   ❌ {description} NO encontrado")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def main():
    """Ejecutar todos los tests"""
    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 12 + "TEST SUITE: LLM MONITORING FRONTEND" + " " * 21 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    
    tests = [
        ("Archivos existen", test_files_exist),
        ("Estructura HTML", test_html_structure),
        ("Funciones JavaScript", test_javascript_functions),
        ("Estilos CSS", test_css_styles),
        ("Ruta en app.py", test_route_in_app),
        ("Integración API", test_api_endpoints_integration),
        ("Diseño Responsive", test_responsive_design),
        ("Chart.js Integration", test_chart_integration),
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
        logger.info("✅ Frontend de LLM Monitoring listo")
        logger.info("")
        logger.info("📝 PRÓXIMOS PASOS:")
        logger.info("   1. Iniciar servidor Flask:")
        logger.info("      python3 app.py")
        logger.info("")
        logger.info("   2. Abrir en navegador:")
        logger.info("      http://localhost:5000/llm-monitoring")
        logger.info("")
        logger.info("   3. Verificar:")
        logger.info("      - Sidebar con link 'LLM Visibility'")
        logger.info("      - Formulario de creación de proyectos")
        logger.info("      - Gráficos con Chart.js")
        logger.info("")
        return 0
    else:
        logger.error("❌ ALGUNOS TESTS FALLARON")
        logger.error(f"   {total - passed} test(s) con errores")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())

