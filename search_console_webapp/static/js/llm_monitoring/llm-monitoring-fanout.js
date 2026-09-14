/**
 * LLM Monitoring - Mixin: Query Fan-out (P7, 2026-09)
 *
 * Todo lo de este fichero existe SOLO para proyectos con la búsqueda web activada
 * (`currentProject.search_mode === 'auto'`, lo activa el admin). Con 'off' cada
 * método sale sin tocar el DOM ni pedir nada al servidor: el panel queda igual.
 *
 * - Sección "Query Fan-out" (GET /projects/<id>/fanout, respeta los filtros globales)
 * - Bloque "How the model searched" en el modal de cada respuesta
 * - Marca de cambio de metodología en las gráficas de evolución
 * - Nota bajo los KPIs y nota en el modal de modelos
 *
 * Brandbook v1.1: sin badges ni pills; el estado va con texto, icono y punto de color.
 */

(function registerSearchMarkerPlugin() {
    if (!window.Chart || window.__csSearchMarkerRegistered) return;
    window.__csSearchMarkerRegistered = true;

    // Línea vertical discontinua entre el último día sin búsqueda y el primero con ella.
    // Solo actúa si la gráfica trae options.plugins.csSearchMarker = { index }.
    Chart.register({
        id: 'csSearchMarker',
        afterDatasetsDraw(chart) {
            const marker = chart.options?.plugins?.csSearchMarker;
            const xScale = chart.scales?.x;
            if (!marker || typeof marker.index !== 'number' || !xScale) return;

            const x = (xScale.getPixelForValue(marker.index - 1) + xScale.getPixelForValue(marker.index)) / 2;
            const { top, bottom } = chart.chartArea;
            const theme = window.CSChartTheme;
            const ink = theme?.ink?.secondary || '#64748B';
            const ctx = chart.ctx;

            ctx.save();
            ctx.beginPath();
            ctx.setLineDash([4, 4]);
            ctx.lineWidth = 1;
            ctx.strokeStyle = theme?.ink?.tertiary || '#94A3B8';
            ctx.moveTo(x, top);
            ctx.lineTo(x, bottom);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.fillStyle = ink;
            ctx.font = `600 11px ${Chart.defaults.font?.family || 'sans-serif'}`;
            const label = 'Web search on';
            const width = ctx.measureText(label).width;
            const fitsRight = x + 6 + width < chart.chartArea.right;
            ctx.textAlign = fitsRight ? 'left' : 'right';
            ctx.fillText(label, fitsRight ? x + 6 : x - 6, top + 12);
            ctx.restore();
        }
    });
})();

const FANOUT_PAGE_SIZE = 10;
const FANOUT_DOMAINS_PER_ROUND = 8;

