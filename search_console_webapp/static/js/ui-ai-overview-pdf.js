// static/js/ui-ai-overview-pdf.js
// Módulo para generar PDF del análisis AI Overview con marca de agua Clicandseo
// v3: Simplified DOM preparation — no forced widths, safe chart/pagination handling

/**
 * Convierte todos los canvas de Chart.js a imágenes estáticas para captura limpia.
 * html2canvas a menudo captura canvas en blanco — convertir a <img> lo evita.
 */
function convertChartsToImages(container) {
    const canvases = container.querySelectorAll('canvas');
    const originals = [];

    canvases.forEach(canvas => {
        try {
            // Intentar obtener el contenido del canvas como imagen
            const dataUrl = canvas.toDataURL('image/png');

            // Solo reemplazar si el canvas tiene contenido (no es blank)
            if (dataUrl && dataUrl !== 'data:,') {
                const img = document.createElement('img');
                img.src = dataUrl;
                img.style.width = canvas.offsetWidth + 'px';
                img.style.height = canvas.offsetHeight + 'px';
                img.style.display = 'block';
                img.className = 'pdf-chart-img-temp';

                canvas.parentNode.insertBefore(img, canvas);
                canvas.style.display = 'none';
                originals.push({ canvas, img, parent: canvas.parentNode });
            }
        } catch (e) {
            console.warn('⚠️ Canvas conversion failed (CORS?):', e);
        }
    });

    return originals;
}

/**
 * Restaura canvas de Chart.js eliminando las imágenes temporales.
 */
function restoreCharts(originals) {
    originals.forEach(({ canvas, img }) => {
        try {
            canvas.style.display = '';
            if (img && img.parentNode) {
                img.parentNode.removeChild(img);
            }
        } catch (e) {
            console.warn('⚠️ Error restoring chart:', e);
        }
    });
}

/**
 * Expande todas las páginas de paginación de URLs para que aparezcan completas en el PDF.
 */
function expandAllPagination(container) {
    // Show all hidden pagination pages
    const hiddenPages = container.querySelectorAll('.cited-urls-page-2');
    const originals = [];

    hiddenPages.forEach(el => {
        originals.push({ el, display: el.style.display });
        el.style.display = '';
    });

    // Also show page 1 if it was hidden (when user was on page 2)
    const page1Elements = container.querySelectorAll('.cited-urls-page-1');
    page1Elements.forEach(el => {
        if (el.style.display === 'none') {
            originals.push({ el, display: el.style.display });
            el.style.display = '';
        }
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
 * Prepara el DOM para captura de PDF (lightweight approach):
 * - Convierte Chart.js canvas a imágenes estáticas
 * - Expande paginación de URLs
 * - Añade clase pdf-capture-mode al body (for URL overflow + pagination hide)
 * NO fuerza width changes — html2canvas se encarga del sizing
 */
function prepareDOMForPDF(container) {
    const state = {
        chartOriginals: [],
        paginationOriginals: []
    };

    // 1. Convertir charts a imágenes estáticas
    state.chartOriginals = convertChartsToImages(container);
    console.log(`📊 ${state.chartOriginals.length} chart(s) convertidos a imagen estática`);

    // 2. Expandir paginación
    state.paginationOriginals = expandAllPagination(container);
    console.log(`📄 ${state.paginationOriginals.length} elemento(s) de paginación expandidos`);

    // 3. Añadir clase de captura al body (CSS handles overflow + pagination buttons)
    document.body.classList.add('pdf-capture-mode');

    return state;
}

/**
 * Restaura el DOM al estado original después de la captura.
 */
function restoreDOMAfterPDF(state) {
    // 1. Restaurar charts
    restoreCharts(state.chartOriginals);

    // 2. Restaurar paginación
    restorePagination(state.paginationOriginals);

    // 3. Quitar clase de captura
    document.body.classList.remove('pdf-capture-mode');
}

/**
 * Genera y descarga un PDF de la sección AI Overview actual.
 * Incluye marca de agua de Clicandseo en cada página.
 */
export async function generateAIOverviewPDF() {
    let domState = null;

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

        // Ocultar overlay, botones de acción y sección de configuración avanzada
        const aiOverlay = document.getElementById('aiOverlay');
        const resetBtn = document.getElementById('resetAIAnalysisBtn');
        const stickyActions = document.getElementById('stickyActions');
        const advancedSection = document.getElementById('advancedAnalysisSection');

        const tempHidden = [];
        [aiOverlay, resetBtn, stickyActions, advancedSection].forEach(el => {
            if (el) {
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
        const targetSection = document.getElementById('aiOverviewContent');
        if (!targetSection) {
            throw new Error('AI Overview content section not found');
        }

        console.log('🔧 Preparando DOM para captura PDF...');
        domState = prepareDOMForPDF(targetSection);

        // Esperar a que el navegador repinte (DOM changes need layout recalc)
        await new Promise(resolve => setTimeout(resolve, 300));

        // ====== FASE 2: Capturar DOM preparado ======
        console.log('🎨 Generando canvas de la sección AI Overview...');

        // Scroll al inicio de la sección para capturar completo
        targetSection.scrollTop = 0;

        const canvas = await html2canvas(targetSection, {
            scale: 1.5,
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#ffffff',
            logging: false,
            imageTimeout: 15000,
            removeContainer: true,
            width: targetSection.scrollWidth,
            height: targetSection.scrollHeight,
            scrollX: 0,
            scrollY: -window.scrollY
        });

        console.log(`📐 Canvas generado: ${canvas.width}x${canvas.height}px`);

        // ====== FASE 3: Restaurar DOM ======
        console.log('🔄 Restaurando DOM...');
        restoreDOMAfterPDF(domState);
        domState = null;

        // Restaurar elementos ocultos
        excluded.forEach(el => {
            el.style.display = prevDisplay.get(el) || '';
        });
        tempHidden.forEach(({ el, display }) => {
            el.style.display = display;
        });

        // ====== FASE 4: Generar PDF ======
        console.log('📄 Creando documento PDF...');

        // Verificar que el canvas tiene contenido
        if (canvas.width === 0 || canvas.height === 0) {
            throw new Error('Canvas capture failed - empty dimensions');
        }

        const imgData = canvas.toDataURL('image/jpeg', 0.85);

        const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const margin = 20;
        const usableWidth = pageWidth - (margin * 2);
        const imgWidth = usableWidth;
        const imgHeight = canvas.height * (imgWidth / canvas.width);

        let yOffset = margin;
        let heightLeft = imgHeight;

        // Función para añadir marca de agua (logo Clicandseo) en esquina inferior derecha
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

                    const wmMargin = 16;
                    const maxLogoWidth = Math.min(80, pageWidth * 0.18);
                    const ratio = (logoImg.naturalHeight || 1) / (logoImg.naturalWidth || 1);
                    const logoW = maxLogoWidth;
                    const logoH = logoW * ratio;
                    const x = pageWidth - logoW - wmMargin;
                    const y = pageHeight - logoH - wmMargin;

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

        // Primera página
        pdf.addImage(imgData, 'JPEG', margin, yOffset, imgWidth, imgHeight);
        await addWatermark();

        // Páginas adicionales
        heightLeft -= (pageHeight - margin);
        while (heightLeft > 0) {
            pdf.addPage();
            const newY = margin - (imgHeight - heightLeft);
            pdf.addImage(imgData, 'JPEG', margin, newY, imgWidth, imgHeight);
            await addWatermark();
            heightLeft -= (pageHeight - (margin * 2));
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
        if (domState) {
            try {
                restoreDOMAfterPDF(domState);
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
