/**
 * Manual AI System - Charts Module
 * Gestión de gráficos Chart.js (visibility, positions, annotations)
 */

import { htmlLegendPlugin } from './manual-ai-utils.js';

// ================================
// VISIBILITY CHART
// ================================

export function renderVisibilityChart(data, events = []) {
    const canvasEl = document.getElementById('visibilityChart');
    if (!canvasEl || !data || data.length === 0) return;

    const ctx = canvasEl.getContext('2d');
    
    // Destroy existing chart (limpiando listeners previos primero)
    if (this.charts.visibility) {
        this.clearEventAnnotations(this.charts.visibility);
        this.charts.visibility.destroy();
    }

    // Modern Chart.js configuration with HTML Legend
    const config = this.getModernChartConfig(true, 'visibilityLegend');
    
    this.charts.visibility = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => new Date(d.analysis_date).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            })),
            datasets: [{
                label: 'Keywords with AI Overview',
                data: data.map(d => d.ai_keywords || 0),
                borderColor: '#5BF0AF',
                backgroundColor: 'rgba(91, 240, 175, 0.12)',
                pointBackgroundColor: '#5BF0AF',
                pointBorderColor: '#FFFFFF',
                pointHoverBackgroundColor: '#45D190',
                pointHoverBorderColor: '#FFFFFF',
                pointStyle: 'rectRounded',
                fill: 'start',
                tension: 0.4
            }, {
                label: 'Domain Mentions',
                data: data.map(d => d.mentions || 0),
                borderColor: '#F0715B',
                backgroundColor: 'rgba(240, 113, 91, 0.12)',
                pointBackgroundColor: '#F0715B',
                pointBorderColor: '#FFFFFF',
                pointHoverBackgroundColor: '#E55A42',
                pointHoverBorderColor: '#FFFFFF',
                pointStyle: 'rectRounded',
                fill: 'start',
                tension: 0.4
            }]
        },
        plugins: [htmlLegendPlugin],
        options: {
            ...config,
            scales: {
                ...config.scales,
                y: {
                    ...config.scales.y,
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Count',
                        color: '#374151',
                        font: { size: 12, weight: '500' }
                    },
                    ticks: {
                        ...config.scales.y.ticks,
                        callback: function(value) {
                            return Math.round(value);
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
                            return new Date(data[context[0].dataIndex].analysis_date).toLocaleDateString('en-US', {
                                weekday: 'short',
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                            });
                        },
                        label: function(context) {
                            const datasetLabel = context.dataset.label;
                            const value = Math.round(context.raw);
                            
                            if (datasetLabel === 'Keywords with AI Overview') {
                                return `Keywords with AI Overview: ${value}`;
                            } else if (datasetLabel === 'Domain Mentions') {
                                return `Domain Mentions: ${value}`;
                            }
                            return `${datasetLabel}: ${value}`;
                        }
                    }
                }
            }
        }
    });

    // 🔄 Limpiar anotaciones y listeners anteriores siempre que re-renderizamos
    this.clearEventAnnotations(this.charts.visibility);

    // ✅ MEJORADO: Aplicar anotaciones de eventos de keywords
    if (events && events.length > 0) {
        const annotations = this.createEventAnnotations(data, events);
        if (annotations && annotations.length > 0) {
            // ✅ MEJORADO: Registrar plugin usando Chart.js 3.x+ API
            if (!Chart.registry.plugins.get('keywordEventAnnotations')) {
                Chart.register({
                    id: 'keywordEventAnnotations',
                    afterDraw: (chart) => {
                        const annotationsData = chart.options.annotationsData;
                        if (annotationsData && annotationsData.length > 0) {
                            this.drawEventAnnotations(chart, annotationsData);
                        }
                    }
                });
            }
            
            // Guardar anotaciones en las opciones del chart
            this.charts.visibility.options.annotationsData = annotations;
            
            // Configurar eventos de mouse para tooltips
            setTimeout(() => {
                this.showEventAnnotations(this.charts.visibility, annotations);
            }, 100);
            
            // Re-render con las anotaciones
            this.charts.visibility.update();
        }
    } else {
        // Asegurar estado limpio cuando no hay eventos
        this.charts.visibility.options.annotationsData = [];
        this.clearEventAnnotations(this.charts.visibility);
    }
}

