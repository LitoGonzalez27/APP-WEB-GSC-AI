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
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // Create project button
        document.getElementById('btnCreateProject')?.addEventListener('click', () => {
            this.showProjectModal();
        });

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

        document.getElementById('btnSaveProject')?.addEventListener('click', () => {
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

        // Export comparison
        document.getElementById('btnExportComparison')?.addEventListener('click', () => {
            this.exportComparison();
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
            const response = await fetch(`${this.baseUrl}/projects`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            loading.style.display = 'none';
            
            if (!data.projects || data.projects.length === 0) {
                empty.style.display = 'flex';
                return;
            }
            
            // Render project cards
            data.projects.forEach(project => {
                this.renderProjectCard(project, grid);
            });
            
            console.log(`✅ Loaded ${data.projects.length} projects`);
            
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
        document.getElementById('projectsSection').style.display = 'none';
        document.getElementById('metricsSection').style.display = 'block';
        
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
            document.getElementById('kpiAvgPosition').textContent = 'No data';
            document.getElementById('kpiShareOfVoice').textContent = 'No data';
            document.getElementById('kpiSentiment').textContent = 'No data';
            return;
        }
        
        // Calculate averages across all LLMs
        const llms = Object.keys(metrics);
        const avgMentionRate = llms.reduce((sum, llm) => sum + (metrics[llm].mention_rate || 0), 0) / llms.length;
        const avgPosition = llms.reduce((sum, llm) => sum + (metrics[llm].avg_position || 0), 0) / llms.length;
        const avgSOV = llms.reduce((sum, llm) => sum + (metrics[llm].share_of_voice || 0), 0) / llms.length;
        
        // Calculate weighted sentiment
        let totalPositive = 0, totalNeutral = 0, totalNegative = 0;
        llms.forEach(llm => {
            if (metrics[llm].sentiment) {
                totalPositive += metrics[llm].sentiment.positive || 0;
                totalNeutral += metrics[llm].sentiment.neutral || 0;
                totalNegative += metrics[llm].sentiment.negative || 0;
            }
        });
        
        const avgPositive = totalPositive / llms.length;
        const sentimentLabel = avgPositive > 60 ? 'Positive' : avgPositive > 40 ? 'Neutral' : 'Negative';
        const sentimentClass = avgPositive > 60 ? 'positive' : avgPositive > 40 ? 'neutral' : 'negative';
        
        document.getElementById('kpiMentionRate').textContent = `${avgMentionRate.toFixed(1)}%`;
        document.getElementById('kpiAvgPosition').textContent = avgPosition > 0 ? `#${avgPosition.toFixed(1)}` : 'N/A';
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
            this.renderShareOfVoiceChart(data);
            
            // Load comparison
            await this.loadComparison(projectId);
            
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
    renderShareOfVoiceChart(data) {
        const canvas = document.getElementById('chartShareOfVoice');
        if (!canvas) return;
        
        // Destroy existing chart
        if (this.charts.shareOfVoice) {
            this.charts.shareOfVoice.destroy();
        }
        
        // Prepare data (mock for now, replace with actual competitor data)
        const labels = ['Your Brand'];
        const values = [50]; // Replace with actual data
        const colors = ['rgba(59, 130, 246, 0.8)'];
        
        // Create chart
        this.charts.shareOfVoice = new Chart(canvas, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: context => `${context.label}: ${context.parsed.toFixed(1)}%`
                        }
                    }
                }
            }
        });
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
            `${item.mention_rate.toFixed(1)}%`,
            item.avg_position ? `#${item.avg_position.toFixed(1)}` : 'N/A',
            `${item.share_of_voice.toFixed(1)}%`,
            this.getSentimentLabel(item.sentiment_score),
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
     * Show projects list
     */
    showProjectsList() {
        document.getElementById('projectsSection').style.display = 'block';
        document.getElementById('metricsSection').style.display = 'none';
        this.currentProject = null;
    }

    /**
     * Show project modal (create or edit)
     */
    showProjectModal(project = null) {
        const modal = document.getElementById('projectModal');
        const title = document.getElementById('modalTitle');
        const btnText = document.getElementById('btnSaveText');
        
        if (project) {
            // Edit mode
            title.textContent = 'Edit Project';
            btnText.textContent = 'Update Project';
            
            // Fill form
            document.getElementById('projectName').value = project.name || '';
            document.getElementById('brandName').value = project.brand_name || '';
            document.getElementById('industry').value = project.industry || '';
            document.getElementById('competitors').value = project.competitors?.join(', ') || '';
            document.getElementById('language').value = project.language || 'es';
            document.getElementById('queriesPerLlm').value = project.queries_per_llm || 15;
            
            // Check LLMs
            const llmCheckboxes = document.querySelectorAll('input[name="llm"]');
            llmCheckboxes.forEach(cb => {
                cb.checked = project.enabled_llms?.includes(cb.value) || false;
            });
        } else {
            // Create mode
            title.textContent = 'Create Project';
            btnText.textContent = 'Create Project';
            
            // Reset form
            document.getElementById('projectForm').reset();
            
            // Check all LLMs by default
            const llmCheckboxes = document.querySelectorAll('input[name="llm"]');
            llmCheckboxes.forEach(cb => cb.checked = true);
        }
        
        modal.style.display = 'flex';
    }

    /**
     * Hide project modal
     */
    hideProjectModal() {
        document.getElementById('projectModal').style.display = 'none';
    }

    /**
     * Save project (create or update)
     */
    async saveProject() {
        console.log('💾 Saving project...');
        
        // Get form data
        const name = document.getElementById('projectName').value.trim();
        const brandName = document.getElementById('brandName').value.trim();
        const industry = document.getElementById('industry').value.trim();
        const competitorsStr = document.getElementById('competitors').value.trim();
        const language = document.getElementById('language').value;
        const queriesPerLlm = parseInt(document.getElementById('queriesPerLlm').value);
        
        // Get checked LLMs
        const llmCheckboxes = document.querySelectorAll('input[name="llm"]:checked');
        const enabledLlms = Array.from(llmCheckboxes).map(cb => cb.value);
        
        // Validate
        if (!name || !brandName || !industry) {
            this.showError('Please fill all required fields');
            return;
        }
        
        if (brandName.length < 2) {
            this.showError('Brand name must be at least 2 characters');
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
        
        // Parse competitors
        const competitors = competitorsStr ? competitorsStr.split(',').map(c => c.trim()).filter(c => c) : [];
        
        // Prepare payload
        const payload = {
            name,
            brand_name: brandName,
            industry,
            competitors,
            language,
            enabled_llms: enabledLlms,
            queries_per_llm: queriesPerLlm
        };
        
        // Show loading
        const btnSave = document.getElementById('btnSaveProject');
        const btnText = document.getElementById('btnSaveText');
        const btnSpinner = btnSave.querySelector('.btn-spinner');
        
        btnText.style.display = 'none';
        btnSpinner.style.display = 'inline-block';
        btnSave.disabled = true;
        
        try {
            const isEdit = this.currentProject && this.currentProject.id;
            const url = isEdit ? `${this.baseUrl}/projects/${this.currentProject.id}` : `${this.baseUrl}/projects`;
            const method = isEdit ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            console.log(`✅ Project ${isEdit ? 'updated' : 'created'} successfully`);
            
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
            btnText.style.display = 'inline';
            btnSpinner.style.display = 'none';
            btnSave.disabled = false;
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
                
                // Reload metrics
                this.viewProject(this.currentProject.id);
                
                // Show success
                this.showSuccess(`Analysis completed! ${data.results.total_queries_executed} queries analyzed.`);
            }, 1500);
            
        } catch (error) {
            console.error('❌ Error running analysis:', error);
            modal.style.display = 'none';
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
    getSentimentLabel(score) {
        if (score > 60) return '😊 Positive';
        if (score > 40) return '😐 Neutral';
        return '😞 Negative';
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
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.LLMMonitoring = LLMMonitoring;
}

