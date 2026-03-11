// static/js/ui-ai-overview-pdf.js
// Módulo para generar PDF del análisis AI Overview con marca de agua Clicandseo
// v5: Structured multi-page layout using hide/show strategy within #aiOverviewContent
//     to preserve CSS variable scope and ancestor selectors.

// ======================================================
// DOM PREPARATION HELPERS
// ======================================================

/**
 * Convierte todos los canvas de Chart.js a imágenes estáticas para captura limpia.
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

function restorePagination(originals) {
    originals.forEach(({ el, display }) => {
        el.style.display = display;
    });
}

// ======================================================
// HIDE/SHOW STRATEGY FOR SECTION CAPTURE
// ======================================================

/**
 * Gets all direct child sections within #aiOverviewContent that we can toggle.
 * Returns a map of sectionName -> element.
 */
function identifySections(container) {
    return {
        summary: container.querySelector('.ai-overview-summary'),
        chartRow: container.querySelector('.competitor-chart-row'),
        tablesRow: container.querySelector('.competitor-tables-row'),
        infoBanner: container.querySelector('.competitor-info-banner'),
        typology: container.querySelector('.ai-typology-section'),
        diagnostic: container.querySelector('.diagnostic-section'),
        detailed: document.getElementById('detailedResultsFilterSection')
    };
}

/**
 * Hides ALL identified sections by setting display:none.
 * Returns a restore function that brings everything back.
 */
function hideAllSections(sections) {
    const originals = [];

    Object.values(sections).forEach(el => {
        if (el) {
            originals.push({ el, display: el.style.display });
            el.style.display = 'none';
        }
    });

    return () => {
        originals.forEach(({ el, display }) => {
            el.style.display = display;
        });
    };
}

/**
 * Shows only the specified section keys, hiding all others.
 * Returns a restore function.
 */
function showOnlySections(sections, visibleKeys) {
    const originals = [];

    Object.entries(sections).forEach(([key, el]) => {
        if (el) {
            originals.push({ el, display: el.style.display });
            if (visibleKeys.includes(key)) {
                el.style.display = '';  // Show
            } else {
                el.style.display = 'none';  // Hide
            }
        }
    });

    return () => {
        originals.forEach(({ el, display }) => {
            el.style.display = display;
        });
    };
}

/**
 * Captures the #aiOverviewContent container with only certain sections visible.
 * This preserves the CSS variable scope and ancestor-scoped selectors.
 */
async function captureContainerWithSections(html2canvas, container, sections, visibleKeys, label) {
    // Toggle visibility
    const restore = showOnlySections(sections, visibleKeys);

    // Wait for repaint
    await new Promise(r => setTimeout(r, 200));

    // Check if container has visible content
    if (container.scrollHeight < 10) {
        console.warn(`  "${label}": container too small (${container.scrollHeight}px) — skipping`);
        restore();
        return null;
    }

    console.log(`  Capturing: ${label} (${container.scrollWidth}x${container.scrollHeight}px)`);

    try {
        const canvas = await html2canvas(container, {
            scale: 1.5,
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#ffffff',
            logging: false,
            imageTimeout: 15000,
            removeContainer: true,
            width: container.scrollWidth,
            height: container.scrollHeight,
            scrollX: 0,
            scrollY: -window.scrollY
        });

        restore();

        if (canvas.width === 0 || canvas.height === 0) {
            console.warn(`  "${label}": empty canvas — skipping`);
            return null;
        }

        const imgData = canvas.toDataURL('image/jpeg', 0.85);
        return { canvas, imgData, label };
    } catch (err) {
        restore();
        console.warn(`  "${label}": capture failed:`, err);
        return null;
    }
}

// ======================================================
// PDF PAGE COMPOSITION
// ======================================================

/**
 * Places a captured image onto the PDF.
 * Returns new yOffset. Adds new page if needed.
 */
function placeImageOnPage(pdf, imgData, canvasW, canvasH, margin, usableWidth, pageHeight, yOffset) {
    const imgWidth = usableWidth;
    const imgHeight = canvasH * (imgWidth / canvasW);

    // If image is taller than a full page, scale down
    if (imgHeight > pageHeight - (margin * 2)) {
        const maxH = pageHeight - (margin * 2);
        const scale = maxH / imgHeight;
        const scaledW = imgWidth * scale;
        const scaledH = maxH;
        const xOffset = margin + (usableWidth - scaledW) / 2;

        if (yOffset > margin + 10) {
            pdf.addPage();
            yOffset = margin;
        }
        pdf.addImage(imgData, 'JPEG', xOffset, yOffset, scaledW, scaledH);
        return yOffset + scaledH + 8;
    }

    // Check if fits on current page
    if (yOffset + imgHeight > pageHeight - margin) {
        pdf.addPage();
        yOffset = margin;
    }

    pdf.addImage(imgData, 'JPEG', margin, yOffset, imgWidth, imgHeight);
    return yOffset + imgHeight + 8;
}

