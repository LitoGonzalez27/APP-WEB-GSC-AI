/**
 * Manual AI System - Analytics Module
 * Gestión completa de analytics (stats, rankings, tablas)
 */

import { escapeHtml, getDomainLogoUrl, htmlLegendPlugin } from './manual-ai-utils.js';

// ================================
// ANALYTICS LOADING & RENDERING
// ================================

export function populateAnalyticsProjectSelect() {
    if (!this.elements.analyticsProjectSelect) return;

    this.elements.analyticsProjectSelect.innerHTML = `
        <option value="">Select a project...</option>
        ${this.projects.map(project => `
            <option value="${project.id}">${escapeHtml(project.name)}</option>
        `).join('')}
    `;
}

export async function loadAnalytics() {
    const projectId = this.elements.analyticsProjectSelect?.value;
    const days = this.elements.analyticsTimeRange?.value || 30;

    if (!projectId) {
        this.elements.analyticsContent.innerHTML = `
            <div class="analytics-empty">
                <i class="fas fa-chart-line"></i>
                <p>Select a project to view analytics</p>
            </div>
        `;
        this.hideElement(this.elements.chartsContainer);
        this.showDownloadButton(false); // Hide download button when no project selected
        return;
    }

    this.elements.analyticsContent.innerHTML = `
        <div class="loading-analytics">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Loading analytics data...</p>
        </div>
    `;

    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/stats?days=${days}`);
        const data = await response.json();

        if (data.success) {
            this.renderAnalytics(data.stats);
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
        this.elements.analyticsContent.innerHTML = `
            <div class="analytics-error">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load analytics data</p>
            </div>
        `;
        this.showDownloadButton(false); // Hide download button on error
    }
}

export function renderAnalytics(stats) {
    console.log('📊 Rendering analytics data:', stats);
    
    // Update summary cards — ahora desde endpoint "latest" (ignora rango)
    const projectIdForLatest = stats.project_id || parseInt(this.elements.analyticsProjectSelect?.value) || this.currentProject?.id;
    if (projectIdForLatest) {
        const latestToken = Date.now();
        this._latestOverviewToken = latestToken;
        fetch(`/manual-ai/api/projects/${projectIdForLatest}/stats-latest`)
            .then(r => r.json())
            .then(latest => {
                if (this._latestOverviewToken !== latestToken) return; // evitar pisado por race
                const ms = latest?.main_stats || {};
                const totalKeywords = Number(ms.total_keywords) || 0;
                const totalAi = Number(ms.total_ai_keywords) || 0;
                const totalMentions = Number(ms.total_mentions) || 0;
                const avgPos = (ms.avg_position !== null && ms.avg_position !== undefined) ? Number(ms.avg_position) : null;
                const aioWeightPct = (ms.aio_weight_percentage !== null && ms.aio_weight_percentage !== undefined) ? Number(ms.aio_weight_percentage) : null;
                const visPctRaw = (ms.visibility_percentage !== null && ms.visibility_percentage !== undefined) ? Number(ms.visibility_percentage) : null;
                
                this.updateSummaryCard('totalKeywords', totalKeywords);
                this.updateSummaryCard('aiKeywords', totalAi);
                this.updateSummaryCard('domainMentions', totalMentions);
                // Mostrar visibilidad con base en último análisis si viene calculada
                const visPct = (typeof ms.visibility_percentage === 'number') ? ms.visibility_percentage : ms.aio_weight_percentage;
                this.updateSummaryCard('visibilityPercentage', typeof visPct === 'number' ? Math.round(visPct) + '%' : '0%');
                this.updateSummaryCard('averagePosition',
                    typeof ms.avg_position === 'number' ? Math.round(ms.avg_position * 10) / 10 : '-');
                this.updateSummaryCard('aioWeight',
                    typeof ms.aio_weight_percentage === 'number' ? Math.round(ms.aio_weight_percentage) + '%' : '0%');

                // Badge "Latest analysis"
                const header = document.querySelector('.overview-section .section-header p.section-description');
                if (header) {
                    const dt = ms.last_analysis_date ? new Date(ms.last_analysis_date).toLocaleDateString() : '';
                    header.textContent = `Data from the latest analysis${dt ? ' (' + dt + ')' : ''}`;
                }
            })
            .catch(() => {/* silencioso */});
    }

    // Show charts container
    this.hideElement(this.elements.analyticsContent);
    this.showElement(this.elements.chartsContainer);

    // Get project ID from stats or current selection
    const projectId = stats.project_id || parseInt(this.elements.analyticsProjectSelect?.value) || this.currentProject?.id;
    if (!projectId) {
        console.warn('No project ID available for analytics rendering');
        return;
    }

    console.log(`📈 Loading analytics components for project ${projectId}`);

    // Store current analytics data for Excel export
    this.currentAnalyticsData = {
        projectId: projectId,
        stats: stats,
        days: this.elements.analyticsTimeRange?.value || 30
    };

    // Show download button when analytics data is loaded
    this.showDownloadButton(true);

    // Render main charts with events annotations
    if (stats.visibility_chart && Array.isArray(stats.visibility_chart)) {
        this.renderVisibilityChart(stats.visibility_chart, stats.events || []);
    } else {
        console.warn('No visibility chart data available');
    }

    if (stats.positions_chart && Array.isArray(stats.positions_chart)) {
        this.renderPositionsChart(stats.positions_chart, stats.events || []);
    } else {
        console.warn('No positions chart data available');
    }

    // Load all competitive analysis components in parallel
    this.loadAnalyticsComponents(projectId);
}

export function updateSummaryCard(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    } else {
        console.warn(`Summary card element not found: ${elementId}`);
    }
}

export async function loadAnalyticsComponents(projectId) {
    console.log(`🔄 Loading analytics components for project ${projectId}`);
    
    try {
        // Load all components in parallel for better performance
        const promises = [
            this.loadGlobalDomainsRanking(projectId),
            this.loadTopUrlsRanking(projectId),
            this.loadComparativeCharts(projectId),
            this.loadCompetitorsPreview(projectId),
            this.loadAIOverviewKeywordsTable(projectId),
            this.loadClustersStatistics(projectId)  // ✨ NEW: Clusters statistics
        ];

        await Promise.allSettled(promises);
        console.log('✅ All analytics components loaded (including clusters)');

    } catch (error) {
        console.error('Error loading analytics components:', error);
    }
}

// ================================
// TOP DOMAINS
// ================================

export async function loadTopDomains(projectId) {
    if (!projectId) {
        this.showNoDomainsMessage();
        return;
    }

    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/top-domains`);
        
        if (!response.ok) {
            if (response.status === 404) {
                this.showNoDomainsMessage();
                return;
            }
            throw new Error('Failed to load top domains data');
        }

        const data = await response.json();
        this.renderTopDomains(data.domains || []);

    } catch (error) {
        console.error('Error loading top domains:', error);
        this.showNoDomainsMessage();
    }
}

