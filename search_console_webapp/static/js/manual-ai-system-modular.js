/**
 * Manual AI System - Modular Entry Point
 * Sistema modular que integra todos los módulos refactorizados
 * Este archivo reemplaza el archivo monolítico original
 */

// ================================
// IMPORTS DE MÓDULOS
// ================================

// Utils
import {
    htmlLegendPlugin,
    escapeHtml,
    debounce,
    getDomainLogoUrl,
    isValidDomain,
    normalizeDomainString,
    showElement,
    hideElement
} from './manual-ai/manual-ai-utils.js';

// Core - Importar la clase ManualAISystem
import { ManualAISystem } from './manual-ai/manual-ai-core.js';

// Projects
import {
    loadProjects,
    renderProjects,
    renderProjectCompetitorsSection,
    renderProjectCompetitorsHorizontal,
    goToProjectAnalytics,
    showCreateProject,
    hideCreateProject,
    handleCreateProject,
    normalizeProjectDomain,
    validateProjectDomain,
    filterCountryOptions,
    addCompetitorChip,
    getCompetitorChipValues,
    setCompetitorError
} from './manual-ai/manual-ai-projects.js';

// Keywords
import {
    loadProjectKeywords,
    renderKeywords,
    showAddKeywords,
    hideAddKeywords,
    updateKeywordsCounter,
    handleAddKeywords,
    toggleKeyword
} from './manual-ai/manual-ai-keywords.js';

// Analysis
import {
    analyzeProject,
    runAnalysis
} from './manual-ai/manual-ai-analysis.js';

// Charts
import {
    renderVisibilityChart,
    renderPositionsChart,
    createEventAnnotations,
    drawEventAnnotations,
    getEventColor,
    getEventIcon,
    clearEventAnnotations,
    showEventAnnotations
} from './manual-ai/manual-ai-charts.js';

// Competitors
import {
    loadCompetitors,
    renderCompetitors,
    addCompetitor,
    removeCompetitor,
    updateCompetitors,
    loadCompetitorsPreview,
    renderCompetitorsPreview,
    initCompetitorsManager
} from './manual-ai/manual-ai-competitors.js';

// Analytics
import {
    populateAnalyticsProjectSelect,
    loadAnalytics,
    renderAnalytics,
    updateSummaryCard,
    loadAnalyticsComponents,
    loadTopDomains,
    renderTopDomains,
    calculateVisibilityScore,
    getScoreClass,
    showNoDomainsMessage,
    loadGlobalDomainsRanking,
    renderGlobalDomainsRanking,
    renderGlobalDomainsPaginator,
    showNoGlobalDomainsMessage,
    loadTopUrlsRanking,
    renderTopUrlsRanking,
    renderTopUrlsPaginator,
    showNoUrlsMessage,
    initUrlsFilter,
    filterUrlsByDomain,
    loadAIOverviewKeywordsTable,
    renderAIOverviewKeywordsTable,
    showNoAIKeywordsMessage,
    loadComparativeCharts,
    renderComparativeVisibilityChart,
    renderComparativePositionChart,
    showNoComparativeChartsMessage,
    processAIOverviewDataForGrid,
    truncateDomain
} from './manual-ai/manual-ai-analytics.js';

// Exports
import {
    handleDownloadExcel,
    handleDownloadPDF
} from './manual-ai/manual-ai-exports.js';

// Modals
import {
    loadProjectResults,
    renderResults,
    getImpactClass,
    calculateImpact,
    showProjectModal,
    hideProjectModal,
    switchModalTab,
    loadProjectIntoModal,
    loadModalKeywords,
    renderModalKeywords,
    loadModalSettings
} from './manual-ai/manual-ai-modals.js';

// Clusters
import {
    initializeClustersConfiguration,
    toggleClustersConfiguration,
    addClusterRow,
    getClustersConfiguration,
    loadClustersConfiguration,
    loadClustersStatistics,
    renderClustersChart,
    renderClustersTable,
    showDataStaleWarning,
    showNoClustersMessage,
    loadProjectClustersForSettings,
    saveClustersConfiguration,
    renderProjectClustersHorizontal
} from './manual-ai/manual-ai-clusters.js';

// ================================
// INTEGRACIÓN DE MÓDULOS
// ================================

