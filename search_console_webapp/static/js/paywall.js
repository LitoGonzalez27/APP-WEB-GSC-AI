// Paywall functionality
class PaywallManager {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('PaywallManager initialized');
    }
    
    showPaywallModal(upgradeOptions = ['basic', 'premium'], featureName = 'This feature') {
        const modal = this.createPaywallModal(upgradeOptions, featureName);
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
            }
        };
        
        const planCards = upgradeOptions.map(planKey => {
            const plan = plans[planKey];
            return `
                <a href="/billing/checkout/${planKey}" class="plan-card ${plan.highlight ? 'premium-highlight' : ''}">
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
                    <h3>🚀 ${featureName} is Premium</h3>
                    <p>Unlock powerful AI-driven insights with a paid plan</p>
                </div>
                
                <div class="paywall-body">
                    <div class="feature-benefits">
                        <h4>✨ What you'll get:</h4>
                        <ul>
                            <li>🔍 <strong>AI Overview Analysis</strong> - Track Google's AI mentions of your domain</li>
                            <li>🎯 <strong>Manual AI Projects</strong> - Keyword-by-keyword tracking and monitoring</li>
                            <li>📊 <strong>Competitor Analysis</strong> - See who dominates AI results in your niche</li>
                            <li>📈 <strong>Historical Data</strong> - Track changes and trends over time</li>
                            <li>📋 <strong>Excel Exports</strong> - Professional reports for clients and teams</li>
                        </ul>
                    </div>
                    
                    <div class="upgrade-options">
                        ${planCards}
                    </div>
                    
                    <div class="paywall-info">
                        <p><strong>💡 What are RU?</strong> Request Units = API calls to analyze keywords. Cached results use 0 RU, so you save on repeated searches!</p>
                    </div>
                </div>
                
                <div class="paywall-footer">
                    <button class="btn-secondary" onclick="window.PaywallManager.hidePaywallModal()">
                        Maybe Later
                    </button>
                    <a href="/billing" class="btn-secondary">
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
        modals.forEach(modal => modal.remove());
    }
}

// Initialize globally
window.PaywallManager = new PaywallManager();

// Helper functions for modules
window.showPaywall = (options, featureName) => window.PaywallManager.showPaywallModal(options, featureName);
window.showQuotaExceeded = (info) => window.PaywallManager.showQuotaExceededModal(info);
