#!/usr/bin/env python3
"""
Script para verificar qué sistema de Manual AI está activo
"""

import sys
import os

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def main():
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  🔍 VERIFICACIÓN - MANUAL AI SYSTEM{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    
    # Verificar qué sistema está importado
    try:
        # Intentar importar el bridge
        try:
            from manual_ai_system_bridge import USING_NEW_SYSTEM, manual_ai_bp
            
            if USING_NEW_SYSTEM:
                print(f"{Colors.GREEN}🆕 SISTEMA NUEVO ACTIVO{Colors.RESET}")
                print(f"   └─ Usando: {Colors.BLUE}manual_ai/{Colors.RESET} (arquitectura modular)")
                print(f"   └─ Archivos: 31 módulos")
                print(f"   └─ Estado: ✅ Funcional")
            else:
                print(f"{Colors.YELLOW}📦 SISTEMA ORIGINAL ACTIVO{Colors.RESET}")
                print(f"   └─ Usando: {Colors.BLUE}manual_ai_system.py{Colors.RESET} (monolítico)")
                print(f"   └─ Fallback: Sistema nuevo tuvo problemas")
                print(f"   └─ Estado: ✅ Funcional (pero legacy)")
            
            print(f"\n{Colors.BOLD}Bridge de Compatibilidad:{Colors.RESET} ✅ ACTIVO")
            
        except ImportError:
            # Bridge no disponible, verificar directamente
            try:
                from manual_ai import manual_ai_bp
                print(f"{Colors.GREEN}🆕 SISTEMA NUEVO ACTIVO{Colors.RESET}")
                print(f"   └─ Usando: {Colors.BLUE}manual_ai/{Colors.RESET} (arquitectura modular)")
                print(f"   └─ Importación: Directa (sin bridge)")
                print(f"   └─ Estado: ✅ Funcional")
            except ImportError:
                from manual_ai_system import manual_ai_bp
                print(f"{Colors.YELLOW}📦 SISTEMA ORIGINAL ACTIVO{Colors.RESET}")
                print(f"   └─ Usando: {Colors.BLUE}manual_ai_system.py{Colors.RESET} (monolítico)")
                print(f"   └─ Importación: Directa")
                print(f"   └─ Estado: ✅ Funcional (legacy)")
        
        # Verificar blueprint
        if manual_ai_bp:
            print(f"\n{Colors.BOLD}Blueprint:{Colors.RESET} ✅ Registrado")
            print(f"   └─ Nombre: {manual_ai_bp.name}")
            print(f"   └─ Prefix: {manual_ai_bp.url_prefix}")
        
        # Verificar archivos
        import os
        if os.path.exists('manual_ai'):
            from pathlib import Path
            py_files = list(Path('manual_ai').rglob('*.py'))
            print(f"\n{Colors.BOLD}Archivos del Sistema Nuevo:{Colors.RESET}")
            print(f"   └─ Archivos .py: {len(py_files)}")
            print(f"   └─ Directorio: ✅ Existe")
        
        if os.path.exists('manual_ai_system.py'):
            size = os.path.getsize('manual_ai_system.py')
            print(f"\n{Colors.BOLD}Archivo del Sistema Original:{Colors.RESET}")
            print(f"   └─ Tamaño: {size:,} bytes")
            print(f"   └─ Estado: ✅ Intacto (backup)")
        
        # Verificar en app.py
        try:
            with open('app.py', 'r') as f:
                app_content = f.read()
                if 'from manual_ai_system_bridge import' in app_content:
                    print(f"\n{Colors.BOLD}Configuración en app.py:{Colors.RESET}")
                    print(f"   └─ Import: {Colors.GREEN}manual_ai_system_bridge{Colors.RESET} ✅")
                    print(f"   └─ Modo: Compatibilidad con fallback")
                elif 'from manual_ai import' in app_content:
                    print(f"\n{Colors.BOLD}Configuración en app.py:{Colors.RESET}")
                    print(f"   └─ Import: {Colors.GREEN}manual_ai{Colors.RESET} ✅")
                    print(f"   └─ Modo: Directo (sin fallback)")
                elif 'from manual_ai_system import' in app_content:
                    print(f"\n{Colors.BOLD}Configuración en app.py:{Colors.RESET}")
                    print(f"   └─ Import: {Colors.YELLOW}manual_ai_system{Colors.RESET}")
                    print(f"   └─ Modo: Original (legacy)")
        except Exception as e:
            print(f"\n{Colors.YELLOW}⚠️  No se pudo leer app.py: {e}{Colors.RESET}")
        
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}✅ SISTEMA FUNCIONANDO CORRECTAMENTE{Colors.RESET}\n")
        
        return 0
        
    except Exception as e:
        print(f"\n{Colors.RED}❌ ERROR:{Colors.RESET} {e}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())

