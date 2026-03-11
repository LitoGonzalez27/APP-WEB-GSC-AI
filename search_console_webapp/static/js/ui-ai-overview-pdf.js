// static/js/ui-ai-overview-pdf.js
// Módulo para generar PDF del análisis AI Overview con marca de agua Clicandseo
// v4: Structured multi-page layout — each section captured individually

// ======================================================
// DOM PREPARATION HELPERS
// ======================================================

/**
 * Convierte todos los canvas de Chart.js a imágenes estáticas para captura limpia.
 * html2canvas a menudo captura canvas en blanco — convertir a <img> lo evita.
 */
function convertChartsToImages(container) {
    const canvases = container.querySelectorAll('canvas');
    const originals = [];

    canvases.forEach(canvas => {
        try {
            const dataUrl = canvas.toDataURL('image/png');
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
            console.warn('Canvas conversion failed (CORS?):', e);
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
            console.warn('Error restoring chart:', e);
        }
    });
}

/**
 * Expande todas las páginas de paginación de URLs para que aparezcan completas en el PDF.
 */
function expandAllPagination(container) {
    const hiddenPages = container.querySelectorAll('.cited-urls-page-2');
    const originals = [];

    hiddenPages.forEach(el => {
        originals.push({ el, display: el.style.display });
        el.style.display = '';
    });

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

// ======================================================
// SECTION CAPTURE
// ======================================================

/**
 * Captura un elemento DOM como imagen usando html2canvas.
 * Returns { canvas, imgData } or null if element not found / capture fails.
 */
async function captureSection(html2canvas, element, label) {
    if (!element) {
        console.warn(`Section "${label}" not found — skipping`);
        return null;
    }

    // Ensure element is visible and has dimensions
    if (element.offsetHeight === 0 || element.offsetWidth === 0) {
        console.warn(`Section "${label}" has zero dimensions — skipping`);
        return null;
    }

    console.log(`  Capturing: ${label} (${element.offsetWidth}x${element.offsetHeight}px)`);

    try {
        const canvas = await html2canvas(element, {
            scale: 1.5,
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#ffffff',
            logging: false,
            imageTimeout: 15000,
            removeContainer: true,
            width: element.scrollWidth,
            height: element.scrollHeight,
            scrollX: 0,
            scrollY: 0,
            x: 0,
            y: 0
        });

        if (canvas.width === 0 || canvas.height === 0) {
            console.warn(`Section "${label}" captured empty canvas — skipping`);
            return null;
        }

        const imgData = canvas.toDataURL('image/jpeg', 0.85);
        return { canvas, imgData, label };
    } catch (err) {
        console.warn(`Section "${label}" capture failed:`, err);
        return null;
    }
}

// ======================================================
// PDF PAGE COMPOSITION
// ======================================================

/**
 * Adds a captured section image to the current PDF page.
 * Handles scaling to fit page width and returns the new Y offset.
 * If the section doesn't fit, adds a new page first.
 *
 * @returns {number} new yOffset after placing the image
 */
function placeImageOnPage(pdf, imgData, canvasW, canvasH, margin, usableWidth, pageHeight, yOffset) {
    const imgWidth = usableWidth;
    const imgHeight = canvasH * (imgWidth / canvasW);

    // Check if we need a new page
    if (yOffset + imgHeight > pageHeight - margin) {
        // If image is taller than a full page, scale it down to fit one page
        if (imgHeight > pageHeight - (margin * 2)) {
            const maxH = pageHeight - (margin * 2);
            const scale = maxH / imgHeight;
            const scaledW = imgWidth * scale;
            const scaledH = maxH;
            const xOffset = margin + (usableWidth - scaledW) / 2; // center
            pdf.addImage(imgData, 'JPEG', xOffset, yOffset, scaledW, scaledH);
            return yOffset + scaledH + 8;
        }
        // Normal case: start new page
        pdf.addPage();
        yOffset = margin;
    }

    pdf.addImage(imgData, 'JPEG', margin, yOffset, imgWidth, imgHeight);
    return yOffset + imgHeight + 8; // 8pt gap between sections
}

/**
 * Carga y añade marca de agua (logo Clicandseo) en esquina inferior derecha.
 * Caches logo data across pages for performance.
 */
let _cachedLogoData = null;

async function loadWatermarkLogo() {
    if (_cachedLogoData) return _cachedLogoData;

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
            _cachedLogoData = {
                dataUrl: tempCanvas.toDataURL('image/png'),
                ratio: (logoImg.naturalHeight || 1) / (logoImg.naturalWidth || 1)
            };
            return _cachedLogoData;
        }
    } catch (err) {
        console.warn('Could not load watermark logo:', err);
    }
    return null;
}