/**
 * Places a large image that may span multiple pages (for detailed results table).
 */
function placeImageMultiPage(pdf, imgData, canvasW, canvasH, margin, usableWidth, pageHeight, yOffset, logoData) {
    const imgWidth = usableWidth;
    const imgHeight = canvasH * (imgWidth / canvasW);

    // If it fits on one page (or remaining space)
    if (yOffset + imgHeight <= pageHeight - margin) {
        pdf.addImage(imgData, 'JPEG', margin, yOffset, imgWidth, imgHeight);
        return yOffset + imgHeight + 8;
    }

    // Multi-page overflow
    if (yOffset > margin + 50) {
        // Start on new page if very little space left
        addWatermark(pdf, logoData);
        pdf.addPage();
        yOffset = margin;
    }

    // First page slice
    pdf.addImage(imgData, 'JPEG', margin, yOffset, imgWidth, imgHeight);
    let heightLeft = imgHeight - (pageHeight - yOffset);

    while (heightLeft > 0) {
        addWatermark(pdf, logoData);
        pdf.addPage();
        const newY = margin - (imgHeight - heightLeft);
        pdf.addImage(imgData, 'JPEG', margin, newY, imgWidth, imgHeight);
        heightLeft -= (pageHeight - (margin * 2));
    }

    return margin; // returned for next section (though typically nothing follows)
}

// ======================================================
// WATERMARK
// ======================================================

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
    const logoW = Math.min(80, pageWidth * 0.18);
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
// PDF PAGE HEADERS
// ======================================================

function addPageHeader(pdf, title, margin, pageWidth) {
    let y = margin;

    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(14);
    pdf.setTextColor(15, 23, 42); // #0F172A
    pdf.text(title, margin, y + 14);
    y += 24;

    pdf.setDrawColor(226, 232, 240); // #E2E8F0
    pdf.setLineWidth(0.5);
    pdf.line(margin, y, pageWidth - margin, y);
    y += 12;

    return y;
}

// ======================================================
// MAIN PDF GENERATOR
// ======================================================

/**
 * Genera y descarga un PDF estructurado del análisis AI Overview.
 *
 * Strategy: Instead of capturing child elements in isolation (which breaks
 * CSS variable scope and ancestor selectors like #aiOverviewContent .aio-*),
 * we hide/show sections within #aiOverviewContent and capture the PARENT
 * container for each page. This preserves all CSS context.
 *
 * Layout:
 *   Page 1: Title + 5 summary metric cards + competitor bar chart
 *   Page 2: Domain Visibility table + Most Cited URLs table + info banner
 *   Page 3: Keyword Length Analysis + Position in AIO table
 *   Page 4: Keyword Diagnostic cards + Detailed Results by Keyword
 */
