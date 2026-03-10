// static/js/ui-aio-recommendations-modal.js
// Standalone AI Recommendations modal — triggered from Grid.js table

// ── Session-level cache ─────────────────────────────────────────────
window._aioRecommendationsCache = window._aioRecommendationsCache || {};

export function hasRecommendationsCache(keyword) {
  if (!keyword) return false;
  return !!window._aioRecommendationsCache[keyword.toLowerCase().trim()];
}

function _getCached(keyword) {
  return window._aioRecommendationsCache[keyword.toLowerCase().trim()] || null;
}

function _setCache(keyword, data) {
  window._aioRecommendationsCache[keyword.toLowerCase().trim()] = data;
}

// ── Find keyword result from global store ───────────────────────────
function _findResult(keyword) {
  const results = window._aioKeywordResults;
  if (!results || !Array.isArray(results)) return null;
  return results.find(r => r.keyword === keyword) || null;
}

// ── Public: open the recommendations modal ──────────────────────────
export function openRecommendationsModal(keyword) {
  const result = _findResult(keyword);
  if (!result) {
    console.warn('No AIO result found for keyword:', keyword);
    return;
  }

  _ensureModalDOM();

  const modal    = document.getElementById('aioRecommendationsModal');
  const kwLabel  = document.getElementById('aioRecKeyword');
  const body     = document.getElementById('aioRecBody');
  const footer   = document.getElementById('aioRecFooter');

  kwLabel.textContent = `"${keyword}"`;
  footer.style.display = 'none';
  modal.classList.add('show');
  document.body.style.overflow = 'hidden';

  // Store keyword on modal for copy/download
  modal.dataset.keyword = keyword;

  const cached = _getCached(keyword);
  if (cached) {
    body.innerHTML = _renderRecommendationsHTML(cached);
    footer.style.display = 'flex';
    _bindFooterActions(cached, keyword);
    return;
  }

  // No cache → loading flow
  _startLoadingAndFetch(result, keyword, body, footer);
}

// ── Modal DOM (created once, appended to body) ──────────────────────
let _modalCreated = false;

