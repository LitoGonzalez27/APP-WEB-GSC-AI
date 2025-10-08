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
    hideElement
} from '/static/js/ai-mode-projects/ai-mode-utils.js';

// Core - Importar la clase AIModeSystem
import { AIModeSystem } from '/static/js/ai-mode-projects/ai-mode-core.js';

// Projects
import {
    loadProjects,
    renderProjects,
    goToProjectAnalytics,
    showCreateProject,
    hideCreateProject,
    handleCreateProject,
    filterCountryOptions
} from '/static/js/ai-mode-projects/ai-mode-projects.js';

// Keywords
import {
    loadProjectKeywords,
    renderKeywords,
    showAddKeywords,
    hideAddKeywords,
    updateKeywordsCounter,
    handleAddKeywords,
    toggleKeyword
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
    loadAnalyticsComponents
} from '/static/js/ai-mode-projects/ai-mode-analytics.js';

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
    
    // Projects
    loadProjects,
    renderProjects,
    goToProjectAnalytics,
    showCreateProject,
    hideCreateProject,
    handleCreateProject,
    filterCountryOptions,
    
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
    
    // Analytics
    populateAnalyticsProjectSelect,
    loadAnalytics,
    renderAnalytics,
    updateSummaryCard,
    loadAnalyticsComponents,
    
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