export async function generateAIOverviewPDF() {
    let chartOriginals = [];
    let paginationOriginals = [];

    try {
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');

        console.log('Iniciando generacion de PDF estructurado (v5)...');

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

        console.log('Preparing DOM for PDF capture...');
        document.body.classList.add('pdf-capture-mode');

        // Convert charts to images + expand pagination
        chartOriginals = convertChartsToImages(targetSection);
        paginationOriginals = expandAllPagination(targetSection);

        console.log(`  ${chartOriginals.length} chart(s) converted to static image`);
        console.log(`  ${paginationOriginals.length} pagination element(s) expanded`);

        // Identify all sections
        const sections = identifySections(targetSection);

        // Log found sections for debugging
        Object.entries(sections).forEach(([key, el]) => {
            console.log(`  Section "${key}": ${el ? `found (${el.offsetWidth}x${el.offsetHeight})` : 'NOT FOUND'}`);
        });

        // ====== CAPTURE SECTIONS (hide/show within parent) ======
        console.log('Capturing sections using hide/show strategy...');

        // Page 1: Summary + Chart
        const capturePage1 = await captureContainerWithSections(
            html2canvas, targetSection, sections,
            ['summary', 'chartRow'],
            'Page 1: Summary + Chart'
        );

        // Page 2: Tables + Banner
        const capturePage2 = await captureContainerWithSections(
            html2canvas, targetSection, sections,
            ['tablesRow', 'infoBanner'],
            'Page 2: Tables + Banner'
        );

        // Page 3: Typology (keyword length + position)
        const capturePage3 = await captureContainerWithSections(
            html2canvas, targetSection, sections,
            ['typology'],
            'Page 3: Keyword Length & Position'
        );

        // Page 4: Diagnostic + Detailed Results
        const capturePage4 = await captureContainerWithSections(
            html2canvas, targetSection, sections,
            ['diagnostic', 'detailed'],
            'Page 4: Diagnostic + Detailed Results'
        );

        // ====== RESTORE DOM ======
        console.log('Restoring DOM...');
        restoreCharts(chartOriginals);
        chartOriginals = [];
        restorePagination(paginationOriginals);
        paginationOriginals = [];
        document.body.classList.remove('pdf-capture-mode');

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

        const logoData = await loadWatermarkLogo();

        // Check we have at least some content
        const captures = [capturePage1, capturePage2, capturePage3, capturePage4];
        const capturedCount = captures.filter(c => c !== null).length;
        if (capturedCount === 0) {
            throw new Error('No sections could be captured. Please ensure the AI Overview analysis is visible.');
        }
        console.log(`  ${capturedCount}/4 page captures successful`);

        // ---- PAGE 1: Title + Summary + Chart ----
        let y = margin;

        // PDF title
        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(18);
        pdf.setTextColor(15, 23, 42);
        pdf.text('AI Overview Analysis', margin, y + 18);
        y += 32;

        // Site URL subtitle
        const siteUrl = document.getElementById('siteUrlSelect')?.value || '';
        if (siteUrl) {
            pdf.setFont('helvetica', 'normal');
            pdf.setFontSize(11);
            pdf.setTextColor(100, 116, 139);
            pdf.text(siteUrl, margin, y + 10);
            y += 22;
        }

        // Generation date
        const now = new Date();
        const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
        pdf.setFontSize(9);
        pdf.setTextColor(148, 163, 184);
        pdf.text(`Generated: ${dateStr}`, margin, y + 8);
        y += 20;

        // Separator
        pdf.setDrawColor(226, 232, 240);
        pdf.setLineWidth(0.5);
        pdf.line(margin, y, pageWidth - margin, y);
        y += 12;

        if (capturePage1) {
            y = placeImageOnPage(pdf, capturePage1.imgData,
                capturePage1.canvas.width, capturePage1.canvas.height,
                margin, usableWidth, pageHeight, y);
        }

        addWatermark(pdf, logoData);

        // ---- PAGE 2: Tables + Banner ----
        if (capturePage2) {
            pdf.addPage();
            y = addPageHeader(pdf, 'Competitor Domains & Cited URLs', margin, pageWidth);

            y = placeImageOnPage(pdf, capturePage2.imgData,
                capturePage2.canvas.width, capturePage2.canvas.height,
                margin, usableWidth, pageHeight, y);

            addWatermark(pdf, logoData);
        }

        // ---- PAGE 3: Keyword Length & Position ----
        if (capturePage3) {
            pdf.addPage();
            y = addPageHeader(pdf, 'Keyword Length & Position Analysis', margin, pageWidth);

            y = placeImageOnPage(pdf, capturePage3.imgData,
                capturePage3.canvas.width, capturePage3.canvas.height,
                margin, usableWidth, pageHeight, y);

            addWatermark(pdf, logoData);
        }

        // ---- PAGE 4: Diagnostic + Detailed Results ----
        if (capturePage4) {
            pdf.addPage();
            y = addPageHeader(pdf, 'Keyword Diagnostic & Detailed Results', margin, pageWidth);

            // This page may be tall (detailed results table) — use multi-page placement
            y = placeImageMultiPage(pdf, capturePage4.imgData,
                capturePage4.canvas.width, capturePage4.canvas.height,
                margin, usableWidth, pageHeight, y, logoData);

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

        // Restore DOM if failed
        if (chartOriginals.length) {
            try { restoreCharts(chartOriginals); } catch (e) {}
        }
        if (paginationOriginals.length) {
            try { restorePagination(paginationOriginals); } catch (e) {}
        }
    } finally {
        document.body.classList.remove('pdf-capture-mode');

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

// ======================================================
// SUCCESS MESSAGE
// ======================================================

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

if (!document.getElementById('pdf-animations')) {
    const style = document.createElement('style');
    style.id = 'pdf-animations';
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}
