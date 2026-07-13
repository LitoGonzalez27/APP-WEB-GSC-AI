/**
 * LLM Monitoring - métodos de prototipo: url content analysis (Fase 1)
 *
 * Analiza el contenido del Top 30 de URLs citadas por los LLMs:
 * badge "Brand Presence" por fila, detalle expandible con anchors y
 * competidores, filtro "Quick Wins Only" y resumen del análisis.
 *
 * Seguridad: todo dato derivado del contenido scrapeado (títulos, anchors,
 * nombres) se pinta SIEMPRE a través de this.escapeHtml().
 */
Object.assign(LLMMonitoring.prototype, {

initUrlContentUi() {
        if (this._urlContentUiWired) return;
        this._urlContentUiWired = true;

        // Filtro "Quick Wins Only"
        document.getElementById('filterQuickWinsLLM')?.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const isActive = btn.dataset.active === 'true';
            btn.dataset.active = String(!isActive);
            btn.classList.toggle('active', !isActive);

            // Desactivar chips incompatibles (brand filter y vista de dominios)
            const brandBtn = document.getElementById('filterMyBrandUrlsLLM');
            if (brandBtn && brandBtn.dataset.active === 'true') {
                brandBtn.dataset.active = 'false';
                brandBtn.classList.remove('active');
            }
            const domainsBtn = document.getElementById('showTopDomainsLLM');
            if (domainsBtn && domainsBtn.dataset.active === 'true') {
                domainsBtn.dataset.active = 'false';
                domainsBtn.classList.remove('active');
                this.toggleDomainsView(false);
            }

            this.applyQuickWinsFilter(!isActive);
        });

        // Si el usuario activa el filtro de marca o la vista de dominios,
        // el chip de quick wins deja de aplicar: sincronizar su estado visual.
        ['filterMyBrandUrlsLLM', 'showTopDomainsLLM'].forEach(id => {
            document.getElementById(id)?.addEventListener('click', () => {
                const quickWinsBtn = document.getElementById('filterQuickWinsLLM');
                if (quickWinsBtn && quickWinsBtn.dataset.active === 'true') {
                    quickWinsBtn.dataset.active = 'false';
                    quickWinsBtn.classList.remove('active');
                }
            });
        });

        // Delegación: click en un badge con detalle → toggle fila de detalle
        document.getElementById('topUrlsLLMBody')?.addEventListener('click', (e) => {
            const badge = e.target.closest('.presence-badge[data-has-detail="true"]');
            if (!badge) return;
            e.preventDefault();
            this.toggleUrlAnalysisDetail(badge);
        });
    },

getUrlContentAnalysis(url) {
        return this._urlContentByUrl?.[url] || null;
    },

async loadUrlContentAnalysis(projectId, options = {}) {
        const { render = true } = options;
        if (!projectId) return;

        try {
            const params = new URLSearchParams({ days: this.globalTimeRange });
            const response = await fetch(
                `${this.baseUrl}/projects/${projectId}/url-content-analysis?${params}`
            );
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();

            this.urlContentData = data;
            this._urlContentByUrl = {};
            (data.results || []).forEach(item => {
                if (item.analysis) this._urlContentByUrl[item.url] = item.analysis;
            });

            this.renderUrlContentSummary();
            this.updateAnalyzeUrlContentButton();

            if (render) this.rerenderTopUrlsLLMCurrentPage();
        } catch (error) {
            console.error('❌ Error loading URL content analysis:', error);
        }
    },

async startUrlContentAnalysis() {
        const projectId = this.currentProject?.id;
        if (!projectId) return;

        const btn = document.getElementById('btnAnalyzeUrlContent');
        if (btn) btn.disabled = true;

        try {
            const response = await fetch(
                `${this.baseUrl}/projects/${projectId}/url-content-analysis`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ days: this.globalTimeRange })
                }
            );

            if (response.status === 409) {
                // Ya hay un análisis corriendo: engancharse al polling igualmente
                this.showSuccess?.('Content analysis already running, showing progress...');
            } else if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            this._startUrlContentPolling(projectId);
        } catch (error) {
            console.error('❌ Error starting URL content analysis:', error);
            this.showError?.('Could not start the content analysis. Please try again.');
            if (btn) btn.disabled = false;
        }
    },

