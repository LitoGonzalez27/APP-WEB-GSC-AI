// static/js/ui-ai-overview-pdf.js
// Módulo para generar PDF del análisis AI Overview con marca de agua Clicandseo
// v6: Robust hide-all/show-selected capture within #aiOverviewContent.
//
// DOM structure of #aiOverviewResultsContainer (direct children):
//   1. .ai-overview-summary           — title + 5 metric cards
//   2. .competitor-results-container   — wrapper containing:
//        ├── h3.competitor-analysis-title
//        ├── .competitor-chart-row     — bar chart
//        ├── .competitor-tables-row    — domain + URL tables
//        └── .competitor-info-banner   — disclaimer
//   3. .topic-clusters-* (optional)
//   4. .ai-overview-grid-section       — "Details of keywords with AIO" Grid.js
//   5. .ai-typology-section            — keyword length & position tables
//   6. .aio-diagnostic-section         — diagnostic category cards
//   7. #detailedResultsFilterSection   — "Detailed Results by Keyword" Grid.js
//
// PDF Layout:
//   Page 1: summary + competitor-container (chart only, tables hidden)
//   Page 2: competitor-container (tables + banner only, chart hidden) + topic-clusters (if configured)
//   Page 3: ai-overview-grid-section + ai-typology-section
//   Page 4: aio-diagnostic-section + detailedResultsFilterSection
//
// NOTE: placeImageOnPage() handles overflow across pages — NEVER creates
//       orphan header pages. If content is taller than remaining space,
//       it starts on the current page and continues on the next.

// ======================================================
// DOM HELPERS
// ======================================================

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
                originals.push({ canvas, img });
            }
        } catch (e) {
            console.warn('Canvas conversion failed:', e);
        }
    });
    return originals;
}

function restoreCharts(originals) {
    originals.forEach(({ canvas, img }) => {
        try {
            canvas.style.display = '';
            if (img && img.parentNode) img.parentNode.removeChild(img);
        } catch (e) {}
    });
}

function expandAllPagination(container) {
    const originals = [];
    container.querySelectorAll('.cited-urls-page-2').forEach(el => {
        originals.push({ el, display: el.style.display });
        el.style.display = '';
    });
    container.querySelectorAll('.cited-urls-page-1').forEach(el => {
        if (el.style.display === 'none') {
            originals.push({ el, display: el.style.display });
            el.style.display = '';
        }
    });
    return originals;
}

function restorePagination(originals) {
    originals.forEach(({ el, display }) => { el.style.display = display; });
}

// ======================================================
// VISIBILITY CONTROL
// ======================================================

/**
 * Hides ALL direct children of the results container.
 * Returns a function to restore original display values.
 */
function hideAllChildren(resultsContainer) {
    const saved = [];
    Array.from(resultsContainer.children).forEach(el => {
        saved.push({ el, display: el.style.display });
        el.style.display = 'none';
    });
    return () => saved.forEach(({ el, display }) => { el.style.display = display; });
}

/**
 * Shows specific elements (sets display to '').
 */
function showElements(...elements) {
    elements.forEach(el => {
        if (el) el.style.display = '';
    });
}

/**
 * Hides specific elements within a visible parent.
 * Returns restore function.
 */
function hideElements(...elements) {
    const saved = [];
    elements.forEach(el => {
        if (el) {
            saved.push({ el, display: el.style.display });
            el.style.display = 'none';
        }
    });
    return () => saved.forEach(({ el, display }) => { el.style.display = display; });
}

// ======================================================
// CAPTURE
// ======================================================

/**
 * Captures #aiOverviewContent with only specific sections visible.
 * The container itself stays visible to preserve CSS variable scope.
 */
