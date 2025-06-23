// ui-serp-modal.js — Código optimizado sin CSS inline (usa styles/serp-and-table.css)

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

// ✅ FUNCIÓN CORREGIDA: getSelectedCountry
function getSelectedCountry() {
    const country = window.getCountryToUse ? window.getCountryToUse() : null;
    
    // ✅ NUEVO: Para SERP API, si no hay país específico, usar España como fallback
    // Esto es porque SERP API siempre necesita un país para geolocalización
    if (!country) {
        console.log('🌍 Sin país específico para SERP - usando España como geolocalización por defecto');
        return 'esp';
    }
    
    console.log(`🎯 Usando país para SERP: ${country}`);
    return country;
}

// ✅ FUNCIÓN CORREGIDA: fetchSerpPosition
async function fetchSerpPosition(keyword, siteUrl) {
    const selectedCountry = getSelectedCountry(); // Siempre devuelve un país para SERP
    const params = new URLSearchParams({
        keyword: keyword,
        site_url: siteUrl,
        country: selectedCountry // Siempre incluir país para SERP
    });
    
    console.log(`🔍 SERP Position API: keyword="${keyword}", country="${selectedCountry}"`);
    const response = await fetch(`/api/serp/position?${params}`);
    return response.json();
}

// ✅ FUNCIÓN CORREGIDA: fetchSerpData
async function fetchSerpData(keyword) {
    const selectedCountry = getSelectedCountry(); // Siempre devuelve un país para SERP
    const params = new URLSearchParams({
        keyword: keyword,
        country: selectedCountry // Siempre incluir país para SERP
    });
    
    console.log(`🔍 SERP Data API: keyword="${keyword}", country="${selectedCountry}"`);
    const response = await fetch(`/api/serp?${params}`);
    return response.json();
}

// ✅ FUNCIÓN CORREGIDA: fetchSerpScreenshot
async function fetchSerpScreenshot(keyword, siteUrl) {
    const selectedCountry = getSelectedCountry(); // Siempre devuelve un país para SERP
    const params = new URLSearchParams({
        keyword: keyword,
        site_url: siteUrl,
        country: selectedCountry // Siempre incluir país para SERP
    });
    
    console.log(`📸 SERP Screenshot API: keyword="${keyword}", country="${selectedCountry}"`);
    const response = await fetch(`/api/serp/screenshot?${params}`);
    return response;
}


// --- Lógica del Modal ---
export function openSerpModal(keyword, userSpecificUrl) {
  const modal = document.getElementById('serpModal');
  if (!modal) {
    console.error('Falta el elemento #serpModal en el DOM.');
    alert('Error: El component modal de SERP no está disponible.');
    return;
  }

  const siteUrlElement = document.querySelector('select[name="site_url"]');
  const siteUrlScProperty = siteUrlElement ? siteUrlElement.value : '';
  if (!siteUrlScProperty) {
    alert('Por favor, selecciona una propiedad de Search Console primero.');
    return;
  }

  const kwSpan = modal.querySelector('#serpKeyword');
  const modalBody = modal.querySelector('.modal-body');
  kwSpan.textContent = keyword;
  modalBody.innerHTML = '';

  const container = document.createElement('div');
  container.innerHTML = `
    <div class="serp-tabs">
      <button class="serp-tab active" data-tab="quick" aria-selected="true">Quick View</button>
      <button class="serp-tab" data-tab="screenshot" aria-selected="false">Screenshot SERP</button>
    </div>
    <div class="serp-content">
      <div id="quick-view" class="tab-content active" role="tabpanel">
        <div class="serp-spinner"></div>
        <p>Cargando vista rápida...</p>
      </div>
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
      document.getElementById(tab.dataset.tab === 'quick' ? 'quick-view' : 'screenshot-view').style.display = 'block';
    });
  });

  // MODIFICADO: Usar las nuevas funciones que obtienen el país
  loadQuickView(keyword, userSpecificUrl, siteUrlScProperty);
  container.querySelector('.load-screenshot').addEventListener('click', () => loadScreenshot(keyword, userSpecificUrl, siteUrlScProperty));

  modal.classList.add('show');
  document.addEventListener('click', (e) => {
    const modal = document.getElementById('serpModal');
    if (
      e.target.matches('#serpModal .close-btn') ||
      e.target === modal
    ) {
      closeSerpModal();
    }
  });
}

function closeSerpModal() {
  const modal = document.getElementById('serpModal');
  if (modal) modal.classList.remove('show');
}

async function loadQuickView(keyword, userSpecificUrl, siteUrlScProperty) {
  const quickView = document.getElementById('quick-view');
  quickView.innerHTML = '<div class="serp-spinner"></div><p>Obteniendo datos de posición...</p>';

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

window.openSerpModal = openSerpModal;