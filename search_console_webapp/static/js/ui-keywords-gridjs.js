// static/js/ui-keywords-gridjs.js - Tabla Grid.js para Keywords del panel principal

import { formatInteger, formatPercentage, formatPercentageChange, formatPosition, formatPositionDelta, formatAbsoluteDelta, calculateAbsoluteDelta, parsePositionValue, parseIntegerValue, parseNumericValue } from './number-utils.js';

// =============================
// UI state y helpers para Keyword Filter
// =============================
const kwFilterState = {
    initialized: false,
    terms: [],
    keywordSearchTerm: '',
    urlSearchTerm: '',
    activePreset: '',
    presetContext: null,
    currentGrid: null,
    currentKeywordsData: [],
    currentAnalysisType: 'comparison'
};

const kwPresetDefinitions = {
    easyWins: {
        label: 'Easy Wins',
        description: 'High impressions, avg. position 8-15, and lower CTR than expected'
    },
    longTail: {
        label: 'Long Tail',
        description: 'Queries with 4 or more words'
    },
    aiSeasonalityAffected: {
        label: 'AI/Seasonality Affected',
        description: 'Impressions/position stable or better, but clicks drop more than 5%'
    },
    cannibalization: {
        label: 'Cannibalization',
        description: 'Same keyword ranking with 2 or more URLs'
    },
    decayRisk: {
        label: 'Decay Risk',
        description: 'Average position worsened more than 15% vs previous period'
    }
};

const kwPresetOrder = ['easyWins', 'longTail', 'aiSeasonalityAffected', 'cannibalization', 'decayRisk'];

const keywordUrlPopoverState = {
    initialized: false,
    closeTimers: new WeakMap(),
    activeCell: null
};

const kwFilterMethodLabels = {
    contains: 'Contains',
    equals: 'Exact Match',
    notContains: 'Not Contains',
    notEquals: 'Not Equal'
};

function getKwFilterMethodLabel(method) {
    return kwFilterMethodLabels[method] || method || 'Contains';
}

function clearKeywordUrlCloseTimer(cellEl) {
    if (!cellEl) return;
    const timerId = keywordUrlPopoverState.closeTimers.get(cellEl);
    if (timerId) {
        clearTimeout(timerId);
        keywordUrlPopoverState.closeTimers.delete(cellEl);
    }
}

function closeKeywordUrlPopover(cellEl) {
    if (!cellEl) return;
    const popoverEl = cellEl.querySelector('.keyword-url-popover');
    if (popoverEl) {
        popoverEl.classList.remove('is-open');
    }
    cellEl.classList.remove('is-open');

    const tdEl = cellEl.closest('.gridjs-td');
    const trEl = cellEl.closest('.gridjs-tr');
    if (tdEl) tdEl.classList.remove('keyword-url-td-open');
    if (trEl) trEl.classList.remove('keyword-url-row-open');

    if (keywordUrlPopoverState.activeCell === cellEl) {
        keywordUrlPopoverState.activeCell = null;
    }
}

function openKeywordUrlPopover(cellEl) {
    if (!cellEl) return;
    const popoverEl = cellEl.querySelector('.keyword-url-popover');
    if (!popoverEl) return;

    if (keywordUrlPopoverState.activeCell && keywordUrlPopoverState.activeCell !== cellEl) {
        closeKeywordUrlPopover(keywordUrlPopoverState.activeCell);
    }

    clearKeywordUrlCloseTimer(cellEl);
    popoverEl.classList.add('is-open');
    cellEl.classList.add('is-open');

    const tdEl = cellEl.closest('.gridjs-td');
    const trEl = cellEl.closest('.gridjs-tr');
    if (tdEl) tdEl.classList.add('keyword-url-td-open');
    if (trEl) trEl.classList.add('keyword-url-row-open');

    keywordUrlPopoverState.activeCell = cellEl;
}

function scheduleKeywordUrlPopoverClose(cellEl, delayMs = 220) {
    if (!cellEl) return;
    clearKeywordUrlCloseTimer(cellEl);
    const timerId = setTimeout(() => {
        const popoverEl = cellEl.querySelector('.keyword-url-popover');
        const isCellHovered = cellEl.matches(':hover');
        const isPopoverHovered = popoverEl ? popoverEl.matches(':hover') : false;
        if (!isCellHovered && !isPopoverHovered) {
            closeKeywordUrlPopover(cellEl);
        }
    }, delayMs);
    keywordUrlPopoverState.closeTimers.set(cellEl, timerId);
}

function ensureKeywordUrlPopoverSetup() {
    if (keywordUrlPopoverState.initialized) return;

    document.addEventListener('pointerover', (event) => {
        const cellEl = event.target.closest('.keyword-url-cell');
        if (!cellEl) return;
        openKeywordUrlPopover(cellEl);
    });

    document.addEventListener('pointerout', (event) => {
        const cellEl = event.target.closest('.keyword-url-cell');
        if (!cellEl) return;

        const nextTarget = event.relatedTarget;
        if (nextTarget && cellEl.contains(nextTarget)) return;
        scheduleKeywordUrlPopoverClose(cellEl);
    });

    document.addEventListener('scroll', () => {
        if (keywordUrlPopoverState.activeCell) {
            closeKeywordUrlPopover(keywordUrlPopoverState.activeCell);
        }
    }, true);

    keywordUrlPopoverState.initialized = true;
}

function notifyKwFilterStateChanged() {
    const detail = getKwFilterSummaryInfo();
    document.dispatchEvent(new CustomEvent('kwFilterStateChanged', { detail }));
    if (typeof window.updateCollapsibleSummary === 'function') {
        window.updateCollapsibleSummary('keywordFilter');
    }
}

function updateKwFilterMethodDescription() {
    const descEl = document.getElementById('kwFilterMethodDescription');
    const methodEl = document.getElementById('kwFilterMethod');
    if (!descEl || !methodEl) return;
    const m = methodEl.value;
    const map = {
        contains: 'Show rows where keyword contains any term',
        equals: 'Show rows where keyword exactly matches any term',
        notContains: 'Hide rows where keyword contains any term',
        notEquals: 'Hide rows where keyword exactly matches any term'
    };
    descEl.textContent = map[m] || 'Filter keywords by terms';
}

function renderKwFilterTags() {
    const container = document.getElementById('kwFilterTagsContainer');
    const countEl = document.getElementById('kwFilterCount');
    if (!container) return;

    if (countEl) countEl.textContent = kwFilterState.terms.length;

    if (kwFilterState.terms.length === 0) {
        container.innerHTML = '<div class="exclusion-empty">No exclusions yet...</div>';
        notifyKwFilterStateChanged();
        return;
    }

    container.innerHTML = kwFilterState.terms.map((term, index) => `
        <div class="exclusion-tag">
            <span class="exclusion-tag-text">${escapeHtmlLocal(term)}</span>
            <span class="exclusion-tag-remove" data-index="${index}" title="Remove">
                <i class="fas fa-times"></i>
            </span>
        </div>
    `).join('');

    notifyKwFilterStateChanged();
}

