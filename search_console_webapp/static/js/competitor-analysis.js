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

/**
 * Creates the competitor donut chart using Chart.js
 * @param {Array<Object>} competitorResults - Array of competitor analysis results
 * @returns {HTMLElement} - Chart container element
 */
function createCompetitorDonutChart(competitorResults) {
    if (!competitorResults || competitorResults.length === 0) {
        return null;
    }

    // Definir colores para usuario y competidores
    const colors = ['#D9FAB9', '#F2B9FA', '#FADBB9', '#B9E8FA'];
    
    // Preparar datos para el gráfico
    const chartData = competitorResults.map((result, index) => ({
        label: result.domain,
        value: result.mentions,
        percentage: result.visibility_percentage,
        color: colors[index] || '#CCCCCC'
    })).filter(item => item.value > 0); // Solo mostrar dominios con menciones

    if (chartData.length === 0) {
        return null;
    }

    // Función helper para truncar dominios largos
    function truncateDomain(domain, maxLength = 20) {
        if (domain.length <= maxLength) return domain;
        return domain.substring(0, maxLength - 3) + '...';
    }

    // Función para determinar el tipo de dominio
    function getDomainType(domain, index) {
        if (index === 0) return 'Your Domain';
        return `Competitor ${index}`;
    }

    // Crear contenedor del gráfico
    const chartContainer = document.createElement('div');
    chartContainer.className = 'competitor-chart-container';
    
    // Crear leyenda
    const legendHTML = chartData.map((item, index) => `
        <div class="legend-item">
            <div class="legend-color" style="background-color: ${item.color};"></div>
            <div class="legend-label">
                <strong>${getDomainType(item.label, index)}</strong><br>
                <span style="font-size: 0.8em; opacity: 0.8;">${truncateDomain(item.label)}</span>
            </div>
        </div>
    `).join('');
    
    chartContainer.innerHTML = `
        <h4><i class="fas fa-chart-pie"></i> Visibility Distribution</h4>
        <div class="chart-wrapper">
            <canvas id="competitorDonutChart" width="300" height="250"></canvas>
        </div>
        <div class="chart-legend">
            ${legendHTML}
        </div>
    `;

    // Configurar el gráfico cuando se añada al DOM
    setTimeout(() => {
        const canvas = document.getElementById('competitorDonutChart');
        if (canvas && window.Chart) {
            const ctx = canvas.getContext('2d');
            
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: chartData.map(item => item.label),
                    datasets: [{
                        data: chartData.map(item => item.value),
                        backgroundColor: chartData.map(item => item.color),
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false // Usamos nuestra leyenda personalizada
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
                                    const item = chartData[context[0].dataIndex];
                                    const domainType = getDomainType(item.label, context[0].dataIndex);
                                    return domainType;
                                },
                                label: function(context) {
                                    const item = chartData[context.dataIndex];
                                    return [
                                        `Domain: ${item.label}`,
                                        `Mentions: ${item.value}`,
                                        `Visibility: ${item.percentage}%`
                                    ];
                                }
                            }
                        }
                    }
                }
            });
        } else {
            console.warn('Chart.js not available or canvas not found');
        }
    }, 100);

    return chartContainer;
}

/**
 * Creates the competitor results table HTML
 * @param {Array<Object>} competitorResults - Array of competitor analysis results
 * @returns {string} - HTML string for the results table
 */
function createCompetitorResultsTable(competitorResults) {
    if (!competitorResults || competitorResults.length === 0) {
        return '';
    }

    const tableRows = competitorResults.map((result, index) => {
        const visibilityClass = getVisibilityClass(result.visibility_percentage);
        const positionClass = getPositionClass(result.average_position);
        const domainClass = index === 0 ? 'user-domain' : 'competitor-domain'; // Primera fila es el usuario
        
        return `
            <tr>
                <td class="domain-cell ${domainClass}">${result.domain}</td>
                <td class="mentions-cell">${result.mentions}</td>
                <td class="visibility-cell ${visibilityClass}">${result.visibility_percentage}%</td>
                <td class="position-cell ${positionClass}">${result.average_position || 'N/A'}</td>
            </tr>
        `;
    }).join('');

    return `
        <div class="competitor-results-table">
            <h4><i class="fas fa-chart-bar"></i> Domain Comparison</h4>
            <table class="competitor-table">
                <thead>
                    <tr>
                        <th>Domain</th>
                        <th>Mentions</th>
                        <th>% Visibility</th>
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
 * Gets CSS class for visibility percentage color coding
 * @param {number} percentage - Visibility percentage
 * @returns {string} - CSS class name
 */
function getVisibilityClass(percentage) {
    if (percentage >= 50) return 'visibility-high';
    if (percentage >= 25) return 'visibility-medium';
    return 'visibility-low';
}

/**
 * Gets CSS class for average position color coding
 * @param {number|null} position - Average position
 * @returns {string} - CSS class name
 */
function getPositionClass(position) {
    if (!position) return '';
    if (position <= 2) return 'position-excellent';
    if (position <= 4) return 'position-good';
    return 'position-poor';
}

/**
 * Displays competitor analysis results in the UI
 * @param {Array<Object>} competitorResults - Array of competitor analysis results
 * @param {HTMLElement} container - Container element to display results
 */
function displayCompetitorResults(competitorResults, container) {
    if (!container) {
        console.warn('No container provided for competitor results');
        return;
    }

    if (!competitorResults || competitorResults.length === 0) {
        console.log('No competitor results to display');
        return;
    }

    // Find existing competitor container or create new one
    let competitorContainer = container.querySelector('.competitor-results-container');
    if (!competitorContainer) {
        competitorContainer = document.createElement('div');
        competitorContainer.className = 'competitor-results-container';
        container.appendChild(competitorContainer);
    }

    // Create the main layout with chart and table
    const chartElement = createCompetitorDonutChart(competitorResults);
    const tableHTML = createCompetitorResultsTable(competitorResults);
    
    // Build the combined layout
    let layoutHTML = '<div class="competitor-analysis-layout">';
    
    if (chartElement) {
        layoutHTML += '<div class="competitor-chart-column"></div>';
    }
    
    layoutHTML += `
        <div class="competitor-table-column">
            ${tableHTML}
        </div>
    </div>`;
    
    competitorContainer.innerHTML = layoutHTML;
    
    // Add the chart element if it exists
    if (chartElement) {
        const chartColumn = competitorContainer.querySelector('.competitor-chart-column');
        if (chartColumn) {
            chartColumn.appendChild(chartElement);
        }
    }
    
    console.log(`✅ Displayed competitor results for ${competitorResults.length} domains with ${chartElement ? 'chart and' : ''} table`);
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
    displayCompetitorResults
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Small delay to ensure all elements are rendered
    setTimeout(() => {
        initializeCompetitorValidation();
    }, 100);
});

console.log('🔧 Competitor Analysis module loaded');