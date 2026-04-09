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
        const response = await fetch(`/manual-ai/api/projects/${projectId}/download-excel`, {
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

        // Extract filename from response headers or create default.
        // Default format matches the server-side filename:
        //   "AI Overview export - {project} - {YYYY-MM-DD} - Clicandseo.xlsx"
        const today = new Date().toISOString().slice(0, 10);
        let filename = `AI Overview export - ${projectName} - ${today} - Clicandseo.xlsx`;
        const contentDisposition = response.headers.get('Content-Disposition');
        if (contentDisposition) {
            // Try filename*=UTF-8''... (RFC 5987) first for Unicode-safe names,
            // then fall back to plain filename=...
            const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;\n]+)/i);
            if (filenameStarMatch) {
                try {
                    filename = decodeURIComponent(filenameStarMatch[1]);
                } catch (e) {
                    // Keep default if decode fails
                }
            } else {
                const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (filenameMatch) {
                    filename = filenameMatch[1].replace(/['"]/g, '');
                }
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
// PDF EXPORT (server-side ReportLab, 2026-04-09)
// ================================
//
// This used to be a client-side `html2canvas + jsPDF` screenshot pipeline
// (~260 lines) that captured DOM sections one page at a time. That produced
// rasterized output with no clickable links and was fragile to layout
// changes.
//
// It is now replaced with a call to the server endpoint
//   GET /manual-ai/api/projects/{id}/export/pdf?days={N}
// which returns a branded, 9-page (8 if clusters disabled) A4 PDF built
// with ReportLab in `manual_ai/services/pdf_export_service.py`. The server
// PDF has vector text, clickable URLs, brand colors and a dark header with
// Clicandseo logo watermark.
//
// This handler mirrors `handleDownloadExcel` above — same spinner UX, same
// filename parsing, same telemetry logging.

export async function handleDownloadPDF() {
    if (!this.currentAnalyticsData) {
        this.showError('No data available for export. Please select a project and load analytics first.');
        return;
    }

    const { projectId, days } = this.currentAnalyticsData;
    const downloadBtn = document.getElementById('sidebarDownloadPdfBtn');
    const spinner = downloadBtn?.querySelector('.download-spinner');
    const btnText = downloadBtn?.querySelector('span');

    console.log(`📄 Starting Manual AI PDF download for project ${projectId} (${days} days)`);

    try {
        // Show loading state
        if (downloadBtn) downloadBtn.disabled = true;
        if (spinner) spinner.style.display = 'inline-block';
        if (btnText) btnText.textContent = 'Generating PDF...';

        // Get current project info for telemetry + default filename fallback
        const project = this.projects.find(p => p.id === projectId);
        const projectName = project?.name || 'Unknown';
        const competitorsCount = project?.selected_competitors?.length || 0;

        // Request the PDF from the server (may take 5-15s for large projects)
        const response = await fetch(
            `/manual-ai/api/projects/${projectId}/export/pdf?days=${days}`,
            { method: 'GET' }
        );

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Error generating PDF file' }));
            throw new Error(errorData.error || 'Failed to generate PDF file');
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;

        // Extract filename from response headers with RFC 5987 support (Unicode).
        // Default mirrors the server format so we produce consistent filenames
        // even if Content-Disposition parsing fails for any reason.
        const today = new Date().toISOString().slice(0, 10);
        let filename = `AI Overview export - ${projectName} - ${today} - Clicandseo.pdf`;

        const contentDisposition = response.headers.get('Content-Disposition');
        if (contentDisposition) {
            // Try filename*=UTF-8''... first (Unicode-safe, RFC 5987)
            const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;\n]+)/i);
            if (filenameStarMatch) {
                try {
                    filename = decodeURIComponent(filenameStarMatch[1]);
                } catch (e) {
                    /* keep default */
                }
            } else {
                const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (filenameMatch) {
                    filename = filenameMatch[1].replace(/['"]/g, '');
                }
            }
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        // Telemetry logging
        console.log('📊 Manual AI PDF export telemetry:', {
            project_id: projectId,
            project_name: projectName,
            keyword_set_id: 'manual-ai',
            date_range: `${days}_days`,
            competitors_count: competitorsCount,
            export_type: 'manual_ai_pdf',
            timestamp: new Date().toISOString()
        });

        // Show success state
        if (btnText) {
            const originalText = btnText.textContent;
            btnText.textContent = 'Downloaded!';
            downloadBtn?.classList.add('success');

            setTimeout(() => {
                btnText.textContent = originalText;
                downloadBtn?.classList.remove('success');
            }, 2000);
        }

        this.showSuccess('PDF file downloaded successfully!');

    } catch (error) {
        console.error('❌ Error downloading Manual AI PDF:', error);
        this.showError(`Error downloading PDF: ${error.message}`);
    } finally {
        // Reset loading state
        if (downloadBtn) downloadBtn.disabled = false;
        if (spinner) spinner.style.display = 'none';
        if (btnText) btnText.textContent = 'Download PDF';
    }
}

