// 🔧 SISTEMA DE VALIDACIÓN DE DATOS
// crear como data-validator.js

export class DataValidator {
    constructor() {
        this.validationResults = [];
        this.debugMode = localStorage.getItem('debugDataValidation') === 'true';
    }

    // 🔍 VALIDACIÓN PRINCIPAL
    validateDataConsistency(responseData) {
        console.log('🔍 Iniciando validación de consistencia de datos...');
        
        this.validationResults = [];
        
        if (!responseData || typeof responseData !== 'object') {
            this.addError('CRITICAL', 'Datos de respuesta inválidos o vacíos');
            return this.getValidationSummary();
        }

        // Validar estructura básica
        this.validateDataStructure(responseData);
        
        // Validar datos de páginas
        if (responseData.pages) {
            this.validatePagesData(responseData.pages);
        }
        
        // Validar datos de keywords
        if (responseData.keyword_comparison_data) {
            this.validateKeywordData(responseData.keyword_comparison_data);
        }
        
        // Validar consistencia entre datasets
        this.validateCrossDataConsistency(responseData);
        
        return this.getValidationSummary();
    }

    // 🔍 VALIDAR ESTRUCTURA DE DATOS
    validateDataStructure(data) {
        const requiredFields = ['pages', 'keywordStats', 'keyword_comparison_data'];
        
        requiredFields.forEach(field => {
            if (!data[field]) {
                this.addWarning('STRUCTURE', `Campo requerido faltante: ${field}`);
            }
        });

        // Validar tipos de datos
        if (data.pages && !Array.isArray(data.pages)) {
            this.addError('STRUCTURE', 'El campo "pages" debe ser un array');
        }
        
        if (data.keyword_comparison_data && !Array.isArray(data.keyword_comparison_data)) {
            this.addError('STRUCTURE', 'El campo "keyword_comparison_data" debe ser un array');
        }
    }

    // 🔍 VALIDAR DATOS DE PÁGINAS
    validatePagesData(pages) {
        if (!Array.isArray(pages) || pages.length === 0) {
            this.addWarning('PAGES', 'No hay datos de páginas para validar');
            return;
        }

        // Detectar páginas duplicadas
        const urlCount = {};
        const duplicatePages = [];
        
        pages.forEach(page => {
            const url = page.URL;
            if (!url) {
                this.addError('PAGES', 'Página sin URL encontrada');
                return;
            }
            
            if (!page.Metrics || !Array.isArray(page.Metrics)) {
                this.addError('PAGES', `Página ${url} sin métricas válidas`);
                return;
            }

            // Contar URLs
            urlCount[url] = (urlCount[url] || 0) + 1;
            if (urlCount[url] > 1) {
                duplicatePages.push(url);
            }

            // Validar métricas por página
            this.validatePageMetrics(page);
        });

        // Reportar duplicados
        if (duplicatePages.length > 0) {
            this.addError('PAGES', `Páginas duplicadas detectadas: ${duplicatePages.slice(0, 5).join(', ')}${duplicatePages.length > 5 ? ' ...' : ''}`);
        }

        console.log(`📊 Páginas validadas: ${pages.length}, Duplicados: ${duplicatePages.length}`);
    }

    // 🔍 VALIDAR MÉTRICAS DE PÁGINA
    validatePageMetrics(page) {
        const url = page.URL;
        const monthMetrics = {};
        
        page.Metrics.forEach(metric => {
            const month = metric.Month;
            
            // Detectar duplicados de mes
            if (monthMetrics[month]) {
                this.addError('METRICS', `Mes duplicado para ${url}: ${month}`);
            }
            monthMetrics[month] = metric;

            // Validar valores
            this.validateMetricValues(metric, url, month);
        });
    }

