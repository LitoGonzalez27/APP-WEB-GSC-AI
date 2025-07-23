// ui-keyword-comparison-table.js — CÓDIGO CORREGIDO (reemplaza completamente el archivo existente)

import { elems } from './utils.js';
import { openSerpModal } from './ui-serp-modal.js';
import { enhanceTable, setupTableRedrawEnhancements } from './ui-table-enhancements.js';
import { 
  formatInteger, 
  formatPercentage, 
  formatPosition, 
  formatPercentageChange, 
  formatPositionDelta,
  getStandardKeywordTableConfig,
  registerDataTableSortingTypes,
  escapeHtml as escapeHtmlUtil
} from './number-utils.js';


let keywordComparisonDataTable = null;

// ✅ REMOVIDO: Funciones duplicadas - ahora se usan las del módulo centralizado number-utils.js

// ✅ FUNCIÓN para determinar el tipo de análisis
function getAnalysisType(keywordData, periods = null) {
  if (!keywordData || keywordData.length === 0) return 'empty';
  
  // ✅ CORREGIDO: Primero verificar si el usuario seleccionó comparación
  if (periods && periods.has_comparison && periods.comparison) {
    console.log('🔍 Usuario seleccionó comparación explícitamente para keywords - forzando modo comparison');
    return 'comparison';
  }
  
  // Verificar si hay datos de comparación reales (lógica original)
  const hasComparison = keywordData.some(row => 
    (row.clicks_m2 > 0 || row.impressions_m2 > 0) && 
    row.delta_clicks_percent !== 'New'
  );
  
  return hasComparison ? 'comparison' : 'single';
}

// ✅ FUNCIÓN para actualizar headers de tabla según el tipo
function updateTableHeaders(analysisType) {
  const table = document.getElementById('keywordComparisonTable');
  if (!table) return;
  
  const headers = table.querySelectorAll('thead th');
  
  if (analysisType === 'single') {
    // Headers para período único
    if (headers[2]) headers[2].textContent = 'Clicks';
    if (headers[3]) headers[3].style.display = 'none'; // Ocultar P2
    if (headers[4]) headers[4].style.display = 'none'; // Ocultar Delta
    if (headers[5]) headers[5].textContent = 'Impressions P1';
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

// ✅ REMOVIDO: Funciones de parsing duplicadas - ahora se usan las del módulo centralizado

export function renderKeywordComparisonTable(keywordData, periods = null) {
  if (!elems.keywordComparisonTableBody) return;

  if (keywordComparisonDataTable) {
    keywordComparisonDataTable.destroy();
    keywordComparisonDataTable = null;
  }

  elems.keywordComparisonTableBody.innerHTML = '';

  // ✅ Determinar tipo de análisis
  const analysisType = getAnalysisType(keywordData, periods);
  console.log(`📊 Tipo de análisis: ${analysisType}, Keywords: ${keywordData ? keywordData.length : 0}`);

  if (!keywordData || keywordData.length === 0) {
    elems.keywordComparisonTableBody.innerHTML =
      `<tr><td colspan="14">No keyword data for the selected URLs and period.</td></tr>`;
  } else {
    // ✅ Actualizar headers según el tipo
    updateTableHeaders(analysisType);

    keywordData.forEach(row => {
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
        (row.delta_position_absolute === 'New' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute < 0))
          ? 'positive-change'
          : (row.delta_position_absolute === 'Lost' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute > 0))
            ? 'negative-change'
            : '';

      const tr = document.createElement('tr');
      
      // ✅ CORREGIDO: Ajustar visibilidad de columnas según el tipo
      const p2ColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';
      const deltaColumnsStyle = analysisType === 'single' ? 'style="display: none;"' : '';

      // ✅ CORREGIDO: Para período único, usar siempre _m1 (que contiene los datos reales)
      // Para comparación, usar _m1 para período actual y _m2 para período de comparación
      tr.innerHTML = `
        <td class="dt-body-center">
          <i class="fas fa-search serp-icon"
             data-keyword="${escapeHtmlUtil(row.keyword)}"
             data-url="${escapeHtmlUtil(row.url || '')}"
             title="Ver SERP para ${escapeHtmlUtil(row.keyword)}"
             style="cursor:pointer;"></i>
        </td>
        <td class="dt-body-left kw-cell">${escapeHtmlUtil(row.keyword || 'N/A')}</td>
        <td>${formatInteger(row.clicks_m1 ?? 0)}</td>
        <td ${p2ColumnsStyle}>${formatInteger(row.clicks_m2 ?? 0)}</td>
        <td class="${deltaClicksClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_clicks_percent)}</td>
        <td>${formatInteger(row.impressions_m1 ?? 0)}</td>
        <td ${p2ColumnsStyle}>${formatInteger(row.impressions_m2 ?? 0)}</td>
        <td class="${deltaImprClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_impressions_percent)}</td>
        <td>${formatPercentage(row.ctr_m1)}</td>
        <td ${p2ColumnsStyle}>${formatPercentage(row.ctr_m2)}</td>
        <td class="${deltaCtrClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_ctr_percent, true)}</td>
        <td>${formatPosition(row.position_m1)}</td>
        <td ${p2ColumnsStyle}>${formatPosition(row.position_m2)}</td>
        <td class="${deltaPosClass}" ${deltaColumnsStyle}>${formatPositionDelta(row.delta_position_absolute, row.position_m1, row.position_m2)}</td>
      `;
      
      elems.keywordComparisonTableBody.appendChild(tr);

      const icon = tr.querySelector('.serp-icon');
      if (icon) {
        icon.addEventListener('click', () => openSerpModal(icon.dataset.keyword, icon.dataset.url));
        icon.addEventListener('mouseenter', () => icon.classList.add('hover'));
        icon.addEventListener('mouseleave', () => icon.classList.remove('hover'));
      }
    });

    // ✅ ACTUALIZADO: Usar configuración estandarizada del módulo centralizado
    registerDataTableSortingTypes(); // Asegurar que los tipos estén registrados
    const dtConfig = getStandardKeywordTableConfig(analysisType);
    keywordComparisonDataTable = new DataTable(elems.keywordComparisonTable, dtConfig);
  }

  if (elems.keywordComparisonTableTitle) {
    elems.keywordComparisonTableTitle.style.display = 'block';
    
    // ✅ Actualizar título según el tipo
    if (analysisType === 'single') {
      elems.keywordComparisonTableTitle.textContent = 'Keyword Comparison Between Periods';
    } else {
      elems.keywordComparisonTableTitle.textContent = 'Comparación de Keywords entre Períodos';
    }
  }
}

export function clearKeywordComparisonTable() {
  if (keywordComparisonDataTable) {
    keywordComparisonDataTable.destroy();
    keywordComparisonDataTable = null;
  }
  if (elems.keywordComparisonTableBody) elems.keywordComparisonTableBody.innerHTML = '';
}