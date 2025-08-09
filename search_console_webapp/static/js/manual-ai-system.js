/*
 * Manual AI Overview Analysis System
 * JavaScript independiente para el sistema de análisis manual
 * SEGURO: No interfiere con el JavaScript existente
 */

class ManualAISystem {
    constructor() {
        this.projects = [];
        this.currentProject = null;
        this.charts = {};
        this.isLoading = false;
        
        // Referencias DOM
        this.elements = {};
        
        this.init();
    }

    init() {
        console.log('🤖 Initializing Manual AI System...');
        
        // Cacheamos referencias DOM
        this.cacheElements();
        
        // Configuramos event listeners
        this.setupEventListeners();
        
        // Cargamos datos iniciales
        this.loadInitialData();
        
        console.log('✅ Manual AI System initialized');
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
        await this.loadProjects();
        this.populateAnalyticsProjectSelect();
        
        // Load cron execution status
        this.updateLastCronExecution();
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
            this.updateLastCronExecution();
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
            const response = await fetch('/manual-ai/api/projects');
            const data = await response.json();

            if (data.success) {
                this.projects = data.projects;
                this.renderProjects();
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
            <div class="project-card" data-project-id="${project.id}">
                <div class="project-header">
                    <h3>${this.escapeHtml(project.name)}</h3>
                    <div class="project-actions">
                        <button type="button" class="btn-icon" onclick="manualAI.showProjectModal(${project.id})"
                                title="Project settings">
                            <i class="fas fa-cog"></i>
                        </button>
                        <button type="button" class="btn-icon" onclick="manualAI.analyzeProject(${project.id})"
                                title="Run analysis">
                            <i class="fas fa-play"></i>
                        </button>
                    </div>
                </div>
                <div class="project-details">
                    <div class="project-meta">
                        <span class="project-domain">
                            <i class="fas fa-globe"></i>
                            ${this.escapeHtml(project.domain)}
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
                        <span class="stat-number">${project.keyword_count || 0}</span>
                        <span class="stat-label">Keywords</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${project.ai_overview_count || 0}</span>
                        <span class="stat-label">AI Results</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">${project.mentions_count || 0}</span>
                        <span class="stat-label">Mentions</span>
                    </div>
                </div>
                <div class="project-footer">
                    <small class="last-analysis">
                        Last analysis: ${project.last_analysis_date ? 
                            new Date(project.last_analysis_date).toLocaleDateString() : 'Never'}
                    </small>
                </div>
            </div>
        `).join('');
    }

    // ================================
    // PROJECT CREATION
    // ================================

    showCreateProject() {
        this.elements.createProjectForm.reset();
        this.showElement(this.elements.createProjectModal);
    }

    hideCreateProject() {
        this.hideElement(this.elements.createProjectModal);
    }

    async handleCreateProject(e) {
        e.preventDefault();

        const formData = new FormData(e.target);
        const projectData = Object.fromEntries(formData.entries());

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
                await this.loadProjects();
                this.populateAnalyticsProjectSelect();
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
                    this.hideProgress();
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

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                clearInterval(backupPolling); // Stop backup polling
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
            this.hideProgress();
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
        }
    }

    renderAnalytics(stats) {
        // Update summary cards
        document.getElementById('totalKeywords').textContent = stats.main_stats.total_keywords || 0;
        document.getElementById('aiKeywords').textContent = stats.main_stats.total_ai_keywords || 0;
        document.getElementById('domainMentions').textContent = stats.main_stats.total_mentions || 0;
        document.getElementById('visibilityPercentage').textContent = 
            stats.main_stats.visibility_percentage ? 
            Math.round(stats.main_stats.visibility_percentage) + '%' : '0%';
        document.getElementById('averagePosition').textContent = 
            stats.main_stats.avg_position ? 
            Math.round(stats.main_stats.avg_position * 10) / 10 : '-';
        document.getElementById('aioWeight').textContent = 
            stats.main_stats.aio_weight_percentage ? 
            Math.round(stats.main_stats.aio_weight_percentage) + '%' : '0%';

        // Show charts container
        this.hideElement(this.elements.analyticsContent);
        this.showElement(this.elements.chartsContainer);

        // Render charts with events annotations
        this.renderVisibilityChart(stats.visibility_chart, stats.events);
        this.renderPositionsChart(stats.positions_chart, stats.events);

        // Load and render top domains
        this.loadTopDomains(stats.project_id || this.currentProject?.id);
    }

    renderVisibilityChart(data, events = []) {
        const ctx = document.getElementById('visibilityChart').getContext('2d');
        
        // Destroy existing chart
        if (this.charts.visibility) {
            this.charts.visibility.destroy();
        }

        // Create annotations for events
        const annotations = this.createEventAnnotations(data, events);

        this.charts.visibility = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => new Date(d.analysis_date).toLocaleDateString()),
                datasets: [{
                    label: 'Domain Visibility %',
                    data: data.map(d => d.visibility_pct || 0),
                    borderColor: '#4F46E5',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    tension: 0.4,
                    fill: true
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
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Visibility: ${Math.round(context.raw)}%`;
                            }
                        }
                    }
                },
                // Add event annotations
                onHover: (event, elements, chart) => {
                    this.showEventAnnotations(chart, annotations);
                }
            },
            plugins: [{
                id: 'eventAnnotations',
                afterDraw: (chart) => {
                    this.drawEventAnnotations(chart, annotations);
                }
            }]
        });
    }

    renderPositionsChart(data, events = []) {
        const ctx = document.getElementById('positionsChart').getContext('2d');
        
        // Destroy existing chart
        if (this.charts.positions) {
            this.charts.positions.destroy();
        }

        // Create annotations for events
        const annotations = this.createEventAnnotations(data, events);

        this.charts.positions = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => new Date(d.analysis_date).toLocaleDateString()),
                datasets: [
                    {
                        label: 'Position 1-3',
                        data: data.map(d => d.pos_1_3 || 0),
                        borderColor: '#10B981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Position 4-10',
                        data: data.map(d => d.pos_4_10 || 0),
                        borderColor: '#F59E0B',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Position 11-20',
                        data: data.map(d => d.pos_11_20 || 0),
                        borderColor: '#EF4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Position 21+',
                        data: data.map(d => d.pos_21_plus || 0),
                        borderColor: '#6B7280',
                        backgroundColor: 'rgba(107, 114, 128, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                }
            },
            plugins: [{
                id: 'eventAnnotations',
                afterDraw: (chart) => {
                    this.drawEventAnnotations(chart, annotations);
                }
            }]
        });
    }

    // ================================
    // EVENT ANNOTATIONS
    // ================================

    createEventAnnotations(chartData, events) {
        if (!events || events.length === 0) return [];
        
        const chartDates = chartData.map(d => new Date(d.analysis_date).toDateString());
        
        return events.map(event => {
            const eventDate = new Date(event.event_date).toDateString();
            const dateIndex = chartDates.indexOf(eventDate);
            
            if (dateIndex === -1) return null;
            
            return {
                x: dateIndex,
                title: event.event_title,
                type: event.event_type,
                keywords: event.keywords_affected,
                date: eventDate
            };
        }).filter(Boolean);
    }

    drawEventAnnotations(chart, annotations) {
        if (!annotations || annotations.length === 0) return;
        
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;
        
        annotations.forEach(annotation => {
            const xPos = chart.scales.x.getPixelForValue(annotation.x);
            
            // Draw vertical line
            ctx.save();
            ctx.strokeStyle = this.getEventColor(annotation.type);
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(xPos, chartArea.top);
            ctx.lineTo(xPos, chartArea.bottom);
            ctx.stroke();
            
            // Draw icon at top
            ctx.fillStyle = this.getEventColor(annotation.type);
            ctx.font = '12px "Font Awesome 5 Free"';
            ctx.textAlign = 'center';
            ctx.fillText(this.getEventIcon(annotation.type), xPos, chartArea.top - 5);
            
            ctx.restore();
        });
    }

    getEventColor(eventType) {
        const colors = {
            'keywords_added': '#10B981',     // Green
            'keywords_removed': '#EF4444',  // Red
            'project_created': '#4F46E5',   // Blue
            'daily_analysis': '#6B7280',    // Gray
            'analysis_failed': '#F59E0B'    // Orange
        };
        return colors[eventType] || '#6B7280';
    }

    getEventIcon(eventType) {
        const icons = {
            'keywords_added': '+',
            'keywords_removed': '−',
            'project_created': '⭐',
            'daily_analysis': '📊',
            'analysis_failed': '⚠'
        };
        return icons[eventType] || '•';
    }

    showEventAnnotations(chart, annotations) {
        // This could be expanded to show tooltips on hover
        // For now, the annotations are always visible
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
        this.showElement(this.elements.progressModal);
    }

    hideProgress() {
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

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
            
            row.innerHTML = `
                <td class="rank-cell">${index + 1}</td>
                <td class="domain-cell" title="${domain.domain}">${domain.domain}</td>
                <td class="appearances-cell">${domain.appearances}</td>
                <td class="position-cell">${domain.avg_position ? domain.avg_position.toFixed(1) : '-'}</td>
                <td class="score-cell ${scoreClass}">${visibilityScore.toFixed(1)}</td>
            `;
            
            tableBody.appendChild(row);
        });
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
        
        // Add input listener for enabling delete button
        confirmInput.oninput = (e) => {
            const deleteBtn = document.getElementById('confirmDeleteBtn');
            const inputValue = e.target.value.trim();
            const projectName = currentProject.name.trim();
            const isMatch = inputValue === projectName;
            
            console.log('🔍 Delete button validation:', {
                inputValue: `"${inputValue}"`,
                projectName: `"${projectName}"`,
                inputLength: inputValue.length,
                nameLength: projectName.length,
                isMatch: isMatch
            });
            
            deleteBtn.disabled = !isMatch;
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
        const currentProject = this.getCurrentProject();
        const confirmText = document.getElementById('deleteConfirmInput').value;
        
        if (!currentProject) {
            this.showError('No project selected');
            return;
        }

        if (confirmText.trim() !== currentProject.name.trim()) {
            this.showError('Please type the project name exactly to confirm');
            return;
        }

        try {
            this.showProgress('Deleting project...');
            
            const response = await fetch(`/manual-ai/api/projects/${currentProject.id}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Failed to delete project');
            }

            this.hideProgress();
            this.hideDeleteProjectModal();
            
            // Show success message
            this.showSuccess('Project deleted successfully');
            
            // Redirect to projects list after short delay
            setTimeout(() => {
                this.showTab('projects');
                this.loadProjects();
            }, 1500);
            
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
        }
    }

    loadProjectIntoModal(project) {
        // Load into both tabs
        this.loadModalKeywords(project.id);
        this.loadModalSettings(project);
    }

    async loadModalKeywords(projectId) {
        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/keywords`);
            
            if (!response.ok) {
                throw new Error('Failed to load keywords');
            }

            const data = await response.json();
            this.renderModalKeywords(data.keywords || []);

        } catch (error) {
            console.error('Error loading modal keywords:', error);
            this.showError('Failed to load keywords');
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
        keywordsList.innerHTML = keywords.map(keyword => `
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

        } catch (error) {
            console.error('Error adding keywords:', error);
            this.showError(`Failed to add keywords: ${error.message}`);
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
                const error = await response.json();
                throw new Error(error.message || 'Failed to remove keyword');
            }

            // Reload keywords and projects
            await this.loadModalKeywords(this.currentModalProject.id);
            await this.loadProjects();
            
            this.showSuccess('Keyword removed successfully');

        } catch (error) {
            console.error('Error removing keyword:', error);
            this.showError(`Failed to remove keyword: ${error.message}`);
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
        
        // Hide project modal and show delete confirmation
        this.hideProjectModal();
        this.showElement(document.getElementById('deleteProjectModal'));
        
        // Reset confirmation input
        const confirmInput = document.getElementById('deleteConfirmInput');
        confirmInput.value = '';
        document.getElementById('confirmDeleteBtn').disabled = true;
        
        // Add input listener for enabling delete button
        confirmInput.oninput = (e) => {
            const deleteBtn = document.getElementById('confirmDeleteBtn');
            const inputValue = e.target.value.trim();
            const projectName = this.currentModalProject.name.trim();
            const isMatch = inputValue === projectName;
            
            console.log('🔍 Delete button validation (modal):', {
                inputValue: `"${inputValue}"`,
                projectName: `"${projectName}"`,
                inputLength: inputValue.length,
                nameLength: projectName.length,
                isMatch: isMatch
            });
            
            deleteBtn.disabled = !isMatch;
        };
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
            if (themeText) themeText.textContent = 'Modo Oscuro';
            localStorage.setItem('theme', 'light');
        } else {
            document.body.classList.add('dark-theme');
            if (themeIcon) themeIcon.className = 'fas fa-sun';
            if (themeText) themeText.textContent = 'Modo Claro';
            localStorage.setItem('theme', 'dark');
        }
    }

    function handleLogout() {
        if (confirm('¿Estás seguro de que quieres cerrar sesión?')) {
            // Redirect to logout endpoint
            window.location.href = '/logout';
        }
    }

    // Initialize theme from localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
        const themeIcon = document.getElementById('dropdownThemeIcon');
        const themeText = document.getElementById('dropdownThemeText');
        if (themeIcon) themeIcon.className = 'fas fa-sun';
        if (themeText) themeText.textContent = 'Modo Claro';
    }
}