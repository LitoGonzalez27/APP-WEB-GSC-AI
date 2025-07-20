/**
 * ✅ MÓDULO CENTRALIZADO PARA FORMATEO Y PARSING DE NÚMEROS
 * ====================================================================
 * Este módulo estandariza el manejo de números en toda la aplicación:
 * - Puntos (.) como separadores de miles
 * - Comas (,) como separadores decimales
 * - Formateo consistente para diferentes tipos de datos
 * - Parsing correcto para ordenamiento en DataTables
 */

// === CONSTANTES DE FORMATEO ===
const ES_LOCALE = 'es-ES';
const ES_FORMAT_OPTIONS = {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0
};

const ES_DECIMAL_FORMAT_OPTIONS = {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
};

// === FUNCIONES DE FORMATEO ===

/**
 * Formatea un número entero usando el formato español (punto para miles)
 * @param {number|string} value - Valor a formatear
 * @returns {string} - Número formateado (ej: "14.789")
 */
export function formatInteger(value) {
  if (value == null || value === '' || isNaN(value)) return '0';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '0';
  
  // Formateo manual para español: punto como separador de miles
  const rounded = Math.round(num);
  return rounded.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/**
 * Formatea un número decimal usando el formato español (punto para miles, coma para decimales)
 * @param {number|string} value - Valor a formatear
 * @param {number} decimals - Número de decimales (default: 2)
 * @returns {string} - Número formateado (ej: "14.789,50")
 */
export function formatDecimal(value, decimals = 2) {
  if (value == null || value === '' || isNaN(value)) return '0,00';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '0,00';
  
  const options = {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  };
  
  return num.toLocaleString(ES_LOCALE, options);
}

/**
 * Formatea un porcentaje usando el formato español
 * @param {number|string} value - Valor a formatear (ya en formato porcentaje, ej: 5.67 para 5.67%)
 * @param {number} decimals - Número de decimales (default: 2)
 * @returns {string} - Porcentaje formateado (ej: "5,67%")
 */
export function formatPercentage(value, decimals = 2) {
  if (value == null || value === '' || isNaN(value)) return '0,00%';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '0,00%';
  
  return formatDecimal(num, decimals) + '%';
}

/**
 * Formatea CTR desde decimal a porcentaje (multiplica por 100)
 * @param {number|string} value - Valor CTR en decimal (ej: 0.0567 para 5.67%)
 * @param {number} decimals - Número de decimales (default: 2)
 * @returns {string} - CTR formateado (ej: "5,67%")
 */
export function formatCTR(value, decimals = 2) {
  if (value == null || value === '' || isNaN(value)) return '0,00%';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '0,00%';
  
  const percentage = num * 100;
  return formatDecimal(percentage, decimals) + '%';
}

/**
 * Formatea posición con un decimal
 * @param {number|string} value - Valor de posición
 * @returns {string} - Posición formateada (ej: "5,2")
 */
export function formatPosition(value) {
  if (value == null || value === '' || isNaN(value)) return 'N/A';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return 'N/A';
  
  return formatDecimal(num, 1);
}

/**
 * Formatea cambios porcentuales con manejo de casos especiales
 * @param {number|string|'Infinity'|'New'|'Lost'} value - Valor del cambio
 * @param {boolean} isCTR - Si es un cambio de CTR (para formato específico)
 * @returns {string} - Cambio formateado
 */
export function formatPercentageChange(value, isCTR = false) {
  if (value === 'Infinity' || value === '+Inf') return '+∞%';
  if (value === '-Infinity' || value === '-Inf') return '-∞%';
  if (value === 'New' || value === 'Nuevo') return '<span class="positive-change">Nuevo</span>';
  if (value === 'Lost' || value === 'Perdido') return '<span class="negative-change">Perdido</span>';
  
  if (value == null || value === '' || isNaN(value)) return 'N/A';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return 'N/A';
  
  // Para CTR, usar 2 decimales; para otros, 1 decimal
  const decimals = isCTR ? 2 : 1;
  const formatted = formatDecimal(num, decimals) + '%';
  
  // Agregar signo positivo si es necesario
  if (num > 0) {
    return '+' + formatted;
  }
  
  return formatted;
}

/**
 * Formatea delta de posición con manejo de casos especiales
 * @param {number|string|'New'|'Lost'} deltaValue - Valor del delta
 * @param {number} posP1 - Posición P1
 * @param {number} posP2 - Posición P2
 * @returns {string} - Delta formateado
 */
export function formatPositionDelta(deltaValue, posP1, posP2) {
  if (deltaValue === 'New' || deltaValue === 'Nuevo') return '<span class="positive-change">Nuevo</span>';
  if (deltaValue === 'Lost' || deltaValue === 'Perdido') return '<span class="negative-change">Perdido</span>';
  
  if (deltaValue == null || deltaValue === '' || isNaN(deltaValue)) return 'N/A';
  const num = typeof deltaValue === 'string' ? parseFloat(deltaValue) : deltaValue;
  if (!isFinite(num)) return 'N/A';
  
  const formatted = formatDecimal(Math.abs(num), 1);
  
  // Para posición, delta negativo es bueno (subió en ranking)
  if (num < 0) {
    return '+' + formatted; // Subió posiciones
  } else if (num > 0) {
    return '-' + formatted; // Bajó posiciones
  } else {
    return '0,0'; // Sin cambio
  }
}

// === FUNCIONES DE PARSING PARA ORDENAMIENTO ===

/**
 * Parsea un valor para ordenamiento, manejando formato español
 * @param {string|number} val - Valor a parsear
 * @returns {number} - Valor numérico para ordenamiento
 */
export function parseNumericValue(val) {
  // Casos especiales
  if (val === 'Infinity' || val === '+∞' || val === '+∞%') return Infinity;
  if (val === '-Infinity' || val === '-∞' || val === '-∞%') return -Infinity;
  if (val === 'New' || val === 'Nuevo') return 0.00001; // Valor positivo pequeño
  if (val === 'Lost' || val === 'Perdido') return -0.00001; // Valor negativo pequeño
  if (val === 'N/A' || val === null || val === undefined || val === '') return 0;
  
  // Si ya es número, devolverlo
  if (typeof val === 'number') return val;
  
  // Limpiar string
  let cleaned = val.toString().trim();
  
  // Quitar símbolos comunes
  cleaned = cleaned.replace(/[%€$]/g, '');
  
  // Manejar formato español: punto para miles, coma para decimales
  if (cleaned.includes('.') && cleaned.includes(',')) {
    // Ambos presentes: determinar cuál es el separador decimal
    const lastDot = cleaned.lastIndexOf('.');
    const lastComma = cleaned.lastIndexOf(',');
    
    if (lastComma > lastDot) {
      // Coma es decimal: "1.234.567,89"
      cleaned = cleaned.replace(/\./g, '').replace(',', '.');
    } else {
      // Punto es decimal: "1,234,567.89" (formato no español, pero manejarlo)
      cleaned = cleaned.replace(/,/g, '');
    }
  } else if (cleaned.includes('.') && !cleaned.includes(',')) {
    // Solo puntos: determinar si son separadores de miles o decimales
    const parts = cleaned.split('.');
    if (parts.length === 2 && parts[1].length <= 2) {
      // Probablemente decimal: "123.45"
      // No hacer nada, ya está en formato correcto para parseFloat
    } else {
      // Probablemente separadores de miles: "123.456" o "1.234.567"
      cleaned = cleaned.replace(/\./g, '');
    }
  } else if (cleaned.includes(',') && !cleaned.includes('.')) {
    // Solo comas: en formato español, coma es decimal
    cleaned = cleaned.replace(',', '.');
  }
  
  const parsed = parseFloat(cleaned);
  return isNaN(parsed) ? 0 : parsed;
}

/**
 * Parsea específicamente números enteros con separadores de miles
 * @param {string|number} val - Valor a parsear
 * @returns {number} - Valor entero para ordenamiento
 */
export function parseIntegerValue(val) {
  if (typeof val === 'number') return Math.round(val);
  if (val == null || val === '') return 0;
  
  let cleaned = val.toString().trim();
  
  // Quitar separadores de miles (puntos en formato español)
  cleaned = cleaned.replace(/\./g, '');
  
  // Si tiene coma, es decimal - tomar solo la parte entera
  if (cleaned.includes(',')) {
    cleaned = cleaned.split(',')[0];
  }
  
  const parsed = parseInt(cleaned, 10);
  return isNaN(parsed) ? 0 : parsed;
}

// === CONFIGURACIÓN PARA DATATABLES ===

/**
 * Registra tipos de ordenamiento personalizados en DataTables
 */
export function registerDataTableSortingTypes() {
  if (!window.DataTable || !window.DataTable.ext || !window.DataTable.ext.type) {
    console.warn('DataTables no está disponible para registrar tipos de ordenamiento');
    return;
  }
  
  // Funciones de detección de tipo
  window.DataTable.ext.type.detect.unshift(function (data) {
    if (typeof data !== 'string') return null;
    
    // Detectar enteros con formato español (ej: "14.789")
    if (/^\d{1,3}(\.\d{3})*$/.test(data)) {
      return 'spanish-integer';
    }
    
    // Detectar decimales con formato español (ej: "14.789,50" o "5,67")
    if (/^\d{1,3}(\.\d{3})*,\d+$/.test(data) || /^\d+,\d+$/.test(data)) {
      return 'spanish-decimal';
    }
    
    // Detectar porcentajes (ej: "5,67%" o "15%")
    if (/^[+\-]?\d+([,\.]\d+)?%$/.test(data)) {
      return 'spanish-percentage';
    }
    
    // Detectar deltas (ej: "+15,5%" o "-8,2%" o "New" o "Lost")
    if (/^[+\-]\d+([,\.]\d+)?%$/.test(data) || data === 'New' || data === 'Lost' || data === 'Infinity') {
      return 'spanish-delta';
    }
    
    return null;
  });
  
  // Funciones de ordenamiento
  window.DataTable.ext.type.order['spanish-integer-pre'] = parseIntegerValue;
  window.DataTable.ext.type.order['spanish-decimal-pre'] = parseNumericValue;
  window.DataTable.ext.type.order['spanish-percentage-pre'] = parseNumericValue;
  window.DataTable.ext.type.order['spanish-delta-pre'] = parseNumericValue;
  
  // También registrar sin el sufijo -pre para compatibilidad
  window.DataTable.ext.type.order['spanish-integer'] = parseIntegerValue;
  window.DataTable.ext.type.order['spanish-decimal'] = parseNumericValue;
  window.DataTable.ext.type.order['spanish-percentage'] = parseNumericValue;
  window.DataTable.ext.type.order['spanish-delta'] = parseNumericValue;
  
  console.log('✅ Tipos de ordenamiento español registrados en DataTables');
}

// === CONFIGURACIÓN ESTÁNDAR DE DATATABLES ===

/**
 * Obtiene la configuración estándar para una tabla de URLs
 * @param {string} analysisType - Tipo de análisis ('single' o 'comparison')
 * @returns {Object} - Configuración de DataTables
 */
export function getStandardUrlTableConfig(analysisType = 'comparison') {
  const columnDefs = [
    { targets: '_all', className: 'dt-body-right' },
    { targets: [0, 1], className: 'dt-body-left' }, // Iconos y URL a la izquierda
    { targets: 0, orderable: false }, // No ordenar la columna de iconos
    // Configuración de tipos para ordenamiento correcto
    { targets: [2, 3], type: 'spanish-integer' }, // Clicks P1 y P2
    { targets: [4], type: 'spanish-delta' }, // ΔClicks (%)
    { targets: [5, 6], type: 'spanish-integer' }, // Impressions P1 y P2
    { targets: [7], type: 'spanish-delta' }, // ΔImp. (%)
    { targets: [8, 9], type: 'spanish-percentage' }, // CTR P1 y P2
    { targets: [10], type: 'spanish-delta' }, // ΔCTR (%)
    { targets: [11, 12], type: 'spanish-decimal' }, // Pos P1 y P2
    { targets: [13], type: 'spanish-delta' } // ΔPos
  ];

  // Ocultar columnas para período único
  if (analysisType === 'single') {
    columnDefs.push(
      { targets: [3, 4, 6, 7, 9, 10, 12, 13], visible: false }
    );
  }

  return {
    pageLength: 10,
    lengthMenu: [10, 25, 50, 100, -1],
    language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
    scrollX: true,
    responsive: false,
    columnDefs: columnDefs,
    order: [[2, 'desc']], // ✅ SIEMPRE ordenar por Clicks P1 descendente
    drawCallback: () => {
      if (window.jQuery && window.jQuery.fn.tooltip) {
        window.jQuery('[data-toggle="tooltip"]').tooltip();
      }
    },
    retrieve: false,
    destroy: false,
    stateSave: false,
    deferRender: true,
    processing: false
  };
}

/**
 * Obtiene la configuración estándar para una tabla de keywords
 * @param {string} analysisType - Tipo de análisis ('single' o 'comparison')
 * @returns {Object} - Configuración de DataTables
 */
export function getStandardKeywordTableConfig(analysisType = 'comparison') {
  const columnDefs = [
    { targets: '_all', className: 'dt-body-right' },
    { targets: [0, 1], className: 'dt-body-left' }, // SERP y keyword a la izquierda
    { targets: 0, orderable: false }, // No ordenar la columna de iconos SERP
    // Configuración de tipos para ordenamiento correcto
    { targets: [2, 3], type: 'spanish-integer' }, // Clicks M1 y M2
    { targets: [4], type: 'spanish-delta' }, // ΔClicks (%)
    { targets: [5, 6], type: 'spanish-integer' }, // Impressions M1 y M2
    { targets: [7], type: 'spanish-delta' }, // ΔImp. (%)
    { targets: [8, 9], type: 'spanish-percentage' }, // CTR M1 y M2
    { targets: [10], type: 'spanish-delta' }, // ΔCTR (%)
    { targets: [11, 12], type: 'spanish-decimal' }, // Pos M1 y M2
    { targets: [13], type: 'spanish-delta' } // ΔPos
  ];

  // Ocultar columnas para período único
  if (analysisType === 'single') {
    columnDefs.push(
      { targets: [3, 4, 6, 7, 9, 10, 12, 13], visible: false }
    );
  }

  return {
    pageLength: 10,
    lengthMenu: [10, 25, 50, 100, -1],
    language: { url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/en-GB.json' },
    scrollX: true,
    responsive: false,
    columnDefs: columnDefs,
    order: [[2, 'desc']], // ✅ SIEMPRE ordenar por Clicks M1 descendente
    drawCallback: () => {
      if (window.jQuery && window.jQuery.fn.tooltip) {
        window.jQuery('[data-toggle="tooltip"]').tooltip();
      }
    }
  };
}

// === FUNCIONES DE UTILIDAD ===

/**
 * Escapa HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string} - Texto escapado
 */
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Inicializa el módulo de números
 */
export function initializeNumberUtils() {
  registerDataTableSortingTypes();
  console.log('✅ Módulo de utilidades de números inicializado');
}

// Auto-inicialización cuando se carga el módulo
if (typeof window !== 'undefined') {
  // Esperar a que DataTables esté disponible
  if (window.DataTable) {
    registerDataTableSortingTypes();
  } else {
    // Intentar registrar cuando se cargue DataTables
    const checkDataTables = setInterval(() => {
      if (window.DataTable) {
        registerDataTableSortingTypes();
        clearInterval(checkDataTables);
      }
    }, 100);
    
    // Timeout después de 10 segundos
    setTimeout(() => {
      clearInterval(checkDataTables);
    }, 10000);
  }
} 