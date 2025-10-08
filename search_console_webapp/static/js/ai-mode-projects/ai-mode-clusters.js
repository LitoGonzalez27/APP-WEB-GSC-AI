/**
 * Manual AI System - Clusters Module
 * Gestión completa de Topic Clusters
 */

import { escapeHtml } from './ai-mode-utils.js';

// ================================
// CLUSTERS CONFIGURATION
// ================================

export function initializeClustersConfiguration() {
    console.log('🎯 Initializing Clusters Configuration...');
    
    // Event listener para toggle en modal de creación
    const enableClustersCreate = document.getElementById('enableClustersCreate');
    if (enableClustersCreate) {
        console.log('✅ Found enableClustersCreate checkbox');
        enableClustersCreate.addEventListener('change', function() {
            const clustersConfigArea = document.getElementById('clustersConfigArea');
            if (clustersConfigArea) {
                console.log(`🔄 Toggle clusters create: ${this.checked}`);
                clustersConfigArea.style.display = this.checked ? 'block' : 'none';
                clustersConfigArea.setAttribute('aria-hidden', !this.checked);
                
                // Si se activa y no hay clusters, añadir uno por defecto
                if (this.checked) {
                    const clustersListCreate = document.getElementById('clustersListCreate');
                    if (clustersListCreate && clustersListCreate.children.length === 0) {
                        // Usar window.manualAI para llamar al método
                        if (window.manualAI && typeof window.manualAI.addClusterRow === 'function') {
                            window.manualAI.addClusterRow('clustersListCreate');
                        }
                    }
                }
            }
        });
    } else {
        console.warn('⚠️ enableClustersCreate not found');
    }
    
    // Event listener para toggle en modal de settings
    const projectClustersEnabled = document.getElementById('projectClustersEnabled');
    if (projectClustersEnabled) {
        console.log('✅ Found projectClustersEnabled checkbox');
        projectClustersEnabled.addEventListener('change', function() {
            const projectClustersContainer = document.getElementById('projectClustersContainer');
            if (projectClustersContainer) {
                console.log(`🔄 Toggle clusters settings: ${this.checked}`);
                projectClustersContainer.style.display = this.checked ? 'block' : 'none';
                
                // Si se activa y no hay clusters, añadir uno por defecto
                if (this.checked) {
                    const clustersList = document.getElementById('clustersList');
                    if (clustersList && clustersList.children.length === 0) {
                        // Usar window.manualAI para llamar al método
                        if (window.manualAI && typeof window.manualAI.addClusterRow === 'function') {
                            window.manualAI.addClusterRow('clustersList');
                        }
                    }
                }
            }
        });
    } else {
        console.warn('⚠️ projectClustersEnabled not found');
    }
    
    console.log('✅ Clusters Configuration initialized');
}

export function toggleClustersConfiguration(enabled) {
    const clustersContainer = document.getElementById('projectClustersContainer');
    if (!clustersContainer) return;
    
    if (enabled) {
        clustersContainer.style.display = 'block';
        // Si no hay clusters, añadir uno por defecto
        const clustersRows = document.querySelectorAll('.cluster-row');
        if (clustersRows.length === 0) {
            this.addClusterRow();
        }
    } else {
        clustersContainer.style.display = 'none';
    }
}

