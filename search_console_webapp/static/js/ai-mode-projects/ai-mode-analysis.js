/**
 * Manual AI System - Analysis Module
 * Gestión de análisis de proyectos (análisis, progress, polling)
 */

// ================================
// ANALYSIS
// ================================

export async function analyzeProject(projectId) {
    const project = this.projects.find(p => p.id === projectId);
    
    if (!project) {
        this.showError('Project not found');
        return;
    }

    this.showProgress('Running analysis...', 
        `Analyzing ${project.keyword_count} keywords for AI Overview visibility. This may take several minutes.`);

    // Start a backup polling system in case main request fails
    const startTime = Date.now();
    const backupPolling = setInterval(async () => {
        try {
            await this.loadProjects();
            const updatedProject = this.projects.find(p => p.id === projectId);
            
            // Check if project has new analysis data (very basic check)
            if (updatedProject && updatedProject.total_results > project.total_results) {
                console.log('📡 Backup polling detected analysis completion');
                clearInterval(backupPolling);
                this.completeProgressBar();
                setTimeout(() => this.hideProgress(), 400);
                this.showSuccess('Analysis completed! Results detected via backup monitoring.');
                
                // Refresh analytics if needed
                if (this.elements.analyticsProjectSelect.value == projectId) {
                    await this.loadAnalytics();
                }
            }
            
            // Stop polling after 10 minutes
            if (Date.now() - startTime > 600000) {
                clearInterval(backupPolling);
            }
        } catch (pollError) {
            console.error('Backup polling error:', pollError);
        }
    }, 30000); // Check every 30 seconds

    let analysisCompleted = false;
    try {
        // Create AbortController for timeout management
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1800000); // 30 minutes timeout for up to 200 keywords
        
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/analyze`, {
            method: 'POST',
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        clearTimeout(timeoutId);

        const data = await response.json();

        // ✅ NUEVO FASE 4.5: Manejar paywalls (402)
        if (response.status === 402) {
            clearInterval(backupPolling);
            this.hideProgress();
            
            console.warn(`🚫 Manual AI analysis blocked by paywall: ${data.error}`);
            
            // Mostrar paywall si está disponible
            if (window.showPaywall) {
                window.showPaywall('Manual AI Analysis', data.upgrade_options || ['basic','premium','business']);
            }
            
            this.showToast('Manual AI Analysis requires a paid plan. Please upgrade to continue.', 'error', 8000);
            return;
        }

        // ✅ FASE 4: Manejar errores de quota específicamente
        if (response.status === 429 && data.quota_exceeded) {
            clearInterval(backupPolling);
            this.hideProgress();
            
            const quotaInfo = data.quota_info || {};
            const analyzed = data.keywords_analyzed || 0;
            const remaining = data.keywords_remaining || 0;
            
            console.warn(`🚫 Manual AI analysis blocked by quota: ${data.error}`);
            
            // Mostrar UI de quota si está disponible
            if (window.QuotaUI) {
                window.QuotaUI.showBlockModal({
                    error: data.error,
                    quota_blocked: true,
                    quota_info: quotaInfo,
                    action_required: data.action_required || 'upgrade'
                });
            }
            
            // Mostrar mensaje específico de quota
            const quotaMessage = analyzed > 0 
                ? `Analysis stopped due to quota limit. ${analyzed} keywords were analyzed successfully before reaching the limit. ${remaining} keywords remain.`
                : `Analysis blocked: You have reached your monthly quota limit. Please upgrade your plan to continue.`;
                
            this.showError(quotaMessage);
            
            // Refresh project stats en caso de que se hayan analizado algunas keywords
            if (analyzed > 0) {
                await this.loadProjects();
                
                // Refresh analytics if needed
                if (this.elements.analyticsProjectSelect.value == projectId) {
                    await this.loadAnalytics();
                }
            }
            
            return; // No continuar con el flujo normal
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        if (data.success) {
            clearInterval(backupPolling); // Stop backup polling
            analysisCompleted = true;
            this.completeProgressBar();
            this.showSuccess(`Analysis completed! Processed ${data.results_count} keywords`);
            await this.loadProjects(); // Refresh project stats
            
            // If analytics tab is active and this project is selected, refresh charts
            if (this.elements.analyticsProjectSelect.value == projectId) {
                await this.loadAnalytics();
            }
        } else {
            throw new Error(data.error || 'Analysis failed');
        }
    } catch (error) {
        console.error('Error running analysis:', error);
        
        // Handle different types of errors
        let errorMessage = 'Analysis failed';
        if (error.name === 'AbortError') {
            errorMessage = 'Analysis timeout (30 minutes). This usually indicates a server or network issue. Consider running the analysis during off-peak hours.';
        } else if (error.message.includes('Failed to fetch') || error.message.includes('ERR_NETWORK_CHANGED')) {
            // Network error - check if analysis actually completed
            console.log('🔍 Network error detected, checking if analysis completed...');
            try {
                // Wait a moment and check if we have new results
                await new Promise(resolve => setTimeout(resolve, 2000));
                await this.loadProjects(); // Refresh project stats
                
                // If analytics tab is active, refresh it too
                if (this.elements.analyticsProjectSelect.value == projectId) {
                    await this.loadAnalytics();
                }
                
                this.showSuccess('Analysis may have completed despite network error. Please check the Results tab.');
                return; // Don't show error if we managed to refresh
            } catch (refreshError) {
                console.error('Failed to refresh after network error:', refreshError);
            }
            errorMessage = 'Network connection lost during analysis. Analysis might have completed - please check the Results tab.';
        } else if (error.message.includes('HTTP')) {
            errorMessage = `Server error: ${error.message}`;
        } else {
            errorMessage = error.message || 'Analysis failed';
        }
        
        this.showError(errorMessage);
    } finally {
        clearInterval(backupPolling); // Stop backup polling in all cases
        if (analysisCompleted) {
            this.completeProgressBar();
            setTimeout(() => this.hideProgress(), 400);
        } else {
            this.hideProgress();
        }
    }
}

export function runAnalysis() {
    if (this.currentProject) {
        this.analyzeProject(this.currentProject.id);
    }
}

