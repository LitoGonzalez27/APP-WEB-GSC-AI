// ui-date-selector.js - Componente de selección de fechas avanzado con Modal
import { elems, storage } from './utils.js';

export class DateRangeSelector {
    constructor() {
        this.currentPeriod = {
            startDate: null,
            endDate: null
        };
        this.comparisonPeriod = {
            startDate: null,
            endDate: null
        };
        this.comparisonMode = 'none'; // 'none', 'custom', 'pop', 'yoy'
        
        // ✅ ARREGLO: Límites de GSC corregidos (máximo 16 meses hacia atrás)
        this.maxDate = new Date();
        this.maxDate.setDate(this.maxDate.getDate() - 3); // GSC tiene delay de ~3 días
        
        this.minDate = new Date();
        this.minDate.setMonth(this.minDate.getMonth() - 16);
        
        this.isModalOpen = false;
        
        // ✅ DEBUGGING: Log de límites de fechas
        console.log('📅 Límites de fechas GSC:');
        console.log('  Fecha mínima:', this.formatDateForDisplay(this.minDate));
        console.log('  Fecha máxima:', this.formatDateForDisplay(this.maxDate));
        
        this.init();
    }

    init() {
        this.createHTML();
        this.attachEventListeners();
        this.loadSavedDates();
        this.setDefaultDates();
    }

