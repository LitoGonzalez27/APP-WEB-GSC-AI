/**
 * Manual AI System - Utilities Module
 * Funciones helper, validadores, y utilidades UI
 */

// ================================
// HTML LEGEND PLUGIN FOR CHART.JS
// ================================

export const htmlLegendPlugin = {
    id: 'htmlLegend',
    afterUpdate(chart, args, options) {
        const ul = this.getOrCreateLegendList(chart, options.containerID);
        
        // Remove old legend items
        while (ul.firstChild) {
            ul.firstChild.remove();
        }
        
        // Reuse the built-in legendItems generator
        const items = chart.options.plugins.legend.labels.generateLabels(chart);
        
        items.forEach(item => {
            const li = document.createElement('li');
            li.style.alignItems = 'center';
            li.style.cursor = 'pointer';
            li.style.display = 'flex';
            li.style.flexDirection = 'row';
            li.style.marginLeft = '12px';
            li.style.marginRight = '12px';
            
            li.onclick = () => {
                const {type} = chart.config;
                if (type === 'pie' || type === 'doughnut') {
                    chart.toggleDataVisibility(item.index);
                } else {
                    chart.setDatasetVisibility(item.datasetIndex, !chart.isDatasetVisible(item.datasetIndex));
                }
                chart.update();
            };
            
            // Color box with rectRounded style
            const boxSpan = document.createElement('span');
            boxSpan.style.background = item.fillStyle;
            boxSpan.style.borderColor = item.strokeStyle;
            boxSpan.style.borderWidth = item.lineWidth + 'px';
            boxSpan.style.borderRadius = '3px';
            boxSpan.style.display = 'inline-block';
            boxSpan.style.flexShrink = 0;
            boxSpan.style.height = '12px';
            boxSpan.style.marginRight = '8px';
            boxSpan.style.width = '12px';
            
            // Text
            const textContainer = document.createElement('span');
            textContainer.style.color = item.fontColor || '#374151';
            textContainer.style.fontSize = '12px';
            textContainer.style.fontFamily = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
            textContainer.style.fontWeight = '500';
            textContainer.style.textDecoration = item.hidden ? 'line-through' : '';
            textContainer.style.opacity = item.hidden ? '0.5' : '1';
            textContainer.textContent = item.text;
            
            li.appendChild(boxSpan);
            li.appendChild(textContainer);
            ul.appendChild(li);
        });
    },
    
    getOrCreateLegendList(chart, id) {
        const legendContainer = document.getElementById(id);
        if (!legendContainer) return null;
        
        let listContainer = legendContainer.querySelector('ul');
        if (!listContainer) {
            listContainer = document.createElement('ul');
            listContainer.style.display = 'flex';
            listContainer.style.flexDirection = 'row';
            listContainer.style.flexWrap = 'wrap';
            listContainer.style.margin = '0';
            listContainer.style.padding = '0';
            listContainer.style.listStyle = 'none';
            listContainer.style.justifyContent = 'flex-start';
            listContainer.style.alignItems = 'center';
            legendContainer.appendChild(listContainer);
        }
        return listContainer;
    }
};

// ================================
// HELPER FUNCTIONS
// ================================

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

export function getDomainLogoUrl(domain) {
    if (!domain || typeof domain !== 'string') {
        return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTAiIGN5PSIxMCIgcj0iMTAiIGZpbGw9IiNlNWU3ZWIiLz4KPHR5cGUgeD0iMTAiIHk9IjE0IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LXNpemU9IjEwIiBmaWxsPSIjMzc0MTUxIj4/PC90ZXh0Pgo8L3N2Zz4K';
    }
    
    // Clean domain to remove any protocol or paths
    const cleanDomain = domain.toLowerCase()
        .replace(/^https?:\/\//, '')
        .replace(/^www\./, '')
        .split('/')[0]
        .split('?')[0]
        .split('#')[0]
        .trim();
        
    if (!cleanDomain) {
        return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTAiIGN5PSIxMCIgcj0iMTAiIGZpbGw9IiNlNWU3ZWIiLz4KPHR5cGUgeD0iMTAiIHk9IjE0IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LXNpemU9IjEwIiBmaWxsPSIjMzc0MTUxIj4/PC90ZXh0Pgo8L3N2Zz4K';
    }
    
    // Multiple fallback services for domain logos/favicons
    const logoServices = [
        `https://logo.clearbit.com/${cleanDomain}`,                       // Clearbit - high quality
        `https://www.google.com/s2/favicons?domain=${cleanDomain}&sz=32`, // Google favicons
        `https://icon.horse/icon/${cleanDomain}`,                         // Icon Horse
        `https://${cleanDomain}/favicon.ico`                            // Direct favicon
    ];
    
    // Return primary service (Clearbit) - fallback handled in onerror
    return logoServices[0];
}

export function truncateDomain(domain, maxLength = 15) {
    if (!domain || domain.length <= maxLength) return domain;
    return domain.substring(0, maxLength - 3) + '...';
}

// ================================
// VALIDATORS
// ================================

export function isValidDomain(domain) {
    const re = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/i;
    return re.test(domain);
}

export function normalizeDomainString(value) {
    let v = (value || '').trim().toLowerCase();
    v = v.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
    return v;
}

// ================================
// UI UTILITIES
// ================================

export function showElement(element) {
    if (element) element.style.display = 'block';
}

export function hideElement(element) {
    if (element) element.style.display = 'none';
}

export function showToast(message, type = 'info', duration = 3000) {
    // Simple toast implementation
    console.log(`Toast [${type}]: ${message}`);
    // You could implement a more sophisticated toast system here
}

// ================================
// SCORE CALCULATION
// ================================

export function calculateVisibilityScore(appearances, avgPosition) {
    if (!appearances || !avgPosition) return 0;
    
    // Score = appearances × (weight based on position)
    // Better positions (lower numbers) get higher weights
    const positionWeight = Math.max(0, (21 - avgPosition) / 20);
    return appearances * positionWeight * 10; // Scale to 0-100 range
}

export function getScoreClass(score) {
    if (score >= 80) return 'score-excellent';
    if (score >= 60) return 'score-good';
    if (score >= 30) return 'score-average';
    return 'score-poor';
}

