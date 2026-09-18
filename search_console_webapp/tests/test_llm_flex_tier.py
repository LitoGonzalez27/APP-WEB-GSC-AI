"""
Flex processing de OpenAI en el cron (2026-09-18).

- Por defecto (llamadas interactivas) no se envía `service_tier`: cola estándar.
- Con `set_service_tier('flex')` la petición va con `service_tier='flex'` y timeout
  largo; el coste se calcula con el precio flex (mitad del registry) SOLO si la
  API confirma que sirvió en flex; el tier servido se devuelve para auditoría.
- Si flex no tiene capacidad (429 `resource_unavailable`, sin cargo) la misma
  petición se repite en la cola estándar (`auto`) al precio normal: nunca se
  pierde la respuesta.
- La ruta de búsqueda web (Responses API) aplica lo mismo; el descuento no toca
  el coste por llamada de la herramienta de búsqueda.
- El servicio propaga el tier a los providers; el engine lo guarda en
  execution_metadata.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.llm_providers import openai_provider as op  # noqa: E402
from services.llm_providers.openai_provider import OpenAIProvider  # noqa: E402

PRICING = {'input': 5e-06, 'output': 3e-05, 'search': 0.01}
FLEX_UNAVAILABLE = Exception(
    "Error code: 429 - {'error': {'message': 'The flex processing tier is currently unavailable. "
    "Please try again later.', 'type': 'rate_limit_error', 'code': 'resource_unavailable'}}"
)


def _response(tier='default', in_tok=100, out_tok=1000, content='respuesta'):
    r = MagicMock()
    r.service_tier = tier
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    r.usage.prompt_tokens = in_tok
    r.usage.completion_tokens = out_tok
    r.usage.total_tokens = in_tok + out_tok
    return r


@pytest.fixture
def provider():
    with patch('services.llm_providers.openai_provider.get_model_pricing_from_db', return_value=PRICING), \
         patch('services.llm_providers.openai_provider.resolve_model_id', return_value='gpt-5.5'), \
         patch('services.llm_providers.openai_provider.openai.OpenAI') as client_cls:
        p = OpenAIProvider(api_key='sk-test')
        p.client = client_cls.return_value
        yield p


class TestHelpers:
    def test_flex_unavailable_detection(self):
        assert op.is_flex_unavailable(FLEX_UNAVAILABLE)
        assert not op.is_flex_unavailable(Exception("Error code: 429 - insufficient_quota"))
        assert not op.is_flex_unavailable(Exception("Rate limit exceeded"))

    def test_price_factor_only_when_served_in_flex(self):
        assert op.tier_price_factor('flex') == 0.5
        assert op.tier_price_factor('default') == 1.0
        assert op.tier_price_factor(None) == 1.0

    def test_served_tier_normalization(self):
        assert op.served_service_tier('flex') == 'flex'
        assert op.served_service_tier(None) == 'default'
        assert op.served_service_tier(MagicMock()) == 'default'  # SDK sin el campo

    def test_invalid_tier_rejected(self, provider):
        with pytest.raises(ValueError):
            provider.set_service_tier('turbo')


class TestChatCompletions:
    def test_default_tier_sends_no_service_tier(self, provider):
        provider.client.chat.completions.create.return_value = _response()
        result = provider.execute_query('ventanas que aíslen del ruido')
        kwargs = provider.client.chat.completions.create.call_args.kwargs
        assert 'service_tier' not in kwargs
        assert kwargs['timeout'] == op.STANDARD_TIMEOUT_SECONDS
        assert result['success'] and result['service_tier'] == 'default'
        assert result['cost_usd'] == pytest.approx(100 * 5e-06 + 1000 * 3e-05)

    def test_flex_tier_sends_param_and_halves_cost(self, provider):
        provider.set_service_tier('flex')
        provider.client.chat.completions.create.return_value = _response(tier='flex')
        result = provider.execute_query('ventanas que aíslen del ruido')
        kwargs = provider.client.chat.completions.create.call_args.kwargs
        assert kwargs['service_tier'] == 'flex'
        assert kwargs['timeout'] == op.FLEX_TIMEOUT_SECONDS
        assert result['service_tier'] == 'flex'
        assert result['cost_usd'] == pytest.approx((100 * 5e-06 + 1000 * 3e-05) * 0.5)
        assert result['content'] == 'respuesta'

    def test_flex_requested_but_served_standard_costs_full_price(self, provider):
        # La API puede servir en la cola estándar aunque se pida flex: se cobra entero
        provider.set_service_tier('flex')
        provider.client.chat.completions.create.return_value = _response(tier='default')
        result = provider.execute_query('q')
        assert result['service_tier'] == 'default'
        assert result['cost_usd'] == pytest.approx(100 * 5e-06 + 1000 * 3e-05)

    def test_flex_unavailable_falls_back_to_standard_queue(self, provider):
        provider.set_service_tier('flex')
        provider.client.chat.completions.create.side_effect = [FLEX_UNAVAILABLE, _response(tier='default')]
        result = provider.execute_query('q')
        calls = provider.client.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs['service_tier'] == 'flex'
        assert calls[1].kwargs['service_tier'] == 'auto'
        assert calls[1].kwargs['timeout'] == op.STANDARD_TIMEOUT_SECONDS
        assert result['success'] and result['service_tier'] == 'default'
        assert result['cost_usd'] == pytest.approx(100 * 5e-06 + 1000 * 3e-05)

    def test_flex_timeout_falls_back_to_standard_queue(self, provider):
        # Un timeout en flex no debe encadenar reintentos en flex: se repite en la cola estándar
        import openai as openai_sdk
        provider.set_service_tier('flex')
        timeout_error = openai_sdk.APITimeoutError(request=MagicMock())
        provider.client.chat.completions.create.side_effect = [timeout_error, _response(tier='default')]
        result = provider.execute_query('q')
        calls = provider.client.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs['timeout'] == op.FLEX_TIMEOUT_SECONDS
        assert calls[1].kwargs['service_tier'] == 'auto'
        assert calls[1].kwargs['timeout'] == op.STANDARD_TIMEOUT_SECONDS
        assert result['success'] and result['service_tier'] == 'default'

    def test_standard_tier_timeout_is_not_retried_as_auto(self, provider):
        import openai as openai_sdk
        provider.client.chat.completions.create.side_effect = openai_sdk.APITimeoutError(request=MagicMock())
        provider.execute_query('q')
        assert all('service_tier' not in c.kwargs for c in provider.client.chat.completions.create.call_args_list)

    def test_other_errors_are_not_retried_as_auto(self, provider):
        provider.set_service_tier('flex')
        provider.client.chat.completions.create.side_effect = Exception(
            "Error code: 429 - {'error': {'type': 'insufficient_quota', 'code': 'credit_balance_exhausted'}}"
        )
        result = provider.execute_query('q')
        assert not result['success']
        assert provider.client.chat.completions.create.call_count == 1

    def test_health_check_ignores_tier(self, provider):
        provider.set_service_tier('flex')
        provider.client.chat.completions.create.return_value = _response()
        assert provider.test_connection() is True
        assert 'service_tier' not in provider.client.chat.completions.create.call_args.kwargs


class TestResponsesApiSearch:
    def _parsed(self):
        return {
            'content': 'texto', 'sources': [], 'search_queries': [], 'search_used': True,
            'search_calls': 1, 'page_opens': 0, 'billable_search_calls': 1,
            'input_tokens': 100, 'output_tokens': 1000, 'tokens': 1100, 'api_model_reported': 'gpt-5.5',
        }

    def test_search_flex_discount_on_tokens_only(self, provider):
        provider.set_service_tier('flex')
        with patch.object(provider, '_post_responses', return_value=({'service_tier': 'flex', 'output': []}, None)) as post, \
             patch('services.llm_providers.openai_provider.parse_responses_output', return_value=self._parsed()):
            result = provider._execute_with_search('q', None)
        body = post.call_args.args[0]
        assert body['service_tier'] == 'flex'
        assert post.call_args.kwargs['timeout'] == op.FLEX_TIMEOUT_SECONDS
        tokens = (100 * 5e-06 + 1000 * 3e-05) * 0.5
        assert result['search_cost_usd'] == pytest.approx(0.01)
        assert result['cost_usd'] == pytest.approx(tokens + 0.01)
        assert result['service_tier'] == 'flex'

    def test_search_flex_unavailable_falls_back(self, provider):
        provider.set_service_tier('flex')
        responses = [
            (None, "OpenAI API Error: HTTP 429 - resource_unavailable: flex tier unavailable"),
            ({'service_tier': 'default', 'output': []}, None),
        ]
        with patch.object(provider, '_post_responses', side_effect=responses) as post, \
             patch('services.llm_providers.openai_provider.parse_responses_output', return_value=self._parsed()):
            result = provider._execute_with_search('q', None)
        assert post.call_args_list[1].args[0]['service_tier'] == 'auto'
        assert result['success'] and result['service_tier'] == 'default'
        assert result['cost_usd'] == pytest.approx(100 * 5e-06 + 1000 * 3e-05 + 0.01)

    def test_search_flex_timeout_falls_back(self, provider):
        provider.set_service_tier('flex')
        responses = [
            (None, f"OpenAI request timed out after {op.FLEX_TIMEOUT_SECONDS}s"),
            ({'service_tier': 'default', 'output': []}, None),
        ]
        with patch.object(provider, '_post_responses', side_effect=responses) as post, \
             patch('services.llm_providers.openai_provider.parse_responses_output', return_value=self._parsed()):
            result = provider._execute_with_search('q', None)
        assert post.call_args_list[1].args[0]['service_tier'] == 'auto'
        assert result['success'] and result['service_tier'] == 'default'

    def test_search_default_tier_untouched(self, provider):
        with patch.object(provider, '_post_responses', return_value=({'output': []}, None)) as post, \
             patch('services.llm_providers.openai_provider.parse_responses_output', return_value=self._parsed()):
            provider._execute_with_search('q', None)
        assert 'service_tier' not in post.call_args.args[0]
        assert post.call_args.kwargs == {}


class TestServiceWiring:
    def test_cron_service_tier_default_and_override(self, monkeypatch):
        from services.llm_monitoring_service import cron_service_tier
        monkeypatch.delenv('OPENAI_CRON_SERVICE_TIER', raising=False)
        assert cron_service_tier() == 'flex'
        monkeypatch.setenv('OPENAI_CRON_SERVICE_TIER', 'default')
        assert cron_service_tier() == 'default'

    def test_service_propagates_tier_to_providers(self):
        from services.llm_monitoring_service import MultiLLMMonitoringService
        openai_p, google_p = MagicMock(), MagicMock()
        with patch('services.llm_monitoring_service.LLMProviderFactory.create_all_providers',
                   return_value={'openai': openai_p, 'google': google_p}):
            MultiLLMMonitoringService(api_keys=None, service_tier='flex')
            openai_p.set_service_tier.assert_called_once_with('flex')
            google_p.set_service_tier.assert_called_once_with('flex')
            openai_p.reset_mock()
            MultiLLMMonitoringService(api_keys=None)  # interactivo: cola estándar
            openai_p.set_service_tier.assert_not_called()

    def test_base_provider_ignores_tier(self):
        from services.llm_providers.base_provider import BaseLLMProvider
        assert BaseLLMProvider.set_service_tier(MagicMock(), 'flex') is None


class TestFlexAlerts:
    """Check `openai_flex_share` y fila del email (cron_alerts)."""
    RUN = {'id': 71, 'started_at': __import__('datetime').datetime(2026, 9, 18, 4, 0),
           'completed_at': __import__('datetime').datetime(2026, 9, 18, 4, 30)}

    @staticmethod
    def _conn(row):
        cur = MagicMock(); cur.fetchone.return_value = row
        conn = MagicMock(); conn.cursor.return_value = cur
        return conn

    def test_full_flex_run_has_no_alert_and_reports_saving(self, monkeypatch):
        import cron_alerts
        monkeypatch.delenv('OPENAI_CRON_SERVICE_TIER', raising=False)
        conn = self._conn({'rows_total': 219, 'rows_flex': 219, 'cost_total': 5.74, 'cost_flex': 5.74})
        assert cron_alerts._check_flex_share(self.RUN, 0.7, lambda: conn) is None
        stats = cron_alerts._load_flex_stats(self.RUN, lambda: conn)
        assert stats['share'] == 1.0 and stats['saved_usd'] == pytest.approx(5.74) and stats['extra_usd'] == 0
        row = cron_alerts._format_flex_row(stats)
        assert '219/219 (100%)' in row and 'ahorro $5.74' in row and 'de más' not in row

    def test_low_flex_share_is_medium_alert_with_extra_cost(self, monkeypatch):
        import cron_alerts
        monkeypatch.delenv('OPENAI_CRON_SERVICE_TIER', raising=False)
        # 100 en flex (2,60 $) + 119 en estándar (6,20 $): de más = 3,10 $
        conn = self._conn({'rows_total': 219, 'rows_flex': 100, 'cost_total': 8.80, 'cost_flex': 2.60})
        alert = cron_alerts._check_flex_share(self.RUN, 0.7, lambda: conn)
        assert alert['type'] == 'openai_flex_share' and alert['severity'] == 'medium'
        assert '100/219' in alert['metric'] and '119 respuesta' in alert['message'] and '$3.10' in alert['message']

    def test_no_alert_when_cron_does_not_request_flex(self, monkeypatch):
        import cron_alerts
        monkeypatch.setenv('OPENAI_CRON_SERVICE_TIER', 'default')
        conn = self._conn({'rows_total': 219, 'rows_flex': 0, 'cost_total': 11.5, 'cost_flex': 0})
        assert cron_alerts._check_flex_share(self.RUN, 0.7, lambda: conn) is None

    def test_no_openai_rows_means_no_stats_and_no_alert(self, monkeypatch):
        import cron_alerts
        monkeypatch.delenv('OPENAI_CRON_SERVICE_TIER', raising=False)
        conn = self._conn({'rows_total': 0, 'rows_flex': 0, 'cost_total': 0, 'cost_flex': 0})
        assert cron_alerts._load_flex_stats(self.RUN, lambda: conn) is None
        assert cron_alerts._check_flex_share(self.RUN, 0.7, lambda: conn) is None
        assert cron_alerts._format_flex_row(None) == ''

    def test_check_is_registered_and_db_errors_never_raise(self, monkeypatch):
        import cron_alerts
        monkeypatch.delenv('OPENAI_CRON_SERVICE_TIER', raising=False)
        broken = MagicMock(); broken.cursor.side_effect = RuntimeError('db down')
        assert cron_alerts._check_flex_share(self.RUN, 0.7, lambda: broken) is None
        cfg = cron_alerts._get_config()
        assert cfg['flex_min_share'] == 0.7
        with patch.object(cron_alerts, '_check_flex_share', return_value={'type': 'openai_flex_share', 'severity': 'medium'}) as chk:
            alerts = cron_alerts._run_checks(self.RUN, cfg, lambda: broken)
        assert chk.called and any(a['type'] == 'openai_flex_share' for a in alerts)


class TestEngineMetadata:
    def test_execution_metadata_keeps_served_tier(self):
        import inspect
        from services.llm_monitoring import engine
        src = inspect.getsource(engine)
        assert "_execution_metadata['service_tier'] = llm_result['service_tier']" in src
