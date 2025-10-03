#!/usr/bin/env python3
"""
Script para dividir manual-ai-system.js en módulos
Mantiene toda la funcionalidad intacta
"""

import os
import re

# Rutas
SOURCE_FILE = 'static/js/manual-ai-system.js'
OUTPUT_DIR = 'static/js/manual-ai'
BACKUP_FILE = 'static/js/manual-ai-system.js.backup'

# Verificar que existe el backup
if not os.path.exists(BACKUP_FILE):
    print(f"❌ Backup no encontrado: {BACKUP_FILE}")
    print("Por favor ejecuta: cp {SOURCE_FILE} {BACKUP_FILE}")
    exit(1)

print("📂 Leyendo archivo original...")
with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print(f"📊 Total de líneas: {len(lines)}")

# Definir los rangos de líneas para cada módulo basado en el análisis del archivo
modules = {
    'manual-ai-progress.js': {
        'start': 2318,  # resetProgressBar
        'end': 2363,    # updateProgressUI
        'description': 'Progress bar utilities'
    },
    'manual-ai-projects.js': {
        'ranges': [
            (518, 638),     # Projects management
            (777, 910),     # Project creation
            (639, 760),     # renderProjectCompetitorsSection
            (866, 878),     # normalizeProjectDomain
            (880, 910),     # validateProjectDomain
            (912, 922),     # filterCountryOptions
        ],
        'description': 'Project CRUD and rendering'
    },
    'manual-ai-keywords.js': {
        'ranges': [
            (1211, 1280),   # Keywords management
            (1014, 1090),   # loadProjectKeywords, renderKeywords
            (4059, 4160),   # Modal keywords functions
            (4176, 4227),   # addKeywordsFromModal
            (4285, 4360),   # removeKeywordFromModal
        ],
        'description': 'Keywords management'
    },
    'manual-ai-analysis.js': {
        'ranges': [
            (1282, 1462),   # analyzeProject
            (2318, 2363),   # Progress bar
            (3387, 3396),   # runAnalysis
        ],
        'description': 'Analysis execution'
    },
    'manual-ai-charts.js': {
        'ranges': [
            (1635, 1780),   # renderVisibilityChart
            (1782, 1907),   # renderPositionsChart
            (3285, 3375),   # renderComparativeVisibilityChart
            (3377, 3467),   # renderComparativePositionChart
        ],
        'description': 'Chart rendering'
    },
    'manual-ai-annotations.js': {
        'ranges': [
            (1909, 2015),   # Event annotations
            (2017, 2195),   # showEventAnnotations
            (4474, 4577),   # Annotation modal
            (2197, 2270),   # Competitor change markers
        ],
        'description': 'Event annotations and markers'
    },
    'manual-ai-competitors.js': {
        'ranges': [
            (924, 988),     # Competitor chips
            (3549, 3804),   # Competitors management
            (2520, 2849),   # Competitors charts
            (3482, 3543),   # Competitors preview
        ],
        'description': 'Competitors management'
    },
    'manual-ai-analytics.js': {
        'ranges': [
            (1464, 1633),   # loadAnalytics, renderAnalytics
            (2851, 2949),   # Global domains ranking
            (2951, 3247),   # AI Overview table
            (3249, 3480),   # Comparative charts
            (2399, 2518),   # Top domains
        ],
        'description': 'Analytics data loading'
    },
    'manual-ai-modals.js': {
        'ranges': [
            (3999, 4472),   # Project modal management
            (3806, 3997),   # Project settings
            (990, 1209),    # Project details
        ],
        'description': 'Modal management'
    },
    'manual-ai-exports.js': {
        'ranges': [
            (4579, 4802),   # Excel/PDF download
        ],
        'description': 'Export functionality'
    },
    'manual-ai-init.js': {
        'ranges': [
            (4805, 4912),   # User dropdown and initialization
        ],
        'description': 'Initialization and user dropdown'
    }
}

def extract_lines(lines, start, end):
    """Extraer líneas del array (0-indexed)"""
    return lines[start-1:end]

def create_module_header(name, description):
    """Crear header para el módulo"""
    return f"""/**
 * Manual AI System - {description}
 * Auto-generado desde manual-ai-system.js
 */

"""

# Nota: Este script es un template
# En producción, necesitarías analizar el archivo más cuidadosamente
# y extraer funciones/métodos específicos en lugar de rangos de líneas

print("✅ Script preparado")
print("⚠️  IMPORTANTE: Debido a la complejidad del archivo original,")
print("   se recomienda una división manual cuidadosa de las funciones.")
print("   Este script sirve como guía de los rangos aproximados.")
print("")
print("📋 Módulos planificados:")
for name, config in modules.items():
    print(f"   - {name}: {config['description']}")

