/**
 * LLM Monitoring - métodos de prototipo: prompt sets
 *
 * Espejo del patrón de clusters (llm-monitoring-clusters.js): config del
 * proyecto + asignación por prompt. Diferencias:
 * - El set "Core" (núcleo) es implícito: prompt_set = NULL, siempre existe
 *   y no se edita ni se borra.
 * - Cada set adicional puede llevar ventana estacional (MM-DD → MM-DD, UTC).
 *   Fuera de ventana el cron NO analiza sus prompts (y no consumen API).
 */
Object.assign(LLMMonitoring.prototype, {

async loadSetsConfig(projectId) {
        if (!projectId) {
            this.promptSetsConfig = { enabled: false, sets: [], counts: {}, activeToday: {} };
            return this.promptSetsConfig;
        }
        try {
            const resp = await fetch(`${this.baseUrl}/projects/${projectId}/sets`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const cfg = data.sets_config || { enabled: false, sets: [] };
            const setsArr = Array.isArray(cfg.sets)
                ? cfg.sets
                    .map(s => (typeof s === 'string'
                        ? { name: s, window: null }
                        : { name: s?.name || '', window: s?.window || null }))
                    .filter(s => s.name)
                : [];
            this.promptSetsConfig = {
                enabled: !!cfg.enabled,
                sets: setsArr,
                counts: data.counts || {},
                activeToday: data.active_today || {}
            };
            const enableCb = document.getElementById('promptSetsEnabled');
            if (enableCb) enableCb.checked = this.promptSetsConfig.enabled;
            this.toggleSetsConfigContainer(this.promptSetsConfig.enabled);
            return this.promptSetsConfig;
        } catch (err) {
            console.warn('Could not load sets config:', err);
            this.promptSetsConfig = { enabled: false, sets: [], counts: {}, activeToday: {} };
            return this.promptSetsConfig;
        }
    },

toggleSetsConfigContainer(enabled) {
        const container = document.getElementById('promptSetsContainer');
        if (!container) return;
        container.classList.toggle('disabled', !enabled);
    },

getDefinedSetNames() {
        const cfg = this.promptSetsConfig || { sets: [] };
        return (cfg.sets || [])
            .map(s => (s?.name || '').trim())
            .filter(Boolean);
    },

renderSetsManagerList() {
        const list = document.getElementById('setsList');
        const emptyHint = document.getElementById('setsEmptyHint');
        if (!list) return;

        const cfg = this.promptSetsConfig || { sets: [], counts: {} };
        const sets = cfg.sets || [];
        const counts = cfg.counts || {};
        const activeToday = cfg.activeToday || {};

        if (emptyHint) emptyHint.style.display = sets.length === 0 ? '' : 'none';

        // Fila fija informativa del set Core + filas editables de sets
        const coreCount = counts.core !== undefined ? counts.core : 0;
        let html = `
            <div class="llm-set-row llm-set-row-core">
                <span class="prompt-set-badge set-core"><i class="fas fa-anchor"></i> Core</span>
                <span class="set-row-hint">Always analyzed, all year round. Prompts without a set belong here (${coreCount}).</span>
            </div>
        `;

        html += sets.map((s, idx) => {
            const count = counts[s.name] !== undefined ? ` (${counts[s.name]})` : '';
            const win = s.window || {};
            const hasWindow = !!(win.start && win.end);
            const inWindow = activeToday[s.name] !== false;
            const windowState = hasWindow
                ? `<span class="set-window-dot ${inWindow ? 'in-window' : 'out-of-window'}"
                         title="${inWindow ? 'In season today (UTC)' : 'Out of season today (UTC) — not analyzed by the daily run'}"></span>`
                : '';
            return `
                <div class="llm-set-row" data-index="${idx}">
                    ${windowState}
                    <input type="text"
                           class="form-control set-name-input"
                           placeholder="Set name (e.g. Black Friday)"
                           maxlength="80"
                           value="${this.escapeHtml(s.name)}">
                    <span class="set-window-fields" title="Seasonal window (UTC). Leave empty for an always-active set.">
                        <input type="text" class="form-control set-window-start"
                               placeholder="MM-DD" maxlength="5" size="5"
                               value="${this.escapeHtml(win.start || '')}">
                        <span class="set-window-arrow">→</span>
                        <input type="text" class="form-control set-window-end"
                               placeholder="MM-DD" maxlength="5" size="5"
                               value="${this.escapeHtml(win.end || '')}">
                    </span>
                    <span class="set-row-count">${count}</span>
                    <button type="button" class="btn btn-icon btn-sm"
                            title="Remove set (its prompts go back to Core)"
                            onclick="window.llmMonitoring.removeSetRow(this)">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
        }).join('');

        list.innerHTML = html;
    },

addSetRow() {
        if (!this.promptSetsConfig) {
            this.promptSetsConfig = { enabled: true, sets: [], counts: {}, activeToday: {} };
        }
        this._syncSetsConfigFromUI();
        this.promptSetsConfig.enabled = true;
        const enableCb = document.getElementById('promptSetsEnabled');
        if (enableCb) enableCb.checked = true;
        this.toggleSetsConfigContainer(true);

        this.promptSetsConfig.sets = this.promptSetsConfig.sets || [];
        this.promptSetsConfig.sets.push({ name: '', window: null });
        this.renderSetsManagerList();

        const list = document.getElementById('setsList');
        if (list) {
            const inputs = list.querySelectorAll('.set-name-input');
            const last = inputs[inputs.length - 1];
            if (last) {
                last.focus();
                last.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.saveSetsConfig();
                    }
                }, { once: true });
            }
        }
    },

removeSetRow(btnEl) {
        const row = btnEl?.closest('.llm-set-row');
        if (!row || row.classList.contains('llm-set-row-core')) return;
        const idx = parseInt(row.dataset.index || '-1', 10);
        if (idx >= 0 && this.promptSetsConfig?.sets) {
            this._syncSetsConfigFromUI();
            this.promptSetsConfig.sets.splice(idx, 1);
            this.renderSetsManagerList();
        }
    },

_syncSetsConfigFromUI() {
        const enableCb = document.getElementById('promptSetsEnabled');
        const enabled = !!(enableCb && enableCb.checked);

        const list = document.getElementById('setsList');
        const rows = list ? list.querySelectorAll('.llm-set-row:not(.llm-set-row-core)') : [];
        const seen = new Set();
        const result = [];

        for (const row of rows) {
            const nameInput = row.querySelector('.set-name-input');
            const raw = (nameInput?.value || '').trim().replace(/\s+/g, ' ').slice(0, 80);
            if (!raw) continue;
            const key = raw.toLowerCase();
            if (seen.has(key)) continue;
            seen.add(key);

            const start = (row.querySelector('.set-window-start')?.value || '').trim();
            const end = (row.querySelector('.set-window-end')?.value || '').trim();
            const entry = { name: raw };
            if (start || end) {
                entry.window = { start, end };
            }
            result.push(entry);
        }

        this.promptSetsConfig = {
            enabled: enabled && result.length > 0,
            sets: result,
            counts: this.promptSetsConfig?.counts || {},
            activeToday: this.promptSetsConfig?.activeToday || {}
        };
        return true;
    },

async saveSetsConfig() {
        const projectId = this.currentProject?.id;
        if (!projectId) {
            this.showError('No project selected');
            return;
        }
        const hint = document.getElementById('setsSaveHint');
        this._syncSetsConfigFromUI();

        // Validación front de ventanas MM-DD (el backend re-valida)
        const windowRe = /^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$/;
        for (const s of (this.promptSetsConfig.sets || [])) {
            const win = s.window;
            if (!win) continue;
            const bothFilled = !!(win.start && win.end);
            if (!bothFilled || !windowRe.test(win.start) || !windowRe.test(win.end)) {
                if (hint) {
                    hint.textContent = `"${s.name}": seasonal window must be MM-DD → MM-DD (e.g. 11-15 → 12-02), or both empty.`;
                    hint.classList.add('error');
                }
                return;
            }
        }

        try {
            const resp = await fetch(`${this.baseUrl}/projects/${projectId}/sets`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sets_config: {
                        enabled: this.promptSetsConfig.enabled,
                        sets: this.promptSetsConfig.sets
                    }
                })
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.error || `HTTP ${resp.status}`);
            }

            if (hint) {
                hint.classList.remove('error');
                const reassigned = data.reassigned_to_core || 0;
                hint.textContent = reassigned > 0
                    ? `Saved. ${reassigned} prompt(s) moved back to Core.`
                    : 'Saved.';
                setTimeout(() => { hint.textContent = ''; }, 4000);
            }

            // Refrescar estado local + selects + barra de filtros del informe
            await this.loadSetsConfig(projectId);
            this.renderSetsManagerList();
            this.refreshPromptClusterSelects();
            this.updatePromptsMgmtTabCounts();
            await this.initReportFilters(projectId);
        } catch (err) {
            console.error('❌ Error saving sets:', err);
            if (hint) {
                hint.textContent = err.message || 'Failed to save sets';
                hint.classList.add('error');
            }
        }
    },

buildPromptSetSelectHtml(query) {
        const cfg = this.promptSetsConfig;
        const sets = this.getDefinedSetNames();
        if (!cfg || !cfg.enabled || sets.length === 0) return '';

        const current = query.prompt_set || '';
        const state = current ? 'assigned' : 'unassigned';
        const options = [
            `<option value="">Core</option>`,
            ...sets.map(name => {
                const selected = (name === current) ? 'selected' : '';
                return `<option value="${this.escapeHtml(name)}" ${selected}>${this.escapeHtml(name)}</option>`;
            })
        ].join('');

        return `
            <span class="prompt-cluster-select-wrapper prompt-set-select-wrapper" title="Prompt set: Core is always analyzed; seasonal sets only inside their window">
                <i class="fas fa-calendar-alt"></i>
                <select class="prompt-cluster-select prompt-set-select"
                        data-state="${state}"
                        data-query-id="${query.id}"
                        onchange="window.llmMonitoring.onPromptSetChange(this, ${query.id})">
                    ${options}
                </select>
            </span>
        `;
    },

async onPromptSetChange(selectEl, queryId) {
        const projectId = this.currentProject?.id;
        if (!projectId || !queryId) return;
        const value = selectEl.value || null;
        const original = selectEl.getAttribute('data-original') || '';
        selectEl.disabled = true;
        try {
            const resp = await fetch(`${this.baseUrl}/projects/${projectId}/queries/${queryId}/set`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ set: value })
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.error || `HTTP ${resp.status}`);
            }
            const prompt = (this.allPrompts || []).find(p => p.id === queryId);
            if (prompt) prompt.prompt_set = data.prompt_set || null;
            selectEl.setAttribute('data-state', value ? 'assigned' : 'unassigned');
            // Refrescar contadores del gestor y de la barra de filtros
            await this.loadSetsConfig(projectId);
            this.renderSetsManagerList();
            await this.initReportFilters(projectId);
        } catch (err) {
            console.error('❌ Error updating set assignment:', err);
            selectEl.value = original;
            this.showError(`Could not update set: ${err.message || ''}`);
        } finally {
            selectEl.disabled = false;
        }
    }
});