_startUrlContentPolling(projectId) {
        if (this._urlContentPollTimer) clearInterval(this._urlContentPollTimer);

        let attempts = 0;
        const maxAttempts = 150; // ~10 min a 4s por tick

        const tick = async () => {
            attempts++;
            await this.loadUrlContentAnalysis(projectId);
            const running = this.urlContentData?.progress?.running;
            if (!running || attempts >= maxAttempts) {
                clearInterval(this._urlContentPollTimer);
                this._urlContentPollTimer = null;
                this.updateAnalyzeUrlContentButton();
            }
        };

        this._urlContentPollTimer = setInterval(tick, 4000);
        tick();
    },

updateAnalyzeUrlContentButton() {
        const btn = document.getElementById('btnAnalyzeUrlContent');
        if (!btn) return;

        const running = Boolean(this.urlContentData?.progress?.running);
        btn.disabled = running;

        const label = btn.querySelector('span');
        const icon = btn.querySelector('i');
        if (running) {
            const { done = 0, total = 0 } = this.urlContentData?.progress || {};
            if (label) label.textContent = total > 0 ? `Analyzing ${done}/${total}...` : 'Analyzing...';
            if (icon) icon.className = 'fas fa-spinner fa-spin';
        } else {
            if (label) label.textContent = 'Analyze Top 30 Content';
            if (icon) icon.className = 'fas fa-search-plus';
        }
    },

rerenderTopUrlsLLMCurrentPage() {
        const state = this._topUrlsLLMState;
        if (!state || state.isDomainView) return;
        if (!Array.isArray(this.allLLMUrls) || this.allLLMUrls.length === 0) return;

        const quickWinsBtn = document.getElementById('filterQuickWinsLLM');
        const brandBtn = document.getElementById('filterMyBrandUrlsLLM');

        if (quickWinsBtn?.dataset.active === 'true') {
            this.applyQuickWinsFilter(true);
        } else if (brandBtn?.dataset.active === 'true') {
            this.filterLLMUrlsByBrand(true);
        } else {
            const pageSize = 10;
            const fullList = state.fullList || this.allLLMUrls;
            const totalPages = Math.max(1, Math.ceil(fullList.length / pageSize));
            const page = Math.min(state.page || 1, totalPages);
            const start = (page - 1) * pageSize;
            this._topUrlsLLMState = { page, totalPages, fullList, isDomainView: false };
            this.renderTopUrlsRankingLLM(fullList.slice(start, start + pageSize));
            this.renderTopUrlsLLMPaginator();
        }
    },

applyQuickWinsFilter(active) {
        if (!active) {
            // Volver a la lista completa
            this._topUrlsLLMState = { ...(this._topUrlsLLMState || {}), page: 1, isDomainView: false };
            this.filterLLMUrlsByBrand(false);
            return;
        }

        const filtered = (this.allLLMUrls || [])
            .filter(urlData => this.getUrlContentAnalysis(urlData.url)?.opportunity === 'quick_win')
            .map((urlData, index) => ({ ...urlData, rank: index + 1 }));

        if (filtered.length === 0) {
            this._topUrlsLLMState = { page: 1, totalPages: 1, fullList: [], isDomainView: false };
            this.updateTableHeaderForUrls();
            this.showNoUrlsLLMMessage({
                title: 'No Quick Wins Found',
                description: 'No analyzed URLs mention your competitors without mentioning you.',
                helper: 'Run "Analyze Top 30 Content" or disable this filter to view all cited URLs.'
            });
            this.renderTopUrlsLLMPaginator();
            return;
        }

        const pageSize = 10;
        const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
        const page = Math.min(this._topUrlsLLMState?.page || 1, totalPages);
        const start = (page - 1) * pageSize;

        this._topUrlsLLMState = { page, totalPages, fullList: filtered, isDomainView: false };
        this.updateTableHeaderForUrls();
        this.renderTopUrlsRankingLLM(filtered.slice(start, start + pageSize));
        this.renderTopUrlsLLMPaginator();
    },

