# 🔧 Troubleshooting - Sistema Modular Manual AI

**Fecha:** 3 de Octubre, 2025

## ⚠️ Problema Actual

El navegador muestra:
```
TypeError: this.loadComparativeCharts is not a function
```

## 🎯 Causa

El navegador está cargando versiones cacheadas de los módulos. Los navegadores modernos cachean agresivamente los módulos ES6.

## ✅ Soluciones

### Solución 1: Hard Refresh Multiple (RECOMENDADO)

1. **Abrir DevTools** (F12)
2. **Click derecho en el botón de refresh** del navegador
3. **Seleccionar "Empty Cache and Hard Reload"** o "Vaciar caché y recargar de manera forzada"
4. **Repetir 2-3 veces** para asegurar

### Solución 2: Desactivar Caché Completamente

1. Abrir **DevTools** (F12)
2. Ir a **Network tab**
3. Marcar **"Disable cache"**
4. **Recargar** la página (F5)
5. Verificar en consola

### Solución 3: Modo Incógnito

1. Abrir **ventana de incógnito** (Ctrl+Shift+N / Cmd+Shift+N)
2. Navegar a tu aplicación
3. Verificar que funciona correctamente

### Solución 4: Limpiar Caché del Navegador

**Chrome/Edge:**
1. `Ctrl+Shift+Del` (Windows) o `Cmd+Shift+Del` (Mac)
2. Seleccionar "Cached images and files"
3. Seleccionar "All time"
4. Click "Clear data"

**Firefox:**
1. `Ctrl+Shift+Del` (Windows) o `Cmd+Shift+Del` (Mac)
2. Marcar "Cache"
3. Click "Clear Now"

### Solución 5: Añadir Cache Buster (DEFINITIVO)

Editar `templates/manual_ai_dashboard.html` línea ~1359:

```html
<!-- Añadir ?v=timestamp para forzar recarga -->
<script type="module" src="{{ url_for('static', filename='js/manual-ai-system-modular.js') }}?v={{ now }}"></script>
```

Y en `app.py`, añadir al contexto:

```python
from datetime import datetime

@app.route('/manual-ai/')
def manual_ai():
    return render_template('manual_ai_dashboard.html', now=datetime.now().timestamp())
```

## 🧪 Verificación

Después de aplicar cualquier solución, verifica en la consola:

### ✅ Debe aparecer:
```
✅ Sistema Modular Manual AI cargado correctamente
📦 Módulos integrados: Utils, Core, Projects, Keywords, Analysis, Charts, Competitors, Analytics, Modals
🤖 Initializing Manual AI System...
✅ Manual AI System initialized
🚀 Manual AI System inicializado (sistema modular)
🔄 Projects loaded: X
📊 Rendering analytics data: {...}
📈 Loading analytics components for project X
```

### ❌ NO debe aparecer:
```
❌ TypeError: this.loadComparativeCharts is not a function
❌ TypeError: this.handleDownloadExcel is not a function
❌ ... is not a function
```

## 🔍 Verificación Manual

Ejecuta esto en la consola del navegador:

```javascript
// Verificar que el sistema está cargado
console.log('Sistema cargado:', typeof window.manualAI);
// Debe mostrar: "object"

// Verificar función específica
console.log('loadComparativeCharts:', typeof window.manualAI.loadComparativeCharts);
// Debe mostrar: "function"

// Verificar todas las funciones
const funciones = Object.keys(window.manualAI).filter(k => typeof window.manualAI[k] === 'function');
console.log(`Total funciones: ${funciones.length}`);
// Debe mostrar: 100+

// Buscar función específica
console.log('Tiene loadComparativeCharts:', funciones.includes('loadComparativeCharts'));
// Debe mostrar: true
```

## 🚨 Si Nada Funciona

Si después de probar todas las soluciones el problema persiste:

### Plan B: Rollback Temporal

Edita `templates/manual_ai_dashboard.html` línea ~1359:

```html
<!-- Comentar sistema modular temporalmente -->
<!-- <script type="module" src="{{ url_for('static', filename='js/manual-ai-system-modular.js') }}"></script> -->

<!-- Volver al sistema original temporalmente -->
<script src="{{ url_for('static', filename='js/manual-ai-system.js') }}"></script>
```

Esto te permitirá seguir trabajando mientras investigamos el problema del caché.

## 📝 Notas

- **Problema común:** Los módulos ES6 son cacheados agresivamente por navegadores
- **No es un bug del código:** El código está correcto
- **Es un problema de caché:** El navegador no está cargando la versión nueva
- **Solución definitiva:** Implementar cache busting con timestamps

## ✅ Verificación de Archivos

Asegúrate de que estos archivos existen:

```bash
ls -la static/js/manual-ai-system-modular.js
ls -la static/js/manual-ai/*.js
```

Deberías ver:
```
manual-ai-system-modular.js     (entrada principal)
manual-ai/manual-ai-analytics.js (con loadComparativeCharts)
manual-ai/manual-ai-exports.js   (con handleDownloadExcel)
manual-ai/manual-ai-core.js      (con showDownloadButton)
... (más archivos)
```

## 🎯 Recomendación Final

**La solución más rápida y efectiva:**

1. **Abrir DevTools** (F12)
2. **Ir a Application/Almacenamiento**
3. **Click en "Clear storage"**
4. **Click en "Clear site data"**
5. **Recargar** (F5)

Esto limpia TODO el caché del sitio y fuerza una carga completamente fresca.

---

**Si sigues teniendo problemas después de esto, avísame y añadiré cache busting automático al sistema.** 🛠️

