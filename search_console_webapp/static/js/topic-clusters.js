/* ==============================================
   TOPIC CLUSTERS SYSTEM
   Lógica para agrupar keywords en clusters temáticos para análisis de AI Overview
   ============================================== */

/**
 * Clase para manejar el sistema de Topic Clusters
 */
class TopicClusters {
    constructor() {
        this.clusters = [];
        this.clusterMethod = 'contains';
        this.init();
    }

    /**
     * Inicializar event listeners
     */
    init() {
        const clusterNameInput = document.getElementById('clusterName');
        const clusterTermsInput = document.getElementById('clusterTerms');
        const clusterMethodSelect = document.getElementById('clusterMethod');

        if (clusterNameInput) {
            clusterNameInput.addEventListener('keydown', (e) => this.handleNameKeyDown(e));
        }

        if (clusterTermsInput) {
            clusterTermsInput.addEventListener('keydown', (e) => this.handleTermsKeyDown(e));
            clusterTermsInput.addEventListener('input', (e) => this.handleTermsInput(e));
        }

        if (clusterMethodSelect) {
            clusterMethodSelect.addEventListener('change', (e) => {
                this.clusterMethod = e.target.value;
                this.updateMethodDescription();
                this.updateCollapsibleSummary();
            });
        }

        // Inicializar descripción del método
        this.updateMethodDescription();

        // Configurar botón "Clear All"
        this.setupClearAllButton();

        // Renderizar clusters vacíos inicialmente
        this.renderClusters();
        console.log('✅ Sistema de Topic Clusters inicializado');
    }

