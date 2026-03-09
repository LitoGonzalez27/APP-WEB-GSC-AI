// ui-serp-modal.js — Código optimizado sin CSS inline (usa styles/serp-and-table.css)

import { MobileModalManager, isMobileDevice } from './utils.js';

// Instancia global del gestor de modal robusto
let serpModalManager = null;

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
    alert('Error: The SERP modal component is not available.');
    return;
  }

  const siteUrlElement = document.querySelector('select[name="site_url"]');
  const siteUrlScProperty = siteUrlElement ? siteUrlElement.value : '';
  if (!siteUrlScProperty) {
    alert('Please select a Search Console property first.');
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
  html += `
    <div style="
      margin-bottom: 1.2em; padding: 0.9em 1.1em; border-radius: 10px;
      ${isDomainSource
        ? 'background: rgba(40,167,69,0.08); border-left: 4px solid #28a745;'
        : 'background: rgba(220,53,69,0.08); border-left: 4px solid #dc3545;'}
    ">
      <div style="display:flex;align-items:center;gap:8px;">
        <i class="fas fa-${isDomainSource ? 'check-circle' : 'times-circle'}" style="color: ${isDomainSource ? '#28a745' : '#dc3545'}; font-size: 1.3em;"></i>
        <div>
          <strong style="color: ${isDomainSource ? '#28a745' : '#dc3545'};">
            ${isDomainSource ? `Your domain appears at position #${domainPos} in this AI Overview` : 'Your domain is NOT cited in this AI Overview'}
          </strong>
        </div>
      </div>
    </div>
  `;

  // --- Content preview ---
  if (contentPreview) {
    const truncated = contentPreview.length >= 490
      ? contentPreview.substring(0, 300) + '...'
      : contentPreview;
    html += `
      <div style="margin-bottom: 1.2em;">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:0.5em;font-size:0.85em;font-weight:600;color:#444;">
          <i class="fas fa-align-left" style="color: #6f42c1;"></i>
          AI Overview Content
          <span style="font-weight:400;color:#888;font-size:0.9em;">(${totalBlocks} block${totalBlocks !== 1 ? 's' : ''})</span>
        </div>
        <div style="
          background:#f8f9fa;border-radius:8px;padding:0.9em 1em;
          font-size:0.85em;line-height:1.65;color:#333;
          border-left:3px solid #6f42c1;
          max-height:140px;overflow-y:auto;
        ">
          <i class="fas fa-robot" style="color:#6f42c1;margin-right:4px;opacity:0.6;"></i>
          ${escapeHtml(truncated)}
        </div>
      </div>
    `;
  }

  // --- Cited sources + Position mockup (side by side) ---
  if (references.length > 0) {
    // Cited sources list
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

      const isHighlighted = cls.type !== 'other';
      const bgColor = cls.type === 'user' ? 'rgba(40,167,69,0.08)' : (cls.type === 'competitor' ? 'rgba(253,126,20,0.08)' : 'transparent');
      const borderColor = isHighlighted ? cls.color : '#e9ecef';

      return `
        <div style="
          display:flex;align-items:center;gap:8px;
          padding:7px 10px;border-radius:8px;
          background:${bgColor};
          border:1px solid ${borderColor};
          ${isHighlighted ? `box-shadow:0 0 0 1px ${cls.color}25;` : ''}
        ">
          <div style="
            min-width:26px;height:26px;
            background:${cls.color};
            color:white;border-radius:50%;
            display:flex;align-items:center;justify-content:center;
            font-weight:700;font-size:0.75em;
          ">${pos}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:0.8em;font-weight:600;color:#333;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
              title="${escapeHtml(refTitle)}"
            >${escapeHtml(refTitle.length > 50 ? refTitle.substring(0, 50) + '...' : refTitle)}</div>
            <div style="font-size:0.7em;color:#888;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
              ${escapeHtml(displayDomain)}
            </div>
          </div>
          ${cls.type === 'user'
            ? `<span style="color:${cls.color};font-weight:700;font-size:0.8em;white-space:nowrap;"><i class="fas ${cls.icon}"></i> You</span>`
            : cls.type === 'competitor'
              ? `<span style="color:${cls.color};font-weight:700;font-size:0.75em;white-space:nowrap;"><i class="fas ${cls.icon}"></i> Competitor</span>`
              : `<span style="color:#aaa;font-size:0.8em;"><i class="fas ${cls.icon}"></i></span>`
          }
        </div>
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

      if (cls.type === 'user') {
        return `<div style="display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:7px;background:linear-gradient(135deg,#28a74520,#28a74510);border:2px solid #28a745;font-size:0.8em;font-weight:700;color:#28a745;">
          <span style="background:#28a745;color:white;border-radius:50%;min-width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:0.75em;">${i+1}</span>
          <i class="fas fa-check-circle" style="font-size:0.85em;"></i>${escapeHtml(displayName)}
        </div>`;
      }
      if (cls.type === 'competitor') {
        return `<div style="display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:7px;background:linear-gradient(135deg,#fd7e1420,#fd7e1410);border:2px solid #fd7e14;font-size:0.8em;font-weight:700;color:#e67e22;">
          <span style="background:#fd7e14;color:white;border-radius:50%;min-width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:0.75em;">${i+1}</span>
          <i class="fas fa-crosshairs" style="font-size:0.85em;"></i>${escapeHtml(displayName)}
        </div>`;
      }
      return `<div style="display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:7px;background:#f1f3f5;border:1px solid #dee2e6;font-size:0.8em;color:#555;">
        <span style="background:#6c757d;color:white;border-radius:50%;min-width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:0.75em;">${i+1}</span>
        ${escapeHtml(displayName)}
      </div>`;
    }).join('');

    const extraCount = references.length - maxShow;
    const serpPosBadge = serpPosition !== 'unknown'
      ? `<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 7px;border-radius:10px;background:#6f42c120;color:#6f42c1;font-size:0.7em;font-weight:600;"><i class="fas fa-map-pin"></i>AIO pos: ${escapeHtml(String(serpPosition))}</span>`
      : '';

    html += `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1em;margin-bottom:1em;">
        <div>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:0.5em;font-size:0.85em;font-weight:600;color:#444;">
            <i class="fas fa-quote-right" style="color:#17a2b8;"></i>
            Cited Sources <span style="font-weight:400;color:#888;font-size:0.9em;">(${references.length})</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:5px;max-height:280px;overflow-y:auto;padding-right:4px;">
            ${sourceItems}
          </div>
        </div>
        <div>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:0.5em;font-size:0.85em;font-weight:600;color:#444;">
            <i class="fas fa-list-ol" style="color:#fd7e14;"></i>
            Source Ranking ${serpPosBadge}
          </div>
          <div style="background:#fafbfc;border-radius:10px;padding:10px;border:1px solid #e9ecef;">
            <div style="display:flex;flex-direction:column;gap:4px;">
              ${slotsHTML}
            </div>
            ${extraCount > 0 ? `<div style="text-align:center;color:#888;font-size:0.72em;margin-top:5px;">+${extraCount} more</div>` : ''}
          </div>
          <div style="display:flex;gap:10px;margin-top:8px;justify-content:center;">
            <span style="font-size:0.7em;color:#28a745;"><i class="fas fa-circle" style="font-size:0.6em;"></i> You</span>
            <span style="font-size:0.7em;color:#fd7e14;"><i class="fas fa-circle" style="font-size:0.6em;"></i> Competitor</span>
            <span style="font-size:0.7em;color:#6c757d;"><i class="fas fa-circle" style="font-size:0.6em;"></i> Other</span>
          </div>
        </div>
      </div>
    `;
  }

  // --- Rich Snippets detected ---
  if (aiElements.length > 0) {
    const elementsHTML = aiElements.map((el, i) => {
      const isAIO = el.type?.toLowerCase().includes('ai overview');
      return `
        <div style="
          display:flex;align-items:center;gap:8px;
          padding:6px 10px;border-radius:6px;
          background:${isAIO ? 'rgba(220,53,69,0.06)' : 'rgba(255,193,7,0.06)'};
          border-left:3px solid ${isAIO ? '#dc3545' : '#ffc107'};
        ">
          <span style="font-size:0.75em;font-weight:700;color:${isAIO ? '#dc3545' : '#e67e22'};min-width:18px;">
            ${el.position != null ? el.position : i + 1}
          </span>
          <span style="font-size:0.82em;color:#333;font-weight:500;">${escapeHtml(el.type || 'Unknown')}</span>
          ${el.sources_count ? `<span style="font-size:0.7em;color:#888;margin-left:auto;">${el.sources_count} sources</span>` : ''}
        </div>
      `;
    }).join('');

    html += `
      <div style="padding-top:0.8em;border-top:1px solid #dee2e6;">
        <div style="font-size:0.85em;font-weight:600;color:#444;margin-bottom:0.5em;">
          <i class="fas fa-layer-group" style="margin-right:4px;color:#6f42c1;"></i>
          Detected Rich Snippets (${aiElements.length})
        </div>
        <div style="display:flex;flex-direction:column;gap:4px;max-height:160px;overflow-y:auto;">
          ${elementsHTML}
        </div>
      </div>
    `;
  }

  // --- AI Recommendations button ---
  html += `
    <div style="padding-top:1em;border-top:1px solid #dee2e6;text-align:center;">
      <button id="aio-get-recommendations-btn" class="aio-rec-btn">
        <i class="fas fa-magic"></i> Get AI Recommendations
      </button>
      <div id="aio-recommendations-container" style="display:none;margin-top:1em;text-align:left;"></div>
    </div>
  `;

  // Wrap everything
  container.innerHTML = `
    <div style="
      padding:1.2em;
      background:white;
      border-radius:12px;
      border:1px solid #e0e4e8;
      box-shadow:0 2px 8px rgba(0,0,0,0.04);
    ">
      <h5 style="margin-bottom:1em;color:#333;font-size:1.05em;display:flex;align-items:center;gap:8px;">
        <span style="display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#667eea,#764ba2);">
          <i class="fas fa-eye" style="color:white;font-size:0.8em;"></i>
        </span>
        What Google Shows in AI Overview
      </h5>
      ${html || '<p style="color:#888;text-align:center;">No AI Overview data available for this keyword.</p>'}
    </div>
  `;

  // Bind the recommendations button
  const recBtn = container.querySelector('#aio-get-recommendations-btn');
  if (recBtn) {
    recBtn.addEventListener('click', () => _fetchAIRecommendations(result));
  }
}

