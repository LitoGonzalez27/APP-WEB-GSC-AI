// static/js/ui-ai-overview-pdf.js
// Módulo para generar PDF del análisis AI Overview con marca de agua Clicandseo
// v2: Preparar DOM antes de captura para fix chart/URLs/grid issues

/**
 * Convierte todos los canvas de Chart.js a imágenes estáticas para captura limpia.
 * Returns array of originals para restaurar después.
 */
function convertChartsToImages(container) {
    const canvases = container.querySelectorAll('canvas');
    const originals = [];

    canvases.forEach(canvas => {
        try {
            const img = document.createElement('img');
            img.src = canvas.toDataURL('image/png');
            img.style.width = (canvas.offsetWidth || canvas.width) + 'px';
            img.style.height = (canvas.offsetHeight || canvas.height) + 'px';
            img.style.display = 'block';
            img.className = 'pdf-chart-img-temp';
            canvas.parentNode.insertBefore(img, canvas);
            canvas.style.display = 'none';
            originals.push({ canvas, img });
        } catch (e) {
            console.warn('⚠️ Canvas conversion failed:', e);
        }
    });

    return originals;
}

/**
 * Restaura canvas de Chart.js eliminando las imágenes temporales.
 */
function restoreCharts(originals) {
    originals.forEach(({ canvas, img }) => {
        canvas.style.display = '';
        if (img.parentNode) img.parentNode.removeChild(img);
    });
}

/**
 * Expande todas las páginas de paginación de URLs para que aparezcan en el PDF.
 * Returns array of originals para restaurar después.
 */
function expandAllPagination(container) {
    const hiddenPages = container.querySelectorAll('.cited-urls-page-2');
    const originals = [];

    hiddenPages.forEach(el => {
        originals.push({ el, display: el.style.display });
        el.style.display = '';  // Mostrar todas las páginas
    });

    return originals;
}

/**
 * Restaura la paginación ocultando las páginas que estaban ocultas.
 */
function restorePagination(originals) {
    originals.forEach(({ el, display }) => {
        el.style.display = display;
    });
}

/**
 * Prepara el DOM para captura de PDF:
 * - Convierte Chart.js canvas a imágenes estáticas
 * - Expande paginación de URLs
 * - Añade clase pdf-capture-mode al body
 * - Fuerza min-width para evitar colapso de grid
 */
function prepareDOMForPDF(container) {
    const state = {
        chartOriginals: [],
        paginationOriginals: [],
        containerMinWidth: container.style.minWidth,
        containerWidth: container.style.width
    };

    // 1. Convertir charts a imágenes
    state.chartOriginals = convertChartsToImages(container);
    console.log(`📊 ${state.chartOriginals.length} chart(s) convertidos a imagen`);

    // 2. Expandir paginación
    state.paginationOriginals = expandAllPagination(container);
    console.log(`📄 ${state.paginationOriginals.length} página(s) de paginación expandidas`);

    // 3. Añadir clase de captura al body
    document.body.classList.add('pdf-capture-mode');

    // 4. Forzar ancho mínimo para evitar colapso de grid
    container.style.minWidth = '1100px';
    container.style.width = '1100px';

    return state;
}

/**
 * Restaura el DOM al estado original después de la captura.
 */
function restoreDOMAfterPDF(container, state) {
    // 1. Restaurar charts
    restoreCharts(state.chartOriginals);

    // 2. Restaurar paginación
    restorePagination(state.paginationOriginals);

    // 3. Quitar clase de captura
    document.body.classList.remove('pdf-capture-mode');

    // 4. Restaurar width
    container.style.minWidth = state.containerMinWidth || '';
    container.style.width = state.containerWidth || '';
}

/**
 * Genera y descarga un PDF de la sección AI Overview actual.
 * Incluye marca de agua de Clicandseo en cada página.
 */
