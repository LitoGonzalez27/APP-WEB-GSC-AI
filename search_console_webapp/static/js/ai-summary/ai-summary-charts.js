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
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y != null ? ctx.parsed.y.toFixed(1) + '%' : 'n/a'}`
                    }
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
