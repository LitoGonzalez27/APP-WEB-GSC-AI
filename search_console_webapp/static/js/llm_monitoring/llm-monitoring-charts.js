/**
 * LLM Monitoring - métodos de prototipo: charts
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

// Empty state centrado para gráficas timeline (canvas oculto mientras se muestra)
showChartEmptyState(canvasId, legendId, title, subtitle) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const container = canvas.parentElement;
        container.querySelector('.chart-empty-state')?.remove();
        canvas.style.display = 'none';
        if (legendId) {
            const legend = document.getElementById(legendId);
            if (legend) legend.innerHTML = '';
        }
        // Overlay absoluto ocupando el área del chart (el contenedor tiene altura fija)
        if (!container.style.position) container.style.position = 'relative';
        const overlay = document.createElement('div');
        overlay.className = 'chart-empty-state';
        overlay.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#6b7280;text-align:center;padding:2rem;';
        overlay.innerHTML = `
            <i class="fas fa-chart-line" style="font-size:2.5rem;opacity:0.3;margin-bottom:1rem;"></i>
            <p style="font-size:1rem;font-weight:600;margin:0;">${title}</p>
            ${subtitle ? `<p style="font-size:0.85rem;margin-top:0.5rem;color:#9ca3af;max-width:420px;">${subtitle}</p>` : ''}
        `;
        container.appendChild(overlay);
    },

clearChartEmptyState(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        canvas.parentElement.querySelector('.chart-empty-state')?.remove();
        canvas.style.display = '';
    },

// Mensajes del empty state según el scope activo (branded/non_branded/all)
chartEmptyStateCopy(scope) {
        if (scope === 'branded') {
            return {
                title: 'No branded prompts in this period',
                subtitle: 'None of the analyzed prompts include your brand name. Switch to "All" or "Non-Branded" to see data.'
            };
        }
        if (scope === 'non_branded') {
            return {
                title: 'No non-branded prompts in this period',
                subtitle: 'All analyzed prompts include your brand name. Switch to "All" or "Branded" to see data.'
            };
        }
        return {
            title: 'No data yet for this period',
            subtitle: 'Run an analysis or extend the time range to see this chart.'
        };
    },

renderRichChartTooltip(context) {
        let tooltipEl = document.getElementById('llm-chart-tooltip');
        if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.id = 'llm-chart-tooltip';
            tooltipEl.className = 'llm-chart-tooltip';
            document.body.appendChild(tooltipEl);
        }

        const tooltipModel = context.tooltip;
        if (tooltipModel.opacity === 0) {
            tooltipEl.classList.remove('active');
            return;
        }

        if (tooltipModel.body) {
            const dataIndex = tooltipModel.dataPoints[0].dataIndex;
            const chart = context.chart;
            const titleText = tooltipModel.title[0] || '';

            // Detect if this is the SOV chart (has previous period averages)
            const isSovChart = chart.canvas.id === 'chartShareOfVoice';
            const prevAvg = isSovChart ? (this.sovPreviousPeriodAvg || {}) : {};

            let rows = '';
            chart.data.datasets.forEach((ds, i) => {
                const meta = chart.getDatasetMeta(i);
                if (meta.hidden) return;
                const value = ds.data[dataIndex];
                if (value === null || value === undefined) return;
                const color = ds.borderColor || ds.backgroundColor || '#888';
                const isPercentMetric = ds.label && (ds.label.toLowerCase().includes('voice') || ds.label.toLowerCase().includes('rate'));
                const displayVal = isPercentMetric ? `${Number(value).toFixed(1)}%` : Math.round(value);

                // Previous period comparison for SOV chart
                let prevHtml = '';
                const prevVal = prevAvg[ds.label];
                if (prevVal !== undefined && prevVal !== null && isPercentMetric) {
                    const delta = (Number(value) - prevVal).toFixed(1);
                    const sign = delta > 0 ? '+' : '';
                    const cls = delta > 0 ? 'up' : delta < 0 ? 'down' : 'stable';
                    prevHtml = `<span class="llm-chart-tooltip__prev">prev ${prevVal}% <span class="delta delta--${cls}">${sign}${delta}pp</span></span>`;
                }

                rows += `<div class="llm-chart-tooltip__row">
                    <span class="llm-chart-tooltip__dot" style="background:${color}"></span>
                    <span class="llm-chart-tooltip__label">${ds.label}</span>
                    <span class="llm-chart-tooltip__value">${displayVal}${prevHtml}</span>
                </div>`;
            });

            tooltipEl.innerHTML = `<div class="llm-chart-tooltip__title">${titleText}</div>${rows}`;
        }

        const position = context.chart.canvas.getBoundingClientRect();
        const tooltipWidth = tooltipEl.offsetWidth || 200;
        const tooltipHeight = tooltipEl.offsetHeight || 100;
        const caretAbsX = position.left + window.scrollX + tooltipModel.caretX;
        const caretAbsY = position.top + window.scrollY + tooltipModel.caretY;
        const viewportRight = window.innerWidth + window.scrollX;
        const viewportBottom = window.innerHeight + window.scrollY;

        // Flip left if tooltip would overflow right edge
        let leftPos = caretAbsX + 12;
        if (leftPos + tooltipWidth > viewportRight - 16) {
            leftPos = caretAbsX - tooltipWidth - 12;
        }
        // Push up if tooltip would overflow bottom
        let topPos = caretAbsY - 10;
        if (topPos + tooltipHeight > viewportBottom - 16) {
            topPos = caretAbsY - tooltipHeight + 10;
        }
        // Never go off-screen left/top
        leftPos = Math.max(8, leftPos);
        topPos = Math.max(8, topPos);

        tooltipEl.style.left = leftPos + 'px';
        tooltipEl.style.top = topPos + 'px';
        tooltipEl.classList.add('active');
    },

renderMentionRateChart(data) {
        const canvas = document.getElementById('chartMentionRate');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.mentionRate) {
            this.charts.mentionRate.destroy();
        }

        // Prepare data
        const llms = Object.keys(data.aggregated.metrics_by_llm || {});
        const mentionRates = llms.map(llm => data.aggregated.metrics_by_llm[llm].avg_mention_rate || 0);

        // Previous period data (may be absent)
        const prevByLLM = data.previous_metrics_by_llm || {};
        const prevRates = llms.map(llm => prevByLLM[llm]?.avg_mention_rate ?? null);
        const hasPrev = prevRates.some(v => v !== null);

        // Color por entidad (cada LLM tiene el suyo fijo), no por posici\u00f3n en el
        // array: si se filtra un LLM, los que quedan conservan su color.
        const barColors = llms.map((llm, i) => CSChartTheme.seriesColorFor(llm, i));

        const datasets = [{
            label: 'Mention Rate (%)',
            data: mentionRates,
            backgroundColor: barColors
        }];

        // Periodo anterior como barras de contexto: mismo color, muy atenuado,
        // para que se lea como "lo de antes" y no como una segunda categor\u00eda.
        if (hasPrev) {
            datasets.push({
                label: 'Previous Period',
                data: prevRates,
                backgroundColor: CSChartTheme.seriesMuted
            });
        }

        // Create chart \u2014 tipograf\u00eda, grid, tooltip y marcas vienen del tema
        // global (static/js/llm-chart-theme.js).
        this.charts.mentionRate = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: llms.map(llm => this.getLLMDisplayName(llm)),
                datasets: datasets
            },
            options: {
                responsive: true,
                scales: { y: CSChartTheme.percentAxis() },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: ctx => ctx[0].label,
                            label: ctx => {
                                if (ctx.datasetIndex === 1) return null; // hide previous period label
                                const current = ctx.parsed.y;
                                const prev = ctx.chart.data.datasets[1]?.data[ctx.dataIndex];
                                let label = `Current: ${current.toFixed(1)}%`;
                                if (prev !== undefined && prev !== null) {
                                    const delta = current - prev;
                                    const arrow = delta > 0 ? '\u2191' : delta < 0 ? '\u2193' : '=';
                                    label += ` | Previous: ${prev.toFixed(1)}% (${arrow}${Math.abs(delta).toFixed(1)}pp)`;
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    },

renderMentionRateChartScoped(scope) {
        if (!this.lastMetricsData) return;

        if (scope === 'all') {
            this.renderMentionRateChart(this.lastMetricsData);
            return;
        }

        // Use per-LLM breakdown from the API
        const byLlm = scope === 'branded'
            ? this.lastMetricsData.branded_by_llm
            : this.lastMetricsData.non_branded_by_llm;

        const canvas = document.getElementById('chartMentionRate');
        if (!canvas || !this.charts.mentionRate) return;

        const providerLabels = {
            openai: 'ChatGPT', anthropic: 'Claude',
            google: 'Gemini', perplexity: 'Perplexity'
        };
        const providerOrder = ['openai', 'anthropic', 'google', 'perplexity'];

        if (!byLlm || Object.keys(byLlm).length === 0) {
            this.charts.mentionRate.data.labels = providerOrder.map(p => providerLabels[p] || p);
            this.charts.mentionRate.data.datasets[0].data = [0, 0, 0, 0];
            this.charts.mentionRate.update();
            return;
        }

        const labels = [];
        const data = [];
        const colors = [];
        for (const prov of providerOrder) {
            if (byLlm[prov] !== undefined) {
                labels.push(providerLabels[prov] || prov);
                data.push(byLlm[prov]);
                colors.push(CSChartTheme.seriesColorFor(prov));
            }
        }
        // Include any providers not in the fixed order
        for (const [prov, rate] of Object.entries(byLlm)) {
            if (!providerOrder.includes(prov)) {
                labels.push(providerLabels[prov] || prov);
                data.push(rate);
                colors.push(CSChartTheme.seriesMuted);
            }
        }

        this.charts.mentionRate.data.labels = labels;
        this.charts.mentionRate.data.datasets[0].data = data;
        this.charts.mentionRate.data.datasets[0].backgroundColor = colors;
        // Remove ghost bars when scoped
        if (this.charts.mentionRate.data.datasets.length > 1) {
            this.charts.mentionRate.data.datasets[1].data = new Array(data.length).fill(0);
        }
        this.charts.mentionRate.update();
    },

async renderShareOfVoiceChart() {
        const canvas = document.getElementById('chartShareOfVoice');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.shareOfVoice) {
            this.charts.shareOfVoice.destroy();
        }

        // Obtener datos históricos del nuevo endpoint
        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Share of Voice history');
                return;
            }

            // ✨ GLOBAL: Get selected metric type from global FAB toggle
            const metricType = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
            console.log(`📊 Rendering Share of Voice chart with metric: ${metricType}`);

            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=${this.globalTimeRange}&metric=${metricType}&query_scope=${this.sovScope || 'all'}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || 'Failed to load Share of Voice history');
            }

            const { dates, datasets } = result;

            // Store previous period averages for tooltip use
            this.sovPreviousPeriodAvg = result.previous_period_avg || {};

            // Si no hay datos (el chart ya se destruyó arriba), mostrar empty state
            // centrado y limpiar la leyenda del render anterior
            if (!dates || dates.length === 0 || !datasets || datasets.length === 0) {
                console.warn('⚠️ No data available for Share of Voice chart');
                const copy = this.chartEmptyStateCopy(this.sovScope);
                this.showChartEmptyState('chartShareOfVoice', 'shareOfVoiceLegend', copy.title, copy.subtitle);
                return;
            }

            this.clearChartEmptyState('chartShareOfVoice');

            // Formatear fechas para el eje X
            const formattedLabels = dates.map(dateStr => {
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });

            // Configurar leyenda HTML personalizada
            const legendContainer = document.getElementById('shareOfVoiceLegend');
            if (legendContainer) {
                legendContainer.innerHTML = '';

                datasets.forEach((dataset, index) => {
                    const legendItem = document.createElement('div');
                    legendItem.className = 'legend-item';
                    legendItem.dataset.index = index;

                    legendItem.innerHTML = `
                        <div class="legend-color" style="background-color: ${dataset.borderColor}"></div>
                        <div class="legend-label">${dataset.label}</div>
                    `;

                    // Toggle visibility on click
                    legendItem.addEventListener('click', () => {
                        const chart = this.charts.shareOfVoice;
                        const meta = chart.getDatasetMeta(index);
                        meta.hidden = !meta.hidden;
                        chart.update();
                        legendItem.classList.toggle('hidden', meta.hidden);
                    });

                    legendContainer.appendChild(legendItem);
                });
            }

            // Crear gráfico de líneas
            this.charts.shareOfVoice = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: formattedLabels,
                    // Marca sólida; competidores con trazos discontinuos distintos.
                    // Sin esto, cuando dos series coinciden en el mismo valor la
                    // dibujada encima tapa por completo a la de debajo y esa línea
                    // "desaparece" del gráfico (además el trazo distingue las
                    // series sin depender solo del color).
                    //
                    // `order`: Chart.js pinta el dataset 0 EN ÚLTIMO lugar (encima
                    // de todos), así que la marca sólida seguía tapando cualquier
                    // punteado coincidente. Con orden menor (= encima) para los
                    // competidores, sus trazos se ven y sus huecos dejan ver la
                    // línea sólida de la marca por debajo.
                    datasets: datasets.map((ds, idx) => ({
                        ...ds,
                        borderDash: idx === 0 ? [] : [[6, 4], [2, 3], [10, 4, 2, 4]][(idx - 1) % 3],
                        order: idx === 0 ? 2 : 1,
                        pointBackgroundColor: ds.borderColor,
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: ds.borderColor,
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'circle',
                        pointBorderWidth: 2
                    }))
                },
                options: {
                    responsive: true,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: CSChartTheme.percentAxis({
                            title: {
                                display: true,
                                text: 'Share of Voice (%)',
                                color: CSChartTheme.ink.secondary,
                                font: { size: 12, weight: '600' }
                            }
                        })
                    },
                    plugins: {
                        legend: {
                            display: false  // Usar leyenda HTML personalizada
                        },
                        tooltip: {
                            enabled: false,
                            external: (context) => this.renderRichChartTooltip(context)
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Share of Voice history:', error);
        }
    },

async renderMentionsTimelineChart() {
        const canvas = document.getElementById('chartMentionsTimeline');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.mentionsTimeline) {
            this.charts.mentionsTimeline.destroy();
        }

        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Mentions Timeline');
                return;
            }

            // ⚠️ Total Mentions siempre usa conteo estándar (no weighted)
            // Una mención es una mención - el weighted solo aplica a Share of Voice
            const metricType = 'normal';

            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=${this.globalTimeRange}&metric=${metricType}&query_scope=${this.mentionsScope || 'all'}`);
            if (!response.ok) {
                console.warn('Could not load mentions timeline data');
                return;
            }

            const result = await response.json();

            if (!result.success || !result.mentions_datasets || !result.dates || result.dates.length === 0) {
                console.warn('⚠️ No mentions data available yet for this project');
                // El chart ya se destruyó arriba: empty state centrado según el scope
                const copy = this.chartEmptyStateCopy(this.mentionsScope);
                this.showChartEmptyState('chartMentionsTimeline', 'mentionsTimelineLegend', copy.title, copy.subtitle);
                return;
            }

            this.clearChartEmptyState('chartMentionsTimeline');

            const { dates, mentions_datasets } = result;

            // Formatear fechas para el eje X
            const formattedLabels = dates.map(dateStr => {
                const date = new Date(dateStr);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });

            // Configurar leyenda HTML
            const legendContainer = document.getElementById('mentionsTimelineLegend');
            if (legendContainer) {
                legendContainer.innerHTML = '';

                mentions_datasets.forEach((dataset, index) => {
                    const legendItem = document.createElement('div');
                    legendItem.className = 'legend-item';
                    legendItem.dataset.index = index;

                    legendItem.innerHTML = `
                        <div class="legend-color" style="background-color: ${dataset.borderColor}"></div>
                        <div class="legend-label">${dataset.label}</div>
                    `;

                    legendItem.addEventListener('click', () => {
                        const chart = this.charts.mentionsTimeline;
                        const meta = chart.getDatasetMeta(index);
                        meta.hidden = !meta.hidden;
                        chart.update();
                        legendItem.classList.toggle('hidden', meta.hidden);
                    });

                    legendContainer.appendChild(legendItem);
                });
            }

            // Crear gráfico
            this.charts.mentionsTimeline = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: formattedLabels,
                    // Mismo criterio que en Share of Voice: competidores con trazo
                    // discontinuo Y pintados encima (order menor) para que una
                    // coincidencia exacta de valores no deje ninguna línea
                    // invisible bajo otra.
                    datasets: mentions_datasets.map((ds, idx) => ({
                        ...ds,
                        borderDash: idx === 0 ? [] : [[6, 4], [2, 3], [10, 4, 2, 4]][(idx - 1) % 3],
                        order: idx === 0 ? 2 : 1,
                        pointBackgroundColor: ds.borderColor,
                        pointBorderColor: '#FFFFFF',
                        pointHoverBackgroundColor: ds.borderColor,
                        pointHoverBorderColor: '#FFFFFF',
                        pointStyle: 'circle',
                        pointBorderWidth: 2
                    }))
                },
                options: {
                    responsive: true,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: {
                            beginAtZero: true,
                            ticks: { callback: value => Math.round(value) },
                            title: {
                                display: true,
                                text: 'Total Mentions',
                                color: CSChartTheme.ink.secondary,
                                font: { size: 12, weight: '600' }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            enabled: false,
                            external: (context) => this.renderRichChartTooltip(context)
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Mentions Timeline:', error);
        }
    },

async renderShareOfVoiceDonutChart() {
        const canvas = document.getElementById('chartShareOfVoiceDonut');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.shareOfVoiceDonut) {
            this.charts.shareOfVoiceDonut.destroy();
        }

        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Share of Voice Donut');
                return;
            }

            // ✨ GLOBAL: Get selected metric type from global FAB toggle
            const metricType = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
            console.log(`📊 Rendering Share of Voice Donut with metric: ${metricType}`);

            const response = await fetch(`/api/llm-monitoring/projects/${projectId}/share-of-voice-history?days=${this.globalTimeRange}&metric=${metricType}`);
            if (!response.ok) {
                console.warn('Could not load Share of Voice donut data');
                return;
            }

            const result = await response.json();

            if (!result.success || !result.donut_data) {
                console.warn('⚠️ No donut data available yet for this project');
                return;
            }

            const { donut_data } = result;

            // Si no hay datos, simplemente retornar
            if (!donut_data.labels || donut_data.labels.length === 0) {
                console.warn('⚠️ No distribution data available');
                return;
            }

            // Crear gráfico de rosco
            this.charts.shareOfVoiceDonut = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: donut_data.labels,
                    datasets: [{
                        data: donut_data.values,
                        backgroundColor: donut_data.colors,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'bottom' },
                        tooltip: {
                            callbacks: {
                                label: context => {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    return `${label}: ${value.toFixed(1)}%`;
                                }
                            }
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Share of Voice Donut:', error);
        }
    },

async renderSentimentDistributionChart() {
        const canvas = document.getElementById('chartSentimentDistribution');
        if (!canvas) return;

        // Destroy existing chart
        if (this.charts.sentimentDistribution) {
            this.charts.sentimentDistribution.destroy();
        }

        try {
            const projectId = this.currentProject?.id;
            if (!projectId) {
                console.warn('No project ID available for Sentiment Distribution');
                return;
            }

            // Obtener datos de snapshots (comparación) que incluyen sentimiento
            const metricType = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
            const response = await fetch(
                `${this.baseUrl}/projects/${projectId}/comparison?metric=${metricType}&days=${this.globalTimeRange}`
            );
            if (!response.ok) {
                console.warn('Could not load sentiment data');
                return;
            }

            const result = await response.json();

            if (!result.comparison || result.comparison.length === 0) {
                console.warn('⚠️ No comparison data available for sentiment analysis');
                return;
            }

            // Agregar contadores de sentimiento de todos los LLMs (último snapshot real)
            let totalPositive = 0;
            let totalNeutral = 0;
            let totalNegative = 0;

            // Usar solo filas del snapshot_date más reciente para evitar mezclar fechas.
            const toDateKey = (value) => {
                const parsed = new Date(value);
                if (Number.isNaN(parsed.getTime())) return String(value || '');
                return parsed.toISOString().slice(0, 10);
            };
            const datedSnapshots = Array.isArray(result.comparison)
                ? result.comparison.filter((row) => row?.snapshot_date)
                : [];
            if (datedSnapshots.length === 0) {
                console.warn('⚠️ No dated snapshots available for sentiment analysis');
                return;
            }
            datedSnapshots.sort((a, b) => new Date(b.snapshot_date) - new Date(a.snapshot_date));
            const latestDateKey = toDateKey(datedSnapshots[0].snapshot_date);
            const recentSnapshots = datedSnapshots.filter(
                (snapshot) => toDateKey(snapshot.snapshot_date) === latestDateKey
            );
            if (recentSnapshots.length === 0) {
                console.warn('⚠️ No recent snapshots available for sentiment analysis');
                return;
            }

            recentSnapshots.forEach(snapshot => {
                if (snapshot.sentiment) {
                    totalPositive += snapshot.sentiment.positive || 0;
                    totalNeutral += snapshot.sentiment.neutral || 0;
                    totalNegative += snapshot.sentiment.negative || 0;
                }
            });

            const total = totalPositive + totalNeutral + totalNegative;

            if (total === 0) {
                console.warn('⚠️ No sentiment data available');
                return;
            }

            // Calcular porcentajes promedio
            const avgPositive = totalPositive / recentSnapshots.length;
            const avgNeutral = totalNeutral / recentSnapshots.length;
            const avgNegative = totalNegative / recentSnapshots.length;

            const data = {
                labels: ['Positive', 'Neutral', 'Negative'],
                values: [
                    avgPositive.toFixed(1),
                    avgNeutral.toFixed(1),
                    avgNegative.toFixed(1)
                ],
                // El sentimiento SÍ significa bueno/malo, así que va con los
                // colores de estado de la marca, nunca con los de serie: un
                // color de estado no debe hacerse pasar por una categoría.
                colors: [
                    CSChartTheme.status.success,
                    CSChartTheme.status.neutral,
                    CSChartTheme.status.error
                ]
            };

            // Crear gráfico de rosco
            this.charts.sentimentDistribution = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.values,
                        backgroundColor: data.colors,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    // ✨ Click en un segmento → LLM Responses Inspector con el
                    // filtro de sentimiento correspondiente activo
                    onHover: (event, elements) => {
                        const target = event?.native?.target;
                        if (target) target.style.cursor = elements.length ? 'pointer' : 'default';
                    },
                    onClick: (event, elements) => {
                        if (!elements || elements.length === 0) return;
                        const label = this.charts.sentimentDistribution?.data?.labels?.[elements[0].index];
                        if (!label) return;
                        this.goToResponsesWithSentiment(String(label).toLowerCase());
                    },
                    plugins: {
                        legend: { position: 'bottom' },
                        tooltip: {
                            footerFont: {
                                size: 11,
                                style: 'italic',
                                weight: '400'
                            },
                            footerColor: CSChartTheme.ink.tertiary,
                            callbacks: {
                                label: context => {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    return `${label}: ${value}%`;
                                },
                                footer: () => 'Click to inspect these responses'
                            }
                        }
                    }
                }
            });

        } catch (error) {
            console.error('❌ Error loading Sentiment Distribution:', error);
        }
    },

async loadQueryHistoryChart(queryId) {
        const loadingEl = document.getElementById('historyChartLoading');
        const emptyEl = document.getElementById('historyChartEmpty');
        const chartContainer = document.querySelector('.history-chart-container');
        const periodLabel = document.getElementById('historyChartPeriod');
        const canvas = document.getElementById('brandMentionsHistoryChart');

        if (!canvas) {
            console.error('❌ History chart canvas not found');
            return;
        }

        // Actualizar el label del período con el time range global
        if (periodLabel) {
            periodLabel.textContent = `Last ${this.globalTimeRange} days`;
        }

        // Mostrar loading
        if (loadingEl) loadingEl.style.display = 'flex';
        if (emptyEl) emptyEl.style.display = 'none';
        if (chartContainer) chartContainer.style.display = 'block';

        try {
            // ✨ Usar el time range global del proyecto
            const response = await fetch(`${this.baseUrl}/projects/${this.currentProject.id}/queries/${queryId}/history?days=${this.globalTimeRange}`);
            const data = await response.json();

            if (loadingEl) loadingEl.style.display = 'none';

            if (!data.success || !data.history || data.history.length === 0) {
                if (emptyEl) emptyEl.style.display = 'flex';
                if (chartContainer) chartContainer.style.display = 'none';
                return;
            }

            // Preparar datos para la gráfica
            const labels = data.history.map(h => {
                const date = new Date(h.date);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });

            // Dataset principal: Visibility Rate total (% de LLMs que mencionan)
            const visibilityData = data.history.map(h => h.visibility_rate);
            
            // Guardar datos completos para el tooltip
            const historyData = data.history;
            const llmProviders = data.llm_providers;
            const self = this;

            // Destruir gráfico anterior si existe
            if (this.historyChart) {
                this.historyChart.destroy();
            }

            // ✨ Una sola línea: Overall Visibility. Al ser serie única no lleva
            // leyenda — el título de la sección ya la nombra — y usa el slot 1
            // de la paleta con un relleno tenue del mismo tono.
            const datasets = [
                {
                    label: 'Visibility Rate',
                    data: visibilityData,
                    borderColor: CSChartTheme.series[0],
                    backgroundColor: 'rgba(42, 120, 214, 0.08)',
                    fill: true,
                    pointBackgroundColor: CSChartTheme.series[0],
                    pointBorderColor: CSChartTheme.surface.paper
                }
            ];

            // Crear gráfico
            const ctx = canvas.getContext('2d');
            this.historyChart = new Chart(ctx, {
                type: 'line',
                data: { labels, datasets },
                options: {
                    responsive: true,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            displayColors: false,
                            callbacks: {
                                title: function(context) {
                                    return context[0].label;
                                },
                                label: function(context) {
                                    const idx = context.dataIndex;
                                    const dayData = historyData[idx];
                                    const value = context.parsed.y;
                                    
                                    // Línea principal con el %
                                    return `Visibility: ${value.toFixed(1)}% (${dayData.llms_mentioned}/${dayData.total_llms} LLMs)`;
                                },
                                afterLabel: function(context) {
                                    const idx = context.dataIndex;
                                    const dayData = historyData[idx];
                                    
                                    // Mostrar qué LLMs mencionaron
                                    const lines = [];
                                    llmProviders.forEach(llm => {
                                        const llmInfo = dayData.by_llm[llm];
                                        if (llmInfo) {
                                            const status = llmInfo.mentioned ? 'Mentioned' : 'Not mentioned';
                                            const displayName = self.getLLMDisplayName(llm);
                                            lines.push(`${displayName}: ${status}`);
                                        }
                                    });
                                    
                                    return lines.length > 0 ? '\n' + lines.join('\n') : '';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { maxRotation: 45 }
                        },
                        y: CSChartTheme.percentAxis({
                            min: 0,
                            ticks: { callback: value => `${value}%`, stepSize: 25 }
                        })
                    }
                }
            });

            console.log(`📊 History chart loaded with ${data.total_data_points} data points`);

        } catch (error) {
            console.error('❌ Error loading query history:', error);
            if (loadingEl) loadingEl.style.display = 'none';
            if (emptyEl) {
                emptyEl.style.display = 'flex';
                emptyEl.innerHTML = `
                    <span>Error loading history</span>
                `;
            }
        }
    },

// ✨ Resumen compacto del prompt: SOV, Avg Position, Sentiment, Cluster, Top Domains
renderBrandMentionsOverview(query) {
        const container = document.getElementById('brandMentionsOverview');
        if (!container) return;

        const sov = query.share_of_voice;
        const avgPosition = query.avg_position;
        const sentiment = query.sentiment || {};
        const cluster = query.topic_cluster;
        const topDomains = query.top_domains || [];

        const sentimentMeta = {
            positive: { color: '#22C55E', label: 'Positive' },
            neutral: { color: '#94A3B8', label: 'Neutral' },
            negative: { color: '#EF4444', label: 'Negative' }
        };
        const sMeta = sentiment.label
            ? (sentimentMeta[sentiment.label] || { color: '#94A3B8', label: sentiment.label })
            : null;

        // Pila con tooltip agrupado (data-domains), igual que en la tabla.
        const topThree = topDomains.slice(0, 3);
        const domainsHtml = topThree.length > 0
            ? `<span class="bm-domain-stack" data-domains="${this.escapeAttr(JSON.stringify(topThree))}">${
                topThree.map(d => this.getDomainFaviconImg(d.domain, 22)).join('')
              }</span>`
            : '<span class="bm-stat-value bm-stat-value--muted">—</span>';

        container.innerHTML = `
            <div class="bm-stat-tile">
                <span class="bm-stat-label">Share of Voice</span>
                <span class="bm-stat-value">${sov != null ? Number(sov).toFixed(1) + '%' : '-'}</span>
            </div>
            <div class="bm-stat-tile">
                <span class="bm-stat-label">Avg. Position</span>
                <span class="bm-stat-value">${avgPosition != null ? '#' + Number(avgPosition).toFixed(1) : '-'}</span>
            </div>
            <div class="bm-stat-tile">
                <span class="bm-stat-label">Sentiment</span>
                <span class="bm-stat-value">
                    ${sMeta ? `<span class="lm-sentiment-dot" style="background:${sMeta.color};"></span>${sMeta.label}` : '-'}
                </span>
            </div>
            <div class="bm-stat-tile">
                <span class="bm-stat-label">Cluster</span>
                <span class="bm-stat-value bm-stat-value--text">${cluster ? this.escapeHtml(cluster) : '—'}</span>
            </div>
            <div class="bm-stat-tile bm-stat-tile--domains">
                <span class="bm-stat-label">Top Domains</span>
                ${domainsHtml}
            </div>
        `;

        // El tooltip agrupado de la pila lo pinta el binder global (con guard).
        this.bindDomainStackTooltips();
    },

renderBrandMentionsModalContent(query) {
        const mentionsByLLM = query.mentions_by_llm || {};
        const llmNames = Object.keys(mentionsByLLM);

        if (llmNames.length === 0) {
            return `
                <div class="brand-mentions-empty">
                    <p>No analysis data available for this prompt yet.</p>
                </div>
            `;
        }

        // Calculate summary
        let brandMentionedCount = 0;
        const allCompetitors = new Set();

        llmNames.forEach(llm => {
            const data = mentionsByLLM[llm];
            if (data.brand_mentioned) brandMentionedCount++;

            Object.keys(data.competitors || {}).forEach(comp => {
                allCompetitors.add(comp);
            });
        });

        const brandCardClass = brandMentionedCount > 0 ? 'brand-positive' : 'brand-negative';
        const brandStatusLabel = brandMentionedCount > 0 ? 'Mentioned' : 'Not mentioned';

        // Build HTML with CSS classes
        let html = `
            <!-- Summary Cards -->
            <div class="brand-summary-grid">
                <!-- Your Brand Card -->
                <div class="brand-summary-card ${brandCardClass}">
                    <div class="brand-summary-card-header">
                        <div class="brand-summary-card-label">Your Brand</div>
                        <div class="brand-summary-card-status">${brandStatusLabel}</div>
                    </div>
                    <div class="brand-summary-card-value">${brandMentionedCount}<span>/${llmNames.length}</span></div>
                    <div class="brand-summary-card-subtitle">LLMs mentioned</div>
                </div>

                <!-- Competitors Card -->
                <div class="brand-summary-card competitors">
                    <div class="brand-summary-card-header">
                        <div class="brand-summary-card-label">Competitors</div>
                    </div>
                    <div class="brand-summary-card-value">${allCompetitors.size}</div>
                    <div class="brand-summary-card-subtitle">Mentioned total</div>
                </div>
            </div>

            <!-- Detailed Breakdown -->
            <div class="llm-breakdown-section">
                <div class="llm-breakdown-title">
                    <span>Breakdown by LLM</span>
                </div>
                <div class="llm-breakdown-list">
        `;

        // LLM rows
        llmNames.forEach(llm => {
            const data = mentionsByLLM[llm];
            const llmDisplayName = this.getLLMDisplayName(llm);
            const position = data.position ? `#${data.position}` : 'N/A';
            const positionClass = data.brand_mentioned ? 'mentioned' : 'not-mentioned';
            const rowClass = data.brand_mentioned ? 'mentioned' : '';

            // Badge de tipo de mención (texto plano, sin emojis)
            let mentionBadge = '';
            if (data.brand_mentioned) {
                const inText = data.brand_mentioned_in_text;
                const inUrls = data.brand_mentioned_in_urls;

                if (inText && inUrls) {
                    mentionBadge = '<span class="llm-row-badge">Text + Citation</span>';
                } else if (inText) {
                    mentionBadge = '<span class="llm-row-badge">Text</span>';
                } else if (inUrls) {
                    mentionBadge = '<span class="llm-row-badge url-only">Citation</span>';
                }
            }

            // Competitors
            const competitorKeys = Object.keys(data.competitors || {});
            let competitorsHtml = '';
            if (competitorKeys.length > 0) {
                competitorsHtml = competitorKeys.map(c =>
                    `<span class="llm-row-competitor-tag">${c}</span>`
                ).join('');
            } else {
                competitorsHtml = '<span class="llm-row-no-competitors">None</span>';
            }

            html += `
                <div class="llm-row ${rowClass}">
                    <div class="llm-row-name">
                        <span class="llm-row-dot" style="background: ${this.getLLMColor(llm)};"></span>
                        ${llmDisplayName}
                    </div>
                    <div class="llm-row-status">
                        <span class="llm-row-position ${positionClass}">${position}</span>
                        ${mentionBadge}
                    </div>
                    <div class="llm-row-competitors">
                        <span class="llm-row-competitors-label">Competitors:</span>
                        ${competitorsHtml}
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;

        return html;
    },

renderClustersManagerList() {
        const list = document.getElementById('clustersList');
        const emptyHint = document.getElementById('clustersEmptyHint');
        if (!list) return;

        const allRows = (this.promptClustersConfig?.clusters || []);
        const counts = (this.promptClustersConfig || {}).counts || {};

        if (allRows.length === 0) {
            list.innerHTML = '';
            if (emptyHint) emptyHint.style.display = 'block';
            this.updatePromptsMgmtTabCounts();
            return;
        }
        if (emptyHint) emptyHint.style.display = 'none';

        list.innerHTML = allRows.map((cluster, idx) => {
            const name = (cluster?.name || '').trim();
            const count = name ? (counts[name] || 0) : 0;
            const countClass = count === 0 ? 'empty' : '';
            const safeName = this.escapeHtml(name);
            return `
                <div class="llm-cluster-row" data-original-name="${safeName}" data-index="${idx}">
                    <input type="text"
                           class="cluster-name-input"
                           value="${safeName}"
                           placeholder="Cluster name (e.g. Satisfaction)"
                           maxlength="80" />
                    <span class="cluster-row-count ${countClass}" title="${count} prompts assigned">
                        <i class="fas fa-comment-dots"></i>
                        ${count}
                    </span>
                    <button type="button" class="btn-cluster-delete" title="Delete cluster"
                            onclick="window.llmMonitoring.removeClusterRow(this)">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
        }).join('');

        this.updatePromptsMgmtTabCounts();
    },

renderClustersPerformanceChart(data, metric) {
        const canvas = document.getElementById('clustersPerformanceChart');
        const container = document.getElementById('clustersChartContainer');
        const emptyBox = document.getElementById('clustersChartEmpty');
        if (!canvas || !container || !emptyBox) return;

        const clustersWithData = (data?.clusters || []).filter(c => c.has_data);
        const anyConfigured = (this.promptClustersConfig?.clusters || []).length > 0;

        if (!anyConfigured) {
            container.style.display = 'none';
            emptyBox.style.display = '';
            const t = document.getElementById('clustersChartEmptyTitle');
            const m = document.getElementById('clustersChartEmptyMsg');
            if (t) t.textContent = 'No clusters configured';
            if (m) m.textContent = 'Group your prompts into topic clusters to compare Share of Voice and average position side by side.';
            return;
        }

        if (clustersWithData.length === 0) {
            container.style.display = 'none';
            emptyBox.style.display = '';
            const t = document.getElementById('clustersChartEmptyTitle');
            const m = document.getElementById('clustersChartEmptyMsg');
            if (t) t.textContent = 'No data yet for your clusters';
            if (m) m.textContent = 'Assign prompts to your clusters and wait for the next analysis to populate these metrics.';
            return;
        }

        container.style.display = '';
        emptyBox.style.display = 'none';

        // Ordenado de mayor a menor Share of Voice: la pregunta que responde este
        // gráfico es "en qué temas soy fuerte y en cuáles no", y ordenar la
        // contesta de un vistazo (antes salían en orden de inserción).
        const ordered = clustersWithData.slice().sort(
            (a, b) => (b.share_of_voice || 0) - (a.share_of_voice || 0)
        );

        const labels = ordered.map(c => c.cluster);
        const sovData = ordered.map(c => c.share_of_voice || 0);

        if (this.charts.clustersPerformance) {
            try { this.charts.clustersPerformance.destroy(); } catch (_) {}
        }

        // Store cluster data for the rich tooltip
        this._clusterChartData = ordered;

        // La posición media acompaña como texto bajo cada barra, no como una
        // segunda serie. Antes vivía en un eje derecho propio: dos escalas cuya
        // alineación es arbitraria sugieren una correlación que no está en los
        // datos, y encima aquí una métrica mejora subiendo (SOV) y la otra
        // bajando (posición), así que las barras se leían al revés.
        this.renderClustersPositionStrip(ordered);

        const self = this;
        const ctx = canvas.getContext('2d');
        this.charts.clustersPerformance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: metric === 'weighted' ? 'Share of Voice (weighted)' : 'Share of Voice',
                        data: sovData,
                        backgroundColor: CSChartTheme.series[0],
                        categoryPercentage: 0.7,
                        barPercentage: 0.85
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    // Serie única: el título de la card ya dice qué se mide.
                    legend: { display: false },
                    tooltip: {
                        enabled: false,
                        external: (context) => self.renderClustersChartTooltip(context)
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: CSChartTheme.ink.primary,
                            font: { weight: '600', size: 12 }
                        }
                    },
                    y: CSChartTheme.percentAxis({
                        max: undefined,
                        suggestedMax: 100,
                        title: {
                            display: true,
                            text: 'Share of Voice (%)',
                            color: CSChartTheme.ink.secondary,
                            font: { size: 11 }
                        }
                    })
                }
            }
        });
    },

/**
 * Posición media por cluster, alineada bajo las barras. Texto plano: el
 * brandbook reserva las formas de cápsula a botones y nav links, así que el
 * estado de un dato se comunica con texto, icono y color.
 */
