# Manual AI JavaScript Refactoring Plan

## Objetivo
Refactorizar `manual-ai-system.js` (4912 líneas) en ~10 módulos más pequeños y manejables sin romper funcionalidad.

## Estrategia de División

### 1. `manual-ai-utils.js` (~300 líneas)
- HTML Legend Plugin para Chart.js
- Funciones helper: `escapeHtml`, `debounce`, `getDomainLogoUrl`
- Validadores: `isValidDomain`, `normalizeDomainString`
- Funciones UI: `showElement`, `hideElement`, `showProgress`, `hideProgress`

### 2. `manual-ai-core.js` (~400 líneas)
- Constructor de ManualAISystem
- `init()`, `cacheElements()`, `setupEventListeners()`
- `clearObsoleteCache()`, `setupAutoRefresh()`
- `loadInitialData()`, `switchTab()`, `switchDetailTab()`
- Modern Chart Configuration

### 3. `manual-ai-projects.js` (~500 líneas)
- `loadProjects()`, `renderProjects()`
- `showCreateProject()`, `handleCreateProject()`
- `validateProjectDomain()`, `normalizeProjectDomain()`
- `goToProjectAnalytics()`
- Competitor chips (add, remove, get)

### 4. `manual-ai-keywords.js` (~300 líneas)
- `loadProjectKeywords()`, `renderKeywords()`
- `showAddKeywords()`, `handleAddKeywords()`
- `toggleKeyword()`, `updateKeywordsCounter()`
- `loadModalKeywords()`, `renderModalKeywords()`
- `addKeywordsFromModal()`, `removeKeywordFromModal()`

### 5. `manual-ai-analysis.js` (~350 líneas)
- `analyzeProject()` - Lógica completa de análisis
- Progress bar control: `resetProgressBar()`, `startProgressBar()`, `stopProgressBar()`, `completeProgressBar()`
- Manejo de errores de quota y paywall

### 6. `manual-ai-charts.js` (~600 líneas)
- `getModernChartConfig()` - Configuración base
- `renderVisibilityChart()` - Chart de visibilidad
- `renderPositionsChart()` - Chart de posiciones
- `renderComparativeVisibilityChart()` - Comparativo de visibilidad
- `renderComparativePositionChart()` - Comparativo de posiciones

### 7. `manual-ai-annotations.js` (~400 líneas)
- `createEventAnnotations()`, `drawEventAnnotations()`
- `getEventColor()`, `getEventIcon()`
- `showEventAnnotations()`, `clearEventAnnotations()`
- `addCompetitorChangeMarkers()` - Markers temporales
- `showAnnotationModal()`, `saveAnnotation()`

### 8. `manual-ai-competitors.js` (~700 líneas)
- `initCompetitorsManager()`, `loadCompetitors()`, `renderCompetitors()`
- `addCompetitor()`, `removeCompetitor()`, `updateCompetitors()`
- `loadCompetitorsCharts()` - Charts de competencia
- `renderCompetitorsVisibilityChart()`, `renderCompetitorsPositionChart()`
- `loadCompetitorsPreview()`, `renderCompetitorsPreview()`

### 9. `manual-ai-analytics.js` (~800 líneas)
- `loadAnalytics()`, `renderAnalytics()`, `loadAnalyticsComponents()`
- `populateAnalyticsProjectSelect()`, `updateSummaryCard()`
- `loadGlobalDomainsRanking()`, `renderGlobalDomainsRanking()`
- `loadAIOverviewKeywordsTable()`, `renderAIOverviewKeywordsTable()`
- `processAIOverviewDataForGrid()`, `findCompetitorDataInResult()`
- `loadComparativeCharts()`

### 10. `manual-ai-modals.js` (~700 líneas)
- `showProjectModal()`, `hideProjectModal()`, `switchModalTab()`
- `loadProjectIntoModal()`, `loadModalSettings()`
- `updateProjectFromModal()`, `confirmDeleteProjectFromModal()`
- `executeDeleteProject()`, `confirmDeleteProject()`
- `hideAllModals()`

### 11. `manual-ai-exports.js` (~300 líneas)
- `showDownloadButton()`, `handleDownloadExcel()`
- `handleDownloadPDF()`

### 12. `manual-ai-init.js` (~100 líneas)
- Inicialización global
- `initializeUserDropdown()` - Dropdown del usuario
- Auto-detección de página Manual AI

## Arquitectura de Importación

```
manual-ai-system.js (main entry point)
  ├── imports: manual-ai-utils.js
  ├── imports: manual-ai-core.js
  ├── imports: manual-ai-projects.js
  ├── imports: manual-ai-keywords.js
  ├── imports: manual-ai-analysis.js
  ├── imports: manual-ai-charts.js
  ├── imports: manual-ai-annotations.js
  ├── imports: manual-ai-competitors.js
  ├── imports: manual-ai-analytics.js
  ├── imports: manual-ai-modals.js
  ├── imports: manual-ai-exports.js
  └── imports: manual-ai-init.js
```

## Estrategia de Migración

1. ✅ Crear backup: `manual-ai-system.js.backup`
2. ⏳ Crear módulos individuales en `static/js/manual-ai/`
3. ⏳ Cada módulo exporta funciones que se asignan al prototipo de `ManualAISystem`
4. ⏳ Crear nuevo `manual-ai-system.js` que importa todos los módulos
5. ⏳ Verificar que no se rompa nada
6. ⏳ Mantener backup hasta confirmar que todo funciona

## Compatibilidad

- ✅ Mantener la clase `ManualAISystem` global
- ✅ Mantener `window.manualAI` accesible desde HTML
- ✅ No cambiar nombres de métodos públicos
- ✅ Mantener estructura de eventos y callbacks
- ✅ Compatibilidad con todos los templates HTML existentes

## Verificación Final

- [ ] Projects CRUD funciona
- [ ] Keywords management funciona
- [ ] Analysis ejecuta correctamente
- [ ] Charts se renderizan
- [ ] Modals abren/cierran
- [ ] Competitors se gestionan
- [ ] Analytics carga datos
- [ ] Excel/PDF download funciona
- [ ] Event annotations se muestran
- [ ] No hay errores en consola

---

**Fecha:** 3 de Octubre, 2025  
**Estado:** En progreso  
**Backup:** `static/js/manual-ai-system.js.backup` ✅