function addKwFilterTerm(raw) {
    if (!raw) return;
    const term = raw.trim().toLowerCase();
    if (!term) return;
    if (kwFilterState.terms.includes(term)) return;
    kwFilterState.terms.push(term);
    renderKwFilterTags();
}

function clearAllKwFilterTerms() {
    kwFilterState.terms = [];
    const input = document.getElementById('kwFilterTerms');
    if (input) input.value = '';
    renderKwFilterTags();
    renderMainKeywordsGridWithFilter();
}

function setMainKeywordsGridContext(grid, keywordsData, analysisType) {
    kwFilterState.currentGrid = grid || null;
    kwFilterState.currentKeywordsData = Array.isArray(keywordsData) ? keywordsData : [];
    kwFilterState.currentAnalysisType = analysisType || 'comparison';
    kwFilterState.presetContext = buildKeywordPresetContext(kwFilterState.currentKeywordsData);
}

function normalizeUrlCandidate(urlValue) {
    if (!urlValue) return '';
    if (typeof urlValue === 'string') return urlValue;
    if (typeof urlValue === 'object') {
        if (typeof urlValue.url === 'string') return urlValue.url;
        if (typeof urlValue.page === 'string') return urlValue.page;
        return '';
    }
    return String(urlValue || '');
}

function collectRowUrlsForSearch(row) {
    const seen = new Set();
    const pushUrl = (rawUrl) => {
        const normalized = normalizeUrlCandidate(rawUrl).trim().toLowerCase();
        if (normalized) seen.add(normalized);
    };

    pushUrl(row?.url);
    pushUrl(row?.page);

    if (Array.isArray(row?.top_urls)) {
        row.top_urls.forEach(pushUrl);
    }

    return Array.from(seen);
}

function normalizeUrlForCannibalization(urlValue) {
    const normalized = normalizeUrlCandidate(urlValue).trim().toLowerCase();
    if (!normalized) return '';

    const withoutHash = normalized.split('#')[0];
    const withoutQuery = withoutHash.split('?')[0];
    if (!withoutQuery) return '';

    return withoutQuery.length > 1 ? withoutQuery.replace(/\/+$/, '') : withoutQuery;
}

function collectRowUrlsForCannibalization(row) {
    const seen = new Set();
    const pushUrl = (rawUrl) => {
        const normalized = normalizeUrlForCannibalization(rawUrl);
        if (normalized) seen.add(normalized);
    };

    pushUrl(row?.url);
    pushUrl(row?.page);

    if (Array.isArray(row?.top_urls)) {
        row.top_urls.forEach(pushUrl);
    }

    return Array.from(seen);
}

function toFiniteNumber(value, fallback = 0) {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
}

function getCurrentMetric(row, key) {
    return toFiniteNumber(row?.[`${key}_m1`], 0);
}

function getPreviousMetric(row, key) {
    return toFiniteNumber(row?.[`${key}_m2`], 0);
}

function getCurrentPosition(row) {
    const position = toFiniteNumber(row?.position_m1, 0);
    return position > 0 ? position : 0;
}

function getPreviousPosition(row) {
    const position = toFiniteNumber(row?.position_m2, 0);
    return position > 0 ? position : 0;
}

function normalizeCtrToPercent(rawCtr) {
    const ctr = toFiniteNumber(rawCtr, 0);
    if (ctr <= 0) return 0;
    return ctr <= 1 ? ctr * 100 : ctr;
}

