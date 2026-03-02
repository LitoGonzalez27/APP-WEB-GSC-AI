/**
 * MEJORAS PARA TABLAS EXISTENTES - VERSIÓN CORREGIDA
 * ui-table-enhancements.js
 */

// ✅ FUNCIÓN para aplicar clases de estado a las filas
function applyRowStateClasses(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  
  const rows = table.querySelectorAll('tbody tr');
  
  rows.forEach(row => {
    // Reset existing classes
    row.classList.remove('row-improved', 'row-declined', 'row-highlighted');
    
    // Find change indicators in the row
    const changeElements = row.querySelectorAll('.positive-change, .negative-change');
    let hasPositive = false;
    let hasNegative = false;
    
    changeElements.forEach(el => {
      if (el.classList.contains('positive-change')) hasPositive = true;
      if (el.classList.contains('negative-change')) hasNegative = true;
    });
    
    // Apply state classes
    if (hasPositive && !hasNegative) {
      row.classList.add('row-improved');
    } else if (hasNegative && !hasPositive) {
      row.classList.add('row-declined');
    } else if (hasPositive && hasNegative) {
      row.classList.add('row-highlighted'); // Mixed results
    }
    
    // Special highlighting for top keywords (position 1-3)
    const cells = row.querySelectorAll('td');
    cells.forEach((cell, index) => {
      const text = cell.textContent.trim();
      // Si es una celda de posición y el valor es 1-3
      if (text && !isNaN(text) && parseFloat(text) <= 3) {
        row.classList.add('row-highlighted');
      }
    });
  });
}

// ✅ FUNCIÓN para mejorar los iconos SERP existentes
function enhanceSerpIcons(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  
  const serpIcons = table.querySelectorAll('.serp-icon');
  
  serpIcons.forEach(icon => {
    // Añadir clases modernas si no las tiene
    if (!icon.classList.contains('enhanced')) {
      icon.classList.add('enhanced');
      
      // Mejorar el tooltip
      const keyword = icon.dataset.keyword;
      const url = icon.dataset.url;
      
      if (keyword) {
        icon.title = `View SERP for "${keyword}"${url ? ` on ${url}` : ''}`;
      }
      
      // Añadir efectos de hover mejorados
      icon.addEventListener('mouseenter', () => {
        icon.style.transform = 'scale(1.1)';
      });
      
      icon.addEventListener('mouseleave', () => {
        icon.style.transform = 'scale(1)';
      });
    }
  });
}

// ✅ FUNCIÓN para mejorar las celdas de URL
function enhanceUrlCells(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  
  const urlCells = table.querySelectorAll('.scrollable-url-cell, .url-cell');
  
  urlCells.forEach(cell => {
    const url = cell.textContent.trim();
    
    // Añadir el URL completo como atributo para tooltips
    if (url && !cell.hasAttribute('title')) {
      cell.setAttribute('title', url);
    }
    
    // Añadir data attribute para el URL completo
    if (url && !cell.hasAttribute('data-full-url')) {
      cell.setAttribute('data-full-url', url);
    }
    
    // Hacer la URL clicable si no lo es ya
    if (!cell.querySelector('a') && url.startsWith('http')) {
      const link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = url;
      link.style.color = 'inherit';
      link.style.textDecoration = 'none';
      
      cell.innerHTML = '';
      cell.appendChild(link);
    }
  });
}

// ✅ FUNCIÓN para añadir loading state a las tablas
function setTableLoadingState(tableId, isLoading = true) {
  const wrapper = document.querySelector(`#${tableId}`).closest('.dataTables_wrapper');
  if (!wrapper) return;
  
  if (isLoading) {
    wrapper.classList.add('loading');
  } else {
    wrapper.classList.remove('loading');
  }
}

// ✅ FUNCIÓN para mejorar la paginación
function enhancePagination(tableId) {
  const wrapper = document.querySelector(`#${tableId}`).closest('.dataTables_wrapper');
  if (!wrapper) return;
  
  // Añadir clases modernas a los botones de paginación
  const paginateButtons = wrapper.querySelectorAll('.dataTables_paginate .paginate_button');
  
  paginateButtons.forEach(button => {
    if (!button.classList.contains('enhanced')) {
      button.classList.add('enhanced');
      
      // Mejorar accesibilidad
      button.setAttribute('role', 'button');
      
      if (button.classList.contains('current')) {
        button.setAttribute('aria-current', 'page');
      }
    }
  });
}

// ✅ FUNCIÓN para formatear números grandes
function formatLargeNumbers() {
  const tables = document.querySelectorAll('#resultsTable');
  
  tables.forEach(table => {
    const cells = table.querySelectorAll('tbody td');
    
    cells.forEach(cell => {
      const text = cell.textContent.trim();
      const number = parseInt(text.replace(/,/g, ''));
      
      // Si es un número grande, asegurar formato con comas
      if (!isNaN(number) && number >= 1000) {
        const formatted = number.toLocaleString('es-ES');
        if (text !== formatted) {
          cell.textContent = formatted;
        }
      }
    });
  });
}

// ✅ FUNCIÓN para mejorar los filtros de búsqueda
function enhanceTableSearch(tableId) {
  const wrapper = document.querySelector(`#${tableId}`).closest('.dataTables_wrapper');
  if (!wrapper) return;
  
  const searchInput = wrapper.querySelector('.dataTables_filter input');
  
  if (searchInput && !searchInput.classList.contains('enhanced')) {
    searchInput.classList.add('enhanced');
    
    // Mejorar placeholder
    searchInput.placeholder = 'Buscar en la tabla...';
    
    // Añadir atributos de accesibilidad
    searchInput.setAttribute('aria-label', 'Buscar en la tabla');
    
    // Mejorar el comportamiento del input
    let searchTimeout;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        // Aplicar mejoras después de cada búsqueda
        setTimeout(() => {
          applyRowStateClasses(tableId);
          enhanceSerpIcons(tableId);
        }, 100);
      }, 300);
    });
  }
}

