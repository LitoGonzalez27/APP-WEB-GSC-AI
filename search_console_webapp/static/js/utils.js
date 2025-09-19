// utils.js - SISTEMA DE TEMA CENTRALIZADO
export const elems = {
  toggleBtn: document.getElementById('toggleModeBtn'), // Cambiado para usar el del navbar
  loader: document.getElementById('loader'),
  form: document.getElementById('urlForm'),
  siteUrlSelect: document.getElementById('siteUrlSelect'),
  urlsInput: document.getElementById('urlsInput'), // ✅ NUEVO: Campo de URLs
  monthChipsDiv: document.getElementById('monthChips'),
  matchType: document.getElementById('matchType'),
  // downloadExcelBtn: document.getElementById('downloadExcelBtn'), // Eliminado - ahora está en el sidebar
  
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
  // stickyDownloadBtn: document.getElementById('stickyDownloadBtn'), // Eliminado - ahora está en el sidebar
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

// =============================================
// MOBILE DEVICE UTILITIES
// =============================================

/**
 * Detecta si el dispositivo es móvil usando múltiples métodos
 */
export function isMobileDevice() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
         window.innerWidth <= 768 ||
         'ontouchstart' in window ||
         navigator.maxTouchPoints > 0;
}

/**
 * Detecta el tipo específico de dispositivo
 */
export function getDeviceType() {
  const userAgent = navigator.userAgent;
  const width = window.innerWidth;
  
  if (/iPad/i.test(userAgent)) return 'tablet';
  if (/iPhone|iPod/i.test(userAgent)) return 'mobile';
  if (/Android/i.test(userAgent)) {
    return width > 768 ? 'tablet' : 'mobile';
  }
  if (width <= 480) return 'mobile-small';
  if (width <= 768) return 'mobile';
  if (width <= 1024) return 'tablet';
  return 'desktop';
}

/**
 * Configuración adaptativa de timeouts basada en dispositivo
 */
export function getAdaptiveTimeouts() {
  const device = getDeviceType();
  const isMobile = isMobileDevice();
  
  return {
    modal: {
      close: isMobile ? 4000 : 2500,
      animation: isMobile ? 500 : 300,
      retry: isMobile ? 1000 : 500
    },
    request: {
      timeout: isMobile ? 45000 : 30000,
      retry: isMobile ? 3 : 2
    },
    ui: {
      debounce: isMobile ? 300 : 150,
      throttle: isMobile ? 200 : 100
    }
  };
}

/**
 * Sistema de cierre robusto para modales en móviles
 */
export class MobileModalManager {
  constructor(modalId, options = {}) {
    this.modalId = modalId;
    this.options = {
      maxAttempts: isMobileDevice() ? 5 : 3,
      baseDelay: isMobileDevice() ? 4000 : 2500,
      forceClose: options.forceClose !== false,
      removeFromDOM: options.removeFromDOM === true,
      ...options
    };
    this.closeAttempt = 0;
  }
  
  close() {
    console.log(`🚪 Starting robust close for modal: ${this.modalId}`);
    this.closeAttempt = 0;
    this.attemptClose();
  }
  
  attemptClose() {
    this.closeAttempt++;
    const modal = document.getElementById(this.modalId);
    
    console.log(`🔄 Close attempt ${this.closeAttempt}/${this.options.maxAttempts} for ${this.modalId}`);
    
    if (!modal) {
      console.log(`❌ Modal ${this.modalId} not found`);
      this.finalizeCleanup();
      return;
    }
    
    const isVisible = modal.classList.contains('show') || 
                     getComputedStyle(modal).display !== 'none' ||
                     parseFloat(getComputedStyle(modal).opacity) > 0.1;
    
    if (!isVisible) {
      console.log(`✅ Modal ${this.modalId} already closed`);
      this.finalizeCleanup();
      return;
    }
    
    // Aplicar cierre optimizado para móviles
    if (isMobileDevice()) {
      modal.style.transition = 'none';
      modal.style.opacity = '0';
      modal.style.visibility = 'hidden';
      modal.style.pointerEvents = 'none';
    }
    
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
    
    // Verificar cierre después de un delay
    setTimeout(() => {
      this.verifyClose();
    }, isMobileDevice() ? 500 : 300);
  }
  
  verifyClose() {
    const modal = document.getElementById(this.modalId);
    
    if (!modal) {
      console.log(`✅ Modal ${this.modalId} removed from DOM`);
      this.finalizeCleanup();
      return;
    }
    
    const isStillVisible = modal.classList.contains('show') || 
                          getComputedStyle(modal).display !== 'none' ||
                          parseFloat(getComputedStyle(modal).opacity) > 0.1;
    
    if (isStillVisible && this.closeAttempt < this.options.maxAttempts) {
      console.log(`⚠️ Modal ${this.modalId} still visible, retrying...`);
      const retryDelay = this.options.baseDelay * (this.closeAttempt * 0.5);
      setTimeout(() => this.attemptClose(), retryDelay);
      
    } else if (isStillVisible && this.closeAttempt >= this.options.maxAttempts) {
      console.log(`🆘 Max attempts reached for ${this.modalId}, forcing close`);
      if (this.options.forceClose) {
        this.forceClose();
      }
      
    } else {
      console.log(`✅ Modal ${this.modalId} successfully closed`);
      this.finalizeCleanup();
    }
  }
  