// ── AI Recommendations helpers ────────────────────────────────────────

/**
 * Fetch AI Recommendations for a keyword from the backend.
 * Assembles the payload from the existing AIO result object.
 */
async function _fetchAIRecommendations(result) {
  const btn       = document.getElementById('aio-get-recommendations-btn');
  const container = document.getElementById('aio-recommendations-container');
  if (!btn || !container) return;

  // -- Assemble payload from result --
  const ai = result.ai_analysis || {};
  const debug = ai.debug_info || {};

  const citedUrls = (debug.references_found || [])
    .map(r => r.link)
    .filter(Boolean)
    .slice(0, 4);

  const payload = {
    keyword:          result.keyword || '',
    cited_urls:       citedUrls,
    aio_content:      debug.aio_content_preview || '',
    user_domain:      debug.site_url_normalized || '',
    user_url:         ai.domain_ai_source_link || null,
    organic_position: result.site_position || null
  };

  // -- Loading state --
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Fetching competitor content…';
  container.style.display = 'none';

  const msgTimer = setTimeout(() => {
    btn.innerHTML = '<i class="fas fa-brain fa-spin"></i> Analyzing with AI…';
  }, 5000);

  const abortCtrl = new AbortController();
  const abortTimer = setTimeout(() => abortCtrl.abort(), 120000);

  try {
    const resp = await fetch('/api/ai-recommendations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: abortCtrl.signal
    });

    clearTimeout(msgTimer);
    clearTimeout(abortTimer);

    if (resp.status === 402) {
      container.innerHTML = _renderPaywallMessage();
      container.style.display = 'block';
      btn.innerHTML = '<i class="fas fa-lock"></i> Upgrade Required';
      return;
    }

    if (resp.status === 429) {
      container.innerHTML = `
        <div class="aio-rec-error">
          <i class="fas fa-clock"></i>
          <strong>Quota pause</strong> — Please wait a moment and try again.
        </div>`;
      container.style.display = 'block';
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-magic"></i> Retry';
      return;
    }

    const data = await resp.json();

    if (!resp.ok || !data.success) {
      throw new Error(data.error || 'Unknown error');
    }

    container.innerHTML = _renderRecommendations(data);
    container.style.display = 'block';
    btn.innerHTML = '<i class="fas fa-check"></i> Loaded';
    btn.classList.add('aio-rec-btn--done');

  } catch (err) {
    clearTimeout(msgTimer);
    clearTimeout(abortTimer);

    const msg = err.name === 'AbortError'
      ? 'Request timed out. The analysis is taking too long.'
      : (err.message || 'Something went wrong.');

    container.innerHTML = `
      <div class="aio-rec-error">
        <i class="fas fa-exclamation-triangle"></i>
        <strong>Error:</strong> ${msg}
        <button class="aio-rec-retry-btn" onclick="document.getElementById('aio-get-recommendations-btn').click()">
          <i class="fas fa-redo"></i> Retry
        </button>
      </div>`;
    container.style.display = 'block';
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-magic"></i> Retry';
  }
}