Object.assign(LLMMonitoring.prototype, {

isSearchProject() {
        return this.currentProject?.search_mode === 'auto' && Boolean(this.currentProject?.search_enabled_at);
    },

// Día (YYYY-MM-DD) de la activación de la búsqueda, en local.
searchEnabledDay() {
        if (!this.isSearchProject()) return null;
        const d = new Date(this.currentProject.search_enabled_at);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    },

// Opción del plugin csSearchMarker para una gráfica cuyas etiquetas son estos días.
// false (el plugin no pinta nada) si el proyecto está en off o la serie no cruza la fecha.
searchMarkerOption(dayStrings) {
        const enabledDay = this.searchEnabledDay();
        if (!enabledDay || !Array.isArray(dayStrings)) return false;
        const days = dayStrings.map(d => String(d).slice(0, 10));
        const index = days.findIndex(d => d >= enabledDay);
        return index > 0 ? { index } : false;
    },

formatShortDate(value) {
        return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    },

formatRate(rate) {
        return rate === null || rate === undefined ? null : `${Math.round(rate * 100)}%`;
    },

// ───────────────────────────── Sección del panel ─────────────────────────────

async loadFanout(projectId) {
        const card = document.getElementById('fanoutCard');
        const note = document.getElementById('searchMethodNote');
        if (!this.isSearchProject()) {
            if (card) card.style.display = 'none';
            if (note) note.hidden = true;
            return;
        }

        this.renderSearchMethodNote();
        if (!card) return;
        card.style.display = '';
        const body = document.getElementById('fanoutBody');
        body.innerHTML = this.renderFanoutSkeleton();

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/fanout?days=${this.globalTimeRange}${this.getReportFilterParams()}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (this.currentProject?.id !== projectId) return;  // el usuario cambió de proyecto
            if (!data.enabled) {
                card.style.display = 'none';
                return;
            }
            this.fanoutData = data;
            this._fanoutPage = 1;
            this.renderFanout();
        } catch (error) {
            console.error('❌ Error loading fan-out:', error);
            body.innerHTML = `
                <div class="fanout-state" role="alert">
                    <p class="fanout-state-title">Couldn't load the fan-out data.</p>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="window.llmMonitoring.loadFanout(${Number(projectId)})">
                        <i class="fas fa-redo"></i> Try again
                    </button>
                </div>`;
        }
    },

renderSearchMethodNote() {
        const note = document.getElementById('searchMethodNote');
        if (!note) return;
        const enabledDay = this.searchEnabledDay();
        const rangeStart = new Date();
        rangeStart.setDate(rangeStart.getDate() - (Number(this.globalTimeRange) || 30));
        const startDay = rangeStart.toISOString().slice(0, 10);
        if (!enabledDay || enabledDay <= startDay) {
            note.hidden = true;
            return;
        }
        note.querySelector('[data-role="text"]').textContent =
            `Web search was enabled on ${this.formatShortDate(this.currentProject.search_enabled_at)}. ` +
            'Days before that were measured without it, so trends in this range compare two methods.';
        note.hidden = false;
    },

renderFanoutSkeleton() {
        return `<div class="fanout-skeleton" aria-hidden="true">${'<span></span>'.repeat(5)}</div>
                <span class="sr-only">Loading fan-out data</span>`;
    },

renderFanout() {
        const data = this.fanoutData;
        const body = document.getElementById('fanoutBody');
        const period = document.getElementById('fanoutPeriod');
        if (!data || !body) return;

        if (period) {
            period.textContent = `${data.responses_with_search} of ${data.responses} answers used web search`;
        }

        if (!data.responses) {
            const filtered = this.getReportFilterParams() !== '';
            body.innerHTML = `
                <div class="fanout-state">
                    <i class="fas fa-search" aria-hidden="true"></i>
                    <p class="fanout-state-title">${filtered ? 'No fan-out data for these filters' : 'No web search data yet'}</p>
                    <p class="fanout-state-text">${filtered
                        ? 'Try a wider date range or clear some filters.'
                        : 'Sub-queries appear here after the next analysis with web search.'}</p>
                </div>`;
            return;
        }

        body.innerHTML = `
            ${this.renderFanoutByModel(data.by_llm)}
            <section class="fanout-block" aria-labelledby="fanoutQueriesTitle">
                <div class="fanout-block-head">
                    <h4 class="fanout-eyebrow" id="fanoutQueriesTitle">Top sub-queries</h4>
                    <span class="fanout-block-meta">${data.top_queries_total} distinct</span>
                </div>
                <div id="fanoutQueries"></div>
            </section>
            <div class="fanout-pages-grid">
                ${this.renderFanoutPages('Your pages the models read', data.brand_pages,
                    "The models didn't open any of your pages in this period.")}
                ${this.renderFanoutPages('Competitor pages the models read', data.competitor_pages,
                    "The models didn't open any competitor page in this period.", true)}
            </div>`;
        this.renderFanoutQueries();
    },

renderFanoutLlm(llm) {
        return `<span class="fanout-llm"><span class="fanout-dot" style="background:${this.escapeAttr(this.getLLMColor(llm))}" aria-hidden="true"></span>${this.escapeHtml(this.getLLMDisplayName(llm))}</span>`;
    },

// Modelos que usaron una sub-consulta o abrieron una página, del que más veces a menos.
renderFanoutProviders(providers) {
        return Object.entries(providers || {})
            .sort((a, b) => b[1] - a[1])
            .map(([llm, n]) => `<span class="fanout-provider" title="${n} time${n === 1 ? '' : 's'}">${this.renderFanoutLlm(llm)}</span>`)
            .join('');
    },

renderBrandRate(rate, notReportedTitle) {
        const formatted = this.formatRate(rate);
        return formatted === null
            ? `<span class="fanout-muted" title="${this.escapeAttr(notReportedTitle)}">Not reported</span>`
            : formatted;
    },

renderFanoutByModel(rows) {
        const body = (rows || []).map(row => `
            <tr>
                <th scope="row">${this.renderFanoutLlm(row.llm_provider)}</th>
                <td class="num">${this.formatRate(row.search_rate) ?? '–'} <span class="fanout-muted">(${row.searched} of ${row.responses})</span></td>
                <td class="num">${row.avg_searches ?? '–'}</td>
                <td class="num">${row.avg_page_opens ?? '–'}</td>
                <td class="num">${row.searched ? this.renderBrandRate(row.brand_in_results_rate,
                    row.llm_provider === 'google' ? "Gemini doesn't link sources to each search" : 'No search results recorded') : '–'}</td>
            </tr>`).join('');
        return `
            <section class="fanout-block" aria-labelledby="fanoutModelsTitle">
                <h4 class="fanout-eyebrow" id="fanoutModelsTitle">By model</h4>
                <div class="fanout-table-wrap">
                    <table class="fanout-table">
                        <thead><tr>
                            <th scope="col">Model</th>
                            <th scope="col" class="num">Searched the web</th>
                            <th scope="col" class="num">Searches per answer</th>
                            <th scope="col" class="num">Pages read per answer</th>
                            <th scope="col" class="num">Your brand in results</th>
                        </tr></thead>
                        <tbody>${body}</tbody>
                    </table>
                </div>
            </section>`;
    },

renderFanoutQueries() {
        const container = document.getElementById('fanoutQueries');
        const queries = this.fanoutData?.top_queries || [];
        if (!container) return;

        const totalPages = Math.max(1, Math.ceil(queries.length / FANOUT_PAGE_SIZE));
        const page = Math.min(Math.max(1, this._fanoutPage || 1), totalPages);
        this._fanoutPage = page;
        const offset = (page - 1) * FANOUT_PAGE_SIZE;

        const rows = queries.slice(offset, offset + FANOUT_PAGE_SIZE).map((q, i) => {
            const rank = offset + i + 1;
            const detailId = `fanout-detail-${rank}`;
            const variants = q.variants.map(v => `<li><span>${this.escapeHtml(v.query)}</span><span class="fanout-muted">×${v.count}</span></li>`).join('');
            const prompts = q.prompts.map(p => `<li><span>${this.escapeHtml(p.prompt || `Prompt #${p.query_id}`)}</span><span class="fanout-muted">×${p.count}</span></li>`).join('');
            const hiddenVariants = q.variants_total - q.variants.length;
            return `
                <tr class="fanout-query-row">
                    <td class="fanout-rank">${rank}</td>
                    <td class="fanout-query-cell">${this.escapeHtml(q.query)}</td>
                    <td class="num">${q.responses} <span class="fanout-muted">(${this.formatRate(q.share)})</span></td>
                    <td><span class="fanout-providers">${this.renderFanoutProviders(q.providers)}</span></td>
                    <td class="num">${this.renderBrandRate(q.brand_in_results_rate, "Gemini doesn't link sources to each search")}</td>
                    <td class="fanout-expand-cell">
                        <button type="button" class="fanout-expand" aria-expanded="false" aria-controls="${detailId}"
                                aria-label="Show variants and prompts" onclick="window.llmMonitoring.toggleFanoutRow(this)">
                            <i class="fas fa-chevron-down" aria-hidden="true"></i>
                        </button>
                    </td>
                </tr>
                <tr class="fanout-detail-row" id="${detailId}" hidden>
                    <td></td>
                    <td colspan="5">
                        <div class="fanout-detail">
                            <div>
                                <p class="fanout-detail-title">How the models wrote it</p>
                                <ul class="fanout-detail-list">${variants}</ul>
                                ${hiddenVariants > 0 ? `<p class="fanout-muted">+${hiddenVariants} more variants</p>` : ''}
                            </div>
                            <div>
                                <p class="fanout-detail-title">From your prompts</p>
                                <ul class="fanout-detail-list">${prompts}</ul>
                            </div>
                        </div>
                    </td>
                </tr>`;
        }).join('');

        container.innerHTML = `
            <div class="fanout-table-wrap">
                <table class="fanout-table fanout-queries-table">
                    <thead><tr>
                        <th scope="col" class="fanout-rank">#</th>
                        <th scope="col">Sub-query</th>
                        <th scope="col" class="num">Answers</th>
                        <th scope="col">Models</th>
                        <th scope="col" class="num">Your brand in results</th>
                        <th scope="col"><span class="sr-only">Details</span></th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            ${totalPages > 1 ? `
                <nav class="fanout-pagination" aria-label="Sub-queries pages">
                    <button type="button" class="btn btn-ghost btn-sm" ${page === 1 ? 'disabled' : ''}
                            onclick="window.llmMonitoring.goToFanoutPage(${page - 1})">Previous</button>
                    <span class="fanout-muted">Page ${page} of ${totalPages}</span>
                    <button type="button" class="btn btn-ghost btn-sm" ${page === totalPages ? 'disabled' : ''}
                            onclick="window.llmMonitoring.goToFanoutPage(${page + 1})">Next</button>
                </nav>` : ''}`;
    },

goToFanoutPage(page) {
        this._fanoutPage = page;
        this.renderFanoutQueries();
        document.getElementById('fanoutQueriesTitle')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    },

toggleFanoutRow(button) {
        const detail = document.getElementById(button.getAttribute('aria-controls'));
        if (!detail) return;
        const expanded = button.getAttribute('aria-expanded') === 'true';
        button.setAttribute('aria-expanded', String(!expanded));
        button.setAttribute('aria-label', expanded ? 'Show variants and prompts' : 'Hide variants and prompts');
        detail.hidden = expanded;
    },

renderFanoutPages(title, pages, emptyText, isCompetitor = false) {
        const items = (pages || []).map(page => {
            const href = this.toNavigableUrl(page.url);
            const safeHref = this.isSafeUrl(href) ? href : '#';
            let path = '';
            try { path = new URL(page.url).pathname; } catch (e) { path = page.url; }
            return `
                <li class="fanout-page">
                    ${this.getDomainFaviconImg(page.host, 16)}
                    <a href="${this.escapeAttr(safeHref)}" target="_blank" rel="noopener noreferrer" title="${this.escapeAttr(page.url)}">
                        <span class="fanout-page-host">${this.escapeHtml(page.host)}</span><span class="fanout-page-path">${this.escapeHtml(path === '/' ? '' : path)}</span>
                    </a>
                    <span class="fanout-providers">${this.renderFanoutProviders(page.providers)}</span>
                </li>`;
        }).join('');
        this.bindFaviconFallback();
        return `
            <section class="fanout-block" aria-label="${this.escapeAttr(title)}">
                <h4 class="fanout-eyebrow">${this.escapeHtml(title)}</h4>
                ${items ? `<ul class="fanout-page-list">${items}</ul>` : `<p class="fanout-muted">${this.escapeHtml(emptyText)}</p>`}
            </section>`;
    },

// ───────────────────────────── Modal de respuesta ────────────────────────────

// HTML del bloque "How the model searched". '' si la respuesta no se hizo con búsqueda
// activada (proyectos off: el endpoint ni siquiera manda `search`).
renderResponseSearchSection(response) {
        const search = response?.search;
        if (!search) return '';

        if (!search.used) {
            return `
                <div class="response-modal-section fanout-response">
                    <h4><i class="fas fa-search"></i> How the model searched</h4>
                    <p class="fanout-response-summary">Answered without searching the web.</p>
                </div>`;
        }

        const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
        const summary = ['Searched the web', plural(search.calls, 'search')];
        if (search.page_opens) summary.push(`${plural(search.page_opens, 'page')} read`);

        const rounds = new Map();
        (search.searches || []).forEach(s => {
            const key = s.round ?? rounds.size + 1;
            if (!rounds.has(key)) rounds.set(key, { queries: [], sources: [] });
            const round = rounds.get(key);
            if (s.query) round.queries.push(s.query);
            round.sources.push(...(s.sources || []));
        });
        const anyAttributed = [...rounds.values()].some(r => r.sources.length);

        const roundItems = [...rounds.values()].map((round, i) => {
            const hosts = [...new Set(round.sources.map(url => this.extractNormalizedHost(url)).filter(Boolean))];
            const shown = hosts.slice(0, FANOUT_DOMAINS_PER_ROUND).map(host => {
                const url = `https://${host}`;
                const label = this.isUrlFromBrand(url)
                    ? '<span class="fanout-domain-label is-brand"><i class="fas fa-check-circle"></i> Your brand</span>'
                    : this.isUrlFromCompetitor(url) ? '<span class="fanout-domain-label">Competitor</span>' : '';
                return `<li>${this.getDomainFaviconImg(host, 14)}<span>${this.escapeHtml(host)}</span>${label}</li>`;
            }).join('');
            const more = hosts.length - FANOUT_DOMAINS_PER_ROUND;
            return `
                <li class="fanout-round">
                    <span class="fanout-round-n" aria-hidden="true">${i + 1}</span>
                    <div>
                        ${round.queries.map(q => `<p class="fanout-query">${this.escapeHtml(q)}</p>`).join('')}
                        ${shown ? `<ul class="fanout-domains">${shown}${more > 0 ? `<li class="fanout-muted">+${more} more</li>` : ''}</ul>` : ''}
                    </div>
                </li>`;
        }).join('');

        const pages = (search.pages || []).filter(p => p.url).map(p => {
            const href = this.toNavigableUrl(p.url);
            const safeHref = this.isSafeUrl(href) ? href : '#';
            return `
                <li>
                    <a href="${this.escapeAttr(safeHref)}" target="_blank" rel="noopener noreferrer">${this.escapeHtml(this.truncateUrl ? this.truncateUrl(p.url, 90) : p.url)}</a>
                    ${p.action === 'find_in_page' && p.pattern ? `<span class="fanout-muted">looked for "${this.escapeHtml(p.pattern)}"</span>` : ''}
                </li>`;
        }).join('');
        this.bindFaviconFallback();

        return `
            <div class="response-modal-section fanout-response">
                <h4><i class="fas fa-search"></i> How the model searched</h4>
                <p class="fanout-response-summary">${summary.join(' · ')}</p>
                ${roundItems ? `<ol class="fanout-rounds">${roundItems}</ol>` : ''}
                ${!anyAttributed && roundItems ? `<p class="fanout-muted fanout-response-note">${this.escapeHtml(this.getLLMDisplayName(response.llm_provider))} doesn't link sources to each search. The sources it cited are listed below.</p>` : ''}
                ${pages ? `<p class="fanout-detail-title">Pages read</p><ul class="fanout-read-pages">${pages}</ul>` : ''}
            </div>`;
    },

// ───────────────────────────── Modal de modelos ──────────────────────────────

renderModelsSearchNote() {
        const note = document.getElementById('modelsSearchNote');
        if (!note) return;
        if (!this.isSearchProject()) {
            note.hidden = true;
            return;
        }
        const weights = this.currentProject.search_unit_weights || {};
        const units = Object.entries(weights)
            .map(([llm, w]) => `${this.getLLMDisplayName(llm)} ×${w}`).join(', ');
        note.querySelector('[data-role="text"]').textContent =
            `Since ${this.formatShortDate(this.currentProject.search_enabled_at)}, ChatGPT, Claude and Gemini can search the web before answering, ` +
            'and Perplexity runs deeper searches. Results are observed through each provider\'s API, so the consumer apps may search differently.' +
            (units ? ` Each prompt uses more units: ${units}.` : '');
        note.hidden = false;
    },
});
