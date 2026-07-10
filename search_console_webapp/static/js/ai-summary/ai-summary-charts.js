/**
 * AI Summary - Charts
 * Gráfico de tendencia de visibilidad por canal (Chart.js).
 */

// Paleta brandbook clicandseo v1.1 (sin colores inventados)
const CHANNEL_COLORS = {
    ai_overview: { border: '#0F172A', background: 'rgba(15, 23, 42, 0.05)' },
    ai_mode: { border: '#94A3B8', background: 'rgba(148, 163, 184, 0.08)' },
    llm: { border: '#3CB371', background: 'rgba(60, 179, 113, 0.07)' },
};

const CHANNEL_LABELS = {
    ai_overview: 'Google AI Overview',
    ai_mode: 'Google AI Mode',
    llm: 'LLMs (mention rate)',
};

/**
 * Tooltip externo enriquecido (mismo componente visual que las gráficas de
 * LLM Monitoring): tarjeta oscura con título en mayúsculas y filas con dot
 * de color por dataset. Chart.js lo invoca con enabled:false + external.
 */
export function renderRichChartTooltip(context) {
    let tooltipEl = document.getElementById('ais-chart-tooltip');
    if (!tooltipEl) {
        tooltipEl = document.createElement('div');
        tooltipEl.id = 'ais-chart-tooltip';
        tooltipEl.className = 'ais-chart-tooltip';
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
        // El histórico del score va en puntos (0-100); el resto, en %
        const suffix = chart.canvas.id === 'scoreHistoryChart' ? '' : '%';

        let rows = '';
        chart.data.datasets.forEach((ds, i) => {
            const meta = chart.getDatasetMeta(i);
            if (meta.hidden) return;
            const value = ds.data[dataIndex];
            if (value === null || value === undefined) return;
            const color = ds.borderColor || ds.backgroundColor || '#888';
            rows += `<div class="ais-chart-tooltip__row">
                <span class="ais-chart-tooltip__dot" style="background:${color}"></span>
                <span class="ais-chart-tooltip__label">${this.escapeHtml(ds.label)}</span>
                <span class="ais-chart-tooltip__value">${Number(value).toFixed(1)}${suffix}</span>
            </div>`;
        });

        tooltipEl.innerHTML = `<div class="ais-chart-tooltip__title">${this.escapeHtml(titleText)}</div>${rows}`;
    }

    // Posicionamiento con flip en bordes (mismo comportamiento que LLM)
    const position = context.chart.canvas.getBoundingClientRect();
    const tooltipWidth = tooltipEl.offsetWidth || 200;
    const tooltipHeight = tooltipEl.offsetHeight || 100;
    const caretAbsX = position.left + window.scrollX + tooltipModel.caretX;
    const caretAbsY = position.top + window.scrollY + tooltipModel.caretY;
    const viewportRight = window.innerWidth + window.scrollX;
    const viewportBottom = window.innerHeight + window.scrollY;

    let leftPos = caretAbsX + 12;
    if (leftPos + tooltipWidth > viewportRight - 16) {
        leftPos = caretAbsX - tooltipWidth - 12;
    }
    let topPos = caretAbsY - 10;
    if (topPos + tooltipHeight > viewportBottom - 16) {
        topPos = caretAbsY - tooltipHeight + 10;
    }
    tooltipEl.style.left = Math.max(8, leftPos) + 'px';
    tooltipEl.style.top = Math.max(8, topPos) + 'px';
    tooltipEl.classList.add('active');
}

export function renderScoreHistoryChart(history) {
    const canvas = this.elements.scoreHistoryChart;
    if (!canvas || typeof Chart === 'undefined') return;

    if (this.charts.scoreHistory) {
        this.charts.scoreHistory.destroy();
        this.charts.scoreHistory = null;
    }

    this.charts.scoreHistory = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: history.map(p => p.date),
            datasets: [{
                label: 'AI Visibility Score',
                data: history.map(p => p.score),
                borderColor: '#0F172A',
                backgroundColor: 'rgba(217, 249, 184, 0.35)',
                borderWidth: 2,
                pointRadius: 2,
                pointHoverRadius: 5,
                tension: 0.3,
                fill: true,
                clip: false,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: false,
                    external: (context) => this.renderRichChartTooltip(context)
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(0,0,0,0.04)' }
                },
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 10 }
                }
            }
        }
    });
}

export function renderTrendChart(channels) {
    const canvas = this.elements.trendChart;
    if (!canvas || typeof Chart === 'undefined') return;

    if (this.charts.trend) {
        this.charts.trend.destroy();
        this.charts.trend = null;
    }

    // Unificar el eje X con todas las fechas presentes en cualquier canal
    const allDates = new Set();
    Object.values(channels).forEach(channel => {
        (channel.timeseries || []).forEach(point => allDates.add(point.date));
    });
    const labels = Array.from(allDates).sort();
    if (!labels.length) return;

    const datasets = Object.entries(CHANNEL_LABELS)
        .filter(([channel]) => (channels[channel]?.timeseries || []).length > 0)
        .map(([channel, label]) => {
            const byDate = new Map(
                (channels[channel].timeseries || []).map(p => [p.date, p.value])
            );
            return {
                label,
                data: labels.map(d => byDate.has(d) ? byDate.get(d) : null),
                borderColor: CHANNEL_COLORS[channel].border,
                backgroundColor: CHANNEL_COLORS[channel].background,
                borderWidth: 2,
                pointRadius: 2,
                pointHoverRadius: 5,
                tension: 0.3,
                spanGaps: true,
                fill: false,
                clip: false,
            };
        });

    this.charts.trend = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { usePointStyle: true, boxWidth: 8, padding: 16 }
                },
                tooltip: {
                    enabled: false,
                    external: (context) => this.renderRichChartTooltip(context)
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { callback: value => `${value}%` },
                    grid: { color: 'rgba(0,0,0,0.04)' }
                },
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 12 }
                }
            }
        }
    });
}
