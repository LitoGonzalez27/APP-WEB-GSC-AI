/* ==============================================
   COLLAPSIBLE SECTIONS SYSTEM
   Maneja el comportamiento de expandir/colapsar para secciones avanzadas
   ============================================== */

/**
 * Estado global de las secciones
 */
const collapsibleState = {
    competitor: false,
    exclusion: false,
    keywordFilter: false,
    topicClusters: false
};

/**
 * Alternar estado de una sección colapsable
 * @param {string} sectionType - Tipo de sección ('competitor' o 'exclusion')
 */
function toggleCollapsible(sectionType) {
    const content = document.getElementById(`${sectionType}Content`);
    const arrow = document.getElementById(`${sectionType}Arrow`);
    const summary = document.getElementById(`${sectionType}Summary`);
    
    if (!content || !arrow) {
        console.error(`Elementos no encontrados para sección: ${sectionType}`);
        return;
    }

    const isExpanded = collapsibleState[sectionType];
    
    if (isExpanded) {
        // Colapsar
        collapseSection(content, arrow, summary, sectionType);
    } else {
        // Expandir
        expandSection(content, arrow, summary, sectionType);
    }
    
    collapsibleState[sectionType] = !isExpanded;
    
    // Actualizar resumen cuando se colapsa
    if (isExpanded) {
        updateCollapsibleSummary(sectionType);
    }
}

/**
 * Expandir una sección
 * @param {HTMLElement} content - Contenido de la sección
 * @param {HTMLElement} arrow - Flecha indicadora
 * @param {HTMLElement} summary - Resumen de la sección
 * @param {string} sectionType - Tipo de sección
 */
function expandSection(content, arrow, summary, sectionType) {
    // Mostrar contenido con animación
    content.style.display = 'block';
    content.style.maxHeight = '0px';
    content.style.opacity = '0';
    
    // Forzar reflow
    content.offsetHeight;
    
    // Animar expansión
    content.style.transition = 'max-height 0.3s ease, opacity 0.3s ease';
    content.style.maxHeight = content.scrollHeight + 'px';
    content.style.opacity = '1';

    // Tras la animación, permitir crecimiento dinámico (evita que botones queden ocultos)
    setTimeout(() => {
        // Si sigue expandida esta sección, quitar límite de altura
        if (collapsibleState[sectionType] === false) { // aún estaba colapsada previo toggle
            // nada
        }
        // Permitir que el contenido crezca si se añaden chips/etiquetas dinámicamente
        content.style.maxHeight = 'none';
        content.style.overflow = 'visible';
    }, 320);
    
    // Rotar flecha
    arrow.style.transform = 'rotate(180deg)';
    
    // Ocultar resumen cuando está expandido
    if (summary) {
        summary.style.opacity = '0';
        summary.style.maxHeight = '0px';
    }
    
    console.log(`📖 Sección ${sectionType} expandida`);
}

/**
 * Colapsar una sección
 * @param {HTMLElement} content - Contenido de la sección
 * @param {HTMLElement} arrow - Flecha indicadora
 * @param {HTMLElement} summary - Resumen de la sección
 * @param {string} sectionType - Tipo de sección
 */
function collapseSection(content, arrow, summary, sectionType) {
    // Animar colapso
    // Si estaba sin límite, fijar altura actual para habilitar la transición a 0
    if (content.style.maxHeight === '' || content.style.maxHeight === 'none') {
        content.style.maxHeight = content.scrollHeight + 'px';
        // Forzar reflow antes de iniciar transición
        content.offsetHeight;
    }
    content.style.transition = 'max-height 0.3s ease, opacity 0.3s ease';
    content.style.maxHeight = '0px';
    content.style.opacity = '0';
    content.style.overflow = 'hidden';
    
    // Rotar flecha de vuelta
    arrow.style.transform = 'rotate(0deg)';
    
    // Mostrar resumen cuando está colapsado
    if (summary) {
        summary.style.opacity = '1';
        summary.style.maxHeight = 'none';
    }
    
    // Ocultar contenido después de la animación
    setTimeout(() => {
        if (!collapsibleState[sectionType]) {
            content.style.display = 'none';
        }
    }, 300);
    
    console.log(`📕 Sección ${sectionType} colapsada`);
}

/**
 * Actualizar el resumen de una sección colapsada
 * @param {string} sectionType - Tipo de sección
 */
function updateCollapsibleSummary(sectionType) {
    const summary = document.getElementById(`${sectionType}Summary`);
    if (!summary) return;
    
    let summaryText = '';
    
    if (sectionType === 'competitor') {
        const competitors = getCompetitorSummary();
        if (competitors.length > 0) {
            summaryText = `${competitors.length} competitor${competitors.length > 1 ? 's' : ''} added: ${competitors.join(', ')}`;
        } else {
            summaryText = 'Click to add competitor domains';
        }
    } else if (sectionType === 'exclusion') {
        const exclusions = getExclusionSummary();
        if (exclusions.count > 0) {
            summaryText = `${exclusions.count} exclusion${exclusions.count > 1 ? 's' : ''} (${exclusions.method}): ${exclusions.preview}`;
        } else {
            summaryText = 'Click to exclude brand terms or irrelevant keywords';
        }
    } else if (sectionType === 'keywordFilter') {
        const info = (window.getKwFilterSummaryInfo && window.getKwFilterSummaryInfo()) || { count: 0, method: '', preview: '' };
        if (info.count > 0) {
            summaryText = `${info.count} filter${info.count > 1 ? 's' : ''} (${info.method}): ${info.preview}`;
        } else {
            summaryText = 'Filter keywords by terms (optional)';
        }
    } else if (sectionType === 'topicClusters') {
        const clusters = getTopicClustersSummary();
        if (clusters.count > 0) {
            summaryText = `${clusters.count} cluster${clusters.count > 1 ? 's' : ''} (${clusters.method}): ${clusters.preview}`;
        } else {
            summaryText = 'Click to group keywords into clusters for AI Overview analysis';
        }
    }
    
    summary.textContent = summaryText;
}

