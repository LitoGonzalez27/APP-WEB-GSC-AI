/*
 * Manual AI Overview Analysis System
 * JavaScript independiente para el sistema de análisis manual
 * SEGURO: No interfiere con el JavaScript existente
 */

// HTML Legend Plugin for custom Chart.js legends
const htmlLegendPlugin = {
    id: 'htmlLegend',
    afterUpdate(chart, args, options) {
        // Guardas de seguridad para evitar errores cuando falta el contenedor o las opciones
        if (!options || !options.containerID) {
            return;
        }

        const ul = this.getOrCreateLegendList(chart, options.containerID);
        if (!ul) {
            return;
        }
        
        // Remove old legend items
        while (ul.firstChild) {
            ul.firstChild.remove();
        }
        
        // Reuse the built-in legendItems generator
        const items = chart.options.plugins.legend.labels.generateLabels(chart);
        
        items.forEach(item => {
            const li = document.createElement('li');
            li.style.alignItems = 'center';
            li.style.cursor = 'pointer';
            li.style.display = 'flex';
            li.style.flexDirection = 'row';
            li.style.marginLeft = '12px';
            li.style.marginRight = '12px';
            
            li.onclick = () => {
                const {type} = chart.config;
                if (type === 'pie' || type === 'doughnut') {
                    chart.toggleDataVisibility(item.index);
                } else {
                    chart.setDatasetVisibility(item.datasetIndex, !chart.isDatasetVisible(item.datasetIndex));
                }
                chart.update();
            };
            
            // Color box with rectRounded style
            const boxSpan = document.createElement('span');
            boxSpan.style.background = item.fillStyle;
            boxSpan.style.borderColor = item.strokeStyle;
            boxSpan.style.borderWidth = item.lineWidth + 'px';
            boxSpan.style.borderRadius = '3px';
            boxSpan.style.display = 'inline-block';
            boxSpan.style.flexShrink = 0;
            boxSpan.style.height = '12px';
            boxSpan.style.marginRight = '8px';
            boxSpan.style.width = '12px';
            
            // Text
            const textContainer = document.createElement('span');
            textContainer.style.color = item.fontColor || '#374151';
            textContainer.style.fontSize = '12px';
            textContainer.style.fontFamily = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
            textContainer.style.fontWeight = '500';
            textContainer.style.textDecoration = item.hidden ? 'line-through' : '';
            textContainer.style.opacity = item.hidden ? '0.5' : '1';
            textContainer.textContent = item.text;
            
            li.appendChild(boxSpan);
            li.appendChild(textContainer);
            ul.appendChild(li);
        });
    },
    
    getOrCreateLegendList(chart, id) {
        const legendContainer = document.getElementById(id);
        if (!legendContainer) return null;
        
        let listContainer = legendContainer.querySelector('ul');
        if (!listContainer) {
            listContainer = document.createElement('ul');
            listContainer.style.display = 'flex';
            listContainer.style.flexDirection = 'row';
            listContainer.style.flexWrap = 'wrap';
            listContainer.style.margin = '0';
            listContainer.style.padding = '0';
            listContainer.style.listStyle = 'none';
            listContainer.style.justifyContent = 'flex-start';
            listContainer.style.alignItems = 'center';
            legendContainer.appendChild(listContainer);
        }
        return listContainer;
    }
};

class ManualAISystem {
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
            