function addWatermark(pdf, logoData) {
    if (!logoData) return;

    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const wmMargin = 16;
    const maxLogoWidth = Math.min(80, pageWidth * 0.18);
    const logoW = maxLogoWidth;
    const logoH = logoW * logoData.ratio;
    const x = pageWidth - logoW - wmMargin;
    const y = pageHeight - logoH - wmMargin;

    try {
        pdf.addImage(logoData.dataUrl, 'PNG', x, y, logoW, logoH);
    } catch (err) {
        console.warn('Error adding watermark:', err);
    }
}

// ======================================================
// MAIN PDF GENERATOR
// ======================================================

/**
 * Genera y descarga un PDF estructurado del análisis AI Overview.
 *
 * Layout:
 *   Page 1: Title + 5 summary metric cards + competitor bar chart
 *   Page 2: Domain Visibility table + Most Cited URLs table + info banner
 *   Page 3: Keyword Length Analysis + Position in AIO table
 *   Page 4: Keyword Diagnostic cards + Detailed Results by Keyword
 *
 * Each section is captured individually via html2canvas and composed onto
 * specific PDF pages, instead of capturing the entire container as one image.
 */
export async function generateAIOverviewPDF() {
    let domState = null;

    try {
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');

        console.log('Iniciando generacion de PDF estructurado...');

        // Show loading state
        if (spinner && btnText) {
            spinner.style.display = 'inline-block';
            btnText.textContent = 'Preparing PDF...';
        }
        if (btn) btn.disabled = true;

        // Verify AI Overview data exists
        const aiSection = document.getElementById('aiOverviewSection');
        const aiResults = document.getElementById('aiOverviewResultsContainer');

        if (!aiSection || !aiResults || aiResults.style.display === 'none') {
            throw new Error('No AI Overview data to export. Please run an AI analysis first.');
        }

        // Hide elements excluded from PDF
        const excluded = Array.from(document.querySelectorAll('[data-pdf-exclude="true"]'));
        const prevDisplay = new Map();
        excluded.forEach(el => {
            prevDisplay.set(el, el.style.display);
            el.style.display = 'none';
        });

        // Hide overlay, action buttons, advanced config section
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

        // ====== LOAD LIBRARIES ======
        console.log('Loading html2canvas...');
        const [{ default: html2canvas }] = await Promise.all([
            import('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.esm.js')
        ]);

        if (!window.jspdf || !window.jspdf.jsPDF) {
            console.log('Loading jsPDF...');
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js';
                script.onload = () => resolve();
                script.onerror = () => reject(new Error('Failed to load jsPDF'));
                document.head.appendChild(script);
            });
        }

        // ====== PREPARE DOM ======
        const targetSection = document.getElementById('aiOverviewContent');
        if (!targetSection) {
            throw new Error('AI Overview content section not found');
        }

        console.log('Preparing DOM for structured PDF capture...');

        // Prepare: convert charts + expand pagination + add capture class
        domState = {
            chartOriginals: convertChartsToImages(targetSection),
            paginationOriginals: expandAllPagination(targetSection)
        };
        document.body.classList.add('pdf-capture-mode');

        console.log(`  ${domState.chartOriginals.length} chart(s) converted to static image`);
        console.log(`  ${domState.paginationOriginals.length} pagination element(s) expanded`);

        // Wait for browser repaint
        await new Promise(resolve => setTimeout(resolve, 400));

        // ====== IDENTIFY SECTIONS ======
        // Page 1: Summary + Chart
        const summarySection = targetSection.querySelector('.ai-overview-summary');
        const chartRow = targetSection.querySelector('.competitor-chart-row');

        // Page 2: Tables + Banner
        const tablesRow = targetSection.querySelector('.competitor-tables-row');
        const infoBanner = targetSection.querySelector('.competitor-info-banner');

        // Page 3: Keyword typology (length + position)
        const typologySection = targetSection.querySelector('.ai-typology-section');

        // Page 4: Diagnostic + Detailed Results
        const diagnosticSection = targetSection.querySelector('.diagnostic-section');
        const detailedResults = document.getElementById('detailedResultsFilterSection');

        // ====== CAPTURE SECTIONS ======
        console.log('Capturing individual sections...');

        // Capture all sections in sequence (cannot parallelize — html2canvas
        // modifies the DOM during capture and needs sequential execution)
        const captures = {
            summary: await captureSection(html2canvas, summarySection, 'Summary Cards'),
            chart: await captureSection(html2canvas, chartRow, 'Competitor Chart'),
            tables: await captureSection(html2canvas, tablesRow, 'Domain & URL Tables'),
            banner: await captureSection(html2canvas, infoBanner, 'Info Banner'),
            typology: await captureSection(html2canvas, typologySection, 'Keyword Length & Position'),
            diagnostic: await captureSection(html2canvas, diagnosticSection, 'Keyword Diagnostic'),
            detailed: await captureSection(html2canvas, detailedResults, 'Detailed Results')
        };

        // ====== RESTORE DOM ======
        console.log('Restoring DOM...');
        restoreCharts(domState.chartOriginals);
        restorePagination(domState.paginationOriginals);
        document.body.classList.remove('pdf-capture-mode');
        domState = null;

        // Restore hidden elements
        excluded.forEach(el => {
            el.style.display = prevDisplay.get(el) || '';
        });
        tempHidden.forEach(({ el, display }) => {
            el.style.display = display;
        });

        // ====== BUILD PDF ======
        console.log('Building structured PDF document...');

        const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const margin = 28;
        const usableWidth = pageWidth - (margin * 2);

        // Load watermark logo once
        const logoData = await loadWatermarkLogo();

        // Helper to count captured sections for validation
        const capturedCount = Object.values(captures).filter(c => c !== null).length;
        if (capturedCount === 0) {
            throw new Error('No sections could be captured. Please ensure the AI Overview analysis is visible.');
        }
        console.log(`  ${capturedCount} section(s) captured successfully`);

        // ---- PAGE 1: Title + Summary + Chart ----
        let y = margin;

        // Add title text
        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(18);
        pdf.setTextColor(15, 23, 42); // #0F172A
        pdf.text('AI Overview Analysis', margin, y + 18);
        y += 32;

        // Add site name subtitle
        const siteUrl = document.getElementById('siteUrlSelect')?.value || '';
        if (siteUrl) {
            pdf.setFont('helvetica', 'normal');
            pdf.setFontSize(11);
            pdf.setTextColor(100, 116, 139); // #64748B
            pdf.text(siteUrl, margin, y + 10);
            y += 22;
        }

        // Add generation date
        const now = new Date();
        const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
        pdf.setFontSize(9);
        pdf.setTextColor(148, 163, 184); // #94A3B8
        pdf.text(`Generated: ${dateStr}`, margin, y + 8);
        y += 20;

        // Add separator line
        pdf.setDrawColor(226, 232, 240); // #E2E8F0
        pdf.setLineWidth(0.5);
        pdf.line(margin, y, pageWidth - margin, y);
        y += 12;

        // Place summary cards
        if (captures.summary) {
            y = placeImageOnPage(pdf, captures.summary.imgData,
                captures.summary.canvas.width, captures.summary.canvas.height,
                margin, usableWidth, pageHeight, y);
        }

        // Place chart (should fit on page 1 with the summary)
        if (captures.chart) {
            y = placeImageOnPage(pdf, captures.chart.imgData,
                captures.chart.canvas.width, captures.chart.canvas.height,
                margin, usableWidth, pageHeight, y);
        }

        addWatermark(pdf, logoData);

        // ---- PAGE 2: Domain Visibility + Most Cited URLs + Banner ----
        pdf.addPage();
        y = margin;

        // Page 2 section header
        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(14);
        pdf.setTextColor(15, 23, 42);
        pdf.text('Competitor Domains & Cited URLs', margin, y + 14);
        y += 28;

        pdf.setDrawColor(226, 232, 240);
        pdf.setLineWidth(0.5);
        pdf.line(margin, y, pageWidth - margin, y);
        y += 12;

        if (captures.tables) {
            y = placeImageOnPage(pdf, captures.tables.imgData,
                captures.tables.canvas.width, captures.tables.canvas.height,
                margin, usableWidth, pageHeight, y);
        }

        if (captures.banner) {
            y = placeImageOnPage(pdf, captures.banner.imgData,
                captures.banner.canvas.width, captures.banner.canvas.height,
                margin, usableWidth, pageHeight, y);
        }

        addWatermark(pdf, logoData);

        // ---- PAGE 3: Keyword Length & Position Analysis ----
        if (captures.typology) {
            pdf.addPage();
            y = margin;

            pdf.setFont('helvetica', 'bold');
            pdf.setFontSize(14);
            pdf.setTextColor(15, 23, 42);
            pdf.text('Keyword Length & Position Analysis', margin, y + 14);
            y += 28;

            pdf.setDrawColor(226, 232, 240);
            pdf.setLineWidth(0.5);
            pdf.line(margin, y, pageWidth - margin, y);
            y += 12;

            y = placeImageOnPage(pdf, captures.typology.imgData,
                captures.typology.canvas.width, captures.typology.canvas.height,
                margin, usableWidth, pageHeight, y);

            addWatermark(pdf, logoData);
        }

        // ---- PAGE 4: Keyword Diagnostic + Detailed Results ----
        if (captures.diagnostic || captures.detailed) {
            pdf.addPage();
            y = margin;

            pdf.setFont('helvetica', 'bold');
            pdf.setFontSize(14);
            pdf.setTextColor(15, 23, 42);
            pdf.text('Keyword Diagnostic & Detailed Results', margin, y + 14);
            y += 28;

            pdf.setDrawColor(226, 232, 240);
            pdf.setLineWidth(0.5);
            pdf.line(margin, y, pageWidth - margin, y);
            y += 12;

            if (captures.diagnostic) {
                y = placeImageOnPage(pdf, captures.diagnostic.imgData,
                    captures.diagnostic.canvas.width, captures.diagnostic.canvas.height,
                    margin, usableWidth, pageHeight, y);
            }

            if (captures.detailed) {
                // Detailed results table can be very tall — handle multi-page overflow
                const detailedImgWidth = usableWidth;
                const detailedImgHeight = captures.detailed.canvas.height * (detailedImgWidth / captures.detailed.canvas.width);

                if (y + detailedImgHeight <= pageHeight - margin) {
                    // Fits on current page
                    pdf.addImage(captures.detailed.imgData, 'JPEG', margin, y, detailedImgWidth, detailedImgHeight);
                    y += detailedImgHeight + 8;
                } else {
                    // Need overflow: place image and let it span multiple pages
                    const remainingOnPage = pageHeight - margin - y;

                    if (remainingOnPage > 100) {
                        // Some space left — start here and overflow
                        pdf.addImage(captures.detailed.imgData, 'JPEG', margin, y, detailedImgWidth, detailedImgHeight);
                        addWatermark(pdf, logoData);

                        // Add continuation pages for the overflow
                        let heightLeft = detailedImgHeight - remainingOnPage;
                        while (heightLeft > 0) {
                            pdf.addPage();
                            const newY = margin - (detailedImgHeight - heightLeft);
                            pdf.addImage(captures.detailed.imgData, 'JPEG', margin, newY, detailedImgWidth, detailedImgHeight);
                            addWatermark(pdf, logoData);
                            heightLeft -= (pageHeight - (margin * 2));
                        }
                    } else {
                        // Almost no space — start fresh on next page
                        pdf.addPage();
                        y = margin;
                        pdf.addImage(captures.detailed.imgData, 'JPEG', margin, y, detailedImgWidth, detailedImgHeight);

                        let heightLeft = detailedImgHeight - (pageHeight - margin - y);
                        while (heightLeft > 0) {
                            pdf.addPage();
                            const newY = margin - (detailedImgHeight - heightLeft);
                            pdf.addImage(captures.detailed.imgData, 'JPEG', margin, newY, detailedImgWidth, detailedImgHeight);
                            addWatermark(pdf, logoData);
                            heightLeft -= (pageHeight - (margin * 2));
                        }
                    }
                }
            }

            addWatermark(pdf, logoData);
        }

        // ====== SAVE PDF ======
        const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const siteName = siteUrl.replace(/^https?:\/\//i, '').replace(/[^a-z0-9]/gi, '_').substring(0, 30);
        const fileName = `ai_overview_${siteName}_${timestamp}.pdf`;

        console.log(`Saving PDF: ${fileName}`);
        pdf.save(fileName);

        console.log('PDF generated successfully');
        showSuccessMessage('PDF downloaded successfully!');

    } catch (err) {
        console.error('Error generating PDF:', err);
        alert(`Error generating PDF: ${err.message}`);

        // Restore DOM if failed before restoration
        if (domState) {
            try {
                restoreCharts(domState.chartOriginals);
                restorePagination(domState.paginationOriginals);
            } catch (restoreErr) {
                console.error('Error restoring DOM:', restoreErr);
            }
        }
    } finally {
        // Always remove capture mode class
        document.body.classList.remove('pdf-capture-mode');

        // Restore button state
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

// Add CSS animations if not already present
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