export function renderTopDomains(domains) {
    const tableBody = document.getElementById('topDomainsBody');
    const noDomainsMessage = document.getElementById('noDomainsMessage');
    const topDomainsTable = document.getElementById('topDomainsTable');

    if (!domains || domains.length === 0) {
        this.showNoDomainsMessage();
        return;
    }

    // Hide no domains message and show table
    noDomainsMessage.style.display = 'none';
    topDomainsTable.style.display = 'table';

    // Clear existing rows
    tableBody.innerHTML = '';

    // Render each domain row
    domains.forEach((domain, index) => {
        const row = document.createElement('tr');
        
        // Calculate visibility score (appearances weighted by position)
        const visibilityScore = this.calculateVisibilityScore(domain.appearances, domain.avg_position);
        const scoreClass = this.getScoreClass(visibilityScore);
        
        // Get logo URL for domain
        const logoUrl = getDomainLogoUrl(domain.domain);
        
        row.innerHTML = `
            <td class="rank-cell">${index + 1}</td>
            <td class="domain-cell" title="${domain.domain}">
                <div class="domain-cell-content">
                    <img src="${logoUrl}" alt="${domain.domain} logo" class="domain-logo" 
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22><circle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23e5e7eb%22/><text x=%2212%22 y=%2216%22 text-anchor=%22middle%22 font-size=%2210%22 fill=%22%23374151%22>${domain.domain.charAt(0).toUpperCase()}</text></svg>'">
                    <span class="domain-name">${domain.domain}</span>
                </div>
            </td>
            <td class="appearances-cell">${domain.appearances}</td>
            <td class="position-cell">${domain.avg_position ? domain.avg_position.toFixed(1) : '-'}</td>
            <td class="score-cell ${scoreClass}">${visibilityScore.toFixed(1)}</td>
        `;
        
        tableBody.appendChild(row);
    });
}

export function calculateVisibilityScore(appearances, avgPosition) {
    if (!appearances || !avgPosition) return 0;
    
    // Score = appearances × (weight based on position)
    // Better positions (lower numbers) get higher weights
    const positionWeight = Math.max(0, (21 - avgPosition) / 20);
    return appearances * positionWeight * 10; // Scale to 0-100 range
}

export function getScoreClass(score) {
    if (score >= 80) return 'score-excellent';
    if (score >= 60) return 'score-good';
    if (score >= 30) return 'score-average';
    return 'score-poor';
}

