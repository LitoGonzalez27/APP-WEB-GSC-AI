/**
 * AI Summary - Render
 * Carga y renderizado del resumen: score, tarjetas por canal,
 * highlights y ranking unificado de competidores.
 */

const CHANNEL_META = {
    ai_overview: {
        label: 'Google AI Overview',
        link: '/manual-ai/',
        metricLabel: 'AIO visibility',
    },
    ai_mode: {
        label: 'Google AI Mode',
        link: '/ai-mode-projects/',
        metricLabel: 'Brand visibility',
    },
    llm: {
        label: 'LLMs (ChatGPT, Gemini...)',
        link: '/llm-monitoring',
        metricLabel: 'Mention rate',
    },
};

export async function loadSummary() {
    if (!this.currentBrandId) return;

    this.hideSetup();
    this.showLoading(true);

    let data;
    try {
        data = await this.fetchJson(
            `${this.apiBase}/brands/${this.currentBrandId}/summary?period=${this.period}`
        );
    } catch (error) {
        console.error('❌ Error loading summary:', error);
        this.showLoading(false);
        alert(error.message);
        return;
    }

    // Mostrar el contenedor ANTES de renderizar: Chart.js no pinta los
    // datasets si el canvas se crea dentro de un contenedor display:none.
    this.showLoading(false);
    if (this.elements.summaryContent) {
        this.elements.summaryContent.style.display = 'block';
    }
    this.renderBrandIdentity();
    this.renderSummary(data);
    this.loadScoreHistory();
}

export function renderBrandIdentity() {
    const brand = this.getCurrentBrand();
    if (!brand) return;
    if (this.elements.summaryBrandTitle) {
        this.elements.summaryBrandTitle.textContent = brand.brand_name;
    }
    if (this.elements.summaryBrandDomain) {
        this.elements.summaryBrandDomain.textContent = brand.brand_domain;
    }
    const logo = this.elements.summaryBrandLogo;
    if (logo) {
        logo.src = this.getDomainLogoUrl(brand.brand_domain);
        logo.style.display = 'block';
        logo.onerror = () => { logo.style.display = 'none'; };
    }
    // Acciones de dueño: editar, compartir y desvincular no aplican a viewers
    if (this.elements.editBrandBtn) {
        this.elements.editBrandBtn.style.display = brand.is_owner ? 'inline-flex' : 'none';
    }
    if (this.elements.shareBrandBtn) {
        this.elements.shareBrandBtn.style.display = brand.is_owner ? 'inline-flex' : 'none';
    }
    if (this.elements.deleteBrandBtn) {
        this.elements.deleteBrandBtn.style.display = brand.is_owner ? 'inline-flex' : 'none';
    }
}

export async function loadScoreHistory() {
    const panel = this.elements.scoreHistoryPanel;
    if (!panel || !this.currentBrandId) return;
    try {
        const data = await this.fetchJson(
            `${this.apiBase}/brands/${this.currentBrandId}/score-history?months=6`
        );
        const history = data.history || [];
        if (history.length < 2) {
            panel.style.display = 'none';
            return;
        }
        panel.style.display = 'block';
        this.renderScoreHistoryChart(history);
    } catch (error) {
        console.warn('⚠️ Score history unavailable:', error.message);
        panel.style.display = 'none';
    }
}

export function renderOpportunities(opportunities) {
    const panel = this.elements.opportunitiesPanel;
    if (!panel) return;
    const aio = opportunities?.aio || [];
    const llm = opportunities?.llm || [];

    if (!aio.length && !llm.length) {
        panel.style.display = 'none';
        return;
    }
    panel.style.display = 'block';

    const fillColumn = (columnEl, listEl, items, renderItem) => {
        if (!columnEl || !listEl) return;
        columnEl.style.display = items.length ? 'block' : 'none';
        listEl.innerHTML = items.map(renderItem).join('');
    };

    fillColumn(this.elements.opportunitiesAioColumn, this.elements.opportunitiesAioList, aio, item => `
        <li>
            <strong>"${this.escapeHtml(item.keyword)}"</strong>
            <span class="opportunity-competitors">cited: ${item.competitors.map(c => this.escapeHtml(c)).join(', ')}</span>
            <span class="opportunity-meta">missed ${item.times_missed}×</span>
        </li>
    `);

    fillColumn(this.elements.opportunitiesLlmColumn, this.elements.opportunitiesLlmList, llm, item => {
        const prompt = item.prompt.length > 90 ? `${item.prompt.slice(0, 90)}…` : item.prompt;
        return `
        <li>
            <strong>"${this.escapeHtml(prompt)}"</strong>
            <span class="opportunity-competitors">mentioned: ${item.competitors.map(c => this.escapeHtml(c)).join(', ')}</span>
            <span class="opportunity-meta">missed ${item.times_missed}×</span>
        </li>
    `;
    });
}

export function renderSummary(data) {
    this.renderScore(data.score);
    this.renderHighlights(data.highlights || []);
    this.renderChannelCards(data.channels || {});
    this.renderTrendChart(data.channels || {});
    this.renderCompetitorsTable(data.competitors_unified || []);
    this.renderOpportunities(data.opportunities);
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
    // Deep link al proyecto concreto dentro de su módulo (no al listado
    // genérico): cada dashboard lee ?open_project=<id> al inicializarse.
    const projectLink = summary?.project_id
        ? `${meta.link}${meta.link.includes('?') ? '&' : '?'}open_project=${summary.project_id}`
        : meta.link;

    if (!summary || (!summary.available && !summary.project_id)) {
        // Si el usuario ya tiene un proyecto propio cuyo dominio coincide con
        // la marca, ofrecer vincularlo con un clic en vez del alta genérica.
        const linkable = this.findLinkableProject(channel);
        const action = linkable
            ? `<button type="button" class="channel-quick-link" data-channel="${channel}" data-project-id="${linkable.id}">
                   <i class="fas fa-link"></i> Link "${this.escapeHtml(linkable.name)}"
               </button>`
            : `<a href="${meta.link}" class="channel-card-link">Set it up →</a>`;
        return `
            <div class="channel-card channel-missing">
                <div class="channel-card-header">
                    <h4>${meta.label}</h4>
                </div>
                <p class="channel-missing-text">
                    Not monitored for this brand.
                </p>
                <div class="channel-missing-action">${action}</div>
            </div>
        `;
    }

    // visibility_pct null con available=true no debería llegar (los adapters
    // lo marcan como no_data), pero un null aquí rompería todo el render.
    if (!summary.available || summary.visibility_pct == null) {
        return `
            <div class="channel-card channel-missing">
                <div class="channel-card-header">
                    <h4>${meta.label}</h4>
                    <a href="${projectLink}" class="channel-card-link">Open <i class="fas fa-arrow-right"></i></a>
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
            .map(v => `${this.escapeHtml(v.label)} ${v.mention_rate.toFixed(0)}%`);
        if (parts.length) {
            secondary.push(metricBlock('By model', parts.join(' · ')));
        }
    }

    return `
        <div class="channel-card ${trendClass}">
            <div class="channel-card-header">
                <h4>${meta.label}</h4>
                <a href="${projectLink}" class="channel-card-link">Open <i class="fas fa-arrow-right"></i></a>
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
                        <img class="domain-logo" src="${this.getDomainLogoUrl(c.domain)}" alt="" loading="lazy" onerror="this.style.display='none'">
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
