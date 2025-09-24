/* ==============================================
   TOPIC CLUSTERS VISUALIZATION
   Visualización de resultados de análisis de Topic Clusters con tabla y gráfico de burbujas
   ============================================== */

/**
 * Muestra los resultados de análisis de Topic Clusters
 * @param {Object} clustersAnalysis - Datos de análisis de clusters del backend
 * @param {HTMLElement} container - Contenedor donde mostrar los resultados
 */
function displayTopicClustersResults(clustersAnalysis, container) {
    console.log('🔍 RECIBIENDO datos de clusters:', clustersAnalysis);
    console.log('🔍 Estructura clustersAnalysis:', JSON.stringify(clustersAnalysis, null, 2));
    
    // Siempre renderizamos la sección, incluso si no hay coincidencias
    const hasClustersArray = Array.isArray(clustersAnalysis?.clusters);
    const noData = !hasClustersArray || clustersAnalysis.clusters.length === 0;

    // Buscar contenedor existente o crear uno nuevo (usar mismas clases que competitor analysis)
    let clustersContainer = container.querySelector('.topic-clusters-results');
    if (!clustersContainer) {
        clustersContainer = document.createElement('div');
        clustersContainer.className = 'topic-clusters-results';
        container.appendChild(clustersContainer);
    }

    // Layout de una sola columna para mayor tamaño
    const titleHTML = `<h3 class="competitor-analysis-title">Topic Clusters Analysis</h3>`;
    
    const emptyStateHTML = `
        <div id="clustersEmptyState" style="display:flex;align-items:center;justify-content:center;padding:24px;color:#666;border:1px dashed rgba(0,0,0,0.15);border-radius:8px;background:rgba(0,0,0,0.02);margin-top:8px;text-align:center;">
            <div>
                <i class="fas fa-info-circle" style="font-size:20px;opacity:0.7;"></i>
                <p style="margin:8px 0 0 0;">No matches for the current clusters. Adjust the terms or the method.</p>
            </div>
        </div>`;

    const layoutHTML = `
        <div class="clusters-single-column-layout">
            <div class="clusters-chart-section">
                <div class="clusters-chart-container" id="clustersChartContainer">
                    <canvas id="clustersChart" ${noData ? 'style="display:none;"' : ''}></canvas>
                    ${noData ? emptyStateHTML : ''}
                </div>
            </div>
            <div class="clusters-table-section">
                ${createClustersTable(clustersAnalysis.clusters)}
            </div>
        </div>
    `;
    
    clustersContainer.innerHTML = titleHTML + layoutHTML;
    
    // Crear el gráfico de burbujas después de que el elemento esté en el DOM
    if (!noData) {
        setTimeout(() => {
            createClustersBubbleChart(clustersAnalysis.clusters);
        }, 100);
    }
    
    console.log(`✅ Mostrados resultados de ${clustersAnalysis.clusters.length} clusters`);
}

/**
 * Crea la tabla de resultados de clusters
 * @param {Array} clusters - Array de datos de clusters
 * @returns {string} HTML de la tabla
 */
function createClustersTable(clusters) {
    if (!clusters || clusters.length === 0) {
        return '<div class="clusters-no-data">No cluster data available</div>';
    }

    const tableRows = clusters.map(cluster => {
        const visibilityClass = getClusterVisibilityClass(cluster.total_mentions, cluster.total_aio_keywords);
        const positionClass = getClusterPositionClass(cluster.avg_position);
        
        return `
            <tr>
                <td class="cluster-name-cell">${escapeHtml(cluster.name)}</td>
                <td class="cluster-metric-cell">${cluster.total_aio_keywords}</td>
                <td class="cluster-metric-cell ${visibilityClass}">${cluster.total_mentions}</td>
                <td class="cluster-metric-cell">${formatNumber(cluster.total_clicks)}</td>
                <td class="cluster-metric-cell">${formatNumber(cluster.total_impressions)}</td>
                <td class="cluster-metric-cell ${positionClass}">${cluster.avg_position || 'N/A'}</td>
            </tr>
        `;
    }).join('');

    return `
        <div class="clusters-results-table">
            <table class="clusters-table">
                <thead>
                    <tr>
                        <th>Cluster Name</th>
                        <th>AIO Generated</th>
                        <th>Your Mentions</th>
                        <th>Total Clicks</th>
                        <th>Total Impressions</th>
                        <th>Avg Position</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRows}
                </tbody>
            </table>
        </div>
    `;
}

/**
 * Crea el gráfico de burbujas de clusters usando Chart.js
 * @param {Array} clusters - Array de datos de clusters
 */
