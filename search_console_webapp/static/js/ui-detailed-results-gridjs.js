/* ==============================================
   DETAILED RESULTS - GRID.JS TABLE
   Tabla Grid.js para resultados detallados por keyword
   ============================================== */

import { openSerpModal } from './ui-serp-modal.js';

/**
 * Crea y renderiza la tabla detallada de keywords usando Grid.js
 * @param {Array} keywordResults - Array de resultados de keywords
 * @param {HTMLElement} container - Contenedor donde renderizar la tabla
 * @returns {Object|null} Instancia de Grid.js o null si hay error
 */
export function createDetailedResultsGridTable(keywordResults, container) {
    if (!keywordResults || keywordResults.length === 0) {
        console.log('📊 No hay resultados para mostrar en tabla detallada');
        
        // Mostrar mensaje de no hay datos
        const noDataContainer = document.createElement('div');
        noDataContainer.className = 'ai-overview-grid-section';
        noDataContainer.innerHTML = `
            <div class="no-aio-message">
                <i class="fas fa-info-circle"></i>
                <h3>No Detailed Results</h3>
                <p>No detailed results found to display.</p>
            </div>
        `;
        
        container.appendChild(noDataContainer);
        return null;
    }

    console.log(`📊 Creando tabla detallada Grid.js con ${keywordResults.length} keywords`);

    // Procesar datos para Grid.js
    const { columns, data } = processDetailedDataForGrid(keywordResults);

    // Crear contenedor para la tabla
    const tableContainer = document.createElement('div');
    tableContainer.className = 'ai-overview-grid-container';
    tableContainer.innerHTML = `
        <h3 class="ai-overview-grid-title">Detailed Results by Keyword</h3>
        <div id="detailed-results-grid-table" class="ai-overview-grid-wrapper"></div>
    `;

    // Limpiar contenedor anterior si existe
    const existingContainer = container.querySelector('.ai-results-table-container');
    if (existingContainer) {
        existingContainer.remove();
    }

    // Añadir nueva tabla
    const sectionContainer = document.createElement('div');
    sectionContainer.className = 'ai-overview-grid-section';
    sectionContainer.appendChild(tableContainer);
    container.appendChild(sectionContainer);

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
        grid.render(document.getElementById('detailed-results-grid-table'));
        console.log('✅ Tabla detallada Grid.js renderizada exitosamente');
        return grid;
    } catch (error) {
        console.error('❌ Error renderizando tabla detallada Grid.js:', error);
        return null;
    }
}

/**
 * Procesa los datos de keywords para Grid.js
 * @param {Array} keywordResults - Resultados de keywords
 * @returns {Object} - Objeto con columns y data para Grid.js
 */
