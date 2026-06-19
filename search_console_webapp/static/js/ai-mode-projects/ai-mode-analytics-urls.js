/**
 * AI Mode System - Analytics — Top URLs Ranking (filtro por marca + paginación)
 *
 * Extraído verbatim de ai-mode-analytics.js (refactor Fase 4).
 */

import { getDomainLogoUrl } from './ai-mode-utils.js';

// ================================
// TOP URLS RANKING
// ================================

export async function loadTopUrlsRanking(projectId) {
    if (!projectId) {
        this.showNoAiModeUrlsMessage();
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/urls-ranking?days=${days}&limit=100`);
        
        if (!response.ok) {
            if (response.status === 404) {
                this.showNoAiModeUrlsMessage();
                return;
            }
            throw new Error('Failed to load URLs ranking');
        }

        const data = await response.json();
        
        // Store all URLs for filtering
        this._allUrlsData = data.urls || [];
        
        console.log('📥 Loaded AI Mode URLs data:', this._allUrlsData.length);
        
        // Initialize filter chip event listener (only once)
        try {
            this.initAiModeUrlsFilter();
        } catch (e) {
            console.error('Error initializing filter:', e);
        }
        
        // Check if filter is currently active
        let isFilterActive = false;
        try {
            const filterBtn = document.getElementById('filterMyBrandUrls');
            isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';
        } catch (e) {
            console.error('Error checking filter state:', e);
        }
        
        // Apply filter if active, otherwise show all with pagination
        if (isFilterActive) {
            console.log('🔵 Filter is active, applying filter...');
            try {
                this.filterAiModeUrlsByBrand(true);
            } catch (e) {
                console.error('Error applying filter, showing all URLs:', e);
                // Apply pagination on error
                const pageSize = 20;
                const state = { page: 1 };
                const totalPages = Math.max(1, Math.ceil(this._allUrlsData.length / pageSize));
                const paged = this._allUrlsData.slice(0, pageSize);
                this._topUrlsState = { page: state.page, totalPages, fullList: this._allUrlsData };
                this.renderTopUrlsRanking(paged);
                this.renderTopUrlsPaginator();
            }
        } else {
            console.log('⚪ Filter is inactive, showing all URLs with pagination');
            // Apply pagination
            const pageSize = 20;
            const state = this._topUrlsState || { page: 1 };
            const totalPages = Math.max(1, Math.ceil(this._allUrlsData.length / pageSize));
            state.page = Math.min(state.page, totalPages);
            const start = (state.page - 1) * pageSize;
            const paged = this._allUrlsData.slice(start, start + pageSize);
            this._topUrlsState = { page: state.page, totalPages, fullList: this._allUrlsData };
            this.renderTopUrlsRanking(paged);
            this.renderTopUrlsPaginator();
        }

    } catch (error) {
        console.error('Error loading URLs ranking:', error);
        this.showNoAiModeUrlsMessage();
    }
}

export function initAiModeUrlsFilter() {
    const filterBtn = document.getElementById('filterMyBrandUrls');
    if (!filterBtn || filterBtn._listenerAttached) return;
    
    filterBtn._listenerAttached = true;
    filterBtn.addEventListener('click', () => {
        const isActive = filterBtn.getAttribute('data-active') === 'true';
        filterBtn.setAttribute('data-active', !isActive);
        
        // Apply filter
        this.filterAiModeUrlsByBrand(!isActive);
    });
}

export function filterAiModeUrlsByBrand(showOnlyMyBrand) {
    if (!this._allUrlsData || this._allUrlsData.length === 0) {
        console.warn('⚠️ No URLs data available for filtering');
        this.showNoAiModeUrlsMessage();
        return;
    }
    
    let filteredUrls = this._allUrlsData;
    
    if (showOnlyMyBrand) {
        try {
            // Get current project brand name
            const projectSelect = document.getElementById('analyticsProjectSelect');
            const currentProjectId = projectSelect ? parseInt(projectSelect.value) : null;
            const project = this.projects?.find(p => p.id === currentProjectId) || this.currentProject;
            
            if (!project || !project.brand_name) {
                console.error('❌ No project or brand name found for filtering, showing all URLs');
                // Reset pagination and render all
                const pageSize = 20;
                const state = { page: 1 };
                const totalPages = Math.max(1, Math.ceil(this._allUrlsData.length / pageSize));
                const paged = this._allUrlsData.slice(0, pageSize);
                this._topUrlsState = { page: state.page, totalPages, fullList: this._allUrlsData };
                this.renderTopUrlsRanking(paged);
                this.renderTopUrlsPaginator();
                return;
            }
            
            // Get brand name and normalize (same logic as renderTopUrlsRanking)
            const rawBrand = project.brand_name || '';
            const normalizedBrand = rawBrand.toLowerCase()
                .replace(/^www\./, '')
                .replace(/\s+/g, '')  // Remove spaces
                .replace(/-/g, '')     // Remove hyphens
                .trim();
            
            console.log('🔍 Filtering URLs for brand:', {
                raw: project.brand_name,
                normalized: normalizedBrand
            });
            
            // Filter URLs that contain the brand name
            filteredUrls = this._allUrlsData.filter(urlData => {
                try {
                    const urlObj = new URL(urlData.url);
                    const urlDomain = urlObj.hostname.toLowerCase().replace(/^www\./, '');
                    const normalizedUrlDomain = urlDomain.replace(/\s+/g, '').replace(/-/g, '');
                    
                    // Check if normalized URL domain contains normalized brand name
                    const matches = normalizedBrand && normalizedUrlDomain.includes(normalizedBrand);
                    
                    if (matches) {
                        console.log('✅ Match:', urlData.url, `(${normalizedUrlDomain} includes ${normalizedBrand})`);
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
                console.warn('⚠️ No URLs found for your brand');
                this.showNoAiModeUrlsMessage();
                return;
            }
            
            // Recalculate ranks
            filteredUrls = filteredUrls.map((url, index) => ({
                ...url,
                rank: index + 1
            }));
        } catch (e) {
            console.error('❌ Error in filterAiModeUrlsByBrand:', e);
            filteredUrls = this._allUrlsData;
        }
    }
    
    // Apply pagination
    const pageSize = 20;
    const state = this._topUrlsState || { page: 1 };
    const totalPages = Math.max(1, Math.ceil(filteredUrls.length / pageSize));
    state.page = Math.min(state.page, totalPages);
    const start = (state.page - 1) * pageSize;
    const paged = filteredUrls.slice(start, start + pageSize);
    this._topUrlsState = { page: state.page, totalPages, fullList: filteredUrls };
    this.renderTopUrlsRanking(paged);
    this.renderTopUrlsPaginator();
}

export function renderTopUrlsRanking(urls) {
    const tableBody = document.getElementById('topUrlsBody');
    const noUrlsMessage = document.getElementById('noAiModeUrlsMessage');
    const topUrlsTable = document.getElementById('topUrlsTable');

    if (!urls || urls.length === 0) {
        this.showNoAiModeUrlsMessage();
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
    
    // Normalize project brand/domain
    let projectBrandName = '';
    let competitorDomains = [];
    
    if (currentProject) {
        // AI Mode uses brand_name (e.g., "HM Fertility Center")
        // Normalize it to match against URLs
        const rawBrand = currentProject.brand_name || currentProject.domain || '';
        projectBrandName = rawBrand.toLowerCase()
            .replace(/^www\./, '')
            .replace(/\s+/g, '')  // Remove spaces: "HM Fertility" → "hmfertility"
            .replace(/-/g, '')     // Remove hyphens
            .trim();
        
        // Normalize competitor domains - they might be stored as objects or strings
        const competitors = currentProject.competitors || currentProject.selected_competitors || [];
        competitorDomains = competitors.map(c => {
            // Handle if competitor is an object with domain property
            const domain = typeof c === 'object' ? (c.domain || c.competitor_domain || c) : c;
            return String(domain).toLowerCase().replace(/^www\./, '').trim();
        }).filter(d => d && d.length > 0);
        
        console.log('🎯 URL Highlighting Config (AI Mode):', {
            rawBrandName: currentProject.brand_name,
            normalizedBrandName: projectBrandName,
            competitorDomains,
            totalUrls: urls.length
        });
    }

    // Debug: Log first URL data to see structure
    if (urls.length > 0) {
        console.log('🔍 First URL data structure:', urls[0]);
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
            
            // Normalize URL domain for comparison (remove spaces, hyphens)
            const normalizedUrlDomain = urlDomain.replace(/\s+/g, '').replace(/-/g, '');
            
            // Check if it's project brand
            // Match if brand name appears in the domain
            if (projectBrandName && normalizedUrlDomain.includes(projectBrandName)) {
                domainType = 'project';
            } 
            // Check if it's competitor domain
            else if (competitorDomains.some(comp => urlDomain === comp || urlDomain.endsWith('.' + comp))) {
                domainType = 'competitor';
            }
            
            if (index < 5) { // Log first 5 for debugging
                console.log(`  URL ${index + 1}: ${urlDomain} (normalized: ${normalizedUrlDomain}) → ${domainType}`, 
                    projectBrandName ? `(brand: ${projectBrandName})` : '');
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
            <td class="position-cell">${(typeof urlData.avg_position === 'number') ? urlData.avg_position.toFixed(1) : '-'}</td>
            <td class="percentage-cell">${urlData.percentage ? urlData.percentage.toFixed(2) : '0.00'}%</td>
        `;
        
        tableBody.appendChild(row);
    });
}

