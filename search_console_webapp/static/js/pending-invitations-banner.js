/**
 * Banner de invitaciones pendientes (compartido entre dashboard y módulos)
 *
 * - Consulta /api/project-access/my-invitations (pendientes del email logueado).
 * - Si hay pendientes, muestra un banner brandbook con botón "Reenviarme el email"
 *   (self-service seguro: el correo solo va al buzón del propio usuario).
 * - Si la página muestra el overlay "Upgrade Required" (.llm-access-blocked-modal)
 *   y el usuario tiene invitaciones pendientes, convierte el overlay en una guía
 *   de aceptación en lugar del upsell — el caso típico del invitado con cuenta free.
 *
 * Nota: con el auto-accept de OAuth, la mayoría de invitados no verá nada de
 * esto; cubre a las cuentas de email+contraseña, cuya aceptación sigue
 * requiriendo el clic en el enlace del correo (prueba de propiedad del buzón).
 */
(function () {
    'use strict';

    var API_LIST = '/api/project-access/my-invitations';
    var DISMISS_KEY = 'pendingInvitationsBannerDismissed';

    function esc(value) {
        var div = document.createElement('div');
        div.textContent = String(value == null ? '' : value);
        return div.innerHTML;
    }

    function injectStyles() {
        if (document.getElementById('pendingInvitationsStyles')) return;
        var css = [
            '.pending-inv-banner{background:#161616;color:#fff;border-radius:12px;padding:14px 18px;',
            'margin:16px auto;max-width:1200px;display:flex;align-items:flex-start;gap:14px;',
            'box-shadow:0 4px 12px rgba(0,0,0,.15);font-size:14px;position:relative;z-index:50;}',
            '.pending-inv-banner .pi-icon{color:#D8F9B8;font-size:1.25rem;margin-top:2px;}',
            '.pending-inv-banner .pi-body{flex:1;}',
            '.pending-inv-banner .pi-title{font-weight:700;margin:0 0 6px;color:#D8F9B8;}',
            '.pending-inv-banner .pi-item{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:4px 0;}',
            '.pending-inv-banner .pi-module{background:rgba(216,249,184,.15);color:#D8F9B8;border-radius:999px;',
            'padding:2px 10px;font-size:12px;font-weight:600;}',
            '.pending-inv-banner .pi-resend{background:#D8F9B8;color:#161616;border:none;border-radius:8px;',
            'padding:5px 12px;font-size:12px;font-weight:700;cursor:pointer;transition:opacity .15s;}',
            '.pending-inv-banner .pi-resend:hover{opacity:.85;}',
            '.pending-inv-banner .pi-resend:disabled{opacity:.5;cursor:default;}',
            '.pending-inv-banner .pi-hint{color:#9ca3af;font-size:12px;margin-top:6px;}',
            '.pending-inv-banner .pi-close{background:none;border:none;color:#9ca3af;font-size:1rem;',
            'cursor:pointer;padding:2px 6px;}',
            '.pending-inv-banner .pi-close:hover{color:#fff;}',
            '.pi-overlay-list{text-align:left;margin:16px 0;}',
            '.pi-overlay-list .pi-item{display:flex;align-items:center;gap:10px;flex-wrap:wrap;',
            'padding:10px 12px;background:rgba(255,255,255,.06);border-radius:10px;margin-bottom:8px;}'
        ].join('');
        var style = document.createElement('style');
        style.id = 'pendingInvitationsStyles';
        style.textContent = css;
        document.head.appendChild(style);
    }

    function invitationRow(inv) {
        return (
            '<div class="pi-item" data-invitation-id="' + esc(inv.id) + '">' +
            '<span class="pi-module">' + esc(inv.module_label || inv.module_name) + '</span>' +
            '<strong>' + esc(inv.project_name || ('Proyecto ' + inv.project_id)) + '</strong>' +
            '<button type="button" class="pi-resend">Reenviarme el email</button>' +
            '</div>'
        );
    }

    function wireResendButtons(root) {
        root.querySelectorAll('.pi-resend').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var item = btn.closest('[data-invitation-id]');
                if (!item) return;
                btn.disabled = true;
                btn.textContent = 'Enviando…';
                fetch('/api/project-access/my-invitations/' + item.dataset.invitationId + '/resend', {
                    method: 'POST',
                    credentials: 'same-origin'
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        btn.textContent = data.success && data.email_sent !== false
                            ? 'Enviado ✓ — revisa tu buzón'
                            : 'No se pudo enviar';
                        if (!data.success) btn.disabled = false;
                    })
                    .catch(function () {
                        btn.textContent = 'Error de red';
                        btn.disabled = false;
                    });
            });
        });
    }

    function replaceUpgradeOverlay(invitations) {
        var modal = document.querySelector('.llm-access-blocked-modal');
        if (!modal) return false;

        modal.innerHTML =
            '<h2 style="color:#D8F9B8;">Tienes ' + invitations.length +
            (invitations.length === 1 ? ' invitación pendiente' : ' invitaciones pendientes') + '</h2>' +
            '<p class="llm-blocked-description">Te han invitado a ver estos proyectos. ' +
            'Para activar el acceso, abre el email de invitación y pulsa el enlace de aceptación. ' +
            'Si no lo encuentras, reenvíatelo desde aquí:</p>' +
            '<div class="pi-overlay-list">' + invitations.map(invitationRow).join('') + '</div>' +
            '<p class="llm-blocked-notify" style="font-size:12px;">Consejo: si entras con Google usando este mismo email, ' +
            'las invitaciones se aceptan automáticamente.</p>' +
            '<div class="llm-blocked-actions">' +
            '<a href="/dashboard" class="btn-secondary">Volver al dashboard</a>' +
            '</div>';
        wireResendButtons(modal);
        return true;
    }

    function insertBanner(invitations) {
        if (sessionStorage.getItem(DISMISS_KEY) === '1') return;

        var banner = document.createElement('div');
        banner.className = 'pending-inv-banner';
        banner.innerHTML =
            '<span class="pi-icon">✉️</span>' +
            '<div class="pi-body">' +
            '<p class="pi-title">Tienes ' + invitations.length +
            (invitations.length === 1 ? ' invitación pendiente' : ' invitaciones pendientes') + '</p>' +
            invitations.map(invitationRow).join('') +
            '<p class="pi-hint">Acepta desde el enlace del email de invitación. Si entras con Google con este email, se aceptan solas.</p>' +
            '</div>' +
            '<button type="button" class="pi-close" title="Ocultar">✕</button>';

        banner.querySelector('.pi-close').addEventListener('click', function () {
            sessionStorage.setItem(DISMISS_KEY, '1');
            banner.remove();
        });
        wireResendButtons(banner);

        var anchor = document.querySelector('main') || document.body;
        anchor.insertBefore(banner, anchor.firstChild);
    }

    function init() {
        fetch(API_LIST, { credentials: 'same-origin' })
            .then(function (r) { return r.ok ? r.json() : { invitations: [] }; })
            .then(function (data) {
                var invitations = data.invitations || [];
                if (!invitations.length) return;
                injectStyles();
                // Prioridad: si hay overlay de upgrade, convertirlo en guía;
                // si no, banner informativo arriba del contenido.
                if (!replaceUpgradeOverlay(invitations)) {
                    insertBanner(invitations);
                }
            })
            .catch(function () { /* silencioso: el banner nunca debe romper la página */ });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