// ✅ FUNCIÓN principal para aplicar todas las mejoras
function enhanceTable(tableId) {
  console.log(`🎨 Aplicando mejoras modernas a tabla: ${tableId}`);
  
  // Esperar a que DataTable esté inicializado
  const checkDataTable = () => {
    const table = document.getElementById(tableId);
    if (table && typeof $ !== 'undefined' && $.fn.DataTable && $.fn.DataTable.isDataTable(`#${tableId}`)) {
      // Aplicar mejoras
      applyRowStateClasses(tableId);
      enhanceSerpIcons(tableId);
      enhanceUrlCells(tableId);
      enhancePagination(tableId);
      enhanceTableSearch(tableId);
      formatLargeNumbers();
      
      console.log(`✅ Mejoras aplicadas a tabla: ${tableId}`);
      return true;
    }
    return false;
  };
  
  // Intentar inmediatamente
  if (!checkDataTable()) {
    // Si no está listo, intentar después de un breve delay
    setTimeout(() => {
      if (!checkDataTable()) {
        // Último intento después de más tiempo
        setTimeout(checkDataTable, 500);
      }
    }, 100);
  }
}

// ✅ FUNCIÓN para aplicar mejoras después de cada redraw de DataTable
function setupTableRedrawEnhancements(tableId) {
  const table = $(`#${tableId}`);
  
  if (table.length && typeof $ !== 'undefined' && $.fn.DataTable.isDataTable(table)) {
    table.on('draw.dt', () => {
      // Aplicar mejoras después de cada redraw
      setTimeout(() => {
        applyRowStateClasses(tableId);
        enhanceSerpIcons(tableId);
        enhanceUrlCells(tableId);
        formatLargeNumbers();
      }, 50);
    });
    
    console.log(`🔄 Auto-mejoras configuradas para tabla: ${tableId}`);
  }
}

// ✅ FUNCIÓN para mejorar también la tabla de URLs (resultsTable)
function enhanceResultsTable() {
  // Aplicar mejoras a la tabla de URLs cuando esté disponible
  const checkResultsTable = () => {
    if (document.getElementById('resultsTable')) {
      enhanceTable('resultsTable');
      setupTableRedrawEnhancements('resultsTable');
      return true;
    }
    return false;
  };
  
  if (!checkResultsTable()) {
    // Observar cambios en el DOM para detectar cuando la tabla se carga
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1 && (node.id === 'resultsTable' || node.querySelector('#resultsTable'))) {
              setTimeout(() => {
                if (checkResultsTable()) {
                  observer.disconnect();
                }
              }, 100);
            }
          });
        }
      });
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    
    // Desconectar el observer después de 10 segundos para evitar memory leaks
    setTimeout(() => observer.disconnect(), 10000);
  }
}

// ✅ FUNCIÓN utilitaria para debugging
function debugTableEnhancements(tableId) {
  const table = document.getElementById(tableId);
  if (!table) {
    console.warn(`Tabla ${tableId} no encontrada`);
    return;
  }
  
  const wrapper = table.closest('.dataTables_wrapper');
  const isDataTable = typeof $ !== 'undefined' && $.fn.DataTable && $.fn.DataTable.isDataTable(`#${tableId}`);
  
  console.log(`=== DEBUG TABLA ${tableId} ===`);
  console.log('Tabla existe:', !!table);
  console.log('Wrapper existe:', !!wrapper);
  console.log('Es DataTable:', isDataTable);
  console.log('Filas en tbody:', table.querySelectorAll('tbody tr').length);
  console.log('Iconos SERP:', table.querySelectorAll('.serp-icon').length);
  console.log('Celdas URL:', table.querySelectorAll('.scrollable-url-cell, .url-cell').length);
  console.log('Cambios positivos:', table.querySelectorAll('.positive-change').length);
  console.log('Cambios negativos:', table.querySelectorAll('.negative-change').length);
  console.log('===========================');
}

// ✅ HACER FUNCIONES DISPONIBLES GLOBALMENTE PARA DEBUGGING
if (typeof window !== 'undefined') {
  window.tableEnhancements = {
    enhance: enhanceTable,
    applyStates: applyRowStateClasses,
    enhanceSerp: enhanceSerpIcons,
    enhanceUrls: enhanceUrlCells,
    debug: debugTableEnhancements,
    setLoading: setTableLoadingState
  };
}

// ✅ AUTO-INICIALIZACIÓN cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  // Aplicar mejoras a tablas existentes después de un breve delay
  setTimeout(() => {
    enhanceResultsTable();
    
    // Si las tablas ya existen, mejorarlas
    ['resultsTable'].forEach(tableId => {
      if (document.getElementById(tableId)) {
        enhanceTable(tableId);
      }
    });
  }, 1000);
});

// ✅ EXPORTAR FUNCIONES (SIN DUPLICADOS)
export {
  enhanceTable,
  setupTableRedrawEnhancements,
  applyRowStateClasses,
  enhanceSerpIcons,
  enhanceUrlCells,
  setTableLoadingState,
  enhancePagination,
  enhanceTableSearch,
  formatLargeNumbers,
  enhanceResultsTable,
  debugTableEnhancements
};
