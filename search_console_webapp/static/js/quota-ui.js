/**
 * QUOTA UI MANAGER - FASE 4
 * ========================
 * 
 * Maneja la UI para quotas, warnings, y bloqueos en el frontend.
 * Incluye mensajes de soft limit (80%) y bloqueo (100%).
 */

/**
 * Configuración de mensajes UX
 */
const QUOTA_MESSAGES = {
    softLimit: {
        title: "⚠️ Approaching Usage Limit",
        message: "You've used {percentage}% of your monthly quota ({remaining} requests remaining).",
        action: "Consider upgrading to continue seamless analysis."
    },
    hardLimit: {
        title: "🚫 Usage Limit Reached", 
        message: "You've reached your monthly limit of {limit} requests.",
        action: "Upgrade your plan to continue using AI Overview and Manual AI features."
    },
    freeBlocked: {
        title: "🔒 Premium Feature",
        message: "AI Overview and Manual AI are available with Basic, Premium and Business plans.",
        action: "Upgrade to access advanced SERP analysis features."
    },
    enterpriseBlocked: {
        title: "📞 Custom Quota Needed",
        message: "Your Enterprise plan requires custom quota configuration.",
        action: "Contact support to configure your usage limits."
    }
};

/**
 * URLs de upgrade por plan
 */
const UPGRADE_URLS = {
    free: "/billing",
    basic: "/billing/checkout/premium?interval=monthly", 
    premium: "/billing/checkout/business?interval=monthly",
    enterprise: "/contact"
};

/**
 * Muestra un banner de warning de quota
 */
function showQuotaWarning(quotaInfo) {
    if (!shouldShowQuotaUI(quotaInfo)) {
        return;
    }
    if (isQuotaWarningDismissed(quotaInfo)) {
        return;
    }
    // Evitar warnings duplicados
    if (document.querySelector('.quota-warning-modal-overlay')) {
        return;
    }

    const percentage = quotaInfo.percentage;
    const remaining = quotaInfo.remaining_ru;
    const plan = quotaInfo.plan;
    
    let config;
    if (percentage >= 100) {
        config = QUOTA_MESSAGES.hardLimit;
    } else {
        config = QUOTA_MESSAGES.softLimit;
    }

    ensureQuotaModalStyles();

    const modal = document.createElement('div');
    modal.className = 'quota-warning-modal-overlay';
    modal._quotaInfo = quotaInfo;
    modal.innerHTML = `
        <div class="quota-warning-modal">
            <div class="quota-warning-header">
                <h4>${config.title}</h4>
                <button class="quota-warning-close" aria-label="Close" onclick="dismissQuotaWarning()">&times;</button>
            </div>
            <p class="quota-warning-message">
                ${config.message
                    .replace('{percentage}', Math.round(percentage))
                    .replace('{remaining}', remaining)
                    .replace('{limit}', quotaInfo.quota_limit)}
            </p>
            <p class="quota-warning-action">${config.action}</p>
            <div class="quota-warning-buttons">
                <button class="btn btn-primary quota-upgrade-btn" onclick="handleQuotaUpgrade('${plan}')">
                    ${percentage >= 100 ? 'Upgrade Now' : 'Upgrade Plan'}
                </button>
                <a class="btn btn-secondary" href="mailto:info@clicandseo.com">
                    Contact Support
                </a>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.classList.add('active'));
}

/**
 * Muestra modal de bloqueo por quota
 */
function showQuotaBlockModal(errorData) {
    const quotaInfo = errorData.quota_info || {};
    const actionRequired = errorData.action_required || 'upgrade';
    const plan = quotaInfo.plan || 'free';

    if (!shouldShowQuotaUI({ ...quotaInfo, plan })) {
        return;
    }

    let config;
    if (plan === 'free') {
        config = QUOTA_MESSAGES.freeBlocked;
    } else if (plan === 'enterprise') {
        config = QUOTA_MESSAGES.enterpriseBlocked;
    } else {
        config = QUOTA_MESSAGES.hardLimit;
    }

    ensureQuotaModalStyles();
    const modal = document.createElement('div');
    modal.className = 'quota-block-modal-overlay';
    modal.innerHTML = `
        <div class="quota-block-modal">
            <div class="quota-block-header">
                <h3>${config.title}</h3>
            </div>
            <div class="quota-block-content">
                <p class="quota-block-message">
                    ${config.message.replace('{limit}', quotaInfo.quota_limit || 'N/A')}
                </p>
                <p class="quota-block-action">${config.action}</p>
                
                ${quotaInfo.quota_limit ? `
                    <div class="quota-usage-info">
                        <div class="quota-progress-bar">
                            <div class="quota-progress-fill" style="width: 100%"></div>
                        </div>
                        <p class="quota-usage-text">
                            ${quotaInfo.quota_used || 0} / ${quotaInfo.quota_limit} requests used this month
                        </p>
                    </div>
                ` : ''}
            </div>
            <div class="quota-block-buttons">
                ${actionRequired === 'contact_support'
                    ? `<a class="btn btn-primary" href="mailto:info@clicandseo.com">Contact Support</a>`
                    : `<button class="btn btn-primary" onclick="handleQuotaUpgrade('${plan}')">Upgrade Plan</button>`
                }
                <button class="btn btn-secondary" onclick="closeQuotaBlockModal()">
                    Close
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.classList.add('active'));

    // Focus en el modal para accesibilidad
    modal.querySelector('.btn').focus();
}

/**
 * Maneja el upgrade de plan
 */
function handleQuotaUpgrade(currentPlan) {
    const upgradeUrl = UPGRADE_URLS[currentPlan] || '/upgrade';
    
    if (currentPlan === 'enterprise') {
        // Para Enterprise, abrir en nueva pestaña
        window.open('/contact', '_blank');
    } else {
        // Para otros planes, navegar directamente
        window.location.href = upgradeUrl;
    }
}