async function captureWithVisibleSections(html2canvas, aiOverviewContent, resultsContainer, setupFn, label) {
    // 1. Hide ALL children
    const restoreAll = hideAllChildren(resultsContainer);

    // 2. Run setup function to show specific sections
    const restoreSetup = setupFn();

    // 3. Wait for repaint
    await new Promise(r => setTimeout(r, 250));

    // 4. Verify content is visible
    const contentHeight = aiOverviewContent.scrollHeight;
    if (contentHeight < 20) {
        console.warn(`  "${label}": too small (${contentHeight}px) — skipping`);
        restoreSetup();
        restoreAll();
        return null;
    }

    console.log(`  Capturing: ${label} (${aiOverviewContent.scrollWidth}x${contentHeight}px)`);

    try {
        const canvas = await html2canvas(aiOverviewContent, {
            scale: 1.5,
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#ffffff',
            logging: false,
            imageTimeout: 15000,
            removeContainer: true,
            width: aiOverviewContent.scrollWidth,
            height: contentHeight,
            scrollX: 0,
            scrollY: -window.scrollY
        });

        // 5. Restore
        restoreSetup();
        restoreAll();

        if (!canvas || canvas.width === 0 || canvas.height === 0) {
            console.warn(`  "${label}": empty canvas`);
            return null;
        }

        return { canvas, imgData: canvas.toDataURL('image/jpeg', 0.85), label };
    } catch (err) {
        console.warn(`  "${label}": capture failed:`, err);
        restoreSetup();
        restoreAll();
        return null;
    }
}

// ======================================================
// PDF COMPOSITION
// ======================================================

/**
 * Places a captured image on the current PDF page.
 *
 * @param {boolean} allowOverflow - If false (default), scales the image down
 *   proportionally to fit the remaining page space. If true, allows the image
 *   to overflow onto continuation pages (for very tall content like tables).
 */
function placeImageOnPage(pdf, imgData, canvasW, canvasH, margin, usableWidth, pageHeight, yOffset, logoData, allowOverflow) {
    const imgW = usableWidth;
    const imgH = canvasH * (imgW / canvasW);
    const availableH = pageHeight - yOffset - margin;

    // Case 1: Fits on current page — place at full size
    if (imgH <= availableH) {
        pdf.addImage(imgData, 'JPEG', margin, yOffset, imgW, imgH);
        return yOffset + imgH + 8;
    }

    // Case 2: Doesn't fit — scale down to fit (default for most pages)
    if (!allowOverflow) {
        const scale = availableH / imgH;
        const sw = imgW * scale;
        const sh = availableH;
        // Center horizontally after scaling
        const xOffset = margin + (usableWidth - sw) / 2;
        pdf.addImage(imgData, 'JPEG', xOffset, yOffset, sw, sh);
        return yOffset + sh + 8;
    }

    // Case 3: Allow overflow — place and continue on next pages
    if (yOffset > margin + 80) {
        addWatermark(pdf, logoData);
        pdf.addPage();
        yOffset = margin;
    }

    pdf.addImage(imgData, 'JPEG', margin, yOffset, imgW, imgH);
    let heightLeft = imgH - (pageHeight - yOffset);

    while (heightLeft > 0) {
        addWatermark(pdf, logoData);
        pdf.addPage();
        const newY = margin - (imgH - heightLeft);
        pdf.addImage(imgData, 'JPEG', margin, newY, imgW, imgH);
        heightLeft -= (pageHeight - margin * 2);
    }

    return margin;
}

// ======================================================
// WATERMARK
// ======================================================

let _cachedLogo = null;

async function loadWatermarkLogo() {
    if (_cachedLogo) return _cachedLogo;
    try {
        const logoEl = document.querySelector('.navbar .logo-image');
        const logoSrc = logoEl?.src || '/static/images/logos/logo%20clicandseo.png';
        const img = new Image();
        img.crossOrigin = 'anonymous';
        await new Promise(r => { img.onload = r; img.onerror = r; img.src = logoSrc; });

        const c = document.createElement('canvas');
        c.width = img.naturalWidth || 0;
        c.height = img.naturalHeight || 0;
        if (c.width && c.height) {
            c.getContext('2d').drawImage(img, 0, 0);
            _cachedLogo = { dataUrl: c.toDataURL('image/png'), ratio: c.height / c.width };
        }
    } catch (e) {}
    return _cachedLogo;
}

