#!/bin/bash
# Script de verificación para Manual AI JavaScript

echo "🔍 Verificando estado de Manual AI JavaScript..."
echo ""

# Verificar backup
if [ -f "static/js/manual-ai-system.js.backup" ]; then
    echo "✅ Backup encontrado: manual-ai-system.js.backup"
    backup_size=$(wc -l < static/js/manual-ai-system.js.backup)
    echo "   Líneas: $backup_size"
else
    echo "❌ Backup NO encontrado"
fi

echo ""

# Verificar archivo original
if [ -f "static/js/manual-ai-system.js" ]; then
    echo "✅ Archivo original intacto: manual-ai-system.js"
    original_size=$(wc -l < static/js/manual-ai-system.js)
    echo "   Líneas: $original_size"
else
    echo "❌ Archivo original NO encontrado"
fi

echo ""

# Verificar directorio de módulos
if [ -d "static/js/manual-ai" ]; then
    echo "✅ Directorio de módulos creado: static/js/manual-ai/"
    module_count=$(ls -1 static/js/manual-ai/*.js 2>/dev/null | wc -l)
    echo "   Módulos JavaScript: $module_count"
    echo "   Archivos en directorio:"
    ls -1 static/js/manual-ai/ | sed 's/^/      /'
else
    echo "❌ Directorio de módulos NO encontrado"
fi

echo ""

# Verificar módulos específicos
echo "📦 Estado de módulos:"
modules=(
    "manual-ai-utils.js"
    "manual-ai-core.js"
    "manual-ai-projects.js"
    "manual-ai-keywords.js"
    "manual-ai-analysis.js"
    "manual-ai-charts.js"
    "manual-ai-annotations.js"
    "manual-ai-competitors.js"
    "manual-ai-analytics.js"
    "manual-ai-modals.js"
    "manual-ai-exports.js"
    "manual-ai-init.js"
)

completed=0
for module in "${modules[@]}"; do
    if [ -f "static/js/manual-ai/$module" ]; then
        echo "   ✅ $module"
        ((completed++))
    else
        echo "   ⏳ $module (pendiente)"
    fi
done

echo ""
echo "📊 Progreso: $completed / ${#modules[@]} módulos completados"

# Calcular porcentaje
percentage=$((completed * 100 / ${#modules[@]}))
echo "   $percentage% completado"

echo ""
echo "✅ Verificación completada"
echo ""
echo "📋 Próximos pasos:"
echo "   1. Revisar STATUS.md para ver el plan completo"
echo "   2. Decidir estrategia: gradual (recomendado) o mantener actual"
echo "   3. Si eliges gradual, continuar creando módulos restantes"
echo ""

