/**
 * Manual AI System - Modals Module
 * Gestión de modales (proyectos, keywords, settings, results)
 */

import { escapeHtml } from './ai-mode-utils.js';

// ================================
// PROJECT RESULTS MODAL
// ================================

export async function loadProjectResults(projectId) {
    const resultsContent = document.getElementById('resultsContent');
    resultsContent.innerHTML = '<div class="loading-small"><i class="fas fa-spinner fa-spin"></i> Loading results...</div>';

    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/results`);
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

export function renderResults(results) {
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
                                    <div class="col-keyword">${escapeHtml(result.keyword)}</div>
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
                                        ${result.domain_position ? result.domain_position : '-'}
                                    </div>
                                    <div class="col-impact">
                                        <span class="impact-badge ${this.getImpactClass(result)}">
                                            ${this.calculateImpact(result)}
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

export function getImpactClass(result) {
    if (result.has_ai_overview && result.domain_mentioned) {
        if (result.domain_position <= 3) return 'impact-high';
        if (result.domain_position <= 10) return 'impact-medium';
        return 'impact-low';
    }
    if (result.has_ai_overview) return 'impact-potential';
    return 'impact-none';
}

export function calculateImpact(result) {
    if (result.has_ai_overview && result.domain_mentioned) {
        if (result.domain_position <= 3) return 'High';
        if (result.domain_position <= 10) return 'Medium';
        return 'Low';
    }
    if (result.has_ai_overview) return 'Potential';
    return 'None';
}

// ================================
// PROJECT MODAL MANAGEMENT
// ================================

export function showProjectModal(projectId) {
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

export function hideProjectModal() {
    this.hideElement(document.getElementById('projectModal'));
    this.currentModalProject = null;
    
    // Reset modal to keywords tab
    this.switchModalTab('keywords');
}

export function switchModalTab(tabName) {
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

export function loadProjectIntoModal(project) {
    // Load into both tabs
    this.loadModalKeywords(project.id);
    this.loadModalSettings(project);
    this.loadCompetitors(project.id);
}

export async function loadModalKeywords(projectId) {
    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/keywords`);
        
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

export function renderModalKeywords(keywords) {
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
    
    const filteredKeywords = query 
        ? keywords.filter(kw => kw.keyword.toLowerCase().includes(query))
        : keywords;

    keywordsList.innerHTML = filteredKeywords.map(keyword => `
        <div class="modal-keyword-item">
            <span class="keyword-text">${escapeHtml(keyword.keyword)}</span>
            <div class="keyword-stats">
                <span class="keyword-stat" title="Analyses count">
                    <i class="fas fa-chart-line"></i> ${keyword.analysis_count || 0}
                </span>
                <span class="keyword-stat" title="AI Overview frequency">
                    <i class="fas fa-robot"></i> ${keyword.ai_overview_frequency ? Math.round(keyword.ai_overview_frequency * 100) + '%' : '0%'}
                </span>
            </div>
        </div>
    `).join('');
}

export function loadModalSettings(project) {
    // Load project settings into modal
    const projectNameEdit = document.getElementById('projectNameEdit');
    const projectDescriptionEdit = document.getElementById('projectDescriptionEdit');
    const projectDomainEdit = document.getElementById('projectDomainEdit');
    const projectCountryEdit = document.getElementById('projectCountryEdit');
    
    // Only set values for elements that exist
    if (projectNameEdit) {
        projectNameEdit.value = project.name || '';
    }
    
    if (projectDescriptionEdit) {
        projectDescriptionEdit.value = project.description || '';
    }
    
    if (projectDomainEdit) {
        projectDomainEdit.value = project.domain || '';
    }
    
    if (projectCountryEdit) {
        projectCountryEdit.value = project.country_code || '';
    }
    
    // Load clusters configuration if function exists
    if (typeof this.loadProjectClustersForSettings === 'function') {
        this.loadProjectClustersForSettings(project.id);
    }
}