export function addClusterRow(containerIdOrData = null) {
    // Allow calling with just container ID or with cluster data
    let containerId = 'clustersList'; // default
    let clusterData = null;
    
    if (typeof containerIdOrData === 'string') {
        containerId = containerIdOrData;
    } else if (containerIdOrData && typeof containerIdOrData === 'object') {
        clusterData = containerIdOrData;
    }
    
    const clustersContainer = document.getElementById(containerId);
    if (!clustersContainer) {
        console.warn(`⚠️ Container ${containerId} not found for cluster row`);
        return;
    }
    
    const clusterIndex = clustersContainer.children.length;
    const clusterName = clusterData?.name || '';
    const clusterTerms = clusterData?.terms ? clusterData.terms.join(', ') : '';
    const matchMethod = clusterData?.match_method || 'contains';
    
    const clusterRow = document.createElement('div');
    clusterRow.className = 'cluster-row';
    clusterRow.dataset.clusterIndex = clusterIndex;
    
    clusterRow.innerHTML = `
        <div class="cluster-row-field">
            <label>Cluster Name</label>
            <input type="text" 
                   class="cluster-name-input" 
                   placeholder="e.g. Verifactu" 
                   value="${escapeHtml(clusterName)}">
        </div>
        
        <div class="cluster-row-field">
            <label>Terms (comma separated)</label>
            <input type="text" 
                   class="cluster-terms-input" 
                   placeholder="e.g. verifactu, veri-factu" 
                   value="${escapeHtml(clusterTerms)}">
        </div>
        
        <div class="cluster-row-field" style="flex: 0.5;">
            <label>Method</label>
            <select class="cluster-match-method">
                <option value="contains" ${matchMethod === 'contains' ? 'selected' : ''}>Contains</option>
                <option value="exact" ${matchMethod === 'exact' ? 'selected' : ''}>Exact</option>
                <option value="starts_with" ${matchMethod === 'starts_with' ? 'selected' : ''}>Starts with</option>
                <option value="regex" ${matchMethod === 'regex' ? 'selected' : ''}>Regex</option>
            </select>
        </div>
        
        <div class="cluster-row-actions">
            <button type="button" class="btn-remove-cluster" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `;
    
    clustersContainer.appendChild(clusterRow);
    console.log(`✅ Cluster row added to ${containerId}`);
}

export function getClustersConfiguration() {
    // Get the checkbox from DOM directly (it might be in either location)
    const enabledCheckbox = document.getElementById('projectClustersEnabled') || 
                           document.getElementById('enableClustersCreate');
    const enabled = enabledCheckbox?.checked || false;
    
    console.log('🔍 getClustersConfiguration - enabled:', enabled);
    
    if (!enabled) {
        console.log('⚠️ Clusters not enabled, returning empty config');
        return {
            enabled: false,
            clusters: []
        };
    }
    
    const clusters = [];
    const clusterRows = document.querySelectorAll('.cluster-row');
    
    console.log(`🔍 Found ${clusterRows.length} cluster rows`);
    
    clusterRows.forEach(row => {
        const nameInput = row.querySelector('.cluster-name-input');
        const termsInput = row.querySelector('.cluster-terms-input');
        const methodSelect = row.querySelector('.cluster-match-method');  // ✅ FIXED: correct class name
        
        const name = nameInput?.value.trim();
        const termsText = termsInput?.value.trim();
        const method = methodSelect?.value || 'contains';
        
        if (name && termsText) {
            // Separar términos por comas y limpiar espacios
            const terms = termsText.split(',').map(t => t.trim()).filter(t => t.length > 0);
            
            if (terms.length > 0) {
                const cluster = {
                    name: name,
                    terms: terms,
                    match_method: method
                };
                clusters.push(cluster);
                console.log('✅ Cluster added:', cluster);
            } else {
                console.log('⚠️ No terms found for cluster:', name);
            }
        } else {
            console.log('⚠️ Skipping row - name or terms missing');
        }
    });
    
    const config = {
        enabled: enabled && clusters.length > 0,
        clusters: clusters
    };
    
    console.log('📦 Final clusters configuration:', config);
    return config;
}

export function loadClustersConfiguration(clustersConfig) {
    if (!clustersConfig) return;
    
    // Habilitar/deshabilitar clusters
    const enabled = clustersConfig.enabled || false;
    if (this.elements.projectClustersEnabledCheckbox) {
        this.elements.projectClustersEnabledCheckbox.checked = enabled;
        this.toggleClustersConfiguration(enabled);
    }
    
    // Limpiar clusters existentes
    const clustersContainer = document.getElementById('clustersList');
    if (clustersContainer) {
        clustersContainer.innerHTML = '';
    }
    
    // Cargar clusters
    const clusters = clustersConfig.clusters || [];
    clusters.forEach(cluster => {
        this.addClusterRow(cluster);
    });
}

// ================================
// CLUSTERS STATISTICS & VISUALIZATION
// ================================

