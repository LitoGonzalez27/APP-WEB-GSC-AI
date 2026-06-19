/**
 * Manual AI System - Analytics — AIO vs Organic comparison (2026-04-09)
 *
 * Extraído verbatim de manual-ai-analytics.js (refactor Fase 4).
 */

import { escapeHtml } from './manual-ai-utils.js';

// ================================
// AIO vs ORGANIC COMPARISON (2026-04-09)
// ================================
// Compara URLs en el top 10 orgánico vs URLs citadas como referencias
// por el AI Overview. Identifica 4 cuadrantes para el dominio del
// proyecto: 🟢 Rank & Cited / 🟡 Rank-only (GEO opp) / 🔵 Cited-only
// (SEO opp) / ⚪ Neither. Reutiliza datos ya guardados en raw_serp_data.

export async function loadAioVsOrganicComparison(projectId) {
    if (!projectId) {
        this.showNoAioVsOrganicMessage();
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    try {
        const response = await fetch(
            `/manual-ai/api/projects/${projectId}/aio-vs-organic?days=${days}`
        );

        if (!response.ok) {
            if (response.status === 404) {
                this.showNoAioVsOrganicMessage();
                return;
            }
            throw new Error('Failed to load AIO vs Organic comparison');
        }

        const data = await response.json();
        if (!data.success || !data.comparison) {
            this.showNoAioVsOrganicMessage();
            return;
        }

        this.renderAioVsOrganicComparison(data.comparison);

    } catch (error) {
        console.error('Error loading AIO vs Organic comparison:', error);
        this.showNoAioVsOrganicMessage();
    }
}

export function renderAioVsOrganicComparison(comparison) {
    const { overall, my_domain_stats, position_correlation, per_keyword } = comparison || {};

    if (!overall || !my_domain_stats) {
        this.showNoAioVsOrganicMessage();
        return;
    }

    if (!overall.total_keywords_analyzed || overall.total_keywords_analyzed === 0) {
        this.showNoAioVsOrganicMessage();
        return;
    }

    // Stats bar (overall totals) — 4 stats distribuidas a lo ancho +
    // tooltip explicativo en la esquina superior derecha.
    const statsBar = document.getElementById('aioVsOrganicStats');
    if (statsBar) {
        statsBar.innerHTML = `
            <span class="stat-item">
                <strong>${overall.total_keywords_analyzed}</strong>
                <small>keywords analyzed</small>
            </span>
            <span class="stat-item">
                <strong>${overall.overlap_rate_url}%</strong>
                <small>URL-exact overlap</small>
            </span>
            <span class="stat-item">
                <strong>${overall.overlap_rate_domain}%</strong>
                <small>domain overlap</small>
            </span>
            <span class="stat-item">
                <strong>${escapeHtml(my_domain_stats.project_domain || '—')}</strong>
                <small>your domain</small>
            </span>
            <span class="stats-bar-tooltip">
                <i class="fas fa-info-circle"></i>
                <span class="stats-bar-tooltip-content">
                    <strong>Keywords analyzed</strong>
                    Total unique keywords with both AI Overview and organic results in the selected period.
                    <strong>URL-exact overlap</strong>
                    % of AI Overview references whose exact URL also appears in the organic top 10 for the same keyword.
                    <strong>Domain overlap</strong>
                    % of AI Overview references whose domain also appears in the organic top 10 (even if on a different page). Higher than URL-exact because many sites rank and are cited with different URLs.
                    <strong>Your domain</strong>
                    The project's domain used for the 4-quadrant analysis below.
                </span>
            </span>
        `;
    }

    // KPI cards (4 cuadrantes)
    const kpiContainer = document.getElementById('aioVsOrganicKpis');
    if (kpiContainer) {
        kpiContainer.innerHTML = `
            <div class="kpi-card kpi-both">
                <div class="kpi-icon">🟢</div>
                <div class="kpi-value">${my_domain_stats.keywords_in_both}</div>
                <div class="kpi-label">Rank &amp; Cited</div>
                <div class="kpi-help">Ranks in top 10 AND cited in AI Overview</div>
            </div>
            <div class="kpi-card kpi-organic-only">
                <div class="kpi-icon">🟡</div>
                <div class="kpi-value">${my_domain_stats.keywords_organic_only}</div>
                <div class="kpi-label">Rank, Not Cited</div>
                <div class="kpi-help">GEO opportunity — ranks but AI Overview doesn't use you</div>
            </div>
            <div class="kpi-card kpi-aio-only">
                <div class="kpi-icon">🔵</div>
                <div class="kpi-value">${my_domain_stats.keywords_aio_only}</div>
                <div class="kpi-label">Cited, Not Ranking</div>
                <div class="kpi-help">SEO opportunity — cited in AIO but not in top 10</div>
            </div>
            <div class="kpi-card kpi-neither">
                <div class="kpi-icon">⚪</div>
                <div class="kpi-value">${my_domain_stats.keywords_neither}</div>
                <div class="kpi-label">Neither</div>
                <div class="kpi-help">Full content gap — neither ranks nor cited</div>
            </div>
        `;
    }

    // Position correlation bars: Top 3 / 4-10 / 11+ / Not ranking.
    // Estilo horizontal (barras de progreso) claramente diferenciado del
    // grid vertical de KPI cards de arriba. Responde "¿rankear más alto
    // correlaciona con más AIO mentions?" — útil para justificar el
    // trabajo SEO vs GEO.
    //
    // Textos optimizados para que el usuario entienda INMEDIATAMENTE
    // qué significa cada fila, sin ambigüedad. Ejemplo (HMFC, Top 3):
    //   - Título:  "Ranks in Top 3"
    //   - Detalle: "25 keywords where you rank #1-3 organically"
    //   - Tasa:    "76%"
    //   - Caption: "19 of those 25 are also cited in the AI Overview"
    const positionCards = document.getElementById('aioVsOrganicPositionCards');
    if (positionCards && position_correlation) {
        const buckets = [
            {
                key: 'top_3',
                cssClass: 'pos-top3',
                title: 'Ranks in Top 3',
                detailTpl: (n) => `${n} keyword${n === 1 ? '' : 's'} where you rank #1-3 organically`,
                captionTpl: (cited, total) =>
                    `${cited} of those ${total} are also cited in the AI Overview`,
                emptyLabel: 'No keywords where you rank #1-3'
            },
            {
                key: 'positions_4_10',
                cssClass: 'pos-4-10',
                title: 'Ranks in Positions 4-10',
                detailTpl: (n) => `${n} keyword${n === 1 ? '' : 's'} where you rank #4-10 organically`,
                captionTpl: (cited, total) =>
                    `${cited} of those ${total} are also cited in the AI Overview`,
                emptyLabel: 'No keywords where you rank #4-10'
            },
            {
                key: 'beyond_top_10',
                cssClass: 'pos-11-plus',
                title: 'Ranks in Positions 11+',
                detailTpl: (n) => `${n} keyword${n === 1 ? '' : 's'} where you rank #11 or below`,
                captionTpl: (cited, total) =>
                    `${cited} of those ${total} are also cited in the AI Overview`,
                emptyLabel: 'No keywords ranking below #10'
            },
            {
                key: 'not_ranking',
                cssClass: 'pos-not-ranking',
                title: "Doesn't rank organically",
                detailTpl: (n) => `${n} keyword${n === 1 ? '' : 's'} where your domain is not in the organic results`,
                captionTpl: (cited, total) =>
                    `${cited} of those ${total} are still cited in the AI Overview`,
                emptyLabel: 'All keywords have you ranking organically'
            }
        ];
        // Ocultamos el bucket "beyond_top_10" si está vacío (Google
        // suele devolver max 10-13 orgánicos, así que casi siempre es 0).
        const visible = buckets.filter(b => {
            if (b.key === 'beyond_top_10') {
                return (position_correlation[b.key]?.total_keywords || 0) > 0;
            }
            return true;
        });
        positionCards.innerHTML = visible.map(b => {
            const d = position_correlation[b.key] || { total_keywords: 0, cited_in_aio: 0, aio_rate: 0 };
            const isEmpty = d.total_keywords === 0;
            const detailText = isEmpty ? b.emptyLabel : b.detailTpl(d.total_keywords);
            const captionText = isEmpty
                ? '—'
                : b.captionTpl(d.cited_in_aio, d.total_keywords);
            return `
                <div class="position-row ${b.cssClass}${isEmpty ? ' position-row-empty' : ''}">
                    <div class="position-row-label">
                        <div class="position-row-title">${b.title}</div>
                        <div class="position-row-detail">${detailText}</div>
                    </div>
                    <div class="position-row-bar-wrapper">
                        <div class="position-row-bar-track">
                            <div class="position-row-bar-fill" style="width: ${Math.min(100, d.aio_rate)}%"></div>
                        </div>
                        <div class="position-row-bar-labels">
                            <span class="position-row-rate">${d.aio_rate}<span class="position-row-rate-unit">%</span> <span class="position-row-rate-suffix">cited in AI Overview</span></span>
                            <span class="position-row-count">${captionText}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Per-keyword breakdown table
    const tbody = document.getElementById('aioVsOrganicBody');
    if (tbody) {
        const quadrantBadge = {
            both: '<span class="q-badge q-both">🟢 Rank &amp; Cited</span>',
            organic_only: '<span class="q-badge q-org">🟡 Rank only</span>',
            aio_only: '<span class="q-badge q-aio">🔵 Cited only</span>',
            neither: '<span class="q-badge q-none">⚪ Neither</span>',
        };

        if (!per_keyword || per_keyword.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align:center; padding:16px; color:#6b7280;">
                        No per-keyword data available
                    </td>
                </tr>
            `;
        } else {
            tbody.innerHTML = per_keyword.map((kw, idx) => {
                // Formatear la posición orgánica del dominio del proyecto
                let posDisplay;
                if (kw.my_organic_position) {
                    const posClass = kw.my_organic_position <= 3
                        ? 'color:#10b981; font-weight:700;'
                        : (kw.my_organic_position <= 10 ? 'color:#3b82f6; font-weight:600;' : 'color:#8b5cf6;');
                    posDisplay = `<span style="${posClass}">#${kw.my_organic_position}</span>`;
                } else {
                    posDisplay = '<span style="color:#9ca3af;">—</span>';
                }
                return `
                    <tr class="q-row-${kw.quadrant}">
                        <td class="rank-cell">${idx + 1}</td>
                        <td class="kw-cell" title="${escapeHtml(kw.keyword)}">
                            ${escapeHtml(kw.keyword)}
                        </td>
                        <td>${posDisplay}</td>
                        <td>${kw.aio_refs_count}</td>
                        <td>${kw.overlap_url_count} <small style="color:#6b7280;">(${kw.overlap_domain_count} dom)</small></td>
                        <td>${quadrantBadge[kw.quadrant] || ''}</td>
                    </tr>
                `;
            }).join('');
        }
    }

    // Mostrar la sección, ocultar el mensaje "no data"
    const noMsg = document.getElementById('noAioVsOrganicMessage');
    const section = document.getElementById('aioVsOrganicContent');
    if (noMsg) noMsg.style.display = 'none';
    if (section) section.style.display = 'block';
}

export function showNoAioVsOrganicMessage() {
    const noMsg = document.getElementById('noAioVsOrganicMessage');
    const section = document.getElementById('aioVsOrganicContent');
    if (section) section.style.display = 'none';
    if (noMsg) noMsg.style.display = 'block';
}
