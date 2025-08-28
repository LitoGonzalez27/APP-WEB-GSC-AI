#!/usr/bin/env python3
"""
Run Full Staging Tests - Test completo de staging y Stripe
==========================================================

Script principal que ejecuta todos los tests automatizados para verificar
que el sistema está listo para producción.
"""

import os
import sys
import subprocess
import json
from datetime import datetime

def print_header():
    """Imprimir header del script"""
    print("="*80)
    print("🚀 FULL STAGING TESTS - CLICANDSEO ADMIN PANEL")
    print("="*80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Objetivo: Verificar sistema completo antes de producción")
    print("="*80)

def check_requirements():
    """Verificar que tenemos todo lo necesario"""
    print("\n🔍 VERIFICANDO REQUISITOS...")
    
    requirements = {
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'STRIPE_SECRET_KEY': os.getenv('STRIPE_SECRET_KEY'),
        'Python psycopg2': None,
        'Python stripe': None,
        'Python requests': None
    }
    
    # Verificar módulos Python
    try:
        import psycopg2
        requirements['Python psycopg2'] = "✅ Disponible"
    except ImportError:
        requirements['Python psycopg2'] = "❌ No instalado"
    
    try:
        import stripe
        requirements['Python stripe'] = "✅ Disponible"
    except ImportError:
        requirements['Python stripe'] = "❌ No instalado"
    
    try:
        import requests
        requirements['Python requests'] = "✅ Disponible"
    except ImportError:
        requirements['Python requests'] = "❌ No instalado"
    
    # Mostrar resultados
    missing = []
    for req, status in requirements.items():
        if req.startswith('Python'):
            print(f"  📦 {req}: {status}")
            if "❌" in str(status):
                missing.append(req)
        else:
            is_present = bool(status)
            status_text = "✅ Configurado" if is_present else "❌ Faltante"
            print(f"  🔑 {req}: {status_text}")
            if not is_present:
                missing.append(req)
    
    if missing:
        print(f"\n⚠️ FALTAN REQUISITOS: {', '.join(missing)}")
        print("\n💡 INSTRUCCIONES:")
        
        if 'DATABASE_URL' in missing:
            print("   export DATABASE_URL='postgresql://postgres:...'")
        
        if 'STRIPE_SECRET_KEY' in missing:
            print("   export STRIPE_SECRET_KEY='sk_test_...'")
        
        python_missing = [req for req in missing if req.startswith('Python')]
        if python_missing:
            print("   pip install psycopg2 stripe requests")
        
        return False
    
    print("✅ Todos los requisitos están presentes")
    return True

def run_test_script(script_name, description):
    """Ejecutar un script de test y retornar resultado"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print('='*60)
    
    try:
        # Ejecutar script
        result = subprocess.run([
            sys.executable, script_name
        ], capture_output=True, text=True, timeout=120)
        
        # Mostrar output
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Determinar si pasó
        success = result.returncode == 0
        return success, result.stdout + result.stderr
        
    except subprocess.TimeoutExpired:
        print("❌ Test timeout (120s)")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Error ejecutando test: {e}")
        return False, str(e)

def analyze_results(results):
    """Analizar resultados y dar recomendaciones"""
    print("\n" + "="*80)
    print("📊 ANÁLISIS DE RESULTADOS")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for success, _ in results.values() if success)
    
    print(f"📈 Tests ejecutados: {total_tests}")
    print(f"✅ Tests exitosos: {passed_tests}")
    print(f"❌ Tests fallidos: {total_tests - passed_tests}")
    print(f"📊 Tasa de éxito: {(passed_tests/total_tests)*100:.1f}%")
    
    # Análisis por categoría
    print(f"\n📋 RESULTADOS POR CATEGORÍA:")
    for test_name, (success, output) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")
        
        # Extraer información adicional de los outputs
        if "TODOS LOS TESTS PASARON" in output:
            print("    🎊 Todos los subtests pasaron")
        elif "HAY TESTS FALLIDOS" in output:
            print("    ⚠️ Algunos subtests fallaron")
    
    # Recomendaciones
    print(f"\n🎯 RECOMENDACIONES:")
    
    if passed_tests == total_tests:
        print("🎊 EXCELENTE: Todos los tests pasaron")
        print("✅ El sistema está listo para:")
        print("   - Despliegue a producción")
        print("   - Testing manual del panel admin")
        print("   - Activación de Stripe en modo live")
        
    elif passed_tests >= total_tests * 0.8:  # 80% o más
        print("🟡 BUENO: La mayoría de tests pasaron")
        print("⚠️ Revisar tests fallidos antes de producción")
        print("✅ Puedes continuar con testing manual")
        
    else:
        print("🔴 CRÍTICO: Muchos tests fallaron")
        print("❌ NO desplegar a producción")
        print("🛠️ Corregir errores críticos primero")
    
    # Próximos pasos específicos
    print(f"\n📋 PRÓXIMOS PASOS:")
    
    if 'Admin Panel Tests' in results and results['Admin Panel Tests'][0]:
        print("1. ✅ Panel admin está funcionando")
        print("   - Continuar con checklist manual")
        print("   - Verificar barras progresivas visualmente")
    else:
        print("1. ❌ Corregir panel admin")
        print("   - Revisar logs de Railway")
        print("   - Verificar base de datos")
    
    if 'Stripe Integration Tests' in results and results['Stripe Integration Tests'][0]:
        print("2. ✅ Stripe está configurado")
        print("   - Probar webhooks con eventos de test")
        print("   - Verificar sincronización con base de datos")
    else:
        print("2. ❌ Configurar Stripe")
        print("   - Verificar API keys")
        print("   - Configurar productos y precios")
        print("   - Configurar webhooks")
    
    print("3. 📋 Ejecutar checklist manual completo")
    print("4. 🚀 Si todo está bien → preparar producción")
    
    return passed_tests == total_tests

def main():
    """Función principal"""
    print_header()
    
    # Verificar requisitos
    if not check_requirements():
        print("\n❌ No se pueden ejecutar los tests sin los requisitos")
        return False
    
    # Tests a ejecutar
    tests_to_run = [
        ('test_admin_panel_staging.py', 'Admin Panel Tests'),
        ('test_stripe_integration.py', 'Stripe Integration Tests')
    ]
    
    results = {}
    
    # Ejecutar tests
    for script, description in tests_to_run:
        if not os.path.exists(script):
            print(f"⚠️ Script {script} no encontrado, saltando...")
            results[description] = (False, f"Script {script} no encontrado")
            continue
        
        success, output = run_test_script(script, description)
        results[description] = (success, output)
    
    # Analizar resultados
    overall_success = analyze_results(results)
    
    # Resumen final
    print(f"\n{'='*80}")
    if overall_success:
        print("🎊 STAGING TESTS COMPLETED SUCCESSFULLY")
        print("🚀 Sistema listo para el siguiente paso")
    else:
        print("⚠️ STAGING TESTS COMPLETED WITH ISSUES")
        print("🛠️ Revisar y corregir antes de continuar")
    
    print("📋 Continuar con checklist_manual_testing.md")
    print("="*80)
    
    return overall_success

if __name__ == "__main__":
    success = main()
    
    # Exit code para scripts automatizados
    sys.exit(0 if success else 1)
