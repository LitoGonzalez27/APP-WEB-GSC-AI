// static/js/ui-url-keywords-gridjs.js - Grid.js para modal de keywords por URL

import { openSerpModal } from './ui-serp-modal.js';
import { formatInteger, formatPercentage, formatPercentageChange, formatPosition, formatPositionDelta, formatAbsoluteDelta, calculateAbsoluteDelta, parsePositionValue, parseIntegerValue, parseNumericValue } from './number-utils.js';

/**
 * Crea y renderiza la tabla Grid.js de keywords en el modal
 * @param {Array} keywordsData - Datos de keywords
 * @param {boolean} hasComparison - Si hay comparación entre períodos
 * @param {HTMLElement} container - Contenedor donde renderizar la tabla
 * @returns {Object|null} Instancia de Grid.js o null si hay error
 */
export function createUrlKeywordsGridTable(keywordsData, hasComparison = false, container) {
    console.log('🏗️ Creating URL Keywords Grid.js table with:', {
        keywords: keywordsData?.length || 0,
        hasComparison: hasComparison
    });

    if (!container) {
        console.error('❌ No container provided for URL Keywords Grid.js table');
        return null;
    }

    if (!window.gridjs) {
        console.error('❌ Grid.js library not loaded');
        return null;
    }

    if (!keywordsData || keywordsData.length === 0) {
        displayNoKeywordsMessage(container);
        return null;
    }

    // Procesar datos para Grid.js
    const { columns, data } = processKeywordsDataForGrid(keywordsData, hasComparison);

    // Crear contenedor para la tabla
    const tableContainer = document.createElement('div');
    tableContainer.className = 'ai-overview-grid-container';
    tableContainer.innerHTML = `
        <div id="url-keywords-grid-table" class="ai-overview-grid-wrapper"></div>
    `;

    // Limpiar contenedor y añadir nueva tabla
    container.innerHTML = '';
    container.appendChild(tableContainer);

    // Crear instancia de Grid.js
    const grid = new gridjs.Grid({
        columns: columns,
        data: data,
        pagination: {
            limit: 10
        },
        sort: {
            multiColumn: false,
            sortColumn: 2, // Clicks P1 siempre (índice 2)
            sortDirection: 'desc' // De mayor a menor
        },
        search: true,
        resizable: true,
        style: {
            table: {
                'white-space': 'normal'
            }
        }
    });

    // Renderizar la tabla
    try {
        grid.render(document.getElementById('url-keywords-grid-table'));
        console.log('✅ URL Keywords Grid.js table rendered successfully');
        return grid;
    } catch (error) {
        console.error('❌ Error rendering URL Keywords Grid.js table:', error);
        return null;
    }
}

/**
 * Procesa los datos de keywords para Grid.js
 * @param {Array} keywordsData - Datos de keywords
 * @param {boolean} hasComparison - Si hay comparación
 * @returns {Object} Objeto con columnas y datos para Grid.js
 */
