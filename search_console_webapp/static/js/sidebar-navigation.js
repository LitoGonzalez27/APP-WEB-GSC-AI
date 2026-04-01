/*=============================================
  SIDEBAR NAVIGATION SYSTEM
  Sistema de navegacion lateral para mejorar UX
=============================================*/

// Lightweight toast helper for sidebar — follows Clicandseo brandbook
function _sidebarShowToast(message, type, duration) {
  type = type || 'info';
  duration = duration || 5000;
  var borderColors = { success: '#3CB371', error: '#E05252', warning: '#E05252', info: '#0F172A' };
  var toast = document.createElement('div');
  toast.setAttribute('role', 'alert');
  toast.style.cssText =
    'position:fixed;top:88px;right:18px;padding:14px 16px;border-radius:20px;color:#0F172A;' +
    "font-family:'Inter Tight',-apple-system,BlinkMacSystemFont,sans-serif;" +
    'font-size:0.875rem;line-height:1.6;font-weight:500;z-index:10000;' +
    'transition:all 0.3s cubic-bezier(0.2,0.8,0.2,1);' +
    'box-shadow:0 2px 4px rgba(15,23,42,0.04),0 8px 24px rgba(15,23,42,0.08);' +
    'background:#FFFFFF;border:1px solid #E2E8F0;' +
    'border-left:4px solid ' + (borderColors[type] || borderColors.info) + ';' +
    'max-width:420px;word-wrap:break-word;';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(function() { toast.style.opacity = '0'; setTimeout(function() { toast.remove(); }, 300); }, duration);
}

class SidebarNavigation {
  constructor() {
    this.currentSection = 'configuration'; // Sección por defecto
    this.analysisState = 'pending'; // pending, running, complete
    this.sections = ['configuration', 'performance', 'keywords', 'pages', 'ai-overview'];
    this.initialized = false;
    
    // Referencias a elementos DOM
    this.sidebar = null;
    this.overlay = null;
    this.toggleBtn = null;
    this.navItems = {};
    this.contentSections = {};
    this.statusDots = {};
    
    this.init();
  }

