"""
Tests de fiabilidad del camino de error de LLM Monitoring (Fase A).

Contexto: en el análisis de Fini (2026-08-21) anthropic completó 54/59 prompts.
Causa raíz: (1) el 529 "overloaded" de Anthropic se clasificaba como no
reintentable, (2) 3 fallos consecutivos abrían el circuit breaker (cooldown
120s) y los reintentos post-batch del engine (3s/6s) rebotaban contra el
breaker abierto sin tocar la API, (3) los clientes sin timeout explícito
podían colgar un slot de concurrencia 600s (default del SDK).

Estos tests fijan el comportamiento corregido.
"""

import time
import unittest
from unittest.mock import patch

from services.llm_providers.retry_handler import (
    CircuitBreaker,
    RetryConfig,
    classify_error,
)


class TestClassifyErrorOverloaded(unittest.TestCase):
    """El 529/overloaded de Anthropic debe ser reintentable (server_error)."""

    def test_anthropic_529_full_message(self):
        # Mensaje real del SDK de Anthropic
        err = Exception(
            "Error code: 529 - {'type': 'error', 'error': "
            "{'type': 'overloaded_error', 'message': 'Overloaded'}}"
        )
        self.assertEqual(classify_error(err), 'server_error')

    def test_overloaded_word_alone(self):
        self.assertEqual(classify_error(Exception("Overloaded")), 'server_error')

    def test_overloaded_error_type(self):
        self.assertEqual(classify_error(Exception("overloaded_error")), 'server_error')

    # Regresión: las clasificaciones previas no deben cambiar
    def test_rate_limit_still_rate_limit(self):
        self.assertEqual(classify_error(Exception("429 Too Many Requests")), 'rate_limit')

    def test_daily_quota_still_non_retryable_class(self):
        self.assertEqual(
            classify_error(Exception("Quota exceeded for requests_per_model_per_day")),
            'quota_exhausted'
        )

    def test_timeout_still_timeout(self):
        self.assertEqual(classify_error(Exception("Request timed out")), 'timeout')

    def test_500_still_server_error(self):
        self.assertEqual(classify_error(Exception("500 Internal Server Error")), 'server_error')

    def test_unknown_still_non_retryable(self):
        self.assertEqual(classify_error(Exception("something exotic happened")), 'non_retryable')

    def test_auth_still_non_retryable(self):
        self.assertEqual(classify_error(Exception("invalid api key")), 'non_retryable')

    def test_server_error_is_configured_retryable(self):
        self.assertIn('server_error', RetryConfig.RETRYABLE_ERRORS)


class TestProviderTimeouts(unittest.TestCase):
    """Los timeouts por provider deben superar la generación más larga legítima."""

    def test_anthropic_timeout_covers_long_generations(self):
        # Con max_tokens=8000 una respuesta larga puede tardar ~2 min:
        # un timeout < 150s mataría justo los prompts agénticos que fallaban
        self.assertGreaterEqual(RetryConfig.PROVIDER_TIMEOUTS['anthropic'], 150)

    def test_all_providers_have_bounded_timeouts(self):
        for provider in ('openai', 'google', 'anthropic', 'perplexity'):
            timeout = RetryConfig.PROVIDER_TIMEOUTS[provider]
            # acotado: ni colgado (600s default SDK) ni suicida (<30s)
            self.assertGreaterEqual(timeout, 30, provider)
            self.assertLessEqual(timeout, 300, provider)

    def test_anthropic_client_gets_explicit_timeout(self):
        with patch(
            'services.llm_providers.anthropic_provider.get_model_pricing_from_db',
            return_value={'input': 0.000003, 'output': 0.000015}
        ):
            from services.llm_providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(api_key='sk-test-dummy', model='claude-sonnet-4-6')
            self.assertEqual(
                float(provider.client.timeout),
                float(RetryConfig.PROVIDER_TIMEOUTS['anthropic'])
            )

    def test_perplexity_client_gets_explicit_timeout(self):
        with patch(
            'services.llm_providers.perplexity_provider.get_model_pricing_from_db',
            return_value={'input': 0.000001, 'output': 0.000001}
        ):
            from services.llm_providers.perplexity_provider import PerplexityProvider
            provider = PerplexityProvider(api_key='pplx-test-dummy', model='sonar-pro')
            self.assertEqual(
                float(provider.client.timeout),
                float(RetryConfig.PROVIDER_TIMEOUTS['perplexity'])
            )


