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

        // Analyze project
        document.getElementById('btnAnalyzeProject')?.addEventListener('click', () => {
            this.analyzeProject();
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

        // ✅ NUEVO: Gestión de prompts
        document.getElementById('btnManagePrompts')?.addEventListener('click', () => {
            this.scrollToPrompts();
        });

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
                <button class="btn btn-ghost btn-sm btn-danger" onclick="window.llmMonitoring.deleteProject(${project.id}, '${this.escapeHtml(project.name)}')">
                    <i class="fas fa-trash"></i>
                    Delete
                </button>
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
        
        try {
            // Load project details
            const response = await fetch(`${this.baseUrl}/projects/${projectId}`);
            
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
     */
    updateKPIs(metrics) {
        if (!metrics || Object.keys(metrics).length === 0) {
            document.getElementById('kpiMentionRate').textContent = 'No data';
            document.getElementById('kpiShareOfVoice').textContent = 'No data';
            document.getElementById('kpiSentiment').textContent = 'No data';
            return;
        }
        
        // Calculate averages across all LLMs
        const llms = Object.keys(metrics);
        const avgMentionRate = llms.reduce((sum, llm) => sum + (metrics[llm].mention_rate || 0), 0) / llms.length;
        const avgSOV = llms.reduce((sum, llm) => sum + (metrics[llm].share_of_voice || 0), 0) / llms.length;
        
        // 🔧 FIX: Calculate weighted sentiment correctly
        // Los porcentajes ya vienen calculados por LLM, ahora los promediamos
        let totalPositivePct = 0, totalNeutralPct = 0, totalNegativePct = 0;
        llms.forEach(llm => {
            if (metrics[llm].sentiment) {
                totalPositivePct += metrics[llm].sentiment.positive || 0;
                totalNeutralPct += metrics[llm].sentiment.neutral || 0;
                totalNegativePct += metrics[llm].sentiment.negative || 0;
            }
        });
        
        // Promediar los porcentajes entre todos los LLMs
        const avgPositive = totalPositivePct / llms.length;
        const avgNeutral = totalNeutralPct / llms.length;
        const avgNegative = totalNegativePct / llms.length;
        
        // Determinar el sentiment predominante
        let sentimentLabel, sentimentClass;
        if (avgPositive >= avgNeutral && avgPositive >= avgNegative) {
            sentimentLabel = 'Positive';
            sentimentClass = 'positive';
        } else if (avgNegative > avgPositive && avgNegative > avgNeutral) {
            sentimentLabel = 'Negative';
            sentimentClass = 'negative';
        } else {
            sentimentLabel = 'Neutral';
            sentimentClass = 'neutral';
        }
        
        document.getElementById('kpiMentionRate').textContent = `${avgMentionRate.toFixed(1)}%`;
        document.getElementById('kpiShareOfVoice').textContent = `${avgSOV.toFixed(1)}%`;
        document.getElementById('kpiSentiment').innerHTML = `<span class="sentiment-${sentimentClass}">${sentimentLabel}</span>`;
    }

    /**
     * Load detailed metrics for a project
     */
    async loadMetrics(projectId) {
        console.log(`📈 Loading detailed metrics for project ${projectId}...`);
        
        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/metrics`);
            
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
            
            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=30`);
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
            
            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=30`);
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
            
            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=30`);
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
            
            // Obtener datos de queries/resultados del proyecto
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/queries`);
            if (!response.ok) {
                console.warn('Could not load sentiment data');
                return;
            }
            
            const result = await response.json();
            
            if (!result.queries || result.queries.length === 0) {
                console.warn('⚠️ No queries data available for sentiment analysis');
                return;
            }
            
            // Contar sentimientos por query
            const sentimentCounts = {
                positive: 0,
                neutral: 0,
                negative: 0
            };
            
            // Procesar resultados de queries
            result.queries.forEach(query => {
                if (query.results) {
                    query.results.forEach(result => {
                        const sentiment = (result.sentiment || 'neutral').toLowerCase();
                        if (sentimentCounts.hasOwnProperty(sentiment)) {
                            sentimentCounts[sentiment]++;
                        } else {
                            sentimentCounts.neutral++;
                        }
                    });
                }
            });
            
            // Calcular total y porcentajes
            const total = sentimentCounts.positive + sentimentCounts.neutral + sentimentCounts.negative;
            
            if (total === 0) {
                console.warn('⚠️ No sentiment data available');
                return;
            }
            
            const data = {
                labels: ['Positive', 'Neutral', 'Negative'],
                values: [
                    ((sentimentCounts.positive / total) * 100).toFixed(1),
                    ((sentimentCounts.neutral / total) * 100).toFixed(1),
                    ((sentimentCounts.negative / total) * 100).toFixed(1)
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
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/comparison`);
            
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
            item.avg_position ? `#${item.avg_position.toFixed(1)}` : 'N/A',
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
                { name: 'Queries', width: '80px' }
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
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/queries?days=30`);
            
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
        
        // Formatear datos para la tabla
        const rows = queries.map(q => {
            const visibilityPct = q.visibility_pct != null ? q.visibility_pct : 0;
            const visibilityStr = visibilityPct.toFixed(1);
            
            return [
                q.prompt,
                q.country,
                q.language ? q.language.toUpperCase() : 'N/A',
                q.total_responses || 0,
                q.total_mentions || 0,
                // Visibility con barra de progreso
                gridjs.html(`
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="flex: 1; background: #e5e7eb; border-radius: 9999px; height: 8px; overflow: hidden;">
                            <div style="height: 100%; background: linear-gradient(90deg, #22c55e ${visibilityPct}%, transparent ${visibilityPct}%); width: 100%; border-radius: 9999px;"></div>
                        </div>
                        <span style="font-weight: 600; min-width: 45px;">${visibilityStr}%</span>
                    </div>
                `),
                q.last_update ? this.formatRelativeTime(q.last_update) : 'Never'
            ];
        });
        
        // Create grid
        this.queriesGrid = new gridjs.Grid({
            columns: [
                { name: 'Prompt', width: '300px' },
                { name: 'Country', width: '80px' },
                { name: 'Language', width: '80px' },
                { name: 'Responses', width: '90px' },
                { name: 'Mentions', width: '90px' },
                { name: 'Visibility', width: '150px' },
                { name: 'Last Update', width: '120px' }
            ],
            data: rows,
            sort: true,
            search: {
                placeholder: 'Search prompts...'
            },
            pagination: {
                limit: 15,
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
        
        if (projectsTab) {
            projectsTab.style.display = 'block';
            projectsTab.classList.add('active');
        }
        if (metricsSection) {
            metricsSection.style.display = 'none';
            metricsSection.classList.remove('active');
        }
        this.currentProject = null;
    }

    /**
     * Delete a project
     */
    async deleteProject(projectId, projectName) {
        console.log(`🗑️ Deleting project ${projectId}...`);
        
        // Confirm deletion
        if (!confirm(`Are you sure you want to delete the project "${projectName}"?\n\nThis action cannot be undone.`)) {
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}`, {
                method: 'DELETE',
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            console.log(`✅ Project ${projectId} deleted`);
            
            // If we're viewing this project, go back to projects list
            if (this.currentProject && this.currentProject.id === projectId) {
                this.showProjectsList();
            }
            
            // Reload projects list
            await this.loadProjects();
            
            this.showSuccess(`Project "${projectName}" deleted successfully`);
            
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
     */
    async analyzeProject() {
        if (!this.currentProject || !this.currentProject.id) {
            return;
        }
        
        console.log(`🚀 Starting analysis for project ${this.currentProject.id}...`);
        
        // Get button and add loading state
        const btnAnalyze = document.getElementById('btnAnalyzeProject');
        const originalHTML = btnAnalyze.innerHTML;
        
        btnAnalyze.disabled = true;
        btnAnalyze.innerHTML = '<div class="btn-spinner"></div> <span>Analyzing...</span>';
        
        // Show progress modal
        const modal = document.getElementById('analysisModal');
        const progressBar = document.getElementById('analysisProgress');
        const progressText = document.getElementById('analysisProgressText');
        
        modal.style.display = 'flex';
        progressBar.style.width = '10%';
        progressText.textContent = 'Starting analysis...';
        
        try {
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/analyze`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            console.log('✅ Analysis completed:', data.results);
            
            // Update progress
            progressBar.style.width = '100%';
            progressText.textContent = 'Analysis completed!';
            
            // Hide modal after delay
            setTimeout(() => {
                modal.style.display = 'none';
                
                // Restore button
                btnAnalyze.disabled = false;
                btnAnalyze.innerHTML = originalHTML;
                
                // Reload metrics
                this.viewProject(this.currentProject.id);
                
                // Show success
                this.showSuccess(`Analysis completed! ${data.results.total_queries_executed} queries analyzed.`);
            }, 1500);
            
        } catch (error) {
            console.error('❌ Error running analysis:', error);
            modal.style.display = 'none';
            
            // Restore button
            btnAnalyze.disabled = false;
            btnAnalyze.innerHTML = originalHTML;
            
            this.showError(error.message || 'Failed to run analysis');
        }
    }

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
    async loadPrompts(projectId) {
        console.log(`📝 Loading prompts for project ${projectId}...`);
        
        const container = document.getElementById('promptsList');
        const counter = document.getElementById('promptsCount');
        
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
            this.renderPrompts();
            
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
    renderPrompts() {
        const container = document.getElementById('promptsList');
        const paginationDiv = document.getElementById('promptsPagination');
        
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
                document.getElementById('paginationInfo').textContent = 
                    `Showing ${startIndex + 1}-${endIndex} of ${this.allPrompts.length} prompts`;
                
                // Update page numbers
                document.getElementById('currentPage').textContent = this.currentPromptsPage;
                document.getElementById('totalPages').textContent = totalPages;
                
                // Update button states
                document.getElementById('btnPrevPage').disabled = this.currentPromptsPage === 1;
                document.getElementById('btnNextPage').disabled = this.currentPromptsPage === totalPages;
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
            this.renderPrompts();
        }
    }

    /**
     * Go to previous page
     */
    prevPage() {
        if (this.currentPromptsPage > 1) {
            this.currentPromptsPage--;
            this.renderPrompts();
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
            'openai': 'OpenAI (GPT-5)',
            'anthropic': 'Anthropic (Claude)',
            'google': 'Google (Gemini)',
            'perplexity': 'Perplexity'
        };
        return names[llm] || llm;
    }

    /**
     * Utility: Get sentiment label
     */
    getSentimentLabel(sentiment) {
        if (!sentiment) return '😐 Neutral';
        
        // Si es un número (legacy), usar el método anterior
        if (typeof sentiment === 'number') {
            if (sentiment > 60) return '😊 Positive';
            if (sentiment > 40) return '😐 Neutral';
            return '😞 Negative';
        }
        
        // Si es un objeto con {positive, neutral, negative} porcentajes
        const positive = sentiment.positive || 0;
        const neutral = sentiment.neutral || 0;
        const negative = sentiment.negative || 0;
        
        // Determinar cual es mayor
        if (positive >= neutral && positive >= negative) {
            return '😊 Positive';
        } else if (negative > positive && negative > neutral) {
            return '😞 Negative';
        } else {
            return '😐 Neutral';
        }
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
            let url = `${this.baseUrl}/projects/${projectId}/responses?days=7`;
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

            // Populate query filter dropdown if empty
            this.populateQueryFilter(data.responses);

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
     * Populate query filter dropdown with unique queries
     */
    populateQueryFilter(responses) {
        const select = document.getElementById('responsesQueryFilter');
        if (!select || select.options.length > 1) return;

        const uniqueQueries = new Map();
        responses.forEach(r => {
            if (!uniqueQueries.has(r.query_id)) {
                uniqueQueries.set(r.query_id, r.query_text);
            }
        });

        uniqueQueries.forEach((text, id) => {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = text.length > 60 ? text.substring(0, 60) + '...' : text;
            select.appendChild(option);
        });
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
        this.renderResponses(responsesToShow, responsesWrapper);
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
    renderResponses(responses, container) {
        let html = '';

        responses.forEach((response, index) => {
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
                        <div class="response-text ${isCollapsed ? 'collapsed' : ''}" id="responseText${index}">
                            ${response.full_response ? this.parseMarkdown(response.full_response) : '<em style="color: #9ca3af;">No response text available</em>'}
                        </div>
                        ${isCollapsed ? `
                            <button class="response-expand-btn" onclick="window.llmMonitoring.toggleResponseText(${index})">
                                <i class="fas fa-chevron-down"></i>
                                Show Full Response
                            </button>
                        ` : ''}
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

                    ${response.sources && response.sources.length > 0 ? `
                        <div class="sources-list">
                            <h5>
                                <i class="fas fa-link"></i>
                                Sources & Links (${response.sources.length})
                            </h5>
                            <div class="sources-container">
                                ${response.sources.map((source, idx) => {
                                    const domain = new URL(source.url).hostname.replace('www.', '');
                                    return `
                                        <a href="${this.escapeHtml(source.url)}" 
                                           target="_blank" 
                                           rel="noopener noreferrer" 
                                           class="source-link"
                                           title="${this.escapeHtml(source.url)}">
                                            <i class="fas fa-external-link-alt"></i>
                                            <span class="source-domain">${this.escapeHtml(domain)}</span>
                                            <span class="source-badge">${source.provider === 'perplexity' ? 'Citation' : 'Link'}</span>
                                        </a>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        container.innerHTML = html;
    }

    /**
     * Toggle expand/collapse response text
     */
    toggleResponseText(index) {
        const textEl = document.getElementById(`responseText${index}`);
        const btn = event.target.closest('.response-expand-btn');
        
        if (!textEl || !btn) return;

        if (textEl.classList.contains('collapsed')) {
            textEl.classList.remove('collapsed');
            btn.innerHTML = '<i class="fas fa-chevron-up"></i> Show Less';
        } else {
            textEl.classList.add('collapsed');
            btn.innerHTML = '<i class="fas fa-chevron-down"></i> Show Full Response';
        }
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.LLMMonitoring = LLMMonitoring;
}

