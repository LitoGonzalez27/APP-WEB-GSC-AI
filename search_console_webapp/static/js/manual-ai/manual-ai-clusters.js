/**
 * Manual AI System - Clusters Module
 * Gestión completa de Topic Clusters
 */

import { escapeHtml } from './manual-ai-utils.js';

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
            <label>Nombre del Cluster</label>
            <input type="text" 
                   class="cluster-name-input" 
                   placeholder="ej: Verifactu" 
                   value="${escapeHtml(clusterName)}">
        </div>
        
        <div class="cluster-row-field">
            <label>Términos (separados por comas)</label>
            <input type="text" 
                   class="cluster-terms-input" 
                   placeholder="ej: verifactu, veri-factu" 
                   value="${escapeHtml(clusterTerms)}">
        </div>
        
        <div class="cluster-row-field" style="flex: 0.5;">
            <label>Método</label>
            <select class="cluster-match-method">
                <option value="contains" ${matchMethod === 'contains' ? 'selected' : ''}>Contiene</option>
                <option value="exact" ${matchMethod === 'exact' ? 'selected' : ''}>Exacto</option>
                <option value="starts_with" ${matchMethod === 'starts_with' ? 'selected' : ''}>Empieza con</option>
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
    const enabled = this.elements.projectClustersEnabledCheckbox?.checked || false;
    
    if (!enabled) {
        return {
            enabled: false,
            clusters: []
        };
    }
    
    const clusters = [];
    const clusterRows = document.querySelectorAll('.cluster-row');
    
    clusterRows.forEach(row => {
        const nameInput = row.querySelector('.cluster-name-input');
        const termsInput = row.querySelector('.cluster-terms-input');
        const methodSelect = row.querySelector('.cluster-method-select');
        
        const name = nameInput?.value.trim();
        const termsText = termsInput?.value.trim();
        const method = methodSelect?.value || 'contains';
        
        if (name && termsText) {
            // Separar términos por comas y limpiar espacios
            const terms = termsText.split(',').map(t => t.trim()).filter(t => t.length > 0);
            
            if (terms.length > 0) {
                clusters.push({
                    name: name,
                    terms: terms,
                    match_method: method
                });
            }
        }
    });
    
    return {
        enabled: enabled && clusters.length > 0,
        clusters: clusters
    };
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
        this.showNoClustersMessage();
        return;
    }
    
    const days = this.elements.analyticsTimeRange?.value || 30;
    
    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/clusters/statistics?days=${days}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                this.showNoClustersMessage();
                return;
            }
            throw new Error('Failed to load clusters statistics');
        }
        
        const result = await response.json();
        const data = result.data || {};
        
        console.log('📊 Clusters statistics loaded:', data);
        
        if (!data.enabled || data.total_clusters === 0) {
            this.showNoClustersMessage();
            return;
        }
        
        // Renderizar gráfica y tabla
        this.renderClustersChart(data.chart_data);
        this.renderClustersTable(data.table_data);
        
    } catch (error) {
        console.error('Error loading clusters statistics:', error);
        this.showNoClustersMessage();
    }
}

