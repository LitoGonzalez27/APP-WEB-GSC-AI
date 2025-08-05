// static/js/ai-reset-manager.js - Gestión del botón reset para AI Overview

/**
 * Gestor del botón reset para AI Overview
 * Maneja el reseteo completo del módulo con efecto fluido
 */
class AIResetManager {
  constructor() {
    this.resetBtn = null;
    this.aiSection = null;
    this.aiContentWrapper = null;
    this.aiOverlay = null;
    this.aiResultsContainer = null;
    this.advancedAnalysisSection = null;
    
    this.init();
  }

  init() {
    // Esperar a que el DOM esté completamente cargado
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.setupElements());
    } else {
      this.setupElements();
    }
  }

  setupElements() {
    // Obtener referencias a los elementos
    this.resetBtn = document.getElementById('resetAIAnalysisBtn');
    this.aiSection = document.getElementById('aiOverviewSection');
    this.aiContentWrapper = document.getElementById('aiContentWrapper');
    this.aiOverlay = document.getElementById('aiOverlay');
    this.aiResultsContainer = document.getElementById('aiOverviewResultsContainer');
    this.advancedAnalysisSection = document.getElementById('advancedAnalysisSection');

    if (!this.resetBtn) {
      console.warn('⚠️ Reset button not found');
      return;
    }

    // Configurar event listeners
    this.setupEventListeners();
    
    console.log('✅ AI Reset Manager initialized');
  }

  setupEventListeners() {
    // Event listener para el botón reset
    this.resetBtn.addEventListener('click', (e) => {
      e.preventDefault();
      this.resetAIAnalysis();
    });

    // Mostrar/ocultar botón según el estado del análisis
    this.updateResetButtonVisibility();
    
    // Observer para detectar cambios en el contenido
    this.setupMutationObserver();
  }

  setupMutationObserver() {
    if (!this.aiResultsContainer) return;

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'childList' || mutation.type === 'attributes') {
          this.updateResetButtonVisibility();
        }
      });
    });

    observer.observe(this.aiResultsContainer, {
      childList: true,
      attributes: true,
      attributeFilter: ['style']
    });
  }

  updateResetButtonVisibility() {
    if (!this.resetBtn || !this.aiResultsContainer) return;

    // Mostrar botón si hay resultados visibles
    const hasResults = this.aiResultsContainer.style.display !== 'none' && 
                      this.aiResultsContainer.children.length > 0;
    
    if (hasResults) {
      this.showResetButton();
    } else {
      this.hideResetButton();
    }
  }

  showResetButton() {
    if (!this.resetBtn) return;
    
    this.resetBtn.style.display = 'inline-flex';
    // Pequeña animación de entrada
    setTimeout(() => {
      this.resetBtn.style.opacity = '1';
      this.resetBtn.style.transform = 'translateY(0)';
    }, 50);
  }

  hideResetButton() {
    if (!this.resetBtn) return;
    
    this.resetBtn.style.opacity = '0';
    this.resetBtn.style.transform = 'translateY(-5px)';
    setTimeout(() => {
      this.resetBtn.style.display = 'none';
    }, 200);
  }

  async resetAIAnalysis() {
    console.log('🔄 Initiating AI Analysis reset...');
    
    try {
      // 1. Mostrar indicador de carga en el botón
      this.showResetLoading();
      
      // 2. Efecto de desvanecimiento del módulo
      await this.fadeOutModule();
      
      // 3. Resetear todo el contenido
      this.resetAllContent();
      
      // 4. Resetear filtros y configuraciones
      this.resetFiltersAndConfig();
      
      // 5. Efecto de reaparición del módulo
      await this.fadeInModule();
      
      // 6. Restaurar botón reset
      this.hideResetLoading();
      
      console.log('✅ AI Analysis reset completed');
      
      // Mostrar notificación de éxito
      if (window.showToast) {
        window.showToast('AI Analysis reset successfully', 'success', 3000);
      }
      
    } catch (error) {
      console.error('❌ Error during AI reset:', error);
      this.hideResetLoading();
      
      if (window.showToast) {
        window.showToast('Error resetting AI Analysis', 'error', 3000);
      }
    }
  }

  showResetLoading() {
    if (!this.resetBtn) return;
    
    const icon = this.resetBtn.querySelector('i');
    const span = this.resetBtn.querySelector('span');
    
    if (icon) {
      icon.className = 'fas fa-spinner fa-spin';
    }
    if (span) {
      span.textContent = 'Resetting...';
    }
    
    this.resetBtn.disabled = true;
    this.resetBtn.style.opacity = '0.7';
  }

  hideResetLoading() {
    if (!this.resetBtn) return;
    
    const icon = this.resetBtn.querySelector('i');
    const span = this.resetBtn.querySelector('span');
    
    if (icon) {
      icon.className = 'fas fa-refresh';
    }
    if (span) {
      span.textContent = 'Reset Analysis';
    }
    
    this.resetBtn.disabled = false;
    this.resetBtn.style.opacity = '0.9';
  }

  fadeOutModule() {
    return new Promise((resolve) => {
      if (!this.aiSection) {
        resolve();
        return;
      }
      
      // Añadir clase de fade out
      this.aiSection.classList.add('ai-module-fadeout');
      this.aiSection.classList.remove('ai-module-fadein');
      
      // Esperar a que termine la animación
      setTimeout(resolve, 400);
    });
  }

  fadeInModule() {
    return new Promise((resolve) => {
      if (!this.aiSection) {
        resolve();
        return;
      }
      
      // Añadir clase de fade in
      this.aiSection.classList.remove('ai-module-fadeout');
      this.aiSection.classList.add('ai-module-fadein');
      
      // Esperar a que termine la animación
      setTimeout(resolve, 500);
    });
  }

  resetAllContent() {
    // Limpiar contenedor de resultados
    if (this.aiResultsContainer) {
      this.aiResultsContainer.innerHTML = '';
      this.aiResultsContainer.style.display = 'none';
    }

    // Limpiar mensaje de análisis
    const aiAnalysisMessage = document.getElementById('aiAnalysisMessage');
    if (aiAnalysisMessage) {
      aiAnalysisMessage.innerHTML = '';
      aiAnalysisMessage.style.display = 'none';
    }

    // Restaurar el wrapper blurred
    if (this.aiContentWrapper) {
      this.aiContentWrapper.classList.add('blurred');
    }

    // ✅ MEJORADO: Usar la función resetAIOverlay existente que restaura completamente el overlay
    if (window.resetAIOverlay) {
      window.resetAIOverlay();
      console.log('🔄 AI Overlay restaurado con función nativa');
      
      // Después del reset, reactivar el overlay con datos existentes si están disponibles
      setTimeout(() => {
        this.reactivateOverlayData();
      }, 100); // Pequeño delay para asegurar que el DOM esté actualizado
      
    } else {
      // Fallback manual si la función no está disponible
      if (this.aiOverlay) {
        this.aiOverlay.style.display = 'flex';
      }
      console.warn('⚠️ resetAIOverlay function not available, using fallback');
    }

    // Limpiar datos globales
    if (window.currentAIOverviewData) {
      window.currentAIOverviewData = null;
    }

    console.log('🧹 AI content reset completed');
  }

  resetFiltersAndConfig() {
    // Resetear selector de keywords
    const keywordCountSelect = document.getElementById('keywordCountSelect');
    if (keywordCountSelect) {
      keywordCountSelect.value = '50'; // Valor por defecto
    }

    // Resetear competidores si existen
    const competitorInputs = document.querySelectorAll('input[name="competitor_domain"]');
    competitorInputs.forEach(input => {
      input.value = '';
    });

    // Resetear exclusiones de keywords si existen
    const keywordExclusionsInput = document.getElementById('keywordExclusions');
    if (keywordExclusionsInput) {
      keywordExclusionsInput.value = '';
    }

    // Cerrar todas las secciones colapsibles
    const collapsibleSections = document.querySelectorAll('.collapsible-section');
    collapsibleSections.forEach(section => {
      const toggle = section.querySelector('.collapsible-toggle');
      const content = section.querySelector('.collapsible-content');
      
      if (toggle && content) {
        toggle.classList.remove('active');
        content.style.display = 'none';
      }
    });

    console.log('🔧 Filters and config reset completed');
  }

  // Método público para otros módulos
  triggerReset() {
    this.resetAIAnalysis();
  }

  // Método para mostrar/ocultar manualmente el botón
  setResetButtonVisibility(visible) {
    if (visible) {
      this.showResetButton();
    } else {
      this.hideResetButton();
    }
  }

  // ✅ NUEVO: Reactivar overlay con datos existentes
  reactivateOverlayData() {
    try {
      // Obtener datos globales de keywords si están disponibles
      let keywordData = null;
      let siteUrl = null;

      // Intentar obtener datos desde window.currentData (datos del análisis principal)
      if (window.currentData && window.currentData.keyword_comparison_data) {
        keywordData = window.currentData.keyword_comparison_data;
        console.log('📊 Datos de keywords obtenidos desde currentData:', keywordData?.length);
      }

      // Obtener siteUrl desde el selector
      const siteUrlSelect = document.getElementById('siteUrlSelect');
      if (siteUrlSelect && siteUrlSelect.value) {
        siteUrl = siteUrlSelect.value;
        console.log('🌐 SiteUrl obtenido desde selector:', siteUrl);
      }

      // Si tenemos datos válidos, reactivar el overlay
      if (keywordData && keywordData.length > 0 && siteUrl && window.updateAIOverlayData) {
        window.updateAIOverlayData(keywordData, siteUrl);
        console.log('✅ Overlay reactivado con datos existentes');
      } else {
        console.log('ℹ️ No hay datos válidos para reactivar el overlay');
      }

    } catch (error) {
      console.error('❌ Error reactivando overlay data:', error);
    }
  }
}

// Instancia global
window.aiResetManager = new AIResetManager();

// Exportar para usar en otros módulos si es necesario
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AIResetManager;
}

console.log('📝 AI Reset Manager loaded');