export function showNoDomainsMessage() {
    const tableBody = document.getElementById('topDomainsBody');
    const noDomainsMessage = document.getElementById('noDomainsMessage');
    const topDomainsTable = document.getElementById('topDomainsTable');

    if (tableBody) tableBody.innerHTML = '';
    if (topDomainsTable) topDomainsTable.style.display = 'none';
    if (noDomainsMessage) noDomainsMessage.style.display = 'block';
}

// ================================
// GLOBAL DOMAINS RANKING
// ================================

export async function loadGlobalDomainsRanking(projectId) {
    if (!projectId) {
        this.showNoGlobalDomainsMessage();
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/global-domains-ranking?days=${days}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                this.showNoGlobalDomainsMessage();
                return;
            }
            throw new Error('Failed to load global domains ranking');
        }

        const data = await response.json();
        this.renderGlobalDomainsRanking(data.domains || []);

    } catch (error) {
        console.error('Error loading global domains ranking:', error);
        this.showNoGlobalDomainsMessage();
    }
}

export function renderGlobalDomainsRanking(domains) {
    const tableBody = document.getElementById('globalDomainsBody');
    const noDomainsMessage = document.getElementById('noGlobalDomainsMessage');
    const globalDomainsTable = document.getElementById('globalDomainsTable');

    if (!domains || domains.length === 0) {
        this.showNoGlobalDomainsMessage();
        return;
    }

    // Hide no domains message and show table
    noDomainsMessage.style.display = 'none';
    globalDomainsTable.style.display = 'table';

    // Clear existing rows
    tableBody.innerHTML = '';

    // Render each domain row with highlighting
    domains.forEach((domain, index) => {
        const row = document.createElement('tr');
        // Use 'table' prefix for project domain to avoid conflicts with other CSS
        const domainTypeClass = domain.domain_type === 'project' ? 'table' : domain.domain_type;
        row.className = `domain-row ${domainTypeClass}-domain`;
        
        // Get logo URL
        const logoUrl = getDomainLogoUrl(domain.detected_domain);
        
        // Create domain badge if needed
        let domainBadge = '';
        if (domain.domain_type === 'project') {
            domainBadge = '<span class="domain-badge project">Your Domain</span>';
        } else if (domain.domain_type === 'competitor') {
            domainBadge = '<span class="domain-badge competitor">Competitor</span>';
        }
        
        row.innerHTML = `
            <td class="rank-cell">${domain.rank}</td>
            <td class="domain-cell">
                <div class="global-domain-cell">
                    <img src="${logoUrl}" alt="${domain.detected_domain} logo" class="domain-logo" 
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22><circle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23e5e7eb%22/><text x=%2212%22 y=%2216%22 text-anchor=%22middle%22 font-size=%2210%22 fill=%22%23374151%22>${domain.detected_domain.charAt(0).toUpperCase()}</text></svg>'">
                    <div class="global-domain-info">
                        <div class="global-domain-label">
                            <span class="global-domain-name">${domain.detected_domain}</span>
                            ${domainBadge}
                        </div>
                    </div>
                </div>
            </td>
            <td class="appearances-cell">${domain.appearances || 0}</td>
            <td class="position-cell">${domain.avg_position && typeof domain.avg_position === 'number' ? domain.avg_position.toFixed(1) : '-'}</td>
            <td class="visibility-cell">${domain.visibility_percentage && typeof domain.visibility_percentage === 'number' ? domain.visibility_percentage.toFixed(1) : '0.0'}%</td>
        `;
        
        tableBody.appendChild(row);
    });
}

export function showNoGlobalDomainsMessage() {
    const tableBody = document.getElementById('globalDomainsBody');
    const noDomainsMessage = document.getElementById('noGlobalDomainsMessage');
    const globalDomainsTable = document.getElementById('globalDomainsTable');

    if (tableBody) tableBody.innerHTML = '';
    if (globalDomainsTable) globalDomainsTable.style.display = 'none';
    if (noDomainsMessage) noDomainsMessage.style.display = 'block';
}

// ================================
// TOP URLS RANKING
// ================================

