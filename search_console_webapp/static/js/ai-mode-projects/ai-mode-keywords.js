/**
 * Manual AI System - Keywords Module
 * Gestión completa de keywords (CRUD, renderizado, validación)
 */

import { escapeHtml } from './ai-mode-utils.js';

// ================================
// KEYWORDS LOADING & RENDERING
// ================================

export async function loadProjectKeywords(projectId) {
    const keywordsList = document.getElementById('keywordsList');
    keywordsList.innerHTML = '<div class="loading-small"><i class="fas fa-spinner fa-spin"></i> Loading keywords...</div>';

    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/keywords`);
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

export function renderKeywords(keywords) {
    const keywordsList = document.getElementById('keywordsList');
    
    if (keywords.length === 0) {
        keywordsList.innerHTML = `
            <div class="empty-keywords">
                <i class="fas fa-key"></i>
                <p>No keywords added yet</p>
                <button type="button" class="btn-primary btn-sm" onclick="aiModeSystem.showAddKeywords()">
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
                        <div class="col-keyword">${escapeHtml(keyword.keyword)}</div>
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
                                    onclick="aiModeSystem.toggleKeyword(${keyword.id})"
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

export function showAddKeywords() {
    this.elements.addKeywordsForm.reset();
    this.updateKeywordsCounter();
    this.showElement(this.elements.addKeywordsModal);
}

export function hideAddKeywords() {
    this.hideElement(this.elements.addKeywordsModal);
}

export function updateKeywordsCounter() {
    const textarea = document.getElementById('keywordsTextarea');
    const counter = document.getElementById('keywordsCount');
    
    if (textarea && counter) {
        const keywords = textarea.value.split('\n').filter(k => k.trim().length > 0);
        counter.textContent = keywords.length;
    }
}

export async function handleAddKeywords(e) {
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
        const response = await fetch(`/ai-mode-projects/api/projects/${this.currentProject.id}/keywords`, {
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

export function toggleKeyword(keywordId) {
    // TODO: Implement keyword toggle functionality
    console.log('Toggle keyword:', keywordId);
}

