// static/js/ui-urls-gridjs.js - Tabla Grid.js para URLs del panel principal

import { formatInteger, formatPercentage, formatPercentageChange, formatPosition, formatPositionDelta } from './number-utils.js';

/**
 * Crea y renderiza la tabla Grid.js de URLs
 * @param {Array} urlsData - Datos de URLs procesados
 * @param {string} analysisType - Tipo de análisis ('single' o 'comparison')
 * @param {HTMLElement} container - Contenedor donde renderizar la tabla
 * @returns {Object|null} Instancia de Grid.js o null si hay error
 */
export function createUrlsGridTable(urlsData, analysisType = 'comparison', container) {
    console.log('🏗️ Creating URLs Grid.js table with:', {
        urls: urlsData?.length || 0,
        analysisType: analysisType
    });

    if (!container) {
        console.error('❌ No container provided for URLs Grid.js table');
        return null;
    }

    if (!window.gridjs) {
        console.error('❌ Grid.js library not loaded');
        return null;
    }

    if (!urlsData || urlsData.length === 0) {
        displayNoUrlsMessage(container);
        return null;
    }

    // Procesar datos para Grid.js
    const { columns, data } = processUrlsDataForGrid(urlsData, analysisType);

    // Crear contenedor para la tabla
    const tableContainer = document.createElement('div');
    tableContainer.className = 'ai-overview-grid-container';
    tableContainer.innerHTML = `
        <div id="urls-grid-table" class="ai-overview-grid-wrapper"></div>
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
            sortColumn: 2, // Columna Clics P1 (índice 2)
            sortDirection: 'desc' // De mayor a menor
        },
        search: {
            placeholder: 'Type an URL...'
        },
        language: {
            search: {
                placeholder: 'Type an URL...'
            }
        },
        resizable: true,
        style: {
            table: {
                'white-space': 'nowrap'
            }
        }
    });

    // Renderizar la tabla
    try {
        grid.render(document.getElementById('urls-grid-table'));
        console.log('✅ URLs Grid.js table rendered successfully');
        
        // Forzar ordenamiento por Clics P1 después del render
        setTimeout(() => {
            try {
                // Grid.js usa eventos de click en los headers para ordenar
                const gridContainer = document.getElementById('urls-grid-table');
                if (gridContainer) {
                    const clicksHeader = gridContainer.querySelector('th:nth-child(3)'); // Columna Clics P1
                    if (clicksHeader) {
                        // Simular dos clicks para ordenar descendente (mayor a menor)
                        clicksHeader.click();
                        setTimeout(() => clicksHeader.click(), 50);
                        console.log('🔄 Ordenamiento por Clics P1 (desc) aplicado');
                    }
                }
            } catch (sortError) {
                console.warn('⚠️ No se pudo aplicar ordenamiento automático:', sortError);
            }
        }, 100);
        
        return grid;
    } catch (error) {
        console.error('❌ Error rendering URLs Grid.js table:', error);
        return null;
    }
}

/**
 * Procesa los datos de URLs para Grid.js
 * @param {Array} urlsData - Datos de URLs
 * @param {string} analysisType - Tipo de análisis
 * @returns {Object} Objeto con columnas y datos para Grid.js
 */
function processUrlsDataForGrid(urlsData, analysisType) {
    // Definir columnas base
    const columns = [
        {
            name: 'Keywords',
            width: '80px',
            sort: false,
            formatter: (cell, row) => {
                const url = row.cells[1].data; // La URL está en la segunda columna
                return gridjs.html(`
                    <div style="display: flex; justify-content: center; align-items: center; height: 100%;">
                        <button 
                            class="serp-view-btn" 
                            onclick="window.urlsGrid.openKeywordsModal('${escapeForAttribute(url)}')"
                            title="Ver keywords para esta URL"
                        >
                            <i class="fas fa-list"></i>
                        </button>
                    </div>
                `);
            }
        },
        {
            name: 'URL',
            width: '350px',
            sort: true,
            formatter: (cell) => {
                // Separar la URL en dos líneas más legibles
                let formattedUrl = escapeForAttribute(cell);
                let displayUrl = formattedUrl;
                
                // Si la URL es muy larga, separarla en dos líneas
                if (formattedUrl.length > 50) {
                    // Buscar un punto de corte lógico (después de .com/, .es/, etc.)
                    const breakPoints = ['/', '?', '&', '#'];
                    let breakIndex = -1;
                    
                    for (let i = 30; i < Math.min(formattedUrl.length, 60); i++) {
                        if (breakPoints.includes(formattedUrl[i])) {
                            breakIndex = i + 1;
                            break;
                        }
                    }
                    
                    if (breakIndex > 0) {
                        const firstLine = formattedUrl.substring(0, breakIndex);
                        const secondLine = formattedUrl.substring(breakIndex);
                        displayUrl = `${firstLine}<br/><span style="opacity: 0.7; font-size: 0.9em;">${secondLine}</span>`;
                    }
                }
                
                return gridjs.html(`
                    <div class="url-cell" title="${escapeForAttribute(cell)}" style="
                        max-width: 330px;
                        white-space: normal;
                        line-height: 1.3;
                        word-break: break-all;
                        overflow: hidden;
                        display: -webkit-box;
                        -webkit-line-clamp: 2;
                        -webkit-box-orient: vertical;
                    ">
                        ${displayUrl}
                    </div>
                `);
            }
        },
        {
            name: gridjs.html('Clicks<br>P1'),
            width: '100px',
            sort: {
                compare: (a, b) => {
                    return parseInteger(a) - parseInteger(b);
                }
            }
        }
    ];

    // Añadir columnas según el tipo de análisis
    if (analysisType === 'comparison') {
        columns.push(
            {
                name: gridjs.html('Clicks<br>P2'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseInteger(a) - parseInteger(b);
                    }
                }
            },
            {
                name: gridjs.html('ΔClicks<br>(%)'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parsePercentageForSort(a) - parsePercentageForSort(b);
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
                    return parseInteger(a) - parseInteger(b);
                }
            }
        }
    );

    if (analysisType === 'comparison') {
        columns.push(
            {
                name: gridjs.html('Impressions<br>P2'),
                width: '120px',
                sort: {
                    compare: (a, b) => {
                        return parseInteger(a) - parseInteger(b);
                    }
                }
            },
            {
                name: gridjs.html('ΔImp.<br>(%)'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parsePercentageForSort(a) - parsePercentageForSort(b);
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
                    return parsePercentageForSort(a) - parsePercentageForSort(b);
                }
            }
        }
    );

    if (analysisType === 'comparison') {
        columns.push(
            {
                name: gridjs.html('CTR<br>P2 (%)'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parsePercentageForSort(a) - parsePercentageForSort(b);
                    }
                }
            },
            {
                name: gridjs.html('ΔCTR<br>(%)'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parsePercentageForSort(a) - parsePercentageForSort(b);
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
            sort: {
                compare: (a, b) => {
                    return parseFloat(a) - parseFloat(b);
                }
            }
        }
    );

    if (analysisType === 'comparison') {
        columns.push(
            {
                name: gridjs.html('Position<br>P2'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseFloat(a) - parseFloat(b);
                    }
                }
            },
            {
                name: gridjs.html('ΔPos'),
                width: '100px',
                sort: {
                    compare: (a, b) => {
                        return parseFloat(a) - parseFloat(b);
                    }
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClassPosition(cell)}">${cell}</span>`);
                }
            }
        );
    }

    // Procesar datos
    const data = urlsData.map(row => {
        const rowData = [
            '', // Columna de keywords (será reemplazada por el formatter)
            row.url || ''
        ];

        // Añadir datos según el tipo de análisis
        rowData.push(formatInteger(row.clicks_p1 ?? 0));
        
        if (analysisType === 'comparison') {
            rowData.push(formatInteger(row.clicks_p2 ?? 0));
            rowData.push(formatPercentageChange(row.delta_clicks_percent));
        }
        
        rowData.push(formatInteger(row.impressions_p1 ?? 0));
        
        if (analysisType === 'comparison') {
            rowData.push(formatInteger(row.impressions_p2 ?? 0));
            rowData.push(formatPercentageChange(row.delta_impressions_percent));
        }
        
        rowData.push(formatPercentage(row.ctr_p1));
        
        if (analysisType === 'comparison') {
            rowData.push(formatPercentage(row.ctr_p2));
            rowData.push(formatPercentageChange(row.delta_ctr_percent, true));
        }
        
        rowData.push(formatPosition(row.position_p1));
        
        if (analysisType === 'comparison') {
            rowData.push(formatPosition(row.position_p2));
            rowData.push(formatPositionDelta(row.delta_position_absolute, row.position_p1, row.position_p2));
        }

        return rowData;
    });

    return { columns, data };
}

