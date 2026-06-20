/**
 * LLM Monitoring - métodos de prototipo: urls
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

handleInvitationFeedbackFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const invitationStatus = params.get('invitation');
        const invitationError = params.get('invitation_error');
        const projectName = params.get('project_name');

        if (invitationStatus === 'accepted') {
            const displayName = projectName || 'project';
            this.showSuccess(`Invitation accepted. You now have access to "${displayName}".`);
        } else if (invitationError) {
            const errorMap = {
                missing_token: 'Invitation link is missing a token.',
                'Invitation not found': 'Invitation link is invalid or no longer available.',
                'Invitation has expired': 'Invitation has expired. Ask the owner to send a new one.',
                'Invitation is revoked': 'Invitation was revoked by the project owner.',
                'Invitation is accepted': 'This invitation was already accepted.',
                'Invitation email does not match your current account': 'This invitation was sent to a different email address.'
            };
            this.showError(errorMap[invitationError] || invitationError);
        }

        if (invitationStatus || invitationError || params.has('project_id') || params.has('project_name')) {
            params.delete('invitation');
            params.delete('invitation_error');
            params.delete('project_id');
            params.delete('project_name');
            const nextQuery = params.toString();
            const nextUrl = nextQuery ? `${window.location.pathname}?${nextQuery}` : window.location.pathname;
            window.history.replaceState({}, '', nextUrl);
        }
    },

toNavigableUrl(rawUrl) {
        const value = String(rawUrl || '').trim();
        if (!value) return '#';
        if (/^https?:\/\//i.test(value)) return value;
        return `https://${value}`;
    },

isUrlFromBrand(url) {
        if (!url || !this.currentProject) return false;

        const brandDomain = this.normalizeDomainInput(this.currentProject.brand_domain);
        const urlDomain = this.extractNormalizedHost(url);

        return Boolean(
            brandDomain &&
            urlDomain &&
            (urlDomain === brandDomain || urlDomain.endsWith(`.${brandDomain}`))
        );
    },

isUrlFromCompetitor(url) {
        if (!this.currentProject?.selected_competitors || !url) return false;

        const urlDomain = this.extractNormalizedHost(url);
        if (!urlDomain) return false;

        return this.currentProject.selected_competitors.some(comp => {
            const compRaw = typeof comp === 'object'
                ? (comp.domain || comp.competitor_domain || '')
                : String(comp || '');
            const compDomain = this.normalizeDomainInput(compRaw);
            if (!compDomain) return false;
            return urlDomain === compDomain || urlDomain.endsWith(`.${compDomain}`);
        });
    },

async loadTopUrlsRanking(projectId) {
        console.log(`🔗 Loading top URLs ranking for project ${projectId}...`);

        const enabledLlms = this.getProjectEnabledLlms();
        const llmFilterSelect = document.getElementById('urlsLLMFilter');
        let llmFilter = llmFilterSelect?.value || '';
        if (llmFilter && !enabledLlms.includes(llmFilter)) {
            llmFilter = '';
            if (llmFilterSelect) llmFilterSelect.value = '';
        }
        const days = this.globalTimeRange; // ✨ Use global time range

        try {
            const params = new URLSearchParams({ days });
            if (llmFilter) params.append('llm_provider', llmFilter);
            if (!llmFilter) {
                // In "All LLMs (Combined)" we need the full union of URLs, not a top-N subset.
                params.append('limit', '0');
            }

            const response = await fetch(`${this.baseUrl}/projects/${projectId}/urls-ranking?${params}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            const loadedUrls = Array.isArray(data.urls) ? data.urls : [];
            console.log(`✅ Loaded ${loadedUrls.length} URLs`);

            // Store for filtering
            this.allLLMUrls = loadedUrls;

            // Reset to empty state when API returns no URLs and keep paginator in sync.
            if (loadedUrls.length === 0) {
                this._topUrlsLLMState = { page: 1, totalPages: 1, fullList: [], isDomainView: false };
                this.showNoUrlsLLMMessage();
                this.renderTopUrlsLLMPaginator();
                return;
            }

            // Apply brand filter if active
            const filterBtn = document.getElementById('filterMyBrandUrlsLLM');
            const showOnlyMyBrand = filterBtn?.dataset.active === 'true';

            if (showOnlyMyBrand) {
                this.filterLLMUrlsByBrand(true);
            } else {
                // Apply pagination for all URLs
                const pageSize = 10;
                const state = this._topUrlsLLMState || { page: 1 };
                const totalPages = Math.max(1, Math.ceil(loadedUrls.length / pageSize));
                state.page = Math.min(state.page, totalPages);
                const start = (state.page - 1) * pageSize;
                const paged = loadedUrls.slice(start, start + pageSize);

                this._topUrlsLLMState = { page: state.page, totalPages, fullList: loadedUrls, isDomainView: false };

                // Ensure we're in URLs view (not domains)
                this.updateTableHeaderForUrls();

                this.renderTopUrlsRankingLLM(paged);
                this.renderTopUrlsLLMPaginator();
            }

        } catch (error) {
            console.error('❌ Error loading URLs ranking:', error);
            this._topUrlsLLMState = { page: 1, totalPages: 1, fullList: [], isDomainView: false };
            this.showNoUrlsLLMMessage();
            this.renderTopUrlsLLMPaginator();
        }
    },

filterLLMUrlsByBrand(showOnlyMyBrand) {
        if (!this.allLLMUrls || this.allLLMUrls.length === 0) {
            console.warn('⚠️ No URLs data available for filtering');
            this._topUrlsLLMState = { page: 1, totalPages: 1, fullList: [], isDomainView: false };
            this.showNoUrlsLLMMessage();
            this.renderTopUrlsLLMPaginator();
            return;
        }

        let filtered = this.allLLMUrls;

        if (showOnlyMyBrand && this.currentProject) {
            const projectDomain = this.normalizeDomainInput(this.currentProject.brand_domain);
            const hasBrandFilters = Boolean(projectDomain);

            if (hasBrandFilters) {
                filtered = this.allLLMUrls.filter(urlData => this.isUrlFromBrand(urlData.url));

                console.log(`🔍 Filtered: ${filtered.length} URLs from ${this.allLLMUrls.length} total`);
            }

            // If no URLs match, show message
            if (filtered.length === 0) {
                console.warn('⚠️ No URLs found for your brand');
                this._topUrlsLLMState = { page: 1, totalPages: 1, fullList: [], isDomainView: false };
                this.updateTableHeaderForUrls();
                this.showNoUrlsLLMMessage({
                    title: 'No Brand URLs in This Range',
                    description: 'No cited URLs match your brand domain with current filters.',
                    helper: 'Disable "My Brand URLs Only" to view all cited URLs.'
                });
                this.renderTopUrlsLLMPaginator();
                return;
            }

            // Recalculate ranks after filtering
            filtered = filtered.map((url, index) => ({
                ...url,
                rank: index + 1
            }));
        }

        // Apply pagination (preserve current page when navigating with filter active)
        const pageSize = 10;
        const currentPage = this._topUrlsLLMState?.page || 1;
        const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
        const page = Math.min(currentPage, totalPages);
        const start = (page - 1) * pageSize;
        const paged = filtered.slice(start, start + pageSize);

        this._topUrlsLLMState = { page, totalPages, fullList: filtered, isDomainView: false };

        // Make sure we're in URLs view, not domains view
        this.updateTableHeaderForUrls();

        this.renderTopUrlsRankingLLM(paged);
        this.renderTopUrlsLLMPaginator();
    },

renderTopUrlsRankingLLM(urls) {
        const tableBody = document.getElementById('topUrlsLLMBody');
        const noUrlsMessage = document.getElementById('noUrlsLLMMessage');
        const topUrlsTable = document.getElementById('topUrlsLLMTable');

        if (!urls || urls.length === 0) {
            this.showNoUrlsLLMMessage();
            return;
        }

        // Show table, hide message
        noUrlsMessage.style.display = 'none';
        topUrlsTable.style.display = 'table';

        // Clear existing rows
        tableBody.innerHTML = '';

        // Get project info for highlighting
        let projectDomain = '';
        let competitorDomains = [];

        if (this.currentProject) {
            projectDomain = this.normalizeDomainInput(this.currentProject.brand_domain);

            // Normalize competitor domains
            const competitors = this.currentProject.selected_competitors || [];
            competitorDomains = competitors.map(c => {
                const domain = typeof c === 'object' ? (c.domain || c.competitor_domain || c) : c;
                return this.normalizeDomainInput(domain);
            }).filter(d => d && d.length > 0);

            console.log('🎯 URL Highlighting Config (LLM Monitoring):', {
                projectDomain,
                competitorDomains,
                totalUrls: urls.length
            });
        }

        // Render rows
        urls.forEach((urlData, index) => {
            const url = urlData.url;

            // Extract domain from URL
            let urlDomain = '';
            let domainType = 'other';
            urlDomain = this.extractNormalizedHost(url);

            // Check if it's project or competitor domain
            if (projectDomain && (urlDomain === projectDomain || urlDomain.endsWith('.' + projectDomain))) {
                domainType = 'project';
            } else if (competitorDomains.some(comp => urlDomain === comp || urlDomain.endsWith('.' + comp))) {
                domainType = 'competitor';
            }

            if (index < 5) { // Log first 5 for debugging
                console.log(`  URL ${index + 1}: ${urlDomain || 'invalid'} → ${domainType}`);
            }

            // Use 'table' prefix for project domain to avoid conflicts with other CSS
            const domainTypeClass = domainType === 'project' ? 'table' : domainType;
            const rowClass = `url-row ${domainTypeClass}-domain`;
            const safeUrl = this.toNavigableUrl(url);

            // Create domain badge if needed
            let domainBadge = '';
            if (domainType === 'project') {
                domainBadge = '<span class="domain-badge project">Your Domain</span>';
            } else if (domainType === 'competitor') {
                domainBadge = '<span class="domain-badge competitor">Competitor</span>';
            }

            const row = document.createElement('tr');
            row.className = rowClass;
            row.innerHTML = `
                <td class="rank-cell">${urlData.rank}</td>
                <td class="url-cell">
                    <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        <a href="${this.escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer"
                           class="url-link" title="${this.escapeHtml(url)}">
                            ${this.truncateUrl(url, 80)}
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                        ${domainBadge}
                    </div>
                </td>
                <td class="mentions-cell">${urlData.mentions}</td>
                <td class="percentage-cell">${urlData.percentage.toFixed(1)}%</td>
            `;

            tableBody.appendChild(row);
        });

        console.log(`✅ Rendered ${urls.length} URL rows with highlighting`);
    },

showNoUrlsLLMMessage(customCopy = {}) {
        const tableBody = document.getElementById('topUrlsLLMBody');
        const noUrlsMessage = document.getElementById('noUrlsLLMMessage');
        const topUrlsTable = document.getElementById('topUrlsLLMTable');
        const paginator = document.getElementById('topUrlsLLMPaginator');

        const titleEl = noUrlsMessage?.querySelector('h4');
        const descriptionEl = noUrlsMessage?.querySelector('p');
        const helperEl = noUrlsMessage?.querySelector('small');
        if (titleEl) {
            titleEl.textContent = customCopy.title || 'No URL Data Available';
        }
        if (descriptionEl) {
            descriptionEl.textContent = customCopy.description || 'LLMs haven\'t cited any URLs yet in their responses';
        }
        if (helperEl) {
            helperEl.textContent = customCopy.helper || 'This is normal if analysis just started or LLMs don\'t include sources';
        }

        if (tableBody) tableBody.innerHTML = '';
        if (topUrlsTable) topUrlsTable.style.display = 'none';
        if (noUrlsMessage) noUrlsMessage.style.display = 'flex';
        if (paginator) paginator.style.display = 'none';
    },

aggregateUrlsByDomain(urlsData) {
        const domainStats = {};

        urlsData.forEach(urlData => {
            const domain = this.extractNormalizedHost(urlData.url);
            if (!domain) {
                console.warn('Invalid URL:', urlData.url);
                return;
            }

            if (!domainStats[domain]) {
                domainStats[domain] = {
                    domain: domain,
                    urlCount: 0,
                    totalMentions: 0,
                    urls: []
                };
            }

            domainStats[domain].urlCount++;
            domainStats[domain].totalMentions += urlData.mentions || 0;
            domainStats[domain].urls.push(urlData.url);
        });

        // Convert to array and calculate percentages
        const totalMentions = Object.values(domainStats).reduce((sum, d) => sum + d.totalMentions, 0);

        const domainsArray = Object.values(domainStats).map(domainData => ({
            ...domainData,
            percentage: totalMentions > 0 ? (domainData.totalMentions / totalMentions * 100) : 0
        }));

        // Sort by total mentions (descending)
        domainsArray.sort((a, b) => b.totalMentions - a.totalMentions);

        // Add ranking
        domainsArray.forEach((domain, index) => {
            domain.rank = index + 1;
        });

        console.log(`✅ Aggregated ${domainsArray.length} unique domains from ${urlsData.length} URLs`);

        return domainsArray;
    },

updateTableHeaderForUrls() {
        const thead = document.querySelector('#topUrlsLLMTable thead');
        if (!thead) return;

        thead.innerHTML = `
            <tr>
                <th style="width: 60px;">#</th>
                <th style="width: 60%;">URL</th>
                <th style="width: 120px;">Mentions</th>
                <th style="width: 120px;">% of Total</th>
            </tr>
        `;
    },

renderTopUrlsLLMPaginator() {
        const container = document.getElementById('topUrlsLLMTable')?.parentElement || document.getElementById('noUrlsLLMMessage')?.parentElement;
        if (!container || !this._topUrlsLLMState) return;

        let paginator = document.getElementById('topUrlsLLMPaginator');
        if (!paginator) {
            paginator = document.createElement('div');
            paginator.id = 'topUrlsLLMPaginator';
            paginator.style.cssText = 'display:flex;justify-content:flex-end;gap:8px;margin:24px 0;align-items:center;';
            container.appendChild(paginator);
        }

        const { page, totalPages, fullList } = this._topUrlsLLMState;

        if (!Array.isArray(fullList) || fullList.length === 0) {
            paginator.style.display = 'none';
            return;
        }
        paginator.style.display = 'flex';
        paginator.innerHTML = '';

        // Previous button
        const btnPrev = document.createElement('button');
        btnPrev.className = 'btn btn-light btn-sm';
        btnPrev.style.backgroundColor = '#C3F5A4';
        btnPrev.style.borderColor = '#C3F5A4';
        btnPrev.style.color = '#111827';
        btnPrev.innerHTML = '<i class="fas fa-chevron-left"></i> Previous';
        btnPrev.disabled = page <= 1;
        btnPrev.onclick = () => {
            this._topUrlsLLMState.page = Math.max(1, page - 1);

            // Check if domain view is active
            const isDomainView = this._topUrlsLLMState.isDomainView;

            // Check if brand filter is active
            const filterBtn = document.getElementById('filterMyBrandUrlsLLM');
            const isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';

            if (isFilterActive) {
                this.filterLLMUrlsByBrand(true);
            } else {
                const pageSize = 10;
                const start = (this._topUrlsLLMState.page - 1) * pageSize;
                const paged = fullList.slice(start, start + pageSize);

                if (isDomainView) {
                    this.renderTopDomainsRankingLLM(paged);
                } else {
                    this.renderTopUrlsRankingLLM(paged);
                }
                this.renderTopUrlsLLMPaginator();
            }
        };

        // Page info
        const info = document.createElement('span');
        info.style.cssText = 'display:flex;align-items:center;font-size:13px;color:#6b7280;font-weight:500;';
        info.textContent = `Page ${page} of ${totalPages}`;

        // Next button
        const btnNext = document.createElement('button');
        btnNext.className = 'btn btn-light btn-sm';
        btnNext.style.backgroundColor = '#C3F5A4';
        btnNext.style.borderColor = '#C3F5A4';
        btnNext.style.color = '#111827';
        btnNext.innerHTML = 'Next <i class="fas fa-chevron-right"></i>';
        btnNext.disabled = page >= totalPages;
        btnNext.onclick = () => {
            this._topUrlsLLMState.page = Math.min(totalPages, page + 1);

            // Check if domain view is active
            const isDomainView = this._topUrlsLLMState.isDomainView;

            // Check if brand filter is active
            const filterBtn = document.getElementById('filterMyBrandUrlsLLM');
            const isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';

            if (isFilterActive) {
                this.filterLLMUrlsByBrand(true);
            } else {
                const pageSize = 10;
                const start = (this._topUrlsLLMState.page - 1) * pageSize;
                const paged = fullList.slice(start, start + pageSize);

                if (isDomainView) {
                    this.renderTopDomainsRankingLLM(paged);
                } else {
                    this.renderTopUrlsRankingLLM(paged);
                }
                this.renderTopUrlsLLMPaginator();
            }
        };

        // Append buttons
        paginator.appendChild(btnPrev);
        paginator.appendChild(info);
        paginator.appendChild(btnNext);

        console.log(`📄 Rendered paginator: Page ${page}/${totalPages}`);
    },

truncateUrl(url, maxLength) {
        if (url.length <= maxLength) return this.escapeHtml(url);

        try {
            const urlObj = new URL(url);
            const domain = urlObj.hostname.replace('www.', '');
            const path = urlObj.pathname + urlObj.search;

            if (path.length > maxLength - domain.length - 3) {
                return this.escapeHtml(domain + path.substring(0, maxLength - domain.length - 6) + '...');
            }

            return this.escapeHtml(domain + path);
        } catch {
            return this.escapeHtml(url.substring(0, maxLength - 3) + '...');
        }
    }

});
