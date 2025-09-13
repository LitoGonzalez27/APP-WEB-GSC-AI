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

        <div class="paywall-footer">
          <a href="/connections/google/start" class="btn-primary">Connect Google</a>
          <a href="/manual-ai/" class="btn-secondary btn-secondary-dashboard">Open Manual AI (no GSC)</a>
        </div>
      </div>
    `;

    // Cierre al hacer click fuera o con ESC
    modal.addEventListener('click', (e) => {
      if (e.target === modal) hide();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') hide();
    }, { once: true });

    function hide() { modal.remove(); }

    return modal;
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
      const modal = createGscModal();
      document.body.appendChild(modal);
    }
  });
})();


