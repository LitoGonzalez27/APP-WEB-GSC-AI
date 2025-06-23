// ui-validations.js - Nuevo archivo para validaciones

import { detectOverlappingURLs, validateDataIntegrity } from './data.js';

export class DataValidator {
    constructor() {
        this.warnings = [];
        this.errors = [];
    }
    
    validateURLs(urls, matchType) {
        this.warnings = [];
        this.errors = [];
        
        // Validar formato de URLs
        const invalidURLs = urls.filter(url => {
            try {
                new URL(url);
                return false;
            } catch {
                // Si falla, verificar si es una ruta relativa válida
                return !url.startsWith('/') && !url.includes('://');
            }
        });
        
        if (invalidURLs.length > 0) {
            this.errors.push(`URLs con formato inválido: ${invalidURLs.join(', ')}`);
        }
        
        // Detectar solapamientos
        const overlaps = detectOverlappingURLs(urls, matchType);
        if (overlaps.length > 0) {
            overlaps.forEach(overlap => {
                this.warnings.push(overlap.warning);
            });
        }
        
        // Advertir si hay muchas URLs
        if (urls.length > 20) {
            this.warnings.push(`Estás consultando ${urls.length} URLs. Esto puede tardar varios minutos.`);
        }
        
        return {
            isValid: this.errors.length === 0,
            errors: this.errors,
            warnings: this.warnings
        };
    }
    
    validateDateRange(months) {
        const sortedMonths = months.sort();
        const firstMonth = new Date(sortedMonths[0] + '-01');
        const lastMonth = new Date(sortedMonths[sortedMonths.length - 1] + '-01');
        
        // Verificar que no sea un rango demasiado amplio
        const monthDiff = (lastMonth.getFullYear() - firstMonth.getFullYear()) * 12 + 
                         (lastMonth.getMonth() - firstMonth.getMonth()) + 1;
        
        if (monthDiff > 16) {
            this.warnings.push(`Rango de ${monthDiff} meses seleccionado. Considera reducirlo para mejor rendimiento.`);
        }
        
        // Verificar datos muy recientes
        const today = new Date();
        const daysFromLastMonth = Math.floor((today - lastMonth) / (1000 * 60 * 60 * 24));
        
        if (daysFromLastMonth < 3) {
            this.warnings.push('Los datos de los últimos 2-3 días pueden estar incompletos en GSC.');
        }
        
        return {
            isValid: true,
            warnings: this.warnings
        };
    }
    
    validateResponseData(data) {
        const issues = validateDataIntegrity(data);
        
        if (issues.length > 0) {
            this.errors.push(...issues);
        }
        
        // Verificar si hay datos vacíos
        if (!data.pages || data.pages.length === 0) {
            this.warnings.push('No se encontraron datos para las URLs especificadas.');
        }
        
        // Verificar discrepancias grandes
        data.pages?.forEach(page => {
            const metrics = page.Metrics || [];
            for (let i = 1; i < metrics.length; i++) {
                const prev = metrics[i-1];
                const curr = metrics[i];
                
                // Alertar si hay cambios drásticos (>500%)
                if (prev.Impressions > 100 && curr.Impressions > 100) {
                    const change = Math.abs(curr.Impressions - prev.Impressions) / prev.Impressions;
                    if (change > 5) {
                        this.warnings.push(
                            `Cambio drástico detectado para ${page.URL}: ` +
                            `${prev.Month} (${prev.Impressions} imp.) → ${curr.Month} (${curr.Impressions} imp.)`
                        );
                    }
                }
            }
        });
        
        return {
            isValid: this.errors.length === 0,
            errors: this.errors,
            warnings: this.warnings
        };
    }
}

// Componente de alertas mejorado
export class AlertManager {
    constructor() {
        this.container = document.createElement('div');
        this.container.id = 'alert-container';
        this.container.className = 'alert-container';
        document.body.appendChild(this.container);
    }
    
    show(message, type = 'info', duration = 5000) {
        const alertEl = document.createElement('div');
        alertEl.className = `alert alert-${type} alert-dismissible`;
        
        const icon = {
            'error': 'fa-circle-exclamation',
            'warning': 'fa-triangle-exclamation',
            'success': 'fa-circle-check',
            'info': 'fa-circle-info'
        }[type] || 'fa-circle-info';
        
        alertEl.innerHTML = `
            <i class="fas ${icon}"></i>
            <span>${message}</span>
            <button class="alert-close">&times;</button>
        `;
        
        this.container.appendChild(alertEl);
        
        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(alertEl), duration);
        }
        
        // Manual dismiss
        alertEl.querySelector('.alert-close').addEventListener('click', () => {
            this.dismiss(alertEl);
        });
    }
    
    dismiss(alertEl) {
        alertEl.classList.add('alert-fade-out');
        setTimeout(() => alertEl.remove(), 300);
    }
    
    showValidationResults(validation) {
        // Mostrar errores
        validation.errors?.forEach(error => {
            this.show(error, 'error', 0); // No auto-dismiss errors
        });
        
        // Mostrar advertencias
        validation.warnings?.forEach(warning => {
            this.show(warning, 'warning', 10000); // 10 segundos para warnings
        });
        
        // Si todo está bien
        if (validation.isValid && validation.warnings.length === 0) {
            this.show('✓ Validación exitosa', 'success', 3000);
        }
    }
}

// CSS para las alertas (agregar a estilos-app-od.css)
const alertStyles = `
.alert-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    max-width: 400px;
}

.alert {
    background: white;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    display: flex;
    align-items: center;
    gap: 10px;
    animation: slideIn 0.3s ease-out;
}

.alert-error {
    border-left: 4px solid #dc3545;
    color: #dc3545;
}

.alert-warning {
    border-left: 4px solid #ffc107;
    color: #856404;
}

.alert-success {
    border-left: 4px solid #28a745;
    color: #155724;
}

.alert-info {
    border-left: 4px solid #17a2b8;
    color: #0c5460;
}

.alert-close {
    margin-left: auto;
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: inherit;
    opacity: 0.5;
}

.alert-close:hover {
    opacity: 1;
}

.alert-fade-out {
    animation: fadeOut 0.3s ease-out forwards;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes fadeOut {
    to {
        transform: translateX(100%);
        opacity: 0;
    }
}

/* Modo oscuro */
.dark-mode .alert {
    background: #2d2d30;
    color: #e0e0e0;
}
`;