  init() {
    // Verificar si está deshabilitado (ej: en Manual AI)
    if (window.DISABLE_SIDEBAR_NAVIGATION) {
      console.log('🚫 SidebarNavigation deshabilitado por configuración');
      return;
    }
    
    // Esperar a que el DOM esté listo
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.setup());
    } else {
      this.setup();
    }
  }

  setup() {
    console.log('🎯 Iniciando sistema de navegación del sidebar...');
    
    // Obtener referencias a elementos DOM
    this.sidebar = document.getElementById('sidebarContainer');
    this.overlay = document.getElementById('sidebarMobileOverlay');
    this.toggleBtn = document.getElementById('mobileSidebarToggle');
    
    // Mapear elementos de navegación
    this.sections.forEach(section => {
      let navId, contentId, statusId;
      
      if (section === 'ai-overview') {
        navId = 'navAI';
        contentId = 'aiOverviewContent';
        statusId = 'statusAI';
      } else if (section === 'configuration') {
        navId = 'navConfiguration';
        contentId = 'configurationContent';
        statusId = 'statusConfiguration';
      } else {
        navId = `nav${this.capitalize(section)}`;
        contentId = `${section}Content`;
        statusId = `status${this.capitalize(section)}`;
      }
      
      this.navItems[section] = document.getElementById(navId);
      this.contentSections[section] = document.getElementById(contentId);
      this.statusDots[section] = document.getElementById(statusId);
      
      console.log(`🔍 Mapping section "${section}":`, {
        navId, navItem: this.navItems[section],
        contentId, contentElement: this.contentSections[section],
        statusId, statusDot: this.statusDots[section]
      });
    });

    // Configurar event listeners
    this.setupEventListeners();
    
    // Configurar estado inicial
    this.setInitialState();
    
    this.initialized = true;
    console.log('✅ Sistema de navegación del sidebar inicializado');
    
    // ✅ NUEVO: Auto-colapsar sidebar después de unos segundos
    this.setupAutoCollapse();
  }

  capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  // Sidebar siempre abierto - funcionalidad de colapso removida
  setupAutoCollapse() {
    // El sidebar permanece siempre expandido
    console.log('✅ Sidebar configurado como siempre abierto');
  }

  setupEventListeners() {
    // Event listeners para navegación
    Object.entries(this.navItems).forEach(([section, element]) => {
      if (element) {
        element.addEventListener('click', (e) => {
          e.preventDefault();
          console.log(`🖱️ Click en sección: ${section}`);
          this.navigateToSection(section);
        });
        console.log(`✅ Event listener agregado para sección: ${section}`);
      } else {
        console.warn(`⚠️ No se pudo agregar event listener para sección: ${section} (elemento no encontrado)`);
      }
    });

    // ✅ NUEVO: Event listener para botón de descarga Excel
    const sidebarDownloadBtn = document.getElementById('sidebarDownloadBtn');
    if (sidebarDownloadBtn) {
      sidebarDownloadBtn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('🖱️ Click en botón de descarga Excel del sidebar');
        this.handleDownloadClick();
      });
      console.log('✅ Event listener agregado para botón de descarga Excel');
    }

    const sidebarDownloadJsonBtn = document.getElementById('sidebarDownloadJsonBtn');
    if (sidebarDownloadJsonBtn) {
      sidebarDownloadJsonBtn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('🖱️ Click en botón de descarga JSON del sidebar');
        this.handleDownloadJsonClick();
      });
      console.log('✅ Event listener agregado para botón de descarga JSON');
    }

    // ✅ NUEVO: Event listener para botón de descarga PDF
    const sidebarDownloadPdfBtn = document.getElementById('sidebarDownloadPdfBtn');
    if (sidebarDownloadPdfBtn) {
      sidebarDownloadPdfBtn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('🖱️ Click en botón de descarga PDF del sidebar');
        this.handleDownloadPdfClick();
      });
      console.log('✅ Event listener agregado para botón de descarga PDF');
    }

    // Event listeners para móvil
    if (this.toggleBtn) {
      this.toggleBtn.addEventListener('click', () => this.toggleMobileSidebar());
    }

    if (this.overlay) {
      this.overlay.addEventListener('click', () => this.closeMobileSidebar());
    }

    // Cerrar sidebar en móvil al redimensionar ventana
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768) {
        this.closeMobileSidebar();
      }
    });

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isMobileSidebarOpen()) {
        this.closeMobileSidebar();
      }
    });
  }

  setInitialState() {
    // Configuration siempre disponible, las demás deshabilitadas
    this.analysisState = 'pending';
    this.sections.forEach(section => {
      if (section === 'configuration') {
        this.setSectionStatus(section, 'ready');
      } else {
        this.setSectionStatus(section, 'disabled');
      }
    });
    
    // Activar la sección de configuración como seleccionada
    this.currentSection = 'configuration';
    this.updateActiveSection();
    
    // Mostrar solo la sección de configuración inicialmente
    Object.entries(this.contentSections).forEach(([section, element]) => {
      if (element) {
        const isActive = section === 'configuration';
        element.style.display = isActive ? 'block' : 'none';
        element.classList.toggle('active', isActive);
      }
    });
  }

  navigateToSection(section) {
    if (!this.initialized || !this.sections.includes(section)) {
      console.warn(`❌ Sección no válida: ${section}`);
      return;
    }

    // Verificar si la sección está habilitada (configuration siempre disponible)
    const navItem = this.navItems[section];
    if (navItem && navItem.classList.contains('disabled') && section !== 'configuration') {
      console.log(`⚠️ Intento de navegar a sección deshabilitada: ${section}`);
      this.showSectionDisabledMessage(section);
      return;
    }

    console.log(`🧭 Navegando a sección: ${section}`, {
      previousSection: this.currentSection,
      newSection: section,
      navItem: navItem,
      contentElement: this.contentSections[section]
    });
    
    // Actualizar sección actual
    const previousSection = this.currentSection;
    this.currentSection = section;
    
    // Actualizar UI
    this.updateActiveSection();
    this.updateContentVisibility();
    
    // ✅ NUEVO: Mostrar elementos internos de la sección
    this.showSectionInternalElements(section);
    
    // ✅ NUEVO: Actualizar visibilidad del botón PDF (solo visible en AI Overview con datos)
    this.updatePdfButtonVisibility();
    
    // Cerrar sidebar móvil si está abierto
    this.closeMobileSidebar();
    
    // Trigger evento personalizado
    this.dispatchNavigationEvent(section, previousSection);
  }

  updateActiveSection() {
    // Actualizar estados de navegación
    Object.entries(this.navItems).forEach(([section, element]) => {
      if (element) {
        element.classList.toggle('active', section === this.currentSection);
      }
    });
  }

  updateContentVisibility() {
    // Ocultar todas las secciones
    Object.entries(this.contentSections).forEach(([section, element]) => {
      if (element) {
        const isActive = section === this.currentSection;
        element.style.display = isActive ? 'block' : 'none';
        element.classList.toggle('active', isActive);
        
        console.log(`🎯 Section ${section}: ${isActive ? 'VISIBLE' : 'HIDDEN'}`, {
          element: element,
          display: element.style.display,
          hasActiveClass: element.classList.contains('active')
        });
      } else {
        console.warn(`⚠️ Content section element not found for: ${section}`);
      }
    });
  }

  // ✅ NUEVO: Mostrar elementos internos específicos de cada sección
  showSectionInternalElements(section) {
    console.log(`🔍 Mostrando elementos internos para sección: ${section}`);
    
    try {
      switch (section) {
        case 'performance':
          this.showPerformanceElements();
          break;
        case 'keywords':
          this.showKeywordsElements();
          break;
        case 'pages':
          this.showPagesElements();
          break;
        case 'ai-overview':
          this.showAIElements();
          break;
        case 'configuration':
          // Configuration no necesita elementos especiales
          break;
        default:
          console.log(`⚠️ No hay elementos específicos para la sección: ${section}`);
      }
    } catch (error) {
      console.error(`❌ Error mostrando elementos para sección ${section}:`, error);
    }
  }

  showPerformanceElements() {
    console.log('🎯 Mostrando elementos de Performance...');
    
    // Elementos de insights/performance
    const elements = [
      document.getElementById('insightsSection'),
      document.getElementById('performanceSection'),
      document.getElementById('insightsTitle'),
      document.getElementById('performanceTitle'),
      document.getElementById('summaryBlock'),
      document.getElementById('moversSection'),
      document.getElementById('positionDistSection')
    ];
    
    elements.forEach((element, index) => {
      if (element) {
        element.style.display = 'block';
        console.log(`  ✅ Elemento ${index + 1} mostrado`);
      }
    });
  }

  showKeywordsElements() {
    console.log('🎯 Mostrando elementos de Keywords...');
    
    const elements = [
      document.getElementById('keywordsSection'),
      document.getElementById('keywordsTitle'),
      document.getElementById('keyword-overview'),
      document.getElementById('keyword-category-cards'),
      document.getElementById('keywordComparisonBlock')
    ];
    
    elements.forEach((element, index) => {
      if (element) {
        element.style.display = 'block';
        console.log(`  ✅ Elemento ${index + 1} mostrado`);
      }
    });
  }

  showPagesElements() {
    console.log('🎯 Mostrando elementos de Pages...');
    
    const elements = [
      document.getElementById('resultsSection'),
      document.getElementById('resultsTitle'),
      document.getElementById('resultsBlock')
    ];
    
    elements.forEach((element, index) => {
      if (element) {
        element.style.display = 'block';
        console.log(`  ✅ Elemento ${index + 1} mostrado`);
      }
    });
  }

  showAIElements() {
    console.log('🎯 Mostrando elementos de AI Overview...');
    
    const elements = [
      document.getElementById('aiOverviewResultsContainer'),
      document.getElementById('aiAnalysisMessage')
    ];
    
    elements.forEach((element, index) => {
      if (element) {
        // Solo mostrar si tiene contenido o clase específica
        if (element.children.length > 0 || element.classList.contains('has-content')) {
          element.style.display = 'block';
          console.log(`  ✅ Elemento AI ${index + 1} mostrado`);
        }
      }
    });

    // ✅ NUEVO: Controlar visibilidad del botón PDF según disponibilidad de datos
    this.updatePdfButtonVisibility();
  }

  // ✅ NUEVO: Actualizar visibilidad del botón PDF según contexto
  updatePdfButtonVisibility() {
    // El botón PDF solo se muestra si:
    // 1. Estamos en la sección AI Overview
    // 2. Y hay datos de AI Overview disponibles
    
    const isAISection = this.currentSection === 'ai-overview';
    
    // Verificar datos en window.currentAIOverviewData
    const hasAIData = window.currentAIOverviewData && 
                      (window.currentAIOverviewData.keywordResults?.length > 0 ||
                       window.currentAIOverviewData.analysis?.results?.length > 0);
    
    // Verificar que el contenedor de resultados está visible
    // Más robusto: aceptar display vacío ('') o 'block', y verificar offsetParent
    const aiResults = document.getElementById('aiOverviewResultsContainer');
    const displayValue = aiResults?.style.display;
    const isDisplayed = !displayValue || displayValue === '' || displayValue === 'block';
    const hasContent = (aiResults?.children.length || 0) > 0;
    const isInDOM = aiResults?.offsetParent !== null || aiResults?.style.display !== 'none';
    
    const resultsVisible = aiResults && isDisplayed && hasContent && isInDOM;
    
    // Criterio simplificado: si tenemos datos y estamos en AI section, mostrar
    const shouldShowPdf = isAISection && hasAIData;
    
    console.log(`📄 [PDF BUTTON] Actualizando visibilidad:`, {
      currentSection: this.currentSection,
      isAISection,
      hasWindowData: !!window.currentAIOverviewData,
      keywordResultsLength: window.currentAIOverviewData?.keywordResults?.length || 0,
      analysisResultsLength: window.currentAIOverviewData?.analysis?.results?.length || 0,
      hasAIData,
      aiResultsElement: !!aiResults,
      displayValue: displayValue || '(empty string)',
      isDisplayed,
      resultsChildrenCount: aiResults?.children.length || 0,
      hasContent,
      offsetParent: !!aiResults?.offsetParent,
      isInDOM,
      resultsVisible,
      shouldShow: shouldShowPdf
    });
    
    this.showPdfDownloadButton(shouldShowPdf);
  }

  // Estados de sección: 'disabled', 'ready', 'loading'
  setSectionStatus(section, status) {
    const navItem = this.navItems[section];
    const statusDot = this.statusDots[section];
    
    console.log(`🔧 Setting status for section "${section}": ${status}`, {
      navItem: !!navItem,
      statusDot: !!statusDot,
      currentClasses: navItem ? Array.from(navItem.classList) : 'N/A'
    });
    
    if (!navItem || !statusDot) {
      console.warn(`⚠️ Cannot set status for section "${section}" - missing elements:`, {
        navItem: !!navItem,
        statusDot: !!statusDot
      });
      return;
    }

    // Limpiar clases previas
    navItem.classList.remove('disabled');
    statusDot.classList.remove('status-disabled', 'status-ready', 'status-loading');
    
    // Aplicar nuevo estado
    switch (status) {
      case 'disabled':
        navItem.classList.add('disabled');
        statusDot.classList.add('status-disabled');
        break;
      case 'ready':
        statusDot.classList.add('status-ready');
        break;
      case 'loading':
        statusDot.classList.add('status-loading');
        break;
    }
    
    console.log(`✅ Status set for section "${section}": ${status}`, {
      newClasses: Array.from(navItem.classList),
      statusDotClasses: Array.from(statusDot.classList)
    });
  }



  showSectionDisabledMessage(section) {
    const sectionNames = {
      'configuration': 'Configuration',
      'performance': 'Performance Overview',
      'keywords': 'Keywords',
      'pages': 'Pages',
      'ai-overview': 'AI Overview'
    };
    
    const message = `The section "${sectionNames[section]}" requires you to run a data analysis first.`;
    
    // Crear notificación temporal
    this.showTemporaryNotification(message, 'warning');
  }

  showTemporaryNotification(message, type = 'info') {
    // Crear elemento de notificación
    const notification = document.createElement('div');
    notification.className = `sidebar-notification sidebar-notification-${type}`;
    notification.innerHTML = `
      <div class="notification-content">
        <i class="fas fa-${type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
        <span>${message}</span>
      </div>
    `;
    
    // Agregar estilos dinámicamente si no existen
    if (!document.getElementById('sidebar-notification-styles')) {
      const styles = document.createElement('style');
      styles.id = 'sidebar-notification-styles';
      styles.textContent = `
        .sidebar-notification {
          position: fixed;
          top: 80px;
          left: 50%;
          transform: translateX(-50%);
          z-index: 1050;
          padding: 12px 20px;
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          opacity: 0;
          transition: all 0.3s ease;
          max-width: 400px;
        }
        .sidebar-notification.show {
          opacity: 1;
          transform: translateX(-50%) translateY(0);
        }
        .sidebar-notification-warning {
          background: #fff3cd;
          border: 1px solid #ffeaa7;
          color: #856404;
        }
        .sidebar-notification-info {
          background: #d1ecf1;
          border: 1px solid #bee5eb;
          color: #0c5460;
        }
        .notification-content {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.9rem;
        }
        @media (max-width: 768px) {
          .sidebar-notification {
            left: 16px;
            right: 16px;
            transform: none;
            max-width: none;
          }
          .sidebar-notification.show {
            transform: none;
          }
        }
      `;
      document.head.appendChild(styles);
    }
    
    // Agregar al DOM
    document.body.appendChild(notification);
    
    // Mostrar animación
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Remover después de 3 segundos
    setTimeout(() => {
      notification.classList.remove('show');
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 3000);
  }

  // Funciones para móvil
  toggleMobileSidebar() {
    if (this.isMobileSidebarOpen()) {
      this.closeMobileSidebar();
    } else {
      this.openMobileSidebar();
    }
  }

  openMobileSidebar() {
    if (this.sidebar) this.sidebar.classList.add('mobile-open');
    if (this.overlay) this.overlay.classList.add('active');
    if (this.toggleBtn) this.toggleBtn.classList.add('hidden');
    document.body.style.overflow = 'hidden';
  }

  closeMobileSidebar() {
    if (this.sidebar) this.sidebar.classList.remove('mobile-open');
    if (this.overlay) this.overlay.classList.remove('active');
    if (this.toggleBtn) this.toggleBtn.classList.remove('hidden');
    document.body.style.overflow = '';
  }

  isMobileSidebarOpen() {
    return this.sidebar && this.sidebar.classList.contains('mobile-open');
  }

  // Funciones para integración con el sistema existente
  onAnalysisStart() {
    console.log('📊 Análisis iniciado - actualizando estados del sidebar');
    this.analysisState = 'running';
    
    // Marcar secciones como cargando
    this.sections.forEach(section => {
      if (section !== 'ai-overview') {
        this.setSectionStatus(section, 'loading');
      }
    });
  }

  onAnalysisComplete(availableSections = []) {
    console.log('✅ Análisis completado - habilitando secciones:', availableSections);
    this.analysisState = 'complete';
    
    // Habilitar secciones disponibles
    this.sections.forEach(section => {
      if (section === 'configuration') {
        // Configuration siempre disponible
        this.setSectionStatus(section, 'ready');
        console.log(`🎯 Section ${section}: Always available (configuration)`);
      } else if (section === 'ai-overview') {
        // AI Overview requiere ejecución manual
        this.setSectionStatus(section, 'disabled');
        console.log(`🎯 Section ${section}: Requires manual execution`);
      } else if (availableSections.includes(section)) {
        this.setSectionStatus(section, 'ready');
        console.log(`🎯 Section ${section}: ENABLED (found in available sections)`);
      } else {
        // ✅ NUEVO: Verificar si la sección ya está habilitada antes de deshabilitarla
        const navItem = this.navItems[section];
        const isAlreadyEnabled = navItem && !navItem.classList.contains('disabled');
        
        if (isAlreadyEnabled) {
          console.log(`🎯 Section ${section}: KEEPING ENABLED (already enabled by content detection)`);
        } else {
          this.setSectionStatus(section, 'disabled');
          console.log(`🎯 Section ${section}: DISABLED (not in available sections: [${availableSections.join(', ')}])`);
        }
      }
    });

    // ✅ NUEVO: No navegar automáticamente, dejar que el usuario elija
    // Las secciones estarán habilitadas y el usuario puede navegar cuando quiera
    console.log(`✅ Análisis completado. Secciones disponibles: [${availableSections.join(', ')}]`);
    console.log('👆 Usuario puede navegar a las secciones habilitadas cuando lo desee');
    
    // ✅ NUEVO: Mostrar botón de descarga Excel si hay datos disponibles
    this.showDownloadButton(availableSections.length > 0);
  }

  onAIAnalysisReady() {
    console.log('🤖 AI Overview habilitado');
    this.setSectionStatus('ai-overview', 'ready');
    
    // ✅ Si estamos en la sección AI, mostrar los elementos
    if (this.currentSection === 'ai-overview') {
      this.showSectionInternalElements('ai-overview');
    }
    
    // ✅ NUEVO: Actualizar visibilidad del botón PDF cuando hay datos listos
    this.updatePdfButtonVisibility();
  }

  // ✅ NUEVO: Mostrar/ocultar botón de descarga Excel
  showDownloadButton(show = true) {
    const sidebarDownloadBtn = document.getElementById('sidebarDownloadBtn');
    const sidebarDownloadJsonBtn = document.getElementById('sidebarDownloadJsonBtn');
    
    if (sidebarDownloadBtn) {
      sidebarDownloadBtn.style.display = show ? 'flex' : 'none';
      console.log(`📥 Botón de descarga Excel ${show ? 'mostrado' : 'ocultado'}`);
    }

    if (sidebarDownloadJsonBtn) {
      sidebarDownloadJsonBtn.style.display = show ? 'flex' : 'none';
      console.log(`🧾 Botón de descarga JSON ${show ? 'mostrado' : 'ocultado'}`);
    }
  }

  // ✅ NUEVO: Mostrar/ocultar botón de descarga PDF (solo para AI Overview)
  showPdfDownloadButton(show = true) {
    const sidebarDownloadPdfBtn = document.getElementById('sidebarDownloadPdfBtn');
    
    if (sidebarDownloadPdfBtn) {
      const currentDisplay = sidebarDownloadPdfBtn.style.display;
      sidebarDownloadPdfBtn.style.display = show ? 'flex' : 'none';
      console.log(`📄 [PDF BUTTON] ${show ? 'MOSTRANDO' : 'OCULTANDO'} botón PDF (display: ${currentDisplay} → ${show ? 'flex' : 'none'})`);
    } else {
      console.warn('⚠️ [PDF BUTTON] Elemento sidebarDownloadPdfBtn NO encontrado en el DOM');
    }
  }

  getDownloadButtonElements(buttonId) {
    const button = document.getElementById(buttonId);
    return {
      button,
      spinner: button?.querySelector('.download-spinner'),
      text: button?.querySelector('span')
    };
  }

  setDownloadButtonLoadingState(buttonId, isLoading) {
    const { button, spinner, text } = this.getDownloadButtonElements(buttonId);
    if (!button) return false;
    if (spinner) spinner.style.display = isLoading ? 'inline-block' : 'none';
    if (text) text.style.display = isLoading ? 'none' : 'inline';
    button.disabled = !!isLoading;
    return true;
  }

  showDownloadButtonSuccess(buttonId, successText = 'Downloaded!') {
    const { button, text } = this.getDownloadButtonElements(buttonId);
    if (!button || !text) return;
    const originalText = text.textContent;
    text.textContent = successText;
    button.classList.add('success');
    setTimeout(() => {
      text.textContent = originalText;
      button.classList.remove('success');
    }, 2000);
  }

  triggerBlobDownload(blob, fileName) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }

  buildExportPayload() {
    if (!window.currentData || !window.currentData.pages) {
      throw new Error('NO_DATA');
    }

    let aiOverviewDataToDownload = null;

    if (window.currentAIOverviewData) {
      console.log('🔍 Procesando datos AI Overview para descarga...', window.currentAIOverviewData);

      if (window.currentAIOverviewData.analysis) {
        aiOverviewDataToDownload = {
          results: window.currentAIOverviewData.analysis.results || window.currentAIOverviewData.keywordResults || [],
          summary: window.currentAIOverviewData.analysis.summary || window.currentAIOverviewData.summary || {},
          clusters_analysis: window.currentAIOverviewData.clusters_analysis || null
        };
      } else if (window.currentAIOverviewData.results && window.currentAIOverviewData.summary) {
        aiOverviewDataToDownload = {
          results: window.currentAIOverviewData.results,
          summary: window.currentAIOverviewData.summary,
          clusters_analysis: window.currentAIOverviewData.clusters_analysis || null
        };
      } else if (window.currentAIOverviewData.keywordResults) {
        aiOverviewDataToDownload = {
          results: window.currentAIOverviewData.keywordResults,
          summary: window.currentAIOverviewData.summary || {},
          clusters_analysis: window.currentAIOverviewData.clusters_analysis || null
        };
      } else {
        aiOverviewDataToDownload = window.currentAIOverviewData;
      }
    }

    const siteUrlSelect = document.getElementById('siteUrlSelect');

    // Optimizado: enviar solo los campos que excel_generator.py realmente usa
    const prunedData = {
      pages: window.currentData.pages || [],
      keyword_comparison_data: window.currentData.keyword_comparison_data || [],
      selected_country: window.currentData.selected_country || ''
    };

    const payload = {
      data: prunedData,
      ai_overview_data: aiOverviewDataToDownload,
      metadata: {
        site_url: siteUrlSelect ? siteUrlSelect.value : '',
        months: [...document.querySelectorAll('.chip.selected')].map(c => c.dataset.value),
        generated_at: new Date().toISOString()
      }
    };

    return { payload, aiOverviewDataToDownload };
  }

  // ✅ NUEVO: Manejar click del botón de descarga Excel
  async handleDownloadClick() {
    const buttonId = 'sidebarDownloadBtn';
    const { button } = this.getDownloadButtonElements(buttonId);
    if (!button) return;

    console.log('📥 Iniciando descarga Excel desde sidebar...');

    try {
      const { payload, aiOverviewDataToDownload } = this.buildExportPayload();
      this.setDownloadButtonLoadingState(buttonId, true);

      const response = await fetch('/download-excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Error parsing server response' }));
        let alertMessage = `Error generating Excel: ${errorData.error || response.statusText}`;
        if (errorData.reauth_required) {
          alertMessage += '\nGoogle authentication failed or expired. Please reload the page to re-authenticate.';
        }
        _sidebarShowToast(alertMessage, 'error', 6000);
        return;
      }

      const blob = await response.blob();
      const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
      const hasAI = aiOverviewDataToDownload ? '_con_AI' : '';
      this.triggerBlobDownload(blob, `search_console_report${hasAI}_${timestamp}.xlsx`);
      this.showDownloadButtonSuccess(buttonId, 'Downloaded!');
      console.log('✅ Descarga Excel completada');
    } catch (error) {
      console.error('❌ Error al descargar Excel:', error);
      if (error?.message === 'NO_DATA') {
        _sidebarShowToast('No data to download. Please run a query first.', 'warning');
      } else {
        _sidebarShowToast('An unexpected error occurred while trying to download the Excel file.', 'error');
      }
    } finally {
      this.setDownloadButtonLoadingState(buttonId, false);
    }
  }

  // ✅ NUEVO: Manejar click del botón de descarga JSON
  async handleDownloadJsonClick() {
    const buttonId = 'sidebarDownloadJsonBtn';
    const { button } = this.getDownloadButtonElements(buttonId);
    if (!button) return;

    console.log('🧾 Iniciando descarga JSON desde sidebar...');

    try {
      const { payload, aiOverviewDataToDownload } = this.buildExportPayload();
      this.setDownloadButtonLoadingState(buttonId, true);

      // JSON export: usar datos completos (no podados como para Excel)
      if (window.currentData) {
        payload.data = window.currentData;
      }

      const jsonBlob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json;charset=utf-8'
      });

      const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
      const hasAI = aiOverviewDataToDownload ? '_con_AI' : '';
      this.triggerBlobDownload(jsonBlob, `search_console_report${hasAI}_${timestamp}.json`);
      this.showDownloadButtonSuccess(buttonId, 'Downloaded!');
      console.log('✅ Descarga JSON completada');
    } catch (error) {
      console.error('❌ Error al descargar JSON:', error);
      if (error?.message === 'NO_DATA') {
        _sidebarShowToast('No data to download. Please run a query first.', 'warning');
      } else {
        _sidebarShowToast('An unexpected error occurred while trying to download the JSON file.', 'error');
      }
    } finally {
      this.setDownloadButtonLoadingState(buttonId, false);
    }
  }

  // ✅ NUEVO: Manejador para descarga de PDF
  async handleDownloadPdfClick() {
    console.log('📄 Iniciando descarga PDF desde sidebar...');
    
    // Verificar que estamos en la sección AI Overview
    if (this.currentSection !== 'ai-overview') {
      _sidebarShowToast('PDF download is only available in the AI Overview section. Please navigate to AI Overview first.', 'warning', 5000);
      return;
    }

    // Verificar que hay datos de AI Overview disponibles
    const aiResults = document.getElementById('aiOverviewResultsContainer');
    if (!aiResults || aiResults.style.display === 'none') {
      _sidebarShowToast('No AI Overview data to export. Please run an AI analysis first.', 'warning');
      return;
    }

    try {
      // Importar dinámicamente el módulo de generación de PDF
      const { generateAIOverviewPDF } = await import('./ui-ai-overview-pdf.js');
      
      // Llamar a la función de generación de PDF
      await generateAIOverviewPDF();
      
    } catch (error) {
      console.error('❌ Error al cargar o ejecutar el módulo de PDF:', error);
      _sidebarShowToast('Error generating PDF: ' + error.message, 'error', 5000);
    }
  }

  // Event dispatch para integración
  dispatchNavigationEvent(newSection, previousSection) {
    const event = new CustomEvent('sidebarNavigation', {
      detail: {
        newSection,
        previousSection,
        timestamp: Date.now()
      }
    });
    document.dispatchEvent(event);
  }

  // API pública
  getCurrentSection() {
    return this.currentSection;
  }

  getAnalysisState() {
    return this.analysisState;
  }

  resetSidebar() {
    console.log('🔄 Reseteando sidebar...');
    this.setInitialState();
  }

  // ✅ NUEVA: Función para mostrar una sección específica (llamada desde ui-render.js)
  showSection(sectionName) {
    if (!this.initialized) return;
    
    // Mapear nombres de secciones del sistema antiguo al nuevo
    const sectionMapping = {
      'insightsSection': 'performance',
      'performanceSection': 'performance', 
      'keywordsSection': 'keywords',
      'resultsSection': 'pages',
      'aiOverviewSection': 'ai-overview'
    };
    
    const targetSection = sectionMapping[sectionName] || sectionName;
    
    if (this.sections.includes(targetSection)) {
      // Solo navegar si la sección está habilitada o es configuration
      const navItem = this.navItems[targetSection];
      if (!navItem || !navItem.classList.contains('disabled') || targetSection === 'configuration') {
        this.navigateToSection(targetSection);
      }
    }
  }
}