/**
 * Render the recommendations cards returned by the backend.
 */
function _renderRecommendations(data) {
  const priorityColors = { high: '#EF4444', medium: '#F59E0B', low: '#22C55E' };
  const priorityLabels = { high: 'High', medium: 'Medium', low: 'Low' };
  const categoryIcons  = {
    content:   'fas fa-file-alt',
    structure: 'fas fa-sitemap',
    authority: 'fas fa-link',
    technical: 'fas fa-cog'
  };

  // Summary card
  let html = `
    <div class="aio-rec-summary">
      <i class="fas fa-lightbulb" style="color:#F59E0B;font-size:1.1em;"></i>
      <span>${data.summary || 'Analysis complete.'}</span>
    </div>`;

  // Cited sources analysis (if present)
  if (data.cited_sources_analysis) {
    html += `
      <div class="aio-rec-sources-analysis">
        <strong><i class="fas fa-search"></i> Why competitors are cited:</strong>
        <p>${data.cited_sources_analysis}</p>
      </div>`;
  }

  // Recommendation cards
  const recs = data.recommendations || [];
  recs.forEach((rec, i) => {
    const color = priorityColors[rec.priority] || '#94A3B8';
    const label = priorityLabels[rec.priority] || rec.priority;
    const icon  = categoryIcons[rec.category]   || 'fas fa-check';

    html += `
      <div class="aio-rec-card">
        <div class="aio-rec-card__header">
          <span class="aio-rec-card__num" style="background:${color};">${i + 1}</span>
          <span class="aio-rec-card__title">${rec.title || ''}</span>
          <span class="aio-rec-card__priority" style="color:${color};border-color:${color};">${label}</span>
        </div>
        <p class="aio-rec-card__desc">${rec.description || ''}</p>
        <span class="aio-rec-card__category"><i class="${icon}"></i> ${rec.category || ''}</span>
      </div>`;
  });

  // Footer meta
  const pagesNote = data.cited_pages_analyzed
    ? `${data.cited_pages_analyzed} competitor pages analyzed`
    : '';
  const costNote = data.cost_usd != null
    ? `· $${data.cost_usd.toFixed(4)}`
    : '';
  const cachedNote = data.cached ? ' · <i class="fas fa-bolt" title="Cached"></i> Cached' : '';

  html += `
    <div class="aio-rec-footer">
      ${pagesNote} ${costNote} ${cachedNote}
    </div>`;

  return html;
}

/**
 * Paywall message for free-plan users.
 */
function _renderPaywallMessage() {
  return `
    <div class="aio-rec-paywall">
      <i class="fas fa-crown" style="font-size:1.6em;color:#F59E0B;"></i>
      <strong>Premium Feature</strong>
      <p>AI Recommendations are available on paid plans. Upgrade to get specific, actionable insights for every keyword.</p>
      <a href="/pricing" class="aio-rec-upgrade-btn">See Plans</a>
    </div>`;
}

// ✅ HACER DISPONIBLE GLOBALMENTE PARA DEBUG
window.getSelectedCountry = getSelectedCountry;

window.openSerpModal = openSerpModal;