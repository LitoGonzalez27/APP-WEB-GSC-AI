#!/usr/bin/env python3
"""
Script para verificar que TODOS los métodos necesarios estén importados
en el sistema modular de AI Mode
"""

import re
import sys

def extract_methods_used(file_path):
    """Extraer todos los métodos llamados con this.metodo()"""
    methods = set()
    with open(file_path, 'r') as f:
        content = f.read()
        # Buscar this.metodoNombre()
        pattern = r'this\.([a-zA-Z_][a-zA-Z0-9_]*)\('
        matches = re.findall(pattern, content)
        methods.update(matches)
    return methods

def extract_exported_methods(file_path):
    """Extraer todos los métodos exportados de un archivo"""
    methods = set()
    with open(file_path, 'r') as f:
        content = f.read()
        # Buscar export function metodoNombre
        pattern = r'export\s+(?:async\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, content)
        methods.update(matches)
    return methods

def extract_assigned_methods(file_path):
    """Extraer métodos asignados con Object.assign"""
    methods = set()
    with open(file_path, 'r') as f:
        content = f.read()
        # Encontrar el bloque Object.assign
        assign_match = re.search(r'Object\.assign\(.*?\{(.*?)\}\);', content, re.DOTALL)
        if assign_match:
            assign_block = assign_match.group(1)
            # Buscar nombres de métodos (palabra seguida de coma o comentario)
            pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[,\n]'
            matches = re.findall(pattern, assign_block)
            methods.update(matches)
    return methods

print("🔍 Analizando métodos de AI Mode...")
print("=" * 70)

# Analizar archivos JS
js_files = [
    'static/js/ai-mode-projects/ai-mode-projects.js',
    'static/js/ai-mode-projects/ai-mode-keywords.js',
    'static/js/ai-mode-projects/ai-mode-analysis.js',
    'static/js/ai-mode-projects/ai-mode-core.js'
]

all_used_methods = set()
for js_file in js_files:
    try:
        methods = extract_methods_used(js_file)
        all_used_methods.update(methods)
        print(f"✅ {js_file}: {len(methods)} métodos usados")
    except Exception as e:
        print(f"❌ Error leyendo {js_file}: {e}")

print(f"\n📊 Total de métodos únicos usados: {len(all_used_methods)}")

# Analizar métodos exportados
print("\n🔍 Verificando métodos exportados...")
export_files = {
    'projects': 'static/js/ai-mode-projects/ai-mode-projects.js',
    'keywords': 'static/js/ai-mode-projects/ai-mode-keywords.js',
    'analysis': 'static/js/ai-mode-projects/ai-mode-analysis.js',
    'charts': 'static/js/ai-mode-projects/ai-mode-charts.js',
    'modals': 'static/js/ai-mode-projects/ai-mode-modals.js',
    'competitors': 'static/js/ai-mode-projects/ai-mode-competitors.js',
    'clusters': 'static/js/ai-mode-projects/ai-mode-clusters.js',
    'analytics': 'static/js/ai-mode-projects/ai-mode-analytics.js',
    'exports': 'static/js/ai-mode-projects/ai-mode-exports.js',
    'utils': 'static/js/ai-mode-projects/ai-mode-utils.js'
}

all_exported = set()
for module_name, file_path in export_files.items():
    try:
        methods = extract_exported_methods(file_path)
        all_exported.update(methods)
        print(f"✅ {module_name}: {len(methods)} métodos exportados")
    except Exception as e:
        print(f"❌ Error leyendo {file_path}: {e}")

print(f"\n📊 Total de métodos exportados: {len(all_exported)}")

# Analizar métodos en sistema modular
print("\n🔍 Verificando sistema modular...")
try:
    assigned_methods = extract_assigned_methods('static/js/ai-mode-system-modular.js')
    print(f"✅ Métodos asignados en Object.assign: {len(assigned_methods)}")
except Exception as e:
    print(f"❌ Error leyendo sistema modular: {e}")
    assigned_methods = set()

# Comparar
print("\n" + "=" * 70)
print("📋 ANÁLISIS DE COBERTURA")
print("=" * 70)

missing_in_modular = all_used_methods - assigned_methods
covered_methods = all_used_methods & assigned_methods

print(f"\n✅ Métodos cubiertos: {len(covered_methods)}/{len(all_used_methods)}")
print(f"❌ Métodos faltantes: {len(missing_in_modular)}")

if missing_in_modular:
    print("\n⚠️  MÉTODOS FALTANTES EN SISTEMA MODULAR:")
    for method in sorted(missing_in_modular):
        # Verificar si está exportado en algún módulo
        if method in all_exported:
            print(f"   ❌ {method} - EXPORTADO pero NO asignado")
        else:
            print(f"   ⚠️  {method} - NO exportado (probablemente interno de core)")
else:
    print("\n🎉 ¡TODOS LOS MÉTODOS NECESARIOS ESTÁN IMPORTADOS!")

print("\n" + "=" * 70)
sys.exit(0 if not missing_in_modular else 1)

