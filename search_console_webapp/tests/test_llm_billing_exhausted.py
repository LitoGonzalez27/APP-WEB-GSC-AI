"""
Cuenta de proveedor sin crédito (incidente OpenAI 2026-09-11).

Antes: el 429 `insufficient_quota` se clasificaba como rate limit, se reintentaba,
abría el breaker 120s y el engine volvía a chocar: 38/240 errores, sin alerta.
Ahora: se detecta como `billing_exhausted`, se abre el breaker con cooldown largo,
el resto de tareas del provider falla al instante con un mensaje claro, el engine
no las reintenta y cron_alerts envía una alerta específica.
"""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# engine importa database, que exige DATABASE_URL al importarse (no conecta)
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from cron_alerts import _check_provider_billing
from services.llm_providers.retry_handler import (
    BILLING_EXHAUSTED_ERROR_PREFIX,
    CircuitBreaker,
    classify_error,
    circuit_breaker,
    note_health_check_failure,
    with_retry,
)

# Mensaje real guardado en producción el 2026-09-11
OPENAI_NO_CREDIT = (
    "OpenAI API Error: Error code: 429 - {'error': {'message': 'You have no credits remaining. "
    "Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.', "
    "'type': 'insufficient_quota', 'param': None, 'code': 'credit_balance_exhausted'}}"
)
ANTHROPIC_NO_CREDIT = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Your credit balance is too low to access the Anthropic API.'}}"
)
GEMINI_RPM = (
    "429 You exceeded your current quota, please check your plan and billing details. "
    "Quota exceeded for metric: generate_content_free_tier_requests, limit: 10 per minute"
)


@pytest.fixture(autouse=True)
def _reset_global_breaker():
    yield
    for provider in ('openai', 'anthropic', 'fake'):
        circuit_breaker.record_success(provider)


class TestClassification:
    @pytest.mark.parametrize('message', [OPENAI_NO_CREDIT, ANTHROPIC_NO_CREDIT])
    def test_no_credit_messages(self, message):
        assert classify_error(Exception(message)) == 'billing_exhausted'

    def test_gemini_per_minute_quota_is_not_billing(self):
        # Menciona "billing details" pero es un límite por minuto
        assert classify_error(Exception(GEMINI_RPM)) != 'billing_exhausted'

    def test_plain_rate_limit_unchanged(self):
        assert classify_error(Exception("429 Too Many Requests")) == 'rate_limit'


class TestBreaker:
    def test_billing_trip_uses_long_cooldown(self):
        cb = CircuitBreaker(cooldown_seconds=120, billing_cooldown_seconds=1800)
        cb.trip_billing_exhausted('openai', OPENAI_NO_CREDIT)

        assert cb.is_open('openai')
        assert cb.billing_exhausted_reason('openai') == OPENAI_NO_CREDIT
        assert cb.seconds_until_half_open('openai') > 1700

    def test_half_open_after_billing_cooldown_allows_probe(self):
        cb = CircuitBreaker(billing_cooldown_seconds=1800)
        cb.trip_billing_exhausted('openai', OPENAI_NO_CREDIT)
        cb._last_failure_time['openai'] -= 1801

        assert cb.billing_exhausted_reason('openai') is None
        assert cb.is_open('openai') is False

    def test_success_after_recharge_clears_billing_state(self):
        cb = CircuitBreaker(cooldown_seconds=120, billing_cooldown_seconds=1800)
        cb.trip_billing_exhausted('openai', OPENAI_NO_CREDIT)
        cb.record_success('openai')

        assert cb.billing_exhausted_reason('openai') is None
        assert cb.get_status('openai')['cooldown_seconds'] == 120

    def test_isolated_per_provider(self):
        cb = CircuitBreaker()
        cb.trip_billing_exhausted('openai', OPENAI_NO_CREDIT)
        assert cb.billing_exhausted_reason('anthropic') is None