export async function loadTopUrlsRanking(projectId) {
    if (!projectId) {
        this.showNoUrlsMessage();
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/urls-ranking?days=${days}&limit=20`);
        
        if (!response.ok) {
            if (response.status === 404) {
                this.showNoUrlsMessage();
                return;
            }
            throw new Error('Failed to load URLs ranking');
        }

        const data = await response.json();
        
        // Store all URLs for filtering
        this._allUrlsData = data.urls || [];
        
        console.log('📥 Loaded URLs data:', this._allUrlsData.length);
        
        // Initialize filter chip event listener (only once)
        try {
            this.initUrlsFilter();
        } catch (e) {
            console.error('Error initializing filter:', e);
        }
        
        // Check if filter is currently active
        let isFilterActive = false;
        try {
            const filterBtn = document.getElementById('filterMyDomainUrls');
            isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';
        } catch (e) {
            console.error('Error checking filter state:', e);
        }
        
        // Apply filter if active, otherwise show all
        if (isFilterActive) {
            console.log('🔵 Filter is active, applying filter...');
            try {
                this.filterUrlsByDomain(true);
            } catch (e) {
                console.error('Error applying filter, showing all URLs:', e);
                this.renderTopUrlsRanking(this._allUrlsData);
            }
        } else {
            console.log('⚪ Filter is inactive, showing all URLs');
            this.renderTopUrlsRanking(this._allUrlsData);
        }

    } catch (error) {
        console.error('Error loading URLs ranking:', error);
        this.showNoUrlsMessage();
    }
}

export function initUrlsFilter() {
    const filterBtn = document.getElementById('filterMyDomainUrls');
    if (!filterBtn || filterBtn._listenerAttached) return;
    
    filterBtn._listenerAttached = true;
    filterBtn.addEventListener('click', () => {
        const isActive = filterBtn.getAttribute('data-active') === 'true';
        filterBtn.setAttribute('data-active', !isActive);
        
        // Apply filter
        this.filterUrlsByDomain(!isActive);
    });
}

export function filterUrlsByDomain(showOnlyMyDomain) {
    if (!this._allUrlsData || this._allUrlsData.length === 0) {
        console.warn('⚠️ No URLs data available for filtering');
        this.showNoUrlsMessage();
        return;
    }
    
    let filteredUrls = this._allUrlsData;
    
    if (showOnlyMyDomain) {
        try {
            // Get current project from analytics dropdown or currentProject
            const projectSelect = document.getElementById('analyticsProjectSelect');
            const currentProjectId = projectSelect ? parseInt(projectSelect.value) : null;
            const project = this.projects?.find(p => p.id === currentProjectId) || this.currentProject;
            
            if (!project || !project.domain) {
                console.error('❌ No project or domain found for filtering, showing all URLs');
                this.renderTopUrlsRanking(this._allUrlsData);
                return;
            }
            
            // Get project domain and normalize
            const projectDomain = project.domain.toLowerCase().replace(/^www\./, '');
            console.log('🔍 Filtering URLs for domain:', projectDomain);
            
            // Filter URLs that belong to the project domain
            filteredUrls = this._allUrlsData.filter(urlData => {
                try {
                    const url = new URL(urlData.url);
                    const urlDomain = url.hostname.toLowerCase().replace(/^www\./, '');
                    const matches = urlDomain === projectDomain;
                    
                    if (matches) {
                        console.log('✅ Match:', urlData.url);
                    }
                    
                    return matches;
                } catch (e) {
                    console.error('Error parsing URL:', urlData.url, e);
                    return false;
                }
            });
            
            console.log(`📊 Filtered: ${filteredUrls.length} URLs from ${this._allUrlsData.length} total`);
            
            // If no URLs match, show message
            if (filteredUrls.length === 0) {
                console.warn('⚠️ No URLs found for your domain');
                // Still show the table structure but empty
            }
            
            // Recalculate ranks
            filteredUrls = filteredUrls.map((url, index) => ({
                ...url,
                rank: index + 1
            }));
        } catch (e) {
            console.error('❌ Error in filterUrlsByDomain:', e);
            filteredUrls = this._allUrlsData;
        }
    }
    
    // Always render something
    this.renderTopUrlsRanking(filteredUrls);
}

export function renderTopUrlsRanking(urls) {
    const tableBody = document.getElementById('topUrlsBody');
    const noUrlsMessage = document.getElementById('noUrlsMessage');
    const topUrlsTable = document.getElementById('topUrlsTable');

    if (!urls || urls.length === 0) {
        this.showNoUrlsMessage();
        return;
    }

    // Hide no URLs message and show table
    noUrlsMessage.style.display = 'none';
    topUrlsTable.style.display = 'table';

    // Clear existing rows
    tableBody.innerHTML = '';
    
    // Get current project info for domain highlighting
    const projectSelect = document.getElementById('analyticsProjectSelect');
    const currentProjectId = projectSelect ? parseInt(projectSelect.value) : null;
    const currentProject = this.projects?.find(p => p.id === currentProjectId) || this.currentProject;
    
    // Normalize project domain
    let projectDomain = '';
    let competitorDomains = [];
    
    if (currentProject) {
        projectDomain = (currentProject.domain || '').toLowerCase().replace(/^www\./, '').trim();
        competitorDomains = (currentProject.competitors || []).map(c => 
            c.toLowerCase().replace(/^www\./, '').trim()
        );
    }

    // Render each URL row with highlighting
    urls.forEach((urlData, index) => {
        const row = document.createElement('tr');
        
        // Extract domain from URL
        let urlDomain = '';
        let domainType = 'other';
        try {
            const urlObj = new URL(urlData.url);
            urlDomain = urlObj.hostname.toLowerCase().replace(/^www\./, '');
            
            // Check if it's project or competitor domain
            if (projectDomain && urlDomain.includes(projectDomain)) {
                domainType = 'project';
            } else if (competitorDomains.some(comp => urlDomain.includes(comp))) {
                domainType = 'competitor';
            }
        } catch (e) {
            // Invalid URL, keep as 'other'
        }
        
        // Use 'table' prefix for project domain to avoid conflicts with other CSS
        const domainTypeClass = domainType === 'project' ? 'table' : domainType;
        row.className = `url-row ${domainTypeClass}-domain`;
        
        // Get logo URL
        const logoUrl = getDomainLogoUrl(urlDomain || 'unknown');
        
        // Create domain badge if needed
        let domainBadge = '';
        if (domainType === 'project') {
            domainBadge = '<span class="domain-badge project">Your Domain</span>';
        } else if (domainType === 'competitor') {
            domainBadge = '<span class="domain-badge competitor">Competitor</span>';
        }
        
        // Truncate URL for display if too long
        const displayUrl = urlData.url.length > 70 
            ? urlData.url.substring(0, 67) + '...' 
            : urlData.url;
        
        row.innerHTML = `
            <td class="rank-cell">${urlData.rank}</td>
            <td class="url-cell">
                <div class="global-domain-cell">
                    <img src="${logoUrl}" alt="${urlDomain} logo" class="domain-logo" 
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22><circle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22%23e5e7eb%22/><text x=%2212%22 y=%2216%22 text-anchor=%22middle%22 font-size=%2210%22 fill=%22%23374151%22>${urlDomain.charAt(0).toUpperCase()}</text></svg>'">
                    <div class="global-domain-info">
                        <div class="global-domain-label">
                            <a href="${urlData.url}" target="_blank" rel="noopener noreferrer" title="${urlData.url}" class="url-link">
                                ${displayUrl}
                                <i class="fas fa-external-link-alt"></i>
                            </a>
                            ${domainBadge}
                        </div>
                    </div>
                </div>
            </td>
            <td class="mentions-cell">${urlData.mentions || 0}</td>
            <td class="position-cell">${urlData.avg_position ? urlData.avg_position.toFixed(1) : '-'}</td>
            <td class="percentage-cell">${urlData.percentage ? urlData.percentage.toFixed(2) : '0.00'}%</td>
        `;
        
        tableBody.appendChild(row);
    });
}

export function showNoUrlsMessage() {
    const tableBody = document.getElementById('topUrlsBody');
    const noUrlsMessage = document.getElementById('noUrlsMessage');
    const topUrlsTable = document.getElementById('topUrlsTable');

    if (tableBody) tableBody.innerHTML = '';
    if (topUrlsTable) topUrlsTable.style.display = 'none';
    if (noUrlsMessage) noUrlsMessage.style.display = 'block';
}

// ================================
// AI OVERVIEW KEYWORDS TABLE
// ================================

export async function loadAIOverviewKeywordsTable(projectId) {
    if (!projectId) {
        this.showNoAIKeywordsMessage();
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    try {
        // Tabla de AI Overview debe quedarse fija al último análisis disponible
        const latestToken = Date.now();
        this._latestAIOTableToken = latestToken;
        const response = await fetch(`/manual-ai/api/projects/${projectId}/ai-overview-table-latest`);
        
        if (!response.ok) {
            if (response.status === 404) {
                this.showNoAIKeywordsMessage();
                return;
            }
            throw new Error('Failed to load AI Overview keywords data');
        }

        const result = await response.json();
        if (this._latestAIOTableToken !== latestToken) return; // evitar pisado por race
        const data = result.data || {};
        
        // Render AI Overview keywords table using Grid.js
        this.renderAIOverviewKeywordsTable(data);

    } catch (error) {
        console.error('Error loading AI Overview keywords table:', error);
        this.showNoAIKeywordsMessage();
    }
}

export function renderAIOverviewKeywordsTable(data) {
    const container = document.getElementById('manualAIOverviewGrid');
    const noKeywordsMessage = document.getElementById('noAIKeywordsMessage');
    
    if (!container) {
        console.error('❌ AI Overview grid container not found');
        return;
    }

    // Clear existing content
    container.innerHTML = '';

    const keywordResults = data.keywordResults || [];
    // Asegurar orden y unicidad de competidores para columnas deterministas
    const competitorDomains = Array.from(new Set((data.competitorDomains || []).map(d => (d || '').toLowerCase()))).sort();

    console.log('🏗️ Rendering AI Overview table with:', {
        keywords: keywordResults.length,
        competitors: competitorDomains.length
    });

    if (keywordResults.length === 0) {
        this.showNoAIKeywordsMessage();
        return;
    }

    // Hide no keywords message
    if (noKeywordsMessage) {
        noKeywordsMessage.style.display = 'none';
    }

    // Check if Grid.js is available
    if (!window.gridjs) {
        console.error('❌ Grid.js library not loaded');
        container.innerHTML = '<p class="error-message">Grid.js library not available</p>';
        return;
    }

    // Rebuild Grid.js table from scratch (destroy previous instances)
    try {
        const { columns, gridData } = this.processAIOverviewDataForGrid(keywordResults, competitorDomains);
        // Hard rebuild: replace container node to avoid stale Grid.js state
        const parent = container.parentNode;
        const fresh = container.cloneNode(false);
        parent.replaceChild(fresh, container);
        
        const grid = new gridjs.Grid({
            columns: columns,
            data: gridData,
            pagination: {
                limit: 10,
                summary: true
            },
            sort: true,
            search: {
                placeholder: 'Type a keyword...'
            },
            resizable: true,
            className: {
                container: 'manual-ai-overview-grid',
                table: 'manual-ai-overview-table',
                search: 'manual-ai-overview-search'
            }
        });

        grid.render(fresh);
        console.log('✅ AI Overview table rendered successfully');

    } catch (error) {
        console.error('❌ Error rendering AI Overview table:', error);
        container.innerHTML = '<p class="error-message">Failed to render table</p>';
    }
}

export function showNoAIKeywordsMessage() {
    const container = document.getElementById('manualAIOverviewGrid');
    const noKeywordsMessage = document.getElementById('noAIKeywordsMessage');
    
    if (container) {
        container.innerHTML = '';
    }
    
    if (noKeywordsMessage) {
        noKeywordsMessage.style.display = 'block';
    }
}

// ================================
// COMPARATIVE CHARTS
// ================================

export async function loadComparativeCharts(projectId) {
    if (!projectId) {
        this.showNoComparativeChartsMessage();
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/comparative-charts?days=${days}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                console.warn('⚠️ Comparative charts endpoint returned 404');
                this.showNoComparativeChartsMessage();
                return;
            }
            throw new Error('Failed to load comparative charts data');
        }

        const result = await response.json();
        console.log('📊 Comparative charts data received:', result);
        const data = result.data || {};
        
        console.log('📈 Visibility chart:', data.visibility_chart);
        console.log('📉 Position chart:', data.position_chart);
        
        // Render both comparative charts
        this.renderComparativeVisibilityChart(data.visibility_chart || {});
        this.renderComparativePositionChart(data.position_chart || {});

    } catch (error) {
        console.error('❌ Error loading comparative charts:', error);
        this.showNoComparativeChartsMessage();
    }
}

export function renderComparativeVisibilityChart(chartData) {
    const ctx = document.getElementById('comparativeVisibilityChart');
    if (!ctx) {
        console.error('❌ comparativeVisibilityChart canvas not found');
        return;
    }

    // Destroy existing chart
    if (this.charts.comparativeVisibility) {
        this.charts.comparativeVisibility.destroy();
    }

    console.log('🔍 Rendering comparative visibility chart with data:', chartData);
    
    if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
        console.warn('⚠️ No datasets for comparative visibility chart');
        this.showNoComparativeChartsMessage();
        return;
    }
    
    console.log(`✅ Rendering comparative visibility chart with ${chartData.datasets.length} datasets`);
    
    // Show canvas and hide any "no data" messages
    ctx.style.display = 'block';
    const noDataMsg = ctx.parentElement?.querySelector('.no-data-message');
    if (noDataMsg) {
        noDataMsg.style.display = 'none';
    }

    // Modern Chart.js configuration with HTML Legend
    const config = this.getModernChartConfig(true, 'comparativeVisibilityLegend');
    
    this.charts.comparativeVisibility = new Chart(ctx, {
        type: 'line',
        data: {
            labels: (chartData.dates || []).map(d => new Date(d).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            })),
            datasets: chartData.datasets.map((dataset, index) => ({
                ...dataset,
                pointBackgroundColor: dataset.borderColor,
                pointBorderColor: '#FFFFFF',
                pointHoverBackgroundColor: dataset.borderColor,
                pointHoverBorderColor: '#FFFFFF',
                pointStyle: 'rectRounded',
                backgroundColor: dataset.borderColor ? dataset.borderColor.replace('rgb', 'rgba').replace(')', ', 0.3)') : 'rgba(99, 102, 241, 0.3)',
                fill: false,
                tension: 0.4
            }))
        },
        plugins: [htmlLegendPlugin],
        options: {
            ...config,
            scales: {
                ...config.scales,
                y: {
                    ...config.scales.y,
                    beginAtZero: true,
                    max: 100,
                    stacked: false,
                    title: {
                        display: true,
                        text: 'Visibility (%)',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    },
                    ticks: {
                        ...config.scales.y.ticks,
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    ...config.scales.x,
                    title: {
                        display: true,
                        text: 'Date',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    }
                }
            },
            plugins: {
                ...config.plugins,
                tooltip: {
                    ...config.plugins.tooltip,
                    callbacks: {
                        title: function(context) {
                            return new Date(chartData.dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                weekday: 'short',
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                            });
                        },
                        label: function(context) {
                            return `${context.dataset.label}: ${Math.round(context.raw)}%`;
                        }
                    }
                }
            }
        }
    });
}

export function renderComparativePositionChart(chartData) {
    const ctx = document.getElementById('comparativePositionChart');
    if (!ctx) {
        console.error('❌ comparativePositionChart canvas not found');
        return;
    }

    // Destroy existing chart
    if (this.charts.comparativePosition) {
        this.charts.comparativePosition.destroy();
    }

    console.log('🔍 Rendering comparative position chart with data:', chartData);
    
    if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
        console.warn('⚠️ No datasets for comparative position chart');
        this.showNoComparativeChartsMessage();
        return;
    }
    
    console.log(`✅ Rendering comparative position chart with ${chartData.datasets.length} datasets`);
    
    // Show canvas and hide any "no data" messages
    ctx.style.display = 'block';
    const noDataMsg = ctx.parentElement?.querySelector('.no-data-message');
    if (noDataMsg) {
        noDataMsg.style.display = 'none';
    }

    // Modern Chart.js configuration
    const config = this.getModernChartConfig(true, 'comparativePositionLegend');
    
    this.charts.comparativePosition = new Chart(ctx, {
        type: 'line',
        data: {
            labels: (chartData.dates || []).map(d => new Date(d).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            })),
            datasets: chartData.datasets.map((dataset, index) => ({
                ...dataset,
                pointBackgroundColor: dataset.borderColor,
                pointBorderColor: '#FFFFFF',
                pointHoverBackgroundColor: dataset.borderColor,
                pointHoverBorderColor: '#FFFFFF',
                pointStyle: 'rectRounded',
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.4
            }))
        },
        plugins: [htmlLegendPlugin],
        options: {
            ...config,
            scales: {
                ...config.scales,
                y: {
                    ...config.scales.y,
                    reverse: true,
                    beginAtZero: false,
                    min: 1,
                    max: 20,
                    ticks: {
                        ...config.scales.y.ticks,
                        stepSize: 1
                    },
                    title: {
                        display: true,
                        text: 'Position in AI Overview',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    }
                },
                x: {
                    ...config.scales.x,
                    title: {
                        display: true,
                        text: 'Date',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    }
                }
            },
            plugins: {
                ...config.plugins,
                tooltip: {
                    ...config.plugins.tooltip,
                    callbacks: {
                        title: function(context) {
                            return new Date(chartData.dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                weekday: 'short',
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                            });
                        },
                        label: function(context) {
                            return `${context.dataset.label}: Position ${Math.round(context.raw)}`;
                        }
                    }
                }
            }
        }
    });
}

export function showNoComparativeChartsMessage() {
    console.log('⚠️ No comparative charts data available');
    
    // Hide both charts and show empty state
    const visChart = document.getElementById('comparativeVisibilityChart');
    const posChart = document.getElementById('comparativePositionChart');
    
    if (visChart && visChart.parentElement) {
        const parent = visChart.parentElement;
        visChart.style.display = 'none';
        
        // Check if message already exists
        let message = parent.querySelector('.no-data-message');
        if (!message) {
            message = document.createElement('div');
            message.className = 'no-data-message';
            message.style.cssText = 'text-align: center; padding: 40px; color: #6b7280;';
            message.innerHTML = '<i class="fas fa-chart-line" style="font-size: 48px; margin-bottom: 16px; display: block; opacity: 0.3;"></i><p>No data available for visibility comparison</p><p style="font-size: 0.875rem; margin-top: 8px;">Add competitors to your project to see comparative analysis</p>';
            parent.appendChild(message);
        }
        message.style.display = 'block';
    }
    
    if (posChart && posChart.parentElement) {
        const parent = posChart.parentElement;
        posChart.style.display = 'none';
        
        // Check if message already exists
        let message = parent.querySelector('.no-data-message');
        if (!message) {
            message = document.createElement('div');
            message.className = 'no-data-message';
            message.style.cssText = 'text-align: center; padding: 40px; color: #6b7280;';
            message.innerHTML = '<i class="fas fa-chart-line" style="font-size: 48px; margin-bottom: 16px; display: block; opacity: 0.3;"></i><p>No data available for position comparison</p><p style="font-size: 0.875rem; margin-top: 8px;">Add competitors to your project to see comparative analysis</p>';
            parent.appendChild(message);
        }
        message.style.display = 'block';
    }
}

// ================================
// GRID.JS PROCESSING
// ================================

export function processAIOverviewDataForGrid(keywordResults, competitorDomains) {
    // Define base columns
    const columns = [
        {
            id: 'keyword',
            name: 'Keyword',
            width: '200px',
            sort: true
        },
        {
            id: 'your_domain_in_aio',
            name: gridjs.html('Your Domain<br>in AIO'),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    const va = (a === 'Yes') ? 1 : 0;
                    const vb = (b === 'Yes') ? 1 : 0;
                    return vb - va;
                }
            },
            formatter: (cell) => {
                const isPresent = cell === 'Yes';
                return gridjs.html(`
                    <span class="aio-status ${isPresent ? 'aio-yes' : 'aio-no'}">
                        ${cell}
                    </span>
                `);
            }
        },
        {
            id: 'your_position_in_aio',
            name: gridjs.html('Your Position<br>in AIO'),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    const numA = typeof a === 'number' ? a : (a === 'N/A' ? Infinity : parseInt(a) || Infinity);
                    const numB = typeof b === 'number' ? b : (b === 'N/A' ? Infinity : parseInt(b) || Infinity);
                    return numA - numB;
                }
            },
            formatter: (cell) => {
                if (cell === 'N/A') {
                    return gridjs.html('<span class="aio-na">N/A</span>');
                }
                return gridjs.html(`<span class="aio-position">${cell}</span>`);
            }
        }
    ];

    // Add competitor columns
    competitorDomains.forEach((domain, index) => {
        const truncatedDomain = this.truncateDomain(domain, 15);
        const domainId = (domain || '')
            .toLowerCase()
            .replace(/^https?:\/\//, '')
            .replace(/^www\./, '')
            .replace(/[^a-z0-9]+/g, '_');
        
        columns.push({
            id: `comp_${domainId}_present`,
            name: gridjs.html(`${truncatedDomain}<br>in AIO`),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    const va = (a === 'Yes') ? 1 : 0;
                    const vb = (b === 'Yes') ? 1 : 0;
                    return vb - va;
                }
            },
            formatter: (cell) => {
                const isPresent = cell === 'Yes';
                return gridjs.html(`
                    <span class="aio-status ${isPresent ? 'aio-yes' : 'aio-no'}">
                        ${cell}
                    </span>
                `);
            }
        });

        columns.push({
            id: `comp_${domainId}_position`,
            name: gridjs.html(`Position of<br>${truncatedDomain}`),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    const numA = typeof a === 'number' ? a : (a === 'N/A' ? Infinity : parseInt(a) || Infinity);
                    const numB = typeof b === 'number' ? b : (b === 'N/A' ? Infinity : parseInt(b) || Infinity);
                    return numA - numB;
                }
            },
            formatter: (cell) => {
                if (cell === 'N/A') {
                    return gridjs.html('<span class="aio-na">N/A</span>');
                }
                return gridjs.html(`<span class="aio-position">${cell}</span>`);
            }
        });
    });

    // Process data
    const gridData = keywordResults.map(kw => {
        const row = [
            kw.keyword,
            kw.user_domain_in_aio ? 'Yes' : 'No',
            kw.user_domain_position || 'N/A'
        ];

        competitorDomains.forEach(comp => {
            const compData = kw.competitors?.find(c => c.domain.toLowerCase() === comp.toLowerCase());
            row.push(compData ? 'Yes' : 'No');
            row.push(compData?.position || 'N/A');
        });

        return row;
    });

    return { columns, gridData };
}

export function truncateDomain(domain, maxLength = 20) {
    if (!domain || domain.length <= maxLength) return domain;
    return domain.substring(0, maxLength - 3) + '...';
}