export async function loadClustersStatistics(projectId) {
    if (!projectId) {
        console.warn('⚠️ No projectId provided');
        this.showNoClustersMessage();
        return;
    }
    
    const days = 30; // Default 30 days
    
    try {
        console.log(`📊 Loading clusters statistics for project ${projectId}, days: ${days}`);
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/clusters/statistics?days=${days}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                console.log('ℹ️ No clusters data (404)');
                this.showNoClustersMessage();
                return;
            }
            throw new Error('Failed to load clusters statistics');
        }
        
        const result = await response.json();
        console.log('📦 Clusters statistics result:', result);
        
        if (!result.success) {
            console.log('ℹ️ Request not successful');
            this.showNoClustersMessage();
            return;
        }
        
        // Get data from the nested structure
        const data = result.data || {};
        const tableData = data.table_data || [];
        const chartData = data.chart_data || {};
        
        console.log('📊 Statistics data:', { tableData, chartData, enabled: data.enabled });
        
        if (!data.enabled) {
            console.log('ℹ️ Clusters not enabled');
            this.showNoClustersMessage('not_enabled');
            return;
        }
        
        if (tableData.length === 0) {
            console.log('ℹ️ No clusters data - probably no analysis results yet');
            this.showNoClustersMessage('no_data');
            return;
        }
        
        console.log(`✅ Found ${tableData.length} clusters with data`);
        
        // Show visualization section
        const visualizationSection = document.getElementById('clustersVisualization');
        const noDataMessage = document.getElementById('noClustersMessage');
        
        if (visualizationSection) {
            visualizationSection.style.display = 'block';
        }
        if (noDataMessage) {
            noDataMessage.style.display = 'none';
        }
        
        // Render chart and table
        this.renderClustersChart(chartData);
        this.renderClustersTable(tableData);
        
    } catch (error) {
        console.error('❌ Error loading clusters statistics:', error);
        this.showNoClustersMessage();
    }
}

export function renderClustersChart(chartData) {
    const canvas = document.getElementById('clustersChart');
    if (!canvas) {
        console.error('❌ clustersChart canvas not found');
        return;
    }
    
    console.log('📊 Rendering clusters chart with data:', chartData);
    
    if (!chartData || !chartData.labels || chartData.labels.length === 0) {
        console.warn('⚠️ No data for clusters chart');
        this.showNoClustersMessage();
        return;
    }
    
    // Destroy existing chart
    if (!this.charts) {
        this.charts = {};
    }
    if (this.charts.clustersChart) {
        this.charts.clustersChart.destroy();
    }
    
    // Use data directly from backend
    const labels = chartData.labels || [];
    const aiOverviewData = chartData.ai_overview || [];
    const mentionsData = chartData.mentions || [];
    
    console.log('📊 Chart prepared:', { labels, aiOverviewData, mentionsData });
    
    // Create chart
    const ctx = canvas.getContext('2d');
    this.charts.clustersChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    type: 'bar',
                    label: 'Keywords with AI Overview',
                    data: aiOverviewData,
                    backgroundColor: 'rgba(99, 102, 241, 0.7)',
                    borderColor: 'rgb(99, 102, 241)',
                    borderWidth: 1,
                    yAxisID: 'y',
                    order: 2
                },
                {
                    type: 'line',
                    label: 'Keywords with Brand Mentions',
                    data: mentionsData,
                    borderColor: 'rgb(34, 197, 94)',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    borderWidth: 3,
                    fill: false,
                    tension: 0.4,
                    pointRadius: 6,
                    pointBackgroundColor: 'rgb(34, 197, 94)',
                    pointBorderColor: '#FFFFFF',
                    pointBorderWidth: 2,
                    pointHoverRadius: 8,
                    yAxisID: 'y',
                    order: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                title: {
                    display: false
                },
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: '#1f2937',
                    bodyColor: '#4b5563',
                    borderColor: '#e5e7eb',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            const label = context.dataset.label || '';
                            const value = context.parsed.y || 0;
                            return `${label}: ${value} keywords`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                        precision: 0
                    },
                    title: {
                        display: true,
                        text: 'Number of Keywords'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Cluster Name'
                    }
                }
            }
        }
    });
    
    console.log('✅ Clusters chart rendered successfully');
}

