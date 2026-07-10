/**
 * AI Summary - Brands
 * Listado de marcas en tarjetas (mismo patrón que LLM Visibility Monitor),
 * sugerencias de vinculación y CRUD de marcas.
 *
 * Tres vistas excluyentes: brandsView (tarjetas) → summaryContent (panel de
 * una marca, con "Back to brands") → brandSetupSection (crear/vincular).
 */

const CHANNEL_LINKS = [
    ['manual_ai_project_id', 'AI Overview'],
    ['ai_mode_project_id', 'AI Mode'],
    ['llm_project_id', 'LLMs'],
];

export async function loadBrands(options = {}) {
    try {
        const data = await this.fetchJson(`${this.apiBase}/brands`);
        this.brands = data.brands || [];
        this.suggestions = data.suggestions || [];
        this.moduleProjects = data.projects || { manual_ai: [], ai_mode: [], llm: [] };

        this.renderBrandsGrid();
        this.populateLinkSelects();
        this.renderSuggestions();

        const openId = options.openBrandId;
        if (openId && this.brands.some(b => b.id === openId)) {
            await this.openBrand(openId);
        } else if (this.brands.length > 0) {
            this.showBrandsList();
        } else {
            this.currentBrandId = null;
            this.showSetup();
        }
    } catch (error) {
        console.error('❌ Error loading brands:', error);
        this.showSetup();
    }
}

// ----------------------------------------------------------------------
// Vista 1: listado de marcas
// ----------------------------------------------------------------------

export function renderBrandsGrid() {
    const grid = this.elements.brandsGrid;
    if (!grid) return;

    grid.innerHTML = this.brands.map(brand => `
        <div class="brand-card" data-brand-id="${brand.id}" role="button" tabindex="0"
             aria-label="Open ${this.escapeHtml(brand.brand_name)} summary">
            <div class="brand-card-header">
                <img class="brand-card-logo" src="${this.getDomainLogoUrl(brand.brand_domain)}"
                     alt="" loading="lazy" onerror="this.style.display='none'">
                <div class="brand-card-identity">
                    <h3>${this.escapeHtml(brand.brand_name)}</h3>
                    <span class="brand-card-domain">${this.escapeHtml(brand.brand_domain)}</span>
                </div>
                ${brand.is_owner ? '' : '<span class="brand-card-shared">Shared</span>'}
            </div>
            <div class="brand-card-score" data-score-slot>
                <span class="brand-score-value">–</span>
                <span class="brand-score-delta"></span>
                <span class="brand-score-label">AI Visibility Score</span>
            </div>
            <div class="brand-card-channels">
                ${CHANNEL_LINKS.map(([field, label]) => `
                    <span class="brand-card-channel ${brand[field] ? 'linked' : ''}">
                        <span class="channel-dot"></span> ${label}
                    </span>
                `).join('')}
            </div>
            <div class="brand-card-footer">
                View summary <i class="fas fa-arrow-right"></i>
            </div>
        </div>
    `).join('');
}

export function showBrandsList() {
    this.currentBrandId = null;
    this.showLoading(false);
    this.hideSetup();
    if (this.elements.summaryContent) {
        this.elements.summaryContent.style.display = 'none';
    }
    if (this.elements.brandsView) {
        this.elements.brandsView.style.display = 'block';
    }
    // Los scores llegan en segundo plano y se pintan sobre las tarjetas
    this.loadBrandScores();
}

export async function loadBrandScores() {
    if (!this.brands.length) return;
    try {
        const data = await this.fetchJson(`${this.apiBase}/brands/scores`);
        this.brandScores = data.scores || {};
        this.patchBrandScores();
    } catch (error) {
        console.warn('⚠️ Brand scores unavailable:', error.message);
    }
}

