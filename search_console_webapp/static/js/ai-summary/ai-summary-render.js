/**
 * AI Summary - Render
 * Carga y renderizado del resumen: score, tarjetas por canal,
 * highlights y ranking unificado de competidores.
 */

const CHANNEL_META = {
    ai_overview: {
        label: 'Google AI Overview',
        icon: 'fa-cogs',
        link: '/manual-ai/',
        metricLabel: 'AIO visibility',
    },
    ai_mode: {
        label: 'Google AI Mode',
        icon: 'fa-brain',
        link: '/ai-mode-projects/',
        metricLabel: 'Brand visibility',
    },
    llm: {
        label: 'LLMs (ChatGPT, Gemini...)',
        icon: 'fa-eye',
        link: '/llm-monitoring',
        metricLabel: 'Mention rate',
    },
};

export async function loadSummary() {
    if (!this.currentBrandId) return;

    this.hideSetup();
    this.showLoading(true);

    try {
        const data = await this.fetchJson(
            `${this.apiBase}/brands/${this.currentBrandId}/summary?days=${this.days}`
        );
        this.currentSummary = data;
        this.renderSummary(data);
    } catch (error) {
        console.error('❌ Error loading summary:', error);
        this.showLoading(false);
        alert(error.message);
        return;
    }

    this.showLoading(false);
    if (this.elements.summaryContent) {
        this.elements.summaryContent.style.display = 'block';
    }
}

export function renderSummary(data) {
    this.renderScore(data.score);
    this.renderHighlights(data.highlights || []);
    this.renderChannelCards(data.channels || {});
    this.renderTrendChart(data.channels || {});
    this.renderCompetitorsTable(data.competitors_unified || []);
}

export function renderScore(score) {
    const { scoreValue, scoreDelta, scoreCoverage } = this.elements;
    if (!scoreValue) return;

    if (score.value == null) {
        scoreValue.textContent = '–';
        scoreDelta.textContent = 'No data in this period';
        scoreDelta.className = 'score-delta delta-flat';
        scoreCoverage.textContent = '';
        return;
    }

    scoreValue.textContent = score.value.toFixed(1);

    if (score.delta == null) {
        scoreDelta.textContent = 'No previous period to compare';
        scoreDelta.className = 'score-delta delta-flat';
    } else if (Math.abs(score.delta) < 0.5) {
        scoreDelta.innerHTML = '<i class="fas fa-equals"></i> Stable vs previous period';
        scoreDelta.className = 'score-delta delta-flat';
    } else {
        const up = score.delta > 0;
        scoreDelta.innerHTML =
            `<i class="fas fa-arrow-${up ? 'up' : 'down'}"></i> ${up ? '+' : ''}${score.delta.toFixed(1)} pts vs previous period`;
        scoreDelta.className = `score-delta ${up ? 'delta-up' : 'delta-down'}`;
    }

    const used = score.channels_used || [];
    const total = used.length + (score.channels_missing || []).length;
    scoreCoverage.textContent =
        `Based on ${used.length} of ${total} channels: ${used.map(c => CHANNEL_META[c]?.label || c).join(', ')}`;
}

export function renderHighlights(highlights) {
    const container = this.elements.highlightsList;
    if (!container) return;

    if (!highlights.length) {
        container.innerHTML = '<div class="highlight-item highlight-info"><i class="fas fa-circle-info"></i> No notable changes in this period.</div>';
        return;
    }

    const icons = {
        positive: 'fa-arrow-trend-up',
        negative: 'fa-triangle-exclamation',
        neutral: 'fa-scale-unbalanced',
        info: 'fa-circle-info',
    };

    container.innerHTML = highlights.map(h => `
        <div class="highlight-item highlight-${h.severity}">
            <i class="fas ${icons[h.severity] || 'fa-circle-info'}"></i>
            <span>${this.escapeHtml(h.text)}</span>
        </div>
    `).join('');
}

export function renderChannelCards(channels) {
    const container = this.elements.channelCards;
    if (!container) return;

    container.innerHTML = Object.entries(CHANNEL_META)
        .map(([channel, meta]) => this.renderChannelCard(channel, meta, channels[channel]))
        .join('');
}