export function renderTopUrlsPaginator() {
    const container = document.getElementById('topUrlsTable')?.parentElement || document.getElementById('noAiModeUrlsMessage')?.parentElement;
    if (!container || !this._topUrlsState) return;
    
    let paginator = document.getElementById('topUrlsPaginator');
    if (!paginator) {
        paginator = document.createElement('div');
        paginator.id = 'topUrlsPaginator';
        paginator.style.cssText = 'display:flex;justify-content:flex-end;gap:8px;margin:24px 0;';
        container.appendChild(paginator);
    }
    
    const { page, totalPages, fullList } = this._topUrlsState;
    paginator.innerHTML = '';
    
    // Previous button
    const btnPrev = document.createElement('button');
    btnPrev.className = 'btn btn-light btn-sm';
    btnPrev.style.backgroundColor = '#C3F5A4';
    btnPrev.style.borderColor = '#C3F5A4';
    btnPrev.style.color = '#111827';
    btnPrev.textContent = 'Previous';
    btnPrev.disabled = page <= 1;
    btnPrev.onclick = () => { 
        this._topUrlsState.page = Math.max(1, page - 1);
        // Check if filter is active
        const filterBtn = document.getElementById('filterMyBrandUrls');
        const isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';
        if (isFilterActive) {
            this.filterAiModeUrlsByBrand(true);
        } else {
            const pageSize = 20;
            const start = (this._topUrlsState.page - 1) * pageSize;
            const paged = fullList.slice(start, start + pageSize);
            this.renderTopUrlsRanking(paged);
            this.renderTopUrlsPaginator();
        }
    };
    
    // Page info
    const info = document.createElement('span');
    info.style.cssText = 'display:flex;align-items:center;font-size:12px;color:#6b7280;';
    info.textContent = `Page ${page} / ${totalPages}`;
    
    // Next button
    const btnNext = document.createElement('button');
    btnNext.className = 'btn btn-light btn-sm';
    btnNext.style.backgroundColor = '#C3F5A4';
    btnNext.style.borderColor = '#C3F5A4';
    btnNext.style.color = '#111827';
    btnNext.textContent = 'Next';
    btnNext.disabled = page >= totalPages;
    btnNext.onclick = () => { 
        this._topUrlsState.page = Math.min(totalPages, page + 1);
        // Check if filter is active
        const filterBtn = document.getElementById('filterMyBrandUrls');
        const isFilterActive = filterBtn && filterBtn.getAttribute('data-active') === 'true';
        if (isFilterActive) {
            this.filterAiModeUrlsByBrand(true);
        } else {
            const pageSize = 20;
            const start = (this._topUrlsState.page - 1) * pageSize;
            const paged = fullList.slice(start, start + pageSize);
            this.renderTopUrlsRanking(paged);
            this.renderTopUrlsPaginator();
        }
    };
    
    paginator.appendChild(btnPrev);
    paginator.appendChild(info);
    paginator.appendChild(btnNext);
}

export function showNoAiModeUrlsMessage() {
    const tableBody = document.getElementById('topUrlsBody');
    const noUrlsMessage = document.getElementById('noAiModeUrlsMessage');
    const topUrlsTable = document.getElementById('topUrlsTable');

    if (tableBody) tableBody.innerHTML = '';
    if (topUrlsTable) topUrlsTable.style.display = 'none';
    if (noUrlsMessage) noUrlsMessage.style.display = 'block';
    
    // Remove paginator if exists
    const paginator = document.getElementById('topUrlsPaginator');
    if (paginator) paginator.remove();
}
