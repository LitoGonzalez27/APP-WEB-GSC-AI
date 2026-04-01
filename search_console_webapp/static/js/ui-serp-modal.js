// ui-serp-modal.js — Código optimizado sin CSS inline (usa styles/serp-and-table.css)

import { MobileModalManager, isMobileDevice } from './utils.js';

// Instancia global del gestor de modal robusto
let serpModalManager = null;

// --- Toast helper for SERP modal — Clicandseo brandbook ---
function _serpShowToast(message, type, duration) {
  type = type || 'info';
  duration = duration || 5000;
  const borderColors = { success: '#3CB371', error: '#E05252', warning: '#E05252', info: '#0F172A' };
  const toast = document.createElement('div');
  toast.setAttribute('role', 'alert');
  toast.style.cssText =
    "position:fixed;top:88px;right:18px;padding:14px 16px;border-radius:20px;color:#0F172A;" +
    "font-family:'Inter Tight',-apple-system,BlinkMacSystemFont,sans-serif;" +
    "font-size:0.875rem;line-height:1.6;font-weight:500;z-index:10000;" +
    "transition:all 0.3s cubic-bezier(0.2,0.8,0.2,1);" +
    "box-shadow:0 2px 4px rgba(15,23,42,0.04),0 8px 24px rgba(15,23,42,0.08);" +
    "background:#FFFFFF;border:1px solid #E2E8F0;" +
    "border-left:4px solid " + (borderColors[type] || borderColors.info) + ";" +
    "max-width:420px;word-wrap:break-word;";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, duration);
}
// Expose globally for inline onclick handlers
window._serpShowToast = _serpShowToast;

