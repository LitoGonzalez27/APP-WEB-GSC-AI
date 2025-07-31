// static/js/ui-ai-overview-display.js - Visualización de resultados AI Overview

import { escapeHtml, formatNumber, showToast } from './ui-ai-overview-utils.js';
import { showAIDetailsModalImproved } from './ui-ai-overview-modals.js';
import { openSerpModal } from './ui-serp-modal.js'; // IMPORTANTE: Importar la función del modal SERP

export function displayAIOverviewResults(data) {
  const resultsContainer = document.getElementById('aiOverviewResultsContainer');
  if (!resultsContainer) {
    console.error('Container aiOverviewResultsContainer not found');
    return;
  }

  // Limpiar resultados anteriores antes de mostrar los nuevos
  resultsContainer.innerHTML = '';

  // Mostrar sección AI Overview
  const aiSection = document.getElementById('aiOverviewSection');
  if (aiSection) aiSection.style.display = 'block';

  // 1️⃣ Mostrar resumen
  displaySummary(data.summary, resultsContainer);
  
  // 2️⃣ Mostrar tablas de tipología y posiciones (MOVIDO ARRIBA)
  displayTypologyChart(resultsContainer, data);
  
  // 3️⃣ Mostrar tabla detallada de keywords (MOVIDO ABAJO)
  displayDetailedResults(data.keywordResults, resultsContainer);
  
  showToast('AI Overview analysis complete', 'success');
}

// ====================================
// 📊 GRÁFICO DE TIPOLOGÍA DE CONSULTAS
// ====================================

/**
 * Muestra el gráfico de barras de tipología basado en el análisis actual
 */
