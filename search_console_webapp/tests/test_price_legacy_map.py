"""
Tests del grandfathering de precios (PRICE_ID_LEGACY_MAP)

Garantiza que al subir precios (rotar PRICE_ID_* a los nuevos) los clientes
existentes con price IDs antiguos siguen resolviendo su plan en los webhooks
en lugar de degradarse a 'free'.
"""

import os
from unittest.mock import patch

import pytest

REQUIRED_ENV = {
    'STRIPE_SECRET_KEY': 'sk_test_dummy',
    'STRIPE_PUBLISHABLE_KEY': 'pk_test_dummy',
    'STRIPE_WEBHOOK_SECRET': 'whsec_dummy',
    'PRICE_ID_BASIC': 'price_new_basic_m',
    'PRICE_ID_PREMIUM': 'price_new_premium_m',
    'PRICE_ID_BASIC_MONTHLY': 'price_new_basic_m',
    'PRICE_ID_BASIC_ANNUAL': 'price_new_basic_a',
    'PRICE_ID_PREMIUM_MONTHLY': 'price_new_premium_m',
    'PRICE_ID_PREMIUM_ANNUAL': 'price_new_premium_a',
    'PRICE_ID_BUSINESS_MONTHLY': 'price_new_business_m',
    'PRICE_ID_BUSINESS_ANNUAL': 'price_new_business_a',
    'STRIPE_ENTERPRISE_PRODUCT_ID': 'prod_enterprise_dummy',
    'CUSTOMER_PORTAL_RETURN_URL': 'https://example.com/billing',
}


def _make_config(legacy_map_json=None):
    env = dict(REQUIRED_ENV)
    if legacy_map_json is not None:
        env['PRICE_ID_LEGACY_MAP'] = legacy_map_json
    with patch.dict(os.environ, env, clear=False):
        # Asegurar que la var no se hereda de un test anterior
        if legacy_map_json is None:
            os.environ.pop('PRICE_ID_LEGACY_MAP', None)
        from stripe_config import StripeConfig
        return StripeConfig()


class TestPriceLegacyMap:

    def test_without_legacy_map_behaves_as_before(self):
        config = _make_config()
        mapping = config.get_price_to_plan_map()
        assert mapping['price_new_basic_m'] == 'basic'
        assert mapping['price_new_business_a'] == 'business'
        assert 'price_old_basic_m' not in mapping

    def test_legacy_prices_resolve_their_plan(self):
        config = _make_config(
            '{"price_old_basic_m": "basic", "price_old_premium_a": "premium",'
            ' "price_old_business_m": "business"}'
        )
        mapping = config.get_price_to_plan_map()
        # Clientes grandfathered siguen reconociéndose
        assert mapping['price_old_basic_m'] == 'basic'
        assert mapping['price_old_premium_a'] == 'premium'
        assert mapping['price_old_business_m'] == 'business'
        # Y los precios nuevos conviven
        assert mapping['price_new_premium_m'] == 'premium'

    def test_current_prices_win_on_collision(self):
        # Si un price ID aparece en ambos sitios, manda la config actual
        config = _make_config('{"price_new_basic_m": "premium"}')
        mapping = config.get_price_to_plan_map()
        assert mapping['price_new_basic_m'] == 'basic'

    def test_invalid_json_is_ignored_not_fatal(self):
        config = _make_config('{esto no es json}')
        assert config.price_id_legacy_map == {}
        # Y la config sigue funcionando
        assert config.get_price_to_plan_map()['price_new_basic_m'] == 'basic'

    def test_invalid_plans_are_dropped(self):
        config = _make_config('{"price_old_x": "superplan", "price_old_y": "basic", "": "basic"}')
        assert config.price_id_legacy_map == {'price_old_y': 'basic'}

    def test_non_dict_json_is_ignored(self):
        config = _make_config('["price_old_x"]')
        assert config.price_id_legacy_map == {}