  forceClose() {
    const modal = document.getElementById(this.modalId);
    
    if (modal) {
      modal.classList.remove('show');
      modal.style.display = 'none';
      modal.style.opacity = '0';
      modal.style.visibility = 'hidden';
      modal.style.pointerEvents = 'none';
      modal.style.zIndex = '-9999';
      
      if (this.options.removeFromDOM && isMobileDevice()) {
        setTimeout(() => {
          if (modal.parentNode) {
            modal.parentNode.removeChild(modal);
          }
        }, 100);
      }
    }
    
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    
    this.finalizeCleanup();
  }
  
  finalizeCleanup() {
    document.body.style.overflow = '';
    document.body.classList.remove('modal-open');
    
    // Trigger evento personalizado
    document.dispatchEvent(new CustomEvent('modalClosed', {
      detail: { 
        modalId: this.modalId,
        device: getDeviceType(),
        attempts: this.closeAttempt,
        success: this.closeAttempt <= this.options.maxAttempts
      }
    }));
    
    console.log(`✅ Modal ${this.modalId} cleanup complete`);
  }
}

/**
 * Mejoras específicas para móviles en formularios
 */
export function optimizeForMobile() {
  if (!isMobileDevice()) return;
  
  console.log('📱 Applying mobile optimizations');
  
  // Prevenir zoom en inputs en iOS
  const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="password"], input[type="search"], select, textarea');
  inputs.forEach(input => {
    if (input.style.fontSize && parseFloat(input.style.fontSize) < 16) {
      input.style.fontSize = '16px';
    }
  });
  
  // Mejorar touch targets
  const buttons = document.querySelectorAll('button, .btn, .chip, .match-type-btn');
  buttons.forEach(button => {
    const rect = button.getBoundingClientRect();
    if (rect.width < 44 || rect.height < 44) {
      button.style.minWidth = '44px';
      button.style.minHeight = '44px';
    }
  });
  
  // Optimizar scroll en contenedores
  const scrollContainers = document.querySelectorAll('.table-responsive-container, .modal-body, .date-modal-body');
  scrollContainers.forEach(container => {
    container.style.webkitOverflowScrolling = 'touch';
    container.style.scrollBehavior = 'smooth';
  });
}

/**
 * Notificación específica para móviles
 */
export function showMobileOptimizationNotice() {
  if (!isMobileDevice()) return;
  
  const notification = document.createElement('div');
  notification.className = 'mobile-optimization-notice';
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    left: 20px;
    right: 20px;
    background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
    border: 1px solid #2196f3;
    border-radius: 12px;
    padding: 16px;
    font-size: 14px;
    color: #1976d2;
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 10000;
    box-shadow: 0 4px 20px rgba(33, 150, 243, 0.3);
    animation: slideInDown 0.5s ease-out;
    max-width: 400px;
    margin: 0 auto;
  `;
  
  notification.innerHTML = `
    <div style="
      background: #2196f3;
      border-radius: 50%;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    ">
      <i class="fas fa-mobile-alt" style="color: white; font-size: 16px;"></i>
    </div>
    <div style="flex: 1;">
      <div style="font-weight: 600; margin-bottom: 4px;">📱 Dispositivo móvil detectado</div>
      <div style="font-size: 13px; opacity: 0.8;">Aplicando optimizaciones: timeouts extendidos, cierre robusto de modales y reintentos automáticos.</div>
    </div>
    <button onclick="this.parentElement.remove()" style="
      background: none;
      border: none;
      color: #1976d2;
      font-size: 18px;
      cursor: pointer;
      padding: 4px;
      opacity: 0.7;
    ">&times;</button>
  `;
  
  document.body.appendChild(notification);
  
  // Auto-remover después de 6 segundos
  setTimeout(() => {
    if (notification.parentElement) {
      notification.style.animation = 'slideOutUp 0.5s ease-in forwards';
      setTimeout(() => notification.remove(), 500);
    }
  }, 6000);
}

// CSS para las animaciones de la notificación móvil
const mobileAnimationCSS = `
@keyframes slideInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideOutUp {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-20px);
  }
}
`;

// Inyectar CSS si no existe
if (!document.querySelector('#mobile-animations-css')) {
  const style = document.createElement('style');
  style.id = 'mobile-animations-css';
  style.textContent = mobileAnimationCSS;
  document.head.appendChild(style);
}