export function patchBrandScores() {
    this.elements.brandsGrid?.querySelectorAll('.brand-card').forEach(card => {
        const slot = card.querySelector('[data-score-slot]');
        const info = this.brandScores?.[card.dataset.brandId];
        if (!slot || !info) return;
        slot.querySelector('.brand-score-value').textContent = info.score.toFixed(1);
        const deltaEl = slot.querySelector('.brand-score-delta');
        if (info.delta == null || Math.abs(info.delta) < 0.05) {
            deltaEl.innerHTML = '<i class="fas fa-equals"></i>';
            deltaEl.className = 'brand-score-delta delta-flat';
        } else {
            const up = info.delta > 0;
            deltaEl.innerHTML = `<i class="fas fa-arrow-${up ? 'up' : 'down'}"></i> ${up ? '+' : ''}${info.delta.toFixed(1)}`;
            deltaEl.className = `brand-score-delta ${up ? 'delta-up' : 'delta-down'}`;
        }
    });
}

export async function openBrand(brandId) {
    this.currentBrandId = brandId;
    if (this.elements.brandsView) {
        this.elements.brandsView.style.display = 'none';
    }
    await this.loadSummary();
}

// ----------------------------------------------------------------------
// Vista 2: setup / vinculación
// ----------------------------------------------------------------------

export function showSetup() {
    if (this.elements.brandsView) {
        this.elements.brandsView.style.display = 'none';
    }
    if (this.elements.summaryContent) {
        this.elements.summaryContent.style.display = 'none';
    }
    if (this.elements.brandSetupSection) {
        this.elements.brandSetupSection.style.display = 'block';
    }
    // Solo se puede "volver a las marcas" si existen
    if (this.elements.setupBackBtn) {
        this.elements.setupBackBtn.style.display = this.brands.length ? 'inline-flex' : 'none';
    }
    this.showLoading(false);
}

export function hideSetup() {
    if (this.elements.brandSetupSection) {
        this.elements.brandSetupSection.style.display = 'none';
    }
}

export function showFormError(message) {
    const el = this.elements.brandFormError;
    if (!el) return;
    el.textContent = message || '';
    el.style.display = message ? 'block' : 'none';
}

// ----------------------------------------------------------------------
// Formulario y sugerencias
// ----------------------------------------------------------------------

export function populateLinkSelects() {
    const mapping = [
        ['linkManualAI', 'manual_ai'],
        ['linkAIMode', 'ai_mode'],
        ['linkLLM', 'llm'],
    ];
    const linked = {
        manual_ai: new Set(this.brands.map(b => b.manual_ai_project_id).filter(Boolean)),
        ai_mode: new Set(this.brands.map(b => b.ai_mode_project_id).filter(Boolean)),
        llm: new Set(this.brands.map(b => b.llm_project_id).filter(Boolean)),
    };

    mapping.forEach(([elementId, module]) => {
        const select = this.elements[elementId];
        if (!select) return;
        select.innerHTML = '<option value="">— Not monitored —</option>';
        (this.moduleProjects[module] || []).forEach(project => {
            const option = document.createElement('option');
            option.value = String(project.id);
            const suffix = linked[module].has(project.id) ? ' (already linked)' : '';
            option.textContent = `${project.name} — ${project.identity || ''}${suffix}`;
            select.appendChild(option);
        });
    });
}

export function renderSuggestions() {
    const container = this.elements.suggestionsList;
    if (!container) return;

    if (!this.suggestions.length) {
        container.innerHTML = '';
        return;
    }

    const moduleLabels = {
        manual_ai: 'AI Overview',
        ai_mode: 'AI Mode',
        llm: 'LLM Monitoring',
    };

    container.innerHTML = this.suggestions.map((s, index) => `
        <div class="ai-summary-suggestion-card">
            <div class="suggestion-info">
                <strong>${this.escapeHtml(s.brand_name)} · ${this.escapeHtml(s.brand_domain)}</strong>
                <div class="suggestion-modules">
                    ${s.matched_projects.map(p =>
                        `<span class="suggestion-module-tag">${moduleLabels[p.module] || p.module}: ${this.escapeHtml(p.name)}</span>`
                    ).join('')}
                </div>
            </div>
            <button type="button" class="ai-summary-btn-primary" data-suggestion-index="${index}">
                <i class="fas fa-check"></i> Confirm link
            </button>
        </div>
    `).join('');

    container.querySelectorAll('[data-suggestion-index]').forEach(button => {
        button.addEventListener('click', () => {
            const suggestion = this.suggestions[Number(button.dataset.suggestionIndex)];
            if (suggestion) this.confirmSuggestion(suggestion, button);
        });
    });
}

