/**
 * LLM Monitoring - barra de filtros global del dashboard
 *
 * Dimensiones:
 * - Prompt set (EXCLUSIVO: núcleo O un set de tendencia, nunca mezcla — al
 *   activarse un set estacional el denominador del SOV cambia y las series
 *   temporales darían saltos artificiales).
 * - Clusters (multiselección).
 * - Brand scope (Todos / Branded / Non-branded) — sustituye a los antiguos
 *   toggles por-gráfica; los controles locales duplicados se retiraron.
 * - LLMs (multiselección con checks) — sustituye al select del Inspector.
 *
 * Reglas de estado (decisión de producto):
 * - SIN persistencia: al salir del proyecto los filtros se restablecen; al
 *   volver a entrar se ve todo por defecto. Dentro del mismo proyecto, el
 *   estado sobrevive a las recargas internas (cambiar días, guardar sets...).
 * - Los fetches del informe añaden this.getReportFilterParams(); sin filtros
 *   activos devuelve lo mínimo y el backend usa su camino legacy rápido.
 */

// window.* y no const: el archivo debe poder recargarse (hot-reload en dev)
// sin reventar por redeclaración de un binding léxico global.
window.REPORT_LLM_LABELS = window.REPORT_LLM_LABELS || {
    openai: 'ChatGPT',
    anthropic: 'Claude',
    google: 'Gemini',
    perplexity: 'Perplexity'
};
const REPORT_LLM_LABELS_REF = window.REPORT_LLM_LABELS;