function percentile(values, ratio) {
    if (!Array.isArray(values) || values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const clampedRatio = Math.min(1, Math.max(0, ratio));
    const index = Math.floor((sorted.length - 1) * clampedRatio);
    return sorted[index] || 0;
}

function expectedCtrForPosition(position) {
    const pos = toFiniteNumber(position, 0);
    if (pos <= 0) return 0;

    if (pos <= 1) return 28;
    if (pos <= 2) return 15;
    if (pos <= 3) return 10;
    if (pos <= 4) return 7;
    if (pos <= 5) return 5.5;
    if (pos <= 6) return 4.3;
    if (pos <= 7) return 3.5;
    if (pos <= 8) return 2.9;
    if (pos <= 9) return 2.5;
    if (pos <= 10) return 2.2;
    if (pos <= 12) return 1.8;
    if (pos <= 15) return 1.4;
    if (pos <= 20) return 0.9;
    return 0.5;
}

function getKeywordText(row) {
    return String(row?.keyword || row?.query || '').trim();
}

function getKeywordWordCount(row) {
    const keywordText = getKeywordText(row);
    if (!keywordText) return 0;
    return keywordText.split(/\s+/).filter(Boolean).length;
}

function buildKeywordPresetContext(keywordsData) {
    const rows = Array.isArray(keywordsData) ? keywordsData : [];
    const impressions = rows
        .map((row) => getCurrentMetric(row, 'impressions'))
        .filter((value) => value > 0);

    const p65 = percentile(impressions, 0.65);
    const highImpressionsThreshold = Math.max(30, Math.round(p65 || 0));

    return {
        highImpressionsThreshold
    };
}

function rowMatchesKeywordPreset(row, presetId, presetContext = {}) {
    if (!row || !presetId) return true;

    const clicksCurrent = getCurrentMetric(row, 'clicks');
    const clicksPrevious = getPreviousMetric(row, 'clicks');
    const impressionsCurrent = getCurrentMetric(row, 'impressions');
    const impressionsPrevious = getPreviousMetric(row, 'impressions');
    const positionCurrent = getCurrentPosition(row);
    const positionPrevious = getPreviousPosition(row);

    switch (presetId) {
        case 'easyWins': {
            if (!(positionCurrent >= 8 && positionCurrent <= 15)) return false;
            if (impressionsCurrent < (presetContext.highImpressionsThreshold || 30)) return false;

            const ctrCurrent = normalizeCtrToPercent(row?.ctr_m1);
            const expectedCtr = expectedCtrForPosition(positionCurrent);
            return expectedCtr > 0 && ctrCurrent < (expectedCtr * 0.8);
        }

        case 'longTail':
            return getKeywordWordCount(row) >= 4;

        case 'aiSeasonalityAffected': {
            if (clicksPrevious <= 0 || impressionsPrevious <= 0 || positionPrevious <= 0) return false;
            const clicksDropRatio = (clicksCurrent - clicksPrevious) / clicksPrevious;
            const impressionsStable = impressionsCurrent >= impressionsPrevious;
            const positionStableOrBetter = positionCurrent > 0 && positionCurrent <= positionPrevious;
            return impressionsStable && positionStableOrBetter && clicksDropRatio < -0.05;
        }

        case 'cannibalization':
            if (toFiniteNumber(row?.top_urls_count, 0) >= 2) return true;
            return collectRowUrlsForCannibalization(row).length >= 2;

        case 'decayRisk': {
            if (positionPrevious <= 0 || positionCurrent <= 0) return false;
            const positionDecayRatio = (positionCurrent - positionPrevious) / positionPrevious;
            return positionDecayRatio > 0.15;
        }

        default:
            return true;
    }
}

function sortRowsByColumnDesc(rows, columnIndex) {
    if (!Array.isArray(rows)) return [];
    const idx = Number.isInteger(columnIndex) ? columnIndex : 0;
    return [...rows].sort((rowA, rowB) => parseIntegerValue(rowB?.[idx]) - parseIntegerValue(rowA?.[idx]));
}

function setupMainKeywordsSearchControls(containerEl) {
    if (!containerEl) return;
    const keywordInput = containerEl.querySelector('.keywords-text-search-input');
    const urlInput = containerEl.querySelector('.keywords-url-search-input');

    if (keywordInput) {
        if (keywordInput.value !== kwFilterState.keywordSearchTerm) {
            keywordInput.value = kwFilterState.keywordSearchTerm;
        }
        if (!keywordInput.dataset.bound) {
            let keywordDebounce = null;
            keywordInput.addEventListener('input', () => {
                if (keywordDebounce) clearTimeout(keywordDebounce);
                keywordDebounce = setTimeout(() => {
                    kwFilterState.keywordSearchTerm = String(keywordInput.value || '').trim().toLowerCase();
                    renderMainKeywordsGridWithFilter();
                }, 120);
            });
            keywordInput.dataset.bound = 'true';
        }
    }

    if (urlInput) {
        if (urlInput.value !== kwFilterState.urlSearchTerm) {
            urlInput.value = kwFilterState.urlSearchTerm;
        }
        if (!urlInput.dataset.bound) {
            let urlDebounce = null;
            urlInput.addEventListener('input', () => {
                if (urlDebounce) clearTimeout(urlDebounce);
                urlDebounce = setTimeout(() => {
                    kwFilterState.urlSearchTerm = String(urlInput.value || '').trim().toLowerCase();
                    renderMainKeywordsGridWithFilter();
                }, 120);
            });
            urlInput.dataset.bound = 'true';
        }
    }
}

function updatePresetChipActiveState(containerEl) {
    if (!containerEl) return;
    const chipButtons = containerEl.querySelectorAll('.keywords-preset-chip');
    chipButtons.forEach((chipButton) => {
        const presetId = chipButton.getAttribute('data-preset-id') || '';
        const isActive = presetId && kwFilterState.activePreset === presetId;
        chipButton.classList.toggle('is-active', isActive);
        chipButton.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
}

function setupMainKeywordsPresetControls(containerEl) {
    if (!containerEl) return;
    const chipButtons = containerEl.querySelectorAll('.keywords-preset-chip');
    if (!chipButtons.length) return;

    updatePresetChipActiveState(containerEl);

    chipButtons.forEach((chipButton) => {
        if (chipButton.dataset.bound === 'true') return;
        chipButton.addEventListener('click', () => {
            const presetId = chipButton.getAttribute('data-preset-id') || '';
            if (!presetId) return;

            kwFilterState.activePreset = kwFilterState.activePreset === presetId ? '' : presetId;
            updatePresetChipActiveState(containerEl);
            renderMainKeywordsGridWithFilter();
        });
        chipButton.dataset.bound = 'true';
    });
}

function setupScopedKeywordsSearchControls(containerEl, grid, keywordsData, analysisType, fallbackSortColumn = 0) {
    if (!containerEl || !grid) return;

    const keywordInput = containerEl.querySelector('.keywords-text-search-input');
    const urlInput = containerEl.querySelector('.keywords-url-search-input');
    if (!keywordInput || !urlInput) return;

    let keywordTerm = '';
    let urlTerm = '';

    const applyScopedFilters = () => {
        let filtered = Array.isArray(keywordsData) ? keywordsData : [];

        if (keywordTerm) {
            filtered = filtered.filter((row) => {
                const keyword = String(row?.keyword || row?.query || '').toLowerCase();
                return keyword.includes(keywordTerm);
            });
        }

        if (urlTerm) {
            filtered = filtered.filter((row) => {
                const urls = collectRowUrlsForSearch(row);
                return urls.some((url) => url.includes(urlTerm));
            });
        }

        const processed = processKeywordsDataForGrid(filtered, analysisType) || { data: [], defaultSortColumn: fallbackSortColumn };
        const safeData = sortRowsByColumnDesc(processed.data, processed.defaultSortColumn ?? fallbackSortColumn);
        grid.updateConfig({ data: () => safeData }).forceRender();
    };

    let keywordDebounce = null;
    keywordInput.addEventListener('input', () => {
        if (keywordDebounce) clearTimeout(keywordDebounce);
        keywordDebounce = setTimeout(() => {
            keywordTerm = String(keywordInput.value || '').trim().toLowerCase();
            applyScopedFilters();
        }, 120);
    });

    let urlDebounce = null;
    urlInput.addEventListener('input', () => {
        if (urlDebounce) clearTimeout(urlDebounce);
        urlDebounce = setTimeout(() => {
            urlTerm = String(urlInput.value || '').trim().toLowerCase();
            applyScopedFilters();
        }, 120);
    });
}

function renderMainKeywordsGridWithFilter() {
    const grid = kwFilterState.currentGrid;
    if (!grid || typeof grid.updateConfig !== 'function') return false;

    try {
        const filtered = applyKeywordAndSearchFilters(kwFilterState.currentKeywordsData) || [];
        const processed = processKeywordsDataForGrid(filtered, kwFilterState.currentAnalysisType) || { data: [], defaultSortColumn: 0 };
        const safeData = sortRowsByColumnDesc(processed.data, processed.defaultSortColumn);
        grid.updateConfig({ data: () => safeData }).forceRender();
        return true;
    } catch (e) {
        console.warn('⚠️ No se pudo aplicar filtro dinámico de keywords:', e);
        return false;
    }
}

function runKwFilterApplyAction() {
    const applyBtn = document.getElementById('kwFilterApplyBtn');
    const icon = applyBtn ? applyBtn.querySelector('i') : null;
    if (applyBtn) {
        applyBtn.disabled = true;
        applyBtn.classList.add('loading');
    }
    if (icon) {
        icon.classList.remove('fa-check');
        icon.classList.add('fa-spinner', 'fa-spin');
    }

    setTimeout(() => {
        renderMainKeywordsGridWithFilter();
        if (applyBtn) {
            applyBtn.disabled = false;
            applyBtn.classList.remove('loading');
        }
        if (icon) {
            icon.classList.remove('fa-spinner', 'fa-spin');
            icon.classList.add('fa-check');
        }
    }, 0);
}

function getKwFilterSummaryInfo() {
    const { method, terms } = getKeywordFilterConfig();
    const count = terms.length;
    const preview = count > 0
        ? (terms.length > 2 ? `${terms.slice(0, 2).join(', ')} +${terms.length - 2} more` : terms.join(', '))
        : '';
    return {
        count,
        method: getKwFilterMethodLabel(method),
        preview
    };
}

function ensureKwFilterUISetup() {
    if (kwFilterState.initialized) return;
    const input = document.getElementById('kwFilterTerms');
    const methodEl = document.getElementById('kwFilterMethod');
    const tagsContainer = document.getElementById('kwFilterTagsContainer');
    const clearBtn = document.getElementById('kwFilterClearBtn');
    if (!input || !methodEl || !tagsContainer) return; // UI aún no en DOM

    // Eventos de input: coma/Enter crean tag; comas pegadas se reparten
    input.addEventListener('keydown', (e) => {
        const v = input.value.trim();
        if ((e.key === ',' || e.key === 'Enter') && v) {
            e.preventDefault();
            addKwFilterTerm(v);
            input.value = '';
        }
        if (e.key === 'Backspace' && !v && kwFilterState.terms.length > 0) {
            kwFilterState.terms.pop();
            renderKwFilterTags();
        }
    });
    input.addEventListener('input', () => {
        const val = input.value;
        if (val.includes(',')) {
            const parts = val.split(',');
            const last = parts.pop();
            parts.forEach(p => addKwFilterTerm(p));
            input.value = (last || '').trim();
        }
    });

    // Cambios de método → descripción
    methodEl.addEventListener('change', () => {
        updateKwFilterMethodDescription();
        notifyKwFilterStateChanged();
    });
    updateKwFilterMethodDescription();

    // Eliminar tag por click
    tagsContainer.addEventListener('click', (e) => {
        const rm = e.target.closest('.exclusion-tag-remove');
        if (rm && rm.dataset.index !== undefined) {
            const idx = parseInt(rm.dataset.index, 10);
            if (!isNaN(idx)) {
                kwFilterState.terms.splice(idx, 1);
                renderKwFilterTags();
            }
        }
    });
    // Clear All
    if (clearBtn && !clearBtn.dataset.bound) {
        clearBtn.addEventListener('click', () => clearAllKwFilterTerms());
        clearBtn.dataset.bound = 'true';
    }

    // Apply Filter (bind único)
    const applyBtn = document.getElementById('kwFilterApplyBtn');
    if (applyBtn && !applyBtn.dataset.bound) {
        applyBtn.addEventListener('click', runKwFilterApplyAction);
        applyBtn.dataset.bound = 'true';
    }

    renderKwFilterTags();
    kwFilterState.initialized = true;
}

// =============================
// Keyword Filter (frontend)
// =============================
function getKeywordFilterConfig() {
    const methodEl = document.getElementById('kwFilterMethod');
    const method = methodEl ? methodEl.value : 'contains';
    // Usar el estado interno (tags creados por el usuario)
    const terms = kwFilterState.terms.slice();
    return { method, terms };
}

function applyKeywordFilter(keywordsData) {
    const { method, terms } = getKeywordFilterConfig();
    if (!Array.isArray(keywordsData) || terms.length === 0) return keywordsData;

    const matches = (kw) => {
        const k = (kw || '').toString().toLowerCase();
        switch (method) {
            case 'contains':
                return terms.some(t => k.includes(t));
            case 'equals':
                return terms.some(t => k === t);
            case 'notContains':
                return terms.every(t => !k.includes(t));
            case 'notEquals':
                return terms.every(t => k !== t);
            default:
                return true;
        }
    };

    // keywordsData es array de objetos { keyword, ... }
    return keywordsData.filter((row) => matches(row?.keyword || row?.query || ''));
}

function applyKeywordSearchInputFilter(keywordsData) {
    const term = String(kwFilterState.keywordSearchTerm || '').trim().toLowerCase();
    if (!Array.isArray(keywordsData) || !term) return keywordsData;

    return keywordsData.filter((row) => {
        const keyword = String(row?.keyword || row?.query || '').toLowerCase();
        return keyword.includes(term);
    });
}

function applyUrlSearchInputFilter(keywordsData) {
    const term = String(kwFilterState.urlSearchTerm || '').trim().toLowerCase();
    if (!Array.isArray(keywordsData) || !term) return keywordsData;

    return keywordsData.filter((row) => {
        const urls = collectRowUrlsForSearch(row);
        return urls.some((url) => url.includes(term));
    });
}

function applyKeywordPresetFilter(keywordsData) {
    const activePreset = String(kwFilterState.activePreset || '').trim();
    if (!Array.isArray(keywordsData) || !activePreset) return keywordsData;

    const presetContext = kwFilterState.presetContext || buildKeywordPresetContext(kwFilterState.currentKeywordsData);
    return keywordsData.filter((row) => rowMatchesKeywordPreset(row, activePreset, presetContext));
}

function applyKeywordAndSearchFilters(keywordsData) {
    const keywordFiltered = applyKeywordFilter(keywordsData);
    const presetFiltered = applyKeywordPresetFilter(keywordFiltered);
    const keywordSearchFiltered = applyKeywordSearchInputFilter(presetFiltered);
    return applyUrlSearchInputFilter(keywordSearchFiltered);
}

function renderKeywordPresetChips() {
    return `
        <div class="keywords-presets-row" role="group" aria-label="Keyword opportunities presets">
            ${kwPresetOrder.map((presetId) => {
                const preset = kwPresetDefinitions[presetId];
                if (!preset) return '';
                const isActive = kwFilterState.activePreset === presetId;
                const activeClass = isActive ? ' is-active' : '';
                const ariaPressed = isActive ? 'true' : 'false';
                return `
                    <button
                        type="button"
                        class="keywords-preset-chip${activeClass}"
                        data-preset-id="${presetId}"
                        title="${escapeForAttribute(preset.description)}"
                        aria-pressed="${ariaPressed}"
                    >
                        ${escapeHtmlLocal(preset.label)}
                    </button>
                `;
            }).join('')}
        </div>
    `;
}

/**
 * Crea y renderiza la tabla Grid.js de Keywords
 * @param {Array} keywordsData - Datos de keywords procesados
 * @param {string} analysisType - Tipo de análisis ('single' o 'comparison')
 * @param {HTMLElement} container - Contenedor donde renderizar la tabla
 * @returns {Object|null} Instancia de Grid.js o null si hay error
 */
export function createKeywordsGridTable(keywordsData, analysisType = 'comparison', container) {
    console.log('🏗️ Creating Keywords Grid.js table with:', {
        keywords: keywordsData?.length || 0,
        analysisType: analysisType
    });

    if (!container) {
        console.error('❌ No container provided for Keywords Grid.js table');
        return null;
    }

    if (!window.gridjs) {
        console.error('❌ Grid.js library not loaded');
        return null;
    }

    const isMainGrid = container && container.id === 'keywordComparisonBlock';
    const isRangeModalGrid = !!(container && typeof container.id === 'string' && container.id.startsWith('keywordModalTableContainer-'));
    const quickFiltersHost = isMainGrid ? container.querySelector('#keywordQuickFiltersHost') : null;
    const hasExternalMainControls = !!quickFiltersHost;
    const gridMountContainer = isMainGrid
        ? (container.querySelector('#keywordComparisonGridMount') || container)
        : container;
    const useInlineDualSearchControls = isRangeModalGrid || (isMainGrid && !hasExternalMainControls);
    const disableNativeSearch = isMainGrid || isRangeModalGrid;

    if (!keywordsData || keywordsData.length === 0) {
        displayNoKeywordsMessage(gridMountContainer);
        return null;
    }

    // Asegurar inicialización de UI del filtro avanzado solo en la tabla principal
    if (isMainGrid) {
        ensureKwFilterUISetup();
    }
    ensureKeywordUrlPopoverSetup();
    const sourceKeywords = Array.isArray(keywordsData) ? keywordsData : [];
    if (isMainGrid) {
        kwFilterState.presetContext = buildKeywordPresetContext(sourceKeywords);
    }
    const filteredKeywords = isMainGrid ? applyKeywordAndSearchFilters(sourceKeywords) : sourceKeywords;

    // Procesar datos para Grid.js
    const { columns, data, defaultSortColumn } = processKeywordsDataForGrid(filteredKeywords, analysisType);
    const initialSortedData = sortRowsByColumnDesc(data, defaultSortColumn);

    // Crear contenedor para la tabla con ID único y consistente
    const uniqueId = `keywords-grid-table-${Date.now()}`;
    const tableContainer = document.createElement('div');
    tableContainer.className = 'ai-overview-grid-container';
    if (isMainGrid && hasExternalMainControls) {
        quickFiltersHost.innerHTML = `
            ${renderKeywordPresetChips()}
            <div class="keywords-dual-search-row">
                <div class="gridjs-search keywords-custom-search">
                    <input type="search" class="gridjs-input keywords-text-search-input" placeholder="Search keywords..." aria-label="Search keywords">
                </div>
                <div class="gridjs-search keywords-custom-search">
                    <input type="search" class="gridjs-input keywords-url-search-input" placeholder="Search URLs..." aria-label="Search URLs">
                </div>
            </div>
        `;
        tableContainer.innerHTML = `
            <div id="${uniqueId}" class="ai-overview-grid-wrapper keywords-grid-wrapper"></div>
        `;
    } else if (isMainGrid) {
        tableContainer.innerHTML = `
            ${renderKeywordPresetChips()}
            <div class="keywords-dual-search-row">
                <div class="gridjs-search keywords-custom-search">
                    <input type="search" class="gridjs-input keywords-text-search-input" placeholder="Search keywords..." aria-label="Search keywords">
                </div>
                <div class="gridjs-search keywords-custom-search">
                    <input type="search" class="gridjs-input keywords-url-search-input" placeholder="Search URLs..." aria-label="Search URLs">
                </div>
            </div>
            <div id="${uniqueId}" class="ai-overview-grid-wrapper keywords-grid-wrapper"></div>
        `;
    } else if (useInlineDualSearchControls) {
        tableContainer.innerHTML = `
            <div class="keywords-dual-search-row">
                <div class="gridjs-search keywords-custom-search">
                    <input type="search" class="gridjs-input keywords-text-search-input" placeholder="Search keywords..." aria-label="Search keywords">
                </div>
                <div class="gridjs-search keywords-custom-search">
                    <input type="search" class="gridjs-input keywords-url-search-input" placeholder="Search URLs..." aria-label="Search URLs">
                </div>
            </div>
            <div id="${uniqueId}" class="ai-overview-grid-wrapper keywords-grid-wrapper"></div>
        `;
    } else {
        tableContainer.innerHTML = `
            <div id="${uniqueId}" class="ai-overview-grid-wrapper keywords-grid-wrapper"></div>
        `;
    }
    
    // Limpiar contenedor de la tabla y añadir nueva tabla
    gridMountContainer.innerHTML = '';
    gridMountContainer.appendChild(tableContainer);
    if (isMainGrid) {
        const mainControlsScope = hasExternalMainControls ? quickFiltersHost : tableContainer;
        setupMainKeywordsPresetControls(mainControlsScope);
        setupMainKeywordsSearchControls(mainControlsScope);
    }

    // Crear instancia de Grid.js
    const grid = new gridjs.Grid({
        columns: columns,
        data: initialSortedData,
        sort: true, // ✅ MEJORADO: Simplificar para evitar conflictos (igual que URLs)
        search: disableNativeSearch ? false : {
            enabled: true,
            placeholder: 'Search keywords...',
            selector: (cell) => (typeof cell === 'string' ? cell : '')
        },
        pagination: {
            enabled: true,
            limit: 10,
            summary: true
        },
        language: {
            search: {
                placeholder: 'Search keywords...'
            },
            pagination: {
                previous: '←',
                next: '→',
                showing: 'Showing',
                of: 'of',
                to: 'to',
                results: 'results'
            },
            noRecordsFound: 'No keywords found',
            error: 'Error loading keywords data'
        },
        resizable: true,
        fixedHeader: true,
        height: '600px',
        style: {
            table: {
                'font-size': '14px',
                'border-collapse': 'collapse'
            },
            th: {
                'background-color': 'var(--card-bg)',
                'color': 'var(--heading)',
                'border-bottom': '2px solid var(--border-color)',
                'padding': '12px 8px',
                'text-align': 'left',
                'font-weight': '600',
                'font-size': '13px',
                'white-space': 'nowrap'
            },
            td: {
                'padding': '10px 8px',
                'border-bottom': '1px solid var(--border-color)',
                'color': 'var(--text-color)',
                'vertical-align': 'middle'
            },
            header: {
                'background-color': 'var(--card-bg)',
                'border-bottom': '1px solid var(--border-color)',
                'color': 'var(--text-color)'
            },
            footer: {
                'background-color': 'var(--card-bg)',
                'border-top': '1px solid var(--border-color)',
                'color': 'var(--text-color)'
            }
        },
        className: {
            table: 'keywords-grid-table',
            th: 'keywords-grid-th',
            td: 'keywords-grid-td'
        }
    });

    try {
        const gridElement = document.getElementById(uniqueId);
        if (!gridElement) {
            console.error('❌ Grid container not found for keywords table');
            return null;
        }
        
        grid.render(gridElement);
        console.log('✅ Keywords Grid.js table rendered successfully');

        // Asociar contexto de filtros solo para la tabla principal (evita stale closures)
        if (isMainGrid) {
            setMainKeywordsGridContext(grid, keywordsData, analysisType);
        } else if (isRangeModalGrid) {
            setupScopedKeywordsSearchControls(tableContainer, grid, sourceKeywords, analysisType, defaultSortColumn);
        }
        
        // Mantener orden visual por Clicks P1 desc en la tabla principal.
        // En modales se evita este re-render extra para mejorar rendimiento.
        if (isMainGrid) {
            setTimeout(() => {
                try {
                    if (grid && grid.config && grid.config.data) {
                        grid.updateConfig({
                            sort: {
                                multiColumn: false,
                                sortColumn: defaultSortColumn,
                                sortDirection: 'desc'
                            }
                        }).forceRender();
                        console.log('🔄 Keywords: Ordenamiento por Clics P1 (desc) aplicado programáticamente');
                    }
                } catch (sortError) {
                    console.warn('⚠️ Keywords: No se pudo aplicar ordenamiento automático:', sortError);
                    const specificContainer = document.getElementById(uniqueId);
                    if (specificContainer) {
                        const clicksHeader = specificContainer.querySelector(`th:nth-child(${defaultSortColumn + 1})`);
                        if (clicksHeader) {
                            clicksHeader.click();
                            setTimeout(() => clicksHeader.click(), 50);
                        }
                    }
                }
            }, 800);
        }
        
        return grid;
    } catch (error) {
        console.error('❌ Error rendering Keywords Grid.js table:', error);
        displayErrorMessage(container);
        return null;
    }
}

/**
 * Procesa los datos de keywords para Grid.js
 * @param {Array} keywordsData - Datos de keywords
 * @param {string} analysisType - Tipo de análisis ('single' o 'comparison')
 * @returns {Object} Objeto con columns y data para Grid.js
 */
function processKeywordsDataForGrid(keywordsData, analysisType) {
    console.log('🔄 Processing keywords data for Grid.js:', { 
        count: keywordsData.length, 
        analysisType 
    });

    // Definir columnas base
    const baseColumns = [
        {
            id: 'serp',
            name: 'View SERP',
            width: '80px',
            sort: false,
            formatter: (cell, row) => {
                const keyword = row.cells[1].data; // Obtener keyword de la columna siguiente
                return gridjs.html(`
                    <button class="serp-btn" 
                            onclick="window.keywordsGrid.openSerpModal('${escapeForAttribute(keyword)}')"
                            title="View SERP for: ${escapeForAttribute(keyword)}">
                        <i class="fas fa-search"></i>
                    </button>
                `);
            }
        },
        {
            id: 'keyword',
            name: 'Keyword',
            width: '200px',
            formatter: (cell) => gridjs.html(`<span class="keyword-text">${escapeHtmlLocal(cell)}</span>`)
        },
        {
            id: 'url',
            name: 'Landing URL',
            width: '320px',
            sort: false,
            formatter: (cell) => formatKeywordUrlCell(cell)
        }
    ];

    // Definir columnas según el tipo de análisis
    let columns, dataColumns;
    
    if (analysisType === 'single') {
        columns = [
            ...baseColumns,
            { id: 'clicks_m1', name: 'Clicks', width: '100px', 
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'impressions_m1', name: 'Impressions', width: '120px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'ctr_m1', name: 'CTR (%)', width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }
            },
            { id: 'position_m1', name: 'Position', width: '100px',
                sort: true, // Usar ordenamiento numérico nativo de Grid.js
                formatter: (cell) => {
                    // Formatear para display pero pasar valor numérico para sorting
                    if (cell === null || cell === undefined || cell === 0) return '0';
                    return formatPosition(cell);
                }
            }
        ];
        
        dataColumns = ['serp', 'keyword', 'url', 'clicks_m1', 'impressions_m1', 'ctr_m1', 'position_m1'];
    } else {
        columns = [
            ...baseColumns,
            { id: 'clicks_m1', name: gridjs.html('Clicks<br>P1'), width: '100px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'clicks_m2', name: gridjs.html('Clicks<br>P2'), width: '100px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'delta_clicks_percent', name: gridjs.html('ΔClicks'), width: '100px', 
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                },
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            },
            { id: 'impressions_m1', name: gridjs.html('Impressions<br>P1'), width: '120px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'impressions_m2', name: gridjs.html('Impressions<br>P2'), width: '120px',
                sort: {
                    compare: (a, b) => parseIntegerValue(b) - parseIntegerValue(a) // Mayor a menor
                }
            },
            { id: 'delta_impressions_percent', name: gridjs.html('ΔImp.'), width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                }, 
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            },
            { id: 'ctr_m1', name: gridjs.html('CTR<br>P1 (%)'), width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }
            },
            { id: 'ctr_m2', name: gridjs.html('CTR<br>P2 (%)'), width: '100px',
                sort: {
                    compare: (a, b) => parseNumericValue(b) - parseNumericValue(a) // Mayor a menor
                }
            },
            { id: 'delta_ctr_percent', name: gridjs.html('ΔCTR'), width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaValuesImproved(a, b) // Mayor mejora a mayor pérdida
                }, 
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClass(cell)}">${cell}</span>`);
                }
            },
            { id: 'position_m1', name: gridjs.html('Position<br>P1'), width: '100px',
                sort: true, // Usar ordenamiento numérico nativo de Grid.js
                formatter: (cell) => {
                    // Formatear para display pero pasar valor numérico para sorting
                    if (cell === null || cell === undefined || cell === 0) return '0';
                    return formatPosition(cell);
                }
            },
            { id: 'position_m2', name: gridjs.html('Position<br>P2'), width: '100px',
                sort: true, // Usar ordenamiento numérico nativo de Grid.js
                formatter: (cell) => {
                    // Formatear para display pero pasar valor numérico para sorting
                    if (cell === null || cell === undefined || cell === 0) return '0';
                    return formatPosition(cell);
                }
            },
            { id: 'delta_position_absolute', name: gridjs.html('ΔPos'), width: '100px',
                sort: {
                    compare: (a, b) => compareDeltaPositionImproved(a, b) // New → negativo → 0 → positivo
                }, 
                formatter: (cell) => {
                    return gridjs.html(`<span class="${getDeltaClassPosition(cell)}">${cell}</span>`);
                }
            }
        ];
        
        dataColumns = [
            'serp', 'keyword', 'url', 'clicks_m1', 'clicks_m2', 'delta_clicks_percent',
            'impressions_m1', 'impressions_m2', 'delta_impressions_percent',
            'ctr_m1', 'ctr_m2', 'delta_ctr_percent',
            'position_m1', 'position_m2', 'delta_position_absolute'
        ];
    }

    // Procesar datos (igual que URLs)
    const data = keywordsData.map(keyword => {
        const normalizedUrls = Array.isArray(keyword.top_urls) ? keyword.top_urls.filter(Boolean) : [];
        const primaryUrl = keyword.url || keyword.page || normalizedUrls[0] || '';
        const topUrlsCountRaw = Number(keyword.top_urls_count);
        const totalUrls = Number.isFinite(topUrlsCountRaw) && topUrlsCountRaw > 0
            ? topUrlsCountRaw
            : normalizedUrls.length;

        const rowData = [
            '', // Columna SERP (será reemplazada por el formatter)
            keyword.query || keyword.keyword || '',
            {
                primary: primaryUrl,
                urls: normalizedUrls.length > 0 ? normalizedUrls : (primaryUrl ? [primaryUrl] : []),
                total: totalUrls > 0 ? totalUrls : (primaryUrl ? 1 : 0)
            }
        ];

        // Añadir datos según el tipo de análisis
        if (analysisType === 'single') {
            rowData.push(formatInteger(keyword.clicks_m1 ?? 0));
            rowData.push(formatInteger(keyword.impressions_m1 ?? 0));
            rowData.push(formatPercentage(keyword.ctr_m1));
            
            // ✅ NUEVO: Pasar valores numéricos para posiciones (0 en lugar de N/A)
            const pos1 = (keyword.position_m1 == null || isNaN(keyword.position_m1)) ? 0 : Number(keyword.position_m1);
            rowData.push(pos1);
        } else {
            // Comparison mode
            rowData.push(formatInteger(keyword.clicks_m1 ?? 0));
            rowData.push(formatInteger(keyword.clicks_m2 ?? 0));
            rowData.push(calculateAbsoluteDelta(keyword.clicks_m1 ?? 0, keyword.clicks_m2 ?? 0, 'clicks'));
            
            rowData.push(formatInteger(keyword.impressions_m1 ?? 0));
            rowData.push(formatInteger(keyword.impressions_m2 ?? 0));
            rowData.push(calculateAbsoluteDelta(keyword.impressions_m1 ?? 0, keyword.impressions_m2 ?? 0, 'impressions'));
            
            rowData.push(formatPercentage(keyword.ctr_m1));
            rowData.push(formatPercentage(keyword.ctr_m2));
            rowData.push(calculateAbsoluteDelta(keyword.ctr_m1 ?? 0, keyword.ctr_m2 ?? 0, 'ctr'));
            
            // ✅ NUEVO: Pasar valores numéricos para posiciones (0 en lugar de N/A)
            const pos1 = (keyword.position_m1 == null || isNaN(keyword.position_m1)) ? 0 : Number(keyword.position_m1);
            const pos2 = (keyword.position_m2 == null || isNaN(keyword.position_m2)) ? 0 : Number(keyword.position_m2);
            rowData.push(pos1);
            rowData.push(pos2);
            // Calcular delta usando los valores reales (0 para N/A)
            rowData.push(calculateAbsoluteDelta(pos1, pos2, 'position'));
        }

        return rowData;
    });

    console.log('✅ Keywords data processed for Grid.js:', { 
        columns: columns.length, 
        rows: data.length 
    });

    const defaultSortColumn = Math.max(0, dataColumns.indexOf('clicks_m1'));
    return { columns, data, defaultSortColumn };
}

