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

    this.elements.projectsContainer.innerHTML = this.projects.map(project => {
        const canEdit = project.can_edit !== false;
        const isActive = project.is_active !== false;
        const isPausedByQuota = !!project.is_paused_by_quota;
        const cardClickable = isActive && !isPausedByQuota;
        const cardOnClick = cardClickable
            ? `onclick="aiModeSystem.goToProjectAnalytics(${project.id})"`
            : '';
        const cardStyle = cardClickable
            ? 'cursor: pointer;'
            : 'cursor: default; opacity: 0.78;';

        const safeName = JSON.stringify(project.name || '');
        const pausedUntilLabel = formatPauseDate(project.paused_until);
        let statusBadge = '';
        if (!isActive) {
            statusBadge = `
                <span class="badge badge-language" title="This project is paused. It will not run in automatic analyses." style="background:#fef3c7;color:#92400e;border:1px solid #fde68a;">
                    <i class="fas fa-pause" style="margin-right:4px;"></i>Paused
                </span>
            `;
        } else if (isPausedByQuota) {
            statusBadge = `
                <span class="badge badge-language" title="Paused automatically because the monthly quota is exhausted." style="background:#fee2e2;color:#991b1b;border:1px solid #fecaca;">
                    <i class="fas fa-pause" style="margin-right:4px;"></i>Paused (quota)${pausedUntilLabel ? ` · resumes ${pausedUntilLabel}` : ''}
                </span>
            `;
        }

        const hasInitialAnalysis = !!project.last_analysis_date;
        const hasKeywords = (project.total_keywords || 0) > 0;
        const showFirstRunCta = canEdit && cardClickable && !hasInitialAnalysis && hasKeywords;
        const showPauseBtn = canEdit && isActive;
        const showResumeBtn = canEdit && !isActive;
        const showDeleteBtn = canEdit && !isActive;

        return `
        <div class="project-card${!cardClickable ? ' project-card--paused' : ''}" data-project-id="${project.id}" ${cardOnClick} style="${cardStyle}">
            <div class="project-header">
                <h3>${escapeHtml(project.name)}</h3>
                ${(canEdit === false) ? `
                    <div class="project-actions">
                        <span class="badge badge-language">Shared (view only)</span>
                        ${statusBadge}
                    </div>
                ` : `
                    <div class="project-actions" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                        ${statusBadge}
                        <button type="button" class="btn-icon" onclick="event.stopPropagation(); aiModeSystem.showProjectModal(${project.id})"
                                title="Project settings" aria-label="Open project settings">
                            <i class="fas fa-cog" aria-hidden="true"></i>
                        </button>
                    </div>
                `}
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
                <div class="project-footer-actions" style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
                    ${showFirstRunCta ? `
                        <button type="button" class="btn-primary btn-small"
                                onclick="event.stopPropagation(); aiModeSystem.analyzeProject(${project.id})"
                                title="Run the first analysis for this project">
                            <i class="fas fa-play"></i>
                            Run first analysis now
                        </button>
                    ` : ''}
                    ${showPauseBtn ? `
                        <button type="button" class="btn-secondary btn-small"
                                onclick="event.stopPropagation(); aiModeSystem.pauseProject(${project.id}, ${safeName})"
                                title="Pause this project — it will stop running in automatic analyses and stop consuming quota.">
                            <i class="fas fa-pause"></i>
                            Pause
                        </button>
                    ` : ''}
                    ${showResumeBtn ? `
                        <button type="button" class="btn-primary btn-small"
                                onclick="event.stopPropagation(); aiModeSystem.resumeProject(${project.id}, ${safeName})"
                                title="Resume this project. Requires available monthly quota.">
                            <i class="fas fa-play"></i>
                            Resume
                        </button>
                    ` : ''}
                    ${showDeleteBtn ? `
                        <button type="button" class="btn-danger btn-small"
                                onclick="event.stopPropagation(); aiModeSystem.deleteProjectPermanently(${project.id}, ${safeName})"
                                title="Permanently delete this project and all its data.">
                            <i class="fas fa-trash"></i>
                            Delete
                        </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
    }).join('');
}

function formatPauseDate(value) {
    if (!value) return '';
    try {
        const d = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(d.getTime())) return '';
        return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
    } catch (_) {
        return '';
    }
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
    const selectedProject = this.projects.find(p => Number(p.id) === Number(projectId));
    if (selectedProject) {
        this.currentProject = selectedProject;
    }

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
    // Bloqueo por plan para mantener consistencia con el overlay del dashboard
    if (window.currentUser && window.currentUser.plan === 'free') {
        if (window.currentUser.has_shared_access) {
            this.showError('You have view-only access to shared projects. Creating new projects requires a paid owner plan.');
            return;
        }

        console.log('🆓 Usuario gratuito bloqueado al crear proyecto - redirigiendo a billing');
        window.location.href = '/billing';
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

// ================================
// PAUSE / RESUME / DELETE
// ================================

export async function pauseProject(projectId, projectName) {
    const name = projectName || 'this project';
    const confirmed = window.confirm(
        `Pause "${name}"?\n\nThe project will stop running in automatic analyses and will not consume any quota until you resume it. All its data will be kept.`
    );
    if (!confirmed) return;

    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/pause`, {
            method: 'PUT',
            credentials: 'same-origin'
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }

        this.showSuccess(data.message || `Project "${name}" paused.`);
        await this.loadProjects();
    } catch (error) {
        console.error('Error pausing project:', error);
        this.showError(error.message || 'Failed to pause project');
    }
}

export async function resumeProject(projectId, projectName) {
    const name = projectName || 'this project';
    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/resume`, {
            method: 'PUT',
            credentials: 'same-origin'
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 402 && data.error === 'quota_exceeded') {
            const renewal = formatRenewalDate(data.reset_date);
            const renewalSuffix = renewal ? ` until ${renewal}` : '';
            this.showError(
                `Quota exhausted${renewalSuffix}. You can resume "${name}" once your plan renews.`
            );
            return;
        }

        if (!response.ok || !data.success) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }

        this.showSuccess(data.message || `Project "${name}" reactivated.`);
        await this.loadProjects();
    } catch (error) {
        console.error('Error resuming project:', error);
        this.showError(error.message || 'Failed to resume project');
    }
}

export async function deleteProjectPermanently(projectId, projectName) {
    const name = projectName || 'this project';
    const confirmed = window.confirm(
        `Permanently delete "${name}"?\n\nThis will remove the project, all its keywords, results and history. This action cannot be undone.`
    );
    if (!confirmed) return;

    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });

        const data = await response.json().catch(() => ({}));
        if (response.status === 400 && data.action_required === 'deactivate_first') {
            this.showError('Pause the project first before deleting it.');
            return;
        }
        if (!response.ok || !data.success) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }

        this.showSuccess(data.message || `Project "${name}" permanently deleted.`);
        await this.loadProjects();
    } catch (error) {
        console.error('Error deleting project:', error);
        this.showError(error.message || 'Failed to delete project');
    }
}

function formatRenewalDate(value) {
    if (!value) return '';
    try {
        const d = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(d.getTime())) return '';
        return d.toLocaleDateString(undefined, { day: '2-digit', month: 'long', year: 'numeric' });
    } catch (_) {
        return '';
    }
}