    // 🔍 VALIDAR VALORES DE MÉTRICAS
    validateMetricValues(metric, url, month) {
        const { Clicks, Impressions, CTR, Position } = metric;

        // Validar tipos y rangos
        if (typeof Clicks !== 'number' || Clicks < 0) {
            this.addError('METRICS', `Clicks inválidos para ${url} en ${month}: ${Clicks}`);
        }
        
        if (typeof Impressions !== 'number' || Impressions < 0) {
            this.addError('METRICS', `Impressions inválidas para ${url} en ${month}: ${Impressions}`);
        }
        
        if (typeof CTR !== 'number' || CTR < 0 || CTR > 1) {
            this.addError('METRICS', `CTR inválido para ${url} en ${month}: ${CTR} (debe estar entre 0 y 1)`);
        }
        
        if (typeof Position !== 'number' || Position < 1) {
            this.addError('METRICS', `Position inválida para ${url} en ${month}: ${Position}`);
        }

        // Validar consistencia CTR
        if (Impressions > 0) {
            const calculatedCTR = Clicks / Impressions;
            const difference = Math.abs(calculatedCTR - CTR);
            
            if (difference > 0.001) { // Tolerancia para errores de punto flotante
                this.addWarning('METRICS', `CTR inconsistente para ${url} en ${month}: reportado=${CTR.toFixed(4)}, calculado=${calculatedCTR.toFixed(4)}`);
            }
        } else if (Clicks > 0) {
            this.addError('METRICS', `Clicks sin impresiones para ${url} en ${month}: ${Clicks} clicks, ${Impressions} impressions`);
        }
    }

    // 🔍 VALIDAR DATOS DE KEYWORDS
    validateKeywordData(keywords) {
        if (!Array.isArray(keywords) || keywords.length === 0) {
            this.addWarning('KEYWORDS', 'No hay datos de keywords para validar');
            return;
        }

        const keywordCount = {};
        const duplicateKeywords = [];

        keywords.forEach(kw => {
            const keyword = kw.keyword;
            
            if (!keyword) {
                this.addError('KEYWORDS', 'Keyword sin nombre encontrada');
                return;
            }

            // Detectar duplicados
            keywordCount[keyword] = (keywordCount[keyword] || 0) + 1;
            if (keywordCount[keyword] > 1) {
                duplicateKeywords.push(keyword);
            }

            // Validar métricas de keyword
            this.validateKeywordMetrics(kw);
        });

        if (duplicateKeywords.length > 0) {
            this.addError('KEYWORDS', `Keywords duplicadas: ${duplicateKeywords.slice(0, 3).join(', ')}${duplicateKeywords.length > 3 ? ' ...' : ''}`);
        }

        console.log(`🔑 Keywords validadas: ${keywords.length}, Duplicados: ${duplicateKeywords.length}`);
    }

    // 🔍 VALIDAR MÉTRICAS DE KEYWORD
    validateKeywordMetrics(kw) {
        const { keyword, clicks_m1, clicks_m2, impressions_m1, impressions_m2, ctr_m1, ctr_m2 } = kw;

        // Validar CTR calculado
        if (impressions_m1 > 0) {
            const calculatedCTR1 = (clicks_m1 / impressions_m1) * 100;
            const difference1 = Math.abs(calculatedCTR1 - ctr_m1);
            
            if (difference1 > 0.1) { // Tolerancia del 0.1%
                this.addWarning('KEYWORDS', `CTR M1 inconsistente para "${keyword}": reportado=${ctr_m1?.toFixed(2)}%, calculado=${calculatedCTR1.toFixed(2)}%`);
            }
        }

        if (impressions_m2 > 0) {
            const calculatedCTR2 = (clicks_m2 / impressions_m2) * 100;
            const difference2 = Math.abs(calculatedCTR2 - ctr_m2);
            
            if (difference2 > 0.1) {
                this.addWarning('KEYWORDS', `CTR M2 inconsistente para "${keyword}": reportado=${ctr_m2?.toFixed(2)}%, calculado=${calculatedCTR2.toFixed(2)}%`);
            }
        }

        // Detectar cambios extremos
        if (clicks_m1 > 0 && clicks_m2 > 0) {
            const clicksChange = Math.abs((clicks_m2 - clicks_m1) / clicks_m1) * 100;
            if (clicksChange > 1000) { // Cambio mayor al 1000%
                this.addWarning('KEYWORDS', `Cambio extremo en clicks para "${keyword}": ${clicksChange.toFixed(0)}%`);
            }
        }
    }

