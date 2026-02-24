// Modal suave para sugerir conexión a Google Search Console cuando no hay propiedades
(function () {
  function createGscModal() {
    const modal = document.createElement('div');
    modal.className = 'paywall-modal gsc-connect-overlay';
    modal.id = 'gsc-connect-modal';

    modal.innerHTML = `
      <div class="paywall-content gsc-connect-content" style="max-width:520px">
        <button class="gsc-connect-close" aria-label="Close">&times;</button>
        <div class="gsc-connect-icon">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" stroke="#6b7280" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
        <h3 class="gsc-connect-title">Connect Google Search Console</h3>
        <p class="gsc-connect-desc">To use the main app features, connect at least one Search Console property. <strong>Manual AI Overview</strong> does not require GSC and can be used right away.</p>
        <a href="/connections/google/start" class="gsc-connect-btn">
          <i class="fab fa-google" style="font-size:15px"></i>
          Connect Google Search Console
        </a>
        <button class="gsc-connect-dismiss" id="gscDismissBtn">Maybe later</button>
      </div>
    `;

    // Cierre al hacer click fuera, con ESC, o con "X" / "Maybe later"
    modal.addEventListener('click', (e) => {
      if (e.target === modal) hide();
    });
    modal.querySelector('.gsc-connect-close').addEventListener('click', hide);
    modal.querySelector('#gscDismissBtn').addEventListener('click', hide);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') hide();
    }, { once: true });

    function hide() {
      modal.classList.remove('visible');
      setTimeout(() => modal.remove(), 300);
    }

    return modal;
  }

  function injectStyles() {
    if (document.getElementById('gsc-connect-styles')) return;
    const style = document.createElement('style');
    style.id = 'gsc-connect-styles';
    style.textContent = `
      .gsc-connect-overlay {
        opacity: 0;
        transition: opacity 0.4s ease;
        background: rgba(15, 23, 42, 0.35) !important;
      }
      .gsc-connect-overlay.visible {
        opacity: 1;
      }
      .gsc-connect-content {
        text-align: center;
        padding: 2.5rem 2rem 2rem !important;
        border-radius: 16px !important;
        position: relative;
        transform: translateY(12px) scale(0.97);
        transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
      }
      .gsc-connect-overlay.visible .gsc-connect-content {
        transform: translateY(0) scale(1);
      }
      .gsc-connect-close {
        position: absolute;
        top: 14px;
        right: 16px;
        background: none;
        border: none;
        font-size: 22px;
        line-height: 1;
        color: #9ca3af;
        cursor: pointer;
        padding: 4px;
        transition: color 0.15s ease;
      }
      .gsc-connect-close:hover { color: #374151; }
      .gsc-connect-icon {
        margin: 0 auto 1rem;
        width: 56px;
        height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f3f4f6;
        border-radius: 50%;
      }
      .gsc-connect-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #111827;
        margin: 0 0 0.5rem;
      }
      .gsc-connect-desc {
        font-size: 0.9rem;
        color: #6b7280;
        line-height: 1.55;
        margin: 0 0 1.5rem;
      }
      .gsc-connect-desc strong { color: #374151; }
      .gsc-connect-btn {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #111827;
        color: #D8F9B8;
        border: 1px solid #111827;
        padding: 11px 24px;
        border-radius: 8px;
        font-size: 0.9rem;
        font-weight: 500;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.2s ease;
      }
      .gsc-connect-btn:hover {
        background: #D8F9B8;
        color: #111827;
        border-color: #c4e8a5;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        text-decoration: none;
      }
      .gsc-connect-dismiss {
        display: block;
        margin: 0.75rem auto 0;
        background: none;
        border: none;
        color: #9ca3af;
        font-size: 0.8rem;
        cursor: pointer;
        padding: 4px 8px;
        transition: color 0.15s ease;
      }
      .gsc-connect-dismiss:hover { color: #374151; }
    `;
    document.head.appendChild(style);
  }

  async function shouldShowModal() {
    try {
      const auth = document.body.getAttribute('data-authenticated');
      if (auth !== 'true') return false;

      const resp = await fetch('/gsc/properties', { credentials: 'include' });
      if (!resp.ok) return false;
      const data = await resp.json();
      const props = (data && Array.isArray(data.properties)) ? data.properties : [];
      return props.length === 0; // Sin propiedades → mostrar
    } catch (e) {
      console.warn('[GSC MODAL] No se pudo determinar propiedades:', e);
      return false;
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (await shouldShowModal()) {
      injectStyles();
      const modal = createGscModal();
      document.body.appendChild(modal);
      // Delay 2.5s before showing, then smooth fade-in
      setTimeout(() => {
        modal.classList.add('visible');
      }, 2500);
    }
  });
})();
