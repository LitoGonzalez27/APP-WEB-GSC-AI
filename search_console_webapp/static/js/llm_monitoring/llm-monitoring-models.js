/**
 * LLM Monitoring - métodos de prototipo: models
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

updateModelScopeBanner() {
        const banner = document.getElementById('llmModelScopeBanner');
        const bannerText = document.getElementById('llmModelScopeBannerText');
        if (!banner || !bannerText) return;

        const projectId = this.currentProject?.id;
        let message = '';

        if (this.pendingModelScopeNotice && this.pendingModelScopeNotice.project_id === projectId) {
            const change = this.pendingModelScopeNotice;
            const activeNames = this.formatLlmNames(change.current_enabled_llms || this.currentProject?.enabled_llms || []);
            const changeParts = [];
            if (Array.isArray(change.added_llms) && change.added_llms.length > 0) {
                changeParts.push(`added ${this.formatLlmNames(change.added_llms).join(', ')}`);
            }
            if (Array.isArray(change.removed_llms) && change.removed_llms.length > 0) {
                changeParts.push(`removed ${this.formatLlmNames(change.removed_llms).join(', ')}`);
            }
            message =
                `Model selection updated: now using ${activeNames.join(', ') || 'selected LLMs'} for metrics and exports.` +
                `${changeParts.length > 0 ? ` You ${changeParts.join(' and ')}.` : ''}`;
            this.pendingModelScopeNotice = null;
        }

        if (!message && this.serverModelScopeNotice && this.serverModelScopeNotice.project_id === projectId) {
            const scope = this.serverModelScopeNotice;
            if (scope.show) {
                const activeNames = this.formatLlmNames(scope.active_llms || this.currentProject?.enabled_llms || []);
                const excludedNames = this.formatLlmNames(scope.excluded_llms_with_data || []);
                const rangeDays = Number(scope.range_days) || this.globalTimeRange;
                message =
                    `Showing only active models (${activeNames.join(', ') || 'selected LLMs'}). ` +
                    `Historical data from disabled models exists in the last ${rangeDays} days: ` +
                    `${excludedNames.join(', ')}.`;
            }
        }

        if (!message) {
            banner.style.display = 'none';
            bannerText.textContent = '';
            return;
        }

        bannerText.textContent = message;
        banner.style.display = 'flex';
    },

async showModelsModal() {
        const modal = document.getElementById('modelsInfoModal');
        const content = document.getElementById('modelsInfoContent');
        const cutoffContent = document.getElementById('knowledgeCutoffContent');
        if (!modal || !content) return;

        modal.style.display = 'flex';
        modal.style.opacity = '0';
        setTimeout(() => modal.style.opacity = '1', 10);

        // Show loading
        content.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <i class="fas fa-spinner fa-spin" style="font-size: 24px; color: #3b82f6;"></i>
                <p style="margin-top: 12px; color: #666;">Loading models...</p>
            </div>
        `;

        try {
            const response = await fetch(`${this.baseUrl}/models/current`);
            const data = await response.json();

            if (data.success && data.models) {
                const providerIcons = {
                    'openai': 'fas fa-robot',
                    'anthropic': 'fas fa-brain',
                    'google': 'fab fa-google',
                    'perplexity': 'fas fa-search'
                };

                const providerLabels = {
                    'openai': 'ChatGPT',
                    'anthropic': 'Claude',
                    'google': 'Gemini',
                    'perplexity': 'Perplexity'
                };

                const providerColors = {
                    'openai': '#10b981',
                    'anthropic': '#f97316',
                    'google': '#3b82f6',
                    'perplexity': '#8b5cf6'
                };

                // Render model cards
                let html = '<div class="models-grid">';

                for (const [provider, model] of Object.entries(data.models)) {
                    html += `
                        <div class="model-card">
                            <div class="model-icon ${provider}">
                                <i class="${providerIcons[provider] || 'fas fa-microchip'}"></i>
                            </div>
                            <div class="model-info">
                                <div class="model-provider">${providerLabels[provider] || provider}</div>
                                <div class="model-name">${model.display_name}</div>
                                <div class="model-id">${model.model_id}</div>
                            </div>
                        </div>
                    `;
                }

                html += '</div>';
                content.innerHTML = html;

                // Render knowledge cutoff dates dynamically
                if (cutoffContent) {
                    let cutoffHtml = '';
                    for (const [provider, model] of Object.entries(data.models)) {
                        const label = providerLabels[provider] || provider;
                        const color = providerColors[provider] || '#6b7280';
                        const cutoff = model.knowledge_cutoff || 'Unknown';
                        const isWebGrounded = cutoff.toLowerCase().includes('web-grounded');

                        cutoffHtml += `
                            <div style="background: white; padding: 10px; border-radius: 8px; display: flex; align-items: center; gap: 8px;">
                                <span style="background: ${color}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600; white-space: nowrap;">${label}</span>
                                <span style="color: ${isWebGrounded ? '#059669' : '#374151'}; ${isWebGrounded ? 'font-weight: 600;' : ''}">
                                    ${model.display_name}: ${isWebGrounded ? '🔍 ' : ''}${cutoff}
                                </span>
                            </div>
                        `;
                    }
                    cutoffContent.innerHTML = cutoffHtml;
                }
            } else {
                throw new Error('Could not load models');
            }
        } catch (error) {
            console.error('Error loading models:', error);
            content.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #ef4444;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 24px;"></i>
                    <p style="margin-top: 12px;">Failed to load models info</p>
                </div>
            `;
            if (cutoffContent) {
                cutoffContent.innerHTML = '<div style="text-align: center; padding: 10px; color: #ef4444; grid-column: span 2;">Could not load cutoff dates</div>';
            }
        }
    },

hideModelsModal() {
        const modal = document.getElementById('modelsInfoModal');
        if (!modal) return;

        modal.style.opacity = '0';
        setTimeout(() => modal.style.display = 'none', 200);
    }

});
