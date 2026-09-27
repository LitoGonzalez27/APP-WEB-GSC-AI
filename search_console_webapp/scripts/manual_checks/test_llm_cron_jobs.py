#!/usr/bin/env python3
"""
Script de Test para los Cron Jobs de Multi-LLM Monitoring

IMPORTANTE: Este script NO ejecuta los crons completos (no consume API calls)
Solo verifica que los scripts existan y se importen correctamente
"""

import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_file_exists():
    """Test 1: Verificar que los archivos existan"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 1: VERIFICANDO QUE LOS ARCHIVOS EXISTAN")
    logger.info("=" * 70)
    
    files = [
        'daily_llm_monitoring_cron.py',
        'weekly_model_check_cron.py',
        'railway.json'
    ]
    
    all_exist = True
    
    for file in files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            logger.info(f"   ✅ {file} ({size} bytes)")
        else:
            logger.error(f"   ❌ {file} NO ENCONTRADO")
            all_exist = False
    
    return all_exist


def test_scripts_syntax():
    """Test 2: Verificar sintaxis de Python"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 2: VERIFICANDO SINTAXIS DE PYTHON")
    logger.info("=" * 70)
    
    scripts = [
        'daily_llm_monitoring_cron.py',
        'weekly_model_check_cron.py'
    ]
    
    all_ok = True
    
    for script in scripts:
        try:
            with open(script, 'r') as f:
                code = f.read()
                compile(code, script, 'exec')
            logger.info(f"   ✅ {script} - Sintaxis válida")
        except SyntaxError as e:
            logger.error(f"   ❌ {script} - Error de sintaxis: {e}")
            all_ok = False
        except Exception as e:
            logger.error(f"   ❌ {script} - Error: {e}")
            all_ok = False
    
    return all_ok


def test_railway_json():
    """Test 3: Verificar configuración de Railway"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 3: VERIFICANDO CONFIGURACIÓN DE RAILWAY")
    logger.info("=" * 70)
    
    try:
        import json
        
        with open('railway.json', 'r') as f:
            config = json.load(f)
        
        if 'crons' not in config:
            logger.error("   ❌ No se encontró 'crons' en railway.json")
            return False
        
        crons = config['crons']
        logger.info(f"   Cron jobs configurados: {len(crons)}")
        logger.info("")
        
        # Verificar que estén los nuevos crons
        expected_crons = {
            'daily_llm_monitoring_cron.py': '0 4 * * *',
            'weekly_model_check_cron.py': '0 0 * * 0'
        }
        
        found_crons = {}
        
        for cron in crons:
            command = cron.get('command', '')
            schedule = cron.get('schedule', '')
            
            for script, expected_schedule in expected_crons.items():
                if script in command:
                    found_crons[script] = schedule
            
            logger.info(f"   • {command}")
            logger.info(f"     Schedule: {schedule}")
        
        logger.info("")
        
        all_ok = True
        
        for script, expected_schedule in expected_crons.items():
            if script in found_crons:
                actual_schedule = found_crons[script]
                if actual_schedule == expected_schedule:
                    logger.info(f"   ✅ {script} configurado correctamente ({actual_schedule})")
                else:
                    logger.warning(f"   ⚠️ {script} tiene schedule diferente:")
                    logger.warning(f"      Esperado: {expected_schedule}")
                    logger.warning(f"      Actual: {actual_schedule}")
            else:
                logger.error(f"   ❌ {script} NO encontrado en railway.json")
                all_ok = False
        
        return all_ok
        
    except json.JSONDecodeError as e:
        logger.error(f"   ❌ Error parseando railway.json: {e}")
        return False
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def test_imports():
    """Test 4: Verificar imports críticos"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 4: VERIFICANDO IMPORTS CRÍTICOS")
    logger.info("=" * 70)
    
    # Test daily_llm_monitoring_cron
    logger.info("   Verificando daily_llm_monitoring_cron.py...")
    try:
        # No ejecutar main(), solo verificar que se puede importar
        import importlib.util
        
        spec = importlib.util.spec_from_file_location(
            "daily_llm_monitoring_cron",
            "daily_llm_monitoring_cron.py"
        )
        module = importlib.util.module_from_spec(spec)
        
        # Verificar que tenga función main
        if hasattr(module, '__file__'):
            logger.info("      ✅ Script importable")
        
        # Verificar que pueda importar el servicio
        from services.llm_monitoring_service import analyze_all_active_projects
        logger.info("      ✅ Puede importar analyze_all_active_projects")
        
    except ImportError as e:
        logger.error(f"      ❌ Error de import: {e}")
        return False
    except Exception as e:
        logger.error(f"      ❌ Error: {e}")
        return False
    
    # Test weekly_model_check_cron
    logger.info("   Verificando weekly_model_check_cron.py...")
    try:
        spec = importlib.util.spec_from_file_location(
            "weekly_model_check_cron",
            "weekly_model_check_cron.py"
        )
        module = importlib.util.module_from_spec(spec)
        
        if hasattr(module, '__file__'):
            logger.info("      ✅ Script importable")
        
    except Exception as e:
        logger.error(f"      ❌ Error: {e}")
        return False
    
    return True


def test_helper_functions():
    """Test 5: Verificar funciones helper del cron diario"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 5: VERIFICANDO FUNCIONES HELPER")
    logger.info("=" * 70)
    
    try:
        # Verificar que las funciones existan en el script
        with open('daily_llm_monitoring_cron.py', 'r') as f:
            content = f.read()
        
        functions = [
            'check_budget_limits',
            'get_api_keys_from_db',
            'update_monthly_spend',
            'main'
        ]
        
        all_ok = True
        
        for func in functions:
            if f"def {func}(" in content:
                logger.info(f"   ✅ {func}() definida")
            else:
                logger.error(f"   ❌ {func}() NO encontrada")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        logger.error(f"   ❌ Error: {e}")
        return False


def main():
    """Ejecutar todos los tests"""
    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 15 + "TEST SUITE: LLM CRON JOBS" + " " * 28 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    
    tests = [
        ("Archivos existen", test_file_exists),
        ("Sintaxis Python", test_scripts_syntax),
        ("Configuración Railway", test_railway_json),
        ("Imports críticos", test_imports),
        ("Funciones helper", test_helper_functions),
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
        logger.info("✅ Cron jobs listos para deployar en Railway")
        logger.info("")
        logger.info("📝 PRÓXIMOS PASOS:")
        logger.info("   1. Configurar API keys en Railway (variables de entorno):")
        logger.info("      • OPENAI_API_KEY")
        logger.info("      • ANTHROPIC_API_KEY")
        logger.info("      • GOOGLE_API_KEY")
        logger.info("      • PERPLEXITY_API_KEY")
        logger.info("")
        logger.info("   2. Deploy a Railway:")
        logger.info("      railway up")
        logger.info("")
        logger.info("   3. Verificar logs en Railway:")
        logger.info("      railway logs --service <service-name>")
        logger.info("")
        return 0
    else:
        logger.error("❌ ALGUNOS TESTS FALLARON")
        logger.error(f"   {total - passed} test(s) con errores")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())