export function renderClustersTable(clustersData) {
    const table = document.getElementById('clustersTable');
    if (!table) {
        console.error('❌ clustersTable not found');
        return;
    }
    
    console.log('📋 Rendering clusters table (transposed) with data:', clustersData);
    
    if (!clustersData || clustersData.length === 0) {
        table.innerHTML = '<tbody><tr><td style="text-align: center;">No data available</td></tr></tbody>';
        return;
    }
    
    // Transponer la tabla: las columnas son los clusters, las filas son las métricas
    const metrics = [
        { label: 'Total Keywords', key: 'total_keywords', format: (v) => v || 0 },
        { label: 'AI Overview', key: 'ai_overview_count', format: (v) => v || 0 },
        { label: 'Brand Mentions', key: 'mentions_count', format: (v) => v || 0 },
        { label: '% AI Overview', key: 'ai_overview_percentage', format: (v) => `${(v || 0).toFixed(1)}%` },
        { label: '% Mentions', key: 'mentions_percentage', format: (v) => `${(v || 0).toFixed(1)}%` }
    ];
    
    // Crear header con nombres de clusters
    const headerCells = clustersData.map(cluster => 
        `<th class="text-center">${escapeHtml(cluster.cluster_name)}</th>`
    ).join('');
    
    // Crear filas de métricas
    const rows = metrics.map(metric => {
        const cells = clustersData.map(cluster => 
            `<td class="text-center">${metric.format(cluster[metric.key])}</td>`
        ).join('');
        
        return `<tr>
            <th class="metric-label">${metric.label}</th>
            ${cells}
        </tr>`;
    }).join('');
    
    table.innerHTML = `
        <thead>
            <tr>
                <th class="metric-header">Metric</th>
                ${headerCells}
            </tr>
        </thead>
        <tbody>
            ${rows}
        </tbody>
    `;
    
    console.log('✅ Clusters table (transposed) rendered successfully');
}

export function showNoClustersMessage(reason = 'not_enabled') {
    const visualizationSection = document.getElementById('clustersVisualization');
    const noDataMessage = document.getElementById('noClustersMessage');
    
    if (visualizationSection) {
        visualizationSection.style.display = 'block';
    }
    
    if (noDataMessage) {
        noDataMessage.style.display = 'block';
        
        // Update message based on reason
        const messageTitle = noDataMessage.querySelector('h4');
        const messageParagraph = noDataMessage.querySelector('p');
        
        if (reason === 'no_data') {
            if (messageTitle) messageTitle.textContent = 'No Analysis Data Yet';
            if (messageParagraph) messageParagraph.textContent = 'Run an analysis to see cluster statistics. Your clusters are configured and ready!';
        } else {
            if (messageTitle) messageTitle.textContent = 'No Cluster Data Available';
            if (messageParagraph) messageParagraph.textContent = 'Enable and configure thematic clusters in project settings to see analysis by topic';
        }
    }
    
    // Hide chart and table
    const chartSection = document.querySelector('.clusters-chart-section');
    const tableSection = document.querySelector('.clusters-table-section');
    
    if (chartSection) {
        chartSection.style.display = 'none';
    }
    if (tableSection) {
        tableSection.style.display = 'none';
    }
    
    console.log(`ℹ️ Showing no clusters message (reason: ${reason})`);
}

// ================================
// SETTINGS - CLUSTERS CONFIGURATION
// ================================