function createClustersBubbleChart(clusters) {
    const canvas = document.getElementById('clustersChart');
    if (!canvas || !window.Chart) {
        console.warn('Canvas clustersChart no encontrado o Chart.js no disponible');
        return;
    }

    // Destruir gráfico existente si existe
    if (window.clustersChartInstance) {
        window.clustersChartInstance.destroy();
    }

    const ctx = canvas.getContext('2d');
    
    // Filtrar clusters válidos y preparar datos
    const validClusters = (Array.isArray(clusters) ? clusters : []).filter(cluster => 
        (cluster.total_mentions || 0) > 0 || (cluster.total_impressions || 0) > 0
    );

    // Estado vacío si no hay puntos válidos
    const containerDiv = canvas.parentElement;
    const emptyStateId = 'clustersEmptyState';
    const existingEmpty = containerDiv ? containerDiv.querySelector(`#${emptyStateId}`) : null;
    if (validClusters.length === 0) {
        // Ocultar canvas y mostrar estado vacío
        canvas.style.display = 'none';
        if (!existingEmpty && containerDiv) {
            const wrapper = document.createElement('div');
            wrapper.id = emptyStateId;
            wrapper.style.display = 'flex';
            wrapper.style.alignItems = 'center';
            wrapper.style.justifyContent = 'center';
            wrapper.style.padding = '24px';
            wrapper.style.color = '#666';
            wrapper.style.border = '1px dashed rgba(0,0,0,0.15)';
            wrapper.style.borderRadius = '8px';
            wrapper.style.background = 'rgba(0,0,0,0.02)';
            wrapper.style.marginTop = '8px';
            wrapper.style.textAlign = 'center';
            wrapper.innerHTML = `
                <div>
                    <i class="fas fa-info-circle" style="font-size:20px;opacity:0.7;"></i>
                    <p style="margin:8px 0 0 0;">Not enough data for the chart. No impressions or mentions in the current clusters.</p>
                </div>
            `;
            containerDiv.appendChild(wrapper);
        }
        return;
    } else {
        // Asegurar que el canvas esté visible y retirar cualquier estado vacío
        canvas.style.display = '';
        if (existingEmpty) existingEmpty.remove();
    }
    
    // Calcular rango de clicks para escalar burbujas proporcionalmente  
    const clicksValues = validClusters.map(cluster => cluster.total_clicks || 0);
    const minClicks = Math.min(...clicksValues);
    const maxClicks = Math.max(...clicksValues);
    
    console.log(`🎯 [BUBBLES DEBUG] Clicks range: min=${minClicks}, max=${maxClicks}`);
    console.log(`🎯 [BUBBLES DEBUG] All clicks values:`, clicksValues);
    
    // Preparar datos para el gráfico de burbujas
    const chartData = validClusters.map((cluster, index) => {
        // Calcular radio proporcional mejorado
        let radius = 10; // Radio mínimo
        
        if (maxClicks > 0 && cluster.total_clicks > 0) {
            if (maxClicks === minClicks) {
                // Si todos tienen los mismos clicks, usar tamaño medio
                radius = 20;
            } else {
                // Escalado logarítmico para mejor diferenciación
                const clicksNormalized = (cluster.total_clicks - minClicks) / (maxClicks - minClicks);
                radius = 10 + (clicksNormalized * 25); // Entre 10 y 35 pixels
            }
        }
        
        console.log(`🎯 [BUBBLES] ${cluster.name}: clicks=${cluster.total_clicks}, radius=${Math.round(radius)}`);
        
        return {
            label: cluster.name,
            x: cluster.total_mentions || 0, // Eje X: Menciones en AI Overview
            y: cluster.total_impressions || 0, // Eje Y: Impresiones
            r: Math.round(radius), // Radio: Clics escalados proporcionalmente
            clicks: cluster.total_clicks || 0,
            aioKeywords: cluster.total_aio_keywords || 0,
            keywordCount: cluster.keyword_count || 0,
            avgPosition: cluster.avg_position
        };
    });

    // Definir colores para las burbujas y crear mapping global
    const colors = [
        'rgba(79, 70, 229, 0.6)',  // Purple
        'rgba(16, 185, 129, 0.6)', // Green
        'rgba(245, 158, 11, 0.6)', // Yellow
        'rgba(239, 68, 68, 0.6)',  // Red
        'rgba(139, 92, 246, 0.6)', // Violet
        'rgba(34, 197, 94, 0.6)',  // Emerald
        'rgba(249, 115, 22, 0.6)', // Orange
        'rgba(236, 72, 153, 0.6)'  // Pink
    ];

    // 🆕 NUEVO: Crear mapping global de cluster name to color
    window.clusterColorMapping = {};
    chartData.forEach((cluster, index) => {
        const colorIndex = index % colors.length;
        window.clusterColorMapping[cluster.label] = {
            background: colors[colorIndex],
            border: colors[colorIndex].replace('0.6', '1'),
            solid: colors[colorIndex].replace('0.6', '1').replace('rgba', 'rgb').replace(', 1)', ')')
        };
    });

    const backgroundColors = chartData.map((_, index) => colors[index % colors.length]);
    const borderColors = backgroundColors.map(color => color.replace('0.6', '1'));

    window.clustersChartInstance = new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [{
                label: 'Topic Clusters',
                data: chartData,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        generateLabels: function(chart) {
                            const data = chart.data.datasets[0].data;
                            const backgroundColors = chart.data.datasets[0].backgroundColor;
                            
                            return data.map((point, index) => ({
                                text: point.label,
                                fillStyle: backgroundColors[index],
                                strokeStyle: chart.data.datasets[0].borderColor[index],
                                lineWidth: 2,
                                pointStyle: 'circle'
                            }));
                        },
                        usePointStyle: true,
                        padding: 20,
                        font: {
                            size: 12,
                            weight: '500'
                        }
                    }
                },
                tooltip: {
                    backgroundColor: '#ffffff',
                    titleColor: '#1f2937',
                    bodyColor: '#374151',
                    borderColor: '#e5e7eb',
                    borderWidth: 1,
                    cornerRadius: 8,
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
                    titleFont: {
                        size: 15,
                        weight: '600',
                        family: 'Inter, system-ui, sans-serif'
                    },
                    bodyFont: {
                        size: 13,
                        weight: '400',
                        family: 'Inter, system-ui, sans-serif'
                    },
                    padding: {
                        top: 12,
                        bottom: 12,
                        left: 16,
                        right: 16
                    },
                    displayColors: false,
                    titleSpacing: 8,
                    bodySpacing: 6,
                    callbacks: {
                        title: function(context) {
                            return context[0].raw.label;
                        },
                        beforeBody: function() {
                            return '';
                        },
                        label: function(context) {
                            const data = context.raw;
                            return [
                                `Mentions: ${data.x}`,
                                `Impressions: ${formatNumber(data.y)}`,
                                `Clicks: ${formatNumber(data.clicks)}`,
                                `Keywords: ${data.keywordCount}`,
                                `AIO Generated: ${data.aioKeywords}`,
                                `Avg Position: ${data.avgPosition || 'N/A'}`
                            ];
                        },
                        labelColor: function(context) {
                            return {
                                borderColor: 'transparent',
                                backgroundColor: 'transparent'
                            };
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Mentions in AI Overview',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        stepSize: 1,
                        precision: 0,
                        callback: function(value) {
                            return Number.isInteger(value) ? value : '';
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Total Impressions',
                        font: {
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        callback: function(value) {
                            if (value >= 1000000) {
                                return (value / 1000000).toFixed(1) + 'M';
                            } else if (value >= 1000) {
                                return (value / 1000).toFixed(0) + 'K';
                            }
                            return value;
                        }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'point'
            }
        }
    });

    console.log(`📊 Gráfico de burbujas de clusters creado con ${chartData.length} clusters`);
    console.log(`🎯 Tamaños de burbujas escalados proporcionalmente: min=${minClicks} clicks, max=${maxClicks} clicks`);
}

/**
 * Obtiene la clase CSS para el color de visibilidad del cluster
 * @param {number} mentions - Número de menciones
 * @param {number} aioKeywords - Número de keywords con AIO
 * @returns {string} Clase CSS
 */
function getClusterVisibilityClass(mentions, aioKeywords) {
    if (mentions === 0) return 'cluster-metric-low';
    if (mentions >= 5 || (mentions > 0 && aioKeywords >= 10)) return 'cluster-metric-high';
    return 'cluster-metric-medium';
}

/**
 * Obtiene la clase CSS para el color de posición del cluster
 * @param {number|null} position - Posición promedio
 * @returns {string} Clase CSS
 */
function getClusterPositionClass(position) {
    if (!position) return '';
    if (position <= 3) return 'cluster-metric-high';
    if (position <= 7) return 'cluster-metric-medium';
    return 'cluster-metric-low';
}

/**
 * Formatea un número para mostrar en la UI
 * @param {number} num - Número a formatear
 * @returns {string} Número formateado
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * Escapa HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string} Texto escapado
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Limpia los resultados de clusters del contenedor
 * @param {HTMLElement} container - Contenedor de resultados
 */
function clearTopicClustersResults(container) {
    const clustersContainer = container.querySelector('.topic-clusters-results');
    if (clustersContainer) {
        // Destruir gráfico existente
        if (window.clustersChartInstance) {
            window.clustersChartInstance.destroy();
            window.clustersChartInstance = null;
        }
        
        clustersContainer.remove();
        console.log('🗑️ Resultados de clusters limpiados');
    }
}

/**
 * Actualiza los resultados de clusters después de un nuevo análisis
 * @param {Object} analysisData - Datos completos del análisis AI Overview
 * @param {HTMLElement} container - Contenedor de resultados
 */
function updateTopicClustersResults(analysisData, container) {
    // Limpiar resultados anteriores
    clearTopicClustersResults(container);
    
    // Mostrar nuevos resultados si hay datos de clusters
    if (analysisData && analysisData.clusters_analysis) {
        displayTopicClustersResults(analysisData.clusters_analysis, container);
    }
}

// Exportar funciones para uso global
window.TopicClustersVisualization = {
    displayTopicClustersResults,
    clearTopicClustersResults,
    updateTopicClustersResults,
    createClustersBubbleChart
};

console.log('🎨 Topic Clusters Visualization module loaded');
