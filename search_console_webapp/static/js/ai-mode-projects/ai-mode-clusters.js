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
                        // Usar window.aiModeSystem para llamar al método
                        if (window.aiModeSystem && typeof window.aiModeSystem.addClusterRow === 'function') {
                            window.aiModeSystem.addClusterRow('clustersListCreate');
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
                        // Usar window.aiModeSystem para llamar al método
                        if (window.aiModeSystem && typeof window.aiModeSystem.addClusterRow === 'function') {
                            window.aiModeSystem.addClusterRow('clustersList');
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
        
        // Render chart and table (pasar data_freshness para validación de datos)
        this.renderClustersChart(chartData);
        this.renderClustersTable(tableData, data.data_freshness);
        
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
    
    // Destroy existing chart properly
    const existingChart = Chart.getChart('clustersChart');
    if (existingChart) {
        existingChart.destroy();
    }
    
    // Initialize charts object if needed
    if (!this.charts) {
        this.charts = {};
    }
    
    // Use data directly from backend (total_keywords como métrica base)
    const labels = chartData.labels || [];
    const totalKeywordsData = chartData.total_keywords || [];
    const mentionsData = chartData.mentions || [];
    
    console.log('📊 Chart prepared:', { labels, totalKeywordsData, mentionsData });
    
    // Create chart
    const ctx = canvas.getContext('2d');
    this.charts.clustersChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    type: 'bar',
                    label: 'Total Keywords',
                    data: totalKeywordsData,
                    backgroundColor: 'rgba(99, 102, 241, 0.7)',
                    borderColor: 'rgb(99, 102, 241)',
                    borderWidth: 1,
                    yAxisID: 'y',
                    order: 2
                },
                {
                    type: 'line',
                    label: 'Brand Mentions',
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
                        title: function(context) {
                            // Nombre del cluster
                            return context[0].label || '';
                        },
                        label: function(context) {
                            const datasetLabel = context.dataset.label;
                            const value = context.parsed.y || 0;
                            
                            if (datasetLabel === 'Total Keywords') {
                                return `Total Keywords: ${value}`;
                            } else if (datasetLabel === 'Brand Mentions') {
                                return `Brand Mentions: ${value}`;
                            }
                            return `${datasetLabel}: ${value}`;
                        },
                        afterLabel: function(context) {
                            // Calcular y mostrar % de menciones
                            const dataIndex = context.dataIndex;
                            const totalKeywords = totalKeywordsData[dataIndex] || 0;
                            const mentions = mentionsData[dataIndex] || 0;
                            
                            if (context.dataset.label === 'Brand Mentions' && totalKeywords > 0) {
                                const percentage = ((mentions / totalKeywords) * 100).toFixed(1);
                                return `% Mentions: ${percentage}%`;
                            }
                            return '';
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

export function renderClustersTable(clustersData, dataFreshness = null) {
    const tableContainer = document.getElementById('clustersTableContainer');
    const table = document.getElementById('clustersTable');
    
    if (!table) {
        console.error('❌ clustersTable not found');
        return;
    }
    
    console.log('📋 Rendering clusters table with data:', clustersData);
    
    if (!clustersData || clustersData.length === 0) {
        table.innerHTML = '<tbody><tr><td colspan="4" style="text-align: center;">No data available</td></tr></tbody>';
        return;
    }
    
    // Verificar si los datos están desactualizados (>24h)
    let dataStaleWarning = '';
    if (dataFreshness) {
        try {
            const freshnessDate = new Date(dataFreshness);
            const now = new Date();
            const hoursDiff = (now - freshnessDate) / (1000 * 60 * 60);
            
            if (hoursDiff > 24) {
                const daysDiff = Math.floor(hoursDiff / 24);
                dataStaleWarning = `
                    <div class="data-stale-warning" style="background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 12px; margin-bottom: 16px; border-radius: 4px;">
                        <i class="fas fa-exclamation-triangle" style="color: #F59E0B;"></i>
                        <strong>Data stale:</strong> Last analysis was ${daysDiff} day${daysDiff > 1 ? 's' : ''} ago.
                    </div>
                `;
            }
        } catch (e) {
            console.warn('⚠️ Error parsing data freshness:', e);
        }
    }
    
    // Crear filtro de búsqueda si no existe
    let searchFilterHtml = '';
    const existingFilter = document.getElementById('clustersSearchFilter');
    if (!existingFilter) {
        searchFilterHtml = `
            <div class="clusters-filter" style="margin-bottom: 16px;">
                <input type="text" 
                       id="clustersSearchFilter" 
                       placeholder="Search clusters..." 
                       style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px;">
            </div>
        `;
    }
    
    // Crear filas de la tabla (formato normal: cada fila es un cluster)
    const rows = clustersData.map((cluster, index) => {
        return `<tr class="cluster-table-row" data-cluster-name="${escapeHtml(cluster.cluster_name).toLowerCase()}">
            <td class="text-left"><strong>${escapeHtml(cluster.cluster_name)}</strong></td>
            <td class="text-center">${cluster.total_keywords || 0}</td>
            <td class="text-center">${cluster.mentions_count || 0}</td>
            <td class="text-center">${(cluster.mentions_percentage || 0).toFixed(1)}%</td>
        </tr>`;
    }).join('');
    
    // Renderizar tabla completa
    const tableHtml = `
        <thead>
            <tr>
                <th class="text-left">Cluster</th>
                <th class="text-center">Total Keywords</th>
                <th class="text-center">Brand Mentions</th>
                <th class="text-center">% Mentions</th>
            </tr>
        </thead>
        <tbody>
            ${rows}
        </tbody>
    `;
    
    // Insertar HTML
    if (tableContainer) {
        tableContainer.innerHTML = dataStaleWarning + searchFilterHtml + table.outerHTML;
        // Re-obtener referencia al table después de insertar HTML
        const updatedTable = document.getElementById('clustersTable');
        if (updatedTable) {
            updatedTable.innerHTML = tableHtml;
        }
    } else {
        table.innerHTML = tableHtml;
    }
    
    // Configurar filtro de búsqueda
    const searchInput = document.getElementById('clustersSearchFilter');
    if (searchInput && !existingFilter) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase().trim();
            const rows = document.querySelectorAll('.cluster-table-row');
            
            rows.forEach(row => {
                const clusterName = row.getAttribute('data-cluster-name') || '';
                if (clusterName.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Mostrar mensaje si no hay resultados
            const visibleRows = Array.from(rows).filter(row => row.style.display !== 'none');
            const tbody = document.querySelector('#clustersTable tbody');
            if (tbody) {
                const noResultsRow = tbody.querySelector('.no-results-row');
                if (visibleRows.length === 0 && !noResultsRow) {
                    tbody.insertAdjacentHTML('beforeend', '<tr class="no-results-row"><td colspan="4" style="text-align: center; padding: 20px; color: #6b7280;">No clusters match your search</td></tr>');
                } else if (visibleRows.length > 0 && noResultsRow) {
                    noResultsRow.remove();
                }
            }
        });
    }
    
    console.log('✅ Clusters table rendered successfully with', clustersData.length, 'clusters');
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
        
        // Si es 404, clusters no están configurados aún - es normal, no es error
        if (response.status === 404) {
            console.log('ℹ️ No clusters configured yet for this project');
            return;
        }
        
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
                        
                        if (window.aiModeSystem && typeof window.aiModeSystem.addClusterRow === 'function') {
                            window.aiModeSystem.addClusterRow('clustersList');
                            
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