// Crear instancia global
let sidebarNavigation = null;

// Función de inicialización
function initSidebarNavigation() {
  if (!sidebarNavigation) {
    sidebarNavigation = new SidebarNavigation();
    
    // Hacer disponible globalmente para compatibilidad
    window.sidebarNavigation = sidebarNavigation;
  }
  
  return sidebarNavigation;
}

// Funciones de utilidad para integración
function getSidebarNavigation() {
  return sidebarNavigation;
}

function onAnalysisStart() {
  if (sidebarNavigation) {
    sidebarNavigation.onAnalysisStart();
  }
}

function onAnalysisComplete(availableSections = []) {
  if (sidebarNavigation) {
    sidebarNavigation.onAnalysisComplete(availableSections);
  }
}

function onAIAnalysisReady() {
  if (sidebarNavigation) {
    sidebarNavigation.onAIAnalysisReady();
  }
}

function resetSidebar() {
  if (sidebarNavigation) {
    sidebarNavigation.resetSidebar();
  }
}

function navigateToSection(section) {
  if (sidebarNavigation) {
    sidebarNavigation.navigateToSection(section);
  }
}

function showSection(sectionName) {
  if (sidebarNavigation) {
    sidebarNavigation.showSection(sectionName);
  }
}

// ✅ NUEVO: Función para actualizar visibilidad del botón PDF
function updatePdfButtonVisibility() {
  if (sidebarNavigation) {
    sidebarNavigation.updatePdfButtonVisibility();
  }
}

