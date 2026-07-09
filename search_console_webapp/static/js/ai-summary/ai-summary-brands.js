/**
 * AI Summary - Brands
 * Carga de marcas, sugerencias de vinculación y CRUD de marcas.
 */

export async function loadBrands() {
    try {
        const data = await this.fetchJson(`${this.apiBase}/brands`);
        this.brands = data.brands || [];
        this.suggestions = data.suggestions || [];
        this.moduleProjects = data.projects || { manual_ai: [], ai_mode: [], llm: [] };

        this.renderBrandSelect();
        this.populateLinkSelects();
        this.renderSuggestions();

        if (this.brands.length > 0) {
            // Conservar la marca que el usuario estaba viendo (o la recién
            // creada); solo caer a la primera si ya no existe.
            const preferred = this.brands.find(b => b.id === this.currentBrandId) || this.brands[0];
            this.currentBrandId = preferred.id;
            this.elements.brandSelect.value = String(this.currentBrandId);
            await this.loadSummary();
        } else {
            this.currentBrandId = null;
            this.showSetup();
        }
    } catch (error) {
        console.error('❌ Error loading brands:', error);
        this.showSetup();
    }
}

export function renderBrandSelect() {
    const select = this.elements.brandSelect;
    if (!select) return;

    select.innerHTML = '<option value="">Select a brand...</option>';
    this.brands.forEach(brand => {
        const option = document.createElement('option');
        option.value = String(brand.id);
        option.textContent = `${brand.brand_name} — ${brand.brand_domain}`;
        select.appendChild(option);
    });
}

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
        this.currentBrandId = data.brand?.id || this.currentBrandId;
        await this.loadBrands();
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
        this.currentBrandId = data.brand?.id || this.currentBrandId;
        await this.loadBrands();
    } catch (error) {
        console.error('❌ Error creating brand:', error);
        this.showFormError(error.message);
    } finally {
        this.elements.createBrandBtn.disabled = false;
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

export function showSetup() {
    if (this.elements.brandSetupSection) {
        this.elements.brandSetupSection.style.display = 'block';
    }
    if (this.elements.summaryContent) {
        this.elements.summaryContent.style.display = 'none';
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