renderUrlPresenceCell(url) {
        const analysis = this.getUrlContentAnalysis(url);

        if (!analysis) {
            return '<span class="presence-badge not-analyzed" title="Not analyzed yet. Click \'Analyze Top 30 Content\' above.">' +
                   '<i class="fas fa-minus"></i></span>';
        }

        if (analysis.status !== 'completed') {
            const reason = this.escapeAttr(analysis.error_reason || 'error');
            return `<span class="presence-badge error" title="Could not analyze this page (${reason})">` +
                   '<i class="fas fa-exclamation-triangle"></i> Error</span>';
        }

        const badges = {
            mentioned: { css: 'mentioned', icon: 'fa-check-circle', label: "You're mentioned" },
            quick_win: { css: 'quick-win', icon: 'fa-bolt', label: 'Quick Win' },
            competitor_page: { css: 'competitor-page', icon: 'fa-building', label: 'Competitor site' },
            no_mentions: { css: 'no-mentions', icon: 'fa-circle-notch', label: 'No brands' }
        };
        const badge = badges[analysis.opportunity] || badges.no_mentions;

        return `<span class="presence-badge ${badge.css}" data-has-detail="true" ` +
               `data-url="${this.escapeAttr(url)}" role="button" tabindex="0" ` +
               `title="Click to see details">` +
               `<i class="fas ${badge.icon}"></i> ${badge.label} ` +
               `<i class="fas fa-chevron-down presence-caret"></i></span>`;
    },

toggleUrlAnalysisDetail(badgeEl) {
        const row = badgeEl.closest('tr');
        if (!row) return;

        const existingDetail = row.nextElementSibling;
        if (existingDetail?.classList.contains('url-analysis-detail-row')) {
            existingDetail.remove();
            badgeEl.classList.remove('expanded');
            return;
        }

        // Cerrar cualquier otro detalle abierto
        row.parentElement.querySelectorAll('.url-analysis-detail-row').forEach(el => el.remove());
        row.parentElement.querySelectorAll('.presence-badge.expanded').forEach(el => el.classList.remove('expanded'));

        const url = badgeEl.dataset.url;
        const analysis = this.getUrlContentAnalysis(url);
        if (!analysis) return;

        const detailRow = document.createElement('tr');
        detailRow.className = 'url-analysis-detail-row';
        const colCount = row.children.length;
        detailRow.innerHTML = `<td colspan="${colCount}">${this.buildUrlAnalysisDetailHtml(analysis)}</td>`;
        row.after(detailRow);
        badgeEl.classList.add('expanded');
    },

