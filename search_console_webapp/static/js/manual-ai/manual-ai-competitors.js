/**
 * Manual AI System - Competitors Module
 * Gestión completa de competidores (CRUD, preview, charts)
 */

import { getDomainLogoUrl, isValidDomain } from './manual-ai-utils.js';

// ================================
// COMPETITORS LOADING & RENDERING
// ================================

export async function loadCompetitors(projectId = null) {
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

export function renderCompetitors(competitors) {
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
        const logoUrl = getDomainLogoUrl(domain);
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

// ================================
// COMPETITORS CRUD
// ================================

export async function addCompetitor() {
    const newCompetitorInput = document.getElementById('newCompetitorInput');
    const domain = newCompetitorInput.value.trim();

    if (!domain) {
        this.showError('Please enter a domain');
        return;
    }

    // Basic domain validation
    if (!isValidDomain(domain)) {
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

export async function removeCompetitor(domain) {
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

export async function updateCompetitors(competitors) {
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

// ================================
// COMPETITORS PREVIEW (Dashboard Main)
// ================================

export async function loadCompetitorsPreview(projectId) {
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

export function renderCompetitorsPreview(competitors) {
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
        const logoUrl = getDomainLogoUrl(domain);
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
// COMPETITORS INITIALIZATION
// ================================

export function initCompetitorsManager() {
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

