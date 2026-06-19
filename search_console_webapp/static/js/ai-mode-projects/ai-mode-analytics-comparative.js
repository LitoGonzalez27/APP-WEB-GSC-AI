/**
 * AI Mode System - Analytics — Comparative Charts (visibility / position)
 *
 * Extraído verbatim de ai-mode-analytics.js (refactor Fase 4).
 */

import { htmlLegendPlugin } from './ai-mode-utils.js';

// ================================
// COMPARATIVE CHARTS
// ================================

export async function loadComparativeCharts(projectId) {
    if (!projectId) {
        this.showNoComparativeChartsMessage();
        return;
    }

    const days = this.elements.analyticsTimeRange?.value || 30;

    try {
        const response = await fetch(`/ai-mode-projects/api/projects/${projectId}/comparative-charts?days=${days}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                console.warn('⚠️ Comparative charts endpoint returned 404');
                this.showNoComparativeChartsMessage();
                return;
            }
            throw new Error('Failed to load comparative charts data');
        }

        const result = await response.json();
        console.log('📊 Comparative charts data received:', result);
        const data = result.data || {};
        
        console.log('📈 Visibility chart:', data.visibility_chart);
        console.log('📉 Position chart:', data.position_chart);
        
        // Render both comparative charts
        this.renderComparativeVisibilityChart(data.visibility_chart || {});
        this.renderComparativePositionChart(data.position_chart || {});

    } catch (error) {
        console.error('❌ Error loading comparative charts:', error);
        this.showNoComparativeChartsMessage();
    }
}

export function renderComparativeVisibilityChart(chartData) {
    const ctx = document.getElementById('comparativeVisibilityChart');
    if (!ctx) {
        console.error('❌ comparativeVisibilityChart canvas not found');
        return;
    }

    // Destroy existing chart
    if (this.charts.comparativeVisibility) {
        this.charts.comparativeVisibility.destroy();
    }

    console.log('🔍 Rendering comparative visibility chart with data:', chartData);
    
    if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
        console.warn('⚠️ No datasets for comparative visibility chart');
        this.showNoComparativeChartsMessage();
        return;
    }
    
    console.log(`✅ Rendering comparative visibility chart with ${chartData.datasets.length} datasets`);
    
    // Show canvas and hide any "no data" messages
    ctx.style.display = 'block';
    const noDataMsg = ctx.parentElement?.querySelector('.no-data-message');
    if (noDataMsg) {
        noDataMsg.style.display = 'none';
    }

    // Modern Chart.js configuration with HTML Legend
    const config = this.getModernChartConfig(true, 'comparativeVisibilityLegend');
    
    this.charts.comparativeVisibility = new Chart(ctx, {
        type: 'line',
        data: {
            labels: (chartData.dates || []).map(d => new Date(d).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            })),
            datasets: chartData.datasets.map((dataset, index) => ({
                ...dataset,
                pointBackgroundColor: dataset.borderColor,
                pointBorderColor: '#FFFFFF',
                pointHoverBackgroundColor: dataset.borderColor,
                pointHoverBorderColor: '#FFFFFF',
                pointStyle: 'rectRounded',
                backgroundColor: dataset.borderColor ? dataset.borderColor.replace('rgb', 'rgba').replace(')', ', 0.3)') : 'rgba(99, 102, 241, 0.3)',
                fill: false,
                tension: 0.4
            }))
        },
        plugins: [htmlLegendPlugin],
        options: {
            ...config,
            scales: {
                ...config.scales,
                y: {
                    ...config.scales.y,
                    beginAtZero: true,
                    max: 100,
                    stacked: false,
                    title: {
                        display: true,
                        text: 'Share of Voice (%)',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    },
                    ticks: {
                        ...config.scales.y.ticks,
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    ...config.scales.x,
                    title: {
                        display: true,
                        text: 'Date',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    }
                }
            },
            plugins: {
                ...config.plugins,
                tooltip: {
                    ...config.plugins.tooltip,
                    callbacks: {
                        title: function(context) {
                            return new Date(chartData.dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                weekday: 'short',
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                            });
                        },
                        label: function(context) {
                            return `${context.dataset.label}: ${Math.round(context.raw)}% Share of Voice`;
                        }
                    }
                }
            }
        }
    });
}

export function renderComparativePositionChart(chartData) {
    const ctx = document.getElementById('comparativePositionChart');
    if (!ctx) {
        console.error('❌ comparativePositionChart canvas not found');
        return;
    }

    // Destroy existing chart
    if (this.charts.comparativePosition) {
        this.charts.comparativePosition.destroy();
    }

    console.log('🔍 Rendering comparative position chart with data:', chartData);
    
    if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
        console.warn('⚠️ No datasets for comparative position chart');
        this.showNoComparativeChartsMessage();
        return;
    }
    
    console.log(`✅ Rendering comparative position chart with ${chartData.datasets.length} datasets`);
    
    // Show canvas and hide any "no data" messages
    ctx.style.display = 'block';
    const noDataMsg = ctx.parentElement?.querySelector('.no-data-message');
    if (noDataMsg) {
        noDataMsg.style.display = 'none';
    }

    // Modern Chart.js configuration
    const config = this.getModernChartConfig(true, 'comparativePositionLegend');
    
    this.charts.comparativePosition = new Chart(ctx, {
        type: 'line',
        data: {
            labels: (chartData.dates || []).map(d => new Date(d).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            })),
            datasets: chartData.datasets.map((dataset, index) => ({
                ...dataset,
                pointBackgroundColor: dataset.borderColor,
                pointBorderColor: '#FFFFFF',
                pointHoverBackgroundColor: dataset.borderColor,
                pointHoverBorderColor: '#FFFFFF',
                pointStyle: 'rectRounded',
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.4
            }))
        },
        plugins: [htmlLegendPlugin],
        options: {
            ...config,
            scales: {
                ...config.scales,
                y: {
                    ...config.scales.y,
                    reverse: true,
                    beginAtZero: false,
                    min: 1,
                    max: 20,
                    ticks: {
                        ...config.scales.y.ticks,
                        stepSize: 1
                    },
                    title: {
                        display: true,
                        text: 'Position in AI Mode',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    }
                },
                x: {
                    ...config.scales.x,
                    title: {
                        display: true,
                        text: 'Date',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    }
                }
            },
            plugins: {
                ...config.plugins,
                tooltip: {
                    ...config.plugins.tooltip,
                    callbacks: {
                        title: function(context) {
                            return new Date(chartData.dates[context[0].dataIndex]).toLocaleDateString('en-US', {
                                weekday: 'short',
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                            });
                        },
                        label: function(context) {
                            return `${context.dataset.label}: Position ${Math.round(context.raw)}`;
                        }
                    }
                }
            }
        }
    });
}

export function showNoComparativeChartsMessage() {
    console.log('⚠️ No comparative charts data available');
    
    // Hide both charts and show empty state
    const visChart = document.getElementById('comparativeVisibilityChart');
    const posChart = document.getElementById('comparativePositionChart');
    
    if (visChart && visChart.parentElement) {
        const parent = visChart.parentElement;
        visChart.style.display = 'none';
        
        // Check if message already exists
        let message = parent.querySelector('.no-data-message');
        if (!message) {
            message = document.createElement('div');
            message.className = 'no-data-message';
            message.style.cssText = 'text-align: center; padding: 40px; color: #6b7280;';
            message.innerHTML = '<i class="fas fa-chart-line" style="font-size: 48px; margin-bottom: 16px; display: block; opacity: 0.3;"></i><p>No data available for visibility comparison</p><p style="font-size: 0.875rem; margin-top: 8px;">Add competitors to your project to see comparative analysis</p>';
            parent.appendChild(message);
        }
        message.style.display = 'block';
    }
    
    if (posChart && posChart.parentElement) {
        const parent = posChart.parentElement;
        posChart.style.display = 'none';
        
        // Check if message already exists
        let message = parent.querySelector('.no-data-message');
        if (!message) {
            message = document.createElement('div');
            message.className = 'no-data-message';
            message.style.cssText = 'text-align: center; padding: 40px; color: #6b7280;';
            message.innerHTML = '<i class="fas fa-chart-line" style="font-size: 48px; margin-bottom: 16px; display: block; opacity: 0.3;"></i><p>No data available for position comparison</p><p style="font-size: 0.875rem; margin-top: 8px;">Add competitors to your project to see comparative analysis</p>';
            parent.appendChild(message);
        }
        message.style.display = 'block';
    }
}