/**
 * Muestra mensaje cuando no hay URLs
 * @param {HTMLElement} container - Contenedor
 */
function displayNoUrlsMessage(container) {
    container.innerHTML = `
        <div class="no-aio-message">
            <i class="fas fa-info-circle"></i>
            <h3>No URLs Found</h3>
            <p>No URL data available to display for the selected period.</p>
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
 * Función auxiliar para parsear porcentajes para ordenamiento
 * @param {string} str - String con porcentaje
 * @returns {number} - Número parseado
 */
function parsePercentageForSort(str) {
    if (!str || str === '-' || str === '0%') return 0;
    return parseFloat(str.replace(/[%+]/g, '')) || 0;
}

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
    if (!value || value === '-') return '';
    const numValue = parseFloat(value.replace(/[%+]/g, ''));
    // Solo negro si es exactamente 0
    if (numValue === 0) return 'delta-neutral';
    // Para posiciones: negativo = mejora (verde), positivo = empeora (rojo)
    if (numValue > 0) return 'delta-negative'; // Empeora posición = rojo
    if (numValue < 0) return 'delta-positive'; // Mejora posición = verde
    return '';
}

// Funciones globales para eventos
window.urlsGrid = {
    openKeywordsModal: (url) => {
        console.log('🔍 Opening keywords modal for URL:', url);
        // Buscar la función en el scope global donde está definida
        if (typeof window.openUrlKeywordsModal === 'function') {
            window.openUrlKeywordsModal(url);
        } else {
            // Fallback: buscar en el módulo ui-render
            const uiRenderModule = window.uiRender || {};
            if (typeof uiRenderModule.openUrlKeywordsModal === 'function') {
                uiRenderModule.openUrlKeywordsModal(url);
            } else {
                console.warn('⚠️ URLs keywords modal function not available');
            }
        }
    }
};

console.log('📦 URLs Grid.js module loaded');