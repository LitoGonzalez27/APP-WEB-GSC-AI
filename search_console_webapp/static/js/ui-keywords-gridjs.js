// static/js/ui-keywords-gridjs.js - Tabla Grid.js para Keywords del panel principal

import { formatInteger, formatPercentage, formatPercentageChange, formatPosition, formatPositionDelta } from './number-utils.js';

/**
 * Crea y renderiza la tabla Grid.js de Keywords
 * @param {Array} keywordsData - Datos de keywords procesados
 * @param {string} analysisType - Tipo de análisis ('single' o 'comparison')
 * @param {HTMLElement} container - Contenedor donde renderizar la tabla
 * @returns {Object|null} Instancia de Grid.js o null si hay error
 */
export function createKeywordsGridTable(keywordsData, analysisType = 'comparison', container) {
    console.log('🏗️ Creating Keywords Grid.js table with:', {
        keywords: keywordsData?.length || 0,
        analysisType: analysisType
    });

    if (!container) {
        console.error('❌ No container provided for Keywords Grid.js table');
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
    const { columns, data } = processKeywordsDataForGrid(keywordsData, analysisType);

    // Limpiar contenedor completamente
    container.innerHTML = '';
    
    // Crear contenedor para la tabla
    const tableContainer = document.createElement('div');
    tableContainer.className = 'ai-overview-grid-container';
    
    const gridContainer = document.createElement('div');
    gridContainer.id = `keywords-grid-table-${Date.now()}`; // ID único para evitar conflictos
    gridContainer.className = 'ai-overview-grid-wrapper';
    
    tableContainer.appendChild(gridContainer);
    container.appendChild(tableContainer);

    // Crear instancia de Grid.js
    const grid = new gridjs.Grid({
        columns: columns,
        data: data,
        sort: {
            multiColumn: false,
            sortColumn: analysisType === 'comparison' ? 2 : 2, // Clicks P1 siempre (índice 2)
            sortDirection: 'desc' // De mayor a menor
        },
        search: {
            enabled: true,
            placeholder: 'Search keywords...'
        },
        pagination: {
            enabled: true,
            limit: 10,
            summary: true
        },
        language: {
            search: {
                placeholder: 'Search keywords...'
            },
            pagination: {
                previous: '←',
                next: '→',
                showing: 'Showing',
                of: 'of',
                to: 'to',
                results: 'results'
            },
            noRecordsFound: 'No keywords found',
            error: 'Error loading keywords data'
        },
        resizable: true,
        fixedHeader: true,
        height: '600px',
        style: {
            table: {
                'font-size': '14px',
                'border-collapse': 'collapse'
            },
            th: {
                'background-color': 'var(--card-bg)',
                'color': 'var(--heading)',
                'border-bottom': '2px solid var(--border-color)',
                'padding': '12px 8px',
                'text-align': 'left',
                'font-weight': '600',
                'font-size': '13px',
                'white-space': 'nowrap'
            },
            td: {
                'padding': '10px 8px',
                'border-bottom': '1px solid var(--border-color)',
                'color': 'var(--text-color)',
                'vertical-align': 'middle'
            },
            header: {
                'background-color': 'var(--card-bg)',
                'border-bottom': '1px solid var(--border-color)',
                'color': 'var(--text-color)'
            },
            footer: {
                'background-color': 'var(--card-bg)',
                'border-top': '1px solid var(--border-color)',
                'color': 'var(--text-color)'
            }
        },
        className: {
            table: 'keywords-grid-table',
            th: 'keywords-grid-th',
            td: 'keywords-grid-td'
        }
    });

    try {
        grid.render(gridContainer);
        console.log('✅ Keywords Grid.js table rendered successfully');
        
        // Forzar ordenamiento por Clicks P1 después del render (igual que URLs)
        setTimeout(() => {
            try {
                const clicksHeader = gridContainer.querySelector('th:nth-child(3)'); // Columna Clicks P1
                if (clicksHeader) {
                    // Simular dos clicks para ordenar descendente (mayor a menor)
                    clicksHeader.click();
                    setTimeout(() => clicksHeader.click(), 50);
                    console.log('🔄 Ordenamiento por Clicks P1 (desc) aplicado');
                }
            } catch (sortError) {
                console.warn('⚠️ No se pudo aplicar ordenamiento automático:', sortError);
            }
        }, 100);
        
        return grid;
    } catch (error) {
        console.error('❌ Error rendering Keywords Grid.js table:', error);
        displayErrorMessage(container);
        return null;
    }
}

/**
 * Procesa los datos de keywords para Grid.js
 * @param {Array} keywordsData - Datos de keywords
 * @param {string} analysisType - Tipo de análisis ('single' o 'comparison')
 * @returns {Object} Objeto con columns y data para Grid.js
 */
function processKeywordsDataForGrid(keywordsData, analysisType) {
    console.log('🔄 Processing keywords data for Grid.js:', { 
        count: keywordsData.length, 
        analysisType 
    });

    // Definir columnas base
    const baseColumns = [
        {
            id: 'serp',
            name: 'View SERP',
            width: '80px',
            sort: false,
            formatter: (cell, row) => {
                const keyword = row.cells[1].data; // Obtener keyword de la columna siguiente
                return gridjs.html(`
                    <button class="serp-btn" 
                            onclick="window.keywordsGrid.openSerpModal('${escapeForAttribute(keyword)}')"
                            title="View SERP for: ${escapeForAttribute(keyword)}">
                        <i class="fas fa-search"></i>
                    </button>
                `);
            }
        },
        {
            id: 'keyword',
            name: 'Keyword',
            width: '200px',
            formatter: (cell) => gridjs.html(`<span class="keyword-text">${escapeHtml(cell)}</span>`)
        }
    ];

    // Definir columnas según el tipo de análisis
    let columns, dataColumns;
    
    if (analysisType === 'single') {
        columns = [
            ...baseColumns,
            { id: 'clicks', name: 'Clicks', width: '100px', 
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                },
                formatter: (cell) => formatInteger(cell) 
            },
            { id: 'impressions', name: 'Impressions', width: '120px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatInteger(cell) 
            },
            { id: 'ctr', name: 'CTR (%)', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatPercentage(cell) 
            },
            { id: 'position', name: 'Position', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor (50 → 0.1)
                }, 
                formatter: (cell) => formatPosition(cell) 
            }
        ];
        
        dataColumns = ['serp', 'keyword', 'clicks_m1', 'impressions_m1', 'ctr_m1', 'position_m1'];
    } else {
        columns = [
            ...baseColumns,
            { id: 'clicks_p1', name: 'Clicks P1', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatInteger(cell) 
            },
            { id: 'clicks_p2', name: 'Clicks P2', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatInteger(cell) 
            },
            { id: 'delta_clicks', name: 'ΔClicks (%)', width: '120px', 
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                },
                formatter: (cell) => {
                    const formatted = formatPercentageChange(cell);
                    return gridjs.html(`<span class="${getDeltaClass(formatted)}">${formatted}</span>`);
                } 
            },
            { id: 'impressions_p1', name: 'Impressions P1', width: '120px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatInteger(cell) 
            },
            { id: 'impressions_p2', name: 'Impressions P2', width: '120px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatInteger(cell) 
            },
            { id: 'delta_impressions', name: 'ΔImp. (%)', width: '120px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                }, 
                formatter: (cell) => {
                    const formatted = formatPercentageChange(cell);
                    return gridjs.html(`<span class="${getDeltaClass(formatted)}">${formatted}</span>`);
                } 
            },
            { id: 'ctr_p1', name: 'CTR P1 (%)', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatPercentage(cell) 
            },
            { id: 'ctr_p2', name: 'CTR P2 (%)', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }, 
                formatter: (cell) => formatPercentage(cell) 
            },
            { id: 'delta_ctr', name: 'ΔCTR (%)', width: '120px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                }, 
                formatter: (cell) => {
                    const formatted = formatPercentageChange(cell, true);
                    return gridjs.html(`<span class="${getDeltaClass(formatted)}">${formatted}</span>`);
                } 
            },
            { id: 'pos_p1', name: 'Pos P1', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor (50 → 0.1)
                }, 
                formatter: (cell) => formatPosition(cell) 
            },
            { id: 'pos_p2', name: 'Pos P2', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor (50 → 0.1)
                }, 
                formatter: (cell) => formatPosition(cell) 
            },
            { id: 'delta_pos', name: 'ΔPos', width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaPositionImproved(a, b) // New → negativo → 0 → positivo
                }, 
                formatter: (cell, row) => {
                    // Acceder a las posiciones usando el índice correcto en la fila
                    const pos1 = row.cells && row.cells[11] ? row.cells[11].data : null;  // position_m1 (índice 11)
                    const pos2 = row.cells && row.cells[12] ? row.cells[12].data : null; // position_m2 (índice 12)
                    const formatted = formatPositionDelta(cell, pos1, pos2);
                    return gridjs.html(`<span class="${getDeltaClassPosition(formatted)}">${formatted}</span>`);
                } 
            }
        ];
        
        dataColumns = [
            'serp', 'keyword', 'clicks_m1', 'clicks_m2', 'delta_clicks_percent',
            'impressions_m1', 'impressions_m2', 'delta_impressions_percent',
            'ctr_m1', 'ctr_m2', 'delta_ctr_percent',
            'position_m1', 'position_m2', 'delta_position_absolute'
        ];
    }

    // Procesar datos
    const data = keywordsData.map(keyword => {
        const row = [];
        
        dataColumns.forEach(col => {
            if (col === 'serp') {
                row.push(''); // Placeholder para el botón SERP
            } else if (col === 'keyword') {
                row.push(keyword.query || keyword.keyword || '');
            } else {
                // Obtener valor del keyword object
                let value = keyword[col];
                
                // Manejar valores especiales
                if (value === null || value === undefined || value === '') {
                    if (col.includes('delta_')) {
                        value = analysisType === 'comparison' ? (col === 'delta_position_absolute' ? '-' : '0%') : 'New';
                    } else if (col.includes('_m2')) {
                        value = analysisType === 'comparison' ? 0 : '';
                    } else {
                        value = 0;
                    }
                }
                
                // ✅ NUEVO: Preservar valores 'New' y 'Lost' explícitos para deltas
                if (typeof value === 'string' && (value === 'New' || value === 'Lost') && col.includes('delta_')) {
                    // Mantener el valor 'New' o 'Lost' tal como está
                } else {
                    // Validar tipos de datos específicos
                    if (col.includes('position') && value !== '-' && value !== '' && value !== null) {
                        value = parseFloat(value) || 0;
                    }
                    if (col.includes('clicks') || col.includes('impressions')) {
                        value = parseInt(value) || 0;
                    }
                    if (col.includes('ctr')) {
                        value = parseFloat(value) || 0;
                    }
                }
                
                row.push(value);
            }
        });
        
        return row;
    });

    console.log('✅ Keywords data processed for Grid.js:', { 
        columns: columns.length, 
        rows: data.length 
    });

    return { columns, data };
}

