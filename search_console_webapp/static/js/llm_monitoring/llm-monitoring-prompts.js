/**
 * LLM Monitoring - métodos de prototipo: prompts
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

updatePromptsLimitUI() {
        const limits = this.planLimits;
        const badge = document.getElementById('promptsLimitBadge');
        if (!badge || !limits) return;

        const maxPrompts = limits.max_prompts_per_project;
        if (maxPrompts === null) {
            badge.style.display = 'none';
            return;
        }

        const currentCount = this.allPrompts ? this.allPrompts.length : 0;
        badge.textContent = `${currentCount} / ${maxPrompts}`;
        badge.style.display = 'inline-flex';
        badge.classList.remove('limit-warning', 'limit-reached');
        if (currentCount >= maxPrompts) {
            badge.classList.add('limit-reached');
        } else if (currentCount >= maxPrompts * 0.8) {
            badge.classList.add('limit-warning');
        }

        // Also update Add Prompts button in modal
        const btnAddModal = document.getElementById('btnAddPromptsModal');
        if (btnAddModal) {
            if (currentCount >= maxPrompts) {
                btnAddModal.classList.add('btn-limit-reached');
                btnAddModal.setAttribute('title', `Prompt limit reached (${currentCount}/${maxPrompts}). Upgrade to add more.`);
            } else {
                btnAddModal.classList.remove('btn-limit-reached');
                const remaining = maxPrompts - currentCount;
                btnAddModal.setAttribute('title', `${remaining} prompt${remaining !== 1 ? 's' : ''} remaining`);
            }
        }
    },

async loadPrompts(projectId, renderInModal = false) {
        console.log(`📝 Loading prompts for project ${projectId}...`, renderInModal ? '(in modal)' : '');

        const container = document.getElementById(renderInModal ? 'promptsListModal' : 'promptsList');
        const counter = document.getElementById(renderInModal ? 'promptsCountModal' : 'promptsCount');

        if (!container) return;

        // Show loading
        container.innerHTML = `
            <div class="loading-container" style="padding: 20px;">
                <i class="fas fa-spinner fa-spin"></i>
                <span>Loading prompts...</span>
            </div>
        `;

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/queries`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Loaded ${data.queries.length} prompts`);

            // Store all prompts
            this.allPrompts = data.queries;
            this.currentPromptsPage = 1;

            // Update counter
            if (counter) {
                counter.textContent = data.queries.length;
            }

            // Render prompts list with pagination
            this.renderPrompts(renderInModal);

            // Update prompts limit UI (badge in management modal)
            this.updatePromptsLimitUI();

        } catch (error) {
            console.error('❌ Error loading prompts:', error);
            container.innerHTML = `
                <div class="error-state" style="padding: 20px; text-align: center;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Error loading prompts</p>
                </div>
            `;
        }
    },

async refreshPromptViews() {
        if (!this.currentProject || !this.currentProject.id) {
            return;
        }

        const projectId = this.currentProject.id;
        if (this.isRenderingInModal) {
            await this.loadPrompts(projectId, true);
            await this.loadPrompts(projectId, false);
            return;
        }

        await this.loadPrompts(projectId, false);
    },

renderPrompts(renderInModal = false) {
        const container = document.getElementById(renderInModal ? 'promptsListModal' : 'promptsList');
        const paginationDiv = document.getElementById(renderInModal ? 'promptsPaginationModal' : 'promptsPagination');

        if (!container) return;

        // ✨ NEW: Apply cluster filter (if active and we're in the modal)
        const clusterFilter = (renderInModal
            ? document.getElementById('promptsListClusterFilter')?.value
            : '') || '';
        const source = Array.isArray(this.allPrompts) ? this.allPrompts : [];
        let promptsView = source;
        if (clusterFilter === '__unassigned__') {
            promptsView = source.filter(p => !p.topic_cluster);
        } else if (clusterFilter) {
            promptsView = source.filter(p => (p.topic_cluster || '') === clusterFilter);
        }

        // Handle empty state
        if (promptsView.length === 0) {
            // If filter is active but source has prompts, show a different message
            if (clusterFilter && source.length > 0) {
                container.innerHTML = `
                    <div class="empty-state" style="padding: 40px 20px;">
                        <div class="empty-icon">
                            <i class="fas fa-filter"></i>
                        </div>
                        <h4>No prompts in this cluster</h4>
                        <p>Change the filter or assign prompts to this cluster.</p>
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="empty-state" style="padding: 40px 20px;">
                        <div class="empty-icon">
                            <i class="fas fa-comments"></i>
                        </div>
                        <h4>No prompts yet</h4>
                        <p>Add prompts to start analyzing brand visibility in LLMs</p>
                        <button class="btn btn-primary mt-2 btn-first-prompt" onclick="window.llmMonitoring.showPromptsModal()">
                            <i class="fas fa-plus"></i>
                            Add Your First Prompt
                        </button>
                    </div>
                `;
            }
            if (paginationDiv) paginationDiv.style.display = 'none';
            return;
        }

        // Calculate pagination (over filtered view)
        const totalPages = Math.ceil(promptsView.length / this.promptsPerPage);
        if (this.currentPromptsPage > totalPages) {
            this.currentPromptsPage = 1;
        }
        const startIndex = (this.currentPromptsPage - 1) * this.promptsPerPage;
        const endIndex = Math.min(startIndex + this.promptsPerPage, promptsView.length);
        const pagePrompts = promptsView.slice(startIndex, endIndex);

        // Render prompts for current page
        let html = '<div class="prompts-list-container">';

        pagePrompts.forEach(query => {
            const clusterSelectHtml = this.buildPromptClusterSelectHtml
                ? this.buildPromptClusterSelectHtml(query)
                : '';
            const hasCluster = !!clusterSelectHtml;
            html += `
                <div class="prompt-item">
                    <div class="prompt-meta">
                        <span class="badge badge-${query.query_type}">${query.query_type}</span>
                        <span class="badge badge-language">${query.language}</span>
                        <span class="prompt-date">
                            <i class="fas fa-clock"></i>
                            ${this.formatDate(query.created_at)}
                        </span>
                    </div>
                    <div class="prompt-text">${this.escapeHtml(query.prompt)}</div>
                    <div class="prompt-bottom-row">
                        <div>${clusterSelectHtml}</div>
                        <div class="prompt-actions">
                            <button class="btn btn-icon btn-sm" onclick="window.llmMonitoring.deletePrompt(${query.id})" title="Delete prompt">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

        // Update pagination controls
        if (promptsView.length > this.promptsPerPage) {
            if (paginationDiv) {
                paginationDiv.style.display = 'flex';

                // Update pagination info
                const paginationInfoId = renderInModal ? 'paginationInfoModal' : 'paginationInfo';
                const currentPageId = renderInModal ? 'currentPageModal' : 'currentPage';
                const totalPagesId = renderInModal ? 'totalPagesModal' : 'totalPages';
                const btnPrevId = renderInModal ? 'btnPrevPageModal' : 'btnPrevPage';
                const btnNextId = renderInModal ? 'btnNextPageModal' : 'btnNextPage';

                const paginationInfo = document.getElementById(paginationInfoId);
                if (paginationInfo) {
                    paginationInfo.textContent = `Showing ${startIndex + 1}-${endIndex} of ${promptsView.length} prompts`;
                }

                // Update page numbers
                const currentPageEl = document.getElementById(currentPageId);
                const totalPagesEl = document.getElementById(totalPagesId);
                if (currentPageEl) currentPageEl.textContent = this.currentPromptsPage;
                if (totalPagesEl) totalPagesEl.textContent = totalPages;

                // Update button states
                const btnPrev = document.getElementById(btnPrevId);
                const btnNext = document.getElementById(btnNextId);
                if (btnPrev) btnPrev.disabled = this.currentPromptsPage === 1;
                if (btnNext) btnNext.disabled = this.currentPromptsPage === totalPages;
            }
        } else {
            if (paginationDiv) paginationDiv.style.display = 'none';
        }
    },

togglePromptsSection() {
        const content = document.getElementById('promptsContent');
        const icon = document.getElementById('promptsToggleIcon');
        const card = document.getElementById('promptsCard');

        if (!content || !icon || !card) return;

        this.promptsSectionCollapsed = !this.promptsSectionCollapsed;

        if (this.promptsSectionCollapsed) {
            content.style.display = 'none';
            icon.className = 'fas fa-chevron-right';
            card.classList.add('collapsed');
        } else {
            content.style.display = 'block';
            icon.className = 'fas fa-chevron-down';
            card.classList.remove('collapsed');
        }
    },

showPromptsModal() {
        console.log('🎬 Showing prompts modal...');

        // Pre-check: block if prompt limit already reached
        const limits = this.planLimits;
        const maxPrompts = limits ? limits.max_prompts_per_project : null;
        const currentCount = this.allPrompts ? this.allPrompts.length : 0;
        if (maxPrompts !== null && currentCount >= maxPrompts) {
            if (window.showPaywall) {
                window.showPaywall('LLM Monitoring', ['premium', 'business', 'enterprise']);
            }
            this.showError(`You've reached the prompt limit for your plan (${currentCount}/${maxPrompts}). Upgrade to add more prompts.`);
            return;
        }

        const modal = document.getElementById('promptsModal');
        if (!modal) return;

        // Reset form
        document.getElementById('promptsForm').reset();

        // Reset counter
        this.updatePromptsCounter();

        // Show remaining prompts hint
        this.updatePromptsRemainingHint();

        // Add input listener for real-time updates
        const textarea = document.getElementById('promptsInput');
        if (textarea) {
            // Remove previous listener if any
            textarea.removeEventListener('input', this._promptsInputHandler);
            // Create and store handler
            this._promptsInputHandler = () => this.updatePromptsCounter();
            textarea.addEventListener('input', this._promptsInputHandler);
        }

        // Show modal
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('active');
            // Focus textarea
            textarea?.focus();
        }, 10);
        
        // Load quick suggestions
        this.loadQuickSuggestions();
    },

hidePromptsModal() {
        const modal = document.getElementById('promptsModal');
        if (!modal) return;

        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    },

clearPromptsInput() {
        const textarea = document.getElementById('promptsInput');
        if (textarea) {
            textarea.value = '';
            textarea.focus();
            this.updatePromptsCounter();
        }
    },

updatePromptsCounter() {
        const textarea = document.getElementById('promptsInput');
        const counterNumber = document.getElementById('promptsCountNumber');
        const submitBtn = document.getElementById('btnSavePrompts');
        const submitText = document.getElementById('btnSavePromptsText');

        if (!textarea) return;

        const text = textarea.value.trim();
        const prompts = text ? text.split('\n').map(line => line.trim()).filter(line => line.length > 0) : [];
        const promptCount = prompts.length;
        const hasShortPrompts = prompts.some(line => line.length > 0 && line.length < 10);

        // Check against plan limits
        const limits = this.planLimits;
        const maxPrompts = limits ? limits.max_prompts_per_project : null;
        const existingCount = this.allPrompts ? this.allPrompts.length : 0;
        const wouldExceed = maxPrompts !== null && (existingCount + promptCount) > maxPrompts;
        const remaining = maxPrompts !== null ? Math.max(0, maxPrompts - existingCount) : null;

        // Update counter
        if (counterNumber) {
            counterNumber.textContent = promptCount;
            counterNumber.classList.toggle('counter-over-limit', wouldExceed);
        }

        // Enable/disable submit button
        if (submitBtn) {
            submitBtn.disabled = promptCount === 0 || wouldExceed;
        }

        // Update button text
        if (submitText) {
            if (wouldExceed) {
                submitText.textContent = `Limit exceeded (max ${remaining} more)`;
            } else if (promptCount > 0) {
                submitText.textContent = `Add ${promptCount} Prompt${promptCount !== 1 ? 's' : ''}`;
            } else {
                submitText.textContent = 'Add Prompts';
            }
        }

        // Update limit warning inside modal
        const limitWarning = document.getElementById('promptsLimitWarning');
        if (limitWarning) {
            if (wouldExceed) {
                limitWarning.innerHTML = `<i class="fas fa-exclamation-triangle"></i> You can only add ${remaining} more prompt${remaining !== 1 ? 's' : ''} on your current plan.`;
                limitWarning.style.display = 'flex';
                limitWarning.className = 'prompts-limit-warning limit-exceeded';
            } else if (remaining !== null && remaining <= 5 && promptCount > 0) {
                limitWarning.innerHTML = `<i class="fas fa-info-circle"></i> ${remaining - promptCount} prompt${(remaining - promptCount) !== 1 ? 's' : ''} remaining after adding these.`;
                limitWarning.style.display = 'flex';
                limitWarning.className = 'prompts-limit-warning limit-approaching';
            } else {
                limitWarning.style.display = 'none';
            }
        }

        const lengthWarning = document.getElementById('promptLengthWarning');
        if (lengthWarning) {
            lengthWarning.style.display = hasShortPrompts ? 'block' : 'none';
        }
    },

updatePromptsRemainingHint() {
        const hint = document.getElementById('promptsRemainingHint');
        if (!hint) return;

        const limits = this.planLimits;
        const maxPrompts = limits ? limits.max_prompts_per_project : null;
        if (maxPrompts === null) {
            hint.style.display = 'none';
            return;
        }

        const existingCount = this.allPrompts ? this.allPrompts.length : 0;
        const remaining = Math.max(0, maxPrompts - existingCount);
        hint.innerHTML = `<i class="fas fa-layer-group"></i> <strong>${remaining}</strong> of ${maxPrompts} prompts available`;
        hint.style.display = 'flex';
        hint.classList.toggle('hint-low', remaining <= 5 && remaining > 0);
        hint.classList.toggle('hint-zero', remaining === 0);
    },

showPromptsManagementModal() {
        console.log('🎬 Showing prompts management modal...');

        const modal = document.getElementById('promptsManagementModal');
        if (!modal) return;

        // Set flag for pagination
        this.isRenderingInModal = true;

        // Ensure we start on the Prompts tab each time the modal opens
        if (typeof this.switchPromptsTab === 'function') {
            this.switchPromptsTab('prompts', { silent: true });
        }

        // Load prompts AND clusters config in parallel
        if (this.currentProject && this.currentProject.id) {
            this.loadPrompts(this.currentProject.id, true); // true = render in modal
            // Clusters are needed by per-prompt selector → load config first,
            // then refresh the prompt list so selects include the cluster options.
            this.loadClustersConfig(this.currentProject.id)
                .then(() => {
                    // Update selects inline once clusters are known
                    this.refreshPromptClusterSelects();
                    this.renderClustersManagerList();
                    this.populatePromptsListClusterFilter();
                    this.updatePromptsMgmtTabCounts();
                })
                .catch(err => console.warn('Error loading clusters config:', err));

            // Hook the per-modal cluster filter change once
            const filterSel = document.getElementById('promptsListClusterFilter');
            if (filterSel && !filterSel.dataset.bound) {
                filterSel.dataset.bound = '1';
                filterSel.addEventListener('change', () => {
                    this.currentPromptsPage = 1;
                    this.renderPrompts(true);
                });
            }

            // Hook the enable/disable switch once
            const enableCb = document.getElementById('promptClustersEnabled');
            if (enableCb && !enableCb.dataset.bound) {
                enableCb.dataset.bound = '1';
                enableCb.addEventListener('change', () => {
                    this.toggleClustersConfigContainer(enableCb.checked);
                });
            }
        }

        // Show modal
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);
    },

openPromptsManagementForProject(project) {
        if (!project || !project.id) {
            this.showError('No project selected');
            return;
        }

        this.currentProject = project;
        this.showPromptsManagementModal();
    },

hidePromptsManagementModal() {
        const modal = document.getElementById('promptsManagementModal');
        if (!modal) return;

        // Reset flag for pagination
        this.isRenderingInModal = false;

        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    },

async savePrompts() {
        console.log('💾 Saving prompts...');

        if (!this.currentProject || !this.currentProject.id) {
            this.showError('No project selected');
            return;
        }

        // Get form data
        const promptsText = document.getElementById('promptsInput').value.trim();
        const language = document.getElementById('promptLanguage').value || null;
        const queryType = document.getElementById('promptType').value || 'manual';

        if (!promptsText) {
            this.showError('Please enter at least one prompt');
            return;
        }

        // Parse prompts (one per line)
        const queries = promptsText
            .split('\n')
            .map(q => q.trim())
            .filter(q => q.length > 0);

        if (queries.length === 0) {
            this.showError('All prompts must be at least 10 characters long');
            return;
        }

        // Prepare payload
        const payload = {
            queries: queries
        };

        if (language) {
            payload.language = language;
        }

        if (queryType) {
            payload.query_type = queryType;
        }

        // Show loading
        const btnSave = document.getElementById('btnSavePrompts');
        const btnText = document.getElementById('btnSavePromptsText');
        const originalText = btnText.textContent;

        btnText.textContent = 'Adding...';
        btnSave.disabled = true;

        try {
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            if (response.status === 402) {
                const errorData = await response.json().catch(() => ({}));
                // Detailed limit error for prompts
                if (errorData.error === 'prompt_limit_exceeded') {
                    const current = errorData.current || '?';
                    const limit = errorData.limit || '?';
                    const requested = errorData.requested || '?';
                    this.showError(`Prompt limit reached: you have ${current}/${limit} prompts and tried to add ${requested}. Upgrade your plan to add more.`);
                    if (window.showPaywall) {
                        window.showPaywall('LLM Monitoring', errorData.upgrade_options || ['premium', 'business', 'enterprise']);
                    }
                    return;
                }
                // Generic paywall
                if (window.showPaywall) {
                    window.showPaywall('LLM Monitoring', errorData.upgrade_options || ['basic', 'premium', 'business']);
                }
                throw new Error(errorData.message || 'LLM Monitoring requires a paid plan.');
            }

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Added ${data.added_count} prompts`);

            if (data.added_count === 0) {
                let message = 'No prompts were added.';
                if (data.duplicate_count > 0 && data.error_count === 0) {
                    message = 'All prompts already exist in this project.';
                } else if (data.error_count > 0 && data.duplicate_count === 0) {
                    message = 'All prompts are invalid. Make sure each prompt is not empty.';
                } else if (data.error_count > 0 && data.duplicate_count > 0) {
                    message = `No prompts added (${data.duplicate_count} duplicates, ${data.error_count} invalid).`;
                }
                this.showError(message);
                return;
            }

            // Hide modal
            this.hidePromptsModal();

            // Reload prompts
            await this.refreshPromptViews();

            // ✨ NUEVO: Actualizar dropdown de prompts en Responses Inspector
            await this.populateQueryFilter();

            // Refresh project cards so "Run First Analysis" CTA updates immediately
            await this.refreshProjectsListIfVisible();

            // Show success message
            let message = `${data.added_count} prompts added successfully!`;
            if (data.duplicate_count > 0) {
                message += ` (${data.duplicate_count} duplicates skipped)`;
            }
            if (data.error_count > 0) {
                message += ` (${data.error_count} errors)`;
            }
            this.showSuccess(message);

        } catch (error) {
            console.error('❌ Error saving prompts:', error);
            this.showError(error.message || 'Failed to save prompts');
        } finally {
            btnText.textContent = originalText;
            btnSave.disabled = false;
        }
    },

async deletePrompt(queryId) {
        if (!this.currentProject || !this.currentProject.id) {
            return;
        }

        const confirmed = await this.showConfirmDialog({
            title: 'Delete Prompt?',
            message: 'This prompt will be removed from the project.',
            confirmText: 'Delete Prompt',
            cancelText: 'Cancel',
            variant: 'danger'
        });
        if (!confirmed) {
            return;
        }

        console.log(`🗑️ Deleting prompt ${queryId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries/${queryId}`, {
                method: 'DELETE',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            console.log(`✅ Prompt ${queryId} deleted`);

            // Reload prompts
            await this.refreshPromptViews();

            // ✨ NUEVO: Actualizar dropdown de prompts en Responses Inspector
            await this.populateQueryFilter();

            // Refresh project cards so CTA state stays in sync
            await this.refreshProjectsListIfVisible();

            this.showSuccess('Prompt deleted successfully');

        } catch (error) {
            console.error('❌ Error deleting prompt:', error);
            this.showError(error.message || 'Failed to delete prompt');
        }
    },

scrollToPrompts() {
        const promptsCard = document.getElementById('promptsCard');
        if (promptsCard) {
            promptsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    },

switchPromptsTab(tab, opts = {}) {
        const valid = (tab === 'clusters') ? 'clusters' : 'prompts';
        const tabPrompts = document.getElementById('promptsMgmtTabPrompts');
        const tabClusters = document.getElementById('promptsMgmtTabClusters');
        const panePrompts = document.getElementById('promptsMgmtPanePrompts');
        const paneClusters = document.getElementById('promptsMgmtPaneClusters');
        if (!tabPrompts || !tabClusters || !panePrompts || !paneClusters) return;

        const isClusters = valid === 'clusters';
        tabPrompts.classList.toggle('active', !isClusters);
        tabClusters.classList.toggle('active', isClusters);
        tabPrompts.setAttribute('aria-selected', String(!isClusters));
        tabClusters.setAttribute('aria-selected', String(isClusters));
        panePrompts.classList.toggle('active', !isClusters);
        paneClusters.classList.toggle('active', isClusters);
        panePrompts.style.display = isClusters ? 'none' : '';
        paneClusters.style.display = isClusters ? '' : 'none';

        // When moving to clusters tab, render the editor UI with current state.
        // If the project has no clusters yet, seed one empty row so the user
        // can type immediately instead of hunting for the "Add cluster" button.
        if (isClusters) {
            this.renderClustersManagerList();
            const existing = this.getDefinedClusterNames();
            const isSilent = opts && opts.silent;
            if (!isSilent && existing.length === 0 && this.promptClustersConfig) {
                this.addClusterRow();
            }
        }
    },

updatePromptsMgmtTabCounts() {
        const promptsCount = Array.isArray(this.allPrompts) ? this.allPrompts.length : 0;
        const clustersCount = this.getDefinedClusterNames().length;
        const pEl = document.getElementById('promptsMgmtTabCount');
        const cEl = document.getElementById('clustersMgmtTabCount');
        if (pEl) pEl.textContent = promptsCount;
        if (cEl) cEl.textContent = clustersCount;
    },

buildPromptClusterSelectHtml(query) {
        const cfg = this.promptClustersConfig;
        // Only render the selector if clusters are enabled and there is at least one
        const clusters = this.getDefinedClusterNames();
        if (!cfg || !cfg.enabled || clusters.length === 0) return '';

        const current = query.topic_cluster || '';
        const state = current ? 'assigned' : 'unassigned';
        const options = [
            `<option value="">— Unassigned —</option>`,
            ...clusters.map(name => {
                const selected = (name === current) ? 'selected' : '';
                return `<option value="${this.escapeHtml(name)}" ${selected}>${this.escapeHtml(name)}</option>`;
            })
        ].join('');

        return `
            <span class="prompt-cluster-select-wrapper" title="Assign this prompt to a topic cluster">
                <i class="fas fa-layer-group"></i>
                <select class="prompt-cluster-select"
                        data-state="${state}"
                        data-query-id="${query.id}"
                        onchange="window.llmMonitoring.onPromptClusterChange(this, ${query.id})">
                    ${options}
                </select>
            </span>
        `;
    },

async onPromptClusterChange(selectEl, queryId) {
        const projectId = this.currentProject?.id;
        if (!projectId || !queryId) return;
        const value = selectEl.value || null;
        const original = selectEl.getAttribute('data-original') || '';
        selectEl.disabled = true;
        try {
            const resp = await fetch(`${this.baseUrl}/projects/${projectId}/queries/${queryId}/cluster`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cluster: value })
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.error || `HTTP ${resp.status}`);
            }
            // Update local state
            const prompt = (this.allPrompts || []).find(p => p.id === queryId);
            if (prompt) prompt.topic_cluster = data.topic_cluster || null;
            selectEl.setAttribute('data-state', value ? 'assigned' : 'unassigned');
            // Update counts without a full reload
            await this.loadClustersConfig(projectId);
            this.renderClustersManagerList();
            this.populatePromptsListClusterFilter();
            this.populateResponsesClusterFilter();
        } catch (err) {
            console.error('❌ Error updating cluster assignment:', err);
            // Revert selection
            selectEl.value = original;
            this.showError(`Could not update cluster: ${err.message || ''}`);
        } finally {
            selectEl.disabled = false;
        }
    },

refreshPromptClusterSelects() {
        // Easiest path: re-render the prompts list (source data already has topic_cluster)
        this.renderPrompts(this.isRenderingInModal);
    },

populatePromptsListClusterFilter() {
        const wrapper = document.getElementById('promptsClusterFilterWrapper');
        const sel = document.getElementById('promptsListClusterFilter');
        if (!sel || !wrapper) return;
        const clusters = this.getDefinedClusterNames();
        const enabled = this.promptClustersConfig?.enabled;
        if (!enabled || clusters.length === 0) {
            wrapper.style.display = 'none';
            sel.value = '';
            return;
        }
        wrapper.style.display = '';
        const prev = sel.value;
        const options = [
            `<option value="">All clusters</option>`,
            `<option value="__unassigned__">Unassigned</option>`,
            ...clusters.map(n => `<option value="${this.escapeHtml(n)}">${this.escapeHtml(n)}</option>`)
        ].join('');
        sel.innerHTML = options;
        // Restore previous value if still valid
        if (prev && (prev === '__unassigned__' || clusters.includes(prev))) {
            sel.value = prev;
        }
    }

});
