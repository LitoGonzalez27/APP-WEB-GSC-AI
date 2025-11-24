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

        // Pagination state
        this.promptsPerPage = 10;
        this.currentPromptsPage = 1;
        this.allPrompts = [];
        this.promptsSectionCollapsed = false;
        this.isRenderingInModal = false; // Track if we're rendering prompts in modal

        // ✨ NEW: Responses pagination
        this.allResponses = [];
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
    }

    /**
     * Initialize the system
     */
    init() {
        console.log('🎯 Initializing LLM Monitoring System...');

        // Load projects
        this.loadProjects();

        // Setup event listeners
        this.setupEventListeners();

        // Setup chips functionality
        this.setupChipsInputs();
    }

    // ============================================================================
    // CHIPS FUNCTIONALITY
    // ============================================================================

    /**
     * Setup chips inputs with event listeners
     */
    setupChipsInputs() {
        // Brand Keywords
        const brandKeywordsInput = document.getElementById('brandKeywords');
        if (brandKeywordsInput) {
            brandKeywordsInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    this.addChipFromInput('brandKeywords', 'brand');
                }
            });

            brandKeywordsInput.addEventListener('blur', () => {
                this.addChipFromInput('brandKeywords', 'brand');
            });
        }

        // Competitor Domains
        const competitorDomainsInput = document.getElementById('competitorDomains');
        if (competitorDomainsInput) {
            competitorDomainsInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    this.addChipFromInput('competitorDomains', 'competitor-domain');
                }
            });

            competitorDomainsInput.addEventListener('blur', () => {
                this.addChipFromInput('competitorDomains', 'competitor-domain');
            });
        }

        // ✨ NEW: Competitor 1-4 Keywords
        for (let i = 1; i <= 4; i++) {
            const competitorKeywordsInput = document.getElementById(`competitor${i}Keywords`);
            if (competitorKeywordsInput) {
                competitorKeywordsInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ',') {
                        e.preventDefault();
                        this.addChipFromInput(`competitor${i}Keywords`, 'competitor');
                    }
                });

                competitorKeywordsInput.addEventListener('blur', () => {
                    this.addChipFromInput(`competitor${i}Keywords`, 'competitor');
                });
            }
        }
    }

    /**
     * Add chip from input field
     */
    addChipFromInput(inputId, type) {
        const input = document.getElementById(inputId);
        if (!input) return;

        const value = input.value.trim().replace(/,/g, '');

        if (!value) return;

        // Determine which array to use
        let chipsArray;
        if (inputId === 'brandKeywords') {
            chipsArray = this.brandKeywordsChips;
        } else if (inputId === 'competitor1Keywords') {
            chipsArray = this.competitor1KeywordsChips;
        } else if (inputId === 'competitor2Keywords') {
            chipsArray = this.competitor2KeywordsChips;
        } else if (inputId === 'competitor3Keywords') {
            chipsArray = this.competitor3KeywordsChips;
        } else if (inputId === 'competitor4Keywords') {
            chipsArray = this.competitor4KeywordsChips;
        }

        // Check for duplicates
        if (chipsArray.includes(value)) {
            input.value = '';
            return;
        }

        // Add to array
        chipsArray.push(value);

        // Clear input
        input.value = '';

        // Render chips
        this.renderChips(inputId, type);
    }

    /**
     * Render chips in container
     */
    renderChips(inputId, type) {
        const containerId = inputId + 'Chips';
        const container = document.getElementById(containerId);

        if (!container) return;

        // Determine which array to use
        let chipsArray;
        if (inputId === 'brandKeywords') {
            chipsArray = this.brandKeywordsChips;
        } else if (inputId === 'competitor1Keywords') {
            chipsArray = this.competitor1KeywordsChips;
        } else if (inputId === 'competitor2Keywords') {
            chipsArray = this.competitor2KeywordsChips;
        } else if (inputId === 'competitor3Keywords') {
            chipsArray = this.competitor3KeywordsChips;
        } else if (inputId === 'competitor4Keywords') {
            chipsArray = this.competitor4KeywordsChips;
        }

        // Clear container
        container.innerHTML = '';

        // Render each chip
        chipsArray.forEach((value, index) => {
            const chip = document.createElement('div');
            chip.className = `chip chip-${type}`;
            chip.innerHTML = `
                <span class="chip-text">${this.escapeHtml(value)}</span>
                <button type="button" class="chip-remove" data-input="${inputId}" data-index="${index}">
                    <i class="fas fa-times"></i>
                </button>
            `;

            // Add remove event
            const removeBtn = chip.querySelector('.chip-remove');
            removeBtn.addEventListener('click', (e) => {
                const inputIdAttr = e.currentTarget.dataset.input;
                const indexAttr = parseInt(e.currentTarget.dataset.index);
                this.removeChip(inputIdAttr, indexAttr, type);
            });

            container.appendChild(chip);
        });
    }

    /**
     * Remove chip
     */
    removeChip(inputId, index, type) {
        // Determine which array to use
        let chipsArray;
        if (inputId === 'brandKeywords') {
            chipsArray = this.brandKeywordsChips;
        } else if (inputId === 'competitor1Keywords') {
            chipsArray = this.competitor1KeywordsChips;
        } else if (inputId === 'competitor2Keywords') {
            chipsArray = this.competitor2KeywordsChips;
        } else if (inputId === 'competitor3Keywords') {
            chipsArray = this.competitor3KeywordsChips;
        } else if (inputId === 'competitor4Keywords') {
            chipsArray = this.competitor4KeywordsChips;
        }

        // Remove from array
        chipsArray.splice(index, 1);

        // Re-render
        this.renderChips(inputId, type);
    }

    /**
     * Clear all chips
     */
    clearAllChips() {
        this.brandKeywordsChips = [];
        this.competitor1KeywordsChips = [];
        this.competitor2KeywordsChips = [];
        this.competitor3KeywordsChips = [];
        this.competitor4KeywordsChips = [];

        // Clear containers
        const brandContainer = document.getElementById('brandKeywordsChips');
        if (brandContainer) brandContainer.innerHTML = '';

        for (let i = 1; i <= 4; i++) {
            const container = document.getElementById(`competitor${i}KeywordsChips`);
            if (container) container.innerHTML = '';
        }
    }

    /**
     * Load chips from data
     */
    loadChipsFromData(brandKeywords, selectedCompetitors) {
        // Clear existing chips
        this.clearAllChips();

        // Load brand keywords
        if (Array.isArray(brandKeywords) && brandKeywords.length > 0) {
            this.brandKeywordsChips = [...brandKeywords];
            this.renderChips('brandKeywords', 'brand');
        }

        // ✨ NEW: Load selected_competitors into individual fields
        if (Array.isArray(selectedCompetitors) && selectedCompetitors.length > 0) {
            selectedCompetitors.forEach((comp, index) => {
                const competitorNum = index + 1;
                if (competitorNum > 4) return; // Max 4 competitors

                // Set domain field
                const domainInput = document.getElementById(`competitor${competitorNum}Domain`);
                if (domainInput && comp.domain) {
                    domainInput.value = comp.domain;
                }

                // Set keywords chips
                if (Array.isArray(comp.keywords) && comp.keywords.length > 0) {
                    this[`competitor${competitorNum}KeywordsChips`] = [...comp.keywords];
                    this.renderChips(`competitor${competitorNum}Keywords`, 'competitor');
                }
            });
        }
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        console.log('🎯 Setting up event listeners...');

        // Create project button
        const btnCreateProject = document.getElementById('btnCreateProject');
        console.log('📦 btnCreateProject element:', btnCreateProject);

        if (btnCreateProject) {
            btnCreateProject.addEventListener('click', () => {
                console.log('🖱️ btnCreateProject clicked!');
                this.showProjectModal();
            });
            console.log('✅ Event listener added to btnCreateProject');
        } else {
            console.error('❌ btnCreateProject element not found!');
        }

        // Refresh projects
        document.getElementById('btnRefreshProjects')?.addEventListener('click', () => {
            this.loadProjects();
        });

        // Back to projects
        document.getElementById('btnBackToProjects')?.addEventListener('click', () => {
            this.showProjectsList();
        });

        // Modal buttons
        document.getElementById('btnCloseModal')?.addEventListener('click', () => {
            this.hideProjectModal();
        });

        document.getElementById('btnCancelModal')?.addEventListener('click', () => {
            this.hideProjectModal();
        });

        // Form submit handler
        document.getElementById('projectForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            console.log('📝 Form submitted!');
            this.saveProject();
        });

        // Analyze project: REMOVED - Analysis now runs via daily cron, not manual triggers

        // Top URLs LLM filters
        document.getElementById('urlsLLMFilter')?.addEventListener('change', () => {
            if (this.currentProject) {
                // Reset domain view when changing filters
                const domainsBtn = document.getElementById('showTopDomainsLLM');
                if (domainsBtn && domainsBtn.dataset.active === 'true') {
                    domainsBtn.dataset.active = 'false';
                    domainsBtn.classList.remove('active');
                }

                this.loadTopUrlsRanking(this.currentProject.id);
            }
        });

        // ✨ GLOBAL: Share of Voice metric toggle (FAB)
        document.querySelectorAll('input[name="globalSovMetric"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (this.currentProject) {
                    const metricType = e.target.value;
                    console.log(`📊 GLOBAL: Switching to ${metricType} Share of Voice metric`);
                    console.log(`   → Updating all charts and metrics...`);

                    // Guardar preferencia en localStorage
                    localStorage.setItem('llm_monitoring_sov_metric', metricType);

                    // Actualizar TODOS los gráficos, métricas y tablas
                    this.renderShareOfVoiceChart();  // Gráfico de líneas temporal
                    this.renderShareOfVoiceDonutChart();  // Gráfico de rosco/distribución
                    this.renderMentionsTimelineChart();  // Timeline de menciones (usa los mismos datos)
                    this.loadComparison(this.currentProject.id);  // ✨ NUEVO: Tabla LLM Comparison

                    console.log(`✅ All charts and tables updated to ${metricType} metric`);
                }
            });
        });

        // ✨ GLOBAL: Share of Voice info modal (from FAB)
        document.getElementById('btnGlobalSovInfo')?.addEventListener('click', () => {
            this.showSovInfoModal();
        });

        // Restaurar preferencia de métrica desde localStorage
        const savedMetric = localStorage.getItem('llm_monitoring_sov_metric') || 'weighted';
        const radioToCheck = document.getElementById(savedMetric === 'weighted' ? 'globalMetricWeighted' : 'globalMetricNormal');
        if (radioToCheck) {
            radioToCheck.checked = true;
        }

        // Animación de pulso al cargar (destacar el FAB)
        setTimeout(() => {
            document.getElementById('globalMetricFab')?.classList.add('pulse');
            setTimeout(() => {
                document.getElementById('globalMetricFab')?.classList.remove('pulse');
            }, 6000); // 3 pulsos x 2 segundos
        }, 1000);

        document.getElementById('btnCloseSovInfo')?.addEventListener('click', () => {
            this.hideSovInfoModal();
        });

        document.getElementById('btnCloseSovInfoFooter')?.addEventListener('click', () => {
            this.hideSovInfoModal();
        });

        // Close modal on overlay click
        document.getElementById('sovInfoModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'sovInfoModal') {
                this.hideSovInfoModal();
            }
        });

        document.getElementById('urlsDaysFilter')?.addEventListener('change', () => {
            if (this.currentProject) {
                // Reset domain view when changing filters
                const domainsBtn = document.getElementById('showTopDomainsLLM');
                if (domainsBtn && domainsBtn.dataset.active === 'true') {
                    domainsBtn.dataset.active = 'false';
                    domainsBtn.classList.remove('active');
                }

                this.loadTopUrlsRanking(this.currentProject.id);
            }
        });

        document.getElementById('filterMyBrandUrlsLLM')?.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const isActive = btn.dataset.active === 'true';
            btn.dataset.active = !isActive;
            btn.classList.toggle('active', !isActive);

            // Desactivar el botón de dominios si está activo
            const domainsBtn = document.getElementById('showTopDomainsLLM');
            if (domainsBtn && domainsBtn.dataset.active === 'true') {
                domainsBtn.dataset.active = 'false';
                domainsBtn.classList.remove('active');
            }

            if (this.currentProject) {
                this.filterLLMUrlsByBrand(!isActive);
            }
        });

        document.getElementById('showTopDomainsLLM')?.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const isActive = btn.dataset.active === 'true';
            btn.dataset.active = !isActive;
            btn.classList.toggle('active', !isActive);

            // Desactivar el botón de my brand si está activo
            const brandBtn = document.getElementById('filterMyBrandUrlsLLM');
            if (brandBtn && brandBtn.dataset.active === 'true') {
                brandBtn.dataset.active = 'false';
                brandBtn.classList.remove('active');
            }

            if (this.currentProject) {
                this.toggleDomainsView(!isActive);
            }
        });

        // Edit project
        document.getElementById('btnEditProject')?.addEventListener('click', () => {
            this.showProjectModal(this.currentProject);
        });

        // Delete project (from metrics view)
        document.getElementById('btnDeleteProject')?.addEventListener('click', () => {
            if (this.currentProject && this.currentProject.id) {
                this.deleteProject(this.currentProject.id, this.currentProject.name);
            }
        });

        // Export comparison
        document.getElementById('btnExportComparison')?.addEventListener('click', () => {
            this.exportComparison();
        });

        // ✅ NUEVO: Gestión de prompts - Abrir modal
        document.getElementById('btnManagePrompts')?.addEventListener('click', () => {
            this.showPromptsManagementModal();
        });

        // Botones dentro del modal de Prompts Management
        document.getElementById('btnAddPromptsModal')?.addEventListener('click', () => {
            this.showPromptsModal();
        });

        document.getElementById('btnGetSuggestionsModal')?.addEventListener('click', () => {
            this.showSuggestionsModal();
        });

        // Legacy: Mantener botón antiguo por si acaso
        document.getElementById('btnAddPrompts')?.addEventListener('click', () => {
            this.showPromptsModal();
        });

        // Prompts form submit
        document.getElementById('promptsForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.savePrompts();
        });

        // ✅ NUEVO: Sugerencias con IA
        document.getElementById('btnGetSuggestions')?.addEventListener('click', () => {
            this.showSuggestionsModal();
        });

        document.getElementById('btnAddSelectedSuggestions')?.addEventListener('click', () => {
            this.addSelectedSuggestions();
        });

        // ✨ NUEVO: Event listeners para filtros de Responses Inspector
        document.getElementById('responsesQueryFilter')?.addEventListener('change', () => {
            if (this.currentProject?.id) {
                this.loadResponses();
            }
        });

        document.getElementById('responsesLLMFilter')?.addEventListener('change', () => {
            if (this.currentProject?.id) {
                this.loadResponses();
            }
        });

        document.getElementById('responsesDaysFilter')?.addEventListener('change', () => {
            if (this.currentProject?.id) {
                this.loadResponses();
            }
        });

        // ✨ NEW: Global Time Range Selector
        document.getElementById('globalTimeRange')?.addEventListener('change', (e) => {
            if (this.currentProject) {
                this.globalTimeRange = parseInt(e.target.value);
                console.log(`📅 Global time range changed to: ${this.globalTimeRange} days`);

                // Update local filters to match global
                const urlsFilter = document.getElementById('urlsDaysFilter');
                if (urlsFilter) urlsFilter.value = this.globalTimeRange;

                const responsesFilter = document.getElementById('responsesDaysFilter');
                if (responsesFilter) responsesFilter.value = this.globalTimeRange;

                // Reload project data
                this.viewProject(this.currentProject.id);
            }
        });
    }

    /**
     * Load all projects from API
     */
    async loadProjects() {
        console.log('📊 Loading projects...');

        const loading = document.getElementById('projectsLoading');
        const empty = document.getElementById('projectsEmpty');
        const grid = document.getElementById('projectsGrid');

        // Show loading
        loading.style.display = 'flex';
        empty.style.display = 'none';

        // Remove old project cards
        const oldCards = grid.querySelectorAll('.project-card');
        oldCards.forEach(card => card.remove());

        try {
            const response = await fetch(`${this.baseUrl}/projects`, {
                credentials: 'same-origin' // Incluir cookies de sesión
            });

            console.log('📡 Load projects response:', response.status, response.statusText);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log('📦 Projects loaded:', data.projects?.length || 0);

            // Hide loading
            loading.style.display = 'none';

            // Check if we have projects
            if (!data.projects || data.projects.length === 0) {
                console.log('📭 No projects found, showing empty state');
                empty.style.display = 'flex';
                grid.style.display = 'none';
                return;
            }

            // Hide empty state and show grid
            empty.style.display = 'none';
            grid.style.display = 'grid';

            console.log('📦 Rendering', data.projects.length, 'projects...');

            // Clear existing cards
            grid.innerHTML = '';

            // Render project cards
            data.projects.forEach((project, index) => {
                console.log(`  → Rendering project ${index + 1}:`, project.name);
                this.renderProjectCard(project, grid);
            });

            console.log(`✅ Successfully rendered ${data.projects.length} projects`);

        } catch (error) {
            console.error('❌ Error loading projects:', error);
            loading.style.display = 'none';
            this.showError('Failed to load projects. Please try again.');
        }
    }

    /**
     * Render a project card
     */
    renderProjectCard(project, container) {
        const card = document.createElement('div');
        card.className = 'project-card';
        card.innerHTML = `
            <div class="project-card-header">
                <h3>${this.escapeHtml(project.name)}</h3>
                <div class="project-status ${project.is_active ? 'active' : 'inactive'}">
                    ${project.is_active ? 'Active' : 'Inactive'}
                </div>
            </div>
            <div class="project-card-body">
                <div class="project-info">
                    <div class="info-item">
                        <i class="fas fa-tag"></i>
                        <span>${this.escapeHtml(project.brand_name)}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-industry"></i>
                        <span>${this.escapeHtml(project.industry)}</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-robot"></i>
                        <span>${project.enabled_llms.length} LLMs</span>
                    </div>
                    <div class="info-item">
                        <i class="fas fa-users"></i>
                        <span>${project.competitors?.length || 0} Competitors</span>
                    </div>
                </div>
                ${project.last_analysis_date ? `
                    <div class="project-meta">
                        <small>
                            <i class="fas fa-clock"></i>
                            Last analysis: ${this.formatDate(project.last_analysis_date)}
                        </small>
                    </div>
                ` : ''}
            </div>
            <div class="project-card-footer">
                <button class="btn btn-primary btn-sm" onclick="window.llmMonitoring.viewProject(${project.id})">
                    <i class="fas fa-eye"></i>
                    View Metrics
                </button>
                <button class="btn btn-ghost btn-sm" onclick="window.llmMonitoring.showProjectModal(${JSON.stringify(project).replace(/"/g, '&quot;')})">
                    <i class="fas fa-edit"></i>
                    Edit
                </button>
                ${project.is_active ? `
                    <button class="btn btn-ghost btn-sm btn-warning" onclick="window.llmMonitoring.deactivateProject(${project.id}, '${this.escapeHtml(project.name)}')">
                        <i class="fas fa-pause"></i>
                        Deactivate
                    </button>
                ` : `
                    <button class="btn btn-ghost btn-sm btn-success" onclick="window.llmMonitoring.activateProject(${project.id}, '${this.escapeHtml(project.name)}')">
                        <i class="fas fa-play"></i>
                        Activate
                    </button>
                    <button class="btn btn-ghost btn-sm btn-danger" onclick="window.llmMonitoring.deleteProject(${project.id}, '${this.escapeHtml(project.name)}', true)">
                        <i class="fas fa-trash"></i>
                        Delete
                    </button>
                `}
            </div>
        `;

        container.appendChild(card);
    }

    /**
     * View project metrics
     */
    async viewProject(projectId) {
        console.log(`📊 Loading metrics for project ${projectId}...`);

        this.currentProject = { id: projectId };

        // Hide projects, show metrics
        const projectsTab = document.getElementById('projectsTab');
        const metricsSection = document.getElementById('metricsSection');
        const fab = document.getElementById('globalMetricFab');

        console.log('📦 Projects tab element:', projectsTab);
        console.log('📦 Metrics section element:', metricsSection);

        if (projectsTab) {
            projectsTab.style.display = 'none';
            projectsTab.classList.remove('active');
        }
        if (metricsSection) {
            metricsSection.style.display = 'block';
            metricsSection.classList.add('active');
        }
        // ✨ Show FAB when viewing a project
        if (fab) {
            fab.style.display = 'flex';
        }

        try {
            // Load project details with time range
            const response = await fetch(`${this.baseUrl}/projects/${projectId}?days=${this.globalTimeRange}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.currentProject = data.project;

            // Update title
            document.getElementById('projectTitle').textContent = data.project.name;

            // Update KPIs
            this.updateKPIs(data.latest_metrics);

            // ✅ NUEVO: Cargar prompts del proyecto
            await this.loadPrompts(projectId);

            // ✨ NUEVO: Poblar dropdown de prompts en Responses Inspector
            await this.populateQueryFilter();

            // Load detailed metrics
            await this.loadMetrics(projectId);

        } catch (error) {
            console.error('❌ Error loading project:', error);
            this.showError('Failed to load project details.');
            this.showProjectsList();
        }
    }

    /**
     * Update KPI cards
     * 
     * ✨ ACTUALIZADO: Ahora usa métricas AGREGADAS (Método 2: SoV Agregado)
     * Todos los LLMs reciben el mismo valor agregado del backend
     */
    updateKPIs(metrics) {
        if (!metrics || Object.keys(metrics).length === 0) {
            document.getElementById('kpiMentionRate').textContent = 'No data';
            document.getElementById('kpiShareOfVoice').textContent = 'No data';
            document.getElementById('kpiSentiment').textContent = 'No data';
            return;
        }

        // ✨ MÉTODO 2 (SoV Agregado): TODOS los LLMs tienen el MISMO valor agregado
        // Backend ya calcula y envía el mismo valor para todos los LLMs
        const llms = Object.keys(metrics);
        const firstLLM = llms[0];

        // ✨ AGREGADO: Mention Rate (mismo valor para todos los LLMs)
        const aggregatedMentionRate = metrics[firstLLM].mention_rate || 0;

        // ✨ AGREGADO: Share of Voice (mismo valor para todos los LLMs)
        const aggregatedSOV = metrics[firstLLM].share_of_voice || 0;

        // ✨ AGREGADO: Sentiment (mismo valor para todos los LLMs)
        const sentiment = metrics[firstLLM].sentiment || { positive: 0, neutral: 0, negative: 0 };

        // Determinar el sentiment predominante
        let sentimentLabel, sentimentClass;
        if (sentiment.positive >= sentiment.neutral && sentiment.positive >= sentiment.negative) {
            sentimentLabel = 'Positive';
            sentimentClass = 'positive';
        } else if (sentiment.negative > sentiment.positive && sentiment.negative > sentiment.neutral) {
            sentimentLabel = 'Negative';
            sentimentClass = 'negative';
        } else {
            sentimentLabel = 'Neutral';
            sentimentClass = 'neutral';
        }

        document.getElementById('kpiMentionRate').textContent = `${aggregatedMentionRate.toFixed(1)}%`;
        document.getElementById('kpiShareOfVoice').textContent = `${aggregatedSOV.toFixed(1)}%`;
        document.getElementById('kpiSentiment').innerHTML = `<span class="sentiment-${sentimentClass}">${sentimentLabel}</span>`;
    }

    /**
     * Load detailed metrics for a project
     */
    async loadMetrics(projectId) {
        console.log(`📈 Loading detailed metrics for project ${projectId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/metrics?days=${this.globalTimeRange}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            // Render charts
            this.renderMentionRateChart(data);
            await this.renderShareOfVoiceChart();  // Now async - fetches its own data
            await this.renderMentionsTimelineChart();  // Gráfico de líneas de menciones
            await this.renderSentimentDistributionChart();  // Gráfico de distribución de sentimiento
            await this.renderShareOfVoiceDonutChart();  // Gráfico de rosco

            // Load comparison
            await this.loadComparison(projectId);

            // Load queries table
            await this.loadQueriesTable(projectId);

            // Load top URLs ranking
            await this.loadTopUrlsRanking(projectId);

        } catch (error) {
            console.error('❌ Error loading metrics:', error);
            this.showError('Failed to load metrics.');
        }
    }

    /**
     * Render Mention Rate chart
     */
    renderMentionRateChart(data) {
        const canvas = document.getElementById('chartMentionRate');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.mentionRate) {
            this.charts.mentionRate.destroy();
        }

        // Prepare data
        const llms = Object.keys(data.aggregated.metrics_by_llm || {});
        const mentionRates = llms.map(llm => data.aggregated.metrics_by_llm[llm].avg_mention_rate || 0);

        // Create chart
        this.charts.mentionRate = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: llms.map(llm => this.getLLMDisplayName(llm)),
                datasets: [{
                    label: 'Mention Rate (%)',
                    data: mentionRates,
                    backgroundColor: [
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(249, 115, 22, 0.8)',
                        'rgba(139, 92, 246, 0.8)'
                    ],
                    borderColor: [
                        'rgb(59, 130, 246)',
                        'rgb(16, 185, 129)',
                        'rgb(249, 115, 22)',
                        'rgb(139, 92, 246)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: value => value + '%'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: context => `${context.parsed.y.toFixed(1)}%`
                        }
                    }
                }
            }
        });
    }

    /**
     * Show Share of Voice Info Modal
     */
    showSovInfoModal() {
        const modal = document.getElementById('sovInfoModal');
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    /**
     * Hide Share of Voice Info Modal
     */
    hideSovInfoModal() {
        const modal = document.getElementById('sovInfoModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
    }

    /**
     * Render Share of Voice chart
     */
    /**
     * Render Share of Voice chart - TEMPORAL LINE CHART
     * Muestra la evolución del Share of Voice de la marca vs competidores a lo largo del tiempo
     */
    async renderShareOfVoiceChart() {
        const canvas = document.getElementById('chartShareOfVoice');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.shareOfVoice) {
            this.charts.shareOfVoice.destroy();
        }

        // Obtener datos históricos del nuevo endpoint
        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Share of Voice history');
                return;
            }

            // ✨ GLOBAL: Get selected metric type from global FAB toggle
            const metricType = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
            console.log(`📊 Rendering Share of Voice chart with metric: ${metricType}`);

            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=${this.globalTimeRange}&metric=${metricType}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || 'Failed to load Share of Voice history');
            }

            const { dates, datasets } = result;

            // Si no hay datos, simplemente retornar sin renderizar
            if (!dates || dates.length === 0 || !datasets || datasets.length === 0) {
                console.warn('⚠️ No data available for Share of Voice chart');
                return;
            }

            // Formatear fechas para el eje X
            const formattedLabels = dates.map(dateStr => {
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });

            // Configurar leyenda HTML personalizada
            const legendContainer = document.getElementById('shareOfVoiceLegend');
            if (legendContainer) {
                legendContainer.innerHTML = '';

                datasets.forEach((dataset, index) => {
                    const legendItem = document.createElement('div');
                    legendItem.className = 'legend-item';
                    legendItem.dataset.index = index;

                    legendItem.innerHTML = `
                        <div class="legend-color" style="background-color: ${dataset.borderColor}"></div>
                        <div class="legend-label">${dataset.label}</div>
                    `;

                    // Toggle visibility on click
                    legendItem.addEventListener('click', () => {
                        const chart = this.charts.shareOfVoice;
                        const meta = chart.getDatasetMeta(index);
                        meta.hidden = !meta.hidden;
                        chart.update();
                        legendItem.classList.toggle('hidden', meta.hidden);
                    });

                    legendContainer.appendChild(legendItem);
                });
            }

            // Crear gráfico de líneas
            this.charts.shareOfVoice = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: formattedLabels,
                    datasets: datasets.map(ds => ({
                        ...ds,
                        pointBackgroundColor: ds.borderColor,
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: ds.borderColor,
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'circle',
                        pointBorderWidth: 2
                    }))
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: value => `${value}%`,
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            },
                            grid: {
                                color: '#f3f4f6',
                                drawBorder: false
                            },
                            title: {
                                display: true,
                                text: 'Share of Voice (%)',
                                font: {
                                    size: 13,
                                    weight: '600'
                                },
                                color: '#374151'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false  // Usar leyenda HTML personalizada
                        },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            titleFont: {
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                size: 12
                            },
                            callbacks: {
                                title: context => {
                                    return new Date(dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                        weekday: 'short',
                                        year: 'numeric',
                                        month: 'short',
                                        day: 'numeric'
                                    });
                                },
                                label: context => {
                                    return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
                                }
                            }
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Share of Voice history:', error);
        }
    }

    /**
     * Render Mentions Timeline Chart - Gráfico de líneas con total de menciones
     */
    async renderMentionsTimelineChart() {
        const canvas = document.getElementById('chartMentionsTimeline');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.mentionsTimeline) {
            this.charts.mentionsTimeline.destroy();
        }

        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Mentions Timeline');
                return;
            }

            // ⚠️ Total Mentions siempre usa conteo estándar (no weighted)
            // Una mención es una mención - el weighted solo aplica a Share of Voice
            const metricType = 'normal';

            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=30&metric=${metricType}`);
            if (!response.ok) {
                console.warn('Could not load mentions timeline data');
                return;
            }

            const result = await response.json();

            if (!result.success || !result.mentions_datasets || !result.dates || result.dates.length === 0) {
                console.warn('⚠️ No mentions data available yet for this project');
                return;
            }

            const { dates, mentions_datasets } = result;

            // Formatear fechas para el eje X
            const formattedLabels = dates.map(dateStr => {
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });

            // Configurar leyenda HTML
            const legendContainer = document.getElementById('mentionsTimelineLegend');
            if (legendContainer) {
                legendContainer.innerHTML = '';

                mentions_datasets.forEach((dataset, index) => {
                    const legendItem = document.createElement('div');
                    legendItem.className = 'legend-item';
                    legendItem.dataset.index = index;

                    legendItem.innerHTML = `
                        <div class="legend-color" style="background-color: ${dataset.borderColor}"></div>
                        <div class="legend-label">${dataset.label}</div>
                    `;

                    legendItem.addEventListener('click', () => {
                        const chart = this.charts.mentionsTimeline;
                        const meta = chart.getDatasetMeta(index);
                        meta.hidden = !meta.hidden;
                        chart.update();
                        legendItem.classList.toggle('hidden', meta.hidden);
                    });

                    legendContainer.appendChild(legendItem);
                });
            }

            // Crear gráfico
            this.charts.mentionsTimeline = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: formattedLabels,
                    datasets: mentions_datasets.map(ds => ({
                        ...ds,
                        pointBackgroundColor: ds.borderColor,
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: ds.borderColor,
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'circle',
                        pointBorderWidth: 2
                    }))
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: value => Math.round(value),
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            },
                            grid: {
                                color: '#f3f4f6',
                                drawBorder: false
                            },
                            title: {
                                display: true,
                                text: 'Total Mentions',
                                font: {
                                    size: 13,
                                    weight: '600'
                                },
                                color: '#374151'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            titleFont: {
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                size: 12
                            },
                            callbacks: {
                                title: context => {
                                    return new Date(dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                        weekday: 'short',
                                        year: 'numeric',
                                        month: 'short',
                                        day: 'numeric'
                                    });
                                },
                                label: context => {
                                    return `${context.dataset.label}: ${Math.round(context.parsed.y)} mentions`;
                                }
                            }
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Mentions Timeline:', error);
        }
    }

    /**
     * Render Share of Voice Donut Chart - Gráfico de rosco con distribución
     */
    async renderShareOfVoiceDonutChart() {
        const canvas = document.getElementById('chartShareOfVoiceDonut');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.shareOfVoiceDonut) {
            this.charts.shareOfVoiceDonut.destroy();
        }

        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Share of Voice Donut');
                return;
            }

            // ✨ GLOBAL: Get selected metric type from global FAB toggle
            const metricType = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
            console.log(`📊 Rendering Share of Voice Donut with metric: ${metricType}`);

            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=30&metric=${metricType}`);
            if (!response.ok) {
                console.warn('Could not load Share of Voice donut data');
                return;
            }

            const result = await response.json();

            if (!result.success || !result.donut_data) {
                console.warn('⚠️ No donut data available yet for this project');
                return;
            }

            const { donut_data } = result;

            // Si no hay datos, simplemente retornar
            if (!donut_data.labels || donut_data.labels.length === 0) {
                console.warn('⚠️ No distribution data available');
                return;
            }

            // Crear gráfico de rosco
            this.charts.shareOfVoiceDonut = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: donut_data.labels,
                    datasets: [{
                        data: donut_data.values,
                        backgroundColor: donut_data.colors,
                        borderWidth: 3,
                        borderColor: '#fff',
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                font: {
                                    size: 13,
                                    weight: '500'
                                },
                                color: '#374151',
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            titleFont: {
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                size: 12
                            },
                            callbacks: {
                                label: context => {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    return `${label}: ${value.toFixed(1)}%`;
                                }
                            }
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Share of Voice Donut:', error);
        }
    }

    /**
     * Render Sentiment Distribution Chart
     */
    async renderSentimentDistributionChart() {
        const canvas = document.getElementById('chartSentimentDistribution');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.sentimentDistribution) {
            this.charts.sentimentDistribution.destroy();
        }

        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Sentiment Distribution');
                return;
            }

            // Obtener datos de snapshots (comparación) que incluyen sentimiento
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/comparison`);
            if (!response.ok) {
                console.warn('Could not load sentiment data');
                return;
            }

            const result = await response.json();

            if (!result.comparison || result.comparison.length === 0) {
                console.warn('⚠️ No comparison data available for sentiment analysis');
                return;
            }

            // Agregar contadores de sentimiento de todos los LLMs (último snapshot)
            let totalPositive = 0;
            let totalNeutral = 0;
            let totalNegative = 0;

            // Usar solo los datos más recientes (primeros resultados)
            const recentSnapshots = result.comparison.slice(0, 4); // Último análisis de cada LLM

            recentSnapshots.forEach(snapshot => {
                if (snapshot.sentiment) {
                    totalPositive += snapshot.sentiment.positive || 0;
                    totalNeutral += snapshot.sentiment.neutral || 0;
                    totalNegative += snapshot.sentiment.negative || 0;
                }
            });

            const total = totalPositive + totalNeutral + totalNegative;

            if (total === 0) {
                console.warn('⚠️ No sentiment data available');
                return;
            }

            // Calcular porcentajes promedio
            const avgPositive = totalPositive / recentSnapshots.length;
            const avgNeutral = totalNeutral / recentSnapshots.length;
            const avgNegative = totalNegative / recentSnapshots.length;

            const data = {
                labels: ['Positive', 'Neutral', 'Negative'],
                values: [
                    avgPositive.toFixed(1),
                    avgNeutral.toFixed(1),
                    avgNegative.toFixed(1)
                ],
                colors: [
                    'rgba(34, 197, 94, 0.8)',   // Green for positive
                    'rgba(245, 158, 11, 0.8)',  // Orange for neutral
                    'rgba(239, 68, 68, 0.8)'    // Red for negative
                ]
            };

            // Crear gráfico de rosco
            this.charts.sentimentDistribution = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.values,
                        backgroundColor: data.colors,
                        borderWidth: 3,
                        borderColor: '#fff',
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                font: {
                                    size: 13,
                                    weight: '500'
                                },
                                color: '#374151',
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            titleFont: {
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                size: 12
                            },
                            callbacks: {
                                label: context => {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    return `${label}: ${value}%`;
                                }
                            }
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Sentiment Distribution:', error);
        }
    }

    /**
     * Load comparison table
     */
    async loadComparison(projectId) {
        console.log(`📊 Loading comparison for project ${projectId}...`);

        try {
            // ✨ GLOBAL: Get selected metric type from global FAB toggle
            const metricType = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
            console.log(`📊 Loading comparison with metric: ${metricType}`);

            const response = await fetch(`${this.baseUrl}/projects/${projectId}/comparison?metric=${metricType}&days=${this.globalTimeRange}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            this.renderComparisonTable(data.comparison);

        } catch (error) {
            console.error('❌ Error loading comparison:', error);
        }
    }

    /**
     * Render comparison table with Grid.js
     */
    renderComparisonTable(data) {
        const container = document.getElementById('comparisonTable');
        if (!container) return;

        // Destroy existing grid
        if (this.comparisonGrid) {
            this.comparisonGrid.destroy();
        }

        // Prepare data
        const rows = data.map(item => [
            this.getLLMDisplayName(item.llm_provider),
            this.formatDate(item.snapshot_date),
            `${item.mention_rate.toFixed(1)}% (${(item.total_mentions || 0)}/${(item.total_queries || 0)})`,
            this.formatPositionWithBadge(item.avg_position, item.position_source, item.position_source_details),
            `${item.share_of_voice.toFixed(1)}%`,
            this.getSentimentLabel(item.sentiment),
            item.total_queries
        ]);

        // Create grid
        this.comparisonGrid = new gridjs.Grid({
            columns: [
                { name: 'LLM', width: '120px' },
                { name: 'Date', width: '100px' },
                { name: 'Mention Rate', width: '100px' },
                { name: 'Avg Position', width: '100px' },
                { name: 'Share of Voice', width: '120px' },
                { name: 'Sentiment', width: '100px' },
                { name: 'Prompts', width: '80px' }
            ],
            data: rows,
            sort: true,
            search: true,
            pagination: {
                limit: 10
            },
            style: {
                table: {
                    'font-size': '14px'
                }
            }
        }).render(container);
    }

    /**
     * Load and render queries table
     */
    async loadQueriesTable(projectId) {
        console.log(`📝 Loading queries table for project ${projectId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/queries?days=${this.globalTimeRange}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || 'Failed to load queries');
            }

            console.log(`✅ Loaded ${result.queries.length} queries`);
            this.renderQueriesTable(result.queries);

        } catch (error) {
            console.error('❌ Error loading queries:', error);
            const container = document.getElementById('queriesTable');
            if (container) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 2rem; color: #ef4444;">
                        <i class="fas fa-exclamation-triangle" style="font-size: 2rem; opacity: 0.5; margin-bottom: 1rem;"></i>
                        <p>Error loading queries table</p>
                    </div>
                `;
            }
        }
    }

    /**
     * Render queries table with Grid.js
     */
    renderQueriesTable(queries) {
        const container = document.getElementById('queriesTable');
        if (!container) return;

        // Destroy existing grid
        if (this.queriesGrid) {
            this.queriesGrid.destroy();
        }

        // Si no hay queries, mostrar mensaje
        if (!queries || queries.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: #6b7280;">
                    <i class="fas fa-list-ul" style="font-size: 3rem; opacity: 0.3; margin-bottom: 1rem; display: block;"></i>
                    <p style="font-size: 1rem; font-weight: 500;">No queries found</p>
                    <p style="font-size: 0.875rem; margin-top: 0.5rem;">Run analysis to see query results</p>
                </div>
            `;
            return;
        }

        // ✨ NUEVO: Guardar queries data para acceso en acordeón
        this.queriesData = queries;
        this.expandedRows = new Set(); // Track expanded rows

        // Formatear datos para la tabla
        const rows = queries.map((q, idx) => {
            const visibilityPct = q.visibility_pct != null ? q.visibility_pct : 0;
            const visibilityStr = visibilityPct.toFixed(1);

            // ✨ NUEVO: Botón que abre modal con análisis detallado
            const viewDetailsBtn = gridjs.html(`
                <button 
                    class="view-details-btn" 
                    data-row-idx="${idx}"
                    title="View detailed analysis"
                    style="
                        background: linear-gradient(135deg, #D8F9B8 0%, #a8e063 100%);
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        padding: 0.4rem 0.65rem;
                        color: #1a1a1a;
                        font-size: 0.8rem;
                        font-weight: 600;
                        transition: all 0.2s;
                        display: inline-flex;
                        align-items: center;
                        gap: 0.4rem;
                        box-shadow: 0 2px 4px rgba(216, 249, 184, 0.2);
                        white-space: nowrap;
                    "
                    onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 8px rgba(216, 249, 184, 0.3)'"
                    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(216, 249, 184, 0.2)'"
                >
                    <i class="fas fa-chart-bar"></i>
                    <span>Details</span>
                </button>
            `);

            return [
                viewDetailsBtn,  // ✨ NUEVO: Botón para ver detalles
                q.prompt,
                q.country,
                q.language ? q.language.toUpperCase() : 'N/A',
                q.total_mentions || 0,
                // Visibility con barra de progreso
                gridjs.html(`
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="flex: 1; background: #e5e7eb; border-radius: 9999px; height: 8px; overflow: hidden;">
                            <div style="height: 100%; background: linear-gradient(90deg, #22c55e ${visibilityPct}%, transparent ${visibilityPct}%); width: 100%; border-radius: 9999px;"></div>
                        </div>
                        <span style="font-weight: 600; min-width: 45px;">${visibilityStr}%</span>
                    </div>
                `)
            ];
        });

        // Create grid
        this.queriesGrid = new gridjs.Grid({
            columns: [
                { id: 'expand', name: '', width: '40px', sort: false },  // ✨ NUEVO: Columna expandible
                { id: 'prompt', name: 'Prompt', width: '320px' },
                { id: 'country', name: 'Country', width: '80px' },
                { id: 'language', name: 'Language', width: '90px' },
                { id: 'mentions', name: 'Total Mentions (30d)', width: '140px', sort: true },
                { id: 'visibility', name: 'Avg Visibility % (30d)', width: '180px', sort: true }
            ],
            data: rows,
            sort: true,
            search: {
                placeholder: 'Search prompts...'
            },
            pagination: {
                limit: 10,
                summary: true
            },
            style: {
                table: {
                    'font-size': '14px'
                },
                th: {
                    'background-color': '#161616',
                    'color': '#D8F9B8',
                    'font-weight': '700',
                    'padding': '1rem'
                },
                td: {
                    'padding': '0.875rem'
                }
            },
            className: {
                table: 'llm-queries-table'
            }
        }).render(container);

        // ✨ NUEVO: Añadir event listeners para abrir modal
        const attachWithRetry = (attempts = 0) => {
            const detailBtns = document.querySelectorAll('.view-details-btn');
            if (detailBtns.length > 0) {
                console.log(`✅ Found ${detailBtns.length} detail buttons, attaching listeners...`);
                this.attachDetailListeners();
            } else if (attempts < 5) {
                console.log(`⏳ Detail buttons not ready, retrying... (attempt ${attempts + 1})`);
                setTimeout(() => attachWithRetry(attempts + 1), 200);
            } else {
                console.warn('⚠️ Could not find detail buttons after 5 attempts');
            }
        };

        setTimeout(() => attachWithRetry(), 100);
    }

    /**
     * ✨ NUEVO: Attach event listeners to detail buttons
     */
    attachDetailListeners() {
        const detailBtns = document.querySelectorAll('.view-details-btn');
        console.log(`🔗 Attaching listeners to ${detailBtns.length} detail buttons`);
        detailBtns.forEach((btn, idx) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const rowIdx = parseInt(btn.dataset.rowIdx);
                console.log(`📊 Opening brand mentions modal for row ${rowIdx}`);
                this.showBrandMentionsModal(rowIdx);
            });
        });
    }

    /**
     * ✨ NUEVO: Show brand mentions modal
     */
    showBrandMentionsModal(rowIdx) {
        const query = this.queriesData[rowIdx];
        if (!query) return;

        const modal = document.getElementById('brandMentionsModal');
        const modalTitle = document.getElementById('brandMentionsModalPrompt');
        const modalBody = document.getElementById('brandMentionsModalBody');

        if (!modal || !modalBody) {
            console.error('❌ Modal elements not found');
            return;
        }

        // Set prompt text in modal header
        modalTitle.textContent = `"${query.prompt}"`;

        // Render modal content
        modalBody.innerHTML = this.renderBrandMentionsModalContent(query);

        // Show modal
        modal.style.display = 'flex';

        // Add fade-in animation
        setTimeout(() => {
            modal.style.opacity = '1';
        }, 10);
    }

    /**
     * ✨ NUEVO: Hide brand mentions modal
     */
    hideBrandMentionsModal() {
        const modal = document.getElementById('brandMentionsModal');
        if (!modal) return;

        modal.style.opacity = '0';
        setTimeout(() => {
            modal.style.display = 'none';
        }, 200);
    }

    /**
     * ✨ NUEVO: Render brand mentions modal content
     */
    renderBrandMentionsModalContent(query) {
        const mentionsByLLM = query.mentions_by_llm || {};
        const llmNames = Object.keys(mentionsByLLM);

        if (llmNames.length === 0) {
            return `
                <div style="padding: 1.5rem; color: #9ca3af; text-align: center;">
                    <i class="fas fa-info-circle" style="margin-right: 0.5rem;"></i>
                    No analysis data available for this prompt yet.
                </div>
            `;
        }

        // Calculate summary
        let brandMentionedCount = 0;
        const allCompetitors = new Set();
        const competitorCounts = {};

        llmNames.forEach(llm => {
            const data = mentionsByLLM[llm];
            if (data.brand_mentioned) brandMentionedCount++;

            Object.keys(data.competitors || {}).forEach(comp => {
                allCompetitors.add(comp);
                competitorCounts[comp] = (competitorCounts[comp] || 0) + 1;
            });
        });

        // Build HTML
        let html = `
            <div style="padding: 0;">
                <!-- Summary Cards -->
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.25rem; margin-bottom: 2rem;">
                    <!-- Your Brand Card -->
                    <div style="background: linear-gradient(135deg, ${brandMentionedCount > 0 ? '#064e3b' : '#7f1d1d'} 0%, ${brandMentionedCount > 0 ? '#065f46' : '#991b1b'} 100%); padding: 1.5rem; border-radius: 12px; border: 2px solid ${brandMentionedCount > 0 ? '#10b981' : '#ef4444'}; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                            <div style="color: #9ca3af; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600;">Your Brand</div>
                            <div style="background: rgba(255,255,255,0.1); padding: 0.375rem 0.625rem; border-radius: 6px; font-size: 1.25rem;">
                                ${brandMentionedCount > 0 ? '✅' : '❌'}
                            </div>
                        </div>
                        <div style="color: white; font-size: 2.5rem; font-weight: 700; line-height: 1; margin-bottom: 0.5rem;">${brandMentionedCount}<span style="font-size: 1.5rem; color: #9ca3af;">/${llmNames.length}</span></div>
                        <div style="color: #d1d5db; font-size: 0.9rem;">LLMs mentioned</div>
                    </div>
                    
                    <!-- Competitors Card -->
                    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 1.5rem; border-radius: 12px; border: 2px solid #475569; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                            <div style="color: #9ca3af; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600;">Competitors</div>
                            <div style="background: rgba(255,255,255,0.1); padding: 0.375rem 0.625rem; border-radius: 6px; font-size: 1.25rem;">
                                ⚔️
                            </div>
                        </div>
                        <div style="color: white; font-size: 2.5rem; font-weight: 700; line-height: 1; margin-bottom: 0.5rem;">${allCompetitors.size}</div>
                        <div style="color: #d1d5db; font-size: 0.9rem;">Mentioned total</div>
                    </div>
                </div>
                
                <!-- Detailed Breakdown -->
                <div style="background: linear-gradient(to bottom, #0a0a0a, #1a1a1a); border-radius: 12px; padding: 1.5rem; border: 1px solid #333; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
                    <div style="font-weight: 700; color: #D8F9B8; margin-bottom: 1.25rem; font-size: 1rem; display: flex; align-items: center; gap: 0.5rem;">
                        <div style="background: linear-gradient(135deg, #D8F9B8, #a8e063); width: 4px; height: 20px; border-radius: 2px;"></div>
                        <i class="fas fa-list-ul"></i>
                        <span>Breakdown by LLM</span>
                    </div>
                    <div style="display: grid; gap: 1rem;">
        `;

        // LLM rows
        llmNames.forEach(llm => {
            const data = mentionsByLLM[llm];
            const llmDisplayName = this.getLLMDisplayName(llm);
            const brandIcon = data.brand_mentioned ? '✅' : '❌';
            const brandColor = data.brand_mentioned ? '#10b981' : '#6b7280';
            const position = data.position ? `#${data.position}` : 'N/A';

            // 🔧 FIX: Mostrar badge de tipo de mención (texto/URL/ambos)
            let mentionBadge = '';
            if (data.brand_mentioned) {
                const inText = data.brand_mentioned_in_text;
                const inUrls = data.brand_mentioned_in_urls;

                if (inText && inUrls) {
                    mentionBadge = '<span style="background: #064e3b; color: #10b981; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem;" title="Mentioned in text and URLs">📝🔗</span>';
                } else if (inText) {
                    mentionBadge = '<span style="background: #064e3b; color: #10b981; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem;" title="Mentioned in text">📝</span>';
                } else if (inUrls) {
                    mentionBadge = '<span style="background: #1e3a5f; color: #60a5fa; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem;" title="Mentioned in URLs only">🔗</span>';
                }
            }

            const competitorsStr = Object.keys(data.competitors || {}).length > 0
                ? Object.keys(data.competitors).map(c => `<span style="background: #1e293b; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">${c}</span>`).join(' ')
                : '<span style="color: #6b7280; font-size: 0.75rem;">None</span>';

            html += `
                <div style="display: grid; grid-template-columns: 140px 120px 1fr; gap: 1.25rem; align-items: center; padding: 1rem 1.25rem; background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%); border-radius: 10px; border: 1px solid ${data.brand_mentioned ? '#374151' : '#262626'}; transition: all 0.2s; ${data.brand_mentioned ? 'box-shadow: 0 2px 8px rgba(16, 185, 129, 0.1);' : ''}">
                    <div style="font-weight: 600; color: white; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="${this.getLLMIcon(llm)}" style="color: ${this.getLLMColor(llm)};"></i>
                        ${llmDisplayName}
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.625rem;">
                        <span style="font-size: 1.25rem;">${brandIcon}</span>
                        <span style="color: ${brandColor}; font-weight: 700; font-size: 0.95rem;">${position}</span>
                        ${mentionBadge}
                    </div>
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
                        <span style="color: #6b7280; font-size: 0.8rem; font-weight: 600;">Competitors:</span>
                        ${competitorsStr}
                    </div>
                </div>
            `;
        });

        html += `
                    </div>
                </div>
                
                <!-- Leyenda explicativa con diseño moderno -->
                <div style="margin-top: 1.5rem; padding: 1.25rem; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 10px; border: 1px solid #475569;">
                    <div style="color: #D8F9B8; font-size: 0.85rem; margin-bottom: 0.875rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-info-circle"></i>
                        <span>Mention Type Legend</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.875rem; font-size: 0.8rem; color: #d1d5db;">
                        <div style="display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem; background: rgba(255,255,255,0.05); border-radius: 6px;">
                            <span style="background: #064e3b; color: #10b981; padding: 0.25rem 0.625rem; border-radius: 6px; font-weight: 600;">📝</span>
                            <span>Text mention</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem; background: rgba(255,255,255,0.05); border-radius: 6px;">
                            <span style="background: #1e3a5f; color: #60a5fa; padding: 0.25rem 0.625rem; border-radius: 6px; font-weight: 600;">🔗</span>
                            <span>URL citation</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem; background: rgba(255,255,255,0.05); border-radius: 6px;">
                            <span style="background: #064e3b; color: #10b981; padding: 0.25rem 0.625rem; border-radius: 6px; font-weight: 600;">📝🔗</span>
                            <span>Both</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        return html;
    }

    /**
     * Format relative time (e.g., "2 hours ago")
     */
    formatRelativeTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffSeconds = Math.floor(diffMs / 1000);
        const diffMinutes = Math.floor(diffSeconds / 60);
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffSeconds < 60) return 'just now';
        if (diffMinutes < 60) return `${diffMinutes} min ago`;
        if (diffHours < 24) return `${diffHours} hours ago`;
        if (diffDays < 7) return `${diffDays} days ago`;

        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    /**
     * Show projects list
     */
    showProjectsList() {
        const projectsTab = document.getElementById('projectsTab');
        const metricsSection = document.getElementById('metricsSection');
        const fab = document.getElementById('globalMetricFab');

        if (projectsTab) {
            projectsTab.style.display = 'block';
            projectsTab.classList.add('active');
        }
        if (metricsSection) {
            metricsSection.style.display = 'none';
            metricsSection.classList.remove('active');
        }
        // ✨ Hide FAB when viewing projects list
        if (fab) {
            fab.style.display = 'none';
        }
        this.currentProject = null;
    }

    /**
     * ✨ NUEVO: Desactivar un proyecto (deja de ejecutarse en CRON)
     */
    async deactivateProject(projectId, projectName) {
        console.log(`⏸️ Deactivating project ${projectId}...`);

        // Confirm deactivation
        if (!confirm(`Are you sure you want to deactivate the project "${projectName}"?\n\nThe project will stop running in automatic analysis, but all data will be preserved.`)) {
            return;
        }

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/deactivate`, {
                method: 'PUT',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            console.log(`✅ Project ${projectId} deactivated`);

            // If we're viewing this project, update current project state
            if (this.currentProject && this.currentProject.id === projectId) {
                this.currentProject.is_active = false;
            }

            // Reload projects list
            await this.loadProjects();

            this.showSuccess(`Project "${projectName}" deactivated. It won't run in automatic analysis.`);

        } catch (error) {
            console.error('❌ Error deactivating project:', error);
            this.showError(error.message || 'Failed to deactivate project');
        }
    }

    /**
     * ✨ NUEVO: Reactivar un proyecto inactivo
     */
    async activateProject(projectId, projectName) {
        console.log(`▶️ Activating project ${projectId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/activate`, {
                method: 'PUT',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            console.log(`✅ Project ${projectId} activated`);

            // If we're viewing this project, update current project state
            if (this.currentProject && this.currentProject.id === projectId) {
                this.currentProject.is_active = true;
            }

            // Reload projects list
            await this.loadProjects();

            this.showSuccess(`Project "${projectName}" activated. It will be included in next automatic analysis.`);

        } catch (error) {
            console.error('❌ Error activating project:', error);
            this.showError(error.message || 'Failed to activate project');
        }
    }

    /**
     * Delete a project (permanent deletion, only works if inactive)
     */
    async deleteProject(projectId, projectName, isPermanent = false) {
        console.log(`🗑️ Deleting project ${projectId}... (permanent: ${isPermanent})`);

        // Confirm deletion
        const message = isPermanent
            ? `⚠️ PERMANENT DELETION\n\nAre you sure you want to permanently delete the project "${projectName}"?\n\nThis will delete:\n- The project\n- All queries\n- All analysis results\n- All snapshots\n\nThis action CANNOT be undone!`
            : `Are you sure you want to delete the project "${projectName}"?\n\nThis action cannot be undone.`;

        if (!confirm(message)) {
            return;
        }

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}`, {
                method: 'DELETE',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const error = await response.json();
                if (error.action_required === 'deactivate_first') {
                    this.showError('Please deactivate the project first before deleting it.');
                    return;
                }
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            const result = await response.json();
            console.log(`✅ Project ${projectId} deleted permanently:`, result.stats);

            // If we're viewing this project, go back to projects list
            if (this.currentProject && this.currentProject.id === projectId) {
                this.showProjectsList();
            }

            // Reload projects list
            await this.loadProjects();

            this.showSuccess(`Project "${projectName}" permanently deleted.`);

        } catch (error) {
            console.error('❌ Error deleting project:', error);
            this.showError(error.message || 'Failed to delete project');
        }
    }

    /**
     * Show project modal (create or edit)
     */
    showProjectModal(project = null) {
        console.log('🎬 showProjectModal() called, project:', project);

        const modal = document.getElementById('projectModal');
        const title = document.getElementById('modalTitle');
        const modalDesc = document.getElementById('modalDesc');
        const btnText = document.getElementById('btnSaveText');

        console.log('📦 Modal element:', modal);
        console.log('📦 Title element:', title);
        console.log('📦 Modal desc element:', modalDesc);
        console.log('📦 Button text element:', btnText);

        // Store current project for later use
        this.currentProject = project;

        // Clear all chips first
        this.clearAllChips();

        if (project) {
            // Edit mode
            title.textContent = 'Edit LLM Monitoring Project';
            if (modalDesc) modalDesc.textContent = 'Update your project settings and configuration';
            btnText.textContent = 'Update Project';

            // Fill form
            document.getElementById('projectName').value = project.name || '';
            document.getElementById('industry').value = project.industry || '';
            document.getElementById('language').value = project.language || 'es';
            document.getElementById('countryCode').value = project.country_code || 'ES';
            document.getElementById('queriesPerLlm').value = project.queries_per_llm || 15;

            // Fill brand domain
            document.getElementById('brandDomain').value = project.brand_domain || '';

            // ✨ NEW: Load chips from project data (including selected_competitors)
            this.loadChipsFromData(
                project.brand_keywords || [],
                project.selected_competitors || []
            );

            // Check LLMs
            const llmCheckboxes = document.querySelectorAll('input[name="llm"]');
            llmCheckboxes.forEach(cb => {
                cb.checked = project.enabled_llms?.includes(cb.value) || false;
            });
        } else {
            // Create mode
            title.textContent = 'Create New LLM Monitoring Project';
            if (modalDesc) modalDesc.textContent = 'Set up a new project to track brand visibility in LLMs';
            btnText.textContent = 'Create Project';

            // Reset form
            document.getElementById('projectForm').reset();

            // Check all LLMs by default
            const llmCheckboxes = document.querySelectorAll('input[name="llm"]');
            llmCheckboxes.forEach(cb => cb.checked = true);
        }

        console.log('👁️ Setting modal display to flex...');
        modal.style.display = 'flex';
        console.log('✅ Modal display set:', modal.style.display);
        console.log('✅ Modal should now be visible');

        // Add a slight delay to ensure styles are applied
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
    }

    /**
     * Hide project modal
     */
    hideProjectModal() {
        const modal = document.getElementById('projectModal');
        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300); // Match transition duration
    }

    /**
     * Save project (create or update)
     */
    async saveProject() {
        console.log('💾 Saving project...');

        // Get form data
        const name = document.getElementById('projectName').value.trim();
        const industry = document.getElementById('industry').value.trim();
        const brandDomain = document.getElementById('brandDomain').value.trim();
        const language = document.getElementById('language').value;
        const countryCode = document.getElementById('countryCode').value;
        const queriesPerLlm = parseInt(document.getElementById('queriesPerLlm').value);

        // Get checked LLMs
        const llmCheckboxes = document.querySelectorAll('input[name="llm"]:checked');
        const enabledLlms = Array.from(llmCheckboxes).map(cb => cb.value);

        // Validate
        if (!name || !industry) {
            this.showError('Please fill all required fields');
            return;
        }

        // Validate brand keywords (required)
        if (this.brandKeywordsChips.length === 0) {
            this.showError('Please add at least one brand keyword');
            return;
        }

        if (enabledLlms.length === 0) {
            this.showError('Please select at least one LLM');
            return;
        }

        if (queriesPerLlm < 5 || queriesPerLlm > 50) {
            this.showError('Queries per LLM must be between 5 and 50');
            return;
        }

        // ✨ NEW: Build selected_competitors array from 4 individual fields
        const selectedCompetitors = [];
        for (let i = 1; i <= 4; i++) {
            const domainInput = document.getElementById(`competitor${i}Domain`);
            const domain = domainInput ? domainInput.value.trim() : '';
            const keywords = this[`competitor${i}KeywordsChips`] || [];

            // Only add if domain is provided OR if there are keywords
            if (domain || (keywords && keywords.length > 0)) {
                selectedCompetitors.push({
                    domain: domain || '',
                    keywords: keywords
                });
            }
        }

        // Prepare payload with new structure
        const payload = {
            name,
            industry,
            brand_domain: brandDomain || null,
            brand_keywords: this.brandKeywordsChips,
            selected_competitors: selectedCompetitors, // ✨ NEW: Use new structure
            language,
            country_code: countryCode,
            enabled_llms: enabledLlms,
            queries_per_llm: queriesPerLlm
        };

        // Show loading
        const btnSave = document.getElementById('btnSaveProject');
        const btnText = document.getElementById('btnSaveText');
        const originalText = btnText.textContent;

        const isEdit = this.currentProject && this.currentProject.id;

        console.log('🔄 Disabling button and showing loading...');
        btnText.textContent = isEdit ? 'Updating...' : 'Creating...';
        btnSave.disabled = true;
        btnSave.classList.add('loading');

        try {
            const url = isEdit ? `${this.baseUrl}/projects/${this.currentProject.id}` : `${this.baseUrl}/projects`;
            const method = isEdit ? 'PUT' : 'POST';

            console.log(`📡 Sending ${method} request to:`, url);
            console.log('📦 Payload:', payload);

            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin', // Incluir cookies de sesión
                body: JSON.stringify(payload)
            });

            console.log('📡 Response status:', response.status, response.statusText);

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}`;
                try {
                    const error = await response.json();
                    errorMessage = error.error || errorMessage;
                    console.error('❌ Server error:', error);
                } catch (e) {
                    console.error('❌ Failed to parse error response:', e);
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();

            console.log(`✅ Project ${isEdit ? 'updated' : 'created'} successfully:`, data);

            // Hide modal
            this.hideProjectModal();

            // Reload projects
            this.loadProjects();

            // Show success message
            this.showSuccess(`Project ${isEdit ? 'updated' : 'created'} successfully!`);

        } catch (error) {
            console.error('❌ Error saving project:', error);
            this.showError(error.message || 'Failed to save project');
        } finally {
            console.log('🔄 Re-enabling button...');
            btnText.textContent = originalText;
            btnSave.disabled = false;
            btnSave.classList.remove('loading');
        }
    }

    /**
     * Run analysis on current project
     * 
     * REMOVED: Manual analysis is no longer supported.
     * Analysis now runs automatically via daily cron job at 4:00 AM.
     * 
     * This ensures:
     * - 100% completeness (all LLMs, all prompts)
     * - Reliable data collection
     * - No timeout issues (analysis can take 15-30 minutes)
     * - Automatic retry and reconciliation
     * 
     * Users can view the latest analysis results in the dashboard,
     * which are updated daily by the cron job.
     */

    /**
     * Load budget information
     * 
     * NOTA: Este método está deshabilitado porque en el modelo de negocio actual,
     * los usuarios NO configuran presupuestos individuales. El dueño del servicio
     * gestiona las API keys y los costes de forma global.
     * 
     * Si en el futuro se implementa un plan "Enterprise" donde los usuarios
     * configuren sus propios presupuestos, este método se puede reactivar.
     */
    /*
    async loadBudget() {
        try {
            const response = await fetch(`${this.baseUrl}/budget`);
            
            if (!response.ok) return;
            
            const data = await response.json();
            
            if (data.configured && data.budget) {
                const { is_over_budget, is_near_limit, percentage_used, monthly_budget_usd, current_month_spend } = data.budget;
                
                const alert = document.getElementById('budgetAlert');
                const alertText = document.getElementById('budgetAlertText');
                
                if (is_over_budget) {
                    alert.className = 'alert alert-danger';
                    alertText.textContent = `Budget exceeded! $${current_month_spend.toFixed(2)} / $${monthly_budget_usd.toFixed(2)} (${percentage_used.toFixed(1)}%)`;
                    alert.style.display = 'flex';
                } else if (is_near_limit) {
                    alert.className = 'alert alert-warning';
                    alertText.textContent = `Approaching budget limit: $${current_month_spend.toFixed(2)} / $${monthly_budget_usd.toFixed(2)} (${percentage_used.toFixed(1)}%)`;
                    alert.style.display = 'flex';
                }
            }
        } catch (error) {
            console.error('❌ Error loading budget:', error);
        }
    }
    */

    /**
     * Export comparison data
     */
    exportComparison() {
        if (this.comparisonGrid) {
            // This would require additional implementation
            // For now, just show a message
            this.showInfo('Export functionality coming soon!');
        }
    }

    // ============================================================================
    // PROMPTS MANAGEMENT (NUEVO)
    // ============================================================================

    /**
     * Load prompts for a project
     */
    async loadPrompts(projectId, renderInModal = false) {
        console.log(`📝 Loading prompts for project ${projectId}...`, renderInModal ? '(in modal)' : '');

        const container = document.getElementById(renderInModal ? 'promptsListModal' : 'promptsList');
        const counter = document.getElementById(renderInModal ? 'promptsCountModal' : 'promptsCount');

        if (!container) return;

        // Show loading
        container.innerHTML = `
            <div class="loading-container" style="padding: 20px;">
                <i class="fas fa-spinner fa-spin"></i>
                <span>Loading prompts...</span>
            </div>
        `;

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/queries`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Loaded ${data.queries.length} prompts`);

            // Store all prompts
            this.allPrompts = data.queries;
            this.currentPromptsPage = 1;

            // Update counter
            if (counter) {
                counter.textContent = data.queries.length;
            }

            // Render prompts list with pagination
            this.renderPrompts(renderInModal);

        } catch (error) {
            console.error('❌ Error loading prompts:', error);
            container.innerHTML = `
                <div class="error-state" style="padding: 20px; text-align: center;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Error loading prompts</p>
                </div>
            `;
        }
    }

    /**
     * Render prompts with pagination
     */
    renderPrompts(renderInModal = false) {
        const container = document.getElementById(renderInModal ? 'promptsListModal' : 'promptsList');
        const paginationDiv = document.getElementById(renderInModal ? 'promptsPaginationModal' : 'promptsPagination');

        if (!container) return;

        // Handle empty state
        if (this.allPrompts.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="padding: 40px 20px;">
                    <div class="empty-icon">
                        <i class="fas fa-comments"></i>
                    </div>
                    <h4>No prompts yet</h4>
                    <p>Add prompts to start analyzing brand visibility in LLMs</p>
                    <button class="btn btn-primary btn-sm mt-2" onclick="window.llmMonitoring.showPromptsModal()">
                        <i class="fas fa-plus"></i>
                        Add Your First Prompt
                    </button>
                </div>
            `;
            if (paginationDiv) paginationDiv.style.display = 'none';
            return;
        }

        // Calculate pagination
        const totalPages = Math.ceil(this.allPrompts.length / this.promptsPerPage);
        const startIndex = (this.currentPromptsPage - 1) * this.promptsPerPage;
        const endIndex = Math.min(startIndex + this.promptsPerPage, this.allPrompts.length);
        const pagePrompts = this.allPrompts.slice(startIndex, endIndex);

        // Render prompts for current page
        let html = '<div class="prompts-list-container">';

        pagePrompts.forEach(query => {
            html += `
                <div class="prompt-item">
                    <div class="prompt-content">
                        <div class="prompt-text">${this.escapeHtml(query.prompt)}</div>
                        <div class="prompt-meta">
                            <span class="badge badge-${query.query_type}">${query.query_type}</span>
                            <span class="badge badge-language">${query.language}</span>
                            <span class="prompt-date">
                                <i class="fas fa-clock"></i>
                                ${this.formatDate(query.created_at)}
                            </span>
                        </div>
                    </div>
                    <div class="prompt-actions">
                        <button class="btn btn-icon btn-sm" onclick="window.llmMonitoring.deletePrompt(${query.id})" title="Delete prompt">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

        // Update pagination controls
        if (this.allPrompts.length > this.promptsPerPage) {
            if (paginationDiv) {
                paginationDiv.style.display = 'flex';

                // Update pagination info
                const paginationInfoId = renderInModal ? 'paginationInfoModal' : 'paginationInfo';
                const currentPageId = renderInModal ? 'currentPageModal' : 'currentPage';
                const totalPagesId = renderInModal ? 'totalPagesModal' : 'totalPages';
                const btnPrevId = renderInModal ? 'btnPrevPageModal' : 'btnPrevPage';
                const btnNextId = renderInModal ? 'btnNextPageModal' : 'btnNextPage';

                const paginationInfo = document.getElementById(paginationInfoId);
                if (paginationInfo) {
                    paginationInfo.textContent = `Showing ${startIndex + 1}-${endIndex} of ${this.allPrompts.length} prompts`;
                }

                // Update page numbers
                const currentPageEl = document.getElementById(currentPageId);
                const totalPagesEl = document.getElementById(totalPagesId);
                if (currentPageEl) currentPageEl.textContent = this.currentPromptsPage;
                if (totalPagesEl) totalPagesEl.textContent = totalPages;

                // Update button states
                const btnPrev = document.getElementById(btnPrevId);
                const btnNext = document.getElementById(btnNextId);
                if (btnPrev) btnPrev.disabled = this.currentPromptsPage === 1;
                if (btnNext) btnNext.disabled = this.currentPromptsPage === totalPages;
            }
        } else {
            if (paginationDiv) paginationDiv.style.display = 'none';
        }
    }

    /**
     * Go to next page
     */
    nextPage() {
        const totalPages = Math.ceil(this.allPrompts.length / this.promptsPerPage);
        if (this.currentPromptsPage < totalPages) {
            this.currentPromptsPage++;
            this.renderPrompts(this.isRenderingInModal);
        }
    }

    /**
     * Go to previous page
     */
    prevPage() {
        if (this.currentPromptsPage > 1) {
            this.currentPromptsPage--;
            this.renderPrompts(this.isRenderingInModal);
        }
    }

    /**
     * Toggle prompts section collapse/expand
     */
    togglePromptsSection() {
        const content = document.getElementById('promptsContent');
        const icon = document.getElementById('promptsToggleIcon');
        const card = document.getElementById('promptsCard');

        if (!content || !icon || !card) return;

        this.promptsSectionCollapsed = !this.promptsSectionCollapsed;

        if (this.promptsSectionCollapsed) {
            content.style.display = 'none';
            icon.className = 'fas fa-chevron-right';
            card.classList.add('collapsed');
        } else {
            content.style.display = 'block';
            icon.className = 'fas fa-chevron-down';
            card.classList.remove('collapsed');
        }
    }

    /**
     * Show prompts modal
     */
    showPromptsModal() {
        console.log('🎬 Showing prompts modal...');

        const modal = document.getElementById('promptsModal');
        if (!modal) return;

        // Reset form
        document.getElementById('promptsForm').reset();

        // Show modal
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
    }

    /**
     * Hide prompts modal
     */
    hidePromptsModal() {
        const modal = document.getElementById('promptsModal');
        if (!modal) return;

        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }

    /**
     * Show prompts management modal
     */
    showPromptsManagementModal() {
        console.log('🎬 Showing prompts management modal...');

        const modal = document.getElementById('promptsManagementModal');
        if (!modal) return;

        // Set flag for pagination
        this.isRenderingInModal = true;

        // Load prompts into modal
        if (this.currentProject && this.currentProject.id) {
            this.loadPrompts(this.currentProject.id, true); // true = render in modal
        }

        // Show modal
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
    }

    /**
     * Hide prompts management modal
     */
    hidePromptsManagementModal() {
        const modal = document.getElementById('promptsManagementModal');
        if (!modal) return;

        // Reset flag for pagination
        this.isRenderingInModal = false;

        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }

    /**
     * Save prompts
     */
    async savePrompts() {
        console.log('💾 Saving prompts...');

        if (!this.currentProject || !this.currentProject.id) {
            this.showError('No project selected');
            return;
        }

        // Get form data
        const promptsText = document.getElementById('promptsInput').value.trim();
        const language = document.getElementById('promptLanguage').value || null;
        const queryType = document.getElementById('promptType').value || 'manual';

        if (!promptsText) {
            this.showError('Please enter at least one prompt');
            return;
        }

        // Parse prompts (one per line)
        const queries = promptsText
            .split('\n')
            .map(q => q.trim())
            .filter(q => q.length >= 10);

        if (queries.length === 0) {
            this.showError('All prompts must be at least 10 characters long');
            return;
        }

        // Prepare payload
        const payload = {
            queries: queries
        };

        if (language) {
            payload.language = language;
        }

        if (queryType) {
            payload.query_type = queryType;
        }

        // Show loading
        const btnSave = document.getElementById('btnSavePrompts');
        const btnText = document.getElementById('btnSavePromptsText');
        const originalText = btnText.textContent;

        btnText.textContent = 'Adding...';
        btnSave.disabled = true;

        try {
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Added ${data.added_count} prompts`);

            // Hide modal
            this.hidePromptsModal();

            // Reload prompts
            await this.loadPrompts(this.currentProject.id);

            // ✨ NUEVO: Actualizar dropdown de prompts en Responses Inspector
            await this.populateQueryFilter();

            // Show success message
            let message = `${data.added_count} prompts added successfully!`;
            if (data.duplicate_count > 0) {
                message += ` (${data.duplicate_count} duplicates skipped)`;
            }
            if (data.error_count > 0) {
                message += ` (${data.error_count} errors)`;
            }
            this.showSuccess(message);

        } catch (error) {
            console.error('❌ Error saving prompts:', error);
            this.showError(error.message || 'Failed to save prompts');
        } finally {
            btnText.textContent = originalText;
            btnSave.disabled = false;
        }
    }

    /**
     * Delete a prompt
     */
    async deletePrompt(queryId) {
        if (!this.currentProject || !this.currentProject.id) {
            return;
        }

        if (!confirm('Are you sure you want to delete this prompt?')) {
            return;
        }

        console.log(`🗑️ Deleting prompt ${queryId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries/${queryId}`, {
                method: 'DELETE',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            console.log(`✅ Prompt ${queryId} deleted`);

            // Reload prompts
            await this.loadPrompts(this.currentProject.id);

            // ✨ NUEVO: Actualizar dropdown de prompts en Responses Inspector
            await this.populateQueryFilter();

            this.showSuccess('Prompt deleted successfully');

        } catch (error) {
            console.error('❌ Error deleting prompt:', error);
            this.showError(error.message || 'Failed to delete prompt');
        }
    }

    /**
     * Scroll to prompts section
     */
    scrollToPrompts() {
        const promptsCard = document.getElementById('promptsCard');
        if (promptsCard) {
            promptsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // ============================================================================
    // AI SUGGESTIONS (NUEVO)
    // ============================================================================

    /**
     * Show suggestions modal and get AI suggestions
     */
    async showSuggestionsModal() {
        console.log('🤖 Mostrando modal de sugerencias IA...');

        if (!this.currentProject || !this.currentProject.id) {
            this.showError('No project selected');
            return;
        }

        const modal = document.getElementById('suggestionsModal');
        if (!modal) return;

        // Show modal
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);

        // Reset states
        document.getElementById('suggestionsLoading').style.display = 'flex';
        document.getElementById('suggestionsList').style.display = 'none';
        document.getElementById('suggestionsError').style.display = 'none';

        // Get suggestions from AI
        await this.getSuggestions();
    }

    /**
     * Hide suggestions modal
     */
    hideSuggestionsModal() {
        const modal = document.getElementById('suggestionsModal');
        if (!modal) return;

        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }

    /**
     * Get AI suggestions
     */
    async getSuggestions() {
        console.log('🤖 Solicitando sugerencias a la IA...');

        if (!this.currentProject || !this.currentProject.id) {
            return;
        }

        try {
            // Create timeout promise (30 seconds)
            const timeoutPromise = new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Request timeout - Gemini está tardando demasiado. Intenta de nuevo.')), 30000)
            );

            // Create fetch promise
            const fetchPromise = fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries/suggest`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    count: 10
                })
            });

            // Race between fetch and timeout
            const response = await Promise.race([fetchPromise, timeoutPromise]);

            console.log(`📡 Response status: ${response.status}`);

            if (!response.ok) {
                const error = await response.json();
                console.error('❌ Error response:', error);
                throw new Error(error.error || error.hint || `HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Recibidas ${data.suggestions.length} sugerencias de IA`);

            // Hide loading, show suggestions
            document.getElementById('suggestionsLoading').style.display = 'none';
            document.getElementById('suggestionsList').style.display = 'block';
            document.getElementById('suggestionsError').style.display = 'none';

            // Render suggestions
            this.renderSuggestions(data.suggestions);

        } catch (error) {
            console.error('❌ Error obteniendo sugerencias:', error);
            console.error('❌ Error stack:', error.stack);

            // Show error state
            document.getElementById('suggestionsLoading').style.display = 'none';
            document.getElementById('suggestionsList').style.display = 'none';
            document.getElementById('suggestionsError').style.display = 'flex';
            document.getElementById('suggestionsErrorText').textContent = error.message || 'Error generating suggestions';
        }
    }

    /**
     * Render AI suggestions
     */
    renderSuggestions(suggestions) {
        const container = document.getElementById('suggestionsContainer');
        if (!container) return;

        container.innerHTML = '';

        if (suggestions.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="padding: 40px;">
                    <p>No suggestions generated. Try again.</p>
                </div>
            `;
            return;
        }

        suggestions.forEach((suggestion, index) => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.innerHTML = `
                <label class="suggestion-label">
                    <input type="checkbox" class="suggestion-checkbox" data-index="${index}" data-text="${this.escapeHtml(suggestion)}">
                    <span class="suggestion-text">${this.escapeHtml(suggestion)}</span>
                    <span class="suggestion-badge">
                        <i class="fas fa-magic"></i>
                        AI
                    </span>
                </label>
            `;
            container.appendChild(item);
        });

        // Update counter
        this.updateSuggestionsCounter();

        // Add change event listeners
        const checkboxes = container.querySelectorAll('.suggestion-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateSuggestionsCounter();
            });
        });
    }

    /**
     * Update suggestions counter
     */
    updateSuggestionsCounter() {
        const checkboxes = document.querySelectorAll('.suggestion-checkbox:checked');
        const count = checkboxes.length;
        const btnText = document.getElementById('btnAddSuggestionsText');

        if (btnText) {
            btnText.textContent = `Add Selected (${count})`;
        }
    }

    /**
     * Select all suggestions
     */
    selectAllSuggestions() {
        const checkboxes = document.querySelectorAll('.suggestion-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
        this.updateSuggestionsCounter();
    }

    /**
     * Deselect all suggestions
     */
    deselectAllSuggestions() {
        const checkboxes = document.querySelectorAll('.suggestion-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updateSuggestionsCounter();
    }

    /**
     * Add selected suggestions to project
     */
    async addSelectedSuggestions() {
        console.log('💾 Añadiendo sugerencias seleccionadas...');

        if (!this.currentProject || !this.currentProject.id) {
            return;
        }

        // Get selected suggestions
        const checkboxes = document.querySelectorAll('.suggestion-checkbox:checked');

        if (checkboxes.length === 0) {
            this.showError('Please select at least one suggestion');
            return;
        }

        const selectedQueries = Array.from(checkboxes).map(cb => cb.dataset.text);

        console.log(`📝 Añadiendo ${selectedQueries.length} sugerencias...`);

        // Prepare payload
        const payload = {
            queries: selectedQueries,
            query_type: 'general'  // Las sugerencias de IA se marcan como 'general'
        };

        // Show loading
        const btn = document.getElementById('btnAddSelectedSuggestions');
        const btnText = document.getElementById('btnAddSuggestionsText');
        const originalText = btnText.textContent;

        btnText.textContent = 'Adding...';
        btn.disabled = true;

        try {
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Añadidas ${data.added_count} sugerencias`);

            // Hide modal
            this.hideSuggestionsModal();

            // Reload prompts
            await this.loadPrompts(this.currentProject.id);

            // Show success
            let message = `${data.added_count} AI suggestions added successfully!`;
            if (data.duplicate_count > 0) {
                message += ` (${data.duplicate_count} were duplicates)`;
            }
            this.showSuccess(message);

        } catch (error) {
            console.error('❌ Error añadiendo sugerencias:', error);
            this.showError(error.message || 'Failed to add suggestions');
        } finally {
            btnText.textContent = originalText;
            btn.disabled = false;
        }
    }

    /**
     * Utility: Get LLM display name
     */
    getLLMDisplayName(llm) {
        const names = {
            'openai': 'ChatGPT',
            'anthropic': 'Claude',
            'google': 'Gemini',
            'perplexity': 'Perplexity'
        };
        return names[llm] || llm;
    }

    /**
     * Utility: Get LLM icon
     */
    getLLMIcon(llm) {
        const icons = {
            'openai': 'fas fa-robot',
            'anthropic': 'fas fa-brain',
            'google': 'fas fa-star',
            'perplexity': 'fas fa-search'
        };
        return icons[llm] || 'fas fa-robot';
    }

    /**
     * Utility: Get LLM color
     */
    getLLMColor(llm) {
        const colors = {
            'openai': '#10b981',
            'anthropic': '#a855f7',
            'google': '#3b82f6',
            'perplexity': '#f59e0b'
        };
        return colors[llm] || '#6b7280';
    }

    /**
     * Utility: Get sentiment label
     */
    getSentimentLabel(sentiment) {
        if (!sentiment) return 'Neutral';

        // Si es un número (legacy), usar el método anterior
        if (typeof sentiment === 'number') {
            if (sentiment > 60) return 'Positive';
            if (sentiment > 40) return 'Neutral';
            return 'Negative';
        }

        // Si es un objeto con {positive, neutral, negative} porcentajes
        const positive = sentiment.positive || 0;
        const neutral = sentiment.neutral || 0;
        const negative = sentiment.negative || 0;

        // Determinar cual es mayor
        if (positive >= neutral && positive >= negative) {
            return 'Positive';
        } else if (negative > positive && negative > neutral) {
            return 'Negative';
        } else {
            return 'Neutral';
        }
    }

    /**
     * ✨ NUEVO: Formatear posición con badge de origen
     * @param {number|null} avgPosition - Posición media
     * @param {string|null} positionSource - 'text', 'link', 'both'
     * @param {object} details - Detalles con counts de cada tipo
     * @returns {string} HTML string con posición y badge
     */
    formatPositionWithBadge(avgPosition, positionSource, details) {
        if (!avgPosition) return 'N/A';

        const positionStr = `#${avgPosition.toFixed(1)}`;

        // Si no hay información de source, solo mostrar posición
        if (!positionSource) {
            return positionStr;
        }

        // Mapeo de badges
        const badges = {
            'text': '📝',
            'link': '🔗',
            'both': '📝🔗'
        };

        const badge = badges[positionSource] || '';

        // Crear tooltip con detalles (en inglés)
        let tooltipText = 'Position source: ';
        if (positionSource === 'text') {
            tooltipText += 'Detected in response text';
        } else if (positionSource === 'link') {
            tooltipText += 'Detected in cited URLs (default position 15)';
        } else if (positionSource === 'both') {
            tooltipText += 'Detected in text and URLs';
        }

        // Si hay detalles, añadirlos
        if (details && (details.text_count || details.link_count || details.both_count)) {
            tooltipText += ` | Text: ${details.text_count || 0}, URLs: ${details.link_count || 0}, Both: ${details.both_count || 0}`;
        }

        // Grid.js soporta HTML en celdas, pero para tooltip necesitamos un wrapper
        return gridjs.html(`
            <span title="${tooltipText}" style="display: inline-flex; align-items: center; gap: 4px;">
                <span>${positionStr}</span>
                <span style="font-size: 12px;">${badge}</span>
            </span>
        `);
    }

    /**
     * Utility: Format date
     */
    formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleDateString('es-ES', { year: 'numeric', month: 'short', day: 'numeric' });
    }

    /**
     * Utility: Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Utility: Show error message
     */
    showError(message) {
        // You can implement a toast notification system here
        alert(`Error: ${message}`);
    }

    /**
     * Utility: Show success message
     */
    showSuccess(message) {
        // You can implement a toast notification system here
        alert(`Success: ${message}`);
    }

    /**
     * Utility: Show info message
     */
    showInfo(message) {
        alert(message);
    }

    /**
     * Parse Markdown text to HTML
     */
    parseMarkdown(text) {
        if (!text) return '';

        let html = text;

        // Headers (### Header -> <h3>)
        html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>');

        // Bold (**text** or __text__)
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

        // Italic (*text* or _text_)
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/_(.+?)_/g, '<em>$1</em>');

        // Inline code (`code`)
        html = html.replace(/`(.+?)`/g, '<code class="md-code">$1</code>');

        // Links [text](url)
        html = html.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="md-link">$1</a>');

        // Unordered lists (- item or * item)
        html = html.replace(/^\s*[-*]\s+(.+)$/gm, '<li class="md-li">$1</li>');
        html = html.replace(/(<li class="md-li">.+<\/li>\n?)+/g, '<ul class="md-ul">$&</ul>');

        // Ordered lists (1. item)
        html = html.replace(/^\s*\d+\.\s+(.+)$/gm, '<li class="md-li">$1</li>');
        // Wrap consecutive <li> in <ol> if not already in <ul>
        const lines = html.split('\n');
        let inList = false;
        let listType = null;
        let result = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            if (line.includes('<li class="md-li">') && !line.includes('<ul') && !line.includes('<ol')) {
                if (!inList) {
                    // Start new list - determine type by checking previous lines
                    const prevLines = html.substring(0, html.indexOf(line));
                    if (prevLines.match(/^\s*\d+\.\s+/m)) {
                        result.push('<ol class="md-ol">');
                        listType = 'ol';
                    } else {
                        result.push('<ul class="md-ul">');
                        listType = 'ul';
                    }
                    inList = true;
                }
                result.push(line);
            } else {
                if (inList && !line.includes('<li')) {
                    result.push(`</${listType}>`);
                    inList = false;
                    listType = null;
                }
                result.push(line);
            }
        }

        if (inList) {
            result.push(`</${listType}>`);
        }

        html = result.join('\n');

        // Paragraphs (double line breaks)
        html = html.replace(/\n\n/g, '</p><p class="md-p">');
        html = '<p class="md-p">' + html + '</p>';

        // Clean up empty paragraphs and fix nested tags
        html = html.replace(/<p class="md-p"><\/p>/g, '');
        html = html.replace(/<p class="md-p">(<[uo]l class="md-[uo]l">)/g, '$1');
        html = html.replace(/(<\/[uo]l>)<\/p>/g, '$1');
        html = html.replace(/<p class="md-p">(<h[1-3] class="md-h[1-3]">)/g, '$1');
        html = html.replace(/(<\/h[1-3]>)<\/p>/g, '$1');

        return html;
    }

    /**
     * Load and display LLM responses for manual inspection
     */
    async loadResponses() {
        const projectId = this.currentProject?.id;
        if (!projectId) {
            this.showError('No project selected');
            return;
        }

        const queryFilter = document.getElementById('responsesQueryFilter')?.value || '';
        const llmFilter = document.getElementById('responsesLLMFilter')?.value || '';
        const daysFilter = document.getElementById('responsesDaysFilter')?.value || '7';
        const container = document.getElementById('responsesContainer');

        if (!container) return;

        // Show loading
        container.innerHTML = `
            <div class="loading-state" style="padding: 40px; text-align: center;">
                <div class="spinner"></div>
                <p>Loading LLM responses...</p>
            </div>
        `;

        try {
            let url = `${this.baseUrl}/projects/${projectId}/responses?days=${daysFilter}`;
            if (queryFilter) url += `&query_id=${queryFilter}`;
            if (llmFilter) url += `&llm_provider=${llmFilter}`;

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log(`✅ Loaded ${data.responses.length} responses`);

            if (data.responses.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-inbox"></i>
                        <h4>No responses found</h4>
                        <p>Try changing the filters or run an analysis first</p>
                    </div>
                `;
                return;
            }

            // ✨ NEW: Store all responses and reset pagination
            this.allResponses = data.responses;
            this.currentResponsesShown = this.responsesPerPage;

            // Populate query filter dropdown with ALL queries from project
            await this.populateQueryFilter();

            // Render responses with pagination
            this.renderResponsesPaginated(container);

        } catch (error) {
            console.error('❌ Error loading responses:', error);
            container.innerHTML = `
                <div class="empty-state" style="color: #ef4444;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h4>Error loading responses</h4>
                    <p>${error.message}</p>
                </div>
            `;
        }
    }

    /**
     * Populate query filter dropdown with ALL queries from project (not just those with responses)
     */
    async populateQueryFilter() {
        const select = document.getElementById('responsesQueryFilter');
        if (!select || !this.currentProject?.id) return;

        // Save current selection
        const currentSelection = select.value;

        // Clear all options except the default "All Prompts"
        while (select.options.length > 1) {
            select.remove(1);
        }

        try {
            // Fetch ALL queries for the project (not just those with responses)
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries?days=30`);
            if (!response.ok) {
                console.warn('Could not load queries for filter');
                return;
            }

            const data = await response.json();
            if (!data.success || !data.queries || data.queries.length === 0) {
                console.warn('No queries available for filter');
                return;
            }

            // Sort queries by last update (most recent first)
            const sortedQueries = data.queries.sort((a, b) => {
                const dateA = new Date(a.last_update || a.created_at || 0);
                const dateB = new Date(b.last_update || b.created_at || 0);
                return dateB - dateA;
            });

            // Add all queries to dropdown
            sortedQueries.forEach(query => {
                const option = document.createElement('option');
                option.value = query.id;
                option.textContent = query.prompt.length > 60 ? query.prompt.substring(0, 60) + '...' : query.prompt;
                select.appendChild(option);
            });

            // Restore previous selection if it still exists
            if (currentSelection && select.querySelector(`option[value="${currentSelection}"]`)) {
                select.value = currentSelection;
            }

            console.log(`✅ Loaded ${sortedQueries.length} prompts into filter dropdown`);
        } catch (error) {
            console.error('❌ Error populating query filter:', error);
        }
    }

    /**
     * ✨ NEW: Render responses with pagination
     */
    renderResponsesPaginated(container) {
        if (!container) return;

        // Get subset of responses to show
        const responsesToShow = this.allResponses.slice(0, this.currentResponsesShown);
        const hasMore = this.currentResponsesShown < this.allResponses.length;
        const remaining = this.allResponses.length - this.currentResponsesShown;

        // Clear container
        container.innerHTML = '';

        // Create responses wrapper
        const responsesWrapper = document.createElement('div');
        responsesWrapper.className = 'responses-list';
        // Pass startIndex as 0 since we're slicing from the beginning
        this.renderResponses(responsesToShow, responsesWrapper, 0);
        container.appendChild(responsesWrapper);

        // Add "Load More" button if there are more responses
        if (hasMore) {
            const loadMoreSection = document.createElement('div');
            loadMoreSection.className = 'load-more-section';
            loadMoreSection.innerHTML = `
                <button class="btn btn-ghost" onclick="window.llmMonitoring.loadMoreResponses()">
                    <i class="fas fa-chevron-down"></i>
                    Load ${Math.min(this.responsesPerPage, remaining)} More
                    <span style="color: #6b7280;">(${remaining} remaining)</span>
                </button>
            `;
            container.appendChild(loadMoreSection);
        }

        // Show total count
        const countSection = document.createElement('div');
        countSection.className = 'responses-count';
        countSection.innerHTML = `
            <small style="color: #6b7280;">
                <i class="fas fa-info-circle"></i>
                Showing ${responsesToShow.length} of ${this.allResponses.length} responses
            </small>
        `;
        container.insertBefore(countSection, container.firstChild);
    }

    /**
     * ✨ NEW: Load more responses
     */
    loadMoreResponses() {
        this.currentResponsesShown += this.responsesPerPage;
        const container = document.getElementById('responsesContainer');
        if (container) {
            this.renderResponsesPaginated(container);
        }
    }

    /**
     * Render responses in the container
     */
    renderResponses(responses, container, startIndex = 0) {
        let html = '';

        responses.forEach((response, relativeIndex) => {
            const globalIndex = startIndex + relativeIndex;
            const llmName = this.getLLMDisplayName(response.llm_provider);
            const isCollapsed = response.full_response && response.full_response.length > 500;

            html += `
                <div class="response-item">
                    <div class="response-header">
                        <div class="response-header-left">
                            <h4>
                                <span class="response-llm-badge ${response.llm_provider}">${llmName}</span>
                                ${this.escapeHtml(response.query_text)}
                            </h4>
                            <div class="response-meta">
                                <span class="response-meta-item">
                                    <i class="fas fa-calendar"></i>
                                    ${this.formatDate(response.analysis_date)}
                                </span>
                                <span class="response-meta-item">
                                    <i class="fas fa-robot"></i>
                                    ${this.escapeHtml(response.model_used || 'N/A')}
                                </span>
                                <span class="response-meta-item">
                                    <i class="fas fa-align-left"></i>
                                    ${response.response_length || 0} chars
                                </span>
                            </div>
                        </div>
                        <div class="response-status">
                            <span class="status-badge ${response.brand_mentioned ? 'mentioned' : 'not-mentioned'}">
                                ${response.brand_mentioned ? '✓ Mentioned' : '✗ Not Mentioned'}
                            </span>
                            ${response.sentiment ? `
                                <span class="status-badge ${response.sentiment}">
                                    ${response.sentiment.charAt(0).toUpperCase() + response.sentiment.slice(1)}
                                </span>
                            ` : ''}
                            ${response.position_in_list ? `
                                <span class="status-badge" style="background: #dbeafe; color: #1e40af;">
                                    Position #${response.position_in_list}
                                </span>
                            ` : ''}
                        </div>
                    </div>

                    <div class="response-body">
                        <div class="response-summary">
                            <p>${this.getSummaryText(response)}</p>
                            <button class="btn-view-full-response" onclick="window.llmMonitoring.showResponseModal(${globalIndex})">
                                <i class="fas fa-expand-alt"></i>
                                Show Full Response
                            </button>
                        </div>
                    </div>

                    ${response.mention_contexts && response.mention_contexts.length > 0 ? `
                        <div class="mention-contexts">
                            <h5>
                                <i class="fas fa-quote-left"></i>
                                Mention Contexts (${response.mention_contexts.length})
                            </h5>
                            ${response.mention_contexts.map(context => `
                                <div class="context-item">
                                    ${this.escapeHtml(context)}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    ${response.competitors_mentioned && Object.keys(response.competitors_mentioned).length > 0 ? `
                        <div class="competitors-list">
                            <h5>
                                <i class="fas fa-users"></i>
                                Competitors Mentioned (${Object.keys(response.competitors_mentioned).length})
                            </h5>
                            <div class="competitor-chips">
                                ${Object.entries(response.competitors_mentioned).map(([comp, count]) => `
                                    <span class="competitor-chip">
                                        ${this.escapeHtml(comp)} (${count})
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        container.innerHTML = html;
    }

    /**
     * Get summary text for response preview
     */
    getSummaryText(response) {
        if (!response.full_response) {
            return '<em style="color: #9ca3af;">No response text available</em>';
        }

        const maxLength = 200;
        const text = response.full_response.replace(/[*#\[\]]/g, '').trim();

        if (text.length <= maxLength) {
            return this.escapeHtml(text);
        }

        return this.escapeHtml(text.substring(0, maxLength)) + '...';
    }

    /**
     * Show full response in modal with highlighting
     */
    showResponseModal(index) {
        // Get the response directly from allResponses using the global index
        const response = this.allResponses[index];

        if (!response) {
            console.error('Response not found for index:', index);
            console.error('Total responses:', this.allResponses.length);
            console.error('Requested index:', index);
            return;
        }

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'response-modal-overlay';
        modal.innerHTML = `
            <div class="response-modal">
                <div class="response-modal-header">
                    <div class="response-modal-title">
                        <span class="response-llm-badge ${response.llm_provider}">
                            ${this.getLLMDisplayName(response.llm_provider)}
                        </span>
                        <h3>${this.escapeHtml(response.query_text)}</h3>
                    </div>
                    <button class="response-modal-close" onclick="this.closest('.response-modal-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="response-modal-meta">
                    <div class="meta-item">
                        <i class="fas fa-calendar"></i>
                        <span>${this.formatDate(response.analysis_date)}</span>
                    </div>
                    <div class="meta-item">
                        <i class="fas fa-robot"></i>
                        <span>${this.escapeHtml(response.model_used || 'N/A')}</span>
                    </div>
                    <div class="meta-item">
                        <i class="fas fa-align-left"></i>
                        <span>${response.response_length || 0} chars</span>
                    </div>
                    <div class="meta-item">
                        <span class="status-badge ${response.brand_mentioned ? 'mentioned' : 'not-mentioned'}">
                            ${response.brand_mentioned ? '✓ Mentioned' : '✗ Not Mentioned'}
                        </span>
                    </div>
                    ${response.sentiment ? `
                        <div class="meta-item">
                            <span class="status-badge ${response.sentiment}">
                                ${response.sentiment.charAt(0).toUpperCase() + response.sentiment.slice(1)}
                            </span>
                        </div>
                    ` : ''}
                    ${response.position_in_list ? `
                        <div class="meta-item">
                            <span class="status-badge" style="background: #dbeafe; color: #1e40af;">
                                Position #${response.position_in_list}
                            </span>
                        </div>
                    ` : ''}
                </div>

                <div class="response-modal-body">
                    <div class="response-modal-section">
                        <h4><i class="fas fa-file-alt"></i> Full Response</h4>
                        <div class="response-full-text">
                            ${this.highlightMentions(response)}
                        </div>
                    </div>

                    ${response.mention_contexts && response.mention_contexts.length > 0 ? `
                        <div class="response-modal-section">
                            <h4><i class="fas fa-quote-left"></i> Mention Contexts (${response.mention_contexts.length})</h4>
                            <div class="mention-contexts-list">
                                ${response.mention_contexts.map(context => `
                                    <div class="context-item-modal">
                                        ${this.highlightTextMentions(context, response)}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${response.competitors_mentioned && Object.keys(response.competitors_mentioned).length > 0 ? `
                        <div class="response-modal-section">
                            <h4><i class="fas fa-users"></i> Competitors Mentioned (${Object.keys(response.competitors_mentioned).length})</h4>
                            <div class="competitor-chips-modal">
                                ${Object.entries(response.competitors_mentioned).map(([comp, count]) => `
                                    <span class="competitor-chip-modal">
                                        ${this.escapeHtml(comp)} <span class="count-badge">${count}</span>
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${response.sources && response.sources.length > 0 ? `
                        <div class="response-modal-section">
                            <h4><i class="fas fa-link"></i> Sources & Links (${response.sources.length})</h4>
                            <div class="sources-list-modal">
                                ${response.sources.map((source, idx) => {
            const domain = new URL(source.url).hostname.replace('www.', '');
            const isBrand = this.isUrlFromBrand(source.url);
            const isCompetitor = this.isUrlFromCompetitor(source.url);

            return `
                                        <a href="${this.escapeHtml(source.url)}" 
                                           target="_blank" 
                                           rel="noopener noreferrer" 
                                           class="source-link-modal ${isBrand ? 'brand-source' : ''} ${isCompetitor ? 'competitor-source' : ''}"
                                           title="${this.escapeHtml(source.url)}">
                                            <i class="fas fa-external-link-alt"></i>
                                            <span class="source-domain">${this.escapeHtml(domain)}</span>
                                            ${isBrand ? '<span class="source-label brand-label">Your Brand</span>' : ''}
                                            ${isCompetitor ? '<span class="source-label competitor-label">Competitor</span>' : ''}
                                            <span class="source-badge">${source.provider === 'perplexity' ? 'Citation' : 'Link'}</span>
                                        </a>
                                    `;
        }).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>

                <div class="response-modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.response-modal-overlay').remove()">
                        Close
                    </button>
                </div>
            </div>
        `;

        // Add to body
        document.body.appendChild(modal);

        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

        // Close on ESC key
        const closeOnEsc = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', closeOnEsc);
            }
        };
        document.addEventListener('keydown', closeOnEsc);
    }

    /**
     * Highlight brand and competitor mentions in text
     */
    highlightMentions(response) {
        if (!response.full_response) {
            return '<em style="color: #9ca3af;">No response text available</em>';
        }

        let html = this.parseMarkdown(response.full_response);

        // Get brand keywords and competitor keywords
        const brandKeywords = this.currentProject?.brand_keywords || [];
        const brandName = this.currentProject?.brand_name || '';
        const brandDomain = this.currentProject?.brand_domain || '';

        // Get competitors
        const competitors = this.currentProject?.selected_competitors || [];
        const competitorKeywords = [];
        competitors.forEach(comp => {
            if (comp.domain) competitorKeywords.push(comp.domain);
            if (comp.keywords) competitorKeywords.push(...comp.keywords);
        });

        // Combine all brand terms
        const allBrandTerms = [...brandKeywords];
        if (brandName) allBrandTerms.push(brandName);
        if (brandDomain) allBrandTerms.push(brandDomain.replace('www.', ''));

        // Highlight in order: first competitors (to avoid conflicts), then brand
        html = this.highlightTextMentions(html, response, allBrandTerms, competitorKeywords);

        return html;
    }

    /**
     * Highlight specific text mentions
     */
    highlightTextMentions(text, response, brandTerms = null, competitorTerms = null) {
        if (!text) return '';

        // Get brand and competitor terms if not provided
        if (!brandTerms) {
            const brandKeywords = this.currentProject?.brand_keywords || [];
            const brandName = this.currentProject?.brand_name || '';
            const brandDomain = this.currentProject?.brand_domain || '';

            brandTerms = [...brandKeywords];
            if (brandName) brandTerms.push(brandName);
            if (brandDomain) brandTerms.push(brandDomain.replace('www.', ''));
        }

        if (!competitorTerms) {
            const competitors = this.currentProject?.selected_competitors || [];
            competitorTerms = [];
            competitors.forEach(comp => {
                if (comp.domain) competitorTerms.push(comp.domain);
                if (comp.keywords) competitorTerms.push(...comp.keywords);
            });
        }

        let result = text;

        // First highlight competitors (orange/red)
        competitorTerms.forEach(term => {
            if (!term) return;
            const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`\\b(${escapedTerm})\\b`, 'gi');
            result = result.replace(regex, '<mark class="competitor-mention">$1</mark>');
        });

        // Then highlight brand (blue) - will take precedence if term appears in both lists
        brandTerms.forEach(term => {
            if (!term) return;
            const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`\\b(${escapedTerm})\\b`, 'gi');
            result = result.replace(regex, '<mark class="brand-mention">$1</mark>');
        });

        return result;
    }

    /**
     * Check if URL is from brand
     */
    isUrlFromBrand(url) {
        if (!this.currentProject?.brand_domain || !url) return false;

        try {
            const urlObj = new URL(url);
            const urlDomain = urlObj.hostname.toLowerCase().replace('www.', '');
            const brandDomain = this.currentProject.brand_domain.toLowerCase().replace('www.', '');

            return urlDomain === brandDomain || urlDomain.endsWith('.' + brandDomain);
        } catch (e) {
            return false;
        }
    }

    /**
     * Check if URL is from competitor
     */
    isUrlFromCompetitor(url) {
        if (!this.currentProject?.selected_competitors || !url) return false;

        try {
            const urlObj = new URL(url);
            const urlDomain = urlObj.hostname.toLowerCase().replace('www.', '');

            return this.currentProject.selected_competitors.some(comp => {
                if (!comp.domain) return false;
                const compDomain = comp.domain.toLowerCase().replace('www.', '');
                return urlDomain === compDomain || urlDomain.endsWith('.' + compDomain);
            });
        } catch (e) {
            return false;
        }
    }

    /**
     * Load top URLs ranking from LLM responses
     */
    async loadTopUrlsRanking(projectId) {
        console.log(`🔗 Loading top URLs ranking for project ${projectId}...`);

        const llmFilter = document.getElementById('urlsLLMFilter')?.value || '';
        const days = parseInt(document.getElementById('urlsDaysFilter')?.value || 30);

        try {
            const params = new URLSearchParams({ days });
            if (llmFilter) params.append('llm_provider', llmFilter);

            const response = await fetch(`${this.baseUrl}/projects/${projectId}/urls-ranking?${params}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Loaded ${data.urls.length} URLs`);

            // Store for filtering
            this.allLLMUrls = data.urls;

            // Apply brand filter if active
            const filterBtn = document.getElementById('filterMyBrandUrlsLLM');
            const showOnlyMyBrand = filterBtn?.dataset.active === 'true';

            if (showOnlyMyBrand) {
                this.filterLLMUrlsByBrand(true);
            } else {
                // Apply pagination for all URLs
                const pageSize = 10;
                const state = this._topUrlsLLMState || { page: 1 };
                const totalPages = Math.max(1, Math.ceil(data.urls.length / pageSize));
                state.page = Math.min(state.page, totalPages);
                const start = (state.page - 1) * pageSize;
                const paged = data.urls.slice(start, start + pageSize);

                this._topUrlsLLMState = { page: state.page, totalPages, fullList: data.urls, isDomainView: false };

                // Ensure we're in URLs view (not domains)
                this.updateTableHeaderForUrls();

                this.renderTopUrlsRankingLLM(paged);
                this.renderTopUrlsLLMPaginator();
            }

        } catch (error) {
            console.error('❌ Error loading URLs ranking:', error);
            this.showNoUrlsLLMMessage();
        }
    }

    /**
     * Filter URLs by brand domain with pagination
     */
    filterLLMUrlsByBrand(showOnlyMyBrand) {
        if (!this.allLLMUrls || this.allLLMUrls.length === 0) {
            console.warn('⚠️ No URLs data available for filtering');
            this.showNoUrlsLLMMessage();
            return;
        }

        let filtered = this.allLLMUrls;

        if (showOnlyMyBrand && this.currentProject) {
            const projectDomain = (this.currentProject.brand_domain || '').toLowerCase().replace(/^www\./, '').trim();

            if (projectDomain) {
                filtered = this.allLLMUrls.filter(urlData => {
                    try {
                        const urlObj = new URL(urlData.url);
                        const urlDomain = urlObj.hostname.toLowerCase().replace(/^www\./, '');
                        return urlDomain === projectDomain || urlDomain.endsWith('.' + projectDomain);
                    } catch (e) {
                        return false;
                    }
                });

                console.log(`🔍 Filtered: ${filtered.length} URLs from ${this.allLLMUrls.length} total`);
            }

            // If no URLs match, show message
            if (filtered.length === 0) {
                console.warn('⚠️ No URLs found for your brand');
                this.showNoUrlsLLMMessage();
                return;
            }

            // Recalculate ranks after filtering
            filtered = filtered.map((url, index) => ({
                ...url,
                rank: index + 1
            }));
        }

        // Apply pagination
        const pageSize = 10;
        const state = { page: 1 };
        const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
        const paged = filtered.slice(0, pageSize);

        this._topUrlsLLMState = { page: state.page, totalPages, fullList: filtered, isDomainView: false };

        // Make sure we're in URLs view, not domains view
        this.updateTableHeaderForUrls();

        this.renderTopUrlsRankingLLM(paged);
        this.renderTopUrlsLLMPaginator();
    }

    /**
     * Render top URLs ranking table
     */
    renderTopUrlsRankingLLM(urls) {
        const tableBody = document.getElementById('topUrlsLLMBody');
        const noUrlsMessage = document.getElementById('noUrlsLLMMessage');
        const topUrlsTable = document.getElementById('topUrlsLLMTable');

        if (!urls || urls.length === 0) {
            this.showNoUrlsLLMMessage();
            return;
        }

        // Show table, hide message
        noUrlsMessage.style.display = 'none';
        topUrlsTable.style.display = 'table';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Get project info for highlighting
        let projectDomain = '';
        let competitorDomains = [];

        if (this.currentProject) {
            projectDomain = (this.currentProject.brand_domain || '').toLowerCase().replace(/^www\./, '').trim();

            // Normalize competitor domains
            const competitors = this.currentProject.selected_competitors || [];
            competitorDomains = competitors.map(c => {
                const domain = typeof c === 'object' ? (c.domain || c.competitor_domain || c) : c;
                return String(domain).toLowerCase().replace(/^www\./, '').trim();
            }).filter(d => d && d.length > 0);

            console.log('🎯 URL Highlighting Config (LLM Monitoring):', {
                projectDomain,
                competitorDomains,
                totalUrls: urls.length
            });
        }

        // Render rows
        urls.forEach((urlData, index) => {
            const url = urlData.url;

            // Extract domain from URL
            let urlDomain = '';
            let domainType = 'other';
            try {
                const urlObj = new URL(url);
                urlDomain = urlObj.hostname.toLowerCase().replace(/^www\./, '');

                // Check if it's project or competitor domain
                if (projectDomain && (urlDomain === projectDomain || urlDomain.endsWith('.' + projectDomain))) {
                    domainType = 'project';
                } else if (competitorDomains.some(comp => urlDomain === comp || urlDomain.endsWith('.' + comp))) {
                    domainType = 'competitor';
                }

                if (index < 5) { // Log first 5 for debugging
                    console.log(`  URL ${index + 1}: ${urlDomain} → ${domainType}`);
                }
            } catch (e) {
                // Invalid URL, keep as 'other'
            }

            // Use 'table' prefix for project domain to avoid conflicts with other CSS
            const domainTypeClass = domainType === 'project' ? 'table' : domainType;
            const rowClass = `url-row ${domainTypeClass}-domain`;

            // Create domain badge if needed
            let domainBadge = '';
            if (domainType === 'project') {
                domainBadge = '<span class="domain-badge project">Your Domain</span>';
            } else if (domainType === 'competitor') {
                domainBadge = '<span class="domain-badge competitor">Competitor</span>';
            }

            const row = document.createElement('tr');
            row.className = rowClass;
            row.innerHTML = `
                <td class="rank-cell">${urlData.rank}</td>
                <td class="url-cell">
                    <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        <a href="${this.escapeHtml(url)}" target="_blank" rel="noopener noreferrer" 
                           class="url-link" title="${this.escapeHtml(url)}">
                            ${this.truncateUrl(url, 80)}
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                        ${domainBadge}
                    </div>
                </td>
                <td class="mentions-cell">${urlData.mentions}</td>
                <td class="percentage-cell">${urlData.percentage.toFixed(1)}%</td>
            `;

            tableBody.appendChild(row);
        });

        console.log(`✅ Rendered ${urls.length} URL rows with highlighting`);
    }

    /**
     * Show no URLs message
     */
    showNoUrlsLLMMessage() {
        const tableBody = document.getElementById('topUrlsLLMBody');
        const noUrlsMessage = document.getElementById('noUrlsLLMMessage');
        const topUrlsTable = document.getElementById('topUrlsLLMTable');

        if (tableBody) tableBody.innerHTML = '';
        if (topUrlsTable) topUrlsTable.style.display = 'none';
        if (noUrlsMessage) noUrlsMessage.style.display = 'flex';
    }

    /**
     * Toggle between URLs view and Domains view
     */
    toggleDomainsView(showDomains) {
        if (!this.allLLMUrls || this.allLLMUrls.length === 0) {
            console.warn('⚠️ No URLs data available');
            this.showNoUrlsLLMMessage();
            return;
        }

        if (showDomains) {
            console.log('🏢 Switching to Domains view...');

            // Aggregate URLs by domain
            const domainsData = this.aggregateUrlsByDomain(this.allLLMUrls);

            // Apply pagination
            const pageSize = 10;
            const state = { page: 1 };
            const totalPages = Math.max(1, Math.ceil(domainsData.length / pageSize));
            const paged = domainsData.slice(0, pageSize);

            this._topUrlsLLMState = { page: state.page, totalPages, fullList: domainsData, isDomainView: true };

            // Update table header for domains view
            this.updateTableHeaderForDomains();

            // Render domains table
            this.renderTopDomainsRankingLLM(paged);
            this.renderTopUrlsLLMPaginator();
        } else {
            console.log('🔗 Switching back to URLs view...');

            // Restore URLs view
            const pageSize = 10;
            const state = { page: 1 };
            const totalPages = Math.max(1, Math.ceil(this.allLLMUrls.length / pageSize));
            const paged = this.allLLMUrls.slice(0, pageSize);

            this._topUrlsLLMState = { page: state.page, totalPages, fullList: this.allLLMUrls, isDomainView: false };

            // Update table header for URLs view
            this.updateTableHeaderForUrls();

            // Render URLs table
            this.renderTopUrlsRankingLLM(paged);
            this.renderTopUrlsLLMPaginator();
        }
    }

    /**
     * Aggregate URLs by domain
     */
    aggregateUrlsByDomain(urlsData) {
        const domainStats = {};

        urlsData.forEach(urlData => {
            try {
                const urlObj = new URL(urlData.url);
                const domain = urlObj.hostname.toLowerCase().replace(/^www\./, '');

                if (!domainStats[domain]) {
                    domainStats[domain] = {
                        domain: domain,
                        urlCount: 0,
                        totalMentions: 0,
                        urls: []
                    };
                }

                domainStats[domain].urlCount++;
                domainStats[domain].totalMentions += urlData.mentions || 0;
                domainStats[domain].urls.push(urlData.url);

            } catch (e) {
                console.warn('Invalid URL:', urlData.url);
            }
        });

        // Convert to array and calculate percentages
        const totalMentions = Object.values(domainStats).reduce((sum, d) => sum + d.totalMentions, 0);

        const domainsArray = Object.values(domainStats).map(domainData => ({
            ...domainData,
            percentage: totalMentions > 0 ? (domainData.totalMentions / totalMentions * 100) : 0
        }));

        // Sort by total mentions (descending)
        domainsArray.sort((a, b) => b.totalMentions - a.totalMentions);

        // Add ranking
        domainsArray.forEach((domain, index) => {
            domain.rank = index + 1;
        });

        console.log(`✅ Aggregated ${domainsArray.length} unique domains from ${urlsData.length} URLs`);

        return domainsArray;
    }

    /**
     * Update table header for domains view
     */
    updateTableHeaderForDomains() {
        const thead = document.querySelector('#topUrlsLLMTable thead');
        if (!thead) return;

        thead.innerHTML = `
            <tr>
                <th style="width: 60px;">#</th>
                <th style="width: 45%;">Domain</th>
                <th style="width: 100px;">URLs</th>
                <th style="width: 120px;">Total Mentions</th>
                <th style="width: 120px;">% of Total</th>
            </tr>
        `;
    }

    /**
     * Update table header for URLs view
     */
    updateTableHeaderForUrls() {
        const thead = document.querySelector('#topUrlsLLMTable thead');
        if (!thead) return;

        thead.innerHTML = `
            <tr>
                <th style="width: 60px;">#</th>
                <th style="width: 60%;">URL</th>
                <th style="width: 120px;">Mentions</th>
                <th style="width: 120px;">% of Total</th>
            </tr>
        `;
    }

    /**
     * Render top domains ranking table
     */
    renderTopDomainsRankingLLM(domains) {
        const tableBody = document.getElementById('topUrlsLLMBody');
        const noUrlsMessage = document.getElementById('noUrlsLLMMessage');
        const topUrlsTable = document.getElementById('topUrlsLLMTable');

        if (!domains || domains.length === 0) {
            this.showNoUrlsLLMMessage();
            return;
        }

        // Show table, hide message
        noUrlsMessage.style.display = 'none';
        topUrlsTable.style.display = 'table';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Get project info for highlighting
        let projectDomain = '';
        let competitorDomains = [];

        if (this.currentProject) {
            projectDomain = (this.currentProject.brand_domain || '').toLowerCase().replace(/^www\./, '').trim();

            // Normalize competitor domains
            const competitors = this.currentProject.selected_competitors || [];
            competitorDomains = competitors.map(c => {
                const domain = typeof c === 'object' ? (c.domain || c.competitor_domain || c) : c;
                return String(domain).toLowerCase().replace(/^www\./, '').trim();
            }).filter(d => d && d.length > 0);
        }

        // Render each domain row
        domains.forEach((domainData, index) => {
            const domain = domainData.domain;

            // Determine if it's project or competitor domain
            let domainType = 'other';
            if (projectDomain && (domain === projectDomain || domain.endsWith('.' + projectDomain))) {
                domainType = 'project';
            } else if (competitorDomains.some(comp => domain === comp || domain.endsWith('.' + comp))) {
                domainType = 'competitor';
            }

            const domainTypeClass = domainType === 'project' ? 'table' : domainType;
            const rowClass = `url-row ${domainTypeClass}-domain`;

            // Create domain badge if needed
            let domainBadge = '';
            if (domainType === 'project') {
                domainBadge = '<span class="domain-badge project">Your Domain</span>';
            } else if (domainType === 'competitor') {
                domainBadge = '<span class="domain-badge competitor">Competitor</span>';
            }

            // Get logo URL
            const logoUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

            const row = document.createElement('tr');
            row.className = rowClass;
            row.innerHTML = `
                <td class="rank-cell">${domainData.rank}</td>
                <td class="url-cell">
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <img src="${logoUrl}" alt="${this.escapeHtml(domain)}" 
                             style="width: 24px; height: 24px; border-radius: 4px; flex-shrink: 0;"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22><circle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23e5e7eb%22/><text x=%2212%22 y=%2216%22 text-anchor=%22middle%22 font-size=%2210%22 fill=%22%23374151%22>${domain.charAt(0).toUpperCase()}</text></svg>'">
                        <div style="flex: 1; min-width: 0;">
                            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                                <a href="https://${this.escapeHtml(domain)}" target="_blank" rel="noopener noreferrer" 
                                   class="url-link" style="font-weight: 500;">
                                    ${this.escapeHtml(domain)}
                                    <i class="fas fa-external-link-alt"></i>
                                </a>
                                ${domainBadge}
                            </div>
                        </div>
                    </div>
                </td>
                <td class="mentions-cell" style="text-align: center;">${domainData.urlCount}</td>
                <td class="mentions-cell">${domainData.totalMentions}</td>
                <td class="percentage-cell">${domainData.percentage.toFixed(1)}%</td>
            `;

            tableBody.appendChild(row);
        });

        console.log(`✅ Rendered ${domains.length} domain rows with highlighting`);
    }

    /**
     * Render pagination controls for URLs table
     */
    renderTopUrlsLLMPaginator() {
        const container = document.getElementById('topUrlsLLMTable')?.parentElement || document.getElementById('noUrlsLLMMessage')?.parentElement;
        if (!container || !this._topUrlsLLMState) return;

        let paginator = document.getElementById('topUrlsLLMPaginator');
        if (!paginator) {
            paginator = document.createElement('div');
            paginator.id = 'topUrlsLLMPaginator';
            paginator.style.cssText = 'display:flex;justify-content:flex-end;gap:8px;margin:24px 0;align-items:center;';
            container.appendChild(paginator);
        }

        const { page, totalPages, fullList } = this._topUrlsLLMState;
        paginator.innerHTML = '';

        // Previous button
        const btnPrev = document.createElement('button');
        btnPrev.className = 'btn btn-light btn-sm';
        btnPrev.style.backgroundColor = '#C3F5A4';
        btnPrev.style.borderColor = '#C3F5A4';
        btnPrev.style.color = '#111827';
        btnPrev.innerHTML = '<i class="fas fa-chevron-left"></i> Previous';
        btnPrev.disabled = page <= 1;
        btnPrev.onclick = () => {
            this._topUrlsLLMState.page = Math.max(1, page - 1);

            // Check if domain view is active
            const isDomainView = this._topUrlsLLMState.isDomainView;

            // Check if brand filter is active
            const filterBtn = document.getElementById('filterMyBrandUrlsLLM');
            const isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';

            if (isFilterActive) {
                this.filterLLMUrlsByBrand(true);
            } else {
                const pageSize = 10;
                const start = (this._topUrlsLLMState.page - 1) * pageSize;
                const paged = fullList.slice(start, start + pageSize);

                if (isDomainView) {
                    this.renderTopDomainsRankingLLM(paged);
                } else {
                    this.renderTopUrlsRankingLLM(paged);
                }
                this.renderTopUrlsLLMPaginator();
            }
        };

        // Page info
        const info = document.createElement('span');
        info.style.cssText = 'display:flex;align-items:center;font-size:13px;color:#6b7280;font-weight:500;';
        info.textContent = `Page ${page} of ${totalPages}`;

        // Next button
        const btnNext = document.createElement('button');
        btnNext.className = 'btn btn-light btn-sm';
        btnNext.style.backgroundColor = '#C3F5A4';
        btnNext.style.borderColor = '#C3F5A4';
        btnNext.style.color = '#111827';
        btnNext.innerHTML = 'Next <i class="fas fa-chevron-right"></i>';
        btnNext.disabled = page >= totalPages;
        btnNext.onclick = () => {
            this._topUrlsLLMState.page = Math.min(totalPages, page + 1);

            // Check if domain view is active
            const isDomainView = this._topUrlsLLMState.isDomainView;

            // Check if brand filter is active
            const filterBtn = document.getElementById('filterMyBrandUrlsLLM');
            const isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';

            if (isFilterActive) {
                this.filterLLMUrlsByBrand(true);
            } else {
                const pageSize = 10;
                const start = (this._topUrlsLLMState.page - 1) * pageSize;
                const paged = fullList.slice(start, start + pageSize);

                if (isDomainView) {
                    this.renderTopDomainsRankingLLM(paged);
                } else {
                    this.renderTopUrlsRankingLLM(paged);
                }
                this.renderTopUrlsLLMPaginator();
            }
        };

        // Append buttons
        paginator.appendChild(btnPrev);
        paginator.appendChild(info);
        paginator.appendChild(btnNext);

        console.log(`📄 Rendered paginator: Page ${page}/${totalPages}`);
    }

    /**
     * Truncate URL for display
     */
    truncateUrl(url, maxLength) {
        if (url.length <= maxLength) return this.escapeHtml(url);

        try {
            const urlObj = new URL(url);
            const domain = urlObj.hostname.replace('www.', '');
            const path = urlObj.pathname + urlObj.search;

            if (path.length > maxLength - domain.length - 3) {
                return this.escapeHtml(domain + path.substring(0, maxLength - domain.length - 6) + '...');
            }

            return this.escapeHtml(domain + path);
        } catch {
            return this.escapeHtml(url.substring(0, maxLength - 3) + '...');
        }
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.LLMMonitoring = LLMMonitoring;
}

