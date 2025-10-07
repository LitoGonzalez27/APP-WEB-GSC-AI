// static/js/ui-ai-overview-pdf.js
// Módulo para generar PDF del análisis AI Overview con marca de agua Clicandseo

/**
 * Genera y descarga un PDF de la sección AI Overview actual
 * Incluye marca de agua de Clicandseo en cada página
 */
export async function generateAIOverviewPDF() {
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

        // Ocultar elementos que no deben aparecer en el PDF
        const excluded = Array.from(document.querySelectorAll('[data-pdf-exclude="true"]'));
        const prevDisplay = new Map();
        excluded.forEach(el => {
            prevDisplay.set(el, el.style.display);
            el.style.display = 'none';
        });

        // También ocultar el overlay y botones de acción si están visibles
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

        console.log('🎨 Generando canvas de la sección AI Overview...');
        
        // Generar canvas del contenido de AI Overview
        const targetSection = document.getElementById('aiOverviewContent');
        const canvas = await html2canvas(targetSection, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff',
            logging: false,
            windowWidth: targetSection.scrollWidth,
            windowHeight: targetSection.scrollHeight
        });

        console.log('📄 Creando documento PDF...');
        const imgData = canvas.toDataURL('image/jpeg', 0.92);

        // Crear PDF
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
                        console.log('✅ Marca de agua añadida correctamente');
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

        // Restaurar elementos ocultos
        excluded.forEach(el => {
            el.style.display = prevDisplay.get(el) || '';
        });
        tempHidden.forEach(({ el, display }) => {
            el.style.display = display;
        });

        console.log('✅ PDF generado exitosamente');
        
        // Mostrar mensaje de éxito breve
        showSuccessMessage('PDF downloaded successfully!');

    } catch (err) {
        console.error('❌ Error generating PDF:', err);
        alert(`Error generating PDF: ${err.message}`);
    } finally {
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

