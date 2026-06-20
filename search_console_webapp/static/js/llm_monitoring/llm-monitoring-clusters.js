/**
 * LLM Monitoring - métodos de prototipo: clusters
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

async loadClustersConfig(projectId) {
        if (!projectId) {
            this.promptClustersConfig = { enabled: false, clusters: [], counts: {} };
            return this.promptClustersConfig;
        }
        try {
            const resp = await fetch(`${this.baseUrl}/projects/${projectId}/clusters`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const cfg = data.clusters_config || { enabled: false, clusters: [] };
            const clustersArr = Array.isArray(cfg.clusters)
                ? cfg.clusters.map(c => (typeof c === 'string' ? { name: c } : { name: c?.name || '' }))
                    .filter(c => c.name)
                : [];
            this.promptClustersConfig = {
                enabled: !!cfg.enabled,
                clusters: clustersArr,
                counts: data.counts || {}
            };
            // Mirror toggle in UI
            const enableCb = document.getElementById('promptClustersEnabled');
            if (enableCb) enableCb.checked = this.promptClustersConfig.enabled;
            this.toggleClustersConfigContainer(this.promptClustersConfig.enabled);
            return this.promptClustersConfig;
        } catch (err) {
            console.warn('Could not load clusters config:', err);
            this.promptClustersConfig = { enabled: false, clusters: [], counts: {} };
            return this.promptClustersConfig;
        }
    },

toggleClustersConfigContainer(enabled) {
        const container = document.getElementById('promptClustersContainer');
        if (!container) return;
        container.classList.toggle('disabled', !enabled);
    },

getDefinedClusterNames() {
        const cfg = this.promptClustersConfig || { clusters: [] };
        return (cfg.clusters || [])
            .map(c => (c?.name || '').trim())
            .filter(Boolean);
    },

addClusterRow() {
        // Defensive init: this can be called before loadClustersConfig completes
        if (!this.promptClustersConfig) {
            this.promptClustersConfig = { enabled: true, clusters: [], counts: {} };
        }
        // Sync any in-flight edits from existing inputs first so we don't lose
        // names the user just typed in other rows.
        this._syncClustersConfigFromUI();
        // Ensure enabled flag is on — user is creating a cluster
        this.promptClustersConfig.enabled = true;
        const enableCb = document.getElementById('promptClustersEnabled');
        if (enableCb) enableCb.checked = true;
        this.toggleClustersConfigContainer(true);

        this.promptClustersConfig.clusters = this.promptClustersConfig.clusters || [];
        this.promptClustersConfig.clusters.push({ name: '' });
        this.renderClustersManagerList();

        // Focus on the last input so the user can type immediately
        const list = document.getElementById('clustersList');
        if (list) {
            const inputs = list.querySelectorAll('.cluster-name-input');
            const last = inputs[inputs.length - 1];
            if (last) {
                last.focus();
                // Submit on Enter for ergonomics
                last.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.saveClustersConfig();
                    }
                }, { once: true });
            }
        }
    },

removeClusterRow(btnEl) {
        const row = btnEl?.closest('.llm-cluster-row');
        if (!row) return;
        const idx = parseInt(row.dataset.index || '-1', 10);
        if (idx >= 0 && this.promptClustersConfig?.clusters) {
            this.promptClustersConfig.clusters.splice(idx, 1);
            this.renderClustersManagerList();
        }
    },

_syncClustersConfigFromUI() {
        const enableCb = document.getElementById('promptClustersEnabled');
        const enabled = !!(enableCb && enableCb.checked);

        const list = document.getElementById('clustersList');
        const rows = list ? list.querySelectorAll('.llm-cluster-row') : [];
        const seen = new Set();
        const result = [];

        for (const row of rows) {
            const input = row.querySelector('.cluster-name-input');
            const raw = (input?.value || '').trim().replace(/\s+/g, ' ').slice(0, 80);
            if (!raw) continue;
            const key = raw.toLowerCase();
            if (seen.has(key)) continue;
            seen.add(key);
            result.push({ name: raw });
        }

        this.promptClustersConfig = {
            enabled: enabled && result.length > 0,
            clusters: result,
            counts: this.promptClustersConfig?.counts || {}
        };
        return true;
    },

async saveClustersConfig() {
        const projectId = this.currentProject?.id;
        if (!projectId) {
            this.showError('No project selected');
            return;
        }
        const hint = document.getElementById('clustersSaveHint');
        if (!this._syncClustersConfigFromUI()) return;

        // ✨ Front-end validation: detect rows that exist in the DOM but have empty names
        const list = document.getElementById('clustersList');
        const domRowCount = list ? list.querySelectorAll('.llm-cluster-row').length : 0;
        const validClusters = this.promptClustersConfig.clusters || [];

        // If the user has rows but none of them have valid names → warn instead of silently saving empty
        if (domRowCount > 0 && validClusters.length === 0) {
            if (hint) {
                hint.className = 'clusters-save-hint error';
                hint.textContent = 'Please type a name for each cluster before saving.';
            }
            this.showError('Please type a name for each cluster before saving.');
            // Focus first empty input
            const firstEmpty = list.querySelector('.cluster-name-input');
            if (firstEmpty) firstEmpty.focus();
            return;
        }

        // If user clicks Save with no rows at all → confirm they want to disable clusters
        if (domRowCount === 0 && (this.promptClustersConfig?.clusters || []).length === 0) {
            // Only confirm if there were clusters previously (avoid no-op confirmation on first use)
            const counts = this.promptClustersConfig?.counts || {};
            const hasExistingAssignments = Object.keys(counts).some(k => k !== 'Unassigned' && counts[k] > 0);
            if (hasExistingAssignments) {
                const proceed = confirm(
                    'You are about to remove all clusters. Any prompts assigned to clusters will be unassigned. Continue?'
                );
                if (!proceed) {
                    if (hint) hint.textContent = '';
                    return;
                }
            } else {
                // Nothing to save — just hint that they should add a cluster
                if (hint) {
                    hint.className = 'clusters-save-hint';
                    hint.textContent = 'Add at least one cluster before saving.';
                }
                this.showInfo('Click "Add cluster" first, then type a name and save.');
                return;
            }
        }

        const payload = {
            clusters_config: {
                enabled: !!this.promptClustersConfig.enabled,
                clusters: (this.promptClustersConfig.clusters || []).map(c => ({ name: c.name }))
            }
        };

        try {
            if (hint) {
                hint.className = 'clusters-save-hint';
                hint.textContent = 'Saving...';
            }
            const resp = await fetch(`${this.baseUrl}/projects/${projectId}/clusters`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.error || `HTTP ${resp.status}`);
            }

            // Refresh counts from server (prompts may have been orphaned)
            await this.loadClustersConfig(projectId);
            // Re-fetch prompts (topic_cluster may have changed on some)
            await this.loadPrompts(projectId, true);
            // Refresh UI pieces that depend on clusters
            this.refreshPromptClusterSelects();
            this.populatePromptsListClusterFilter();
            this.populateResponsesClusterFilter();
            this.renderClustersManagerList();
            // If the chart is on screen, refresh it
            this.loadClustersPerformance(projectId);

            const savedCount = (this.promptClustersConfig?.clusters || []).length;
            const baseMsg = savedCount > 0
                ? `Saved ${savedCount} cluster${savedCount === 1 ? '' : 's'}.`
                : 'Cluster configuration cleared.';
            const orphanMsg = data.orphaned_prompts > 0
                ? ` ${data.orphaned_prompts} prompt${data.orphaned_prompts === 1 ? ' was' : 's were'} unassigned.`
                : '';

            if (hint) {
                hint.className = 'clusters-save-hint saved';
                hint.textContent = baseMsg + orphanMsg;
                setTimeout(() => { if (hint) hint.textContent = ''; }, 5000);
            }
            // Visible toast as well
            if (savedCount > 0) {
                this.showSuccess(baseMsg + orphanMsg);
            } else {
                this.showInfo(baseMsg + orphanMsg);
            }
        } catch (err) {
            console.error('❌ Error saving clusters:', err);
            if (hint) {
                hint.className = 'clusters-save-hint error';
                hint.textContent = `Error: ${err.message || 'could not save'}`;
            }
            this.showError(`Could not save clusters: ${err.message || ''}`);
        }
    },

populateResponsesClusterFilter() {
        const sel = document.getElementById('responsesClusterFilter');
        const wrapper = document.getElementById('responsesClusterFilterWrapper');
        if (!sel) return;
        const clusters = this.getDefinedClusterNames();
        const enabled = this.promptClustersConfig?.enabled;
        if (!enabled || clusters.length === 0) {
            if (wrapper) wrapper.style.display = 'none';
            sel.value = '';
            return;
        }
        if (wrapper) wrapper.style.display = '';
        const prev = sel.value;
        const options = [
            `<option value="">All Clusters</option>`,
            `<option value="__unassigned__">Unassigned</option>`,
            ...clusters.map(n => `<option value="${this.escapeHtml(n)}">${this.escapeHtml(n)}</option>`)
        ].join('');
        sel.innerHTML = options;
        if (prev && (prev === '__unassigned__' || clusters.includes(prev))) {
            sel.value = prev;
        }
    },

async loadClustersPerformance(projectId) {
        if (!projectId) projectId = this.currentProject?.id;
        if (!projectId) return;
        const metric = document.querySelector('input[name="globalSovMetric"]:checked')?.value || 'weighted';
        try {
            // Always reload clusters config for the CURRENT project to avoid stale
            // data when switching between projects (e.g. project A has no clusters,
            // project B does — without reload the chart would show empty state).
            await this.loadClustersConfig(projectId);

            const resp = await fetch(
                `${this.baseUrl}/projects/${projectId}/clusters/metrics?days=${this.globalTimeRange}&metric=${encodeURIComponent(metric)}`
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this.renderClustersPerformanceChart(data, metric);
        } catch (err) {
            console.error('❌ Error loading clusters performance:', err);
            this.renderClustersPerformanceChart({ success: false, clusters: [] }, metric);
        }
    }

});
