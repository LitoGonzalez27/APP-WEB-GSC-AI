/**
 * Manual AI System - Modals Module
 * Gestión de modales (proyectos, keywords, settings, results)
 */

import { escapeHtml } from './manual-ai-utils.js';

const PROJECT_ACCESS_MODULE = 'manual_ai';

function formatAccessDate(value) {
    if (!value) return '-';
    try {
        return new Date(value).toLocaleString();
    } catch (error) {
        return '-';
    }
}

// ================================
// PROJECT RESULTS MODAL
// ================================

export async function loadProjectResults(projectId) {
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

export function renderResults(results) {
    const resultsContent = document.getElementById('resultsContent');
    const isReadOnly = this.isProjectReadOnly();
    
    if (results.length === 0) {
        resultsContent.innerHTML = `
            <div class="empty-keywords">
                <i class="fas fa-chart-bar"></i>
                <p>No analysis results yet</p>
                ${isReadOnly ? '<p class="small" style="margin-top:8px;">Shared project (view only)</p>' : `
                    <button type="button" class="btn-primary btn-sm" onclick="manualAI.runAnalysis()">
                        <i class="fas fa-play"></i>
                        Run First Analysis
                    </button>
                `}
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
    this.currentProject = project;

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
        const response = await fetch(`/manual-ai/api/projects/${projectId}/keywords`);
        
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
    const modalProjectName = document.getElementById('modalProjectName');
    const modalProjectDescription = document.getElementById('modalProjectDescription');
    
    // Only set values for elements that exist
    if (projectNameEdit) {
        projectNameEdit.value = project.name || '';
    }
    
    if (projectDescriptionEdit) {
        projectDescriptionEdit.value = project.description || '';
    }

    if (modalProjectName) {
        modalProjectName.value = project.name || '';
    }

    if (modalProjectDescription) {
        modalProjectDescription.value = project.description || '';
    }
    
    if (projectDomainEdit) {
        projectDomainEdit.value = project.domain || '';
    }
    
    if (projectCountryEdit) {
        projectCountryEdit.value = project.country_code || '';
    }

    const isReadOnly = project?.can_edit === false;
    const toggleDisabled = (el, disabled) => {
        if (!el) return;
        el.disabled = disabled;
        if (disabled) {
            el.setAttribute('aria-disabled', 'true');
        } else {
            el.removeAttribute('aria-disabled');
        }
    };
    const toggleActionButton = (selector, visible) => {
        const button = document.querySelector(selector);
        if (!button) return;
        button.style.display = visible ? '' : 'none';
        button.disabled = !visible;
    };

    toggleDisabled(projectNameEdit, isReadOnly);
    toggleDisabled(projectDescriptionEdit, isReadOnly);
    toggleDisabled(modalProjectName, isReadOnly);
    toggleDisabled(modalProjectDescription, isReadOnly);
    toggleDisabled(document.getElementById('modalKeywordsInput'), isReadOnly);
    toggleDisabled(document.getElementById('newCompetitorInput'), isReadOnly);
    toggleDisabled(document.getElementById('projectClustersEnabled'), isReadOnly);
    toggleDisabled(document.getElementById('modalNotesInput'), isReadOnly);

    toggleActionButton('button[onclick="manualAI.addKeywordsFromModal()"]', !isReadOnly);
    toggleActionButton('button[onclick="manualAI.addCompetitor()"]', !isReadOnly);
    toggleActionButton('button[onclick="manualAI.saveClustersConfiguration()"]', !isReadOnly);
    toggleActionButton("button[onclick=\"manualAI.addClusterRow('clustersList')\"]", !isReadOnly);
    toggleActionButton('button[onclick="manualAI.addNoteFromModal()"]', !isReadOnly);
    toggleActionButton('button[onclick="manualAI.updateProjectFromModal()"]', !isReadOnly);
    toggleActionButton('button[onclick="manualAI.confirmDeleteProjectFromModal()"]', !isReadOnly);

    if (typeof this.loadProjectAccessSection === 'function') {
        this.loadProjectAccessSection(project);
    }
    
    // Load clusters configuration if function exists
    if (typeof this.loadProjectClustersForSettings === 'function') {
        this.loadProjectClustersForSettings(project.id);
    }
}

// ================================
// PROJECT DELETION
// ================================

export function confirmDeleteProjectFromModal() {
    if (!this.currentModalProject) {
        this.showError('No project selected');
        return;
    }

    if (!this.assertProjectEditable(this.currentModalProject)) {
        return;
    }

    // Set project name in delete modal
    document.getElementById('deleteProjectName').textContent = this.currentModalProject.name;
    document.getElementById('deleteProjectNamePrompt').textContent = this.currentModalProject.name;
    
    // Store project reference for deletion (use the same variable as the other function)
    this.projectToDelete = this.currentModalProject;
    
    // Hide project modal and show delete confirmation
    this.hideProjectModal();
    this.showElement(document.getElementById('deleteProjectModal'));
    
    // Reset confirmation input
    const confirmInput = document.getElementById('deleteConfirmInput');
    confirmInput.value = '';
    document.getElementById('confirmDeleteBtn').disabled = true;
    
    // Remove any existing event listener to prevent duplicates
    confirmInput.oninput = null;
    
    // Add input listener for enabling delete button
    confirmInput.oninput = (e) => {
        const deleteBtn = document.getElementById('confirmDeleteBtn');
        const inputValue = e.target.value.trim();
        
        // Safety check: ensure projectToDelete exists
        if (!this.projectToDelete || !this.projectToDelete.name) {
            console.error('❌ projectToDelete is null or has no name');
            deleteBtn.disabled = true;
            return;
        }
        
        const projectName = this.projectToDelete.name.trim();
        const isMatch = inputValue === projectName;
        
        console.log('🔍 Delete button validation (modal):', {
            inputValue: `"${inputValue}"`,
            projectName: `"${projectName}"`,
            inputLength: inputValue.length,
            nameLength: projectName.length,
            isMatch: isMatch,
            inputCharCodes: Array.from(inputValue).map(c => c.charCodeAt(0)),
            nameCharCodes: Array.from(projectName).map(c => c.charCodeAt(0))
        });
        
        deleteBtn.disabled = !isMatch;
    };
}

export function confirmDeleteProject(projectId) {
    // Find project from list
    const currentProject = this.projects.find(p => p.id === projectId);
    if (!currentProject) {
        this.showError('Project not found');
        return;
    }

    if (!this.assertProjectEditable(currentProject)) {
        return;
    }

    // Set project name in delete modal
    document.getElementById('deleteProjectName').textContent = currentProject.name;
    document.getElementById('deleteProjectNamePrompt').textContent = currentProject.name;
    
    // Reset confirmation input
    const confirmInput = document.getElementById('deleteConfirmInput');
    confirmInput.value = '';
    document.getElementById('confirmDeleteBtn').disabled = true;
    
    // Store project reference for deletion
    this.projectToDelete = currentProject;
    
    // Remove any existing event listener to prevent duplicates
    confirmInput.oninput = null;
    
    // Add input listener for enabling delete button
    confirmInput.oninput = (e) => {
        const deleteBtn = document.getElementById('confirmDeleteBtn');
        const inputValue = e.target.value.trim();
        
        // Use the stored project reference
        if (!this.projectToDelete || !this.projectToDelete.name) {
            console.error('❌ projectToDelete is null or has no name');
            deleteBtn.disabled = true;
            return;
        }
        
        const projectName = this.projectToDelete.name.trim();
        const isMatch = inputValue === projectName;
        
        console.log('🔍 Delete button validation:', {
            inputValue: `"${inputValue}"`,
            projectName: `"${projectName}"`,
            inputLength: inputValue.length,
            nameLength: projectName.length,
            isMatch: isMatch,
            charCodes: {
                input: Array.from(inputValue).map(c => c.charCodeAt(0)),
                name: Array.from(projectName).map(c => c.charCodeAt(0))
            }
        });
        
        deleteBtn.disabled = !isMatch;
    };
    
    // Show delete modal
    this.showElement(document.getElementById('deleteProjectModal'));
}

export function cancelDeleteProject() {
    this.hideElement(document.getElementById('deleteProjectModal'));
    this.projectToDelete = null;
    document.getElementById('deleteConfirmInput').value = '';
    document.getElementById('confirmDeleteBtn').disabled = true;
}

export async function executeDeleteProject() {
    if (!this.assertProjectEditable(this.projectToDelete || this.currentModalProject || this.currentProject)) {
        return;
    }

    const projectToDelete = this.projectToDelete;
    const confirmText = document.getElementById('deleteConfirmInput').value;
    
    if (!projectToDelete) {
        this.showError('No project selected for deletion');
        return;
    }

    if (confirmText.trim() !== projectToDelete.name.trim()) {
        this.showError('Please type the project name exactly to confirm');
        return;
    }

    try {
        this.showProgress('Deleting project...', 'Removing project and all associated data...');
        
        const response = await fetch(`/manual-ai/api/projects/${encodeURIComponent(projectToDelete.id)}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            this.showSuccess('Project deleted successfully');
            
            // Close delete modal
            this.cancelDeleteProject();
            
            // Reload projects
            await this.loadProjects();
            this.populateAnalyticsProjectSelect();
            
            // Clear analytics if deleted project was selected
            if (this.elements.analyticsProjectSelect?.value == projectToDelete.id) {
                this.elements.analyticsProjectSelect.value = '';
                this.elements.analyticsContent.innerHTML = '<div class="empty-analytics"><i class="fas fa-chart-line"></i><p>Select a project to view analytics</p></div>';
            }
        } else {
            throw new Error(data.error || 'Failed to delete project');
        }
    } catch (error) {
        console.error('Error deleting project:', error);
        this.showError(error.message || 'Failed to delete project');
    } finally {
        this.hideProgress();
    }
}

