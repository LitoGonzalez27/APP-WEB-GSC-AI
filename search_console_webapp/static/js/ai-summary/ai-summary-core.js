/**
 * AI Summary - Core
 * Clase principal del panel AI Visibility Summary.
 * Los métodos de brands/render/charts se inyectan vía Object.assign
 * desde ai-summary-modular.js (mismo patrón que Manual AI).
 */

export class AISummarySystem {
    constructor() {
        this.apiBase = '/ai-summary/api';
        this.brands = [];
        this.suggestions = [];
        this.moduleProjects = { manual_ai: [], ai_mode: [], llm: [] };
        this.currentBrandId = null;
        this.period = '30';
        this.charts = {};

        this.elements = {};

        this.init();
    }

    async init() {
        this.cacheElements();
        this.setupEventListeners();
        await this.loadBrands();

        if (typeof window.initAISummaryComponents === 'function') {
            window.initAISummaryComponents();
        }
    }

    cacheElements() {
        const ids = [
            'brandsView', 'brandsGrid', 'newBrandBtn',
            'brandSetupSection', 'setupBackBtn', 'suggestionsList',
            'brandNameInput', 'brandDomainInput',
            'linkManualAI', 'linkAIMode', 'linkLLM',
            'createBrandBtn', 'brandFormError',
            'summaryContent', 'summaryLoading',
            'backToBrandsBtn', 'summaryBrandTitle', 'summaryBrandDomain', 'summaryBrandLogo',
            'daysSelect',
            'scoreValue', 'scoreDelta', 'scoreCoverage',
            'highlightsList', 'channelCards',
            'trendChart', 'competitorsTableBody',
            'deleteBrandBtn'
        ];
        ids.forEach(id => {
            this.elements[id] = document.getElementById(id);
        });
    }

    setupEventListeners() {
        // Abrir una marca desde su tarjeta (delegación en el grid)
        this.elements.brandsGrid?.addEventListener('click', (e) => {
            const card = e.target.closest('.brand-card');
            if (card) this.openBrand(Number(card.dataset.brandId));
        });
        this.elements.brandsGrid?.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            const card = e.target.closest('.brand-card');
            if (card) {
                e.preventDefault();
                this.openBrand(Number(card.dataset.brandId));
            }
        });

        this.elements.backToBrandsBtn?.addEventListener('click', () => this.showBrandsList());
        this.elements.setupBackBtn?.addEventListener('click', () => this.showBrandsList());

        this.elements.daysSelect?.addEventListener('change', () => {
            this.period = this.elements.daysSelect.value || '30';
            if (this.currentBrandId) {
                this.loadSummary();
            }
        });

        this.elements.newBrandBtn?.addEventListener('click', () => this.showSetup());
        this.elements.createBrandBtn?.addEventListener('click', () => this.handleCreateBrand());
        this.elements.deleteBrandBtn?.addEventListener('click', () => this.handleDeleteBrand());
    }

    getCurrentBrand() {
        return this.brands.find(b => b.id === this.currentBrandId) || null;
    }

    async fetchJson(url, options = {}) {
        const response = await fetch(url, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || `Request failed (${response.status})`);
        }
        return data;
    }

    showLoading(visible) {
        if (this.elements.summaryLoading) {
            this.elements.summaryLoading.style.display = visible ? 'block' : 'none';
        }
        if (visible && this.elements.summaryContent) {
            this.elements.summaryContent.style.display = 'none';
        }
    }
}
