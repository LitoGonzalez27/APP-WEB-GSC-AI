/**
 * LLM Monitoring - métodos de prototipo: modals
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

getSelectedLlmsFromModal() {
        const llmCheckboxes = document.querySelectorAll('input[name="llm"]:checked');
        return this.normalizeLlmSelection(Array.from(llmCheckboxes).map(cb => cb.value));
    },

setupConfirmModalListeners() {
        const modal = document.getElementById('actionConfirmModal');
        if (!modal || modal.dataset.listenersAttached === 'true') return;

        const closeBtn = document.getElementById('actionConfirmClose');
        const cancelBtn = document.getElementById('actionConfirmCancel');
        const acceptBtn = document.getElementById('actionConfirmAccept');

        const cancelHandler = () => this.resolveConfirmDialog(false);
        const acceptHandler = () => this.resolveConfirmDialog(true);

        closeBtn?.addEventListener('click', cancelHandler);
        cancelBtn?.addEventListener('click', cancelHandler);
        acceptBtn?.addEventListener('click', acceptHandler);

        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                this.resolveConfirmDialog(false);
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && this.isConfirmModalOpen) {
                this.resolveConfirmDialog(false);
            }
        });

        modal.dataset.listenersAttached = 'true';
    },

showConfirmDialog({
        title = 'Confirm action',
        message = 'Are you sure?',
        confirmText = 'Confirm',
        cancelText = 'Cancel',
        variant = 'warning'
    } = {}) {
        const modal = document.getElementById('actionConfirmModal');
        const titleEl = document.getElementById('actionConfirmTitle');
        const messageEl = document.getElementById('actionConfirmMessage');
        const iconEl = document.getElementById('actionConfirmIcon');
        const cancelBtn = document.getElementById('actionConfirmCancel');
        const acceptBtn = document.getElementById('actionConfirmAccept');

        if (!modal || !titleEl || !messageEl || !cancelBtn || !acceptBtn) {
            console.error('Custom confirm modal is not available in DOM');
            return Promise.resolve(false);
        }

        // If there is a pending dialog, resolve it as cancelled first.
        if (this.confirmResolver) {
            this.confirmResolver(false);
            this.confirmResolver = null;
        }

        this.setupConfirmModalListeners();

        titleEl.textContent = title;
        messageEl.textContent = message;
        cancelBtn.textContent = cancelText;
        acceptBtn.textContent = confirmText;

        modal.dataset.variant = variant;
        acceptBtn.classList.remove('confirm-warning', 'confirm-danger');
        iconEl?.classList.remove('variant-warning', 'variant-danger');

        if (variant === 'danger') {
            acceptBtn.classList.add('confirm-danger');
            iconEl?.classList.add('variant-danger');
            if (iconEl) iconEl.innerHTML = '<i class="fas fa-trash-alt"></i>';
        } else {
            acceptBtn.classList.add('confirm-warning');
            iconEl?.classList.add('variant-warning');
            if (iconEl) iconEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i>';
        }

        modal.style.display = 'flex';
        requestAnimationFrame(() => {
            modal.classList.add('show');
        });
        this.isConfirmModalOpen = true;

        return new Promise((resolve) => {
            this.confirmResolver = resolve;
        });
    },

resolveConfirmDialog(confirmed) {
        const modal = document.getElementById('actionConfirmModal');
        if (modal) {
            modal.classList.remove('show');
            setTimeout(() => {
                modal.style.display = 'none';
            }, 120);
        }
        this.isConfirmModalOpen = false;

        if (this.confirmResolver) {
            const resolve = this.confirmResolver;
            this.confirmResolver = null;
            resolve(confirmed);
        }
    },

showToast(message, type = 'info', durationMs = 3800) {
        const container = document.getElementById('llmToastContainer');
        if (!container) {
            console.log(`[${type}] ${message}`);
            return;
        }

        const iconByType = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            info: 'fa-info-circle'
        };

        const toast = document.createElement('div');
        toast.className = `llm-toast llm-toast-${type}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.innerHTML = `
            <div class="llm-toast-icon">
                <i class="fas ${iconByType[type] || iconByType.info}"></i>
            </div>
            <div class="llm-toast-message">${this.escapeHtml(String(message || ''))}</div>
            <button type="button" class="llm-toast-close" aria-label="Close notification">
                <i class="fas fa-times"></i>
            </button>
        `;

        const removeToast = () => {
            if (!toast.parentNode) return;
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 180);
        };

        toast.querySelector('.llm-toast-close')?.addEventListener('click', removeToast);

        container.appendChild(toast);
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        setTimeout(removeToast, durationMs);
    },

showCompareModal() {
        const responses = this.allResponses;
        
        if (!responses || responses.length === 0) {
            this.showError('No responses available to compare');
            return;
        }

        // Get unique prompts
        const prompts = [...new Set(responses.map(r => r.query_text))];
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'compare-modal-overlay';
        modal.id = 'compareModal';
        
        // Get brand and competitor names for legend
        const brandName = this.currentProject?.brand_name || 'Tu marca';
        const competitors = this.currentProject?.selected_competitors || [];
        const competitorNames = competitors.map(c => c.domain || c.name || 'Competidor').slice(0, 3);

        modal.innerHTML = `
            <div class="compare-modal">
                <div class="compare-modal-header">
                    <h3><i class="fas fa-columns"></i> Compare LLM Responses</h3>
                    <button class="compare-modal-close" onclick="document.getElementById('compareModal').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="compare-modal-controls">
                    <label>
                        <i class="fas fa-search"></i>
                        Select Prompt:
                    </label>
                    <select id="comparePromptSelect" onchange="window.llmMonitoring.updateCompareView()">
                        ${prompts.map((p, i) => `
                            <option value="${i}">${p.length > 80 ? p.substring(0, 80) + '...' : p}</option>
                        `).join('')}
                    </select>
                    
                    <!-- ✨ Leyenda visual -->
                    <div class="compare-legend">
                        <div class="compare-legend-item">
                            <span class="legend-badge brand-badge">✓</span>
                            <span class="legend-text">Marca mencionada</span>
                        </div>
                        <div class="compare-legend-item">
                            <span class="legend-badge position-badge">#N</span>
                            <span class="legend-text">Posición en lista</span>
                        </div>
                        <div class="compare-legend-separator"></div>
                        <div class="compare-legend-item">
                            <mark class="brand-mention">${this.escapeHtml(brandName)}</mark>
                            <span class="legend-text">Tu marca</span>
                        </div>
                        ${competitorNames.length > 0 ? `
                            <div class="compare-legend-item">
                                <mark class="competitor-mention">${this.escapeHtml(competitorNames[0])}</mark>
                                <span class="legend-text">Competidor</span>
                            </div>
                        ` : ''}
                    </div>
                </div>
                
                <div class="compare-modal-body">
                    <div class="compare-grid" id="compareGrid">
                        <!-- Will be populated by updateCompareView -->
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        
        // Store prompts for reference
        this.comparePrompts = prompts;
        this.compareLlms = this.getProjectEnabledLlms();
        
        // Initial render
        this.updateCompareView();

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

        // Close on Escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

});
