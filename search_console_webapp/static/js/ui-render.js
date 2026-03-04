// ui-render.js - ACTUALIZADO para manejar períodos específicos en lugar de meses
import { elems } from './utils.js';
import { 
  formatInteger, 
  formatDecimal, 
  formatPercentage,
  formatPosition, 
  formatPercentageChange, 
  formatPositionDelta,
  parseNumericValue, 
  parseIntegerValue,
  getStandardUrlTableConfig,
  registerDataTableSortingTypes,
  escapeHtml as escapeHtmlUtil
} from './number-utils.js';
import { createUrlsGridTable } from './ui-urls-gridjs.js';
import { createUrlKeywordsGridTable } from './ui-url-keywords-gridjs.js';

// Variables para almacenar las instancias de Grid.js principales
let urlsGridTable = null;
let keywordsGridTable = null;

// ✅ MEJORADA: Función para resetear completamente el estado de la tabla de URLs (Grid.js)
export async function resetUrlsTableState() {
  console.log('🔄 Reseteando estado completo de la tabla de URLs...');
  
  // Resetear variables globales de Grid.js
  if (urlsGridTable && urlsGridTable.destroy) {
    try {
      urlsGridTable.destroy();
      console.log('✅ URLs Grid.js anterior destruido en reset');
    } catch (e) {
      console.warn('⚠️ Error destruyendo URLs Grid.js en reset:', e);
    }
  }
  urlsGridTable = null;
  
  // ✅ MEJORADO: Limpiar tabla principal de keywords
  try {
    const { clearKeywordComparisonTable } = await import('./ui-keyword-comparison-table.js');
    clearKeywordComparisonTable();
    console.log('✅ Keywords Grid.js principal destruido en reset');
  } catch (e) {
    console.warn('⚠️ Error destruyendo Keywords Grid.js principal en reset:', e);
  }
  
  // ✅ NUEVO: Limpiar también las instancias de Grid.js de modales keywords
  Object.keys(preProcessedModalData).forEach(range => {
    if (preProcessedModalData[range].gridTable && preProcessedModalData[range].gridTable.destroy) {
      try {
        preProcessedModalData[range].gridTable.destroy();
        console.log(`✅ Modal Grid.js destruido para ${range}`);
      } catch (e) {
        console.warn(`⚠️ Error destruyendo Modal Grid.js para ${range}:`, e);
      }
      preProcessedModalData[range].gridTable = null;
    }
    preProcessedModalData[range].isLoading = false;
  });
  
  // Limpiar datos globales relacionados
  window.currentData = null;
  
  // Asegurar que la sección esté oculta inicialmente
  if (elems.resultsSection) {
    elems.resultsSection.style.display = 'none';
  }
  if (elems.resultsTitle) {
    elems.resultsTitle.style.display = 'none';
  }
  
  console.log('✅ Estado de tabla de URLs y modales reseteado completamente');
}

// ✅ NUEVO: Variable global para almacenar los datos de keywords
let globalKeywordData = [];

const KEYWORD_MODAL_META = {
  top3: {
    title: 'Top 1-3',
    info: 'These are the keywords positioned between 1 and 3. Click the search icon to view the SERP.'
  },
  top10: {
    title: 'Positions 4-10',
    info: 'These are the keywords positioned between 4 and 10. Click the search icon to view the SERP.'
  },
  top20: {
    title: 'Positions 11-20',
    info: 'These are the keywords positioned between 11 and 20. Click the search icon to view the SERP.'
  },
  top20plus: {
    title: 'Positions 20+',
    info: 'These are the keywords positioned beyond 20. Click the search icon to view the SERP.'
  },
  improved: {
    title: 'Keywords That Improve',
    info: 'Keywords with better average position in P1 vs P2.'
  },
  worsened: {
    title: 'Keywords That Decline',
    info: 'Keywords with worse average position in P1 vs P2.'
  },
  same: {
    title: 'Keywords That Keep Position',
    info: 'Keywords with the same average position in P1 and P2.'
  },
  new: {
    title: 'New Keywords',
    info: 'Keywords that rank in P1 but did not rank in P2.'
  },
  lost: {
    title: 'Lost Keywords',
    info: 'Keywords that ranked in P2 but no longer rank in P1.'
  }
};

function createInitialKeywordModalState() {
  return Object.fromEntries(
    Object.keys(KEYWORD_MODAL_META).map((key) => ([
      key,
      { keywords: [], gridTable: null, analysisType: 'single', isLoading: false }
    ]))
  );
}

// ✅ REMOVIDO: Funciones de formateo - ahora se usan las del módulo centralizado number-utils.js

// ✅ NUEVA función para determinar el tipo de análisis para URLs
function getUrlAnalysisType(urlData, periods = null) {
  if (!urlData || urlData.length === 0) return 'empty';
  
  // ✅ CORREGIDO: Primero verificar si el usuario seleccionó comparación
  if (periods && periods.has_comparison && periods.comparison) {
    console.log('🔍 Usuario seleccionó comparación explícitamente - forzando modo comparison');
    return 'comparison';
  }
  
  // Verificar si hay múltiples períodos por URL (lógica original)
  const hasMultiplePeriods = urlData.some(urlItem => 
    urlItem.Metrics && urlItem.Metrics.length > 1
  );
  
  return hasMultiplePeriods ? 'comparison' : 'single';
}

// ✅ NUEVA función para actualizar headers de tabla de URLs
function updateUrlTableHeaders(analysisType) {
  const table = document.getElementById('resultsTable');
  if (!table) return;
  
  const headers = table.querySelectorAll('thead th');
  
  if (analysisType === 'single') {
    // Headers para período único
    if (headers[2]) headers[2].textContent = 'Clicks P1';
    if (headers[3]) headers[3].style.display = 'none'; // Ocultar P2
    if (headers[4]) headers[4].style.display = 'none'; // Ocultar Delta
    if (headers[5]) headers[5].textContent = 'Impressions P1';
    if (headers[6]) headers[6].style.display = 'none'; // Ocultar P2
    if (headers[7]) headers[7].style.display = 'none'; // Ocultar Delta
    if (headers[8]) headers[8].textContent = 'CTR P1 (%)';
    if (headers[9]) headers[9].style.display = 'none'; // Ocultar P2
    if (headers[10]) headers[10].style.display = 'none'; // Ocultar Delta
    if (headers[11]) headers[11].textContent = 'Pos P1';
    if (headers[12]) headers[12].style.display = 'none'; // Ocultar P2
    if (headers[13]) headers[13].style.display = 'none'; // Ocultar Delta
  } else {
    // Headers para comparación (mostrar todos)
    if (headers[2]) headers[2].textContent = 'Clicks P1';
    if (headers[3]) {
      headers[3].style.display = '';
      headers[3].textContent = 'Clicks P2';
    }
    if (headers[4]) {
      headers[4].style.display = '';
      headers[4].textContent = 'ΔClicks (%)';
    }
    if (headers[5]) headers[5].textContent = 'Impressions P1';
    if (headers[6]) {
      headers[6].style.display = '';
      headers[6].textContent = 'Impressions P2';
    }
    if (headers[7]) {
      headers[7].style.display = '';
      headers[7].textContent = 'ΔImp. (%)';
    }
    if (headers[8]) headers[8].textContent = 'CTR P1 (%)';
    if (headers[9]) {
      headers[9].style.display = '';
      headers[9].textContent = 'CTR P2 (%)';
    }
    if (headers[10]) {
      headers[10].style.display = '';
      headers[10].textContent = 'ΔCTR (%)';
    }
    if (headers[11]) headers[11].textContent = 'Pos P1';
    if (headers[12]) {
      headers[12].style.display = '';
      headers[12].textContent = 'Pos P2';
    }
    if (headers[13]) {
      headers[13].style.display = '';
      headers[13].textContent = 'ΔPos';
    }
  }
}

// ✅ FUNCIÓN CORREGIDA: processUrlsData en ui-render.js
function processUrlsData(pages) {
  const urlsData = [];
  
  pages.forEach(item => {
    const url = item.URL || 'N/A';
    const metrics = item.Metrics || [];
    
    if (metrics.length === 1) {
      // Período único - ✅ CORREGIDO: Datos van a P1 (período actual)
      const metric = metrics[0];
      urlsData.push({
        url: url,
        clicks_p1: metric.Clicks || 0,
        clicks_p2: 0,
        impressions_p1: metric.Impressions || 0,
        impressions_p2: 0,
        ctr_p1: (metric.CTR || 0) * 100,  // ✅ Convertir decimal GSC a porcentaje
        ctr_p2: 0,
        position_p1: metric.Position || null,
        position_p2: null,
        delta_clicks_percent: 'New',
        delta_impressions_percent: 'New',
        delta_ctr_percent: 'New',
        delta_position_absolute: 'New'
      });
    } else if (metrics.length >= 2) {
      // ✅ CORREGIDO: Ordenar por fecha para asegurar el orden correcto
      const sortedMetrics = metrics.sort((a, b) => {
        if (a.StartDate && b.StartDate) {
          return new Date(a.StartDate) - new Date(b.StartDate);
        }
        return 0;
      });
      
      // ✅ CORREGIDO: Asignación correcta según el orden temporal
      const currentMetric = sortedMetrics[sortedMetrics.length - 1]; // P1 = Más reciente (actual)
      const comparisonMetric = sortedMetrics[0]; // P2 = Más antiguo (comparación)
      
      // ✅ CORREGIDO: Calcular deltas como P1 sobre P2 (actual sobre comparación)
      const deltaClicks = calculatePercentageChange(currentMetric.Clicks, comparisonMetric.Clicks);
      const deltaImpressions = calculatePercentageChange(currentMetric.Impressions, comparisonMetric.Impressions);
      const deltaCTR = ((currentMetric.CTR || 0) - (comparisonMetric.CTR || 0)) * 100;
      const deltaPosition = (currentMetric.Position && comparisonMetric.Position)
        ? currentMetric.Position - comparisonMetric.Position
        : (currentMetric.Position ? 'New' : 'Lost');
      
      urlsData.push({
        url: url,
        // ✅ CORREGIDO: P1 = período actual (más reciente)
        clicks_p1: currentMetric.Clicks || 0,      
        impressions_p1: currentMetric.Impressions || 0,
        ctr_p1: (currentMetric.CTR || 0) * 100,  // ✅ Convertir decimal GSC a porcentaje
        position_p1: currentMetric.Position || null,
        
        // ✅ CORREGIDO: P2 = período de comparación (más antiguo)
        clicks_p2: comparisonMetric.Clicks || 0,      
        impressions_p2: comparisonMetric.Impressions || 0,
        ctr_p2: (comparisonMetric.CTR || 0) * 100,  // ✅ Convertir decimal GSC a porcentaje
        position_p2: comparisonMetric.Position || null,
        
        // ✅ CORREGIDO: Deltas calculados como (P1 - P2) / P2
        delta_clicks_percent: deltaClicks,
        delta_impressions_percent: deltaImpressions,
        delta_ctr_percent: deltaCTR,
        delta_position_absolute: deltaPosition
      });
    }
  });
  
  return urlsData;
}

// ✅ FUNCIÓN auxiliar para calcular cambio porcentual
function calculatePercentageChange(p1, p2) {
  if (p1 === null || p2 === null || typeof p1 === 'undefined' || typeof p2 === 'undefined') {
    return 'N/A';
  }
  if (p2 === 0) {
    if (p1 > 0) return "Infinity";
    if (p1 < 0) return "-Infinity";
    return 0;
  }
  return ((p1 / p2) - 1) * 100;
}

// Genera la tarjeta de categoría para palabras clave
function buildCatCard(title, stat = { current: 0, new: 0, lost: 0, stay: 0 }) {
  return `
    <div class="category-card">
      <div class="value">${stat.current}</div>
      <div class="subtitle">${title}</div>
      <div class="entry">New: <strong>+${stat.new}</strong></div>
      <div class="exit">Lost: <strong>-${stat.lost}</strong></div>
      <div class="maintain">Maintained: <strong>${stat.stay}</strong></div>
    </div>
  `;
}

