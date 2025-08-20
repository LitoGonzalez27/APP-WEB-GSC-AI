// ================================
// TOOLTIPS FIX - URLs y Match Type
// ================================

// Función para el tooltip de URLs actualizada
function initUrlsInfoTooltip() {
    console.log('🔍 Iniciando initUrlsInfoTooltip...');
    
    const urlsLabel = document.querySelector('label[for="urlsInput"]');
    const urlsIcon = document.getElementById('urlsInfoIcon');
    
    console.log('🔍 Elementos encontrados:', {
        urlsLabel: !!urlsLabel,
        urlsIcon: !!urlsIcon,
        labelElement: urlsLabel,
        iconElement: urlsIcon
    });
    
    if (!urlsLabel || !urlsIcon) {
        console.error('❌ No se encontraron los elementos necesarios para el tooltip');
        return;
    }
    
    // Verificar si ya existe el tooltip
    const existingTooltip = document.getElementById('urlsInfoTooltip');
    if (existingTooltip) {
        console.log('⚠️ Tooltip ya existe, eliminando...');
        existingTooltip.remove();
    }
    
    // Crear el tooltip HTML con el nuevo contenido
    const tooltipHTML = `
        <div class="urls-info-tooltip" id="urlsInfoTooltip">
            <strong>ℹ️ URL Analysis Guide</strong>
            <p>When you leave the URL field empty, the analysis covers your entire Search Console property with all pages included. If you specify URLs, the system will filter data to show only pages that match your criteria. Enter one URL per line for multiple URL analysis. You can also use multiple paths.</p>
        </div>
    `;
    
    // Agregar el tooltip al label
    urlsLabel.insertAdjacentHTML('beforeend', tooltipHTML);
    
    const tooltip = document.getElementById('urlsInfoTooltip');
    console.log('🔍 Tooltip creado:', !!tooltip);
    
    // Funcionalidad de click
    urlsIcon.addEventListener('click', (e) => {
        console.log('🔍 Click en icono detectado');
        e.preventDefault();
        e.stopPropagation();
        tooltip.classList.toggle('active');
        console.log('🔍 Tooltip activo:', tooltip.classList.contains('active'));
    });
    
    // Agregar hover también
    urlsIcon.addEventListener('mouseenter', () => {
        console.log('🔍 Hover en icono detectado');
        tooltip.classList.add('active');
    });
    
    urlsIcon.addEventListener('mouseleave', () => {
        // Delay para permitir hover en el tooltip
        setTimeout(() => {
            if (!tooltip.matches(':hover')) {
                tooltip.classList.remove('active');
            }
        }, 100);
    });
    
    // Mantener abierto cuando se hace hover en el tooltip
    tooltip.addEventListener('mouseenter', () => {
        tooltip.classList.add('active');
    });
    
    tooltip.addEventListener('mouseleave', () => {
        tooltip.classList.remove('active');
    });
    
    // Cerrar al hacer click fuera
    document.addEventListener('click', (e) => {
        if (!urlsLabel.contains(e.target)) {
            tooltip.classList.remove('active');
        }
    });
    
    // Cerrar con ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            tooltip.classList.remove('active');
        }
    });
    
    console.log('✅ Tooltip del campo URLs inicializado correctamente');
}

// Nueva función para el tooltip de Match Type
function initMatchTypeInfoTooltip() {
    console.log('🔍 Iniciando initMatchTypeInfoTooltip...');
    
    const matchTypeLabel = document.querySelector('label[for="matchTypeGroup"]');
    const matchTypeIcon = document.getElementById('matchTypeInfoIcon');
    
    console.log('🔍 Elementos encontrados:', {
        matchTypeLabel: !!matchTypeLabel,
        matchTypeIcon: !!matchTypeIcon
    });
    
    if (!matchTypeLabel || !matchTypeIcon) {
        console.error('❌ No se encontraron los elementos necesarios para el tooltip de Match Type');
        return;
    }
    
    // Verificar si ya existe el tooltip
    const existingTooltip = document.getElementById('matchTypeInfoTooltip');
    if (existingTooltip) {
        console.log('⚠️ Tooltip Match Type ya existe, eliminando...');
        existingTooltip.remove();
    }
    
    // Crear el tooltip HTML
    const tooltipHTML = `
        <div class="urls-info-tooltip" id="matchTypeInfoTooltip">
            <strong>ℹ️ Match Type Options</strong>
            <p>Use <em>Contains</em> to find pages that include your specified text anywhere in the URL, <em>Equals</em> for exact URL matches (use it to analyze multiple URLs), or <em>Not Contains</em> to exclude pages that contain your specified text.</p>
        </div>
    `;
    
    // Agregar el tooltip al label
    matchTypeLabel.insertAdjacentHTML('beforeend', tooltipHTML);
    
    const tooltip = document.getElementById('matchTypeInfoTooltip');
    console.log('🔍 Tooltip Match Type creado:', !!tooltip);
    
    // Funcionalidad de click
    matchTypeIcon.addEventListener('click', (e) => {
        console.log('🔍 Click en icono Match Type detectado');
        e.preventDefault();
        e.stopPropagation();
        tooltip.classList.toggle('active');
        console.log('🔍 Tooltip Match Type activo:', tooltip.classList.contains('active'));
    });
    
    // Agregar hover también
    matchTypeIcon.addEventListener('mouseenter', () => {
        console.log('🔍 Hover en icono Match Type detectado');
        tooltip.classList.add('active');
    });
    
    matchTypeIcon.addEventListener('mouseleave', () => {
        // Delay para permitir hover en el tooltip
        setTimeout(() => {
            if (!tooltip.matches(':hover')) {
                tooltip.classList.remove('active');
            }
        }, 100);
    });
    
    // Mantener abierto cuando se hace hover en el tooltip
    tooltip.addEventListener('mouseenter', () => {
        tooltip.classList.add('active');
    });
    
    tooltip.addEventListener('mouseleave', () => {
        tooltip.classList.remove('active');
    });
    
    // Cerrar al hacer click fuera
    document.addEventListener('click', (e) => {
        if (!matchTypeLabel.contains(e.target)) {
            tooltip.classList.remove('active');
        }
    });
    
    // Cerrar con ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            tooltip.classList.remove('active');
        }
    });
    
    console.log('✅ Tooltip del Match Type inicializado correctamente');
}

// Inicializar ambos tooltips cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Inicializando tooltips personalizados...');
    
    // Usar timeout para asegurar que los elementos estén disponibles
    setTimeout(() => {
        initUrlsInfoTooltip();
        initMatchTypeInfoTooltip();
    }, 600); // Un poco más de delay que el original
});

// Hacer funciones disponibles globalmente
window.initUrlsInfoTooltip = initUrlsInfoTooltip;
window.initMatchTypeInfoTooltip = initMatchTypeInfoTooltip;