/**
 * Cierra el modal de bloqueo
 */
function closeQuotaBlockModal() {
    const modal = document.querySelector('.quota-block-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 200);
    }
}

/**
 * Dismisses el banner de warning
 */
function dismissQuotaWarning() {
    const modal = document.querySelector('.quota-warning-modal-overlay');
    if (modal) {
        const quotaInfo = modal._quotaInfo || {};
        const key = getQuotaDismissKey(quotaInfo);
        sessionStorage.setItem(key, '1');
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 200);
    }
}

function ensureQuotaModalStyles() {
    if (document.getElementById('quota-modal-styles')) {
        return;
    }
    const style = document.createElement('style');
    style.id = 'quota-modal-styles';
    style.textContent = `
        .quota-warning-modal-overlay,
        .quota-block-modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(15, 23, 42, 0.45);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.2s ease;
        }
        .quota-warning-modal-overlay.active,
        .quota-block-modal-overlay.active {
            opacity: 1;
        }
        .quota-warning-modal,
        .quota-block-modal {
            background: #fff;
            border-radius: 16px;
            padding: 20px 22px;
            width: min(560px, 92vw);
            box-shadow: 0 20px 60px rgba(15, 23, 42, 0.2);
            transform: translateY(8px);
            transition: transform 0.2s ease;
        }
        .quota-warning-modal-overlay.active .quota-warning-modal,
        .quota-block-modal-overlay.active .quota-block-modal {
            transform: translateY(0);
        }
        .quota-warning-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .quota-warning-close {
            background: transparent;
            border: none;
            font-size: 22px;
            line-height: 1;
            cursor: pointer;
            color: #6b7280;
        }
        .quota-warning-message {
            margin: 8px 0;
            color: #111827;
            font-size: 14.5px;
        }
        .quota-warning-action {
            margin: 0 0 14px 0;
            color: #6b7280;
            font-size: 13.5px;
        }
        .quota-warning-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
    `;
    document.head.appendChild(style);
}

function isPaidFeatureSection() {
    const path = window.location.pathname || '';
    const allowed = [
        'manual-ai',
        'ai-mode',
        'ai-mode-projects',
        'llm-monitoring'
    ];
    return allowed.some(segment => path.includes(segment));
}

function shouldShowQuotaUI(quotaInfo = {}) {
    const plan = quotaInfo.plan || 'free';
    if (plan === 'free') {
        return false;
    }
    return isPaidFeatureSection();
}

function getQuotaDismissKey(quotaInfo = {}) {
    const plan = quotaInfo.plan || 'unknown';
    const used = quotaInfo.quota_used || 0;
    const limit = quotaInfo.quota_limit || 0;
    return `quotaWarningDismissed:${plan}:${used}:${limit}`;
}

function isQuotaWarningDismissed(quotaInfo = {}) {
    const key = getQuotaDismissKey(quotaInfo);
    return sessionStorage.getItem(key) === '1';
}

/**
 * Verifica errores de quota en respuestas de API
 */
function handleApiQuotaError(response, data) {
    if (response.status === 429 && data.quota_blocked) {
        console.warn('🚫 API call blocked by quota:', data);
        showQuotaBlockModal(data);
        return true; // Error manejado
    }
    return false; // No es error de quota
}

/**
 * Wrapper para fetch que maneja quotas automáticamente
 */
async function quotaAwareFetch(url, options = {}) {
    try {
        const response = await fetch(url, options);
        const data = await response.json();

        // Verificar errores de quota
        if (handleApiQuotaError(response, data)) {
            throw new Error('QUOTA_BLOCKED');
        }

        return { response, data };
    } catch (error) {
        if (error.message === 'QUOTA_BLOCKED') {
            throw error;
        }
        
        // Re-throw otros errores
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * Chequea el estado de quota del usuario y muestra warnings si es necesario
 * NOTA: Deshabilitado el aviso preventivo del 80% - Solo muestra cuando se alcanza el 100%
 */
async function checkUserQuotaStatus() {
    try {
        const response = await fetch('/api/quota/status');
        if (response.ok) {
            const quotaStatus = await response.json();
            
            // Solo mostrar warning si se alcanza el límite completo (100%)
            // Aviso preventivo del 80% deshabilitado por solicitud del admin
            if (quotaStatus.warning_info && quotaStatus.warning_info.percentage >= 100) {
                showQuotaWarning(quotaStatus.warning_info);
            }
        }
    } catch (error) {
        console.warn('Could not check quota status:', error);
    }
}

/**
 * Inicializa el sistema de quota UI
 */
function initQuotaUI() {
    // Verificar estado de quota al cargar la página
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkUserQuotaStatus);
    } else {
        checkUserQuotaStatus();
    }

    // Escuchar eventos de quota desde otros módulos
    // Solo mostrar cuando se alcance el 100% (aviso preventivo del 80% deshabilitado)
    window.addEventListener('quotaWarning', (event) => {
        if (event.detail && event.detail.percentage >= 100) {
            showQuotaWarning(event.detail);
        }
    });

    window.addEventListener('quotaBlocked', (event) => {
        showQuotaBlockModal(event.detail);
    });
}

// Auto-inicializar
initQuotaUI();

// Exponer funciones globalmente para uso desde otros módulos
window.QuotaUI = {
    showWarning: showQuotaWarning,
    showBlockModal: showQuotaBlockModal,
    handleApiError: handleApiQuotaError,
    quotaAwareFetch: quotaAwareFetch,
    checkStatus: checkUserQuotaStatus
};