// ✅ ACTUALIZADA: Función para crear mini-gráficos que maneja períodos específicos
function createMiniChart(canvasId, data, color, labels, type = 'line') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  
  const ctx = canvas.getContext('2d');
  
  if (canvas.chart) {
    canvas.chart.destroy();
  }

  const gradient = ctx.createLinearGradient(0, 0, 0, 60);
  gradient.addColorStop(0, `${color}40`);
  gradient.addColorStop(1, `${color}08`);
  
  const chartConfig = {
    type: 'line',
    data: {
      labels: labels || ['P1', 'P2'], // Etiquetas por defecto para períodos
      datasets: [{
        data: data,
        borderColor: color,
        backgroundColor: gradient,
        borderWidth: 2.5,
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: color,
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
        pointHoverBackgroundColor: color,
        pointHoverBorderColor: '#ffffff',
        pointHoverBorderWidth: 3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index',
      },
      plugins: {
        legend: { display: false },
        tooltip: { 
          enabled: true,
          mode: 'index',
          intersect: false,
          bodyFont: { size: 12 },
          titleFont: { size: 12 },
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          borderColor: color,
          borderWidth: 1,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            title: function(context) {
              return labels ? labels[context[0].dataIndex] : `Período ${context[0].dataIndex + 1}`;
            },
            label: function(context) {
              const value = context.parsed.y;
              if (canvasId.includes('ctr')) return `${value.toFixed(2)}%`;
              if (canvasId.includes('position')) return value.toFixed(1);
              return Number.isInteger(value) ? formatInteger(value) : value;
            }
          }
        }
      },
      scales: {
        x: { 
          display: false,
          grid: { display: false }
        },
        y: { 
          display: false,
          grid: { display: false },
          beginAtZero: true
        }
      },
      animation: {
        duration: 1000,
        easing: 'easeInOutQuart'
      },
      hover: {
        animationDuration: 200
      }
    }
  };
  
  canvas.chart = new Chart(ctx, chartConfig);
  return canvas.chart;
}

// ✅ ACTUALIZADA: Renderiza el bloque de resumen con períodos específicos
export function renderSummary(periodSummary) {
  ['#summaryClicks', '#summaryImpressions', '#summaryCTR', '#summaryPosition'].forEach(sel => {
    const el = document.querySelector(`${sel} .summary-content`);
    if (el) el.innerHTML = '';
  });

  const periods = Object.keys(periodSummary).sort((a, b) => {
    // Ordenar por fecha de inicio si está disponible
    const periodA = periodSummary[a];
    const periodB = periodSummary[b];
    
    if (periodA.StartDate && periodB.StartDate) {
      return new Date(periodA.StartDate) - new Date(periodB.StartDate);
    }
    
    return a.localeCompare(b);
  });
  
  window.currentPeriodSummary = periodSummary;

  if (periods.length === 0) {
    console.warn('No hay períodos para mostrar en el resumen');
    return;
  }

  // ✅ NUEVO: Usar datos del último período (más reciente) como base
  const lastPeriod = periodSummary[periods[periods.length - 1]];
  const p1Clicks = lastPeriod.Clicks || 0;
  const p1Impressions = lastPeriod.Impressions || 0;
  const p1CTR = (lastPeriod.CTR || 0) * 100;
  const p1Position = lastPeriod.Position || 0;

  // Preparar datos para mini-gráficos
  const clicksData = periods.map(p => periodSummary[p].Clicks || 0);
  const impressionsData = periods.map(p => periodSummary[p].Impressions || 0);
  const ctrData = periods.map(p => parseFloat(((periodSummary[p].CTR || 0) * 100).toFixed(2)));
  const positionData = periods.map(p => parseFloat((periodSummary[p].Position || 0).toFixed(1)));

  // Generar etiquetas más legibles para los gráficos
  const chartLabels = periods.map((periodKey, index) => {
    const period = periodSummary[periodKey];
    if (period.StartDate && period.EndDate) {
      const start = new Date(period.StartDate);
      const end = new Date(period.EndDate);
      
      // Si es el mismo día
      if (period.StartDate === period.EndDate) {
        return start.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' });
      }
      
      // Si es un rango
      return `${start.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })} - ${end.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })}`;
    }
    
    return `P${index + 1}`;
  });

  const colors = {
    clicks: '#3B82F6',      // Azul
    impressions: '#22C55E',  // Verde (brandbook)
    ctr: '#F59E0B',         // Naranja
    position: '#EF4444'     // Rojo
  };

  // ✅ ACTUALIZADA: Función para crear cards con información de períodos
  const createSummaryCard = (id, title, icon, total, chartData, chartLabels, color, isPercentage = false, isPosition = false) => {
    const formatValue = (val) => {
      if (isPercentage) return formatDecimal(val, 2) + '%';
      if (isPosition) return formatDecimal(val, 1);
      return formatInteger(val);
    };

    // Función para formatear el delta
    const formatDelta = (deltaValue, isDeltaPercentage = false, isDeltaPosition = false, isDeltaCTR = false) => {
      if (deltaValue === 'N/A' || deltaValue === null || deltaValue === undefined) return 'N/A';
      if (deltaValue === 'Infinity' || deltaValue === '-Infinity') return deltaValue === 'Infinity' ? '+∞%' : '-∞%';
      
      if (isDeltaPosition) {
        // Para posición, el delta es absoluto (no porcentual)
        const sign = deltaValue > 0 ? '+' : '';
        return `${sign}${deltaValue.toFixed(1)}`;
      } else if (isDeltaCTR) {
        // Para CTR, el delta es en puntos porcentuales
        const sign = deltaValue > 0 ? '+' : '';
        return `${sign}${deltaValue.toFixed(2)}%`;
      } else {
        // Para clicks e impressions, el delta es porcentual
        const sign = deltaValue > 0 ? '+' : '';
        return `${sign}${deltaValue.toFixed(1)}%`;
      }
    };

    // ✅ NUEVO: Crear valores de períodos con formato de fechas (P1 primero)
    let periodValues = '';
    let deltaValues = [];
    
    // Invertir el orden para mostrar P1 (más reciente) primero
    const reversedPeriods = [...periods].reverse();
    reversedPeriods.forEach((periodKey, index) => {
      const period = periodSummary[periodKey];
      let value;
      if (id === 'clicks') value = period.Clicks || 0;
      else if (id === 'impressions') value = period.Impressions || 0;
      else if (id === 'ctr') value = (period.CTR || 0) * 100;
      else if (id === 'position') value = period.Position || 0;
      
      deltaValues.push(value);
      
      // Crear etiqueta con formato de fecha
      let dateLabel = '';
      if (period.StartDate && period.EndDate) {
        const start = new Date(period.StartDate);
        const end = new Date(period.EndDate);
        dateLabel = `${start.toLocaleDateString('es-ES', { day: 'numeric', month: 'numeric', year: 'numeric' })} - ${end.toLocaleDateString('es-ES', { day: 'numeric', month: 'numeric', year: 'numeric' })}`;
      } else {
        // Ajustar numeración para mostrar P1, P2 correctamente
        const originalIndex = periods.length - index;
        dateLabel = `P${originalIndex}`;
      }
      
      periodValues += `<div class="period-value-line">
        <span class="period-date">${dateLabel}</span>
        <span class="period-metric">${formatValue(value)}</span>
      </div>`;
    });

    // ✅ NUEVO: Calcular y mostrar delta solo cuando hay múltiples períodos
    let deltaHTML = '';
    if (periods.length >= 2 && deltaValues.length >= 2) {
      const p1Value = deltaValues[0]; // Período más reciente (P1)
      const p2Value = deltaValues[deltaValues.length - 1]; // Período más antiguo (P2)
      
      let deltaValue;
      if (isPosition) {
        // Para posición, calcular diferencia absoluta (P1 - P2)
        deltaValue = p1Value - p2Value;
      } else if (id === 'ctr') {
        // Para CTR, calcular diferencia absoluta en puntos porcentuales (P1 - P2)
        deltaValue = p1Value - p2Value;
        

      } else {
        // Para clicks e impressions, calcular cambio porcentual ((P1 - P2) / P2) * 100
        deltaValue = calculatePercentageChange(p1Value, p2Value);
      }
      
      // Determinar clase CSS según si es positivo o negativo
      let deltaClass = 'delta-neutral';
      if (deltaValue !== 'N/A' && deltaValue !== 'Infinity' && deltaValue !== '-Infinity') {
        if (isPosition) {
          // Para posición, negativo es mejor (menor posición es mejor)
          deltaClass = deltaValue < 0 ? 'delta-positive' : (deltaValue > 0 ? 'delta-negative' : 'delta-neutral');
        } else {
          // Para clicks, impressions, CTR, positivo es mejor
          deltaClass = deltaValue > 0 ? 'delta-positive' : (deltaValue < 0 ? 'delta-negative' : 'delta-neutral');
        }
      }
      
      deltaHTML = `
        <div class="period-delta-line ${deltaClass}">
          <span class="delta-label">Δ P1 vs P2</span>
          <span class="delta-value">${formatDelta(deltaValue, !isPosition && id !== 'ctr', isPosition, id === 'ctr')}</span>
        </div>
      `;
    }

    return `
      <div class="summary-card-enhanced modern-card">
        <div class="card-header-modern">
          <div class="card-icon-modern">
            <i class="${icon}"></i>
          </div>
          <h3 class="card-title-modern">${title}</h3>
        </div>
        
        <div class="period-values-modern">
          ${periodValues}
          ${deltaHTML}
        </div>
      </div>
    `;
  };

  // Limpiar y actualizar HTML de cada card completamente
  document.querySelector('#summaryClicks').innerHTML = 
    createSummaryCard('clicks', 'Clicks', 'fas fa-mouse-pointer', null, clicksData, chartLabels, colors.clicks);

  document.querySelector('#summaryImpressions').innerHTML =
    createSummaryCard('impressions', 'Impressions', 'fas fa-eye', null, impressionsData, chartLabels, colors.impressions);

  document.querySelector('#summaryCTR').innerHTML =
    createSummaryCard('ctr', 'CTR', 'fas fa-percentage', null, ctrData, chartLabels, colors.ctr, true);

  document.querySelector('#summaryPosition').innerHTML =
    createSummaryCard('position', 'Position', 'fas fa-location-arrow', null, positionData, chartLabels, colors.position, false, true);

  if (elems.summaryBlock) elems.summaryBlock.style.display = 'grid';
  
  // ✅ SIDEBAR: El contenido está listo, notificar al sidebar que puede mostrar la sección
      console.log('✅ Performance content ready - sidebar can show it when user navigates');
    
    // ✅ Notificar al sidebar que el contenido de performance está listo
    if (window.sidebarOnContentReady) {
      window.sidebarOnContentReady('performance');
    }
  
  if (elems.chartsBlock) elems.chartsBlock.style.display = 'none';
}

// ✅ FUNCIÓN CORREGIDA para ui-render.js (reemplazar solo la función renderKeywords)