    // 🔍 VALIDAR CONSISTENCIA CRUZADA
    validateCrossDataConsistency(data) {
        if (!data.pages || !data.keyword_comparison_data) {
            this.addWarning('CONSISTENCY', 'Datos insuficientes para validación cruzada');
            return;
        }

        // Calcular totales de páginas
        const pagesTotals = this.calculatePageTotals(data.pages);
        
        // Calcular totales de keywords  
        const keywordTotals = this.calculateKeywordTotals(data.keyword_comparison_data);

        // Comparar totales
        this.compareDatasetTotals(pagesTotals, keywordTotals);
    }

    // 🔍 CALCULAR TOTALES DE PÁGINAS
    calculatePageTotals(pages) {
        const totals = {};
        
        pages.forEach(page => {
            page.Metrics.forEach(metric => {
                const month = metric.Month;
                if (!totals[month]) {
                    totals[month] = { clicks: 0, impressions: 0 };
                }
                
                totals[month].clicks += metric.Clicks;
                totals[month].impressions += metric.Impressions;
            });
        });

        return totals;
    }

    // 🔍 CALCULAR TOTALES DE KEYWORDS
    calculateKeywordTotals(keywords) {
        let totalClicks1 = 0, totalImpressions1 = 0;
        let totalClicks2 = 0, totalImpressions2 = 0;

        keywords.forEach(kw => {
            totalClicks1 += kw.clicks_m1 || 0;
            totalImpressions1 += kw.impressions_m1 || 0;
            totalClicks2 += kw.clicks_m2 || 0;
            totalImpressions2 += kw.impressions_m2 || 0;
        });

        return {
            period1: { clicks: totalClicks1, impressions: totalImpressions1 },
            period2: { clicks: totalClicks2, impressions: totalImpressions2 }
        };
    }

    // 🔍 COMPARAR TOTALES DE DATASETS
    compareDatasetTotals(pagesTotals, keywordTotals) {
        const pageMonths = Object.keys(pagesTotals).sort();
        
        if (pageMonths.length >= 2) {
            const firstMonth = pageMonths[0];
            const lastMonth = pageMonths[pageMonths.length - 1];
            
            const pageFirst = pagesTotals[firstMonth];
            const pageLast = pagesTotals[lastMonth];
            
            // Comparar con keyword totals
            this.compareMetrics('Clicks P1', pageFirst.clicks, keywordTotals.period1.clicks);
            this.compareMetrics('Impressions P1', pageFirst.impressions, keywordTotals.period1.impressions);
            this.compareMetrics('Clicks P2', pageLast.clicks, keywordTotals.period2.clicks);
            this.compareMetrics('Impressions P2', pageLast.impressions, keywordTotals.period2.impressions);
        }
    }

    // 🔍 COMPARAR MÉTRICAS ESPECÍFICAS
    compareMetrics(metricName, pageValue, keywordValue) {
        if (pageValue === 0 && keywordValue === 0) return;
        
        const difference = Math.abs(pageValue - keywordValue);
        const percentDiff = pageValue > 0 ? (difference / pageValue) * 100 : 100;
        
        if (percentDiff > 5) { // Tolerancia del 5%
            this.addWarning('CONSISTENCY', `Discrepancia en ${metricName}: Páginas=${pageValue.toLocaleString()}, Keywords=${keywordValue.toLocaleString()} (${percentDiff.toFixed(1)}% diff)`);
        } else if (this.debugMode) {
            console.log(`✅ ${metricName} consistente: ${percentDiff.toFixed(2)}% diferencia`);
        }
    }