// --- Funciones auxiliares ---
function escapeHtml(unsafe) {
  if (typeof unsafe !== 'string') return '';
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function extractDomainJS(url) {
  if (!url) return '';
  try {
    if (!/^https?:\/\//.test(url)) {
      url = 'https://' + url;
    }
    const u = new URL(url);
    return u.hostname.replace(/^www\./, '');
  } catch {
    const simpleDomain = url.replace(/^https?:\/\//, '').replace(/^www\./, '');
    return simpleDomain.split('/')[0];
  }
}

function normalizeSearchConsoleUrlJS(scUrl) {
  if (!scUrl) return '';
  return scUrl.startsWith('sc-domain:') ? scUrl.split(':')[1] : extractDomainJS(scUrl);
}

function urlsMatchJS(serpUrl, scPropertyUrl) {
  if (!serpUrl || !scPropertyUrl) return false;
  const serpDomain = extractDomainJS(serpUrl);
  const scMainDomain = normalizeSearchConsoleUrlJS(scPropertyUrl);
  return Boolean(
    serpDomain &&
    scMainDomain &&
    (serpDomain === scMainDomain || serpDomain.endsWith(`.${scMainDomain}`))
  );
}

// ✅ FUNCIÓN CORREGIDA: getSelectedCountry para SERP
function getSelectedCountry() {
    const countrySelect = document.getElementById('countrySelect');
    
    // ✅ NUEVA LÓGICA: Retornar exactamente lo que el usuario seleccionó
    // Si seleccionó "All countries" (value=""), retornamos vacío para activar detección dinámica
    if (countrySelect && countrySelect.value === '') {
        console.log('🌍 User selected "All countries" - SERP will dynamically use the country with more clicks');
        return '';
    }
    
    if (countrySelect && countrySelect.value) {
        console.log(`🎯 User selected specific country for SERP: ${countrySelect.value}`);
        return countrySelect.value;
    }
    
    // Fallback si no hay country select disponible
    console.log('🔄 No country selector available - SERP will use dynamic detection');
    return '';
}

// ✅ FUNCIÓN CORREGIDA: fetchSerpPosition
async function fetchSerpPosition(keyword, siteUrl) {
    const selectedCountry = getSelectedCountry(); // Puede ser vacío para activar detección dinámica
    const currentSiteUrl = siteUrl || document.getElementById('siteUrlSelect')?.value || '';
    
    const params = new URLSearchParams({
        keyword: keyword,
        site_url: currentSiteUrl
    });
    
    // Solo añadir country si hay uno específico seleccionado
    if (selectedCountry) {
        params.set('country', selectedCountry);
    }
    
    console.log(`🔍 SERP Position API: keyword="${keyword}", country="${selectedCountry || 'DYNAMIC'}", site="${currentSiteUrl}"`);
    const response = await fetch(`/api/serp/position?${params}`);
    return response.json();
}

// ✅ FUNCIÓN CORREGIDA: fetchSerpData
async function fetchSerpData(keyword) {
    const selectedCountry = getSelectedCountry(); // Puede ser vacío para activar detección dinámica
    const currentSiteUrl = document.getElementById('siteUrlSelect')?.value || '';
    
    const params = new URLSearchParams({
        keyword: keyword,
        site_url: currentSiteUrl
    });
    
    // Solo añadir country si hay uno específico seleccionado
    if (selectedCountry) {
        params.set('country', selectedCountry);
    }
    
    console.log(`🔍 SERP Data API: keyword="${keyword}", country="${selectedCountry || 'DYNAMIC'}", site="${currentSiteUrl}"`);
    const response = await fetch(`/api/serp?${params}`);
    return response.json();
}

// ✅ FUNCIÓN CORREGIDA: fetchSerpScreenshot
async function fetchSerpScreenshot(keyword, siteUrl) {
    const selectedCountry = getSelectedCountry(); // Puede ser vacío para activar detección dinámica
    const currentSiteUrl = siteUrl || document.getElementById('siteUrlSelect')?.value || '';
    
    const params = new URLSearchParams({
        keyword: keyword,
        site_url: currentSiteUrl
    });
    
    // Solo añadir country si hay uno específico seleccionado
    if (selectedCountry) {
        params.set('country', selectedCountry);
    }
    
    console.log(`📸 SERP Screenshot API: keyword="${keyword}", country="${selectedCountry || 'DYNAMIC'}", site="${currentSiteUrl}"`);
    const response = await fetch(`/api/serp/screenshot?${params}`);
    return response;
}


// --- Lógica del Modal ---
export function openSerpModal(keyword, userSpecificUrl) {
  const modal = document.getElementById('serpModal');
  if (!modal) {
    console.error('Missing #serpModal element in the DOM.');
    _serpShowToast('Error: The SERP modal component is not available.', 'error');
    return;
  }

  const siteUrlElement = document.querySelector('select[name="site_url"]');
  const siteUrlScProperty = siteUrlElement ? siteUrlElement.value : '';
  if (!siteUrlScProperty) {
    _serpShowToast('Please select a Search Console property first.', 'warning');
    return;
  }

  // 🆕 Check if we have AI analysis data for this keyword
  const keywordResult = _findKeywordResult(keyword);
  const hasAIOData = keywordResult?.ai_analysis?.has_ai_overview || false;

  const kwSpan = modal.querySelector('#serpKeyword');
  const modalBody = modal.querySelector('.modal-body');
  kwSpan.textContent = keyword;
  modalBody.innerHTML = '';

  const container = document.createElement('div');
  container.innerHTML = `
    <div class="serp-tabs">
      <button class="serp-tab active serp-tab-active-dark" data-tab="quick" aria-selected="true">Quick View</button>
      ${hasAIOData ? '<button class="serp-tab" data-tab="aio-preview" aria-selected="false"><i class="fas fa-robot" style="margin-right:4px;"></i>AI Overview</button>' : ''}
      <button class="serp-tab" data-tab="screenshot" aria-selected="false">Screenshot SERP</button>
    </div>
    <div class="serp-content">
      <div id="quick-view" class="tab-content active" role="tabpanel">
        <div class="serp-spinner"></div>
        <p>Loading quick view...</p>
      </div>
      ${hasAIOData ? '<div id="aio-preview-view" class="tab-content" role="tabpanel" style="display:none;"><div class="serp-spinner"></div><p>Loading AI Overview...</p></div>' : ''}
      <div id="screenshot-view" class="tab-content" role="tabpanel" style="display:none;">
        <div class="screenshot-info">
          <p>The screenshot may take between 5 and 15 seconds to generate.</p>
          <button class="btn btn-primary load-screenshot">
            <i class="fas fa-camera"></i> Load Screenshot
          </button>
        </div>
      </div>
    </div>
  `;
  modalBody.appendChild(container);

  const tabs = container.querySelectorAll('.serp-tab');
  const tabContents = container.querySelectorAll('.tab-content');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tabContents.forEach(tc => (tc.style.display = 'none'));
      tab.classList.add('active');
      tabs.forEach(t => t.classList.remove('serp-tab-active-dark'));
      tab.classList.add('serp-tab-active-dark');
      const tabName = tab.dataset.tab;
      const targetId = tabName === 'quick' ? 'quick-view' : (tabName === 'aio-preview' ? 'aio-preview-view' : 'screenshot-view');
      document.getElementById(targetId).style.display = 'block';
    });
  });

  // MODIFICADO: Usar las nuevas funciones que obtienen el país
  loadQuickView(keyword, userSpecificUrl, siteUrlScProperty);
  container.querySelector('.load-screenshot').addEventListener('click', () => loadScreenshot(keyword, userSpecificUrl, siteUrlScProperty));

  // 🆕 If AIO data exists, render the preview tab content
  if (hasAIOData && keywordResult) {
    _renderAIOPreviewTab(keywordResult);
  }

  modal.classList.add('show');
  
  // Inicializar gestor robusto para móviles
  if (!serpModalManager) {
    serpModalManager = new MobileModalManager('serpModal', {
      removeFromDOM: false, // No remover del DOM, solo ocultar
      forceClose: true
    });
  }
  
  // Improve click detection to close
  const closeHandler = (e) => {
    const modal = document.getElementById('serpModal');
    if (
      e.target.matches('#serpModal .close-btn') ||
      e.target === modal ||
      e.target.matches('.modal-backdrop')
    ) {
      closeSerpModal();
    }
  };
  
  // Remover listener previo y agregar nuevo
  document.removeEventListener('click', closeHandler);
  document.addEventListener('click', closeHandler);
  
  // Handler para tecla Escape
  const escapeHandler = (e) => {
    if (e.key === 'Escape') {
      closeSerpModal();
    }
  };
  
  document.addEventListener('keydown', escapeHandler);
  
  // Almacenar handlers para limpieza posterior
  modal.setAttribute('data-handlers-attached', 'true');
}

