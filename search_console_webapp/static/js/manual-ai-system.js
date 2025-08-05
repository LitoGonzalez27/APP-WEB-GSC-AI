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
                        <button type="button" class="btn-icon" onclick="manualAI.showProjectDetails(${project.id})"
                                title="View details">
                            <i class="fas fa-eye"></i>
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
            `Analyzing ${project.keyword_count} keywords for AI Overview visibility`);

        try {
            const response = await fetch(`/manual-ai/api/projects/${projectId}/analyze`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
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
            this.showError(error.message || 'Analysis failed');
        } finally {
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

        // Show charts container
        this.hideElement(this.elements.analyticsContent);
        this.showElement(this.elements.chartsContainer);

        // Render charts
        this.renderVisibilityChart(stats.visibility_chart);
        this.renderPositionsChart(stats.positions_chart);
    }

    renderVisibilityChart(data) {
        const ctx = document.getElementById('visibilityChart').getContext('2d');
        
        // Destroy existing chart
        if (this.charts.visibility) {
            this.charts.visibility.destroy();
        }

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
                }
            }
        });
    }

    renderPositionsChart(data) {
        const ctx = document.getElementById('positionsChart').getContext('2d');
        
        // Destroy existing chart
        if (this.charts.positions) {
            this.charts.positions.destroy();
        }

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
            }
        });
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
}

// Auto-initialize if we're on the manual AI page
if (window.location.pathname.includes('/manual-ai/')) {
    console.log('📍 Manual AI page detected - ready for initialization');
}