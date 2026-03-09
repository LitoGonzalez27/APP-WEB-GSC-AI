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

// 🆕 Render the AI Overview preview tab content
function _renderAIOPreviewTab(result) {
  const container = document.getElementById('aio-preview-view');
  if (!container) return;

  const aiAnalysis = result.ai_analysis || {};
  const debugInfo = aiAnalysis.debug_info || {};
  const ctr = result._ctr_analysis || {};

  const contentPreview = debugInfo.aio_content_preview || '';
  const references = debugInfo.references_found || [];
  const siteUrl = debugInfo.site_url_normalized || '';
  const serpPosition = debugInfo.aio_serp_position || 'unknown';
  const totalBlocks = debugInfo.total_text_blocks || 0;
  const isDomainSource = aiAnalysis.domain_is_ai_source || false;
  const domainPos = aiAnalysis.domain_ai_source_position;

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

  // --- CTR Benchmark mini-summary ---
  if (ctr.expected_ctr != null && ctr.actual_ctr != null) {
    const expectedPct = (ctr.expected_ctr * 100).toFixed(1);
    const actualPct = (ctr.actual_ctr * 100).toFixed(1);
    const gapPct = ctr.ctr_gap != null ? (ctr.ctr_gap * 100).toFixed(1) : null;
    const absorbed = ctr.clicks_absorbed || 0;
    const isUnder = ctr.ctr_gap > 0;
    const gapColor = isUnder ? '#dc3545' : '#28a745';
    const position = result.position_m2 != null ? Math.round(result.position_m2) : '?';

    html += `
      <div style="margin-bottom:1.2em;padding:1em;background:linear-gradient(135deg,#f8f9fa,#e9ecef);border-radius:10px;border-left:4px solid ${gapColor};">
        <div style="font-size:0.85em;font-weight:600;color:#333;margin-bottom:0.6em;">
          <i class="fas fa-chart-bar" style="margin-right:6px;color:#6f42c1;"></i> CTR Benchmark (pos #${position})
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.8em;text-align:center;">
          <div style="padding:0.6em;background:white;border-radius:8px;">
            <div style="font-size:0.7em;color:#888;">Expected</div>
            <div style="font-size:1.3em;font-weight:bold;color:#6c757d;">${expectedPct}%</div>
          </div>
          <div style="padding:0.6em;background:white;border-radius:8px;">
            <div style="font-size:0.7em;color:#888;">Actual</div>
            <div style="font-size:1.3em;font-weight:bold;color:${gapColor};">${actualPct}%</div>
          </div>
          <div style="padding:0.6em;background:white;border-radius:8px;">
            <div style="font-size:0.7em;color:#888;">Absorbed</div>
            <div style="font-size:1.3em;font-weight:bold;color:#dc3545;">~${absorbed}</div>
          </div>
        </div>
        ${gapPct != null ? `
          <div style="text-align:center;margin-top:0.5em;">
            <span style="display:inline-block;padding:3px 12px;border-radius:16px;background:${gapColor}15;color:${gapColor};font-weight:700;font-size:0.82em;">
              CTR Gap: ${isUnder ? '+' : ''}${gapPct}% ${isUnder ? 'below benchmark' : 'above benchmark'}
            </span>
          </div>
        ` : ''}
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

      let isUserDomain = false;
      if (siteUrl) {
        const normalizedRef = (refLink + ' ' + refSource).toLowerCase();
        const normalizedSite = siteUrl.toLowerCase().replace(/^www\./, '');
        isUserDomain = normalizedRef.includes(normalizedSite);
      }

      const pos = i + 1;
      let displayDomain = refSource || '';
      if (!displayDomain && refLink) {
        try { displayDomain = new URL(refLink).hostname; } catch (e) { displayDomain = refLink; }
      }

      return `
        <div style="
          display:flex;align-items:center;gap:8px;
          padding:7px 10px;border-radius:8px;
          background:${isUserDomain ? 'rgba(40,167,69,0.08)' : 'transparent'};
          border:1px solid ${isUserDomain ? '#28a745' : '#e9ecef'};
          ${isUserDomain ? 'box-shadow:0 0 0 1px rgba(40,167,69,0.15);' : ''}
        ">
          <div style="
            min-width:26px;height:26px;
            background:${isUserDomain ? '#28a745' : '#6c757d'};
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
          ${isUserDomain
            ? '<span style="color:#28a745;font-weight:700;font-size:0.8em;white-space:nowrap;"><i class="fas fa-check-circle"></i> You</span>'
            : '<span style="color:#aaa;font-size:0.8em;"><i class="fas fa-external-link-alt"></i></span>'
          }
        </div>
      `;
    }).join('');

    // Position mini-mockup
    const maxShow = Math.min(references.length, 6);
    const slotsHTML = Array.from({ length: maxShow }, (_, i) => {
      const ref = references[i];
      const refLink = ref.link || '';
      const refSource = ref.source || '';
      let displayName = refSource || '';
      if (!displayName && refLink) {
        try { displayName = new URL(refLink).hostname.replace(/^www\./, ''); } catch (e) { displayName = refLink; }
      }
      if (displayName.length > 18) displayName = displayName.substring(0, 16) + '...';

      let isUser = false;
      if (siteUrl) {
        const normalizedRef = (refLink + ' ' + refSource).toLowerCase();
        const normalizedSite = siteUrl.toLowerCase().replace(/^www\./, '');
        isUser = normalizedRef.includes(normalizedSite);
      }

      if (isUser) {
        return `<div style="display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:7px;background:linear-gradient(135deg,#28a74520,#28a74510);border:2px solid #28a745;font-size:0.8em;font-weight:700;color:#28a745;">
          <span style="background:#28a745;color:white;border-radius:50%;min-width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:0.75em;">${i+1}</span>
          <i class="fas fa-check-circle" style="font-size:0.85em;"></i>${escapeHtml(displayName)}
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
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1em;">
        <div>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:0.5em;font-size:0.85em;font-weight:600;color:#444;">
            <i class="fas fa-quote-right" style="color:#17a2b8;"></i>
            Cited Sources <span style="font-weight:400;color:#888;font-size:0.9em;">(${references.length})</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:5px;max-height:250px;overflow-y:auto;padding-right:4px;">
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
        </div>
      </div>
    `;
  }

  // --- SERP Features pills ---
  const features = ctr.serp_features || [];
  if (features.length > 0) {
    const impactPct = ctr.serp_features_impact ? (ctr.serp_features_impact * 100).toFixed(0) : '0';
    const pills = features.map(f => `
      <span style="display:inline-flex;align-items:center;gap:3px;padding:3px 9px;border-radius:12px;font-size:0.78em;background:${f.color}15;color:${f.color};border:1px solid ${f.color}25;">
        <i class="fas ${f.icon}" style="font-size:0.85em;"></i> ${escapeHtml(f.label)}
      </span>
    `).join('');

    html += `
      <div style="margin-top:1em;padding-top:0.8em;border-top:1px solid #dee2e6;">
        <div style="font-size:0.8em;color:#555;font-weight:600;margin-bottom:0.4em;">
          <i class="fas fa-layer-group" style="margin-right:4px;color:#6f42c1;"></i>
          Other SERP Features (~${impactPct}% CTR impact)
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:5px;">
          ${pills}
        </div>
      </div>
    `;
  }

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
}

// ✅ HACER DISPONIBLE GLOBALMENTE PARA DEBUG
window.getSelectedCountry = getSelectedCountry;

window.openSerpModal = openSerpModal;