renderClustersPositionStrip(clusters) {
        const strip = document.getElementById('clustersPositionStrip');
        if (!strip) return;

        if (!clusters || clusters.length === 0) {
            strip.innerHTML = '';
            return;
        }

        strip.innerHTML = clusters.map(c => {
            const pos = c.avg_position;
            const value = pos != null ? `#${pos.toFixed(1)}` : '—';
            const cls = pos != null ? 'cluster-pos-value' : 'cluster-pos-value is-empty';
            return `
                <div class="cluster-pos-item">
                    <span class="cluster-pos-label">Avg pos</span>
                    <span class="${cls}">${value}</span>
                </div>
            `;
        }).join('');
    },

renderClustersChartTooltip(context) {
        let el = document.getElementById('llm-clusters-chart-tooltip');
        if (!el) {
            el = document.createElement('div');
            el.id = 'llm-clusters-chart-tooltip';
            el.className = 'llm-chart-tooltip';
            document.body.appendChild(el);
        }

        const tooltipModel = context.tooltip;
        if (tooltipModel.opacity === 0) {
            el.classList.remove('active');
            return;
        }

        if (tooltipModel.body) {
            const dataIndex = tooltipModel.dataPoints[0]?.dataIndex;
            const clusterData = this._clusterChartData?.[dataIndex];
            const clusterName = clusterData?.cluster || tooltipModel.title[0] || '';

            const sov = clusterData?.share_of_voice ?? '—';
            const pos = clusterData?.avg_position ?? null;
            const mentions = clusterData?.brand_mentions ?? 0;
            const total = clusterData?.total_results ?? 0;

            const sovLabel = (typeof sov === 'number') ? `${sov.toFixed(1)}%` : '—';
            const posLabel = pos != null ? `#${pos.toFixed(1)}` : 'N/A';
            const posNote = pos != null ? '<span style="opacity:0.5;font-size:11px"> (lower is better)</span>' : '';

            el.innerHTML = `
                <div class="llm-chart-tooltip__title">${this.escapeHtml(clusterName)}</div>
                <div class="llm-chart-tooltip__row">
                    <span class="llm-chart-tooltip__dot" style="background:#64748B"></span>
                    <span class="llm-chart-tooltip__label">Share of Voice</span>
                    <span class="llm-chart-tooltip__value">${sovLabel}</span>
                </div>
                <div class="llm-chart-tooltip__row">
                    <span class="llm-chart-tooltip__dot" style="background:#D9F9B8"></span>
                    <span class="llm-chart-tooltip__label">Avg position</span>
                    <span class="llm-chart-tooltip__value">${posLabel}${posNote}</span>
                </div>
                <div class="llm-chart-tooltip__row" style="border-top:1px solid rgba(255,255,255,0.06);margin-top:4px;padding-top:6px;">
                    <span class="llm-chart-tooltip__label" style="opacity:0.4">Brand mentions</span>
                    <span class="llm-chart-tooltip__value" style="font-size:12px">${mentions} / ${total}</span>
                </div>
            `;
        }

        const pos = context.chart.canvas.getBoundingClientRect();
        const ttW = el.offsetWidth || 200;
        const ttH = el.offsetHeight || 100;
        const caretX = pos.left + window.scrollX + tooltipModel.caretX;
        const caretY = pos.top + window.scrollY + tooltipModel.caretY;
        const vpR = window.innerWidth + window.scrollX;
        const vpB = window.innerHeight + window.scrollY;

        let left = caretX + 12;
        if (left + ttW > vpR - 16) left = caretX - ttW - 12;
        let top = caretY - 10;
        if (top + ttH > vpB - 16) top = caretY - ttH + 10;
        left = Math.max(8, left);
        top = Math.max(8, top);

        el.style.left = left + 'px';
        el.style.top = top + 'px';
        el.classList.add('active');
    }

});
