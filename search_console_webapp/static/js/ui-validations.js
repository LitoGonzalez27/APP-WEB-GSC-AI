// ui-validations.js - Nuevo archivo para validaciones

import { detectOverlappingURLs, validateDataIntegrity } from './data.js';

// ✅ ACTUALIZADO: Funciones auxiliares para validación de dominios
function extractDomainFromUrl(url) {
    if (!url) return '';
    
    // ✅ NUEVO: Si es un path relativo (empieza con /), retornamos null para indicar que es válido
    if (url.trim().startsWith('/')) {
        return null; // null significa "es un path relativo válido"
    }
    
    try {
        // Manejar URLs sin protocolo
        if (!/^https?:\/\//.test(url)) {
            url = 'https://' + url;
        }
        const u = new URL(url);
        return u.hostname.replace(/^www\./, '');
    } catch {
        // Fallback para URLs mal formateadas
        const simpleDomain = url.replace(/^https?:\/\//, '').replace(/^www\./, '');
        return simpleDomain.split('/')[0];
    }
}

function normalizeSearchConsoleProperty(scProperty) {
    if (!scProperty) return '';
    // Manejar propiedades de tipo dominio (sc-domain:ejemplo.com)
    if (scProperty.startsWith('sc-domain:')) {
        return scProperty.split(':')[1];
    }
    // Manejar propiedades de tipo URL (https://ejemplo.com/)
    return extractDomainFromUrl(scProperty);
}

// ✅ ACTUALIZADO: Función para verificar si los dominios coinciden
function domainsMatch(urlDomain, propertyDomain) {
    // Si urlDomain es null, significa que es un path relativo válido
    if (urlDomain === null) return true;
    
    if (!urlDomain || !propertyDomain) return false;
    
    // Normalizar ambos dominios
    const normalizedUrlDomain = urlDomain.toLowerCase();
    const normalizedPropertyDomain = propertyDomain.toLowerCase();
    
    // Verificar coincidencia exacta o subdominio
    return normalizedUrlDomain === normalizedPropertyDomain || 
           normalizedUrlDomain.endsWith(`.${normalizedPropertyDomain}`);
}

// ✅ NUEVO: Función para verificar si una URL contiene un dominio explícito diferente
function hasConflictingDomain(url, propertyDomain) {
    if (!url || !propertyDomain) return false;
    
    // Si es un path relativo, no hay conflicto
    if (url.trim().startsWith('/')) return false;
    
    // Extraer el dominio de la URL
    const urlDomain = extractDomainFromUrl(url);
    
    // Si no se pudo extraer dominio, no hay conflicto
    if (!urlDomain) return false;
    
    // Verificar si hay conflicto de dominios
    return !domainsMatch(urlDomain, propertyDomain);
}

export class DataValidator {
    constructor() {
        this.warnings = [];
        this.errors = [];
    }
    
    // ✅ ACTUALIZADA: Validación de compatibilidad de dominios mejorada
    validateDomainCompatibility(urls, selectedProperty) {
        this.warnings = [];
        this.errors = [];
        
        if (!selectedProperty) {
            this.errors.push('Debes seleccionar una propiedad de Search Console antes de continuar.');
            return {
                isValid: false,
                errors: this.errors,
                warnings: this.warnings
            };
        }
        
        // Si no hay URLs especificadas, es válido (análisis de propiedad completa)
        if (!urls || urls.length === 0) {
            return {
                isValid: true,
                errors: this.errors,
                warnings: this.warnings
            };
        }
        
        const propertyDomain = normalizeSearchConsoleProperty(selectedProperty);
        const propertyDisplay = selectedProperty.replace('sc-domain:', '').replace('https://', '').replace('http://', '').replace(/\/$/, '');
        
        console.log('🔍 Validando dominios:', {
            selectedProperty,
            propertyDomain,
            urlsToCheck: urls.length
        });
        
        const incompatibleUrls = [];
        const validUrls = [];
        const relativePaths = [];
        
        urls.forEach(url => {
            if (!url.trim()) return; // Saltar URLs vacías
            
            const trimmedUrl = url.trim();
            
            // ✅ NUEVO: Verificar si es un path relativo
            if (trimmedUrl.startsWith('/')) {
                relativePaths.push({ url: trimmedUrl, type: 'relative_path' });
                validUrls.push({ url: trimmedUrl, domain: 'relative_path' });
                return;
            }
            
            // ✅ NUEVO: Verificar si hay conflicto de dominios
            if (hasConflictingDomain(trimmedUrl, propertyDomain)) {
                const urlDomain = extractDomainFromUrl(trimmedUrl);
                incompatibleUrls.push({ url: trimmedUrl, domain: urlDomain });
            } else {
                const urlDomain = extractDomainFromUrl(trimmedUrl);
                validUrls.push({ url: trimmedUrl, domain: urlDomain || 'same_domain' });
            }
        });
        
        // ✅ MEJORADO: Mensaje de error más específico y claro
        if (incompatibleUrls.length > 0) {
            const domainList = [...new Set(incompatibleUrls.map(item => item.domain))].filter(d => d).join(', ');
            
            this.errors.push(
                `❌ Error de dominio incompatible\n\n` +
                `Tu propiedad de Search Console: ${propertyDisplay}\n` +
                `Dominio(s) detectado(s) en tus URLs: ${domainList}\n\n` +
                `URLs problemáticas:\n${incompatibleUrls.map(item => `• ${item.url}`).join('\n')}\n\n` +
                `💡 Solución:\n` +
                `• Para analizar páginas de tu propiedad, usa paths relativos: /blog/, /productos/\n` +
                `• Para analizar URLs completas, asegúrate de que sean del mismo dominio que tu propiedad\n` +
                `• Si quieres analizar otro dominio, cambia la propiedad seleccionada en Search Console`
            );
            
            console.warn('❌ URLs incompatibles encontradas:', incompatibleUrls);
        }
        
        // ✅ NUEVO: Logging informativo
        if (relativePaths.length > 0) {
            console.log(`✅ ${relativePaths.length} paths relativos detectados (válidos para la propiedad):`, relativePaths.map(p => p.url));
        }
        
        if (validUrls.length > 0) {
            console.log('✅ URLs válidas encontradas:', validUrls.length);
        }
        
        return {
            isValid: incompatibleUrls.length === 0,
            errors: this.errors,
            warnings: this.warnings,
            validUrls: validUrls,
            incompatibleUrls: incompatibleUrls,
            relativePaths: relativePaths
        };
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