export function renderKeywords(keywordStats = {}) {
  const ov = keywordStats.overall || {};
  
  if (elems.keywordOverviewDiv) {
    const hasExplicitComparison = !!(
      window.currentData &&
      window.currentData.periods &&
      window.currentData.periods.has_comparison &&
      window.currentData.periods.comparison
    );
    // ✅ Adaptar mensajes según si hay comparación o no
    const hasComparison = hasExplicitComparison || (ov.improved > 0 || ov.worsened > 0 || ov.lost > 0);
    
    if (hasComparison) {
      const buildOverviewTrendCard = ({
        cardClass,
        iconClass,
        label,
        value,
        prefix = '',
        modalKey
      }) => {
        const numericValue = Number(value) || 0;
        const isClickable = numericValue > 0 && !!modalKey;
        const interactiveAttrs = isClickable
          ? `data-overview-range="${modalKey}" data-modal-label="${label}" role="button" tabindex="0" aria-label="Open ${label} keywords modal"`
          : '';
        const actionClass = isClickable ? '' : ' is-disabled';
        const actionText = isClickable ? 'View keywords' : 'No keywords';
        return `
          <div class="overview-card ${cardClass}${isClickable ? ' overview-card-clickable' : ''}" ${interactiveAttrs}>
            <div class="card-icon"><i class="${iconClass}"></i></div>
            <div class="label">${label}</div>
            <div class="value">${prefix}${formatInteger(numericValue)}</div>
            <div class="overview-card-action${actionClass}">${actionText}</div>
          </div>
        `;
      };

      // Mostrar iconos completos cuando hay comparación de períodos
      elems.keywordOverviewDiv.innerHTML = `
        <div class="overview-card total-kws">
          <div class="card-icon"><i class="fas fa-search"></i></div>
          <div class="label">Total KWs</div>
          <div class="value">${formatInteger(ov.total ?? 0)}</div>
        </div>
        ${buildOverviewTrendCard({
          cardClass: 'improved',
          iconClass: 'fas fa-arrow-trend-up',
          label: 'Improve positions',
          value: ov.improved ?? 0,
          prefix: '+',
          modalKey: 'improved'
        })}
        ${buildOverviewTrendCard({
          cardClass: 'declined',
          iconClass: 'fas fa-arrow-trend-down',
          label: 'Decline positions',
          value: ov.worsened ?? 0,
          prefix: '-',
          modalKey: 'worsened'
        })}
        ${buildOverviewTrendCard({
          cardClass: 'same-pos',
          iconClass: 'fas fa-equals',
          label: 'Same pos.',
          value: ov.same ?? 0,
          modalKey: 'same'
        })}
        ${buildOverviewTrendCard({
          cardClass: 'added',
          iconClass: 'fas fa-plus-circle',
          label: 'New',
          value: ov.new ?? 0,
          prefix: '+',
          modalKey: 'new'
        })}
        ${buildOverviewTrendCard({
          cardClass: 'removed',
          iconClass: 'fas fa-minus-circle',
          label: 'Lost',
          value: ov.lost ?? 0,
          prefix: '-',
          modalKey: 'lost'
        })}
      `;
    } else {
      // Mostrar solo el total de keywords cuando no hay comparación
      elems.keywordOverviewDiv.innerHTML = `
        <div class="overview-card total-kws single-period">
          <div class="card-icon"><i class="fas fa-search"></i></div>
          <div class="label">Total Keywords</div>
          <div class="value">${formatInteger(ov.total ?? 0)}</div>
        </div>
      `;
    }
    elems.keywordOverviewDiv.style.display = 'flex';
    
    const overviewCards = elems.keywordOverviewDiv.querySelectorAll('.overview-card[data-overview-range]');
    overviewCards.forEach(card => {
      const openFromCard = () => {
        const modalRange = card.dataset.overviewRange;
        const modalLabel = card.dataset.modalLabel || card.querySelector('.label')?.textContent || '';
        if (!modalRange) return;
        openKeywordModal(modalRange, modalLabel);
      };

      card.addEventListener('click', openFromCard);
      card.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openFromCard();
        }
      });
    });
  }

  if (elems.keywordCategoryDiv) {
    const buckets = keywordStats;
    
    const buildModernCatCard = (title, stat = { current: 0, new: 0, lost: 0, stay: 0 }, dataRange) => {
      const hasComparison = (stat.new > 0 || stat.lost > 0);

      let iconClass = 'fas fa-layer-group';
      let iconColor = '#94A3B8';

      switch (dataRange) {
        case 'top3':
          iconClass = 'fas fa-trophy';
          iconColor = '#FFD700';
          break;
        case 'top10':
          iconClass = 'fas fa-trophy';
          iconColor = '#C0C0C0';
          break;
        case 'top20':
          iconClass = 'fas fa-trophy';
          iconColor = '#CD7F32';
          break;
        case 'top20plus':
          iconClass = 'fas fa-medal';
          iconColor = '#94A3B8';
          break;
      }

      return `
        <div class="category-card clickable-card" data-position-range="${dataRange}" style="cursor: pointer;">
          <div class="card-icon"><i class="${iconClass}" style="color: ${iconColor};"></i></div>
          <div class="value">${formatInteger(stat.current ?? 0)}</div>
          <div class="subtitle">${title}</div>
          ${hasComparison ? `
            <div class="entry">New: <strong>+${formatInteger(stat.new ?? 0)}</strong></div>
            <div class="exit">Lost: <strong>-${formatInteger(stat.lost ?? 0)}</strong></div>
            <div class="maintain">Maintained: <strong>${formatInteger(stat.stay ?? 0)}</strong></div>
          ` : ``}
          <div class="overview-card-action" style="margin-top: 10px;">View keywords</div>
        </div>
      `;
    };
    
    elems.keywordCategoryDiv.innerHTML = [
      buildModernCatCard('Positions 1 – 3', buckets.top3, 'top3'),
      buildModernCatCard('Positions 4 – 10', buckets.top10, 'top10'),
      buildModernCatCard('Positions 11 – 20', buckets.top20, 'top20'),
      buildModernCatCard('Positions 20 or more', buckets.top20plus, 'top20plus')
    ].join('');
    elems.keywordCategoryDiv.style.display = 'grid';
    
    // ✅ NUEVO: Agregar event listeners para las tarjetas de categorías
    const categoryCards = elems.keywordCategoryDiv.querySelectorAll('.clickable-card');
    categoryCards.forEach(card => {
      card.addEventListener('click', function() {
        const positionRange = this.dataset.positionRange;
        const title = this.querySelector('.subtitle').textContent;
        openKeywordModal(positionRange, title);
      });
    });
  }

  // ✅ SIDEBAR: El contenido está listo, notificar al sidebar que puede mostrar la sección
  console.log('✅ Keywords content ready - sidebar can show it when user navigates');
}

// ✅ ACTUALIZADA: renderInsights para trabajar con períodos específicos
export function renderInsights(periodData) {
  console.log('📊 Datos recibidos en renderInsights:', periodData);
  
  const insightsContainer = document.getElementById('summaryDisclaimer');
  if (!insightsContainer) {
    console.warn('Container de insights no encontrado');
    return;
  }

  if (!periodData || typeof periodData !== 'object') {
    console.warn('No hay datos de períodos para mostrar insights');
    insightsContainer.innerHTML = '<p>No hay datos disponibles para mostrar insights.</p>';
    return;
  }

  const periods = Object.keys(periodData).sort((a, b) => {
    const periodA = periodData[a];
    const periodB = periodData[b];
    
    if (periodA.StartDate && periodB.StartDate) {
      return new Date(periodA.StartDate) - new Date(periodB.StartDate);
    }
    
    return a.localeCompare(b);
  });

  console.log('📅 Períodos encontrados:', periods);

  if (periods.length === 0) {
    insightsContainer.innerHTML = '<p>No hay datos de períodos disponibles.</p>';
    return;
  }

  // ✅ NUEVO: Usar datos del último período (más reciente) como base
  const lastPeriod = periodData[periods[periods.length - 1]];
  const p1Clicks = lastPeriod.Clicks || 0;
  const p1Impressions = lastPeriod.Impressions || 0;
  const p1CTR = (lastPeriod.CTR || 0) * 100;
  const p1Position = lastPeriod.Position || 0;

  // ✅ NUEVO: Calcular comparaciones entre períodos si hay múltiples
  let changeData = null;
  if (periods.length >= 2) {
    const firstPeriod = periodData[periods[0]];
    const lastPeriod = periodData[periods[periods.length - 1]];
    
    changeData = {
      clicks: calculatePercentageChangeInsights(firstPeriod.Clicks, lastPeriod.Clicks),
      impressions: calculatePercentageChangeInsights(firstPeriod.Impressions, lastPeriod.Impressions),
      ctr: calculatePercentageChangeInsights(firstPeriod.CTR, lastPeriod.CTR),
      position: calculatePercentageChangeInsights(firstPeriod.Position, lastPeriod.Position, true)
    };
  }

  console.log('📈 Datos calculados:', {
    p1Clicks,
    p1Impressions,  
    p1CTR,
    p1Position,
    changeData,
    periodsCount: periods.length
  });

  // ✅ ACTUALIZADO: Generar insights con información de períodos
  const insights = [
    {
      type: 'clicks',
      icon: 'fas fa-mouse-pointer',
      label: 'Clicks',
      value: formatInteger(p1Clicks),
      change: changeData ? formatChange(changeData.clicks) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Total del período`
    },
    {
      type: 'impressions',
      icon: 'fas fa-eye',
      label: 'Impressions',
      value: formatInteger(p1Impressions),
      change: changeData ? formatChange(changeData.impressions) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Total del período`
    },
    {
      type: 'ctr',
      icon: 'fas fa-percentage',
      label: 'Average CTR',
      value: formatDecimal(p1CTR, 2) + '%',
      change: changeData ? formatChange(changeData.ctr) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Promedio del período`
    },
    {
      type: 'position',
      icon: 'fas fa-location-arrow',
      label: 'Average Position',
      value: p1Position.toFixed(1),
      change: changeData ? formatChange(changeData.position) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Promedio del período`
    }
  ];

  insightsContainer.innerHTML = insights.map(insight => `
    <div class="insight-item ${insight.type}">
      <div class="insight-icon">
        <i class="${insight.icon}"></i>
      </div>
      
      <h3 class="insight-label">${insight.label}</h3>
      
      <div class="insight-value">${insight.value}</div>
      
      ${insight.change}
      
      <p class="insight-description">${insight.description}</p>
    </div>
  `).join('');

  const insightsSection = document.getElementById('insightsSection');
  const insightsTitle = document.getElementById('insightsTitle');
  
  // ✅ SIDEBAR: El contenido está listo, notificar al sidebar que puede mostrar la sección
      console.log('✅ Insights content ready - sidebar can show it when user navigates');
    
    // ✅ Notificar al sidebar que el contenido de insights está listo
    if (window.sidebarOnContentReady) {
      window.sidebarOnContentReady('insights');
    }

  console.log('✅ Insights renderizados correctamente');
}

// ✅ ACTUALIZADA: Función auxiliar para mostrar estado cuando no hay comparación
function getNoChangeHTML(periodsCount) {
  if (periodsCount === 1) {
    return '<div class="insight-change neutral"><span>Período único</span></div>';
  }
  return '<div class="insight-change neutral"><span>Análisis consolidado</span></div>';
}

// ✅ SIN CAMBIOS: Funciones auxiliares para cálculos permanecen igual
function calculatePercentageChangeInsights(oldValue, newValue, lowerIsBetter = false) {
  if (oldValue === null || newValue === null || typeof oldValue === 'undefined' || typeof newValue === 'undefined') {
    return null;
  }
  if (oldValue === 0) {
    if (newValue > 0) return { value: Infinity, isPositive: true, isNegative: false };
    if (newValue < 0) return { value: -Infinity, isPositive: false, isNegative: true };
    return { value: 0, isPositive: false, isNegative: false };
  }
  
  const change = ((newValue - oldValue) / oldValue) * 100;
  return {
    value: change,
    isPositive: lowerIsBetter ? change < 0 : change > 0,
    isNegative: lowerIsBetter ? change > 0 : change < 0
  };
}

function formatChange(changeObj) {
  if (!changeObj || changeObj.value === null) {
    return getNoChangeHTML(1);
  }
  if (changeObj.value === Infinity) {
    return '<div class="insight-change positive"><i class="fas fa-infinity change-icon"></i> <span>+∞%</span></div>';
  }
  if (changeObj.value === -Infinity) {
    return '<div class="insight-change negative"><i class="fas fa-infinity change-icon"></i> <span>-∞%</span></div>';
  }

  let changeClass = 'neutral';
  let icon = '';
  
  if (changeObj.isPositive) {
    changeClass = 'positive';
    icon = '<i class="fas fa-arrow-up change-icon"></i>';
  } else if (changeObj.isNegative) {
    changeClass = 'negative';
    icon = '<i class="fas fa-arrow-down change-icon"></i>';
  }

  const formattedChange = Math.abs(changeObj.value).toFixed(1);
  
  return `<div class="insight-change ${changeClass}">
    ${icon}
    <span>${formattedChange}%</span>
  </div>`;
}

