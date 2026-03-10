// Paywall functionality
class PaywallManager {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('PaywallManager initialized');
    }
    
    showPaywallModal(upgradeOptions = ['basic', 'premium', 'business'], featureName = 'This feature') {
        const modal = this.createPaywallModal(upgradeOptions, featureName);
        
        // ✅ NUEVO: Guardar featureName para restaurar estado al cerrar
        modal.dataset.featureName = featureName;
        
        document.body.appendChild(modal);
        
        // Auto-remove after 30 seconds or on click outside
        setTimeout(() => this.hidePaywallModal(), 30000);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.hidePaywallModal();
        });
    }
    
    createPaywallModal(upgradeOptions, featureName = 'This feature') {
        const modal = document.createElement('div');
        modal.className = 'paywall-modal';
        modal.id = 'paywall-modal';

        const plans = {
            basic: {
                name: 'Basic Plan',
                price: '€29.99',
                period: '/month',
                quota: '1,225 RU/month',
                description: 'Perfect for small businesses',
                icon: 'fas fa-rocket',
                highlight: false
            },
            premium: {
                name: 'Premium Plan',
                price: '€49.99',
                period: '/month',
                quota: '2,950 RU/month',
                description: 'Perfect for agencies',
                icon: 'fas fa-crown',
                highlight: true
            },
            business: {
                name: 'Business Plan',
                price: '€139.99',
                period: '/month',
                quota: '8,000 RU/month',
                description: 'For high-volume teams',
                icon: 'fas fa-building',
                highlight: false
            }
        };

        const renderCard = (planKey) => {
            const plan = plans[planKey];
            if (!plan) return '';
            return `
                <a href="/billing/checkout/${planKey}?interval=monthly" class="pw-plan-card ${plan.highlight ? 'pw-plan-card--highlight' : ''}">
                    ${plan.highlight ? '<div class="pw-plan-badge">MOST POPULAR</div>' : ''}
                    <div class="pw-plan-icon"><i class="${plan.icon}"></i></div>
                    <h4>${plan.name}</h4>
                    <div class="pw-plan-price">
                        <span class="pw-price-amount">${plan.price}</span>
                        <span class="pw-price-period">${plan.period}</span>
                    </div>
                    <div class="pw-plan-quota">${plan.quota}</div>
                    <div class="pw-plan-desc">${plan.description}</div>
                    <div class="pw-plan-cta">
                        Start ${plan.name} <i class="fas fa-arrow-right"></i>
                    </div>
                </a>
            `;
        };

        // Order: Basic & Premium top (2 cols), Business bottom (1 col)
        const hasBusiness = upgradeOptions.includes('business');
        const topPlans = upgradeOptions.filter(p => p !== 'business');
        topPlans.sort((a, b) => {
            const order = { 'basic': 0, 'premium': 1 };
            return (order[a] ?? 99) - (order[b] ?? 99);
        });
        const topCards = topPlans.map(renderCard).join('');
        const businessCard = hasBusiness ? renderCard('business') : '';

        modal.innerHTML = `
            <div class="paywall-content pw-brandbook">
                <button class="pw-close-btn" onclick="window.PaywallManager.hidePaywallModal()" aria-label="Close">
                    <i class="fas fa-times"></i>
                </button>

                <div class="pw-header-dark">
                    <div class="pw-header-icon">
                        <i class="fas fa-lock"></i>
                    </div>
                    <h3>${featureName} is <em>Premium</em></h3>
                    <p>Unlock powerful AI-driven insights with a paid plan</p>
                </div>

                <div class="pw-body">
                    <div class="pw-benefits">
                        <h4>What you'll get</h4>
                        <ul class="pw-benefits-list">
                            <li>
                                <i class="fas fa-brain"></i>
                                <div><strong>AI Overview Analysis</strong><span>Track Google's AI mentions of your domain</span></div>
                            </li>
                            <li>
                                <i class="fas fa-crosshairs"></i>
                                <div><strong>Manual AI Projects</strong><span>Keyword-by-keyword tracking and monitoring</span></div>
                            </li>
                            <li>
                                <i class="fas fa-users"></i>
                                <div><strong>Competitor Analysis</strong><span>See who dominates AI results in your niche</span></div>
                            </li>
                            <li>
                                <i class="fas fa-chart-line"></i>
                                <div><strong>Historical Data</strong><span>Track changes and trends over time</span></div>
                            </li>
                            <li>
                                <i class="fas fa-file-excel"></i>
                                <div><strong>Excel Exports</strong><span>Professional reports for clients and teams</span></div>
                            </li>
                        </ul>
                    </div>

                    <div class="pw-plans-grid pw-plans-grid--two">
                        ${topCards}
                    </div>
                    ${hasBusiness ? `<div class="pw-plans-grid pw-plans-grid--single">${businessCard}</div>` : ''}

                    <div class="pw-info-box">
                        <i class="fas fa-info-circle"></i>
                        <p><strong>What are RU?</strong> Request Units = API calls to analyze keywords (1 API Call = 1 keyword analyzed). Cached results use 0 RU, so you save on repeated searches!</p>
                    </div>
                </div>

                <div class="pw-footer">
                    <button class="pw-btn-ghost" onclick="window.PaywallManager.hidePaywallModal()">
                        Maybe Later
                    </button>
                    <a href="https://clicandseo.com/pricing/" target="_blank" rel="noopener noreferrer" class="pw-btn-primary">
                        <i class="fas fa-external-link-alt"></i> View All Plans
                    </a>
                </div>
            </div>
        `;

        return modal;
    }
    
    showQuotaExceededModal(quotaInfo = {}) {
        const modal = this.createQuotaExceededModal(quotaInfo);
        document.body.appendChild(modal);
    }
    
    createQuotaExceededModal(quotaInfo) {
        const modal = document.createElement('div');
        modal.className = 'quota-exceeded-modal paywall-modal';
        modal.id = 'quota-exceeded-modal';

        const quotaUsed = quotaInfo.quota_used || 0;
        const quotaLimit = quotaInfo.quota_limit || 0;
        const percentage = quotaLimit > 0 ? Math.round((quotaUsed / quotaLimit) * 100) : 100;

        modal.innerHTML = `
            <div class="paywall-content pw-brandbook">
                <button class="pw-close-btn" onclick="window.PaywallManager.hidePaywallModal()" aria-label="Close">
                    <i class="fas fa-times"></i>
                </button>

                <div class="pw-header-dark">
                    <div class="pw-header-icon">
                        <i class="fas fa-chart-pie"></i>
                    </div>
                    <h3>Monthly Limit Reached</h3>
                    <p>You've used all your Request Units for this month</p>
                </div>

                <div class="pw-body">
                    <div class="pw-quota-card">
                        <div class="pw-quota-label">
                            <span>Usage</span>
                            <span class="pw-quota-numbers">${quotaUsed.toLocaleString()} / ${quotaLimit.toLocaleString()} RU</span>
                        </div>
                        <div class="pw-quota-bar">
                            <div class="pw-quota-fill" style="width: ${percentage}%;"></div>
                        </div>
                        <p class="pw-quota-reset">
                            <i class="fas fa-clock"></i>
                            Your quota resets on your next billing date
                        </p>
                    </div>

                    <div class="pw-benefits">
                        <h4>Upgrade to continue analyzing</h4>
                        <ul class="pw-benefits-list">
                            <li>
                                <i class="fas fa-bolt"></i>
                                <div><strong>Higher monthly limits</strong><span>Never run out of RU again</span></div>
                            </li>
                            <li>
                                <i class="fas fa-brain"></i>
                                <div><strong>All premium features</strong><span>Full access to AI Overview tools</span></div>
                            </li>
                            <li>
                                <i class="fas fa-headset"></i>
                                <div><strong>Priority support</strong><span>Get help when you need it</span></div>
                            </li>
                            <li>
                                <i class="fas fa-file-excel"></i>
                                <div><strong>Advanced exports</strong><span>Professional Excel reports</span></div>
                            </li>
                        </ul>
                    </div>

                    <a href="/billing/checkout/premium?interval=monthly" class="pw-upgrade-card">
                        <div class="pw-upgrade-badge">RECOMMENDED</div>
                        <div class="pw-upgrade-info">
                            <h4>Premium Plan</h4>
                            <div class="pw-upgrade-price">
                                <span class="pw-price-amount">€49.99</span>
                                <span class="pw-price-period">/month</span>
                            </div>
                            <div class="pw-upgrade-quota">2,950 RU/month</div>
                        </div>
                        <div class="pw-upgrade-cta">
                            Upgrade Now <i class="fas fa-arrow-right"></i>
                        </div>
                    </a>
                </div>

                <div class="pw-footer">
                    <button class="pw-btn-ghost" onclick="window.PaywallManager.hidePaywallModal()">
                        Maybe Later
                    </button>
                    <a href="/billing" class="pw-btn-outline">
                        <i class="fas fa-cog"></i> Manage Billing
                    </a>
                </div>
            </div>
        `;

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) window.PaywallManager.hidePaywallModal();
        });

        return modal;
    }
    
    hidePaywallModal() {
        const modals = document.querySelectorAll('.paywall-modal');
        
        modals.forEach(modal => {
            // ✅ NUEVO: Restaurar estado según el feature
            const featureName = modal.dataset.featureName;
            
            if (featureName && featureName.includes('AI Overview')) {
                console.log('🔄 Paywall cerrado para AI Overview - cambiando a "View Plans"');
                
                // Restaurar overlay y cambiar botón a "View Plans"
                if (window.resetAIOverlay) {
                    window.resetAIOverlay();
                } else {
                    // Fallback: restaurar overlay manualmente
                    const overlay = document.getElementById('aiOverlay');
                    const progressOverlay = document.getElementById('aiProgressOverlay');
                    
                    if (progressOverlay) {
                        progressOverlay.classList.remove('active');
                    }
                    
                    if (overlay) {
                        overlay.classList.remove('hidden');
                    }
                }
                
                // ✅ NUEVO: Cambiar botón después de un pequeño delay para asegurar que el overlay esté restaurado
                setTimeout(() => {
                    this.changeAIOverviewToViewPlans();
                }, 100);
            }
            
            modal.remove();
        });
    }
    
    // ✅ NUEVO: Cambiar botón AI Overview a "View Plans"
    changeAIOverviewToViewPlans() {
        const executeBtn = document.getElementById('executeAIBtn');
        
        if (executeBtn) {
            // Cambiar texto y estilo
            executeBtn.innerHTML = `
                <i class="fas fa-crown"></i>
                View Plans
            `;
            
            // Añadir clase CTA de Manual AI (negro con texto verde)
            executeBtn.className = 'btn-view-plans-ai';
            
            // Quitar cualquier event listener anterior
            executeBtn.onclick = null;
            executeBtn.removeEventListener('click', executeBtn._oldClickHandler);
            
            // Añadir nuevo event listener
            const newClickHandler = (e) => {
                e.preventDefault();
                console.log('🎯 Redirigiendo a pricing desde View Plans button');
                window.location.href = 'https://clicandseo.com/pricing/';
            };
            
            executeBtn._oldClickHandler = newClickHandler;
            executeBtn.addEventListener('click', newClickHandler);
            
            // También añadir onclick como fallback
            executeBtn.setAttribute('onclick', "window.location.href='https://clicandseo.com/pricing/'");
            
            console.log('🎯 Botón AI Overview cambiado a "View Plans" con redirection a pricing');
        } else {
            console.error('❌ No se encontró el botón executeAIBtn para cambiar a View Plans');
        }
    }
}

// Initialize globally
window.PaywallManager = new PaywallManager();

// Helper functions for modules
window.showPaywall = (featureName, upgradeOptions = ['basic', 'premium', 'business']) => window.PaywallManager.showPaywallModal(upgradeOptions, featureName);
window.showQuotaExceeded = (info) => window.PaywallManager.showQuotaExceededModal(info);