// ✅ DEBUG: Función para forzar mostrar botón PDF (debug)
function debugShowPdfButton() {
  console.log('🔧 [DEBUG] Forzando mostrar botón PDF...');
  const pdfBtn = document.getElementById('sidebarDownloadPdfBtn');
  if (pdfBtn) {
    pdfBtn.style.display = 'flex';
    console.log('✅ [DEBUG] Botón PDF forzado a mostrar');
  } else {
    console.error('❌ [DEBUG] Botón PDF NO encontrado en DOM');
  }
  
  // Mostrar estado actual
  console.log('📊 [DEBUG] Estado actual:', {
    sidebarNav: !!sidebarNavigation,
    currentSection: sidebarNavigation?.currentSection,
    hasAIData: !!window.currentAIOverviewData,
    aiDataKeys: window.currentAIOverviewData ? Object.keys(window.currentAIOverviewData) : []
  });
}

// Hacer funciones disponibles globalmente para compatibilidad
window.getSidebarNavigation = getSidebarNavigation;
window.onAnalysisStart = onAnalysisStart;
window.onAnalysisComplete = onAnalysisComplete;
window.onAIAnalysisReady = onAIAnalysisReady;
window.resetSidebar = resetSidebar;
window.navigateToSection = navigateToSection;
window.showSection = showSection;
window.onContentReady = onContentReady;
window.updatePdfButtonVisibility = updatePdfButtonVisibility;
window.debugShowPdfButton = debugShowPdfButton;