export async function generateAIOverviewPDF() {
    let domState = null;
    let targetSection = null;

    try {
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');

        console.log('📄 Iniciando generación de PDF para AI Overview...');

        // Mostrar estado de carga
        if (spinner && btnText) {
            spinner.style.display = 'inline-block';
            btnText.textContent = 'Preparing PDF...';
        }
        if (btn) btn.disabled = true;

        // Verificar que hay datos de AI Overview disponibles
        const aiSection = document.getElementById('aiOverviewSection');
        const aiResults = document.getElementById('aiOverviewResultsContainer');

        if (!aiSection || !aiResults || aiResults.style.display === 'none') {
            throw new Error('No AI Overview data to export. Please run an AI analysis first.');
        }

        // Ocultar elementos excluidos del PDF
        const excluded = Array.from(document.querySelectorAll('[data-pdf-exclude="true"]'));
        const prevDisplay = new Map();
        excluded.forEach(el => {
            prevDisplay.set(el, el.style.display);
            el.style.display = 'none';
        });

        // Ocultar overlay y botones de acción
        const aiOverlay = document.getElementById('aiOverlay');
        const resetBtn = document.getElementById('resetAIAnalysisBtn');
        const stickyActions = document.getElementById('stickyActions');

        const tempHidden = [];
        [aiOverlay, resetBtn, stickyActions].forEach(el => {
            if (el && el.style.display !== 'none') {
                tempHidden.push({ el, display: el.style.display });
                el.style.display = 'none';
            }
        });

        // Cargar librerías necesarias
        console.log('📦 Cargando html2canvas...');
        const [{ default: html2canvas }] = await Promise.all([
            import('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.esm.js')
        ]);

        // Cargar jsPDF si no está disponible
        if (!window.jspdf || !window.jspdf.jsPDF) {
            console.log('📦 Cargando jsPDF...');
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js';
                script.onload = () => resolve();
                script.onerror = () => reject(new Error('Failed to load jsPDF'));
                document.head.appendChild(script);
            });
        }

        // ====== FASE 1: Preparar DOM para captura ======
        targetSection = document.getElementById('aiOverviewContent');
        console.log('🔧 Preparando DOM para captura PDF...');
        domState = prepareDOMForPDF(targetSection);

        // Pequeña pausa para que el navegador repinte el layout
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

        // ====== FASE 2: Capturar DOM preparado ======
        console.log('🎨 Generando canvas de la sección AI Overview...');
        const canvas = await html2canvas(targetSection, {
            scale: 1.5,
            useCORS: true,
            backgroundColor: '#ffffff',
            logging: false,
            windowWidth: Math.max(targetSection.scrollWidth, 1100),
            windowHeight: targetSection.scrollHeight
        });

        // ====== FASE 3: Restaurar DOM ======
        console.log('🔄 Restaurando DOM...');
        restoreDOMAfterPDF(targetSection, domState);
        domState = null; // Marcar como restaurado

        // Restaurar elementos ocultos
        excluded.forEach(el => {
            el.style.display = prevDisplay.get(el) || '';
        });
        tempHidden.forEach(({ el, display }) => {
            el.style.display = display;
        });

        // ====== FASE 4: Generar PDF ======
        console.log('📄 Creando documento PDF...');
        const imgData = canvas.toDataURL('image/jpeg', 0.85);

        const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const imgWidth = pageWidth;
        const imgHeight = canvas.height * (imgWidth / canvas.width);

        let position = 0;
        let heightLeft = imgHeight;

        // Añadir primera página
        pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);

        /**
         * Función para añadir marca de agua (logo Clicandseo) en esquina inferior derecha
         */
        const addWatermark = async () => {
            try {
                const logoEl = document.querySelector('.navbar .logo-image');
                const logoSrc = logoEl?.src || '/static/images/logos/logo%20clicandseo.png';
                const logoImg = new Image();
                logoImg.crossOrigin = 'anonymous';

                await new Promise((resolve) => {
                    logoImg.onload = resolve;
                    logoImg.onerror = resolve;
                    logoImg.src = logoSrc;
                });

                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = logoImg.naturalWidth || 0;
                tempCanvas.height = logoImg.naturalHeight || 0;

                if (tempCanvas.width && tempCanvas.height) {
                    const ctx = tempCanvas.getContext('2d');
                    ctx.drawImage(logoImg, 0, 0);
                    const dataUrl = tempCanvas.toDataURL('image/png');

                    // Configuración de la marca de agua
                    const margin = 16; // pt
                    const maxLogoWidth = Math.min(80, pageWidth * 0.18);
                    const ratio = (logoImg.naturalHeight || 1) / (logoImg.naturalWidth || 1);
                    const logoW = maxLogoWidth;
                    const logoH = logoW * ratio;
                    const x = pageWidth - logoW - margin;
                    const y = pageHeight - logoH - margin;

                    try {
                        pdf.addImage(dataUrl, 'PNG', x, y, logoW, logoH);
                    } catch (err) {
                        console.warn('⚠️ Error al añadir marca de agua:', err);
                    }
                }
            } catch (err) {
                console.warn('⚠️ No se pudo cargar la marca de agua:', err);
            }
        };

        // Añadir marca de agua a la primera página
        await addWatermark();

        // Añadir páginas adicionales si es necesario
        heightLeft -= pageHeight;
        while (heightLeft > 0) {
            position = heightLeft - imgHeight;
            pdf.addPage();
            pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);
            await addWatermark();
            heightLeft -= pageHeight;
        }

        // Generar nombre de archivo con timestamp
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const siteUrl = document.getElementById('siteUrlSelect')?.value || 'site';
        const siteName = siteUrl.replace(/^https?:\/\//i, '').replace(/[^a-z0-9]/gi, '_').substring(0, 30);
        const fileName = `ai_overview_${siteName}_${timestamp}.pdf`;

        console.log(`💾 Guardando PDF: ${fileName}`);
        pdf.save(fileName);

        console.log('✅ PDF generado exitosamente');
        showSuccessMessage('PDF downloaded successfully!');

    } catch (err) {
        console.error('❌ Error generating PDF:', err);
        alert(`Error generating PDF: ${err.message}`);

        // Restaurar DOM si falló antes de la restauración
        if (domState && targetSection) {
            try {
                restoreDOMAfterPDF(targetSection, domState);
            } catch (restoreErr) {
                console.error('❌ Error restaurando DOM:', restoreErr);
            }
        }
    } finally {
        // Asegurar que pdf-capture-mode se quita siempre
        document.body.classList.remove('pdf-capture-mode');

        // Restaurar estado del botón
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');

        if (spinner && btnText) {
            spinner.style.display = 'none';
            btnText.textContent = 'Download PDF';
        }
        if (btn) btn.disabled = false;
    }
}

/**
 * Muestra un mensaje de éxito temporal
 */
function showSuccessMessage(message) {
    const existingMsg = document.querySelector('.pdf-success-message');
    if (existingMsg) existingMsg.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'pdf-success-message';
    msgDiv.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: #28a745;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        font-size: 14px;
        font-weight: 500;
        animation: slideInRight 0.3s ease-out;
    `;
    msgDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    document.body.appendChild(msgDiv);

    setTimeout(() => {
        msgDiv.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => msgDiv.remove(), 300);
    }, 3000);
}

// Añadir animaciones CSS si no existen
if (!document.getElementById('pdf-animations')) {
    const style = document.createElement('style');
    style.id = 'pdf-animations';
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOutRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}