export function renderChannelCard(channel, meta, summary) {
    if (!summary || (!summary.available && !summary.project_id)) {
        return `
            <div class="channel-card channel-missing">
                <div class="channel-card-header">
                    <h4><i class="fas ${meta.icon}"></i> ${meta.label}</h4>
                </div>
                <p class="channel-missing-text">
                    Not monitored for this brand.
                    <a href="${meta.link}" class="channel-card-link">Set it up →</a>
                </p>
            </div>
        `;
    }

    if (!summary.available) {
        return `
            <div class="channel-card channel-missing">
                <div class="channel-card-header">
                    <h4><i class="fas ${meta.icon}"></i> ${meta.label}</h4>
                    <a href="${meta.link}" class="channel-card-link">Open <i class="fas fa-arrow-right"></i></a>
                </div>
                <p class="channel-missing-text">No data yet in this period.</p>
            </div>
        `;
    }

    const deltaHtml = formatDelta(summary.visibility_delta);
    const trendClass = summary.visibility_delta > 0.5 ? 'trend-up'
        : summary.visibility_delta < -0.5 ? 'trend-down' : '';

    const secondary = [];
    if (summary.avg_position != null) {
        secondary.push(metricBlock('Avg position', `#${summary.avg_position.toFixed(1)}`, formatDelta(summary.position_delta, true)));
    }

    const extras = summary.extras || {};
    if (channel === 'ai_overview' && extras.aio_weight_pct != null) {
        secondary.push(metricBlock('Keywords with AIO', `${extras.aio_weight_pct.toFixed(1)}%`));
    }
    if (channel === 'llm') {
        if (extras.share_of_voice != null) {
            secondary.push(metricBlock('Share of Voice', `${extras.share_of_voice.toFixed(1)}%`, formatDelta(extras.sov_delta)));
        }
        const s = extras.sentiment || {};
        if (s.positive != null) {
            secondary.push(metricBlock('Sentiment',
                `<span class="sentiment-dots">
                    <span class="sentiment-dot positive"></span>${s.positive}%
                    <span class="sentiment-dot neutral"></span>${s.neutral}%
                    <span class="sentiment-dot negative"></span>${s.negative}%
                </span>`));
        }
        const byLlm = extras.by_llm || {};
        const parts = Object.values(byLlm)
            .filter(v => v.mention_rate != null)
            .map(v => `${v.label} ${v.mention_rate.toFixed(0)}%`);
        if (parts.length) {
            secondary.push(metricBlock('By model', parts.join(' · ')));
        }
    }

    return `
        <div class="channel-card ${trendClass}">
            <div class="channel-card-header">
                <h4><i class="fas ${meta.icon}"></i> ${meta.label}</h4>
                <a href="${meta.link}" class="channel-card-link">Open <i class="fas fa-arrow-right"></i></a>
            </div>
            <div class="channel-metric-main">
                <span class="channel-metric-value">${summary.visibility_pct.toFixed(1)}%</span>
                ${deltaHtml}
            </div>
            <div class="channel-metric-label">${meta.metricLabel}</div>
            <div class="channel-secondary-metrics">${secondary.join('')}</div>
        </div>
    `;
}

export function renderCompetitorsTable(competitors) {
    const tbody = this.elements.competitorsTableBody;
    if (!tbody) return;

    if (!competitors.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="metric-na">No competitor data in this period.</td></tr>';
        return;
    }

    tbody.innerHTML = competitors.map(c => {
        const cell = (value, suffix = '%') => value == null
            ? '<span class="metric-na">–</span>'
            : `${Number(value).toFixed(1)}${suffix}`;
        return `
            <tr class="${c.is_brand ? 'row-brand' : ''}">
                <td>${c.rank}</td>
                <td>
                    <div class="domain-cell">
                        ${this.escapeHtml(c.domain)}
                        ${c.is_brand ? '<span class="brand-badge">YOU</span>' : ''}
                    </div>
                </td>
                <td>${cell(c.channels.ai_overview)}</td>
                <td>${cell(c.channels.ai_mode)}</td>
                <td>${cell(c.channels.llm)}</td>
                <td><strong>${cell(c.avg_visibility)}</strong></td>
            </tr>
        `;
    }).join('');
}

// ----------------------------------------------------------------------
// Helpers (módulo privado, no van al prototype)
// ----------------------------------------------------------------------

function formatDelta(delta, invertColors = false) {
    if (delta == null) {
        return '<span class="channel-delta delta-flat">–</span>';
    }
    if (Math.abs(delta) < 0.05) {
        return '<span class="channel-delta delta-flat"><i class="fas fa-equals"></i></span>';
    }
    const up = delta > 0;
    // Para posición, bajar es bueno (invertColors)
    const good = invertColors ? !up : up;
    return `
        <span class="channel-delta ${good ? 'delta-up' : 'delta-down'}">
            <i class="fas fa-arrow-${up ? 'up' : 'down'}"></i> ${up ? '+' : ''}${delta.toFixed(1)}
        </span>
    `;
}

function metricBlock(label, value, deltaHtml = '') {
    return `
        <div class="channel-secondary-metric">
            ${label}
            <strong>${value} ${deltaHtml}</strong>
        </div>
    `;
}