function processKeywordsDataForGrid(keywordsData, hasComparison) {
    // Definir columnas base
    const columns = [
        {
            name: 'View SERP',
            width: '100px',
            sort: false,
            formatter: (cell, row) => {
                const keyword = row.cells[1].data; // La keyword está en la segunda columna
                return gridjs.html(`
                    <div style="display: flex; justify-content: center; align-items: center; height: 100%;">
                        <button 
                            class="serp-view-btn" 
                            onclick="window.urlKeywordsGrid.openSerpModal('${escapeForAttribute(keyword)}')"
                            title="View SERP"
                        >
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                `);
            }
        },
        {
            name: 'Keyword',
            width: '250px',
            sort: true,
            formatter: (cell) => {
                return gridjs.html(`
                    <div class="keyword-cell" title="${escapeForAttribute(cell)}" style="
                        max-width: 230px;
                        white-space: normal;
                        line-height: 1.3;
                        word-break: break-word;
                        overflow: hidden;
                        display: -webkit-box;
                        -webkit-line-clamp: 3;
                        -webkit-box-orient: vertical;
                    ">
                        ${escapeForAttribute(cell)}
                    </div>
                `);
            }
        },
        {
            name: gridjs.html('Clicks<br>P1'),
            width: '100px',
            sort: {
                compare: (a, b) => {
                    return parseIntegerValue(b) - parseIntegerValue(a); // Mayor a menor
                }
            }
        }
    ];

    // Añadir columnas según si hay comparación
    if (hasComparison) {
        columns.push(
            {
                name: gridjs.html('Clicks<br>P2'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseIntegerValue(b) - parseIntegerValue(a); // Mayor a menor
                    }
                }
            },
            {
                name: gridjs.html('ΔClicks'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseNumericValue(b) - parseNumericValue(a); // Mayor a menor
                    }
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            }
        );
    }

    columns.push(
        {
            name: gridjs.html('Impressions<br>P1'),
            width: '120px',
            sort: {
                compare: (a, b) => {
                    return parseIntegerValue(b) - parseIntegerValue(a); // Mayor a menor
                }
            }
        }
    );

    if (hasComparison) {
        columns.push(
            {
                name: gridjs.html('Impressions<br>P2'),
                width: '120px',
                sort: {
                    compare: (a, b) => {
                        return parseIntegerValue(b) - parseIntegerValue(a); // Mayor a menor
                    }
                }
            },
            {
                name: gridjs.html('ΔImp.'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseNumericValue(b) - parseNumericValue(a); // Mayor a menor
                    }
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            }
        );
    }

    columns.push(
        {
            name: gridjs.html('CTR<br>P1 (%)'),
            width: '100px',
            sort: {
                compare: (a, b) => {
                    return parseNumericValue(b) - parseNumericValue(a); // Mayor a menor
                }
            }
        }
    );

    if (hasComparison) {
        columns.push(
            {
                name: gridjs.html('CTR<br>P2 (%)'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseNumericValue(b) - parseNumericValue(a); // Mayor a menor
                    }
                }
            },
            {
                name: gridjs.html('ΔCTR'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseNumericValue(b) - parseNumericValue(a); // Mayor a menor
                    }
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            }
        );
    }

    columns.push(
        {
            name: gridjs.html('Position<br>P1'),
            width: '100px',
            sort: true, // Usar ordenamiento numérico nativo de Grid.js
            formatter: (cell) => {
                // Formatear para display pero pasar valor numérico para sorting
                if (cell === null || cell === undefined || cell === 0) return '0';
                return formatPosition(cell);
            }
        }
    );

    if (hasComparison) {
        columns.push(
            {
                name: gridjs.html('Position<br>P2'),
                width: '100px',
                sort: true, // Usar ordenamiento numérico nativo de Grid.js
                formatter: (cell) => {
                    // Formatear para display pero pasar valor numérico para sorting
                    if (cell === null || cell === undefined || cell === 0) return '0';
                    return formatPosition(cell);
                }
            },
            {
                name: gridjs.html('ΔPos'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseNumericValue(a) - parseNumericValue(b); // Menor a mayor (mejoras primero)
                    }
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClassPosition(cell)}">${cell}</span>`);
                }
            }
        );
    }

    // Procesar datos
    const data = keywordsData.map(keyword => {
        const rowData = [
            '', // Columna SERP (será reemplazada por el formatter)
            keyword.keyword || keyword.query || ''
        ];

        // Añadir datos según si hay comparación
        rowData.push(formatInteger(keyword.clicks_m1 ?? keyword.clicks_p1 ?? 0));
        
        if (hasComparison) {
            rowData.push(formatInteger(keyword.clicks_m2 ?? keyword.clicks_p2 ?? 0));
            rowData.push(calculateAbsoluteDelta(keyword.clicks_m1 ?? keyword.clicks_p1 ?? 0, keyword.clicks_m2 ?? keyword.clicks_p2 ?? 0, 'clicks'));
        }
        
        rowData.push(formatInteger(keyword.impressions_m1 ?? keyword.impressions_p1 ?? 0));
        
        if (hasComparison) {
            rowData.push(formatInteger(keyword.impressions_m2 ?? keyword.impressions_p2 ?? 0));
            rowData.push(calculateAbsoluteDelta(keyword.impressions_m1 ?? keyword.impressions_p1 ?? 0, keyword.impressions_m2 ?? keyword.impressions_p2 ?? 0, 'impressions'));
        }
        
        rowData.push(formatPercentage(keyword.ctr_m1 ?? keyword.ctr_p1));
        
        if (hasComparison) {
            rowData.push(formatPercentage(keyword.ctr_m2 ?? keyword.ctr_p2));
            rowData.push(calculateAbsoluteDelta(keyword.ctr_m1 ?? keyword.ctr_p1 ?? 0, keyword.ctr_m2 ?? keyword.ctr_p2 ?? 0, 'ctr'));
        }
        
        // ✅ NUEVO: Pasar valores numéricos para posiciones (0 en lugar de N/A)
        const pos1 = keyword.position_m1 ?? keyword.position_p1;
        const pos1Numeric = (pos1 == null || isNaN(pos1)) ? 0 : Number(pos1);
        rowData.push(pos1Numeric);
        
        if (hasComparison) {
            const pos2 = keyword.position_m2 ?? keyword.position_p2;
            const pos2Numeric = (pos2 == null || isNaN(pos2)) ? 0 : Number(pos2);
            rowData.push(pos2Numeric);
            // Calcular delta usando los valores reales (0 para N/A)
            rowData.push(calculateAbsoluteDelta(pos1Numeric, pos2Numeric, 'position'));
        }

        return rowData;
    });

    return { columns, data };
}

