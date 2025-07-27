// ui-sticky-actions.js - Manejo de botones sticky flotantes
import { elems } from './utils.js';

// Variables de estado
let stickyActionsVisible = false;
let currentKeywordData = null;
let currentSiteUrl = null;

/**
 * Inicializa los event listeners para los botones sticky
 */
export function initStickyActions() {
    console.log('🎯 Inicializando botones sticky...');
    
    if (!elems.stickyAIBtn) {
        console.warn('Elemento sticky AI no encontrado');
        return;
    }

    // Event listener para análisis IA
    elems.stickyAIBtn.addEventListener('click', handleStickyAIAnalysis);

    // Tooltip para móvil
    elems.stickyAIBtn.setAttribute('data-tooltip', 'Execute AI Analysis');

    console.log('✅ Botón sticky AI inicializado correctamente');
}

/**
 * Muestra los botones sticky con animación
 */
export function showStickyActions() {
    if (!elems.stickyActions || stickyActionsVisible) return;
    
    console.log('👁️ Mostrando botones sticky');
    elems.stickyActions.style.display = 'block';
    
    // Pequeño delay para permitir que se renderice antes de la animación
    setTimeout(() => {
        elems.stickyActions.classList.add('show');
        stickyActionsVisible = true;
    }, 50);
}

/**
 * Oculta los botones sticky
 */
export function hideStickyActions() {
    if (!elems.stickyActions || !stickyActionsVisible) return;
    
    console.log('🫥 Ocultando botones sticky');
    elems.stickyActions.classList.remove('show');
    
    setTimeout(() => {
        if (!stickyActionsVisible) {
            elems.stickyActions.style.display = 'none';
        }
    }, 400);
    
    stickyActionsVisible = false;
}

/**
 * Actualiza los datos necesarios para los botones
 */
export function updateStickyData(keywordData, siteUrl) {
    currentKeywordData = keywordData;
    currentSiteUrl = siteUrl;
    
    // Actualizar estado del botón de IA - siempre habilitado para navegación
    if (elems.stickyAIBtn) {
        elems.stickyAIBtn.disabled = false;
        elems.stickyAIBtn.title = 'Navigate to AI Overview Analysis section';
    }
}

// ✅ Función de descarga Excel eliminada - ahora se maneja desde el sidebar

/**
 * Maneja el click en el botón de análisis IA - Navega a la sección
 */
function handleStickyAIAnalysis() {
    console.log('🤖 Navegando a sección AI Overview desde botón sticky');
    
    // ✅ NUEVO: Usar el sistema de navegación del sidebar
    if (window.showSection) {
        console.log('📍 Navegando a AI Overview usando el sistema del sidebar');
        window.showSection('ai-overview');
        
        // Scroll al top de la página
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
        // Fallback al método anterior
        console.log('📍 Fallback: Navegando usando scroll directo');
        scrollToAISection();
    }
}

/**
 * Realiza scroll suave a la sección de AI Overview
 */
function scrollToAISection() {
    const aiSection = document.getElementById('aiOverviewSection');
    if (aiSection) {
        // Asegurar que la sección sea visible antes del scroll
        if (aiSection.style.display === 'none') {
            aiSection.style.display = 'block';
        }
        
        aiSection.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start',
            inline: 'nearest'
        });
        
        console.log('📍 Navegando a sección AI Overview');
    } else {
        console.warn('Sección AI Overview no encontrada');
    }
}

/**
 * Establece el estado de loading de un botón sticky
 */
function setStickyButtonLoading(button, isLoading) {
    if (!button) return;
    
    const textElement = button.querySelector('.sticky-btn-text');
    const spinnerElement = button.querySelector('.sticky-btn-spinner');
    
    if (isLoading) {
        button.classList.add('loading');
        button.disabled = true;
        if (textElement) textElement.style.display = 'none';
        if (spinnerElement) spinnerElement.style.display = 'inline-flex';
    } else {
        button.classList.remove('loading');
        button.disabled = false;
        if (textElement) textElement.style.display = 'inline';
        if (spinnerElement) spinnerElement.style.display = 'none';
    }
}

/**
 * Muestra un estado de éxito temporal en un botón
 */
function showStickySuccess(button, message) {
    if (!button) return;
    
    const textElement = button.querySelector('.sticky-btn-text');
    const originalText = textElement ? textElement.textContent : '';
    
    // Cambiar temporalmente el texto y estilo
    button.classList.add('success');
    if (textElement) textElement.textContent = message;
    
    setTimeout(() => {
        button.classList.remove('success');
        if (textElement) textElement.textContent = originalText;
    }, 2000);
}

/**
 * Añade efecto de pulso al botón AI (para notificaciones)
 */
export function pulseStickyButton(buttonType = 'ai', duration = 3000) {
    const button = elems.stickyAIBtn;
    if (!button) return;
    
    button.classList.add('pulse');
    setTimeout(() => {
        button.classList.remove('pulse');
    }, duration);
}

/**
 * Verifica si los botones sticky están visibles
 */
export function areStickyActionsVisible() {
    return stickyActionsVisible;
}

// Exportar funciones principales (se dejaron vacías porque las funciones ya se exportan directamente)
export {
    // No es necesario exportar nada aquí ya que las funciones se exportan directamente.
};