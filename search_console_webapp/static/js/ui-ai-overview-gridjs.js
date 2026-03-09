// static/js/ui-ai-overview-gridjs.js - Tabla Grid.js para análisis detallado de AI Overview

import { openSerpModal } from './ui-serp-modal.js';

/**
 * Crea y renderiza la tabla Grid.js con análisis detallado de AI Overview
 * @param {Array} keywordResults - Resultados de keywords del análisis
 * @param {Array} competitorDomains - Lista de dominios de competidores
 * @param {HTMLElement} container - Contenedor donde renderizar la tabla
 */
export function createAIOverviewGridTable(keywordResults, competitorDomains = [], container) {
    console.log('🏗️ Creating Grid.js table with:', {
        keywords: keywordResults?.length || 0,
        competitors: competitorDomains?.length || 0
    });

    if (!container) {
        console.error('❌ No container provided for Grid.js table');
        return null;
    }

    if (!window.gridjs) {
        console.error('❌ Grid.js library not loaded');
        return null;
    }

    // Filtrar solo keywords que tienen AI Overview
    const keywordsWithAIO = filterKeywordsWithAIO(keywordResults);
    
    if (keywordsWithAIO.length === 0) {
        displayNoAIOMessage(container);
        return null;
    }

    // Procesar datos para Grid.js
    const { columns, data } = processDataForGrid(keywordsWithAIO, competitorDomains);

    // Crear contenedor para la tabla
    const tableContainer = document.createElement('div');
    tableContainer.className = 'ai-overview-grid-container';
    tableContainer.innerHTML = `
        <h3 class="ai-overview-grid-title">Details of keywords with AIO</h3>
        <div id="ai-overview-grid-table" class="ai-overview-grid-wrapper"></div>
    `;

    // Limpiar contenedor y añadir nueva tabla
    container.innerHTML = '';
    container.appendChild(tableContainer);

    // Crear instancia de Grid.js
    const grid = new gridjs.Grid({
        columns: columns,
        data: data,
        pagination: true,
        sort: true,
        search: true,
        resizable: true
    });

    // Renderizar la tabla
    try {
        grid.render(document.getElementById('ai-overview-grid-table'));
        console.log('✅ Grid.js table rendered successfully');
        return grid;
    } catch (error) {
        console.error('❌ Error rendering Grid.js table:', error);
        return null;
    }
}

/**
 * Filtra keywords que tienen AI Overview
 * @param {Array} keywordResults - Resultados de keywords
 * @returns {Array} Keywords con AI Overview
 */
function filterKeywordsWithAIO(keywordResults) {
    if (!keywordResults || !Array.isArray(keywordResults)) {
        return [];
    }

    return keywordResults.filter(result => {
        const hasAI = result.ai_analysis?.has_ai_overview || false;
        if (hasAI) {
            console.log(`📝 Keyword with AIO: "${result.keyword}"`);
        }
        return hasAI;
    });
}

/**
 * Procesa los datos para Grid.js
 * @param {Array} keywordsWithAIO - Keywords con AI Overview
 * @param {Array} competitorDomains - Dominios de competidores
 * @returns {Object} Objeto con columnas y datos para Grid.js
 */