    createHTML() {
        const container = document.getElementById('monthChips');
        if (!container) {
            console.error('Container monthChips no encontrado');
            return;
        }

        // Crear el botón que abrirá el modal y el resumen de fechas seleccionadas
        container.innerHTML = `
            <div class="date-selector-trigger-container">
                <!-- Botón principal para abrir el modal -->
                <button type="button" class="date-selector-btn" id="dateRangeTrigger">
                    <div class="btn-content">
                        <div class="btn-icon">
                            <i class="fas fa-calendar-alt"></i>
                        </div>
                        <div class="btn-text">
                            <span class="btn-title">Date Range & Comparison</span>
                            <span class="btn-subtitle" id="dateRangePreview">Click to select dates</span>
                        </div>
                        <div class="btn-arrow">
                            <i class="fas fa-chevron-right"></i>
                        </div>
                    </div>
                </button>

                <!-- Badges de resumen cuando hay fechas seleccionadas -->
                <div class="date-summary-badges" id="dateSummaryBadges" style="display: none;">
                    <div class="date-badge date-badge-primary" id="primaryPeriodBadge">
                        <i class="fas fa-calendar"></i>
                        <span id="primaryPeriodText">Period 1</span>
                    </div>
                    <div class="date-badge date-badge-comparison" id="comparisonPeriodBadge" style="display: none;">
                        <i class="fas fa-exchange-alt"></i>
                        <span id="comparisonPeriodText">Comparison</span>
                    </div>
                </div>
            </div>

            <!-- Modal del selector de fechas -->
            <div class="date-modal-overlay" id="dateModalOverlay" style="display: none;">
                <div class="date-modal" id="dateModal">
                    <div class="date-modal-header">
                        <h2 class="modal-title">
                            <i class="fas fa-calendar-alt"></i>
                            Select Date Range & Comparison
                        </h2>
                        <button type="button" class="modal-close-btn" id="modalCloseBtn">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <div class="date-modal-body">
                        <div class="date-selector-container">
                            <!-- Período Principal -->
                            <div class="date-period-section">
                                <div class="period-header">
                                    <h3 class="period-title">
                                        <i class="fas fa-calendar-alt"></i>
                                        Primary Period
                                    </h3>
                                    <span class="period-preview" id="currentPeriodPreview">
                                        Select dates
                                    </span>
                                </div>
                                
                                <div class="date-inputs-row">
                                    <div class="date-input-group">
                                        <label for="currentStartDate">Start Date</label>
                                        <input 
                                            type="date" 
                                            id="currentStartDate" 
                                            class="date-input"
                                            min="${this.formatDate(this.minDate)}"
                                            max="${this.formatDate(this.maxDate)}"
                                        >
                                    </div>
                                    
                                    <div class="date-input-group">
                                        <label for="currentEndDate">End Date</label>
                                        <input 
                                            type="date" 
                                            id="currentEndDate" 
                                            class="date-input"
                                            min="${this.formatDate(this.minDate)}"
                                            max="${this.formatDate(this.maxDate)}"
                                        >
                                    </div>
                                </div>

                                <!-- Presets rápidos -->
                                <div class="date-presets">
                                    <span class="presets-label">Quick presets:</span>
                                    <button type="button" class="preset-btn" data-preset="last7days">Last 7 days</button>
                                    <button type="button" class="preset-btn" data-preset="last30days">Last 30 days</button>
                                    <button type="button" class="preset-btn" data-preset="last3months">Last 3 months</button>
                                    <button type="button" class="preset-btn" data-preset="currentMonth">Current month</button>
                                    <button type="button" class="preset-btn" data-preset="lastMonth">Last month</button>
                                </div>
                            </div>

                            <!-- Comparación -->
                            <div class="date-comparison-section">
                                <div class="comparison-header">
                                    <h3 class="period-title">
                                        <i class="fas fa-exchange-alt"></i>
                                        Comparison (Optional)
                                    </h3>
                                    <span class="period-preview" id="comparisonPeriodPreview">
                                        No comparison
                                    </span>
                                </div>

                                <!-- Opciones de comparación -->
                                <div class="comparison-options">
                                    <div class="comparison-mode-group">
                                        <input type="radio" id="comparisonNone" name="comparisonMode" value="none" checked>
                                        <label for="comparisonNone" class="comparison-mode-btn">
                                            <i class="fas fa-times"></i>
                                            <span>No comparison</span>
                                        </label>

                                        <input type="radio" id="comparisonPop" name="comparisonMode" value="pop">
                                        <label for="comparisonPop" class="comparison-mode-btn">
                                            <i class="fas fa-calendar-week"></i>
                                            <span>Previous Period</span>
                                        </label>

                                        <input type="radio" id="comparisonYoy" name="comparisonMode" value="yoy">
                                        <label for="comparisonYoy" class="comparison-mode-btn">
                                            <i class="fas fa-calendar-year"></i>
                                            <span>Year over Year</span>
                                        </label>

                                        <input type="radio" id="comparisonCustom" name="comparisonMode" value="custom">
                                        <label for="comparisonCustom" class="comparison-mode-btn">
                                            <i class="fas fa-calendar-edit"></i>
                                            <span>Custom Period</span>
                                        </label>
                                    </div>
                                </div>

                                <!-- Fechas de comparación personalizada -->
                                <div class="custom-comparison-dates" id="customComparisonDates" style="display: none;">
                                    <div class="date-inputs-row">
                                        <div class="date-input-group">
                                            <label for="comparisonStartDate">Start Date</label>
                                            <input 
                                                type="date" 
                                                id="comparisonStartDate" 
                                                class="date-input"
                                                min="${this.formatDate(this.minDate)}"
                                                max="${this.formatDate(this.maxDate)}"
                                            >
                                        </div>
                                        
                                        <div class="date-input-group">
                                            <label for="comparisonEndDate">End Date</label>
                                            <input 
                                                type="date" 
                                                id="comparisonEndDate" 
                                                class="date-input"
                                                min="${this.formatDate(this.minDate)}"
                                                max="${this.formatDate(this.maxDate)}"
                                            >
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Información adicional -->
                            <div class="date-info-section">
                                <div class="date-info-card">
                                    <i class="fas fa-info-circle"></i>
                                    <div class="info-content">
                                        <strong>Duration:</strong>
                                        <span id="dateRangeDuration">Select a period to see duration</span>
                                    </div>
                                </div>
                                
                                <!-- ✅ NUEVO: Info sobre límites GSC -->
                                <div class="date-info-card" style="background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.2); color: #DC2626;">
                                    <i class="fas fa-exclamation-triangle"></i>
                                    <div class="info-content">
                                        <strong>GSC Limits:</strong>
                                        <span>Data available from ${this.formatDateForDisplay(this.minDate)} to ${this.formatDateForDisplay(this.maxDate)}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="date-modal-footer">
                        <button type="button" class="btn-modal btn-modal-secondary" id="modalCancelBtn">
                            <i class="fas fa-times"></i>
                            Cancel
                        </button>
                        <button type="button" class="btn-modal btn-modal-primary" id="modalApplyBtn">
                            <i class="fas fa-check"></i>
                            Apply Selection
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    attachEventListeners() {
        // Botón para abrir el modal
        const triggerBtn = document.getElementById('dateRangeTrigger');
        if (triggerBtn) {
            triggerBtn.addEventListener('click', () => this.openModal());
        }

        // Botones para cerrar el modal
        const modalCloseBtn = document.getElementById('modalCloseBtn');
        const modalCancelBtn = document.getElementById('modalCancelBtn');
        const modalOverlay = document.getElementById('dateModalOverlay');

        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', () => this.closeModal());
        }
        if (modalCancelBtn) {
            modalCancelBtn.addEventListener('click', () => this.closeModal());
        }
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) {
                    this.closeModal();
                }
            });
        }

        // Botón para aplicar selección
        const modalApplyBtn = document.getElementById('modalApplyBtn');
        if (modalApplyBtn) {
            modalApplyBtn.addEventListener('click', () => this.applyAndCloseModal());
        }

        // Escape key para cerrar modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isModalOpen) {
                this.closeModal();
            }
        });

        // Inputs de fecha principal
        const currentStartDate = document.getElementById('currentStartDate');
        const currentEndDate = document.getElementById('currentEndDate');
        
        if (currentStartDate) {
            currentStartDate.addEventListener('change', () => this.handleCurrentDateChange());
        }
        if (currentEndDate) {
            currentEndDate.addEventListener('change', () => this.handleCurrentDateChange());
        }

        // Presets rápidos
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const preset = e.target.dataset.preset;
                this.applyPreset(preset);
            });
        });

        // Modos de comparación
        document.querySelectorAll('input[name="comparisonMode"]').forEach(radio => {
            radio.addEventListener('change', () => this.handleComparisonModeChange());
        });

        // Inputs de fecha de comparación personalizada
        const comparisonStartDate = document.getElementById('comparisonStartDate');
        const comparisonEndDate = document.getElementById('comparisonEndDate');
        
        if (comparisonStartDate) {
            comparisonStartDate.addEventListener('change', () => this.handleComparisonDateChange());
        }
        if (comparisonEndDate) {
            comparisonEndDate.addEventListener('change', () => this.handleComparisonDateChange());
        }
    }

    openModal() {
        const overlay = document.getElementById('dateModalOverlay');
        const modal = document.getElementById('dateModal');
        
        if (overlay && modal) {
            this.isModalOpen = true;
            overlay.style.display = 'flex';
            document.body.classList.add('modal-open');
            
            // Animación de entrada
            requestAnimationFrame(() => {
                overlay.classList.add('show');
                modal.classList.add('show');
            });
        }
    }

    closeModal() {
        const overlay = document.getElementById('dateModalOverlay');
        const modal = document.getElementById('dateModal');
        
        if (overlay && modal) {
            overlay.classList.remove('show');
            modal.classList.remove('show');
            
            setTimeout(() => {
                overlay.style.display = 'none';
                document.body.classList.remove('modal-open');
                this.isModalOpen = false;
            }, 300);
        }
    }

    applyAndCloseModal() {
        // Validar fechas antes de cerrar
        const validation = this.validateDates();
        if (!validation.isValid) {
            this.showDateError(validation.errors[0]);
            return;
        }

        this.updateTriggerButton();
        this.updateSummaryBadges();
        this.saveToStorage();
        this.closeModal();
    }

    updateTriggerButton() {
        const preview = document.getElementById('dateRangePreview');
        if (!preview) return;

        if (this.currentPeriod.startDate && this.currentPeriod.endDate) {
            const duration = Math.ceil((this.currentPeriod.endDate - this.currentPeriod.startDate) / (1000 * 60 * 60 * 24)) + 1;
            let text = `${this.formatDateForDisplay(this.currentPeriod.startDate)} - ${this.formatDateForDisplay(this.currentPeriod.endDate)}`;
            
            if (this.comparisonMode !== 'none' && this.comparisonPeriod.startDate) {
                const comparisonLabels = {
                    'pop': 'vs Previous Period',
                    'yoy': 'vs Last Year',
                    'custom': 'vs Custom Period'
                };
                text += ` ${comparisonLabels[this.comparisonMode] || ''}`;
            }
            
            preview.textContent = text;
        } else {
            preview.textContent = 'Click to select dates';
        }
    }

    updateSummaryBadges() {
        const container = document.getElementById('dateSummaryBadges');
        const primaryBadge = document.getElementById('primaryPeriodBadge');
        const comparisonBadge = document.getElementById('comparisonPeriodBadge');
        const primaryText = document.getElementById('primaryPeriodText');
        const comparisonText = document.getElementById('comparisonPeriodText');

        if (!container || !primaryBadge || !comparisonBadge) return;

        if (this.currentPeriod.startDate && this.currentPeriod.endDate) {
            container.style.display = 'flex';
            const duration = Math.ceil((this.currentPeriod.endDate - this.currentPeriod.startDate) / (1000 * 60 * 60 * 24)) + 1;
            primaryText.textContent = `${this.formatDateForDisplay(this.currentPeriod.startDate)} - ${this.formatDateForDisplay(this.currentPeriod.endDate)} (${duration} days)`;

            if (this.comparisonMode !== 'none' && this.comparisonPeriod.startDate && this.comparisonPeriod.endDate) {
                comparisonBadge.style.display = 'flex';
                const compDuration = Math.ceil((this.comparisonPeriod.endDate - this.comparisonPeriod.startDate) / (1000 * 60 * 60 * 24)) + 1;
                const modeLabels = {
                    'pop': 'Previous Period',
                    'yoy': 'Year over Year',
                    'custom': 'Custom Period'
                };
                comparisonText.textContent = `${modeLabels[this.comparisonMode]}: ${this.formatDateForDisplay(this.comparisonPeriod.startDate)} - ${this.formatDateForDisplay(this.comparisonPeriod.endDate)} (${compDuration} days)`;
            } else {
                comparisonBadge.style.display = 'none';
            }
        } else {
            container.style.display = 'none';
        }
    }

    setDefaultDates() {
        // ✅ ARREGLO: Por defecto usar fechas reales del pasado (últimos 30 días)
        const endDate = new Date(this.maxDate);
        const startDate = new Date(endDate);
        startDate.setDate(startDate.getDate() - 30);
        
        // ✅ DEBUGGING: Log de fechas por defecto
        console.log('📅 Fechas por defecto establecidas:');
        console.log('  Inicio:', this.formatDateForDisplay(startDate));
        console.log('  Fin:', this.formatDateForDisplay(endDate));
        
        this.setCurrentPeriod(startDate, endDate);
        this.updateUI();
        this.updateTriggerButton();
        this.updateSummaryBadges();
    }

    applyPreset(preset) {
        const endDate = new Date(this.maxDate);
        let startDate = new Date(endDate);

        switch (preset) {
            case 'last7days':
                startDate.setDate(endDate.getDate() - 7);
                break;
            case 'last30days':
                startDate.setDate(endDate.getDate() - 30);
                break;
            case 'last3months':
                startDate.setMonth(endDate.getMonth() - 3);
                break;
            case 'currentMonth':
                // ✅ ARREGLO: Mes actual pero respetando límites GSC
                const currentMonth = new Date();
                currentMonth.setDate(currentMonth.getDate() - 3); // Respetar delay GSC
                startDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
                endDate.setTime(Math.min(
                    new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getTime(), // Último día del mes
                    this.maxDate.getTime() // No exceder límite GSC
                ));
                break;
            case 'lastMonth':
                // ✅ ARREGLO: Mes anterior completo
                const lastMonth = new Date(this.maxDate);
                lastMonth.setMonth(lastMonth.getMonth() - 1);
                endDate.setTime(new Date(lastMonth.getFullYear(), lastMonth.getMonth() + 1, 0).getTime()); // Último día del mes anterior
                startDate = new Date(lastMonth.getFullYear(), lastMonth.getMonth(), 1); // Primer día del mes anterior
                break;
        }

        // Asegurar que no excedamos los límites
        if (startDate < this.minDate) startDate = new Date(this.minDate);
        if (endDate > this.maxDate) endDate = new Date(this.maxDate);

        // ✅ DEBUGGING: Log de preset aplicado
        console.log(`📅 Preset "${preset}" aplicado:`, {
            inicio: this.formatDateForDisplay(startDate),
            fin: this.formatDateForDisplay(endDate)
        });

        this.setCurrentPeriod(startDate, endDate);
        this.updateComparison();
        this.updateUI();
        this.saveToStorage();
        
        // Activar animación en el preset seleccionado
        document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`[data-preset="${preset}"]`)?.classList.add('active');
        setTimeout(() => {
            document.querySelector(`[data-preset="${preset}"]`)?.classList.remove('active');
        }, 300);
    }

    handleCurrentDateChange() {
        const startInput = document.getElementById('currentStartDate');
        const endInput = document.getElementById('currentEndDate');
        
        if (!startInput?.value || !endInput?.value) return;

        // ✅ ARREGLO: Crear fechas sin problemas de zona horaria
        const startDate = this.parseDate(startInput.value);
        const endDate = this.parseDate(endInput.value);

        // Validar que la fecha de inicio sea anterior a la de fin
        if (startDate >= endDate) {
            this.showDateError('Start date must be before end date');
            return;
        }

        // Validar duración máxima (16 meses)
        const maxDuration = 16 * 30 * 24 * 60 * 60 * 1000; // ~16 meses en ms
        if (endDate - startDate > maxDuration) {
            this.showDateError('Period cannot exceed 16 months');
            return;
        }

        // ✅ DEBUGGING: Log de cambio de fechas
        console.log('📅 Fechas cambiadas manualmente:', {
            inicio: this.formatDateForDisplay(startDate),
            fin: this.formatDateForDisplay(endDate)
        });

        this.setCurrentPeriod(startDate, endDate);
        this.updateComparison();
        this.updateUI();
        this.saveToStorage();
    }

    handleComparisonModeChange() {
        const selectedMode = document.querySelector('input[name="comparisonMode"]:checked')?.value;
        this.comparisonMode = selectedMode || 'none';
        
        const customDates = document.getElementById('customComparisonDates');
        if (customDates) {
            customDates.style.display = selectedMode === 'custom' ? 'block' : 'none';
        }

        this.updateComparison();
        this.updateUI();
        this.saveToStorage();
    }

    handleComparisonDateChange() {
        if (this.comparisonMode !== 'custom') return;

        const startInput = document.getElementById('comparisonStartDate');
        const endInput = document.getElementById('comparisonEndDate');
        
        if (!startInput?.value || !endInput?.value) return;

        // ✅ ARREGLO: Crear fechas sin problemas de zona horaria
        const startDate = this.parseDate(startInput.value);
        const endDate = this.parseDate(endInput.value);

        if (startDate >= endDate) {
            this.showDateError('Comparison start date must be before end date');
            return;
        }

        this.setComparisonPeriod(startDate, endDate);
        this.updateUI();
        this.saveToStorage();
    }

    updateComparison() {
        if (!this.currentPeriod.startDate || !this.currentPeriod.endDate) return;

        const duration = this.currentPeriod.endDate - this.currentPeriod.startDate;

        switch (this.comparisonMode) {
            case 'pop': {
                // Período anterior de la misma duración
                const compEndDate = new Date(this.currentPeriod.startDate);
                compEndDate.setDate(compEndDate.getDate() - 1);
                const compStartDate = new Date(compEndDate.getTime() - duration);
                
                this.setComparisonPeriod(compStartDate, compEndDate);
                break;
            }
            case 'yoy': {
                // Mismo período del año anterior
                const compStartDate = new Date(this.currentPeriod.startDate);
                const compEndDate = new Date(this.currentPeriod.endDate);
                compStartDate.setFullYear(compStartDate.getFullYear() - 1);
                compEndDate.setFullYear(compEndDate.getFullYear() - 1);
                
                this.setComparisonPeriod(compStartDate, compEndDate);
                break;
            }
            case 'none':
            default:
                this.comparisonPeriod = { startDate: null, endDate: null };
                break;
        }
    }

    setCurrentPeriod(startDate, endDate) {
        this.currentPeriod = { startDate, endDate };
        
        const startInput = document.getElementById('currentStartDate');
        const endInput = document.getElementById('currentEndDate');
        
        if (startInput) startInput.value = this.formatDate(startDate);
        if (endInput) endInput.value = this.formatDate(endDate);
    }

    setComparisonPeriod(startDate, endDate) {
        this.comparisonPeriod = { startDate, endDate };
        
        if (this.comparisonMode === 'custom') {
            const startInput = document.getElementById('comparisonStartDate');
            const endInput = document.getElementById('comparisonEndDate');
            
            if (startInput) startInput.value = this.formatDate(startDate);
            if (endInput) endInput.value = this.formatDate(endDate);
        }
    }

    updateUI() {
        this.updatePeriodPreviews();
        this.updateDateInfo();
    }

    updatePeriodPreviews() {
        const currentPreview = document.getElementById('currentPeriodPreview');
        const comparisonPreview = document.getElementById('comparisonPeriodPreview');

        if (currentPreview && this.currentPeriod.startDate && this.currentPeriod.endDate) {
            const duration = Math.ceil((this.currentPeriod.endDate - this.currentPeriod.startDate) / (1000 * 60 * 60 * 24)) + 1;
            currentPreview.textContent = `${this.formatDateForDisplay(this.currentPeriod.startDate)} - ${this.formatDateForDisplay(this.currentPeriod.endDate)} (${duration} days)`;
        }

        if (comparisonPreview) {
            if (this.comparisonMode === 'none' || !this.comparisonPeriod.startDate) {
                comparisonPreview.textContent = 'No comparison';
            } else {
                const duration = Math.ceil((this.comparisonPeriod.endDate - this.comparisonPeriod.startDate) / (1000 * 60 * 60 * 24)) + 1;
                const modeLabels = {
                    'pop': 'Previous Period',
                    'yoy': 'Year over Year',
                    'custom': 'Custom Period'
                };
                comparisonPreview.textContent = `${modeLabels[this.comparisonMode]}: ${this.formatDateForDisplay(this.comparisonPeriod.startDate)} - ${this.formatDateForDisplay(this.comparisonPeriod.endDate)} (${duration} days)`;
            }
        }
    }

    updateDateInfo() {
        const infoElement = document.getElementById('dateRangeDuration');
        if (!infoElement || !this.currentPeriod.startDate || !this.currentPeriod.endDate) return;

        const duration = Math.ceil((this.currentPeriod.endDate - this.currentPeriod.startDate) / (1000 * 60 * 60 * 24)) + 1;
        const weekends = this.countWeekends(this.currentPeriod.startDate, this.currentPeriod.endDate);
        
        let info = `${duration} days`;
        if (weekends > 0) {
            info += ` (includes ${weekends} weekend days)`;
        }
        
        infoElement.textContent = info;
    }

    countWeekends(startDate, endDate) {
        let count = 0;
        const current = new Date(startDate);
        
        while (current <= endDate) {
            const dayOfWeek = current.getDay();
            if (dayOfWeek === 0 || dayOfWeek === 6) { // Domingo o Sábado
                count++;
            }
            current.setDate(current.getDate() + 1);
        }
        
        return count;
    }

    showDateError(message) {
        // Crear toast de error temporal
        const toast = document.createElement('div');
        toast.className = 'date-error-toast';
        toast.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    }

    // ✅ ARREGLO CRÍTICO: Función para crear fechas sin problemas de zona horaria
    parseDate(dateString) {
        if (!dateString) return null;
        
        // Crear fecha en UTC para evitar problemas de zona horaria
        const parts = dateString.split('-');
        return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    }

    // ✅ ARREGLO: Formatear fecha para input (YYYY-MM-DD)
    formatDate(date) {
        if (!date) return '';
        
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    }

    // ✅ ARREGLO: Formatear fecha para mostrar al usuario
    formatDateForDisplay(date) {
        if (!date) return '';
        return date.toLocaleDateString('en-US', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    }

    saveToStorage() {
        const dateData = {
            currentPeriod: {
                startDate: this.currentPeriod.startDate?.toISOString(),
                endDate: this.currentPeriod.endDate?.toISOString()
            },
            comparisonPeriod: {
                startDate: this.comparisonPeriod.startDate?.toISOString(),
                endDate: this.comparisonPeriod.endDate?.toISOString()
            },
            comparisonMode: this.comparisonMode
        };
        
        localStorage.setItem('dateRangeSelector', JSON.stringify(dateData));
        
        // ✅ DEBUGGING: Log de datos guardados
        console.log('💾 Fechas guardadas en localStorage:', dateData);
    }

    loadSavedDates() {
        try {
            const saved = localStorage.getItem('dateRangeSelector');
            if (!saved) return;

            const dateData = JSON.parse(saved);
            
            // ✅ ARREGLO: Validar que las fechas guardadas estén dentro de los límites
            if (dateData.currentPeriod.startDate && dateData.currentPeriod.endDate) {
                const startDate = new Date(dateData.currentPeriod.startDate);
                const endDate = new Date(dateData.currentPeriod.endDate);
                
                // Solo cargar si las fechas están dentro de los límites GSC
                if (startDate >= this.minDate && endDate <= this.maxDate) {
                    this.currentPeriod = { startDate, endDate };
                    console.log('📅 Fechas guardadas cargadas:', {
                        inicio: this.formatDateForDisplay(startDate),
                        fin: this.formatDateForDisplay(endDate)
                    });
                } else {
                    console.warn('⚠️ Fechas guardadas fuera de límites GSC, usando valores por defecto');
                }
            }

            if (dateData.comparisonPeriod.startDate && dateData.comparisonPeriod.endDate) {
                const startDate = new Date(dateData.comparisonPeriod.startDate);
                const endDate = new Date(dateData.comparisonPeriod.endDate);
                
                // Solo cargar si las fechas están dentro de los límites GSC
                if (startDate >= this.minDate && endDate <= this.maxDate) {
                    this.comparisonPeriod = { startDate, endDate };
                }
            }

            this.comparisonMode = dateData.comparisonMode || 'none';
            
            // Actualizar UI después de cargar
            setTimeout(() => {
                const modeRadio = document.querySelector(`input[name="comparisonMode"][value="${this.comparisonMode}"]`);
                if (modeRadio) {
                    modeRadio.checked = true;
                    this.handleComparisonModeChange();
                }
                this.updateUI();
                this.updateTriggerButton();
                this.updateSummaryBadges();
            }, 100);

        } catch (error) {
            console.warn('Error loading saved dates:', error);
        }
    }

    // Método para obtener las fechas en el formato que necesita el backend
    getFormattedDates() {
        const result = {
            currentPeriod: {
                startDate: this.formatDate(this.currentPeriod.startDate),
                endDate: this.formatDate(this.currentPeriod.endDate)
            },
            hasComparison: this.comparisonMode !== 'none' && this.comparisonPeriod.startDate && this.comparisonPeriod.endDate,
            comparisonMode: this.comparisonMode
        };

        if (result.hasComparison) {
            result.comparisonPeriod = {
                startDate: this.formatDate(this.comparisonPeriod.startDate),
                endDate: this.formatDate(this.comparisonPeriod.endDate)
            };
        }

        // ✅ DEBUGGING: Log de fechas formateadas para el backend
        console.log('📤 Fechas formateadas para backend:', result);

        return result;
    }

    // Validar que las fechas sean válidas para GSC
    validateDates() {
        const errors = [];

        if (!this.currentPeriod.startDate || !this.currentPeriod.endDate) {
            errors.push('You must select a primary period');
            return { isValid: false, errors };
        }

        if (this.currentPeriod.startDate >= this.currentPeriod.endDate) {
            errors.push('Start date must be before end date');
        }

        if (this.currentPeriod.startDate < this.minDate) {
            errors.push(`Start date cannot be before ${this.formatDateForDisplay(this.minDate)}`);
        }

        if (this.currentPeriod.endDate > this.maxDate) {
            errors.push(`End date cannot be after ${this.formatDateForDisplay(this.maxDate)}`);
        }

        // ✅ ARREGLO: Validar que las fechas no sean del futuro
        const today = new Date();
        if (this.currentPeriod.startDate > today) {
            errors.push('Start date cannot be in the future');
        }
        if (this.currentPeriod.endDate > today) {
            errors.push('End date cannot be in the future');
        }

        // Validar período de comparación si existe
        if (this.comparisonMode !== 'none' && this.comparisonPeriod.startDate && this.comparisonPeriod.endDate) {
            if (this.comparisonPeriod.startDate >= this.comparisonPeriod.endDate) {
                errors.push('Comparison dates are not valid');
            }

            if (this.comparisonPeriod.startDate < this.minDate || this.comparisonPeriod.endDate > this.maxDate) {
                errors.push('Comparison dates are outside the allowed range');
            }

            if (this.comparisonPeriod.startDate > today || this.comparisonPeriod.endDate > today) {
                errors.push('Comparison dates cannot be in the future');
            }
        }

        return {
            isValid: errors.length === 0,
            errors
        };
    }
}

// Función para reemplazar initMonthChips en ui-core.js
export function initDateRangeSelector() {
    window.dateSelector = new DateRangeSelector();
    return window.dateSelector;
}

// Función para obtener las fechas seleccionadas (para usar en el formulario)
export function getSelectedDates() {
    if (window.dateSelector) {
        return window.dateSelector.getFormattedDates();
    }
    return null;
}

// Función para validar fechas antes del envío
export function validateSelectedDates() {
    if (window.dateSelector) {
        return window.dateSelector.validateDates();
    }
    return { isValid: false, errors: ['Date selector not initialized'] };
}