/**
 * ✅ NUEVA FUNCIÓN: Limpieza completa y robusta de la tabla anterior
 */
function cleanupPreviousTable() {
  console.log('🧹 Limpiando tabla anterior...');
  
  const table = document.getElementById('resultsTable');
  
  // 1. Verificar si existe una instancia de DataTable
  const isDataTableInitialized = table && window.DataTable && 
    window.DataTable.isDataTable('#resultsTable');
  
  if (isDataTableInitialized) {
    try {
      console.log('🔄 DataTable detectada, procediendo con destrucción segura...');
      
      // ✅ MÉTODO MÁS SEGURO: Destruir desde jQuery si está disponible
      if (window.$ && window.$.fn.DataTable && window.$.fn.DataTable.isDataTable('#resultsTable')) {
        const jqTable = window.$('#resultsTable').DataTable();
        
        // Pausar cualquier procesamiento de DataTable
        try {
          jqTable.processing(false);
        } catch (e) {
          // Ignorar error si processing() no está disponible
        }
        
        // Destruir la instancia
        jqTable.destroy(false); // false = conservar HTML
        console.log('✅ DataTable destruida con jQuery (método seguro)');
      } else {
        // Método alternativo con API nativa de DataTable
        const dt = new DataTable('#resultsTable');
        dt.destroy(false);
        console.log('✅ DataTable destruida con API nativa');
      }
      
    } catch (error) {
      console.warn('⚠️ Error al destruir DataTable, aplicando limpieza manual...', error);
      
      // ✅ LIMPIEZA MANUAL: Remover todas las referencias de DataTable del DOM
      try {
        // Limpiar clases y atributos de DataTable del elemento table
        if (table) {
          table.classList.remove('dataTable', 'table-striped', 'table-bordered');
          table.removeAttribute('role');
          table.removeAttribute('aria-describedby');
          table.removeAttribute('style');
          
          // Limpiar headers
          const headers = table.querySelectorAll('thead th');
          headers.forEach(header => {
            header.removeAttribute('class');
            header.removeAttribute('style');
            header.removeAttribute('aria-label');
            header.removeAttribute('aria-sort');
            header.removeAttribute('tabindex');
          });
          
          // Limpiar filas del tbody
          const rows = table.querySelectorAll('tbody tr');
          rows.forEach(row => {
            row.removeAttribute('class');
            row.removeAttribute('style');
            row.removeAttribute('role');
          });
        }
        
        console.log('✅ Limpieza manual de DataTable completada');
      } catch (manualError) {
        console.warn('⚠️ Error en limpieza manual, continuando...', manualError);
      }
    }
  }
  
  // Siempre resetear la variable (actualizado para Grid.js)
  urlsGridTable = null;
  console.log('✅ Variable urlsGridTable reseteada');
  
  // 2. Limpiar completamente el DOM de la tabla
  if (table) {
    // ✅ MEJORADO: Limpieza más agresiva del DOM
    
    // Remover cualquier wrapper de DataTable
    const wrapper = table.closest('.dataTables_wrapper');
    if (wrapper && wrapper !== table.parentNode) {
      const parent = wrapper.parentNode;
      parent.insertBefore(table, wrapper);
      wrapper.remove();
      console.log('✅ Wrapper de DataTable removido');
    }
    
    // Limpiar todas las clases y atributos de DataTable
    table.classList.remove('dataTable', 'table-striped', 'table-bordered', 'dataTable');
    table.removeAttribute('role');
    table.removeAttribute('aria-describedby');
    table.removeAttribute('style');
    
    // Limpiar ID único que DataTable puede añadir
    const tableId = table.getAttribute('id');
    if (tableId && tableId !== 'resultsTable') {
      table.setAttribute('id', 'resultsTable');
    }
  }
  
  // 3. Limpiar contenido del tbody
  if (elems.tableBody) {
    elems.tableBody.innerHTML = '';
    console.log('✅ Contenido tbody limpiado');
  }
  
  // 4. Resetear headers de tabla a valores por defecto
  if (table) {
    const headers = table.querySelectorAll('thead th');
    if (headers.length >= 13) {
      // Resetear headers a estado por defecto (comparación)
      const headerTexts = [
        'Keywords',
        'URL',
        'Clicks P1', 'Clicks P2', 'ΔClicks (%)',
        'Impressions P1', 'Impressions P2', 'ΔImp. (%)',
        'CTR P1 (%)', 'CTR P2 (%)', 'ΔCTR (%)',
        'Pos P1', 'Pos P2', 'ΔPos'
      ];
      
      headers.forEach((header, index) => {
        if (index < headerTexts.length) {
          header.textContent = headerTexts[index];
          header.style.display = '';
          header.removeAttribute('class');
          header.removeAttribute('style');
          header.removeAttribute('aria-label');
          header.removeAttribute('aria-sort');
          header.removeAttribute('tabindex');
        }
      });
      
      console.log('✅ Headers de tabla reseteados');
    }
  }
  
  // 5. ✅ NUEVO: Limpiar cualquier elemento relacionado con DataTable en el DOM
  const relatedElements = document.querySelectorAll(
    '.dataTables_length, .dataTables_filter, .dataTables_info, .dataTables_paginate, .dataTables_processing'
  );
  relatedElements.forEach(el => {
    if (el.id && el.id.includes('resultsTable')) {
      el.remove();
    }
  });
  
  // 6. ✅ NUEVO: Forzar garbage collection de eventos si es posible
  if (window.jQuery) {
    try {
      window.jQuery('#resultsTable').off();
      console.log('✅ Event listeners limpiados con jQuery');
    } catch (e) {
      // Silencioso, no es crítico
    }
  }
  
  console.log('✅ Limpieza completa de tabla anterior finalizada');
}

/**
 * ✅ NUEVA FUNCIÓN: Asegurar que la estructura HTML de la tabla existe
 */
function ensureTableStructure() {
  let table = document.getElementById('resultsTable');
  
  if (!table) {
    console.log('🔧 Tabla no existe, recreando estructura HTML...');
    
    const resultsBlock = document.getElementById('resultsBlock');
    if (!resultsBlock) {
      console.error('❌ No se encontró resultsBlock para crear la tabla');
      return false;
    }
    
    // Crear la estructura HTML completa de la tabla
    const tableHTML = `
      <table id="resultsTable" class="display" aria-live="polite" style="width:100%;">
        <thead>
          <tr>
            <th>Keywords</th>
            <th>URL</th>
            <th>Clicks P1</th>
            <th>Clicks P2</th>
            <th>ΔClicks (%)</th>
            <th>Impressions P1</th>
            <th>Impressions P2</th>
            <th>ΔImp. (%)</th>
            <th>CTR P1 (%)</th>
            <th>CTR P2 (%)</th>
            <th>ΔCTR (%)</th>
            <th>Pos P1</th>
            <th>Pos P2</th>
            <th>ΔPos</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    `;
    
    resultsBlock.innerHTML = tableHTML;
    
    // Actualizar referencia de elems.tableBody
    elems.tableBody = document.getElementById('tableBody');
    
    console.log('✅ Estructura HTML de tabla recreada');
    return true;
  }
  
  // Verificar que el tbody existe
  if (!elems.tableBody) {
    elems.tableBody = table.querySelector('tbody');
    if (!elems.tableBody) {
      console.warn('⚠️ tbody no encontrado, añadiendo...');
      const tbody = document.createElement('tbody');
      tbody.id = 'tableBody';
      table.appendChild(tbody);
      elems.tableBody = tbody;
    }
  }
  
  console.log('✅ Estructura de tabla verificada');
  return true;
}

// ✅ MIGRADO A GRID.JS: renderTable para manejar comparación de URLs
export async function renderTable(pages) {
  console.log('🚀 Renderizando tabla de URLs con Grid.js...', { 
    pagesCount: pages?.length, 
    pagesType: typeof pages, 
    pagesData: pages ? pages.slice(0, 2) : 'null' 
  });
  
  // ✅ Limpiar tabla Grid.js anterior si existe
  if (urlsGridTable && urlsGridTable.destroy) {
    try {
      urlsGridTable.destroy();
      console.log('✅ Grid.js anterior destruido');
    } catch (e) {
      console.warn('⚠️ Error destruyendo Grid.js anterior:', e);
    }
    urlsGridTable = null;
  }
  
  // ✅ Obtener contenedor para Grid.js
  elems.resultsSection = document.getElementById('resultsBlock');
  elems.resultsTitle = document.querySelector('.results-title');
  
  if (!elems.resultsSection) {
    console.error('❌ No se pudo obtener contenedor para Grid.js');
    return;
  }
  
  if (!pages || !pages.length) {
    console.log('⚠️ No hay datos de páginas para mostrar');
    
    // Mostrar mensaje con Grid.js
    const emptyContainer = document.createElement('div');
    emptyContainer.className = 'no-aio-message';
    emptyContainer.innerHTML = `
      <i class="fas fa-info-circle"></i>
      <h3>No URLs Found</h3>
      <p>No URL data available to display for the selected period.</p>
    `;
    
    elems.resultsSection.innerHTML = '';
    elems.resultsSection.appendChild(emptyContainer);
    
    if (elems.resultsTitle) elems.resultsTitle.innerHTML = 'Performance <span class="pg-title-accent">URLs</span>';
    
    const urlsSubtitle = document.querySelector('.urls-overview-subtitle');
    if (urlsSubtitle) {
      urlsSubtitle.style.display = 'block';
      console.log('✅ Subtítulo de URLs mostrado (sin datos)');
    }
    
    return;
  }

  // ✅ Procesar datos de URLs
  const urlsData = processUrlsData(pages);
  
  // ✅ Determinar tipo de análisis
  const periods = window.currentData && window.currentData.periods ? window.currentData.periods : null;
  const analysisType = getUrlAnalysisType(pages, periods);
  
  console.log(`📊 Tipo de análisis URLs: ${analysisType}, URLs: ${urlsData.length}`);
  console.log('📋 Datos procesados:', urlsData.slice(0, 3)); // Log primeros 3 para debugging

  // ✅ CREAR TABLA GRID.JS
  try {
    console.log('🔧 Creando tabla Grid.js...', { 
      analysisType, 
      rowsCount: urlsData.length
    });
    
    // Crear Grid.js table
    urlsGridTable = createUrlsGridTable(urlsData, analysisType, elems.resultsSection);
    
    if (urlsGridTable) {
      console.log('✅ Tabla Grid.js creada exitosamente');
    } else {
      console.warn('⚠️ No se pudo crear tabla Grid.js');
    }
    
  } catch (error) {
    console.error('❌ Error al crear tabla Grid.js:', error);
    
    // Fallback - mostrar mensaje de error
    const errorContainer = document.createElement('div');
    errorContainer.className = 'no-aio-message';
    errorContainer.innerHTML = `
      <i class="fas fa-exclamation-triangle"></i>
      <h3>Error Loading Table</h3>
      <p>There was an error loading the URLs table. Please try refreshing the page.</p>
    `;
    
    elems.resultsSection.innerHTML = '';
    elems.resultsSection.appendChild(errorContainer);
  }
  


  // ✅ SIDEBAR: El contenido está listo, notificar al sidebar que puede mostrar la sección
  console.log('✅ Pages content ready - sidebar can show it when user navigates');
  
  if (elems.resultsTitle) {
    // ✅ SIDEBAR: No mostrar automáticamente, pero sí actualizar el contenido
    // elems.resultsTitle.style.display = 'block';
    
    // ✅ NUEVO: Título simple y consistente como keywords
    elems.resultsTitle.innerHTML = 'Performance <span class="pg-title-accent">URLs</span>';
    console.log('✅ Título actualizado: URLs Performance');
  }
  
  // ✅ NUEVO: Mostrar subtítulo explícitamente (igual que en keywords)
  const urlsSubtitle = document.querySelector('.urls-overview-subtitle');
  if (urlsSubtitle) {
    urlsSubtitle.style.display = 'block';
    console.log('✅ Subtítulo de URLs mostrado');
  }
  
  console.log('✅ Tabla de URLs actualizada completamente');
  
  // ✅ NUEVO: Verificación final para asegurar que la tabla es visible
  setTimeout(() => {
    const resultsSection = document.getElementById('resultsSection') || elems.resultsSection;
    const resultsTitle = document.getElementById('resultsTitle') || elems.resultsTitle;
    const tableElement = document.getElementById('resultsTable');
    
    // ✅ SIDEBAR: Las secciones se muestran solo cuando el usuario navega a ellas desde el sidebar
    // if (resultsSection && resultsSection.style.display !== 'block') {
    //   console.warn('⚠️ Sección de resultados no visible, forzando visibilidad...');
    //   resultsSection.style.display = 'block';
    // }
    
    // ✅ SIDEBAR: Las secciones se muestran solo cuando el usuario navega a ellas desde el sidebar
    // if (resultsTitle && resultsTitle.style.display !== 'block') {
    //   console.warn('⚠️ Título de resultados no visible, forzando visibilidad...');
    //   resultsTitle.style.display = 'block';
    //   resultsTitle.textContent = 'URLs Performance';
    // }
    
    if (tableElement && !tableElement.offsetParent) {
      console.warn('⚠️ Tabla no visible, verificando estructura...');
      ensureTableStructure();
    }
    
    console.log('🔍 Verificación final de visibilidad completada');
  }, 100);
}

