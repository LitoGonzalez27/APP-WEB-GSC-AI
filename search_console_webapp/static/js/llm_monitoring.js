/**
 * LLM Monitoring System - Frontend JavaScript
 * 
 * Handles all UI interactions for the Multi-LLM Brand Monitoring system
 */

class LLMMonitoring {
    constructor() {
        this.baseUrl = '/api/llm-monitoring';
        this.currentProject = null;
        this.charts = {};
        this.comparisonGrid = null;
        this.queriesGrid = null;
        this.historyChart = null; // ✨ NUEVO: Gráfica de historial en el modal

        // Pagination state
        this.promptsPerPage = 10;
        this.currentPromptsPage = 1;
        this.allPrompts = [];
        this.promptsSectionCollapsed = false;
        this.isRenderingInModal = false; // Track if we're rendering prompts in modal
        this.quickSuggestionsCache = new Map();

        // ✨ NEW: Responses pagination
        this.allResponses = [];
        this.filteredResponses = null;
        this.currentDisplayResponses = [];
        this.responsesLoaded = false;
        this.responsesPerPage = 5;
        this.currentResponsesShown = 5;

        // Chips state
        this.brandKeywordsChips = [];

        // ✨ NEW: Individual competitor chips (4 competitors max)
        this.competitor1KeywordsChips = [];
        this.competitor2KeywordsChips = [];
        this.competitor3KeywordsChips = [];
        this.competitor4KeywordsChips = [];

        // ✨ Pagination state for URLs table
        this._topUrlsLLMState = null;

        // ✨ NEW: Global Time Range
        this.globalTimeRange = 30; // Default to 30 days

        // Plan limits snapshot loaded from /usage
        this.planLimits = null;

        // Custom confirm modal state
        this.confirmResolver = null;
        this.isConfirmModalOpen = false;

        // LLM selection UX state
        this.modalOriginalEnabledLlms = null;
        this.pendingModelScopeNotice = null;
        this.serverModelScopeNotice = null;
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.LLMMonitoring = LLMMonitoring;
}
