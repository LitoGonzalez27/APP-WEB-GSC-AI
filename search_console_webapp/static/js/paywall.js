// Paywall functionality
class PaywallManager {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('PaywallManager initialized');
    }
    
    showPaywallModal(upgradeOptions = ['basic', 'premium']) {
        const modal = this.createPaywallModal(upgradeOptions);
        document.body.appendChild(modal);
        
        // Auto-remove after 30 seconds or on click outside
        setTimeout(() => this.hidePaywallModal(), 30000);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.hidePaywallModal();
        });
    }
    
    createPaywallModal(upgradeOptions) {
        const modal = document.createElement('div');
        modal.className = 'paywall-modal';
        modal.id = 'paywall-modal';
        
        const plans = {
            basic: { name: 'Basic', price: '€29.99/mo', quota: '1,225 RU/month' },
            premium: { name: 'Premium', price: '€49.99/mo', quota: '2,950 RU/month' }
        };
        
        const planCards = upgradeOptions.map(plan => `
            <a href="/billing/checkout/${plan}" class="plan-card">
                <h4>${plans[plan].name} - ${plans[plan].price}</h4>
                <p>${plans[plan].quota}</p>
            </a>
        `).join('');
        
        modal.innerHTML = `
            <div class="paywall-content">
                <h3>🚀 Unlock Premium Features</h3>
                <p>This feature requires a paid plan to continue</p>
                <div class="upgrade-options">
                    ${planCards}
                </div>
                <button onclick="window.PaywallManager.hidePaywallModal()" 
                        style="margin-top: 1rem; background: none; border: none; color: #666;">
                    Maybe later
                </button>
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
        
        modal.innerHTML = `
            <div class="paywall-content">
                <h3>📊 Monthly Limit Reached</h3>
                <p>You've used all ${quotaInfo.quota_limit || 'your'} RU this month</p>
                <p>Upgrade to get more Request Units and continue analyzing</p>
                <div class="upgrade-options">
                    <a href="/billing/checkout/premium" class="plan-card">
                        <h4>Upgrade to Premium</h4>
                        <p>2,950 RU/month</p>
                    </a>
                </div>
                <a href="/billing" style="margin-top: 1rem; color: #666;">
                    Manage billing
                </a>
            </div>
        `;
        
        return modal;
    }
    
    hidePaywallModal() {
        const modals = document.querySelectorAll('.paywall-modal');
        modals.forEach(modal => modal.remove());
    }
}

// Initialize globally
window.PaywallManager = new PaywallManager();

// Helper functions for modules
window.showPaywall = (options) => window.PaywallManager.showPaywallModal(options);
window.showQuotaExceeded = (info) => window.PaywallManager.showQuotaExceededModal(info);