            // 🆕 NUEVO: Clear sessionStorage as well
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
    // Modern Chart.js Configuration
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
                // ✅ NUEVO: Solo auto-refresh para usuarios con plan de pago
                if (window.currentUser && window.currentUser.plan !== 'free') {
                    console.log('🔄 Auto-refreshing projects...');
                    this.loadProjects();
                } else {
                    console.log('🆓 Auto-refresh omitido para usuario gratuito');
                }
            }
        }, 120000); // 2 minutos
        
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
                    // Close modal with Esc
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
        // ✅ NUEVO: Solo cargar proyectos para usuarios con plan de pago
        if (window.currentUser && window.currentUser.plan !== 'free') {
            console.log('💳 Usuario con plan de pago - cargando proyectos:', window.currentUser.plan);
            await this.loadProjects();
        } else {
            console.log('🆓 Usuario gratuito - mostrando estado sin proyectos');
            // Mostrar estado sin proyectos (el botón "Crear proyecto" activará paywall)
            this.showFreeUserState();
        }
        
        this.populateAnalyticsProjectSelect();
    }

    // ✅ NUEVO: Estado para usuarios gratuitos
    showFreeUserState() {
        // Ocultar loading
        this.hideElement(this.elements.projectsLoading);
        
        // Mostrar estado "sin proyectos" que es compatible con usuarios gratuitos
        this.projects = []; // Array vacío
        this.renderProjects(); // Esto mostrará el empty state con "Crear proyecto"
        
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
            // Load competitors when switching to settings
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
    // PROJECTS MANAGEMENT
    // ================================

    async loadProjects() {
        this.showElement(this.elements.projectsLoading);
        this.hideElement(this.elements.projectsContainer);
        this.hideElement(this.elements.projectsEmptyState);

        try {
            // Add timestamp to avoid browser cache
            const timestamp = new Date().getTime();
            const response = await fetch(`/manual-ai/api/projects?_t=${timestamp}`);
            const data = await response.json();

            if (data.success) {
                this.projects = data.projects;
                
                // Validate that projects in frontend still exist
                if (this.currentModalProject) {
                    const projectExists = this.projects.find(p => p.id === this.currentModalProject.id);
                    if (!projectExists) {
                        console.warn(`⚠️ Current modal project ${this.currentModalProject.id} no longer exists`);
                        this.hideProjectModal();
                        this.showError('The project you were viewing no longer exists.');
                    }
                }
                
                this.renderProjects();
                console.log('🔄 Projects loaded:', this.projects.length);
            } else {
                throw new Error(data.error || 'Failed to load projects');
            }
        } catch (error) {
            console.error('Error loading projects:', error);
            this.showError('Failed to load projects');
        } finally {
            this.hideElement(this.elements.projectsLoading);
        }
    }

    renderProjects() {
        if (this.projects.length === 0) {
            this.showElement(this.elements.projectsEmptyState);
            this.hideElement(this.elements.projectsContainer);
            return;
        }

        this.hideElement(this.elements.projectsEmptyState);
        this.showElement(this.elements.projectsContainer);

        this.elements.projectsContainer.innerHTML = this.projects.map(project => `
            <div class="project-card" data-project-id="${project.id}" onclick="manualAI.goToProjectAnalytics(${project.id})" style="cursor: pointer;">
                <div class="project-header">
                    <h3>${this.escapeHtml(project.name)}</h3>
                    <div class="project-actions">
                        <button type="button" class="btn-icon" onclick="event.stopPropagation(); manualAI.showProjectModal(${project.id})"
                                title="Project settings" aria-label="Open project settings">
                            <i class="fas fa-cog" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>
                <div class="project-details">
                    <div class="project-meta">
                        <span class="project-domain clickable-domain" title="Click to visit ${this.escapeHtml(project.domain)}" onclick="window.open('https://${this.escapeHtml(project.domain)}', '_blank')" style="cursor: pointer;">
                            <i class="fas fa-globe"></i>
                            <span class="user-domain-underline">${this.escapeHtml(project.domain)}</span>
                        </span>
                        <span class="project-country">
                            <i class="fas fa-flag"></i>
                            ${project.country_code}
                        </span>
                    </div>
                    ${project.description ? `<p class="project-description">${this.escapeHtml(project.description)}</p>` : ''}
                </div>
                <div class="project-stats">
                    <div class="stat">
                        <span class="stat-number">${project.total_keywords || 0}</span>
                        <span class="stat-label">Total Keywords</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${project.total_ai_keywords || 0}</span>
                        <span class="stat-label">AI Overview Results</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${project.aio_weight_percentage ? Math.round(project.aio_weight_percentage) + '%' : '0%'}</span>
                        <span class="stat-label">AI Overview Weight</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${project.total_mentions || 0}</span>
                        <span class="stat-label">Domain Mentions</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${project.visibility_percentage ? Math.round(project.visibility_percentage) + '%' : '0%'}</span>
                        <span class="stat-label">Visibility</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${project.avg_position ? Math.round(project.avg_position * 10) / 10 : '-'}</span>
                        <span class="stat-label">Average Position</span>
                    </div>
                </div>
                ${this.renderProjectCompetitorsHorizontal(project)}
                <div class="project-footer">
                    <small class="last-analysis">
                        Last analysis: ${project.last_analysis_date ? 
                            new Date(project.last_analysis_date).toLocaleDateString() : 'Never'}
                    </small>
                    ${(!project.last_analysis_date && (project.total_keywords || 0) > 0) ? `
                        <div class="first-run-cta" style="margin-top: 10px;">
                            <button type="button" class="btn-primary btn-small" 
                                    onclick="event.stopPropagation(); manualAI.analyzeProject(${project.id})"
                                    title="Run the first analysis for this project">
                                <i class="fas fa-play"></i>
                                Run first analysis now
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    renderProjectCompetitorsSection(project) {
        const competitorsData = project.selected_competitors || [];
        const competitorsCount = Array.isArray(competitorsData) ? competitorsData.length : 0;
        
        if (competitorsCount === 0) {
            return `
                <div class="stat competitors-stat">
                    <div class="stat-content">
                        <span class="stat-number">0</span>
                        <span class="stat-label">Competitors</span>
                    </div>
                    <div class="competitors-empty">
                        <small style="color: var(--manual-ai-gray-500); font-size: 11px;">
                            <i class="fas fa-users" style="margin-right: 4px; opacity: 0.6;"></i>
                            No competitors added yet
                        </small>
                    </div>
                </div>
            `;
        }

        // Generate competitor logos/previews with improved error handling
        const competitorLogos = competitorsData.slice(0, 4).map(domain => {
            const logoUrl = this.getDomainLogoUrl(domain);
            const firstLetter = this.escapeHtml(domain.charAt(0).toUpperCase());
            const safeDomain = this.escapeHtml(domain);
            const logoId = `logo-${project.id}-${Math.random().toString(36).substr(2, 9)}`;
            
            return `
                <div class="competitor-logo-container" title="${safeDomain}">
                    <img id="${logoId}" 
                         src="${logoUrl}" 
                         alt="${safeDomain} logo" 
                     class="competitor-logo-preview" 
                         style="display: block;"
                         onload="this.style.display='block';"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <div class="competitor-logo-fallback" style="display: none;" title="${safeDomain}">
                        ${firstLetter}
                    </div>
                </div>
            `;
        }).join('');

        // Generate competitor names with proper escaping
        const competitorNames = competitorsData.slice(0, 2).map(domain => this.escapeHtml(domain)).join(', ');
        const moreText = competitorsCount > 2 ? ` +${competitorsCount - 2} more` : '';

        return `
            <div class="stat competitors-stat">
                <div class="stat-content">
                    <span class="stat-number">${competitorsCount}</span>
                    <span class="stat-label">Competitors</span>
                </div>
                <div class="competitors-preview-section">
                    <div class="competitors-logos">
                        ${competitorLogos}
                    </div>
                    <div class="competitors-list-preview">
                        <small style="color: var(--manual-ai-gray-600); font-size: 11px; font-weight: 500; line-height: 1.3;">
                            ${competitorNames}${moreText}
                        </small>
                    </div>
                </div>
            </div>
        `;
    }

    renderProjectCompetitorsHorizontal(project) {
        const competitorsData = project.selected_competitors || [];
        const competitorsCount = Array.isArray(competitorsData) ? competitorsData.length : 0;
        
        if (competitorsCount === 0) {
            return `
                <div class="project-competitors-horizontal">
                    <h5 class="competitors-section-title">Selected Competitors</h5>
                    <small style="color: var(--manual-ai-gray-500); font-size: 11px; text-align: center; display: block; margin-top: 8px;">
                        <i class="fas fa-users" style="margin-right: 4px; opacity: 0.6;"></i>
                        No competitors added yet
                    </small>
                </div>
            `;
        }

        // Generate competitor logos/previews with improved error handling and clickable links
        const competitorLogos = competitorsData.slice(0, 4).map(domain => {
            const logoUrl = this.getDomainLogoUrl(domain);
            const firstLetter = this.escapeHtml(domain.charAt(0).toUpperCase());
            const safeDomain = this.escapeHtml(domain);
            const logoId = `logo-${project.id}-${Math.random().toString(36).substr(2, 9)}`;
            const websiteUrl = domain.startsWith('http') ? domain : `https://${domain}`;
            
            return `
                <div class="competitor-horizontal-item" title="Click to visit ${safeDomain}" onclick="window.open('${websiteUrl}', '_blank')" style="cursor: pointer;">
                    <img id="${logoId}" 
                         src="${logoUrl}" 
                         alt="${safeDomain} logo" 
                         class="competitor-horizontal-logo" 
                         style="display: block;"
                         onload="this.style.display='block';"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <div class="competitor-horizontal-fallback" style="display: none;" title="${safeDomain}">
                        ${firstLetter}
                    </div>
                    <span class="competitor-horizontal-name">${this.escapeHtml(domain)}</span>
                </div>
            `;
        }).join('');

        const moreText = competitorsCount > 4 ? ` <span class="competitors-more">+${competitorsCount - 4} more</span>` : '';

        return `
            <div class="project-competitors-horizontal">
                <h5 class="competitors-section-title">Selected Competitors</h5>
                <div class="competitors-horizontal-list">
                    ${competitorLogos}
                    ${moreText}
                </div>
            </div>
        `;
    }

    goToProjectAnalytics(projectId) {
        // Switch to Analytics tab
        this.switchTab('analytics');
        
        // Select the project in the analytics dropdown
        if (this.elements.analyticsProjectSelect) {
            this.elements.analyticsProjectSelect.value = projectId;
            
            // Trigger the analytics loading
            this.loadAnalytics();
        }
    }

    // ================================
    // PROJECT CREATION
    // ================================

    showCreateProject() {
        // ✅ NUEVO: Verificar plan antes de mostrar formulario
        if (window.currentUser && window.currentUser.plan === 'free') {
            console.log('🆓 Usuario gratuito intentó crear proyecto - mostrando paywall');
            window.showPaywall('Manual AI Analysis', ['basic','premium','business']);
            return;
        }
        
        console.log('💳 Usuario con plan - mostrando formulario de creación');
        this.elements.createProjectForm.reset();
        this.showElement(this.elements.createProjectModal);
        // Reset validation UI
        this.validateProjectDomain();
        if (this.elements.projectCountryFilter) this.elements.projectCountryFilter.value = '';
        // Focus first field for accessibility
        setTimeout(() => {
            this.elements.projectDomain?.focus();
        }, 0);
    }

    hideCreateProject() {
        this.hideElement(this.elements.createProjectModal);
    }

    async handleCreateProject(e) {
        e.preventDefault();

        const formData = new FormData(e.target);
        const projectData = Object.fromEntries(formData.entries());

        // Competitors: either auto-detect or manual chips
        const useAuto = this.elements.autoDetectCompetitors?.checked !== false;
        if (!useAuto) {
            const chips = this.getCompetitorChipValues();
            if (chips.length) projectData.competitors = chips;
        }
        projectData.auto_detect_competitors = useAuto;

        this.showProgress('Creating project...', 'Setting up your new AI analysis project');

        try {
            const response = await fetch('/manual-ai/api/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(projectData)
            });

            const data = await response.json();

            if (data.success) {
                this.hideCreateProject();
                this.showSuccess('Project created successfully!');

                // Refresh projects to include the new one
                await this.loadProjects();
                this.populateAnalyticsProjectSelect();

                const newProjectId = data.project_id;

                // Open the project modal directly in Settings to manage competitors
                if (newProjectId) {
                    this.showProjectModal(newProjectId);
                    this.switchModalTab('settings');
                    // Load competitors list (will show empty state if none)
                    await this.loadCompetitors(newProjectId);
                    // Update dashboard competitors preview as well
                    await this.loadCompetitorsPreview(newProjectId);
        } else {
            // Fallback: ensure at least competitors preview updates
            this.switchTab('projects');
        }
            } else {
                throw new Error(data.error || 'Failed to create project');
            }
        } catch (error) {
            console.error('Error creating project:', error);
            this.showError(error.message || 'Failed to create project');
        } finally {
            this.hideProgress();
        }
    }

    // ================================
    // UX HELPERS: Domain + Country filter
    // ================================
    normalizeProjectDomain() {
        const input = this.elements.projectDomain;
        if (!input) return;
        let v = (input.value || '').trim().toLowerCase();
        if (!v) return;
        try {
            // Strip scheme and path
            v = v.replace(/^https?:\/\//, '').replace(/^www\./, '');
            // Keep only host part
            v = v.split('/')[0].split('?')[0];
            input.value = v;
        } catch (_) {}
    }

    validateProjectDomain() {
        const input = this.elements.projectDomain;
        const hint = this.elements.projectDomainHint;
        const submitBtn = this.elements.createProjectSubmit;
        if (!input || !hint) return;

        const v = (input.value || '').trim().toLowerCase();
        if (!v) {
            hint.textContent = '';
            if (submitBtn) submitBtn.disabled = true;
            return false;
        }

        // Simple domain regex (hostname without scheme)
        const domainRegex = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/i;
        const looksLikeUrl = /^https?:\/\//i.test(v);

        if (looksLikeUrl) {
            hint.textContent = 'We removed https:// and path automatically.';
        } else {
            hint.textContent = '';
        }

        const normalized = v.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
        const isValid = domainRegex.test(normalized);

        input.classList.toggle('input-error', !isValid);
        input.classList.toggle('input-ok', isValid);
        if (submitBtn) submitBtn.disabled = !isValid || !this.elements.projectCountry?.value;
        return isValid;
    }

    filterCountryOptions() {
        const filter = (this.elements.projectCountryFilter?.value || '').toLowerCase();
        const select = this.elements.projectCountry;
        if (!select) return;
        const options = Array.from(select.options);
        options.forEach(opt => {
            const text = (opt.textContent || '').toLowerCase();
            const show = !filter || text.includes(filter);
            opt.hidden = !show;
        });
    }

    // ================================
    // Competitor chips
    // ================================
    addCompetitorChip() {
        if (!this.elements.competitorInput || !this.elements.competitorChips) return;
        const raw = (this.elements.competitorInput.value || '').trim().toLowerCase();
        if (!raw) return;
        const normalized = this.normalizeDomainString(raw);
        if (!this.isValidDomain(normalized)) {
            this.setCompetitorError('Invalid domain format. Example: competitor.com');
            return;
        }
        const existing = this.getCompetitorChipValues();
        if (existing.includes(normalized)) {
            this.setCompetitorError('This domain is already added');
            return;
        }
        if (existing.length >= 4) {
            this.setCompetitorError('Maximum 4 competitors');
            return;
        }
        this.setCompetitorError('');
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = normalized;
        chip.setAttribute('role', 'button');
        chip.setAttribute('tabindex', '0');
        chip.style.padding = '6px 10px';
        chip.style.border = '1px solid #e5e7eb';
        chip.style.borderRadius = '9999px';
        chip.style.background = '#f9fafb';
        chip.style.cursor = 'pointer';
        chip.style.userSelect = 'none';

        const remove = () => chip.remove();
        chip.addEventListener('click', remove);
        chip.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' || e.key === 'Delete' || e.key === 'Enter') {
                e.preventDefault();
                remove();
            }
        });
        this.elements.competitorChips.appendChild(chip);
        this.elements.competitorInput.value = '';
    }

    getCompetitorChipValues() {
        if (!this.elements.competitorChips) return [];
        return Array.from(this.elements.competitorChips.querySelectorAll('.chip')).map(el => el.textContent || '').filter(Boolean);
    }

    setCompetitorError(msg) {
        if (this.elements.competitorError) this.elements.competitorError.textContent = msg || '';
    }

    normalizeDomainString(value) {
        let v = (value || '').trim().toLowerCase();
        v = v.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
        return v;
    }

    isValidDomain(v) {
        const re = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/i;
        return re.test(v);
    }

    // ================================
    // PROJECT DETAILS
    // ================================

    async showProjectDetails(projectId) {
        this.currentProject = this.projects.find(p => p.id === projectId);
        
        if (!this.currentProject) {
            this.showError('Project not found');
            return;
        }

        document.getElementById('projectDetailsTitle').textContent = this.currentProject.name;
        this.showElement(this.elements.projectDetailsModal);

        // Load keywords by default
        await this.loadProjectKeywords(projectId);
    }

    hideProjectDetails() {
        this.hideElement(this.elements.projectDetailsModal);
        this.currentProject = null;
    }

    async loadProjectKeywords(projectId) {
        const keywordsList = document.getElementById('keywordsList');
        keywordsList.innerHTML = '<div class="loading-small"><i class="fas fa-spinner fa-spin"></i> Loading keywords...</div>';

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/keywords`);
            const data = await response.json();

            if (data.success) {
                this.renderKeywords(data.keywords);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading keywords:', error);
            keywordsList.innerHTML = '<div class="error-message">Failed to load keywords</div>';
        }
    }

    renderKeywords(keywords) {
        const keywordsList = document.getElementById('keywordsList');
        
        if (keywords.length === 0) {
            keywordsList.innerHTML = `
                <div class="empty-keywords">
                    <i class="fas fa-key"></i>
                    <p>No keywords added yet</p>
                    <button type="button" class="btn-primary btn-sm" onclick="manualAI.showAddKeywords()">
                        <i class="fas fa-plus"></i>
                        Add First Keywords
                    </button>
                </div>
            `;
            return;
        }

        keywordsList.innerHTML = `
            <div class="keywords-header-stats">
                <span>${keywords.length} keywords total</span>
                <span>${keywords.filter(k => k.is_active).length} active</span>
            </div>
            <div class="keywords-table">
                <div class="keywords-table-header">
                    <div class="col-keyword">Keyword</div>
                    <div class="col-analyses">Analyses</div>
                    <div class="col-frequency">AI Frequency</div>
                    <div class="col-last">Last Analysis</div>
                    <div class="col-actions">Actions</div>
                </div>
                <div class="keywords-table-body">
                    ${keywords.map(keyword => `
                        <div class="keyword-row ${!keyword.is_active ? 'disabled' : ''}">
                            <div class="col-keyword">${this.escapeHtml(keyword.keyword)}</div>
                            <div class="col-analyses">${keyword.analysis_count || 0}</div>
                            <div class="col-frequency">
                                ${keyword.ai_overview_frequency ? 
                                    Math.round(keyword.ai_overview_frequency * 100) + '%' : 
                                    '-'}
                            </div>
                            <div class="col-last">
                                ${keyword.last_analysis_date ? 
                                    new Date(keyword.last_analysis_date).toLocaleDateString() : 
                                    'Never'}
                            </div>
                            <div class="col-actions">
                                <button type="button" class="btn-icon btn-sm" 
                                        onclick="manualAI.toggleKeyword(${keyword.id})"
                                        title="${keyword.is_active ? 'Disable' : 'Enable'} keyword">
                                    <i class="fas fa-${keyword.is_active ? 'pause' : 'play'}"></i>
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    async loadProjectResults(projectId) {
        const resultsContent = document.getElementById('resultsContent');
        resultsContent.innerHTML = '<div class="loading-small"><i class="fas fa-spinner fa-spin"></i> Loading results...</div>';

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/results`);
            const data = await response.json();

            if (data.success) {
                this.renderResults(data.results);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading results:', error);
            resultsContent.innerHTML = '<div class="error-message">Failed to load analysis results</div>';
        }
    }

    renderResults(results) {
        const resultsContent = document.getElementById('resultsContent');
        
        if (results.length === 0) {
            resultsContent.innerHTML = `
                <div class="empty-keywords">
                    <i class="fas fa-chart-bar"></i>
                    <p>No analysis results yet</p>
                    <button type="button" class="btn-primary btn-sm" onclick="manualAI.runAnalysis()">
                        <i class="fas fa-play"></i>
                        Run First Analysis
                    </button>
                </div>
            `;
            return;
        }

        // Group results by date
        const resultsByDate = {};
        results.forEach(result => {
            const date = result.analysis_date;
            if (!resultsByDate[date]) {
                resultsByDate[date] = [];
            }
            resultsByDate[date].push(result);
        });

        const sortedDates = Object.keys(resultsByDate).sort((a, b) => new Date(b) - new Date(a));

        resultsContent.innerHTML = `
            <div class="results-summary">
                <div class="summary-stats">
                    <div class="stat">
                        <span class="stat-number">${results.length}</span>
                        <span class="stat-label">Total Results</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${results.filter(r => r.has_ai_overview).length}</span>
                        <span class="stat-label">AI Overview</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${results.filter(r => r.domain_mentioned).length}</span>
                        <span class="stat-label">Domain Mentions</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${sortedDates.length}</span>
                        <span class="stat-label">Analysis Days</span>
                    </div>
                </div>
            </div>
            
            <div class="results-by-date">
                ${sortedDates.map(date => `
                    <div class="date-group">
                        <div class="date-header">
                            <h5>${new Date(date).toLocaleDateString()}</h5>
                            <span class="date-stats">
                                ${resultsByDate[date].length} keywords analyzed
                            </span>
                        </div>
                        <div class="results-table">
                            <div class="results-table-header">
                                <div class="col-keyword">Keyword</div>
                                <div class="col-ai">AI Overview</div>
                                <div class="col-mentioned">Mentioned</div>
                                <div class="col-position">Position</div>
                                <div class="col-impact">Impact</div>
                            </div>
                            <div class="results-table-body">
                                ${resultsByDate[date].map(result => `
                                    <div class="result-row">
                                        <div class="col-keyword">${this.escapeHtml(result.keyword)}</div>
                                        <div class="col-ai">
                                            <span class="status-badge ${result.has_ai_overview ? 'status-yes' : 'status-no'}">
                                                ${result.has_ai_overview ? 'Yes' : 'No'}
                                            </span>
                                        </div>
                                        <div class="col-mentioned">
                                            <span class="status-badge ${result.domain_mentioned ? 'status-yes' : 'status-no'}">
                                                ${result.domain_mentioned ? 'Yes' : 'No'}
                                            </span>
                                        </div>
                                        <div class="col-position">
                                            ${result.domain_position ? `#${result.domain_position}` : '-'}
                                        </div>
                                        <div class="col-impact">
                                            <span class="impact-score impact-${result.impact_score >= 70 ? 'high' : result.impact_score >= 40 ? 'medium' : 'low'}">
                                                ${result.impact_score || 0}
                                            </span>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // ================================
    // KEYWORDS MANAGEMENT
    // ================================

    showAddKeywords() {
        this.elements.addKeywordsForm.reset();
        this.updateKeywordsCounter();
        this.showElement(this.elements.addKeywordsModal);
    }

    hideAddKeywords() {
        this.hideElement(this.elements.addKeywordsModal);
    }

    updateKeywordsCounter() {
        const textarea = document.getElementById('keywordsTextarea');
        const counter = document.getElementById('keywordsCount');
        
        if (textarea && counter) {
            const keywords = textarea.value.split('\n').filter(k => k.trim().length > 0);
            counter.textContent = keywords.length;
        }
    }

    async handleAddKeywords(e) {
        e.preventDefault();

        if (!this.currentProject) {
            this.showError('No project selected');
            return;
        }

        const textarea = document.getElementById('keywordsTextarea');
        const keywords = textarea.value.split('\n')
            .map(k => k.trim())
            .filter(k => k.length > 0);

        if (keywords.length === 0) {
            this.showError('Please enter at least one keyword');
            return;
        }

        this.showProgress('Adding keywords...', `Adding ${keywords.length} keywords to project`);

        try {
            const response = await fetch(`/manual-ai/api/projects/${this.currentProject.id}/keywords`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ keywords })
            });

            const data = await response.json();

            if (data.success) {
                this.hideAddKeywords();
                this.showSuccess(`${data.added_count} keywords added successfully!`);
                await this.loadProjectKeywords(this.currentProject.id);
                await this.loadProjects(); // Refresh project stats
            } else {
                throw new Error(data.error || 'Failed to add keywords');
            }
        } catch (error) {
            console.error('Error adding keywords:', error);
            this.showError(error.message || 'Failed to add keywords');
        } finally {
            this.hideProgress();
        }
    }

    // ================================
    // ANALYSIS
    // ================================

    async analyzeProject(projectId) {
        const project = this.projects.find(p => p.id === projectId);
        
        if (!project) {
            this.showError('Project not found');
            return;
        }

        this.showProgress('Running analysis...', 
            `Analyzing ${project.keyword_count} keywords for AI Overview visibility. This may take several minutes.`);

        // Start a backup polling system in case main request fails
        const startTime = Date.now();
        const backupPolling = setInterval(async () => {
            try {
                await this.loadProjects();
                const updatedProject = this.projects.find(p => p.id === projectId);
                
                // Check if project has new analysis data (very basic check)
                if (updatedProject && updatedProject.total_results > project.total_results) {
                    console.log('📡 Backup polling detected analysis completion');
                    clearInterval(backupPolling);
                    this.completeProgressBar();
                    setTimeout(() => this.hideProgress(), 400);
                    this.showSuccess('Analysis completed! Results detected via backup monitoring.');
                    
                    // Refresh analytics if needed
                    if (this.elements.analyticsProjectSelect.value == projectId) {
                        await this.loadAnalytics();
                    }
                }
                
                // Stop polling after 10 minutes
                if (Date.now() - startTime > 600000) {
                    clearInterval(backupPolling);
                }
            } catch (pollError) {
                console.error('Backup polling error:', pollError);
            }
        }, 30000); // Check every 30 seconds

        let analysisCompleted = false;
        try {
            // Create AbortController for timeout management
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1800000); // 30 minutes timeout for up to 200 keywords
            
            const response = await fetch(`/manual-ai/api/projects/${projectId}/analyze`, {
                method: 'POST',
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            clearTimeout(timeoutId);

            const data = await response.json();

            // ✅ NUEVO FASE 4.5: Manejar paywalls (402)
            if (response.status === 402) {
                clearInterval(backupPolling);
                this.hideProgress();
                
                console.warn(`🚫 Manual AI analysis blocked by paywall: ${data.error}`);
                
                // Mostrar paywall si está disponible
                if (window.showPaywall) {
                    window.showPaywall('Manual AI Analysis', data.upgrade_options || ['basic','premium','business']);
                }
                
                this.showToast('Manual AI Analysis requires a paid plan. Please upgrade to continue.', 'error', 8000);
                return;
            }

            // ✅ FASE 4: Manejar errores de quota específicamente
            if (response.status === 429 && data.quota_exceeded) {
                clearInterval(backupPolling);
                this.hideProgress();
                
                const quotaInfo = data.quota_info || {};
                const analyzed = data.keywords_analyzed || 0;
                const remaining = data.keywords_remaining || 0;
                
                console.warn(`🚫 Manual AI analysis blocked by quota: ${data.error}`);
                
                // Mostrar UI de quota si está disponible
                if (window.QuotaUI) {
                    window.QuotaUI.showBlockModal({
                        error: data.error,
                        quota_blocked: true,
                        quota_info: quotaInfo,
                        action_required: data.action_required || 'upgrade'
                    });
                }
                
                // Mostrar mensaje específico de quota
                const quotaMessage = analyzed > 0 
                    ? `Analysis stopped due to quota limit. ${analyzed} keywords were analyzed successfully before reaching the limit. ${remaining} keywords remain.`
                    : `Analysis blocked: You have reached your monthly quota limit. Please upgrade your plan to continue.`;
                    
                this.showError(quotaMessage);
                
                // Refresh project stats en caso de que se hayan analizado algunas keywords
                if (analyzed > 0) {
                    await this.loadProjects();
                    
                    // Refresh analytics if needed
                    if (this.elements.analyticsProjectSelect.value == projectId) {
                        await this.loadAnalytics();
                    }
                }
                
                return; // No continuar con el flujo normal
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            if (data.success) {
                clearInterval(backupPolling); // Stop backup polling
                analysisCompleted = true;
                this.completeProgressBar();
                this.showSuccess(`Analysis completed! Processed ${data.results_count} keywords`);
                await this.loadProjects(); // Refresh project stats
                
                // If analytics tab is active and this project is selected, refresh charts
                if (this.elements.analyticsProjectSelect.value == projectId) {
                    await this.loadAnalytics();
                }
            } else {
                throw new Error(data.error || 'Analysis failed');
            }
        } catch (error) {
            console.error('Error running analysis:', error);
            
            // Handle different types of errors
            let errorMessage = 'Analysis failed';
            if (error.name === 'AbortError') {
                errorMessage = 'Analysis timeout (30 minutes). This usually indicates a server or network issue. Consider running the analysis during off-peak hours.';
            } else if (error.message.includes('Failed to fetch') || error.message.includes('ERR_NETWORK_CHANGED')) {
                // Network error - check if analysis actually completed
                console.log('🔍 Network error detected, checking if analysis completed...');
                try {
                    // Wait a moment and check if we have new results
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    await this.loadProjects(); // Refresh project stats
                    
                    // If analytics tab is active, refresh it too
                    if (this.elements.analyticsProjectSelect.value == projectId) {
                        await this.loadAnalytics();
                    }
                    
                    this.showSuccess('Analysis may have completed despite network error. Please check the Results tab.');
                    return; // Don't show error if we managed to refresh
                } catch (refreshError) {
                    console.error('Failed to refresh after network error:', refreshError);
                }
                errorMessage = 'Network connection lost during analysis. Analysis might have completed - please check the Results tab.';
            } else if (error.message.includes('HTTP')) {
                errorMessage = `Server error: ${error.message}`;
            } else {
                errorMessage = error.message || 'Analysis failed';
            }
            
            this.showError(errorMessage);
        } finally {
            clearInterval(backupPolling); // Stop backup polling in all cases
            if (analysisCompleted) {
                this.completeProgressBar();
                setTimeout(() => this.hideProgress(), 400);
            } else {
                this.hideProgress();
            }
        }
    }



    // ================================
    // ANALYTICS
    // ================================

    populateAnalyticsProjectSelect() {
        if (!this.elements.analyticsProjectSelect) return;

        this.elements.analyticsProjectSelect.innerHTML = `
            <option value="">Select a project...</option>
            ${this.projects.map(project => `
                <option value="${project.id}">${this.escapeHtml(project.name)}</option>
            `).join('')}
        `;
    }

    async loadAnalytics() {
        const projectId = this.elements.analyticsProjectSelect?.value;
        const days = this.elements.analyticsTimeRange?.value || 30;

        if (!projectId) {
            this.elements.analyticsContent.innerHTML = `
                <div class="analytics-empty">
                    <i class="fas fa-chart-line"></i>
                    <p>Select a project to view analytics</p>
                </div>
            `;
            this.hideElement(this.elements.chartsContainer);
            this.showDownloadButton(false); // Hide download button when no project selected
            return;
        }

        this.elements.analyticsContent.innerHTML = `
            <div class="loading-analytics">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading analytics data...</p>
            </div>
        `;

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/stats?days=${days}`);
            const data = await response.json();

            if (data.success) {
                this.renderAnalytics(data.stats);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading analytics:', error);
            this.elements.analyticsContent.innerHTML = `
                <div class="analytics-error">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Failed to load analytics data</p>
                </div>
            `;
            this.showDownloadButton(false); // Hide download button on error
        }
    }

    renderAnalytics(stats) {
        console.log('📊 Rendering analytics data:', stats);
        
        // Update summary cards — ahora desde endpoint "latest" (ignora rango)
        const projectIdForLatest = stats.project_id || parseInt(this.elements.analyticsProjectSelect?.value) || this.currentProject?.id;
        if (projectIdForLatest) {
            const latestToken = Date.now();
            this._latestOverviewToken = latestToken;
            fetch(`/manual-ai/api/projects/${projectIdForLatest}/stats-latest`)
                .then(r => r.json())
                .then(latest => {
                    if (this._latestOverviewToken !== latestToken) return; // evitar pisado por race
                    const ms = latest?.main_stats || {};
                    const totalKeywords = Number(ms.total_keywords) || 0;
                    const totalAi = Number(ms.total_ai_keywords) || 0;
                    const totalMentions = Number(ms.total_mentions) || 0;
                    const avgPos = (ms.avg_position !== null && ms.avg_position !== undefined) ? Number(ms.avg_position) : null;
                    const aioWeightPct = (ms.aio_weight_percentage !== null && ms.aio_weight_percentage !== undefined) ? Number(ms.aio_weight_percentage) : null;
                    const visPctRaw = (ms.visibility_percentage !== null && ms.visibility_percentage !== undefined) ? Number(ms.visibility_percentage) : null;
                    
                    this.updateSummaryCard('totalKeywords', totalKeywords);
                    this.updateSummaryCard('aiKeywords', totalAi);
                    this.updateSummaryCard('domainMentions', totalMentions);
                    // Mostrar visibilidad con base en último análisis si viene calculada
                    const visPct = (typeof ms.visibility_percentage === 'number') ? ms.visibility_percentage : ms.aio_weight_percentage;
                    this.updateSummaryCard('visibilityPercentage', typeof visPct === 'number' ? Math.round(visPct) + '%' : '0%');
                    this.updateSummaryCard('averagePosition',
                        typeof ms.avg_position === 'number' ? Math.round(ms.avg_position * 10) / 10 : '-');
                    this.updateSummaryCard('aioWeight',
                        typeof ms.aio_weight_percentage === 'number' ? Math.round(ms.aio_weight_percentage) + '%' : '0%');

                    // Badge "Latest analysis"
                    const header = document.querySelector('.overview-section .section-header p.section-description');
                    if (header) {
                        const dt = ms.last_analysis_date ? new Date(ms.last_analysis_date).toLocaleDateString() : '';
                        header.textContent = `Data from the latest analysis${dt ? ' (' + dt + ')' : ''}`;
                    }
                })
                .catch(() => {/* silencioso */});
        }

        // Show charts container
        this.hideElement(this.elements.analyticsContent);
        this.showElement(this.elements.chartsContainer);

        // Get project ID from stats or current selection
        const projectId = stats.project_id || parseInt(this.elements.analyticsProjectSelect?.value) || this.currentProject?.id;
        if (!projectId) {
            console.warn('No project ID available for analytics rendering');
            return;
        }

        console.log(`📈 Loading analytics components for project ${projectId}`);

        // Store current analytics data for Excel export
        this.currentAnalyticsData = {
            projectId: projectId,
            stats: stats,
            days: this.elements.analyticsTimeRange?.value || 30
        };

        // Show download button when analytics data is loaded
        this.showDownloadButton(true);

        // Render main charts with events annotations
        if (stats.visibility_chart && Array.isArray(stats.visibility_chart)) {
            this.renderVisibilityChart(stats.visibility_chart, stats.events || []);
        } else {
            console.warn('No visibility chart data available');
        }

        if (stats.positions_chart && Array.isArray(stats.positions_chart)) {
            this.renderPositionsChart(stats.positions_chart, stats.events || []);
        } else {
            console.warn('No positions chart data available');
        }

        // Load all competitive analysis components in parallel
        this.loadAnalyticsComponents(projectId);
    }

    updateSummaryCard(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
        } else {
            console.warn(`Summary card element not found: ${elementId}`);
        }
    }

    async loadAnalyticsComponents(projectId) {
        console.log(`🔄 Loading analytics components for project ${projectId}`);
        
        try {
            // Load all components in parallel for better performance
            const promises = [
                this.loadGlobalDomainsRanking(projectId),
                this.loadComparativeCharts(projectId),
                this.loadCompetitorsPreview(projectId),
                this.loadAIOverviewKeywordsTable(projectId),
                this.loadClustersStatistics(projectId)  // ✨ NEW: Clusters statistics
            ];

            await Promise.allSettled(promises);
            console.log('✅ All analytics components loaded');

        } catch (error) {
            console.error('Error loading analytics components:', error);
        }
    }

    renderVisibilityChart(data, events = []) {
        const canvasEl = document.getElementById('visibilityChart');
        if (!canvasEl || !data || data.length === 0) return;

        const ctx = canvasEl.getContext('2d');
        
        // Destroy existing chart (limpiando listeners previos primero)
        if (this.charts.visibility) {
            this.clearEventAnnotations(this.charts.visibility);
            this.charts.visibility.destroy();
        }

        // Modern Chart.js configuration with HTML Legend
        const config = this.getModernChartConfig(true, 'visibilityLegend');
        
        this.charts.visibility = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => new Date(d.analysis_date).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric' 
                })),
                datasets: [{
                    label: 'Keywords with AI Overview',
                    data: data.map(d => d.ai_keywords || 0),
                    borderColor: '#5BF0AF',
                    backgroundColor: 'rgba(91, 240, 175, 0.12)',
                    pointBackgroundColor: '#5BF0AF',
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: '#45D190',
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    fill: 'start',
                    tension: 0.4
                }, {
                    label: 'Domain Mentions',
                    data: data.map(d => d.mentions || 0),
                    borderColor: '#F0715B',
                    backgroundColor: 'rgba(240, 113, 91, 0.12)',
                    pointBackgroundColor: '#F0715B',
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: '#E55A42',
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    fill: 'start',
                    tension: 0.4
                }]
            },
            plugins: [htmlLegendPlugin],
            options: {
                ...config,
                scales: {
                    ...config.scales,
                    y: {
                        ...config.scales.y,
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Count',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        },
                        ticks: {
                            ...config.scales.y.ticks,
                            callback: function(value) {
                                return Math.round(value);
                            }
                        }
                    },
                    x: {
                        ...config.scales.x,
                        title: {
                            display: true,
                            text: 'Date',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        }
                    }
                },
                plugins: {
                    ...config.plugins,
                    tooltip: {
                        ...config.plugins.tooltip,
                        callbacks: {
                            title: function(context) {
                                return new Date(data[context[0].dataIndex].analysis_date).toLocaleDateString('en-US', {
                                    weekday: 'short',
                                    year: 'numeric',
                                    month: 'short',
                                    day: 'numeric'
                                });
                            },
                            label: function(context) {
                                const datasetLabel = context.dataset.label;
                                const value = Math.round(context.raw);
                                
                                if (datasetLabel === 'Keywords with AI Overview') {
                                    return `Keywords with AI Overview: ${value}`;
                                } else if (datasetLabel === 'Domain Mentions') {
                                    return `Domain Mentions: ${value}`;
                                }
                                return `${datasetLabel}: ${value}`;
                            }
                        }
                    }
                }
            }
        });

        // 🔄 Limpiar anotaciones y listeners anteriores siempre que re-renderizamos
        this.clearEventAnnotations(this.charts.visibility);

        // ✅ MEJORADO: Aplicar anotaciones de eventos de keywords
        if (events && events.length > 0) {
            const annotations = this.createEventAnnotations(data, events);
            if (annotations && annotations.length > 0) {
                // ✅ MEJORADO: Registrar plugin usando Chart.js 3.x+ API
                if (!Chart.registry.plugins.get('keywordEventAnnotations')) {
                    Chart.register({
                        id: 'keywordEventAnnotations',
                        afterDraw: (chart) => {
                            const annotationsData = chart.options.annotationsData;
                            if (annotationsData && annotationsData.length > 0) {
                                this.drawEventAnnotations(chart, annotationsData);
                            }
                        }
                    });
                }
                
                // Guardar anotaciones en las opciones del chart
                this.charts.visibility.options.annotationsData = annotations;
                
                // Configurar eventos de mouse para tooltips
                setTimeout(() => {
                    this.showEventAnnotations(this.charts.visibility, annotations);
                }, 100);
                
                // Re-render con las anotaciones
                this.charts.visibility.update();
            }
        } else {
            // Asegurar estado limpio cuando no hay eventos
            this.charts.visibility.options.annotationsData = [];
            this.clearEventAnnotations(this.charts.visibility);
        }
    }

    renderPositionsChart(data, events = []) {
        const canvasEl = document.getElementById('positionsChart');
        if (!canvasEl || !data || data.length === 0) return;

        const ctx = canvasEl.getContext('2d');
        
        // Destroy existing chart
        if (this.charts.positions) {
            this.charts.positions.destroy();
        }

        // Modern Chart.js configuration with modern colors
        const config = this.getModernChartConfig(true, 'positionsLegend');
        
        this.charts.positions = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => new Date(d.analysis_date).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric' 
                })),
                datasets: [
                    {
                        label: 'Position 1-3',
                        data: data.map(d => d.pos_1_3 || 0),
                        borderColor: '#5BF0AF',
                        backgroundColor: 'rgba(91, 240, 175, 0.12)',
                        pointBackgroundColor: '#5BF0AF',
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: '#45D190',
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'rectRounded',
                        fill: 'start',
                        tension: 0.4
                    },
                    {
                        label: 'Position 4-10',
                        data: data.map(d => d.pos_4_10 || 0),
                        borderColor: '#1851F1',
                        backgroundColor: 'rgba(24, 81, 241, 0.12)',
                        pointBackgroundColor: '#1851F1',
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: '#1040D6',
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'rectRounded',
                        fill: 'start',
                        tension: 0.4
                    },
                    {
                        label: 'Position 11-20',
                        data: data.map(d => d.pos_11_20 || 0),
                        borderColor: '#F0715B',
                        backgroundColor: 'rgba(240, 113, 91, 0.12)',
                        pointBackgroundColor: '#F0715B',
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: '#E55A42',
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'rectRounded',
                        fill: 'start',
                        tension: 0.4
                    },
                    {
                        label: 'Position 21+',
                        data: data.map(d => d.pos_21_plus || 0),
                        borderColor: '#8EAA96',
                        backgroundColor: 'rgba(142, 170, 150, 0.12)',
                        pointBackgroundColor: '#8EAA96',
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: '#6B8A77',
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'rectRounded',
                        fill: 'start',
                        tension: 0.4
                    }
                ]
            },
            plugins: [htmlLegendPlugin],
            options: {
                ...config,
                scales: {
                    ...config.scales,
                    y: {
                        ...config.scales.y,
                        beginAtZero: true,
                        stacked: true,
                        title: {
                            display: true,
                            text: 'Number of Keywords',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        }
                    },
                    x: {
                        ...config.scales.x,
                        title: {
                            display: true,
                            text: 'Date',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        }
                    }
                },
                plugins: {
                    ...config.plugins,
                    tooltip: {
                        ...config.plugins.tooltip,
                        callbacks: {
                            title: function(context) {
                                return new Date(data[context[0].dataIndex].analysis_date).toLocaleDateString('en-US', {
                                    weekday: 'short',
                                    year: 'numeric',
                                    month: 'short',
                                    day: 'numeric'
                                });
                            },
                            label: function(context) {
                                return `${context.dataset.label}: ${context.raw} keywords`;
                            }
                        }
                    }
                }
            }
        });

        // ❌ REMOVIDO: No queremos anotaciones en la gráfica de posiciones
    }

    // ================================
    // EVENT ANNOTATIONS
    // ================================

    createEventAnnotations(chartData, events) {
        if (!events || events.length === 0) return [];
        
        // ✅ MEJORADO: Eventos de cambios de keywords Y notas manuales
        const relevantEvents = events.filter(event => 
            event.event_type === 'keywords_added' ||
            event.event_type === 'keyword_deleted' ||
            event.event_type === 'keywords_removed' ||
            event.event_type === 'manual_note_added'  // ✅ NUEVO: Incluir notas manuales
        );
        
        if (relevantEvents.length === 0) return [];
        
        const chartDates = chartData.map(d => new Date(d.analysis_date).toDateString());
        
        return relevantEvents.map(event => {
            const eventDate = new Date(event.event_date).toDateString();
            const dateIndex = chartDates.indexOf(eventDate);
            
            // ✅ CORREGIDO: Solo crear anotación si la fecha del evento coincide con datos del chart
            if (dateIndex === -1) return null;
            
            return {
                x: dateIndex,
                title: event.event_title,
                type: event.event_type,
                keywords: event.keywords_affected,
                date: eventDate,
                event: event, // Incluir evento completo para tooltips
            };
        }).filter(Boolean);
    }

    drawEventAnnotations(chart, annotations) {
        if (!annotations || annotations.length === 0) return;
        
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;
        
        annotations.forEach(annotation => {
            // ✅ MEJORADO: Calcular posición correcta basada en el índice de datos
            const xPos = chart.scales.x.getPixelForValue(annotation.x);
            
            if (xPos < chartArea.left || xPos > chartArea.right) return; // Skip if outside chart
            
            // ✅ MEJORADO: Línea vertical más visible
            ctx.save();
            ctx.strokeStyle = this.getEventColor(annotation.type);
            ctx.lineWidth = 3;  // Más gruesa
            ctx.setLineDash([8, 4]); // Línea más definida
            ctx.globalAlpha = 0.8;
            ctx.beginPath();
            ctx.moveTo(xPos, chartArea.top);
            ctx.lineTo(xPos, chartArea.bottom);
            ctx.stroke();
            
            // ✅ MEJORADO: Círculo de fondo para el icono
            ctx.globalAlpha = 1;
            ctx.fillStyle = this.getEventColor(annotation.type);
            ctx.beginPath();
            ctx.arc(xPos, chartArea.top - 12, 10, 0, 2 * Math.PI);
            ctx.fill();
            
            // ✅ MEJORADO: Icono de warning más visible
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 14px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(this.getEventIcon(annotation.type), xPos, chartArea.top - 12);
            
            ctx.restore();
        });
    }

    getEventColor(eventType) {
        const colors = {
            'keywords_added': '#F59E0B',     // ✅ Warning orange para cambios de keywords
            'keyword_deleted': '#F59E0B',   // ✅ Warning orange para eliminación de keywords
            'keywords_removed': '#F59E0B',  // ✅ Warning orange para cambios de keywords
            'manual_note_added': '#3B82F6', // ✅ NUEVO: Azul para notas manuales del usuario
            'project_created': '#4F46E5',   // Blue
            'daily_analysis': '#6B7280',    // Gray
            'analysis_failed': '#EF4444',   // Red para errores reales
            'competitors_changed': '#8B5CF6', // ✅ Purple para cambios de competidores
            'competitors_updated': '#8B5CF6'  // ✅ Purple para actualizaciones de competidores
        };
        return colors[eventType] || '#6B7280';
    }

    getEventIcon(eventType) {
        const icons = {
            'keywords_added': '⚠',           // ✅ Warning para cambios de keywords
            'keyword_deleted': '⚠',         // ✅ Warning para eliminación de keywords
            'keywords_removed': '⚠',        // ✅ Warning para cambios de keywords
            'manual_note_added': '📝',       // ✅ NUEVO: Icono de nota para anotaciones manuales
            'project_created': '⭐',
            'daily_analysis': '📊',
            'analysis_failed': '⚠',
            'competitors_changed': '🔄',     // ✅ Icono para cambios de competidores
            'competitors_updated': '🔄'      // ✅ Icono para actualizaciones de competidores
        };
        return icons[eventType] || '•';
    }

    // 🧹 NUEVO: Limpieza segura de listeners y tooltip de anotaciones
    clearEventAnnotations(chart) {
        if (!chart) return;
        const canvas = chart.canvas;
        if (chart._annotationHandlers) {
            try {
                canvas.removeEventListener('mousemove', chart._annotationHandlers.onMouseMove);
                canvas.removeEventListener('mouseleave', chart._annotationHandlers.onMouseLeave);
            } catch (_) { /* noop */ }
            chart._annotationHandlers = null;
        }
        // Ocultar tooltip si existe
        const tooltip = document.getElementById('chart-annotation-tooltip');
        if (tooltip) tooltip.style.opacity = 0;
        // Limpiar datos de anotaciones por si el plugin los lee
        if (chart.options) chart.options.annotationsData = [];
    }

    showEventAnnotations(chart, annotations) {
        // Enhanced tooltip functionality for annotations
        const canvas = chart.canvas;
        const ctx = chart.ctx;
        
        // Create tooltip element if it doesn't exist
        let tooltip = document.getElementById('chart-annotation-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'chart-annotation-tooltip';
            tooltip.style.cssText = `
                position: fixed;
                background: rgba(0, 0, 0, 0.92);
                color: white;
                padding: 12px 16px;
                border-radius: 8px;
                font-size: 13px;
                line-height: 1.5;
                max-width: 280px;
                min-width: 200px;
                z-index: 10000;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.2s ease;
                white-space: pre-wrap;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.1);
            `;
            document.body.appendChild(tooltip);
        }
        
        // Mouse move handler for tooltip
        const onMouseMove = (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Check if mouse is over any annotation
            let hoveredAnnotation = null;
            const chartArea = chart.chartArea;
            
            for (const annotation of annotations) {
                // ✅ CORREGIDO: Usar la posición correcta de la anotación
                const annotationX = chart.scales.x.getPixelForValue(annotation.x);
                
                // ✅ MEJORADO: Área de detección más amplia para facilitar interacción
                if (Math.abs(x - annotationX) <= 20 && y >= chartArea.top - 30 && y <= chartArea.bottom + 10) {
                    hoveredAnnotation = annotation;
                    break;
                }
            }
            
            if (hoveredAnnotation) {
                // ✅ CORREGIDO: Mostrar el texto que el usuario añadió
                const eventTitle = hoveredAnnotation.event.event_title || 'Cambio en Keywords';
                const userDescription = hoveredAnnotation.event.event_description;
                const eventDate = new Date(hoveredAnnotation.event.event_date).toLocaleDateString('es-ES', {
                    weekday: 'short',
                    year: 'numeric', 
                    month: 'short',
                    day: 'numeric'
                });
                const eventType = hoveredAnnotation.event.event_type;
                const keywordsAffected = hoveredAnnotation.event.keywords_affected || 0;
                
                // Debug solo cuando hay descripción del usuario para verificar que funciona
                if (userDescription && userDescription.trim()) {
                    console.log('🔍 Tooltip con comentario del usuario:', userDescription);
                }
                
                // ✅ MEJORADO: Título y contenido según el tipo de evento
                let tooltipTitle = '';
                let tooltipContent = '';
                
                if (eventType === 'manual_note_added') {
                    // ✅ NUEVO: Caso especial para notas manuales del usuario
                    tooltipTitle = `📝 User Note`;
                    tooltipContent = `<strong>${tooltipTitle}</strong><br>${eventDate}`;
                    if (userDescription && userDescription.trim()) {
                        tooltipContent += `<br><br><em>"${userDescription}"</em>`;
                    }
                } else {
                    // ✅ Casos existentes para eventos de keywords
                    if (eventType === 'keywords_added') {
                        tooltipTitle = `⚠️ Keywords Añadidas (${keywordsAffected})`;
                    } else if (eventType === 'keyword_deleted') {
                        tooltipTitle = `⚠️ Keyword Eliminada`;
                    } else if (eventType === 'keywords_removed') {
                        tooltipTitle = `⚠️ Keywords Eliminadas (${keywordsAffected})`;
                    } else {
                        tooltipTitle = `⚠️ ${eventTitle}`;
                    }
                    
                    tooltipContent = `<strong>${tooltipTitle}</strong><br>${eventDate}`;
                    
                    // ✅ Mostrar comentarios del usuario para eventos de keywords
                    if (userDescription && 
                        userDescription.trim() && 
                        userDescription !== 'Sin notas adicionales' && 
                        userDescription !== 'No additional notes provided' &&
                        userDescription !== 'No description provided') {
                        tooltipContent += `<br><br><em>"${userDescription}"</em>`;
                    } else {
                        tooltipContent += `<br><br><small style="opacity: 0.7;">Sin comentarios del usuario</small>`;
                    }
                }
                
                tooltip.innerHTML = tooltipContent;
                
                // ✅ MEJORADO: Posicionamiento inteligente del tooltip
                const rect = canvas.getBoundingClientRect();
                const tooltipRect = tooltip.getBoundingClientRect();
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;
                
                let left = e.clientX + 15;
                let top = e.clientY - 10;
                
                // Ajustar si se sale por la derecha
                if (left + 250 > viewportWidth) { // 250px es el ancho aproximado del tooltip
                    left = e.clientX - 250 - 15;
                }
                
                // Ajustar si se sale por arriba
                if (top < 10) {
                    top = e.clientY + 25;
                }
                
                // Ajustar si se sale por abajo
                if (top + 100 > viewportHeight) { // 100px es la altura aproximada del tooltip
                    top = e.clientY - 100 - 15;
                }
                
                tooltip.style.left = Math.max(10, left) + 'px';
                tooltip.style.top = Math.max(10, top) + 'px';
                tooltip.style.opacity = '1';
                canvas.style.cursor = 'pointer';
            } else {
                // Hide tooltip
                tooltip.style.opacity = '0';
                canvas.style.cursor = 'default';
            }
        };
        
        // Mouse leave handler
        const onMouseLeave = () => {
            tooltip.style.opacity = '0';
            canvas.style.cursor = 'default';
        };
        
        // 🔄 Remover listeners previos usando referencias persistentes
        if (chart._annotationHandlers) {
            canvas.removeEventListener('mousemove', chart._annotationHandlers.onMouseMove);
            canvas.removeEventListener('mouseleave', chart._annotationHandlers.onMouseLeave);
        }
        
        // Add new listeners y guardar referencias para próximas limpiezas
        canvas.addEventListener('mousemove', onMouseMove);
        canvas.addEventListener('mouseleave', onMouseLeave);
        chart._annotationHandlers = { onMouseMove, onMouseLeave };
    }
    
    // ================================================
    // TEMPORAL COMPETITOR MARKERS
    // ================================================
    
    addCompetitorChangeMarkers(chart, temporalOptions) {
        // 🆕 NUEVO: Añadir marcadores visuales cuando cambian competidores
        if (!temporalOptions.hasTemporalChanges || !temporalOptions.competitorChanges) {
            return;
        }
        
        const changePoints = [];
        let previousCompetitors = null;
        
        for (const change of temporalOptions.competitorChanges) {
            if (change.is_change || (previousCompetitors && 
                JSON.stringify(change.competitors) !== JSON.stringify(previousCompetitors))) {
                changePoints.push({
                    date: change.date,
                    type: 'competitor_change',
                    icon: '🔄',
                    color: '#f59e0b',
                    competitors: change.competitors,
                    previousCompetitors: previousCompetitors
                });
            }
            previousCompetitors = change.competitors;
        }
        
        // Añadir plugin personalizado para dibujar marcadores
        if (changePoints.length > 0) {
            const drawMarkers = {
                id: 'competitorChangeMarkers',
                afterDraw: (chart) => {
                    const ctx = chart.ctx;
                    const chartArea = chart.chartArea;
                    
                    changePoints.forEach(marker => {
                        // Encontrar posición X del marcador
                        const labels = chart.data.labels || [];
                        const dateIndex = labels.indexOf(marker.date);
                        
                        if (dateIndex !== -1) {
                            const x = chart.scales.x.getPixelForValue(dateIndex);
                            
                            // Dibujar línea vertical
                            ctx.save();
                            ctx.strokeStyle = marker.color;
                            ctx.lineWidth = 2;
                            ctx.setLineDash([5, 5]);
                            ctx.beginPath();
                            ctx.moveTo(x, chartArea.top);
                            ctx.lineTo(x, chartArea.bottom);
                            ctx.stroke();
                            
                            // Dibujar ícono
                            ctx.fillStyle = marker.color;
                            ctx.font = '14px Arial';
                            ctx.textAlign = 'center';
                            ctx.fillText(marker.icon, x, chartArea.top - 10);
                            
                            ctx.restore();
                        }
                    });
                }
            };
            
            // Registrar plugin si no existe
            if (!Chart.registry.plugins.get('competitorChangeMarkers')) {
                Chart.register(drawMarkers);
            }
        }
        
        return changePoints;
    }

    // ================================
    // UI HELPERS
    // ================================

    showElement(element) {
        if (element) element.style.display = 'block';
    }

    hideElement(element) {
        if (element) element.style.display = 'none';
    }

    hideAllModals() {
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            this.hideElement(modal);
        });
    }

    showProgress(title, message) {
        document.getElementById('progressTitle').textContent = title;
        document.getElementById('progressMessage').textContent = message;
        // Reset and start soft progress animation for better UX
        this.resetProgressBar();
        this.startProgressBar(90);
        this.showElement(this.elements.progressModal);
    }

    hideProgress() {
        // Stop progress animation when hiding
        this.stopProgressBar();
        this.hideElement(this.elements.progressModal);
    }

    showSuccess(message) {
        // Simple success notification (can be improved with toast)
        alert('✅ ' + message);
    }

    showError(message) {
        // Simple error notification (can be improved with toast)
        alert('❌ ' + message);
    }

    // ================================
    // PROGRESS BAR CONTROL (UX)
    // ================================

    resetProgressBar() {
        this._progressValue = 0;
        this._progressMax = 100;
        const fill = document.getElementById('progressFill');
        const percent = document.getElementById('progressPercent');
        if (fill) fill.style.width = '0%';
        if (percent) percent.textContent = '0%';
    }

    startProgressBar(maxPercent = 90, stepMs = 800) {
        // Smoothly increase progress up to maxPercent while the task runs
        this.stopProgressBar();
        this._progressTarget = Math.max(0, Math.min(100, maxPercent));
        this._progressInterval = setInterval(() => {
            // Random small steps to feel alive
            const step = Math.max(1, Math.min(3, Math.round(Math.random() * 3)));
            this._progressValue = Math.min(this._progressTarget, (this._progressValue || 0) + step);
            this.updateProgressUI(this._progressValue);
            if (this._progressValue >= this._progressTarget) {
                clearInterval(this._progressInterval);
                this._progressInterval = null;
            }
        }, stepMs);
    }

    stopProgressBar() {
        if (this._progressInterval) {
            clearInterval(this._progressInterval);
            this._progressInterval = null;
        }
    }

    completeProgressBar() {
        this.stopProgressBar();
        this._progressValue = 100;
        this.updateProgressUI(100);
    }

    updateProgressUI(value) {
        const val = Math.max(0, Math.min(100, Math.floor(value)));
        const fill = document.getElementById('progressFill');
        const percent = document.getElementById('progressPercent');
        if (fill) fill.style.width = `${val}%`;
        if (percent) percent.textContent = `${val}%`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // ================================
    // PUBLIC METHODS (called from HTML)
    // ================================

    runAnalysis() {
        if (this.currentProject) {
            this.analyzeProject(this.currentProject.id);
        }
    }

    toggleKeyword(keywordId) {
        // TODO: Implement keyword toggle functionality
        console.log('Toggle keyword:', keywordId);
    }

    // ================================
    // TOP DOMAINS MANAGEMENT
    // ================================

    async loadTopDomains(projectId) {
        if (!projectId) {
            this.showNoDomainsMessage();
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/top-domains`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    this.showNoDomainsMessage();
                    return;
                }
                throw new Error('Failed to load top domains data');
            }

            const data = await response.json();
            this.renderTopDomains(data.domains || []);

        } catch (error) {
            console.error('Error loading top domains:', error);
            this.showNoDomainsMessage();
        }
    }

    renderTopDomains(domains) {
        const tableBody = document.getElementById('topDomainsBody');
        const noDomainsMessage = document.getElementById('noDomainsMessage');
        const topDomainsTable = document.getElementById('topDomainsTable');

        if (!domains || domains.length === 0) {
            this.showNoDomainsMessage();
            return;
        }

        // Hide no domains message and show table
        noDomainsMessage.style.display = 'none';
        topDomainsTable.style.display = 'table';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Render each domain row
        domains.forEach((domain, index) => {
            const row = document.createElement('tr');
            
            // Calculate visibility score (appearances weighted by position)
            const visibilityScore = this.calculateVisibilityScore(domain.appearances, domain.avg_position);
            const scoreClass = this.getScoreClass(visibilityScore);
            
            // Get logo URL for domain
            const logoUrl = this.getDomainLogoUrl(domain.domain);
            
            row.innerHTML = `
                <td class="rank-cell">${index + 1}</td>
                <td class="domain-cell" title="${domain.domain}">
                    <div class="domain-cell-content">
                        <img src="${logoUrl}" alt="${domain.domain} logo" class="domain-logo" 
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22><circle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23e5e7eb%22/><text x=%2212%22 y=%2216%22 text-anchor=%22middle%22 font-size=%2210%22 fill=%22%23374151%22>${domain.domain.charAt(0).toUpperCase()}</text></svg>'">
                        <span class="domain-name">${domain.domain}</span>
                    </div>
                </td>
                <td class="appearances-cell">${domain.appearances}</td>
                <td class="position-cell">${domain.avg_position ? domain.avg_position.toFixed(1) : '-'}</td>
                <td class="score-cell ${scoreClass}">${visibilityScore.toFixed(1)}</td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    getDomainLogoUrl(domain) {
        if (!domain || typeof domain !== 'string') {
            return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTAiIGN5PSIxMCIgcj0iMTAiIGZpbGw9IiNlNWU3ZWIiLz4KPHR5cGUgeD0iMTAiIHk9IjE0IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LXNpemU9IjEwIiBmaWxsPSIjMzc0MTUxIj4/PC90ZXh0Pgo8L3N2Zz4K';
        }
        
        // Clean domain to remove any protocol or paths
        const cleanDomain = domain.toLowerCase()
            .replace(/^https?:\/\//, '')
            .replace(/^www\./, '')
            .split('/')[0]
            .split('?')[0]
            .split('#')[0]
            .trim();
            
        if (!cleanDomain) {
            return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTAiIGN5PSIxMCIgcj0iMTAiIGZpbGw9IiNlNWU3ZWIiLz4KPHR5cGUgeD0iMTAiIHk9IjE0IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LXNpemU9IjEwIiBmaWxsPSIjMzc0MTUxIj4/PC90ZXh0Pgo8L3N2Zz4K';
        }
        
        // Multiple fallback services for domain logos/favicons
        const logoServices = [
            `https://logo.clearbit.com/${cleanDomain}`,                       // Clearbit - high quality
            `https://www.google.com/s2/favicons?domain=${cleanDomain}&sz=32`, // Google favicons - smaller size for better performance
            `https://icon.horse/icon/${cleanDomain}`,                         // Icon Horse - reliable fallback
            `https://${cleanDomain}/favicon.ico`                            // Direct favicon
        ];
        
        // Return primary service (Clearbit) - fallback handled in onerror
        return logoServices[0];
    }

    calculateVisibilityScore(appearances, avgPosition) {
        if (!appearances || !avgPosition) return 0;
        
        // Score = appearances × (weight based on position)
        // Better positions (lower numbers) get higher weights
        const positionWeight = Math.max(0, (21 - avgPosition) / 20);
        return appearances * positionWeight * 10; // Scale to 0-100 range
    }

    getScoreClass(score) {
        if (score >= 80) return 'score-excellent';
        if (score >= 60) return 'score-good';
        if (score >= 30) return 'score-average';
        return 'score-poor';
    }

    // ================================
    // COMPETITORS CHARTS FUNCTIONS
    // ================================

    async loadCompetitorsCharts(projectId) {
        if (!projectId) {
            this.showNoCompetitorsChartsMessage();
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/competitors-charts?days=30`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    this.showNoCompetitorsChartsMessage();
                    return;
                }
                throw new Error('Failed to load competitors charts data');
            }

            const result = await response.json();
            const data = result.data || {};
            
            // 🆕 NUEVO: Extraer información temporal
            const temporalInfo = data.temporal_info || {};
            const hasTemporalChanges = data.has_temporal_changes || false;
            const competitorChanges = data.competitor_changes || [];
            
            // Log información temporal para debugging
            if (hasTemporalChanges) {
                console.log('🔄 Temporal competitor changes detected:', competitorChanges);
            }
            
            // Render both charts with temporal information
            this.renderCompetitorsVisibilityChart(data.visibility_scatter || [], {
                temporalInfo,
                hasTemporalChanges,
                competitorChanges
            });
            this.renderCompetitorsPositionChart(data.position_evolution || {}, {
                temporalInfo,
                hasTemporalChanges,
                competitorChanges
            });

        } catch (error) {
            console.error('Error loading competitors charts:', error);
            this.showNoCompetitorsChartsMessage();
        }
    }

    renderCompetitorsVisibilityChart(scatterData, temporalOptions = {}) {
        const ctx = document.getElementById('competitorsVisibilityChart');
        if (!ctx) return;

        // Destroy existing chart
        if (this.charts.competitorsVisibility) {
            this.charts.competitorsVisibility.destroy();
        }

        if (!scatterData || scatterData.length === 0) {
            this.showNoCompetitorsChartsMessage();
            return;
        }

        // Prepare data for scatter chart
        const datasets = scatterData.map((item, index) => {
            // Generate colors similar to the example image
            const colors = [
                { bg: '#3B82F6', border: '#2563EB' }, // Blue
                { bg: '#EF4444', border: '#DC2626' }, // Red
                { bg: '#10B981', border: '#059669' }, // Green
                { bg: '#F59E0B', border: '#D97706' }, // Orange
                { bg: '#8B5CF6', border: '#7C3AED' }, // Purple
                { bg: '#06B6D4', border: '#0891B2' }  // Cyan
            ];
            
            const color = colors[index % colors.length];
            
            return {
                label: item.domain,
                data: [{
                    x: item.x,
                    y: item.y,
                    appearances: item.appearances,
                    avg_position: item.avg_position,
                    keywords_count: item.keywords_count
                }],
                backgroundColor: color.bg + '80', // Add transparency
                borderColor: color.border,
                borderWidth: 2,
                pointRadius: 8,
                pointHoverRadius: 10
            };
        });

        this.charts.competitorsVisibility = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false // We'll create a custom legend
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return context[0].dataset.label;
                            },
                            label: function(context) {
                                const data = context.raw;
                                const labels = [
                                    `Visibility Score: ${data.x.toFixed(1)}`,
                                    `Brand Likelihood: ${data.y.toFixed(1)}%`,
                                    `Appearances: ${data.appearances}`,
                                    `Avg Position: ${data.avg_position}`,
                                    `Keywords: ${data.keywords_count}`
                                ];
                                
                                // 🆕 NUEVO: Añadir información temporal si está disponible
                                if (temporalOptions.hasTemporalChanges) {
                                    labels.push('');
                                    labels.push('📊 Temporal Data:');
                                    labels.push('This competitor may have changed');
                                    labels.push('during the analysis period.');
                                }
                                
                                return labels;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: 'Visibility Score (Brand Mentions)'
                        },
                        grid: {
                            color: '#E5E7EB'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Likelihood to buy (%)'
                        },
                        grid: {
                            color: '#E5E7EB'
                        }
                    }
                }
            }
        });

        // Create custom legend
        this.createCompetitorsVisibilityLegend(scatterData);
        
        // 🆕 NUEVO: Añadir marcadores de cambios temporales
        if (temporalOptions.hasTemporalChanges) {
            this.addCompetitorChangeMarkers(this.charts.competitorsVisibility, temporalOptions);
        }
    }

    createCompetitorsVisibilityLegend(scatterData) {
        const legendContainer = document.querySelector('.competitors-charts-grid .chart-container:first-child .chart-legend');
        if (!legendContainer) return;

        // Clear existing legend
        legendContainer.innerHTML = '';

        // Add quadrant labels
        const quadrants = [
            { label: 'Low performance', class: 'low-performance' },
            { label: 'Low conversion', class: 'low-conversion' }
        ];

        quadrants.forEach(quadrant => {
            const item = document.createElement('div');
            item.className = 'legend-item';
            item.innerHTML = `
                <span class="legend-color ${quadrant.class}"></span>
                <span>${quadrant.label}</span>
            `;
            legendContainer.appendChild(item);
        });
    }

    renderCompetitorsPositionChart(positionData, temporalOptions = {}) {
        const ctx = document.getElementById('competitorsPositionChart');
        if (!ctx) return;

        // Destroy existing chart
        if (this.charts.competitorsPosition) {
            this.charts.competitorsPosition.destroy();
        }

        if (!positionData || !positionData.datasets || positionData.datasets.length === 0) {
            this.showNoCompetitorsChartsMessage();
            return;
        }

        this.charts.competitorsPosition = new Chart(ctx, {
            type: 'line',
            data: {
                labels: positionData.dates || [],
                datasets: positionData.datasets || []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false // We'll create a custom legend
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                return new Date(context[0].label).toLocaleDateString();
                            },
                            label: function(context) {
                                return `${context.dataset.label}: Position ${context.raw}`;
                            },
                            // 🆕 NUEVO: Footer con información temporal
                            footer: function(context) {
                                if (!temporalOptions.hasTemporalChanges) return '';
                                
                                const date = context[0].label;
                                const competitors = temporalOptions.temporalInfo[date];
                                
                                if (competitors) {
                                    return [
                                        '',
                                        '📊 Active competitors on this date:',
                                        competitors.join(', ')
                                    ];
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        },
                        grid: {
                            color: '#E5E7EB'
                        }
                    },
                    y: {
                        reverse: true, // Position 1 should be at the top
                        title: {
                            display: true,
                            text: 'Brand Position'
                        },
                        grid: {
                            color: '#E5E7EB'
                        },
                        ticks: {
                            stepSize: 1,
                            callback: function(value) {
                                return value.toString();
                            }
                        }
                    }
                },
                elements: {
                    point: {
                        radius: 3,
                        hoverRadius: 6
                    },
                    line: {
                        tension: 0.4
                    }
                }
            }
        });

        // Create custom legend for position chart
        this.createCompetitorsPositionLegend(positionData.datasets || []);
        
        // 🆕 NUEVO: Añadir marcadores de cambios temporales
        if (temporalOptions.hasTemporalChanges) {
            this.addCompetitorChangeMarkers(this.charts.competitorsPosition, temporalOptions);
        }
    }

    createCompetitorsPositionLegend(datasets) {
        const legendContainer = document.getElementById('positionChartLegend');
        if (!legendContainer) return;

        // Clear existing legend
        legendContainer.innerHTML = '';

        datasets.forEach(dataset => {
            const item = document.createElement('div');
            item.className = 'brand-legend-item';
            item.innerHTML = `
                <span class="brand-color" style="background-color: ${dataset.borderColor};"></span>
                <span>${dataset.label}</span>
            `;
            legendContainer.appendChild(item);
        });
    }

    showNoCompetitorsChartsMessage() {
        // Hide charts and show empty state message
        const charts = ['competitorsVisibilityChart', 'competitorsPositionChart'];
        charts.forEach(chartId => {
            const canvas = document.getElementById(chartId);
            if (canvas) {
                canvas.style.display = 'none';
            }
        });

        // You could add a "no data" message here if needed
        console.log('No competitors charts data available');
    }

    // ================================
    // GLOBAL DOMAINS RANKING FUNCTIONS
    // ================================

    async loadGlobalDomainsRanking(projectId) {
        if (!projectId) {
            this.showNoGlobalDomainsMessage();
            return;
        }

        const days = this.elements.analyticsTimeRange?.value || 30;

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/global-domains-ranking?days=${days}`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    this.showNoGlobalDomainsMessage();
                    return;
                }
                throw new Error('Failed to load global domains ranking');
            }

            const data = await response.json();
            this.renderGlobalDomainsRanking(data.domains || []);

        } catch (error) {
            console.error('Error loading global domains ranking:', error);
            this.showNoGlobalDomainsMessage();
        }
    }

    renderGlobalDomainsRanking(domains) {
        const tableBody = document.getElementById('globalDomainsBody');
        const noDomainsMessage = document.getElementById('noGlobalDomainsMessage');
        const globalDomainsTable = document.getElementById('globalDomainsTable');

        if (!domains || domains.length === 0) {
            this.showNoGlobalDomainsMessage();
            return;
        }

        // Hide no domains message and show table
        noDomainsMessage.style.display = 'none';
        globalDomainsTable.style.display = 'table';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Render each domain row with highlighting
        domains.forEach((domain, index) => {
            const row = document.createElement('tr');
            // Use 'table' prefix for project domain to avoid conflicts with other CSS
            const domainTypeClass = domain.domain_type === 'project' ? 'table' : domain.domain_type;
            row.className = `domain-row ${domainTypeClass}-domain`;
            
            // Get logo URL
            const logoUrl = this.getDomainLogoUrl(domain.detected_domain);
            
            // Create domain badge if needed
            let domainBadge = '';
            if (domain.domain_type === 'project') {
                domainBadge = '<span class="domain-badge project">Your Domain</span>';
            } else if (domain.domain_type === 'competitor') {
                domainBadge = '<span class="domain-badge competitor">Competitor</span>';
            }
            
            row.innerHTML = `
                <td class="rank-cell">${domain.rank}</td>
                <td class="domain-cell">
                    <div class="global-domain-cell">
                        <img src="${logoUrl}" alt="${domain.detected_domain} logo" class="domain-logo" 
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22><circle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23e5e7eb%22/><text x=%2212%22 y=%2216%22 text-anchor=%22middle%22 font-size=%2210%22 fill=%22%23374151%22>${domain.detected_domain.charAt(0).toUpperCase()}</text></svg>'">
                        <div class="global-domain-info">
                            <div class="global-domain-label">
                                <span class="global-domain-name">${domain.detected_domain}</span>
                                ${domainBadge}
                            </div>
                        </div>
                    </div>
                </td>
                <td class="appearances-cell">${domain.appearances || 0}</td>
                <td class="position-cell">${domain.avg_position && typeof domain.avg_position === 'number' ? domain.avg_position.toFixed(1) : '-'}</td>
                <td class="visibility-cell">${domain.visibility_percentage && typeof domain.visibility_percentage === 'number' ? domain.visibility_percentage.toFixed(1) : '0.0'}%</td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    showNoGlobalDomainsMessage() {
        const tableBody = document.getElementById('globalDomainsBody');
        const noDomainsMessage = document.getElementById('noGlobalDomainsMessage');
        const globalDomainsTable = document.getElementById('globalDomainsTable');

        if (tableBody) tableBody.innerHTML = '';
        if (globalDomainsTable) globalDomainsTable.style.display = 'none';
        if (noDomainsMessage) noDomainsMessage.style.display = 'block';
    }

    // ================================
    // AI OVERVIEW KEYWORDS TABLE FUNCTIONS
    // ================================

    async loadAIOverviewKeywordsTable(projectId) {
        if (!projectId) {
            this.showNoAIKeywordsMessage();
            return;
        }

        const days = this.elements.analyticsTimeRange?.value || 30;

        try {
            // Tabla de AI Overview debe quedarse fija al último análisis disponible
            const latestToken = Date.now();
            this._latestAIOTableToken = latestToken;
            const response = await fetch(`/manual-ai/api/projects/${projectId}/ai-overview-table-latest`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    this.showNoAIKeywordsMessage();
                    return;
                }
                throw new Error('Failed to load AI Overview keywords data');
            }

            const result = await response.json();
            if (this._latestAIOTableToken !== latestToken) return; // evitar pisado por race
            const data = result.data || {};
            
            // Render AI Overview keywords table using Grid.js
            this.renderAIOverviewKeywordsTable(data);

        } catch (error) {
            console.error('Error loading AI Overview keywords table:', error);
            this.showNoAIKeywordsMessage();
        }
    }

    renderAIOverviewKeywordsTable(data) {
        const container = document.getElementById('manualAIOverviewGrid');
        const noKeywordsMessage = document.getElementById('noAIKeywordsMessage');
        
        if (!container) {
            console.error('❌ AI Overview grid container not found');
            return;
        }

        // Clear existing content
        container.innerHTML = '';

        const keywordResults = data.keywordResults || [];
        // Asegurar orden y unicidad de competidores para columnas deterministas
        const competitorDomains = Array.from(new Set((data.competitorDomains || []).map(d => (d || '').toLowerCase()))).sort();

        console.log('🏗️ Rendering AI Overview table with:', {
            keywords: keywordResults.length,
            competitors: competitorDomains.length
        });

        if (keywordResults.length === 0) {
            this.showNoAIKeywordsMessage();
            return;
        }

        // Hide no keywords message
        if (noKeywordsMessage) {
            noKeywordsMessage.style.display = 'none';
        }

        // Check if Grid.js is available
        if (!window.gridjs) {
            console.error('❌ Grid.js library not loaded');
            container.innerHTML = '<p class="error-message">Grid.js library not available</p>';
            return;
        }

        // Rebuild Grid.js table from scratch (destroy previous instances)
        try {
            const { columns, gridData } = this.processAIOverviewDataForGrid(keywordResults, competitorDomains);
            // Hard rebuild: replace container node to avoid stale Grid.js state
            const parent = container.parentNode;
            const fresh = container.cloneNode(false);
            parent.replaceChild(fresh, container);
            
            const grid = new gridjs.Grid({
                columns: columns,
                data: gridData,
                pagination: {
                    limit: 10,
                    summary: true
                },
                sort: true,
                search: {
                    placeholder: 'Type a keyword...'
                },
                resizable: true,
                className: {
                    container: 'manual-ai-overview-grid',
                    table: 'manual-ai-overview-table',
                    search: 'manual-ai-overview-search'
                }
            });

            // Render the grid
            grid.render(fresh);
            console.log('✅ AI Overview Grid.js table rendered successfully');

        } catch (error) {
            console.error('❌ Error creating AI Overview Grid.js table:', error);
            container.innerHTML = '<p class="error-message">Error creating table</p>';
        }
    }

    processAIOverviewDataForGrid(keywordResults, competitorDomains) {
        // Define base columns (sin la columna View)
        const columns = [
            {
                id: 'keyword',
                name: 'Keyword',
                width: '200px',
                sort: true
            },
            {
                id: 'your_domain_in_aio',
                name: gridjs.html('Your Domain<br>in AIO'),
                width: '120px',
                sort: {
                    compare: (a, b) => {
                        // Ordenar Yes/No: Yes primero
                        const va = (a === 'Yes') ? 1 : 0;
                        const vb = (b === 'Yes') ? 1 : 0;
                        return vb - va; // Yes > No
                    }
                },
                formatter: (cell) => {
                    const isPresent = cell === 'Yes';
                    return gridjs.html(`
                        <span class="aio-status ${isPresent ? 'aio-yes' : 'aio-no'}">
                            ${cell}
                        </span>
                    `);
                }
            },
            {
                id: 'your_position_in_aio',
                name: gridjs.html('Your Position<br>in AIO'),
                width: '120px',
                sort: {
                    compare: (a, b) => {
                        // Convertir a números para comparación - N/A como valor mayor para ir al final
                        const numA = typeof a === 'number' ? a : (a === 'N/A' ? Infinity : parseInt(a) || Infinity);
                        const numB = typeof b === 'number' ? b : (b === 'N/A' ? Infinity : parseInt(b) || Infinity);
                        return numA - numB;
                    }
                },
                formatter: (cell) => {
                    if (cell === 'N/A') {
                        return gridjs.html('<span class="aio-na">N/A</span>');
                    }
                    return gridjs.html(`<span class="aio-position">${cell}</span>`);
                }
            }
        ];

        // Add competitor columns
        competitorDomains.forEach((domain, index) => {
            const truncatedDomain = this.truncateDomain(domain, 15);
            const domainId = (domain || '')
                .toLowerCase()
                .replace(/^https?:\/\//, '')
                .replace(/^www\./, '')
                .replace(/[^a-z0-9]+/g, '_');
            
            // Competitor presence column
            columns.push({
                id: `comp_${domainId}_present`,
                name: gridjs.html(`${truncatedDomain}<br>in AIO`),
                width: '120px',
                sort: {
                    compare: (a, b) => {
                        const va = (a === 'Yes') ? 1 : 0;
                        const vb = (b === 'Yes') ? 1 : 0;
                        return vb - va; // Yes > No
                    }
                },
                formatter: (cell) => {
                    const isPresent = cell === 'Yes';
                    return gridjs.html(`
                        <span class="aio-status ${isPresent ? 'aio-yes' : 'aio-no'}">
                            ${cell}
                        </span>
                    `);
                }
            });

            // Competitor position column
            columns.push({
                id: `comp_${domainId}_position`,
                name: gridjs.html(`Position of<br>${truncatedDomain}`),
                width: '120px',
                sort: {
                    compare: (a, b) => {
                        // Convertir a números para comparación - N/A como valor mayor para ir al final
                        const numA = typeof a === 'number' ? a : (a === 'N/A' ? Infinity : parseInt(a) || Infinity);
                        const numB = typeof b === 'number' ? b : (b === 'N/A' ? Infinity : parseInt(b) || Infinity);
                        return numA - numB;
                    }
                },
                formatter: (cell) => {
                    if (cell === 'N/A') {
                        return gridjs.html('<span class="aio-na">N/A</span>');
                    }
                    return gridjs.html(`<span class="aio-position">${cell}</span>`);
                }
            });
        });

        // Process data for Grid.js
        const gridData = keywordResults.map(result => {
            const keyword = result.keyword || '';
            const aiAnalysis = result.ai_analysis || {};
            
            // Base row data (sin la columna View)
            const row = [
                keyword,
                aiAnalysis.domain_is_ai_source ? 'Yes' : 'No',
                (typeof aiAnalysis.domain_ai_source_position === 'number' && aiAnalysis.domain_ai_source_position > 0)
                    ? aiAnalysis.domain_ai_source_position : 'N/A'
            ];

            // Add competitor data
            competitorDomains.forEach(domain => {
                const competitorData = this.findCompetitorDataInResult(result, domain);
                row.push(competitorData.isPresent ? 'Yes' : 'No');
                row.push((typeof competitorData.position === 'number' && competitorData.position > 0) ? competitorData.position : 'N/A');
            });

            return row;
        });

        return { columns, gridData };
    }

    findCompetitorDataInResult(result, domain) {
        // Find competitor data in AI analysis references
        const aiAnalysis = result.ai_analysis || {};
        const debugInfo = aiAnalysis.debug_info || {};
        const references = debugInfo.references_found || [];
        
        if (!references || references.length === 0) {
            return { isPresent: false, position: null };
        }
        
        // Normalize domain for comparison
        const normalizedDomain = domain.toLowerCase().replace('www.', '');
        
        // Search for domain in references
        for (let i = 0; i < references.length; i++) {
            const ref = references[i];
            const refLink = ref.link || '';
            const refSource = ref.source || '';
            const refTitle = ref.title || '';
            
            // Check for matches in link, source or title
            const linkMatch = refLink.toLowerCase().includes(normalizedDomain);
            const sourceMatch = refSource.toLowerCase().includes(normalizedDomain);
            const titleMatch = refTitle.toLowerCase().includes(normalizedDomain);
            
            if (linkMatch || sourceMatch || titleMatch) {
                return {
                    isPresent: true,
                    position: (ref.index || 0) + 1 // Convert 0-based index to 1-based position
                };
            }
        }
        
        return { isPresent: false, position: null };
    }

    truncateDomain(domain, maxLength = 15) {
        if (!domain || domain.length <= maxLength) return domain;
        return domain.substring(0, maxLength - 3) + '...';
    }

    showNoAIKeywordsMessage() {
        const container = document.getElementById('manualAIOverviewGrid');
        const noKeywordsMessage = document.getElementById('noAIKeywordsMessage');
        
        if (container) {
            container.innerHTML = '';
        }
        
        if (noKeywordsMessage) {
            noKeywordsMessage.style.display = 'block';
        }
    }

    // ================================
    // COMPARATIVE CHARTS FUNCTIONS (Project vs Selected Competitors)
    // ================================

    async loadComparativeCharts(projectId) {
        if (!projectId) {
            this.showNoComparativeChartsMessage();
            return;
        }

        const days = this.elements.analyticsTimeRange?.value || 30;

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/comparative-charts?days=${days}`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    this.showNoComparativeChartsMessage();
                    return;
                }
                throw new Error('Failed to load comparative charts data');
            }

            const result = await response.json();
            const data = result.data || {};
            
            // Render both comparative charts
            this.renderComparativeVisibilityChart(data.visibility_chart || {});
            this.renderComparativePositionChart(data.position_chart || {});

        } catch (error) {
            console.error('Error loading comparative charts:', error);
            this.showNoComparativeChartsMessage();
        }
    }

    renderComparativeVisibilityChart(chartData) {
        const ctx = document.getElementById('comparativeVisibilityChart');
        if (!ctx) return;

        // Destroy existing chart
        if (this.charts.comparativeVisibility) {
            this.charts.comparativeVisibility.destroy();
        }

        if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
            this.showNoComparativeChartsMessage();
            return;
        }

        // Modern Chart.js configuration with HTML Legend
        const config = this.getModernChartConfig(true, 'comparativeVisibilityLegend');
        
        this.charts.comparativeVisibility = new Chart(ctx, {
            type: 'line',
            data: {
                labels: (chartData.dates || []).map(d => new Date(d).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric' 
                })),
                datasets: chartData.datasets.map((dataset, index) => ({
                    ...dataset,
                    pointBackgroundColor: dataset.borderColor,
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: dataset.borderColor,
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    backgroundColor: dataset.borderColor ? dataset.borderColor.replace('rgb', 'rgba').replace(')', ', 0.3)') : 'rgba(99, 102, 241, 0.3)',
                    fill: false, // Superpuesto como Sistrix
                    tension: 0.4
                }))
            },
            plugins: [htmlLegendPlugin],
            options: {
                ...config,
                scales: {
                    ...config.scales,
                    y: {
                        ...config.scales.y,
                        beginAtZero: true,
                        max: 100,
                        stacked: false,
                        title: {
                            display: true,
                            text: 'Visibility (%)',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        },
                        ticks: {
                            ...config.scales.y.ticks,
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    x: {
                        ...config.scales.x,
                        title: {
                            display: true,
                            text: 'Date',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        }
                    }
                },
                plugins: {
                    ...config.plugins,
                    tooltip: {
                        ...config.plugins.tooltip,
                        callbacks: {
                            title: function(context) {
                                return new Date(chartData.dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                    weekday: 'short',
                                    year: 'numeric',
                                    month: 'short',
                                    day: 'numeric'
                                });
                            },
                            label: function(context) {
                                return `${context.dataset.label}: ${Math.round(context.raw)}%`;
                            }
                        }
                    }
                }
            }
        });
    }

    renderComparativePositionChart(chartData) {
        const ctx = document.getElementById('comparativePositionChart');
        if (!ctx) return;

        // Destroy existing chart
        if (this.charts.comparativePosition) {
            this.charts.comparativePosition.destroy();
        }

        if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
            this.showNoComparativeChartsMessage();
            return;
        }

        // Modern Chart.js configuration with HTML Legend
        const config = this.getModernChartConfig(true, 'comparativePositionLegend');
        
        this.charts.comparativePosition = new Chart(ctx, {
            type: 'line',
            data: {
                labels: (chartData.dates || []).map(d => new Date(d).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric' 
                })),
                datasets: chartData.datasets.map((dataset, index) => ({
                    ...dataset,
                    pointBackgroundColor: dataset.borderColor,
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: dataset.borderColor,
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    backgroundColor: dataset.borderColor ? dataset.borderColor.replace('rgb', 'rgba').replace(')', ', 0.3)') : 'rgba(99, 102, 241, 0.3)',
                    fill: false, // Superpuesto como Sistrix
                    tension: 0.4
                }))
            },
            plugins: [htmlLegendPlugin],
            options: {
                ...config,
                scales: {
                    ...config.scales,
                    y: {
                        ...config.scales.y,
                        reverse: true,
                        min: 1,
                        title: {
                            display: true,
                            text: 'Average Position',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        },
                        ticks: {
                            ...config.scales.y.ticks,
                            callback: function(value) {
                                return '#' + Math.round(value);
                            }
                        }
                    },
                    x: {
                        ...config.scales.x,
                        title: {
                            display: true,
                            text: 'Date',
                            color: '#374151',
                            font: { size: 12, weight: '500' }
                        }
                    }
                },
                plugins: {
                    ...config.plugins,
                    tooltip: {
                        ...config.plugins.tooltip,
                        callbacks: {
                            title: function(context) {
                                return new Date(chartData.dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                    weekday: 'short',
                                    year: 'numeric',
                                    month: 'short',
                                    day: 'numeric'
                                });
                            },
                            label: function(context) {
                                const value = context.raw;
                                return `${context.dataset.label}: Position ${value ? Math.round(value) : 'N/A'}`;
                            }
                        }
                    }
                }
            }
        });
    }

    showNoComparativeChartsMessage() {
        // Hide charts and show empty state message
        const charts = ['comparativeVisibilityChart', 'comparativePositionChart'];
        charts.forEach(chartId => {
            const canvas = document.getElementById(chartId);
            if (canvas) {
                canvas.style.display = 'none';
            }
        });

        console.log('No comparative charts data available');
    }

    // ================================
    // COMPETITORS PREVIEW (Dashboard Main) 
    // ================================
    
    async loadCompetitorsPreview(projectId) {
        if (!projectId) {
            this.renderCompetitorsPreview([]);
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/competitors`);
            if (!response.ok) {
                if (response.status === 404) {
                    this.renderCompetitorsPreview([]);
                    return;
                }
                throw new Error('Failed to load competitors');
            }

            const data = await response.json();
            this.renderCompetitorsPreview(data.competitors || []);

        } catch (error) {
            console.error('Error loading competitors preview:', error);
            this.renderCompetitorsPreview([]);
        }
    }

    renderCompetitorsPreview(competitors) {
        const competitorsCountEl = document.getElementById('competitorsCount');
        const competitorsPreviewEl = document.getElementById('competitorsPreview');

        // Since we removed the Analytics chip, these elements no longer exist
        // This function is kept for compatibility but does nothing
        if (!competitorsCountEl || !competitorsPreviewEl) {
            console.log('🗑️ Competitors preview elements not found (removed from UI)');
            return;
        }

        // Legacy code kept for potential future use
        competitorsCountEl.textContent = competitors.length;
        competitorsPreviewEl.innerHTML = '';

        if (competitors.length === 0) {
            competitorsPreviewEl.innerHTML = '<span style="color: var(--text-secondary); font-size: 12px;">No competitors selected</span>';
            return;
        }

        competitors.forEach(domain => {
            const logoUrl = this.getDomainLogoUrl(domain);
            const logoEl = document.createElement('img');
            logoEl.src = logoUrl;
            logoEl.alt = `${domain} logo`;
            logoEl.className = 'competitor-logo-small';
            logoEl.title = domain;
            logoEl.onerror = function() {
                this.outerHTML = `<div class="competitor-logo-placeholder" title="${domain}">${domain.charAt(0).toUpperCase()}</div>`;
            };
            competitorsPreviewEl.appendChild(logoEl);
        });
    }

    // ================================
    // COMPETITORS MANAGEMENT FUNCTIONS
    // ================================

    initCompetitorsManager() {
        const addBtn = document.getElementById('addCompetitorBtn');
        const newCompetitorInput = document.getElementById('newCompetitorInput');

        if (addBtn) {
            addBtn.addEventListener('click', () => this.addCompetitor());
        }

        if (newCompetitorInput) {
            newCompetitorInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.addCompetitor();
                }
            });
        }



        // Ensure competitors are loaded when modal Settings is opened
        // (actual load is triggered contextually in showProjectModal/switchModalTab)
    }



    async loadCompetitors(projectId = null) {
        // Prefer explicit projectId (e.g., from modal) otherwise fallback to current project context
        const project = projectId ? this.projects.find(p => p.id == projectId) : (this.currentModalProject || this.getCurrentProject());
        if (!project) {
            console.warn('No project found for loading competitors');
            return;
        }

        console.log(`🔍 Loading competitors for project ${project.id}: ${project.name}`);
        console.log('📋 Project data:', project);

        // Load competitors directly from project data (from database selected_competitors field)
        const competitors = project.selected_competitors || [];
        
        console.log(`📊 Found ${competitors.length} competitors in project data:`, competitors);
        
        // Render the competitors immediately
                this.renderCompetitors(competitors);
    }

    renderCompetitors(competitors) {
        console.log('🎨 renderCompetitors called with:', competitors);
        
        const competitorsList = document.getElementById('competitorsList');
        const competitorEmptyState = document.getElementById('competitorEmptyState');
        
        console.log('🔍 DOM elements found:', {
            competitorsList: !!competitorsList,
            competitorEmptyState: !!competitorEmptyState
        });
        
        if (!competitorsList || !competitorEmptyState) {
            console.warn('⚠️ Required DOM elements not found for competitors rendering');
            return;
        }

        // Clear existing competitors
        competitorsList.innerHTML = '';

        if (competitors.length === 0) {
            console.log('📝 Showing empty state - no competitors');
            competitorsList.classList.remove('has-competitors');
            competitorEmptyState.classList.remove('hidden');
            competitorEmptyState.style.display = 'flex';
        } else {
            console.log(`📝 Showing ${competitors.length} competitors`);
            competitorsList.classList.add('has-competitors');
            competitorEmptyState.classList.add('hidden');
            competitorEmptyState.style.display = 'none';
        }

        competitors.forEach((domain, index) => {
            const logoUrl = this.getDomainLogoUrl(domain);
            const competitorItem = document.createElement('div');
            competitorItem.className = 'competitor-item';
            
            // Crear elementos de forma segura
            const competitorInfo = document.createElement('div');
            competitorInfo.className = 'competitor-info';
            
            const logoImg = document.createElement('img');
            logoImg.src = logoUrl;
            logoImg.alt = domain;
            logoImg.className = 'domain-logo';
            
            // Fallback seguro para el logo
            logoImg.onerror = () => {
                logoImg.style.display = 'none';
                const fallback = document.createElement('div');
                fallback.className = 'competitor-logo-fallback';
                fallback.textContent = domain.charAt(0).toUpperCase();
                fallback.title = domain;
                competitorInfo.insertBefore(fallback, logoImg.nextSibling);
            };
            
            const domainSpan = document.createElement('span');
            domainSpan.className = 'competitor-domain';
            domainSpan.textContent = domain;
            
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'competitor-remove-btn';
            removeBtn.innerHTML = '<i class="fas fa-times"></i>';
            removeBtn.onclick = () => this.removeCompetitor(domain);
            
            competitorInfo.appendChild(logoImg);
            competitorInfo.appendChild(domainSpan);
            competitorItem.appendChild(competitorInfo);
            competitorItem.appendChild(removeBtn);
            
            competitorsList.appendChild(competitorItem);
        });

        // Update add button state
        const addBtn = document.getElementById('addCompetitorBtn');
        const newCompetitorInput = document.getElementById('newCompetitorInput');
        
        if (competitors.length >= 4) {
            addBtn.disabled = true;
            addBtn.textContent = 'Max 4 competitors';
            newCompetitorInput.disabled = true;
            newCompetitorInput.placeholder = 'Maximum 4 competitors allowed';
        } else {
            addBtn.disabled = false;
            addBtn.textContent = 'Add Competitor';
            newCompetitorInput.disabled = false;
            newCompetitorInput.placeholder = 'Enter competitor domain (e.g., example.com)';
        }
    }

    async addCompetitor() {
        const newCompetitorInput = document.getElementById('newCompetitorInput');
        const domain = newCompetitorInput.value.trim();

        if (!domain) {
            this.showError('Please enter a domain');
            return;
        }

        // Basic domain validation
        if (!this.isValidDomain(domain)) {
            this.showError('Please enter a valid domain (e.g., example.com)');
            return;
        }

        const currentProject = this.currentModalProject;
        if (!currentProject) {
            this.showError('No project selected');
            return;
        }

        try {
            // Get current competitors directly from project data
            const currentCompetitors = currentProject.selected_competitors || [];

            // Check for duplicates
            if (currentCompetitors.includes(domain.toLowerCase())) {
                this.showError('This competitor is already added');
                return;
            }

            // Check maximum limit
            if (currentCompetitors.length >= 4) {
                this.showError('Maximum 4 competitors allowed');
                return;
            }

            // Add new competitor
            const updatedCompetitors = [...currentCompetitors, domain.toLowerCase()];
            await this.updateCompetitors(updatedCompetitors);

            // Clear input
            newCompetitorInput.value = '';
            this.showSuccess('Competitor added successfully');

        } catch (error) {
            console.error('Error adding competitor:', error);
            this.showError('Failed to add competitor');
        }
    }

    async removeCompetitor(domain) {
        const currentProject = this.currentModalProject;
        if (!currentProject) return;

        try {
            // Get current competitors directly from project data
            const currentCompetitors = currentProject.selected_competitors || [];

            // Remove competitor
            const updatedCompetitors = currentCompetitors.filter(comp => comp !== domain);
            await this.updateCompetitors(updatedCompetitors);

            this.showSuccess('Competitor removed successfully');

        } catch (error) {
            console.error('Error removing competitor:', error);
            this.showError('Failed to remove competitor');
        }
    }

    async updateCompetitors(competitors) {
        const currentProject = this.currentModalProject;
        if (!currentProject) return;

        const response = await fetch(`/manual-ai/api/projects/${currentProject.id}/competitors`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ competitors })
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.error || 'Failed to update competitors');
        }

        // Update the current project in memory with new competitors
        currentProject.selected_competitors = competitors;
        
        // Update the project in the projects array
        const projectIndex = this.projects.findIndex(p => p.id === currentProject.id);
        if (projectIndex !== -1) {
            this.projects[projectIndex].selected_competitors = competitors;
        }

        // Reload competitors display in modal and dashboard preview
        await Promise.all([
            this.loadCompetitors(currentProject.id),
            this.loadCompetitorsPreview(currentProject.id)
        ]);
        
        // Refresh the projects list to update the project cards with new competitor info
        await this.loadProjects();
    }

    isValidDomain(domain) {
        // Basic domain validation regex
        const domainRegex = /^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?\.([a-zA-Z]{2,}\.?)+$/;
        return domainRegex.test(domain);
    }

    showNoDomainsMessage() {
        const tableBody = document.getElementById('topDomainsBody');
        const noDomainsMessage = document.getElementById('noDomainsMessage');
        const topDomainsTable = document.getElementById('topDomainsTable');

        if (tableBody) tableBody.innerHTML = '';
        if (topDomainsTable) topDomainsTable.style.display = 'none';
        if (noDomainsMessage) noDomainsMessage.style.display = 'block';
    }

    // ================================
    // PROJECT SETTINGS MANAGEMENT
    // ================================

    async updateProjectName() {
        const newName = document.getElementById('projectNameEdit').value.trim();
        const currentProject = this.getCurrentProject();
        
        if (!newName) {
            this.showError('Project name cannot be empty');
            return;
        }

        if (!currentProject) {
            this.showError('No project selected');
            return;
        }

        if (newName === currentProject.name) {
            this.showSuccess('Project name is already up to date');
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${currentProject.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Failed to update project name');
            }

            // Update current project data
            currentProject.name = newName;
            
            // Refresh project list and UI
            await this.loadProjects();
            this.updateProjectUI();
            
            this.showSuccess('Project name updated successfully');
            
        } catch (error) {
            console.error('Error updating project name:', error);
            this.showError(`Failed to update project name: ${error.message}`);
        }
    }

    confirmDeleteProject() {
        const currentProject = this.getCurrentProject();
        
        if (!currentProject) {
            this.showError('No project selected');
            return;
        }

        // Set project name in modal
        document.getElementById('deleteProjectName').textContent = currentProject.name;
        document.getElementById('deleteProjectNamePrompt').textContent = currentProject.name;
        
        // Reset confirmation input
        const confirmInput = document.getElementById('deleteConfirmInput');
        confirmInput.value = '';
        document.getElementById('confirmDeleteBtn').disabled = true;
        
        // Store project reference for deletion
        this.projectToDelete = currentProject;
        
        // Remove any existing event listener to prevent duplicates
        confirmInput.oninput = null;
        
        // Add input listener for enabling delete button
        confirmInput.oninput = (e) => {
            const deleteBtn = document.getElementById('confirmDeleteBtn');
            const inputValue = e.target.value.trim();
            
            // Use the stored project reference
            if (!this.projectToDelete || !this.projectToDelete.name) {
                console.error('❌ projectToDelete is null or has no name');
                deleteBtn.disabled = true;
                return;
            }
            
            const projectName = this.projectToDelete.name.trim();
            const isMatch = inputValue === projectName;
            
            console.log('🔍 Delete button validation:', {
                inputValue: `"${inputValue}"`,
                projectName: `"${projectName}"`,
                inputLength: inputValue.length,
                nameLength: projectName.length,
                isMatch: isMatch,
                charCodes: {
                    input: Array.from(inputValue).map(c => c.charCodeAt(0)),
                    name: Array.from(projectName).map(c => c.charCodeAt(0))
                }
            });
            
            deleteBtn.disabled = !isMatch;
            
            // Force visual update
            if (isMatch) {
                deleteBtn.style.opacity = '1';
                deleteBtn.style.cursor = 'pointer';
            } else {
                deleteBtn.style.opacity = '0.5';
                deleteBtn.style.cursor = 'not-allowed';
            }
        };
        
        // Show modal
        this.showElement(document.getElementById('deleteProjectModal'));
    }

    hideDeleteProjectModal() {
        this.hideElement(document.getElementById('deleteProjectModal'));
        document.getElementById('deleteConfirmInput').value = '';
        document.getElementById('confirmDeleteBtn').disabled = true;
    }

    async executeDeleteProject() {
        const projectToDelete = this.projectToDelete;
        const confirmText = document.getElementById('deleteConfirmInput').value;
        
        if (!projectToDelete) {
            this.showError('No project selected for deletion');
            return;
        }

        if (confirmText.trim() !== projectToDelete.name.trim()) {
            this.showError('Please type the project name exactly to confirm');
            return;
        }

        try {
            this.showProgress('Deleting project...');
            
            const response = await fetch(`/manual-ai/api/projects/${encodeURIComponent(projectToDelete.id)}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.error || error.message || `Failed to delete project (HTTP ${response.status})`);
            }

            this.hideProgress();
            this.hideDeleteProjectModal();
            
            // Show success message
            this.showSuccess('Project deleted successfully');
            
            // Mercado estándar: recargar para reflejar el cambio inmediatamente
            setTimeout(() => {
                window.location.reload();
            }, 600);
            
        } catch (error) {
            this.hideProgress();
            console.error('Error deleting project:', error);
            this.showError(`Failed to delete project: ${error.message}`);
        }
    }

    getCurrentProject() {
        const projectSelect = this.elements.keywordsProjectSelect;
        if (!projectSelect || !projectSelect.value) return null;
        
        return this.projects.find(p => p.id == projectSelect.value);
    }

    updateProjectUI() {
        // Update project name in detail view header if open
        const currentProject = this.getCurrentProject();
        if (currentProject && this.elements.projectDetailView.style.display !== 'none') {
            const projectTitle = document.querySelector('#projectDetailView h3');
            if (projectTitle) {
                projectTitle.textContent = `Project: ${currentProject.name}`;
            }
        }
    }

    loadProjectSettings(project) {
        // Load project name into edit field
        const projectNameEdit = document.getElementById('projectNameEdit');
        if (projectNameEdit) {
            projectNameEdit.value = project.name || '';
        }
    }

    // ================================
    // PROJECT MODAL MANAGEMENT
    // ================================

    showProjectModal(projectId) {
        // Find project data
        const project = this.projects.find(p => p.id === projectId);
        if (!project) {
            this.showError('Project not found');
            return;
        }

        // Set current modal project
        this.currentModalProject = project;

        // Update modal title
        document.getElementById('projectModalTitle').textContent = `${project.name} - Settings`;

        // Load project data into modal
        this.loadProjectIntoModal(project);

        // Show modal
        this.showElement(document.getElementById('projectModal'));
    }

    hideProjectModal() {
        this.hideElement(document.getElementById('projectModal'));
        this.currentModalProject = null;
        
        // Reset modal to keywords tab
        this.switchModalTab('keywords');
    }

    switchModalTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.modal-nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.modalTab === tabName);
        });

        // Update tab contents
        document.querySelectorAll('.modal-tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `modal${tabName.charAt(0).toUpperCase() + tabName.slice(1)}Tab`);
        });

        // Load specific tab data
        if (tabName === 'keywords' && this.currentModalProject) {
            this.loadModalKeywords(this.currentModalProject.id);
        } else if (tabName === 'settings' && this.currentModalProject) {
            this.loadModalSettings(this.currentModalProject);
            this.loadCompetitors(this.currentModalProject.id);
        }
    }

    loadProjectIntoModal(project) {
        // Load into both tabs
        this.loadModalKeywords(project.id);
        this.loadModalSettings(project);
        this.loadCompetitors(project.id);
    }

    async loadModalKeywords(projectId) {
        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/keywords`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    console.warn(`⚠️ Project ${projectId} not found, reloading projects...`);
                    await this.loadProjects();
                    this.hideProjectModal();
                    this.showError('The project does not exist. Data has been updated.');
                    return;
                } else if (response.status === 403) {
                    this.showError('You do not have permission to view this project.');
                    return;
                }
                throw new Error(`Failed to load keywords (${response.status})`);
            }

            const data = await response.json();
            this.renderModalKeywords(data.keywords || []);

        } catch (error) {
            console.error('Error loading modal keywords:', error);
            this.showError(`Error loading keywords: ${error.message}`);
        }
    }

    renderModalKeywords(keywords) {
        const keywordsList = document.getElementById('modalKeywordsList');
        const noKeywords = document.getElementById('modalNoKeywords');

        if (!keywords || keywords.length === 0) {
            keywordsList.innerHTML = '';
            noKeywords.style.display = 'block';
            return;
        }

        noKeywords.style.display = 'none';
        // Guardar copia en memoria para filtrado
        this._modalAllKeywords = keywords;

        // Si existe input de búsqueda, aplicar filtro inicial (si mantiene valor)
        const searchInput = document.getElementById('modalKeywordsSearch');
        const query = (searchInput && searchInput.value || '').trim().toLowerCase();

        const filtered = query
            ? keywords.filter(k => (k.keyword || '').toLowerCase().includes(query))
            : keywords;

        keywordsList.innerHTML = filtered.map(keyword => `
            <div class="keyword-item" data-keyword-id="${keyword.id}">
                <div class="keyword-text">${this.escapeHtml(keyword.keyword)}</div>
                <div class="keyword-meta">${keyword.is_active ? 'Active' : 'Inactive'}</div>
                <button type="button" class="btn-remove-keyword" 
                        onclick="manualAI.removeKeywordFromModal(${keyword.id})"
                        title="Remove keyword">
                    <i class="fas fa-trash"></i>
                    Remove
                </button>
            </div>
        `).join('');

        // Atachar listener una sola vez
        if (searchInput && !searchInput._listenerAttached) {
            const handler = (e) => {
                const q = e.target.value.trim().toLowerCase();
                const data = this._modalAllKeywords || [];
                const subset = q ? data.filter(k => (k.keyword || '').toLowerCase().includes(q)) : data;
                keywordsList.innerHTML = subset.map(keyword => `
                    <div class=\"keyword-item\" data-keyword-id=\"${keyword.id}\"> 
                        <div class=\"keyword-text\">${this.escapeHtml(keyword.keyword)}</div>
                        <div class=\"keyword-meta\">${keyword.is_active ? 'Active' : 'Inactive'}</div>
                        <button type=\"button\" class=\"btn-remove-keyword\" onclick=\"manualAI.removeKeywordFromModal(${keyword.id})\" title=\"Remove keyword\"> 
                            <i class=\"fas fa-trash\"></i> Remove 
                        </button>
                    </div>
                `).join('');
            };
            searchInput.addEventListener('input', handler);
            searchInput._listenerAttached = true;
        }
    }

    clearModalKeywordsSearch() {
        const input = document.getElementById('modalKeywordsSearch');
        if (input) {
            input.value = '';
            // Re-render listado completo con la copia en memoria
            const data = this._modalAllKeywords || [];
            const keywordsList = document.getElementById('modalKeywordsList');
            keywordsList.innerHTML = data.map(keyword => `
                <div class=\"keyword-item\" data-keyword-id=\"${keyword.id}\"> 
                    <div class=\"keyword-text\">${this.escapeHtml(keyword.keyword)}</div>
                    <div class=\"keyword-meta\">${keyword.is_active ? 'Active' : 'Inactive'}</div>
                    <button type=\"button\" class=\"btn-remove-keyword\" onclick=\"manualAI.removeKeywordFromModal(${keyword.id})\" title=\"Remove keyword\"> 
                        <i class=\"fas fa-trash\"></i> Remove 
                    </button>
                </div>
            `).join('');
            input.focus();
        }
    }

    loadModalSettings(project) {
        // Load project name and description into modal settings
        const modalProjectName = document.getElementById('modalProjectName');
        const modalProjectDescription = document.getElementById('modalProjectDescription');
        
        if (modalProjectName) {
            modalProjectName.value = project.name || '';
        }
        
        if (modalProjectDescription) {
            modalProjectDescription.value = project.description || '';
        }
    }

    async addKeywordsFromModal() {
        const keywordsInput = document.getElementById('modalKeywordsInput');
        const keywordsText = keywordsInput.value.trim();
        
        if (!keywordsText) {
            this.showError('Please enter some keywords');
            return;
        }

        if (!this.currentModalProject) {
            this.showError('No project selected');
            return;
        }

        try {
            // Parse keywords (split by newlines or commas)
            const keywords = keywordsText
                .split(/[,\n]/)
                .map(k => k.trim())
                .filter(k => k.length > 0);

            if (keywords.length === 0) {
                this.showError('No valid keywords found');
                return;
            }

            const response = await fetch(`/manual-ai/api/projects/${this.currentModalProject.id}/keywords`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keywords })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Failed to add keywords');
            }

            // Clear input and reload keywords
            keywordsInput.value = '';
            await this.loadModalKeywords(this.currentModalProject.id);
            await this.loadProjects(); // Refresh projects list
            
            this.showSuccess(`Added ${keywords.length} keyword(s) successfully`);
            
            // Show annotation modal after successful addition
            this.showAnnotationModal('keywords_added', `Added ${keywords.length} keyword${keywords.length !== 1 ? 's' : ''} to ${this.currentModalProject.name}`);

        } catch (error) {
            console.error('Error adding keywords:', error);
            this.showError(`Failed to add keywords: ${error.message}`);
        }
    }

    // ✅ NUEVO: Función para añadir notas manuales del usuario
    async addNoteFromModal() {
        const notesInput = document.getElementById('modalNotesInput');
        const noteText = notesInput.value.trim();
        
        if (!noteText) {
            this.showError('Please enter a note');
            return;
        }

        if (noteText.length > 500) {
            this.showError('Note must be 500 characters or less');
            return;
        }

        if (!this.currentModalProject) {
            this.showError('No project selected');
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${this.currentModalProject.id}/notes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ note: noteText })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to add note');
            }

            const result = await response.json();
            
            // Clear input
            notesInput.value = '';
            
            // Refresh analytics if we're currently viewing this project
            if (this.currentProject && this.currentProject.id === this.currentModalProject.id) {
                await this.loadAnalyticsComponents(this.currentProject.id);
            }
            
            this.showSuccess(`Note added successfully for ${result.note_date}`);
            
            console.log('📝 Manual note added successfully:', {
                project: this.currentModalProject.name,
                note: noteText.substring(0, 50) + (noteText.length > 50 ? '...' : ''),
                date: result.note_date
            });

        } catch (error) {
            console.error('Error adding note:', error);
            this.showError(`Failed to add note: ${error.message}`);
        }
    }

    async removeKeywordFromModal(keywordId) {
        if (!this.currentModalProject) {
            this.showError('No project selected');
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${this.currentModalProject.id}/keywords/${keywordId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                let errorMessage = 'Failed to remove keyword';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorData.message || errorMessage;
                } catch (parseError) {
                    console.error('Error parsing error response:', parseError);
                }
                
                if (response.status === 404) {
                    errorMessage = 'The keyword or project does not exist. Data will be synchronized automatically.';
                } else if (response.status === 403) {
                    errorMessage = 'You do not have permission to delete this keyword. Data will be synchronized automatically.';
                } else if (response.status === 500) {
                    errorMessage = 'Internal server error. Data will be synchronized automatically.';
                }
                
                throw new Error(errorMessage);
            }

            const result = await response.json();
            
            // Reload keywords and projects to ensure sync
            await this.loadModalKeywords(this.currentModalProject.id);
            await this.loadProjects();
            
            this.showSuccess(result.message || 'Keyword deleted successfully');
            
            // Show annotation modal after successful deletion
            this.showAnnotationModal('keyword_deleted', `Deleted keyword from ${this.currentModalProject.name}`);

        } catch (error) {
            console.error('💥 Error removing keyword:', error);
            this.showError(error.message);
            
            // 🆕 MEJORADO: Automatic data synchronization for all error types
            console.log('🔄 Auto-synchronizing data due to error...');
            
            try {
                // Clear any stale cache
                this.clearObsoleteCache();
                
                // Force reload projects from server
                await this.loadProjects();
                
                // If modal is still open and project still exists, reload keywords
                if (this.currentModalProject) {
                    const projectStillExists = this.projects.find(p => p.id === this.currentModalProject.id);
                    if (projectStillExists) {
                        await this.loadModalKeywords(this.currentModalProject.id);
                    } else {
                        // Project no longer exists, close modal
                        console.log('⚠️ Project no longer exists, closing modal');
                        this.hideProjectModal();
                        this.showError('The project no longer exists. Data has been synchronized.');
                    }
                }
                
                console.log('✅ Data synchronization completed');
            } catch (syncError) {
                console.error('❌ Error during auto-sync:', syncError);
            }
        }
    }

    async updateProjectFromModal() {
        const newName = document.getElementById('modalProjectName').value.trim();
        const newDescription = document.getElementById('modalProjectDescription').value.trim();
        
        if (!newName) {
            this.showError('Project name cannot be empty');
            return;
        }

        if (!this.currentModalProject) {
            this.showError('No project selected');
            return;
        }

        // Check if anything actually changed
        if (newName === this.currentModalProject.name && 
            newDescription === (this.currentModalProject.description || '')) {
            this.showSuccess('Project is already up to date');
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${this.currentModalProject.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    name: newName,
                    description: newDescription 
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Failed to update project');
            }

            // Update current project data
            this.currentModalProject.name = newName;
            this.currentModalProject.description = newDescription;
            
            // Update modal title
            document.getElementById('projectModalTitle').textContent = `${newName} - Settings`;
            
            // Refresh projects list
            await this.loadProjects();
            
            this.showSuccess('Project updated successfully');
            
        } catch (error) {
            console.error('Error updating project:', error);
            this.showError(`Failed to update project: ${error.message}`);
        }
    }

    confirmDeleteProjectFromModal() {
        if (!this.currentModalProject) {
            this.showError('No project selected');
            return;
        }

        // Set project name in delete modal
        document.getElementById('deleteProjectName').textContent = this.currentModalProject.name;
        document.getElementById('deleteProjectNamePrompt').textContent = this.currentModalProject.name;
        
        // Store project reference for deletion (use the same variable as the other function)
        this.projectToDelete = this.currentModalProject;
        
        // Hide project modal and show delete confirmation
        this.hideProjectModal();
        this.showElement(document.getElementById('deleteProjectModal'));
        
        // Reset confirmation input
        const confirmInput = document.getElementById('deleteConfirmInput');
        confirmInput.value = '';
        document.getElementById('confirmDeleteBtn').disabled = true;
        
        // Remove any existing event listener to prevent duplicates
        confirmInput.oninput = null;
        
        // Add input listener for enabling delete button
        confirmInput.oninput = (e) => {
            const deleteBtn = document.getElementById('confirmDeleteBtn');
            const inputValue = e.target.value.trim();
            
            // Safety check: ensure projectToDelete exists
            if (!this.projectToDelete || !this.projectToDelete.name) {
                console.error('❌ projectToDelete is null or has no name');
                deleteBtn.disabled = true;
                return;
            }
            
            const projectName = this.projectToDelete.name.trim();
            const isMatch = inputValue === projectName;
            
            console.log('🔍 Delete button validation (modal):', {
                inputValue: `"${inputValue}"`,
                projectName: `"${projectName}"`,
                inputLength: inputValue.length,
                nameLength: projectName.length,
                isMatch: isMatch,
                inputCharCodes: Array.from(inputValue).map(c => c.charCodeAt(0)),
                nameCharCodes: Array.from(projectName).map(c => c.charCodeAt(0))
            });
            
            deleteBtn.disabled = !isMatch;
            
            // Visual feedback for debugging
            deleteBtn.style.opacity = isMatch ? '1' : '0.5';
            deleteBtn.style.cursor = isMatch ? 'pointer' : 'not-allowed';
        };
    }

    // ================================================
    // ANNOTATION MODAL FUNCTIONALITY  
    // ================================================

    showAnnotationModal(changeType, changeDescription) {
        // Store the annotation data
        this.pendingAnnotation = {
            type: changeType,
            description: changeDescription,
            projectId: (this.currentModalProject && this.currentModalProject.id) ||
                       (this.currentProject && this.currentProject.id) ||
                       (this.elements.analyticsProjectSelect ? parseInt(this.elements.analyticsProjectSelect.value) : null)
        };

        // Update modal content
        const titleElement = document.getElementById('annotationChangeTitle');
        const descriptionElement = document.getElementById('annotationChangeDescription');
        
        if (titleElement && descriptionElement) {
            if (changeType === 'keywords_added') {
                titleElement.textContent = 'Keywords Added';
                descriptionElement.textContent = `${changeDescription}. Add a note to track this change in your analytics.`;
            } else if (changeType === 'keyword_deleted') {
                titleElement.textContent = 'Keyword Deleted';
                descriptionElement.textContent = `${changeDescription}. Add a note to track this change in your analytics.`;
            }
        }

        // Reset textarea and show modal
        const textarea = document.getElementById('annotationDescription');
        const charCount = document.getElementById('annotationCharCount');
        
        if (textarea) {
            textarea.value = '';
            this.updateAnnotationCharCount();
            
            // Add character count listener
            textarea.addEventListener('input', () => this.updateAnnotationCharCount());
        }

        this.showElement(document.getElementById('annotationModal'));
    }

    hideAnnotationModal() {
        this.hideElement(document.getElementById('annotationModal'));
        this.pendingAnnotation = null;
    }

    updateAnnotationCharCount() {
        const textarea = document.getElementById('annotationDescription');
        const charCount = document.getElementById('annotationCharCount');
        
        if (textarea && charCount) {
            const currentLength = textarea.value.length;
            charCount.textContent = currentLength;
            
            // Visual feedback for character limit
            if (currentLength > 240) {
                charCount.style.color = '#f59e0b'; // Warning
            } else if (currentLength > 255) {
                charCount.style.color = '#ef4444'; // Error
            } else {
                charCount.style.color = '#64748b'; // Normal
            }
        }
    }

    async saveAnnotation() {
        if (!this.pendingAnnotation) {
            this.hideAnnotationModal();
            return;
        }

        const textarea = document.getElementById('annotationDescription');
        const userDescription = textarea ? textarea.value.trim() : '';
        
        try {
            // Create the annotation event
            const response = await fetch('/manual-ai/api/annotations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: this.pendingAnnotation.projectId,
                    event_type: this.pendingAnnotation.type,
                    event_title: this.pendingAnnotation.description,
                    event_description: userDescription || 'No additional notes provided',
                    event_date: new Date().toISOString().split('T')[0] // Today's date
                })
            });

            if (response.ok) {
                this.showSuccess('Annotation saved successfully');
                console.log('📝 Annotation saved for chart visualization');
            } else {
                console.warn('⚠️ Failed to save annotation, but continuing...');
            }

        } catch (error) {
            console.error('Error saving annotation:', error);
            // Don't show error to user as annotation is optional
        } finally {
            this.hideAnnotationModal();
        }
    }

    // ================================
    // EXCEL DOWNLOAD FUNCTIONALITY
    // ================================

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

    async handleDownloadExcel() {
        if (!this.currentAnalyticsData) {
            this.showError('No data available for export. Please select a project and load analytics first.');
            return;
        }

        const { projectId, days } = this.currentAnalyticsData;
        const downloadBtn = document.getElementById('sidebarDownloadBtn');
        const spinner = downloadBtn?.querySelector('.download-spinner');
        const btnText = downloadBtn?.querySelector('span');

        console.log(`📥 Starting Manual AI Excel download for project ${projectId} (${days} days)`);

        try {
            // Show loading state
            if (downloadBtn) downloadBtn.disabled = true;
            if (spinner) spinner.style.display = 'inline-block';
            if (btnText) btnText.style.display = 'none';

            // Get current project info for telemetry
            const project = this.projects.find(p => p.id === projectId);
            const projectName = project?.name || 'Unknown';
            const competitorsCount = project?.selected_competitors?.length || 0;

            // Make download request
            const response = await fetch(`/manual-ai/api/projects/${projectId}/download-excel`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    days: days
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: "Error generating Excel file" }));
                throw new Error(errorData.error || 'Failed to generate Excel file');
            }

            // Download the file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;

            // Extract filename from response headers or create default
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'manual-ai_export.xlsx';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (filenameMatch) {
                    filename = filenameMatch[1].replace(/['"]/g, '');
                }
            }

            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            // Telemetry logging
            console.log('📊 Manual AI Excel export telemetry:', {
                project_id: projectId,
                project_name: projectName,
                keyword_set_id: 'manual-ai', // Manual AI doesn't use keyword sets like the main app
                date_range: `${days}_days`,
                competitors_count: competitorsCount,
                rows_total: this.currentAnalyticsData.stats?.main_stats?.total_keywords || 0,
                export_type: 'manual_ai_xlsx',
                timestamp: new Date().toISOString()
            });

            // Show success state
            if (btnText) {
                const originalText = btnText.textContent;
                btnText.textContent = 'Downloaded!';
                downloadBtn.classList.add('success');

                setTimeout(() => {
                    btnText.textContent = originalText;
                    downloadBtn.classList.remove('success');
                }, 2000);
            }

            this.showSuccess('Excel file downloaded successfully!');

        } catch (error) {
            console.error('❌ Error downloading Manual AI Excel:', error);
            this.showError(`Error downloading Excel: ${error.message}`);
        } finally {
            // Reset loading state
            if (downloadBtn) downloadBtn.disabled = false;
            if (spinner) spinner.style.display = 'none';
            if (btnText) btnText.style.display = 'inline';
        }
    }

    async handleDownloadPDF() {
        try {
            const btn = document.getElementById('sidebarDownloadPdfBtn');
            const spinner = btn?.querySelector('.download-spinner');
            const btnText = btn?.querySelector('span');
            if (spinner && btnText) {
                spinner.style.display = 'inline-block';
                btnText.textContent = 'Preparing PDF...';
            }

            // Ocultar elementos excluidos del PDF
            const excluded = Array.from(document.querySelectorAll('[data-pdf-exclude="true"]'));
            const prevDisplay = new Map();
            excluded.forEach(el => {
                prevDisplay.set(el, el.style.display);
                el.style.display = 'none';
            });

            const [{ default: html2canvas }] = await Promise.all([
                import('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.esm.js')
            ]);
            // Cargar jsPDF UMD y acceder via window.jspdf.jsPDF
            if (!window.jspdf || !window.jspdf.jsPDF) {
                await new Promise((resolve, reject) => {
                    const s = document.createElement('script');
                    s.src = 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js';
                    s.onload = () => resolve();
                    s.onerror = () => reject(new Error('Failed to load jsPDF'));
                    document.head.appendChild(s);
                });
            }

            const target = document.querySelector('.manual-ai-app') || document.body;
            const canvas = await html2canvas(target, { scale: 2, useCORS: true, backgroundColor: '#ffffff' });
            const imgData = canvas.toDataURL('image/jpeg', 0.92);

            const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            const imgWidth = pageWidth;
            const imgHeight = canvas.height * (imgWidth / canvas.width);
            let position = 0;
            let heightLeft = imgHeight;
            pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);

            // Añadir logotipo como marca de agua en cada página (esquina inferior derecha)
            const addCornerLogo = async () => {
                try {
                    const logoEl = document.querySelector('.navbar .logo-image');
                    const logoSrc = logoEl?.src || '/static/images/logos/logo%20clicandseo.png';
                    const logoImg = new Image();
                    logoImg.crossOrigin = 'anonymous';
                    await new Promise((resolve) => { logoImg.onload = resolve; logoImg.onerror = resolve; logoImg.src = logoSrc; });
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = logoImg.naturalWidth || 0;
                    tempCanvas.height = logoImg.naturalHeight || 0;
                    if (tempCanvas.width && tempCanvas.height) {
                        const ctx = tempCanvas.getContext('2d');
                        ctx.drawImage(logoImg, 0, 0);
                        const dataUrl = tempCanvas.toDataURL('image/png');
                        const margin = 16; // pt
                        const maxLogoWidth = Math.min(80, pageWidth * 0.18);
                        const ratio = (logoImg.naturalHeight || 1) / (logoImg.naturalWidth || 1);
                        const logoW = maxLogoWidth;
                        const logoH = logoW * ratio;
                        const x = pageWidth - logoW - margin;
                        const y = pageHeight - logoH - margin;
                        try { pdf.addImage(dataUrl, 'PNG', x, y, logoW, logoH); } catch (_) {}
                    }
                } catch (_) { /* silencioso */ }
            };

            await addCornerLogo();
            heightLeft -= pageHeight;
            while (heightLeft > 0) {
                position = heightLeft - imgHeight;
                pdf.addPage();
                pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);
                await addCornerLogo();
                heightLeft -= pageHeight;
            }
            const fileName = `manual_ai_overview_${Date.now()}.pdf`;
            pdf.save(fileName);
            
            // Restaurar elementos excluidos
            excluded.forEach(el => { el.style.display = prevDisplay.get(el) || ''; });
        } catch (err) {
            console.error('Error generating PDF:', err);
            this.showError('Failed to generate PDF.');
        } finally {
            const btn = document.getElementById('sidebarDownloadPdfBtn');
            const spinner = btn?.querySelector('.download-spinner');
            const btnText = btn?.querySelector('span');
            if (spinner && btnText) {
                spinner.style.display = 'none';
                btnText.textContent = 'Download PDF';
            }
        }
    }

    // ================================
    // CLUSTERS CONFIGURATION & VISUALIZATION
    // ================================

    async loadClustersStatistics(projectId) {
        // Verificar que los elementos de clusters existen en el DOM
        const clustersChart = document.getElementById('clustersChart');
        if (!clustersChart) {
            console.log('⚠️ Clusters chart not found in DOM - clusters feature not available in this view');
            return;
        }
        
        if (!projectId) {
            this.showNoClustersMessage();
            return;
        }

        const days = this.elements.analyticsTimeRange?.value || 30;

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/clusters/statistics?days=${days}`);

            if (!response.ok) {
                if (response.status === 404) {
                    this.showNoClustersMessage();
                    return;
                }
                throw new Error('Failed to load clusters statistics');
            }

            const result = await response.json();
            const data = result.data || {};

            console.log('📊 Clusters statistics loaded:', data);

            if (!data.enabled || data.total_clusters === 0) {
                this.showNoClustersMessage();
                return;
            }

            // Renderizar gráfica y tabla
            this.renderClustersChart(data.chart_data);
            this.renderClustersTable(data.table_data);

        } catch (error) {
            console.error('Error loading clusters statistics:', error);
            this.showNoClustersMessage();
        }
    }

    renderClustersChart(chartData) {
        const ctx = document.getElementById('clustersChart');
        if (!ctx) {
            console.error('❌ clustersChart canvas not found');
            return;
        }

        // Destroy existing chart
        if (this.charts.clusters) {
            this.charts.clusters.destroy();
        }

        console.log('🔍 Rendering clusters chart with data:', chartData);

        if (!chartData || !chartData.labels || chartData.labels.length === 0) {
            console.warn('⚠️ No data for clusters chart');
            this.showNoClustersMessage();
            return;
        }

        // Show canvas
        ctx.style.display = 'block';
        const container = document.getElementById('clustersChartContainer');
        if (container) {
            container.style.display = 'block';
        }

        // Preparar datos para Chart.js (gráfica combinada: barras + línea)
        this.charts.clusters = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [
                    {
                        type: 'bar',
                        label: 'AI Overview',
                        data: chartData.ai_overview,
                        backgroundColor: 'rgba(99, 102, 241, 0.7)',
                        borderColor: 'rgb(99, 102, 241)',
                        borderWidth: 1,
                        yAxisID: 'y',
                        order: 2
                    },
                    {
                        type: 'line',
                        label: 'Menciones de Marca',
                        data: chartData.mentions,
                        borderColor: 'rgb(34, 197, 94)',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 5,
                        pointBackgroundColor: 'rgb(34, 197, 94)',
                        pointBorderColor: '#FFFFFF',
                        pointBorderWidth: 2,
                        yAxisID: 'y',
                        order: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Clusters Temáticos: AI Overview y Menciones',
                        font: {
                            size: 16,
                            weight: '600'
                        },
                        color: '#1f2937'
                    },
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        titleColor: '#1f2937',
                        bodyColor: '#4b5563',
                        borderColor: '#e5e7eb',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            title: function(context) {
                                return `Cluster: ${context[0].label}`;
                            },
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y || 0;
                                return `${label}: ${value} keywords`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Número de Keywords',
                            color: '#374151',
                            font: {
                                size: 12,
                                weight: '500'
                            }
                        },
                        ticks: {
                            stepSize: 1,
                            color: '#6b7280'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Clusters',
                            color: '#374151',
                            font: {
                                size: 12,
                                weight: '500'
                            }
                        },
                        ticks: {
                            color: '#6b7280',
                            maxRotation: 45,
                            minRotation: 0
                        },
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        console.log('✅ Clusters chart rendered successfully');
    }

    renderClustersTable(tableData) {
        const tableBody = document.getElementById('clustersTableBody');
        const noDataMessage = document.getElementById('noClustersData');
        const table = document.getElementById('clustersTable');

        if (!tableBody || !table) {
            console.error('❌ Clusters table elements not found');
            return;
        }

        if (!tableData || tableData.length === 0) {
            if (noDataMessage) noDataMessage.style.display = 'block';
            if (table) table.style.display = 'none';
            return;
        }

        // Hide no data message and show table
        if (noDataMessage) noDataMessage.style.display = 'none';
        if (table) table.style.display = 'table';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Render each cluster row
        tableData.forEach(cluster => {
            const row = document.createElement('tr');

            // Aplicar clase especial para Unclassified
            if (cluster.cluster_name === 'Unclassified') {
                row.className = 'unclassified-row';
            }

            row.innerHTML = `
                <td class="cluster-name-cell">
                    <strong>${this.escapeHtml(cluster.cluster_name)}</strong>
                </td>
                <td class="text-center">${cluster.total_keywords}</td>
                <td class="text-center">${cluster.ai_overview_count}</td>
                <td class="text-center">${cluster.mentions_count}</td>
                <td class="text-center">
                    <span class="badge badge-info">${cluster.ai_overview_percentage}%</span>
                </td>
                <td class="text-center">
                    <span class="badge badge-success">${cluster.mentions_percentage}%</span>
                </td>
            `;

            tableBody.appendChild(row);
        });

        console.log('✅ Clusters table rendered with', tableData.length, 'clusters');
    }

    showNoClustersMessage() {
        console.log('⚠️ No clusters data available');

        const chartCanvas = document.getElementById('clustersChart');
        const chartContainer = document.getElementById('clustersChartContainer');
        const table = document.getElementById('clustersTable');
        const noDataMessage = document.getElementById('noClustersData');

        if (chartCanvas) chartCanvas.style.display = 'none';
        if (chartContainer) chartContainer.style.display = 'none';
        if (table) table.style.display = 'none';
        if (noDataMessage) noDataMessage.style.display = 'block';
    }

    // ================================
    // CLUSTERS CONFIGURATION (CREATE & SETTINGS)
    // ================================

    initializeClustersConfiguration() {
        const clustersCheckbox = document.getElementById('projectClustersEnabled');
        if (!clustersCheckbox) {
            console.log('⚠️ Clusters checkbox not found in DOM - skipping initialization');
            return;
        }

        // Event listeners para habilitar/deshabilitar clusters
        clustersCheckbox.addEventListener('change', () => {
            const enabled = clustersCheckbox.checked;
            this.toggleClustersConfiguration(enabled);
        });

        // Event listener para añadir cluster
        const addClusterBtn = document.getElementById('addClusterBtn');
        if (addClusterBtn) {
            addClusterBtn.addEventListener('click', () => {
                this.addClusterRow();
            });
        }
    }

    toggleClustersConfiguration(enabled) {
        const clustersContainer = document.getElementById('projectClustersContainer');
        if (!clustersContainer) {
            console.log('⚠️ Clusters container not found in DOM - skipping toggle');
            return;
        }

        if (enabled) {
            clustersContainer.style.display = 'block';
            // Si no hay clusters, añadir uno por defecto
            const clustersRows = document.querySelectorAll('.cluster-row');
            if (clustersRows.length === 0) {
                this.addClusterRow();
            }
        } else {
            clustersContainer.style.display = 'none';
        }
    }

    addClusterRow(clusterData = null) {
        const clustersContainer = document.getElementById('clustersList');
        if (!clustersContainer) {
            console.log('⚠️ Clusters list container not found in DOM - skipping add row');
            return;
        }

        const clusterIndex = clustersContainer.children.length;
        const clusterName = clusterData?.name || '';
        const clusterTerms = clusterData?.terms ? clusterData.terms.join(', ') : '';
        const matchMethod = clusterData?.match_method || 'contains';

        const clusterRow = document.createElement('div');
        clusterRow.className = 'cluster-row';
        clusterRow.dataset.clusterIndex = clusterIndex;

        clusterRow.innerHTML = `
            <div class="cluster-inputs">
                <div class="form-group">
                    <label class="form-label">Nombre del Cluster</label>
                    <input type="text" 
                           class="form-control cluster-name-input" 
                           placeholder="ej: Verifactu" 
                           value="${this.escapeHtml(clusterName)}"
                           required>
                </div>

                <div class="form-group">
                    <label class="form-label">Términos de Coincidencia</label>
                    <input type="text" 
                           class="form-control cluster-terms-input" 
                           placeholder="ej: verifactu, verificación de facturas, veri-factu" 
                           value="${this.escapeHtml(clusterTerms)}"
                           required>
                    <small class="form-text">Separa los términos con comas</small>
                </div>

                <div class="form-group">
                    <label class="form-label">Método de Coincidencia</label>
                    <select class="form-control cluster-method-select">
                        <option value="contains" ${matchMethod === 'contains' ? 'selected' : ''}>Contiene</option>
                        <option value="exact" ${matchMethod === 'exact' ? 'selected' : ''}>Exacto</option>
                        <option value="starts_with" ${matchMethod === 'starts_with' ? 'selected' : ''}>Empieza con</option>
                        <option value="regex" ${matchMethod === 'regex' ? 'selected' : ''}>Expresión Regular</option>
                    </select>
                </div>

                <button type="button" class="btn btn-danger btn-sm remove-cluster-btn" title="Eliminar cluster">
                    <i class="fas fa-trash"></i> Eliminar
                </button>
            </div>
        `;

        // Event listener para eliminar cluster
        const removeBtn = clusterRow.querySelector('.remove-cluster-btn');
        removeBtn.addEventListener('click', () => {
            clusterRow.remove();
        });

        clustersContainer.appendChild(clusterRow);
    }

    getClustersConfiguration() {
        const clustersCheckbox = document.getElementById('projectClustersEnabled');
        const enabled = clustersCheckbox?.checked || false;

        if (!enabled) {
            return {
                enabled: false,
                clusters: []
            };
        }

        const clusters = [];
        const clusterRows = document.querySelectorAll('.cluster-row');

        clusterRows.forEach(row => {
            const nameInput = row.querySelector('.cluster-name-input');
            const termsInput = row.querySelector('.cluster-terms-input');
            const methodSelect = row.querySelector('.cluster-method-select');

            const name = nameInput?.value.trim();
            const termsText = termsInput?.value.trim();
            const method = methodSelect?.value || 'contains';

            if (name && termsText) {
                // Separar términos por comas y limpiar espacios
                const terms = termsText.split(',').map(t => t.trim()).filter(t => t.length > 0);

                if (terms.length > 0) {
                    clusters.push({
                        name: name,
                        terms: terms,
                        match_method: method
                    });
                }
            }
        });

        return {
            enabled: enabled && clusters.length > 0,
            clusters: clusters
        };
    }

    loadClustersConfiguration(clustersConfig) {
        if (!clustersConfig) return;

        // Habilitar/deshabilitar clusters
        const enabled = clustersConfig.enabled || false;
        const clustersCheckbox = document.getElementById('projectClustersEnabled');
        if (!clustersCheckbox) {
            console.log('⚠️ Clusters configuration elements not found in DOM - skipping load');
            return;
        }
        
        clustersCheckbox.checked = enabled;
        this.toggleClustersConfiguration(enabled);

        // Limpiar clusters existentes
        const clustersContainer = document.getElementById('clustersList');
        if (clustersContainer) {
            clustersContainer.innerHTML = '';
            
            // Cargar clusters
            const clusters = clustersConfig.clusters || [];
            clusters.forEach(cluster => {
                this.addClusterRow(cluster);
            });
        }
    }

    async loadProjectClustersForSettings(projectId) {
        if (!projectId) return;
        
        // Verificar que los elementos existen en el DOM
        const clustersCheckbox = document.getElementById('projectClustersEnabled');
        if (!clustersCheckbox) {
            console.log('⚠️ Clusters elements not found in DOM - clusters feature not available in this view');
            return;
        }

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/clusters`);
            if (!response.ok) throw new Error('Failed to load clusters');

            const data = await response.json();
            if (data.success) {
                this.loadClustersConfiguration(data.clusters_config);
            }
        } catch (error) {
            console.error('Error loading clusters for settings:', error);
        }
    }

    async saveClustersConfiguration(projectId) {
        if (!projectId) {
            this.showNotification('Error: No project selected', 'error');
            return;
        }

        try {
            const clustersConfig = this.getClustersConfiguration();

            console.log('💾 Saving clusters configuration:', clustersConfig);

            const response = await fetch(`/manual-ai/api/projects/${projectId}/clusters`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    clusters_config: clustersConfig
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Clusters configuration saved successfully', 'success');

                // Si hay warnings, mostrarlos
                if (result.warnings && result.warnings.length > 0) {
                    result.warnings.forEach(warning => {
                        this.showNotification(warning, 'warning');
                    });
                }

                // Recargar estadísticas si estamos en la vista de analytics
                if (this.currentView === 'analytics') {
                    this.loadClustersStatistics(projectId);
                }
            } else {
                const errorMsg = result.errors ? result.errors.join(', ') : result.error;
                this.showNotification(`Error saving clusters: ${errorMsg}`, 'error');
            }

        } catch (error) {
            console.error('Error saving clusters configuration:', error);
            this.showNotification('Error saving clusters configuration', 'error');
        }
    }
}

// Auto-initialize if we're on the manual AI page
if (window.location.pathname.includes('/manual-ai/')) {
    console.log('📍 Manual AI page detected - ready for initialization');
    
    // Initialize user dropdown functionality
    initializeUserDropdown();
}

// ================================
// USER DROPDOWN FUNCTIONALITY (REUSED FROM MAIN APP)
// ================================

function initializeUserDropdown() {
    const userDropdownBtn = document.getElementById('userDropdownBtn');
    const userDropdownMenu = document.getElementById('userDropdownMenu');
    const dropdownThemeToggle = document.getElementById('dropdownThemeToggle');
    const dropdownLogoutBtn = document.getElementById('dropdownLogoutBtn');

    if (!userDropdownBtn || !userDropdownMenu) return;

    // Toggle dropdown
    userDropdownBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        const isOpen = userDropdownMenu.classList.contains('show');
        
        if (isOpen) {
            closeUserDropdown();
        } else {
            openUserDropdown();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!userDropdownBtn.contains(e.target) && !userDropdownMenu.contains(e.target)) {
            closeUserDropdown();
        }
    });

    // Theme toggle
    if (dropdownThemeToggle) {
        dropdownThemeToggle.addEventListener('click', function(e) {
            e.preventDefault();
            toggleTheme();
        });
    }

    // Logout functionality
    if (dropdownLogoutBtn) {
        dropdownLogoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            handleLogout();
        });
    }

    function openUserDropdown() {
        userDropdownMenu.classList.add('show');
        userDropdownBtn.setAttribute('aria-expanded', 'true');
    }

    function closeUserDropdown() {
        userDropdownMenu.classList.remove('show');
        userDropdownBtn.setAttribute('aria-expanded', 'false');
    }

    function toggleTheme() {
        // Basic theme toggle - you can extend this based on your app's theme system
        const isDark = document.body.classList.contains('dark-theme');
        const themeIcon = document.getElementById('dropdownThemeIcon');
        const themeText = document.getElementById('dropdownThemeText');
        
        if (isDark) {
            document.body.classList.remove('dark-theme');
            if (themeIcon) themeIcon.className = 'fas fa-moon';
            if (themeText) themeText.textContent = 'Dark Mode';
            localStorage.setItem('theme', 'light');
        } else {
            document.body.classList.add('dark-theme');
            if (themeIcon) themeIcon.className = 'fas fa-sun';
            if (themeText) themeText.textContent = 'Light Mode';
            localStorage.setItem('theme', 'dark');
        }
    }

    async function handleLogout() {
        try {
            // Usar el mismo flujo que el navbar para consistencia
            const response = await fetch('/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            if (response.ok) {
                setTimeout(() => { window.location.href = '/login?session_expired=true'; }, 300);
            } else {
                window.location.href = '/login?auth_error=logout_failed';
            }
        } catch (_) {
            window.location.href = '/login?auth_error=logout_failed';
        }
    }

    // Initialize theme from localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
        const themeIcon = document.getElementById('dropdownThemeIcon');
        const themeText = document.getElementById('dropdownThemeText');
        if (themeIcon) themeIcon.className = 'fas fa-sun';
        if (themeText) themeText.textContent = 'Light Mode';
    }
}