buildUrlAnalysisDetailHtml(analysis) {
        const esc = (v) => this.escapeHtml(String(v ?? ''));
        const escAttr = (v) => this.escapeAttr(String(v ?? ''));

        const anchorChips = (texts) => (texts || [])
            .map(t => `<span class="anchor-chip" title="${escAttr(t)}">${esc(t.length > 60 ? t.slice(0, 57) + '...' : t)}</span>`)
            .join('') || '<span class="detail-muted">No anchor text</span>';

        // Bloque de tu marca
        let brandBlock;
        if (analysis.brand_mentioned || analysis.brand_linked) {
            brandBlock = `
                <div class="detail-stat">
                    <i class="fas fa-check-circle detail-icon-ok"></i>
                    Mentioned ${analysis.brand_mention_count} time${analysis.brand_mention_count === 1 ? '' : 's'}
                    ${analysis.brand_linked ? ' &middot; <i class="fas fa-link"></i> Linked' : ' &middot; Not linked'}
                </div>
                ${analysis.brand_linked ? `<div class="detail-anchors">${anchorChips(analysis.brand_anchor_texts)}</div>` : ''}
            `;
        } else {
            brandBlock = '<div class="detail-stat detail-muted"><i class="fas fa-times-circle"></i> Your brand is not mentioned on this page</div>';
        }

        // Bloque de competidores (solo los presentes)
        const present = (analysis.competitors_found || []).filter(c => c.mentioned || c.linked);
        let competitorsBlock;
        if (present.length > 0) {
            competitorsBlock = present.map(c => `
                <div class="detail-competitor">
                    <div class="detail-stat">
                        <span class="domain-badge competitor">${esc(c.name || c.domain)}</span>
                        ${c.mention_count} mention${c.mention_count === 1 ? '' : 's'}
                        ${c.linked ? ' &middot; <i class="fas fa-link"></i> Linked' : ''}
                    </div>
                    ${c.linked ? `<div class="detail-anchors">${anchorChips(c.anchor_texts)}</div>` : ''}
                </div>
            `).join('');
        } else {
            competitorsBlock = '<div class="detail-stat detail-muted">No competitors detected on this page</div>';
        }

        const fetchedDate = analysis.fetched_at
            ? new Date(analysis.fetched_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
            : '—';
        const fetchMethodNote = analysis.fetch_method === 'jina' ? ' &middot; via reader proxy' : '';

        return `
            <div class="url-analysis-detail">
                ${analysis.page_title ? `<div class="detail-title" title="${escAttr(analysis.page_title)}"><i class="fas fa-file-alt"></i> ${esc(analysis.page_title)}</div>` : ''}
                <div class="detail-columns">
                    <div class="detail-column">
                        <h5>Your Brand</h5>
                        ${brandBlock}
                    </div>
                    <div class="detail-column">
                        <h5>Competitors</h5>
                        ${competitorsBlock}
                    </div>
                </div>
                <div class="detail-footer">Content analyzed on ${esc(fetchedDate)}${fetchMethodNote}</div>
            </div>
        `;
    },

renderUrlContentSummary() {
        const container = document.getElementById('urlContentSummary');
        const quickWinsBtn = document.getElementById('filterQuickWinsLLM');
        if (!container) return;

        const summary = this.urlContentData?.summary;
        const progress = this.urlContentData?.progress || {};
        const hasData = summary && (summary.analyzed > 0 || summary.errors > 0 || progress.running);

        if (!hasData) {
            container.style.display = 'none';
            if (quickWinsBtn) quickWinsBtn.style.display = 'none';
            return;
        }

        container.style.display = 'flex';
        if (quickWinsBtn) quickWinsBtn.style.display = '';

        const chips = [];
        if (progress.running) {
            const { done = 0, total = 0 } = progress;
            chips.push(`<span class="summary-chip running"><i class="fas fa-spinner fa-spin"></i> Analyzing ${done}/${total || '?'}</span>`);
        }
        chips.push(`<span class="summary-chip mentioned"><i class="fas fa-check-circle"></i> Mentioned: <strong>${summary.mentioned}</strong></span>`);
        chips.push(`<span class="summary-chip quick-win"><i class="fas fa-bolt"></i> Quick Wins: <strong>${summary.quick_wins}</strong></span>`);
        chips.push(`<span class="summary-chip neutral"><i class="fas fa-circle-notch"></i> No brands: <strong>${summary.no_mentions}</strong></span>`);
        if (summary.competitor_pages > 0) {
            chips.push(`<span class="summary-chip neutral"><i class="fas fa-building"></i> Competitor sites: <strong>${summary.competitor_pages}</strong></span>`);
        }
        if (summary.errors > 0) {
            chips.push(`<span class="summary-chip error-chip"><i class="fas fa-exclamation-triangle"></i> Errors: <strong>${summary.errors}</strong></span>`);
        }
        if (summary.pending > 0 && !progress.running) {
            chips.push(`<span class="summary-chip neutral"><i class="fas fa-hourglass-half"></i> Not analyzed: <strong>${summary.pending}</strong></span>`);
        }

        container.innerHTML = `
            <span class="summary-label"><i class="fas fa-microscope"></i> Content analysis (Top ${this.urlContentData.top_limit || 30}):</span>
            ${chips.join('')}
        `;
    }

});
