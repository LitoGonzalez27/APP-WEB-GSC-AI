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
    
    if (!clustersAnalysis || !clustersAnalysis.clusters || clustersAnalysis.clusters.length === 0) {
        console.warn('⚠️ No hay datos de clusters para mostrar');
        console.warn('🔍 Detalle del problema:', {
            hasData: !!clustersAnalysis,
            hasClusters: !!clustersAnalysis?.clusters,
            clustersLength: clustersAnalysis?.clusters?.length,
            fullData: clustersAnalysis
        });
        return;
    }

    // Buscar contenedor existente o crear uno nuevo
    let clustersContainer = container.querySelector('.topic-clusters-results');
    if (!clustersContainer) {
        clustersContainer = document.createElement('div');
        clustersContainer.className = 'topic-clusters-results';
        container.appendChild(clustersContainer);
    }

    // Crear el layout principal con título, tabla y gráfico
    const titleHTML = `<h3 class="topic-clusters-title">
        <i class="fas fa-project-diagram"></i>
        Topic Clusters Analysis
    </h3>`;
    
    const layoutHTML = `
        <div class="clusters-analysis-layout">
            <div class="clusters-table-column">
                ${createClustersTable(clustersAnalysis.clusters)}
            </div>
            <div class="clusters-chart-column">
                <div class="clusters-chart-container">
                    <canvas id="clustersChart"></canvas>
                </div>
            </div>
        </div>
    `;
    
    clustersContainer.innerHTML = titleHTML + layoutHTML;
    
    // Crear el gráfico de burbujas después de que el elemento esté en el DOM
    setTimeout(() => {
        createClustersBubbleChart(clustersAnalysis.clusters);
    }, 100);
    
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
    
    // Preparar datos para el gráfico de burbujas
    const chartData = clusters.map((cluster, index) => {
        // Filtrar clusters con datos válidos
        if (cluster.total_mentions === 0 && cluster.total_impressions === 0) {
            return null;
        }
        
        return {
            label: cluster.name,
            x: cluster.total_mentions, // Eje X: Menciones en AI Overview
            y: cluster.total_impressions, // Eje Y: Impresiones
            r: Math.max(5, Math.min(25, cluster.total_clicks / 10)), // Radio: Clics (escalado)
            clicks: cluster.total_clicks,
            aioKeywords: cluster.total_aio_keywords,
            keywordCount: cluster.keyword_count,
            avgPosition: cluster.avg_position
        };
    }).filter(data => data !== null);

    // Definir colores para las burbujas
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
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#ffffff',
                    borderWidth: 1,
                    titleFont: {
                        size: 14,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 12
                    },
                    padding: 12,
                    callbacks: {
                        title: function(context) {
                            return context[0].raw.label;
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
