// Modal suave para sugerir conexión a Google Search Console cuando no hay propiedades
(function () {
  function createGscModal() {
    const modal = document.createElement('div');
    modal.className = 'paywall-modal';
    modal.id = 'gsc-connect-modal';

    modal.innerHTML = `
      <div class="paywall-content" style="max-width:720px">
        <div class="paywall-header">
          <h3 class="paywall-title-premium">Connect Google Search Console</h3>
          <p>To use the main app features, connect at least one Search Console property. Manual AI Overview does not require GSC and can be used right away.</p>
        </div>

        <div class="paywall-body">
          <div class="feature-benefits">
            <h4>Why connect?</h4>
            <ul>
              <li>Unlock <strong>AI Overview Analysis</strong> with your verified sites</li>
              <li>See <strong>clicks, impressions and positions</strong> with real GSC data</li>
              <li>Enable <strong>country-aware</strong> analysis and SERP lookups</li>
            </ul>
          </div>
        </div>

        <div class="paywall-footer">
          <a href="/connections/google/start" class="btn-primary">Connect Google</a>
          <a href="/manual-ai/" class="btn-secondary">Open Manual AI (no GSC)</a>
          <button class="btn-secondary" id="gscModalClose">Maybe Later</button>
        </div>
      </div>
    `;

    // Cierre al hacer click fuera
    modal.addEventListener('click', (e) => {
      if (e.target === modal) hide();
    });

    function hide() {
      localStorage.setItem('gsc_connect_dismissed', 'true');
      modal.remove();
    }

    modal.querySelector('#gscModalClose').addEventListener('click', hide);
    return modal;
  }

  async function shouldShowModal() {
    try {
      const auth = document.body.getAttribute('data-authenticated');
      if (auth !== 'true') return false;
      if (localStorage.getItem('gsc_connect_dismissed') === 'true') return false;

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
      const modal = createGscModal();
      document.body.appendChild(modal);
    }
  });
})();


