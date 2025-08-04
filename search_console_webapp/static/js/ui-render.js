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

// Variable para almacenar la instancia de Grid.js de URLs (migrado desde DataTable)
let urlsGridTable = null;

// ✅ ACTUALIZADA: Función para resetear completamente el estado de la tabla de URLs (Grid.js)
export function resetUrlsTableState() {
  console.log('🔄 Reseteando estado completo de la tabla de URLs...');
  
  // Resetear variable global de Grid.js
  if (urlsGridTable && urlsGridTable.destroy) {
    try {
      urlsGridTable.destroy();
      console.log('✅ Grid.js anterior destruido en reset');
    } catch (e) {
      console.warn('⚠️ Error destruyendo Grid.js en reset:', e);
    }
  }
  urlsGridTable = null;
  
  // Limpiar datos globales relacionados
  window.currentData = null;
  
  // Asegurar que la sección esté oculta inicialmente
  if (elems.resultsSection) {
    elems.resultsSection.style.display = 'none';
  }
  if (elems.resultsTitle) {
    elems.resultsTitle.style.display = 'none';
  }
  
  console.log('✅ Estado de tabla de URLs reseteado completamente');
}

// ✅ NUEVO: Variable global para almacenar los datos de keywords
let globalKeywordData = [];

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
    impressions: '#8B45FF',  // Lila/Morado
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
          <div class="card-icon-modern" style="background: linear-gradient(135deg, ${color}20, ${color}40); color: ${color};">
            <i class="${icon}"></i>
          </div>
          <h3 class="card-title-modern">${title}</h3>
        </div>
        
        <div class="period-values-modern">
          ${periodValues}
          ${deltaHTML}
        </div>
        
        ${periods.length > 1 ? `
        <div class="mini-chart-container-modern">
          <canvas id="mini-chart-${id}" width="120" height="80"></canvas>
        </div>
        ` : ''}
      </div>
    `;
  };

  // Limpiar y actualizar HTML de cada card completamente
  document.querySelector('#summaryClicks').innerHTML = 
    createSummaryCard('clicks', 'Total Clicks', 'fas fa-mouse-pointer', null, clicksData, chartLabels, colors.clicks);
  
  document.querySelector('#summaryImpressions').innerHTML = 
    createSummaryCard('impressions', 'Total Impressions', 'fas fa-eye', null, impressionsData, chartLabels, colors.impressions);
  
  document.querySelector('#summaryCTR').innerHTML = 
    createSummaryCard('ctr', 'Average CTR', 'fas fa-percentage', null, ctrData, chartLabels, colors.ctr, true);
  
  document.querySelector('#summaryPosition').innerHTML = 
    createSummaryCard('position', 'Average Position', 'fas fa-location-arrow', null, positionData, chartLabels, colors.position, false, true);

  // ✅ ACTUALIZADO: Solo crear mini-gráficos si hay múltiples períodos
  if (periods.length > 1) {
    setTimeout(() => {
      createMiniChart('mini-chart-clicks', clicksData, colors.clicks, chartLabels);
      createMiniChart('mini-chart-impressions', impressionsData, colors.impressions, chartLabels);
      createMiniChart('mini-chart-ctr', ctrData, colors.ctr, chartLabels);
      createMiniChart('mini-chart-position', positionData, colors.position, chartLabels);
    }, 100);
  }

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
    // ✅ Adaptar mensajes según si hay comparación o no
    const hasComparison = (ov.improved > 0 || ov.worsened > 0 || ov.lost > 0);
    
    if (hasComparison) {
      // Mostrar iconos completos cuando hay comparación de períodos
      elems.keywordOverviewDiv.innerHTML = `
        <div class="overview-card total-kws">
          <div class="card-icon"><i class="fas fa-search"></i></div>
          <div class="label">Total KWs</div>
          <div class="value">${formatInteger(ov.total ?? 0)}</div>
        </div>
        <div class="overview-card improved">
          <div class="card-icon"><i class="fas fa-arrow-trend-up"></i></div>
          <div class="label">Improve positions</div>
          <div class="value">+${formatInteger(ov.improved ?? 0)}</div>
        </div>
        <div class="overview-card declined">
          <div class="card-icon"><i class="fas fa-arrow-trend-down"></i></div>
          <div class="label">Decline positions</div>
          <div class="value">-${formatInteger(ov.worsened ?? 0)}</div>
        </div>
        <div class="overview-card same-pos">
          <div class="card-icon"><i class="fas fa-equals"></i></div>
          <div class="label">Same pos.</div>
          <div class="value">${formatInteger(ov.same ?? 0)}</div>
        </div>
        <div class="overview-card added">
          <div class="card-icon"><i class="fas fa-plus-circle"></i></div>
          <div class="label">New</div>
          <div class="value">+${formatInteger(ov.new ?? 0)}</div>
        </div>
        <div class="overview-card removed">
          <div class="card-icon"><i class="fas fa-minus-circle"></i></div>
          <div class="label">Lost</div>
          <div class="value">-${formatInteger(ov.lost ?? 0)}</div>
        </div>
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
    
    // ✅ NOTA: No se agregan event listeners a las tarjetas del overview
    // El overview es solo informativo, no clickeable
  }

  if (elems.keywordCategoryDiv) {
    const buckets = keywordStats;
    
    const buildModernCatCard = (title, stat = { current: 0, new: 0, lost: 0, stay: 0 }, dataRange) => {
      const hasComparison = (stat.new > 0 || stat.lost > 0);
      
      // ✅ TAREA 2: Iconos de medallas según rango de posición
      let iconClass = 'fas fa-layer-group'; // fallback
      let iconColor = '#666';
      
      switch (dataRange) {
        case 'top3':
          iconClass = 'fas fa-trophy';
          iconColor = '#FFD700'; // Oro
          break;
        case 'top10':
          iconClass = 'fas fa-trophy';
          iconColor = '#C0C0C0'; // Plata
          break;
        case 'top20':
          iconClass = 'fas fa-trophy';
          iconColor = '#CD7F32'; // Bronce
          break;
        case 'top20plus':
          iconClass = 'fas fa-medal';
          iconColor = '#808080'; // Gris neutro (medalla negra/sin color)
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
    
    if (elems.resultsTitle) elems.resultsTitle.textContent = 'URLs Performance';
    
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
    elems.resultsTitle.textContent = 'URLs Performance';
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
    elems.resultsTitle.textContent = 'URLs Performance';
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
let preProcessedModalData = {
  top3: { keywords: [], gridTable: null, analysisType: 'single' },
  top10: { keywords: [], gridTable: null, analysisType: 'single' },
  top20: { keywords: [], gridTable: null, analysisType: 'single' },
  top20plus: { keywords: [], gridTable: null, analysisType: 'single' }
};

let modalContainersCreated = false;

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
function openKeywordModal(positionRange, label) {
  console.log('🔍 Abriendo modal para rango:', positionRange, 'label:', label);
  
  // Verificar que los datos estén pre-procesados
  if (!preProcessedModalData[positionRange]) {
    console.error('❌ No se encontraron datos pre-procesados para el rango:', positionRange);
    return;
  }
  
  const data = preProcessedModalData[positionRange];
  
  if (data.keywords.length === 0) {
    console.log('⚠️  No hay keywords en este rango de posición');
    return;
  }
  
  // Verificar que los contenedores estén creados
  if (!modalContainersCreated) {
    createAllModalContainers();
  }
  
  // Verificar que el modal específico existe
  const modal = document.getElementById(`keywordModal-${positionRange}`);
  if (!modal) {
    console.error('❌ Modal no encontrado para rango:', positionRange);
    return;
  }
  
  // Verificar que la Grid.js tabla está lista
  if (!data.gridTable && data.keywords.length > 0) {
    console.log('🔄 Grid.js tabla no está lista, creando...');
    // No usar await aquí para mantener la apertura instantánea del modal
    createGridTableForRange(positionRange, data.keywords, data.analysisType).catch(error => {
      console.error(`❌ Error al crear Grid.js tabla para ${positionRange}:`, error);
    });
  }
  
  // Mostrar el modal instantáneamente
  modal.classList.add('modal-open');
  document.body.style.overflow = 'hidden';
  
  console.log(`✅ Modal abierto instantáneamente para: ${label} (${data.keywords.length} keywords)`);
}

// ✅ NUEVO: Función para crear todos los contenedores de modales
function createAllModalContainers() {
  if (modalContainersCreated) return;
  
  console.log('🔍 Creando contenedores de modales pre-cargados...');
  
  const ranges = ['top3', 'top10', 'top20', 'top20plus'];
  const labels = {
    top3: 'Top 1-3',
    top10: 'Posiciones 4-10', 
    top20: 'Posiciones 11-20',
    top20plus: 'Posiciones 20+'
  };

  ranges.forEach(range => {
    const modalHTML = `
      <div id="keywordModal-${range}" class="modal">
        <div class="modal-content">
          <div class="modal-header">
            <h3 id="keywordModalTitle-${range}"><i class="fas fa-search"></i> Keywords en ${labels[range]}</h3>
            <span class="close-btn" onclick="closeKeywordModal('${range}')">&times;</span>
          </div>
          <div class="modal-body">
            <div class="keyword-modal-info">
              <i class="fas fa-info-circle"></i>
              <span>Información: Estas son las keywords que se posicionan en el rango seleccionado. Haz clic en el icono de búsqueda para ver el SERP.</span>
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
  console.log('✅ Contenedores de modales creados para todos los rangos');
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
    console.error(`❌ No se encontró el contenedor para ${range}`);
    return;
  }

  console.log(`🔄 Creando Grid.js tabla para ${range} con ${keywords.length} keywords...`);
  const startTime = performance.now();
  
  if (keywords.length === 0) {
    container.innerHTML = `
      <div class="no-aio-message">
        <i class="fas fa-search"></i>
        <h3>No Keywords Found</h3>
        <p>No se encontraron keywords en este rango de posiciones.</p>
      </div>
    `;
    return;
  }

  // ✅ CREAR TABLA GRID.JS usando el módulo creado
  try {
    // Limpiar completamente el contenedor antes de crear la tabla
    container.innerHTML = '';
    
    // Importar dinámicamente para evitar dependencias circulares
    const { createKeywordsGridTable } = await import('./ui-keywords-gridjs.js');
    
    // Crear Grid.js table
    preProcessedModalData[range].gridTable = createKeywordsGridTable(keywords, analysisType, container);
    
    if (preProcessedModalData[range].gridTable) {
      const endTime = performance.now();
      console.log(`✅ Grid.js tabla para ${range} creada en ${(endTime - startTime).toFixed(2)}ms`);
    } else {
      console.warn(`⚠️ No se pudo crear Grid.js tabla para ${range}`);
    }
    
  } catch (error) {
    console.error(`❌ Error al crear Grid.js tabla para ${range}:`, error);
    
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
    const ranges = ['top3', 'top10', 'top20', 'top20plus'];
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

// ✅ NUEVO: Función para pre-procesar datos por rangos de posición
function preprocessKeywordDataByRanges(keywordData) {
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
    });
    return;
  }

  console.log('🔄 Pre-procesando keywords por rangos...');
  const startTime = performance.now();

  // Determinar tipo de análisis una vez
  const analysisType = getAnalysisTypeModal(keywordData);
  
  // Clasificar keywords por rangos
  const ranges = {
    top3: keywordData.filter(kw => {
      const pos = kw.position_m1;
      return typeof pos === 'number' && pos >= 1 && pos <= 3;
    }).sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0)),
    
    top10: keywordData.filter(kw => {
      const pos = kw.position_m1;
      return typeof pos === 'number' && pos >= 4 && pos <= 10;
    }).sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0)),
    
    top20: keywordData.filter(kw => {
      const pos = kw.position_m1;
      return typeof pos === 'number' && pos >= 11 && pos <= 20;
    }).sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0)),
    
    top20plus: keywordData.filter(kw => {
      const pos = kw.position_m1;
      return typeof pos === 'number' && pos > 20;
    }).sort((a, b) => (b.clicks_m1 || 0) - (a.clicks_m1 || 0))
  };

  // Actualizar datos pre-procesados
  Object.keys(ranges).forEach(range => {
    preProcessedModalData[range].keywords = ranges[range];
    preProcessedModalData[range].analysisType = analysisType;
  });

  const endTime = performance.now();
  console.log(`✅ Keywords pre-procesadas en ${(endTime - startTime).toFixed(2)}ms:`, {
    top3: ranges.top3.length,
    top10: ranges.top10.length,
    top20: ranges.top20.length,
    top20plus: ranges.top20plus.length,
    analysisType: analysisType
  });

  // Pre-crear las Grid.js tables para cada rango
  createPreloadedGridTables();
}

// ✅ MIGRADO A GRID.JS: Función para crear Grid.js tables pre-cargadas
function createPreloadedGridTables() {
  if (!modalContainersCreated) {
    createAllModalContainers();
  }

  Object.keys(preProcessedModalData).forEach(range => {
    const data = preProcessedModalData[range];
    if (data.keywords.length > 0) {
      createGridTableForRange(range, data.keywords, data.analysisType).catch(error => {
        console.error(`❌ Error al crear Grid.js tabla para ${range} en precarga:`, error);
      });
    }
  });
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
    modalTitle.innerHTML = `<i class="fas fa-search"></i> Keywords para: ${escapeHtml(url)}`;
  }
  
  // Mostrar modal con loading
  const modalBody = document.getElementById('keywordModalBody-url');
  if (modalBody) {
    modalBody.innerHTML = `
      <div class="loading-container" style="text-align: center; padding: 2em;">
        <i class="fas fa-spinner fa-spin" style="font-size: 2em; color: #007bff;"></i>
        <p style="margin-top: 1em; color: #666;">Obteniendo keywords para esta URL...</p>
      </div>
    `;
  }
  
  modal.classList.add('modal-open');
  document.body.style.overflow = 'hidden';
  
  // Obtener datos del último análisis desde el contexto global
  const currentData = window.currentData || {};
  const periods = currentData.periods || {};
  
  // Hacer petición al nuevo endpoint
  fetchUrlKeywords(url, periods).then(data => {
    renderUrlKeywordsData(data);
  }).catch(error => {
    console.error('Error obteniendo keywords:', error);
    if (modalBody) {
      modalBody.innerHTML = `
        <div style="text-align: center; padding: 2em; color: #dc3545;">
          <i class="fas fa-exclamation-triangle" style="font-size: 2em;"></i>
          <p style="margin-top: 1em;">Error obteniendo keywords: ${error.message}</p>
        </div>
      `;
    }
  });
}

// ✅ NUEVO: Función para crear el modal HTML
function createUrlKeywordsModal() {
  const modalHTML = `
    <div id="keywordModal-url" class="modal">
      <div class="modal-content">
        <div class="modal-header">
          <h3 id="keywordModalTitle-url"><i class="fas fa-search"></i> Keywords por URL</h3>
          <span class="close-btn" onclick="closeKeywordModal('url')">&times;</span>
        </div>
        <div class="modal-body" id="keywordModalBody-url">
          <!-- Contenido dinámico -->
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
  
  const response = await fetch('/api/url-keywords', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    throw new Error(errorData.error || `Error del servidor: ${response.status}`);
  }
  
  return response.json();
}

// ✅ MIGRADO A GRID.JS: Función para renderizar los datos en el modal
function renderUrlKeywordsData(data) {
  const modalBody = document.getElementById('keywordModalBody-url');
  if (!modalBody) return;
  
  const keywords = data.keywords || [];
  const hasComparison = data.has_comparison || false;
  
  if (keywords.length === 0) {
    modalBody.innerHTML = `
      <div style="text-align: center; padding: 2em; color: #666;">
        <i class="fas fa-info-circle" style="font-size: 2em;"></i>
        <p style="margin-top: 1em;">No se encontraron keywords para esta URL en el período seleccionado.</p>
      </div>
    `;
    return;
  }
  
  // Crear información de la URL
  const infoHTML = `
    <div class="url-keywords-info" style="margin-bottom: 1em; padding: 1em; background: #f8f9fa; border-radius: 5px;">
      <p><strong>URL analizada:</strong> ${escapeHtml(data.url)}</p>
      <p><strong>Keywords encontradas:</strong> ${keywords.length}</p>
      <p><strong>Período:</strong> ${data.periods.current.label}</p>
      ${hasComparison ? `<p><strong>Comparando con:</strong> ${data.periods.comparison.label}</p>` : ''}
    </div>
  `;
  
  // Crear contenedor para Grid.js
  const gridContainer = document.createElement('div');
  gridContainer.innerHTML = infoHTML;
  
  modalBody.innerHTML = '';
  modalBody.appendChild(gridContainer);
  
  // Crear tabla Grid.js para keywords del modal
  try {
    createUrlKeywordsGridTable(keywords, hasComparison, modalBody);
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
           title="Ver SERP para ${escapeHtmlUtil(keyword.keyword)}"
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