    /**
     * Manejar eventos de teclado en el input de nombre del cluster
     * @param {KeyboardEvent} e - Evento de teclado
     */
    handleNameKeyDown(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Enfocar el input de términos
            const termsInput = document.getElementById('clusterTerms');
            if (termsInput) {
                termsInput.focus();
            }
        }
    }

    /**
     * Manejar eventos de teclado en el input de términos
     * @param {KeyboardEvent} e - Evento de teclado
     */
    handleTermsKeyDown(e) {
        const termsInput = e.target;
        const nameInput = document.getElementById('clusterName');
        const value = termsInput.value.trim();
        const clusterName = nameInput ? nameInput.value.trim() : '';

        // Crear cluster al presionar coma o Enter (si hay nombre y términos)
        if ((e.key === ',' || e.key === 'Enter') && value && clusterName) {
            e.preventDefault();
            this.addTermToCurrentCluster(value);
            termsInput.value = '';
        }

        // Finalizar cluster con Enter si hay nombre pero no términos (crear cluster con términos previos)
        if (e.key === 'Enter' && !value && clusterName) {
            e.preventDefault();
            this.finalizeCurrentCluster();
        }
    }

    /**
     * Manejar eventos de input para detectar comas pegadas
     * @param {InputEvent} e - Evento de input
     */
    handleTermsInput(e) {
        const input = e.target;
        const value = input.value;

        // Si el usuario pegó texto con comas, procesarlo
        if (value.includes(',')) {
            const parts = value.split(',');
            const lastPart = parts.pop(); // La última parte permanece en el input
            
            // Añadir todas las partes excepto la última como términos
            parts.forEach(part => {
                const trimmed = part.trim();
                if (trimmed) {
                    this.addTermToCurrentCluster(trimmed);
                }
            });
            
            // Mantener la última parte en el input
            input.value = lastPart.trim();
        }
    }

    /**
     * Añadir un término al cluster actual (temporal)
     * @param {string} term - Término a añadir
     */
    addTermToCurrentCluster(term) {
        const nameInput = document.getElementById('clusterName');
        const clusterName = nameInput ? nameInput.value.trim() : '';
        
        if (!clusterName) {
            if (window.showToast) {
                window.showToast('Please enter a cluster name first', 'warning');
            }
            return;
        }

        const cleanTerm = term.trim().toLowerCase();
        if (!cleanTerm) return;

        // Buscar si ya existe un cluster con este nombre
        let existingCluster = this.clusters.find(cluster => cluster.name === clusterName);
        
        if (!existingCluster) {
            // Crear nuevo cluster
            existingCluster = {
                name: clusterName,
                terms: [],
                method: this.clusterMethod
            };
            this.clusters.push(existingCluster);
        }

        // Añadir término si no existe ya
        if (!existingCluster.terms.includes(cleanTerm)) {
            existingCluster.terms.push(cleanTerm);
            this.renderClusters();
            this.updateCollapsibleSummary();
            
            console.log(`🏷️ Término añadido al cluster "${clusterName}": "${cleanTerm}"`);
        }
    }

    /**
     * Finalizar el cluster actual y limpiar inputs
     */
    finalizeCurrentCluster() {
        const nameInput = document.getElementById('clusterName');
        const termsInput = document.getElementById('clusterTerms');
        
        if (nameInput) nameInput.value = '';
        if (termsInput) termsInput.value = '';
        
        if (window.showToast) {
            window.showToast('Cluster created! Add another one if needed', 'success');
        }
    }

    /**
     * Eliminar un cluster completo
     * @param {number} index - Índice del cluster a eliminar
     */
    removeCluster(index) {
        if (index >= 0 && index < this.clusters.length) {
            const removedCluster = this.clusters.splice(index, 1)[0];
            this.renderClusters();
            this.updateCollapsibleSummary();
            
            console.log(`🗑️ Cluster eliminado: "${removedCluster.name}"`);
        }
    }

    /**
     * Eliminar un término específico de un cluster
     * @param {number} clusterIndex - Índice del cluster
     * @param {number} termIndex - Índice del término
     */
    removeTerm(clusterIndex, termIndex) {
        if (clusterIndex >= 0 && clusterIndex < this.clusters.length) {
            const cluster = this.clusters[clusterIndex];
            if (termIndex >= 0 && termIndex < cluster.terms.length) {
                const removedTerm = cluster.terms.splice(termIndex, 1)[0];
                
                // Si no quedan términos, eliminar el cluster completo
                if (cluster.terms.length === 0) {
                    this.removeCluster(clusterIndex);
                } else {
                    this.renderClusters();
                    this.updateCollapsibleSummary();
                }
                
                console.log(`🗑️ Término eliminado: "${removedTerm}" del cluster "${cluster.name}"`);
            }
        }
    }

    /**
     * Renderizar todos los clusters en el contenedor
     */
    renderClusters() {
        const container = document.getElementById('clustersContainer');
        const countElement = document.getElementById('clustersCount');
        const clearAllElement = document.getElementById('clearAllClusters');
        
        if (!container) return;

        // Actualizar contador
        if (countElement) {
            countElement.textContent = this.clusters.length;
        }

        // Mostrar/ocultar botón "Clear All"
        if (clearAllElement) {
            clearAllElement.style.display = this.clusters.length > 0 ? 'block' : 'none';
        }

        if (this.clusters.length === 0) {
            container.innerHTML = '';
            return;
        }

        const clustersHTML = this.clusters.map((cluster, clusterIndex) => `
            <div class="cluster-group">
                <div class="cluster-header">
                    <span class="cluster-name">${this.escapeHtml(cluster.name)}</span>
                    <span class="cluster-remove" onclick="window.topicClusters.removeCluster(${clusterIndex})">
                        <i class="fas fa-times"></i>
                    </span>
                </div>
                <div class="cluster-terms">
                    ${cluster.terms.map((term, termIndex) => `
                        <div class="exclusion-tag cluster-term">
                            <span class="exclusion-tag-text">${this.escapeHtml(term)}</span>
                            <span class="exclusion-tag-remove" onclick="window.topicClusters.removeTerm(${clusterIndex}, ${termIndex})">
                                <i class="fas fa-times"></i>
                            </span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');

        container.innerHTML = clustersHTML;
    }

    /**
     * Actualizar descripción del método seleccionado
     */
    updateMethodDescription() {
        const descriptionElement = document.getElementById('clusterMethodDescription');
        if (!descriptionElement) return;

        const descriptions = {
            'contains': 'Keywords containing cluster terms',
            'equals': 'Keywords exactly matching cluster terms',
            'notContains': 'Keywords not containing cluster terms',
            'notEquals': 'Keywords not equal to cluster terms'
        };

        descriptionElement.textContent = descriptions[this.clusterMethod] || 'Unknown method';
    }

    /**
     * Configurar botón "Clear All"
     */
    setupClearAllButton() {
        const clearAllBtn = document.querySelector('#clearAllClusters .clear-all-btn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                this.clearAllClusters();
            });
        }
    }

    /**
     * Limpiar todos los clusters
     */
    clearAllClusters() {
        if (this.clusters.length === 0) return;
        
        this.clusters = [];
        this.renderClusters();
        this.updateCollapsibleSummary();
        
        // Limpiar también los inputs
        const nameInput = document.getElementById('clusterName');
        const termsInput = document.getElementById('clusterTerms');
        
        if (nameInput) nameInput.value = '';
        if (termsInput) termsInput.value = '';
        
        console.log('🗑️ Todos los clusters eliminados');
    }

    /**
     * Actualizar el resumen del sistema colapsable
     */
    updateCollapsibleSummary() {
        // Esta función se llama desde collapsible-sections.js
        if (window.updateCollapsibleSummary) {
            window.updateCollapsibleSummary('topicClusters');
        }
    }

    /**
     * Clasificar una keyword en clusters basado en los términos definidos
     * @param {string} keyword - Keyword a clasificar
     * @returns {Array} Array de nombres de clusters que coinciden
     */
    classifyKeyword(keyword) {
        if (!keyword || this.clusters.length === 0) {
            return [];
        }

        const keywordLower = keyword.toLowerCase();
        const matchingClusters = [];

        this.clusters.forEach(cluster => {
            const matches = cluster.terms.some(term => {
                switch (cluster.method || this.clusterMethod) {
                    case 'contains':
                        return keywordLower.includes(term);
                    case 'equals':
                        return keywordLower === term;
                    case 'notContains':
                        return !keywordLower.includes(term);
                    case 'notEquals':
                        return keywordLower !== term;
                    default:
                        return false;
                }
            });

            if (matches) {
                matchingClusters.push(cluster.name);
            }
        });

        return matchingClusters;
    }

    /**
     * Agrupar keywords por clusters
     * @param {Array} keywords - Array de keywords con datos de Search Console
     * @returns {Object} Objeto con clusters como keys y arrays de keywords como values
     */
    groupKeywordsByClusters(keywords) {
        if (!Array.isArray(keywords) || this.clusters.length === 0) {
            return {};
        }

        const clusteredKeywords = {};
        const unclassifiedKeywords = [];

        // Inicializar clusters
        this.clusters.forEach(cluster => {
            clusteredKeywords[cluster.name] = [];
        });

        // Clasificar cada keyword
        keywords.forEach(keywordData => {
            const keywordText = typeof keywordData === 'string' ? keywordData : keywordData.keyword;
            const matchingClusters = this.classifyKeyword(keywordText);

            if (matchingClusters.length > 0) {
                // Añadir a todos los clusters que coinciden
                matchingClusters.forEach(clusterName => {
                    clusteredKeywords[clusterName].push(keywordData);
                });
            } else {
                unclassifiedKeywords.push(keywordData);
            }
        });

        // Añadir cluster especial para keywords no clasificadas
        if (unclassifiedKeywords.length > 0) {
            clusteredKeywords['Unclassified'] = unclassifiedKeywords;
        }

        console.log(`🔍 Keywords agrupadas en ${Object.keys(clusteredKeywords).length} clusters`);
        
        return clusteredKeywords;
    }

    /**
     * Obtener configuración de clusters para enviar al backend
     * @returns {Object} Configuración de clusters
     */
    getClustersConfig() {
        return {
            method: this.clusterMethod,
            clusters: this.clusters,
            enabled: this.clusters.length > 0
        };
    }

    /**
     * Obtener resumen para el sistema colapsable
     * @returns {Object} Información del resumen
     */
    getSummaryInfo() {
        if (this.clusters.length === 0) {
            return { 
                count: 0, 
                method: '', 
                preview: '' 
            };
        }

        // Crear preview (máximo 3 clusters)
        let preview = this.clusters.slice(0, 3).map(cluster => cluster.name).join(', ');
        if (this.clusters.length > 3) {
            preview += '...';
        }

        const totalTerms = this.clusters.reduce((sum, cluster) => sum + cluster.terms.length, 0);

        return {
            count: this.clusters.length,
            method: this.clusterMethod,
            preview: preview,
            totalTerms: totalTerms
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
     * Resetear clusters
     */
    reset() {
        const clusterNameInput = document.getElementById('clusterName');
        const clusterTermsInput = document.getElementById('clusterTerms');
        const clusterMethodSelect = document.getElementById('clusterMethod');
        
        if (clusterNameInput) {
            clusterNameInput.value = '';
        }
        
        if (clusterTermsInput) {
            clusterTermsInput.value = '';
        }
        
        if (clusterMethodSelect) {
            clusterMethodSelect.value = 'contains';
        }
        
        this.clusters = [];
        this.clusterMethod = 'contains';
        this.renderClusters();
        this.updateMethodDescription();
        this.updateCollapsibleSummary();
    }

    /**
     * Obtener estadísticas de clustering
     * @param {Array} originalKeywords - Keywords originales
     * @returns {Object} Estadísticas
     */
    getClusteringStats(originalKeywords) {
        const clusteredKeywords = this.groupKeywordsByClusters(originalKeywords);
        const clusteredCount = Object.values(clusteredKeywords)
            .reduce((sum, keywords) => sum + keywords.length, 0);
        const unclassifiedCount = clusteredKeywords['Unclassified'] ? clusteredKeywords['Unclassified'].length : 0;
        const classifiedCount = clusteredCount - unclassifiedCount;
        const classificationRate = originalKeywords.length > 0 ? (classifiedCount / originalKeywords.length * 100).toFixed(1) : 0;

        return {
            totalKeywords: originalKeywords.length,
            totalClusters: this.clusters.length,
            classifiedKeywords: classifiedCount,
            unclassifiedKeywords: unclassifiedCount,
            classificationRate: classificationRate
        };
    }
}

// Instancia global
window.topicClusters = new TopicClusters();

// Función para integrar con el análisis existente
window.getTopicClustersConfig = function() {
    return window.topicClusters.getClustersConfig();
};

// Función para agrupar keywords por clusters
window.groupKeywordsByClusters = function(keywords) {
    return window.topicClusters.groupKeywordsByClusters(keywords);
};

// Función para obtener resumen (para el sistema colapsable)
window.getTopicClustersSummaryInfo = function() {
    return window.topicClusters.getSummaryInfo();
};