function closeSerpModal() {
  console.log('🚪 Closing SERP modal with robust system');
  
  if (serpModalManager) {
    // Usar el sistema robusto de cierre
    serpModalManager.close();
  } else {
    // Fallback to simple close if no manager
    console.log('⚠️ Robust manager not available, using simple close');
    const modal = document.getElementById('serpModal');
    if (modal) {
      modal.classList.remove('show');
      
      // Aplicar optimizaciones móviles directas si es necesario
      if (isMobileDevice()) {
        modal.style.transition = 'none';
        modal.style.opacity = '0';
        modal.style.visibility = 'hidden';
        modal.style.pointerEvents = 'none';
      }
    }
  }
  
  // Limpiar event listeners
  const modal = document.getElementById('serpModal');
  if (modal && modal.getAttribute('data-handlers-attached')) {
    document.removeEventListener('click', closeSerpModal);
    document.removeEventListener('keydown', closeSerpModal);
    modal.removeAttribute('data-handlers-attached');
  }
  
  // Limpiar body
  document.body.classList.remove('modal-open');
  document.body.style.overflow = '';
}

async function loadQuickView(keyword, userSpecificUrl, siteUrlScProperty) {
  const quickView = document.getElementById('quick-view');
  quickView.innerHTML = '<div class="serp-spinner"></div><p>Fetching position data...</p>';

  try {
    // MODIFICADO: Llamadas a las nuevas funciones
    const posData = await fetchSerpPosition(keyword, siteUrlScProperty);
    if (posData.error) throw new Error(posData.error);

    const serpData = await fetchSerpData(keyword);
    if (serpData.error) throw new Error(serpData.error);


    const domain = posData.searched_domain_normalized || extractDomainJS(siteUrlScProperty);
    let positionHtml = '';
    if (posData.found && posData.result) {
      positionHtml = `
        <div class="position-highlight success">
          <i class="fas fa-check-circle"></i>
          <strong>Found!</strong> Your domain (<strong>${escapeHtml(domain)}</strong>) at position ${posData.position}.
        </div>
        <div class="result-preview">
          <h5><a href="${escapeHtml(posData.result.link)}" target="_blank">${escapeHtml(posData.result.title)}</a></h5>
          <cite>${escapeHtml(posData.result.displayed_link || posData.result.link)}</cite>
          <p>${escapeHtml(posData.result.snippet)}</p>
        </div>
      `;
    } else {
      positionHtml = `
        <div class="position-highlight warning">
          <i class="fas fa-exclamation-triangle"></i>
          Your domain (<strong>${escapeHtml(domain)}</strong>) does not appear in the first ${posData.total_organic_results} results.
        </div>
      `;
    }

    quickView.innerHTML = `
      <div class="serp-summary">
        <h4>Results for: "${escapeHtml(keyword)}"</h4>
        <div class="domain-info">
          <small>Analysis for: <strong>${escapeHtml(domain)}</strong></small>
        </div>
        ${positionHtml}
      </div>
      <div class="serp-results-container">
        <h5>Top ${serpData.organic_results.length} Results:</h5>
        ${serpData.organic_results.length
          ? `<ol class="serp-list">
              ${serpData.organic_results.map((res, i) => `
                <li class="${urlsMatchJS(res.link, siteUrlScProperty) ? 'highlighted-result' : ''}">
                  <span class="position-badge">${i+1}</span>
                  <strong><a href="${escapeHtml(res.link)}" target="_blank">${escapeHtml(res.title)}</a></strong>
                  <cite>${escapeHtml(res.displayed_link || res.link)}</cite>
                  ${res.snippet ? `<small>${escapeHtml(res.snippet)}</small>` : ''}
                </li>
              `).join('')}
            </ol>`
          : '<p>No results found.</p>'}
      </div>
      ${serpData.ads.length
        ? `<div class="serp-ads-container"><h5>Ads:</h5><ul>
            ${serpData.ads.slice(0,3).map(ad => `
              <li>
                <span class="ad-badge">Ad</span>
                <a href="${escapeHtml(ad.link)}">${escapeHtml(ad.title)}</a>
                <cite>${escapeHtml(ad.displayed_link||ad.link)}</cite>
              </li>
            `).join('')}
          </ul></div>`
        : ''}
    `;
  } catch (err) {
    quickView.innerHTML = `<div class="alert alert-danger">${escapeHtml(err.message)}</div>`;
  }
}

