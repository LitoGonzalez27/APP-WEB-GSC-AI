# Manual AI System - JavaScript Modules

## 📁 Estructura Modular

Este directorio contiene los módulos refactorizados del sistema Manual AI.

### Archivos Creados

✅ **manual-ai-utils.js** - Utilidades, helpers, validadores  
✅ **manual-ai-core.js** - Clase principal y configuración base  
⏳ **manual-ai-projects.js** - Gestión de proyectos (pendiente)  
⏳ **manual-ai-keywords.js** - Gestión de keywords (pendiente)  
⏳ **manual-ai-analysis.js** - Ejecución de análisis (pendiente)  
⏳ **manual-ai-charts.js** - Renderizado de gráficos (pendiente)  
⏳ **manual-ai-annotations.js** - Anotaciones y eventos (pendiente)  
⏳ **manual-ai-competitors.js** - Gestión de competidores (pendiente)  
⏳ **manual-ai-analytics.js** - Carga de analytics (pendiente)  
⏳ **manual-ai-modals.js** - Gestión de modales (pendiente)  
⏳ **manual-ai-exports.js** - Exportación Excel/PDF (pendiente)  
⏳ **manual-ai-init.js** - Inicialización global (pendiente)  

## 🔒 Sistema de Seguridad

### Backup
- **Archivo original:** `static/js/manual-ai-system.js` ✅ (Funcional)
- **Backup creado:** `static/js/manual-ai-system.js.backup` ✅

### Estrategia de Migración Gradual

1. **Fase 1:** ✅ Core y Utils creados
2. **Fase 2:** Crear módulos restantes uno por uno
3. **Fase 3:** Probar cada módulo independientemente
4. **Fase 4:** Integrar todo en `manual-ai-system-modular.js`
5. **Fase 5:** Cambiar referencia en HTML cuando todo esté verificado

## 🎯 Ventajas de la Refactorización

- ✅ **Modularidad:** Cada módulo tiene una responsabilidad clara
- ✅ **Mantenibilidad:** Más fácil encontrar y modificar código
- ✅ **Testabilidad:** Cada módulo puede probarse aisladamente
- ✅ **Escalabilidad:** Fácil agregar nuevas funcionalidades
- ✅ **Legibilidad:** Archivos más pequeños y enfocados

## 📋 División de Responsabilidades

### manual-ai-utils.js (~200 líneas)
```javascript
export const htmlLegendPlugin = { ... }
export function escapeHtml(text) { ... }   // delega en static/js/html-escape.js
export function debounce(func, wait) { ... }
export function getDomainLogoUrl(domain) { ... }
export function isValidDomain(domain) { ... }
export function normalizeDomainString(value) { ... }
export function showElement(element) { ... }
export function hideElement(element) { ... }
```

### manual-ai-core.js (~400 líneas)
```javascript
export class ManualAISystem {
    constructor() { ... }
    init() { ... }
    cacheElements() { ... }
    setupEventListeners() { ... }
    getModernChartConfig() { ... }
    switchTab(tabName) { ... }
    showProgress(title, message) { ... }
}
```

### manual-ai-projects.js (pendiente)
```javascript
// Exportará métodos para el prototipo:
export function loadProjects() { ... }
export function renderProjects() { ... }
export function showCreateProject() { ... }
export function handleCreateProject(e) { ... }
export function validateProjectDomain() { ... }
export function goToProjectAnalytics(projectId) { ... }
```

### manual-ai-keywords.js (pendiente)
```javascript
export function loadProjectKeywords(projectId) { ... }
export function renderKeywords(keywords) { ... }
export function showAddKeywords() { ... }
export function handleAddKeywords(e) { ... }
export function updateKeywordsCounter() { ... }
export function addKeywordsFromModal() { ... }
export function removeKeywordFromModal(keywordId) { ... }
```

### manual-ai-analysis.js (pendiente)
```javascript
export function analyzeProject(projectId) { ... }
export function resetProgressBar() { ... }
export function startProgressBar(maxPercent, stepMs) { ... }
export function stopProgressBar() { ... }
export function completeProgressBar() { ... }
export function updateProgressUI(value) { ... }
```

### manual-ai-charts.js (pendiente)
```javascript
export function renderVisibilityChart(data, events) { ... }
export function renderPositionsChart(data, events) { ... }
export function renderComparativeVisibilityChart(chartData) { ... }
export function renderComparativePositionChart(chartData) { ... }
```

