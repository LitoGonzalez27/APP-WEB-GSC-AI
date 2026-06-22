/**
 * Manual AI System - Analytics — Comparación histórica de AI Overview
 *
 * Modal "See historic" de la tabla AI Overview Keywords Details. Compara la
 * presencia en AI Overview entre el primer y el último análisis disponibles
 * dentro del rango seleccionado (7 / 30 / 90 días) para el dominio del proyecto
 * y cada competidor: keywords ganadas, perdidas y mantenidas, con sus URLs.
 *
 * Datos: GET /manual-ai/api/projects/{id}/ai-overview-historical?days={days}
 */

// ================================
// APERTURA / CARGA
// ================================

export function openHistoricalComparison() {
    const projectId = this.currentAnalyticsData?.projectId
        || parseInt(this.elements.analyticsProjectSelect?.value)
        || this.currentProject?.id;

    if (!projectId) {
        this.showError?.('Select a project first');
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    const modal = document.getElementById('historicalComparisonModal');
    const body = document.getElementById('historicalComparisonBody');
    if (!modal || !body) return;

    // Estado de carga + abrir modal.
    // Usamos display inline (flex) como el resto de modales del sistema: el
    // handler global hideAllModals() (Escape / click fuera) cierra con
    // style.display='none', que ganaría a la clase .show e impediría reabrir.
    body.innerHTML = `
        <div class="hist-loading">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Loading historical comparison...</p>
        </div>
    `;
    modal.style.display = 'flex';

    this.loadHistoricalComparison(projectId, days);
}

export async function loadHistoricalComparison(projectId, days) {
    const body = document.getElementById('historicalComparisonBody');
    if (!body) return;

    try {
        const token = Date.now();
        this._historicalToken = token;

        const response = await fetch(`/manual-ai/api/projects/${projectId}/ai-overview-historical?days=${days}`);
        if (!response.ok) throw new Error('Failed to load historical comparison');

        const result = await response.json();
        if (this._historicalToken !== token) return; // evitar pisado por race

        const data = (result && result.data) || {};
        this.renderHistoricalComparison(data);
    } catch (error) {
        console.error('Error loading historical comparison:', error);
        body.innerHTML = `
            <div class="hist-empty">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load historical comparison</p>
            </div>
        `;
    }
}

export function hideHistoricalComparison() {
    const modal = document.getElementById('historicalComparisonModal');
    if (modal) modal.style.display = 'none';
    this.destroyHistoricalChart();
    this._historicalData = null;
}

// ================================
// RENDER
// ================================

export function renderHistoricalComparison(data) {
    const body = document.getElementById('historicalComparisonBody');
    if (!body) return;

    if (!data || data.comparison_available !== true) {
        const count = data?.date_count || 0;
        body.innerHTML = `
            <div class="hist-empty">
                <i class="fas fa-clock-rotate-left"></i>
                <p>Not enough history to compare yet</p>
                <small>
                    ${count <= 1
                        ? 'Only one analysis is available in this range. A historical comparison needs at least two analyses on different dates.'
                        : 'No comparable analyses were found in the selected range.'}
                    Try a wider time range or run another analysis.
                </small>
            </div>
        `;
        return;
    }

    const entities = Array.isArray(data.entities) ? data.entities : [];
    this._historicalData = data;
    this._historicalActiveTab = 0;

    const prev = this.formatHistDate(data.compared_dates?.previous);
    const curr = this.formatHistDate(data.compared_dates?.current);

    // Tab 0 = Overview (resumen + gráfico); tabs 1..N = una por entidad.
    const tabs = [{ label: 'Overview', icon: 'fa-chart-column' }].concat(
        entities.map(e => ({
            label: e.label || e.domain || '',
            icon: e.type === 'project' ? 'fa-star' : null,
        }))
    );
    const tabsHtml = tabs.map((t, i) => `
        <button type="button"
                class="hist-tab ${i === 0 ? 'active' : ''}"
                data-hist-tab="${i}"
                onclick="manualAI.switchHistoricalTab(${i})">
            ${t.icon ? `<i class="fas ${t.icon}"></i> ` : ''}${this.escapeHtml(t.label)}
        </button>
    `).join('');

    body.innerHTML = `
        <div class="hist-meta">
            <i class="fas fa-calendar-alt"></i>
            Comparing <strong>${prev}</strong>
            <i class="fas fa-arrow-right hist-meta-arrow"></i>
            <strong>${curr}</strong>
            <span class="hist-meta-sep">·</span>
            Last ${Number(data.days) || ''} days
            <span class="hist-meta-sep">·</span>
            ${Number(data.date_count) || 0} analyses in range
        </div>
        <div class="hist-tabs" role="tablist">${tabsHtml}</div>
        <div class="hist-panel" id="historicalPanel"></div>
    `;

    this.renderHistoricalPanel(0);
}

export function switchHistoricalTab(index) {
    this._historicalActiveTab = index;
    document.querySelectorAll('#historicalComparisonModal .hist-tab').forEach(tab => {
        tab.classList.toggle('active', String(tab.dataset.histTab) === String(index));
    });
    this.renderHistoricalPanel(index);
}

export function renderHistoricalPanel(index) {
    const panel = document.getElementById('historicalPanel');
    const data = this._historicalData;
    if (!panel || !data) return;

    // Destruir cualquier gráfico previo (evita fugas de Chart.js al re-render).
    this.destroyHistoricalChart();

    if (index === 0) {
        this.renderHistoricalOverview(data);
        return;
    }

    const entity = (data.entities || [])[index - 1];
    panel.innerHTML = entity ? this.renderHistoricalEntity(entity) : '';
}

export function renderHistoricalEntity(entity) {
    const s = entity.summary || {};
    const net = (s.current_count || 0) - (s.previous_count || 0);
    const netClass = net > 0 ? 'hist-net--up' : (net < 0 ? 'hist-net--down' : '');
    const netLabel = net > 0 ? `+${net}` : String(net);

    return `
        <div class="hist-scorecards">
            <div class="hist-card">
                <span class="hist-card-value">${s.previous_count || 0}</span>
                <span class="hist-card-label">Mentioned then</span>
            </div>
            <div class="hist-card">
                <span class="hist-card-value">${s.current_count || 0}</span>
                <span class="hist-card-label">Mentioned now</span>
                <span class="hist-net ${netClass}">${netLabel}</span>
            </div>
            <div class="hist-card hist-card--gain">
                <span class="hist-card-value">+${s.gained_count || 0}</span>
                <span class="hist-card-label">Gained</span>
            </div>
            <div class="hist-card hist-card--loss">
                <span class="hist-card-value">−${s.lost_count || 0}</span>
                <span class="hist-card-label">Lost</span>
            </div>
            <div class="hist-card">
                <span class="hist-card-value">${s.maintained_count || 0}</span>
                <span class="hist-card-label">Maintained</span>
            </div>
        </div>

        <div class="hist-lists">
            ${this.renderHistoricalList('lost', entity.lost || [])}
            ${this.renderHistoricalList('gained', entity.gained || [])}
            ${this.renderHistoricalList('maintained', entity.maintained || [])}
        </div>
    `;
}

// ================================
// OVERVIEW (resumen + gráfico de barras gained vs lost por entidad)
// ================================

export function renderHistoricalOverview(data) {
    const panel = document.getElementById('historicalPanel');
    const entities = data.entities || [];
    if (!panel) return;

    panel.innerHTML = `
        <div class="hist-overview-chart">
            <canvas id="historicalOverviewChart"></canvas>
        </div>
        ${this.renderHistoricalSummaryTable(entities)}
    `;

    const canvas = document.getElementById('historicalOverviewChart');
    if (!canvas || typeof window.Chart === 'undefined') return; // fallback: solo tabla

    const FONT = "'Inter Tight', sans-serif";
    const labelFor = e => (e.type === 'project'
        ? (e.domain || e.label || 'Your domain')
        : (e.domain || e.label || ''));

    // responsive:true → Chart.js observa el contenedor y ajusta el tamaño en
    // cuanto tiene anchura definitiva (no dependemos de timing de layout).
    this._historicalChart = new window.Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: entities.map(labelFor),
            datasets: [
                {
                    label: 'Gained',
                    data: entities.map(e => e.summary?.gained_count || 0),
                    backgroundColor: '#3CB371',
                    borderRadius: 6,
                    maxBarThickness: 48,
                },
                {
                    label: 'Lost',
                    data: entities.map(e => e.summary?.lost_count || 0),
                    backgroundColor: '#E05252',
                    borderRadius: 6,
                    maxBarThickness: 48,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            // Acerca las dos barras (gained/lost) dentro de cada entidad y deja
            // más separación entre entidades.
            datasets: { bar: { categoryPercentage: 0.5, barPercentage: 0.9 } },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { font: { family: FONT }, usePointStyle: true, boxWidth: 8 },
                },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y} keyword${ctx.parsed.y === 1 ? '' : 's'}`,
                    },
                },
            },
            scales: {
                x: { grid: { display: false }, ticks: { font: { family: FONT } } },
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0, font: { family: FONT } },
                    grid: { color: '#EEF2F7' },
                    title: { display: true, text: 'Keywords', font: { family: FONT } },
                },
            },
        },
    });
}

export function renderHistoricalSummaryTable(entities) {
    const rows = entities.map(e => {
        const s = e.summary || {};
        const net = (s.current_count || 0) - (s.previous_count || 0);
        const netClass = net > 0 ? 'hist-net--up' : (net < 0 ? 'hist-net--down' : '');
        const netLabel = net > 0 ? `+${net}` : String(net);
        const name = e.type === 'project'
            ? `<i class="fas fa-star"></i> ${this.escapeHtml(e.domain || e.label || 'Your domain')}`
            : this.escapeHtml(e.domain || e.label || '');
        return `
            <tr>
                <td class="hist-st-name">${name}</td>
                <td>${s.previous_count || 0}</td>
                <td>${s.current_count || 0} <span class="hist-net ${netClass}">${netLabel}</span></td>
                <td class="hist-st-gain">+${s.gained_count || 0}</td>
                <td class="hist-st-loss">−${s.lost_count || 0}</td>
                <td>${s.maintained_count || 0}</td>
            </tr>
        `;
    }).join('');

    return `
        <div class="hist-summary-table-wrap">
            <table class="hist-summary-table">
                <thead>
                    <tr>
                        <th>Domain</th>
                        <th>Then</th>
                        <th>Now</th>
                        <th>Gained</th>
                        <th>Lost</th>
                        <th>Kept</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

export function destroyHistoricalChart() {
    if (this._historicalChart) {
        this._historicalChart.destroy();
        this._historicalChart = null;
    }
}

export function renderHistoricalList(kind, items) {
    const meta = {
        lost: { title: 'Lost', icon: 'fa-circle-minus', cls: 'lost',
                hint: 'Mentioned before, not anymore' },
        gained: { title: 'Gained', icon: 'fa-circle-plus', cls: 'gain',
                  hint: 'Newly mentioned' },
        maintained: { title: 'Maintained', icon: 'fa-equals', cls: 'kept',
                      hint: 'Mentioned on both dates' },
    }[kind];

    const rowsHtml = items.length
        ? items.map(it => this.renderHistoricalRow(kind, it)).join('')
        : `<div class="hist-row hist-row--empty">No keywords</div>`;

    // Maintained puede ser largo: colapsable para no saturar.
    const open = kind !== 'maintained' ? 'open' : '';

    return `
        <details class="hist-list hist-list--${meta.cls}" ${open}>
            <summary class="hist-list-summary">
                <span class="hist-list-title">
                    <i class="fas ${meta.icon}"></i> ${meta.title}
                    <span class="hist-list-count">${items.length}</span>
                </span>
                <span class="hist-list-hint">${meta.hint}</span>
            </summary>
            <div class="hist-rows">${rowsHtml}</div>
        </details>
    `;
}

export function renderHistoricalRow(kind, item) {
    const keyword = this.escapeHtml(item.keyword || '');

    let positionHtml = '';
    if (kind === 'lost') {
        positionHtml = `<span class="hist-pos">${this.formatHistPosition(item.previous_position)}</span>`;
    } else if (kind === 'gained') {
        positionHtml = `<span class="hist-pos">${this.formatHistPosition(item.position)}</span>`;
    } else {
        positionHtml = this.renderHistoricalDelta(item);
    }

    const url = kind === 'lost' ? item.previous_url : item.url;
    const urlHtml = this.renderHistoricalUrl(url);

    return `
        <div class="hist-row">
            <span class="hist-row-kw" title="${keyword}">${keyword}</span>
            ${positionHtml}
            ${urlHtml}
        </div>
    `;
}

export function renderHistoricalDelta(item) {
    const pp = item.previous_position;
    const cp = item.current_position;
    const delta = item.position_delta;

    let arrow = '<i class="fas fa-minus hist-delta-flat"></i>';
    if (typeof delta === 'number' && delta < 0) {
        arrow = `<i class="fas fa-arrow-up hist-delta-up"></i><span class="hist-delta-up">${Math.abs(delta)}</span>`;
    } else if (typeof delta === 'number' && delta > 0) {
        arrow = `<i class="fas fa-arrow-down hist-delta-down"></i><span class="hist-delta-down">${delta}</span>`;
    }

    return `
        <span class="hist-pos hist-pos--delta" title="Position ${this.formatHistPosition(pp)} → ${this.formatHistPosition(cp)}">
            ${this.formatHistPosition(pp)} <i class="fas fa-arrow-right hist-pos-sep"></i> ${this.formatHistPosition(cp)}
            ${arrow}
        </span>
    `;
}

export function renderHistoricalUrl(url) {
    if (!url) {
        return `<span class="hist-url hist-url--none">—</span>`;
    }
    const safe = this.escapeHtml(url);
    let display = url;
    try {
        const u = new URL(url);
        display = u.hostname.replace(/^www\./, '') + (u.pathname && u.pathname !== '/' ? u.pathname : '');
    } catch (_) { /* deja la url tal cual */ }
    if (display.length > 48) display = display.slice(0, 45) + '…';

    return `
        <a class="hist-url" href="${safe}" target="_blank" rel="noopener noreferrer" title="${safe}">
            <i class="fas fa-link"></i> ${this.escapeHtml(display)}
        </a>
    `;
}

// ================================
// HELPERS
// ================================

export function formatHistPosition(pos) {
    if (pos === null || pos === undefined) return '—';
    return `#${pos}`;
}

export function formatHistDate(value) {
    if (!value) return '—';
    try {
        const d = new Date(value + 'T00:00:00');
        return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
    } catch (_) {
        return value;
    }
}