function addWatermark(pdf, logo) {
    if (!logo) return;
    const pw = pdf.internal.pageSize.getWidth();
    const ph = pdf.internal.pageSize.getHeight();
    const w = Math.min(80, pw * 0.18);
    const h = w * logo.ratio;
    try { pdf.addImage(logo.dataUrl, 'PNG', pw - w - 16, ph - h - 16, w, h); } catch (e) {}
}

function addPageHeader(pdf, title, margin, pageWidth) {
    let y = margin;
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(14);
    pdf.setTextColor(15, 23, 42);
    pdf.text(title, margin, y + 14);
    y += 24;
    pdf.setDrawColor(226, 232, 240);
    pdf.setLineWidth(0.5);
    pdf.line(margin, y, pageWidth - margin, y);
    return y + 12;
}

// ======================================================
// MAIN
// ======================================================

export async function generateAIOverviewPDF() {
    let chartOriginals = [];
    let paginationOriginals = [];

    try {
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');

        console.log('PDF v6: Starting structured generation...');
        if (spinner && btnText) { spinner.style.display = 'inline-block'; btnText.textContent = 'Preparing PDF...'; }
        if (btn) btn.disabled = true;

        // Verify data exists
        const aiResults = document.getElementById('aiOverviewResultsContainer');
        if (!aiResults || aiResults.style.display === 'none') {
            throw new Error('No AI Overview data to export. Run an analysis first.');
        }

        // Hide non-content elements
        const aiOverlay = document.getElementById('aiOverlay');
        const resetBtn = document.getElementById('resetAIAnalysisBtn');
        const stickyActions = document.getElementById('stickyActions');
        const advancedSection = document.getElementById('advancedAnalysisSection');
        const tempHidden = [];
        [aiOverlay, resetBtn, stickyActions, advancedSection].forEach(el => {
            if (el) { tempHidden.push({ el, d: el.style.display }); el.style.display = 'none'; }
        });

        // Also hide pdf-excluded elements
        const excluded = Array.from(document.querySelectorAll('[data-pdf-exclude="true"]'));
        excluded.forEach(el => { tempHidden.push({ el, d: el.style.display }); el.style.display = 'none'; });

        // Load libraries
        const [{ default: html2canvas }] = await Promise.all([
            import('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.esm.js')
        ]);
        if (!window.jspdf?.jsPDF) {
            await new Promise((resolve, reject) => {
                const s = document.createElement('script');
                s.src = 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js';
                s.onload = resolve; s.onerror = () => reject(new Error('Failed to load jsPDF'));
                document.head.appendChild(s);
            });
        }

        // Prepare DOM
        const aiOverviewContent = document.getElementById('aiOverviewContent');
        if (!aiOverviewContent) throw new Error('AI Overview content section not found');

        document.body.classList.add('pdf-capture-mode');
        chartOriginals = convertChartsToImages(aiOverviewContent);
        paginationOriginals = expandAllPagination(aiOverviewContent);

        // Identify sections inside the results container
        const summary = aiResults.querySelector('.ai-overview-summary');
        const competitorContainer = aiResults.querySelector('.competitor-results-container');
        const chartRow = competitorContainer?.querySelector('.competitor-chart-row');
        const tablesRow = competitorContainer?.querySelector('.competitor-tables-row');
        const infoBanner = competitorContainer?.querySelector('.competitor-info-banner');
        const competitorTitle = competitorContainer?.querySelector('.competitor-analysis-title');
        const gridSection = aiResults.querySelector('.ai-overview-grid-section');
        const typology = aiResults.querySelector('.ai-typology-section');
        const diagnostic = aiResults.querySelector('.aio-diagnostic-section') ||
                           aiResults.querySelector('.diagnostic-section');
        const detailed = document.getElementById('detailedResultsFilterSection');
        // Topic clusters are optional — only present if user configured them
        const clusterSection = aiResults.querySelector('.topic-clusters-results');

        console.log('Sections found:', {
            summary: !!summary,
            competitorContainer: !!competitorContainer,
            chartRow: !!chartRow,
            tablesRow: !!tablesRow,
            infoBanner: !!infoBanner,
            clusterSection: !!clusterSection,
            gridSection: !!gridSection,
            typology: !!typology,
            diagnostic: !!diagnostic,
            detailed: !!detailed
        });

        // ====== CAPTURE 4 PAGES ======

        // PAGE 1: Summary cards + Chart (hide tables/banner inside competitor container)
        console.log('Capturing Page 1...');
        const cap1 = await captureWithVisibleSections(
            html2canvas, aiOverviewContent, aiResults,
            () => {
                showElements(summary, competitorContainer);
                // Inside competitor container: show only chart, hide tables + banner
                const restoreInner = hideElements(tablesRow, infoBanner);
                return restoreInner;
            },
            'Page 1: Summary + Chart'
        );

        // PAGE 2: Tables + Banner + Clusters (if configured)
        console.log('Capturing Page 2...');
        const cap2 = await captureWithVisibleSections(
            html2canvas, aiOverviewContent, aiResults,
            () => {
                showElements(competitorContainer);
                // Include clusters if they exist
                if (clusterSection) showElements(clusterSection);
                // Inside competitor container: show tables + banner, hide chart + title
                const restoreInner = hideElements(chartRow, competitorTitle);
                return restoreInner;
            },
            'Page 2: Tables + Banner' + (clusterSection ? ' + Clusters' : '')
        );

        // PAGE 3: Grid.js AIO keywords + Typology (keyword length & position)
        console.log('Capturing Page 3...');
        const cap3 = await captureWithVisibleSections(
            html2canvas, aiOverviewContent, aiResults,
            () => {
                showElements(gridSection, typology);
                return () => {};
            },
            'Page 3: Keywords AIO + Typology'
        );

        // PAGE 4: Diagnostic cards + Detailed results
        console.log('Capturing Page 4...');
        const cap4 = await captureWithVisibleSections(
            html2canvas, aiOverviewContent, aiResults,
            () => {
                showElements(diagnostic, detailed);
                return () => {};
            },
            'Page 4: Diagnostic + Detailed'
        );

        // ====== RESTORE DOM ======
        restoreCharts(chartOriginals); chartOriginals = [];
        restorePagination(paginationOriginals); paginationOriginals = [];
        document.body.classList.remove('pdf-capture-mode');
        tempHidden.forEach(({ el, d }) => { el.style.display = d; });

        // ====== BUILD PDF ======
        console.log('Building PDF...');
        const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
        const pw = pdf.internal.pageSize.getWidth();
        const ph = pdf.internal.pageSize.getHeight();
        const margin = 28;
        const usableW = pw - margin * 2;
        const logo = await loadWatermarkLogo();

        const captures = [cap1, cap2, cap3, cap4];
        const count = captures.filter(Boolean).length;
        if (count === 0) throw new Error('No sections captured. Ensure AI Overview analysis is visible.');
        console.log(`  ${count}/4 pages captured`);

        // --- PAGE 1 ---
        let y = margin;
        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(18);
        pdf.setTextColor(15, 23, 42);
        pdf.text('AI Overview Analysis', margin, y + 18);
        y += 32;

        const siteUrl = document.getElementById('siteUrlSelect')?.value || '';
        if (siteUrl) {
            pdf.setFont('helvetica', 'normal');
            pdf.setFontSize(11);
            pdf.setTextColor(100, 116, 139);
            pdf.text(siteUrl, margin, y + 10);
            y += 22;
        }

        const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
        pdf.setFontSize(9);
        pdf.setTextColor(148, 163, 184);
        pdf.text(`Generated: ${dateStr}`, margin, y + 8);
        y += 20;

        pdf.setDrawColor(226, 232, 240);
        pdf.setLineWidth(0.5);
        pdf.line(margin, y, pw - margin, y);
        y += 12;

        if (cap1) {
            y = placeImageOnPage(pdf, cap1.imgData, cap1.canvas.width, cap1.canvas.height, margin, usableW, ph, y, logo);
        }
        addWatermark(pdf, logo);

        // --- PAGE 2 ---
        if (cap2) {
            pdf.addPage();
            y = addPageHeader(pdf, 'Competitor Domains & Cited URLs', margin, pw);
            y = placeImageOnPage(pdf, cap2.imgData, cap2.canvas.width, cap2.canvas.height, margin, usableW, ph, y, logo);
            addWatermark(pdf, logo);
        }

        // --- PAGE 3 ---
        if (cap3) {
            pdf.addPage();
            y = addPageHeader(pdf, 'Keywords with AIO & Position Analysis', margin, pw);
            y = placeImageOnPage(pdf, cap3.imgData, cap3.canvas.width, cap3.canvas.height, margin, usableW, ph, y, logo);
            addWatermark(pdf, logo);
        }

        // --- PAGE 4 (allow overflow — detailed results table can be very long) ---
        if (cap4) {
            pdf.addPage();
            y = addPageHeader(pdf, 'Keyword Diagnostic & Detailed Results', margin, pw);
            y = placeImageOnPage(pdf, cap4.imgData, cap4.canvas.width, cap4.canvas.height, margin, usableW, ph, y, logo, true);
            addWatermark(pdf, logo);
        }

        // Save
        const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const siteName = siteUrl.replace(/^https?:\/\//i, '').replace(/[^a-z0-9]/gi, '_').substring(0, 30);
        pdf.save(`ai_overview_${siteName}_${ts}.pdf`);

        console.log('PDF generated successfully');
        showSuccessMessage('PDF downloaded successfully!');

    } catch (err) {
        console.error('PDF error:', err);
        alert(`Error generating PDF: ${err.message}`);
        if (chartOriginals.length) try { restoreCharts(chartOriginals); } catch (e) {}
        if (paginationOriginals.length) try { restorePagination(paginationOriginals); } catch (e) {}
    } finally {
        document.body.classList.remove('pdf-capture-mode');
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');
        if (spinner && btnText) { spinner.style.display = 'none'; btnText.textContent = 'Download PDF'; }
        if (btn) btn.disabled = false;
    }
}

// ======================================================
// SUCCESS MESSAGE
// ======================================================

function showSuccessMessage(message) {
    const existing = document.querySelector('.pdf-success-message');
    if (existing) existing.remove();

    const div = document.createElement('div');
    div.className = 'pdf-success-message';
    div.style.cssText = `position:fixed;top:80px;right:20px;background:#28a745;color:white;padding:12px 20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:10000;font-size:14px;font-weight:500;animation:slideInRight .3s ease-out;`;
    div.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    document.body.appendChild(div);
    setTimeout(() => { div.style.animation = 'slideOutRight .3s ease-in'; setTimeout(() => div.remove(), 300); }, 3000);
}

if (!document.getElementById('pdf-animations')) {
    const s = document.createElement('style');
    s.id = 'pdf-animations';
    s.textContent = `
        @keyframes slideInRight { from{transform:translateX(100%);opacity:0} to{transform:translateX(0);opacity:1} }
        @keyframes slideOutRight { from{transform:translateX(0);opacity:1} to{transform:translateX(100%);opacity:0} }
    `;
    document.head.appendChild(s);
}