function _ensureModalDOM() {
  if (_modalCreated) return;

  const div = document.createElement('div');
  div.id = 'aioRecommendationsModal';
  div.className = 'aio-rec-modal';
  div.innerHTML = `
    <div class="aio-rec-modal__backdrop"></div>
    <div class="aio-rec-modal__container">
      <div class="aio-rec-modal__header">
        <div class="aio-rec-modal__header-icon">
          <i class="fas fa-lightbulb"></i>
        </div>
        <div class="aio-rec-modal__header-text">
          <h3 class="aio-rec-modal__title">AI Recommendations</h3>
          <p class="aio-rec-modal__subtitle" id="aioRecKeyword"></p>
        </div>
        <button class="aio-rec-modal__close" id="aioRecCloseBtn">&times;</button>
      </div>
      <div class="aio-rec-modal__body" id="aioRecBody"></div>
      <div class="aio-rec-modal__footer" id="aioRecFooter" style="display:none;">
        <button class="aio-rec-modal__action-btn" id="aioRecCopyBtn">
          <i class="fas fa-copy"></i> Copy to Clipboard
        </button>
        <button class="aio-rec-modal__action-btn" id="aioRecDownloadBtn">
          <i class="fas fa-download"></i> Download as TXT
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(div);
  _modalCreated = true;

  // Close handlers
  const modal = div;
  const closeBtn = div.querySelector('#aioRecCloseBtn');
  const backdrop = div.querySelector('.aio-rec-modal__backdrop');

  closeBtn.addEventListener('click', () => _closeModal(modal));
  backdrop.addEventListener('click', () => _closeModal(modal));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('show')) {
      _closeModal(modal);
    }
  });
}

function _closeModal(modal) {
  modal.classList.remove('show');
  document.body.style.overflow = '';

  // Mark Grid.js button as cached
  const keyword = modal.dataset.keyword;
  if (keyword && _getCached(keyword)) {
    _markButtonCached(keyword);
  }
}

function _markButtonCached(keyword) {
  const btns = document.querySelectorAll('.aio-rec-trigger-btn');
  btns.forEach(btn => {
    if (btn.dataset.keyword === keyword) {
      btn.classList.add('aio-rec-trigger-btn--cached');
    }
  });
}

// ── Loading stepper + API fetch ─────────────────────────────────────
function _startLoadingAndFetch(result, keyword, body, footer) {

  body.innerHTML = `
    <div class="aio-rec-loader">
      <div class="aio-rec-loader__step active" id="aioRecStep1">
        <div class="aio-rec-loader__icon"><i class="fas fa-globe"></i></div>
        <span>Scraping competitors…</span>
      </div>
      <div class="aio-rec-loader__step" id="aioRecStep2">
        <div class="aio-rec-loader__icon"><i class="fas fa-file-alt"></i></div>
        <span>Understanding your content…</span>
      </div>
      <div class="aio-rec-loader__step" id="aioRecStep3">
        <div class="aio-rec-loader__icon"><i class="fas fa-brain"></i></div>
        <span>Analyzing improvements…</span>
      </div>
      <div class="aio-rec-loader__progress">
        <div class="aio-rec-loader__bar" id="aioRecProgressBar"></div>
      </div>
    </div>
  `;

  // Animate progress bar to 10%
  requestAnimationFrame(() => {
    const bar = document.getElementById('aioRecProgressBar');
    if (bar) bar.style.width = '15%';
  });

  // Timer-based step progression
  const t1 = setTimeout(() => _advanceStep(1, 2, 40), 4000);
  const t2 = setTimeout(() => _advanceStep(2, 3, 70), 8000);

  // Assemble payload
  const ai    = result.ai_analysis || {};
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

  const abortCtrl  = new AbortController();
  const abortTimer = setTimeout(() => abortCtrl.abort(), 120000);

  fetch('/api/ai-recommendations', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
    signal:  abortCtrl.signal
  })
    .then(resp => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(abortTimer);

      if (resp.status === 402) {
        _completeAllSteps();
        body.innerHTML = _renderPaywallHTML();
        return;
      }
      if (resp.status === 429) {
        _completeAllSteps();
        body.innerHTML = `
          <div class="aio-rec-error">
            <i class="fas fa-clock"></i>
            <strong>Quota pause</strong> — Please wait a moment and try again.
          </div>`;
        return;
      }

      return resp.json().then(data => {
        if (!resp.ok || !data.success) {
          throw new Error(data.error || 'Unknown error');
        }

        _completeAllSteps();
        setTimeout(() => {
          _setCache(keyword, data);
          body.innerHTML = _renderRecommendationsHTML(data);
          footer.style.display = 'flex';
          _bindFooterActions(data, keyword);
        }, 400); // Small delay so user sees the final checkmark
      });
    })
    .catch(err => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(abortTimer);

      const msg = err.name === 'AbortError'
        ? 'Request timed out. The analysis is taking too long.'
        : (err.message || 'Something went wrong.');

      body.innerHTML = `
        <div class="aio-rec-error" style="margin:1.5rem;">
          <i class="fas fa-exclamation-triangle"></i>
          <strong>Error:</strong> ${msg}
          <button class="aio-rec-retry-btn" id="aioRecRetryBtn">
            <i class="fas fa-redo"></i> Retry
          </button>
        </div>`;

      const retryBtn = document.getElementById('aioRecRetryBtn');
      if (retryBtn) {
        retryBtn.addEventListener('click', () => {
          _startLoadingAndFetch(result, keyword, body, footer);
        });
      }
    });
}

function _advanceStep(fromNum, toNum, barPct) {
  const from = document.getElementById(`aioRecStep${fromNum}`);
  const to   = document.getElementById(`aioRecStep${toNum}`);
  const bar  = document.getElementById('aioRecProgressBar');
  if (from) { from.classList.remove('active'); from.classList.add('done'); }
  if (to)   { to.classList.add('active'); }
  if (bar)  { bar.style.width = `${barPct}%`; }
}

function _completeAllSteps() {
  for (let i = 1; i <= 3; i++) {
    const step = document.getElementById(`aioRecStep${i}`);
    if (step) { step.classList.remove('active'); step.classList.add('done'); }
  }
  const bar = document.getElementById('aioRecProgressBar');
  if (bar) bar.style.width = '100%';
}

// ── Render recommendations HTML ─────────────────────────────────────
function _renderRecommendationsHTML(data) {
  const priorityColors = { high: '#EF4444', medium: '#F59E0B', low: '#22C55E' };
  const priorityLabels = { high: 'High', medium: 'Medium', low: 'Low' };
  const categoryIcons  = {
    content:   'fas fa-file-alt',
    structure: 'fas fa-sitemap',
    authority: 'fas fa-link',
    technical: 'fas fa-cog'
  };

  let html = `<div style="padding:0 4px;">`;

  // Summary
  html += `
    <div class="aio-rec-summary">
      <i class="fas fa-lightbulb" style="color:#F59E0B;font-size:1.1em;flex-shrink:0;"></i>
      <span>${data.summary || 'Analysis complete.'}</span>
    </div>`;

  // Cited sources analysis
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
    const icon  = categoryIcons[rec.category]  || 'fas fa-check';

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

  html += `</div>`;
  return html;
}

// ── Paywall HTML ────────────────────────────────────────────────────
function _renderPaywallHTML() {
  return `
    <div class="aio-rec-paywall" style="margin:1.5rem;">
      <i class="fas fa-crown" style="font-size:1.6em;color:#F59E0B;"></i>
      <strong>Premium Feature</strong>
      <p>AI Recommendations are available on paid plans. Upgrade to get specific, actionable insights for every keyword.</p>
      <a href="/pricing" class="aio-rec-upgrade-btn">See Plans</a>
    </div>`;
}

// ── Copy & Download ─────────────────────────────────────────────────
function _buildPlainText(data, keyword) {
  let text = `AI Recommendations for: "${keyword}"\n`;
  text += '='.repeat(50) + '\n\n';

  if (data.summary) {
    text += `Summary:\n${data.summary}\n\n`;
  }
  if (data.cited_sources_analysis) {
    text += `Why competitors are cited:\n${data.cited_sources_analysis}\n\n`;
  }

  text += 'Recommendations:\n';
  text += '-'.repeat(40) + '\n\n';

  const recs = data.recommendations || [];
  recs.forEach((rec, i) => {
    const priority = (rec.priority || '').toUpperCase();
    text += `${i + 1}. [${priority}] ${rec.title || ''}\n`;
    text += `   ${rec.description || ''}\n`;
    text += `   Category: ${rec.category || ''}\n\n`;
  });

  if (data.cited_pages_analyzed) {
    text += `---\n${data.cited_pages_analyzed} competitor pages analyzed.\n`;
  }
  text += `\nGenerated by ClicanDSEO.com\n`;
  return text;
}

function _bindFooterActions(data, keyword) {
  const copyBtn     = document.getElementById('aioRecCopyBtn');
  const downloadBtn = document.getElementById('aioRecDownloadBtn');

  if (copyBtn) {
    // Remove old listeners by cloning
    const newCopy = copyBtn.cloneNode(true);
    copyBtn.parentNode.replaceChild(newCopy, copyBtn);

    newCopy.addEventListener('click', () => {
      const text = _buildPlainText(data, keyword);
      navigator.clipboard.writeText(text).then(() => {
        newCopy.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(() => {
          newCopy.innerHTML = '<i class="fas fa-copy"></i> Copy to Clipboard';
        }, 2000);
      }).catch(() => {
        newCopy.innerHTML = '<i class="fas fa-times"></i> Failed';
        setTimeout(() => {
          newCopy.innerHTML = '<i class="fas fa-copy"></i> Copy to Clipboard';
        }, 2000);
      });
    });
  }

  if (downloadBtn) {
    const newDl = downloadBtn.cloneNode(true);
    downloadBtn.parentNode.replaceChild(newDl, downloadBtn);

    newDl.addEventListener('click', () => {
      const text = _buildPlainText(data, keyword);
      const blob = new Blob([text], { type: 'text/plain' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `ai-recommendations-${keyword.replace(/\s+/g, '-').toLowerCase()}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      newDl.innerHTML = '<i class="fas fa-check"></i> Downloaded!';
      setTimeout(() => {
        newDl.innerHTML = '<i class="fas fa-download"></i> Download as TXT';
      }, 2000);
    });
  }
}

console.log('📦 AI Recommendations modal module loaded');