// ✅ MEJORADO: renderTableError con limpieza robusta
export function renderTableError() {
  console.log('❌ Renderizando estado de error en tabla de URLs...');
  
  // ✅ Usar la función de limpieza robusta
  cleanupPreviousTable();
  
  // Mostrar mensaje de error
  if (elems.tableBody) {
    elems.tableBody.innerHTML = '<tr><td colspan="14">Error al procesar la solicitud.</td></tr>';
  }
  
  // ✅ SIDEBAR: El contenido está listo, notificar al sidebar que puede mostrar la sección
  console.log('✅ Pages content ready - sidebar can show it when user navigates (error state)');
  
  if (elems.resultsTitle) {
    // ✅ SIDEBAR: No mostrar automáticamente, pero sí actualizar el contenido
    // elems.resultsTitle.style.display = 'block';
    elems.resultsTitle.innerHTML = 'Performance <span class="pg-title-accent">URLs</span>';
    console.log('✅ Título actualizado (estado error)');
  }
  
  // ✅ NUEVO: Mostrar subtítulo también en estado de error
  const urlsSubtitle = document.querySelector('.urls-overview-subtitle');
  if (urlsSubtitle) {
    urlsSubtitle.style.display = 'block';
    console.log('✅ Subtítulo de URLs mostrado (estado error)');
  }
}

// ✅ NUEVO: Función para filtrar keywords por rango de posiciones
function filterKeywordsByPosition(keywordData, positionRange) {
  if (!keywordData || keywordData.length === 0) return [];
  
  return keywordData.filter(keyword => {
    const position = keyword.position_m1;
    if (typeof position !== 'number') return false;
    
    switch (positionRange) {
      case 'top3':
        return position >= 1 && position <= 3;
      case 'top10':
        return position >= 4 && position <= 10;
      case 'top20':
        return position >= 11 && position <= 20;
      case 'top20plus':
        return position > 20;
      default:
        return true;
    }
  });
}

// ✅ MIGRADO A GRID.JS: Variables para almacenar datos pre-procesados y Grid.js del modal
let preProcessedModalData = createInitialKeywordModalState();

let modalContainersCreated = false;

function createKeywordModalTableSkeleton(rowCount = 8) {
  const rows = Array.from({ length: rowCount }, () => `
    <div class="keyword-modal-skeleton-row">
      <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-serp"></span>
      <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-keyword"></span>
      <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-url"></span>
      <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-metric"></span>
      <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-metric"></span>
      <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-metric"></span>
    </div>
  `).join('');

  return `
    <div class="keyword-modal-skeleton" aria-hidden="true">
      <div class="keyword-modal-skeleton-row keyword-modal-skeleton-row-header">
        <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-serp"></span>
        <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-keyword"></span>
        <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-url"></span>
        <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-metric"></span>
        <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-metric"></span>
        <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-metric"></span>
      </div>
      ${rows}
      <div class="keyword-modal-skeleton-footer">
        <span class="keyword-modal-skeleton-cell keyword-modal-skeleton-cell-footer"></span>
      </div>
    </div>
  `;
}

function renderKeywordModalTableSkeleton(container, rowCount = 8) {
  if (!container) return;
  container.innerHTML = createKeywordModalTableSkeleton(rowCount);
}

// ✅ NUEVO: Funciones auxiliares para el modal (replicadas de ui-keyword-comparison-table.js)
function getAnalysisTypeModal(keywordData) {
  if (!keywordData || keywordData.length === 0) return 'empty';
  
  // ✅ CORREGIDO: Usar la misma lógica que las tablas principales
  const periods = window.currentData && window.currentData.periods ? window.currentData.periods : null;
  
  if (periods && periods.has_comparison && periods.comparison) {
    console.log('🔍 Usuario seleccionó comparación explícitamente para modal - forzando modo comparison');
    return 'comparison';
  }
  
  // Verificar si hay datos de comparación reales (lógica original)
  const hasComparison = keywordData.some(row => 
    (row.clicks_m2 > 0 || row.impressions_m2 > 0) && 
    row.delta_clicks_percent !== 'New'
  );
  
  return hasComparison ? 'comparison' : 'single';
}

// ✅ REMOVIDO: Funciones Modal duplicadas - ahora se usan las del módulo centralizado

function updateModalTableHeaders(analysisType) {
  const table = document.getElementById('keywordModalTable');
  if (!table) return;
  
  const headers = table.querySelectorAll('thead th');
  
  if (analysisType === 'single') {
    // Headers para período único
    if (headers[2]) headers[2].textContent = 'Clicks';
    if (headers[3]) headers[3].style.display = 'none'; // Ocultar P2
    if (headers[4]) headers[4].style.display = 'none'; // Ocultar Delta
    if (headers[5]) headers[5].textContent = 'Impressions';
    if (headers[6]) headers[6].style.display = 'none'; // Ocultar P2
    if (headers[7]) headers[7].style.display = 'none'; // Ocultar Delta
    if (headers[8]) headers[8].textContent = 'CTR (%)';
    if (headers[9]) headers[9].style.display = 'none'; // Ocultar P2
    if (headers[10]) headers[10].style.display = 'none'; // Ocultar Delta
    if (headers[11]) headers[11].textContent = 'Position';
    if (headers[12]) headers[12].style.display = 'none'; // Ocultar P2
    if (headers[13]) headers[13].style.display = 'none'; // Ocultar Delta
  } else {
    // Headers para comparación (mostrar todos)
    if (headers[2]) headers[2].textContent = 'Clicks P1';
    if (headers[3]) {
      headers[3].style.display = '';
      headers[3].textContent = 'Clicks P2';
    }
    if (headers[4]) {
      headers[4].style.display = '';
      headers[4].textContent = 'ΔClicks (%)';
    }
    if (headers[5]) headers[5].textContent = 'Impressions P1';
    if (headers[6]) {
      headers[6].style.display = '';
      headers[6].textContent = 'Impressions P2';
    }
    if (headers[7]) {
      headers[7].style.display = '';
      headers[7].textContent = 'ΔImp. (%)';
    }
    if (headers[8]) headers[8].textContent = 'CTR P1 (%)';
    if (headers[9]) {
      headers[9].style.display = '';
      headers[9].textContent = 'CTR P2 (%)';
    }
    if (headers[10]) {
      headers[10].style.display = '';
      headers[10].textContent = 'ΔCTR (%)';
    }
    if (headers[11]) headers[11].textContent = 'Pos P1';
    if (headers[12]) {
      headers[12].style.display = '';
      headers[12].textContent = 'Pos P2';
    }
    if (headers[13]) {
      headers[13].style.display = '';
      headers[13].textContent = 'ΔPos';
    }
  }
}

// ✅ NUEVO: Función para actualizar headers de la tabla según el tipo de análisis para un rango específico
function updateModalTableHeadersForRange(range, analysisType) {
  const table = document.getElementById(`keywordModalTable-${range}`);
  if (!table) return;
  
  const headers = table.querySelectorAll('thead th');
  
  if (analysisType === 'single') {
    // Headers para período único
    if (headers[2]) headers[2].textContent = 'Clicks';
    if (headers[3]) headers[3].style.display = 'none'; // Ocultar P2
    if (headers[4]) headers[4].style.display = 'none'; // Ocultar Delta
    if (headers[5]) headers[5].textContent = 'Impressions';
    if (headers[6]) headers[6].style.display = 'none'; // Ocultar P2
    if (headers[7]) headers[7].style.display = 'none'; // Ocultar Delta
    if (headers[8]) headers[8].textContent = 'CTR (%)';
    if (headers[9]) headers[9].style.display = 'none'; // Ocultar P2
    if (headers[10]) headers[10].style.display = 'none'; // Ocultar Delta
    if (headers[11]) headers[11].textContent = 'Position';
    if (headers[12]) headers[12].style.display = 'none'; // Ocultar P2
    if (headers[13]) headers[13].style.display = 'none'; // Ocultar Delta
  } else {
    // Headers para comparación (mostrar todos)
    if (headers[2]) headers[2].textContent = 'Clicks P1';
    if (headers[3]) {
      headers[3].style.display = '';
      headers[3].textContent = 'Clicks P2';
    }
    if (headers[4]) {
      headers[4].style.display = '';
      headers[4].textContent = 'ΔClicks (%)';
    }
    if (headers[5]) headers[5].textContent = 'Impressions P1';
    if (headers[6]) {
      headers[6].style.display = '';
      headers[6].textContent = 'Impressions P2';
    }
    if (headers[7]) {
      headers[7].style.display = '';
      headers[7].textContent = 'ΔImp. (%)';
    }
    if (headers[8]) headers[8].textContent = 'CTR P1 (%)';
    if (headers[9]) {
      headers[9].style.display = '';
      headers[9].textContent = 'CTR P2 (%)';
    }
    if (headers[10]) {
      headers[10].style.display = '';
      headers[10].textContent = 'ΔCTR (%)';
    }
    if (headers[11]) headers[11].textContent = 'Pos P1';
    if (headers[12]) {
      headers[12].style.display = '';
      headers[12].textContent = 'Pos P2';
    }
    if (headers[13]) {
      headers[13].style.display = '';
      headers[13].textContent = 'ΔPos';
    }
  }
}

// ✅ NUEVO: Función para abrir el modal de keywords (versión optimizada con pre-procesamiento)
function openKeywordModal(modalKey, label = '') {
  console.log('🔍 Opening modal for range:', modalKey, 'label:', label);
  
  // Verificar que los datos estén pre-procesados
  if (!preProcessedModalData[modalKey]) {
    console.error('❌ No pre-processed data found for range:', modalKey);
    return;
  }
  
  const data = preProcessedModalData[modalKey];
  const fallbackLabel = KEYWORD_MODAL_META[modalKey]?.title || modalKey;
  const modalLabel = label || fallbackLabel;
  
  if (data.keywords.length === 0) {
    console.log('⚠️  No keywords in this selected keyword group');
    return;
  }
  
  // Verificar que los contenedores estén creados
  if (!modalContainersCreated) {
    createAllModalContainers();
  }
  
  // Verificar que el modal específico existe
  const modal = document.getElementById(`keywordModal-${modalKey}`);
  if (!modal) {
    console.error('❌ Modal no encontrado para rango:', modalKey);
    return;
  }

  const modalTitleEl = document.getElementById(`keywordModalTitle-${modalKey}`);
  if (modalTitleEl) {
    modalTitleEl.innerHTML = `<i class="fas fa-search"></i> ${escapeHtml(modalLabel)}`;
  }
  
  // Verificar que la Grid.js tabla está lista
  if (!data.gridTable && !data.isLoading && data.keywords.length > 0) {
    console.log('🔄 Grid.js table not ready, creating...');
    data.isLoading = true;
    // No usar await aquí para mantener la apertura instantánea del modal
    createGridTableForRange(modalKey, data.keywords, data.analysisType).catch(error => {
      console.error(`❌ Error creating Grid.js table for ${modalKey}:`, error);
    }).finally(() => {
      data.isLoading = false;
    });
  } else if (!data.gridTable && data.isLoading) {
    const loadingContainer = document.getElementById(`keywordModalTableContainer-${modalKey}`);
    if (loadingContainer && !loadingContainer.querySelector('.keyword-modal-skeleton')) {
      renderKeywordModalTableSkeleton(loadingContainer);
    }
  }
  
  // Mostrar el modal instantáneamente
  modal.classList.add('modal-open');
  document.body.style.overflow = 'hidden';
  
  console.log(`✅ Modal opened instantly for: ${modalLabel} (${data.keywords.length} keywords)`);
}