// ✅ Nueva función para habilitar secciones cuando el contenido esté listo
function onContentReady(sectionName) {
  console.log(`📊 Content ready detected for section: ${sectionName}`);
  
  if (!sidebarNavigation) {
    console.warn('Cannot enable section - sidebar not initialized');
    return;
  }
  
  if (sectionName === 'performance' || sectionName === 'insights') {
    // ✅ Habilitar performance cuando insights o performance content esté listo
    sidebarNavigation.setSectionStatus('performance', 'ready');
    console.log('✅ Performance section enabled via content ready detection');
  }
}

// Auto-inicialización
document.addEventListener('DOMContentLoaded', () => {
  initSidebarNavigation();
});

// ✅ NUEVO: Funciones de debug global para testing
window.debugSidebar = function() {
  if (sidebarNavigation) {
    console.log('=== SIDEBAR DEBUG INFO ===');
    console.log('Current section:', sidebarNavigation.currentSection);
    console.log('Analysis state:', sidebarNavigation.analysisState);
    console.log('Sections:', sidebarNavigation.sections);
    console.log('Initialized:', sidebarNavigation.initialized);
    
    console.log('\n📋 SECTION STATES:');
    sidebarNavigation.sections.forEach(section => {
      const navItem = sidebarNavigation.navItems[section];
      const contentElement = sidebarNavigation.contentSections[section];
      const statusDot = sidebarNavigation.statusDots[section];
      
      console.log(`  ${section}:`, {
        navItem: !!navItem,
        disabled: navItem ? navItem.classList.contains('disabled') : 'N/A',
        active: navItem ? navItem.classList.contains('active') : 'N/A',
        contentVisible: contentElement ? contentElement.style.display === 'block' : 'N/A',
        statusDotClass: statusDot ? Array.from(statusDot.classList).filter(c => c.startsWith('status-')) : 'N/A'
      });
    });
    
    console.log('\n🎯 ELEMENT REFERENCES:');
    console.log('Nav items:', sidebarNavigation.navItems);
    console.log('Content sections:', sidebarNavigation.contentSections);
    console.log('Status dots:', sidebarNavigation.statusDots);
    
    console.log('\n🛠️ DEBUG HELPERS:');
    console.log('- diagnoseSectionElements("performance") - Diagnosticar elementos de performance');
    console.log('- showSectionElements("performance") - Forzar mostrar elementos');
    console.log('- forceSectionEnabled("performance") - Habilitar sección');
    console.log('=========================');
  } else {
    console.warn('Sidebar not initialized');
  }
};

