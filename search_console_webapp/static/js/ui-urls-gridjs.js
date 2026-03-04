// static/js/ui-urls-gridjs.js - Tabla Grid.js para URLs del panel principal

import { formatInteger, formatPercentage, formatPercentageChange, formatPosition, formatPositionDelta, formatAbsoluteDelta, calculateAbsoluteDelta, parsePositionValue, parseIntegerValue, parseNumericValue } from './number-utils.js';

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

    // Pre-sort data by Clicks P1 (index 2) descending — most reliable default sort
    data.sort((a, b) => parseIntegerValue(b[2]) - parseIntegerValue(a[2]));

    // Crear instancia de Grid.js
    const grid = new gridjs.Grid({
        columns: columns,
        data: data,
        pagination: {
            limit: 10
        },
        sort: true, // ✅ CAMBIADO: Simplificar para evitar conflictos
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
        
        console.log('✅ [URLs] Data pre-sorted by Clicks P1 (desc) before render');
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
            id: 'keywords_btn',
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
            id: 'url',
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
            id: 'clicks_p1',
            name: gridjs.html('Clicks<br>P1'),
            width: '100px',
            sort: {
                compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
            }
        }
    ];

    // Añadir columnas según el tipo de análisis
    if (analysisType === 'comparison') {
        columns.push(
            {
                id: 'clicks_p2',
                name: gridjs.html('Clicks<br>P2'),
                width: '100px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            {
                id: 'delta_clicks',
                name: gridjs.html('ΔClicks'),
                width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            }
        );
    }

    columns.push(
        {
            id: 'impressions_p1',
            name: gridjs.html('Impressions<br>P1'),
            width: '120px',
            sort: {
                compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
            }
        }
    );

    if (analysisType === 'comparison') {
        columns.push(
            {
                id: 'impressions_p2',
                name: gridjs.html('Impressions<br>P2'),
                width: '120px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            {
                id: 'delta_impressions',
                name: gridjs.html('ΔImp.'),
                width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            }
        );
    }

    columns.push(
        {
            id: 'ctr_p1',
            name: gridjs.html('CTR<br>P1 (%)'),
            width: '100px',
            sort: {
                compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
            }
        }
    );

    if (analysisType === 'comparison') {
        columns.push(
            {
                id: 'ctr_p2',
                name: gridjs.html('CTR<br>P2 (%)'),
                width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }
            },
            {
                id: 'delta_ctr',
                name: gridjs.html('ΔCTR'),
                width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            }
        );
    }

    columns.push(
        {
            id: 'position_p1',
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

    if (analysisType === 'comparison') {
        columns.push(
            {
                id: 'position_p2',
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
                id: 'delta_position',
                name: gridjs.html('ΔPos'),
                width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaPositionImproved(a, b) // New → negativo → 0 → positivo
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
            rowData.push(calculateAbsoluteDelta(row.clicks_p1 ?? 0, row.clicks_p2 ?? 0, 'clicks'));
        }
        
        rowData.push(formatInteger(row.impressions_p1 ?? 0));
        
        if (analysisType === 'comparison') {
            rowData.push(formatInteger(row.impressions_p2 ?? 0));
            rowData.push(calculateAbsoluteDelta(row.impressions_p1 ?? 0, row.impressions_p2 ?? 0, 'impressions'));
        }
        
        rowData.push(formatPercentage(row.ctr_p1));
        
        if (analysisType === 'comparison') {
            rowData.push(formatPercentage(row.ctr_p2));
            rowData.push(calculateAbsoluteDelta(row.ctr_p1 ?? 0, row.ctr_p2 ?? 0, 'ctr'));
        }
        
        // ✅ NUEVO: Pasar valores numéricos para posiciones (0 en lugar de N/A)
        const pos1 = (row.position_p1 == null || isNaN(row.position_p1)) ? 0 : Number(row.position_p1);
        rowData.push(pos1);
        
        if (analysisType === 'comparison') {
            const pos2 = (row.position_p2 == null || isNaN(row.position_p2)) ? 0 : Number(row.position_p2);
            rowData.push(pos2);
            // Calcular delta usando los valores reales (0 para N/A)
            rowData.push(calculateAbsoluteDelta(pos1, pos2, 'position'));
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
    
    // ✅ NUEVA: Identificar URLs nuevas (verde como mejoras)
    if (value === 'New' || value === 'Infinity' || (typeof value === 'string' && value.includes('New'))) {
        return 'delta-positive';
    }
    
    // ✅ NUEVA: Identificar URLs perdidas (rojo como empeoramientos)
    if (value === 'Lost' || (typeof value === 'string' && value.includes('Lost'))) {
        return 'delta-negative';
    }
    
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

// ✅ ELIMINADA: Función local parseNumericValue() duplicada
// Ahora usamos la versión correcta importada desde number-utils.js

/**
 * Compara valores de delta para ordenamiento MEJORADO con DEBUG
 * Orden: Mayor mejora → menor mejora → 0 → menor pérdida → mayor pérdida
 * @param {*} a - Primer valor
 * @param {*} b - Segundo valor  
 * @returns {number} - Resultado de comparación
 */
function compareDeltaValuesImproved(a, b) {
    const valA = String(a || '');
    const valB = String(b || '');
    
    // Manejar valores especiales
    const isNewA = valA === 'New' || valA.includes('New') || valA.includes('Nuevo');
    const isNewB = valB === 'New' || valB.includes('New') || valB.includes('Nuevo');
    const isLostA = valA === 'Lost' || valA.includes('Lost') || valA.includes('Perdido');
    const isLostB = valB === 'Lost' || valB.includes('Lost') || valB.includes('Perdido');
    
    // New va al final del ordenamiento (mejor caso)
    if (isNewA && !isNewB) return 1;
    if (!isNewA && isNewB) return -1;
    if (isNewA && isNewB) return 0;
    
    // Lost va al final (peor caso, después de New)
    if (isLostA && !isLostB) return 1;
    if (!isLostA && isLostB) return -1;
    if (isLostA && isLostB) return 0;
    
    // Para valores numéricos: parsear y comparar
    const numA = parseNumericValue(valA);
    const numB = parseNumericValue(valB);
    
    // Debug logging (comentar en producción)
    if (window.debugSort) {
        console.log(`🔍 Comparando: "${valA}" (${numA}) vs "${valB}" (${numB}) → ${numB - numA}`);
    }
    
    // Ordenar de mayor a menor: +300% → +150% → +100% → 0% → -5% → -30% → -80%
    return numB - numA;
}

/**
 * Compara valores de delta de posición para ordenamiento MEJORADO (lógica invertida)
 * Orden: New → mejor mejora (más negativo) → 0 → peor empeoramiento (más positivo)
 * @param {*} a - Primer valor
 * @param {*} b - Segundo valor
 * @returns {number} - Resultado de comparación
 */
function compareDeltaPositionImproved(a, b) {
    const valA = String(a || '');
    const valB = String(b || '');
    
    // Manejar valores especiales
    const isNewA = valA === 'New' || valA.includes('New');
    const isNewB = valB === 'New' || valB.includes('New');
    const isLostA = valA === 'Lost' || valA.includes('Lost');
    const isLostB = valB === 'Lost' || valB.includes('Lost');
    
    // New va primero (mejor caso para posiciones)
    if (isNewA && !isNewB) return -1;
    if (!isNewA && isNewB) return 1;
    if (isNewA && isNewB) return 0;
    
    // Lost va al final
    if (isLostA && !isLostB) return 1;
    if (!isLostA && isLostB) return -1;
    if (isLostA && isLostB) return 0;
    
    // Para posiciones: negativo es mejor, positivo es peor
    // Orden: -70 → -40 → -10 → 0 → +2 → +10 → +30
    const numA = parseNumericValue(valA);
    const numB = parseNumericValue(valB);
    
    return numA - numB; // Orden ascendente: más negativo primero
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