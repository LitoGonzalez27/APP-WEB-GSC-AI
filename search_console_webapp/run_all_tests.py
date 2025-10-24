#!/usr/bin/env python3
"""
Script para ejecutar todos los tests del sistema LLM Monitoring

Usage:
    python run_all_tests.py               # Todos los tests
    python run_all_tests.py --unit        # Solo tests unitarios
    python run_all_tests.py --e2e         # Solo tests E2E
    python run_all_tests.py --performance # Solo tests de performance
    python run_all_tests.py --fast        # Excluir tests lentos
"""

import sys
import os
import subprocess
import argparse
from datetime import datetime


def print_header(title):
    """Imprime un header bonito"""
    width = 80
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width + "\n")


def run_pytest(args_list):
    """Ejecuta pytest con argumentos específicos"""
    cmd = ["python", "-m", "pytest"] + args_list
    
    print(f"🚀 Ejecutando: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, capture_output=False)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description='Ejecutar tests del sistema LLM Monitoring'
    )
    
    parser.add_argument(
        '--unit',
        action='store_true',
        help='Solo tests unitarios'
    )
    
    parser.add_argument(
        '--e2e',
        action='store_true',
        help='Solo tests End-to-End'
    )
    
    parser.add_argument(
        '--performance',
        action='store_true',
        help='Solo tests de performance'
    )
    
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Excluir tests lentos'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Output verbose'
    )
    
    parser.add_argument(
        '--failfast',
        '-x',
        action='store_true',
        help='Parar en el primer error'
    )
    
    args = parser.parse_args()
    
    # Configurar argumentos de pytest
    pytest_args = []
    
    if args.verbose:
        pytest_args.append('-vv')
    
    if args.failfast:
        pytest_args.append('-x')
    
    # Cambiar al directorio del proyecto
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print_header(f"🧪 LLM MONITORING SYSTEM - TEST SUITE")
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Directorio: {script_dir}\n")
    
    exit_code = 0
    
    # Determinar qué tests ejecutar
    if args.unit:
        print_header("🔬 TESTS UNITARIOS")
        exit_code = run_pytest([
            'tests/test_llm_providers.py',
            'tests/test_llm_monitoring_service.py'
        ] + pytest_args)
    
    elif args.e2e:
        print_header("🌐 TESTS END-TO-END")
        exit_code = run_pytest([
            'tests/test_llm_monitoring_e2e.py'
        ] + pytest_args)
    
    elif args.performance:
        print_header("⚡ TESTS DE PERFORMANCE")
        exit_code = run_pytest([
            'tests/test_llm_monitoring_performance.py',
            '-s'  # No capturar output para ver prints
        ] + pytest_args)
    
    else:
        # Ejecutar todos los tests en orden
        test_suites = [
            ("🔬 TESTS UNITARIOS - Proveedores", "tests/test_llm_providers.py"),
            ("🔬 TESTS UNITARIOS - Servicio", "tests/test_llm_monitoring_service.py"),
            ("🌐 TESTS END-TO-END", "tests/test_llm_monitoring_e2e.py"),
            ("⚡ TESTS DE PERFORMANCE", "tests/test_llm_monitoring_performance.py"),
        ]
        
        for title, test_file in test_suites:
            print_header(title)
            
            result = run_pytest([test_file] + pytest_args)
            
            if result != 0:
                exit_code = result
                print(f"\n❌ Falló: {test_file}")
                
                if args.failfast:
                    print("\n🛑 Parando por --failfast")
                    break
            else:
                print(f"\n✅ Pasó: {test_file}")
    
    # Resumen final
    print_header("📊 RESUMEN FINAL")
    
    if exit_code == 0:
        print("✅ TODOS LOS TESTS PASARON")
        print("\n🎉 Sistema LLM Monitoring validado correctamente")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        print(f"\n🔍 Exit code: {exit_code}")
        print("💡 Revisa los logs arriba para más detalles")
    
    print("\n" + "=" * 80 + "\n")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())

