/**
 * Manual AI System - Analytics — carga y render principal (overview, summary cards)
 *
 * Extraído verbatim de manual-ai-analytics.js (refactor Fase 4).
 */

import { escapeHtml } from './manual-ai-utils.js';

export function populateAnalyticsProjectSelect() {
    if (!this.elements.analyticsProjectSelect) return;

    // Hide paused projects from the analytics selector — they are not
    // running analyses, so showing them only adds noise. They remain
    // visible on the Projects tab (as Paused cards) so the user can
    // resume/delete them from there.
    const selectableProjects = this.projects.filter(p => p.is_active !== false);

    this.elements.analyticsProjectSelect.innerHTML = `
        <option value="">Select a project...</option>
        ${selectableProjects.map(project => `
            <option value="${project.id}">${escapeHtml(project.name)}${project.can_edit === false ? ' (shared)' : ''}</option>
        `).join('')}
    `;
}

export async function loadAnalytics() {
    const projectId = this.elements.analyticsProjectSelect?.value;
    const days = this.elements.analyticsTimeRange?.value || 30;

    if (!projectId) {
        this.currentProject = null;
        this.elements.analyticsContent.innerHTML = `
            <div class="analytics-empty">
                <i class="fas fa-chart-line"></i>
                <p>Select a project to view analytics</p>
            </div>
        `;
        this.hideElement(this.elements.chartsContainer);
        this.showDownloadButton(false); // Hide download button when no project selected
        return;
    }

    const selectedProject = this.projects.find(p => String(p.id) === String(projectId));
    if (selectedProject) {
        this.currentProject = selectedProject;
    }

    this.elements.analyticsContent.innerHTML = `
        <div class="loading-analytics">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Loading analytics data...</p>
        </div>
    `;

    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/stats?days=${days}`);
        const data = await response.json();

        if (data.success) {
            this.renderAnalytics(data.stats);
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
        this.elements.analyticsContent.innerHTML = `
            <div class="analytics-error">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load analytics data</p>
            </div>
        `;
        this.showDownloadButton(false); // Hide download button on error
    }
}

export function renderAnalytics(stats) {
    console.log('📊 Rendering analytics data:', stats);
    
    // Update summary cards — ahora desde endpoint "latest" (ignora rango)
    const projectIdForLatest = stats.project_id || parseInt(this.elements.analyticsProjectSelect?.value) || this.currentProject?.id;
    if (projectIdForLatest) {
        const latestToken = Date.now();
        this._latestOverviewToken = latestToken;
        fetch(`/manual-ai/api/projects/${projectIdForLatest}/stats-latest`)
            .then(r => r.json())
            .then(latest => {
                if (this._latestOverviewToken !== latestToken) return; // evitar pisado por race
                const ms = latest?.main_stats || {};
                const totalKeywords = Number(ms.total_keywords) || 0;
                const totalAi = Number(ms.total_ai_keywords) || 0;
                const totalMentions = Number(ms.total_mentions) || 0;
                const avgPos = (ms.avg_position !== null && ms.avg_position !== undefined) ? Number(ms.avg_position) : null;
                const aioWeightPct = (ms.aio_weight_percentage !== null && ms.aio_weight_percentage !== undefined) ? Number(ms.aio_weight_percentage) : null;
                const visPctRaw = (ms.visibility_percentage !== null && ms.visibility_percentage !== undefined) ? Number(ms.visibility_percentage) : null;
                
                this.updateSummaryCard('totalKeywords', totalKeywords);
                this.updateSummaryCard('aiKeywords', totalAi);
                this.updateSummaryCard('domainMentions', totalMentions);
                // Mostrar visibilidad con base en último análisis si viene calculada
                const visPct = (typeof ms.visibility_percentage === 'number') ? ms.visibility_percentage : ms.aio_weight_percentage;
                this.updateSummaryCard('visibilityPercentage', typeof visPct === 'number' ? Math.round(visPct) + '%' : '0%');
                this.updateSummaryCard('averagePosition',
                    typeof ms.avg_position === 'number' ? Math.round(ms.avg_position * 10) / 10 : '-');
                this.updateSummaryCard('aioWeight',
                    typeof ms.aio_weight_percentage === 'number' ? Math.round(ms.aio_weight_percentage) + '%' : '0%');

                // Badge "Latest analysis"
                const header = document.querySelector('.overview-section .section-header p.section-description');
                if (header) {
                    const dt = ms.last_analysis_date ? new Date(ms.last_analysis_date).toLocaleDateString() : '';
                    header.textContent = `Data from the latest analysis${dt ? ' (' + dt + ')' : ''}`;
                }
            })
            .catch(() => {/* silencioso */});
    }

    // Show charts container
    this.hideElement(this.elements.analyticsContent);
    this.showElement(this.elements.chartsContainer);

    // Get project ID from stats or current selection
    const projectId = stats.project_id || parseInt(this.elements.analyticsProjectSelect?.value) || this.currentProject?.id;
    if (!projectId) {
        console.warn('No project ID available for analytics rendering');
        return;
    }

    console.log(`📈 Loading analytics components for project ${projectId}`);

    // Store current analytics data for Excel export
    this.currentAnalyticsData = {
        projectId: projectId,
        stats: stats,
        days: this.elements.analyticsTimeRange?.value || 30
    };

    // Show download button when analytics data is loaded
    this.showDownloadButton(true);

    // Render main charts with events annotations
    if (stats.visibility_chart && Array.isArray(stats.visibility_chart)) {
        this.renderVisibilityChart(stats.visibility_chart, stats.events || []);
    } else {
        console.warn('No visibility chart data available');
    }

    if (stats.positions_chart && Array.isArray(stats.positions_chart)) {
        this.renderPositionsChart(stats.positions_chart, stats.events || []);
    } else {
        console.warn('No positions chart data available');
    }

    // Load all competitive analysis components in parallel
    this.loadAnalyticsComponents(projectId);
}

export function updateSummaryCard(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    } else {
        console.warn(`Summary card element not found: ${elementId}`);
    }
}

export async function loadAnalyticsComponents(projectId) {
    console.log(`🔄 Loading analytics components for project ${projectId}`);
    
    try {
        // Load all components in parallel for better performance
        const promises = [
            this.loadGlobalDomainsRanking(projectId),
            this.loadTopUrlsRanking(projectId),
            this.loadComparativeCharts(projectId),
            this.loadCompetitorsPreview(projectId),
            this.loadAIOverviewKeywordsTable(projectId),
            this.loadClustersStatistics(projectId),  // ✨ Clusters statistics
            this.loadAioVsOrganicComparison(projectId)  // ✨ NEW (2026-04-09): AIO vs Organic
        ];

        await Promise.allSettled(promises);
        console.log('✅ All analytics components loaded (including clusters + AIO vs Organic)');

    } catch (error) {
        console.error('Error loading analytics components:', error);
    }
}
