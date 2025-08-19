// static/js/ui-keywords-gridjs.js - Tabla Grid.js para Keywords del panel principal

import { formatInteger, formatPercentage, formatPercentageChange, formatPosition, formatPositionDelta, formatAbsoluteDelta, calculateAbsoluteDelta, parsePositionValue, parseIntegerValue, parseNumericValue } from './number-utils.js';

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

    // Crear contenedor para la tabla con ID único y consistente
    const uniqueId = `keywords-grid-table-${Date.now()}`;
    const tableContainer = document.createElement('div');
    tableContainer.className = 'ai-overview-grid-container';
    tableContainer.innerHTML = `
        <div id="${uniqueId}" class="ai-overview-grid-wrapper keywords-grid-wrapper"></div>
    `;
    
    // Limpiar contenedor y añadir nueva tabla
    container.innerHTML = '';
    container.appendChild(tableContainer);

    // Crear instancia de Grid.js
    const grid = new gridjs.Grid({
        columns: columns,
        data: data,
        sort: true, // ✅ MEJORADO: Simplificar para evitar conflictos (igual que URLs)
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
        const gridElement = document.getElementById(uniqueId);
        if (!gridElement) {
            console.error('❌ Grid container not found for keywords table');
            return null;
        }
        
        grid.render(gridElement);
        console.log('✅ Keywords Grid.js table rendered successfully');
        
        // ✅ MEJORADO: Aplicar ordenamiento con delay mayor para evitar conflictos
        setTimeout(() => {
            try {
                // Verificar que la grid aún existe y está renderizada
                if (grid && grid.config && grid.config.data) {
                    grid.updateConfig({
                        sort: {
                            multiColumn: false,
                            sortColumn: 2, // Clicks P1 siempre (índice 2)
                            sortDirection: 'desc' // De mayor a menor
                        }
                    }).forceRender();
                    console.log('🔄 Keywords: Ordenamiento por Clics P1 (desc) aplicado programáticamente');
                }
            } catch (sortError) {
                console.warn('⚠️ Keywords: No se pudo aplicar ordenamiento automático:', sortError);
                // Fallback: usar clicks en header específico de esta tabla
                const specificContainer = document.getElementById(uniqueId);
                if (specificContainer) {
                    const clicksHeader = specificContainer.querySelector('th:nth-child(3)');
                    if (clicksHeader) {
                        clicksHeader.click();
                        setTimeout(() => clicksHeader.click(), 50);
                    }
                }
            }
        }, 800); // Delay mayor para evitar conflictos con URLs y modales
        
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
            { id: 'clicks_m1', name: 'Clicks', width: '100px', 
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'impressions_m1', name: 'Impressions', width: '120px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'ctr_m1', name: 'CTR (%)', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }
            },
            { id: 'position_m1', name: 'Position', width: '100px',
                sort: true, // Usar ordenamiento numérico nativo de Grid.js
                formatter: (cell) => {
                    // Formatear para display pero pasar valor numérico para sorting
                    if (cell === null || cell === undefined || cell === 0) return '0';
                    return formatPosition(cell);
                }
            }
        ];
        
        dataColumns = ['serp', 'keyword', 'clicks_m1', 'impressions_m1', 'ctr_m1', 'position_m1'];
    } else {
        columns = [
            ...baseColumns,
            { id: 'clicks_m1', name: gridjs.html('Clicks<br>P1'), width: '100px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'clicks_m2', name: gridjs.html('Clicks<br>P2'), width: '100px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'delta_clicks_percent', name: gridjs.html('ΔClicks'), width: '100px', 
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            },
            { id: 'impressions_m1', name: gridjs.html('Impressions<br>P1'), width: '120px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'impressions_m2', name: gridjs.html('Impressions<br>P2'), width: '120px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'delta_impressions_percent', name: gridjs.html('ΔImp.'), width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                }, 
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            },
            { id: 'ctr_m1', name: gridjs.html('CTR<br>P1 (%)'), width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }
            },
            { id: 'ctr_m2', name: gridjs.html('CTR<br>P2 (%)'), width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }
            },
            { id: 'delta_ctr_percent', name: gridjs.html('ΔCTR'), width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                }, 
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            },
            { id: 'position_m1', name: gridjs.html('Position<br>P1'), width: '100px',
                sort: true, // Usar ordenamiento numérico nativo de Grid.js
                formatter: (cell) => {
                    // Formatear para display pero pasar valor numérico para sorting
                    if (cell === null || cell === undefined || cell === 0) return '0';
                    return formatPosition(cell);
                }
            },
            { id: 'position_m2', name: gridjs.html('Position<br>P2'), width: '100px',
                sort: true, // Usar ordenamiento numérico nativo de Grid.js
                formatter: (cell) => {
                    // Formatear para display pero pasar valor numérico para sorting
                    if (cell === null || cell === undefined || cell === 0) return '0';
                    return formatPosition(cell);
                }
            },
            { id: 'delta_position_absolute', name: gridjs.html('ΔPos'), width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaPositionImproved(a, b) // New → negativo → 0 → positivo
                }, 
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClassPosition(cell)}">${cell}</span>`);
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

    // Procesar datos (igual que URLs)
    const data = keywordsData.map(keyword => {
        const rowData = [
            '', // Columna SERP (será reemplazada por el formatter)
            keyword.query || keyword.keyword || ''
        ];

        // Añadir datos según el tipo de análisis
        if (analysisType === 'single') {
            rowData.push(formatInteger(keyword.clicks_m1 ?? 0));
            rowData.push(formatInteger(keyword.impressions_m1 ?? 0));
            rowData.push(formatPercentage(keyword.ctr_m1));
            
            // ✅ NUEVO: Pasar valores numéricos para posiciones (0 en lugar de N/A)
            const pos1 = (keyword.position_m1 == null || isNaN(keyword.position_m1)) ? 0 : Number(keyword.position_m1);
            rowData.push(pos1);
        } else {
            // Comparison mode
            rowData.push(formatInteger(keyword.clicks_m1 ?? 0));
            rowData.push(formatInteger(keyword.clicks_m2 ?? 0));
            rowData.push(calculateAbsoluteDelta(keyword.clicks_m1 ?? 0, keyword.clicks_m2 ?? 0, 'clicks'));
            
            rowData.push(formatInteger(keyword.impressions_m1 ?? 0));
            rowData.push(formatInteger(keyword.impressions_m2 ?? 0));
            rowData.push(calculateAbsoluteDelta(keyword.impressions_m1 ?? 0, keyword.impressions_m2 ?? 0, 'impressions'));
            
            rowData.push(formatPercentage(keyword.ctr_m1));
            rowData.push(formatPercentage(keyword.ctr_m2));
            rowData.push(calculateAbsoluteDelta(keyword.ctr_m1 ?? 0, keyword.ctr_m2 ?? 0, 'ctr'));
            
            // ✅ NUEVO: Pasar valores numéricos para posiciones (0 en lugar de N/A)
            const pos1 = (keyword.position_m1 == null || isNaN(keyword.position_m1)) ? 0 : Number(keyword.position_m1);
            const pos2 = (keyword.position_m2 == null || isNaN(keyword.position_m2)) ? 0 : Number(keyword.position_m2);
            rowData.push(pos1);
            rowData.push(pos2);
            // Calcular delta usando los valores reales (0 para N/A)
            rowData.push(calculateAbsoluteDelta(pos1, pos2, 'position'));
        }

        return rowData;
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
 * Obtiene la clase CSS para deltas (igual que URLs)
 * @param {string} value - Valor del delta
 * @returns {string} - Clase CSS
 */
function getDeltaClass(value) {
    if (!value || value === '-') return '';
    
    // ✅ Identificar keywords nuevas (verde como mejoras)
    if (value === 'New' || value === 'Infinity' || (typeof value === 'string' && value.includes('New'))) {
        return 'delta-positive';
    }
    
    // ✅ Identificar keywords perdidas (rojo como empeoramientos)  
    if (value === 'Lost' || (typeof value === 'string' && value.includes('Lost'))) {
        return 'delta-negative';
    }
    
    const numValue = parseNumericValue(value);
    // Solo negro si es exactamente 0
    if (numValue === 0) return 'delta-neutral';
    // Siempre verde o rojo para cualquier cambio, sin importar magnitud
    if (numValue > 0) return 'delta-positive';
    if (numValue < 0) return 'delta-negative';
    return '';
}

/**
 * Obtiene la clase CSS para deltas de posición (lógica invertida igual que URLs)
 * @param {string} value - Valor del delta de posición
 * @returns {string} - Clase CSS
 */
function getDeltaClassPosition(value) {
    if (!value || value === '-') return '';
    
    // ✅ Identificar keywords nuevas en posiciones (verde como mejoras)
    if (value === 'New' || value === 'Infinity' || (typeof value === 'string' && value.includes('New'))) {
        return 'delta-positive';
    }
    
    // ✅ Identificar keywords perdidas en posiciones (rojo como empeoramientos)
    if (value === 'Lost' || (typeof value === 'string' && value.includes('Lost'))) {
        return 'delta-negative';
    }
    
    const numValue = parseNumericValue(value);
    // Solo negro si es exactamente 0
    if (numValue === 0) return 'delta-neutral';
    // Para posiciones: negativo = mejora (verde), positivo = empeora (rojo)
    if (numValue > 0) return 'delta-negative'; // Empeora posición = rojo
    if (numValue < 0) return 'delta-positive'; // Mejora posición = verde
    return '';
}

// ✅ ELIMINADO: parseNumericValue duplicado - ahora se usa el de number-utils.js

/**
 * Compara valores de delta para ordenamiento MEJORADO (igual que URLs)
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
 * Compara valores de delta de posición para ordenamiento MEJORADO (lógica invertida igual que URLs)
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