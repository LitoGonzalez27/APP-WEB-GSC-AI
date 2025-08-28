#!/usr/bin/env python3
"""
STRIPE CONFIGURATION MANAGER
============================

Centraliza la configuración de Stripe y billing para ClicandSEO.
Lee variables de entorno y proporciona configuración consistente.
"""

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class StripeConfig:
    """Configuración centralizada de Stripe"""
    
    def __init__(self):
        """Inicializa configuración desde variables de entorno"""
        
        # Environment detection
        self.app_env = os.getenv('APP_ENV', 'staging')
        self.is_production = self.app_env == 'production'
        
        # Stripe Keys
        self.secret_key = os.getenv('STRIPE_SECRET_KEY')
        self.publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        # Price IDs
        self.price_id_basic = os.getenv('PRICE_ID_BASIC')
        self.price_id_premium = os.getenv('PRICE_ID_PREMIUM')
        
        # Enterprise
        self.enterprise_product_id = os.getenv('STRIPE_ENTERPRISE_PRODUCT_ID')
        
        # URLs
        self.customer_portal_return_url = os.getenv('CUSTOMER_PORTAL_RETURN_URL')
        
        # Control Flags
        self.billing_enabled = os.getenv('BILLING_ENABLED', 'false').lower() == 'true'
        self.enforce_quotas = os.getenv('ENFORCE_QUOTAS', 'false').lower() == 'true'
        self.aio_module_enabled = os.getenv('AIO_MODULE_ENABLED', 'true').lower() == 'true'
        
        # Experience Variables
        self.quota_soft_limit_pct = int(os.getenv('QUOTA_SOFT_LIMIT_PCT', '80'))
        self.quota_grace_period_hours = int(os.getenv('QUOTA_GRACE_PERIOD_HOURS', '24'))
        
        # Validate configuration
        self._validate_config()
        
        logger.info(f"🔧 Stripe config loaded - Environment: {self.app_env}")
        logger.info(f"🎛️ Billing enabled: {self.billing_enabled}, Enforce quotas: {self.enforce_quotas}")
    
    def _validate_config(self):
        """Valida que la configuración esté completa"""
        missing = []
        
        # Required Stripe keys
        if not self.secret_key:
            missing.append('STRIPE_SECRET_KEY')
        if not self.publishable_key:
            missing.append('STRIPE_PUBLISHABLE_KEY')
        if not self.webhook_secret:
            missing.append('STRIPE_WEBHOOK_SECRET')
        
        # Required Price IDs
        if not self.price_id_basic:
            missing.append('PRICE_ID_BASIC')
        if not self.price_id_premium:
            missing.append('PRICE_ID_PREMIUM')
        
        # Required Enterprise config
        if not self.enterprise_product_id:
            missing.append('STRIPE_ENTERPRISE_PRODUCT_ID')
        
        # URLs
        if not self.customer_portal_return_url:
            missing.append('CUSTOMER_PORTAL_RETURN_URL')
        
        if missing:
            logger.error(f"❌ Missing required environment variables: {', '.join(missing)}")
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        # Validate Stripe key format
        if self.is_production:
            if not self.secret_key.startswith('sk_live_'):
                logger.warning("⚠️ Using test key in production environment")
            if not self.publishable_key.startswith('pk_live_'):
                logger.warning("⚠️ Using test publishable key in production environment")
        else:
            if not self.secret_key.startswith('sk_test_'):
                logger.warning("⚠️ Using live key in staging environment")
            if not self.publishable_key.startswith('pk_test_'):
                logger.warning("⚠️ Using live publishable key in staging environment")
    
    def get_plan_price_ids(self) -> Dict[str, str]:
        """Retorna mapeo de planes a Price IDs"""
        return {
            'basic': self.price_id_basic,
            'premium': self.price_id_premium
            # Enterprise no tiene price_id fijo - tiene múltiples precios custom
        }
    
    def get_plan_limits(self) -> Dict[str, int]:
        """Retorna límites de RU por plan"""
        return {
            'free': 0,
            'basic': 1225,
            'premium': 2950,
            'enterprise': None  # Enterprise usa custom_quota_limit
        }
    
    def get_plan_prices(self) -> Dict[str, float]:
        """Retorna precios en EUR por plan"""
        return {
            'free': 0.0,
            'basic': 29.99,
            'premium': 59.99,
            'enterprise': None  # Enterprise precio custom
        }
    
    def is_enterprise_product(self, product_id: str) -> bool:
        """Verifica si un product_id corresponde a Enterprise"""
        return product_id == self.enterprise_product_id
    
    def can_user_access_billing(self) -> bool:
        """Verifica si el billing está habilitado"""
        return self.billing_enabled
    
    def should_enforce_quotas(self) -> bool:
        """Verifica si debe enforcer límites de quotas"""
        return self.enforce_quotas
    
    def should_show_ai_features(self) -> bool:
        """Verifica si debe mostrar features de AI Overview"""
        return self.aio_module_enabled
    
    def get_quota_soft_limit_threshold(self, quota_limit: int) -> int:
        """Calcula el threshold para soft limit warning"""
        return int(quota_limit * (self.quota_soft_limit_pct / 100))
    
    def to_dict(self) -> Dict:
        """Retorna configuración como diccionario (sin claves sensibles)"""
        return {
            'app_env': self.app_env,
            'is_production': self.is_production,
            'billing_enabled': self.billing_enabled,
            'enforce_quotas': self.enforce_quotas,
            'aio_module_enabled': self.aio_module_enabled,
            'quota_soft_limit_pct': self.quota_soft_limit_pct,
            'quota_grace_period_hours': self.quota_grace_period_hours,
            'customer_portal_return_url': self.customer_portal_return_url,
            'enterprise_product_id': self.enterprise_product_id,
            'plan_limits': self.get_plan_limits(),
            'plan_prices': self.get_plan_prices()
        }

