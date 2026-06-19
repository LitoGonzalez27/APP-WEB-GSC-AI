/**
 * Manual AI System - Analytics — Tabla AI Overview Keywords (Grid.js)
 *
 * Extraído verbatim de manual-ai-analytics.js (refactor Fase 4).
 */

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