export async function updateProjectFromModal() {
    if (!this.assertProjectEditable(this.currentModalProject || this.currentProject)) {
        return;
    }

    const newName = (
        document.getElementById('projectNameEdit')?.value ??
        document.getElementById('modalProjectName')?.value ??
        ''
    ).trim();
    const newDescription = (
        document.getElementById('projectDescriptionEdit')?.value ??
        document.getElementById('modalProjectDescription')?.value ??
        ''
    ).trim();
    
    if (!newName) {
        this.showError('Project name cannot be empty');
        return;
    }

    if (!this.currentModalProject) {
        this.showError('No project selected');
        return;
    }

    try {
        this.showProgress('Updating project...', 'Saving changes...');
        
        const response = await fetch(`/manual-ai/api/projects/${this.currentModalProject.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: newName,
                description: newDescription
            })
        });

        const data = await response.json();

        if (data.success) {
            this.showSuccess('Project updated successfully');
            
            // Update local project data
            const projectIndex = this.projects.findIndex(p => p.id === this.currentModalProject.id);
            if (projectIndex !== -1) {
                this.projects[projectIndex].name = newName;
                this.projects[projectIndex].description = newDescription;
            }
            
            // Update currentModalProject
            this.currentModalProject.name = newName;
            this.currentModalProject.description = newDescription;
            
            // Update modal title
            document.getElementById('projectModalTitle').textContent = `${newName} - Settings`;
            
            // Reload projects to reflect changes
            await this.loadProjects();
            this.populateAnalyticsProjectSelect();
        } else {
            throw new Error(data.error || 'Failed to update project');
        }
    } catch (error) {
        console.error('Error updating project:', error);
        this.showError(error.message || 'Failed to update project');
    } finally {
        this.hideProgress();
    }
}

export function showProjectAccessStatus(message, type = 'info') {
    const statusEl = document.getElementById('projectAccessStatus');
    if (!statusEl) return;
    statusEl.textContent = message || '';
    statusEl.className = `project-access-status ${type}`;
    statusEl.style.display = message ? 'block' : 'none';
}

export async function loadProjectAccessSection(project) {
    const section = document.getElementById('projectAccessSection');
    const inviteForm = document.getElementById('projectAccessInviteForm');
    const inviteName = document.getElementById('projectAccessInviteName');
    const inviteEmail = document.getElementById('projectAccessInviteEmail');
    const inviteBtn = document.getElementById('projectAccessInviteBtn');
    const membersList = document.getElementById('projectAccessMembersList');
    const invitationsList = document.getElementById('projectAccessInvitationsList');

    if (!section || !project?.id) return;

    this.showProjectAccessStatus('');
    if (membersList) {
        membersList.innerHTML = '<div class="project-access-empty"><i class="fas fa-spinner fa-spin"></i> Loading members...</div>';
    }
    if (invitationsList) {
        invitationsList.innerHTML = '<div class="project-access-empty"><i class="fas fa-spinner fa-spin"></i> Loading invitations...</div>';
    }

    try {
        const response = await fetch(
            `/api/project-access/projects/${PROJECT_ACCESS_MODULE}/${project.id}/members`,
            { credentials: 'same-origin' }
        );
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }

        const permissions = data.permissions || {};
        const canManage = permissions.can_manage_access === true;
        project.can_manage_access = canManage;
        if (typeof permissions.can_edit === 'boolean') {
            project.can_edit = permissions.can_edit;
        }

        if (inviteForm) {
            inviteForm.style.display = canManage ? '' : 'none';
        }
        if (inviteName) inviteName.disabled = !canManage;
        if (inviteEmail) inviteEmail.disabled = !canManage;
        if (inviteBtn) inviteBtn.disabled = !canManage;

        const members = Array.isArray(data.members) ? data.members : [];
        if (membersList) {
            if (!members.length) {
                membersList.innerHTML = '<div class="project-access-empty">No members yet.</div>';
            } else {
                membersList.innerHTML = members.map((member) => {
                    const roleBadge = member.is_owner
                        ? '<span class="project-access-badge owner"><i class="fas fa-crown"></i> Owner</span>'
                        : '<span class="project-access-badge">Viewer</span>';
                    const removeBtn = (!member.is_owner && canManage)
                        ? `<button type="button" class="btn-danger project-access-btn" onclick="manualAI.removeProjectMemberFromModal(${Number(member.user_id)})"><i class="fas fa-user-minus"></i> Remove</button>`
                        : '';

                    return `
                        <div class="project-access-item">
                            <div class="project-access-item-main">
                                <div><strong>${escapeHtml(member.name || member.email || 'Member')}</strong> ${roleBadge}</div>
                                <div class="project-access-meta">${escapeHtml(member.email || '')}</div>
                            </div>
                            ${removeBtn}
                        </div>
                    `;
                }).join('');
            }
        }

        const invitations = Array.isArray(data.invitations) ? data.invitations : [];
        if (invitationsList) {
            if (!canManage) {
                invitationsList.innerHTML = '<div class="project-access-empty">Only the project owner can manage invitations.</div>';
            } else if (!invitations.length) {
                invitationsList.innerHTML = '<div class="project-access-empty">No invitations yet.</div>';
            } else {
                invitationsList.innerHTML = invitations.map((invitation) => {
                    const status = escapeHtml(invitation.status || 'pending');
                    const canRevoke = invitation.status === 'pending';
                    const revokeBtn = canRevoke
                        ? `<button type="button" class="btn-danger project-access-btn" onclick="manualAI.revokeProjectInvitationFromModal(${Number(invitation.id)})"><i class="fas fa-ban"></i> Revoke</button>`
                        : '';

                    return `
                        <div class="project-access-item">
                            <div class="project-access-item-main">
                                <div><strong>${escapeHtml(invitation.invitee_name || invitation.invitee_email || 'Invitee')}</strong> <span class="project-access-badge">${status}</span></div>
                                <div class="project-access-meta">${escapeHtml(invitation.invitee_email || '')}</div>
                                <div class="project-access-meta">Expires: ${formatAccessDate(invitation.expires_at)}</div>
                            </div>
                            ${revokeBtn}
                        </div>
                    `;
                }).join('');
            }
        }
    } catch (error) {
        console.error('Error loading project access section:', error);
        if (membersList) {
            membersList.innerHTML = '<div class="project-access-empty">Could not load members.</div>';
        }
        if (invitationsList) {
            invitationsList.innerHTML = '<div class="project-access-empty">Could not load invitations.</div>';
        }
        this.showProjectAccessStatus(error.message || 'Could not load project access data', 'error');
    }
}

export async function sendProjectInvitationFromModal() {
    if (!this.currentModalProject?.id) {
        this.showError('No project selected');
        return;
    }
    if (this.currentModalProject.can_manage_access === false) {
        this.showError('Only the project owner can invite collaborators.');
        return;
    }

    const inviteName = document.getElementById('projectAccessInviteName');
    const inviteEmail = document.getElementById('projectAccessInviteEmail');
    const email = (inviteEmail?.value || '').trim().toLowerCase();
    const name = (inviteName?.value || '').trim();

    if (!email) {
        this.showProjectAccessStatus('Invitee email is required.', 'error');
        return;
    }
    const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    if (!emailPattern.test(email)) {
        this.showProjectAccessStatus('Please enter a valid email address.', 'error');
        return;
    }

    try {
        const response = await fetch(
            `/api/project-access/projects/${PROJECT_ACCESS_MODULE}/${this.currentModalProject.id}/invitations`,
            {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, name, role: 'viewer' })
            }
        );
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }

        if (inviteName) inviteName.value = '';
        if (inviteEmail) inviteEmail.value = '';

        const message = data.email_sent
            ? 'Invitation sent successfully.'
            : 'Invitation created, but email delivery failed. Check email settings and resend.';
        this.showProjectAccessStatus(message, data.email_sent ? 'success' : 'error');
        await this.loadProjectAccessSection(this.currentModalProject);
    } catch (error) {
        console.error('Error sending invitation from modal:', error);
        this.showProjectAccessStatus(error.message || 'Failed to send invitation.', 'error');
    }
}

export async function revokeProjectInvitationFromModal(invitationId) {
    try {
        const response = await fetch(`/api/project-access/invitations/${invitationId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        this.showProjectAccessStatus('Invitation revoked.', 'success');
        await this.loadProjectAccessSection(this.currentModalProject);
    } catch (error) {
        console.error('Error revoking invitation from modal:', error);
        this.showProjectAccessStatus(error.message || 'Failed to revoke invitation.', 'error');
    }
}

export async function removeProjectMemberFromModal(memberUserId) {
    if (!this.currentModalProject?.id) {
        this.showError('No project selected');
        return;
    }

    try {
        const response = await fetch(
            `/api/project-access/projects/${PROJECT_ACCESS_MODULE}/${this.currentModalProject.id}/members/${memberUserId}`,
            {
                method: 'DELETE',
                credentials: 'same-origin'
            }
        );
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        this.showProjectAccessStatus('Member removed.', 'success');
        await this.loadProjectAccessSection(this.currentModalProject);
    } catch (error) {
        console.error('Error removing member from modal:', error);
        this.showProjectAccessStatus(error.message || 'Failed to remove member.', 'error');
    }
}