export function renderClustersChart(chartData) {
    const ctx = document.getElementById('clustersChart');
    if (!ctx) {
        console.error('❌ clustersChart canvas not found');
        return;
    }
    
    // Destroy existing chart
    if (this.charts.clusters) {
        this.charts.clusters.destroy();
    }
    
    console.log('🔍 Rendering clusters chart with data:', chartData);
    
    if (!chartData || !chartData.labels || chartData.labels.length === 0) {
        console.warn('⚠️ No data for clusters chart');
        this.showNoClustersMessage();
        return;
    }
    
    // Show canvas
    ctx.style.display = 'block';
    const container = document.getElementById('clustersChartContainer');
    if (container) {
        container.style.display = 'block';
    }
    
    // Preparar datos para Chart.js (gráfica combinada: barras + línea)
    this.charts.clusters = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [
                {
                    type: 'bar',
                    label: 'AI Overview',
                    data: chartData.ai_overview,
                    backgroundColor: 'rgba(99, 102, 241, 0.7)',
                    borderColor: 'rgb(99, 102, 241)',
                    borderWidth: 1,
                    yAxisID: 'y',
                    order: 2
                },
                {
                    type: 'line',
                    label: 'Menciones de Marca',
                    data: chartData.mentions,
                    borderColor: 'rgb(34, 197, 94)',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointRadius: 5,
                    pointBackgroundColor: 'rgb(34, 197, 94)',
                    pointBorderColor: '#FFFFFF',
                    pointBorderWidth: 2,
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
                    display: true,
                    text: 'Clusters Temáticos: AI Overview y Menciones',
                    font: {
                        size: 16,
                        weight: '600'
                    },
                    color: '#1f2937'
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
                            return `Cluster: ${context[0].label}`;
                        },
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
                    title: {
                        display: true,
                        text: 'Número de Keywords',
                        color: '#374151',
                        font: {
                            size: 12,
                            weight: '500'
                        }
                    },
                    ticks: {
                        stepSize: 1,
                        color: '#6b7280'
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Clusters',
                        color: '#374151',
                        font: {
                            size: 12,
                            weight: '500'
                        }
                    },
                    ticks: {
                        color: '#6b7280',
                        maxRotation: 45,
                        minRotation: 0
                    },
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
    
    console.log('✅ Clusters chart rendered successfully');
}

export function renderClustersTable(tableData) {
    const tableBody = document.getElementById('clustersTableBody');
    const noDataMessage = document.getElementById('noClustersData');
    const table = document.getElementById('clustersTable');
    
    if (!tableBody || !table) {
        console.error('❌ Clusters table elements not found');
        return;
    }
    
    if (!tableData || tableData.length === 0) {
        if (noDataMessage) noDataMessage.style.display = 'block';
        if (table) table.style.display = 'none';
        return;
    }
    
    // Hide no data message and show table
    if (noDataMessage) noDataMessage.style.display = 'none';
    if (table) table.style.display = 'table';
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    // Render each cluster row
    tableData.forEach(cluster => {
        const row = document.createElement('tr');
        
        // Aplicar clase especial para Unclassified
        if (cluster.cluster_name === 'Unclassified') {
            row.className = 'unclassified-row';
        }
        
        row.innerHTML = `
            <td class="cluster-name-cell">
                <strong>${escapeHtml(cluster.cluster_name)}</strong>
            </td>
            <td class="text-center">${cluster.total_keywords}</td>
            <td class="text-center">${cluster.ai_overview_count}</td>
            <td class="text-center">${cluster.mentions_count}</td>
            <td class="text-center">
                <span class="badge badge-info">${cluster.ai_overview_percentage}%</span>
            </td>
            <td class="text-center">
                <span class="badge badge-success">${cluster.mentions_percentage}%</span>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    console.log('✅ Clusters table rendered with', tableData.length, 'clusters');
}

export function showNoClustersMessage() {
    console.log('⚠️ No clusters data available');
    
    const chartCanvas = document.getElementById('clustersChart');
    const chartContainer = document.getElementById('clustersChartContainer');
    const table = document.getElementById('clustersTable');
    const noDataMessage = document.getElementById('noClustersData');
    
    if (chartCanvas) chartCanvas.style.display = 'none';
    if (chartContainer) chartContainer.style.display = 'none';
    if (table) table.style.display = 'none';
    if (noDataMessage) noDataMessage.style.display = 'block';
}

// ================================
// SETTINGS - CLUSTERS CONFIGURATION
// ================================

export async function loadProjectClustersForSettings(projectId) {
    if (!projectId) return;
    
    try {
        const response = await fetch(`/manual-ai/api/projects/${projectId}/clusters`);
        if (!response.ok) throw new Error('Failed to load clusters');
        
        const data = await response.json();
        if (data.success) {
            this.loadClustersConfiguration(data.clusters_config);
        }
    } catch (error) {
        console.error('Error loading clusters for settings:', error);
    }
}

export async function saveClustersConfiguration(projectId) {
    if (!projectId) {
        this.showNotification('Error: No project selected', 'error');
        return;
    }
    
    try {
        const clustersConfig = this.getClustersConfiguration();
        
        console.log('💾 Saving clusters configuration:', clustersConfig);
        
        const response = await fetch(`/manual-ai/api/projects/${projectId}/clusters`, {
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
            this.showNotification('Clusters configuration saved successfully', 'success');
            
            // Si hay warnings, mostrarlos
            if (result.warnings && result.warnings.length > 0) {
                result.warnings.forEach(warning => {
                    this.showNotification(warning, 'warning');
                });
            }
            
            // Recargar estadísticas si estamos en la vista de analytics
            if (this.currentView === 'analytics') {
                this.loadClustersStatistics(projectId);
            }
        } else {
            const errorMsg = result.errors ? result.errors.join(', ') : result.error;
            this.showNotification(`Error saving clusters: ${errorMsg}`, 'error');
        }
        
    } catch (error) {
        console.error('Error saving clusters configuration:', error);
        this.showNotification('Error saving clusters configuration', 'error');
    }
}

