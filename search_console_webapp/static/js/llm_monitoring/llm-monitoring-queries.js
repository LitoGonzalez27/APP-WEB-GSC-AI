/**
 * LLM Monitoring - métodos de prototipo: queries
 * Extraído verbatim de llm_monitoring.js (refactor Fase 3).
 */
Object.assign(LLMMonitoring.prototype, {

isQueryBranded(queryText) {
        const keywords = this.currentProject?.brand_keywords || [];
        if (!keywords.length || !queryText) return false;
        const normalize = s => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        const textNorm = normalize(queryText);
        for (const kw of keywords) {
            const kwNorm = normalize(kw);
            const escaped = kwNorm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            try {
                if (new RegExp('\\b' + escaped + '\\b', 'i').test(textNorm)) return true;
            } catch (e) {
                if (textNorm.includes(kwNorm)) return true;
            }
        }
        return false;
    },

async loadQueriesTable(projectId) {
        console.log(`📝 Loading queries table for project ${projectId}...`);

        try {
            const response = await fetch(`${this.baseUrl}/projects/${projectId}/queries?days=${this.globalTimeRange}${this.getReportFilterParams()}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || 'Failed to load queries');
            }

            console.log(`✅ Loaded ${result.queries.length} queries`);
            this.renderQueriesTable(result.queries);

        } catch (error) {
            console.error('❌ Error loading queries:', error);
            const container = document.getElementById('queriesTable');
            if (container) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 2rem; color: #ef4444;">
                        <i class="fas fa-exclamation-triangle" style="font-size: 2rem; opacity: 0.5; margin-bottom: 1rem;"></i>
                        <p>Error loading queries table</p>
                    </div>
                `;
            }
        }
    },

renderQueriesTable(queries) {
        const container = document.getElementById('queriesTable');
        if (!container) return;

        // Destroy existing grid
        if (this.queriesGrid) {
            this.queriesGrid.destroy();
        }

        // Si no hay queries, mostrar mensaje
        if (!queries || queries.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: #6b7280;">
                    <i class="fas fa-list-ul" style="font-size: 3rem; opacity: 0.3; margin-bottom: 1rem; display: block;"></i>
                    <p style="font-size: 1rem; font-weight: 500;">No queries found</p>
                    <p style="font-size: 0.875rem; margin-top: 0.5rem;">Run analysis to see query results</p>
                </div>
            `;
            return;
        }

        // ✨ NUEVO: Guardar queries data para acceso en acordeón
        this.queriesData = queries;

        // Formatear datos para la tabla
        const rows = queries.map((q, idx) => {
            // ✨ Botón que abre modal con análisis detallado — pill plano (brandbook: sin degradados)
            const viewDetailsBtn = gridjs.html(`
                <button
                    class="view-details-btn"
                    data-row-idx="${idx}"
                    title="View detailed analysis"
                    style="
                        background: #d9f9b8;
                        border: none;
                        border-radius: 9999px;
                        cursor: pointer;
                        padding: 0.35rem 0.9rem;
                        color: #0F172A;
                        font-size: 0.75rem;
                        font-weight: 600;
                        transition: transform 0.2s ease, box-shadow 0.2s ease;
                        white-space: nowrap;
                    "
                    onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 10px rgba(15, 23, 42, 0.15)'"
                    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'"
                >Details</button>
            `);

            return [
                viewDetailsBtn,  // ✨ NUEVO: Botón para ver detalles
                q.prompt,
                q.share_of_voice != null ? Number(q.share_of_voice) : null,
                q.avg_position != null ? Number(q.avg_position) : null,
                // Number() defensivo: la API puede devolver el SUM como string
                Number(q.total_mentions) || 0,
                q.top_domains || [],
                q.topic_cluster || null,
                q.sentiment || null
            ];
        });

        // Comparador numérico explícito: sin él Grid.js ordena "31" < "4" (alfabético).
        // OJO: debe devolver -1/0/1 — Grid.js acumula el resultado con OR bitwise (int32),
        // así que restas con decimales, Infinity o valores grandes rompen el orden.
        const numericSort = {
            compare: (a, b) => {
                const x = Number(a) || 0;
                const y = Number(b) || 0;
                return x > y ? 1 : (x < y ? -1 : 0);
            }
        };

        const clusterSort = {
            compare: (a, b) => (a || '').localeCompare(b || '')
        };

        const sentimentSort = {
            compare: (a, b) => {
                const x = (a && typeof a.score === 'number') ? a.score : -1;
                const y = (b && typeof b.score === 'number') ? b.score : -1;
                return x > y ? 1 : (x < y ? -1 : 0);
            }
        };


        // Create grid
        // Orden: Details | Prompt | SOV | Avg. Position | Mentions | Top Domains | Cluster | Sentiment
        // Anchos compactos: la suma de columnas fijas debe caber en el card sin provocar
        // scroll horizontal a nivel de página (el prompt absorbe el espacio restante).
        this.queriesGrid = new gridjs.Grid({
            columns: [
                // 110px: el pill "Details" mide ~66px y la celda lleva 20px de
                // padding izquierdo; con 80px el botón invadía la celda del prompt.
                { id: 'expand', name: '', width: '110px', sort: false },
                { id: 'prompt', name: 'Prompt' },
                {
                    id: 'sov',
                    name: 'SOV %',
                    width: '85px',
                    sort: numericSort,
                    formatter: (sov) => (sov === null || sov === undefined)
                        ? gridjs.html('<span class="lm-cell-muted">-</span>')
                        : gridjs.html(`<span class="lm-cell-strong">${Number(sov).toFixed(1)}%</span>`)
                },
                {
                    id: 'avgPosition',
                    name: 'Avg. Pos.',
                    width: '90px',
                    sort: numericSort,
                    formatter: (pos) => (pos === null || pos === undefined)
                        ? gridjs.html('<span class="lm-cell-muted">-</span>')
                        : gridjs.html(`<span class="lm-cell-strong">#${Number(pos).toFixed(1)}</span>`)
                },
                // Sin sufijo de período: el rango lo gobierna el toggle global de días
                { id: 'mentions', name: 'Mentions', width: '105px', sort: numericSort },
                {
                    id: 'topDomains',
                    name: 'Top Domains',
                    width: '100px',
                    sort: false,
                    formatter: (domains) => {
                        if (!domains || domains.length === 0) {
                            return gridjs.html('<span class="lm-cell-muted">—</span>');
                        }
                        // Un solo tooltip para la pila (data-domains), no uno por
                        // favicon: lo pinta bindDomainStackTooltips con el mismo
                        // estilo oscuro que el resto de tooltips del panel.
                        const top = domains.slice(0, 3);
                        const icons = top.map(d => this.getDomainFaviconImg(d.domain, 20)).join('');
                        const payload = this.escapeAttr(JSON.stringify(top));
                        return gridjs.html(`<span class="lm-domain-stack" data-domains="${payload}">${icons}</span>`);
                    }
                },
                {
                    id: 'cluster',
                    name: 'Cluster',
                    width: '110px',
                    sort: clusterSort,
                    formatter: (cluster) => cluster
                        ? gridjs.html(`<span class="lm-cluster-badge">${this.escapeHtml(cluster)}</span>`)
                        : gridjs.html('<span class="lm-cell-muted">—</span>')
                },
                {
                    id: 'sentiment',
                    name: 'Sentiment',
                    width: '105px',
                    sort: sentimentSort,
                    formatter: (sentiment) => {
                        const label = sentiment && sentiment.label;
                        if (!label) return gridjs.html('<span class="lm-cell-muted">-</span>');
                        const meta = CSChartTheme.sentimentMeta(label);
                        return gridjs.html(`
                            <span class="lm-sentiment-cell">
                                <span class="lm-sentiment-dot" style="background:${meta.color};"></span>
                                ${meta.label}
                            </span>
                        `);
                    }
                },
            ],
            data: rows,
            sort: true,
            search: {
                placeholder: 'Search prompts...'
            },
            pagination: {
                limit: 10,
                summary: true
            },
            // Sin `style`: Grid.js lo aplicaría como estilo en línea en cada celda
            // y ganaría a cualquier hoja, dejando el espaciado y los colores fuera
            // del sistema de diseño. El aspecto de la tabla vive en
            // brand-dashboard-overrides.css (.gridjs-th / .gridjs-td).
            className: {
                table: 'llm-queries-table'
            }
        }).render(container);

        // Use delegated click handling so "Details" keeps working after pagination/sort/search re-renders.
        this.bindDetailButtonsDelegation(container);

        // Tooltip agrupado de la columna Top Domains (delegado en document, con guard interno).
        this.bindDomainStackTooltips();
    },

