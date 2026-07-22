/**
 * LLM Monitoring - métodos de prototipo: core
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

init() {
        console.log('🎯 Initializing LLM Monitoring System...');

        this.handleInvitationFeedbackFromUrl();

        // Deep link desde AI Visibility Summary: /llm-monitoring?open_project=<id>
        // abre directamente ese proyecto tras cargar la lista.
        const params = new URLSearchParams(window.location.search);
        const openProjectId = Number(params.get('open_project') || 0);
        if (openProjectId) {
            params.delete('open_project');
            const nextQuery = params.toString();
            window.history.replaceState({}, '',
                nextQuery ? `${window.location.pathname}?${nextQuery}` : window.location.pathname);
            Promise.resolve(this.loadProjects()).then(() => this.viewProject(openProjectId));
        } else {
            // Load projects
            this.loadProjects();
        }

        // Load plan limits/usage
        this.loadPlanLimits();

        // Setup event listeners
        this.setupEventListeners();

        // Setup chips functionality
        this.setupChipsInputs();
    },

async loadPlanLimits() {
        try {
            const response = await fetch(`${this.baseUrl}/usage`);
            await this.handlePaywallResponse(response);
            if (!response.ok) return;
            const data = await response.json();
            if (!data || !data.limits) return;

            const limits = data.limits;
            this.planLimits = limits;
            // Update UI elements that show plan usage
            this.updatePlanLimitsUI();
        } catch (error) {
            console.warn('Could not load LLM plan limits:', error);
        }
    },

updatePlanLimitsUI() {
        const limits = this.planLimits;
        if (!limits) return;

        // --- Projects counter badge ---
        const projectsBadge = document.getElementById('projectsLimitBadge');
        if (projectsBadge) {
            if (limits.max_projects !== null) {
                const used = limits.active_projects || 0;
                const max = limits.max_projects;
                projectsBadge.textContent = `${used} / ${max}`;
                projectsBadge.style.display = 'inline-flex';
                // Color states
                projectsBadge.classList.remove('limit-warning', 'limit-reached');
                if (used >= max) {
                    projectsBadge.classList.add('limit-reached');
                } else if (used >= max * 0.8) {
                    projectsBadge.classList.add('limit-warning');
                }
            } else {
                // Unlimited (admin or enterprise)
                projectsBadge.style.display = 'none';
            }
        }

        // --- Create project button state ---
        const btnCreate = document.getElementById('btnCreateProject');
        if (btnCreate) {
            const hasLimit = limits.max_projects !== null;
            const atLimit = hasLimit && limits.active_projects >= limits.max_projects;
            if (atLimit) {
                btnCreate.classList.add('btn-limit-reached');
                btnCreate.setAttribute('title', `Project limit reached (${limits.active_projects}/${limits.max_projects}). Upgrade your plan to create more.`);
            } else {
                btnCreate.classList.remove('btn-limit-reached');
                btnCreate.removeAttribute('title');
            }
        }
    },

setupChipsInputs() {
        // Brand Keywords
        const brandKeywordsInput = document.getElementById('brandKeywords');
        if (brandKeywordsInput) {
            brandKeywordsInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    this.addChipFromInput('brandKeywords', 'brand');
                }
            });

            brandKeywordsInput.addEventListener('blur', () => {
                this.addChipFromInput('brandKeywords', 'brand');
            });
        }

        // Competitor Domains
        const competitorDomainsInput = document.getElementById('competitorDomains');
        if (competitorDomainsInput) {
            competitorDomainsInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    this.addChipFromInput('competitorDomains', 'competitor-domain');
                }
            });

            competitorDomainsInput.addEventListener('blur', () => {
                this.addChipFromInput('competitorDomains', 'competitor-domain');
            });
        }

        // ✨ NEW: Competitor 1-4 Keywords
        for (let i = 1; i <= 4; i++) {
            const competitorKeywordsInput = document.getElementById(`competitor${i}Keywords`);
            if (competitorKeywordsInput) {
                competitorKeywordsInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ',') {
                        e.preventDefault();
                        this.addChipFromInput(`competitor${i}Keywords`, 'competitor');
                    }
                });

                competitorKeywordsInput.addEventListener('blur', () => {
                    this.addChipFromInput(`competitor${i}Keywords`, 'competitor');
                });
            }
        }
    },

addChipFromInput(inputId, type) {
        const input = document.getElementById(inputId);
        if (!input) return;

        const value = input.value.trim().replace(/,/g, '');

        if (!value) return;

        // Determine which array to use
        let chipsArray;
        if (inputId === 'brandKeywords') {
            chipsArray = this.brandKeywordsChips;
        } else if (inputId === 'competitor1Keywords') {
            chipsArray = this.competitor1KeywordsChips;
        } else if (inputId === 'competitor2Keywords') {
            chipsArray = this.competitor2KeywordsChips;
        } else if (inputId === 'competitor3Keywords') {
            chipsArray = this.competitor3KeywordsChips;
        } else if (inputId === 'competitor4Keywords') {
            chipsArray = this.competitor4KeywordsChips;
        }

        // Check for duplicates
        if (chipsArray.includes(value)) {
            input.value = '';
            return;
        }

        // Add to array
        chipsArray.push(value);

        // Clear input
        input.value = '';

        // Render chips
        this.renderChips(inputId, type);
    },

renderChips(inputId, type) {
        const containerId = inputId + 'Chips';
        const container = document.getElementById(containerId);

        if (!container) return;

        // Determine which array to use
        let chipsArray;
        if (inputId === 'brandKeywords') {
            chipsArray = this.brandKeywordsChips;
        } else if (inputId === 'competitor1Keywords') {
            chipsArray = this.competitor1KeywordsChips;
        } else if (inputId === 'competitor2Keywords') {
            chipsArray = this.competitor2KeywordsChips;
        } else if (inputId === 'competitor3Keywords') {
            chipsArray = this.competitor3KeywordsChips;
        } else if (inputId === 'competitor4Keywords') {
            chipsArray = this.competitor4KeywordsChips;
        }

        // Clear container
        container.innerHTML = '';

        // Render each chip
        chipsArray.forEach((value, index) => {
            const chip = document.createElement('div');
            chip.className = `chip chip-${type}`;
            chip.innerHTML = `
                <span class="chip-text">${this.escapeHtml(value)}</span>
                <button type="button" class="chip-remove" data-input="${inputId}" data-index="${index}">
                    <i class="fas fa-times"></i>
                </button>
            `;

            // Add remove event
            const removeBtn = chip.querySelector('.chip-remove');
            removeBtn.addEventListener('click', (e) => {
                const inputIdAttr = e.currentTarget.dataset.input;
                const indexAttr = parseInt(e.currentTarget.dataset.index);
                this.removeChip(inputIdAttr, indexAttr, type);
            });

            container.appendChild(chip);
        });
    },

removeChip(inputId, index, type) {
        // Determine which array to use
        let chipsArray;
        if (inputId === 'brandKeywords') {
            chipsArray = this.brandKeywordsChips;
        } else if (inputId === 'competitor1Keywords') {
            chipsArray = this.competitor1KeywordsChips;
        } else if (inputId === 'competitor2Keywords') {
            chipsArray = this.competitor2KeywordsChips;
        } else if (inputId === 'competitor3Keywords') {
            chipsArray = this.competitor3KeywordsChips;
        } else if (inputId === 'competitor4Keywords') {
            chipsArray = this.competitor4KeywordsChips;
        }

        // Remove from array
        chipsArray.splice(index, 1);

        // Re-render
        this.renderChips(inputId, type);
    },

clearAllChips() {
        this.brandKeywordsChips = [];
        this.competitor1KeywordsChips = [];
        this.competitor2KeywordsChips = [];
        this.competitor3KeywordsChips = [];
        this.competitor4KeywordsChips = [];

        // Clear containers
        const brandContainer = document.getElementById('brandKeywordsChips');
        if (brandContainer) brandContainer.innerHTML = '';

        for (let i = 1; i <= 4; i++) {
            const container = document.getElementById(`competitor${i}KeywordsChips`);
            if (container) container.innerHTML = '';

            // Clear competitor domain inputs as well to avoid stale values in edit mode
            const domainInput = document.getElementById(`competitor${i}Domain`);
            if (domainInput) domainInput.value = '';
        }
    },

loadChipsFromData(brandKeywords, selectedCompetitors) {
        // Clear existing chips
        this.clearAllChips();

        // Load brand keywords
        if (Array.isArray(brandKeywords) && brandKeywords.length > 0) {
            this.brandKeywordsChips = [...brandKeywords];
            this.renderChips('brandKeywords', 'brand');
        }

        // ✨ NEW: Load selected_competitors into individual fields
        if (Array.isArray(selectedCompetitors) && selectedCompetitors.length > 0) {
            selectedCompetitors.forEach((comp, index) => {
                const competitorNum = index + 1;
                if (competitorNum > 4) return; // Max 4 competitors

                // Set domain field
                const domainInput = document.getElementById(`competitor${competitorNum}Domain`);
                if (domainInput) {
                    domainInput.value = comp.domain || '';
                }

                // Set keywords chips
                if (Array.isArray(comp.keywords) && comp.keywords.length > 0) {
                    this[`competitor${competitorNum}KeywordsChips`] = [...comp.keywords];
                    this.renderChips(`competitor${competitorNum}Keywords`, 'competitor');
                }
            });
        }
    },

normalizeLlmSelection(llms) {
        if (!Array.isArray(llms)) return [];
        return [...new Set(llms.map(llm => String(llm || '').trim()).filter(Boolean))].sort();
    },

getLlmSelectionChanges(previousLlms, currentLlms) {
        const previous = this.normalizeLlmSelection(previousLlms);
        const current = this.normalizeLlmSelection(currentLlms);
        const previousSet = new Set(previous);
        const currentSet = new Set(current);
        const added = current.filter(llm => !previousSet.has(llm));
        const removed = previous.filter(llm => !currentSet.has(llm));

        return {
            previous,
            current,
            added,
            removed,
            changed: added.length > 0 || removed.length > 0
        };
    },

formatLlmNames(llms) {
        return this.normalizeLlmSelection(llms).map(llm => this.getLLMDisplayName(llm));
    },

orderLlms(llms) {
        const providerOrder = ['openai', 'anthropic', 'google', 'perplexity'];
        const indexOf = (llm) => {
            const idx = providerOrder.indexOf(llm);
            return idx === -1 ? 999 : idx;
        };

        return this.normalizeLlmSelection(llms).sort((a, b) => {
            const diff = indexOf(a) - indexOf(b);
            return diff !== 0 ? diff : a.localeCompare(b);
        });
    },

updateLlmSelectionImpactNotice() {
        const notice = document.getElementById('llmSelectionImpactNotice');
        const noticeText = document.getElementById('llmSelectionImpactNoticeText');
        if (!notice || !noticeText) return;

        if (!this.currentProject?.id || !Array.isArray(this.modalOriginalEnabledLlms)) {
            notice.style.display = 'none';
            noticeText.textContent = '';
            return;
        }

        const change = this.getLlmSelectionChanges(
            this.modalOriginalEnabledLlms,
            this.getSelectedLlmsFromModal()
        );

        if (!change.changed) {
            notice.style.display = 'none';
            noticeText.textContent = '';
            return;
        }

        const details = [];
        if (change.added.length > 0) {
            details.push(`Added: ${this.formatLlmNames(change.added).join(', ')}`);
        }
        if (change.removed.length > 0) {
            details.push(`Removed: ${this.formatLlmNames(change.removed).join(', ')}`);
        }

        noticeText.textContent =
            `Changing active models affects charts and exports for the selected date range after save. ${details.join(' · ')}`;
        notice.style.display = 'flex';
    },

setupEventListeners() {
        console.log('🎯 Setting up event listeners...');

        // Custom confirmation modal handlers
        this.setupConfirmModalListeners();

        // Create project button
        const btnCreateProject = document.getElementById('btnCreateProject');
        console.log('📦 btnCreateProject element:', btnCreateProject);

        if (btnCreateProject) {
            btnCreateProject.addEventListener('click', () => {
                const limits = this.planLimits;
                const hasProjectLimit = limits && limits.max_projects !== null;
                const isLimitReached = hasProjectLimit && limits.active_projects >= limits.max_projects;

                if (isLimitReached) {
                    if (window.showPaywall) {
                        window.showPaywall('LLM Monitoring', ['premium', 'business', 'enterprise']);
                    }
                    this.showError(`You've reached the project limit for your plan (${limits.active_projects}/${limits.max_projects}). Upgrade to create more projects.`);
                    return;
                }

                console.log('🖱️ btnCreateProject clicked!');
                this.showProjectModal();
            });
            console.log('✅ Event listener added to btnCreateProject');
        } else {
            console.error('❌ btnCreateProject element not found!');
        }

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

        document.getElementById('llmProjectInviteBtn')?.addEventListener('click', () => {
            this.sendProjectInvitationFromModal();
        });

        // Form submit handler
        document.getElementById('projectForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            console.log('📝 Form submitted!');
            this.saveProject();
        });

        // Show model-impact warning only when LLM selection changes in edit mode.
        document.querySelectorAll('input[name="llm"]').forEach((checkbox) => {
            checkbox.addEventListener('change', () => {
                this.updateLlmSelectionImpactNotice();
            });
        });

        // Analyze project: REMOVED - Analysis now runs via daily cron, not manual triggers

        // Top URLs LLM filters
        document.getElementById('urlsLLMFilter')?.addEventListener('change', () => {
            if (this.currentProject) {
                // Reset domain view when changing filters
                const domainsBtn = document.getElementById('showTopDomainsLLM');
                if (domainsBtn && domainsBtn.dataset.active === 'true') {
                    domainsBtn.dataset.active = 'false';
                    domainsBtn.classList.remove('active');
                }

                this.loadTopUrlsRanking(this.currentProject.id);
            }
        });

        // ✨ GLOBAL: Share of Voice metric toggle (FAB)
        document.querySelectorAll('input[name="globalSovMetric"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (this.currentProject) {
                    const metricType = e.target.value;
                    console.log(`📊 GLOBAL: Switching to ${metricType} Share of Voice metric`);
                    console.log(`   → Updating all charts and metrics...`);

                    // Guardar preferencia en localStorage
                    localStorage.setItem('llm_monitoring_sov_metric', metricType);

                    // Actualizar TODOS los gráficos, métricas y tablas
                    this.renderShareOfVoiceChart();  // Gráfico de líneas temporal
                    this.renderShareOfVoiceDonutChart();  // Gráfico de rosco/distribución
                    this.renderMentionsTimelineChart();  // Timeline de menciones (usa los mismos datos)
                    this.loadClustersPerformance(this.currentProject.id);  // ✨ NUEVO: Clusters Performance chart (reemplaza LLM Comparison)
                    this.refreshProjectKPIs();  // ✨ NUEVO: KPIs alineados con la métrica

                    console.log(`✅ All charts and tables updated to ${metricType} metric`);
                }
            });
        });

        // ✨ GLOBAL: Share of Voice info modal (from FAB)
        document.getElementById('btnGlobalSovInfo')?.addEventListener('click', () => {
            this.showSovInfoModal();
        });

        // Restaurar preferencia de métrica desde localStorage
        const savedMetric = localStorage.getItem('llm_monitoring_sov_metric') || 'weighted';
        const radioToCheck = document.getElementById(savedMetric === 'weighted' ? 'globalMetricWeighted' : 'globalMetricNormal');
        if (radioToCheck) {
            radioToCheck.checked = true;
        }

        // Animación de pulso al cargar (destacar el FAB)
        setTimeout(() => {
            document.getElementById('globalMetricFab')?.classList.add('pulse');
            setTimeout(() => {
                document.getElementById('globalMetricFab')?.classList.remove('pulse');
            }, 6000); // 3 pulsos x 2 segundos
        }, 1000);

        document.getElementById('btnCloseSovInfo')?.addEventListener('click', () => {
            this.hideSovInfoModal();
        });

        document.getElementById('btnCloseSovInfoFooter')?.addEventListener('click', () => {
            this.hideSovInfoModal();
        });

        // Close modal on overlay click
        document.getElementById('sovInfoModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'sovInfoModal') {
                this.hideSovInfoModal();
            }
        });

        // ✨ urlsDaysFilter listener removed - now using global time range

        document.getElementById('filterMyBrandUrlsLLM')?.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const isActive = btn.dataset.active === 'true';
            btn.dataset.active = !isActive;
            btn.classList.toggle('active', !isActive);

            // Desactivar el botón de dominios si está activo
            const domainsBtn = document.getElementById('showTopDomainsLLM');
            if (domainsBtn && domainsBtn.dataset.active === 'true') {
                domainsBtn.dataset.active = 'false';
                domainsBtn.classList.remove('active');
            }

            if (this.currentProject) {
                this.filterLLMUrlsByBrand(!isActive);
            }
        });

        document.getElementById('showTopDomainsLLM')?.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const isActive = btn.dataset.active === 'true';
            btn.dataset.active = !isActive;
            btn.classList.toggle('active', !isActive);

            // Desactivar el botón de my brand si está activo
            const brandBtn = document.getElementById('filterMyBrandUrlsLLM');
            if (brandBtn && brandBtn.dataset.active === 'true') {
                brandBtn.dataset.active = 'false';
                brandBtn.classList.remove('active');
            }

            if (this.currentProject) {
                this.toggleDomainsView(!isActive);
            }
        });

        // Edit project
        document.getElementById('btnEditProject')?.addEventListener('click', () => {
            this.editProject(this.currentProject?.id, this.currentProject);
        });

        // Show models info
        document.getElementById('btnShowModels')?.addEventListener('click', () => {
            this.showModelsModal();
        });

        // Delete project (from metrics view)
        document.getElementById('btnDeleteProject')?.addEventListener('click', () => {
            if (this.currentProject && this.currentProject.id) {
                this.deleteProject(this.currentProject.id, this.currentProject.name);
            }
        });

        // ✅ NUEVO: Gestión de prompts - Abrir modal
        document.getElementById('btnManagePrompts')?.addEventListener('click', () => {
            this.showPromptsManagementModal();
        });

        // Botones dentro del modal de Prompts Management
        document.getElementById('btnAddPromptsModal')?.addEventListener('click', () => {
            this.showPromptsModal();
        });

        document.getElementById('btnGetSuggestionsModal')?.addEventListener('click', () => {
            this.showSuggestionsModal();
        });

        // Legacy: Mantener botón antiguo por si acaso
        document.getElementById('btnAddPrompts')?.addEventListener('click', () => {
            this.showPromptsModal();
        });

        // Prompts form submit
        document.getElementById('promptsForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.savePrompts();
        });

        // ✅ NUEVO: Sugerencias con IA
        document.getElementById('btnGetSuggestions')?.addEventListener('click', () => {
            this.showSuggestionsModal();
        });

        document.getElementById('btnAddSelectedSuggestions')?.addEventListener('click', () => {
            this.addSelectedSuggestions();
        });

        // ✨ NUEVO: Event listeners para filtros de Responses Inspector
        document.getElementById('responsesQueryFilter')?.addEventListener('change', () => {
            if (this.currentProject?.id) {
                this.loadResponses();
            }
        });

        document.getElementById('responsesLLMFilter')?.addEventListener('change', () => {
            if (this.currentProject?.id) {
                this.loadResponses();
            }
        });

        // Client-side filters: Mention, Sentiment, Prompt Type
        ['responsesMentionFilter', 'responsesSentimentFilter', 'responsesQueryTypeFilter'].forEach(filterId => {
            document.getElementById(filterId)?.addEventListener('change', () => {
                if (this.allResponses && this.allResponses.length > 0) {
                    this.applyClientSideFilters();
                } else if (this.currentProject?.id) {
                    this.loadResponses();
                }
            });
        });

        // Scope chips for Mention Rate and SOV charts
        document.querySelectorAll('.chart-scope-chips').forEach(container => {
            container.addEventListener('click', (e) => {
                const chip = e.target.closest('.scope-chip');
                if (!chip) return;
                const scope = chip.dataset.scope;
                const chart = container.dataset.chart;

                // Toggle active class
                container.querySelectorAll('.scope-chip').forEach(c => c.classList.remove('scope-chip--active'));
                chip.classList.add('scope-chip--active');

                if (chart === 'mentionRate') {
                    this.mentionRateScope = scope;
                    this.renderMentionRateChartScoped(scope);
                } else if (chart === 'sov') {
                    this.sovScope = scope;
                    this.renderShareOfVoiceChart();
                } else if (chart === 'mentions') {
                    this.mentionsScope = scope;
                    this.renderMentionsTimelineChart();
                }
            });
        });

        // ✨ responsesDaysFilter listener removed - now using global time range

        // ✨ Global Time Range Selector - controls all data, charts and tables
        document.getElementById('globalTimeRange')?.addEventListener('change', async (e) => {
            if (this.currentProject) {
                this.globalTimeRange = parseInt(e.target.value);
                console.log(`📅 Global time range changed to: ${this.globalTimeRange} days`);

                // Reload all project data with new time range
                await this.viewProject(this.currentProject.id);

                // Mantener Responses Inspector alineado solo si el usuario ya lo había cargado.
                if (this.responsesLoaded) {
                    await this.loadResponses();
                }
            }
        });

        // ✨ Download Excel button
        document.getElementById('llmDownloadExcelBtn')?.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('📥 LLM Monitoring Excel download clicked');
            this.downloadExcel();
        });

        // ✨ Download PDF button
        document.getElementById('llmDownloadPdfBtn')?.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('📥 LLM Monitoring PDF download clicked');
            this.downloadPdf();
        });
    },

async runInitialAnalysis(projectId, projectName = 'Project', configuredQueries = 0) {
        if (!projectId) {
            this.showError('No project selected');
            return;
        }

        if (Number(configuredQueries || 0) <= 0) {
            this.showInfo('Add at least one prompt before running the first analysis.');
            return;
        }

        const button = document.getElementById(`btnInitialAnalysis-${projectId}`);
        const originalHtml = button ? button.innerHTML : '';

        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        }

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/run-initial-analysis`, {
                method: 'POST',
                credentials: 'same-origin'
            });

            let data = {};
            try {
                data = await response.json();
            } catch (e) {
                data = {};
            }

            if (!response.ok) {
                const errorCode = data.error || `HTTP ${response.status}`;

                if (errorCode === 'initial_analysis_already_completed') {
                    this.showInfo('This project already has data from a previous analysis.');
                    await this.loadProjects();
                    return;
                }

                if (errorCode === 'initial_analysis_in_progress') {
                    this.showInfo('First analysis is already running for this project.');
                    await this.loadProjects();
                    this.pollInitialAnalysisStatus(projectId, projectName);
                    return;
                }

                if (errorCode === 'no_active_queries') {
                    this.showInfo('Add prompts to the project before running the first analysis.');
                    await this.loadProjects();
                    return;
                }

                throw new Error(data.message || errorCode);
            }

            const minMinutes = data.estimated_minutes_min || 2;
            const maxMinutes = data.estimated_minutes_max || 8;

            this.showInfo(
                `First analysis started for "${projectName}". ` +
                `Estimated time: ${minMinutes}-${maxMinutes} minutes. ` +
                'You can keep using the app while it runs in background.'
            );

            // Refresh cards to show "running" state and start polling until completion.
            await this.loadProjects();
            this.pollInitialAnalysisStatus(projectId, projectName, maxMinutes + 5);

        } catch (error) {
            console.error('❌ Error starting initial analysis:', error);
            this.showError(error.message || 'Could not start first analysis');

            if (button) {
                button.disabled = false;
                button.innerHTML = originalHtml;
            }
        }
    },

pollInitialAnalysisStatus(projectId, projectName = 'Project', maxMinutes = 15) {
        const intervalMs = 15000; // 15s
        const maxAttempts = Math.max(8, Math.ceil((maxMinutes * 60 * 1000) / intervalMs));
        let attempts = 0;

        const timer = setInterval(async () => {
            attempts += 1;

            try {
                const response = await fetch(`${this.baseUrl}/projects`, {
                    credentials: 'same-origin'
                });

                if (!response.ok) {
                    if (attempts >= maxAttempts) {
                        clearInterval(timer);
                    }
                    return;
                }

                const data = await response.json();
                const projects = data.projects || [];
                const project = projects.find(p => p.id === projectId);

                if (!project) {
                    clearInterval(timer);
                    return;
                }

                if (project.last_analysis_date) {
                    clearInterval(timer);
                    this.showSuccess(`First analysis for "${projectName}" is complete.`);
                    await this.loadProjects();
                    return;
                }

                if (!project.initial_analysis_in_progress && attempts >= 2) {
                    clearInterval(timer);
                    this.showInfo(
                        `First analysis for "${projectName}" has finished without new data yet. ` +
                        'It may have hit quota/provider limits; you can retry or wait for scheduled cron.'
                    );
                    await this.loadProjects();
                    return;
                }

                if (attempts >= maxAttempts) {
                    clearInterval(timer);
                    this.showInfo(
                        `First analysis for "${projectName}" is still running. ` +
                        'Please check again in a few minutes.'
                    );
                    await this.loadProjects();
                }
            } catch (error) {
                console.warn('Could not poll initial analysis status:', error);
                if (attempts >= maxAttempts) {
                    clearInterval(timer);
                }
            }
        }, intervalMs);
    },

updateKPIs(metrics, trends = null) {
        if (!metrics || Object.keys(metrics).length === 0) {
            document.getElementById('kpiMentionRate').innerHTML = '<span class="kpi-no-data">No data</span>';
            document.getElementById('kpiShareOfVoice').innerHTML = '<span class="kpi-no-data">No data</span>';
            document.getElementById('kpiSentiment').innerHTML = '<span class="kpi-no-data">No data</span>';
            return;
        }

        // ✨ MÉTODO 2 (SoV Agregado): TODOS los LLMs tienen el MISMO valor agregado
        // Backend ya calcula y envía el mismo valor para todos los LLMs
        const llms = Object.keys(metrics);
        const firstLLM = llms[0];

        // ✨ AGREGADO: Mention Rate (mismo valor para todos los LLMs)
        const aggregatedMentionRate = metrics[firstLLM].mention_rate || 0;

        // ✨ AGREGADO: Share of Voice (mismo valor para todos los LLMs)
        const aggregatedSOV = metrics[firstLLM].share_of_voice || 0;

        // ✨ AGREGADO: Sentiment (mismo valor para todos los LLMs)
        const sentiment = metrics[firstLLM].sentiment || { positive: 0, neutral: 0, negative: 0 };

        // Determinar el sentiment predominante
        let sentimentLabel, sentimentClass;
        if (sentiment.positive >= sentiment.neutral && sentiment.positive >= sentiment.negative) {
            sentimentLabel = 'Positive';
            sentimentClass = 'positive';
        } else if (sentiment.negative > sentiment.positive && sentiment.negative > sentiment.neutral) {
            sentimentLabel = 'Negative';
            sentimentClass = 'negative';
        } else {
            sentimentLabel = 'Neutral';
            sentimentClass = 'neutral';
        }

        // ✨ NUEVO: Generar HTML con tendencias
        const mentionRateHTML = this.renderKPIWithTrend(
            aggregatedMentionRate, 
            '%', 
            trends?.mention_rate
        );
        
        const sovHTML = this.renderKPIWithTrend(
            aggregatedSOV, 
            '%', 
            trends?.share_of_voice
        );
        
        // ✨ Sentiment con tendencia CATEGÓRICA (better/worse/same)
        let sentimentHTML = `<span class="kpi-main-value sentiment-${sentimentClass}">${sentimentLabel}</span>`;
        if (trends?.sentiment) {
            const trend = trends.sentiment;
            let trendClass, trendIcon, trendLabel;
            
            if (trend.direction === 'better') {
                trendClass = 'trend-up';
                trendIcon = 'fa-arrow-up';
                trendLabel = 'Better';
            } else if (trend.direction === 'worse') {
                trendClass = 'trend-down';
                trendIcon = 'fa-arrow-down';
                trendLabel = 'Worse';
            } else {
                trendClass = 'trend-stable';
                trendIcon = 'fa-equals';
                trendLabel = 'Same';
            }
            
            // Capitalizar el sentimiento anterior para el tooltip
            const prevSentiment = trend.previous ? trend.previous.charAt(0).toUpperCase() + trend.previous.slice(1) : 'Unknown';
            
            sentimentHTML += `
                <div class="kpi-trend ${trendClass}" title="Previous period: ${prevSentiment}">
                    <i class="fas ${trendIcon}"></i>
                    <span>${trendLabel}</span>
                </div>
            `;
        } else {
            sentimentHTML += `
                <div class="kpi-trend trend-nodata" title="Not enough historical data to calculate trend">
                    <span>&mdash;</span>
                </div>
            `;
        }

        document.getElementById('kpiMentionRate').innerHTML = mentionRateHTML;
        document.getElementById('kpiShareOfVoice').innerHTML = sovHTML;
        document.getElementById('kpiSentiment').innerHTML = sentimentHTML;
    },

renderKPIWithTrend(value, suffix = '', trend = null) {
        let html = `<span class="kpi-main-value">${value.toFixed(1)}${suffix}</span>`;
        
        console.log('🔍 Rendering KPI trend:', { value, trend });
        
        if (trend) {
            if (trend.direction === 'up') {
                html += `
                    <div class="kpi-trend trend-up" title="vs previous ${this.globalTimeRange} days: ${trend.previous}${suffix}">
                        <i class="fas fa-arrow-up"></i>
                        <span>+${trend.change}%</span>
                    </div>
                `;
            } else if (trend.direction === 'down') {
                html += `
                    <div class="kpi-trend trend-down" title="vs previous ${this.globalTimeRange} days: ${trend.previous}${suffix}">
                        <i class="fas fa-arrow-down"></i>
                        <span>-${trend.change}%</span>
                    </div>
                `;
            } else {
                // Stable
                html += `
                    <div class="kpi-trend trend-stable" title="No significant change vs previous ${this.globalTimeRange} days">
                        <i class="fas fa-equals"></i>
                        <span>stable</span>
                    </div>
                `;
            }
        } else {
            // No hay datos de tendencia (primer período)
            html += `
                <div class="kpi-trend trend-nodata" title="Not enough historical data to calculate trend">
                    <span>&mdash;</span>
                </div>
            `;
        }
        
        return html;
    },

renderMiniTrend(trend) {
        if (!trend) return '<span class="branded-trend branded-trend--new" title="Not enough historical data">&mdash;</span>';
        const titleText = `vs previous ${this.globalTimeRange} days: ${trend.previous}%`;
        if (trend.direction === 'up') return `<span class="branded-trend branded-trend--up" title="${titleText}">&uarr; +${trend.change}%</span>`;
        if (trend.direction === 'down') return `<span class="branded-trend branded-trend--down" title="${titleText}">&darr; -${trend.change}%</span>`;
        return `<span class="branded-trend branded-trend--stable" title="${titleText}">= stable</span>`;
    },

updateProgressBar(elementId, value) {
        const bar = document.getElementById(elementId);
        if (bar) {
            bar.style.width = `${Math.min(value, 100)}%`;
        }
    },

updateQualityScore(qualityData) {
        const container = document.getElementById('qualityScoreCard');
        if (!container) return;
        
        if (!qualityData) {
            container.style.display = 'none';
            return;
        }
        
        container.style.display = 'block';
        
        const score = qualityData.score || 0;
        const components = qualityData.components || {};
        const details = qualityData.details || {};
        
        // Determinar estado del score
        let scoreClass, scoreLabel;
        if (score >= 80) {
            scoreClass = 'quality-excellent';
            scoreLabel = 'Excellent';
        } else if (score >= 60) {
            scoreClass = 'quality-good';
            scoreLabel = 'Good';
        } else if (score >= 40) {
            scoreClass = 'quality-fair';
            scoreLabel = 'Fair';
        } else {
            scoreClass = 'quality-poor';
            scoreLabel = 'Needs Attention';
        }
        
        // Actualizar score principal
        const scoreValueEl = document.getElementById('qualityScoreValue');
        if (scoreValueEl) {
            scoreValueEl.textContent = `${score}%`;
            scoreValueEl.className = `quality-score-value ${scoreClass}`;
        }
        
        const scoreLabelEl = document.getElementById('qualityScoreLabel');
        if (scoreLabelEl) {
            scoreLabelEl.textContent = scoreLabel;
            scoreLabelEl.className = `quality-score-label ${scoreClass}`;
        }
        
        // Actualizar componentes
        const analyzedQueries = details.total_analyzed_queries;
        const expectedQueries = details.total_expected_queries;
        this.updateQualityComponent('completeness', components.completeness, analyzedQueries, expectedQueries);
        this.updateQualityComponent('freshness', components.freshness, details.days_since_update);
        this.updateQualityComponent('coverage', components.coverage, details.llms_with_data, details.llms_expected);
    },

updateQualityComponent(type, value, detail1 = null, detail2 = null) {
        const valueEl = document.getElementById(`quality${type.charAt(0).toUpperCase() + type.slice(1)}Value`);
        const barEl = document.getElementById(`quality${type.charAt(0).toUpperCase() + type.slice(1)}Bar`);
        const detailEl = document.getElementById(`quality${type.charAt(0).toUpperCase() + type.slice(1)}Detail`);
        
        if (valueEl) {
            valueEl.textContent = `${(value || 0).toFixed(0)}%`;
        }
        
        if (barEl) {
            barEl.style.width = `${Math.min(value || 0, 100)}%`;
            
            // Color según valor
            if (value >= 80) {
                barEl.style.backgroundColor = '#22c55e';
            } else if (value >= 60) {
                barEl.style.backgroundColor = '#eab308';
            } else {
                barEl.style.backgroundColor = '#ef4444';
            }
        }
        
        if (detailEl) {
            if (type === 'completeness' && detail1 !== null && detail2 !== null) {
                detailEl.textContent = `${detail1}/${detail2} prompts`;
            } else if (type === 'freshness' && detail1 !== null) {
                if (detail1 === 0) {
                    detailEl.textContent = 'Updated today';
                } else if (detail1 === 1) {
                    detailEl.textContent = '1 day ago';
                } else {
                    detailEl.textContent = `${detail1} days ago`;
                }
            } else if (type === 'coverage' && detail1 !== null && detail2 !== null) {
                detailEl.textContent = `${detail1}/${detail2} LLMs`;
            }
        }
    },

bindDetailButtonsDelegation(container) {
        if (!container) return;

        // Avoid duplicate listeners when grid gets re-rendered.
        if (this._onQueryDetailsClick) {
            container.removeEventListener('click', this._onQueryDetailsClick);
        }

        this._onQueryDetailsClick = (event) => {
            const detailBtn = event.target.closest('.view-details-btn');
            if (!detailBtn || !container.contains(detailBtn)) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            const rowIdx = Number.parseInt(detailBtn.dataset.rowIdx, 10);
            if (Number.isNaN(rowIdx)) {
                return;
            }

            console.log(`📊 Opening brand mentions modal for row ${rowIdx}`);
            this.showBrandMentionsModal(rowIdx);
        };

        container.addEventListener('click', this._onQueryDetailsClick);
    },

showDownloadButtons(show = true) {
        const toolsSection = document.getElementById('navSectionTools');
        const excelBtn = document.getElementById('llmDownloadExcelBtn');
        const pdfBtn = document.getElementById('llmDownloadPdfBtn');

        if (toolsSection) {
            toolsSection.style.display = show ? 'block' : 'none';
        }
        if (excelBtn) {
            excelBtn.style.display = show ? 'flex' : 'none';
        }
        if (pdfBtn) {
            pdfBtn.style.display = show ? 'flex' : 'none';
        }

        console.log(`📥 Download buttons ${show ? 'shown' : 'hidden'}`);
    },

async downloadExcel() {
        if (!this.currentProject) {
            this.showError('No project selected');
            return;
        }

        const btn = document.getElementById('llmDownloadExcelBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');

        try {
            // Show loading state
            if (spinner) spinner.style.display = 'inline-block';
            if (btnText) btnText.textContent = 'Exporting...';
            if (btn) btn.disabled = true;

            console.log(`📥 Downloading Excel for project ${this.currentProject.id}...`);

            // Fetch export data from API
            const response = await fetch(
                `${this.baseUrl}/projects/${this.currentProject.id}/export/excel?days=${this.globalTimeRange}`,
                { credentials: 'same-origin' }
            );

            if (!response.ok) {
                const errorPayload = await response.json().catch(() => null);
                const message = errorPayload?.error || `HTTP ${response.status}`;
                throw new Error(message);
            }

            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                const errorPayload = await response.json().catch(() => null);
                const message = errorPayload?.error || 'Export failed';
                throw new Error(message);
            }

            // Get the blob and download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `llm-monitoring-${this.currentProject.name.replace(/[^a-z0-9]/gi, '-')}-${new Date().toISOString().split('T')[0]}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            // Success state
            if (btn) btn.classList.add('success');
            if (btnText) btnText.textContent = 'Downloaded!';

            setTimeout(() => {
                if (btn) btn.classList.remove('success');
                if (btnText) btnText.textContent = 'Download Excel';
            }, 2000);

            console.log('✅ Excel downloaded successfully');

        } catch (error) {
            console.error('❌ Error downloading Excel:', error);
            this.showError('Failed to download Excel. Please try again.');
            if (btnText) btnText.textContent = 'Download Excel';
        } finally {
            if (spinner) spinner.style.display = 'none';
            if (btn) btn.disabled = false;
        }
    },

async downloadPdf() {
        if (!this.currentProject) {
            this.showError('No project selected');
            return;
        }

        const btn = document.getElementById('llmDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');

        try {
            if (spinner) spinner.style.display = 'inline-block';
            if (btnText) btnText.textContent = 'Generating PDF...';
            if (btn) btn.disabled = true;

            const response = await fetch(
                `${this.baseUrl}/projects/${this.currentProject.id}/export/pdf?days=${this.globalTimeRange}`
            );

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'PDF generation failed');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const projectName = this.currentProject.name || 'LLM-Monitoring';
            a.download = `llm-monitoring-${projectName.replace(/[^a-z0-9]/gi, '-')}-${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            if (btn) btn.classList.add('success');
            if (btnText) btnText.textContent = 'Downloaded!';
            setTimeout(() => {
                if (btn) btn.classList.remove('success');
                if (btnText) btnText.textContent = 'Download PDF';
            }, 2000);

            this.showSuccess('PDF generated successfully!');
            console.log('✅ PDF downloaded from server');

        } catch (error) {
            console.error('❌ Error generating PDF:', error);
            this.showError('Failed to generate PDF. Please try again.');
            if (btnText) btnText.textContent = 'Download PDF';
        } finally {
            if (spinner) spinner.style.display = 'none';
            if (btn) btn.disabled = false;
        }
    },

nextPage() {
        // Honor the cluster filter for pagination bounds when in modal
        const clusterFilter = this.isRenderingInModal
            ? (document.getElementById('promptsListClusterFilter')?.value || '')
            : '';
        const source = Array.isArray(this.allPrompts) ? this.allPrompts : [];
        let visible = source;
        if (clusterFilter === '__unassigned__') {
            visible = source.filter(p => !p.topic_cluster);
        } else if (clusterFilter) {
            visible = source.filter(p => (p.topic_cluster || '') === clusterFilter);
        }
        const totalPages = Math.ceil(visible.length / this.promptsPerPage);
        if (this.currentPromptsPage < totalPages) {
            this.currentPromptsPage++;
            this.renderPrompts(this.isRenderingInModal);
        }
    },

prevPage() {
        if (this.currentPromptsPage > 1) {
            this.currentPromptsPage--;
            this.renderPrompts(this.isRenderingInModal);
        }
    },

getCompetitorFallbackLabel(languageCode) {
        const labels = {
            es: 'competidores',
            it: 'concorrenti',
            fr: 'concurrents',
            de: 'Wettbewerber',
            pt: 'concorrentes'
        };
        return labels[languageCode] || 'competitors';
    },

getPrimaryCompetitorName(languageCode) {
        const selectedCompetitors = Array.isArray(this.currentProject?.selected_competitors)
            ? this.currentProject.selected_competitors
            : [];
        const competitorFromSelection = selectedCompetitors.find(comp => comp && comp.domain)?.domain;
        if (competitorFromSelection) {
            return competitorFromSelection;
        }

        const legacyCompetitor = Array.isArray(this.currentProject?.competitors)
            ? this.currentProject.competitors.find(comp => comp && String(comp).trim())
            : null;
        if (legacyCompetitor) {
            return legacyCompetitor;
        }

        return this.getCompetitorFallbackLabel(languageCode);
    },

escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

getLLMDisplayName(llm) {
        const names = {
            'openai': 'ChatGPT',
            'anthropic': 'Claude',
            'google': 'Gemini',
            'perplexity': 'Perplexity'
        };
        return names[llm] || llm;
    },

getLLMIcon(llm) {
        const icons = {
            'openai': 'fas fa-robot',
            'anthropic': 'fas fa-brain',
            'google': 'fas fa-star',
            'perplexity': 'fas fa-search'
        };
        return icons[llm] || 'fas fa-robot';
    },

getLLMColor(llm) {
        const colors = {
            'openai': '#10b981',
            'anthropic': '#a855f7',
            'google': '#3b82f6',
            'perplexity': '#f59e0b'
        };
        return colors[llm] || '#6b7280';
    },

formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleDateString('es-ES', { year: 'numeric', month: 'short', day: 'numeric' });
    },

escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

escapeAttr(text) {
        // escapeHtml (textContent trick) does NOT escape quotes, which can break
        // out of an HTML attribute. Escape quotes too for attribute-value contexts.
        return this.escapeHtml(text)
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

showError(message) {
        this.showToast(message, 'error', 7000);
    },

showSuccess(message) {
        this.showToast(message, 'success', 4000);
    },

showInfo(message) {
        this.showToast(message, 'info', 5000);
    },

isSafeUrl(url) {
        // Allow only http(s) and relative URLs; block javascript:, data:, etc.
        const value = String(url || '').trim();
        if (!value) return false;
        // Absolute http(s) or protocol-relative URLs are safe
        if (/^(https?:)?\/\//i.test(value)) return true;
        // Relative URLs / anchors have no scheme before the first / # ?
        if (/^[^:]*[/#?]/.test(value) || !/:/.test(value)) return true;
        return false;
    },

parseMarkdown(text) {
        if (!text) return '';

        // Escape HTML FIRST so raw LLM output can't inject markup, then decorate.
        let html = this.escapeHtml(text);

        // Headers (### Header -> <h3>)
        html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>');

        // Bold (**text** or __text__)
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

        // Italic (*text* or _text_)
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/_(.+?)_/g, '<em>$1</em>');

        // Inline code (`code`)
        html = html.replace(/`(.+?)`/g, '<code class="md-code">$1</code>');

        // Links [text](url) - only allow http(s)/relative URLs to block javascript:, data:, etc.
        html = html.replace(/\[(.+?)\]\((.+?)\)/g, (match, label, url) => {
            if (!this.isSafeUrl(url)) return label;
            return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="md-link">${label}</a>`;
        });

        // Unordered lists (- item or * item)
        html = html.replace(/^\s*[-*]\s+(.+)$/gm, '<li class="md-li">$1</li>');
        html = html.replace(/(<li class="md-li">.+<\/li>\n?)+/g, '<ul class="md-ul">$&</ul>');

        // Ordered lists (1. item)
        html = html.replace(/^\s*\d+\.\s+(.+)$/gm, '<li class="md-li">$1</li>');
        // Wrap consecutive <li> in <ol> if not already in <ul>
        const lines = html.split('\n');
        let inList = false;
        let listType = null;
        let result = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            if (line.includes('<li class="md-li">') && !line.includes('<ul') && !line.includes('<ol')) {
                if (!inList) {
                    // Start new list - determine type by checking previous lines
                    const prevLines = html.substring(0, html.indexOf(line));
                    if (prevLines.match(/^\s*\d+\.\s+/m)) {
                        result.push('<ol class="md-ol">');
                        listType = 'ol';
                    } else {
                        result.push('<ul class="md-ul">');
                        listType = 'ul';
                    }
                    inList = true;
                }
                result.push(line);
            } else {
                if (inList && !line.includes('<li')) {
                    result.push(`</${listType}>`);
                    inList = false;
                    listType = null;
                }
                result.push(line);
            }
        }

        if (inList) {
            result.push(`</${listType}>`);
        }

        html = result.join('\n');

        // Paragraphs (double line breaks)
        html = html.replace(/\n\n/g, '</p><p class="md-p">');
        html = '<p class="md-p">' + html + '</p>';

        // Clean up empty paragraphs and fix nested tags
        html = html.replace(/<p class="md-p"><\/p>/g, '');
        html = html.replace(/<p class="md-p">(<[uo]l class="md-[uo]l">)/g, '$1');
        html = html.replace(/(<\/[uo]l>)<\/p>/g, '$1');
        html = html.replace(/<p class="md-p">(<h[1-3] class="md-h[1-3]">)/g, '$1');
        html = html.replace(/(<\/h[1-3]>)<\/p>/g, '$1');

        return html;
    },

applyClientSideFilters() {
        const mentionFilter = document.getElementById('responsesMentionFilter')?.value || '';
        const sentimentFilter = document.getElementById('responsesSentimentFilter')?.value || '';

        // Start with all responses
        let filtered = [...this.allResponses];

        // Apply mention filter
        if (mentionFilter === 'mentioned') {
            filtered = filtered.filter(r => r.brand_mentioned === true);
        } else if (mentionFilter === 'not-mentioned') {
            filtered = filtered.filter(r => r.brand_mentioned === false);
        }

        // Apply sentiment filter
        if (sentimentFilter) {
            filtered = filtered.filter(r => r.sentiment === sentimentFilter);
        }

        const queryTypeFilter = document.getElementById('responsesQueryTypeFilter')?.value || '';
        if (queryTypeFilter === 'branded') {
            filtered = filtered.filter(r => this.isQueryBranded(r.query_text));
        } else if (queryTypeFilter === 'non-branded') {
            filtered = filtered.filter(r => !this.isQueryBranded(r.query_text));
        }

        // Store filtered responses and reset pagination
        this.filteredResponses = filtered;
        this.currentResponsesShown = this.responsesPerPage;

        // Re-render with filtered data
        const container = document.getElementById('responsesContainer');
        if (container) {
            this.renderResponsesPaginated(container);
        }

        console.log(`🔍 Applied filters: mention=${mentionFilter || 'all'}, sentiment=${sentimentFilter || 'all'} -> ${filtered.length} results`);
    },

updateQuickStats(responses) {
        const statsContainer = document.getElementById('responsesQuickStats');
        if (!statsContainer) return;

        // Show the stats bar
        statsContainer.style.display = 'flex';

        // Calculate stats
        const total = responses.length;
        const mentioned = responses.filter(r => r.brand_mentioned).length;
        const mentionRate = total > 0 ? ((mentioned / total) * 100).toFixed(1) : 0;
        
        // Average position (only for responses with position)
        const withPosition = responses.filter(
            r =>
                r.brand_mentioned &&
                r.position_in_list !== null &&
                r.position_in_list !== undefined &&
                r.position_in_list <= 30
        );
        const avgPosition = withPosition.length > 0 
            ? (withPosition.reduce((sum, r) => sum + r.position_in_list, 0) / withPosition.length).toFixed(1)
            : '-';

        // Sentiment distribution (only for mentioned responses)
        const mentionedResponses = responses.filter(r => r.brand_mentioned);
        const positive = mentionedResponses.filter(r => r.sentiment === 'positive').length;
        const positiveRate = mentionedResponses.length > 0 
            ? ((positive / mentionedResponses.length) * 100).toFixed(0) 
            : 0;

        // Best LLM (highest mention rate)
        const llmStats = {};
        responses.forEach(r => {
            if (!llmStats[r.llm_provider]) {
                llmStats[r.llm_provider] = { total: 0, mentioned: 0 };
            }
            llmStats[r.llm_provider].total++;
            if (r.brand_mentioned) llmStats[r.llm_provider].mentioned++;
        });

        let bestLLM = '-';
        let bestRate = 0;
        Object.entries(llmStats).forEach(([llm, stats]) => {
            const rate = stats.total > 0 ? (stats.mentioned / stats.total) : 0;
            if (rate > bestRate) {
                bestRate = rate;
                bestLLM = this.getLLMDisplayName(llm);
            }
        });

        // Update DOM
        document.getElementById('statTotalResponses').textContent = total;
        document.getElementById('statMentionRate').textContent = `${mentionRate}%`;
        document.getElementById('statAvgPosition').textContent = avgPosition !== '-' ? `#${avgPosition}` : '-';
        document.getElementById('statPositiveRate').textContent = `${positiveRate}%`;
        document.getElementById('statTopLLM').textContent = bestLLM;
    },

updateCompareView() {
        const select = document.getElementById('comparePromptSelect');
        const grid = document.getElementById('compareGrid');
        
        if (!select || !grid || !this.comparePrompts) return;

        const selectedIndex = Number.parseInt(select.value, 10);
        const selectedPrompt = this.comparePrompts[selectedIndex];
        if (!selectedPrompt) {
            grid.innerHTML = `
                <div class="empty-state" style="padding: 40px; text-align: center;">
                    <i class="fas fa-inbox"></i>
                    <h4>No prompt selected</h4>
                </div>
            `;
            return;
        }
        const responses = this.allResponses.filter(r => r.query_text === selectedPrompt);

        // Get responses by LLM (most recent for each)
        const configuredLlms = this.orderLlms(this.compareLlms || []);
        const llmsFromData = this.orderLlms(
            [...new Set(responses.map((r) => r.llm_provider).filter(Boolean))]
        );
        const llms = configuredLlms.length > 0 ? configuredLlms : llmsFromData;
        if (llms.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="padding: 40px; text-align: center;">
                    <i class="fas fa-inbox"></i>
                    <h4>No LLM responses found</h4>
                </div>
            `;
            return;
        }
        const responsesByLLM = {};
        
        llms.forEach(llm => {
            const llmResponses = responses.filter(r => r.llm_provider === llm);
            // Sort by date descending and get most recent
            llmResponses.sort((a, b) => new Date(b.analysis_date) - new Date(a.analysis_date));
            responsesByLLM[llm] = llmResponses[0] || null;
        });

        // Render comparison grid
        grid.innerHTML = llms.map(llm => {
            const response = responsesByLLM[llm];
            const llmName = this.getLLMDisplayName(llm);

            if (!response) {
                return `
                    <div class="compare-column">
                        <div class="compare-column-header ${llm}">
                            <span class="llm-name">${llmName}</span>
                        </div>
                        <div class="compare-column-body no-response">
                            <span>No response available</span>
                        </div>
                    </div>
                `;
            }

            // Format response text with markdown and highlighting
            const formattedText = this.formatCompareResponseWithHighlights(response.full_response || '', response);

            // Determine badge styles based on mention and position
            const mentionClass = response.brand_mentioned ? 'badge-success' : 'badge-danger';
            const positionClass = response.position_in_list <= 3 ? 'badge-gold' : 
                                  response.position_in_list <= 10 ? 'badge-silver' : 'badge-default';

            return `
                <div class="compare-column">
                    <div class="compare-column-header ${llm}">
                        <span class="llm-name">${llmName}</span>
                        <div class="llm-badges">
                            <span class="mini-badge ${mentionClass}" title="${response.brand_mentioned ? 'Tu marca fue mencionada' : 'Tu marca NO fue mencionada'}">${response.brand_mentioned ? '✓' : '✗'}</span>
                            ${response.position_in_list ? `<span class="mini-badge ${positionClass}" title="Posición #${response.position_in_list} en la lista">#${response.position_in_list}</span>` : ''}
                        </div>
                    </div>
                    <div class="compare-column-body">
                        ${formattedText}
                    </div>
                    <div class="compare-column-footer">
                        <span class="mini-stat">
                            <i class="fas fa-calendar"></i>
                            ${this.formatDate(response.analysis_date)}
                        </span>
                        <span class="mini-stat">
                            <i class="fas fa-align-left"></i>
                            ${response.response_length || 0} chars
                        </span>
                        ${response.sentiment ? `
                            <span class="mini-stat">
                                <i class="fas fa-${response.sentiment === 'positive' ? 'smile' : response.sentiment === 'negative' ? 'frown' : 'meh'}"></i>
                                ${response.sentiment}
                            </span>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    },

getSummaryText(response) {
        if (!response.full_response) {
            return '<em style="color: #9ca3af;">No response text available</em>';
        }

        const maxLength = 200;
        const text = response.full_response.replace(/[*#\[\]]/g, '').trim();

        if (text.length <= maxLength) {
            return this.escapeHtml(text);
        }

        return this.escapeHtml(text.substring(0, maxLength)) + '...';
    },

normalizeDomainInput(rawDomain) {
        const value = String(rawDomain || '').trim().toLowerCase();
        if (!value) return '';

        try {
            const normalizedUrl = this.toNavigableUrl(value);
            const parsed = new URL(normalizedUrl);
            return (parsed.hostname || '')
                .toLowerCase()
                .replace(/^www\./, '')
                .split(':')[0]
                .trim();
        } catch (e) {
            return value
                .replace(/^https?:\/\//, '')
                .split('/')[0]
                .split(':')[0]
                .replace(/^www\./, '')
                .trim();
        }
    },

extractNormalizedHost(rawUrl) {
        const urlValue = String(rawUrl || '').trim();
        if (!urlValue) return '';

        try {
            const normalizedUrl = this.toNavigableUrl(urlValue);
            const urlObj = new URL(normalizedUrl);
            return (urlObj.hostname || '')
                .toLowerCase()
                .replace(/^www\./, '')
                .split(':')[0]
                .trim();
        } catch (e) {
            return '';
        }
    },

toggleDomainsView(showDomains) {
        if (!this.allLLMUrls || this.allLLMUrls.length === 0) {
            console.warn('⚠️ No URLs data available');
            this._topUrlsLLMState = { page: 1, totalPages: 1, fullList: [], isDomainView: false };
            this.showNoUrlsLLMMessage();
            this.renderTopUrlsLLMPaginator();
            return;
        }

        if (showDomains) {
            console.log('🏢 Switching to Domains view...');

            // Aggregate URLs by domain
            const domainsData = this.aggregateUrlsByDomain(this.allLLMUrls);

            // Apply pagination
            const pageSize = 10;
            const state = { page: 1 };
            const totalPages = Math.max(1, Math.ceil(domainsData.length / pageSize));
            const paged = domainsData.slice(0, pageSize);

            this._topUrlsLLMState = { page: state.page, totalPages, fullList: domainsData, isDomainView: true };

            // Update table header for domains view
            this.updateTableHeaderForDomains();

            // Render domains table
            this.renderTopDomainsRankingLLM(paged);
            this.renderTopUrlsLLMPaginator();
        } else {
            console.log('🔗 Switching back to URLs view...');

            // Restore URLs view
            const pageSize = 10;
            const state = { page: 1 };
            const totalPages = Math.max(1, Math.ceil(this.allLLMUrls.length / pageSize));
            const paged = this.allLLMUrls.slice(0, pageSize);

            this._topUrlsLLMState = { page: state.page, totalPages, fullList: this.allLLMUrls, isDomainView: false };

            // Update table header for URLs view
            this.updateTableHeaderForUrls();

            // Render URLs table
            this.renderTopUrlsRankingLLM(paged);
            this.renderTopUrlsLLMPaginator();
        }
    },

updateTableHeaderForDomains() {
        const thead = document.querySelector('#topUrlsLLMTable thead');
        if (!thead) return;

        thead.innerHTML = `
            <tr>
                <th style="width: 60px;">#</th>
                <th style="width: 45%;">Domain</th>
                <th style="width: 100px;">URLs</th>
                <th style="width: 120px;">Total Mentions</th>
                <th style="width: 120px;">% of Total</th>
            </tr>
        `;
    },

renderTopDomainsRankingLLM(domains) {
        const tableBody = document.getElementById('topUrlsLLMBody');
        const noUrlsMessage = document.getElementById('noUrlsLLMMessage');
        const topUrlsTable = document.getElementById('topUrlsLLMTable');

        if (!domains || domains.length === 0) {
            this.showNoUrlsLLMMessage();
            return;
        }

        // Show table, hide message
        noUrlsMessage.style.display = 'none';
        topUrlsTable.style.display = 'table';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Get project info for highlighting
        let projectDomain = '';
        let competitorDomains = [];

        if (this.currentProject) {
            projectDomain = this.normalizeDomainInput(this.currentProject.brand_domain);

            // Normalize competitor domains
            const competitors = this.currentProject.selected_competitors || [];
            competitorDomains = competitors.map(c => {
                const domain = typeof c === 'object' ? (c.domain || c.competitor_domain || c) : c;
                return this.normalizeDomainInput(domain);
            }).filter(d => d && d.length > 0);
        }

        // Render each domain row
        domains.forEach((domainData, index) => {
            const domain = domainData.domain;

            // Determine if it's project or competitor domain
            let domainType = 'other';
            if (projectDomain && (domain === projectDomain || domain.endsWith('.' + projectDomain))) {
                domainType = 'project';
            } else if (competitorDomains.some(comp => domain === comp || domain.endsWith('.' + comp))) {
                domainType = 'competitor';
            }

            const domainTypeClass = domainType === 'project' ? 'table' : domainType;
            const rowClass = `url-row ${domainTypeClass}-domain`;

            // Create domain badge if needed
            let domainBadge = '';
            if (domainType === 'project') {
                domainBadge = '<span class="domain-badge project">Your Domain</span>';
            } else if (domainType === 'competitor') {
                domainBadge = '<span class="domain-badge competitor">Competitor</span>';
            }

            // Get logo URL - Logo.dev replaces deprecated Clearbit API (shutdown Dec 2025)
            const logoUrl = `https://img.logo.dev/${domain}?token=pk_a4PP_KI7Qj-y6MnQSvu-3A&size=64&format=png`;
            const fallbackUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;

            const row = document.createElement('tr');
            row.className = rowClass;
            row.innerHTML = `
                <td class="rank-cell">${domainData.rank}</td>
                <td class="url-cell">
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <img src="${logoUrl}" alt="${this.escapeHtml(domain)}" 
                             style="width: 24px; height: 24px; border-radius: 4px; flex-shrink: 0;"
                             onerror="this.onerror=null; this.src='${fallbackUrl}'">
                        <div style="flex: 1; min-width: 0;">
                            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                                <a href="https://${this.escapeHtml(domain)}" target="_blank" rel="noopener noreferrer" 
                                   class="url-link" style="font-weight: 500;">
                                    ${this.escapeHtml(domain)}
                                    <i class="fas fa-external-link-alt"></i>
                                </a>
                                ${domainBadge}
                            </div>
                        </div>
                    </div>
                </td>
                <td class="mentions-cell" style="text-align: center;">${domainData.urlCount}</td>
                <td class="mentions-cell">${domainData.totalMentions}</td>
                <td class="percentage-cell">${domainData.percentage.toFixed(1)}%</td>
            `;

            tableBody.appendChild(row);
        });

        console.log(`✅ Rendered ${domains.length} domain rows with highlighting`);
    }

});
