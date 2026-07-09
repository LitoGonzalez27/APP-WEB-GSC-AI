/**
 * AI Visibility Summary - Modular Entry Point
 * Mismo patrón que manual-ai-system-modular.js: clase base + Object.assign.
 */

import { AISummarySystem } from './ai-summary/ai-summary-core.js';

// Utils compartidos (mismos helpers que Manual AI / AI Mode)
import { escapeHtml, getDomainLogoUrl } from './manual-ai/manual-ai-utils.js';

import {
    loadBrands,
    renderBrandsGrid,
    showBrandsList,
    openBrand,
    populateLinkSelects,
    renderSuggestions,
    confirmSuggestion,
    handleCreateBrand,
    handleDeleteBrand,
    showSetup,
    hideSetup,
    showFormError
} from './ai-summary/ai-summary-brands.js';

import {
    loadSummary,
    renderBrandIdentity,
    renderSummary,
    renderScore,
    renderHighlights,
    renderChannelCards,
    renderChannelCard,
    renderCompetitorsTable
} from './ai-summary/ai-summary-render.js';

import { renderTrendChart } from './ai-summary/ai-summary-charts.js';

Object.assign(AISummarySystem.prototype, {
    // Utils
    escapeHtml,
    getDomainLogoUrl,

    // Brands
    loadBrands,
    renderBrandsGrid,
    showBrandsList,
    openBrand,
    populateLinkSelects,
    renderSuggestions,
    confirmSuggestion,
    handleCreateBrand,
    handleDeleteBrand,
    showSetup,
    hideSetup,
    showFormError,

    // Render
    loadSummary,
    renderBrandIdentity,
    renderSummary,
    renderScore,
    renderHighlights,
    renderChannelCards,
    renderChannelCard,
    renderCompetitorsTable,

    // Charts
    renderTrendChart
});

window.AISummarySystem = AISummarySystem;

function initializeAISummary() {
    window.aiSummary = new AISummarySystem();
    console.log('🚀 AI Visibility Summary initialized');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAISummary);
} else {
    initializeAISummary();
}

export default AISummarySystem;