// ================================
// POSITIONS CHART
// ================================

export function renderPositionsChart(data, events = []) {
    const canvasEl = document.getElementById('positionsChart');
    if (!canvasEl || !data || data.length === 0) return;

    const ctx = canvasEl.getContext('2d');
    
    // Destroy existing chart
    if (this.charts.positions) {
        this.charts.positions.destroy();
    }

    // Modern Chart.js configuration with modern colors
    const config = this.getModernChartConfig(true, 'positionsLegend');
    
    this.charts.positions = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => new Date(d.analysis_date).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            })),
            datasets: [
                {
                    label: 'Position 1-3',
                    data: data.map(d => d.pos_1_3 || 0),
                    borderColor: '#5BF0AF',
                    backgroundColor: 'rgba(91, 240, 175, 0.12)',
                    pointBackgroundColor: '#5BF0AF',
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: '#45D190',
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    fill: 'start',
                    tension: 0.4
                },
                {
                    label: 'Position 4-10',
                    data: data.map(d => d.pos_4_10 || 0),
                    borderColor: '#1851F1',
                    backgroundColor: 'rgba(24, 81, 241, 0.12)',
                    pointBackgroundColor: '#1851F1',
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: '#1040D6',
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    fill: 'start',
                    tension: 0.4
                },
                {
                    label: 'Position 11-20',
                    data: data.map(d => d.pos_11_20 || 0),
                    borderColor: '#F0715B',
                    backgroundColor: 'rgba(240, 113, 91, 0.12)',
                    pointBackgroundColor: '#F0715B',
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: '#E55A42',
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    fill: 'start',
                    tension: 0.4
                },
                {
                    label: 'Position 21+',
                    data: data.map(d => d.pos_21_plus || 0),
                    borderColor: '#8EAA96',
                    backgroundColor: 'rgba(142, 170, 150, 0.12)',
                    pointBackgroundColor: '#8EAA96',
                    pointBorderColor: '#FFFFFF',
                    pointHoverBackgroundColor: '#6B8A77',
                    pointHoverBorderColor: '#FFFFFF',
                    pointStyle: 'rectRounded',
                    fill: 'start',
                    tension: 0.4
                }
            ]
        },
        plugins: [htmlLegendPlugin],
        options: {
            ...config,
            scales: {
                ...config.scales,
                y: {
                    ...config.scales.y,
                    beginAtZero: true,
                    stacked: true,
                    title: {
                        display: true,
                        text: 'Number of Keywords',
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
                            return new Date(data[context[0].dataIndex].analysis_date).toLocaleDateString('en-US', {
                                weekday: 'short',
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                            });
                        },
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw} keywords`;
                        }
                    }
                }
            }
        }
    });

    // ❌ REMOVIDO: No queremos anotaciones en la gráfica de posiciones
}

// ================================
// EVENT ANNOTATIONS
// ================================

export function createEventAnnotations(chartData, events) {
    if (!events || events.length === 0) return [];
    
    // ✅ MEJORADO: Eventos de cambios de keywords Y notas manuales
    const relevantEvents = events.filter(event => 
        event.event_type === 'keywords_added' ||
        event.event_type === 'keyword_deleted' ||
        event.event_type === 'keywords_removed' ||
        event.event_type === 'manual_note_added'  // ✅ NUEVO: Incluir notas manuales
    );
    
    if (relevantEvents.length === 0) return [];
    
    const chartDates = chartData.map(d => new Date(d.analysis_date).toDateString());
    
    return relevantEvents.map(event => {
        const eventDate = new Date(event.event_date).toDateString();
        const dateIndex = chartDates.indexOf(eventDate);
        
        // ✅ CORREGIDO: Solo crear anotación si la fecha del evento coincide con datos del chart
        if (dateIndex === -1) return null;
        
        return {
            x: dateIndex,
            title: event.event_title,
            type: event.event_type,
            keywords: event.keywords_affected,
            date: eventDate,
            event: event, // Incluir evento completo para tooltips
        };
    }).filter(Boolean);
}

export function drawEventAnnotations(chart, annotations) {
    if (!annotations || annotations.length === 0) return;
    
    const ctx = chart.ctx;
    const chartArea = chart.chartArea;
    
    annotations.forEach(annotation => {
        // ✅ MEJORADO: Calcular posición correcta basada en el índice de datos
        const xPos = chart.scales.x.getPixelForValue(annotation.x);
        
        if (xPos < chartArea.left || xPos > chartArea.right) return; // Skip if outside chart
        
        // ✅ MEJORADO: Línea vertical más visible
        ctx.save();
        ctx.strokeStyle = this.getEventColor(annotation.type);
        ctx.lineWidth = 3;  // Más gruesa
        ctx.setLineDash([8, 4]); // Línea más definida
        ctx.globalAlpha = 0.8;
        ctx.beginPath();
        ctx.moveTo(xPos, chartArea.top);
        ctx.lineTo(xPos, chartArea.bottom);
        ctx.stroke();
        
        // ✅ MEJORADO: Círculo de fondo para el icono
        ctx.globalAlpha = 1;
        ctx.fillStyle = this.getEventColor(annotation.type);
        ctx.beginPath();
        ctx.arc(xPos, chartArea.top - 12, 10, 0, 2 * Math.PI);
        ctx.fill();
        
        // ✅ MEJORADO: Icono de warning más visible
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 14px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(this.getEventIcon(annotation.type), xPos, chartArea.top - 12);
        
        ctx.restore();
    });
}

export function getEventColor(eventType) {
    const colors = {
        'keywords_added': '#F59E0B',     // ✅ Warning orange para cambios de keywords
        'keyword_deleted': '#F59E0B',   // ✅ Warning orange para eliminación de keywords
        'keywords_removed': '#F59E0B',  // ✅ Warning orange para cambios de keywords
        'manual_note_added': '#3B82F6', // ✅ NUEVO: Azul para notas manuales del usuario
        'project_created': '#4F46E5',   // Blue
        'daily_analysis': '#6B7280',    // Gray
        'analysis_failed': '#EF4444',   // Red para errores reales
        'competitors_changed': '#8B5CF6', // ✅ Purple para cambios de competidores
        'competitors_updated': '#8B5CF6'  // ✅ Purple para actualizaciones de competidores
    };
    return colors[eventType] || '#6B7280';
}

export function getEventIcon(eventType) {
    const icons = {
        'keywords_added': '⚠',           // ✅ Warning para cambios de keywords
        'keyword_deleted': '⚠',         // ✅ Warning para eliminación de keywords
        'keywords_removed': '⚠',        // ✅ Warning para cambios de keywords
        'manual_note_added': '📝',       // ✅ NUEVO: Icono de nota para anotaciones manuales
        'project_created': '⭐',
        'daily_analysis': '📊',
        'analysis_failed': '⚠',
        'competitors_changed': '🔄',     // ✅ Icono para cambios de competidores
        'competitors_updated': '🔄'      // ✅ Icono para actualizaciones de competidores
    };
    return icons[eventType] || '•';
}

// 🧹 NUEVO: Limpieza segura de listeners y tooltip de anotaciones
export function clearEventAnnotations(chart) {
    if (!chart) return;
    const canvas = chart.canvas;
    if (chart._annotationHandlers) {
        try {
            canvas.removeEventListener('mousemove', chart._annotationHandlers.onMouseMove);
            canvas.removeEventListener('mouseleave', chart._annotationHandlers.onMouseLeave);
        } catch (_) { /* noop */ }
        chart._annotationHandlers = null;
    }
    // Ocultar tooltip si existe
    const tooltip = document.getElementById('chart-annotation-tooltip');
    if (tooltip) tooltip.style.opacity = 0;
    // Limpiar datos de anotaciones por si el plugin los lee
    if (chart.options) chart.options.annotationsData = [];
}

export function showEventAnnotations(chart, annotations) {
    // Enhanced tooltip functionality for annotations
    const canvas = chart.canvas;
    const ctx = chart.ctx;
    
    // Create tooltip element if it doesn't exist
    let tooltip = document.getElementById('chart-annotation-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'chart-annotation-tooltip';
        tooltip.style.cssText = `
            position: fixed;
            background: rgba(0, 0, 0, 0.92);
            color: white;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
            line-height: 1.5;
            max-width: 280px;
            min-width: 200px;
            z-index: 10000;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s ease;
            white-space: pre-wrap;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
        `;
        document.body.appendChild(tooltip);
    }
    
    // Mouse move handler for tooltip
    const onMouseMove = (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Check if mouse is over any annotation
        let hoveredAnnotation = null;
        const chartArea = chart.chartArea;
        
        for (const annotation of annotations) {
            // ✅ CORREGIDO: Usar la posición correcta de la anotación
            const annotationX = chart.scales.x.getPixelForValue(annotation.x);
            
            // ✅ MEJORADO: Área de detección más amplia para facilitar interacción
            if (Math.abs(x - annotationX) <= 20 && y >= chartArea.top - 30 && y <= chartArea.bottom + 10) {
                hoveredAnnotation = annotation;
                break;
            }
        }
        
        if (hoveredAnnotation) {
            // ✅ CORREGIDO: Mostrar el texto que el usuario añadió
            const eventTitle = hoveredAnnotation.event.event_title || 'Cambio en Keywords';
            const userDescription = hoveredAnnotation.event.event_description;
            const eventDate = new Date(hoveredAnnotation.event.event_date).toLocaleDateString('es-ES', {
                weekday: 'short',
                year: 'numeric', 
                month: 'short',
                day: 'numeric'
            });
            const eventType = hoveredAnnotation.event.event_type;
            const keywordsAffected = hoveredAnnotation.event.keywords_affected || 0;
            
            // Debug solo cuando hay descripción del usuario para verificar que funciona
            if (userDescription && userDescription.trim()) {
                console.log('🔍 Tooltip con comentario del usuario:', userDescription);
            }
            
            // ✅ MEJORADO: Título y contenido según el tipo de evento
            let tooltipTitle = '';
            let tooltipContent = '';
            
            if (eventType === 'manual_note_added') {
                // ✅ NUEVO: Caso especial para notas manuales del usuario
                tooltipTitle = `📝 User Note`;
                tooltipContent = `<strong>${tooltipTitle}</strong><br>${eventDate}`;
                if (userDescription && userDescription.trim()) {
                    tooltipContent += `<br><br><em>"${userDescription}"</em>`;
                }
            } else {
                // ✅ Casos existentes para eventos de keywords
                if (eventType === 'keywords_added') {
                    tooltipTitle = `⚠️ Keywords Added (${keywordsAffected})`;
                } else if (eventType === 'keyword_deleted') {
                    tooltipTitle = `⚠️ Keyword Eliminada`;
                } else if (eventType === 'keywords_removed') {
                    tooltipTitle = `⚠️ Keywords Eliminadas (${keywordsAffected})`;
                } else {
                    tooltipTitle = `⚠️ ${eventTitle}`;
                }
                
                tooltipContent = `<strong>${tooltipTitle}</strong><br>${eventDate}`;
                
                // ✅ Mostrar comentarios del usuario para eventos de keywords
                if (userDescription && 
                    userDescription.trim() && 
                    userDescription !== 'Sin notas adicionales' && 
                    userDescription !== 'No additional notes provided' &&
                    userDescription !== 'No description provided') {
                    tooltipContent += `<br><br><em>"${userDescription}"</em>`;
                }
            }
            
            tooltip.innerHTML = tooltipContent;
            tooltip.style.left = `${e.clientX + 15}px`;
            tooltip.style.top = `${e.clientY - 10}px`;
            tooltip.style.opacity = 1;
            canvas.style.cursor = 'pointer';
        } else {
            tooltip.style.opacity = 0;
            canvas.style.cursor = 'default';
        }
    };
    
    const onMouseLeave = () => {
        tooltip.style.opacity = 0;
        canvas.style.cursor = 'default';
    };
    
    // 🧹 MEJORADO: Limpiar listeners previos antes de añadir nuevos
    this.clearEventAnnotations(chart);
    
    // Añadir nuevos listeners
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseleave', onMouseLeave);
    
    // Guardar referencias para limpieza posterior
    chart._annotationHandlers = { onMouseMove, onMouseLeave };
}