function processDetailedDataForGrid(keywordResults) {
    console.log('🔄 Procesando datos detallados para Grid.js...');

    // Definir columnas - REORDENADAS según especificación del usuario
    const columns = [
        {
            name: 'View SERP',
            width: '80px',
            sort: false,
            formatter: (cell, row) => {
                const keyword = row.cells[1].data; // Keyword está en la segunda columna
                return gridjs.html(`
                    <div style="display: flex; justify-content: center; align-items: center; height: 100%;">
                        <button class="serp-view-btn" onclick="window.openSerpModalFromGrid('${escapeForAttribute(keyword)}')">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                `);
            }
        },
        {
            name: 'Keyword',
            width: '250px',
            sort: true
        },
        {
            name: gridjs.html('With<br>AIO'),
            width: '100px',
            sort: true,
            formatter: (cell) => {
                const hasAIO = cell === 'Yes';
                return gridjs.html(`
                    <span class="aio-status ${hasAIO ? 'aio-yes' : 'aio-no'}">
                        ${cell}
                    </span>
                `);
            }
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
            name: gridjs.html('AIO<br>Position'),
            width: '100px',
            sort: {
                compare: (a, b) => {
                    // Convertir a números para comparación - N/A como valor más negativo
                    const numA = typeof a === 'number' ? a : (a === 'No' || a === 'N/A' ? -Infinity : parseInt(a) || -Infinity);
                    const numB = typeof b === 'number' ? b : (b === 'No' || b === 'N/A' ? -Infinity : parseInt(b) || -Infinity);
                    return numA - numB;
                }
            },
            formatter: (cell) => {
                if (typeof cell === 'number' && cell > 0) {
                    return gridjs.html(`<span class="aio-position">${cell}</span>`);
                }
                return gridjs.html(`<span class="aio-na">${cell}</span>`);
            }
        },
        {
            name: gridjs.html('Organic<br>Position'),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    // Convertir a números para comparación
                    const numA = typeof a === 'number' ? a : (a === 'Not found' ? Infinity : parseInt(a) || Infinity);
                    const numB = typeof b === 'number' ? b : (b === 'Not found' ? Infinity : parseInt(b) || Infinity);
                    return numA - numB;
                }
            },
            formatter: (cell) => {
                if (typeof cell === 'number') {
                    return cell === 0 ? '0 (Featured)' : `${cell}`;
                }
                return cell;
            }
        },
        {
            name: gridjs.html('Clicks<br>(P1)'),
            width: '100px',
            sort: {
                compare: (a, b) => {
                    // Convertir a números para comparación
                    const numA = parseInteger(a);
                    const numB = parseInteger(b);
                    return numA - numB;
                }
            }
        },
        {
            name: gridjs.html('Impressions<br>(P1)'),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    // Convertir a números para comparación
                    const numA = parseInteger(a);
                    const numB = parseInteger(b);
                    return numA - numB;
                }
            }
        }
    ];

    // Procesar datos
    const data = keywordResults.map(result => {
        const aiAnalysis = result.ai_analysis || {};
        const isDomainInAI = aiAnalysis.domain_is_ai_source || false;
        const hasAIOverview = aiAnalysis.has_ai_overview || false;
        
        const organicPosition = (result.site_position !== null && result.site_position !== undefined)
            ? result.site_position
            : 'Not found';
            
        const aiPosition = (aiAnalysis.domain_ai_source_position !== null && aiAnalysis.domain_ai_source_position !== undefined)
            ? aiAnalysis.domain_ai_source_position
            : 'No';

return [
            '', // View SERP (manejado por formatter)
            result.keyword || 'N/A',
            hasAIOverview ? 'Yes' : 'No', // With AIO
            isDomainInAI ? 'Yes' : 'No', // Your Domain in AIO
            aiPosition, // AIO Position
            organicPosition, // Organic Position
            formatInteger(result.clicks_p1 || result.clicks_m1 || 0), // Clics (P1)
            formatInteger(result.impressions_p1 || result.impressions_m1 || 0) // Impresiones (P1)
        ];
    });

    console.log(`✅ Datos procesados: ${data.length} filas`);
    return { columns, data };
}

/**
 * Función auxiliar para escapar atributos HTML
 * @param {string} str - Cadena a escapar
 * @returns {string} - Cadena escapada
 */
function escapeForAttribute(str) {
    if (!str) return '';
    return str.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

/**
 * Función auxiliar para parsear enteros de string formateado
 * @param {string} str - String con número formateado
 * @returns {number} - Número parseado
 */
function parseInteger(str) {
    if (!str || str === '0' || str === '-') return 0;
    return parseInt(str.replace(/[,.]/g, '')) || 0;
}

/**
 * Función auxiliar para formatear enteros
 * @param {number|string} value - Valor a formatear
 * @returns {string} - Valor formateado
 */
function formatInteger(value) {
    if (!value || value === 0) return '0';
    const num = typeof value === 'string' ? parseInt(value.replace(/[,.]/g, '')) : value;
    return num.toLocaleString('es-ES');
}

// Función global para abrir modal SERP desde Grid.js
window.openSerpModalFromGrid = function(keyword) {
    if (window.openSerpModal) {
        window.openSerpModal(keyword, '');
    } else {
        console.error('openSerpModal function not found');
    }
};