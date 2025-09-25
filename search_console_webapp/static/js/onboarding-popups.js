// static/js/onboarding-popups.js - Popups de onboarding con vídeos embebidos

// Sistema simple de registro de vídeos por sección y control de frecuencia
// Requisitos:
// - Mostrar popups de manera suave y no intrusiva
// - Permitir cerrar en cualquier momento
// - Reproducir el vídeo embebido dentro del popup
// - Mostrar sólo en las primeras 2 visitas por usuario y por sección

(function() {
  const STORAGE_KEY = 'onboarding_popup_counts_v1';

  // Recuperar identificador de usuario, si está disponible
  function getCurrentUserId() {
    try {
      const user = window.navbar && typeof window.navbar.getAuthStatus === 'function'
        ? window.navbar.getAuthStatus().user
        : null;
      if (user && (user.id || user.user_id || user.email)) {
        return user.id || user.user_id || user.email;
      }
    } catch (e) {}
    // Fallback: usar flag de autenticado del body
    const isAuth = document.body.getAttribute('data-authenticated') === 'true';
    return isAuth ? 'auth-user' : 'anon';
  }

  function loadCounts() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function saveCounts(counts) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(counts));
    } catch (e) {}
  }

  function getCount(sectionKey, userId) {
    const counts = loadCounts();
    const byUser = counts[userId] || {};
    return byUser[sectionKey] || 0;
  }

  function incrementCount(sectionKey, userId) {
    const counts = loadCounts();
    if (!counts[userId]) counts[userId] = {};
    counts[userId][sectionKey] = (counts[userId][sectionKey] || 0) + 1;
    saveCounts(counts);
  }

  // Registro de vídeos por sección
  const registry = {};

  function registerVideo(sectionKey, { youtubeUrl, title = 'Introducción', description = '' }) {
    if (!youtubeUrl) return;
    registry[sectionKey] = { youtubeUrl, title, description };
  }

  // Crear estilos una sola vez
  function ensureStyles() {
    if (document.getElementById('onboarding-popup-styles')) return;
    const style = document.createElement('style');
    style.id = 'onboarding-popup-styles';
    style.textContent = `
      .onboarding-modal {
        position: fixed;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0,0,0,0.35);
        backdrop-filter: blur(2px);
        z-index: 11000;
        opacity: 0;
        transition: opacity 200ms ease;
      }
      .onboarding-modal.show { opacity: 1; }
      .onboarding-dialog {
        width: min(92vw, 840px);
        max-height: 86vh;
        background: var(--card-bg, #fff);
        color: var(--text-color, #222);
        border-radius: 16px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.25);
        overflow: hidden;
        transform: translateY(10px);
        transition: transform 220ms ease;
      }
      .onboarding-modal.show .onboarding-dialog { transform: translateY(0); }
      .onboarding-header {
        padding: 14px 18px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .onboarding-title { font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
      .onboarding-close {
        background: transparent; border: 0; color: #fff; font-size: 22px; cursor: pointer; opacity: .9;
      }
      .onboarding-body { padding: 0; background: #000; }
      .onboarding-iframe { width: 100%; aspect-ratio: 16/9; border: 0; display: block; }
      .onboarding-footer { padding: 12px 16px; background: #f8f9fa; display: flex; align-items: center; justify-content: space-between; }
      .onboarding-actions { display: flex; gap: 8px; }
      .onboarding-btn { border: 0; border-radius: 10px; padding: 10px 14px; cursor: pointer; font-weight: 500; }
      .onboarding-btn-primary { background: #17a2b8; color: #fff; }
      .onboarding-btn-secondary { background: #6c757d; color: #fff; }
      @media (max-width: 768px) {
        .onboarding-dialog { width: 96vw; border-radius: 14px; }
        .onboarding-title { font-size: 15px; }
      }
    `;
    document.head.appendChild(style);
  }

  function buildModal(sectionKey, config) {
    ensureStyles();
    const modal = document.createElement('div');
    modal.className = 'onboarding-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'Vídeo de introducción');

    const iframeSrc = config.youtubeUrl.includes('youtube.com/embed')
      ? config.youtubeUrl
      : `https://www.youtube.com/embed/${config.youtubeUrl}`;

    modal.innerHTML = `
      <div class="onboarding-dialog">
        <div class="onboarding-header">
          <div class="onboarding-title"><i class="fas fa-video"></i>${config.title}</div>
          <button class="onboarding-close" aria-label="Cerrar">&times;</button>
        </div>
        <div class="onboarding-body">
          <iframe class="onboarding-iframe" src="${iframeSrc}" title="YouTube video player" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
        </div>
        <div class="onboarding-footer">
          <div style="font-size: 12px; opacity: .8;">Puedes cerrar este vídeo cuando quieras</div>
          <div class="onboarding-actions">
            <button class="onboarding-btn onboarding-btn-secondary" data-action="dismiss">Cerrar</button>
          </div>
        </div>
      </div>
    `;

    const close = () => {
      modal.classList.remove('show');
      setTimeout(() => modal.remove(), 200);
    };

    // Cerrar al hacer click fuera
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
    // Botón cerrar
    modal.querySelector('.onboarding-close').addEventListener('click', close);
    modal.querySelector('[data-action="dismiss"]').addEventListener('click', close);
    // Escape
    const escHandler = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', escHandler, { once: true });

    return { modal, show: () => requestAnimationFrame(() => modal.classList.add('show')) };
  }

  function shouldShow(sectionKey, maxViews = 2) {
    const userId = getCurrentUserId();
    const count = getCount(sectionKey, userId);
    return count < maxViews;
  }

  function showForSection(sectionKey) {
    const cfg = registry[sectionKey];
    if (!cfg) return;
    const userId = getCurrentUserId();
    if (!shouldShow(sectionKey)) return;

    const { modal, show } = buildModal(sectionKey, cfg);
    document.body.appendChild(modal);
    modal.id = '__onboarding_modal__';
    show();
    incrementCount(sectionKey, userId);
  }

  // API pública
  window.OnboardingPopups = {
    registerVideo,
    showForSection,
    shouldShow
  };

  // Registro inicial: AI Overview (AIO) usando la URL proporcionada
  registerVideo('ai-overview', {
    youtubeUrl: 'https://www.youtube.com/embed/UMtMvk_2vp8?si=P38CP7p1_NeO5CWw',
    title: 'AI Overview: Introducción rápida',
    description: 'Aprende a interpretar el módulo AI Overview y sus datos clave.'
  });

  // Escuchar navegación del sidebar y disparar el popup en AI Overview
  document.addEventListener('sidebarNavigation', (e) => {
    const section = e && e.detail && e.detail.newSection;
    if (section === 'ai-overview') {
      try {
        if ('requestIdleCallback' in window) {
          window.requestIdleCallback(() => showForSection('ai-overview'));
        } else {
          setTimeout(() => showForSection('ai-overview'), 0);
        }
      } catch (err) {
        showForSection('ai-overview');
      }
    }
  });
})();