/**
 * Muestra mensaje cuando no hay keywords
 */
function displayNoKeywordsMessage(container) {
    container.innerHTML = `
        <div class="no-aio-message">
            <i class="fas fa-search"></i>
            <h3>No Keywords Found</h3>
            <p>No keyword data available to display for the selected period.</p>
        </div>
    `;
}

/**
 * Muestra mensaje de error
 */
function displayErrorMessage(container) {
    container.innerHTML = `
        <div class="no-aio-message">
            <i class="fas fa-exclamation-triangle"></i>
            <h3>Error Loading Keywords</h3>
            <p>There was an error loading the keywords table. Please try refreshing the page.</p>
        </div>
    `;
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Escapa atributos HTML para prevenir XSS
 */
function escapeForAttribute(text) {
    return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * Obtiene la clase CSS para deltas
 * @param {string} value - Valor del delta
 * @returns {string} - Clase CSS
 */
function getDeltaClass(value) {
    if (!value || value === '-') return '';
    
    // ✅ NUEVA: Identificar keywords nuevas (verde como mejoras)
    if (value === 'New' || value === 'Infinity' || (typeof value === 'string' && value.includes('New'))) {
        return 'delta-positive';
    }
    
    // ✅ NUEVA: Identificar keywords perdidas (rojo como empeoramientos)
    if (value === 'Lost' || (typeof value === 'string' && value.includes('Lost'))) {
        return 'delta-negative';
    }
    
    const numValue = parseFloat(value.toString().replace(/[%+]/g, ''));
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
    
    // ✅ NUEVA: Identificar keywords nuevas en posiciones (verde como mejoras)
    if (value === 'New' || value === 'Infinity' || (typeof value === 'string' && value.includes('New'))) {
        return 'delta-positive';
    }
    
    // ✅ NUEVA: Identificar keywords perdidas en posiciones (rojo como empeoramientos)
    if (value === 'Lost' || (typeof value === 'string' && value.includes('Lost'))) {
        return 'delta-negative';
    }
    
    const numValue = parseFloat(value.toString().replace(/[%+]/g, ''));
    // Solo negro si es exactamente 0
    if (numValue === 0) return 'delta-neutral';
    // Para posiciones: negativo = mejora (verde), positivo = empeora (rojo)
    if (numValue > 0) return 'delta-negative'; // Empeora posición = rojo
    if (numValue < 0) return 'delta-positive'; // Mejora posición = verde
    return '';
}

/**
 * Función auxiliar para parsear valores numéricos de strings formateados (MEJORADA)
 * @param {*} value - Valor a parsear
 * @returns {number} - Número parseado
 */
function parseNumericValue(value) {
    if (value === null || value === undefined || value === '' || value === '-') return 0;
    if (typeof value === 'number') return value;
    
    let str = String(value).trim();
    
    // Manejar casos especiales
    if (str === 'New' || str.includes('New') || str.includes('Nuevo')) return Infinity;
    if (str === 'Lost' || str.includes('Lost') || str.includes('Perdido')) return -Infinity;
    if (str.includes('∞')) return str.includes('+') ? Infinity : -Infinity;
    
    // Limpiar HTML tags si existen
    str = str.replace(/<[^>]*>/g, '');
    
    // Preservar el signo negativo
    const isNegative = str.startsWith('-');
    
    // Remover todos los símbolos excepto números y separadores decimales
    str = str.replace(/[^\d,.]/g, '');
    
    // Manejar formato español: si hay tanto punto como coma, el último es decimal
    if (str.includes('.') && str.includes(',')) {
        const lastDot = str.lastIndexOf('.');
        const lastComma = str.lastIndexOf(',');
        
        if (lastComma > lastDot) {
            // Coma es decimal: 1.234,56 → 1234.56
            str = str.replace(/\./g, '').replace(',', '.');
        } else {
            // Punto es decimal: 1,234.56 → 1234.56
            str = str.replace(/,/g, '');
        }
    } else if (str.includes(',')) {
        // Solo coma: asumir decimal español: 5,67 → 5.67
        const commaCount = (str.match(/,/g) || []).length;
        if (commaCount === 1) {
            str = str.replace(',', '.');
        } else {
            // Múltiples comas: separadores de miles
            str = str.replace(/,/g, '');
        }
    }
    
    const num = parseFloat(str);
    const result = isNaN(num) ? 0 : (isNegative ? -Math.abs(num) : num);
    
    return result;
}

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

// Exportar funciones globales para uso en onclick handlers
window.keywordsGrid = {
    openSerpModal: function(keyword) {
        console.log('🔍 Opening SERP modal for keyword:', keyword);
        // Importar dinámicamente para evitar dependencias circulares
        import('./ui-serp-modal.js').then(module => {
            module.openSerpModal(keyword);
        }).catch(error => {
            console.error('❌ Error loading SERP modal:', error);
        });
    },
    
    // Funciones de debug para el ordenamiento
    debugSort: {
        enable: () => {
            window.debugSort = true;
            console.log('🔍 Debug de ordenamiento ACTIVADO');
        },
        disable: () => {
            window.debugSort = false;
            console.log('🔍 Debug de ordenamiento DESACTIVADO');
        },
        test: (values) => {
            console.log('🧪 Probando ordenamiento de deltas...');
            const testValues = values || ['-0,39%', '-2,29%', '-23,33%', '-1,59%', '-8,93%', '-0,38%', '-1,27%', '-5,71%'];
            const parsed = testValues.map(v => ({ original: v, parsed: parseNumericValue(v) }));
            const sorted = [...parsed].sort((a, b) => compareDeltaValuesImproved(a.original, b.original));
            
            console.table(parsed);
            console.log('📊 Orden correcto (de menor pérdida a mayor pérdida):');
            sorted.forEach((item, index) => {
                console.log(`${index + 1}. ${item.original} (${item.parsed})`);
            });
            
            return sorted;
        }
    }
};

console.log('📦 Keywords Grid.js module loaded');