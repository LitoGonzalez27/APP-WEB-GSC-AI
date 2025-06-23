// ui-keyword-comparison-table.js — CÓDIGO CORREGIDO (reemplaza completamente el archivo existente)

import { elems } from './utils.js';
import { openSerpModal } from './ui-serp-modal.js';
import { enhanceTable, setupTableRedrawEnhancements } from './ui-table-enhancements.js';


let keywordComparisonDataTable = null;

function escapeHtml(unsafe) {
  if (!unsafe) return '';
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatPercentageChange(value, isCTR = false) {
  if (value === "Infinity") return '+∞%';
  if (value === "-Infinity") return '-∞%';
  if (value === "New") return '<span class="positive-change">New</span>';
  if (value === "Lost") return '<span class="negative-change">Lost</span>';
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
  if (delta === 'New')   return '<span class="positive-change">New</span>';
  if (delta === 'Lost')  return '<span class="negative-change">Lost</span>';
  if (typeof delta === 'number' && isFinite(delta)) {
    if (delta > 0) return `+${delta.toFixed(1)}`;
    if (delta < 0) return delta.toFixed(1);
    return '0.0';
  }
  if (pos1 == null && pos2 == null) return 'N/A';
  return pos1 === pos2 ? '0.0' : 'N/A';
}

// ✅ FUNCIÓN para determinar el tipo de análisis
function getAnalysisType(keywordData) {
  if (!keywordData || keywordData.length === 0) return 'empty';
  
  // Verificar si hay datos de comparación reales
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

export function renderKeywordComparisonTable(keywordData, periods = null) {
  if (!elems.keywordComparisonTableBody) return;

  if (keywordComparisonDataTable) {
    keywordComparisonDataTable.destroy();
    keywordComparisonDataTable = null;
  }

  elems.keywordComparisonTableBody.innerHTML = '';

  // ✅ Determinar tipo de análisis
  const analysisType = getAnalysisType(keywordData);
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
        (row.delta_position_absolute === 'New' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute > 0))
          ? 'positive-change'
          : (row.delta_position_absolute === 'Lost' || (typeof row.delta_position_absolute === 'number' && row.delta_position_absolute < 0))
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
             data-keyword="${escapeHtml(row.keyword)}"
             data-url="${escapeHtml(row.url || '')}"
             title="Ver SERP para ${escapeHtml(row.keyword)}"
             style="cursor:pointer;"></i>
        </td>
        <td class="dt-body-left kw-cell">${escapeHtml(row.keyword || 'N/A')}</td>
        <td>${(row.clicks_m1 ?? 0).toLocaleString('es-ES')}</td>
        <td ${p2ColumnsStyle}>${(row.clicks_m2 ?? 0).toLocaleString('es-ES')}</td>
        <td class="${deltaClicksClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_clicks_percent)}</td>
        <td>${(row.impressions_m1 ?? 0).toLocaleString('es-ES')}</td>
        <td ${p2ColumnsStyle}>${(row.impressions_m2 ?? 0).toLocaleString('es-ES')}</td>
        <td class="${deltaImprClass}" ${deltaColumnsStyle}>${formatPercentageChange(row.delta_impressions_percent)}</td>
        <td>${typeof row.ctr_m1 === 'number' ? row.ctr_m1.toFixed(2) + '%' : 'N/A'}</td>
        <td ${p2ColumnsStyle}>${typeof row.ctr_m2 === 'number' ? row.ctr_m2.toFixed(2) + '%' : 'N/A'}</td>
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

    // ✅ Configuración de DataTable adaptada
    const columnDefs = [
      { targets: '_all', className: 'dt-body-right' },
      { targets: [0,1], className: 'dt-body-left' },
      { targets: 0, orderable: false },
      // Orden personalizado para cada columna relevante
      { targets: [2,3], type: 'thousands-separated' }, // ✅ CORREGIDO: Clicks M1 y M2 con separadores de miles
      { targets: [4], type: 'delta-custom' }, // ΔClicks (%)
      { targets: [5,6], type: 'thousands-separated' }, // ✅ CORREGIDO: Impressions M1 y M2 con separadores de miles
      { targets: [7], type: 'delta-custom' }, // ΔImp. (%)
      { targets: [8,9], type: 'percent-custom' }, // CTR M1 y M2
      { targets: [10], type: 'delta-custom' }, // ΔCTR (%)
      { targets: [11,12], type: 'position-custom' }, // Pos M1 y M2
      { targets: [13], type: 'delta-custom' } // ΔPos
    ];

    // ✅ Ocultar columnas para período único
    if (analysisType === 'single') {
      columnDefs.push(
        { targets: [3, 4, 6, 7, 9, 10, 12, 13], visible: false }  // Ocultar P2 y Delta
      );
    }

    keywordComparisonDataTable = new DataTable(elems.keywordComparisonTable, {
      pageLength: 10,
      lengthMenu: [10, 25, 50, 100, -1],
      language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
      scrollX: true,
      responsive: false,
      columnDefs: columnDefs,
      order: [[2, 'desc']], // ✅ CORREGIDO: Siempre ordenar por clicks_m1 (columna 2)
      drawCallback: () => {
        if (window.jQuery && window.jQuery.fn.tooltip) window.jQuery('[data-toggle="tooltip"]').tooltip();
      }
    });
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