// ✅ NUEVO: Función para crear todos los contenedores de modales
function createAllModalContainers() {
  if (modalContainersCreated) return;
  
  console.log('🔍 Creating preloaded modal containers...');

  Object.entries(KEYWORD_MODAL_META).forEach(([range, meta]) => {
    const modalHTML = `
      <div id="keywordModal-${range}" class="modal">
        <div class="modal-content">
          <div class="modal-header">
            <h3 id="keywordModalTitle-${range}"><i class="fas fa-search"></i> ${meta.title}</h3>
            <span class="close-btn" onclick="closeKeywordModal('${range}')">&times;</span>
          </div>
          <div class="modal-body">
            <div class="keyword-modal-info">
              <i class="fas fa-info-circle"></i>
              <span>${meta.info}</span>
            </div>
            <div id="keywordModalTableContainer-${range}" class="table-responsive-container">
              <!-- Grid.js table will be inserted here -->
            </div>
          </div>
        </div>
      </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Agregar event listener para cerrar el modal al hacer click fuera
    const modal = document.getElementById(`keywordModal-${range}`);
    if (modal) {
      modal.addEventListener('click', function(event) {
        if (event.target === modal) {
          closeKeywordModal(range);
        }
      });
    }
  });
  
  modalContainersCreated = true;
  console.log('✅ Modal containers created for all ranges');
}

// ✅ MIGRADO A GRID.JS: Función para crear Grid.js table para un rango específico
async function createGridTableForRange(range, keywords, analysisType) {
  // Destruir Grid.js anterior si existe
  if (preProcessedModalData[range].gridTable && preProcessedModalData[range].gridTable.destroy) {
    try {
      preProcessedModalData[range].gridTable.destroy();
      console.log(`✅ Grid.js anterior destruido para ${range}`);
    } catch (e) {
      console.warn(`⚠️ Error destruyendo Grid.js anterior para ${range}:`, e);
    }
    preProcessedModalData[range].gridTable = null;
  }

  const containerId = `keywordModalTableContainer-${range}`;
  const container = document.getElementById(containerId);
  
  if (!container) {
    console.error(`❌ Container not found for ${range}`);
    return;
  }

  console.log(`🔄 Creating Grid.js table for ${range} with ${keywords.length} keywords...`);
  const startTime = performance.now();
  
  if (keywords.length === 0) {
    container.innerHTML = `
      <div class="no-aio-message">
        <i class="fas fa-search"></i>
        <h3>No Keywords Found</h3>
        <p>No keywords found in this selected group.</p>
      </div>
    `;
    return;
  }

  renderKeywordModalTableSkeleton(container);

  // ✅ CREAR TABLA GRID.JS usando el módulo creado
  try {
    // Limpiar completamente el contenedor antes de crear la tabla
    container.innerHTML = '';
    
    // Importar dinámicamente para evitar dependencias circulares
    const { createKeywordsGridTable } = await import('./ui-keywords-gridjs.js');
    preProcessedModalData[range].gridTable = createKeywordsGridTable(keywords, analysisType, container);
    
    if (preProcessedModalData[range].gridTable) {
      const endTime = performance.now();
      console.log(`✅ Grid.js table for ${range} created in ${(endTime - startTime).toFixed(2)}ms`);
    } else {
      console.warn(`⚠️ Could not create Grid.js table for ${range}`);
    }
    
  } catch (error) {
    console.error(`❌ Error creating Grid.js table for ${range}:`, error);
    
    // Fallback - mostrar mensaje de error
    container.innerHTML = `
      <div class="no-aio-message">
        <i class="fas fa-exclamation-triangle"></i>
        <h3>Error Loading Keywords</h3>
        <p>There was an error loading the keywords table. Please try again.</p>
      </div>
    `;
  }
}

// ✅ NUEVO: Función para cerrar el modal
function closeKeywordModal(range = null) {
  // Si no se especifica rango, cerrar todos los modales
  if (!range) {
    const ranges = Object.keys(KEYWORD_MODAL_META);
    ranges.forEach(r => {
      const modal = document.getElementById(`keywordModal-${r}`);
      if (modal && modal.classList.contains('modal-open')) {
        modal.classList.remove('modal-open');
      }
    });
    document.body.style.overflow = '';
    console.log('✅ Todos los modales cerrados');
    return;
  }
  
  // Cerrar modal específico
  const modal = document.getElementById(`keywordModal-${range}`);
  if (modal) {
    modal.classList.remove('modal-open');
    document.body.style.overflow = '';
  }
  
  console.log(`✅ Modal cerrado para rango: ${range}`);
}

function toValidKeywordPosition(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function toNumericMetric(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function sortByCurrentClicksDesc(a, b) {
  return toNumericMetric(b?.clicks_m1) - toNumericMetric(a?.clicks_m1);
}

function sortByPreviousClicksDesc(a, b) {
  return toNumericMetric(b?.clicks_m2) - toNumericMetric(a?.clicks_m2);
}

function sortByPositionGainDesc(a, b) {
  const gainA = (toValidKeywordPosition(a?.position_m2) || 0) - (toValidKeywordPosition(a?.position_m1) || 0);
  const gainB = (toValidKeywordPosition(b?.position_m2) || 0) - (toValidKeywordPosition(b?.position_m1) || 0);
  return gainB - gainA || sortByCurrentClicksDesc(a, b);
}

function sortByPositionLossDesc(a, b) {
  const lossA = (toValidKeywordPosition(a?.position_m1) || 0) - (toValidKeywordPosition(a?.position_m2) || 0);
  const lossB = (toValidKeywordPosition(b?.position_m1) || 0) - (toValidKeywordPosition(b?.position_m2) || 0);
  return lossB - lossA || sortByPreviousClicksDesc(a, b);
}

// ✅ NUEVO: Función para pre-procesar datos por rangos de posición y estado
function preprocessKeywordDataByRanges(keywordData) {
  Object.keys(KEYWORD_MODAL_META).forEach((modalKey) => {
    if (!preProcessedModalData[modalKey]) {
      preProcessedModalData[modalKey] = { keywords: [], gridTable: null, analysisType: 'single', isLoading: false };
    }
  });

  if (!keywordData || keywordData.length === 0) {
    // Limpiar datos existentes
    Object.keys(preProcessedModalData).forEach(range => {
      preProcessedModalData[range].keywords = [];
      if (preProcessedModalData[range].gridTable && preProcessedModalData[range].gridTable.destroy) {
        try {
          preProcessedModalData[range].gridTable.destroy();
        } catch (e) {
          console.warn(`⚠️ Error al limpiar Grid.js anterior para ${range}:`, e);
        }
        preProcessedModalData[range].gridTable = null;
      }
      preProcessedModalData[range].isLoading = false;
    });
    return;
  }

  console.log('🔄 Pre-procesando keywords por rangos y tendencias...');
  const startTime = performance.now();

  // Determinar tipo de análisis una vez
  const analysisType = getAnalysisTypeModal(keywordData);

  // Clasificar keywords por rangos
  const groupedRows = {
    top3: keywordData
      .filter((kw) => {
        const pos = toValidKeywordPosition(kw?.position_m1);
        return pos !== null && pos >= 1 && pos <= 3;
      })
      .sort(sortByCurrentClicksDesc),

    top10: keywordData
      .filter((kw) => {
        const pos = toValidKeywordPosition(kw?.position_m1);
        return pos !== null && pos >= 4 && pos <= 10;
      })
      .sort(sortByCurrentClicksDesc),

    top20: keywordData
      .filter((kw) => {
        const pos = toValidKeywordPosition(kw?.position_m1);
        return pos !== null && pos >= 11 && pos <= 20;
      })
      .sort(sortByCurrentClicksDesc),

    top20plus: keywordData
      .filter((kw) => {
        const pos = toValidKeywordPosition(kw?.position_m1);
        return pos !== null && pos > 20;
      })
      .sort(sortByCurrentClicksDesc),

    improved: [],
    worsened: [],
    same: [],
    new: [],
    lost: []
  };

  keywordData.forEach((kw) => {
    const currentPosition = toValidKeywordPosition(kw?.position_m1);
    const previousPosition = toValidKeywordPosition(kw?.position_m2);

    if (currentPosition !== null && previousPosition !== null) {
      if (currentPosition < previousPosition) {
        groupedRows.improved.push(kw);
      } else if (currentPosition > previousPosition) {
        groupedRows.worsened.push(kw);
      } else {
        groupedRows.same.push(kw);
      }
      return;
    }

    if (currentPosition !== null && previousPosition === null) {
      groupedRows.new.push(kw);
      return;
    }

    if (currentPosition === null && previousPosition !== null) {
      groupedRows.lost.push(kw);
    }
  });

  groupedRows.improved.sort(sortByPositionGainDesc);
  groupedRows.worsened.sort(sortByPositionLossDesc);
  groupedRows.same.sort(sortByCurrentClicksDesc);
  groupedRows.new.sort(sortByCurrentClicksDesc);
  groupedRows.lost.sort(sortByPreviousClicksDesc);

  // Actualizar datos pre-procesados
  Object.keys(KEYWORD_MODAL_META).forEach((modalKey) => {
    preProcessedModalData[modalKey].keywords = groupedRows[modalKey] || [];
    preProcessedModalData[modalKey].analysisType = analysisType;
    preProcessedModalData[modalKey].isLoading = false;
  });

  const endTime = performance.now();
  console.log(`✅ Keywords pre-procesadas en ${(endTime - startTime).toFixed(2)}ms:`, {
    top3: groupedRows.top3.length,
    top10: groupedRows.top10.length,
    top20: groupedRows.top20.length,
    top20plus: groupedRows.top20plus.length,
    improved: groupedRows.improved.length,
    worsened: groupedRows.worsened.length,
    same: groupedRows.same.length,
    new: groupedRows.new.length,
    lost: groupedRows.lost.length,
    analysisType: analysisType
  });

  // Optimización: no pre-cargar tablas de modal.
  // Se crearán bajo demanda al abrir cada modal para reducir tiempo de carga inicial.
}

// ✅ NUEVO: Función para actualizar los datos globales de keywords
export function updateGlobalKeywordData(keywordData) {
  globalKeywordData = keywordData || [];
  console.log('📊 Datos globales de keywords actualizados:', globalKeywordData.length);
  
  // Pre-procesar inmediatamente
  preprocessKeywordDataByRanges(keywordData);
}

// ✅ NUEVO: Función auxiliar para escapar HTML
function escapeHtml(text) {
  if (typeof text !== 'string') return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ✅ NUEVO: Hacer las funciones globales para que puedan ser llamadas desde onclick
window.openKeywordModal = openKeywordModal;
window.closeKeywordModal = closeKeywordModal;

// ✅ SISTEMA DE CACHÉ para keywords por URL
const urlKeywordsCache = {
  data: new Map(),
  maxAge: 10 * 60 * 1000, // 10 minutos
  
  getCacheKey(url, periods) {
    return `${url}|${periods.current?.start_date}|${periods.current?.end_date}|${periods.has_comparison}|${periods.comparison?.start_date}`;
  },
  
  get(url, periods) {
    const key = this.getCacheKey(url, periods);
    const cached = this.data.get(key);
    
    if (!cached) return null;
    
    // Verificar si el caché expiró
    if (Date.now() - cached.timestamp > this.maxAge) {
      this.data.delete(key);
      return null;
    }
    
    console.log('⚡ [URL KEYWORDS CACHE] Datos encontrados en caché para:', url);
    return cached.data;
  },
  
  set(url, periods, data) {
    const key = this.getCacheKey(url, periods);
    this.data.set(key, {
      data: data,
      timestamp: Date.now()
    });
    console.log('💾 [URL KEYWORDS CACHE] Datos guardados en caché para:', url);
  },
  
  clear() {
    this.data.clear();
    console.log('🧹 [URL KEYWORDS CACHE] Caché limpiado');
  }
};

// Limpiar caché cuando se hace un nuevo análisis
document.addEventListener('newAnalysisStarted', () => {
  urlKeywordsCache.clear();
});

// ✅ NUEVO: Skeleton Loader para mejorar percepción de velocidad
function createSkeletonLoader() {
  return `
    <div class="skeleton-loader-container" style="padding: 1em;">
      <!-- Info skeleton -->
      <div class="skeleton-box" style="height: 120px; margin-bottom: 1em; border-radius: 5px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
      
      <!-- Search bar skeleton -->
      <div class="skeleton-box" style="height: 40px; margin-bottom: 1em; border-radius: 5px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
      
      <!-- Table skeleton -->
      <div class="skeleton-table">
        <!-- Header -->
        <div class="skeleton-row" style="display: flex; gap: 10px; margin-bottom: 10px;">
          <div class="skeleton-box" style="flex: 0 0 80px; height: 35px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
          <div class="skeleton-box" style="flex: 1; height: 35px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
          <div class="skeleton-box" style="flex: 0 0 100px; height: 35px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
          <div class="skeleton-box" style="flex: 0 0 100px; height: 35px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
          <div class="skeleton-box" style="flex: 0 0 100px; height: 35px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
        </div>
        
        <!-- Rows -->
        ${Array.from({length: 8}, () => `
          <div class="skeleton-row" style="display: flex; gap: 10px; margin-bottom: 8px;">
            <div class="skeleton-box" style="flex: 0 0 80px; height: 30px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
            <div class="skeleton-box" style="flex: 1; height: 30px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
            <div class="skeleton-box" style="flex: 0 0 100px; height: 30px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
            <div class="skeleton-box" style="flex: 0 0 100px; height: 30px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
            <div class="skeleton-box" style="flex: 0 0 100px; height: 30px; border-radius: 3px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
          </div>
        `).join('')}
      </div>
      
      <!-- Pagination skeleton -->
      <div class="skeleton-box" style="height: 40px; margin-top: 1em; border-radius: 5px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: skeleton-loading 1.5s infinite;"></div>
    </div>
    
    <style>
      @keyframes skeleton-loading {
        0% {
          background-position: 200% 0;
        }
        100% {
          background-position: -200% 0;
        }
      }
      
      .skeleton-loader-container {
        animation: fadeIn 0.3s ease-in;
      }
      
      @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }
    </style>
  `;
}

// ✅ NUEVO: Función para abrir el modal de keywords por URL
export function openUrlKeywordsModal(url) {
  console.log('🔍 Abriendo modal de keywords para URL:', url);
  
  // Crear modal dinámicamente si no existe
  let modal = document.getElementById('keywordModal-url');
  if (!modal) {
    createUrlKeywordsModal();
    modal = document.getElementById('keywordModal-url');
  }
  
  // Actualizar título del modal
  const modalTitle = document.getElementById('keywordModalTitle-url');
  if (modalTitle) {
    modalTitle.innerHTML = `<i class="fas fa-search"></i> Keywords for: ${escapeHtml(url)}`;
  }
  
  // ✅ OPTIMIZADO: Mostrar skeleton loader mientras carga
  const modalBody = document.getElementById('keywordModalBody-url');
  if (modalBody) {
    modalBody.innerHTML = createSkeletonLoader();
  }
  
  modal.classList.add('modal-open');
  document.body.style.overflow = 'hidden';
  
  // Obtener datos del último análisis desde el contexto global
  const currentData = window.currentData || {};
  const periods = currentData.periods || {};
  
  // ✅ DEBUG: Verificar períodos antes de enviar
  console.log('📅 [URL KEYWORDS] Períodos obtenidos de window.currentData:', {
    hasPeriods: !!periods,
    hasComparison: periods.has_comparison,
    current: periods.current,
    comparison: periods.comparison,
    fullCurrentData: currentData
  });
  
  // ✅ OPTIMIZACIÓN: Verificar si hay datos en caché
  const cachedData = urlKeywordsCache.get(url, periods);
  if (cachedData) {
    console.log('⚡ [URL KEYWORDS] Usando datos desde caché - apertura instantánea');
    renderUrlKeywordsData(cachedData);
    return;
  }
  
  // Si no hay caché, hacer petición al backend
  fetchUrlKeywords(url, periods).then(data => {
    // Guardar en caché antes de renderizar
    urlKeywordsCache.set(url, periods, data);
    renderUrlKeywordsData(data);
  }).catch(error => {
    console.error('Error obteniendo keywords:', error);
    if (modalBody) {
      renderErrorState(modalBody, error);
    }
  });
}

// ✅ NUEVO: Función para crear el modal HTML
function createUrlKeywordsModal() {
  const modalHTML = `
    <div id="keywordModal-url" class="modal">
      <div class="modal-content">
        <div class="modal-header">
          <h3 id="keywordModalTitle-url"><i class="fas fa-search"></i> Keywords by URL</h3>
          <span class="close-btn" onclick="closeKeywordModal('url')">&times;</span>
        </div>
        <div class="modal-body" id="keywordModalBody-url">
          <!-- Dynamic content -->
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modalHTML);
}

