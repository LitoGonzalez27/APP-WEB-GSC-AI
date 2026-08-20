/**
 * LLM Monitoring - filtro global del informe (prompt sets + clusters)
 *
 * El set es una vista EXCLUSIVA: el informe muestra núcleo O un set de
 * tendencia, nunca mezcla (decisión de producto: al activarse un set
 * estacional el denominador del SOV cambia y las series temporales darían
 * saltos artificiales). Los clusters sí son multiselección.
 *
 * Todos los fetches de datos del informe añaden this.getReportFilterParams().
 * Sin sets ni clusters configurados, devuelve '' y el backend sigue por su
 * camino legacy (snapshots preagregados, sin coste extra).
 */
Object.assign(LLMMonitoring.prototype, {

    /** Clave de persistencia por proyecto */
    _reportFiltersStorageKey(projectId) {
        return `llmReportFilters_${projectId}`;
    },

    /**
     * Sufijo de query string con el filtro activo (empieza por '&' o es '').
     * - prompt_set solo se envía si el proyecto tiene sets habilitados
     *   (si no, todo es núcleo y el backend usa el camino rápido legacy).
     * - clusters solo si hay selección (vacío = todos).
     */
    getReportFilterParams() {
        const cfg = this.reportFilterConfig;
        if (!cfg) return '';
        let params = '';
        if (cfg.setsEnabled) {
            params += `&prompt_set=${encodeURIComponent(this.reportFilters.set || 'core')}`;
        }
        if (this.reportFilters.clusters && this.reportFilters.clusters.length > 0) {
            params += `&clusters=${encodeURIComponent(this.reportFilters.clusters.join(','))}`;
        }
        return params;
    },

    /**
     * Carga la config de sets y clusters del proyecto y pinta la barra.
     * Se llama desde viewProject() ANTES de las cargas de datos.
     */
    async initReportFilters(projectId) {
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
                clusters: (clustersCfg.clusters || []).map(c => c.name).filter(Boolean)
            };

            this._restoreReportFilters(projectId);
            this.renderReportFilterBar();
        } catch (error) {
            console.warn('Could not load report filter config:', error);
            this.reportFilterConfig = null;
            this.renderReportFilterBar();
        }
    },

    /** Restaura el filtro persistido, validándolo contra la config actual. */
    _restoreReportFilters(projectId) {
        this.reportFilters = { set: 'core', clusters: [] };
        try {
            const raw = localStorage.getItem(this._reportFiltersStorageKey(projectId));
            if (!raw) return;
            const saved = JSON.parse(raw);
            const cfg = this.reportFilterConfig;
            const validSets = new Set((cfg?.sets || []).map(s => s.name));
            if (saved.set && (saved.set === 'core' || validSets.has(saved.set))) {
                this.reportFilters.set = saved.set;
            }
            const validClusters = new Set(cfg?.clusters || []);
            if (Array.isArray(saved.clusters)) {
                this.reportFilters.clusters = saved.clusters.filter(c => validClusters.has(c));
            }
        } catch (e) {
            /* filtro corrupto → defaults */
        }
    },

    _persistReportFilters() {
        const projectId = this.currentProject?.id;
        if (!projectId) return;
        try {
            localStorage.setItem(
                this._reportFiltersStorageKey(projectId),
                JSON.stringify(this.reportFilters)
            );
        } catch (e) { /* storage lleno/bloqueado: no es crítico */ }
    },

    /** Pinta (o esconde) la barra según la config del proyecto. */
    renderReportFilterBar() {
        const bar = document.getElementById('reportFilterBar');
        if (!bar) return;
        const cfg = this.reportFilterConfig;

        const showSets = !!cfg?.setsEnabled;
        const showClusters = !!cfg?.clustersEnabled;
        if (!showSets && !showClusters) {
            bar.style.display = 'none';
            return;
        }
        bar.style.display = 'flex';

        // ── Toggle exclusivo de sets ──
        const setGroup = document.getElementById('setFilterGroup');
        const setToggle = document.getElementById('setFilterToggle');
        if (setGroup && setToggle) {
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
                    const isActive = (this.reportFilters.set || 'core') === opt.key;
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
            clusterGroup.style.display = showClusters ? 'flex' : 'none';
            if (showClusters) {
                const selected = new Set(this.reportFilters.clusters || []);
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

        // ── Reset (visible solo si el filtro difiere del default) ──
        const resetBtn = document.getElementById('btnResetReportFilters');
        if (resetBtn) {
            const isDefault = (this.reportFilters.set || 'core') === 'core'
                && (this.reportFilters.clusters || []).length === 0;
            resetBtn.style.display = isDefault ? 'none' : 'inline-flex';
            resetBtn.onclick = () => this.resetReportFilters();
        }
    },

    async onReportSetChange(setKey) {
        if ((this.reportFilters.set || 'core') === setKey) return;
        this.reportFilters.set = setKey;
        this._persistReportFilters();
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
        this._persistReportFilters();
        await this._reloadReportWithFilters();
    },

    async resetReportFilters() {
        this.reportFilters = { set: 'core', clusters: [] };
        this._persistReportFilters();
        await this._reloadReportWithFilters();
    },

    /** Recarga todo el informe manteniendo la barra pintada y coherente. */
    async _reloadReportWithFilters() {
        this.renderReportFilterBar();
        const projectId = this.currentProject?.id;
        if (!projectId) return;
        await this.viewProject(projectId);
        if (this.responsesLoaded) {
            await this.loadResponses();
        }
    }
});