    // 🔧 MÉTODOS DE UTILIDAD
    addError(category, message) {
        this.validationResults.push({ type: 'ERROR', category, message });
        console.error(`❌ [${category}] ${message}`);
    }

    addWarning(category, message) {
        this.validationResults.push({ type: 'WARNING', category, message });
        console.warn(`⚠️ [${category}] ${message}`);
    }

    addInfo(category, message) {
        this.validationResults.push({ type: 'INFO', category, message });
        console.info(`ℹ️ [${category}] ${message}`);
    }

    getValidationSummary() {
        const errors = this.validationResults.filter(r => r.type === 'ERROR');
        const warnings = this.validationResults.filter(r => r.type === 'WARNING');
        
        const summary = {
            isValid: errors.length === 0,
            hasWarnings: warnings.length > 0,
            errorCount: errors.length,
            warningCount: warnings.length,
            errors: errors,
            warnings: warnings,
            allResults: this.validationResults
        };

        console.log(`🔍 Validación completada: ${errors.length} errores, ${warnings.length} advertencias`);
        
        return summary;
    }

    // 🔧 HABILITAR/DESHABILITAR DEBUG
    enableDebugMode() {
        this.debugMode = true;
        localStorage.setItem('debugDataValidation', 'true');
        console.log('🔍 Modo debug de validación habilitado');
    }

    disableDebugMode() {
        this.debugMode = false;
        localStorage.setItem('debugDataValidation', 'false');
        console.log('🔍 Modo debug de validación deshabilitado');
    }
}

// 🔧 USO EN data.js
export async function fetchData(formData) {
    const resp = await fetch('/get-data', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error('Error al obtener datos del backend.');
    
    const data = await resp.json();
    
    // 🔍 VALIDAR DATOS ANTES DE PROCESARLOS
    const validator = new DataValidator();
    const validation = validator.validateDataConsistency(data);
    
    if (!validation.isValid) {
        console.error('🚨 Datos inválidos detectados:', validation.errors);
        // Opcional: mostrar errores al usuario
        showValidationErrors(validation);
    }
    
    if (validation.hasWarnings) {
        console.warn('⚠️ Advertencias en los datos:', validation.warnings);
        // Opcional: mostrar advertencias al usuario
        showValidationWarnings(validation);
    }
    
    return data;
}

// 🔧 FUNCIONES AUXILIARES PARA UI
function showValidationErrors(validation) {
    const errorMessages = validation.errors.map(e => `${e.category}: ${e.message}`).join('\n');
    
    // Opcional: usar tu sistema de toasts
    if (window.navbar && window.navbar.showToast) {
        window.navbar.showToast(`Errores en datos detectados. Ver consola para detalles.`, 'error');
    } else {
        alert(`Errores en datos detectados:\n\n${errorMessages}`);
    }
}

function showValidationWarnings(validation) {
    if (validation.warningCount > 0) {
        console.group('⚠️ Advertencias de validación');
        validation.warnings.forEach(w => {
            console.warn(`${w.category}: ${w.message}`);
        });
        console.groupEnd();
        
        // Opcional: toast para advertencias
        if (window.navbar && window.navbar.showToast) {
            window.navbar.showToast(`${validation.warningCount} advertencias detectadas. Ver consola.`, 'warning');
        }
    }
}

// 🔧 COMANDOS DE CONSOLA PARA DEBUG
window.dataValidator = {
    enableDebug: () => new DataValidator().enableDebugMode(),
    disableDebug: () => new DataValidator().disableDebugMode(),
    validateLast: () => {
        if (window.currentData) {
            const validator = new DataValidator();
            return validator.validateDataConsistency(window.currentData);
        } else {
            console.warn('No hay datos para validar. Ejecuta una consulta primero.');
        }
    }
};