window.testSidebarNavigation = function(section) {
  if (sidebarNavigation) {
    console.log(`🧪 Testing navigation to: ${section}`);
    sidebarNavigation.navigateToSection(section);
  } else {
    console.warn('Sidebar not initialized');
  }
};

window.forceSectionEnabled = function(section) {
  if (sidebarNavigation && sidebarNavigation.sections.includes(section)) {
    console.log(`🔧 Force enabling section: ${section}`);
    sidebarNavigation.setSectionStatus(section, 'ready');
    console.log(`✅ Section ${section} force enabled`);
  } else {
    console.warn(`Cannot force enable section: ${section}`, {
      sidebarInitialized: !!sidebarNavigation,
      validSections: sidebarNavigation ? sidebarNavigation.sections : 'N/A'
    });
  }
};

// ✅ Exponer onContentReady globalmente para ui-render.js
window.sidebarOnContentReady = function(sectionName) {
  console.log(`📊 Content ready detected for section: ${sectionName}`);
  
  if (!sidebarNavigation) {
    console.warn('Cannot enable section - sidebar not initialized');
    return;
  }
  
  if (sectionName === 'performance' || sectionName === 'insights') {
    // ✅ Habilitar performance cuando insights o performance content esté listo
    sidebarNavigation.setSectionStatus('performance', 'ready');
    console.log('✅ Performance section enabled via content ready detection');
    
    // ✅ Si estamos navegando a la sección performance, mostrar los elementos
    if (sidebarNavigation.currentSection === 'performance') {
      sidebarNavigation.showSectionInternalElements('performance');
    }
  }
};

