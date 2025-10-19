/**
 * Manual AI System - Projects Module
 * Gestión completa de proyectos (CRUD, renderizado, validación)
 */

import { escapeHtml, getDomainLogoUrl, normalizeDomainString, isValidDomain } from './ai-mode-utils.js';

// ================================
// PROJECTS MANAGEMENT
// ================================

export async function loadProjects() {
    this.showElement(this.elements.projectsLoading);
    this.hideElement(this.elements.projectsContainer);
    this.hideElement(this.elements.projectsEmptyState);

    try {
        // Add timestamp to avoid browser cache
        const timestamp = new Date().getTime();
        const response = await fetch(`/ai-mode-projects/api/projects?_t=${timestamp}`);
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

export function renderProjects() {
    if (this.projects.length === 0) {
        this.showElement(this.elements.projectsEmptyState);
        this.hideElement(this.elements.projectsContainer);
        return;
    }

    this.hideElement(this.elements.projectsEmptyState);
    this.showElement(this.elements.projectsContainer);

    this.elements.projectsContainer.innerHTML = this.projects.map(project => `
        <div class="project-card" data-project-id="${project.id}" onclick="aiModeSystem.goToProjectAnalytics(${project.id})" style="cursor: pointer;">
            <div class="project-header">
                <h3>${escapeHtml(project.name)}</h3>
                <div class="project-actions">
                    <button type="button" class="btn-icon" onclick="event.stopPropagation(); aiModeSystem.showProjectModal(${project.id})"
                            title="Project settings" aria-label="Open project settings">
                        <i class="fas fa-cog" aria-hidden="true"></i>
                    </button>
                </div>
            </div>
            <div class="project-details">
                <div class="project-meta">
                    <span class="project-brand-name" title="Brand: ${escapeHtml(project.brand_name)}">
                        <i class="fas fa-tag"></i>
                        <span class="user-brand-highlight">${escapeHtml(project.brand_name)}</span>
                    </span>
                    <span class="project-country">
                        <i class="fas fa-flag"></i>
                        ${project.country_code}
                    </span>
                </div>
                ${project.description ? `<p class="project-description">${escapeHtml(project.description)}</p>` : ''}
            </div>
            <div class="project-stats">
                <div class="stat">
                    <span class="stat-number">${project.total_keywords || 0}</span>
                    <span class="stat-label">Total Keywords</span>
                </div>
                <div class="stat">
                    <span class="stat-number">${project.total_mentions || 0}</span>
                    <span class="stat-label">Brand Mentions</span>
                </div>
                <div class="stat">
                    <span class="stat-number">${project.visibility_percentage ? Math.round(project.visibility_percentage) + '%' : '0%'}</span>
                    <span class="stat-label">Visibility (%)</span>
                </div>
                <div class="stat">
                    <span class="stat-number">${project.avg_position ? Math.round(project.avg_position * 10) / 10 : '-'}</span>
                    <span class="stat-label">Average Position</span>
                </div>
            </div>
            <div class="project-meta-sections">
                ${this.renderProjectCompetitorsHorizontal(project)}
                ${this.renderProjectClustersHorizontal(project)}
            </div>
            <div class="project-footer">
                <small class="last-analysis">
                    Last analysis: ${project.last_analysis_date ? 
                        new Date(project.last_analysis_date).toLocaleDateString() : 'Never'}
                </small>
                ${(!project.last_analysis_date && (project.total_keywords || 0) > 0) ? `
                    <div class="first-run-cta" style="margin-top: 10px;">
                        <button type="button" class="btn-primary btn-small" 
                                onclick="event.stopPropagation(); aiModeSystem.analyzeProject(${project.id})"
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

export function renderProjectCompetitorsSection(project) {
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
        const logoUrl = getDomainLogoUrl(domain);
        const firstLetter = escapeHtml(domain.charAt(0).toUpperCase());
        const safeDomain = escapeHtml(domain);
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
    const competitorNames = competitorsData.slice(0, 2).map(domain => escapeHtml(domain)).join(', ');
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

export function renderProjectCompetitorsHorizontal(project) {
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
        const logoUrl = getDomainLogoUrl(domain);
        const firstLetter = escapeHtml(domain.charAt(0).toUpperCase());
        const safeDomain = escapeHtml(domain);
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
                <span class="competitor-horizontal-name">${escapeHtml(domain)}</span>
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

export function renderProjectClustersHorizontal(project) {
    const clustersConfig = project.topic_clusters || {};
    const clustersEnabled = clustersConfig.enabled || false;
    const clustersList = clustersConfig.clusters || [];
    const clustersCount = clustersList.length;
    
    if (!clustersEnabled || clustersCount === 0) {
        return ''; // No mostrar nada si no hay clusters
    }
    
    // Mostrar hasta 3 clusters
    const displayClusters = clustersList.slice(0, 3);
    const moreCount = clustersCount > 3 ? clustersCount - 3 : 0;
    
    const clustersBadges = displayClusters.map(cluster => {
        const escapedName = cluster.name.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `
            <span class="cluster-badge" title="${escapedName}">
                <i class="fas fa-layer-group"></i>
                ${escapedName}
            </span>
        `;
    }).join('');
    
    const moreText = moreCount > 0 ? `<span class="clusters-more">+${moreCount} more</span>` : '';
    
    return `
        <div class="project-clusters-horizontal">
            <h5 class="clusters-section-title">Thematic Clusters</h5>
            <div class="clusters-horizontal-list">
                ${clustersBadges}
                ${moreText}
            </div>
        </div>
    `;
}

export function goToProjectAnalytics(projectId) {
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

export function showCreateProject() {
    // Verificar plan antes de mostrar formulario
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

export function hideCreateProject() {
    this.hideElement(this.elements.createProjectModal);
}

export async function handleCreateProject(e) {
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
        const response = await fetch('/ai-mode-projects/api/projects', {
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

export function normalizeProjectDomain() {
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

export function validateProjectDomain() {
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

export function filterCountryOptions() {
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

export function addCompetitorChip() {
    if (!this.elements.competitorInput || !this.elements.competitorChips) return;
    const raw = (this.elements.competitorInput.value || '').trim().toLowerCase();
    if (!raw) return;
    const normalized = normalizeDomainString(raw);
    if (!isValidDomain(normalized)) {
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

export function getCompetitorChipValues() {
    if (!this.elements.competitorChips) return [];
    return Array.from(this.elements.competitorChips.querySelectorAll('.chip')).map(el => el.textContent || '').filter(Boolean);
}

export function setCompetitorError(msg) {
    if (this.elements.competitorError) this.elements.competitorError.textContent = msg || '';
}

