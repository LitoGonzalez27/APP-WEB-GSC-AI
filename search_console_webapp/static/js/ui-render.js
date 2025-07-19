// ui-render.js - ACTUALIZADO para manejar períodos específicos en lugar de meses
import { elems } from './utils.js';

// Variable para almacenar la instancia de DataTable de URLs
let urlsDataTable = null;

// ✅ NUEVA: Función para resetear completamente el estado de la tabla de URLs
export function resetUrlsTableState() {
  console.log('🔄 Reseteando estado completo de la tabla de URLs...');
  
  // Resetear variable global
  urlsDataTable = null;
  
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

// Funciones auxiliares para formateo (reutilizadas de la tabla de keywords)
function formatPercentageChange(value, isCTR = false) {
  if (value === "Infinity") return '+∞%';
  if (value === "-Infinity") return '-∞%';
  if (value === "New") return '<span class="positive-change">Nuevo</span>';
  if (value === "Lost") return '<span class="negative-change">Perdido</span>';
  if (typeof value === 'number' && isFinite(value)) {
    if (value === 0 && Object.is(value, -0)) return isCTR ? '-0.00%' : '-0.0%';
    if (value === 0) return isCTR ? '0.00%' : '0.0%';
    return isCTR ? `${value.toFixed(2)}%` : `${value.toFixed(1)}%`;
  }
  return 'N/A';
}

function formatPosition(value) {
  return (value == null || isNaN(value)) ? 'N/A' : value.toFixed(1);
}

function formatPositionDelta(delta, pos1, pos2) {
  if (delta === 'New')   return '<span class="positive-change">Nuevo</span>';
  if (delta === 'Lost')  return '<span class="negative-change">Perdido</span>';
  if (typeof delta === 'number' && isFinite(delta)) {
    if (delta > 0) return `+${delta.toFixed(1)}`;
    if (delta < 0) return delta.toFixed(1);
    return '0.0';
  }
  if (pos1 == null && pos2 == null) return 'N/A';
  return pos1 === pos2 ? '0.0' : 'N/A';
}

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
        ctr_p1: (metric.CTR || 0) * 100,
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
      const deltaCTR = ((currentMetric.CTR || 0) * 100) - ((comparisonMetric.CTR || 0) * 100);
      const deltaPosition = (currentMetric.Position && comparisonMetric.Position)
        ? currentMetric.Position - comparisonMetric.Position
        : (currentMetric.Position ? 'New' : 'Lost');
      
      urlsData.push({
        url: url,
        // ✅ CORREGIDO: P1 = período actual (más reciente)
        clicks_p1: currentMetric.Clicks || 0,      
        impressions_p1: currentMetric.Impressions || 0,
        ctr_p1: (currentMetric.CTR || 0) * 100,
        position_p1: currentMetric.Position || null,
        
        // ✅ CORREGIDO: P2 = período de comparación (más antiguo)
        clicks_p2: comparisonMetric.Clicks || 0,      
        impressions_p2: comparisonMetric.Impressions || 0,
        ctr_p2: (comparisonMetric.CTR || 0) * 100,
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
              return Number.isInteger(value) ? value.toLocaleString() : value;
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
      if (isPercentage) return `${val.toFixed(2)}%`;
      if (isPosition) return val.toFixed(1);
      return val.toLocaleString();
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
  if (elems.performanceTitle) elems.performanceTitle.style.display = 'block';
  if (elems.chartsBlock) elems.chartsBlock.style.display = 'none'; 
  if (elems.performanceSection) elems.performanceSection.style.display = 'block';
}

// ✅ FUNCIÓN CORREGIDA para ui-render.js (reemplazar solo la función renderKeywords)

export function renderKeywords(keywordStats = {}) {
  const ov = keywordStats.overall || {};
  
  if (elems.keywordOverviewDiv) {
    // ✅ Adaptar mensajes según si hay comparación o no
    const hasComparison = (ov.improved > 0 || ov.worsened > 0 || ov.lost > 0);
    
    elems.keywordOverviewDiv.innerHTML = `
      <div class="overview-card total-kws">
        <div class="card-icon"><i class="fas fa-search"></i></div>
        <div class="label">Total KWs</div>
        <div class="value">${(ov.total ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card improved">
        <div class="card-icon"><i class="fas fa-arrow-trend-up"></i></div>
        <div class="label">${hasComparison ? 'Improve positions' : 'Top 1-3'}</div>
        <div class="value">${hasComparison ? '+' + (ov.improved ?? 0).toLocaleString() : (keywordStats.top3?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card declined">
        <div class="card-icon"><i class="fas fa-arrow-trend-down"></i></div>
        <div class="label">${hasComparison ? 'Decline positions' : 'Pos 4-10'}</div>
        <div class="value">${hasComparison ? '-' + (ov.worsened ?? 0).toLocaleString() : (keywordStats.top10?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card same-pos">
        <div class="card-icon"><i class="fas fa-equals"></i></div>
        <div class="label">Same pos.</div>
        <div class="value">${hasComparison ? (ov.same ?? 0).toLocaleString() : (keywordStats.top20?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card added">
        <div class="card-icon"><i class="fas fa-plus-circle"></i></div>
        <div class="label">${hasComparison ? 'New' : 'Pos 20+'}</div>
        <div class="value">${hasComparison ? '+' + (ov.new ?? 0).toLocaleString() : (keywordStats.top20plus?.current ?? 0).toLocaleString()}</div>
      </div>
      <div class="overview-card removed">
        <div class="card-icon"><i class="fas fa-minus-circle"></i></div>
        <div class="label">${hasComparison ? 'Lost' : 'Current period'}</div>
        <div class="value">${hasComparison ? '-' + (ov.lost ?? 0).toLocaleString() : '📊'}</div>
      </div>
    `;
    elems.keywordOverviewDiv.style.display = 'flex';
    
    // ✅ NOTA: No se agregan event listeners a las tarjetas del overview
    // El overview es solo informativo, no clickeable
  }

  if (elems.keywordCategoryDiv) {
    const buckets = keywordStats;
    
    const buildModernCatCard = (title, stat = { current: 0, new: 0, lost: 0, stay: 0 }, dataRange) => {
      const hasComparison = (stat.new > 0 || stat.lost > 0);
      
      return `
        <div class="category-card clickable-card" data-position-range="${dataRange}" style="cursor: pointer;">
          <div class="card-icon"><i class="fas fa-layer-group"></i></div>
          <div class="value">${(stat.current ?? 0).toLocaleString()}</div>
          <div class="subtitle">${title}</div>
          ${hasComparison ? `
            <div class="entry">New: <strong>+${(stat.new ?? 0).toLocaleString()}</strong></div>
            <div class="exit">Lost: <strong>-${(stat.lost ?? 0).toLocaleString()}</strong></div>
            <div class="maintain">Maintained: <strong>${(stat.stay ?? 0).toLocaleString()}</strong></div>
          ` : `
            <div class="entry">Keywords in these positions</div>
            <div class="maintain">Total of the selected period</div>
          `}
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

  if (elems.keywordsSection) elems.keywordsSection.style.display = 'block';
  if (elems.keywordsTitle) elems.keywordsTitle.style.display = 'block';
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
      ctr: calculatePercentageChangeInsights(firstPeriod.CTR * 100, lastPeriod.CTR * 100),
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
      value: p1Clicks.toLocaleString(),
      change: changeData ? formatChange(changeData.clicks) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Total del período`
    },
    {
      type: 'impressions',
      icon: 'fas fa-eye',
      label: 'Impressions',
      value: p1Impressions.toLocaleString(),
      change: changeData ? formatChange(changeData.impressions) : getNoChangeHTML(periods.length),
      description: periods.length > 1 ? 'vs first period' : `Total del período`
    },
    {
      type: 'ctr',
      icon: 'fas fa-percentage',
      label: 'Average CTR',
      value: `${p1CTR.toFixed(2)}%`,
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
  
  if (insightsSection) {
    insightsSection.style.display = 'block';
  }
  
  if (insightsTitle) {
    insightsTitle.style.display = 'block';
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
  
  // Siempre resetear la variable
  urlsDataTable = null;
  console.log('✅ Variable urlsDataTable reseteada');
  
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

// ✅ COMPLETAMENTE NUEVA: renderTable para manejar comparación de URLs
export async function renderTable(pages) {
  console.log('🔄 Actualizando tabla de URLs con nuevos datos...', { 
    pagesCount: pages?.length, 
    pagesType: typeof pages, 
    pagesData: pages ? pages.slice(0, 2) : 'null' 
  });
  
  // ✅ MEJORADO: Limpieza completa de la tabla anterior
  cleanupPreviousTable();
  
  // ✅ NUEVO: Asegurar que la estructura HTML existe
  if (!ensureTableStructure()) {
    console.error('❌ No se pudo asegurar la estructura de la tabla');
    return;
  }
  
  // ✅ CRÍTICO: Re-obtener referencias DOM después de posible recreación
  elems.tableBody = document.querySelector('#resultsTable tbody');
  elems.resultsSection = document.getElementById('resultsBlock');
  elems.resultsTitle = document.querySelector('.results-title');
  
  if (!elems.tableBody) {
    console.error('❌ No se pudo obtener referencia al tbody después de recreación');
    return;
  }
  console.log('✅ Referencias DOM actualizadas después de estructura verificada');
  
  if (!pages || !pages.length) {
    console.log('⚠️ No hay datos de páginas para mostrar');
    if (elems.tableBody) elems.tableBody.innerHTML = '<tr><td colspan="14">No hay datos para la tabla.</td></tr>';
    if (elems.resultsSection) elems.resultsSection.style.display = 'block';
    if (elems.resultsTitle) elems.resultsTitle.style.display = 'block';
    if (elems.resultsTitle) elems.resultsTitle.textContent = 'URLs Performance';
    
    // ✅ NUEVO: Mostrar subtítulo también cuando no hay datos
    const urlsSubtitle = document.querySelector('.urls-overview-subtitle');
    if (urlsSubtitle) {
      urlsSubtitle.style.display = 'block';
      console.log('✅ Subtítulo de URLs mostrado (sin datos)');
    }
    
    return;
  }

  // ✅ Procesar datos de URLs
  const urlsData = processUrlsData(pages);
  
  // ✅ CORREGIDO: Pasar información de períodos para determinar el tipo correcto
  const periods = window.currentData && window.currentData.periods ? window.currentData.periods : null;
  const analysisType = getUrlAnalysisType(pages, periods);
  
  console.log(`📊 Tipo de análisis URLs: ${analysisType}, URLs: ${urlsData.length}`);
  console.log('📋 Datos procesados:', urlsData.slice(0, 3)); // Log primeros 3 para debugging
  
  // ✅ Actualizar headers según el tipo
  updateUrlTableHeaders(analysisType);

  // ✅ NUEVO: Limpiar tbody antes de añadir nuevos datos
  if (elems.tableBody) {
    elems.tableBody.innerHTML = '';
    console.log('🧹 Tbody limpiado antes de añadir nuevos datos');
  }
  
  // ✅ Renderizar filas
  console.log(`🔄 Añadiendo ${urlsData.length} filas al tbody...`);
  urlsData.forEach((row, index) => {
    const deltaClicksClass =
      (row.delta_clicks_percent === 'Infinity' || (typeof row.delta_clicks_percent === 'number' && row.delta_clicks_percent > 0))
        ? 'positive-change'
        : (typeof row.delta_clicks_percent === 'number' && row.delta_clicks_percent < 0)
          ? 'negative-change'
          : '';
    const deltaImprClass   =
      (row.delta_impressions_percent === 'Infinity' || (typeof row.delta_impressions_percent === 'number' && row.delta_impressions_percent > 0))
        ? 'positive-change'
        : (typeof row.delta_impressions_percent === 'number' && row.delta_impressions_percent < 0)
          ? 'negative-change'
          : '';
    const deltaCtrClass    =
      (row.delta_ctr_percent === 'Infinity' || (typeof row.delta_ctr_percent === 'number' && row.delta_ctr_percent > 0))
        ? 'positive-change'
        : (typeof row.delta_ctr_percent === 'number' && row.delta_ctr_percent < 0)
          ? 'negative-change'
          : '';
    const deltaPosClass    =
      (row.delta_position_absolute === 'New' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute < 0)) // Pos delta: negative is good (lower position)
        ? 'positive-change'
        : (row.delta_position_absolute === 'Lost' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute > 0))
          ? 'negative-change'
          : '';

    const tr = document.createElement('tr');
    
    // ✅ Ajustar visibilidad de columnas según el tipo
    const p2ColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';
    const deltaColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';

    tr.innerHTML = `
      <td class="dt-body-center">
        <i class="fas fa-list keywords-icon"
           data-url="${escapeHtml(row.url)}"
           title="Ver keywords para esta URL"
           style="cursor:pointer; color: #007bff;"></i>
      </td>
      <td class="dt-body-left url-cell" title="${row.url}">${row.url}</td>
      <td>${(row.clicks_p1 ?? 0).toLocaleString('es-ES')}</td>
      <td ${p2ColumnsStyle}>${(row.clicks_p2 ?? 0).toLocaleString('es-ES')}</td>
      <td class="${deltaClicksClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_clicks_percent)}</td>
      <td>${(row.impressions_p1 ?? 0).toLocaleString('es-ES')}</td>
      <td ${p2ColumnsStyle}>${(row.impressions_p2 ?? 0).toLocaleString('es-ES')}</td>
      <td class="${deltaImprClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_impressions_percent)}</td>
      <td>${typeof row.ctr_p1 === 'number' ? row.ctr_p1.toFixed(2) + '%' : 'N/A'}</td>
      <td ${p2ColumnsStyle}>${typeof row.ctr_p2 === 'number' ? row.ctr_p2.toFixed(2) + '%' : 'N/A'}</td>
      <td class="${deltaCtrClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_ctr_percent, true)}</td>
      <td>${formatPosition(row.position_p1)}</td>
      <td ${p2ColumnsStyle}>${formatPosition(row.position_p2)}</td>
      <td class="${deltaPosClass}" ${deltaColumnsStyle}>${formatPositionDelta(row.delta_position_absolute, row.position_p1, row.position_p2)}</td>
    `;
    
    if (elems.tableBody) {
      elems.tableBody.appendChild(tr);
      if (index < 3) { // Log solo las primeras 3 para debugging
        console.log(`✅ Fila ${index + 1} añadida: ${row.url}`);
      }
    } else {
      console.error(`❌ No se pudo añadir fila ${index + 1}: tbody no disponible`);
    }
  });
  
  console.log(`✅ ${urlsData.length} filas añadidas al tbody. Filas en DOM: ${elems.tableBody ? elems.tableBody.children.length : 'N/A'}`);

  // === ORDENAMIENTO PERSONALIZADO PARA DATATABLES ===
  function parseSortableValue(val) {
    if (val === 'Infinity' || val === '+∞%' || val === '+∞') return Infinity;
    if (val === '-Infinity' || val === '-∞%' || val === '-∞') return -Infinity;
    if (val === 'New' || val === 'Nuevo') return 0.00001; // Valor bajo pero positivo
    if (val === 'Lost' || val === 'Perdido') return -0.00001; // Valor bajo pero negativo
    if (typeof val === 'string') {
      // ✅ CORREGIDO: Manejar separadores de miles (puntos) y porcentajes
      let num = val.replace(/[%]/g, ''); // Quitar %
      
      // ✅ Si el string contiene puntos, asumir que son separadores de miles
      // Ejemplo: "14.789" -> 14789, "1.234.567" -> 1234567
      if (num.includes('.') && !num.includes(',')) {
        // Solo puntos - interpretar como separadores de miles
        num = num.replace(/\./g, '');
      } else if (num.includes(',') && !num.includes('.')) {
        // Solo comas - interpretar como separadores de miles
        num = num.replace(/,/g, '');
      } else if (num.includes('.') && num.includes(',')) {
        // Ambos - el último carácter determina el separador decimal
        const lastDot = num.lastIndexOf('.');
        const lastComma = num.lastIndexOf(',');
        
        if (lastDot > lastComma) {
          // Punto es decimal, comas son separadores de miles: "1,234.56"
          num = num.replace(/,/g, '');
        } else {
          // Coma es decimal, puntos son separadores de miles: "1.234,56"
          num = num.replace(/\./g, '').replace(',', '.');
        }
      }
      
      let parsed = parseFloat(num);
      if (!isNaN(parsed)) return parsed;
    }
    if (typeof val === 'number') return val;
    return 0;
  }

  // ✅ NUEVO: Función específica para números con separadores de miles
  function parseThousandsSeparatedNumber(val) {
    if (typeof val === 'number') return val;
    if (typeof val !== 'string') return 0;
    
    // Limpiar el string
    let cleaned = val.toString().trim();
    
    // Si contiene solo dígitos y puntos (sin comas), tratar puntos como separadores de miles
    if (/^\d{1,3}(\.\d{3})*$/.test(cleaned)) {
      return parseInt(cleaned.replace(/\./g, ''), 10);
    }
    
    // Si contiene solo dígitos y comas (sin puntos), tratar comas como separadores de miles
    if (/^\d{1,3}(,\d{3})*$/.test(cleaned)) {
      return parseInt(cleaned.replace(/,/g, ''), 10);
    }
    
    // Usar la función general para otros casos
    return parseSortableValue(val);
  }

  if (window.DataTable && window.DataTable.ext && window.DataTable.ext.type) {
    // Para columnas de porcentaje
    DataTable.ext.type.order['percent-custom-pre'] = parseSortableValue;
    // Para columnas de posición
    DataTable.ext.type.order['position-custom-pre'] = parseSortableValue;
    // Para columnas de delta
    DataTable.ext.type.order['delta-custom-pre'] = parseSortableValue;
    // ✅ NUEVO: Para columnas de números con separadores de miles
    DataTable.ext.type.order['thousands-separated-pre'] = parseThousandsSeparatedNumber;
  }
  
  // ✅ NUEVO: Aplicar tipos de ordenamiento personalizados para el modal
  if (window.DataTable && window.DataTable.ext && window.DataTable.ext.type) {
    // Asegurar que los tipos personalizados estén disponibles para el modal
    if (!DataTable.ext.type.order['percent-custom-pre']) {
      DataTable.ext.type.order['percent-custom-pre'] = parseSortableValue;
    }
    if (!DataTable.ext.type.order['position-custom-pre']) {
      DataTable.ext.type.order['position-custom-pre'] = parseSortableValue;
    }
    if (!DataTable.ext.type.order['thousands-separated-pre']) {
      DataTable.ext.type.order['thousands-separated-pre'] = parseThousandsSeparatedNumber;
    }
  }

  // ✅ Configuración de DataTable adaptada
  const columnDefs = [
    { targets: '_all', className: 'dt-body-right' },
    { targets: [0, 1], className: 'dt-body-left' }, // Iconos y URL a la izquierda
    { targets: 0, orderable: false }, // No ordenar la columna de iconos
    // Orden personalizado para cada columna relevante
    { targets: [2,3], type: 'thousands-separated' }, // Clicks P1 y P2 con separadores de miles
    { targets: [4], type: 'delta-custom' }, // ΔClicks (%)
    { targets: [5,6], type: 'thousands-separated' }, // Impressions P1 y P2 con separadores de miles
    { targets: [7], type: 'delta-custom' }, // ΔImp. (%)
    { targets: [8,9], type: 'percent-custom' }, // CTR P1 y P2
    { targets: [10], type: 'delta-custom' }, // ΔCTR (%)
    { targets: [11,12], type: 'position-custom' }, // Pos P1 y P2
    { targets: [13], type: 'delta-custom' } // ΔPos
  ];

  // ✅ Ocultar columnas para período único
  if (analysisType === 'single') {
    columnDefs.push(
      { targets: [3, 4, 6, 7, 9, 10, 12, 13], visible: false }  // Ocultar P2 y Delta (ajustado por nueva columna)
    );
  }

  try {
    console.log('🔧 Creando nueva DataTable...', { 
      analysisType, 
      rowsCount: urlsData.length,
      columnDefs: columnDefs.length 
    });
    
    // ✅ VERIFICACIÓN EXHAUSTIVA: La tabla debe existir y estar lista
    const table = document.getElementById('resultsTable');
    if (!table) {
      throw new Error('Tabla #resultsTable no encontrada después de verificación de estructura');
    }
    
    // Verificar que no hay instancias DataTable residuales
    if (window.DataTable && window.DataTable.isDataTable('#resultsTable')) {
      console.warn('⚠️ Se detectó DataTable residual justo antes de crear nueva instancia, limpiando...');
      try {
        if (window.$ && window.$.fn.DataTable.isDataTable('#resultsTable')) {
          window.$('#resultsTable').DataTable().destroy(false);
        }
      } catch (e) {
        console.warn('⚠️ Error limpiando DataTable residual, continuando...', e);
      }
    }
    
    // Verificar que la estructura es correcta
    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    if (!thead || !tbody) {
      console.warn('⚠️ Estructura de tabla incompleta, recreando...');
      ensureTableStructure();
    }
    
    // ✅ MEJORADO: Verificación exhaustiva y limpieza final
    let finalCleanupAttempts = 0;
    while (window.DataTable && window.DataTable.isDataTable('#resultsTable') && finalCleanupAttempts < 3) {
      finalCleanupAttempts++;
      console.warn(`⚠️ DataTable aún detectada después de limpieza, intento ${finalCleanupAttempts}/3...`);
      
      try {
        // Intentar destrucción completa
        if (window.$ && window.$.fn.DataTable && window.$.fn.DataTable.isDataTable('#resultsTable')) {
          window.$('#resultsTable').DataTable().destroy(true); // true = remover del DOM
          console.log('✅ Destrucción completa con jQuery');
        } else {
          new DataTable('#resultsTable').destroy(true);
          console.log('✅ Destrucción completa con API nativa');
        }
        
        // Forzar recreación de estructura si se removió del DOM
        if (!document.getElementById('resultsTable')) {
          ensureTableStructure();
          console.log('✅ Estructura de tabla recreada después de destrucción completa');
        }
        
        break; // Salir del loop si tuvo éxito
      } catch (e) {
        console.warn(`⚠️ Error en destrucción final intento ${finalCleanupAttempts}:`, e);
        
        if (finalCleanupAttempts >= 3) {
          // Último recurso: recrear la tabla completamente
          console.warn('🆘 Forzando recreación completa de la tabla...');
          const resultsBlock = document.getElementById('resultsBlock');
          if (resultsBlock) {
            // Remover tabla antigua completamente
            const oldTable = document.getElementById('resultsTable');
            if (oldTable) {
              oldTable.remove();
            }
            
            // Recrear estructura
            ensureTableStructure();
            console.log('✅ Tabla recreada completamente como último recurso');
          }
        }
      }
    }
    
    // ✅ VERIFICACIÓN FINAL: Asegurar que la tabla tiene datos antes de crear DataTable
    const finalTableBody = document.querySelector('#resultsTable tbody');
    const finalRowCount = finalTableBody ? finalTableBody.children.length : 0;
    console.log(`🔍 Verificación pre-DataTable: ${finalRowCount} filas en tbody`);
    
    if (finalRowCount === 0) {
      console.warn('⚠️ No hay filas en tbody antes de crear DataTable');
      
      // Intentar re-añadir los datos
      console.log('🔄 Re-intentando añadir datos al tbody...');
      if (finalTableBody && urlsData && urlsData.length > 0) {
        urlsData.forEach((row, index) => {
          // Usar el mismo HTML de antes pero simplificado para este reintento
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td class="dt-body-center">
              <i class="fas fa-list keywords-icon" data-url="${escapeHtml(row.url)}" title="Ver keywords para esta URL" style="cursor:pointer; color: #007bff;"></i>
            </td>
            <td class="dt-body-left url-cell" title="${row.url}">${row.url}</td>
            <td>${(row.clicks_p1 ?? 0).toLocaleString('es-ES')}</td>
            <td>${(row.clicks_p2 ?? 0).toLocaleString('es-ES')}</td>
            <td>${formatPercentageChange(row.delta_clicks_percent)}</td>
            <td>${(row.impressions_p1 ?? 0).toLocaleString('es-ES')}</td>
            <td>${(row.impressions_p2 ?? 0).toLocaleString('es-ES')}</td>
            <td>${formatPercentageChange(row.delta_impressions_percent)}</td>
            <td>${typeof row.ctr_p1 === 'number' ? row.ctr_p1.toFixed(2) + '%' : 'N/A'}</td>
            <td>${typeof row.ctr_p2 === 'number' ? row.ctr_p2.toFixed(2) + '%' : 'N/A'}</td>
            <td>${formatPercentageChange(row.delta_ctr_percent, true)}</td>
            <td>${formatPosition(row.position_p1)}</td>
            <td>${formatPosition(row.position_p2)}</td>
            <td>${formatPositionDelta(row.delta_position_absolute, row.position_p1, row.position_p2)}</td>
          `;
          finalTableBody.appendChild(tr);
        });
        console.log(`✅ Re-añadidas ${urlsData.length} filas. Total en DOM: ${finalTableBody.children.length}`);
      }
    }
    
    // ✅ NUEVO: Pequeño delay para asegurar estabilidad del DOM
    await new Promise(resolve => setTimeout(resolve, 50));
    
    urlsDataTable = new DataTable('#resultsTable', {
      pageLength: 10,
      lengthMenu: [10, 25, 50, 100, -1],
      language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
      scrollX: true,
      responsive: false,
      columnDefs: columnDefs,
      order: [[2, 'desc']], // ✅ CORREGIDO: Siempre ordenar por clicks P1 (período actual, ajustado por nueva columna)
      drawCallback: () => {
        if (window.jQuery && window.jQuery.fn.tooltip) window.jQuery('[data-toggle="tooltip"]').tooltip();
      },
      // ✅ NUEVO: Configuraciones adicionales para evitar conflictos
      retrieve: false, // No recuperar instancia existente
      destroy: false,  // No permitir auto-destroy
      stateSave: false, // No guardar estado entre sesiones
      deferRender: true, // Renderizado diferido para mejor rendimiento
      processing: false // Desactivar indicador de procesamiento
    });
    
    console.log('✅ Nueva DataTable creada exitosamente');
    
    // ✅ NUEVO: Forzar un redraw para asegurar que se muestren los datos
    if (urlsDataTable && urlsDataTable.draw) {
      urlsDataTable.draw();
      console.log('✅ Forzado redraw de DataTable');
    }
    
  } catch (error) {
    console.error('❌ Error al crear DataTable:', error);
    
    // ✅ MEJORADO: Fallback más robusto
    console.log('🔄 Implementando fallback - tabla básica sin DataTable...');
    
    // Asegurar que la tabla sea visible y funcional
    if (elems.tableBody && urlsData.length > 0) {
      console.log(`📊 Tabla básica fallback con ${urlsData.length} filas`);
      
      // La tabla ya está renderizada arriba, solo asegurar visibilidad
      const table = document.getElementById('resultsTable');
      if (table) {
        table.style.display = '';
        table.style.width = '100%';
        console.log('✅ Tabla básica configurada como fallback');
      }
    }
    
    // Resetear variable por seguridad
    urlsDataTable = null;
  }

  // ✅ MEJORADO: Mostrar sección con logging
  if (elems.resultsSection) {
    elems.resultsSection.style.display = 'block';
    console.log('✅ Sección de resultados mostrada');
  }
  
  if (elems.resultsTitle) {
    elems.resultsTitle.style.display = 'block';
    
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
    
    if (resultsSection && resultsSection.style.display !== 'block') {
      console.warn('⚠️ Sección de resultados no visible, forzando visibilidad...');
      resultsSection.style.display = 'block';
    }
    
    if (resultsTitle && resultsTitle.style.display !== 'block') {
      console.warn('⚠️ Título de resultados no visible, forzando visibilidad...');
      resultsTitle.style.display = 'block';
      resultsTitle.textContent = 'URLs Performance';
    }
    
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
  
  if (elems.resultsSection) {
    elems.resultsSection.style.display = 'block';
    console.log('✅ Sección de resultados mostrada (estado error)');
  }
  
  if (elems.resultsTitle) {
    elems.resultsTitle.style.display = 'block';
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

// ✅ NUEVO: Variables para almacenar datos pre-procesados y DataTables del modal
let preProcessedModalData = {
  top3: { keywords: [], dataTable: null, analysisType: 'single' },
  top10: { keywords: [], dataTable: null, analysisType: 'single' },
  top20: { keywords: [], dataTable: null, analysisType: 'single' },
  top20plus: { keywords: [], dataTable: null, analysisType: 'single' }
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

function formatPercentageChangeModal(value, isCTR = false) {
  if (value === 'Infinity' || value === Infinity) {
    return '+∞%';
  }
  if (value === '-Infinity' || value === -Infinity) {
    return '-∞%';
  }
  if (value === 'New' || value === 'Nuevo') {
    return 'New';
  }
  if (value === 'Lost' || value === 'Perdido') {
    return 'Lost';
  }
  if (typeof value === 'number') {
    if (isCTR) {
      return value >= 0 ? `+${value.toFixed(2)}pp` : `${value.toFixed(2)}pp`;
    } else {
      return value >= 0 ? `+${value.toFixed(1)}%` : `${value.toFixed(1)}%`;
    }
  }
  return 'N/A';
}

function formatPositionModal(value) {
  return typeof value === 'number' ? value.toFixed(1) : 'N/A';
}

function formatPositionDeltaModal(delta, pos1, pos2) {
  if (delta === 'New' || delta === 'Nuevo') return 'New';
  if (delta === 'Lost' || delta === 'Perdido') return 'Lost';
  if (typeof delta === 'number') {
    return delta >= 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1);
  }
  return 'N/A';
}

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
  
  // Verificar que la DataTable está lista
  if (!data.dataTable && data.keywords.length > 0) {
    console.log('🔄 DataTable no está lista, creando...');
    createDataTableForRange(positionRange, data.keywords, data.analysisType);
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
            <div class="table-responsive-container">
              <table id="keywordModalTable-${range}" class="display" style="width:100%;">
                <thead>
                  <tr>
                    <th>View SERP</th>
                    <th>Keyword</th>
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
                <tbody id="keywordModalTableBody-${range}"></tbody>
              </table>
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

// ✅ NUEVO: Función para crear DataTable para un rango específico
function createDataTableForRange(range, keywords, analysisType) {
  // Destruir DataTable anterior si existe
  if (preProcessedModalData[range].dataTable) {
    preProcessedModalData[range].dataTable.destroy();
    preProcessedModalData[range].dataTable = null;
  }

  const tableId = `keywordModalTable-${range}`;
  const tableBodyId = `keywordModalTableBody-${range}`;
  const modalTableBody = document.getElementById(tableBodyId);
  
  if (!modalTableBody) {
    console.error(`❌ No se encontró el tbody para ${range}`);
    return;
  }

  // Limpiar tabla
  modalTableBody.innerHTML = '';
  
  if (keywords.length === 0) {
    modalTableBody.innerHTML = '<tr><td colspan="14">No se encontraron keywords en este rango de posiciones.</td></tr>';
    return;
  }

  console.log(`🔄 Creando DataTable para ${range} con ${keywords.length} keywords...`);
  const startTime = performance.now();

  // Llenar la tabla con las keywords
  keywords.forEach(keyword => {
    // Calcular clases CSS para deltas
    const deltaClicksClass =
      (keyword.delta_clicks_percent === 'Infinity' || (typeof keyword.delta_clicks_percent === 'number' && keyword.delta_clicks_percent > 0))
        ? 'positive-change'
        : (typeof keyword.delta_clicks_percent === 'number' && keyword.delta_clicks_percent < 0)
          ? 'negative-change'
          : '';
    const deltaImprClass =
      (keyword.delta_impressions_percent === 'Infinity' || (typeof keyword.delta_impressions_percent === 'number' && keyword.delta_impressions_percent > 0))
        ? 'positive-change'
        : (typeof keyword.delta_impressions_percent === 'number' && keyword.delta_impressions_percent < 0)
          ? 'negative-change'
          : '';
    const deltaCtrClass =
      (keyword.delta_ctr_percent === 'Infinity' || (typeof keyword.delta_ctr_percent === 'number' && keyword.delta_ctr_percent > 0))
        ? 'positive-change'
        : (typeof keyword.delta_ctr_percent === 'number' && keyword.delta_ctr_percent < 0)
          ? 'negative-change'
          : '';
    const deltaPosClass =
      (keyword.delta_position_absolute === 'New' || (typeof keyword.delta_position_absolute === 'number' && keyword.delta_position_absolute > 0))
        ? 'positive-change'
        : (keyword.delta_position_absolute === 'Lost' || (typeof keyword.delta_position_absolute === 'number' && keyword.delta_position_absolute < 0))
          ? 'negative-change'
          : '';

    const tr = document.createElement('tr');
    
    // Configurar visibilidad de columnas según el tipo
    const p2ColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';
    const deltaColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';
    
    tr.innerHTML = `
      <td class="dt-body-center">
        <i class="fas fa-search serp-icon"
           data-keyword="${escapeHtml(keyword.keyword)}"
           data-url="${escapeHtml(keyword.url || '')}"
           title="Ver SERP para ${escapeHtml(keyword.keyword)}"
           style="cursor:pointer;"></i>
      </td>
      <td class="dt-body-left kw-cell">${escapeHtml(keyword.keyword || 'N/A')}</td>
      <td>${(keyword.clicks_m1 ?? 0).toLocaleString('es-ES')}</td>
      <td ${p2ColumnsStyle}>${(keyword.clicks_m2 ?? 0).toLocaleString('es-ES')}</td>
      <td class="${deltaClicksClass}" ${deltaColumnsStyle}>${formatPercentageChangeModal(keyword.delta_clicks_percent)}</td>
      <td>${(keyword.impressions_m1 ?? 0).toLocaleString('es-ES')}</td>
      <td ${p2ColumnsStyle}>${(keyword.impressions_m2 ?? 0).toLocaleString('es-ES')}</td>
      <td class="${deltaImprClass}" ${deltaColumnsStyle}>${formatPercentageChangeModal(keyword.delta_impressions_percent)}</td>
      <td>${typeof keyword.ctr_m1 === 'number' ? (keyword.ctr_m1 * 100).toFixed(2) + '%' : 'N/A'}</td>
      <td ${p2ColumnsStyle}>${typeof keyword.ctr_m2 === 'number' ? (keyword.ctr_m2 * 100).toFixed(2) + '%' : 'N/A'}</td>
      <td class="${deltaCtrClass}" ${deltaColumnsStyle}>${formatPercentageChangeModal(keyword.delta_ctr_percent, true)}</td>
      <td>${formatPositionModal(keyword.position_m1)}</td>
      <td ${p2ColumnsStyle}>${formatPositionModal(keyword.position_m2)}</td>
      <td class="${deltaPosClass}" ${deltaColumnsStyle}>${formatPositionDeltaModal(keyword.delta_position_absolute, keyword.position_m1, keyword.position_m2)}</td>
    `;
    modalTableBody.appendChild(tr);
  });

  // Agregar event listeners para los iconos de SERP
  const serpIcons = modalTableBody.querySelectorAll('.serp-icon');
  serpIcons.forEach(icon => {
    icon.addEventListener('click', () => {
      if (typeof openSerpModal === 'function') {
        openSerpModal(icon.dataset.keyword, icon.dataset.url);
      }
    });
  });

  // Actualizar headers según el tipo de análisis
  updateModalTableHeadersForRange(range, analysisType);

  // Configurar columnas para DataTable
  const columnDefs = [
    { targets: '_all', className: 'dt-body-right' },
    { targets: [0, 1], className: 'dt-body-left' },
    { targets: 0, orderable: false },
    { targets: [2, 3], type: 'thousands-separated-pre' },
    { targets: [4], type: 'delta-custom-pre' },
    { targets: [5, 6], type: 'thousands-separated-pre' },
    { targets: [7], type: 'delta-custom-pre' },
    { targets: [8, 9], type: 'percent-custom-pre' },
    { targets: [10], type: 'delta-custom-pre' },
    { targets: [11, 12], type: 'position-custom-pre' },
    { targets: [13], type: 'delta-custom-pre' }
  ];

  // Ocultar columnas para período único
  if (analysisType === 'single') {
    columnDefs.push(
      { targets: [3, 4, 6, 7, 9, 10, 12, 13], visible: false }
    );
  }

  // Asegurar que los tipos de ordenamiento estén disponibles
  if (window.DataTable && window.DataTable.ext && window.DataTable.ext.type) {
    if (!DataTable.ext.type.order['delta-custom-pre']) {
      DataTable.ext.type.order['delta-custom-pre'] = parseSortableValue;
    }
    if (!DataTable.ext.type.order['thousands-separated-pre']) {
      DataTable.ext.type.order['thousands-separated-pre'] = parseThousandsSeparatedNumber;
    }
    if (!DataTable.ext.type.order['percent-custom-pre']) {
      DataTable.ext.type.order['percent-custom-pre'] = parseSortableValue;
    }
    if (!DataTable.ext.type.order['position-custom-pre']) {
      DataTable.ext.type.order['position-custom-pre'] = parseSortableValue;
    }
  }

  // Inicializar DataTable
  if (window.DataTable) {
    preProcessedModalData[range].dataTable = new DataTable(`#${tableId}`, {
      pageLength: 10,
      lengthMenu: [10, 25, 50, 100],
      language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
      scrollX: true,
      responsive: false,
      columnDefs: columnDefs,
      order: [[2, 'desc']], // Ordenar por clicks M1 de mayor a menor
      drawCallback: () => {
        if (window.jQuery && window.jQuery.fn.tooltip) window.jQuery('[data-toggle="tooltip"]').tooltip();
      }
    });
    
    const endTime = performance.now();
    console.log(`✅ DataTable para ${range} creado en ${(endTime - startTime).toFixed(2)}ms`);
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
      if (preProcessedModalData[range].dataTable) {
        preProcessedModalData[range].dataTable.destroy();
        preProcessedModalData[range].dataTable = null;
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

  // Pre-crear las DataTables para cada rango
  createPreloadedDataTables();
}

// ✅ NUEVO: Función para crear DataTables pre-cargadas
function createPreloadedDataTables() {
  if (!modalContainersCreated) {
    createAllModalContainers();
  }

  Object.keys(preProcessedModalData).forEach(range => {
    const data = preProcessedModalData[range];
    if (data.keywords.length > 0) {
      createDataTableForRange(range, data.keywords, data.analysisType);
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

// ✅ NUEVO: Función para renderizar los datos en el modal
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
  
  // Crear tabla
  const tableHTML = `
    <div class="url-keywords-info" style="margin-bottom: 1em; padding: 1em; background: #f8f9fa; border-radius: 5px;">
      <p><strong>URL analizada:</strong> ${escapeHtml(data.url)}</p>
      <p><strong>Keywords encontradas:</strong> ${keywords.length}</p>
      <p><strong>Período:</strong> ${data.periods.current.label}</p>
      ${hasComparison ? `<p><strong>Comparando con:</strong> ${data.periods.comparison.label}</p>` : ''}
    </div>
    
    <div class="table-responsive-container">
      <table id="keywordModalTable-url" class="display" style="width:100%;">
        <thead>
          <tr>
            <th>View SERP</th>
            <th>Keyword</th>
            <th>Clicks P1</th>
            ${hasComparison ? '<th>Clicks P2</th>' : ''}
            ${hasComparison ? '<th>ΔClicks (%)</th>' : ''}
            <th>Impressions P1</th>
            ${hasComparison ? '<th>Impressions P2</th>' : ''}
            ${hasComparison ? '<th>ΔImp. (%)</th>' : ''}
            <th>CTR P1 (%)</th>
            ${hasComparison ? '<th>CTR P2 (%)</th>' : ''}
            ${hasComparison ? '<th>ΔCTR (%)</th>' : ''}
            <th>Pos P1</th>
            ${hasComparison ? '<th>Pos P2</th>' : ''}
            ${hasComparison ? '<th>ΔPos</th>' : ''}
          </tr>
        </thead>
        <tbody>
          ${keywords.map(keyword => createUrlKeywordRow(keyword, hasComparison)).join('')}
        </tbody>
      </table>
    </div>
  `;
  
  modalBody.innerHTML = tableHTML;
  
  // Inicializar DataTable
  if (window.DataTable) {
    const columnDefs = [
      { targets: '_all', className: 'dt-body-right' },
      { targets: [0, 1], className: 'dt-body-left' },
      { targets: 0, orderable: false }
    ];
    
    new DataTable('#keywordModalTable-url', {
      pageLength: 10,
      lengthMenu: [10, 25, 50, 100],
      language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
      scrollX: true,
      responsive: false,
      columnDefs: columnDefs,
      order: [[2, 'desc']] // Ordenar por clicks
    });
  }
  
  // Añadir event listeners para SERP
  const serpIcons = modalBody.querySelectorAll('.serp-icon');
  serpIcons.forEach(icon => {
    icon.addEventListener('click', () => {
      if (typeof openSerpModal === 'function') {
        openSerpModal(icon.dataset.keyword, icon.dataset.url);
      }
    });
  });
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
           data-keyword="${escapeHtml(keyword.keyword)}"
           data-url="${escapeHtml(keyword.url)}"
           title="Ver SERP para ${escapeHtml(keyword.keyword)}"
           style="cursor:pointer;"></i>
      </td>
      <td class="dt-body-left">${escapeHtml(keyword.keyword)}</td>
      <td>${(keyword.clicks_m1 || 0).toLocaleString('es-ES')}</td>
      ${hasComparison ? `<td>${(keyword.clicks_m2 || 0).toLocaleString('es-ES')}</td>` : ''}
      ${hasComparison ? `<td class="${deltaClicksClass}">${formatPercentageChange(keyword.delta_clicks_percent)}</td>` : ''}
      <td>${(keyword.impressions_m1 || 0).toLocaleString('es-ES')}</td>
      ${hasComparison ? `<td>${(keyword.impressions_m2 || 0).toLocaleString('es-ES')}</td>` : ''}
      ${hasComparison ? `<td class="${deltaImprClass}">${formatPercentageChange(keyword.delta_impressions_percent)}</td>` : ''}
      <td>${typeof keyword.ctr_m1 === 'number' ? keyword.ctr_m1.toFixed(2) + '%' : 'N/A'}</td>
      ${hasComparison ? `<td>${typeof keyword.ctr_m2 === 'number' ? keyword.ctr_m2.toFixed(2) + '%' : 'N/A'}</td>` : ''}
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