/**
 * Obtener resumen de competidores
 * @returns {Array} Lista de dominios de competidores válidos
 */
function getCompetitorSummary() {
    const competitors = [];
    
    for (let i = 1; i <= 3; i++) {
        const input = document.getElementById(`competitor${i}`);
        if (input && input.value.trim()) {
            // Normalizar dominio para mostrar
            let domain = input.value.trim();
            domain = domain.replace(/^https?:\/\//, '').replace(/^www\./, '');
            if (domain.length > 20) {
                domain = domain.substring(0, 17) + '...';
            }
            competitors.push(domain);
        }
    }
    
    return competitors;
}

/**
 * Obtener resumen de exclusiones
 * @returns {Object} Información sobre las exclusiones
 */
function getExclusionSummary() {
    // Usar la función del sistema de tags si está disponible
    if (window.getExclusionSummaryInfo) {
        return window.getExclusionSummaryInfo();
    }
    
    // Fallback por si acaso
    return { count: 0, method: '', preview: '' };
}

/**
 * Inicializar sistema colapsable
 */
function initCollapsibleSections() {
    console.log('🔧 Inicializando sistema de secciones colapsables');
    
    // Asegurar que todas las secciones empiecen colapsadas
    ['competitor', 'exclusion', 'keywordFilter', 'topicClusters'].forEach(sectionType => {
        const content = document.getElementById(`${sectionType}Content`);
        const arrow = document.getElementById(`${sectionType}Arrow`);
        
        if (content) {
            content.style.display = 'none';
            content.style.maxHeight = '0px';
            content.style.opacity = '0';
        }
        
        if (arrow) {
            arrow.style.transform = 'rotate(0deg)';
            arrow.style.transition = 'transform 0.3s ease';
        }
        
        collapsibleState[sectionType] = false;
        updateCollapsibleSummary(sectionType);
    });
    
    // Añadir listeners para actualizar resúmenes
    setupSummaryUpdateListeners();
    
    console.log('✅ Sistema colapsable inicializado');
}

/**
 * Configurar listeners para actualizar resúmenes automáticamente
 */
function setupSummaryUpdateListeners() {
    // Listeners para competidores
    for (let i = 1; i <= 3; i++) {
        const input = document.getElementById(`competitor${i}`);
        if (input) {
            input.addEventListener('input', () => {
                if (!collapsibleState.competitor) {
                    updateCollapsibleSummary('competitor');
                }
            });
        }
    }
    
    // Los listeners para exclusiones ahora se manejan en keyword-exclusion.js
    // mediante el sistema de tags que llama automáticamente a updateCollapsibleSummary()

    // Listener para cambios del filtro de keywords
    document.addEventListener('kwFilterStateChanged', () => {
        if (!collapsibleState.keywordFilter) {
            updateCollapsibleSummary('keywordFilter');
        }
    });
}

/**
 * Obtener resumen de topic clusters
 * @returns {Object} Información sobre los clusters
 */
function getTopicClustersSummary() {
    // Usar la función del sistema de clusters si está disponible
    if (window.getTopicClustersSummaryInfo) {
        return window.getTopicClustersSummaryInfo();
    }
    
    // Fallback por si acaso
    return { count: 0, method: '', preview: '' };
}

/**
 * Función para expandir todas las secciones (útil para debugging)
 */
function expandAllSections() {
    ['competitor', 'exclusion', 'keywordFilter', 'topicClusters'].forEach(sectionType => {
        if (!collapsibleState[sectionType]) {
            toggleCollapsible(sectionType);
        }
    });
}

/**
 * Función para colapsar todas las secciones
 */
function collapseAllSections() {
    ['competitor', 'exclusion', 'keywordFilter', 'topicClusters'].forEach(sectionType => {
        if (collapsibleState[sectionType]) {
            toggleCollapsible(sectionType);
        }
    });
}

// Hacer funciones disponibles globalmente
window.toggleCollapsible = toggleCollapsible;
window.expandAllSections = expandAllSections;
window.collapseAllSections = collapseAllSections;
window.updateCollapsibleSummary = updateCollapsibleSummary;

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', initCollapsibleSections);

/**
 * Prevenir que el click en los iconos de información active otros comportamientos
 */
document.addEventListener('DOMContentLoaded', function() {
    const infoIcons = document.querySelectorAll('.analysis-info-icon');
    infoIcons.forEach(icon => {
        icon.addEventListener('click', function(event) {
            event.stopPropagation();
            event.preventDefault();
        });
        
        // Mejora para móviles - también funciona con touch
        icon.addEventListener('touchstart', function(event) {
            event.stopPropagation();
        });
    });
});
