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
        return { set: 'core', clusters: [], branded: 'all', llms: [], prompts: [] };
    },

    /** ¿Hay algún filtro distinto del default? (para Reset y contador) */
    _activeReportFilterCount() {
        const f = this.reportFilters || this._defaultReportFilters();
        let n = 0;
        if ((f.set || 'core') !== 'core') n += 1;
        if ((f.clusters || []).length > 0) n += 1;
        if ((f.branded || 'all') !== 'all') n += 1;
        if ((f.llms || []).length > 0) n += 1;
        if ((f.prompts || []).length > 0) n += 1;
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
        if ((f.prompts || []).length > 0) {
            params += `&prompts=${encodeURIComponent(f.prompts.join(','))}`;
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
        if (!Array.isArray(f.prompts)) f.prompts = [];
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

        // ── Prompt set (dropdown exclusivo) ──
        const setGroup = document.getElementById('setFilterGroup');
        if (setGroup) {
            const showSets = !!cfg.setsEnabled;
            setGroup.style.display = showSets ? 'flex' : 'none';
            if (showSets) {
                const counts = cfg.setCounts || {};
                const active = cfg.activeToday || {};
                const options = [{
                    key: 'core',
                    label: 'Core',
                    count: counts.core,
                    dot: null
                }].concat(cfg.sets.map(s => ({
                    key: s.name,
                    label: s.name,
                    count: counts[s.name],
                    dot: s.window
                        ? {
                            cls: active[s.name] !== false ? 'in-window' : 'out-of-window',
                            title: `${active[s.name] !== false ? 'In season today' : 'Out of season today'} (${s.window.start} → ${s.window.end} UTC)`
                        }
                        : null
                })));
                const current = f.set || 'core';
                const currentOpt = options.find(o => o.key === current) || options[0];
                this._renderExclusiveDropdown({
                    containerId: 'setFilterDropdown',
                    options,
                    currentKey: current,
                    triggerLabel: currentOpt.label
                        + (currentOpt.count !== undefined ? ` (${currentOpt.count})` : ''),
                    hasSelection: current !== 'core',
                    onSelect: (key) => this.onReportSetChange(key)
                });
            }
        }

        // ── Clusters (dropdown multiselección) ──
        const clusterGroup = document.getElementById('clusterFilterGroup');
        if (clusterGroup) {
            const showClusters = !!cfg.clustersEnabled;
            clusterGroup.style.display = showClusters ? 'flex' : 'none';
            if (showClusters) {
                const selected = new Set(f.clusters || []);
                const effectiveAll = selected.size === 0;
                const triggerLabel = effectiveAll
                    ? 'All clusters'
                    : (selected.size === 1
                        ? [...selected][0]
                        : `${selected.size} of ${cfg.clusters.length} clusters`);
                this._renderMultiCheckDropdown({
                    containerId: 'clustersFilterDropdown',
                    items: cfg.clusters.map(name => ({ value: name, label: name })),
                    selectedValues: selected,
                    checkAllWhenEmpty: true,
                    triggerLabel,
                    hasSelection: !effectiveAll,
                    onChange: (values) => {
                        // Todos marcados == sin filtro de clusters
                        const all = values.length >= cfg.clusters.length ? [] : values;
                        this.reportFilters.clusters = all;
                        this._reloadReportWithFilters();
                    }
                });
            }
        }

        // ── Prompt type (dropdown exclusivo) ──
        const current = f.branded || 'all';
        const brandLabels = { all: 'All', non_branded: 'Non-branded', branded: 'Branded' };
        this._renderExclusiveDropdown({
            containerId: 'brandFilterDropdown',
            options: Object.entries(brandLabels).map(([key, label]) => ({ key, label })),
            currentKey: current,
            triggerLabel: brandLabels[current],
            hasSelection: current !== 'all',
            onSelect: (key) => this.onReportBrandedChange(key)
        });

        // ── LLMs (dropdown con checks) ──
        this._renderLlmFilterDropdown();

        // ── Prompts concretos (dropdown con checks + búsqueda) ──
        this._renderPromptsFilterDropdown();

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

    /** Cierre por clic fuera, compartido por TODOS los dropdowns de la barra. */
    _bindDropdownOutsideClose() {
        if (this._filterDropdownOutsideBound) return;
        this._filterDropdownOutsideBound = true;
        document.addEventListener('click', (e) => {
            document.querySelectorAll('#reportFilterBar .llm-filter-dropdown').forEach(dd => {
                if (!dd.contains(e.target)) {
                    const m = dd.querySelector('.llm-filter-menu');
                    const t = dd.querySelector('.llm-filter-trigger');
                    if (m) m.style.display = 'none';
                    if (t) t.setAttribute('aria-expanded', 'false');
                }
            });
        });
    },

    /** Abre/cierra un menú cerrando los demás (solo un dropdown abierto a la vez). */
    _toggleFilterMenu(dropdown) {
        const menu = dropdown.querySelector('.llm-filter-menu');
        const trigger = dropdown.querySelector('.llm-filter-trigger');
        const open = menu.style.display !== 'none';
        document.querySelectorAll('#reportFilterBar .llm-filter-menu').forEach(m => {
            m.style.display = 'none';
        });
        if (!open) {
            menu.style.display = 'block';
        }
        trigger?.setAttribute('aria-expanded', String(!open));
        return !open;
    },

    /**
     * Dropdown EXCLUSIVO (una opción activa): Prompt set y Prompt type.
     * Cada opción aplica al clicarla y cierra el menú.
     */
    _renderExclusiveDropdown({ containerId, options, currentKey, triggerLabel, hasSelection, onSelect }) {
        const dropdown = document.getElementById(containerId);
        if (!dropdown) return;

        dropdown.innerHTML = `
            <button type="button" class="llm-filter-trigger ${hasSelection ? 'has-selection' : ''}"
                    aria-haspopup="true" aria-expanded="false">
                <span class="llm-filter-trigger-label">${this.escapeHtml(triggerLabel)}</span>
                <i class="fas fa-chevron-down llm-filter-caret"></i>
            </button>
            <div class="llm-filter-menu" role="menu" style="display:none;">
                ${options.map(opt => `
                    <button type="button"
                            class="llm-filter-option filter-option-exclusive ${opt.key === currentKey ? 'is-selected' : ''}"
                            data-key="${this.escapeHtml(opt.key)}">
                        ${opt.dot ? `<span class="set-window-dot ${opt.dot.cls}" title="${this.escapeHtml(opt.dot.title)}"></span>` : ''}
                        <span>${this.escapeHtml(opt.label)}</span>
                        ${opt.count !== undefined ? `<span class="filter-option-count">${opt.count}</span>` : ''}
                        <i class="fas fa-check filter-option-check"></i>
                    </button>
                `).join('')}
            </div>
        `;

        const trigger = dropdown.querySelector('.llm-filter-trigger');
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            this._toggleFilterMenu(dropdown);
        });
        dropdown.querySelectorAll('.filter-option-exclusive').forEach(btn => {
            btn.addEventListener('click', () => {
                dropdown.querySelector('.llm-filter-menu').style.display = 'none';
                onSelect(btn.dataset.key);
            });
        });
        this._bindDropdownOutsideClose();
    },

    /**
     * Dropdown MULTISELECCIÓN con checks (Clusters): aplica en cada cambio,
     * como el de LLMs — son listas cortas.
     */
    _renderMultiCheckDropdown({ containerId, items, selectedValues, checkAllWhenEmpty,
                                triggerLabel, hasSelection, onChange }) {
        const dropdown = document.getElementById(containerId);
        if (!dropdown) return;

        const isChecked = (value) => (checkAllWhenEmpty && selectedValues.size === 0)
            || selectedValues.has(value);

        dropdown.innerHTML = `
            <button type="button" class="llm-filter-trigger ${hasSelection ? 'has-selection' : ''}"
                    aria-haspopup="true" aria-expanded="false">
                <span class="llm-filter-trigger-label">${this.escapeHtml(triggerLabel)}</span>
                <i class="fas fa-chevron-down llm-filter-caret"></i>
            </button>
            <div class="llm-filter-menu" role="menu" style="display:none;">
                ${items.map(item => `
                    <label class="llm-filter-option">
                        <input type="checkbox" value="${this.escapeHtml(item.value)}"
                               ${isChecked(item.value) ? 'checked' : ''}>
                        <span>${this.escapeHtml(item.label)}</span>
                    </label>
                `).join('')}
            </div>
        `;

        const trigger = dropdown.querySelector('.llm-filter-trigger');
        const menu = dropdown.querySelector('.llm-filter-menu');
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            this._toggleFilterMenu(dropdown);
        });
        menu.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', () => {
                const checked = [...menu.querySelectorAll('input:checked')].map(i => i.value);
                onChange(checked);
            });
        });
        this._bindDropdownOutsideClose();
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
            this._toggleFilterMenu(dropdown);
        });
        this._bindDropdownOutsideClose();
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
     * Dropdown de prompts concretos: mismo patrón visual que el de LLMs, con
     * búsqueda y select all/none porque un proyecto puede tener 150+ prompts.
     * La lista sale de this.allPrompts (cargada por viewProject→loadPrompts);
     * si aún no está, el menú se completa al abrirse.
     */
    _renderPromptsFilterDropdown() {
        const group = document.getElementById('promptsFilterGroup');
        const dropdown = document.getElementById('promptsFilterDropdown');
        if (!group || !dropdown) return;
        group.style.display = 'flex';

        const f = this.reportFilters || this._defaultReportFilters();
        const selected = new Set(f.prompts || []);
        const total = Array.isArray(this.allPrompts) ? this.allPrompts.length : 0;
        const triggerLabel = selected.size === 0
            ? 'All prompts'
            : (total ? `${selected.size} of ${total} prompts` : `${selected.size} prompts`);

        dropdown.innerHTML = `
            <button type="button" class="llm-filter-trigger ${selected.size === 0 ? '' : 'has-selection'}"
                    aria-haspopup="true" aria-expanded="false">
                <span class="llm-filter-trigger-label">${this.escapeHtml(triggerLabel)}</span>
                <i class="fas fa-chevron-down llm-filter-caret"></i>
            </button>
            <div class="llm-filter-menu prompts-filter-menu" role="menu" style="display:none;"></div>
        `;

        const trigger = dropdown.querySelector('.llm-filter-trigger');
        const menu = dropdown.querySelector('.llm-filter-menu');
        trigger.addEventListener('click', async (e) => {
            e.stopPropagation();
            const opened = this._toggleFilterMenu(dropdown);
            if (opened) {
                await this._fillPromptsFilterMenu(menu);
                menu.querySelector('.prompts-filter-search input')?.focus();
            }
        });
        this._bindDropdownOutsideClose();
    },

    async _fillPromptsFilterMenu(menu) {
        // Asegurar la lista de prompts (viewProject normalmente ya la cargó)
        if (!Array.isArray(this.allPrompts) || this.allPrompts.length === 0) {
            try {
                const projectId = this.currentProject?.id;
                const data = await fetch(`${this.baseUrl}/projects/${projectId}/queries`)
                    .then(r => r.json());
                this.allPrompts = data.queries || [];
            } catch (e) {
                this.allPrompts = this.allPrompts || [];
            }
        }
        const f = this.reportFilters || this._defaultReportFilters();
        const selected = new Set(f.prompts || []);

        menu.innerHTML = `
            <div class="prompts-filter-search">
                <input type="text" class="form-control" placeholder="Search prompts...">
            </div>
            <div class="prompts-filter-actions">
                <button type="button" class="prompts-filter-action" data-action="all">Select all</button>
                <button type="button" class="prompts-filter-action" data-action="none">Clear</button>
            </div>
            <div class="prompts-filter-list">
                ${this.allPrompts.map(p => `
                    <label class="llm-filter-option" title="${this.escapeHtml(p.prompt)}">
                        <input type="checkbox" value="${p.id}" ${selected.has(p.id) ? 'checked' : ''}>
                        <span class="prompts-filter-text">${this.escapeHtml(p.prompt)}</span>
                    </label>
                `).join('')}
            </div>
            <div class="prompts-filter-footer">
                <button type="button" class="btn btn-primary btn-sm prompts-filter-apply">Apply</button>
            </div>
        `;

        // Búsqueda en vivo (client-side sobre la lista pintada)
        menu.querySelector('.prompts-filter-search input').addEventListener('input', (e) => {
            const term = e.target.value.trim().toLowerCase();
            menu.querySelectorAll('.prompts-filter-list .llm-filter-option').forEach(opt => {
                const text = opt.querySelector('.prompts-filter-text')?.textContent.toLowerCase() || '';
                opt.style.display = !term || text.includes(term) ? 'flex' : 'none';
            });
        });

        // Select all / clear operan sobre lo VISIBLE (respetan la búsqueda)
        menu.querySelectorAll('.prompts-filter-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const check = btn.dataset.action === 'all';
                menu.querySelectorAll('.prompts-filter-list .llm-filter-option').forEach(opt => {
                    if (opt.style.display !== 'none') {
                        opt.querySelector('input').checked = check;
                    }
                });
            });
        });

        // Con listas largas, recargar en cada check sería una tortura: el
        // filtro de prompts se aplica con su botón Apply (o al cerrar fuera
        // no — solo Apply, para que el usuario controle el momento).
        menu.querySelector('.prompts-filter-apply').addEventListener('click', () => {
            const checked = [...menu.querySelectorAll('.prompts-filter-list input:checked')]
                .map(i => parseInt(i.value, 10));
            menu.style.display = 'none';
            // Todos marcados == sin filtro
            const all = Array.isArray(this.allPrompts) ? this.allPrompts.length : 0;
            this.onReportPromptsChange(checked.length >= all ? [] : checked);
        });
    },

    async onReportPromptsChange(promptIds) {
        this.reportFilters.prompts = promptIds;
        await this._reloadReportWithFilters();
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
            // La barra queda pegada a `top` px (bajo el navbar fijo), así que
            // está "stuck" cuando el sentinel cruza esa línea, no el 0.
            const stickyTop = parseFloat(getComputedStyle(bar).top) || 0;
            bar.classList.toggle('is-stuck', sentinel.getBoundingClientRect().bottom < stickyTop);
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
