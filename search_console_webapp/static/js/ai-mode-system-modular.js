/**
 * AI Mode System - Modular Entry Point
 * Sistema modular que integra todos los módulos de AI Mode
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
    hideElement,
    showToast
} from '/static/js/ai-mode-projects/ai-mode-utils.js';

// Core - Importar la clase AIModeSystem
import { AIModeSystem } from '/static/js/ai-mode-projects/ai-mode-core.js';

// Projects
import {
    loadProjects,
    renderProjects,
    renderProjectCompetitorsHorizontal,
    goToProjectAnalytics,
    showCreateProject,
    hideCreateProject,
    handleCreateProject,
    validateProjectDomain,
    normalizeProjectDomain,
    filterCountryOptions,
    addCompetitorChip,
    getCompetitorChipValues,
    setCompetitorError
} from '/static/js/ai-mode-projects/ai-mode-projects.js';

// Keywords
import {
    loadProjectKeywords,
    renderKeywords,
    showAddKeywords,
    hideAddKeywords,
    updateKeywordsCounter,
    updateModalKeywordsCounter,
    handleAddKeywords,
    toggleKeyword,
    addKeywordsFromModal
} from '/static/js/ai-mode-projects/ai-mode-keywords.js';

// Analysis
import {
    analyzeProject,
    runAnalysis
} from '/static/js/ai-mode-projects/ai-mode-analysis.js';

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
} from '/static/js/ai-mode-projects/ai-mode-charts.js';

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
    showNoAiModeUrlsMessage,
    initAiModeUrlsFilter,
    filterAiModeUrlsByBrand,
    loadAIOverviewKeywordsTable,
    renderAIOverviewKeywordsTable,
    showNoAIKeywordsMessage,
    loadComparativeCharts,
    renderComparativeVisibilityChart,
    renderComparativePositionChart,
    showNoComparativeChartsMessage,
    processAIOverviewDataForGrid,
    truncateDomain
} from '/static/js/ai-mode-projects/ai-mode-analytics.js';

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
} from '/static/js/ai-mode-projects/ai-mode-competitors.js';

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
    showNoClustersMessage,
    loadProjectClustersForSettings,
    saveClustersConfiguration,
    renderProjectClustersHorizontal
} from '/static/js/ai-mode-projects/ai-mode-clusters.js';

// Exports
import {
    handleDownloadExcel,
    handleDownloadPDF
} from '/static/js/ai-mode-projects/ai-mode-exports.js';

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
} from '/static/js/ai-mode-projects/ai-mode-modals.js';

// ================================
// INTEGRACIÓN DE MÓDULOS
// ================================

// Extender el prototipo de AIModeSystem con todas las funciones importadas
Object.assign(AIModeSystem.prototype, {
    // Utils
    escapeHtml,
    debounce,
    getDomainLogoUrl,
    isValidDomain,
    normalizeDomainString,
    showElement,
    hideElement,
    showToast,
    
    // Projects
    loadProjects,
    renderProjects,
    renderProjectCompetitorsHorizontal,
    goToProjectAnalytics,
    showCreateProject,
    hideCreateProject,
    handleCreateProject,
    validateProjectDomain,
    normalizeProjectDomain,
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
    updateModalKeywordsCounter,
    handleAddKeywords,
    toggleKeyword,
    addKeywordsFromModal,
    
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
    showNoAiModeUrlsMessage,
    initAiModeUrlsFilter,
    filterAiModeUrlsByBrand,
    loadAIOverviewKeywordsTable,
    renderAIOverviewKeywordsTable,
    showNoAIKeywordsMessage,
    loadComparativeCharts,
    renderComparativeVisibilityChart,
    renderComparativePositionChart,
    showNoComparativeChartsMessage,
    processAIOverviewDataForGrid,
    truncateDomain,
    
    // Competitors
    loadCompetitors,
    renderCompetitors,
    addCompetitor,
    removeCompetitor,
    updateCompetitors,
    loadCompetitorsPreview,
    renderCompetitorsPreview,
    initCompetitorsManager,
    
    // Clusters
    initializeClustersConfiguration,
    toggleClustersConfiguration,
    addClusterRow,
    getClustersConfiguration,
    loadClustersConfiguration,
    loadClustersStatistics,
    renderClustersChart,
    renderClustersTable,
    showNoClustersMessage,
    loadProjectClustersForSettings,
    saveClustersConfiguration,
    renderProjectClustersHorizontal,
    
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
    loadModalSettings
});

// ================================
// INICIALIZACIÓN DEL SISTEMA
// ================================

// Crear instancia global del sistema cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing AI Mode System (Modular)...');
    
    // Crear instancia global
    window.aiModeSystem = new AIModeSystem();
    
    // Inicializar configuración de Clusters (event listeners para toggles)
    try {
        if (window.aiModeSystem && typeof window.aiModeSystem.initializeClustersConfiguration === 'function') {
            window.aiModeSystem.initializeClustersConfiguration();
        }
    } catch (e) {
        console.warn('⚠️ Error initializing clusters configuration:', e);
    }
    
    // Registrar plugin de Chart.js
    if (typeof Chart !== 'undefined') {
        Chart.register(htmlLegendPlugin);
        console.log('✅ Chart.js HTML Legend plugin registered');
    }
    
    // Inicializar componentes adicionales si existen
    if (typeof window.initAIModeComponents === 'function') {
        window.initAIModeComponents();
    }
    
    console.log('✅ AI Mode System (Modular) initialized successfully');
});

// Exportar para acceso global
export { AIModeSystem };