export function displayTypologyChart(container, analysisData) {
  if (!container) {
    console.error('Container no encontrado para gráfico de tipología');
    return;
  }

  // Verificar que tenemos datos del análisis actual
  if (!analysisData || !analysisData.keywordResults || analysisData.keywordResults.length === 0) {
    console.log('No hay datos del análisis actual para tipología');
    return;
  }

  console.log('📊 Generando tipología dinámica con', analysisData.keywordResults.length, 'keywords');

  // Crear contenedor del gráfico con layout de 2 columnas
  const chartHTML = `
    <div class="ai-typology-section">
      <div class="ai-typology-header">
        <h3 class="ai-typology-title">
          <i class="fas fa-chart-bar"></i>
          AI Overview Analysis by Keyword Length & Position
        </h3>
        <div class="ai-typology-subtitle">
          Based on current analysis of ${analysisData.keywordResults.length} keywords
        </div>
      </div>
      
      <div class="ai-typology-main-container">
        <!-- COLUMNA IZQUIERDA: Tabla de Longitud de Keywords -->
        <div class="ai-typology-left">
          <div id="keywordLengthTableContainer" class="ai-typology-container">
            <div class="typology-loading">
              <i class="fas fa-calculator"></i>
              <p>Processing keyword analysis...</p>
            </div>
          </div>
        </div>
        
        <!-- COLUMNA DERECHA: Tabla de Posiciones AIO -->
        <div class="ai-typology-right">
          <div id="aioPositionTableContainer" class="aio-position-table-container">
            <div class="typology-loading">
              <i class="fas fa-list-ol"></i>
              <p>Analyzing AI Overview positions...</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  container.insertAdjacentHTML('beforeend', chartHTML);

  // Procesar datos dinámicamente para ambas visualizaciones
  processCurrentAnalysisData(analysisData.keywordResults);
}

/**
 * Procesa los datos del análisis actual y genera las tablas
 */
function processCurrentAnalysisData(keywordResults) {
  console.log('🔍 Processing', keywordResults.length, 'keywords for analysis');

  // Definir categorías actualizadas según los nuevos criterios
  const categories = {
    'short_tail': { label: 'Short Tail', description: '1 word', min: 1, max: 1, total: 0, withAI: 0 },
    'middle_tail': { label: 'Middle Tail', description: '2-3 words', min: 2, max: 3, total: 0, withAI: 0 },
    'long_tail': { label: 'Long Tail', description: '4-8 words', min: 4, max: 8, total: 0, withAI: 0 },
    'super_long_tail': { label: 'Super Long Tail', description: '9+ words', min: 9, max: Infinity, total: 0, withAI: 0 }
  };

  // Procesar cada keyword del análisis actual
  keywordResults.forEach(result => {
    const keyword = result.keyword || '';
    const wordCount = keyword.trim().split(/\s+/).length;
    const hasAI = result.ai_analysis?.has_ai_overview || false;

    console.log(`📝 Keyword: "${keyword}" - ${wordCount} words - AI: ${hasAI}`);

    // Clasificar en la categoría correcta
    for (const [key, category] of Object.entries(categories)) {
      if (wordCount >= category.min && wordCount <= category.max) {
        category.total++;
        if (hasAI) {
          category.withAI++;
        }
        break;
      }
    }
  });

  // Crear la tabla de longitud de keywords
  createKeywordLengthTable(categories, keywordResults.length);
  
  // Crear la tabla de posiciones AIO
  createAIOPositionTable(keywordResults);
}

/**
 * Crea la tabla de longitud de keywords
 */
function createKeywordLengthTable(categories, totalKeywords) {
  const container = document.getElementById('keywordLengthTableContainer');
  if (!container) {
    console.error('Container de tabla de longitud de keywords no encontrado');
    return;
  }

  // Calcular total de keywords con AI Overview
  const totalWithAI = Object.values(categories).reduce((sum, cat) => sum + cat.withAI, 0);

  console.log('📊 Creating keyword length table with data:', categories);

  // Crear tabla HTML
  let tableHTML = `
    <div class="aio-position-table-header">
      <h4 class="aio-position-table-title">Keyword Length Analysis</h4>
      <p class="aio-position-table-subtitle">
        ${totalWithAI} keywords with AI Overview from ${totalKeywords} analyzed
      </p>
    </div>
    
    <table class="aio-position-table">
      <thead>
        <tr>
          <th>Keyword Length</th>
          <th style="text-align: center;">Keywords with AIO</th>
          <th style="text-align: right;">Weight</th>
        </tr>
      </thead>
      <tbody>
  `;

  // Procesar cada categoría
  Object.values(categories).forEach(category => {
    // Porcentaje basado en keywords CON AIO (no total de keywords)
    const percentage = totalWithAI > 0 ? (category.withAI / totalWithAI * 100) : 0;
    
    tableHTML += `
      <tr>
        <td class="aio-position-range">
          <div style="font-weight: 600; color: #0D7FF3;">
            ${category.label} (${category.description})
          </div>
        </td>
        <td class="aio-position-count">
          <div style="font-weight: 700; font-size: 1.2rem;">${category.withAI}</div>
        </td>
        <td class="aio-position-percentage">${percentage.toFixed(1)}%</td>
      </tr>
    `;
  });

  tableHTML += `
      </tbody>
    </table>
    
    <div class="aio-position-summary" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(0,0,0,0.1); text-align: center;">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.85rem;">
        <div style="padding: 0.75rem; background: rgba(13, 127, 243, 0.08); border-radius: 8px;">
          <div style="font-weight: 700; color: #0D7FF3; font-size: 1.25rem;">${totalWithAI}</div>
          <div style="color: #666666;">With AI Overview</div>
        </div>
        <div style="padding: 0.75rem; background: rgba(149, 165, 166, 0.08); border-radius: 8px;">
          <div style="font-weight: 700; color: #95a5a6; font-size: 1.25rem;">${totalKeywords - totalWithAI}</div>
          <div style="color: #666666;">Without AI Overview</div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = tableHTML;
  
  console.log('✅ Keyword length table created');
}

/**
 * Procesa las posiciones AIO y crea datos para la tabla
 */
function processAIOPositionData(keywordResults) {
  console.log('🎯 Processing AIO positions for', keywordResults.length, 'keywords');

  // Definir rangos de posición
  const positionRanges = {
    '1-3': { label: '1 - 3', min: 1, max: 3, count: 0 },
    '4-6': { label: '4 - 6', min: 4, max: 6, count: 0 },
    '7-9': { label: '7 - 9', min: 7, max: 9, count: 0 },
    '10+': { label: '10 or more', min: 10, max: Infinity, count: 0 }
  };

  let totalWithAIOPosition = 0;

  // Procesar cada keyword del análisis actual
  keywordResults.forEach(result => {
    const keyword = result.keyword || '';
    const hasAI = result.ai_analysis?.has_ai_overview || false;
    const aioPosition = result.ai_analysis?.domain_ai_source_position;

    console.log(`🔍 Keyword: "${keyword}" - AI: ${hasAI} - AIO Position: ${aioPosition}`);

    // Solo procesar si tiene AI Overview y posición
    if (hasAI && aioPosition && aioPosition > 0) {
      totalWithAIOPosition++;
      
      // Clasificar en el rango correcto
      for (const [key, range] of Object.entries(positionRanges)) {
        if (aioPosition >= range.min && aioPosition <= range.max) {
          range.count++;
          console.log(`   ✅ Classified in range ${range.label} (position ${aioPosition})`);
          break;
        }
      }
    }
  });

  // Preparar datos para la tabla
  const positionData = [];
  
  Object.values(positionRanges).forEach(range => {
    const percentage = totalWithAIOPosition > 0 ? (range.count / totalWithAIOPosition * 100) : 0;
    
    if (range.count > 0 || totalWithAIOPosition === 0) { // Mostrar todos los rangos, incluso con 0
      positionData.push({
        range: range.label,
        count: range.count,
        percentage: percentage
      });
    }
  });

  console.log('📊 AIO positions summary:', positionData);

  return {
    positionData,
    totalWithAIOPosition,
    totalWithAI: keywordResults.filter(r => r.ai_analysis?.has_ai_overview).length
  };
}