/**
 * Muestra mensaje cuando no hay keywords
 */
function displayNoKeywordsMessage(container) {
    container.innerHTML = `
        <div class="no-aio-message">
            <i class="fas fa-search"></i>
            <h3>No Keywords Found</h3>
            <p>No keyword data available to display for the selected period.</p>
        </div>
    `;
}

/**
 * Muestra mensaje de error
 */
function displayErrorMessage(container) {
    container.innerHTML = `
        <div class="no-aio-message">
            <i class="fas fa-exclamation-triangle"></i>
            <h3>Error Loading Keywords</h3>
            <p>There was an error loading the keywords table. Please try refreshing the page.</p>
        </div>
    `;
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtmlLocal(text) {
    const safeText = String(text || '');
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return safeText.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Escapa atributos HTML para prevenir XSS
 */
function escapeForAttribute(text) {
    return String(text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function truncateMiddle(text, maxLength = 80) {
    const value = String(text || '');
    if (value.length <= maxLength) return value;
    const half = Math.floor((maxLength - 3) / 2);
    return `${value.slice(0, half)}...${value.slice(-half)}`;
}

function formatKeywordUrlCell(urlValue) {
    const cellData = (urlValue && typeof urlValue === 'object')
        ? urlValue
        : { primary: urlValue, urls: urlValue ? [urlValue] : [], total: urlValue ? 1 : 0 };

    const urls = Array.isArray(cellData.urls) ? cellData.urls.filter(Boolean) : [];
    const primaryUrl = String(cellData.primary || urls[0] || '').trim();
    const totalRaw = Number(cellData.total);
    const totalUrls = Number.isFinite(totalRaw) && totalRaw > 0 ? totalRaw : urls.length;

    if (!primaryUrl) {
        return gridjs.html('<span class="keyword-url-empty">N/A</span>');
    }

    const displayUrl = truncateMiddle(primaryUrl, 82);
    const uniqueUrls = [];
    if (primaryUrl) uniqueUrls.push(primaryUrl);
    urls.forEach((urlItem) => {
        if (urlItem && !uniqueUrls.includes(urlItem)) uniqueUrls.push(urlItem);
    });

    const extraUrls = Math.max(0, totalUrls - 1);
    const safeDisplay = escapeHtmlLocal(displayUrl);
    const isHttpUrl = /^https?:\/\//i.test(primaryUrl);
    const popoverId = `kw-url-${Math.random().toString(36).slice(2, 11)}`;

    const urlMainHtml = isHttpUrl
        ? `
            <a href="${escapeForAttribute(primaryUrl)}" class="keyword-url-link keyword-url-trigger" target="_blank" rel="noopener noreferrer">
                ${safeDisplay}
            </a>
        `
        : `
            <span class="keyword-url-text keyword-url-trigger">
                ${safeDisplay}
            </span>
        `;

    const popoverLinksHtml = uniqueUrls.length > 0
        ? uniqueUrls.map((urlItem, index) => {
            const safeHref = escapeForAttribute(urlItem);
            const safeLabel = escapeHtmlLocal(truncateMiddle(urlItem, 92));
            const badge = index === 0 ? '<span class="keyword-url-main-badge">Main</span>' : '';
            return `
                <a href="${safeHref}" class="keyword-url-popover-link" target="_blank" rel="noopener noreferrer">
                    ${badge}
                    <span>${safeLabel}</span>
                </a>
            `;
        }).join('')
        : '<span class="keyword-url-empty">No URLs available</span>';

    const extraHtml = extraUrls > 0 ? `
        <span class="keyword-url-multi-btn">
            +${extraUrls} URL(s)
        </span>
    ` : '';

    const popoverHtml = `
        <div class="keyword-url-popover" id="kw-url-popover-${escapeForAttribute(popoverId)}">
            <div class="keyword-url-popover-header">Ranking URLs (${Math.max(1, totalUrls)})</div>
            <div class="keyword-url-popover-links">
                ${popoverLinksHtml}
            </div>
        </div>
    `;

    return gridjs.html(`
        <div class="keyword-url-cell">
            ${urlMainHtml}
            ${extraHtml}
            ${popoverHtml}
        </div>
    `);
}

/**
 * Obtiene la clase CSS para deltas (igual que URLs)
 * @param {string} value - Valor del delta
 * @returns {string} - Clase CSS
 */
function getDeltaClass(value) {
    if (!value || value === '-') return '';
    
    // ✅ Identificar keywords nuevas (verde como mejoras)
    if (value === 'New' || value === 'Infinity' || (typeof value === 'string' && value.includes('New'))) {
        return 'delta-positive';
    }
    
    // ✅ Identificar keywords perdidas (rojo como empeoramientos)  
    if (value === 'Lost' || (typeof value === 'string' && value.includes('Lost'))) {
        return 'delta-negative';
    }
    
    const numValue = parseNumericValue(value);
    // Solo negro si es exactamente 0
    if (numValue === 0) return 'delta-neutral';
    // Siempre verde o rojo para cualquier cambio, sin importar magnitud
    if (numValue > 0) return 'delta-positive';
    if (numValue < 0) return 'delta-negative';
    return '';
}

/**
 * Obtiene la clase CSS para deltas de posición (lógica invertida igual que URLs)
 * @param {string} value - Valor del delta de posición
 * @returns {string} - Clase CSS
 */
function getDeltaClassPosition(value) {
    if (!value || value === '-') return '';
    
    // ✅ Identificar keywords nuevas en posiciones (verde como mejoras)
    if (value === 'New' || value === 'Infinity' || (typeof value === 'string' && value.includes('New'))) {
        return 'delta-positive';
    }
    
    // ✅ Identificar keywords perdidas en posiciones (rojo como empeoramientos)
    if (value === 'Lost' || (typeof value === 'string' && value.includes('Lost'))) {
        return 'delta-negative';
    }
    
    const numValue = parseNumericValue(value);
    // Solo negro si es exactamente 0
    if (numValue === 0) return 'delta-neutral';
    // Para posiciones: negativo = mejora (verde), positivo = empeora (rojo)
    if (numValue > 0) return 'delta-negative'; // Empeora posición = rojo
    if (numValue < 0) return 'delta-positive'; // Mejora posición = verde
    return '';
}

// ✅ ELIMINADO: parseNumericValue duplicado - ahora se usa el de number-utils.js

/**
 * Compara valores de delta para ordenamiento MEJORADO (igual que URLs)
 * Orden: Mayor mejora → menor mejora → 0 → menor pérdida → mayor pérdida
 * @param {*} a - Primer valor
 * @param {*} b - Segundo valor  
 * @returns {number} - Resultado de comparación
 */
function compareDeltaValuesImproved(a, b) {
    const valA = String(a || '');
    const valB = String(b || '');
    
    // Manejar valores especiales
    const isNewA = valA === 'New' || valA.includes('New') || valA.includes('Nuevo');
    const isNewB = valB === 'New' || valB.includes('New') || valB.includes('Nuevo');
    const isLostA = valA === 'Lost' || valA.includes('Lost') || valA.includes('Perdido');
    const isLostB = valB === 'Lost' || valB.includes('Lost') || valB.includes('Perdido');
    
    // New va al final del ordenamiento (mejor caso)
    if (isNewA && !isNewB) return 1;
    if (!isNewA && isNewB) return -1;
    if (isNewA && isNewB) return 0;
    
    // Lost va al final (peor caso, después de New)
    if (isLostA && !isLostB) return 1;
    if (!isLostA && isLostB) return -1;
    if (isLostA && isLostB) return 0;
    
    // Para valores numéricos: parsear y comparar
    const numA = parseNumericValue(valA);
    const numB = parseNumericValue(valB);
    
    // Debug logging (comentar en producción)
    if (window.debugSort) {
        console.log(`🔍 Comparando: "${valA}" (${numA}) vs "${valB}" (${numB}) → ${numB - numA}`);
    }
    
    // Ordenar de mayor a menor: +300% → +150% → +100% → 0% → -5% → -30% → -80%
    return numB - numA;
}

/**
 * Compara valores de delta de posición para ordenamiento MEJORADO (lógica invertida igual que URLs)
 * Orden: New → mejor mejora (más negativo) → 0 → peor empeoramiento (más positivo)
 * @param {*} a - Primer valor
 * @param {*} b - Segundo valor
 * @returns {number} - Resultado de comparación
 */
function compareDeltaPositionImproved(a, b) {
    const valA = String(a || '');
    const valB = String(b || '');
    
    // Manejar valores especiales
    const isNewA = valA === 'New' || valA.includes('New');
    const isNewB = valB === 'New' || valB.includes('New');
    const isLostA = valA === 'Lost' || valA.includes('Lost');
    const isLostB = valB === 'Lost' || valB.includes('Lost');
    
    // New va primero (mejor caso para posiciones)
    if (isNewA && !isNewB) return -1;
    if (!isNewA && isNewB) return 1;
    if (isNewA && isNewB) return 0;
    
    // Lost va al final
    if (isLostA && !isLostB) return 1;
    if (!isLostA && isLostB) return -1;
    if (isLostA && isLostB) return 0;
    
    // Para posiciones: negativo es mejor, positivo es peor
    // Orden: -70 → -40 → -10 → 0 → +2 → +10 → +30
    const numA = parseNumericValue(valA);
    const numB = parseNumericValue(valB);
    
    return numA - numB; // Orden ascendente: más negativo primero
}

// Exportar funciones globales para uso en onclick handlers
window.keywordsGrid = {
    openSerpModal: function(keyword) {
        console.log('🔍 Opening SERP modal for keyword:', keyword);
        // Importar dinámicamente para evitar dependencias circulares
        import('./ui-serp-modal.js').then(module => {
            module.openSerpModal(keyword);
        }).catch(error => {
            console.error('❌ Error loading SERP modal:', error);
        });
    },
    
    // Funciones de debug para el ordenamiento
    debugSort: {
        enable: () => {
            window.debugSort = true;
            console.log('🔍 Debug de ordenamiento ACTIVADO');
        },
        disable: () => {
            window.debugSort = false;
            console.log('🔍 Debug de ordenamiento DESACTIVADO');
        },
        test: (values) => {
            console.log('🧪 Probando ordenamiento de deltas...');
            const testValues = values || ['-0,39%', '-2,29%', '-23,33%', '-1,59%', '-8,93%', '-0,38%', '-1,27%', '-5,71%'];
            const parsed = testValues.map(v => ({ original: v, parsed: parseNumericValue(v) }));
            const sorted = [...parsed].sort((a, b) => compareDeltaValuesImproved(a.original, b.original));
            
            console.table(parsed);
            console.log('📊 Orden correcto (de menor pérdida a mayor pérdida):');
            sorted.forEach((item, index) => {
                console.log(`${index + 1}. ${item.original} (${item.parsed})`);
            });
            
            return sorted;
        }
    }
};

window.getKwFilterSummaryInfo = getKwFilterSummaryInfo;

console.log('📦 Keywords Grid.js module loaded');
