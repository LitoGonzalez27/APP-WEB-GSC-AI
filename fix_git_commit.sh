#!/bin/bash

echo "🔧 Arreglando commit con secretos..."
echo ""

# Paso 1: Deshacer el último commit pero mantener los cambios
echo "1️⃣ Deshaciendo el último commit..."
git reset --soft HEAD~1

# Paso 2: Eliminar el archivo problemático del staging
echo "2️⃣ Eliminando archivo con secretos del staging..."
git reset HEAD search_console_webapp/RAILWAY_STAGING_VARIABLES.txt 2>/dev/null || true

# Paso 3: Eliminar el archivo del repositorio si ya estaba trackeado
echo "3️⃣ Eliminando archivo del repositorio..."
git rm --cached search_console_webapp/RAILWAY_STAGING_VARIABLES.txt 2>/dev/null || true

# Paso 4: Agregar el .gitignore actualizado
echo "4️⃣ Agregando .gitignore actualizado..."
git add search_console_webapp/.gitignore

# Paso 5: Agregar todos los otros cambios
echo "5️⃣ Agregando cambios restantes..."
git add .

# Paso 6: Verificar qué se va a commitear
echo ""
echo "📋 Archivos que se van a commitear:"
git status --short

echo ""
echo "✅ Listo! Ahora puedes:"
echo "   1. Hacer commit: git commit -m 'Tu mensaje'"
echo "   2. Hacer push: git push"
echo ""
echo "⚠️  El archivo RAILWAY_STAGING_VARIABLES.txt ahora está en .gitignore y no se subirá"

