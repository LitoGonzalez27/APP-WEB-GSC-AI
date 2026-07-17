/**
 * LLM Monitoring - métodos de prototipo: charts
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

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

        const barColors = [
            'rgba(59, 130, 246, 0.8)',
            'rgba(16, 185, 129, 0.8)',
            'rgba(249, 115, 22, 0.8)',
            'rgba(139, 92, 246, 0.8)'
        ];
        const borderColors = [
            'rgb(59, 130, 246)',
            'rgb(16, 185, 129)',
            'rgb(249, 115, 22)',
            'rgb(139, 92, 246)'
        ];

        const datasets = [{
            label: 'Mention Rate (%)',
            data: mentionRates,
            backgroundColor: barColors,
            borderColor: borderColors,
            borderWidth: 1
        }];

        // Add previous period as ghost bars if available
        if (hasPrev) {
            datasets.push({
                label: 'Previous Period',
                data: prevRates,
                backgroundColor: barColors.map(c => c.replace(/[\d.]+\)$/, '0.25)')),
                borderColor: borderColors.map(c => c.replace('rgb', 'rgba').replace(')', ', 0.3)')),
                borderWidth: 1,
                borderDash: [4, 4]
            });
        }

        // Create chart
        this.charts.mentionRate = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: llms.map(llm => this.getLLMDisplayName(llm)),
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: value => value + '%'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#f1f5f9',
                        bodyColor: '#e2e8f0',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        padding: 14,
                        cornerRadius: 10,
                        titleFont: { size: 13, weight: '600' },
                        bodyFont: { size: 12 },
                        boxPadding: 6,
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
        const providerColors = {
            openai: 'rgba(16, 163, 127, 0.85)', anthropic: 'rgba(204, 153, 0, 0.85)',
            google: 'rgba(66, 133, 244, 0.85)', perplexity: 'rgba(96, 91, 255, 0.85)'
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
                colors.push(providerColors[prov] || 'rgba(107, 114, 128, 0.8)');
            }
        }
        // Include any providers not in the fixed order
        for (const [prov, rate] of Object.entries(byLlm)) {
            if (!providerOrder.includes(prov)) {
                labels.push(providerLabels[prov] || prov);
                data.push(rate);
                colors.push('rgba(107, 114, 128, 0.8)');
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

            // Si no hay datos, simplemente retornar sin renderizar
            if (!dates || dates.length === 0 || !datasets || datasets.length === 0) {
                console.warn('⚠️ No data available for Share of Voice chart');
                return;
            }

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
                    datasets: datasets.map(ds => ({
                        ...ds,
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
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: value => `${value}%`,
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            },
                            grid: {
                                color: '#f3f4f6',
                                drawBorder: false
                            },
                            title: {
                                display: true,
                                text: 'Share of Voice (%)',
                                font: {
                                    size: 13,
                                    weight: '600'
                                },
                                color: '#374151'
                            }
                        }
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
                return;
            }

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
                    datasets: mentions_datasets.map(ds => ({
                        ...ds,
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
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: value => Math.round(value),
                                font: {
                                    size: 12,
                                    weight: '500'
                                },
                                color: '#6b7280'
                            },
                            grid: {
                                color: '#f3f4f6',
                                drawBorder: false
                            },
                            title: {
                                display: true,
                                text: 'Total Mentions',
                                font: {
                                    size: 13,
                                    weight: '600'
                                },
                                color: '#374151'
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
                        borderWidth: 3,
                        borderColor: '#fff',
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                font: {
                                    size: 13,
                                    weight: '500'
                                },
                                color: '#374151',
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            titleFont: {
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                size: 12
                            },
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
                colors: [
                    'rgba(34, 197, 94, 0.8)',   // Green for positive
                    'rgba(245, 158, 11, 0.8)',  // Orange for neutral
                    'rgba(239, 68, 68, 0.8)'    // Red for negative
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
                        borderWidth: 3,
                        borderColor: '#fff',
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
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
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                font: {
                                    size: 13,
                                    weight: '500'
                                },
                                color: '#374151',
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            titleFont: {
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                size: 12
                            },
                            footerFont: {
                                size: 11,
                                style: 'italic',
                                weight: '400'
                            },
                            footerColor: '#D8F9B8',
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

            // Colores para los LLMs
            const llmColors = {
                'openai': { bg: 'rgba(16, 163, 127, 0.2)', border: '#10A37F' },
                'anthropic': { bg: 'rgba(204, 148, 102, 0.2)', border: '#CC9466' },
                'google': { bg: 'rgba(66, 133, 244, 0.2)', border: '#4285F4' },
                'perplexity': { bg: 'rgba(32, 178, 170, 0.2)', border: '#20B2AA' }
            };

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

            // ✨ Solo una línea: Overall Visibility (más limpio y claro)
            const datasets = [
                {
                    label: 'Visibility Rate',
                    data: visibilityData,
                    borderColor: '#8BC34A',
                    backgroundColor: 'rgba(139, 195, 74, 0.2)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 5,
                    pointHoverRadius: 8,
                    pointBackgroundColor: '#8BC34A',
                    pointBorderColor: 'white',
                    pointBorderWidth: 2
                }
            ];

            // Crear gráfico
            const ctx = canvas.getContext('2d');
            this.historyChart = new Chart(ctx, {
                type: 'line',
                data: { labels, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(22, 22, 22, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#e5e7eb',
                            padding: 14,
                            cornerRadius: 10,
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
                                            const icon = llmInfo.mentioned ? '✅' : '❌';
                                            const displayName = self.getLLMDisplayName(llm);
                                            lines.push(`${icon} ${displayName}`);
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
                            ticks: { 
                                color: '#6b7280',
                                font: { size: 11 },
                                maxRotation: 45
                            }
                        },
                        y: {
                            min: 0,
                            max: 100,
                            grid: { 
                                color: 'rgba(0, 0, 0, 0.06)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#6b7280',
                                callback: value => `${value}%`,
                                font: { size: 11 },
                                stepSize: 25
                            }
                        }
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
                    <i class="fas fa-exclamation-triangle"></i>
                    <span>Error loading history</span>
                `;
            }
        }
    },

renderBrandMentionsModalContent(query) {
        const mentionsByLLM = query.mentions_by_llm || {};
        const llmNames = Object.keys(mentionsByLLM);

        if (llmNames.length === 0) {
            return `
                <div class="brand-mentions-empty">
                    <i class="fas fa-info-circle"></i>
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
        const brandIcon = brandMentionedCount > 0 ? '✅' : '❌';

        // Build HTML with CSS classes
        let html = `
            <!-- Summary Cards -->
            <div class="brand-summary-grid">
                <!-- Your Brand Card -->
                <div class="brand-summary-card ${brandCardClass}">
                    <div class="brand-summary-card-header">
                        <div class="brand-summary-card-label">Your Brand</div>
                        <div class="brand-summary-card-icon">${brandIcon}</div>
                    </div>
                    <div class="brand-summary-card-value">${brandMentionedCount}<span>/${llmNames.length}</span></div>
                    <div class="brand-summary-card-subtitle">LLMs mentioned</div>
                </div>
                
                <!-- Competitors Card -->
                <div class="brand-summary-card competitors">
                    <div class="brand-summary-card-header">
                        <div class="brand-summary-card-label">Competitors</div>
                        <div class="brand-summary-card-icon">⚔️</div>
                    </div>
                    <div class="brand-summary-card-value">${allCompetitors.size}</div>
                    <div class="brand-summary-card-subtitle">Mentioned total</div>
                </div>
            </div>
            
            <!-- Detailed Breakdown -->
            <div class="llm-breakdown-section">
                <div class="llm-breakdown-title">
                    <i class="fas fa-list-ul"></i>
                    <span>Breakdown by LLM</span>
                </div>
                <div class="llm-breakdown-list">
        `;

        // LLM rows
        llmNames.forEach(llm => {
            const data = mentionsByLLM[llm];
            const llmDisplayName = this.getLLMDisplayName(llm);
            const brandIcon = data.brand_mentioned ? '✅' : '❌';
            const position = data.position ? `#${data.position}` : 'N/A';
            const positionClass = data.brand_mentioned ? 'mentioned' : 'not-mentioned';
            const rowClass = data.brand_mentioned ? 'mentioned' : '';

            // Badge de tipo de mención
            let mentionBadge = '';
            if (data.brand_mentioned) {
                const inText = data.brand_mentioned_in_text;
                const inUrls = data.brand_mentioned_in_urls;

                if (inText && inUrls) {
                    mentionBadge = '<span class="llm-row-badge" title="Mentioned in text and URLs">📝🔗</span>';
                } else if (inText) {
                    mentionBadge = '<span class="llm-row-badge" title="Mentioned in text">📝</span>';
                } else if (inUrls) {
                    mentionBadge = '<span class="llm-row-badge url-only" title="Mentioned in URLs only">🔗</span>';
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
                        <i class="${this.getLLMIcon(llm)}" style="color: ${this.getLLMColor(llm)};"></i>
                        ${llmDisplayName}
                    </div>
                    <div class="llm-row-status">
                        <span class="llm-row-status-icon">${brandIcon}</span>
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
            
            <!-- Legend -->
            <div class="brand-mentions-legend">
                <div class="brand-mentions-legend-title">
                    <i class="fas fa-info-circle"></i>
                    <span>Mention Type Legend</span>
                </div>
                <div class="brand-mentions-legend-grid">
                    <div class="brand-mentions-legend-item">
                        <span class="brand-mentions-legend-badge text">📝</span>
                        <span class="brand-mentions-legend-text">Text mention</span>
                    </div>
                    <div class="brand-mentions-legend-item">
                        <span class="brand-mentions-legend-badge url">🔗</span>
                        <span class="brand-mentions-legend-text">URL citation</span>
                    </div>
                    <div class="brand-mentions-legend-item">
                        <span class="brand-mentions-legend-badge both">📝🔗</span>
                        <span class="brand-mentions-legend-text">Both</span>
                    </div>
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

        const labels = clustersWithData.map(c => c.cluster);
        const sovData = clustersWithData.map(c => c.share_of_voice || 0);
        const posData = clustersWithData.map(c => c.avg_position == null ? null : c.avg_position);

        if (this.charts.clustersPerformance) {
            try { this.charts.clustersPerformance.destroy(); } catch (_) {}
        }

        // Store cluster data for the rich tooltip
        this._clusterChartData = clustersWithData;

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
                        backgroundColor: 'rgba(15, 23, 42, 0.82)',
                        borderColor: '#0F172A',
                        borderWidth: 0,
                        borderRadius: { topLeft: 6, topRight: 6 },
                        yAxisID: 'y',
                        categoryPercentage: 0.65,
                        barPercentage: 0.85,
                        order: 1
                    },
                    {
                        label: 'Avg position',
                        data: posData,
                        backgroundColor: 'rgba(217, 249, 184, 0.85)',
                        borderColor: '#D9F9B8',
                        borderWidth: 0,
                        borderRadius: { topLeft: 6, topRight: 6 },
                        yAxisID: 'y1',
                        categoryPercentage: 0.65,
                        barPercentage: 0.85,
                        order: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'rectRounded',
                            padding: 18,
                            font: { size: 12, family: "'Inter Tight', sans-serif", weight: '500' },
                            color: '#64748B'
                        }
                    },
                    tooltip: {
                        enabled: false,
                        external: (context) => self.renderClustersChartTooltip(context)
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        border: { display: false },
                        ticks: {
                            color: '#0F172A',
                            font: { weight: '600', size: 12, family: "'Inter Tight', sans-serif" }
                        }
                    },
                    y: {
                        type: 'linear',
                        position: 'left',
                        beginAtZero: true,
                        suggestedMax: 100,
                        title: {
                            display: true,
                            text: 'Share of Voice (%)',
                            color: '#64748B',
                            font: { size: 11 }
                        },
                        ticks: {
                            callback: (v) => `${v}%`,
                            color: '#94A3B8',
                            font: { size: 11 }
                        },
                        grid: { color: 'rgba(226, 232, 240, 0.5)', drawBorder: false }
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        beginAtZero: true,
                        // Both bars grow upward from 0. Lower position = smaller bar.
                        // The tooltip explains that lower is better.
                        title: {
                            display: true,
                            text: 'Avg position',
                            color: '#64748B',
                            font: { size: 11 }
                        },
                        ticks: {
                            callback: (v) => `#${v}`,
                            color: '#94A3B8',
                            font: { size: 11 }
                        },
                        grid: { drawOnChartArea: false, drawBorder: false }
                    }
                }
            }
        });
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