buildQuickSuggestions(languageCode, brandName, industry, competitorName, mode = 'default') {
        const catalog = {
            es: {
                default: [
                    `¿Qué es ${brandName}?`,
                    `Mejores herramientas de ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Opiniones de ${brandName}`,
                    `¿Cómo funciona ${brandName}?`,
                    `Alternativas a ${brandName}`
                ],
                variation: [
                    `¿Qué es ${brandName} y cómo funciona?`,
                    `Mejores alternativas a ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `¿Vale la pena ${brandName}?`,
                    `Cómo usar ${brandName}`,
                    `Precios de ${brandName}`
                ]
            },
            it: {
                default: [
                    `Cos'è ${brandName}?`,
                    `I migliori strumenti di ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Recensioni su ${brandName}`,
                    `Come funziona ${brandName}?`,
                    `Alternative a ${brandName}`
                ],
                variation: [
                    `Cos'è ${brandName} e come funziona?`,
                    `Migliori alternative a ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} vale la pena?`,
                    `Come usare ${brandName}`,
                    `Prezzi di ${brandName}`
                ]
            },
            fr: {
                default: [
                    `Qu'est-ce que ${brandName} ?`,
                    `Meilleurs outils de ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Avis sur ${brandName}`,
                    `Comment fonctionne ${brandName} ?`,
                    `Alternatives à ${brandName}`
                ],
                variation: [
                    `Qu'est-ce que ${brandName} et comment ça marche ?`,
                    `Meilleures alternatives à ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} vaut-il le coup ?`,
                    `Comment utiliser ${brandName}`,
                    `Tarifs de ${brandName}`
                ]
            },
            de: {
                default: [
                    `Was ist ${brandName}?`,
                    `Beste ${industry}-Tools`,
                    `${brandName} vs ${competitorName}`,
                    `Bewertungen zu ${brandName}`,
                    `Wie funktioniert ${brandName}?`,
                    `Alternativen zu ${brandName}`
                ],
                variation: [
                    `Was ist ${brandName} und wie funktioniert es?`,
                    `Beste Alternativen zu ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `Lohnt sich ${brandName}?`,
                    `Wie nutzt man ${brandName}?`,
                    `${brandName} Preise`
                ]
            },
            pt: {
                default: [
                    `O que é ${brandName}?`,
                    `Melhores ferramentas de ${industry}`,
                    `${brandName} vs ${competitorName}`,
                    `Avaliações de ${brandName}`,
                    `Como funciona ${brandName}?`,
                    `Alternativas ao ${brandName}`
                ],
                variation: [
                    `O que é ${brandName} e como funciona?`,
                    `Melhores alternativas ao ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} vale a pena?`,
                    `Como usar ${brandName}`,
                    `Preços do ${brandName}`
                ]
            },
            en: {
                default: [
                    `What is ${brandName}?`,
                    `Best ${industry} tools`,
                    `${brandName} vs ${competitorName}`,
                    `${brandName} reviews`,
                    `How does ${brandName} work?`,
                    `Alternatives to ${brandName}`
                ],
                variation: [
                    `What is ${brandName} and how does it work?`,
                    `Best alternatives to ${brandName}`,
                    `${brandName} vs ${competitorName}`,
                    `Is ${brandName} worth it?`,
                    `How to use ${brandName}`,
                    `${brandName} pricing and plans`
                ]
            }
        };

        const locale = catalog[languageCode] || catalog.en;
        return mode === 'variation' ? locale.variation : locale.default;
    },

async loadQuickSuggestions(forceRefresh = false) {
        const listEl = document.getElementById('quickSuggestionsList');
        const emptyEl = document.getElementById('quickSuggestionsEmpty');
        const sectionEl = document.getElementById('quickSuggestionsSection');

        if (!listEl || !this.currentProject) {
            console.warn('[Suggestions] Missing listEl or currentProject, rendering local fallback');
            this._renderLocalFallbackSuggestions();
            return;
        }

        // Show loading
        listEl.innerHTML = `
            <div class="suggestions-loading-inline">
                <i class="fas fa-spinner fa-spin"></i>
                <span>Generating suggestions...</span>
            </div>
        `;
        if (emptyEl) emptyEl.style.display = 'none';
        if (sectionEl) sectionEl.style.display = 'block';

        // Prepare project context
        const existingPrompts = this.allPrompts || [];
        const languageCode = this.getProjectLanguageCode();
        const brandName = this.currentProject.brand_name || 'your brand';
        const industry = this.currentProject.industry || 'your industry';
        const competitorName = this.getPrimaryCompetitorName(languageCode);
        const mode = existingPrompts.length > 0 ? 'variation' : 'default';
        const cacheKey = existingPrompts.length === 0
            ? `bootstrap:${this.currentProject.id}:${languageCode}`
            : `variation:${this.currentProject.id}:${languageCode}:${existingPrompts.length}`;

        // Check cache first
        if (!forceRefresh && this.quickSuggestionsCache.has(cacheKey)) {
            this.renderQuickSuggestions(this.quickSuggestionsCache.get(cacheKey));
            return;
        }

        // Attempt to fetch AI-generated suggestions with a timeout
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 8000); // 8s timeout

            const body = existingPrompts.length === 0
                ? { existing_prompts: [], count: 6 }
                : { existing_prompts: existingPrompts.slice(0, 5).map(p => p.prompt), count: 6 };

            const response = await fetch(
                `${this.baseUrl}/projects/${this.currentProject.id}/queries/suggest-variations`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                    signal: controller.signal
                }
            );
            clearTimeout(timeoutId);

            if (response.ok) {
                const data = await response.json();
                if (data.success && Array.isArray(data.suggestions) && data.suggestions.length > 0) {
                    this.quickSuggestionsCache.set(cacheKey, data.suggestions);
                    this.renderQuickSuggestions(data.suggestions);
                    return;
                }
            }
        } catch (err) {
            // AbortError = timeout, any other = network / parse error
            console.warn('[Suggestions] API fetch failed, using local fallback:', err.name === 'AbortError' ? 'timeout' : err.message);
        }

        // Fallback: always render local suggestions so the spinner never hangs
        const localSuggestions = this.buildQuickSuggestions(languageCode, brandName, industry, competitorName, mode);
        this.quickSuggestionsCache.set(cacheKey, localSuggestions);
        this.renderQuickSuggestions(localSuggestions);
    },

_renderLocalFallbackSuggestions() {
        const listEl = document.getElementById('quickSuggestionsList');
        if (!listEl) return;
        const brandName = this.currentProject?.brand_name || 'your brand';
        const industry = this.currentProject?.industry || 'your industry';
        const languageCode = this.getProjectLanguageCode ? this.getProjectLanguageCode() : 'en';
        const competitorName = this.getPrimaryCompetitorName ? this.getPrimaryCompetitorName(languageCode) : 'competitors';
        this.renderQuickSuggestions(
            this.buildQuickSuggestions(languageCode, brandName, industry, competitorName, 'default')
        );
    },


renderQuickSuggestions(suggestions) {
        const listEl = document.getElementById('quickSuggestionsList');
        if (!listEl) return;
        
        if (!suggestions || suggestions.length === 0) {
            listEl.innerHTML = '<span class="quick-suggestions-empty">No suggestions available</span>';
            return;
        }
        
        // Filter out duplicates with existing prompts
        const existingTexts = (this.allPrompts || []).map(p => p.prompt.toLowerCase().trim());
        const uniqueSuggestions = suggestions.filter(s => 
            !existingTexts.includes(s.toLowerCase().trim())
        ).slice(0, 6);
        
        if (uniqueSuggestions.length === 0) {
            listEl.innerHTML = '<span class="quick-suggestions-empty">All suggestions already added</span>';
            return;
        }
        
        let html = '';
        // Texto completo: para elegir una sugerencia hay que poder leerla (antes
        // se cortaba a 47 caracteres). <button> para que funcione con teclado.
        uniqueSuggestions.forEach((suggestion) => {
            html += `
                <button type="button" class="suggestion-chip" onclick="window.llmMonitoring.addSuggestionToTextarea(${window.ClicandseoHtml.jsArg(suggestion)})" aria-label="Add prompt: ${this.escapeHtml(suggestion)}">
                    <span class="chip-text">${this.escapeHtml(suggestion)}</span>
                    <i class="fas fa-plus chip-add-icon" aria-hidden="true"></i>
                </button>
            `;
        });
        
        listEl.innerHTML = html;
    },

addSuggestionToTextarea(suggestion) {
        const textarea = document.getElementById('promptsInput');
        if (!textarea) return;
        
        const currentValue = textarea.value.trim();
        if (currentValue) {
            textarea.value = currentValue + '\n' + suggestion;
        } else {
            textarea.value = suggestion;
        }
        
        // Update counter
        this.updatePromptsCounter();
        
        // Remove the chip that was clicked (visual feedback)
        // The chip will be regenerated on refresh
        textarea.focus();
    },

refreshQuickSuggestions() {
        const btn = document.querySelector('.refresh-suggestions-btn');
        if (btn) {
            btn.classList.add('loading');
            setTimeout(() => btn.classList.remove('loading'), 1000);
        }
        this.loadQuickSuggestions(true);
    },

// El modal aparte «AI-Powered Prompt Suggestions» (showSuggestionsModal,
// getSuggestions, addSelectedSuggestions…) se retiró en oct-2026: duplicaba
// las sugerencias que ya trae «Add prompts» (loadQuickSuggestions: IA con
// plantillas por idioma de respaldo) y se abría encima de otro modal.

// populateQueryFilter se retiró: el filtro de prompt del Inspector
// vive ahora en la barra de filtros global (dropdown Prompts).

});
