/**
 * LLM Monitoring - métodos de prototipo: responses
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

async handlePaywallResponse(response) {
        if (response.status !== 402) return false;
        let data = {};
        try {
            data = await response.json();
        } catch (e) {
            data = {};
        }
        if (window.showPaywall) {
            window.showPaywall('LLM Monitoring', data.upgrade_options || ['basic', 'premium', 'business']);
        }
        throw new Error(data.message || 'LLM Monitoring requires a paid plan.');
    },

async loadResponses() {
        const projectId = this.currentProject?.id;
        if (!projectId) {
            this.showError('No project selected');
            return;
        }

        const queryFilter = document.getElementById('responsesQueryFilter')?.value || '';
        const enabledLlms = this.getProjectEnabledLlms();
        const llmFilterSelect = document.getElementById('responsesLLMFilter');
        let llmFilter = llmFilterSelect?.value || '';
        if (llmFilter && !enabledLlms.includes(llmFilter)) {
            llmFilter = '';
            if (llmFilterSelect) llmFilterSelect.value = '';
        }
        const daysFilter = this.globalTimeRange; // ✨ Use global time range
        const container = document.getElementById('responsesContainer');

        if (!container) return;

        // Show loading
        container.innerHTML = `
            <div class="loading-state" style="padding: 40px; text-align: center;">
                <div class="spinner"></div>
                <p>Loading LLM responses...</p>
            </div>
        `;

        try {
            // ✨ NEW: optional cluster filter (server-side)
            const clusterFilter = document.getElementById('responsesClusterFilter')?.value || '';
            let url = `${this.baseUrl}/projects/${projectId}/responses?days=${daysFilter}`;
            if (queryFilter) url += `&query_id=${queryFilter}`;
            if (llmFilter) url += `&llm_provider=${llmFilter}`;
            if (clusterFilter) url += `&cluster=${encodeURIComponent(clusterFilter)}`;

            // Populate the cluster filter dropdown lazily if the project has clusters
            if (!this._responsesClusterFilterBound) {
                this.populateResponsesClusterFilter();
                this._responsesClusterFilterBound = true;
                const sel = document.getElementById('responsesClusterFilter');
                if (sel && !sel.dataset.bound) {
                    sel.dataset.bound = '1';
                    sel.addEventListener('change', () => this.loadResponses());
                }
            }

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log(`✅ Loaded ${data.responses.length} responses`);
            this.responsesLoaded = true;

            if (data.responses.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-inbox"></i>
                        <h4>No responses found</h4>
                        <p>Try changing the filters or run an analysis first</p>
                    </div>
                `;
                this.showResponsesButtons(false);
                const statsContainer = document.getElementById('responsesQuickStats');
                if (statsContainer) statsContainer.style.display = 'none';
                return;
            }

            // ✨ NEW: Store all responses and reset pagination
            this.allResponses = data.responses;
            this.filteredResponses = null; // Reset filtered responses
            this.currentDisplayResponses = data.responses; // ✨ NUEVO: Inicializar array de display
            this.currentResponsesShown = this.responsesPerPage;

            // ✨ Reset client-side filters when loading new data
            const mentionFilter = document.getElementById('responsesMentionFilter');
            const sentimentFilter = document.getElementById('responsesSentimentFilter');
            if (mentionFilter) mentionFilter.value = '';
            if (sentimentFilter) sentimentFilter.value = '';

            // Populate query filter dropdown with ALL queries from project
            await this.populateQueryFilter();

            // Render responses with pagination
            this.renderResponsesPaginated(container);

        } catch (error) {
            console.error('❌ Error loading responses:', error);
            this.responsesLoaded = false;
            container.innerHTML = `
                <div class="empty-state" style="color: #ef4444;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h4>Error loading responses</h4>
                    <p>${error.message}</p>
                </div>
            `;
            this.showResponsesButtons(false);
            const statsContainer = document.getElementById('responsesQuickStats');
            if (statsContainer) statsContainer.style.display = 'none';
        }
    },

getDisplayResponses() {
        const mentionFilter = document.getElementById('responsesMentionFilter')?.value || '';
        const sentimentFilter = document.getElementById('responsesSentimentFilter')?.value || '';
        const queryTypeFilter = document.getElementById('responsesQueryTypeFilter')?.value || '';

        // If no client-side filters active, return all responses
        if (!mentionFilter && !sentimentFilter && !queryTypeFilter) {
            return this.allResponses;
        }
        
        // Return filtered responses if available
        return this.filteredResponses || this.allResponses;
    },

renderResponsesPaginated(container) {
        if (!container) return;

        // Get responses to display (considering client-side filters)
        const displayResponses = this.getDisplayResponses();
        const totalResponses = displayResponses.length;

        // ✨ CORREGIDO: Guardar referencia al array actual para el modal
        // Esto asegura que showResponseModal use el mismo array que se muestra
        this.currentDisplayResponses = displayResponses;

        // Get subset of responses to show
        const responsesToShow = displayResponses.slice(0, this.currentResponsesShown);
        const hasMore = this.currentResponsesShown < totalResponses;
        const remaining = totalResponses - this.currentResponsesShown;

        // Clear container
        container.innerHTML = '';

        // Show empty state if no results after filtering
        if (totalResponses === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-filter"></i>
                    <h4>No responses match the current filters</h4>
                    <p>Try adjusting the Mention or Sentiment filters to see more results</p>
                </div>
            `;
            // Keep buttons visible but update stats to show 0
            this.updateQuickStats([]);
            return;
        }

        // Create responses wrapper
        const responsesWrapper = document.createElement('div');
        responsesWrapper.className = 'responses-list';
        // Pass startIndex as 0 since we're slicing from the beginning
        this.renderResponses(responsesToShow, responsesWrapper, 0);
        container.appendChild(responsesWrapper);

        // Add "Load More" button if there are more responses
        if (hasMore) {
            const loadMoreSection = document.createElement('div');
            loadMoreSection.className = 'load-more-section';
            loadMoreSection.innerHTML = `
                <button class="btn btn-ghost" onclick="window.llmMonitoring.loadMoreResponses()">
                    <i class="fas fa-chevron-down"></i>
                    Load ${Math.min(this.responsesPerPage, remaining)} More
                    <span style="color: #6b7280;">(${remaining} remaining)</span>
                </button>
            `;
            container.appendChild(loadMoreSection);
        }

        // Show total count (with filter info if applicable)
        const mentionFilter = document.getElementById('responsesMentionFilter')?.value || '';
        const sentimentFilter = document.getElementById('responsesSentimentFilter')?.value || '';
        const isFiltered = mentionFilter || sentimentFilter;
        
        const countSection = document.createElement('div');
        countSection.className = 'responses-count';
        countSection.innerHTML = `
            <small style="color: #6b7280;">
                <i class="fas fa-info-circle"></i>
                Showing ${responsesToShow.length} of ${totalResponses} responses${isFiltered ? ` (filtered from ${this.allResponses.length} total)` : ''}
            </small>
        `;
        container.insertBefore(countSection, container.firstChild);

        // ✨ NUEVO: Actualizar estadísticas rápidas y mostrar botones
        this.updateQuickStats(displayResponses);
        this.showResponsesButtons(true);
    },

loadMoreResponses() {
        this.currentResponsesShown += this.responsesPerPage;
        const container = document.getElementById('responsesContainer');
        if (container) {
            this.renderResponsesPaginated(container);
        }
    },

showResponsesButtons(show) {
        const exportBtn = document.getElementById('btnExportResponses');
        const compareBtn = document.getElementById('btnCompareResponses');
        if (exportBtn) exportBtn.style.display = show ? 'flex' : 'none';
        if (compareBtn) compareBtn.style.display = show ? 'flex' : 'none';
    },

exportResponsesToCSV() {
        const responses = this.currentDisplayResponses || this.allResponses;
        
        if (!responses || responses.length === 0) {
            this.showError('No responses to export');
            return;
        }

        // Define CSV headers
        const headers = [
            'Date',
            'LLM',
            'Model',
            'Prompt',
            'Brand Mentioned',
            'Position',
            'Sentiment',
            'Response Length',
            'Competitors Mentioned',
            'Full Response'
        ];

        // Build CSV rows
        const rows = responses.map(r => [
            r.analysis_date,
            this.getLLMDisplayName(r.llm_provider),
            r.model_used || 'N/A',
            `"${(r.query_text || '').replace(/"/g, '""')}"`,
            r.brand_mentioned ? 'Yes' : 'No',
            r.position_in_list || 'N/A',
            r.sentiment || 'N/A',
            r.response_length || 0,
            r.competitors_mentioned ? Object.keys(r.competitors_mentioned).join('; ') : '',
            `"${(r.full_response || '').replace(/"/g, '""').substring(0, 1000)}..."`
        ]);

        // Create CSV content
        const csvContent = [
            headers.join(','),
            ...rows.map(row => row.join(','))
        ].join('\n');

        // Create and trigger download
        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        const projectName = this.currentProject?.name || 'llm-responses';
        const timestamp = new Date().toISOString().split('T')[0];
        link.setAttribute('href', url);
        link.setAttribute('download', `${projectName}_responses_${timestamp}.csv`);
        link.style.display = 'none';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        console.log(`✅ Exported ${responses.length} responses to CSV`);
    },

formatCompareResponseWithHighlights(text, response) {
        if (!text) return '<em>No content</em>';

        // Get brand terms
        const brandKeywords = this.currentProject?.brand_keywords || [];
        const brandName = this.currentProject?.brand_name || '';
        const brandDomain = this.currentProject?.brand_domain || '';
        
        const brandTerms = [...brandKeywords];
        if (brandName) brandTerms.push(brandName);
        if (brandDomain) brandTerms.push(brandDomain.replace('www.', ''));

        // Get competitor terms
        const competitors = this.currentProject?.selected_competitors || [];
        const competitorTerms = [];
        competitors.forEach(comp => {
            if (comp.domain) competitorTerms.push(comp.domain.replace('www.', ''));
            if (comp.keywords) competitorTerms.push(...comp.keywords);
            if (comp.name) competitorTerms.push(comp.name);
        });

        // First, apply highlighting to raw text (before HTML escaping)
        // We'll use placeholder tokens to preserve highlights through HTML escaping
        let processedText = text;
        const highlights = [];
        let highlightIndex = 0;

        // Helper to create unique placeholder
        const createPlaceholder = (type, matchedText) => {
            const placeholder = `___HIGHLIGHT_${highlightIndex}_${type}___`;
            highlights.push({ placeholder, type, text: matchedText });
            highlightIndex++;
            return placeholder;
        };

        // First highlight competitors (to give brand priority in case of overlap)
        competitorTerms.forEach(term => {
            if (!term || term.length < 2) return;
            const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`\\b(${escapedTerm})\\b`, 'gi');
            processedText = processedText.replace(regex, (match) => createPlaceholder('competitor', match));
        });

        // Then highlight brand (will replace competitor highlights if term matches both)
        brandTerms.forEach(term => {
            if (!term || term.length < 2) return;
            const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`\\b(${escapedTerm})\\b`, 'gi');
            processedText = processedText.replace(regex, (match) => createPlaceholder('brand', match));
        });

        // Now apply HTML escaping
        let html = this.escapeHtml(processedText);

        // Restore highlights with proper HTML markup
        highlights.forEach(({ placeholder, type, text: matchedText }) => {
            const cssClass = type === 'brand' ? 'brand-mention' : 'competitor-mention';
            const escapedMatch = this.escapeHtml(matchedText);
            html = html.replace(placeholder, `<mark class="${cssClass}">${escapedMatch}</mark>`);
        });

        // Apply markdown formatting
        // Headers
        html = html.replace(/^### (.+)$/gm, '<strong style="font-size: 1.1em;">$1</strong><br>');
        html = html.replace(/^## (.+)$/gm, '<strong style="font-size: 1.15em;">$1</strong><br>');
        html = html.replace(/^# (.+)$/gm, '<strong style="font-size: 1.2em;">$1</strong><br>');
        
        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Lists
        html = html.replace(/^- (.+)$/gm, '• $1<br>');
        html = html.replace(/^\d+\. (.+)$/gm, '$&<br>');
        
        // Line breaks
        html = html.replace(/\n\n/g, '<br><br>');
        html = html.replace(/\n/g, '<br>');

        return html;
    },

renderResponses(responses, container, startIndex = 0) {
        let html = '';

        responses.forEach((response, relativeIndex) => {
            const globalIndex = startIndex + relativeIndex;
            const llmName = this.getLLMDisplayName(response.llm_provider);
            const isCollapsed = response.full_response && response.full_response.length > 500;

            html += `
                <div class="response-item">
                    <div class="response-header">
                        <div class="response-header-left">
                            <h4>
                                <span class="response-llm-badge ${response.llm_provider}">${llmName}</span>
                                ${this.escapeHtml(response.query_text)}
                            </h4>
                            <div class="response-meta">
                                <span class="response-meta-item">
                                    <i class="fas fa-calendar"></i>
                                    ${this.formatDate(response.analysis_date)}
                                </span>
                                <span class="response-meta-item">
                                    <i class="fas fa-robot"></i>
                                    ${this.escapeHtml(response.model_used || 'N/A')}
                                </span>
                                <span class="response-meta-item">
                                    <i class="fas fa-align-left"></i>
                                    ${response.response_length || 0} chars
                                </span>
                            </div>
                        </div>
                        <div class="response-status">
                            <span class="status-badge ${response.brand_mentioned ? 'mentioned' : 'not-mentioned'}">
                                ${response.brand_mentioned ? '✓ Mentioned' : '✗ Not Mentioned'}
                            </span>
                            ${response.sentiment ? `
                                <span class="status-badge ${response.sentiment}">
                                    ${response.sentiment.charAt(0).toUpperCase() + response.sentiment.slice(1)}
                                </span>
                            ` : ''}
                            ${response.position_in_list ? `
                                <span class="status-badge" style="background: #dbeafe; color: #1e40af;">
                                    Position #${response.position_in_list}
                                </span>
                            ` : ''}
                        </div>
                    </div>

                    <div class="response-body">
                        <div class="response-summary">
                            <p>${this.getSummaryText(response)}</p>
                            <button class="btn-view-full-response" onclick="window.llmMonitoring.showResponseModal(${globalIndex})">
                                <i class="fas fa-expand-alt"></i>
                                Show Full Response
                            </button>
                        </div>
                    </div>

                    ${response.mention_contexts && response.mention_contexts.length > 0 ? `
                        <div class="mention-contexts">
                            <h5>
                                <i class="fas fa-quote-left"></i>
                                Mention Contexts (${response.mention_contexts.length})
                            </h5>
                            ${response.mention_contexts.map(context => `
                                <div class="context-item">
                                    ${this.escapeHtml(context)}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}

                    ${response.competitors_mentioned && Object.keys(response.competitors_mentioned).length > 0 ? `
                        <div class="competitors-list">
                            <h5>
                                <i class="fas fa-users"></i>
                                Competitors Mentioned (${Object.keys(response.competitors_mentioned).length})
                            </h5>
                            <div class="competitor-chips">
                                ${Object.entries(response.competitors_mentioned).map(([comp, count]) => `
                                    <span class="competitor-chip">
                                        ${this.escapeHtml(comp)} (${count})
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        container.innerHTML = html;
    },

showResponseModal(index) {
        // ✨ CORREGIDO: Usar currentDisplayResponses (array filtrado actual) en lugar de allResponses
        // Esto asegura que el índice corresponda a la respuesta correcta incluso con filtros activos
        const responseArray = this.currentDisplayResponses || this.allResponses;
        const response = responseArray[index];

        if (!response) {
            console.error('Response not found for index:', index);
            console.error('Total responses in current view:', responseArray.length);
            console.error('Requested index:', index);
            return;
        }

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'response-modal-overlay';
        modal.innerHTML = `
            <div class="response-modal">
                <div class="response-modal-header">
                    <div class="response-modal-title">
                        <span class="response-llm-badge ${response.llm_provider}">
                            ${this.getLLMDisplayName(response.llm_provider)}
                        </span>
                        <h3>${this.escapeHtml(response.query_text)}</h3>
                    </div>
                    <button class="response-modal-close" onclick="this.closest('.response-modal-overlay').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="response-modal-meta">
                    <div class="meta-item">
                        <i class="fas fa-calendar"></i>
                        <span>${this.formatDate(response.analysis_date)}</span>
                    </div>
                    <div class="meta-item">
                        <i class="fas fa-robot"></i>
                        <span>${this.escapeHtml(response.model_used || 'N/A')}</span>
                    </div>
                    <div class="meta-item">
                        <i class="fas fa-align-left"></i>
                        <span>${response.response_length || 0} chars</span>
                    </div>
                    <div class="meta-item">
                        <span class="status-badge ${response.brand_mentioned ? 'mentioned' : 'not-mentioned'}">
                            ${response.brand_mentioned ? '✓ Mentioned' : '✗ Not Mentioned'}
                        </span>
                    </div>
                    ${response.sentiment ? `
                        <div class="meta-item">
                            <span class="status-badge ${response.sentiment}">
                                ${response.sentiment.charAt(0).toUpperCase() + response.sentiment.slice(1)}
                            </span>
                        </div>
                    ` : ''}
                    ${response.position_in_list ? `
                        <div class="meta-item">
                            <span class="status-badge" style="background: #dbeafe; color: #1e40af;">
                                Position #${response.position_in_list}
                            </span>
                        </div>
                    ` : ''}
                </div>

                <div class="response-modal-body">
                    <div class="response-modal-section">
                        <h4><i class="fas fa-file-alt"></i> Full Response</h4>
                        <div class="response-full-text">
                            ${this.highlightMentions(response)}
                        </div>
                    </div>

                    ${response.mention_contexts && response.mention_contexts.length > 0 ? `
                        <div class="response-modal-section">
                            <h4><i class="fas fa-quote-left"></i> Mention Contexts (${response.mention_contexts.length})</h4>
                            <div class="mention-contexts-list">
                                ${response.mention_contexts.map(context => `
                                    <div class="context-item-modal">
                                        ${this.highlightTextMentions(context, response)}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${response.competitors_mentioned && Object.keys(response.competitors_mentioned).length > 0 ? `
                        <div class="response-modal-section">
                            <h4><i class="fas fa-users"></i> Competitors Mentioned (${Object.keys(response.competitors_mentioned).length})</h4>
                            <div class="competitor-chips-modal">
                                ${Object.entries(response.competitors_mentioned).map(([comp, count]) => `
                                    <span class="competitor-chip-modal">
                                        ${this.escapeHtml(comp)} <span class="count-badge">${count}</span>
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${response.sources && response.sources.length > 0 ? `
                        <div class="response-modal-section">
                            <h4><i class="fas fa-link"></i> Sources & Links (${response.sources.length})</h4>
                            <div class="sources-list-modal">
                                ${response.sources.map((source, idx) => {
            const rawUrl = source?.url || '';
            const navigableUrl = this.toNavigableUrl(rawUrl);
            const safeHref = this.isSafeUrl(navigableUrl) ? navigableUrl : '#';
            const domain = this.extractNormalizedHost(rawUrl) || 'unknown';
            const isBrand = this.isUrlFromBrand(rawUrl);
            const isCompetitor = this.isUrlFromCompetitor(rawUrl);

            return `
                                        <a href="${this.escapeAttr(safeHref)}"
                                           target="_blank"
                                           rel="noopener noreferrer"
                                           class="source-link-modal ${isBrand ? 'brand-source' : ''} ${isCompetitor ? 'competitor-source' : ''}"
                                           title="${this.escapeAttr(rawUrl)}">
                                            <i class="fas fa-external-link-alt"></i>
                                            <span class="source-domain">${this.escapeHtml(domain)}</span>
                                            ${isBrand ? '<span class="source-label brand-label">Your Brand</span>' : ''}
                                            ${isCompetitor ? '<span class="source-label competitor-label">Competitor</span>' : ''}
                                            <span class="source-badge">${source.provider === 'perplexity' ? 'Citation' : 'Link'}</span>
                                        </a>
                                    `;
        }).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>

                <div class="response-modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.response-modal-overlay').remove()">
                        Close
                    </button>
                </div>
            </div>
        `;

        // Add to body
        document.body.appendChild(modal);

        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

        // Close on ESC key
        const closeOnEsc = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', closeOnEsc);
            }
        };
        document.addEventListener('keydown', closeOnEsc);
    }

});