export async function confirmSuggestion(suggestion, button) {
    try {
        if (button) button.disabled = true;
        const data = await this.fetchJson(`${this.apiBase}/brands`, {
            method: 'POST',
            body: JSON.stringify({
                brand_name: suggestion.brand_name,
                brand_domain: suggestion.brand_domain,
                manual_ai_project_id: suggestion.manual_ai_project_id,
                ai_mode_project_id: suggestion.ai_mode_project_id,
                llm_project_id: suggestion.llm_project_id,
            })
        });
        console.log('✅ Brand linked:', data.brand);
        await this.loadBrands({ openBrandId: data.brand?.id });
    } catch (error) {
        console.error('❌ Error confirming suggestion:', error);
        if (button) button.disabled = false;
        this.showFormError(error.message);
    }
}

export async function handleCreateBrand() {
    const brandName = this.elements.brandNameInput?.value.trim();
    const brandDomain = this.elements.brandDomainInput?.value.trim();
    const manualId = Number(this.elements.linkManualAI?.value || 0) || null;
    const aiModeId = Number(this.elements.linkAIMode?.value || 0) || null;
    const llmId = Number(this.elements.linkLLM?.value || 0) || null;

    this.showFormError('');

    if (!brandName || !brandDomain) {
        this.showFormError('Brand name and domain are required.');
        return;
    }
    if (!manualId && !aiModeId && !llmId) {
        this.showFormError('Link at least one project from any module.');
        return;
    }

    try {
        this.elements.createBrandBtn.disabled = true;
        const data = await this.fetchJson(`${this.apiBase}/brands`, {
            method: 'POST',
            body: JSON.stringify({
                brand_name: brandName,
                brand_domain: brandDomain,
                manual_ai_project_id: manualId,
                ai_mode_project_id: aiModeId,
                llm_project_id: llmId,
            })
        });
        this.elements.brandNameInput.value = '';
        this.elements.brandDomainInput.value = '';
        await this.loadBrands({ openBrandId: data.brand?.id });
    } catch (error) {
        console.error('❌ Error creating brand:', error);
        this.showFormError(error.message);
    } finally {
        this.elements.createBrandBtn.disabled = false;
    }
}

// ----------------------------------------------------------------------
// Edición de marca (nombre identificativo + vínculos)
// ----------------------------------------------------------------------

const CHANNEL_TO_MODULE = {
    ai_overview: ['manual_ai', 'manual_ai_project_id'],
    ai_mode: ['ai_mode', 'ai_mode_project_id'],
    llm: ['llm', 'llm_project_id'],
};

export function openEditModal() {
    const brand = this.getCurrentBrand();
    if (!brand?.is_owner) return;
    this.showEditError('');
    if (this.elements.editBrandNameInput) {
        this.elements.editBrandNameInput.value = brand.brand_name;
    }
    this.populateEditSelects(brand);
    if (this.elements.editBrandModal) {
        this.elements.editBrandModal.style.display = 'flex';
    }
}

export function closeEditModal() {
    if (this.elements.editBrandModal) {
        this.elements.editBrandModal.style.display = 'none';
    }
}

export function showEditError(message) {
    const el = this.elements.editBrandError;
    if (!el) return;
    el.textContent = message || '';
    el.style.display = message ? 'block' : 'none';
}

export function populateEditSelects(brand) {
    const mapping = [
        ['editLinkManualAI', 'manual_ai', 'manual_ai_project_id'],
        ['editLinkAIMode', 'ai_mode', 'ai_mode_project_id'],
        ['editLinkLLM', 'llm', 'llm_project_id'],
    ];
    mapping.forEach(([elementId, module, field]) => {
        const select = this.elements[elementId];
        if (!select) return;
        // "(linked to another brand)" = vinculado por OTRA marca distinta de esta
        const linkedElsewhere = new Set(
            this.brands.filter(b => b.id !== brand.id).map(b => b[field]).filter(Boolean)
        );
        select.innerHTML = '<option value="">— Not monitored —</option>';
        (this.moduleProjects[module] || []).forEach(project => {
            const option = document.createElement('option');
            option.value = String(project.id);
            const suffix = linkedElsewhere.has(project.id) ? ' (linked to another brand)' : '';
            option.textContent = `${project.name} — ${project.identity || ''}${suffix}`;
            select.appendChild(option);
        });
        select.value = brand[field] ? String(brand[field]) : '';
    });
}