class TestCircuitBreakerCooldownQuery(unittest.TestCase):
    """seconds_until_half_open: la pieza que permite al engine esperar al breaker."""

    def _fresh_breaker(self, threshold=3, cooldown=120):
        cb = CircuitBreaker()
        cb.failure_threshold = threshold
        cb.cooldown_seconds = cooldown
        return cb

    def test_closed_circuit_returns_zero(self):
        cb = self._fresh_breaker()
        self.assertEqual(cb.seconds_until_half_open('anthropic'), 0.0)

    def test_open_circuit_returns_remaining_cooldown(self):
        cb = self._fresh_breaker(threshold=3, cooldown=120)
        for _ in range(3):
            cb.record_failure('anthropic')
        remaining = cb.seconds_until_half_open('anthropic')
        self.assertGreater(remaining, 100)
        self.assertLessEqual(remaining, 120)

    def test_below_threshold_returns_zero(self):
        cb = self._fresh_breaker(threshold=3)
        cb.record_failure('anthropic')
        cb.record_failure('anthropic')
        self.assertEqual(cb.seconds_until_half_open('anthropic'), 0.0)

    def test_expired_cooldown_returns_zero(self):
        cb = self._fresh_breaker(threshold=3, cooldown=120)
        for _ in range(3):
            cb.record_failure('anthropic')
        # Simular que el cooldown ya pasó
        cb._last_failure_time['anthropic'] = time.time() - 121
        self.assertEqual(cb.seconds_until_half_open('anthropic'), 0.0)

    def test_success_resets_to_zero(self):
        cb = self._fresh_breaker(threshold=3)
        for _ in range(3):
            cb.record_failure('anthropic')
        cb.record_success('anthropic')
        self.assertEqual(cb.seconds_until_half_open('anthropic'), 0.0)

    def test_per_provider_isolation(self):
        cb = self._fresh_breaker(threshold=3)
        for _ in range(3):
            cb.record_failure('anthropic')
        # El breaker de anthropic abierto NO afecta a google
        self.assertGreater(cb.seconds_until_half_open('anthropic'), 0)
        self.assertEqual(cb.seconds_until_half_open('google'), 0.0)


class TestEngineBreakerAwareDelay(unittest.TestCase):
    """La fórmula de espera del retry post-batch del engine."""

    @staticmethod
    def _compute_delay(attempt, breaker_wait):
        # Réplica exacta de la fórmula en engine.py (si se cambia allí, cambiar aquí)
        delay = 3 * attempt
        if breaker_wait > 0:
            delay = min(max(delay, breaker_wait + 5), 300)
        return delay

    def test_no_breaker_keeps_fast_delays(self):
        self.assertEqual(self._compute_delay(1, 0.0), 3)
        self.assertEqual(self._compute_delay(2, 0.0), 6)

    def test_open_breaker_waits_past_cooldown(self):
        # Cooldown restante 115s → esperar 120s (cooldown + margen), no 3s
        self.assertEqual(self._compute_delay(1, 115.0), 120.0)

    def test_wait_is_capped(self):
        # Cooldowns configurados absurdamente largos no bloquean el cron
        self.assertEqual(self._compute_delay(1, 900.0), 300)

    def test_small_breaker_wait_never_reduces_delay(self):
        # breaker_wait pequeño: se respeta el delay base si es mayor
        self.assertEqual(self._compute_delay(2, 0.5), 6)


if __name__ == '__main__':
    unittest.main()