Object.assign(LLMMonitoring.prototype, {

    _defaultReportFilters() {
        return { set: 'core', clusters: [], branded: 'all', llms: [] };
    },

    /** ¿Hay algún filtro distinto del default? (para Reset y contador) */
    _activeReportFilterCount() {
        const f = this.reportFilters || this._defaultReportFilters();
        let n = 0;
        if ((f.set || 'core') !== 'core') n += 1;
        if ((f.clusters || []).length > 0) n += 1;
        if ((f.branded || 'all') !== 'all') n += 1;
        if ((f.llms || []).length > 0) n += 1;
        return n;
    },

    /**
     * Sufijo de query string con el filtro activo (empieza por '&' o es '').
     * - prompt_set solo se envía si el proyecto tiene sets habilitados.
     * - clusters/branded/llms solo cuando difieren del default.
     */
    getReportFilterParams() {
        const cfg = this.reportFilterConfig;
        if (!cfg) return '';
        const f = this.reportFilters || this._defaultReportFilters();
        let params = '';
        if (cfg.setsEnabled) {
            params += `&prompt_set=${encodeURIComponent(f.set || 'core')}`;
        }
        if ((f.clusters || []).length > 0) {
            params += `&clusters=${encodeURIComponent(f.clusters.join(','))}`;
        }
        if ((f.branded || 'all') !== 'all') {
            params += `&branded=${encodeURIComponent(f.branded)}`;
        }
        const enabled = cfg.enabledLlms || [];
        const selected = f.llms || [];
        if (selected.length > 0 && selected.length < enabled.length) {
            params += `&llms=${encodeURIComponent(selected.join(','))}`;
        }
        return params;
    },

    /**
     * Carga la config del proyecto y pinta la barra. Se llama desde
     * viewProject() ANTES de las cargas de datos. Resetea el estado SOLO al
     * cambiar de proyecto (sin persistencia entre visitas — decisión de
     * producto: cada entrada al dashboard empieza limpia).
     */
    async initReportFilters(projectId) {
        if (this._filtersProjectId !== projectId) {
            this._filtersProjectId = projectId;
            this.reportFilters = this._defaultReportFilters();
        }
        this.reportFilterConfig = null;
        try {
            const [setsRes, clustersRes] = await Promise.all([
                fetch(`${this.baseUrl}/projects/${projectId}/sets`),
                fetch(`${this.baseUrl}/projects/${projectId}/clusters`)
            ]);
            const setsData = setsRes.ok ? await setsRes.json() : null;
            const clustersData = clustersRes.ok ? await clustersRes.json() : null;

            const setsCfg = setsData?.sets_config || { enabled: false, sets: [] };
            const clustersCfg = clustersData?.clusters_config || { enabled: false, clusters: [] };

            this.reportFilterConfig = {
                setsEnabled: !!setsCfg.enabled && (setsCfg.sets || []).length > 0,
                sets: setsCfg.sets || [],
                setCounts: setsData?.counts || {},
                activeToday: setsData?.active_today || {},
                clustersEnabled: !!clustersCfg.enabled && (clustersCfg.clusters || []).length > 0,
                clusters: (clustersCfg.clusters || []).map(c => c.name).filter(Boolean),
                enabledLlms: setsData?.enabled_llms || []
            };

            this._sanitizeReportFilters();
            this.renderReportFilterBar();
            this._setupFilterBarStickyShadow();
        } catch (error) {
            console.warn('Could not load report filter config:', error);
            this.reportFilterConfig = null;
            this.renderReportFilterBar();
        }
    },

    /** Poda del estado valores que ya no existen en la config del proyecto. */
    _sanitizeReportFilters() {
        const cfg = this.reportFilterConfig;
        const f = this.reportFilters || this._defaultReportFilters();
        const validSets = new Set((cfg?.sets || []).map(s => s.name));
        if (f.set !== 'core' && !validSets.has(f.set)) f.set = 'core';
        const validClusters = new Set(cfg?.clusters || []);
        f.clusters = (f.clusters || []).filter(c => validClusters.has(c));
        const enabled = new Set(cfg?.enabledLlms || []);
        f.llms = (f.llms || []).filter(l => enabled.has(l));
        if (!['all', 'branded', 'non_branded'].includes(f.branded)) f.branded = 'all';
        this.reportFilters = f;
    },

    /** Pinta (o esconde) la barra según la config del proyecto. */
    renderReportFilterBar() {
        const bar = document.getElementById('reportFilterBar');
        if (!bar) return;
        const cfg = this.reportFilterConfig;
        if (!cfg) {
            bar.style.display = 'none';
            return;
        }
        const f = this.reportFilters || this._defaultReportFilters();

        // La barra siempre se muestra: branded y LLMs aplican a cualquier
        // proyecto; sets/clusters solo si están configurados.
        bar.style.display = 'flex';

        // ── Toggle exclusivo de sets ──
        const setGroup = document.getElementById('setFilterGroup');
        const setToggle = document.getElementById('setFilterToggle');
        if (setGroup && setToggle) {
            const showSets = !!cfg.setsEnabled;
            setGroup.style.display = showSets ? 'flex' : 'none';
            if (showSets) {
                const counts = cfg.setCounts || {};
                const active = cfg.activeToday || {};
                const options = [{ key: 'core', label: 'Core', window: null, inWindow: true }]
                    .concat(cfg.sets.map(s => ({
                        key: s.name,
                        label: s.name,
                        window: s.window || null,
                        inWindow: active[s.name] !== false
                    })));
                setToggle.innerHTML = options.map(opt => {
                    const isActive = (f.set || 'core') === opt.key;
                    const count = counts[opt.key === 'core' ? 'core' : opt.key];
                    const countHtml = (count !== undefined)
                        ? ` <span class="set-count">(${count})</span>` : '';
                    const dotHtml = opt.window
                        ? `<span class="set-window-dot ${opt.inWindow ? 'in-window' : 'out-of-window'}"
                                 title="${opt.inWindow ? 'In season today' : 'Out of season today'} (${this.escapeHtml(opt.window.start)} → ${this.escapeHtml(opt.window.end)} UTC)"></span>`
                        : '';
                    return `<button type="button" role="tab"
                                    class="set-option ${isActive ? 'active' : ''}"
                                    data-set="${this.escapeHtml(opt.key)}">
                                ${dotHtml}${this.escapeHtml(opt.label)}${countHtml}
                            </button>`;
                }).join('');
                setToggle.querySelectorAll('.set-option').forEach(btn => {
                    btn.addEventListener('click', () => this.onReportSetChange(btn.dataset.set));
                });
            }
        }

        // ── Chips multiselección de clusters ──
        const clusterGroup = document.getElementById('clusterFilterGroup');
        const clusterChips = document.getElementById('clusterFilterChips');
        if (clusterGroup && clusterChips) {
            const showClusters = !!cfg.clustersEnabled;
            clusterGroup.style.display = showClusters ? 'flex' : 'none';
            if (showClusters) {
                const selected = new Set(f.clusters || []);
                clusterChips.innerHTML = cfg.clusters.map(name => `
                    <button type="button"
                            class="cluster-chip ${selected.has(name) ? 'active' : ''}"
                            data-cluster="${this.escapeHtml(name)}">
                        ${this.escapeHtml(name)}
                    </button>
                `).join('');
                clusterChips.querySelectorAll('.cluster-chip').forEach(chip => {
                    chip.addEventListener('click', () => this.onReportClusterToggle(chip.dataset.cluster));
                });
            }
        }

        // ── Brand scope (exclusivo: Todos / Non-branded / Branded) ──
        const brandToggle = document.getElementById('brandFilterToggle');
        if (brandToggle) {
            const current = f.branded || 'all';
            brandToggle.innerHTML = [
                { key: 'all', label: 'All' },
                { key: 'non_branded', label: 'Non-branded' },
                { key: 'branded', label: 'Branded' },
            ].map(opt => `
                <button type="button" role="tab"
                        class="set-option ${current === opt.key ? 'active' : ''}"
                        data-branded="${opt.key}">
                    ${opt.label}
                </button>
            `).join('');
            brandToggle.querySelectorAll('.set-option').forEach(btn => {
                btn.addEventListener('click', () => this.onReportBrandedChange(btn.dataset.branded));
            });
        }

        // ── LLMs (dropdown con checks) ──
        this._renderLlmFilterDropdown();

        // ── Reset (visible solo si el filtro difiere del default) ──
        const resetBtn = document.getElementById('btnResetReportFilters');
        if (resetBtn) {
            const activeCount = this._activeReportFilterCount();
            resetBtn.style.display = activeCount > 0 ? 'inline-flex' : 'none';
            const countEl = resetBtn.querySelector('.reset-count');
            if (countEl) countEl.textContent = activeCount > 0 ? `(${activeCount})` : '';
            resetBtn.onclick = () => this.resetReportFilters();
        }
    },

    _renderLlmFilterDropdown() {
        const group = document.getElementById('llmFilterGroup');
        const dropdown = document.getElementById('llmFilterDropdown');
        if (!group || !dropdown) return;
        const cfg = this.reportFilterConfig;
        const enabled = cfg?.enabledLlms || [];
        if (enabled.length <= 1) {
            group.style.display = 'none';
            return;
        }
        group.style.display = 'flex';

        const f = this.reportFilters || this._defaultReportFilters();
        const selected = new Set(f.llms || []);
        const effectiveAll = selected.size === 0 || selected.size === enabled.length;
        const triggerLabel = effectiveAll
            ? 'All LLMs'
            : (selected.size === 1
                ? (REPORT_LLM_LABELS_REF[[...selected][0]] || [...selected][0])
                : `${selected.size} of ${enabled.length} LLMs`);

        dropdown.innerHTML = `
            <button type="button" class="llm-filter-trigger ${effectiveAll ? '' : 'has-selection'}"
                    aria-haspopup="true" aria-expanded="false">
                <i class="fas fa-microchip"></i>
                <span class="llm-filter-trigger-label">${this.escapeHtml(triggerLabel)}</span>
                <i class="fas fa-chevron-down llm-filter-caret"></i>
            </button>
            <div class="llm-filter-menu" role="menu" style="display:none;">
                ${enabled.map(llm => `
                    <label class="llm-filter-option">
                        <input type="checkbox" value="${this.escapeHtml(llm)}"
                               ${effectiveAll || selected.has(llm) ? 'checked' : ''}>
                        <span>${this.escapeHtml(REPORT_LLM_LABELS_REF[llm] || llm)}</span>
                    </label>
                `).join('')}
            </div>
        `;

        const trigger = dropdown.querySelector('.llm-filter-trigger');
        const menu = dropdown.querySelector('.llm-filter-menu');
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = menu.style.display !== 'none';
            menu.style.display = open ? 'none' : 'block';
            trigger.setAttribute('aria-expanded', String(!open));
        });
        // Cierre al clicar fuera (listener único a nivel de documento)
        if (!this._llmDropdownOutsideBound) {
            this._llmDropdownOutsideBound = true;
            document.addEventListener('click', (e) => {
                const dd = document.getElementById('llmFilterDropdown');
                if (dd && !dd.contains(e.target)) {
                    const m = dd.querySelector('.llm-filter-menu');
                    const t = dd.querySelector('.llm-filter-trigger');
                    if (m) m.style.display = 'none';
                    if (t) t.setAttribute('aria-expanded', 'false');
                }
            });
        }
        menu.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', () => {
                const checked = [...menu.querySelectorAll('input:checked')].map(i => i.value);
                // Desmarcar todo no tiene sentido como vista (dashboard vacío):
                // se interpreta como "todos".
                this.onReportLlmsChange(checked.length === 0 ? [] : checked);
            });
        });
    },

    /**
     * Sombra sutil cuando la barra está pegada arriba. Listener de scroll con
     * rAF (barato y determinista): la barra está "stuck" cuando su sentinel
     * (1px justo encima) ha salido del viewport por arriba.
     */
    _setupFilterBarStickyShadow() {
        if (this._filterBarScrollBound) return;
        this._filterBarScrollBound = true;
        let lastRun = 0;
        const update = () => {
            const bar = document.getElementById('reportFilterBar');
            const sentinel = document.getElementById('reportFilterBarSentinel');
            if (!bar || !sentinel) return;
            bar.classList.toggle('is-stuck', sentinel.getBoundingClientRect().bottom < 0);
        };
        const onScroll = () => {
            // Throttle sencillo (~60fps) sin depender de requestAnimationFrame
            const now = Date.now();
            if (now - lastRun < 16) return;
            lastRun = now;
            update();
        };
        window.addEventListener('scroll', onScroll, { passive: true, capture: true });
        update();
    },

    async onReportSetChange(setKey) {
        if ((this.reportFilters.set || 'core') === setKey) return;
        this.reportFilters.set = setKey;
        await this._reloadReportWithFilters();
    },

    async onReportClusterToggle(name) {
        const current = new Set(this.reportFilters.clusters || []);
        if (current.has(name)) {
            current.delete(name);
        } else {
            current.add(name);
        }
        this.reportFilters.clusters = Array.from(current);
        await this._reloadReportWithFilters();
    },

    async onReportBrandedChange(value) {
        if ((this.reportFilters.branded || 'all') === value) return;
        this.reportFilters.branded = value;
        await this._reloadReportWithFilters();
    },

    async onReportLlmsChange(llms) {
        const enabled = this.reportFilterConfig?.enabledLlms || [];
        // Selección completa equivale a "sin filtro"
        this.reportFilters.llms = (llms.length >= enabled.length) ? [] : llms;
        await this._reloadReportWithFilters();
    },

    async resetReportFilters() {
        this.reportFilters = this._defaultReportFilters();
        await this._reloadReportWithFilters();
    },

    /**
     * Recarga todo el informe con el filtro vigente. Serializa recargas y
     * COALESCE de clicks en ráfaga: si el usuario cambia tres filtros seguidos,
     * la recarga en curso termina y se lanza UNA más con el estado final (los
     * fetches leen el estado vivo). Sin esto, una respuesta lenta del filtro
     * anterior podía pisar los datos del filtro nuevo.
     */
    async _reloadReportWithFilters() {
        this.renderReportFilterBar();
        const projectId = this.currentProject?.id;
        if (!projectId) return;

        this._pendingFilterReload = true;
        if (this._filterReloadRunning) return;
        this._filterReloadRunning = true;

        const bar = document.getElementById('reportFilterBar');
        try {
            while (this._pendingFilterReload) {
                this._pendingFilterReload = false;
                if (bar) bar.classList.add('is-reloading');
                await this.viewProject(projectId);
                if (this.responsesLoaded) {
                    await this.loadResponses();
                }
            }
        } finally {
            this._filterReloadRunning = false;
            if (bar) bar.classList.remove('is-reloading');
        }
    }
});