export async function saveBrandEdits() {
    const brand = this.getCurrentBrand();
    if (!brand) return;

    const brandName = this.elements.editBrandNameInput?.value.trim();
    this.showEditError('');
    if (!brandName) {
        this.showEditError('Brand name is required.');
        return;
    }

    const payload = {
        brand_name: brandName,
        manual_ai_project_id: Number(this.elements.editLinkManualAI?.value || 0) || null,
        ai_mode_project_id: Number(this.elements.editLinkAIMode?.value || 0) || null,
        llm_project_id: Number(this.elements.editLinkLLM?.value || 0) || null,
    };
    if (!payload.manual_ai_project_id && !payload.ai_mode_project_id && !payload.llm_project_id) {
        this.showEditError('Link at least one project.');
        return;
    }

    try {
        this.elements.editBrandSaveBtn.disabled = true;
        await this.fetchJson(`${this.apiBase}/brands/${brand.id}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
        this.closeEditModal();
        await this.loadBrands({ openBrandId: brand.id });
    } catch (error) {
        console.error('❌ Error updating brand:', error);
        this.showEditError(error.message);
    } finally {
        this.elements.editBrandSaveBtn.disabled = false;
    }
}

// ----------------------------------------------------------------------
// Quick-link: vincular un canal desde su tarjeta cuando existe un
// proyecto propio cuyo dominio coincide con el de la marca
// ----------------------------------------------------------------------

export function findLinkableProject(channel) {
    const brand = this.getCurrentBrand();
    const [module, field] = CHANNEL_TO_MODULE[channel] || [];
    if (!brand?.is_owner || !module || brand[field]) return null;

    const normalize = value => (value || '').toLowerCase()
        .replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '');
    const slug = value => (value || '').toLowerCase().replace(/[^a-z0-9]/g, '');

    const brandDomain = normalize(brand.brand_domain);
    const domainSlug = slug(brandDomain.split('.')[0]);
    const linkedElsewhere = new Set(this.brands.map(b => b[field]).filter(Boolean));

    return (this.moduleProjects[module] || []).find(project => {
        if (linkedElsewhere.has(project.id)) return false;
        if (module === 'ai_mode') {
            // AI Mode guarda un brand_name libre: igualdad de slug con longitud mínima
            const nameSlug = slug((project.identity || '').split('.')[0]);
            return nameSlug.length >= 4 && nameSlug === domainSlug;
        }
        return normalize(project.identity) === brandDomain;
    }) || null;
}

export async function quickLinkChannel(channel, projectId) {
    const brand = this.getCurrentBrand();
    const field = CHANNEL_TO_MODULE[channel]?.[1];
    if (!brand?.is_owner || !field || !projectId) return;
    try {
        await this.fetchJson(`${this.apiBase}/brands/${brand.id}`, {
            method: 'PUT',
            body: JSON.stringify({ [field]: projectId }),
        });
        await this.loadBrands({ openBrandId: brand.id });
    } catch (error) {
        console.error('❌ Error linking project:', error);
        alert(error.message);
    }
}

export async function handleDeleteBrand() {
    const brand = this.getCurrentBrand();
    if (!brand) return;
    if (!confirm(`Unlink brand "${brand.brand_name}"? The linked projects are not deleted.`)) {
        return;
    }
    try {
        await this.fetchJson(`${this.apiBase}/brands/${brand.id}`, { method: 'DELETE' });
        this.currentBrandId = null;
        await this.loadBrands();
    } catch (error) {
        console.error('❌ Error deleting brand:', error);
        alert(error.message);
    }
}
