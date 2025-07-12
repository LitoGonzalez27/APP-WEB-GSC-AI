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

  // Mostrar resumen
  displaySummary(data.summary, resultsContainer);
  
  // Mostrar resultados detallados
  displayDetailedResults(data.keywordResults, resultsContainer);
  
  showToast('AI Overview analysis complete', 'success');
}

function displaySummary(summary, container) {
  // Calcular % de visibilidad en AIO
  const keywordsWithAIO = summary.keywords_with_ai_overview || 0;
  const mentionsInAIO = summary.keywords_as_ai_source || 0;
  const totalKeywords = summary.total_keywords_analyzed || 0;
  const visibilityPercentage = keywordsWithAIO > 0 ? ((mentionsInAIO / keywordsWithAIO) * 100).toFixed(1) : '0.0';
  
  // Calcular peso AIO en SERPs
  const pesoAIOPercentage = totalKeywords > 0 ? ((keywordsWithAIO / totalKeywords) * 100).toFixed(1) : '0.0';
  
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
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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
        <p>No se encontraron resultados detallados para mostrar.</p>
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
           title="Ver SERP para ${escapeHtml(result.keyword)}"
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
