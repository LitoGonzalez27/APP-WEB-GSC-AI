/**
 * Manual AI System - Core Module
 * Clase principal, inicialización, y configuración base
 */

import { showElement, hideElement } from './manual-ai-utils.js';

export class ManualAISystem {
    constructor() {
        this.projects = [];
        this.currentProject = null;
        this.currentModalProject = null;
        this.projectToDelete = null;
        this.charts = {};
        this.isLoading = false;
        this.refreshInterval = null;
        
        // DOM References
        this.elements = {};
        
        this.init();
    }

    init() {
        console.log('🤖 Initializing Manual AI System...');
        
        // Clear cache data that might be causing problems
        this.clearObsoleteCache();
        
        // Cache DOM references
        this.cacheElements();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial data
        this.loadInitialData();
        
        // Setup auto-refresh
        this.setupAutoRefresh();
        
        // Initialize competitors manager
        this.initCompetitorsManager();
        
        // Initialize clusters configuration
        if (typeof this.initializeClustersConfiguration === 'function') {
            this.initializeClustersConfiguration();
        }
        
        console.log('✅ Manual AI System initialized');
    }
    
    clearObsoleteCache() {
        // Clear any references to projects that no longer exist
        try {
            // Clear localStorage related to Manual AI
            const keysToRemove = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.startsWith('manualAI_') || key.startsWith('manual_ai_'))) {
                    keysToRemove.push(key);
                }
            }
            
            keysToRemove.forEach(key => {
                console.log(`🧹 Removing obsolete cache key: ${key}`);
                localStorage.removeItem(key);
            });
            
            // Reset currentModalProject if active
            this.currentModalProject = null;
            
            // Clear sessionStorage as well
            try {
                const sessionKeys = [];
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    if (key && (key.includes('manual') || key.includes('project') || key.includes('keyword'))) {
                        sessionKeys.push(key);
                    }
                }
                
                sessionKeys.forEach(key => {
                    console.log(`🧹 Removing obsolete session key: ${key}`);
                    sessionStorage.removeItem(key);
                });
                
                if (sessionKeys.length > 0) {
                    console.log(`🧹 Session storage cleared: ${sessionKeys.length} keys removed`);
                }
            } catch (sessionError) {
                console.warn('⚠️ Error clearing session storage:', sessionError);
            }
            
            if (keysToRemove.length > 0) {
                console.log(`🧹 Obsolete cache cleared: ${keysToRemove.length} keys removed`);
            }
            
        } catch (error) {
            console.warn('⚠️ Error clearing cache:', error);
        }
    }

    // ================================
    // MODERN CHART.JS CONFIGURATION
    // ================================
    getModernChartConfig(useHtmlLegend = false, legendId = null) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
                axis: 'x'
            },
            plugins: {
                htmlLegend: useHtmlLegend ? {
                    containerID: legendId
                } : undefined,
                legend: {
                    display: !useHtmlLegend,
                    position: 'bottom',
                    align: 'start',
                    labels: {
                        usePointStyle: true,
                        pointStyle: 'rectRounded',
                        padding: 20,
                        font: {
                            size: 12,
                            family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
                        }
                    }
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                    titleColor: '#F9FAFB',
                    bodyColor: '#F3F4F6',
                    borderColor: 'rgba(156, 163, 175, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true,
                    padding: 12,
                    titleFont: {
                        size: 13,
                        weight: '600'
                    },
                    bodyFont: {
                        size: 12
                    },
                    filter: function(tooltipItem) {
                        return tooltipItem.parsed.y !== null;
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(229, 231, 235, 0.4)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#6B7280',
                        font: {
                            size: 11
                        }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(229, 231, 235, 0.4)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#6B7280',
                        font: {
                            size: 11
                        }
                    }
                }
            },
            elements: {
                line: {
                    tension: 0.4,
                    borderWidth: 2.5,
                    borderCapStyle: 'round',
                    borderJoinStyle: 'round'
                },
                point: {
                    pointStyle: 'rectRounded',
                    radius: 4,
                    hoverRadius: 7,
                    hitRadius: 10,
                    borderWidth: 2,
                    hoverBorderWidth: 3
                }
            },
            animations: {
                tension: {
                    duration: 300,
                    easing: 'easeInOutCubic',
                    from: 1,
                    to: 0.4
                }
            }
        };
    }

    setupAutoRefresh() {
        // Auto-refresh projects every 2 minutes to catch cron updates
        this.refreshInterval = setInterval(() => {
            if (this.currentTab === 'projects') {
                // Only auto-refresh for paid users
                if (window.currentUser && window.currentUser.plan !== 'free') {
                    console.log('🔄 Auto-refreshing projects...');
                    this.loadProjects();
                } else {
                    console.log('🆓 Auto-refresh omitido para usuario gratuito');
                }
            }
        }, 120000); // 2 minutes
        
        console.log('✅ Auto-refresh configurado cada 2 minutos');
    }

    cacheElements() {
        // Tabs
        this.elements.navTabs = document.querySelectorAll('.nav-tab');
        this.elements.tabContents = document.querySelectorAll('.tab-content');
        
        // Projects
        this.elements.projectsContainer = document.getElementById('projectsContainer');
        this.elements.projectsLoading = document.getElementById('projectsLoading');
        this.elements.projectsEmptyState = document.getElementById('projectsEmptyState');
        this.elements.createProjectBtn = document.getElementById('createProjectBtn');
        
        // Modals
        this.elements.createProjectModal = document.getElementById('createProjectModal');
        this.elements.projectDetailsModal = document.getElementById('projectDetailsModal');
        this.elements.addKeywordsModal = document.getElementById('addKeywordsModal');
        this.elements.progressModal = document.getElementById('progressModal');
        
        // Forms
        this.elements.createProjectForm = document.getElementById('createProjectForm');
        this.elements.createProjectSubmit = document.getElementById('createProjectSubmit');
        this.elements.projectDomain = document.getElementById('projectDomain');
        this.elements.projectDomainHint = document.getElementById('projectDomainHint');
        this.elements.projectCountry = document.getElementById('projectCountry');
        this.elements.projectCountryFilter = document.getElementById('projectCountryFilter');
        this.elements.autoDetectCompetitors = document.getElementById('autoDetectCompetitors');
        this.elements.manualCompetitorsArea = document.getElementById('manualCompetitorsArea');
        this.elements.competitorInput = document.getElementById('competitorInput');
        this.elements.addCompetitorBtn = document.getElementById('addCompetitorBtn');
        this.elements.competitorChips = document.getElementById('competitorChips');
        this.elements.competitorError = document.getElementById('competitorError');
        this.elements.addKeywordsForm = document.getElementById('addKeywordsForm');
        
        // Analytics
        this.elements.analyticsProjectSelect = document.getElementById('analyticsProjectSelect');
        this.elements.analyticsTimeRange = document.getElementById('analyticsTimeRange');
        this.elements.analyticsContent = document.getElementById('analyticsContent');
        this.elements.chartsContainer = document.getElementById('chartsContainer');
    }

    setupEventListeners() {
        // Navigation tabs
        this.elements.navTabs.forEach(tab => {
            tab.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });

        // Create project
        this.elements.createProjectBtn?.addEventListener('click', () => this.showCreateProject());
        this.elements.createProjectForm?.addEventListener('submit', (e) => this.handleCreateProject(e));

        // Live domain normalization & validation
        if (this.elements.projectDomain) {
            this.elements.projectDomain.addEventListener('input', () => this.validateProjectDomain());
            this.elements.projectDomain.addEventListener('blur', () => this.normalizeProjectDomain());
        }

        // Country live filter
        if (this.elements.projectCountry && this.elements.projectCountryFilter) {
            this.elements.projectCountryFilter.addEventListener('input', () => this.filterCountryOptions());
        }

        // Auto-detect competitors toggle
        if (this.elements.autoDetectCompetitors && this.elements.manualCompetitorsArea) {
            const syncVisibility = () => {
                const showManual = !this.elements.autoDetectCompetitors.checked;
                const area = this.elements.manualCompetitorsArea;
                if (!area) return;
                area.style.display = showManual ? 'flex' : 'none';
                area.setAttribute('aria-hidden', showManual ? 'false' : 'true');
            };
            this.elements.autoDetectCompetitors.addEventListener('change', syncVisibility);
            syncVisibility();
        }

        // Chips add/remove with keyboard support
        if (this.elements.competitorInput && this.elements.addCompetitorBtn) {
            this.elements.addCompetitorBtn.addEventListener('click', () => this.addCompetitorChip());
            this.elements.competitorInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.addCompetitorChip();
                }
                if (e.key === 'Escape') {
                    if (this.elements.createProjectModal) this.hideCreateProject();
                }
            });
        }

        // Add keywords form
        this.elements.addKeywordsForm?.addEventListener('submit', (e) => this.handleAddKeywords(e));

        // Keywords counter
        const keywordsTextarea = document.getElementById('keywordsTextarea');
        if (keywordsTextarea) {
            keywordsTextarea.addEventListener('input', () => this.updateKeywordsCounter());
        }

        // Analytics controls
        this.elements.analyticsProjectSelect?.addEventListener('change', () => this.loadAnalytics());
        this.elements.analyticsTimeRange?.addEventListener('change', () => this.loadAnalytics());

        // Download Excel button
        const downloadBtn = document.getElementById('sidebarDownloadBtn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('🖱️ Manual AI Excel download button clicked');
                this.handleDownloadExcel();
            });
            console.log('✅ Manual AI Download Excel event listener added');
        }

        // Download PDF button
        const downloadPdfBtn = document.getElementById('sidebarDownloadPdfBtn');
        if (downloadPdfBtn) {
            downloadPdfBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                console.log('🖱️ Manual AI PDF download button clicked');
                await this.handleDownloadPDF();
            });
            console.log('✅ Manual AI Download PDF event listener added');
        }

        // Detail tabs
        document.querySelectorAll('[data-detail-tab]').forEach(tab => {
            tab.addEventListener('click', (e) => this.switchDetailTab(e.target.dataset.detailTab));
        });

        // Modal close on background click
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideAllModals();
                }
            });
        });

        // Escape key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideAllModals();
            }
        });
    }

    async loadInitialData() {
        // Only load projects for paid users
        if (window.currentUser && window.currentUser.plan !== 'free') {
            console.log('💳 Usuario con plan de pago - cargando proyectos:', window.currentUser.plan);
            await this.loadProjects();
        } else {
            console.log('🆓 Usuario gratuito - mostrando estado sin proyectos');
            this.showFreeUserState();
        }
        
        this.populateAnalyticsProjectSelect();
    }

    showFreeUserState() {
        hideElement(this.elements.projectsLoading);
        this.projects = [];
        this.renderProjects();
        console.log('🆓 Estado gratuito mostrado - botón "Crear proyecto" disponible para paywall');
    }

    // ================================
    // TAB NAVIGATION
    // ================================

    switchTab(tabName) {
        // Update nav tabs
        this.elements.navTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab contents
        this.elements.tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}Tab`);
        });

        // Load specific tab data
        if (tabName === 'analytics') {
            this.loadAnalytics();
        } else if (tabName === 'settings') {
            this.loadCompetitors();
        }
    }

    switchDetailTab(tabName) {
        // Update detail tabs
        document.querySelectorAll('.detail-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.detailTab === tabName);
        });

        // Update detail contents
        document.querySelectorAll('.detail-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}DetailTab`);
        });

        // Load specific detail data
        if (tabName === 'keywords' && this.currentProject) {
            this.loadProjectKeywords(this.currentProject.id);
        } else if (tabName === 'results' && this.currentProject) {
            this.loadProjectResults(this.currentProject.id);
        } else if (tabName === 'settings' && this.currentProject) {
            this.loadProjectSettings(this.currentProject);
        }
    }

    // ================================
    // UI HELPERS
    // ================================

    showElement(element) {
        showElement(element);
    }

    hideElement(element) {
        hideElement(element);
    }

    hideAllModals() {
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            this.hideElement(modal);
        });
    }

    showProgress(title, message) {
        document.getElementById('progressTitle').textContent = title;
        document.getElementById('progressMessage').textContent = message;
        this.resetProgressBar();
        this.startProgressBar(90);
        showElement(this.elements.progressModal);
    }

    hideProgress() {
        this.stopProgressBar();
        hideElement(this.elements.progressModal);
    }

    showSuccess(message) {
        alert('✅ ' + message);
    }

    showError(message) {
        alert('❌ ' + message);
    }

    showToast(message, type = 'info', duration = 3000) {
        console.log(`[${type.toUpperCase()}] ${message}`);
        // Can be enhanced with a proper toast UI
    }

    showDownloadButton(show = true) {
        const downloadBtn = document.getElementById('sidebarDownloadBtn');
        const downloadPdfBtn = document.getElementById('sidebarDownloadPdfBtn');
        const globalSection = document.getElementById('navSectionGlobal');
        
        if (downloadBtn) {
            downloadBtn.style.display = show ? 'flex' : 'none';
            console.log(`📥 Download Excel button ${show ? 'shown' : 'hidden'} for Manual AI`);
        }
        if (downloadPdfBtn) {
            downloadPdfBtn.style.display = show ? 'flex' : 'none';
            console.log(`📥 Download PDF button ${show ? 'shown' : 'hidden'} for Manual AI`);
        }
        
        // Show/hide the entire global section based on button visibility
        if (globalSection) {
            globalSection.style.display = show ? 'block' : 'none';
            console.log(`📂 Global tools section ${show ? 'shown' : 'hidden'} for Manual AI`);
        }
    }

    // Placeholder methods that will be implemented in other modules
    renderProjects() { console.warn('renderProjects not implemented'); }
    loadProjects() { console.warn('loadProjects not implemented'); }
    showCreateProject() { console.warn('showCreateProject not implemented'); }
    handleCreateProject() { console.warn('handleCreateProject not implemented'); }
    validateProjectDomain() { console.warn('validateProjectDomain not implemented'); }
    normalizeProjectDomain() { console.warn('normalizeProjectDomain not implemented'); }
    filterCountryOptions() { console.warn('filterCountryOptions not implemented'); }
    addCompetitorChip() { console.warn('addCompetitorChip not implemented'); }
    handleAddKeywords() { console.warn('handleAddKeywords not implemented'); }
    updateKeywordsCounter() { console.warn('updateKeywordsCounter not implemented'); }
    loadAnalytics() { console.warn('loadAnalytics not implemented'); }
    handleDownloadExcel() { console.warn('handleDownloadExcel not implemented'); }
    handleDownloadPDF() { console.warn('handleDownloadPDF not implemented'); }
    loadProjectKeywords() { console.warn('loadProjectKeywords not implemented'); }
    loadProjectResults() { console.warn('loadProjectResults not implemented'); }
    loadProjectSettings() { console.warn('loadProjectSettings not implemented'); }
    loadCompetitors() { console.warn('loadCompetitors not implemented'); }
    initCompetitorsManager() { console.warn('initCompetitorsManager not implemented'); }
    populateAnalyticsProjectSelect() { console.warn('populateAnalyticsProjectSelect not implemented'); }
    hideCreateProject() { console.warn('hideCreateProject not implemented'); }
}