class _FakeProvider:
    def __init__(self, error):
        self.calls = 0
        self.error = error

    def get_provider_name(self):
        return 'fake'

    @with_retry
    def execute_query(self, query):
        self.calls += 1
        return {'success': False, 'error': self.error}


class TestWithRetry:
    def test_no_credit_is_not_retried_and_short_circuits_next_calls(self):
        provider = _FakeProvider(OPENAI_NO_CREDIT)
        with patch('services.llm_providers.retry_handler.time.sleep') as sleep:
            first = provider.execute_query('q1')
            second = provider.execute_query('q2')

        assert provider.calls == 1          # la 2ª ni toca la API
        sleep.assert_not_called()           # sin backoff inútil
        for result in (first, second):
            assert result['success'] is False
            assert result['billing_exhausted'] is True
            assert result['error'].startswith(f'{BILLING_EXHAUSTED_ERROR_PREFIX}: fake: ')


class TestHealthCheck:
    def test_health_check_failure_by_credit_trips_breaker(self):
        note_health_check_failure('openai', Exception(OPENAI_NO_CREDIT))
        assert circuit_breaker.billing_exhausted_reason('openai')

    def test_other_health_check_failures_do_not_trip(self):
        note_health_check_failure('openai', Exception('Request timed out'))
        assert circuit_breaker.billing_exhausted_reason('openai') is None

    @patch('services.llm_providers.openai_provider.openai.OpenAI')
    @patch('services.llm_providers.openai_provider.get_model_pricing_from_db',
           return_value={'input': 0.0, 'output': 0.0})
    def test_openai_health_check_makes_a_real_minimal_call(self, _pricing, openai_cls):
        from services.llm_providers.openai_provider import OpenAIProvider
        client = openai_cls.return_value
        provider = OpenAIProvider(api_key='sk-test', model='gpt-5.5')

        assert provider.test_connection() is True
        client.models.list.assert_not_called()
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs['model'] == 'gpt-5.5' and kwargs['max_completion_tokens'] == 16


class TestCronAlert:
    @staticmethod
    def _run():
        now = datetime.utcnow()
        return {'started_at': now - timedelta(hours=1), 'completed_at': now}

    def test_alert_when_billing_errors_in_run(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{'llm_provider': 'openai', 'n': 38, 'sample': 'x'}]
        conn = MagicMock()
        conn.cursor.return_value = cur

        alert = _check_provider_billing(self._run(), lambda: conn)

        assert alert['type'] == 'provider_billing_exhausted'
        assert alert['severity'] == 'high'
        assert 'openai (38' in alert['metric']
        assert cur.execute.call_args.args[1][2] == f'{BILLING_EXHAUSTED_ERROR_PREFIX}%'

    def test_no_alert_without_billing_errors(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value = cur

        assert _check_provider_billing(self._run(), lambda: conn) is None


class TestEngineSkipsRetries:
    def test_tasks_of_providers_without_credit_are_not_retried(self):
        from services.llm_monitoring.engine import split_billing_exhausted

        circuit_breaker.trip_billing_exhausted('openai', OPENAI_NO_CREDIT)
        failed = [
            {'task': {'llm_name': 'openai', 'query_text': 'a'}, 'error': 'x'},
            {'task': {'llm_name': 'anthropic', 'query_text': 'b'}, 'error': 'y'},
            {'task': {'llm_name': 'openai', 'query_text': 'c'}, 'error': 'x'},
        ]

        retry, skipped = split_billing_exhausted(failed)

        assert [i['task']['llm_name'] for i in retry] == ['anthropic']
        assert [i['task']['query_text'] for i in skipped] == ['a', 'c']

    def test_nothing_skipped_when_all_providers_have_credit(self):
        from services.llm_monitoring.engine import split_billing_exhausted

        failed = [{'task': {'llm_name': 'anthropic', 'query_text': 'b'}, 'error': 'y'}]
        assert split_billing_exhausted(failed) == (failed, [])
