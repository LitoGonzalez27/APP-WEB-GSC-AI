/**
 * Manual AI System - Exports Module
 * Gestión de exportaciones (Excel, PDF)
 */

// ================================
// EXCEL EXPORT
// ================================

export async function handleDownloadExcel() {
    if (!this.currentAnalyticsData) {
        this.showError('No data available for export. Please select a project and load analytics first.');
        return;
    }

    const { projectId, days } = this.currentAnalyticsData;
    const downloadBtn = document.getElementById('sidebarDownloadBtn');
    const spinner = downloadBtn?.querySelector('.download-spinner');
    const btnText = downloadBtn?.querySelector('span');

    console.log(`📥 Starting Manual AI Excel download for project ${projectId} (${days} days)`);

    try {
        // Show loading state
        if (downloadBtn) downloadBtn.disabled = true;
        if (spinner) spinner.style.display = 'inline-block';
        if (btnText) btnText.style.display = 'none';

        // Get current project info for telemetry
        const project = this.projects.find(p => p.id === projectId);
        const projectName = project?.name || 'Unknown';
        const competitorsCount = project?.selected_competitors?.length || 0;

        // Make download request
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/download-excel`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                days: days
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Error generating Excel file" }));
            throw new Error(errorData.error || 'Failed to generate Excel file');
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;

        // Extract filename from response headers or create default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'manual-ai_export.xlsx';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (filenameMatch) {
                filename = filenameMatch[1].replace(/['"]/g, '');
            }
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        // Telemetry logging
        console.log('📊 Manual AI Excel export telemetry:', {
            project_id: projectId,
            project_name: projectName,
            keyword_set_id: 'manual-ai',
            date_range: `${days}_days`,
            competitors_count: competitorsCount,
            rows_total: this.currentAnalyticsData.stats?.main_stats?.total_keywords || 0,
            export_type: 'manual_ai_xlsx',
            timestamp: new Date().toISOString()
        });

        // Show success state
        if (btnText) {
            const originalText = btnText.textContent;
            btnText.textContent = 'Downloaded!';
            downloadBtn.classList.add('success');

            setTimeout(() => {
                btnText.textContent = originalText;
                downloadBtn.classList.remove('success');
            }, 2000);
        }

        this.showSuccess('Excel file downloaded successfully!');

    } catch (error) {
        console.error('❌ Error downloading Manual AI Excel:', error);
        this.showError(`Error downloading Excel: ${error.message}`);
    } finally {
        // Reset loading state
        if (downloadBtn) downloadBtn.disabled = false;
        if (spinner) spinner.style.display = 'none';
        if (btnText) btnText.style.display = 'inline';
    }
}

// ================================
// PDF EXPORT
// ================================

export async function handleDownloadPDF() {
    // Variables que necesitan estar disponibles en catch/finally
    let chartsContainer = null;
    let chartsContainerOriginalDisplay = null;
    
    try {
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');
        if (spinner && btnText) {
            spinner.style.display = 'inline-block';
            btnText.textContent = 'Preparing PDF...';
        }

        // Asegurar que el contenedor de charts esté visible temporalmente
        chartsContainer = document.getElementById('chartsContainer');
        chartsContainerOriginalDisplay = chartsContainer ? chartsContainer.style.display : null;
        if (chartsContainer && chartsContainer.style.display === 'none') {
            chartsContainer.style.display = 'block';
        }

        // Ocultar elementos excluidos del PDF
        const excluded = Array.from(document.querySelectorAll('[data-pdf-exclude="true"]'));
        const prevDisplay = new Map();
        excluded.forEach(el => {
            prevDisplay.set(el, el.style.display);
            el.style.display = 'none';
        });

        const [{ default: html2canvas }] = await Promise.all([
            import('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.esm.js')
        ]);
        // Cargar jsPDF UMD y acceder via window.jspdf.jsPDF
        if (!window.jspdf || !window.jspdf.jsPDF) {
            await new Promise((resolve, reject) => {
                const s = document.createElement('script');
                s.src = 'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js';
                s.onload = () => resolve();
                s.onerror = () => reject(new Error('Failed to load jsPDF'));
                document.head.appendChild(s);
            });
        }

        const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();

        // Función para añadir logotipo en esquina inferior derecha
        const addCornerLogo = async () => {
            try {
                const logoEl = document.querySelector('.navbar .logo-image');
                const logoSrc = logoEl?.src || '/static/images/logos/logo%20clicandseo.png';
                const logoImg = new Image();
                logoImg.crossOrigin = 'anonymous';
                await new Promise((resolve) => { logoImg.onload = resolve; logoImg.onerror = resolve; logoImg.src = logoSrc; });
                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = logoImg.naturalWidth || 0;
                tempCanvas.height = logoImg.naturalHeight || 0;
                if (tempCanvas.width && tempCanvas.height) {
                    const ctx = tempCanvas.getContext('2d');
                    ctx.drawImage(logoImg, 0, 0);
                    const dataUrl = tempCanvas.toDataURL('image/png');
                    const margin = 16;
                    const maxLogoWidth = Math.min(80, pageWidth * 0.18);
                    const ratio = (logoImg.naturalHeight || 1) / (logoImg.naturalWidth || 1);
                    const logoW = maxLogoWidth;
                    const logoH = logoW * ratio;
                    const x = pageWidth - logoW - margin;
                    const y = pageHeight - logoH - margin;
                    try { pdf.addImage(dataUrl, 'PNG', x, y, logoW, logoH); } catch (_) {}
                }
            } catch (_) { /* silencioso */ }
        };

        // Función auxiliar para capturar y añadir sección al PDF
        const addSectionToPDF = async (element, isFirstPage = false, label = '') => {
            if (!element) {
                console.warn(`⚠️ Section not found: ${label}`);
                return false;
            }

            if (btnText) btnText.textContent = `Capturing ${label}...`;
            
            const canvas = await html2canvas(element, { 
                scale: 2, 
                useCORS: true, 
                backgroundColor: '#ffffff',
                logging: false
            });
            
            const imgData = canvas.toDataURL('image/jpeg', 0.92);
            const imgWidth = pageWidth - 40; // Márgenes de 20pt a cada lado
            const imgHeight = canvas.height * (imgWidth / canvas.width);
            
            if (!isFirstPage) {
                pdf.addPage();
            }
            
            // Centrar la imagen con márgenes
            const xPos = 20;
            let yPos = 20;
            
            // Si la imagen es más alta que la página, ajustar
            if (imgHeight > pageHeight - 40) {
                const scaleFactor = (pageHeight - 40) / imgHeight;
                const scaledWidth = imgWidth * scaleFactor;
                const scaledHeight = imgHeight * scaleFactor;
                const xCentered = (pageWidth - scaledWidth) / 2;
                pdf.addImage(imgData, 'JPEG', xCentered, yPos, scaledWidth, scaledHeight);
            } else {
                pdf.addImage(imgData, 'JPEG', xPos, yPos, imgWidth, imgHeight);
            }
            
            await addCornerLogo();
            return true;
        };

        // Crear un wrapper temporal para agrupar elementos visualmente
        const createTempWrapper = (elements) => {
            const wrapper = document.createElement('div');
            wrapper.id = 'pdf-temp-wrapper';
            wrapper.style.cssText = 'background: white; padding: 20px;';
            
            // Guardar padres originales y mover elementos al wrapper
            const originalParents = [];
            elements.forEach(el => {
                if (el) {
                    originalParents.push({ element: el, parent: el.parentNode, nextSibling: el.nextSibling });
                    wrapper.appendChild(el);
                }
            });
            
            chartsContainer.insertBefore(wrapper, chartsContainer.firstChild);
            return { wrapper, originalParents };
        };

        const restoreElements = (originalParents, wrapper) => {
            originalParents.forEach(({ element, parent, nextSibling }) => {
                if (nextSibling) {
                    parent.insertBefore(element, nextSibling);
                } else {
                    parent.appendChild(element);
                }
            });
            if (wrapper && wrapper.parentNode) {
                wrapper.parentNode.removeChild(wrapper);
            }
        };

        // PÁGINA 1: Overview + Position Distribution
        if (btnText) btnText.textContent = 'Page 1/4: Overview...';
        const overviewSection = document.querySelector('.overview-section');
        const summaryCards = document.querySelector('.summary-cards');
        const chartsGrid = document.querySelector('.charts-grid');
        
        const page1Elements = [overviewSection, summaryCards, chartsGrid].filter(el => el);
        if (page1Elements.length > 0) {
            const { wrapper: page1Wrapper, originalParents: page1Parents } = createTempWrapper(page1Elements);
            await addSectionToPDF(page1Wrapper, true, 'Overview & Charts');
            restoreElements(page1Parents, page1Wrapper);
        }

        // PÁGINA 2: Media Source Analysis + Clusters
        if (btnText) btnText.textContent = 'Page 2/5: Media Sources & Clusters...';
        const competitorsSection = document.querySelector('.competitors-charts-section');
        const clustersSection = document.querySelector('.clusters-visualization');
        
        // Verificar si clusters tiene datos (no está display: none por falta de datos)
        const clustersHasData = clustersSection && 
                                clustersSection.style.display !== 'none' && 
                                !clustersSection.querySelector('.no-clusters-message[style*="display: block"]');
        
        const page2Elements = [competitorsSection];
        if (clustersHasData) {
            page2Elements.push(clustersSection);
        }
        
        if (page2Elements.some(el => el)) {
            const filteredElements = page2Elements.filter(el => el);
            if (filteredElements.length === 1) {
                // Solo una sección, capturar directamente
                await addSectionToPDF(filteredElements[0], false, 'Media Sources');
            } else {
                // Múltiples secciones, usar wrapper
                const { wrapper: page2Wrapper, originalParents: page2Parents } = createTempWrapper(filteredElements);
                await addSectionToPDF(page2Wrapper, false, 'Media Sources & Clusters');
                restoreElements(page2Parents, page2Wrapper);
            }
        }

        // PÁGINA 3: AI Mode Keywords Details
        if (btnText) btnText.textContent = 'Page 3/5: Keywords Details...';
        const keywordsSection = document.querySelector('.ai-overview-keywords-section');
        if (keywordsSection) {
            await addSectionToPDF(keywordsSection, false, 'Keywords Details');
        }

        // PÁGINA 4: Top Mentioned URLs in AI Mode
        if (btnText) btnText.textContent = 'Page 4/5: Top URLs...';
        const topUrlsSection = document.querySelector('.top-urls-section');
        if (topUrlsSection) {
            await addSectionToPDF(topUrlsSection, false, 'Top URLs');
        }

        // PÁGINA 5: Global Media Sources Ranking
        if (btnText) btnText.textContent = 'Page 5/5: Global Ranking...';
        const globalDomainsSection = document.querySelector('.top-domains-section');
        if (globalDomainsSection) {
            await addSectionToPDF(globalDomainsSection, false, 'Global Ranking');
        }

        const fileName = `ai_mode_monitoring_${Date.now()}.pdf`;
        pdf.save(fileName);
        
        if (btnText) btnText.textContent = 'Download PDF';
        this.showSuccess('PDF generated successfully!');
        
        // Restaurar elementos excluidos
        excluded.forEach(el => { el.style.display = prevDisplay.get(el) || ''; });
        
        // Restaurar display original del chartsContainer
        if (chartsContainer && chartsContainerOriginalDisplay !== null) {
            chartsContainer.style.display = chartsContainerOriginalDisplay;
        }
    } catch (err) {
        console.error('Error generating PDF:', err);
        this.showError('Failed to generate PDF.');
        
        // Restaurar display del chartsContainer en caso de error
        if (chartsContainer && chartsContainerOriginalDisplay !== null) {
            chartsContainer.style.display = chartsContainerOriginalDisplay;
        }
    } finally {
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');
        if (spinner && btnText) {
            spinner.style.display = 'none';
            btnText.textContent = 'Download PDF';
        }
    }
}