/**
 * Muestra mensaje cuando no hay keywords
 * @param {HTMLElement} container - Contenedor
 */
function displayNoKeywordsMessage(container) {
    container.innerHTML = `
        <div class="no-aio-message">
            <i class="fas fa-info-circle"></i>
            <h3>No Keywords Found</h3>
            <p>No keyword data available for this URL in the selected period.</p>
        </div>
    `;
}

/**
 * Función auxiliar para escapar atributos HTML
 * @param {string} str - Cadena a escapar
 * @returns {string} - Cadena escapada
 */
function escapeForAttribute(str) {
    if (!str) return '';
    return str.replace(/'/g, '&#39;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ✅ ELIMINADAS: Funciones locales incorrectas parseInteger() y parsePercentageForSort()
// Ahora usamos las funciones correctas de number-utils.js:
// - parseIntegerValue() para enteros con separadores de miles españoles
// - parseNumericValue() para números decimales con formato español

/**
 * Obtiene la clase CSS para deltas
 * @param {string} value - Valor del delta
 * @returns {string} - Clase CSS
 */
function getDeltaClass(value) {
    if (!value || value === '-') return '';
    const numValue = parseFloat(value.replace(/[%+]/g, ''));
    // Solo negro si es exactamente 0
    if (numValue === 0) return 'delta-neutral';
    // Siempre verde o rojo para cualquier cambio, sin importar magnitud
    if (numValue > 0) return 'delta-positive';
    if (numValue < 0) return 'delta-negative';
    return '';
}

/**
 * Obtiene la clase CSS para deltas de posición (lógica invertida)
 * @param {string} value - Valor del delta de posición
 * @returns {string} - Clase CSS
 */
function getDeltaClassPosition(value) {
    if (!value || value === '-' || value === '0' || value === '0,0') return 'delta-neutral';
    
    // Parsear el valor numérico limpiando formato español
    let cleanValue = value.toString().replace(/[+\s]/g, '');
    if (cleanValue.includes(',')) {
        cleanValue = cleanValue.replace(',', '.');
    }
    const numValue = parseFloat(cleanValue);
    
    if (isNaN(numValue) || numValue === 0) return 'delta-neutral';
    
    // Para posiciones: negativo = mejora (verde), positivo = empeora (rojo)
    if (numValue > 0) return 'delta-negative'; // Empeora posición = rojo
    if (numValue < 0) return 'delta-positive'; // Mejora posición = verde
    return '';
}

// Funciones globales para eventos
window.urlKeywordsGrid = {
    openSerpModal: (keyword) => {
        console.log('🔍 Opening SERP modal for keyword:', keyword);
        if (window.openSerpModal) {
            openSerpModal(keyword, '');
        } else {
            console.warn('⚠️ SERP modal function not available');
        }
    }
};

console.log('📦 URL Keywords Grid.js module loaded');