/**
 * Crea la tabla de posiciones AIO
 */
function createAIOPositionTable(keywordResults) {
  const container = document.getElementById('aioPositionTableContainer');
  if (!container) {
    console.error('AIO position table container not found');
    return;
  }

  // Procesar datos de posiciones
  const { positionData, totalWithAIOPosition, totalWithAI } = processAIOPositionData(keywordResults);

  // Si no hay datos de posiciones, mostrar mensaje
  if (totalWithAIOPosition === 0) {
    container.innerHTML = `
      <div class="typology-empty">
        <i class="fas fa-info-circle"></i>
        <p>Your domain doesn't appear as a source in any AI Overview</p>
        <p style="font-size: 0.85rem; opacity: 0.7; margin-top: 0.5rem;">
          ${totalWithAI} keywords have AI Overview, but your site is not mentioned
        </p>
      </div>
    `;
    return;
  }

  // Crear tabla HTML
  let tableHTML = `
    <div class="aio-position-table-header">
      <h4 class="aio-position-table-title">AI Overview Positions</h4>
      <p class="aio-position-table-subtitle">
        ${totalWithAIOPosition} mentions of your domain in ${totalWithAI} detected AI Overview
      </p>
    </div>
    
    <table class="aio-position-table">
      <thead>
        <tr>
          <th>Position</th>
          <th style="text-align: center;">Keywords</th>
          <th style="text-align: right;">Weight</th>
        </tr>
      </thead>
      <tbody>
  `;

  positionData.forEach(item => {
    tableHTML += `
      <tr>
        <td class="aio-position-range">${item.range}</td>
        <td class="aio-position-count">${item.count}</td>
        <td class="aio-position-percentage">${item.percentage.toFixed(1)}%</td>
      </tr>
    `;
  });

  tableHTML += `
      </tbody>
    </table>
    
    <div class="aio-position-summary" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(0,0,0,0.1); text-align: center;">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.85rem;">
        <div style="padding: 0.75rem; background: rgba(231, 76, 60, 0.08); border-radius: 8px;">
          <div style="font-weight: 700; color: #e74c3c; font-size: 1.25rem;">${totalWithAIOPosition}</div>
          <div style="color: #666666;">Total mentions</div>
        </div>
        <div style="padding: 0.75rem; background: rgba(149, 165, 166, 0.08); border-radius: 8px;">
          <div style="font-weight: 700; color: #95a5a6; font-size: 1.25rem;">${totalWithAI - totalWithAIOPosition}</div>
          <div style="color: #666666;">Without mention</div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = tableHTML;
  
  console.log('✅ AIO position table created');
}

function displaySummary(summary, container) {
  // Calcular % de visibilidad en AIO
  const keywordsWithAIO = summary.keywords_with_ai_overview || 0;
  const mentionsInAIO = summary.keywords_as_ai_source || 0;
  const totalKeywords = summary.total_keywords_analyzed || 0;
  const visibilityPercentage = keywordsWithAIO > 0 ? ((mentionsInAIO / keywordsWithAIO) * 100).toFixed(1) : '0.0';
  
  // Calcular peso AIO en SERPs
  const pesoAIOPercentage = totalKeywords > 0 ? ((keywordsWithAIO / totalKeywords) * 100).toFixed(1) : '0.0';
  
  // 🆕 NUEVO: Obtener posición promedio en AIO
  const averageAIOPosition = summary.average_ai_position;
  
  const summaryHTML = `
    <div class="ai-overview-summary" style="
      /* Eliminamos el background linear-gradient y el border directos
         para que el estilo de la sección principal glass-effect sea dominante */
      padding: 1.5em;
      margin-bottom: 2em;
      border-radius: 12px; /* Mantenemos el border-radius para las métricas internas */
    ">
      <h3 style="text-align: center; color: var(--heading); margin-bottom: 1em;">
        <i class="fas fa-chart-line"></i> AI Overview Analysis Summary
      </h3>
      <div style="
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 1em;
        margin-bottom: 1em;
      ">
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); /* Usar variable CSS para el fondo de la tarjeta */
          border-radius: 8px;
          border: 1px solid var(--border-color); /* Añadir borde */
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: var(--cta-bg);">
            ${formatNumber(totalKeywords)}
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">Keywords Analyzed</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: var(--error-color);">
            ${formatNumber(keywordsWithAIO)}
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">With AI Overview</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: ${parseFloat(pesoAIOPercentage) >= 75 ? 'var(--error-color)' : parseFloat(pesoAIOPercentage) >= 50 ? 'var(--warning-color)' : parseFloat(pesoAIOPercentage) >= 25 ? 'var(--info-color)' : 'var(--success-color)'};">
            ${pesoAIOPercentage}%
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">AIO Weight in SERPs</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: var(--warning-color);">
            ${formatNumber(mentionsInAIO)}
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">Mentions of Your Brand</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: ${parseFloat(visibilityPercentage) >= 50 ? 'var(--success-color)' : parseFloat(visibilityPercentage) >= 25 ? 'var(--warning-color)' : 'var(--error-color)'};">
            ${visibilityPercentage}%
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">% Visibility in AIO</div>
        </div>
        <div class="summary-metric" style="
          text-align: center; 
          padding: 1em; 
          background: var(--card-bg); 
          border-radius: 8px;
          border: 1px solid var(--border-color);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
          <div style="font-size: 2em; font-weight: bold; color: ${averageAIOPosition !== null && averageAIOPosition !== undefined ? (averageAIOPosition <= 2 ? 'var(--success-color)' : averageAIOPosition <= 4 ? 'var(--warning-color)' : 'var(--error-color)') : 'gray'};">
            ${averageAIOPosition !== null && averageAIOPosition !== undefined ? averageAIOPosition : 'N/A'}
          </div>
          <div style="color: var(--text-color); font-size: 0.9em; opacity: 0.7;">Avg Position in AIO</div>
        </div>
      </div>
    </div>
  `;
  
  container.innerHTML = summaryHTML; 
}

function displayDetailedResults(results, container) {
  // Eliminar tabla previa si existe
  const oldTable = document.getElementById('aiOverviewTable');
  if (oldTable) oldTable.parentNode.removeChild(oldTable);

  if (!results || results.length === 0) {
    container.insertAdjacentHTML('beforeend', `
      <div style="text-align: center; padding: 2em; color: var(--text-color); opacity: 0.7;">
        <i class="fas fa-info-circle" style="font-size: 2em; margin-bottom: 0.5em;"></i>
        <p>No detailed results found to display.</p>
      </div>
    `);
    return;
  }

  // Estructura de tabla igual a Keywords
  const tableHTML = `
    <div class="ai-results-table-container" style="margin-top: 2em;">
      <h3 style="text-align: center; margin-bottom: 1em; color: var(--heading);">
        <i class="fas fa-table"></i> Detailed Results by Keyword
      </h3>
      <div class="table-responsive-container">
        <table id="aiOverviewTable" class="dataTable display" style="width:100%">
          <thead>
            <tr>
              <th style="width: 60px;">View SERP</th>
              <th>Keyword</th>
              <th>With AIO</th>
              <th>Organic Position</th>
              <th>Your Domain in AIO</th>
              <th>AIO Position</th>
            </tr>
          </thead>
          <tbody>
            ${results.map((result, index) => createResultRowAIO(result)).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
  container.insertAdjacentHTML('beforeend', tableHTML);

  // Inicializar DataTable con las mismas opciones que Keywords
  if (window.DataTable) {
    new DataTable('#aiOverviewTable', {
      pageLength: 10,
      lengthMenu: [10, 25, 50, 100, -1],
      language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
      scrollX: true,
      responsive: false,
      autoWidth: false,
      sScrollX: "100%",
      sScrollXInner: "1300px",
      columnDefs: [
        { targets: 0, orderable: false, className: 'dt-body-center', width: '60px' },
        { targets: 1, className: 'dt-body-left kw-cell', width: '250px' },
        { targets: 2, className: 'dt-body-center', width: '120px' },
        { targets: 3, className: 'dt-body-center', width: '150px' },
        { targets: 4, className: 'dt-body-center', width: '180px' },
        { targets: 5, className: 'dt-body-center', width: '130px' }
      ],
      order: [[2, 'desc']],
      drawCallback: () => {
        if (window.jQuery && window.jQuery.fn.tooltip) window.jQuery('[data-toggle="tooltip"]').tooltip();
      },
      initComplete: () => {
        // Forzar ancho del contenedor scroll interno
        const scrollHeadInner = document.querySelector('#aiOverviewTable_wrapper .dataTables_scrollHeadInner');
        if (scrollHeadInner) {
          scrollHeadInner.style.width = '1300px';
          scrollHeadInner.style.boxSizing = 'content-box';
          
          // También forzar el ancho de la tabla dentro del contenedor
          const innerTable = scrollHeadInner.querySelector('table');
          if (innerTable) {
            innerTable.style.width = '1300px';
            innerTable.style.marginLeft = '0px';
          }
        }
        
        // Forzar anchos después de la inicialización
        const table = document.getElementById('aiOverviewTable');
        if (table) {
          const headers = table.querySelectorAll('thead th');
          const widths = ['60px', '250px', '120px', '150px', '180px', '130px'];
          headers.forEach((header, index) => {
            if (widths[index]) {
              header.style.width = widths[index];
              header.style.minWidth = widths[index];
              header.style.maxWidth = widths[index];
            }
          });
          
          // También forzar en las celdas del cuerpo
          const rows = table.querySelectorAll('tbody tr');
          rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            cells.forEach((cell, index) => {
              if (widths[index]) {
                cell.style.width = widths[index];
                cell.style.minWidth = widths[index];
                cell.style.maxWidth = widths[index];
              }
            });
          });
        }
      }
    });
    // Aplicar mejoras visuales
    if (window.tableEnhancements && window.tableEnhancements.enhance) {
      window.tableEnhancements.enhance('aiOverviewTable');
    }
  }

  // Listeners para iconos SERP
  setupTableEventListenersAIO();
}

