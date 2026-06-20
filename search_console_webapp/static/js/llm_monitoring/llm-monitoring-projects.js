/**
 * LLM Monitoring - métodos de prototipo: projects
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

getProjectEnabledLlms() {
        const configured = this.orderLlms(this.currentProject?.enabled_llms || []);
        if (configured.length > 0) return configured;
        return ['openai', 'anthropic', 'google', 'perplexity'];
    },

syncProjectLlmFilterOptions() {
        const enabledLlms = this.getProjectEnabledLlms();
        const configs = [
            {
                id: 'responsesLLMFilter',
                allLabel: 'All Active LLMs',
                formatLabel: (llm) => this.getLLMDisplayName(llm)
            },
            {
                id: 'urlsLLMFilter',
                allLabel: 'All Active LLMs (Combined)',
                formatLabel: (llm) => `${this.getLLMDisplayName(llm)} Only`
            }
        ];

        configs.forEach(({ id, allLabel, formatLabel }) => {
            const select = document.getElementById(id);
            if (!select) return;

            const previousValue = String(select.value || '').trim();
            select.innerHTML = '';

            const allOption = document.createElement('option');
            allOption.value = '';
            allOption.textContent = allLabel;
            select.appendChild(allOption);

            enabledLlms.forEach((llm) => {
                const option = document.createElement('option');
                option.value = llm;
                option.textContent = formatLabel(llm);
                select.appendChild(option);
            });

            select.value = previousValue && enabledLlms.includes(previousValue)
                ? previousValue
                : '';
        });
    },

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

            await this.handlePaywallResponse(response);

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

            // Refresh plan limits after projects load (count may have changed)
            if (this.planLimits) {
                this.planLimits.active_projects = data.projects.filter(p => p.is_active).length;
                this.updatePlanLimitsUI();
            }

        } catch (error) {
            console.error('❌ Error loading projects:', error);
            loading.style.display = 'none';
            this.showError('Failed to load projects. Please try again.');
        }
    },

renderProjectCard(project, container) {
        const card = document.createElement('div');
        card.className = 'project-card';
        const safeProjectName = JSON.stringify(project.name || '').replace(/"/g, '&quot;');
        const competitorCount = Array.isArray(project.selected_competitors)
            ? project.selected_competitors.length
            : (project.competitors?.length || 0);
        const configuredQueries = Number(project.total_queries || 0);
        const hasConfiguredPrompts = configuredQueries > 0;
        const canEdit = project.can_edit !== false;
        const shouldShowInitialAnalysisButton = !!project.is_active && !project.last_analysis_date;
        const isInitialAnalysisRunning = !!project.initial_analysis_in_progress;
        card.innerHTML = `
            <div class="project-card-header">
                <h3>${this.escapeHtml(project.name)}</h3>
                <div class="project-status ${project.is_active ? 'active' : 'inactive'}">
                    ${project.is_active ? 'Active' : 'Inactive'}
                </div>
                ${!canEdit ? '<span class="badge badge-language" style="margin-left: 8px;">Shared (view only)</span>' : ''}
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
                        <span>${competitorCount} Competitors</span>
                    </div>
                </div>
                ${project.last_analysis_date ? `
                    <div class="project-meta">
                        <small>
                            <i class="fas fa-clock"></i>
                            Last analysis: ${this.formatDate(project.last_analysis_date)}
                        </small>
                    </div>
                ` : `
                    <div class="project-meta">
                        <small>
                            <i class="fas fa-hourglass-half"></i>
                            No analysis yet
                        </small>
                    </div>
                `}
            </div>
            <div class="project-card-footer">
                <button class="btn btn-primary btn-sm" onclick="window.llmMonitoring.viewProject(${project.id})">
                    <i class="fas fa-eye"></i>
                    View Metrics
                </button>
                ${canEdit ? `
                    <button class="btn btn-primary btn-sm" onclick="window.llmMonitoring.openPromptsManagementForProject(${JSON.stringify(project).replace(/"/g, '&quot;')})">
                        <i class="fas fa-list"></i>
                        View/Edit Prompts
                    </button>
                    <button class="btn btn-ghost btn-sm" onclick="window.llmMonitoring.editProject(${project.id}, ${JSON.stringify(project).replace(/"/g, '&quot;')})">
                        <i class="fas fa-edit"></i>
                        Edit
                    </button>
                ` : ''}
                ${(canEdit && shouldShowInitialAnalysisButton) ? `
                    <button
                        class="btn btn-success btn-sm"
                        id="btnInitialAnalysis-${project.id}"
                        onclick="window.llmMonitoring.runInitialAnalysis(${project.id}, ${safeProjectName}, ${configuredQueries})"
                        ${(isInitialAnalysisRunning || !hasConfiguredPrompts) ? 'disabled' : ''}
                    >
                        <i class="fas ${isInitialAnalysisRunning ? 'fa-spinner fa-spin' : (hasConfiguredPrompts ? 'fa-play-circle' : 'fa-list')}"></i>
                        ${isInitialAnalysisRunning ? 'First analysis running...' : (hasConfiguredPrompts ? 'Run First Analysis' : 'Add Prompts First')}
                    </button>
                ` : ''}
                ${(canEdit && project.is_active) ? `
                    <button class="btn btn-ghost btn-sm btn-warning" onclick="window.llmMonitoring.deactivateProject(${project.id}, ${safeProjectName})">
                        <i class="fas fa-pause"></i>
                        Pause
                    </button>
                ` : ''}
                ${(canEdit && !project.is_active) ? `
                    <button class="btn btn-ghost btn-sm btn-success" onclick="window.llmMonitoring.activateProject(${project.id}, ${safeProjectName})">
                        <i class="fas fa-play"></i>
                        Resume
                    </button>
                    <button class="btn btn-ghost btn-sm btn-danger" onclick="window.llmMonitoring.deleteProject(${project.id}, ${safeProjectName}, true)">
                        <i class="fas fa-trash"></i>
                        Delete
                    </button>
                ` : ''}
            </div>
        `;

        container.appendChild(card);
    },

async editProject(projectId, fallbackProject = null) {
        if (!projectId) {
            this.showError('No project selected');
            return;
        }

        try {
            const metricType = this.getSelectedSovMetric();
            const response = await fetch(
                `${this.baseUrl}/projects/${projectId}?days=${this.globalTimeRange}&metric=${metricType}`,
                { credentials: 'same-origin' }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (!data?.success || !data?.project) {
                throw new Error('Could not load full project details');
            }

            this.showProjectModal(data.project);
        } catch (error) {
            console.error('❌ Error loading full project for edit:', error);
            if (fallbackProject) {
                this.showProjectModal(fallbackProject);
            } else {
                this.showError('Failed to load project details');
            }
        }
    },

async viewProject(projectId) {
        console.log(`📊 Loading metrics for project ${projectId}...`);

        // Always reset responses state when loading a project
        this.responsesLoaded = false;
        this.allResponses = [];
        this.filteredResponses = null;
        this.currentDisplayResponses = [];
        // Clear responses DOM immediately
        const respContainer = document.getElementById('responsesContainer');
        if (respContainer) respContainer.innerHTML = '';
        const respStatus = document.getElementById('responsesStatus');
        if (respStatus) respStatus.textContent = '';
        // Reset all response filters
        ['responsesQueryFilter', 'responsesLLMFilter', 'responsesMentionFilter', 'responsesSentimentFilter', 'responsesQueryTypeFilter'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });

        this.currentProject = { id: projectId };

        // Hide projects wrapper, show metrics
        const llmProjectsView = document.getElementById('llmProjectsView');
        const projectsTab = document.getElementById('projectsTab');
        const metricsSection = document.getElementById('metricsSection');
        const fab = document.getElementById('globalMetricFab');

        console.log('📦 Projects tab element:', projectsTab);
        console.log('📦 Metrics section element:', metricsSection);

        if (llmProjectsView) {
            llmProjectsView.style.display = 'none';
        }
        if (projectsTab) {
            projectsTab.style.display = 'none';
            projectsTab.classList.remove('active');
        }
        if (metricsSection) {
            metricsSection.style.display = 'block';
            metricsSection.classList.add('active');
        }
        // ✨ Show FAB when viewing a project
        if (fab) {
            fab.style.display = 'flex';
        }

        // ✨ Show download buttons in sidebar
        this.showDownloadButtons(true);

        try {
            // Load project details with time range
            const metricType = this.getSelectedSovMetric();
            const response = await fetch(
                `${this.baseUrl}/projects/${projectId}?days=${this.globalTimeRange}&metric=${metricType}`
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.currentProject = data.project;
            this.serverModelScopeNotice = data.model_scope_notice
                ? { ...data.model_scope_notice, project_id: projectId }
                : null;
            this.updateProjectEditControls();
            this.syncProjectLlmFilterOptions();
            this.updateModelScopeBanner();

            // ✨ NUEVO: Guardar datos adicionales para uso posterior
            this.currentTrends = data.trends || null;
            this.currentPositionMetrics = data.position_metrics || null;
            this.currentQualityScore = data.quality_score || null;

            // Update title
            document.getElementById('projectTitle').textContent = data.project.name;

            // Update KPIs (✨ NUEVO: pasar tendencias)
            this.updateKPIs(data.latest_metrics, data.trends);
            
            // ✨ NUEVO: Actualizar métricas de posición y quality score
            this.updatePositionMetrics(data.position_metrics);
            this.updateQualityScore(data.quality_score);

            // ✅ NUEVO: Cargar prompts del proyecto
            await this.loadPrompts(projectId);

            // ✨ NUEVO: Poblar dropdown de prompts en Responses Inspector
            await this.populateQueryFilter();

            // Load detailed metrics
            await this.loadMetrics(projectId);

            // Auto-load responses for the project
            this.loadResponses();

        } catch (error) {
            console.error('❌ Error loading project:', error);
            this.showError('Failed to load project details.');
            this.showProjectsList();
        }
    },

updateProjectEditControls() {
        const canEdit = this.currentProject?.can_edit !== false;
        const setVisible = (id, visible) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.style.display = visible ? '' : 'none';
        };

        setVisible('btnEditProject', canEdit);
        setVisible('btnDeleteProject', canEdit);
        setVisible('btnManagePrompts', canEdit);
    },

async refreshProjectKPIs() {
        const projectId = this.currentProject?.id;
        if (!projectId) return;
        
        try {
            const metricType = this.getSelectedSovMetric();
            const response = await fetch(
                `${this.baseUrl}/projects/${projectId}?days=${this.globalTimeRange}&metric=${metricType}`
            );
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.currentTrends = data.trends || null;
            this.updateKPIs(data.latest_metrics, data.trends);
        } catch (error) {
            console.error('❌ Error refreshing KPIs:', error);
        }
    },

showProjectsList() {
        const llmProjectsView = document.getElementById('llmProjectsView');
        const projectsTab = document.getElementById('projectsTab');
        const metricsSection = document.getElementById('metricsSection');
        const fab = document.getElementById('globalMetricFab');

        if (llmProjectsView) {
            llmProjectsView.style.display = '';
        }
        if (projectsTab) {
            projectsTab.style.display = 'block';
            projectsTab.classList.add('active');
        }
        if (metricsSection) {
            metricsSection.style.display = 'none';
            metricsSection.classList.remove('active');
        }
        // ✨ Hide FAB when viewing projects list
        if (fab) {
            fab.style.display = 'none';
        }
        
        // ✨ Hide download buttons in sidebar
        this.showDownloadButtons(false);

        this.responsesLoaded = false;
        this.allResponses = [];
        this.filteredResponses = null;
        this.currentDisplayResponses = [];
        
        this.currentProject = null;
        this.serverModelScopeNotice = null;
        this.updateModelScopeBanner();
    },

async deactivateProject(projectId, projectName) {
        // Method name kept for backward compatibility; user-facing copy uses
        // "Pause" / "Resume" to match Manual AI and AI Mode terminology.
        console.log(`⏸️ Pausing project ${projectId}...`);

        const confirmed = await this.showConfirmDialog({
            title: 'Pause Project?',
            message: `The project "${projectName}" will stop running in automatic analyses and will not consume any quota until you resume it. All data will be preserved.`,
            confirmText: 'Pause',
            cancelText: 'Keep Active',
            variant: 'warning'
        });
        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/deactivate`, {
                method: 'PUT',
                credentials: 'same-origin'
            });

            await this.handlePaywallResponse(response);

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            console.log(`✅ Project ${projectId} paused`);

            // If we're viewing this project, update current project state
            if (this.currentProject && this.currentProject.id === projectId) {
                this.currentProject.is_active = false;
            }

            // Reload projects list
            await this.loadProjects();

            this.showSuccess(`Project "${projectName}" paused. It will no longer run in automatic analyses.`);

        } catch (error) {
            console.error('❌ Error pausing project:', error);
            this.showError(error.message || 'Failed to pause project');
        }
    },

async activateProject(projectId, projectName) {
        // Method name kept for backward compatibility; user-facing copy uses
        // "Resume" to match Manual AI and AI Mode terminology.
        console.log(`▶️ Resuming project ${projectId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/activate`, {
                method: 'PUT',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            console.log(`✅ Project ${projectId} resumed`);

            // If we're viewing this project, update current project state
            if (this.currentProject && this.currentProject.id === projectId) {
                this.currentProject.is_active = true;
            }

            // Reload projects list
            await this.loadProjects();

            this.showSuccess(`Project "${projectName}" resumed. It will be included in upcoming automatic analyses.`);

        } catch (error) {
            console.error('❌ Error resuming project:', error);
            this.showError(error.message || 'Failed to resume project');
        }
    },

async deleteProject(projectId, projectName, isPermanent = false) {
        console.log(`🗑️ Deleting project ${projectId}... (permanent: ${isPermanent})`);

        const message = isPermanent
            ? `The project "${projectName}" and all its data (queries, results and snapshots) will be deleted permanently.\n\nThis action cannot be undone.`
            : `The project "${projectName}" will be deleted.\n\nThis action cannot be undone.`;
        const confirmed = await this.showConfirmDialog({
            title: isPermanent ? 'Delete Project Permanently?' : 'Delete Project?',
            message,
            confirmText: isPermanent ? 'Delete Permanently' : 'Delete',
            cancelText: 'Cancel',
            variant: 'danger'
        });
        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}`, {
                method: 'DELETE',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const error = await response.json();
                if (error.action_required === 'deactivate_first') {
                    this.showError('Please pause the project first before deleting it.');
                    return;
                }
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            const result = await response.json();
            console.log(`✅ Project ${projectId} deleted permanently:`, result.stats);

            // If we're viewing this project, go back to projects list
            if (this.currentProject && this.currentProject.id === projectId) {
                this.showProjectsList();
            }

            // Reload projects list
            await this.loadProjects();

            this.showSuccess(`Project "${projectName}" permanently deleted.`);

        } catch (error) {
            console.error('❌ Error deleting project:', error);
            this.showError(error.message || 'Failed to delete project');
        }
    },

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
            this.modalOriginalEnabledLlms = this.normalizeLlmSelection(project.enabled_llms || []);

            // Fill form
            document.getElementById('projectName').value = project.name || '';
            document.getElementById('industry').value = project.industry || '';
            document.getElementById('language').value = project.language || 'es';
            document.getElementById('countryCode').value = project.country_code || 'ES';

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

            this.toggleProjectAccessSection(true);
            this.loadProjectAccessSection(project);
        } else {
            // Create mode
            title.textContent = 'Create New LLM Monitoring Project';
            if (modalDesc) modalDesc.textContent = 'Set up a new project to track brand visibility in LLMs';
            btnText.textContent = 'Create Project';
            this.modalOriginalEnabledLlms = null;

            // Reset form
            document.getElementById('projectForm').reset();

            // Check all LLMs by default
            const llmCheckboxes = document.querySelectorAll('input[name="llm"]');
            llmCheckboxes.forEach(cb => cb.checked = true);

            this.toggleProjectAccessSection(false);
            this.clearProjectAccessSection();
        }

        this.updateLlmSelectionImpactNotice();

        console.log('👁️ Setting modal display to flex...');
        modal.style.display = 'flex';
        console.log('✅ Modal display set:', modal.style.display);
        console.log('✅ Modal should now be visible');

        // Add a slight delay to ensure styles are applied
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
    },

hideProjectModal() {
        const modal = document.getElementById('projectModal');
        modal.classList.remove('active');
        this.modalOriginalEnabledLlms = null;
        this.updateLlmSelectionImpactNotice();
        this.showProjectAccessStatus('');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300); // Match transition duration
    },

toggleProjectAccessSection(show) {
        const section = document.getElementById('llmProjectAccessSection');
        if (!section) return;
        section.style.display = show ? '' : 'none';
    },

clearProjectAccessSection() {
        const members = document.getElementById('llmProjectAccessMembers');
        const invitations = document.getElementById('llmProjectAccessInvitations');
        const inviteName = document.getElementById('llmProjectInviteName');
        const inviteEmail = document.getElementById('llmProjectInviteEmail');
        if (members) members.innerHTML = '';
        if (invitations) invitations.innerHTML = '';
        if (inviteName) inviteName.value = '';
        if (inviteEmail) inviteEmail.value = '';
    },

showProjectAccessStatus(message, type = 'info') {
        const statusEl = document.getElementById('llmProjectAccessStatus');
        if (!statusEl) return;
        statusEl.textContent = message || '';
        statusEl.className = `llm-project-access-status ${type}`;
        statusEl.style.display = message ? 'block' : 'none';
    },

async loadProjectAccessSection(project) {
        const section = document.getElementById('llmProjectAccessSection');
        const inviteForm = document.getElementById('llmProjectAccessInviteForm');
        const inviteName = document.getElementById('llmProjectInviteName');
        const inviteEmail = document.getElementById('llmProjectInviteEmail');
        const inviteBtn = document.getElementById('llmProjectInviteBtn');
        const membersList = document.getElementById('llmProjectAccessMembers');
        const invitationsList = document.getElementById('llmProjectAccessInvitations');

        if (!section || !project?.id) return;

        this.showProjectAccessStatus('');
        if (membersList) {
            membersList.innerHTML = '<div class="llm-project-access-empty"><i class="fas fa-spinner fa-spin"></i> Loading members...</div>';
        }
        if (invitationsList) {
            invitationsList.innerHTML = '<div class="llm-project-access-empty"><i class="fas fa-spinner fa-spin"></i> Loading invitations...</div>';
        }

        try {
            const response = await fetch(`/api/project-access/projects/llm_monitoring/${project.id}/members`, {
                credentials: 'same-origin'
            });
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
                    membersList.innerHTML = '<div class="llm-project-access-empty">No members yet.</div>';
                } else {
                    membersList.innerHTML = members.map((member) => {
                        const roleBadge = member.is_owner
                            ? '<span class="llm-project-access-badge owner"><i class="fas fa-crown"></i> Owner</span>'
                            : '<span class="llm-project-access-badge">Viewer</span>';
                        const removeBtn = (!member.is_owner && canManage)
                            ? `<button type="button" class="btn btn-ghost btn-sm btn-danger" onclick="window.llmMonitoring.removeProjectMemberFromModal(${Number(member.user_id)})"><i class="fas fa-user-minus"></i> Remove</button>`
                            : '';

                        return `
                            <div class="llm-project-access-item">
                                <div class="llm-project-access-main">
                                    <div><strong>${this.escapeHtml(member.name || member.email || 'Member')}</strong> ${roleBadge}</div>
                                    <div class="llm-project-access-meta">${this.escapeHtml(member.email || '')}</div>
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
                    invitationsList.innerHTML = '<div class="llm-project-access-empty">Only the project owner can manage invitations.</div>';
                } else if (!invitations.length) {
                    invitationsList.innerHTML = '<div class="llm-project-access-empty">No invitations yet.</div>';
                } else {
                    invitationsList.innerHTML = invitations.map((invitation) => {
                        const rawStatus = String(invitation.status || 'pending').toLowerCase();
                        const normalizedStatus = ['pending', 'accepted', 'expired'].includes(rawStatus) ? rawStatus : 'default';
                        const statusText = this.escapeHtml(rawStatus.replace(/_/g, ' '));
                        const expires = invitation.expires_at ? new Date(invitation.expires_at).toLocaleString() : '-';
                        const revokeBtn = rawStatus === 'pending'
                            ? `<button type="button" class="btn btn-ghost btn-sm btn-danger" onclick="window.llmMonitoring.revokeProjectInvitationFromModal(${Number(invitation.id)})"><i class="fas fa-ban"></i> Revoke</button>`
                            : '';

                        return `
                            <div class="llm-project-access-item">
                                <div class="llm-project-access-main">
                                    <div><strong>${this.escapeHtml(invitation.invitee_name || invitation.invitee_email || 'Invitee')}</strong> <span class="llm-project-access-badge status-${normalizedStatus}">${statusText}</span></div>
                                    <div class="llm-project-access-meta">${this.escapeHtml(invitation.invitee_email || '')}</div>
                                    <div class="llm-project-access-meta">Expires: ${expires}</div>
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
                membersList.innerHTML = '<div class="llm-project-access-empty">Could not load members.</div>';
            }
            if (invitationsList) {
                invitationsList.innerHTML = '<div class="llm-project-access-empty">Could not load invitations.</div>';
            }
            this.showProjectAccessStatus(error.message || 'Could not load project access data', 'error');
        }
    },

async sendProjectInvitationFromModal() {
        if (!this.currentProject?.id) {
            this.showError('No project selected');
            return;
        }
        if (this.currentProject.can_manage_access === false) {
            this.showError('Only the project owner can invite collaborators.');
            return;
        }

        const inviteName = document.getElementById('llmProjectInviteName');
        const inviteEmail = document.getElementById('llmProjectInviteEmail');
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
            const response = await fetch(`/api/project-access/projects/llm_monitoring/${this.currentProject.id}/invitations`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, name, role: 'viewer' })
            });
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
            await this.loadProjectAccessSection(this.currentProject);
        } catch (error) {
            console.error('Error sending invitation from modal:', error);
            this.showProjectAccessStatus(error.message || 'Failed to send invitation.', 'error');
        }
    },

async revokeProjectInvitationFromModal(invitationId) {
        try {
            const response = await fetch(`/api/project-access/invitations/${invitationId}`, {
                method: 'DELETE',
                credentials: 'same-origin'
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            this.showProjectAccessStatus('Invitation removed.', 'success');
            await this.loadProjectAccessSection(this.currentProject);
        } catch (error) {
            console.error('Error revoking invitation from modal:', error);
            this.showProjectAccessStatus(error.message || 'Failed to revoke invitation.', 'error');
        }
    },

async removeProjectMemberFromModal(memberUserId) {
        if (!this.currentProject?.id) {
            this.showError('No project selected');
            return;
        }

        try {
            const response = await fetch(
                `/api/project-access/projects/llm_monitoring/${this.currentProject.id}/members/${memberUserId}`,
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
            await this.loadProjectAccessSection(this.currentProject);
        } catch (error) {
            console.error('Error removing member from modal:', error);
            this.showProjectAccessStatus(error.message || 'Failed to remove member.', 'error');
        }
    },

async saveProject() {
        console.log('💾 Saving project...');

        // Get form data
        const name = document.getElementById('projectName').value.trim();
        const industry = document.getElementById('industry').value.trim();
        const brandDomain = document.getElementById('brandDomain').value.trim();
        const language = document.getElementById('language').value;
        const countryCode = document.getElementById('countryCode').value;

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
            enabled_llms: enabledLlms
        };

        // Show loading
        const btnSave = document.getElementById('btnSaveProject');
        const btnText = document.getElementById('btnSaveText');
        const originalText = btnText.textContent;

        const isEdit = this.currentProject && this.currentProject.id;
        const editingProjectId = isEdit ? this.currentProject.id : null;
        const isMetricsViewActive = !!document.getElementById('metricsSection')?.classList.contains('active');
        const llmSelectionChange = isEdit
            ? this.getLlmSelectionChanges(this.modalOriginalEnabledLlms || this.currentProject.enabled_llms || [], enabledLlms)
            : { changed: false, added: [], removed: [], current: enabledLlms, previous: [] };

        if (isEdit && llmSelectionChange.changed) {
            const lines = [];
            if (llmSelectionChange.added.length > 0) {
                lines.push(`Added: ${this.formatLlmNames(llmSelectionChange.added).join(', ')}`);
            }
            if (llmSelectionChange.removed.length > 0) {
                lines.push(`Removed: ${this.formatLlmNames(llmSelectionChange.removed).join(', ')}`);
            }

            const confirmed = await this.showConfirmDialog({
                title: 'Apply LLM model changes?',
                message: `This will affect charts and exports for the selected date range.\n\n${lines.join('\n')}`,
                confirmText: 'Save Changes',
                cancelText: 'Review Again',
                variant: 'warning'
            });
            if (!confirmed) {
                return;
            }
        }

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

            if (response.status === 402) {
                const errorData = await response.json().catch(() => ({}));
                if (errorData.error === 'project_limit_reached') {
                    const current = errorData.current || '?';
                    const limit = errorData.limit || '?';
                    this.showError(`Project limit reached: you have ${current}/${limit} projects on your current plan. Upgrade to create more.`);
                } else {
                    this.showError(errorData.message || 'LLM Monitoring requires a paid plan.');
                }
                if (window.showPaywall) {
                    window.showPaywall('LLM Monitoring', errorData.upgrade_options || ['premium', 'business', 'enterprise']);
                }
                return;
            }

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

            if (isEdit && editingProjectId) {
                const serverChanged = Boolean(data?.model_selection_changed);
                const serverChanges = data?.llm_changes || null;

                if (serverChanged && serverChanges) {
                    this.pendingModelScopeNotice = {
                        project_id: editingProjectId,
                        previous_enabled_llms: serverChanges.previous_enabled_llms || llmSelectionChange.previous,
                        current_enabled_llms: serverChanges.current_enabled_llms || llmSelectionChange.current,
                        added_llms: serverChanges.added_llms || llmSelectionChange.added,
                        removed_llms: serverChanges.removed_llms || llmSelectionChange.removed
                    };
                } else if (llmSelectionChange.changed) {
                    // Fallback defensive: keep UX notice even if backend response omits flags.
                    this.pendingModelScopeNotice = {
                        project_id: editingProjectId,
                        previous_enabled_llms: llmSelectionChange.previous,
                        current_enabled_llms: llmSelectionChange.current,
                        added_llms: llmSelectionChange.added,
                        removed_llms: llmSelectionChange.removed
                    };
                }
            }

            // Hide modal
            this.hideProjectModal();

            // Reload projects
            await this.loadProjects();

            // Refresh current metrics view if user edited from inside the project page.
            if (isEdit && isMetricsViewActive && editingProjectId) {
                await this.viewProject(editingProjectId);
            }

            // Show success message
            this.showSuccess(`Project ${isEdit ? 'updated' : 'created'} successfully!`);
            if (!isEdit) {
                this.showInfo('You can now click "Run First Analysis" on the new project card.');
            }

        } catch (error) {
            console.error('❌ Error saving project:', error);
            this.showError(error.message || 'Failed to save project');
        } finally {
            console.log('🔄 Re-enabling button...');
            btnText.textContent = originalText;
            btnSave.disabled = false;
            btnSave.classList.remove('loading');
        }
    },

async refreshProjectsListIfVisible() {
        const projectsTab = document.getElementById('projectsTab');
        if (!projectsTab) {
            return;
        }

        const isVisible = window.getComputedStyle(projectsTab).display !== 'none';
        if (!isVisible) {
            return;
        }

        await this.loadProjects();
    },

getProjectLanguageCode() {
        return (this.currentProject?.language || 'en').toLowerCase();
    }

});
