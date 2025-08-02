/* ==============================================
   KEYWORD EXCLUSION SYSTEM
   Lógica para filtrar keywords no deseadas del análisis de AI Overview
   ============================================== */

/**
 * Clase para manejar las exclusiones de keywords
 */
class KeywordExclusion {
    constructor() {
        this.exclusionTerms = [];
        this.exclusionMethod = 'contains';
        this.init();
    }

    /**
     * Inicializar event listeners
     */
    init() {
        const exclusionTextarea = document.getElementById('exclusionTerms');
        const exclusionMethodSelect = document.getElementById('exclusionMethod');

        if (exclusionTextarea) {
            exclusionTextarea.addEventListener('input', () => this.updatePreview());
        }

        if (exclusionMethodSelect) {
            exclusionMethodSelect.addEventListener('change', (e) => {
                this.exclusionMethod = e.target.value;
                this.updatePreview();
            });
        }

        // Actualizar preview inicial
        this.updatePreview();
    }

    /**
     * Actualizar el preview de términos de exclusión
     */
    updatePreview() {
        const exclusionTextarea = document.getElementById('exclusionTerms');
        const previewContainer = document.getElementById('exclusionPreview');
        
        if (!exclusionTextarea || !previewContainer) return;

        const inputText = exclusionTextarea.value.trim();
        
        if (!inputText) {
            previewContainer.innerHTML = '<em>Enter terms to see preview</em>';
            this.exclusionTerms = [];
            return;
        }

        // Procesar términos de exclusión
        this.exclusionTerms = this.parseExclusionTerms(inputText);
        
        if (this.exclusionTerms.length === 0) {
            previewContainer.innerHTML = '<em>No valid terms found</em>';
            return;
        }

        // Generar preview HTML
        const methodText = this.getMethodDescription();
        const termTags = this.exclusionTerms
            .map(term => `<span class="exclusion-term-tag">${this.escapeHtml(term)}</span>`)
            .join('');

        previewContainer.innerHTML = `
            <div>
                <strong>Method:</strong> ${methodText}
            </div>
            <div>
                <strong>Terms (${this.exclusionTerms.length}):</strong>
            </div>
            <div class="exclusion-term-list">
                ${termTags}
            </div>
        `;
    }

    /**
     * Parsear términos de exclusión del input del usuario
     * @param {string} inputText - Texto de entrada
     * @returns {Array} Array de términos limpios
     */
    parseExclusionTerms(inputText) {
        // Dividir por comas o saltos de línea
        const terms = inputText
            .split(/[,\n]/)
            .map(term => term.trim())
            .filter(term => term.length > 0)
            .map(term => term.toLowerCase()); // Case insensitive

        // Remover duplicados
        return [...new Set(terms)];
    }

    /**
     * Obtener descripción del método de exclusión
     * @returns {string} Descripción del método
     */
    getMethodDescription() {
        const descriptions = {
            'contains': 'Keywords containing any of these terms',
            'equals': 'Keywords exactly matching these terms',
            'startsWith': 'Keywords starting with these terms',
            'endsWith': 'Keywords ending with these terms'
        };
        return descriptions[this.exclusionMethod] || 'Unknown method';
    }

    /**
     * Verificar si una keyword debe ser excluida
     * @param {string} keyword - Keyword a verificar
     * @returns {boolean} True si debe ser excluida
     */
    shouldExcludeKeyword(keyword) {
        if (!keyword || this.exclusionTerms.length === 0) {
            return false;
        }

        const keywordLower = keyword.toLowerCase();

        return this.exclusionTerms.some(term => {
            switch (this.exclusionMethod) {
                case 'contains':
                    return keywordLower.includes(term);
                case 'equals':
                    return keywordLower === term;
                case 'startsWith':
                    return keywordLower.startsWith(term);
                case 'endsWith':
                    return keywordLower.endsWith(term);
                default:
                    return false;
            }
        });
    }

    /**
     * Filtrar array de keywords eliminando las excluidas
     * @param {Array} keywords - Array de keywords
     * @returns {Array} Array filtrado
     */
    filterKeywords(keywords) {
        if (!Array.isArray(keywords) || this.exclusionTerms.length === 0) {
            return keywords;
        }

        const filtered = keywords.filter(keyword => {
            // Si keyword es un objeto con propiedad 'keyword'
            const keywordText = typeof keyword === 'string' ? keyword : keyword.keyword;
            return !this.shouldExcludeKeyword(keywordText);
        });

        console.log(`🔍 Keyword exclusion: ${keywords.length} → ${filtered.length} (excluded: ${keywords.length - filtered.length})`);
        
        return filtered;
    }

    /**
     * Obtener configuración de exclusión para enviar al backend
     * @returns {Object} Configuración de exclusión
     */
    getExclusionConfig() {
        return {
            method: this.exclusionMethod,
            terms: this.exclusionTerms,
            enabled: this.exclusionTerms.length > 0
        };
    }

    /**
     * Escapar HTML para prevenir XSS
     * @param {string} text - Texto a escapar
     * @returns {string} Texto escapado
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Resetear exclusiones
     */
    reset() {
        const exclusionTextarea = document.getElementById('exclusionTerms');
        const exclusionMethodSelect = document.getElementById('exclusionMethod');
        
        if (exclusionTextarea) {
            exclusionTextarea.value = '';
        }
        
        if (exclusionMethodSelect) {
            exclusionMethodSelect.value = 'contains';
        }
        
        this.exclusionTerms = [];
        this.exclusionMethod = 'contains';
        this.updatePreview();
    }

    /**
     * Obtener estadísticas de exclusión
     * @param {Array} originalKeywords - Keywords originales
     * @param {Array} filteredKeywords - Keywords filtradas
     * @returns {Object} Estadísticas
     */
    getExclusionStats(originalKeywords, filteredKeywords) {
        const originalCount = originalKeywords ? originalKeywords.length : 0;
        const filteredCount = filteredKeywords ? filteredKeywords.length : 0;
        const excludedCount = originalCount - filteredCount;
        const excludedPercentage = originalCount > 0 ? (excludedCount / originalCount * 100).toFixed(1) : 0;

        return {
            original: originalCount,
            filtered: filteredCount,
            excluded: excludedCount,
            excludedPercentage: excludedPercentage
        };
    }
}

// Instancia global
window.keywordExclusion = new KeywordExclusion();

// Función para integrar con el análisis existente
window.getKeywordExclusionConfig = function() {
    return window.keywordExclusion.getExclusionConfig();
};

// Función para filtrar keywords (para uso en otras partes del código)
window.filterKeywordsWithExclusion = function(keywords) {
    return window.keywordExclusion.filterKeywords(keywords);
};