export async function loadProjectClustersForSettings(projectId) {
    if (!projectId) {
        console.warn('⚠️ No projectId provided');
        return;
    }
    
    try {
        console.log(`🔄 Loading clusters for project ${projectId}`);
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/clusters`);
        if (!response.ok) throw new Error('Failed to load clusters');
        
        const data = await response.json();
        console.log('📦 Clusters data:', data);
        
        if (data.success && data.clusters_config) {
            const config = data.clusters_config;
            
            // Update checkbox
            const enabledCheckbox = document.getElementById('projectClustersEnabled');
            if (enabledCheckbox) {
                enabledCheckbox.checked = config.enabled || false;
                console.log(`✅ Checkbox set to: ${config.enabled}`);
                
                // Trigger change event to show/hide container
                if (config.enabled) {
                    const event = new Event('change');
                    enabledCheckbox.dispatchEvent(event);
                }
            }
            
            // Load clusters if enabled
            if (config.enabled && config.clusters && config.clusters.length > 0) {
                const clustersList = document.getElementById('clustersList');
                if (clustersList) {
                    clustersList.innerHTML = '';
                    
                    // Add each cluster
                    config.clusters.forEach((cluster, index) => {
                        console.log(`➕ Adding cluster ${index + 1}:`, cluster);
                        
                        if (window.manualAI && typeof window.manualAI.addClusterRow === 'function') {
                            window.manualAI.addClusterRow('clustersList');
                            
                            // Populate the last added row
                            const rows = clustersList.querySelectorAll('.cluster-row');
                            const lastRow = rows[rows.length - 1];
                            if (lastRow) {
                                const nameInput = lastRow.querySelector('.cluster-name-input');
                                const termsInput = lastRow.querySelector('.cluster-terms-input');
                                const methodSelect = lastRow.querySelector('.cluster-match-method');
                                
                                if (nameInput) nameInput.value = cluster.name || '';
                                if (termsInput) termsInput.value = Array.isArray(cluster.terms) ? cluster.terms.join(', ') : cluster.terms || '';
                                if (methodSelect) methodSelect.value = cluster.match_method || 'contains';
                            }
                        }
                    });
                    console.log(`✅ Loaded ${config.clusters.length} clusters`);
                }
            }
        }
    } catch (error) {
        console.error('❌ Error loading clusters for settings:', error);
    }
}

export async function saveClustersConfiguration(projectId = null) {
    // If no projectId provided, try to get from current modal project
    if (!projectId) {
        projectId = this.currentModalProject?.id;
    }
    
    if (!projectId) {
        this.showError('No project selected');
        return;
    }
    
    try {
        const clustersConfig = this.getClustersConfiguration();
        
        console.log('💾 Saving clusters configuration:', clustersConfig);
        
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/clusters`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                clusters_config: clustersConfig
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            this.showSuccess('Clusters configuration saved successfully');
            console.log('✅ Clusters configuration saved');
            
            // Reload clusters statistics if in analytics view
            if (this.currentView === 'analytics') {
                this.loadClustersStatistics(projectId);
            }
        } else {
            const errorMsg = result.errors ? result.errors.join(', ') : result.error;
            this.showError(`Error saving clusters: ${errorMsg}`);
        }
        
    } catch (error) {
        console.error('Error saving clusters configuration:', error);
        this.showError('Error saving clusters configuration');
    }
}

// ================================
// PROJECT CARD - CLUSTERS PREVIEW
// ================================

export function renderProjectClustersHorizontal(project) {
    const clustersConfig = project.topic_clusters || {};
    const clustersEnabled = clustersConfig.enabled || false;
    const clustersList = clustersConfig.clusters || [];
    const clustersCount = clustersList.length;
    
    if (!clustersEnabled || clustersCount === 0) {
        return ''; // No mostrar nada si no hay clusters
    }
    
    // Mostrar hasta 3 clusters
    const displayClusters = clustersList.slice(0, 3);
    const moreCount = clustersCount > 3 ? clustersCount - 3 : 0;
    
    const clustersBadges = displayClusters.map(cluster => {
        const escapedName = cluster.name.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `
            <span class="cluster-badge" title="${escapedName}">
                <i class="fas fa-layer-group"></i>
                ${escapedName}
            </span>
        `;
    }).join('');
    
    const moreText = moreCount > 0 ? `<span class="clusters-more">+${moreCount} more</span>` : '';
    
    return `
        <div class="project-clusters-horizontal">
            <h5 class="clusters-section-title">Thematic Clusters</h5>
            <div class="clusters-horizontal-list">
                ${clustersBadges}
                ${moreText}
            </div>
        </div>
    `;
}