// ✅ NUEVO: Función para hacer la petición al backend
async function fetchUrlKeywords(url, periods) {
  const siteUrl = document.getElementById('siteUrlSelect')?.value || '';
  const selectedCountry = document.getElementById('countrySelect')?.value || '';
  
  const payload = {
    url: url,
    site_url: siteUrl,
    country: selectedCountry,
    current_start_date: periods.current?.start_date,
    current_end_date: periods.current?.end_date,
    comparison_start_date: periods.comparison?.start_date,
    comparison_end_date: periods.comparison?.end_date,
    has_comparison: periods.has_comparison || false
  };
  
  // ✅ DEBUG: Log del payload completo que se envía al backend
  console.log('📤 [URL KEYWORDS] Enviando payload al backend:', payload);
  console.log('📅 [URL KEYWORDS] Fechas enviadas:', {
    current: `${payload.current_start_date} → ${payload.current_end_date}`,
    comparison: payload.has_comparison ? `${payload.comparison_start_date} → ${payload.comparison_end_date}` : 'N/A',
    hasComparison: payload.has_comparison
  });
  
  const response = await fetch('/api/url-keywords', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    
    // ✅ NUEVO: Crear error mejorado con información del backend
    const error = new Error(errorData.error || `Error del servidor: ${response.status}`);
    error.url = url; // Preservar URL para retry buttons
    error.status = response.status;
    error.errorData = errorData; // Preservar datos estructurados del backend
    
    throw error;
  }
  
  return response.json();
}

// ✅ NUEVO: Función para renderizar estados de error específicos
function renderErrorState(modalBody, error) {
  let errorHTML = '';
  
  // Usar datos estructurados del backend si están disponibles
  const errorData = error.errorData || null;
  
  // Error de autenticación (403)
  if (error.message.includes('Authentication issue') || (errorData && errorData.error_type === 'auth_error')) {
    errorHTML = `
      <div class="error-container" style="text-align: center; padding: 2em;">
        <div class="error-icon" style="color: #ffc107; margin-bottom: 1em;">
          <i class="fas fa-exclamation-triangle" style="font-size: 3em;"></i>
        </div>
        <h3 style="color: #dc3545; margin-bottom: 1em;">Authentication Issue</h3>
        <p style="color: #666; margin-bottom: 1.5em;">
          ${errorData?.details || 'Your session may have expired or you may have lost access to this property in Search Console.'}
        </p>
        <div class="error-suggestions" style="background: #f8f9fa; padding: 1em; border-radius: 5px; margin-bottom: 1.5em;">
          <h4 style="margin-bottom: 0.5em; color: #495057;">💡 What you can try:</h4>
          <ul style="text-align: left; margin: 0; padding-left: 1.5em; color: #495057;">
            <li>Refresh the page to re-authenticate</li>
            <li>Verify you still have access to this property in Google Search Console</li>
            <li>Try logging out and logging back in</li>
          </ul>
        </div>
        <div class="error-actions">
          <button onclick="window.location.reload()" class="btn btn-primary" style="margin-right: 0.5em;">
            <i class="fas fa-sync-alt"></i> Refresh Page
          </button>
          <button onclick="closeKeywordModal('url')" class="btn btn-secondary">
            <i class="fas fa-times"></i> Close
          </button>
        </div>
      </div>
    `;
  }
  // Error de rate limit (429)
  else if (error.message.includes('Too many requests') || (errorData && errorData.error_type === 'rate_limit')) {
    errorHTML = `
      <div class="error-container" style="text-align: center; padding: 2em;">
        <div class="error-icon" style="color: #17a2b8; margin-bottom: 1em;">
          <i class="fas fa-clock" style="font-size: 3em;"></i>
        </div>
        <h3 style="color: #17a2b8; margin-bottom: 1em;">Rate Limit Exceeded</h3>
        <p style="color: #666; margin-bottom: 1.5em;">
          ${errorData?.details || 'Google Search Console API rate limit exceeded.'}
        </p>
        <div class="error-suggestions" style="background: #f8f9fa; padding: 1em; border-radius: 5px; margin-bottom: 1.5em;">
          <h4 style="margin-bottom: 0.5em; color: #495057;">💡 What you can try:</h4>
          <ul style="text-align: left; margin: 0; padding-left: 1.5em; color: #495057;">
            <li>Wait a few minutes and try again</li>
            <li>Avoid opening multiple modals simultaneously</li>
          </ul>
        </div>
        <div class="error-actions">
          <button onclick="setTimeout(() => { openUrlKeywordsModal('${escapeHtml(error.url || '')}'); closeKeywordModal('url'); }, 60000);" class="btn btn-primary" style="margin-right: 0.5em;">
            <i class="fas fa-clock"></i> Retry in 1 minute
          </button>
          <button onclick="closeKeywordModal('url')" class="btn btn-secondary">
            <i class="fas fa-times"></i> Close
          </button>
        </div>
      </div>
    `;
  }
  // Error genérico
  else {
    errorHTML = `
      <div class="error-container" style="text-align: center; padding: 2em;">
        <div class="error-icon" style="color: #dc3545; margin-bottom: 1em;">
          <i class="fas fa-exclamation-triangle" style="font-size: 3em;"></i>
        </div>
        <h3 style="color: #dc3545; margin-bottom: 1em;">Error Loading Keywords</h3>
        <p style="color: #666; margin-bottom: 1.5em;">
          ${errorData?.details || 'An unexpected error occurred while fetching keywords.'}
        </p>
        <details style="margin-bottom: 1.5em; text-align: left;">
          <summary style="cursor: pointer; color: #6c757d;">Technical Details</summary>
          <pre style="background: #f8f9fa; padding: 1em; margin-top: 0.5em; border-radius: 3px; font-size: 0.85em; overflow: auto;">${error.message}</pre>
        </details>
        <div class="error-actions">
          <button onclick="closeKeywordModal('url'); openUrlKeywordsModal('${escapeHtml(error.url || '')}');" class="btn btn-primary" style="margin-right: 0.5em;">
            <i class="fas fa-redo"></i> Try Again
          </button>
          <button onclick="closeKeywordModal('url')" class="btn btn-secondary">
            <i class="fas fa-times"></i> Close
          </button>
        </div>
      </div>
    `;
  }
  
  modalBody.innerHTML = errorHTML;
}