// Nueva función para crear filas con la misma estructura visual que Keywords
function createResultRowAIO(result) {
  const aiAnalysis = result.ai_analysis || {};
  const isDomainInAI = aiAnalysis.domain_is_ai_source || false;
  const hasAIOverview = aiAnalysis.has_ai_overview || false;
  const organicPosition = (result.site_position !== null && result.site_position !== undefined)
    ? result.site_position
    : 'Not found';
  const aiPosition = (aiAnalysis.domain_ai_source_position !== null && aiAnalysis.domain_ai_source_position !== undefined)
    ? aiAnalysis.domain_ai_source_position
    : 'No';

  return `
    <tr>
      <td class="dt-body-center">
        <i class="fas fa-search serp-icon"
           data-keyword="${escapeHtml(result.keyword)}"
           data-url="${escapeHtml(result.url || '')}"
           title="View SERP for ${escapeHtml(result.keyword)}"
           style="cursor:pointer;"></i>
      </td>
      <td class="dt-body-left kw-cell">${escapeHtml(result.keyword || 'N/A')}</td>
      <td>${hasAIOverview ? '<span class="negative-change">Yes</span>' : '<span class="positive-change">No</span>'}</td>
      <td>${typeof organicPosition === 'number' ? (organicPosition === 0 ? '#0 (Featured)' : `#${organicPosition}`) : `${organicPosition}`}</td>
      <td>${isDomainInAI ? '<span class="positive-change">Yes</span>' : '<span class="negative-change">No</span>'}</td>
      <td>${(typeof aiPosition === 'number' && aiPosition > 0) ? `#${aiPosition}` : 'No'}</td>
    </tr>
  `;
}

// Listeners para la nueva tabla (iconos SERP)
function setupTableEventListenersAIO() {
  document.querySelectorAll('#aiOverviewTable .serp-icon').forEach(icon => {
    icon.addEventListener('click', () => openSerpModal(icon.dataset.keyword, icon.dataset.url));
    icon.addEventListener('mouseenter', () => icon.classList.add('hover'));
    icon.addEventListener('mouseleave', () => icon.classList.remove('hover'));
  });
}