# Global instance
stripe_config = StripeConfig()

def get_stripe_config() -> StripeConfig:
    """Retorna la instancia global de configuración"""
    return stripe_config

# Helper functions for backward compatibility
def is_billing_enabled() -> bool:
    """Verifica si billing está habilitado"""
    return stripe_config.can_user_access_billing()

def should_enforce_quotas() -> bool:
    """Verifica si debe enforcer quotas"""
    return stripe_config.should_enforce_quotas()

def get_plan_limits() -> Dict[str, int]:
    """Retorna límites por plan"""
    return stripe_config.get_plan_limits()

def get_plan_price_id(plan: str) -> Optional[str]:
    """Retorna Price ID para un plan"""
    price_ids = stripe_config.get_plan_price_ids()
    return price_ids.get(plan)

# Testing function
def test_stripe_config():
    """Función para probar la configuración"""
    print("🧪 TESTING STRIPE CONFIGURATION")
    print("=" * 50)
    
    try:
        config = get_stripe_config()
        config_dict = config.to_dict()
        
        print(f"🌍 Environment: {config_dict['app_env']}")
        print(f"🏭 Is Production: {config_dict['is_production']}")
        print(f"💳 Billing Enabled: {config_dict['billing_enabled']}")
        print(f"🚫 Enforce Quotas: {config_dict['enforce_quotas']}")
        print(f"🤖 AI Module Enabled: {config_dict['aio_module_enabled']}")
        
        print(f"\n📊 Plan Limits:")
        for plan, limit in config_dict['plan_limits'].items():
            print(f"   {plan}: {limit} RU")
        
        print(f"\n💰 Plan Prices:")
        for plan, price in config_dict['plan_prices'].items():
            print(f"   {plan}: €{price}")
        
        print(f"\n🔗 URLs:")
        print(f"   Portal Return: {config_dict['customer_portal_return_url']}")
        
        print(f"\n🏢 Enterprise:")
        print(f"   Product ID: {config_dict['enterprise_product_id']}")
        
        print(f"\n✅ Configuration loaded successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

if __name__ == "__main__":
    test_stripe_config()