// ✅ FUNCIÓN CORREGIDA: loadScreenshot con manejo de errores mejorado
async function loadScreenshot(keyword, userSpecificUrl, siteUrlScProperty) {
  const screenshotView = document.getElementById('screenshot-view');
  screenshotView.innerHTML = `
    <div class="screenshot-loading">
      <div class="serp-spinner"></div>
      <p>Generating screenshot...</p>
    </div>
  `;

  // ✅ NUEVO: Función helper para mostrar error
  const showError = (errorMessage) => {
    screenshotView.innerHTML = `
      <div class="alert alert-danger">
        <h5>Error generating screenshot</h5>
        <p>${escapeHtml(errorMessage)}</p>
        <button class="btn btn-primary retry-screenshot">Retry</button>
      </div>
    `;
    screenshotView.querySelector('.retry-screenshot')
      .addEventListener('click', () => loadScreenshot(keyword, userSpecificUrl, siteUrlScProperty));
  };

  try {
    const img = document.createElement('img');
    img.classList.add('serp-screenshot');
    
    // ✅ DEFINIR HANDLERS ANTES DE USAR
    img.onload = () => {
      screenshotView.innerHTML = '';
      const controls = document.createElement('div');
      controls.className = 'screenshot-controls';
      controls.innerHTML = `
        <button class="btn btn-sm btn-outline-secondary" onclick="window.open('https://www.google.com/search?q=${encodeURIComponent(keyword)}', '_blank')">
          <i class="fas fa-external-link-alt"></i> Open in Google
        </button>
        <button class="btn btn-sm btn-outline-info refresh-screenshot">
          <i class="fas fa-sync-alt"></i> Refresh
        </button>
      `;
      screenshotView.appendChild(controls);
      screenshotView.appendChild(img);
      img.classList.add('visible');

      controls.querySelector('.refresh-screenshot')
        .addEventListener('click', () => loadScreenshot(keyword, userSpecificUrl, siteUrlScProperty));
      img.addEventListener('click', () => img.classList.toggle('zoomed'));
    };

    // ✅ DEFINIR HANDLER DE ERROR CORRECTAMENTE
    img.onerror = () => {
      showError('Unknown error loading image.');
    };

    // ✅ LLAMADA A LA API CON MANEJO DE ERRORES MEJORADO
    const response = await fetchSerpScreenshot(keyword, siteUrlScProperty);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: "Unknown server error" }));
      showError(errorData.error || `Error ${response.status}: ${response.statusText}`);
      return;
    }
    
    const blob = await response.blob();
    
    // ✅ VERIFICAR QUE EL BLOB ES VÁLIDO
    if (!blob || blob.size === 0) {
      showError('Server returned empty image.');
      return;
    }

    img.src = URL.createObjectURL(blob);
    img.alt = `Screenshot of SERP for ${keyword}`;

  } catch (error) {
    console.error('Error in loadScreenshot:', error);
    showError(`Network error: ${error.message || 'Could not connect to server.'}`);
  }
}

