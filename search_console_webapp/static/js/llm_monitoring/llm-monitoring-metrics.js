/**
 * LLM Monitoring - métodos de prototipo: metrics
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

getSelectedSovMetric() {
        return document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
    },

updatePositionMetrics(positionMetrics) {
        const container = document.getElementById('positionMetricsCard');
        if (!container) return;
        
        if (!positionMetrics || positionMetrics.total_appearances === 0) {
            container.style.display = 'none';
            return;
        }
        
        container.style.display = 'block';
        
        // Actualizar valores
        const avgPosition = positionMetrics.avg_position;
        const top3Rate = positionMetrics.top3_rate || 0;
        const top5Rate = positionMetrics.top5_rate || 0;
        const top10Rate = positionMetrics.top10_rate || 0;
        
        // Actualizar el contenido
        document.getElementById('avgPositionValue').textContent = avgPosition ? avgPosition.toFixed(1) : 'N/A';
        document.getElementById('top3RateValue').textContent = `${top3Rate.toFixed(1)}%`;
        document.getElementById('top5RateValue').textContent = `${top5Rate.toFixed(1)}%`;
        document.getElementById('top10RateValue').textContent = `${top10Rate.toFixed(1)}%`;
        
        // Actualizar barras de progreso
        this.updateProgressBar('top3Progress', top3Rate);
        this.updateProgressBar('top5Progress', top5Rate);
        this.updateProgressBar('top10Progress', top10Rate);
        
        // Actualizar contador de apariciones
        const appearancesEl = document.getElementById('totalAppearances');
        if (appearancesEl) {
            appearancesEl.textContent = `Based on ${positionMetrics.total_appearances} appearances`;
        }
    },

async loadMetrics(projectId) {
        console.log(`📈 Loading detailed metrics for project ${projectId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/metrics?days=${this.globalTimeRange}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.lastMetricsData = data;

            // Render charts
            this.renderBrandedComparisonCards(data);
            this.renderMentionRateChart(data);
            await this.renderShareOfVoiceChart();  // Now async - fetches its own data
            await this.renderMentionsTimelineChart();  // Gráfico de líneas de menciones
            await this.renderSentimentDistributionChart();  // Gráfico de distribución de sentimiento
            await this.renderShareOfVoiceDonutChart();  // Gráfico de rosco

            // ✨ NEW: Load Clusters Performance (replaces LLM Comparison table)
            await this.loadClustersPerformance(projectId);

            // Load queries table
            await this.loadQueriesTable(projectId);

            // Load top URLs ranking
            await this.loadTopUrlsRanking(projectId);

        } catch (error) {
            console.error('❌ Error loading metrics:', error);
            this.showError('Failed to load metrics.');
        }
    },

renderBrandedComparisonCards(data) {
        const grid = document.getElementById('brandedComparisonGrid');
        if (!grid) return;

        const branded = data.branded_metrics;
        const nonBranded = data.non_branded_metrics;

        if (!branded && !nonBranded) {
            grid.style.display = 'none';
            return;
        }

        // Non-Branded
        const nbMR = document.getElementById('nonBrandedMentionRate');
        const nbSOV = document.getElementById('nonBrandedSOV');
        const nbCount = document.getElementById('nonBrandedCount');
        if (nbMR) nbMR.innerHTML = nonBranded ? `${nonBranded.mention_rate}% ${this.renderMiniTrend(data.non_branded_trends?.mention_rate)}` : '--';
        if (nbSOV) nbSOV.innerHTML = nonBranded ? `${nonBranded.share_of_voice}% ${this.renderMiniTrend(data.non_branded_trends?.share_of_voice)}` : '--';
        if (nbCount) nbCount.textContent = nonBranded ? nonBranded.total_queries : '0';

        // Branded
        const bMR = document.getElementById('brandedMentionRate');
        const bSOV = document.getElementById('brandedSOV');
        const bCount = document.getElementById('brandedCount');
        if (bMR) bMR.innerHTML = branded ? `${branded.mention_rate}% ${this.renderMiniTrend(data.branded_trends?.mention_rate)}` : '--';
        if (bSOV) bSOV.innerHTML = branded ? `${branded.share_of_voice}% ${this.renderMiniTrend(data.branded_trends?.share_of_voice)}` : '--';
        if (bCount) bCount.textContent = branded ? branded.total_queries : '0';

        grid.style.display = 'grid';
    },

showSovInfoModal() {
        const modal = document.getElementById('sovInfoModal');
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    },

hideSovInfoModal() {
        const modal = document.getElementById('sovInfoModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
    },

async loadComparison(projectId) {
        console.log(`📊 Loading comparison for project ${projectId}...`);

        try {
            // ✨ GLOBAL: Get selected metric type from global FAB toggle
            const metricType = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
            console.log(`📊 Loading comparison with metric: ${metricType}`);

            const response = await fetch(`${this.baseUrl}/projects/${projectId}/comparison?metric=${metricType}&days=${this.globalTimeRange}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            this.renderComparisonTable(data.comparison, data.previous_period || null);

        } catch (error) {
            console.error('❌ Error loading comparison:', error);
        }
    },

renderComparisonTable(data, previousPeriod) {
        const container = document.getElementById('comparisonTable');
        if (!container) return;

        // Destroy existing grid
        if (this.comparisonGrid) {
            this.comparisonGrid.destroy();
        }

        // Build a lookup for previous period data keyed by provider
        const prevByProvider = {};
        if (previousPeriod && Array.isArray(previousPeriod)) {
            previousPeriod.forEach(p => { prevByProvider[p.llm_provider] = p; });
        }

        // Prepare data
        const rows = data.map(item => {
            const prev = prevByProvider[item.llm_provider];
            const mrDelta = prev ? this.formatDelta(item.mention_rate, prev.mention_rate) : '';
            const sovDelta = prev ? this.formatDelta(item.share_of_voice, prev.share_of_voice) : '';
            return [
                this.getLLMDisplayName(item.llm_provider),
                this.formatDate(item.snapshot_date),
                gridjs.html(`${item.mention_rate.toFixed(1)}% (${(item.total_mentions || 0)}/${(item.total_queries || 0)}) ${mrDelta}`),
                this.formatPositionWithBadge(item.avg_position, item.position_source, item.position_source_details),
                gridjs.html(`${item.share_of_voice.toFixed(1)}% ${sovDelta}`),
                this.getSentimentLabel(item.sentiment),
                item.total_queries
            ];
        });

        // Create grid
        this.comparisonGrid = new gridjs.Grid({
            columns: [
                { name: 'LLM', width: '120px' },
                { name: 'Date', width: '100px' },
                { name: 'Mention Rate', width: '100px' },
                { name: 'Avg Position', width: '100px' },
                { name: 'Share of Voice', width: '120px' },
                { name: 'Sentiment', width: '100px' },
                { name: 'Prompts', width: '80px' }
            ],
            data: rows,
            sort: true,
            search: true,
            pagination: {
                limit: 10
            },
            style: {
                table: {
                    'font-size': '14px'
                }
            }
        }).render(container);
    },

async showBrandMentionsModal(rowIdx) {
        const query = this.queriesData[rowIdx];
        if (!query) return;

        const modal = document.getElementById('brandMentionsModal');
        const modalTitle = document.getElementById('brandMentionsModalPrompt');
        const modalBody = document.getElementById('brandMentionsModalBody');

        if (!modal || !modalBody) {
            console.error('❌ Modal elements not found');
            return;
        }

        // Set prompt text in modal header
        modalTitle.textContent = `"${query.prompt}"`;

        // Render modal content
        modalBody.innerHTML = this.renderBrandMentionsModalContent(query);

        // Show modal
        modal.style.display = 'flex';

        // Add fade-in animation
        setTimeout(() => {
            modal.style.opacity = '1';
        }, 10);

        // ✨ NUEVO: Cargar y mostrar la gráfica histórica
        await this.loadQueryHistoryChart(query.id);
    },

hideBrandMentionsModal() {
        const modal = document.getElementById('brandMentionsModal');
        if (!modal) return;

        // Destruir el gráfico de historial si existe
        if (this.historyChart) {
            this.historyChart.destroy();
            this.historyChart = null;
        }

        modal.style.opacity = '0';
        setTimeout(() => {
            modal.style.display = 'none';
        }, 200);
    },

exportComparison() {
        if (this.comparisonGrid) {
            // This would require additional implementation
            // For now, just show a message
            this.showInfo('Export functionality coming soon!');
        }
    },

getSentimentLabel(sentiment) {
        if (!sentiment) return 'Neutral';

        // Si es un número (legacy), usar el método anterior
        if (typeof sentiment === 'number') {
            if (sentiment > 60) return 'Positive';
            if (sentiment > 40) return 'Neutral';
            return 'Negative';
        }

        // Si es un objeto con {positive, neutral, negative} porcentajes
        const positive = sentiment.positive || 0;
        const neutral = sentiment.neutral || 0;
        const negative = sentiment.negative || 0;

        // Determinar cual es mayor
        if (positive >= neutral && positive >= negative) {
            return 'Positive';
        } else if (negative > positive && negative > neutral) {
            return 'Negative';
        } else {
            return 'Neutral';
        }
    },

highlightMentions(response) {
        if (!response.full_response) {
            return '<em style="color: #9ca3af;">No response text available</em>';
        }

        // Get brand keywords and competitor keywords
        const brandKeywords = this.currentProject?.brand_keywords || [];
        const brandName = this.currentProject?.brand_name || '';
        const brandDomain = this.currentProject?.brand_domain || '';

        // Get competitors
        const competitors = this.currentProject?.selected_competitors || [];
        const competitorKeywords = [];
        competitors.forEach(comp => {
            if (comp.domain) competitorKeywords.push(comp.domain);
            if (comp.keywords) competitorKeywords.push(...comp.keywords);
        });

        // Combine all brand terms
        const allBrandTerms = [...brandKeywords];
        if (brandName) allBrandTerms.push(brandName);
        if (brandDomain) allBrandTerms.push(brandDomain.replace('www.', ''));

        // Highlight+escape the RAW response first (highlightTextMentions now
        // escapes internally), then apply markdown decorations that don't re-escape.
        let html = this.highlightTextMentions(response.full_response, response, allBrandTerms, competitorKeywords);
        html = this.applyMarkdownDecorations(html);

        return html;
    },

    applyMarkdownDecorations(html) {
        // Lightweight markdown formatting for already-escaped HTML.
        // Headers
        html = html.replace(/^### (.+)$/gm, '<strong style="font-size: 1.1em;">$1</strong><br>');
        html = html.replace(/^## (.+)$/gm, '<strong style="font-size: 1.15em;">$1</strong><br>');
        html = html.replace(/^# (.+)$/gm, '<strong style="font-size: 1.2em;">$1</strong><br>');

        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Links [text](url) - el texto ya viene escapado; solo se permiten esquemas
        // http(s)/relativos (bloquea javascript:, data:, etc.), igual que parseMarkdown.
        html = html.replace(/\[(.+?)\]\((.+?)\)/g, (match, label, url) => {
            if (!this.isSafeUrl(url)) return label;
            return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="md-link">${label}</a>`;
        });

        // Lists
        html = html.replace(/^- (.+)$/gm, '• $1<br>');
        html = html.replace(/^\d+\. (.+)$/gm, '$&<br>');

        // Line breaks
        html = html.replace(/\n\n/g, '<br><br>');
        html = html.replace(/\n/g, '<br>');

        return html;
    },

highlightTextMentions(text, response, brandTerms = null, competitorTerms = null) {
        if (!text) return '';

        // Get brand and competitor terms if not provided
        if (!brandTerms) {
            const brandKeywords = this.currentProject?.brand_keywords || [];
            const brandName = this.currentProject?.brand_name || '';
            const brandDomain = this.currentProject?.brand_domain || '';

            brandTerms = [...brandKeywords];
            if (brandName) brandTerms.push(brandName);
            if (brandDomain) brandTerms.push(brandDomain.replace('www.', ''));
        }

        if (!competitorTerms) {
            const competitors = this.currentProject?.selected_competitors || [];
            competitorTerms = [];
            competitors.forEach(comp => {
                if (comp.domain) competitorTerms.push(comp.domain);
                if (comp.keywords) competitorTerms.push(...comp.keywords);
            });
        }

        // Apply highlighting to raw text using placeholder tokens, so the <mark>
        // tags we add survive HTML escaping but the user text stays escaped.
        let processedText = text;
        const highlights = [];
        let highlightIndex = 0;

        const createPlaceholder = (type, matchedText) => {
            const placeholder = `___HIGHLIGHT_${highlightIndex}_${type}___`;
            highlights.push({ placeholder, type, text: matchedText });
            highlightIndex++;
            return placeholder;
        };

        // First highlight competitors (orange/red)
        competitorTerms.forEach(term => {
            if (!term) return;
            const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`\\b(${escapedTerm})\\b`, 'gi');
            processedText = processedText.replace(regex, (match) => createPlaceholder('competitor', match));
        });

        // Then highlight brand (blue) - will take precedence if term appears in both lists
        brandTerms.forEach(term => {
            if (!term) return;
            const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`\\b(${escapedTerm})\\b`, 'gi');
            processedText = processedText.replace(regex, (match) => createPlaceholder('brand', match));
        });

        // Now escape HTML, then restore highlights with proper markup
        let result = this.escapeHtml(processedText);
        highlights.forEach(({ placeholder, type, text: matchedText }) => {
            const cssClass = type === 'brand' ? 'brand-mention' : 'competitor-mention';
            const escapedMatch = this.escapeHtml(matchedText);
            result = result.replace(placeholder, `<mark class="${cssClass}">${escapedMatch}</mark>`);
        });

        return result;
    }

});