// ✅ MIGRADO A GRID.JS: Función para renderizar los datos en el modal con carga progresiva
function renderUrlKeywordsData(data) {
  const modalBody = document.getElementById('keywordModalBody-url');
  if (!modalBody) return;
  
  const keywords = data.keywords || [];
  const hasComparison = data.has_comparison || false;
  
  if (keywords.length === 0) {
    modalBody.innerHTML = `
      <div style="text-align: center; padding: 2em; color: #666;">
        <i class="fas fa-info-circle" style="font-size: 2em;"></i>
        <p style="margin-top: 1em;">No keywords found for this URL in the selected period.</p>
      </div>
    `;
    return;
  }
  
  // Crear información de la URL
  const infoHTML = `
    <div class="url-keywords-info" style="margin-bottom: 1em; padding: 1em; background: #f8f9fa; border-radius: 5px;">
      <p><strong>Analyzed URL:</strong> ${escapeHtml(data.url)}</p>
      <p><strong>Keywords found:</strong> ${keywords.length} ${keywords.length > 10 ? '<span style="color: #17a2b8; font-size: 0.9em;">(loading progressively...)</span>' : ''}</p>
      <p><strong>Period:</strong> ${data.periods.current.label}</p>
      ${hasComparison ? `<p><strong>Comparing with:</strong> ${data.periods.comparison.label}</p>` : ''}
    </div>
  `;
  
  // Crear contenedor para Grid.js
  const gridContainer = document.createElement('div');
  gridContainer.innerHTML = infoHTML;
  
  modalBody.innerHTML = '';
  modalBody.appendChild(gridContainer);
  
  // ✅ OPTIMIZACIÓN: Carga progresiva para mejor rendimiento
  try {
    if (keywords.length <= 10) {
      // Si hay 10 o menos, cargar todo de una vez
      console.log('⚡ [PROGRESSIVE LOAD] Pocas keywords, cargando todas:', keywords.length);
      createUrlKeywordsGridTable(keywords, hasComparison, modalBody);
    } else {
      // Si hay más de 10, cargar progresivamente
      console.log('⚡ [PROGRESSIVE LOAD] Muchas keywords, carga progresiva:', keywords.length);
      
      // Cargar primeras 10 inmediatamente para respuesta rápida
      const initialBatch = keywords.slice(0, 10);
      const gridInstance = createUrlKeywordsGridTable(initialBatch, hasComparison, modalBody);
      
      console.log('✅ [PROGRESSIVE LOAD] Primeras 10 keywords cargadas inmediatamente');
      
      // Cargar el resto en lotes de 20 en segundo plano
      const batchSize = 20;
      let currentIndex = 10;
      
      const loadNextBatch = () => {
        if (currentIndex >= keywords.length) {
          console.log('✅ [PROGRESSIVE LOAD] Todas las keywords cargadas');
          
          // Actualizar info sin el mensaje de carga
          const infoBox = document.querySelector('.url-keywords-info');
          if (infoBox) {
            infoBox.innerHTML = `
              <p><strong>Analyzed URL:</strong> ${escapeHtml(data.url)}</p>
              <p><strong>Keywords found:</strong> ${keywords.length}</p>
              <p><strong>Period:</strong> ${data.periods.current.label}</p>
              ${hasComparison ? `<p><strong>Comparing with:</strong> ${data.periods.comparison.label}</p>` : ''}
            `;
          }
          return;
        }
        
        const endIndex = Math.min(currentIndex + batchSize, keywords.length);
        const batchKeywords = keywords.slice(0, endIndex);
        
        console.log(`⚡ [PROGRESSIVE LOAD] Cargando lote: ${currentIndex} a ${endIndex} (${endIndex} / ${keywords.length})`);
        
        // Actualizar Grid.js con más datos
        if (gridInstance && gridInstance.updateConfig) {
          try {
            // Actualizar los datos manteniendo la configuración
            gridInstance.updateConfig({
              data: processKeywordsForGridUpdate(batchKeywords, hasComparison)
            }).forceRender();
          } catch (updateError) {
            console.warn('⚠️ Error actualizando Grid.js, recreando:', updateError);
            // Si falla la actualización, recrear con todos los datos hasta ahora
            createUrlKeywordsGridTable(batchKeywords, hasComparison, modalBody);
          }
        }
        
        currentIndex = endIndex;
        
        // Siguiente lote después de un pequeño delay (para no bloquear UI)
        setTimeout(loadNextBatch, 50); // 50ms entre lotes
      };
      
      // Iniciar carga del resto después de que se muestre lo inicial
      setTimeout(loadNextBatch, 100);
    }
    
    console.log('✅ Grid.js para modal de keywords creado exitosamente');
  } catch (error) {
    console.error('❌ Error al crear Grid.js para modal de keywords:', error);
    
    // Fallback - mostrar mensaje de error
    modalBody.innerHTML = infoHTML + `
      <div class="no-aio-message">
        <i class="fas fa-exclamation-triangle"></i>
        <h3>Error Loading Keywords</h3>
        <p>There was an error loading the keywords table. Please try again.</p>
      </div>
    `;
  }
}

// ✅ HELPER: Procesar keywords para actualización de Grid.js (simplificado)
function processKeywordsForGridUpdate(keywords, hasComparison) {
  // Procesar datos de manera similar a ui-url-keywords-gridjs.js
  // pero sin las columnas, solo los datos ya procesados
  
  const data = keywords.map(keyword => {
    const rowData = [
      '', // Columna SERP (será reemplazada por el formatter)
      keyword.keyword || keyword.query || ''
    ];

    // Función helper para formatear
    const formatInt = (val) => {
      if (val == null || val === undefined) return '0';
      return Math.round(val).toLocaleString('en-US');
    };
    
    const formatPct = (val) => {
      if (val == null || val === undefined) return '0.00';
      return Number(val).toFixed(2);
    };
    
    const formatPos = (val) => {
      if (val == null || val === undefined || val === 0) return 0;
      return Number(val).toFixed(1);
    };
    
    const calcDelta = (current, previous, type) => {
      if (previous === 0 || previous == null) {
        return current > 0 ? 'New' : '0';
      }
      if (type === 'position') {
        const delta = current - previous;
        return delta === 0 ? '0' : (delta > 0 ? '+' : '') + delta.toFixed(1);
      }
      const change = ((current - previous) / previous) * 100;
      return change === 0 ? '0' : (change > 0 ? '+' : '') + change.toFixed(1) + '%';
    };

    // Añadir datos según si hay comparación
    rowData.push(formatInt(keyword.clicks_m1 ?? keyword.clicks_p1 ?? 0));
    
    if (hasComparison) {
      rowData.push(formatInt(keyword.clicks_m2 ?? keyword.clicks_p2 ?? 0));
      rowData.push(calcDelta(keyword.clicks_m1 ?? keyword.clicks_p1 ?? 0, keyword.clicks_m2 ?? keyword.clicks_p2 ?? 0, 'clicks'));
    }
    
    rowData.push(formatInt(keyword.impressions_m1 ?? keyword.impressions_p1 ?? 0));
    
    if (hasComparison) {
      rowData.push(formatInt(keyword.impressions_m2 ?? keyword.impressions_p2 ?? 0));
      rowData.push(calcDelta(keyword.impressions_m1 ?? keyword.impressions_p1 ?? 0, keyword.impressions_m2 ?? keyword.impressions_p2 ?? 0, 'impressions'));
    }
    
    rowData.push(formatPct(keyword.ctr_m1 ?? keyword.ctr_p1));
    
    if (hasComparison) {
      rowData.push(formatPct(keyword.ctr_m2 ?? keyword.ctr_p2));
      rowData.push(calcDelta(keyword.ctr_m1 ?? keyword.ctr_p1 ?? 0, keyword.ctr_m2 ?? keyword.ctr_p2 ?? 0, 'ctr'));
    }
    
    const pos1 = keyword.position_m1 ?? keyword.position_p1;
    const pos1Numeric = (pos1 == null || isNaN(pos1)) ? 0 : Number(pos1);
    rowData.push(pos1Numeric);
    
    if (hasComparison) {
      const pos2 = keyword.position_m2 ?? keyword.position_p2;
      const pos2Numeric = (pos2 == null || isNaN(pos2)) ? 0 : Number(pos2);
      rowData.push(pos2Numeric);
      rowData.push(calcDelta(pos1Numeric, pos2Numeric, 'position'));
    }

    return rowData;
  });

  return data;
}

// ✅ NUEVO: Función para crear filas de keywords
function createUrlKeywordRow(keyword, hasComparison) {
  // Calcular clases para deltas
  const deltaClicksClass = getDeltaClass(keyword.delta_clicks_percent);
  const deltaImprClass = getDeltaClass(keyword.delta_impressions_percent);
  const deltaCtrClass = getDeltaClass(keyword.delta_ctr_percent);
  const deltaPosClass = getDeltaClassPosition(keyword.delta_position_absolute);
  
  return `
    <tr>
      <td class="dt-body-center">
        <i class="fas fa-search serp-icon"
           data-keyword="${escapeHtmlUtil(keyword.keyword)}"
           data-url="${escapeHtmlUtil(keyword.url)}"
           title="View SERP for ${escapeHtmlUtil(keyword.keyword)}"
           style="cursor:pointer;"></i>
      </td>
      <td class="dt-body-left">${escapeHtmlUtil(keyword.keyword)}</td>
      <td>${formatInteger(keyword.clicks_m1 || 0)}</td>
      ${hasComparison ? `<td>${formatInteger(keyword.clicks_m2 || 0)}</td>` : ''}
      ${hasComparison ? `<td class="${deltaClicksClass}">${formatPercentageChange(keyword.delta_clicks_percent)}</td>` : ''}
      <td>${formatInteger(keyword.impressions_m1 || 0)}</td>
      ${hasComparison ? `<td>${formatInteger(keyword.impressions_m2 || 0)}</td>` : ''}
      ${hasComparison ? `<td class="${deltaImprClass}">${formatPercentageChange(keyword.delta_impressions_percent)}</td>` : ''}
      <td>${formatPercentage(keyword.ctr_m1)}</td>
      ${hasComparison ? `<td>${formatPercentage(keyword.ctr_m2)}</td>` : ''}
      ${hasComparison ? `<td class="${deltaCtrClass}">${formatPercentageChange(keyword.delta_ctr_percent, true)}</td>` : ''}
      <td>${formatPosition(keyword.position_m1)}</td>
      ${hasComparison ? `<td>${formatPosition(keyword.position_m2)}</td>` : ''}
      ${hasComparison ? `<td class="${deltaPosClass}">${formatPositionDelta(keyword.delta_position_absolute, keyword.position_m1, keyword.position_m2)}</td>` : ''}
    </tr>
  `;
}

// ✅ NUEVO: Funciones auxiliares para clases CSS
function getDeltaClass(value) {
  if (value === 'New' || value === 'Infinity' || (typeof value === 'number' && value > 0)) {
    return 'positive-change';
  } else if (value === 'Lost' || (typeof value === 'number' && value < 0)) {
    return 'negative-change';
  }
  return '';
}

function getDeltaClassPosition(value) {
  // Para posiciones, negativo es bueno (mejor posición)
  if (value === 'New' || (typeof value === 'number' && value < 0)) {
    return 'positive-change';
  } else if (value === 'Lost' || (typeof value === 'number' && value > 0)) {
    return 'negative-change';
  }
  return '';
}

// ✅ NUEVO: Event listener para los iconos de keywords en la tabla de URLs
document.addEventListener('DOMContentLoaded', function() {
  // Delegación de eventos para los iconos de keywords
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('keywords-icon')) {
      const url = e.target.dataset.url;
      if (url) {
        openUrlKeywordsModal(url);
      }
    }
  });
});

// ✅ NUEVO: Hacer funciones disponibles globalmente
window.openUrlKeywordsModal = openUrlKeywordsModal;