// Extender el prototipo de ManualAISystem con todas las funciones importadas
Object.assign(ManualAISystem.prototype, {
    // Utils
    escapeHtml,
    debounce,
    getDomainLogoUrl,
    isValidDomain,
    normalizeDomainString,
    showElement,
    hideElement,
    
    // Projects
    loadProjects,
    renderProjects,
    renderProjectCompetitorsSection,
    renderProjectCompetitorsHorizontal,
    goToProjectAnalytics,
    showCreateProject,
    hideCreateProject,
    handleCreateProject,
    normalizeProjectDomain,
    validateProjectDomain,
    filterCountryOptions,
    addCompetitorChip,
    getCompetitorChipValues,
    setCompetitorError,
    
    // Keywords
    loadProjectKeywords,
    renderKeywords,
    showAddKeywords,
    hideAddKeywords,
    updateKeywordsCounter,
    handleAddKeywords,
    toggleKeyword,
    
    // Analysis
    analyzeProject,
    runAnalysis,
    
    // Charts
    renderVisibilityChart,
    renderPositionsChart,
    createEventAnnotations,
    drawEventAnnotations,
    getEventColor,
    getEventIcon,
    clearEventAnnotations,
    showEventAnnotations,
    
    // Competitors
    loadCompetitors,
    renderCompetitors,
    addCompetitor,
    removeCompetitor,
    updateCompetitors,
    loadCompetitorsPreview,
    renderCompetitorsPreview,
    initCompetitorsManager,
    
    // Analytics
    populateAnalyticsProjectSelect,
    loadAnalytics,
    renderAnalytics,
    updateSummaryCard,
    loadAnalyticsComponents,
    loadTopDomains,
    renderTopDomains,
    calculateVisibilityScore,
    getScoreClass,
    showNoDomainsMessage,
    loadGlobalDomainsRanking,
    renderGlobalDomainsRanking,
    renderGlobalDomainsPaginator,
    showNoGlobalDomainsMessage,
    loadTopUrlsRanking,
    renderTopUrlsRanking,
    renderTopUrlsPaginator,
    showNoUrlsMessage,
    initUrlsFilter,
    filterUrlsByDomain,
    loadAIOverviewKeywordsTable,
    renderAIOverviewKeywordsTable,
    showNoAIKeywordsMessage,
    loadComparativeCharts,
    renderComparativeVisibilityChart,
    renderComparativePositionChart,
    showNoComparativeChartsMessage,
    processAIOverviewDataForGrid,
    truncateDomain,
    
    // Exports
    handleDownloadExcel,
    handleDownloadPDF,
    
    // Modals
    loadProjectResults,
    renderResults,
    getImpactClass,
    calculateImpact,
    showProjectModal,
    hideProjectModal,
    switchModalTab,
    loadProjectIntoModal,
    loadModalKeywords,
    renderModalKeywords,
    loadModalSettings,
    
    // Clusters
    initializeClustersConfiguration,
    toggleClustersConfiguration,
    addClusterRow,
    getClustersConfiguration,
    loadClustersConfiguration,
    loadClustersStatistics,
    renderClustersChart,
    renderClustersTable,
    showDataStaleWarning,
    showNoClustersMessage,
    loadProjectClustersForSettings,
    saveClustersConfiguration,
    renderProjectClustersHorizontal
});

// ================================
// EXPONER CLASE GLOBALMENTE
// ================================

// Hacer la clase disponible globalmente para compatibilidad
window.ManualAISystem = ManualAISystem;

// ================================
// INICIALIZACIÓN GLOBAL
// ================================

console.log('✅ Sistema Modular Manual AI cargado correctamente');
console.log('📦 Módulos integrados: Utils, Core, Projects, Keywords, Analysis, Charts, Competitors, Analytics, Modals, Exports, Clusters');

// Función de inicialización completa
function initializeManualAI() {
    window.manualAI = new ManualAISystem();
    console.log('🚀 Manual AI System inicializado (sistema modular)');
    
    // Llamar a la función de inicialización de componentes adicionales si existe
    if (typeof window.initManualAIComponents === 'function') {
        window.initManualAIComponents();
        console.log('✅ Componentes adicionales inicializados');
    }
}

// Inicializar el sistema cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeManualAI);
} else {
    initializeManualAI();
}

// Exportar para uso si es necesario
export default ManualAISystem;

