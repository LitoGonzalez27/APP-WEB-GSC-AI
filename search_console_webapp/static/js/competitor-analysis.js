/**
 * Competitor Analysis Module
 * Handles domain normalization, validation, and competitor comparison functionality
 */

/**
 * Normalizes a domain input by removing protocol and www prefix while preserving subdomains
 * @param {string} input - Raw domain input from user
 * @returns {string|null} - Normalized domain or null if invalid
 */
function normalizeDomain(input) {
    if (!input || typeof input !== 'string') {
        return null;
    }

    let domain = input.trim();
    
    // Return empty if input is empty
    if (!domain) {
        return null;
    }

    // Remove protocol prefixes (http://, https://, ftp://, etc.)
    domain = domain.replace(/^https?:\/\//, '');
    domain = domain.replace(/^ftp:\/\//, '');
    domain = domain.replace(/^\/\//, '');

    // Remove www. prefix only (preserve other subdomains like blog., shop., etc.)
    domain = domain.replace(/^www\./, '');

    // Remove trailing slash and path
    domain = domain.split('/')[0];
    
    // Remove query parameters and fragments
    domain = domain.split('?')[0].split('#')[0];

    return domain;
}

/**
 * Validates if a normalized domain has a valid format
 * @param {string} domain - Normalized domain to validate
 * @returns {boolean} - True if valid domain format
 */
function isValidDomain(domain) {
    if (!domain || typeof domain !== 'string') {
        return false;
    }

    // Basic domain pattern: letters, numbers, dots, hyphens
    // Must have at least one dot and valid TLD
    const domainPattern = /^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.([a-zA-Z]{2,}|[a-zA-Z]{2,}\.[a-zA-Z]{2,})$/;
    
    // Check basic pattern
    if (!domainPattern.test(domain)) {
        return false;
    }

    // Additional checks
    const parts = domain.split('.');
    
    // Must have at least 2 parts (domain.tld)
    if (parts.length < 2) {
        return false;
    }

    // Check each part
    for (const part of parts) {
        if (!part || part.length === 0) {
            return false;
        }
        
        // No consecutive hyphens
        if (part.includes('--')) {
            return false;
        }
        
        // Cannot start or end with hyphen
        if (part.startsWith('-') || part.endsWith('-')) {
            return false;
        }
    }

    return true;
}

/**
 * Validates and normalizes a competitor domain input
 * @param {string} input - Raw domain input
 * @returns {Object} - {isValid: boolean, normalizedDomain: string|null, error: string|null}
 */
function validateCompetitorDomain(input) {
    if (!input || !input.trim()) {
        return {
            isValid: true, // Empty is valid (optional field)
            normalizedDomain: null,
            error: null
        };
    }

    const normalized = normalizeDomain(input);
    
    if (!normalized) {
        return {
            isValid: false,
            normalizedDomain: null,
            error: 'Invalid domain format'
        };
    }

    if (!isValidDomain(normalized)) {
        return {
            isValid: false,
            normalizedDomain: null,
            error: 'Please enter a valid domain (e.g., example.com)'
        };
    }

    return {
        isValid: true,
        normalizedDomain: normalized,
        error: null
    };
}

/**
 * Updates the validation UI for a competitor input field
 * @param {string} fieldId - ID of the input field
 * @param {Object} validation - Validation result object
 */
function updateCompetitorValidationUI(fieldId, validation) {
    const input = document.getElementById(fieldId);
    const validationDiv = document.getElementById(fieldId + 'Validation');
    
    if (!input || !validationDiv) {
        return;
    }

    // Clear previous classes
    input.classList.remove('valid', 'invalid');
    validationDiv.classList.remove('valid', 'invalid');
    
    if (validation.normalizedDomain) {
        // Valid domain
        input.classList.add('valid');
        validationDiv.classList.add('valid');
        validationDiv.textContent = `Normalized: ${validation.normalizedDomain}`;
    } else if (validation.error) {
        // Invalid domain
        input.classList.add('invalid');
        validationDiv.classList.add('invalid');
        validationDiv.textContent = validation.error;
    } else {
        // Empty field (valid but no normalization)
        validationDiv.textContent = '';
    }
}

/**
 * Gets all valid competitor domains from the input fields
 * @returns {Array<string>} - Array of normalized competitor domains
 */
function getValidCompetitorDomains() {
    const competitorFields = ['competitor1', 'competitor2', 'competitor3'];
    const validDomains = [];
    const seenDomains = new Set();

    for (const fieldId of competitorFields) {
        const input = document.getElementById(fieldId);
        if (!input) continue;

        const validation = validateCompetitorDomain(input.value);
        if (validation.isValid && validation.normalizedDomain) {
            // Evitar duplicados
            if (!seenDomains.has(validation.normalizedDomain)) {
                validDomains.push(validation.normalizedDomain);
                seenDomains.add(validation.normalizedDomain);
            }
        }
    }

    return validDomains;
}

/**
 * Validates all competitor fields and shows any errors
 * @returns {Object} - {isValid: boolean, errors: Array<string>}
 */
function validateAllCompetitorFields() {
    const competitorFields = ['competitor1', 'competitor2', 'competitor3'];
    const errors = [];
    let allValid = true;

    for (const fieldId of competitorFields) {
        const input = document.getElementById(fieldId);
        if (!input) continue;

        if (input.value.trim()) { // Only validate non-empty fields
            const validation = validateCompetitorDomain(input.value);
            updateCompetitorValidationUI(fieldId, validation);
            
            if (!validation.isValid) {
                allValid = false;
                errors.push(`${fieldId}: ${validation.error}`);
            }
        }
    }

    return {
        isValid: allValid,
        errors: errors
    };
}

/**
 * Clears all competitor input fields and validation messages
 */
function clearCompetitorFields() {
    const competitorFields = ['competitor1', 'competitor2', 'competitor3'];
    
    competitorFields.forEach(fieldId => {
        const input = document.getElementById(fieldId);
        const validationDiv = document.getElementById(fieldId + 'Validation');
        
        if (input) {
            input.value = '';
            input.classList.remove('valid', 'invalid');
        }
        
        if (validationDiv) {
            validationDiv.textContent = '';
            validationDiv.classList.remove('valid', 'invalid');
        }
    });
}

/**
 * Initializes competitor domain validation for all fields
 */
function initializeCompetitorValidation() {
    const competitorFields = ['competitor1', 'competitor2', 'competitor3'];

    competitorFields.forEach(fieldId => {
        const input = document.getElementById(fieldId);
        if (!input) return;

        // Add real-time validation on input
        input.addEventListener('input', function() {
            const validation = validateCompetitorDomain(this.value);
            updateCompetitorValidationUI(fieldId, validation);
        });

        // Add validation on blur for better UX
        input.addEventListener('blur', function() {
            const validation = validateCompetitorDomain(this.value);
            updateCompetitorValidationUI(fieldId, validation);
        });
    });

    console.log('✅ Competitor domain validation initialized');
}

// ====================================
// CHART & TABLE DISPLAY FUNCTIONS
// ====================================

// Expanded color palette for 10+ domains (brandbook-safe on light backgrounds)
const COMPETITOR_COLORS = [
    '#0F172A',  // Dark navy — own domain (brandbook primary)
    '#7C3AED',  // Violet
    '#2563EB',  // Blue
    '#0891B2',  // Cyan
    '#D97706',  // Amber
    '#DC2626',  // Red
    '#059669',  // Emerald
    '#DB2777',  // Pink
    '#4F46E5',  // Indigo
    '#0D9488',  // Teal
    '#CA8A04',  // Dark yellow
    '#9333EA',  // Purple
    '#E11D48',  // Rose
    '#6366F1',  // Slate-indigo
];

/**
 * Helper: truncate long strings
 */
function truncateStr(str, maxLength = 20) {
    if (!str) return '';
    if (str.length <= maxLength) return str;
    return str.substring(0, maxLength - 3) + '...';
}

/**
 * Helper: get label for competitor_type
 */
function getCompetitorTypeLabel(result) {
    const t = result.competitor_type;
    if (t === 'own') return 'Your Domain';
    if (t === 'user') return 'Selected Competitor';
    return 'Auto-Discovered';
}

/**
 * Creates the competitor bar chart using Chart.js (full-width, tall)
 * @param {Array<Object>} competitorResults - with competitor_type field
 * @returns {HTMLElement} - Chart container element
 */
function createCompetitorBarChart(competitorResults) {
    let chartData = [];

    if (competitorResults && competitorResults.length > 0) {
        // Sort by mentions desc and limit to top 10 for the chart
        const sorted = [...competitorResults]
            .sort((a, b) => (b.mentions || 0) - (a.mentions || 0))
            .slice(0, 10);
        chartData = sorted.map((result, index) => ({
            label: result.domain,
            value: result.mentions,
            percentage: result.visibility_percentage || 0,
            competitorType: result.competitor_type || 'auto',
            color: COMPETITOR_COLORS[index] || '#94A3B8'
        }));
    } else {
        chartData = [{ label: 'No data', value: 0, percentage: 0, competitorType: 'auto', color: '#CBD5E1' }];
    }

    const chartContainer = document.createElement('div');
    chartContainer.className = 'competitor-chart-container';

    // Unique canvas ID to avoid conflicts on re-render
    const canvasId = 'competitorBarChart_' + Date.now();

    chartContainer.innerHTML = `
        <div class="chart-wrapper" style="width:100%;position:relative;">
            <canvas id="${canvasId}" style="width:100%!important;"></canvas>
        </div>
    `;

    // Initialize chart after DOM insertion
    setTimeout(() => {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !window.Chart) {
            console.warn('Chart.js not available or canvas not found');
            return;
        }
        const ctx = canvas.getContext('2d');

        // Build border styles: solid for own/user, dashed for auto
        const borderWidths = chartData.map(d => d.competitorType === 'auto' ? 1 : 2);

        // Dynamic bar thickness based on number of domains
        const barPercentage = chartData.length <= 6 ? 0.7 : 0.85;
        const categoryPercentage = chartData.length <= 6 ? 0.65 : 0.8;

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.map(d => truncateStr(d.label, 18)),
                datasets: [{
                    label: 'Visibility %',
                    data: chartData.map(d => d.percentage),
                    backgroundColor: chartData.map(d => d.color + 'CC'),
                    borderColor: chartData.map(d => d.color),
                    borderWidth: borderWidths,
                    barPercentage: barPercentage,
                    categoryPercentage: categoryPercentage,
                    borderRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { left: 8, right: 16, top: 8, bottom: 0 }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Visibility %', font: { family: "'Inter Tight', sans-serif", weight: '500', size: 12 } },
                        grid: { color: '#F1F5F9' },
                        ticks: { font: { size: 11, family: "'Inter Tight', sans-serif" } }
                    },
                    x: {
                        title: { display: false },
                        grid: { display: false },
                        ticks: {
                            font: { size: 11, family: "'Inter Tight', sans-serif" },
                            maxRotation: 45,
                            minRotation: 0
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#ffffff',
                        titleColor: '#0F172A',
                        bodyColor: '#374151',
                        borderColor: '#E2E8F0',
                        borderWidth: 1,
                        cornerRadius: 8,
                        titleFont: { size: 14, weight: '600', family: "'Inter Tight', sans-serif" },
                        bodyFont: { size: 12, weight: '400', family: "'Inter Tight', sans-serif" },
                        padding: { top: 10, bottom: 10, left: 14, right: 14 },
                        displayColors: true,
                        boxWidth: 12,
                        boxHeight: 12,
                        boxPadding: 4,
                        callbacks: {
                            title: function(context) {
                                const item = chartData[context[0].dataIndex];
                                return getCompetitorTypeLabel(item);
                            },
                            label: function(context) {
                                const item = chartData[context.dataIndex];
                                return [
                                    `${item.label}`,
                                    `Mentions: ${item.value}`,
                                    `Visibility: ${context.parsed.y}%`
                                ];
                            }
                        }
                    }
                }
            }
        });
    }, 100);

    return chartContainer;
}

