/**
 * LLM Monitoring - métodos de prototipo: queries
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

isQueryBranded(queryText) {
        const keywords = this.currentProject?.brand_keywords || [];
        if (!keywords.length || !queryText) return false;
        const normalize = s => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        const textNorm = normalize(queryText);
        for (const kw of keywords) {
            const kwNorm = normalize(kw);
            const escaped = kwNorm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            try {
                if (new RegExp('\\b' + escaped + '\\b', 'i').test(textNorm)) return true;
            } catch (e) {
                if (textNorm.includes(kwNorm)) return true;
            }
        }
        return false;
    },

async loadQueriesTable(projectId) {
        console.log(`📝 Loading queries table for project ${projectId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/queries?days=${this.globalTimeRange}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || 'Failed to load queries');
            }

            console.log(`✅ Loaded ${result.queries.length} queries`);
            this.renderQueriesTable(result.queries);

        } catch (error) {
            console.error('❌ Error loading queries:', error);
            const container = document.getElementById('queriesTable');
            if (container) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 2rem; color: #ef4444;">
                        <i class="fas fa-exclamation-triangle" style="font-size: 2rem; opacity: 0.5; margin-bottom: 1rem;"></i>
                        <p>Error loading queries table</p>
                    </div>
                `;
            }
        }
    },

renderQueriesTable(queries) {
        const container = document.getElementById('queriesTable');
        if (!container) return;

        // Destroy existing grid
        if (this.queriesGrid) {
            this.queriesGrid.destroy();
        }

        // Si no hay queries, mostrar mensaje
        if (!queries || queries.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: #6b7280;">
                    <i class="fas fa-list-ul" style="font-size: 3rem; opacity: 0.3; margin-bottom: 1rem; display: block;"></i>
                    <p style="font-size: 1rem; font-weight: 500;">No queries found</p>
                    <p style="font-size: 0.875rem; margin-top: 0.5rem;">Run analysis to see query results</p>
                </div>
            `;
            return;
        }

        // ✨ NUEVO: Guardar queries data para acceso en acordeón
        this.queriesData = queries;
        this.expandedRows = new Set(); // Track expanded rows

        // Formatear datos para la tabla
        const rows = queries.map((q, idx) => {
            const visibilityPct = q.visibility_pct != null ? q.visibility_pct : 0;
            const visibilityStr = visibilityPct.toFixed(1);

            // ✨ NUEVO: Botón que abre modal con análisis detallado
            const viewDetailsBtn = gridjs.html(`
                <button 
                    class="view-details-btn" 
                    data-row-idx="${idx}"
                    title="View detailed analysis"
                    style="
                        background: linear-gradient(135deg, #D8F9B8 0%, #a8e063 100%);
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        padding: 0.35rem 0.7rem;
                        color: #1a1a1a;
                        font-size: 0.75rem;
                        font-weight: 600;
                        transition: all 0.2s;
                        box-shadow: 0 2px 4px rgba(216, 249, 184, 0.2);
                        white-space: nowrap;
                    "
                    onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 8px rgba(216, 249, 184, 0.3)'"
                    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(216, 249, 184, 0.2)'"
                >Details</button>
            `);

            return [
                viewDetailsBtn,  // ✨ NUEVO: Botón para ver detalles
                q.prompt,
                q.country,
                q.language ? q.language.toUpperCase() : 'N/A',
                q.total_mentions || 0,
                // Visibility con barra de progreso
                gridjs.html(`
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="flex: 1; background: #e5e7eb; border-radius: 9999px; height: 8px; overflow: hidden;">
                            <div style="height: 100%; background: linear-gradient(90deg, #22c55e ${visibilityPct}%, transparent ${visibilityPct}%); width: 100%; border-radius: 9999px;"></div>
                        </div>
                        <span style="font-weight: 600; min-width: 45px;">${visibilityStr}%</span>
                    </div>
                `)
            ];
        });

        // Create grid
        this.queriesGrid = new gridjs.Grid({
            columns: [
                { id: 'expand', name: '', width: '90px', sort: false },  // ✨ Columna para botón Details
                { id: 'prompt', name: 'Prompt', width: '45%' },
                { id: 'country', name: 'Country', width: '80px' },
                { id: 'language', name: 'Language', width: '80px' },
                { id: 'mentions', name: `Total Mentions (${this.globalTimeRange}d)`, width: '130px', sort: true },
                { id: 'visibility', name: `Avg Visibility % (${this.globalTimeRange}d)`, width: '150px', sort: true }
            ],
            data: rows,
            sort: true,
            search: {
                placeholder: 'Search prompts...'
            },
            pagination: {
                limit: 10,
                summary: true
            },
            style: {
                table: {
                    'font-size': '14px'
                },
                th: {
                    'background-color': '#161616',
                    'color': '#D8F9B8',
                    'font-weight': '700',
                    'padding': '1rem'
                },
                td: {
                    'padding': '0.875rem'
                }
            },
            className: {
                table: 'llm-queries-table'
            }
        }).render(container);

        // Use delegated click handling so "Details" keeps working after pagination/sort/search re-renders.
        this.bindDetailButtonsDelegation(container);
    },

buildQuickSuggestions(languageCode, brandName, industry, competitorName, mode = 'default') {
        const catalog = {
            es: {
                default: [
                    `¿Qué es ${brandName}?`,
                    `Mejores herramientas de ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Opiniones de ${brandName}`,
                    `¿Cómo funciona ${brandName}?`,
                    `Alternativas a ${brandName}`
                ],
                variation: [
                    `¿Qué es ${brandName} y cómo funciona?`,
                    `Mejores alternativas a ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `¿Vale la pena ${brandName}?`,
                    `Cómo usar ${brandName}`,
                    `Precios de ${brandName}`
                ]
            },
            it: {
                default: [
                    `Cos'è ${brandName}?`,
                    `I migliori strumenti di ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Recensioni su ${brandName}`,
                    `Come funziona ${brandName}?`,
                    `Alternative a ${brandName}`
                ],
                variation: [
                    `Cos'è ${brandName} e come funziona?`,
                    `Migliori alternative a ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} vale la pena?`,
                    `Come usare ${brandName}`,
                    `Prezzi di ${brandName}`
                ]
            },
            fr: {
                default: [
                    `Qu'est-ce que ${brandName} ?`,
                    `Meilleurs outils de ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Avis sur ${brandName}`,
                    `Comment fonctionne ${brandName} ?`,
                    `Alternatives à ${brandName}`
                ],
                variation: [
                    `Qu'est-ce que ${brandName} et comment ça marche ?`,
                    `Meilleures alternatives à ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} vaut-il le coup ?`,
                    `Comment utiliser ${brandName}`,
                    `Tarifs de ${brandName}`
                ]
            },
            de: {
                default: [
                    `Was ist ${brandName}?`,
                    `Beste ${industry}-Tools`,
                    `${brandName} vs ${competitorName}`,
                    `Bewertungen zu ${brandName}`,
                    `Wie funktioniert ${brandName}?`,
                    `Alternativen zu ${brandName}`
                ],
                variation: [
                    `Was ist ${brandName} und wie funktioniert es?`,
                    `Beste Alternativen zu ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `Lohnt sich ${brandName}?`,
                    `Wie nutzt man ${brandName}?`,
                    `${brandName} Preise`
                ]
            },
            pt: {
                default: [
                    `O que é ${brandName}?`,
                    `Melhores ferramentas de ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Avaliações de ${brandName}`,
                    `Como funciona ${brandName}?`,
                    `Alternativas ao ${brandName}`
                ],
                variation: [
                    `O que é ${brandName} e como funciona?`,
                    `Melhores alternativas ao ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} vale a pena?`,
                    `Como usar ${brandName}`,
                    `Preços do ${brandName}`
                ]
            },
            en: {
                default: [
                    `What is ${brandName}?`,
                    `Best ${industry} tools`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} reviews`,
                    `How does ${brandName} work?`,
                    `Alternatives to ${brandName}`
                ],
                variation: [
                    `What is ${brandName} and how does it work?`,
                    `Best alternatives to ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `Is ${brandName} worth it?`,
                    `How to use ${brandName}`,
                    `${brandName} pricing and plans`
                ]
            }
        };

        const locale = catalog[languageCode] || catalog.en;
        return mode === 'variation' ? locale.variation : locale.default;
    },

async loadQuickSuggestions(forceRefresh = false) {
        const listEl = document.getElementById('quickSuggestionsList');
        const emptyEl = document.getElementById('quickSuggestionsEmpty');
        const sectionEl = document.getElementById('quickSuggestionsSection');

        if (!listEl || !this.currentProject) {
            console.warn('[Suggestions] Missing listEl or currentProject, rendering local fallback');
            this._renderLocalFallbackSuggestions();
            return;
        }

        // Show loading
        listEl.innerHTML = `
            <div class="suggestions-loading-inline">
                <i class="fas fa-spinner fa-spin"></i>
                <span>Generating suggestions...</span>
            </div>
        `;
        if (emptyEl) emptyEl.style.display = 'none';
        if (sectionEl) sectionEl.style.display = 'block';

        // Prepare project context
        const existingPrompts = this.allPrompts || [];
        const languageCode = this.getProjectLanguageCode();
        const brandName = this.currentProject.brand_name || 'your brand';
        const industry = this.currentProject.industry || 'your industry';
        const competitorName = this.getPrimaryCompetitorName(languageCode);
        const mode = existingPrompts.length > 0 ? 'variation' : 'default';
        const cacheKey = existingPrompts.length === 0
            ? `bootstrap:${this.currentProject.id}:${languageCode}`
            : `variation:${this.currentProject.id}:${languageCode}:${existingPrompts.length}`;

        // Check cache first
        if (!forceRefresh && this.quickSuggestionsCache.has(cacheKey)) {
            this.renderQuickSuggestions(this.quickSuggestionsCache.get(cacheKey));
            return;
        }

        // Attempt to fetch AI-generated suggestions with a timeout
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 8000); // 8s timeout

            const body = existingPrompts.length === 0
                ? { existing_prompts: [], count: 6 }
                : { existing_prompts: existingPrompts.slice(0, 5).map(p => p.prompt), count: 6 };

            const response = await fetch(
                `${this.baseUrl}/projects/${this.currentProject.id}/queries/suggest-variations`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                    signal: controller.signal
                }
            );
            clearTimeout(timeoutId);

            if (response.ok) {
                const data = await response.json();
                if (data.success && Array.isArray(data.suggestions) && data.suggestions.length > 0) {
                    this.quickSuggestionsCache.set(cacheKey, data.suggestions);
                    this.renderQuickSuggestions(data.suggestions);
                    return;
                }
            }
        } catch (err) {
            // AbortError = timeout, any other = network / parse error
            console.warn('[Suggestions] API fetch failed, using local fallback:', err.name === 'AbortError' ? 'timeout' : err.message);
        }

        // Fallback: always render local suggestions so the spinner never hangs
        const localSuggestions = this.buildQuickSuggestions(languageCode, brandName, industry, competitorName, mode);
        this.quickSuggestionsCache.set(cacheKey, localSuggestions);
        this.renderQuickSuggestions(localSuggestions);
    },

_renderLocalFallbackSuggestions() {
        const listEl = document.getElementById('quickSuggestionsList');
        if (!listEl) return;
        const brandName = this.currentProject?.brand_name || 'your brand';
        const industry = this.currentProject?.industry || 'your industry';
        const languageCode = this.getProjectLanguageCode ? this.getProjectLanguageCode() : 'en';
        const competitorName = this.getPrimaryCompetitorName ? this.getPrimaryCompetitorName(languageCode) : 'competitors';
        this.renderQuickSuggestions(
            this.buildQuickSuggestions(languageCode, brandName, industry, competitorName, 'default')
        );
    },

generateLocalSuggestions(existingPrompts) {
        const brandName = this.currentProject?.brand_name || 'the brand';
        const industry = this.currentProject?.industry || 'your industry';
        const languageCode = this.getProjectLanguageCode();
        const competitorName = this.getPrimaryCompetitorName(languageCode);

        this.renderQuickSuggestions(
            this.buildQuickSuggestions(languageCode, brandName, industry, competitorName, 'variation')
        );
    },

renderQuickSuggestions(suggestions) {
        const listEl = document.getElementById('quickSuggestionsList');
        if (!listEl) return;
        
        if (!suggestions || suggestions.length === 0) {
            listEl.innerHTML = '<span class="quick-suggestions-empty">No suggestions available</span>';
            return;
        }
        
        // Filter out duplicates with existing prompts
        const existingTexts = (this.allPrompts || []).map(p => p.prompt.toLowerCase().trim());
        const uniqueSuggestions = suggestions.filter(s => 
            !existingTexts.includes(s.toLowerCase().trim())
        ).slice(0, 6);
        
        if (uniqueSuggestions.length === 0) {
            listEl.innerHTML = '<span class="quick-suggestions-empty">All suggestions already added</span>';
            return;
        }
        
        let html = '';
        uniqueSuggestions.forEach((suggestion, idx) => {
            const truncated = suggestion.length > 50 ? suggestion.substring(0, 47) + '...' : suggestion;
            html += `
                <div class="suggestion-chip" onclick="window.llmMonitoring.addSuggestionToTextarea('${this.escapeHtml(suggestion).replace(/'/g, "\\'")}')">
                    <span class="chip-text" title="${this.escapeHtml(suggestion)}">${this.escapeHtml(truncated)}</span>
                    <i class="fas fa-plus chip-add-icon"></i>
                </div>
            `;
        });
        
        listEl.innerHTML = html;
    },

addSuggestionToTextarea(suggestion) {
        const textarea = document.getElementById('promptsInput');
        if (!textarea) return;
        
        const currentValue = textarea.value.trim();
        if (currentValue) {
            textarea.value = currentValue + '\n' + suggestion;
        } else {
            textarea.value = suggestion;
        }
        
        // Update counter
        this.updatePromptsCounter();
        
        // Remove the chip that was clicked (visual feedback)
        // The chip will be regenerated on refresh
        textarea.focus();
    },

refreshQuickSuggestions() {
        const btn = document.querySelector('.refresh-suggestions-btn');
        if (btn) {
            btn.classList.add('loading');
            setTimeout(() => btn.classList.remove('loading'), 1000);
        }
        this.loadQuickSuggestions(true);
    },

async showSuggestionsModal() {
        console.log('🤖 Mostrando modal de sugerencias IA...');

        if (!this.currentProject || !this.currentProject.id) {
            this.showError('No project selected');
            return;
        }

        const modal = document.getElementById('suggestionsModal');
        if (!modal) return;

        // Show modal
        modal.style.display = 'flex';
        setTimeout(() => {
            modal.classList.add('active');
        }, 10);

        // Reset states
        document.getElementById('suggestionsLoading').style.display = 'flex';
        document.getElementById('suggestionsList').style.display = 'none';
        document.getElementById('suggestionsError').style.display = 'none';

        // Get suggestions from AI
        await this.getSuggestions();
    },

hideSuggestionsModal() {
        const modal = document.getElementById('suggestionsModal');
        if (!modal) return;

        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    },

async getSuggestions() {
        console.log('🤖 Solicitando sugerencias a la IA...');

        if (!this.currentProject || !this.currentProject.id) {
            return;
        }

        try {
            // Create timeout promise (30 seconds)
            const timeoutPromise = new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Request timeout - Gemini está tardando demasiado. Intenta de nuevo.')), 30000)
            );

            // Create fetch promise
            const fetchPromise = fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries/suggest`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    count: 10
                })
            });

            // Race between fetch and timeout
            const response = await Promise.race([fetchPromise, timeoutPromise]);

            console.log(`📡 Response status: ${response.status}`);

            if (!response.ok) {
                const error = await response.json();
                console.error('❌ Error response:', error);
                throw new Error(error.error || error.hint || `HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Recibidas ${data.suggestions.length} sugerencias de IA`);

            // Hide loading, show suggestions
            document.getElementById('suggestionsLoading').style.display = 'none';
            document.getElementById('suggestionsList').style.display = 'block';
            document.getElementById('suggestionsError').style.display = 'none';

            // Render suggestions
            this.renderSuggestions(data.suggestions);

        } catch (error) {
            console.error('❌ Error obteniendo sugerencias:', error);
            console.error('❌ Error stack:', error.stack);

            // Show error state
            document.getElementById('suggestionsLoading').style.display = 'none';
            document.getElementById('suggestionsList').style.display = 'none';
            document.getElementById('suggestionsError').style.display = 'flex';
            document.getElementById('suggestionsErrorText').textContent = error.message || 'Error generating suggestions';
        }
    },

renderSuggestions(suggestions) {
        const container = document.getElementById('suggestionsContainer');
        if (!container) return;

        container.innerHTML = '';

        if (suggestions.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="padding: 40px;">
                    <p>No suggestions generated. Try again.</p>
                </div>
            `;
            return;
        }

        suggestions.forEach((suggestion, index) => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.innerHTML = `
                <label class="suggestion-label">
                    <input type="checkbox" class="suggestion-checkbox" data-index="${index}" data-text="${this.escapeHtml(suggestion)}">
                    <span class="suggestion-text">${this.escapeHtml(suggestion)}</span>
                    <span class="suggestion-badge">
                        <i class="fas fa-magic"></i>
                        AI
                    </span>
                </label>
            `;
            container.appendChild(item);
        });

        // Update counter
        this.updateSuggestionsCounter();

        // Add change event listeners
        const checkboxes = container.querySelectorAll('.suggestion-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateSuggestionsCounter();
            });
        });
    },

updateSuggestionsCounter() {
        const checkboxes = document.querySelectorAll('.suggestion-checkbox:checked');
        const count = checkboxes.length;
        const btnText = document.getElementById('btnAddSuggestionsText');

        if (btnText) {
            btnText.textContent = `Add Selected (${count})`;
        }
    },

selectAllSuggestions() {
        const checkboxes = document.querySelectorAll('.suggestion-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
        this.updateSuggestionsCounter();
    },

deselectAllSuggestions() {
        const checkboxes = document.querySelectorAll('.suggestion-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updateSuggestionsCounter();
    },

async addSelectedSuggestions() {
        console.log('💾 Añadiendo sugerencias seleccionadas...');

        if (!this.currentProject || !this.currentProject.id) {
            return;
        }

        // Get selected suggestions
        const checkboxes = document.querySelectorAll('.suggestion-checkbox:checked');

        if (checkboxes.length === 0) {
            this.showError('Please select at least one suggestion');
            return;
        }

        const selectedQueries = Array.from(checkboxes).map(cb => cb.dataset.text);

        console.log(`📝 Añadiendo ${selectedQueries.length} sugerencias...`);

        // Prepare payload
        const payload = {
            queries: selectedQueries,
            query_type: 'general'  // Las sugerencias de IA se marcan como 'general'
        };

        // Show loading
        const btn = document.getElementById('btnAddSelectedSuggestions');
        const btnText = document.getElementById('btnAddSuggestionsText');
        const originalText = btnText.textContent;

        btnText.textContent = 'Adding...';
        btn.disabled = true;

        try {
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            const data = await response.json();

            console.log(`✅ Añadidas ${data.added_count} sugerencias`);

            // Hide modal
            this.hideSuggestionsModal();

            // Reload prompts
            await this.refreshPromptViews();

            // Keep query filter synced after adding suggestions
            await this.populateQueryFilter();

            // Refresh project cards so CTA state stays in sync
            await this.refreshProjectsListIfVisible();

            // Show success
            let message = `${data.added_count} AI suggestions added successfully!`;
            if (data.duplicate_count > 0) {
                message += ` (${data.duplicate_count} were duplicates)`;
            }
            this.showSuccess(message);

        } catch (error) {
            console.error('❌ Error añadiendo sugerencias:', error);
            this.showError(error.message || 'Failed to add suggestions');
        } finally {
            btnText.textContent = originalText;
            btn.disabled = false;
        }
    },

async populateQueryFilter() {
        const select = document.getElementById('responsesQueryFilter');
        if (!select || !this.currentProject?.id) return;

        // Save current selection
        const currentSelection = select.value;

        // Clear all options except the default "All Prompts"
        while (select.options.length > 1) {
            select.remove(1);
        }

        try {
            // Fetch queries for the project based on global time range
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries?days=${this.globalTimeRange}`);
            if (!response.ok) {
                console.warn('Could not load queries for filter');
                return;
            }

            const data = await response.json();
            if (!data.success || !data.queries || data.queries.length === 0) {
                console.warn('No queries available for filter');
                return;
            }

            // Sort queries by last update (most recent first)
            const sortedQueries = data.queries.sort((a, b) => {
                const dateA = new Date(a.last_update || a.created_at || 0);
                const dateB = new Date(b.last_update || b.created_at || 0);
                return dateB - dateA;
            });

            // Add all queries to dropdown
            sortedQueries.forEach(query => {
                const option = document.createElement('option');
                option.value = query.id;
                option.textContent = query.prompt.length > 60 ? query.prompt.substring(0, 60) + '...' : query.prompt;
                select.appendChild(option);
            });

            // Restore previous selection if it still exists
            if (currentSelection && select.querySelector(`option[value="${currentSelection}"]`)) {
                select.value = currentSelection;
            }

            console.log(`✅ Loaded ${sortedQueries.length} prompts into filter dropdown`);
        } catch (error) {
            console.error('❌ Error populating query filter:', error);
        }
    }

});
