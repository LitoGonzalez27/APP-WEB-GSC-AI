#!/usr/bin/env python3
"""
Script para verificar el estado de la refactorización del sistema Manual AI
"""

import os
import sys
from pathlib import Path

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def check_file_exists(filepath):
    """Verificar si un archivo existe"""
    return Path(filepath).exists()

def print_status(name, exists, required=True):
    """Imprimir estado de un archivo"""
    if exists:
        print(f"  {Colors.GREEN}✓{Colors.RESET} {name}")
        return 1
    else:
        marker = "✗" if required else "○"
        color = Colors.RED if required else Colors.YELLOW
        print(f"  {color}{marker}{Colors.RESET} {name}")
        return 0

def main():
    base_path = Path(__file__).parent
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  📊 ESTADO DE REFACTORIZACIÓN - MANUAL AI SYSTEM{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    
    total_files = 0
    completed_files = 0
    
    # 1. ESTRUCTURA BASE
    print(f"{Colors.BLUE}📁 Estructura Base{Colors.RESET}")
    files = [
        ('__init__.py', True),
        ('config.py', True),
        ('REFACTORING_GUIDE.md', True),
    ]
    for file, required in files:
        total_files += 1
        completed_files += print_status(file, check_file_exists(base_path / file), required)
    
    # 2. UTILIDADES
    print(f"\n{Colors.BLUE}🔧 Utilidades (utils/){Colors.RESET}")
    utils_path = base_path / 'utils'
    files = [
        ('__init__.py', True),
        ('decorators.py', True),
        ('validators.py', True),
        ('helpers.py', True),
        ('country_utils.py', True),
    ]
    for file, required in files:
        total_files += 1
        completed_files += print_status(file, check_file_exists(utils_path / file), required)
    
    # 3. MODELOS/REPOSITORIOS
    print(f"\n{Colors.BLUE}💾 Modelos/Repositorios (models/){Colors.RESET}")
    models_path = base_path / 'models'
    files = [
        ('__init__.py', True),
        ('project_repository.py', True),
        ('keyword_repository.py', True),
        ('result_repository.py', True),
        ('event_repository.py', True),
    ]
    for file, required in files:
        total_files += 1
        completed_files += print_status(file, check_file_exists(models_path / file), required)
    
    # 4. SERVICIOS
    print(f"\n{Colors.BLUE}⚙️  Servicios (services/){Colors.RESET}")
    services_path = base_path / 'services'
    files = [
        ('__init__.py', True),
        ('project_service.py', True),
        ('analysis_service.py', True),
        ('statistics_service.py', True),
        ('competitor_service.py', True),
        ('export_service.py', True),
        ('cron_service.py', True),
    ]
    for file, required in files:
        total_files += 1
        completed_files += print_status(file, check_file_exists(services_path / file), required)
    
    # 5. RUTAS
    print(f"\n{Colors.BLUE}🌐 Rutas/Endpoints (routes/){Colors.RESET}")
    routes_path = base_path / 'routes'
    files = [
        ('__init__.py', True),
        ('health.py', True),
        ('projects.py', True),
        ('keywords.py', True),
        ('analysis.py', True),
        ('results.py', True),
        ('competitors.py', True),
        ('exports.py', True),
        ('annotations.py', False),  # Opcional
    ]
    for file, required in files:
        total_files += 1
        completed_files += print_status(file, check_file_exists(routes_path / file), required)
    
    # 6. TESTS
    print(f"\n{Colors.BLUE}🧪 Tests (tests/){Colors.RESET}")
    tests_path = base_path / 'tests'
    files = [
        ('__init__.py', False),
        ('test_project_service.py', False),
        ('test_analysis_service.py', False),
        ('test_repositories.py', False),
    ]
    for file, required in files:
        total_files += 1
        completed_files += print_status(file, check_file_exists(tests_path / file), required)
    
    # RESUMEN
    percentage = (completed_files / total_files * 100) if total_files > 0 else 0
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  📈 PROGRESO TOTAL{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"\n  Archivos completados: {completed_files}/{total_files}")
    print(f"  Progreso: {Colors.BOLD}{percentage:.1f}%{Colors.RESET}")
    
    # Barra de progreso
    bar_length = 40
    filled = int(bar_length * completed_files / total_files)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f"  [{bar}]")
    
    # Estado general
    if percentage == 100:
        status = f"{Colors.GREEN}✅ COMPLETO{Colors.RESET}"
    elif percentage >= 70:
        status = f"{Colors.YELLOW}🚧 CASI LISTO{Colors.RESET}"
    elif percentage >= 40:
        status = f"{Colors.YELLOW}🚧 EN PROGRESO{Colors.RESET}"
    else:
        status = f"{Colors.RED}🔴 INICIO{Colors.RESET}"
    
    print(f"\n  Estado: {status}\n")
    
    # Siguiente paso
    if percentage < 100:
        print(f"{Colors.BOLD}📝 PRÓXIMOS PASOS:{Colors.RESET}")
        
        # Determinar qué falta
        if completed_files < 5:
            print(f"  1. Completar estructura base y utilidades")
        elif completed_files < 10:
            print(f"  1. Completar modelos/repositorios")
        elif completed_files < 17:
            print(f"  1. Implementar servicios de negocio")
        else:
            print(f"  1. Implementar rutas/endpoints")
            print(f"  2. Crear tests de integración")
            print(f"  3. Actualizar imports en app.py")
        
        print(f"\n  📖 Ver guía completa en: REFACTORING_GUIDE.md\n")

if __name__ == '__main__':
    main()

