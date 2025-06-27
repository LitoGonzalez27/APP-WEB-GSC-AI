// utils.js - SISTEMA DE TEMA CENTRALIZADO
export const elems = {
  toggleBtn: document.getElementById('toggleModeBtn'), // Cambiado para usar el del navbar
  loader: document.getElementById('loader'),
  form: document.getElementById('urlForm'),
  siteUrlSelect: document.getElementById('siteUrlSelect'),
  urlsInput: document.getElementById('urlsInput'), // ✅ NUEVO: Campo de URLs
  monthChipsDiv: document.getElementById('monthChips'),
  matchType: document.getElementById('matchType'),
  downloadExcelBtn: document.getElementById('downloadExcelBtn'),
  
  insightsSection: document.getElementById('insightsSection'),
  performanceSection: document.getElementById('performanceSection'),
  keywordsSection: document.getElementById('keywordsSection'),
  resultsSection: document.getElementById('resultsSection'),
  
  keywordComparisonTableTitle: document.getElementById('keywordComparisonTableTitle'),
  keywordComparisonTable: document.getElementById('keywordComparisonTable'),
  keywordComparisonTableBody: document.querySelector('#keywordComparisonTable tbody'),

  downloadBlock: document.getElementById('downloadBlock'),
  
  insightsTitle: document.getElementById('insightsTitle'),
  performanceTitle: document.getElementById('performanceTitle'),
  keywordsTitle: document.getElementById('keywordsTitle'),
  resultsTitle: document.getElementById('resultsTitle'),

  summaryBlock: document.getElementById('summaryBlock'),
  disclaimerBlock: document.getElementById('summaryDisclaimer'),
  chartsBlock: document.getElementById('chartsBlock'),
  resultsBlock: document.getElementById('resultsBlock'),
  
  keywordOverviewDiv: document.getElementById('keyword-overview'),
  keywordCategoryDiv: document.getElementById('keyword-category-cards'),
  
  tableBody: document.querySelector('#tableBodyResults'), 

  // ELEMENTOS PARA AI OVERVIEW
  aiOverviewSection: document.getElementById('aiOverviewSection'),
  aiOverviewTitle: document.getElementById('aiOverviewTitle'),
  aiAnalysisMessage: document.getElementById('aiAnalysisMessage'),
  aiOverviewResultsContainer: document.getElementById('aiOverviewResultsContainer'),

  // NUEVOS ELEMENTOS STICKY
  stickyActions: document.getElementById('stickyActions'),
  stickyDownloadBtn: document.getElementById('stickyDownloadBtn'),
  stickyAIBtn: document.getElementById('stickyAIBtn'),

  // ELEMENTOS DEL NAVBAR
  themeIcon: document.getElementById('themeIcon'),
  navbar: document.getElementById('navbar'),
};

export const storage = {
  get darkMode() { return localStorage.getItem('darkMode') === 'true'; },
  set darkMode(v) { localStorage.setItem('darkMode', v); },
  get urls() { return localStorage.getItem('saved_urls') || ''; },
  set urls(v) { localStorage.setItem('saved_urls', v); },
  get matchType() { return localStorage.getItem('saved_match_type') || 'contains'; },
  set matchType(v) { localStorage.setItem('saved_match_type', v); },
  get siteUrl() { return localStorage.getItem('saved_site_url') || ''; },
  set siteUrl(v) { localStorage.setItem('saved_site_url', v); },
};

// ✅ FUNCIÓN CENTRALIZADA DE TEMA MEJORADA
export function initTheme() {
  // Aplicar tema guardado al cargar
  if (storage.darkMode) {
    document.body.classList.add('dark-mode');
    updateThemeIcon(true);
  }

  // ✅ CORREGIDO: No agregar event listener aquí, dejar que navbar lo maneje
  // Solo verificar que el navbar esté configurado
  console.log('🎨 Sistema de tema inicializado, esperando navbar...');
  
  // Integración con el nuevo navbar si existe
  if (window.navbarToggleTheme) {
    console.log('🔗 Navbar integrado con sistema de tema');
  }
}

// ✅ NUEVA FUNCIÓN PARA CAMBIAR TEMA
export function toggleTheme() {
  const isDark = document.body.classList.toggle('dark-mode');
  storage.darkMode = isDark;
  updateThemeIcon(isDark);
  
  // Disparar evento personalizado para que otros componentes escuchen
  window.dispatchEvent(new CustomEvent('themeChanged', { 
    detail: { isDark } 
  }));
  
  console.log('Theme changed to:', isDark ? 'dark' : 'light');
}

// ✅ FUNCIÓN PARA ACTUALIZAR ICONO (COMPATIBLE CON NAVBAR)
export function updateThemeIcon(isDark = null) {
  // Si no se especifica, detectar del DOM
  if (isDark === null) {
    isDark = document.body.classList.contains('dark-mode');
  }
  
  // ✅ CORREGIDO: Obtener iconos directamente del DOM en lugar de usar elems cache
  const themeIcon = document.getElementById('themeIcon');
  const mobileThemeIcon = document.getElementById('mobileThemeIcon');
  const toggleBtn = document.getElementById('toggleModeBtn');
  const mobileThemeText = document.getElementById('mobileThemeText');
  
  const iconClass = isDark ? 'fa-sun' : 'fa-moon';
  const themeText = isDark ? 'Modo Claro' : 'Modo Oscuro';
  
  // Actualizar icono desktop con animación
  if (themeIcon) {
    themeIcon.style.transform = 'scale(0)';
    setTimeout(() => {
      themeIcon.className = `fas ${iconClass}`;
      themeIcon.style.transform = 'scale(1)';
    }, 150);
  }
  
  // Actualizar icono móvil
  if (mobileThemeIcon) {
    mobileThemeIcon.className = `fas ${iconClass}`;
  }
  
  // Actualizar texto móvil
  if (mobileThemeText) {
    mobileThemeText.textContent = themeText;
  }
  
  // Actualizar aria-label
  if (toggleBtn) {
    toggleBtn.setAttribute('aria-label', `Cambiar a ${themeText.toLowerCase()}`);
    toggleBtn.setAttribute('aria-pressed', isDark.toString());
  }
}

// ✅ FUNCIÓN PARA CAMBIAR TEMA PROGRAMÁTICAMENTE
export function setTheme(isDark) {
  if (isDark) {
    document.body.classList.add('dark-mode');
  } else {
    document.body.classList.remove('dark-mode');
  }
  storage.darkMode = isDark;
  updateThemeIcon(isDark);
  
  // Disparar evento
  window.dispatchEvent(new CustomEvent('themeChanged', { 
    detail: { isDark } 
  }));
}

// ✅ FUNCIÓN PARA OBTENER ESTADO ACTUAL DEL TEMA
export function getCurrentTheme() {
  return {
    isDark: document.body.classList.contains('dark-mode'),
    stored: storage.darkMode
  };
}