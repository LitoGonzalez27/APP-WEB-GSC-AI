/**
 * Manual AI System - Analytics — Top Domains y Global Domains Ranking
 *
 * Extraído verbatim de manual-ai-analytics.js (refactor Fase 4).
 */

import { getDomainLogoUrl } from './manual-ai-utils.js';

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
        
        // Añadir paginación simple en cliente (10 por página)
        const fullList = data.domains || [];
        const pageSize = 10;
        const state = this._globalDomainsState || { page: 1 };
        const totalPages = Math.max(1, Math.ceil(fullList.length / pageSize));
        state.page = Math.min(state.page, totalPages);
        const start = (state.page - 1) * pageSize;
        const paged = fullList.slice(start, start + pageSize);
        // Guardar también el projectId para navegación fiable
        this._globalDomainsState = { page: state.page, totalPages, fullList, projectId };
        this.renderGlobalDomainsRanking(paged);
        this.renderGlobalDomainsPaginator();

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

export function renderGlobalDomainsPaginator() {
    const container = document.getElementById('globalDomainsTable')?.parentElement || document.getElementById('noGlobalDomainsMessage')?.parentElement;
    if (!container || !this._globalDomainsState) return;
    
    let paginator = document.getElementById('globalDomainsPaginator');
    if (!paginator) {
        paginator = document.createElement('div');
        paginator.id = 'globalDomainsPaginator';
        paginator.style.cssText = 'display:flex;justify-content:flex-end;gap:8px;margin:24px 0;';
        container.appendChild(paginator);
    }
    
    const { page, totalPages, projectId } = this._globalDomainsState;
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
        this._globalDomainsState.page = Math.max(1, page - 1); 
        this.loadGlobalDomainsRanking(projectId || this.currentProject?.id || this.currentModalProject?.id); 
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
        this._globalDomainsState.page = Math.min(totalPages, page + 1); 
        this.loadGlobalDomainsRanking(projectId || this.currentProject?.id || this.currentModalProject?.id); 
    };
    
    paginator.appendChild(btnPrev);
    paginator.appendChild(info);
    paginator.appendChild(btnNext);
}

export function showNoGlobalDomainsMessage() {
    const tableBody = document.getElementById('globalDomainsBody');
    const noDomainsMessage = document.getElementById('noGlobalDomainsMessage');
    const globalDomainsTable = document.getElementById('globalDomainsTable');

    if (tableBody) tableBody.innerHTML = '';
    if (globalDomainsTable) globalDomainsTable.style.display = 'none';
    if (noDomainsMessage) noDomainsMessage.style.display = 'block';
    
    // Remove paginator if exists
    const paginator = document.getElementById('globalDomainsPaginator');
    if (paginator) paginator.remove();
}