function processDataForGrid(keywordsWithAIO, competitorDomains) {
    // Definir columnas base
    const columns = [
        {
            name: 'View',
            width: '60px',
            sort: false,
            formatter: (cell, row) => {
                const keyword = row.cells[1].data; // La keyword está en la segunda columna
                return gridjs.html(`
                    <button 
                        class="serp-view-btn" 
                        onclick="window.aiOverviewGrid.openSerpModal('${keyword}')"
                        title="View SERP"
                    >
                        <i class="fas fa-search"></i>
                    </button>
                `);
            }
        },
        {
            name: 'Keyword',
            width: '200px',
            sort: true
        },
        {
            name: gridjs.html('Your Domain<br>in AIO'),
            width: '120px',
            sort: true,
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
            name: gridjs.html('Your Position<br>in AIO'),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    // Convertir a números para comparación - N/A como valor mayor para ir al final
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

    // 🆕 CTR Benchmark columns (Expected CTR, CTR Gap, Est. Clicks Absorbed)
    columns.push({
        name: gridjs.html('Expected<br>CTR'),
        width: '85px',
        sort: {
            compare: (a, b) => {
                const numA = typeof a === 'number' ? a : -1;
                const numB = typeof b === 'number' ? b : -1;
                return numA - numB;
            }
        },
        formatter: (cell) => {
            if (cell === null || cell === undefined || cell === '—') {
                return gridjs.html('<span class="aio-na">—</span>');
            }
            return gridjs.html(`<span style="color: #6c757d; font-weight: 500;">${(cell * 100).toFixed(1)}%</span>`);
        }
    });

    columns.push({
        name: gridjs.html('CTR<br>Gap'),
        width: '90px',
        sort: {
            compare: (a, b) => {
                const numA = typeof a === 'number' ? a : -999;
                const numB = typeof b === 'number' ? b : -999;
                return numB - numA; // Higher gap first
            }
        },
        formatter: (cell) => {
            if (cell === null || cell === undefined || cell === '—') {
                return gridjs.html('<span class="aio-na">—</span>');
            }
            const isNegative = cell < 0; // Negative gap = overperforming
            const color = cell > 0.01 ? '#dc3545' : (cell < -0.01 ? '#28a745' : '#6c757d');
            const prefix = cell > 0 ? '+' : '';
            return gridjs.html(`<span style="color: ${color}; font-weight: 600;">${prefix}${(cell * 100).toFixed(1)}%</span>`);
        }
    });

    columns.push({
        name: gridjs.html('Clicks<br>Absorbed'),
        width: '95px',
        sort: {
            compare: (a, b) => {
                const numA = typeof a === 'number' ? a : -1;
                const numB = typeof b === 'number' ? b : -1;
                return numB - numA; // Higher absorbed first
            }
        },
        formatter: (cell) => {
            if (cell === null || cell === undefined || cell === '—') {
                return gridjs.html('<span class="aio-na">—</span>');
            }
            const color = cell > 0 ? '#dc3545' : '#28a745';
            return gridjs.html(`<span style="color: ${color}; font-weight: 700;">${cell > 0 ? '~' : ''}${cell}</span>`);
        }
    });

    // Añadir columnas dinámicas para competidores
    competitorDomains.forEach((domain, index) => {
        const competitorNumber = index + 1;
        const truncatedDomain = truncateDomain(domain, 15);
        
        // Columna de presencia del competidor
        columns.push({
            name: gridjs.html(`${truncatedDomain}<br>in AIO`),
            width: '120px',
            sort: true,
            formatter: (cell) => {
                const isPresent = cell === 'Yes';
                return gridjs.html(`
                    <span class="aio-status ${isPresent ? 'aio-yes' : 'aio-no'}">
                        ${cell}
                    </span>
                `);
            }
        });

        // Columna de posición del competidor
        columns.push({
            name: gridjs.html(`Position of<br>${truncatedDomain}`),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    // Convertir a números para comparación - N/A como valor mayor para ir al final
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

    // Procesar datos
    const data = keywordsWithAIO.map(result => {
        const keyword = result.keyword || '';
        const aiAnalysis = result.ai_analysis || {};
        
        // Datos base
        const row = [
            '', // Columna de lupa (será reemplazada por el formatter)
            keyword,
            aiAnalysis.domain_is_ai_source ? 'Yes' : 'No',
            aiAnalysis.domain_ai_source_position || 'N/A'
        ];

        // 🆕 CTR analysis data
        const ctr = result._ctr_analysis || {};
        row.push(ctr.expected_ctr != null ? ctr.expected_ctr : '—');
        row.push(ctr.ctr_gap != null ? ctr.ctr_gap : '—');
        row.push(ctr.clicks_absorbed != null ? ctr.clicks_absorbed : '—');

        // Añadir datos de competidores
        competitorDomains.forEach(domain => {
            const competitorData = findCompetitorData(result, domain);
            row.push(competitorData.isPresent ? 'Yes' : 'No');
            row.push(competitorData.position || 'N/A');
        });

        return row;
    });

    return { columns, data };
}

/**
 * Busca datos de un competidor específico en los resultados
 * @param {Object} result - Resultado de keyword
 * @param {String} domain - Dominio del competidor
 * @returns {Object} Datos del competidor
 */
function findCompetitorData(result, domain) {
    // Los datos de competidores están en ai_analysis.debug_info.references_found
    const aiAnalysis = result.ai_analysis || {};
    const debugInfo = aiAnalysis.debug_info || {};
    const references = debugInfo.references_found || [];
    
    if (!references || references.length === 0) {
        return { isPresent: false, position: null };
    }
    
    // Buscar el dominio en las referencias
    for (let i = 0; i < references.length; i++) {
        const ref = references[i];
        const refLink = ref.link || '';
        const refSource = ref.source || '';
        const refTitle = ref.title || '';
        
        // Normalizar dominio del competidor para comparar
        const normalizedDomain = domain.toLowerCase().replace('www.', '');
        
        // Buscar coincidencias en link, source o title
        const linkMatch = refLink.toLowerCase().includes(normalizedDomain);
        const sourceMatch = refSource.toLowerCase().includes(normalizedDomain);
        const titleMatch = refTitle.toLowerCase().includes(normalizedDomain);
        
        if (linkMatch || sourceMatch || titleMatch) {
            return {
                isPresent: true,
                position: (ref.index || 0) + 1 // Convertir índice 0-based a posición 1-based
            };
        }
    }
    
    return { isPresent: false, position: null };
}

/**
 * Trunca un dominio para mostrar en columnas
 * @param {String} domain - Dominio completo
 * @param {Number} maxLength - Longitud máxima
 * @returns {String} Dominio truncado
 */
function truncateDomain(domain, maxLength = 15) {
    if (!domain || domain.length <= maxLength) return domain;
    return domain.substring(0, maxLength - 3) + '...';
}

/**
 * Muestra mensaje cuando no hay keywords con AIO
 * @param {HTMLElement} container - Contenedor
 */
function displayNoAIOMessage(container) {
    container.innerHTML = `
        <div class="no-aio-message">
            <i class="fas fa-info-circle"></i>
            <h3>No AI Overview Keywords Found</h3>
            <p>No keywords in this analysis have AI Overview results to display.</p>
        </div>
    `;
}

// Funciones globales para eventos
window.aiOverviewGrid = {
    openSerpModal: (keyword) => {
        console.log('🔍 Opening SERP modal for keyword:', keyword);
        if (window.openSerpModal) {
            openSerpModal(keyword);
        } else {
            console.warn('⚠️ SERP modal function not available');
        }
    }
};

console.log('📦 AI Overview Grid.js module loaded');