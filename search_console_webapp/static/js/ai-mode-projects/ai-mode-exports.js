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
    try {
        const btn = document.getElementById('sidebarDownloadPdfBtn');
        const spinner = btn?.querySelector('.download-spinner');
        const btnText = btn?.querySelector('span');
        if (spinner && btnText) {
            spinner.style.display = 'inline-block';
            btnText.textContent = 'Preparing PDF...';
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

        const target = document.querySelector('.manual-ai-app') || document.body;
        const canvas = await html2canvas(target, { scale: 2, useCORS: true, backgroundColor: '#ffffff' });
        const imgData = canvas.toDataURL('image/jpeg', 0.92);

        const pdf = new window.jspdf.jsPDF('p', 'pt', 'a4');
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const imgWidth = pageWidth;
        const imgHeight = canvas.height * (imgWidth / canvas.width);
        let position = 0;
        let heightLeft = imgHeight;
        pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);

        // Añadir logotipo como marca de agua en cada página (esquina inferior derecha)
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
                    const margin = 16; // pt
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

        await addCornerLogo();
        heightLeft -= pageHeight;
        while (heightLeft > 0) {
            position = heightLeft - imgHeight;
            pdf.addPage();
            pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight);
            await addCornerLogo();
            heightLeft -= pageHeight;
        }
        const fileName = `manual_ai_overview_${Date.now()}.pdf`;
        pdf.save(fileName);
        
        // Restaurar elementos excluidos
        excluded.forEach(el => { el.style.display = prevDisplay.get(el) || ''; });
    } catch (err) {
        console.error('Error generating PDF:', err);
        this.showError('Failed to generate PDF.');
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

