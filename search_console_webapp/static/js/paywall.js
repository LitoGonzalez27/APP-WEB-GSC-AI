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
                highlight: false
            },
            premium: { 
                name: 'Premium Plan', 
                price: '€49.99', 
                period: '/month',
                quota: '2,950 RU/month',
                description: 'Perfect for agencies',
                highlight: true
            },
            business: {
                name: 'Business Plan',
                price: '€139.99',
                period: '/month',
                quota: '8,000 RU/month',
                description: 'For high-volume teams',
                highlight: false
            }
        };
        
        const planCards = upgradeOptions.map(planKey => {
            const plan = plans[planKey];
            return `
                <a href="/billing/checkout/${planKey}?interval=monthly" class="plan-card ${plan.highlight ? 'premium-highlight' : ''}">
                    ${plan.highlight ? '<div class="plan-badge">MOST POPULAR</div>' : ''}
                    <h4>${plan.name}</h4>
                    <div class="plan-price">
                        ${plan.price}<span>${plan.period}</span>
                    </div>
                    <div class="plan-features">${plan.quota}</div>
                    <div class="plan-description">${plan.description}</div>
                    <div class="plan-cta">Start ${plan.name} →</div>
                </a>
            `;
        }).join('');
        
        modal.innerHTML = `
            <div class="paywall-content">
                <div class="paywall-header">
                    <h3 class="paywall-title-premium">${featureName} is Premium</h3>
                    <p>Unlock powerful AI-driven insights with a paid plan</p>
                </div>
                
                <div class="paywall-body">
                    <div class="feature-benefits">
                        <h4>What you'll get:</h4>
                        <ul>
                            <li><strong>AI Overview Analysis</strong> - Track Google's AI mentions of your domain</li>
                            <li><strong>Manual AI Projects</strong> - Keyword-by-keyword tracking and monitoring</li>
                            <li><strong>Competitor Analysis</strong> - See who dominates AI results in your niche</li>
                            <li><strong>Historical Data</strong> - Track changes and trends over time</li>
                            <li><strong>Excel Exports</strong> - Professional reports for clients and teams</li>
                        </ul>
                    </div>
                    
                    <div class="upgrade-options">
                        ${planCards}
                    </div>
                    
                    <div class="paywall-info">
                        <p><strong>What are RU?</strong> Request Units = API calls to analyze keywords (1 API Call = 1 keyword analyzed). Cached results use 0 RU, so you save on repeated searches!</p>
                    </div>
                </div>
                
                <div class="paywall-footer">
                    <button class="btn-secondary" onclick="window.PaywallManager.hidePaywallModal()">
                        Maybe Later
                    </button>
                    <a href="https://clicandseo.com/pricing/" target="_blank" rel="noopener noreferrer" class="btn-primary">
                        View All Plans
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
            <div class="paywall-content">
                <div class="paywall-header">
                    <h3>📊 Monthly Limit Reached</h3>
                    <p>You've used all your Request Units for this month</p>
                </div>
                
                <div class="paywall-body">
                    <div class="quota-status">
                        <div class="quota-bar">
                            <div class="quota-fill" style="width: ${percentage}%; background: #ef4444;"></div>
                        </div>
                        <div class="quota-text">
                            <strong>${quotaUsed}/${quotaLimit} RU used (${percentage}%)</strong>
                        </div>
                        <p style="color: #666; margin-top: 0.5rem;">
                            Your quota resets on your next billing date
                        </p>
                    </div>
                    
                    <div class="quota-explanation">
                        <h4>🚀 Upgrade to continue analyzing:</h4>
                        <ul>
                            <li>✅ <strong>Higher monthly limits</strong> - Never run out of RU again</li>
                            <li>✅ <strong>All premium features</strong> - Full access to AI Overview tools</li>
                            <li>✅ <strong>Priority support</strong> - Get help when you need it</li>
                            <li>✅ <strong>Advanced exports</strong> - Professional Excel reports</li>
                        </ul>
                    </div>
                    
                    <div class="upgrade-options">
                        <a href="/billing/checkout/premium" class="plan-card premium-highlight">
                            <div class="plan-badge">RECOMMENDED</div>
                            <h4>Premium Plan</h4>
                            <div class="plan-price">
                                €49.99<span>/month</span>
                            </div>
                            <div class="plan-features">2,950 RU/month</div>
                            <div class="plan-description">Perfect for agencies and power users</div>
                            <div class="plan-cta">Upgrade Now →</div>
                        </a>
                    </div>
                </div>
                
                <div class="paywall-footer">
                    <button class="btn-secondary" onclick="window.PaywallManager.hidePaywallModal()">
                        Close
                    </button>
                    <a href="/billing" class="btn-secondary">
                        Manage Billing
                    </a>
                </div>
            </div>
        `;
        
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