/**
 * Creates the competitor domain visibility table (max 10 domains)
 * @param {Array<Object>} competitorResults - with competitor_type field
 * @returns {string} - HTML string
 */
function createCompetitorResultsTable(competitorResults) {
    if (!competitorResults || competitorResults.length === 0) return '';

    // Sort by mentions descending, keep top 10
    const sorted = [...competitorResults].sort((a, b) => b.mentions - a.mentions).slice(0, 10);

    const tableRows = sorted.map((result) => {
        const visibilityClass = getVisibilityClass(result.visibility_percentage);
        const positionClass = getPositionClass(result.average_position);
        const isOwn = result.competitor_type === 'own';
        const isUser = result.competitor_type === 'user';
        const rowClass = isOwn ? 'competitor-row-own' : (isUser ? 'competitor-row-highlighted' : '');

        // Badge based on competitor_type
        let badge = '';
        if (isOwn) {
            badge = '<span class="competitor-badge competitor-badge--own">You</span>';
        } else if (isUser) {
            badge = '<span class="competitor-badge competitor-badge--user">Selected</span>';
        }
        // Auto-discovered domains get NO badge — cleaner look

        return `
            <tr class="${rowClass}">
                <td class="domain-cell">${truncateStr(result.domain, 28)} ${badge}</td>
                <td class="mentions-cell">${result.mentions}</td>
                <td class="visibility-cell ${visibilityClass}">${result.visibility_percentage}%</td>
                <td class="position-cell ${positionClass}">${result.average_position || 'N/A'}</td>
            </tr>
        `;
    }).join('');

    return `
        <div class="competitor-results-table">
            <table class="competitor-table">
                <thead>
                    <tr>
                        <th>Domain</th>
                        <th>Mentions</th>
                        <th>Visibility</th>
                        <th>Avg Pos.</th>
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
 * Creates the Most Cited URLs table with pagination (10+10)
 * @param {Array<Object>} citedUrls - [{url, domain, title, citation_count, keywords_cited_in}]
 * @returns {string} - HTML string
 */
function createMostCitedUrlsTable(citedUrls) {
    if (!citedUrls || citedUrls.length === 0) {
        return '<p class="competitor-no-data"><i class="fas fa-link"></i>No cited URLs found in this analysis.</p>';
    }

    // Limit to 20 total
    const allUrls = citedUrls.slice(0, 20);
    const PAGE_SIZE = 10;

    function buildRows(items) {
        return items.map(item => `
            <tr>
                <td class="url-cell" title="${item.url}">
                    <a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.url}</a>
                </td>
                <td class="citation-count">${item.citation_count}</td>
            </tr>
        `).join('');
    }

    const firstPage = allUrls.slice(0, PAGE_SIZE);
    const secondPage = allUrls.slice(PAGE_SIZE, PAGE_SIZE * 2);
    const hasPagination = secondPage.length > 0;

    // Unique ID for pagination control
    const tableId = 'citedUrlsTable_' + Date.now();

    return `
        <div class="cited-urls-table" id="${tableId}">
            <table class="competitor-table cited-urls">
                <thead>
                    <tr>
                        <th>URL</th>
                        <th>Citations</th>
                    </tr>
                </thead>
                <tbody class="cited-urls-page cited-urls-page-1">
                    ${buildRows(firstPage)}
                </tbody>
                ${hasPagination ? `
                    <tbody class="cited-urls-page cited-urls-page-2" style="display:none;">
                        ${buildRows(secondPage)}
                    </tbody>
                ` : ''}
            </table>
            ${hasPagination ? `
                <div class="cited-urls-pagination">
                    <span class="cited-urls-page-info">1–${PAGE_SIZE} of ${allUrls.length}</span>
                    <button class="cited-urls-page-btn cited-urls-prev" disabled>
                        <i class="fas fa-chevron-left"></i>
                    </button>
                    <button class="cited-urls-page-btn cited-urls-next">
                        <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
            ` : `
                <div class="cited-urls-pagination">
                    <span class="cited-urls-page-info">${allUrls.length} URL${allUrls.length !== 1 ? 's' : ''}</span>
                </div>
            `}
        </div>
    `;
}

/**
 * Initializes pagination events for Most Cited URLs table
 * Called after the table is rendered in the DOM
 */
function initCitedUrlsPagination(containerEl) {
    const table = containerEl.querySelector('.cited-urls-table');
    if (!table) return;

    const page1 = table.querySelector('.cited-urls-page-1');
    const page2 = table.querySelector('.cited-urls-page-2');
    if (!page1 || !page2) return;

    const prevBtn = table.querySelector('.cited-urls-prev');
    const nextBtn = table.querySelector('.cited-urls-next');
    const pageInfo = table.querySelector('.cited-urls-page-info');
    if (!prevBtn || !nextBtn || !pageInfo) return;

    const totalRows = page1.querySelectorAll('tr').length + page2.querySelectorAll('tr').length;
    const pageSize = page1.querySelectorAll('tr').length;
    let currentPage = 1;

    function updateView() {
        if (currentPage === 1) {
            page1.style.display = '';
            page2.style.display = 'none';
            prevBtn.disabled = true;
            nextBtn.disabled = false;
            pageInfo.textContent = `1–${pageSize} of ${totalRows}`;
        } else {
            page1.style.display = 'none';
            page2.style.display = '';
            prevBtn.disabled = false;
            nextBtn.disabled = true;
            const page2Rows = page2.querySelectorAll('tr').length;
            pageInfo.textContent = `${pageSize + 1}–${pageSize + page2Rows} of ${totalRows}`;
        }
    }

    nextBtn.addEventListener('click', () => { currentPage = 2; updateView(); });
    prevBtn.addEventListener('click', () => { currentPage = 1; updateView(); });
}

/**
 * Gets CSS class for visibility percentage color coding
 */
function getVisibilityClass(percentage) {
    if (percentage >= 50) return 'visibility-high';
    if (percentage >= 25) return 'visibility-medium';
    return 'visibility-low';
}

/**
 * Gets CSS class for average position color coding
 */
function getPositionClass(position) {
    if (!position) return '';
    if (position <= 2) return 'position-excellent';
    if (position <= 4) return 'position-good';
    return 'position-poor';
}

/**
 * Displays competitor analysis results in the UI
 * NEW LAYOUT: Full-width chart on top, two tables side-by-side below
 * @param {Array<Object>} competitorResults - with competitor_type field
 * @param {HTMLElement} container
 * @param {Object} options - { mostCitedUrls: [], manualDomains: [] }
 */
function displayCompetitorResults(competitorResults, container, options = {}) {
    if (!container) {
        console.warn('No container provided for competitor results');
        return;
    }

    if (!competitorResults || competitorResults.length === 0) {
        console.log('No competitor results to display');
        return;
    }

    const { mostCitedUrls = [] } = options;

    // Find or create competitor container
    let competitorContainer = container.querySelector('.competitor-results-container');
    if (!competitorContainer) {
        competitorContainer = document.createElement('div');
        competitorContainer.className = 'competitor-results-container';
        container.appendChild(competitorContainer);
    }

    // Create components
    const chartElement = createCompetitorBarChart(competitorResults);
    const tableHTML = createCompetitorResultsTable(competitorResults);
    const citedUrlsHTML = createMostCitedUrlsTable(mostCitedUrls);

    // Build new layout: chart full-width on top, two tables side-by-side below, info banner at bottom
    let layoutHTML = `
        <h3 class="competitor-analysis-title">Competitor Analysis</h3>
        <div class="competitor-chart-row">
            <div class="competitor-chart-column"></div>
        </div>
        <div class="competitor-tables-row">
            <div class="competitor-domain-table-column">
                <h4>Domain Visibility</h4>
                ${tableHTML}
            </div>
            <div class="competitor-cited-urls-column">
                <h4>Most Cited URLs</h4>
                ${citedUrlsHTML}
            </div>
        </div>
        <div class="competitor-info-banner">
            <i class="fas fa-info-circle"></i>
            <span>The number of citations in <strong>Most Cited URLs</strong> may not match the mentions in <strong>Domain Visibility</strong>. This is because we also count brand mentions within video platforms like YouTube, social media embeds and other rich media sources that may not have a direct URL reference.</span>
        </div>
    `;

    competitorContainer.innerHTML = layoutHTML;

    // Insert chart element into the chart row
    if (chartElement) {
        const chartColumn = competitorContainer.querySelector('.competitor-chart-column');
        if (chartColumn) {
            chartColumn.appendChild(chartElement);
        }
    }

    // Initialize pagination for cited URLs
    setTimeout(() => initCitedUrlsPagination(competitorContainer), 50);

    console.log(`Displayed competitor results: ${competitorResults.length} domains, ${mostCitedUrls.length} cited URLs`);
}

// Export functions for use in other modules
window.CompetitorAnalysis = {
    normalizeDomain,
    isValidDomain,
    validateCompetitorDomain,
    updateCompetitorValidationUI,
    getValidCompetitorDomains,
    validateAllCompetitorFields,
    clearCompetitorFields,
    initializeCompetitorValidation,
    createCompetitorResultsTable,
    createMostCitedUrlsTable,
    displayCompetitorResults
};

/**
 * Configurar botón "Clear All Competitors"
 */
function setupClearCompetitorsButton() {
    const clearBtn = document.getElementById('clearCompetitors');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearAllCompetitors();
        });
    }
}

/**
 * Limpiar todos los campos de competidores
 */
function clearAllCompetitors() {
    const competitorInputs = ['competitor1', 'competitor2', 'competitor3'];
    let cleared = false;
    
    competitorInputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        const validation = document.getElementById(inputId + 'Validation');
        
        if (input && input.value.trim()) {
            input.value = '';
            cleared = true;
        }
        
        if (validation) {
            validation.textContent = '';
            validation.className = 'competitor-validation';
        }
    });
    
    if (cleared) {
        console.log('🗑️ Todos los competidores eliminados');
        
        // Actualizar resumen del sistema colapsable
        if (window.updateCollapsibleSummary) {
            window.updateCollapsibleSummary('competitor');
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Small delay to ensure all elements are rendered
    setTimeout(() => {
        initializeCompetitorValidation();
        setupClearCompetitorsButton();
    }, 100);
});

console.log('🔧 Competitor Analysis module loaded');