### manual-ai-annotations.js (pendiente)
```javascript
export function createEventAnnotations(chartData, events) { ... }
export function drawEventAnnotations(chart, annotations) { ... }
export function showEventAnnotations(chart, annotations) { ... }
export function clearEventAnnotations(chart) { ... }
export function getEventColor(eventType) { ... }
export function getEventIcon(eventType) { ... }
export function showAnnotationModal(changeType, changeDescription) { ... }
export function saveAnnotation() { ... }
```

### manual-ai-competitors.js (pendiente)
```javascript
export function initCompetitorsManager() { ... }
export function loadCompetitors(projectId) { ... }
export function renderCompetitors(competitors) { ... }
export function addCompetitor() { ... }
export function removeCompetitor(domain) { ... }
export function updateCompetitors(competitors) { ... }
export function loadCompetitorsCharts(projectId) { ... }
export function renderCompetitorsVisibilityChart(scatterData) { ... }
export function renderCompetitorsPositionChart(positionData) { ... }
```

### manual-ai-analytics.js (pendiente)
```javascript
export function loadAnalytics() { ... }
export function renderAnalytics(stats) { ... }
export function loadAnalyticsComponents(projectId) { ... }
export function populateAnalyticsProjectSelect() { ... }
export function updateSummaryCard(elementId, value) { ... }
export function loadGlobalDomainsRanking(projectId) { ... }
export function renderGlobalDomainsRanking(domains) { ... }
export function loadAIOverviewKeywordsTable(projectId) { ... }
export function renderAIOverviewKeywordsTable(data) { ... }
export function loadComparativeCharts(projectId) { ... }
```

### manual-ai-modals.js (pendiente)
```javascript
export function showProjectModal(projectId) { ... }
export function hideProjectModal() { ... }
export function switchModalTab(tabName) { ... }
export function loadProjectIntoModal(project) { ... }
export function loadModalKeywords(projectId) { ... }
export function loadModalSettings(project) { ... }
export function updateProjectFromModal() { ... }
export function confirmDeleteProjectFromModal() { ... }
export function executeDeleteProject() { ... }
```

### manual-ai-exports.js (pendiente)
```javascript
export function showDownloadButton(show) { ... }
export function handleDownloadExcel() { ... }
export function handleDownloadPDF() { ... }
```

### manual-ai-init.js (pendiente)
```javascript
export function initializeUserDropdown() { ... }
export function initialize() { ... }
```

## 🔄 Cómo Usar los Módulos

### Opción 1: Importación Individual (Actual - Desarrollo)
```html
<script type="module">
    import { ManualAISystem } from './manual-ai/manual-ai-core.js';
    import * as utils from './manual-ai/manual-ai-utils.js';
    
    // Asignar utilidades al prototipo
    Object.assign(ManualAISystem.prototype, utils);
    
    // Crear instancia global
    window.manualAI = new ManualAISystem();
</script>
```

### Opción 2: Bundle Completo (Futuro - Producción)
```html
<script src="/static/js/manual-ai-system-modular.js" type="module"></script>
```

## 🚀 Próximos Pasos

1. **Completar módulos restantes:** Crear archivos para projects, keywords, analysis, etc.
2. **Testing incremental:** Probar cada módulo mientras se desarrolla
3. **Crear bundle:** Unificar imports en `manual-ai-system-modular.js`
4. **Actualizar templates:** Cambiar referencia en HTML cuando todo esté verificado
5. **Eliminar archivo original:** Solo después de confirmar que todo funciona

## ⚠️ Precauciones

- ✅ **NO eliminar `manual-ai-system.js`** hasta que la refactorización esté completa
- ✅ **Mantener backup** en `manual-ai-system.js.backup`
- ✅ **Probar exhaustivamente** cada módulo antes de integrar
- ✅ **Verificar** que todos los event listeners funcionen
- ✅ **Confirmar** que los modales se abren/cierran correctamente
- ✅ **Validar** que los charts se renderizan sin errores

## 📞 Soporte

Si encuentras algún problema durante la migración, consulta:
- `REFACTORING_PLAN.md` - Plan detallado de refactorización
- Logs del navegador - Busca errores en consola
- Archivo backup - `manual-ai-system.js.backup`

---

**Fecha:** 3 de Octubre, 2025  
**Estado:** En progreso (2/12 módulos completados)  
**Compatibilidad:** 100% con sistema original