// 🆕 Find keyword result from stored AI analysis data
function _findKeywordResult(keyword) {
  const results = window._aioKeywordResults;
  if (!results || !Array.isArray(results)) return null;
  return results.find(r => r.keyword === keyword) || null;
}

// 🆕 Classify a reference as user, competitor, or other
function _classifyRef(refLink, refSource, siteUrl, competitorDomains) {
  const normalizedRef = (refLink + ' ' + refSource).toLowerCase();

  // Check user domain
  if (siteUrl) {
    const normalizedSite = siteUrl.toLowerCase().replace(/^www\./, '');
    if (normalizedRef.includes(normalizedSite)) return { type: 'user', label: 'You', color: '#28a745', icon: 'fa-check-circle' };
  }

  // Check competitor domains
  if (competitorDomains && competitorDomains.length > 0) {
    for (const comp of competitorDomains) {
      const normComp = comp.toLowerCase().replace(/^www\./, '');
      if (normalizedRef.includes(normComp)) {
        const shortName = comp.replace(/^www\./, '');
        return { type: 'competitor', label: shortName, color: '#fd7e14', icon: 'fa-crosshairs' };
      }
    }
  }

  return { type: 'other', label: '', color: '#6c757d', icon: 'fa-external-link-alt' };
}

// 🆕 Render the AI Overview preview tab content
function _renderAIOPreviewTab(result) {
  const container = document.getElementById('aio-preview-view');
  if (!container) return;

  const aiAnalysis = result.ai_analysis || {};
  const debugInfo = aiAnalysis.debug_info || {};
  const competitorDomains = window._aioCompetitorDomains || [];

  const contentPreview = debugInfo.aio_content_preview || '';
  const references = debugInfo.references_found || [];
  const siteUrl = debugInfo.site_url_normalized || '';
  const serpPosition = debugInfo.aio_serp_position || 'unknown';
  const totalBlocks = debugInfo.total_text_blocks || 0;
  const isDomainSource = aiAnalysis.domain_is_ai_source || false;
  const domainPos = aiAnalysis.domain_ai_source_position;
  const aiElements = Array.isArray(aiAnalysis.ai_overview_detected) ? aiAnalysis.ai_overview_detected : [];

  let html = '';

  // --- Domain status banner ---
  const keyword = result.keyword || '';
  const safeKeyword = keyword.replace(/'/g, "\\'").replace(/"/g, '&quot;');

  html += `
    <div class="saio-status-banner ${isDomainSource ? 'saio-status-banner--cited' : 'saio-status-banner--not-cited'}">
      <i class="fas fa-${isDomainSource ? 'check-circle' : 'times-circle'}"></i>
      <span>
        ${isDomainSource ? `Your domain appears at position #${domainPos} in this AI Overview` : 'Your domain is NOT cited in this AI Overview'}
      </span>
    </div>
  `;

  // --- AI Recommendations CTA button (centered) ---
  const ctaText = isDomainSource
    ? 'Get recommendations to improve your position'
    : 'Get recommendations to appear in AI Overview';
  html += `
    <div class="saio-cta-wrapper">
      <button class="saio-recommendations-cta" onclick="if(window.aiOverviewGrid && window.aiOverviewGrid.openRecommendationsModal) { window.aiOverviewGrid.openRecommendationsModal('${safeKeyword}'); } else { if(window._serpShowToast){window._serpShowToast('AI Recommendations not available. Run the AI Overview analysis first.','warning');}else{console.warn('AI Recommendations not available.');} }">
        <i class="fas fa-lightbulb"></i>
        <span>${ctaText}</span>
        <i class="fas fa-arrow-right saio-cta-arrow"></i>
      </button>
    </div>
  `;

  // --- Full AI Overview content (with line breaks preserved) ---
  if (contentPreview) {
    // Escape HTML then convert newlines to <br> for proper rendering
    const formattedContent = escapeHtml(contentPreview).replace(/\n/g, '<br>');
    html += `
      <div class="saio-content-block">
        <div class="saio-section-label">
          AI Overview Content
          <span class="saio-label-meta">(${totalBlocks} block${totalBlocks !== 1 ? 's' : ''})</span>
        </div>
        <div class="saio-content-preview">
          ${formattedContent}
        </div>
      </div>
    `;
  }

  // --- Cited sources + Position mockup (side by side) ---
  if (references.length > 0) {
    // Cited sources list — clickable URLs ordered by mention
    const sourceItems = references.map((ref, i) => {
      const refLink = ref.link || '';
      const refSource = ref.source || '';
      const refTitle = ref.title || refSource || refLink;
      const cls = _classifyRef(refLink, refSource, siteUrl, competitorDomains);

      const pos = i + 1;
      let displayDomain = refSource || '';
      if (!displayDomain && refLink) {
        try { displayDomain = new URL(refLink).hostname; } catch (e) { displayDomain = refLink; }
      }

      const typeClass = cls.type === 'user' ? 'saio-source--user' : (cls.type === 'competitor' ? 'saio-source--competitor' : '');
      const displayTitle = refTitle.length > 55 ? refTitle.substring(0, 55) + '...' : refTitle;

      // Wrap in <a> if we have a valid link
      const isClickable = refLink && (refLink.startsWith('http://') || refLink.startsWith('https://'));
      const openTag = isClickable
        ? `<a href="${escapeHtml(refLink)}" target="_blank" rel="noopener noreferrer" class="saio-source-item saio-source-item--link ${typeClass}" title="${escapeHtml(refLink)}">`
        : `<div class="saio-source-item ${typeClass}">`;
      const closeTag = isClickable ? '</a>' : '</div>';

      return `
        ${openTag}
          <div class="saio-source-pos ${cls.type === 'user' ? 'saio-source-pos--user' : (cls.type === 'competitor' ? 'saio-source-pos--competitor' : '')}">${pos}</div>
          <div class="saio-source-info">
            <div class="saio-source-title">${escapeHtml(displayTitle)}</div>
            <div class="saio-source-domain">
              ${isClickable ? '<i class="fas fa-external-link-alt saio-source-linkicon"></i>' : ''}
              ${escapeHtml(displayDomain)}
            </div>
          </div>
          ${cls.type === 'user'
            ? '<span class="saio-source-tag saio-source-tag--user">You</span>'
            : cls.type === 'competitor'
              ? '<span class="saio-source-tag saio-source-tag--competitor">Competitor</span>'
              : ''
          }
        ${closeTag}
      `;
    }).join('');

    // Position mini-mockup
    const maxShow = Math.min(references.length, 8);
    const slotsHTML = Array.from({ length: maxShow }, (_, i) => {
      const ref = references[i];
      const refLink = ref.link || '';
      const refSource = ref.source || '';
      const cls = _classifyRef(refLink, refSource, siteUrl, competitorDomains);
      let displayName = refSource || '';
      if (!displayName && refLink) {
        try { displayName = new URL(refLink).hostname.replace(/^www\./, ''); } catch (e) { displayName = refLink; }
      }
      if (displayName.length > 18) displayName = displayName.substring(0, 16) + '...';

      const slotClass = cls.type === 'user' ? 'saio-slot--user' : (cls.type === 'competitor' ? 'saio-slot--competitor' : 'saio-slot--other');
      return `<div class="saio-slot ${slotClass}">
        <span class="saio-slot-num">${i+1}</span>
        ${escapeHtml(displayName)}
      </div>`;
    }).join('');

    const extraCount = references.length - maxShow;
    const serpPosBadge = serpPosition !== 'unknown'
      ? `<span class="saio-pos-badge">AIO pos: ${escapeHtml(String(serpPosition))}</span>`
      : '';

    html += `
      <div class="saio-sources-grid">
        <div>
          <div class="saio-section-label">
            Cited Sources <span class="saio-label-meta">(${references.length})</span>
          </div>
          <div class="saio-sources-list">
            ${sourceItems}
          </div>
        </div>
        <div>
          <div class="saio-section-label">
            Source Ranking ${serpPosBadge}
          </div>
          <div class="saio-ranking-box">
            <div class="saio-ranking-slots">
              ${slotsHTML}
            </div>
            ${extraCount > 0 ? `<div class="saio-ranking-more">+${extraCount} more</div>` : ''}
          </div>
          <div class="saio-legend">
            <span class="saio-legend-item saio-legend-item--user"><i class="fas fa-circle"></i> You</span>
            <span class="saio-legend-item saio-legend-item--competitor"><i class="fas fa-circle"></i> Competitor</span>
            <span class="saio-legend-item saio-legend-item--other"><i class="fas fa-circle"></i> Other</span>
          </div>
        </div>
      </div>
    `;
  }

  // --- Rich Snippets detected — removed per design decision ---

  // Wrap everything
  container.innerHTML = `
    <div class="saio-wrapper">
      <h5 class="saio-header">What Google Shows in AI Overview</h5>
      ${html || '<p class="saio-empty">No AI Overview data available for this keyword.</p>'}
    </div>
  `;

}

// ✅ HACER DISPONIBLE GLOBALMENTE PARA DEBUG
window.getSelectedCountry = getSelectedCountry;

window.openSerpModal = openSerpModal;