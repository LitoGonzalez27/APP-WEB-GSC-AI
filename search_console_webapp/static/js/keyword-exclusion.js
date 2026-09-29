/* ==============================================
   KEYWORD EXCLUSION SYSTEM WITH TAGS
   Lógica para filtrar keywords no deseadas del análisis de AI Overview usando un sistema de tags/burbujas
   ============================================== */

/**
 * Clase para manejar las exclusiones de keywords con sistema de tags
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
        const exclusionInput = document.getElementById('exclusionTerms');
        const exclusionMethodSelect = document.getElementById('exclusionMethod');

        if (exclusionInput) {
            // Cambiar comportamiento para manejar tags
            exclusionInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
            exclusionInput.addEventListener('input', (e) => this.handleInput(e));
        }

        if (exclusionMethodSelect) {
            exclusionMethodSelect.addEventListener('change', (e) => {
                this.exclusionMethod = e.target.value;
                this.updateMethodDescription();
                this.updateCollapsibleSummary();
            });
        }

        // Inicializar descripción del método
        this.updateMethodDescription();

        // Configurar botón "Clear All"
        this.setupClearAllButton();

        // Renderizar tags vacíos inicialmente
        this.renderTags();
        console.log('✅ Sistema de exclusión con tags inicializado');
    }

    /**
     * Manejar eventos de teclado en el input
     * @param {KeyboardEvent} e - Evento de teclado
     */
    handleKeyDown(e) {
        const input = e.target;
        const value = input.value.trim();

        // Crear tag al presionar coma o Enter
        if ((e.key === ',' || e.key === 'Enter') && value) {
            e.preventDefault();
            this.addTag(value);
            input.value = '';
        }
        
        // Eliminar último tag con Backspace en input vacío
        if (e.key === 'Backspace' && !value && this.exclusionTerms.length > 0) {
            e.preventDefault();
            this.removeTag(this.exclusionTerms.length - 1);
        }
    }

    /**
     * Manejar eventos de input (para detectar comas pegadas)
     * @param {InputEvent} e - Evento de input
     */
    handleInput(e) {
        const input = e.target;
        const value = input.value;

        // Si el usuario pegó texto con comas, procesarlo
        if (value.includes(',')) {
            const parts = value.split(',');
            const lastPart = parts.pop(); // La última parte permanece en el input
            
            // Añadir todas las partes excepto la última como tags
            parts.forEach(part => {
                const trimmed = part.trim();
                if (trimmed) {
                    this.addTag(trimmed);
                }
            });
            
            // Mantener la última parte en el input
            input.value = lastPart.trim();
        }
    }

    /**
     * Añadir un nuevo tag
     * @param {string} term - Término a añadir
     */
    addTag(term) {
        const cleanTerm = term.trim().toLowerCase();
        
        // Evitar términos vacíos o duplicados
        if (!cleanTerm || this.exclusionTerms.includes(cleanTerm)) {
            return;
        }

        this.exclusionTerms.push(cleanTerm);
        this.renderTags();
        this.updateCollapsibleSummary();
        
        console.log(`🏷️ Tag añadido: "${cleanTerm}"`);
    }

    /**
     * Eliminar un tag por índice
     * @param {number} index - Índice del tag a eliminar
     */
    removeTag(index) {
        if (index >= 0 && index < this.exclusionTerms.length) {
            const removedTerm = this.exclusionTerms.splice(index, 1)[0];
            this.renderTags();
            this.updateCollapsibleSummary();
            
            console.log(`🗑️ Tag eliminado: "${removedTerm}"`);
        }
    }

    /**
     * Renderizar todos los tags en el contenedor
     */
    renderTags() {
        const container = document.getElementById('exclusionTagsContainer');
        const countElement = document.getElementById('exclusionCount');
        const clearAllElement = document.getElementById('clearAllTags');
        
        if (!container) return;

        // Actualizar contador
        if (countElement) {
            countElement.textContent = this.exclusionTerms.length;
        }

        // Mostrar/ocultar botón "Clear All"
        if (clearAllElement) {
            clearAllElement.style.display = this.exclusionTerms.length > 0 ? 'block' : 'none';
        }

        if (this.exclusionTerms.length === 0) {
            container.innerHTML = '';
            return;
        }

        const tagsHTML = this.exclusionTerms.map((term, index) => `
            <div class="exclusion-tag">
                <span class="exclusion-tag-text">${this.escapeHtml(term)}</span>
                <span class="exclusion-tag-remove" onclick="window.keywordExclusion.removeTag(${index})">
                    <i class="fas fa-times"></i>
                </span>
            </div>
        `).join('');

        container.innerHTML = tagsHTML;
    }

    /**
     * Actualizar descripción del método seleccionado
     */
    updateMethodDescription() {
        const descriptionElement = document.getElementById('methodDescription');
        if (!descriptionElement) return;

        const descriptions = {
            'contains': 'Keywords containing these terms',
            'equals': 'Keywords exactly matching these terms',
            'startsWith': 'Keywords starting with these terms',
            'endsWith': 'Keywords ending with these terms'
        };

        descriptionElement.textContent = descriptions[this.exclusionMethod] || 'Unknown method';
    }

    /**
     * Configurar botón "Clear All"
     */
    setupClearAllButton() {
        const clearAllBtn = document.querySelector('.clear-all-btn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                this.clearAllTags();
            });
        }
    }

    /**
     * Limpiar todos los tags
     */
    clearAllTags() {
        if (this.exclusionTerms.length === 0) return;
        
        this.exclusionTerms = [];
        this.renderTags();
        this.updateCollapsibleSummary();
        
        console.log('🗑️ Todos los tags eliminados');
    }

    /**
     * Actualizar el resumen del sistema colapsable
     */
    updateCollapsibleSummary() {
        // Esta función se llama desde collapsible-sections.js
        if (window.updateCollapsibleSummary) {
            window.updateCollapsibleSummary('exclusion');
        }
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
     * Obtener resumen para el sistema colapsable
     * @returns {Object} Información del resumen
     */
    getSummaryInfo() {
        if (this.exclusionTerms.length === 0) {
            return { 
                count: 0, 
                method: '', 
                preview: '' 
            };
        }

        // Crear preview (máximo 3 términos)
        let preview = this.exclusionTerms.slice(0, 3).join(', ');
        if (this.exclusionTerms.length > 3) {
            preview += '...';
        }

        return {
            count: this.exclusionTerms.length,
            method: this.exclusionMethod,
            preview: preview
        };
    }

    /**
     * Escapar HTML para prevenir XSS
     * @param {string} text - Texto a escapar
     * @returns {string} Texto escapado
     */
    escapeHtml(text) {
        return window.ClicandseoHtml.escapeHtml(text);
    }

    /**
     * Resetear exclusiones
     */
    reset() {
        const exclusionInput = document.getElementById('exclusionTerms');
        const exclusionMethodSelect = document.getElementById('exclusionMethod');
        
        if (exclusionInput) {
            exclusionInput.value = '';
        }
        
        if (exclusionMethodSelect) {
            exclusionMethodSelect.value = 'contains';
        }
        
        this.exclusionTerms = [];
        this.exclusionMethod = 'contains';
        this.renderTags();
        this.updateMethodDescription();
        this.updateCollapsibleSummary();
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

// Función para obtener resumen (para el sistema colapsable)
window.getExclusionSummaryInfo = function() {
    return window.keywordExclusion.getSummaryInfo();
};