// ✅ NUEVO: Exponer showSection globalmente para botones sticky
window.showSection = function(sectionName) {
  if (sidebarNavigation) {
    console.log(`🎯 Global showSection called for: ${sectionName}`);
    sidebarNavigation.showSection(sectionName);
  } else {
    console.warn('Cannot navigate - sidebar not initialized');
  }
};

// ✅ NUEVO: Función para mostrar elementos internos manualmente (debug)
window.showSectionElements = function(section) {
  if (sidebarNavigation) {
    console.log(`🔧 Force showing elements for section: ${section}`);
    sidebarNavigation.showSectionInternalElements(section);
  } else {
    console.warn('Sidebar not initialized');
  }
};

// ✅ NUEVO: Función para diagnosticar elementos ocultos (debug)
window.diagnoseSectionElements = function(section) {
  console.log(`🔍 Diagnosticando elementos de la sección: ${section}`);
  
  const sectionMapping = {
    'performance': ['insightsSection', 'performanceSection', 'insightsTitle', 'performanceTitle', 'summaryBlock', 'moversSection', 'positionDistSection'],
    'keywords': ['keywordsSection', 'keywordsTitle', 'keyword-overview', 'keyword-category-cards', 'keywordComparisonBlock'],
    'pages': ['resultsSection', 'resultsTitle', 'resultsBlock'],
    'ai-overview': ['aiOverviewResultsContainer', 'aiAnalysisMessage']
  };
  
  const elementIds = sectionMapping[section] || [];
  
  elementIds.forEach(id => {
    const element = document.getElementById(id);
    if (element) {
      const isVisible = element.style.display !== 'none' && 
                        getComputedStyle(element).display !== 'none' &&
                        element.offsetParent !== null;
      
      console.log(`  ${isVisible ? '✅' : '❌'} ${id}:`, {
        exists: true,
        display: element.style.display,
        computedDisplay: getComputedStyle(element).display,
        offsetParent: element.offsetParent,
        hasContent: element.children.length > 0 || element.textContent.trim().length > 0
      });
    } else {
      console.log(`  ❌ ${id}: NO EXISTE`);
    }
  });
}; 
