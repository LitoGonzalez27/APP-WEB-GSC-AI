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
    
    if (!elems.stickyDownloadBtn || !elems.stickyAIBtn) {
        console.warn('Elementos sticky no encontrados');
        return;
    }

    // Event listener para descarga Excel
    elems.stickyDownloadBtn.addEventListener('click', handleStickyExcelDownload);
    
    // Event listener para análisis IA
    elems.stickyAIBtn.addEventListener('click', handleStickyAIAnalysis);

    // Tooltips para móvil
    elems.stickyDownloadBtn.setAttribute('data-tooltip', 'Descargar Excel');
    elems.stickyAIBtn.setAttribute('data-tooltip', 'Análisis IA');

    console.log('✅ Botones sticky inicializados correctamente');
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
    
    // Actualizar estado del botón de IA según disponibilidad de datos
    if (elems.stickyAIBtn) {
        const hasKeywordData = keywordData && Array.isArray(keywordData) && keywordData.length > 0;
        elems.stickyAIBtn.disabled = !hasKeywordData || !siteUrl;
        
        if (!hasKeywordData) {
            elems.stickyAIBtn.title = 'No hay datos de keywords para analizar';
        } else if (!siteUrl) {
            elems.stickyAIBtn.title = 'Selecciona un dominio primero';
        } else {
            elems.stickyAIBtn.title = 'Analizar impacto de AI Overview';
        }
    }
}

/**
 * Maneja el click en el botón de descarga Excel
 */
async function handleStickyExcelDownload() {
    console.log('📥 Iniciando descarga Excel desde botón sticky');
    
    if (!window.currentData || !window.currentData.pages) {
        alert('No hay datos para descargar. Por favor, ejecuta primero una consulta.');
        return;
    }

    // Cambiar estado del botón a loading
    setStickyButtonLoading(elems.stickyDownloadBtn, true);

    try {
        // ✅ SOLUCIÓN ROBUSTA: Manejar diferentes estructuras de datos AI Overview
        let aiOverviewDataToDownload = null;
        
        if (window.currentAIOverviewData) {
            console.log('🔍 Procesando datos AI Overview para descarga...', window.currentAIOverviewData);
            
            // Caso 1: La estructura tiene 'analysis' que contiene 'results' y 'summary'
            if (window.currentAIOverviewData.analysis) {
                aiOverviewDataToDownload = {
                    results: window.currentAIOverviewData.analysis.results || 
                             window.currentAIOverviewData.keywordResults || 
                             [],
                    summary: window.currentAIOverviewData.analysis.summary || 
                             window.currentAIOverviewData.summary || 
                             {}
                };
                console.log('✅ Estructura detectada: analysis.results/summary');
            }
            // Caso 2: La estructura ya tiene 'results' y 'summary' directamente
            else if (window.currentAIOverviewData.results && window.currentAIOverviewData.summary) {
                aiOverviewDataToDownload = {
                    results: window.currentAIOverviewData.results,
                    summary: window.currentAIOverviewData.summary
                };
                console.log('✅ Estructura detectada: results/summary directa');
            }
            // Caso 3: Intento de rescate con keywordResults
            else if (window.currentAIOverviewData.keywordResults) {
                aiOverviewDataToDownload = {
                    results: window.currentAIOverviewData.keywordResults,
                    summary: window.currentAIOverviewData.summary || {}
                };
                console.log('✅ Estructura detectada: keywordResults');
            }
            // Caso 4: Estructura no reconocida, intentar usar tal cual
            else {
                console.warn('⚠️ Estructura AI Overview no reconocida, usando tal cual');
                aiOverviewDataToDownload = window.currentAIOverviewData;
            }
            
            // Log de verificación
            console.log('📊 Datos AI Overview preparados para descarga:', {
                tieneResults: !!aiOverviewDataToDownload?.results,
                resultsCount: aiOverviewDataToDownload?.results?.length || 0,
                tieneSummary: !!aiOverviewDataToDownload?.summary,
                summaryKeys: aiOverviewDataToDownload?.summary ? Object.keys(aiOverviewDataToDownload.summary) : []
            });
        } else {
            console.log('ℹ️ No hay datos de AI Overview para incluir en el Excel');
        }

        const payload = {
            data: window.currentData,
            ai_overview_data: aiOverviewDataToDownload,
            metadata: {
                site_url: elems.siteUrlSelect ? elems.siteUrlSelect.value : '',
                months: [...document.querySelectorAll('.chip.selected')].map(c => c.dataset.value),
                generated_at: new Date().toISOString()
            }
        };

        const resp = await fetch('/download-excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            const errorData = await resp.json().catch(() => ({ error: "Error al parsear respuesta del servidor" }));
            let alertMessage = `Error al generar Excel: ${errorData.error || resp.statusText}`;
            if (errorData.reauth_required) {
                alertMessage += "\nLa autenticación con Google ha fallado o expirado. Por favor, recarga la página para re-autenticar.";
            }
            alert(alertMessage);
            return;
        }

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        const hasAI = aiOverviewDataToDownload ? '_con_AI' : '';
        a.download = `search_console_report${hasAI}_${timestamp}.xlsx`;

        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();

        // Mostrar éxito temporal
        showStickySuccess(elems.stickyDownloadBtn, 'Descargado!');

    } catch (e) {
        console.error("Error en la descarga de Excel:", e);
        alert('Se produjo un error inesperado al intentar descargar el archivo Excel.');
    } finally {
        setStickyButtonLoading(elems.stickyDownloadBtn, false);
    }
}

/**
 * Maneja el click en el botón de análisis IA
 */
async function handleStickyAIAnalysis() {
    console.log('🤖 Iniciando análisis IA desde botón sticky');
    
    if (!currentKeywordData || !currentSiteUrl) {
        alert('No hay datos de keywords para analizar. Ejecuta primero una consulta.');
        return;
    }

    if (!Array.isArray(currentKeywordData) || currentKeywordData.length === 0) {
        alert('No hay keywords disponibles para el análisis de IA.');
        return;
    }

    // Cambiar estado del botón a loading
    setStickyButtonLoading(elems.stickyAIBtn, true);

    try {
        // Llamar a la función de análisis IA existente
        const { runAIOverviewAnalysis } = await import('./ui-ai-overview.js');
        
        if (typeof runAIOverviewAnalysis === 'function') {
            await runAIOverviewAnalysis(currentKeywordData, currentSiteUrl);
            
            // Scroll suave a la sección de IA Overview
            scrollToAISection();
            
            // Mostrar éxito temporal
            showStickySuccess(elems.stickyAIBtn, 'Completado!');
        } else {
            throw new Error('Función de análisis IA no disponible');
        }

    } catch (error) {
        console.error('Error en análisis IA:', error);
        alert('Error al ejecutar el análisis de IA: ' + error.message);
    } finally {
        setStickyButtonLoading(elems.stickyAIBtn, false);
    }
}

/**
 * Realiza scroll suave a la sección de AI Overview
 */
function scrollToAISection() {
    const aiSection = document.getElementById('aiOverviewSection');
    if (aiSection && aiSection.style.display !== 'none') {
        aiSection.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start',
            inline: 'nearest'
        });
        
        console.log('📍 Navegando a sección AI Overview');
    } else {
        console.warn('Sección AI Overview no visible o no encontrada');
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
 * Añade efecto de pulso a un botón (para notificaciones)
 */
export function pulseStickyButton(buttonType, duration = 3000) {
    const button = buttonType === 'ai' ? elems.stickyAIBtn : elems.stickyDownloadBtn;
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