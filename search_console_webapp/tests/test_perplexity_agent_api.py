"""
Perplexity sobre el Agent API (migración desde Sonar Chat Completions, 2026-09).

Los fixtures son respuestas reales del endpoint POST /v1/agent guardadas el
2026-09-13 (tests/fixtures/fanout/app-perplexity-agent-api-*.json).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.llm_providers.locale_helpers import create_locale_context
from services.llm_providers.perplexity_provider import (
    PerplexityProvider,
    parse_agent_response,
    resolve_preset,
)
from services.llm_providers.retry_handler import circuit_breaker

FIXTURES = Path(__file__).parent / 'fixtures' / 'fanout'


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """El breaker es un singleton global: aislar cada test."""
    yield
    circuit_breaker.record_success('perplexity')


def _fixture(preset: str) -> dict:
    return json.loads((FIXTURES / f'app-perplexity-agent-api-{preset}.json').read_text())


def _provider(model='sonar') -> PerplexityProvider:
    with patch('services.llm_providers.perplexity_provider.get_model_pricing_from_db',
               return_value={'input': 0.000001, 'output': 0.000001}):
        return PerplexityProvider(api_key='pplx-test', model=model)


def _http_response(status=200, payload=None, text=''):
    response = MagicMock(spec=requests.Response)
    response.status_code = status
    response.text = text or json.dumps(payload or {})
    response.json.return_value = payload
    return response


class TestResolvePreset:
    @pytest.mark.parametrize('model_id,preset', [
        ('sonar', 'fast'), ('sonar-pro', 'low'), ('sonar-reasoning-pro', 'medium'),
        ('sonar-deep-research', 'high'), ('low', 'low'), (None, 'fast'), ('unknown', 'fast'),
    ])
    def test_mapping(self, model_id, preset):
        assert resolve_preset(model_id) == preset


class TestParseAgentResponse:
    @pytest.mark.parametrize('preset,queries,rounds,fetches,calls,cost,tool_cost,tokens', [
        ('fast', 1, 1, 0, 1, 0.00539, 0.0025, 3614),
        ('low', 5, 2, 1, 2, 0.01337, 0.00849, 20300),
        ('medium', 12, 6, 3, 6, 0.03041, 0.02313, 44911),
    ])
    def test_real_responses(self, preset, queries, rounds, fetches, calls, cost, tool_cost, tokens):
        parsed = parse_agent_response(_fixture(preset))

        searches = [q for q in parsed['search_queries'] if q['action'] == 'search']
        assert len(searches) == queries
        assert max(q['round'] for q in searches) == rounds
        assert parsed['page_opens'] == fetches
        assert parsed['search_calls'] == calls
        assert parsed['search_used'] is True
        assert parsed['cost_usd'] == cost
        assert parsed['search_cost_usd'] == tool_cost
        assert parsed['tokens'] == tokens
        assert parsed['api_model_reported'] == 'openai/gpt-5.6-luna'
        assert parsed['content'].strip()

    def test_every_search_carries_its_round_urls(self):
        parsed = parse_agent_response(_fixture('low'))
        for q in parsed['search_queries']:
            if q['action'] == 'search':
                assert q['query'] and q['sources']
            else:
                assert q['url'].startswith('https://') and q['sources'] == []

    def test_sources_are_unique_normalized_and_keep_sonar_shape(self):
        parsed = parse_agent_response(_fixture('fast'))
        urls = [s['url'] for s in parsed['sources']]
        assert len(urls) == len(set(urls)) == 10
        for s in parsed['sources']:
            assert s['provider'] == 'perplexity'   # la UI pinta "Citation" con este valor
            assert 'utm_' not in s['url']
            assert s['query_round'] == 1

    def test_cited_flag_follows_inline_markers(self):
        parsed = parse_agent_response(_fixture('fast'))
        cited = [s for s in parsed['sources'] if s['cited']]
        assert 0 < len(cited) < len(parsed['sources'])

    def test_answer_without_search(self):
        parsed = parse_agent_response({
            'model': 'x', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Hola'}]}],
            'usage': {'input_tokens': 3, 'output_tokens': 2, 'total_tokens': 5},
        })
        assert parsed['search_used'] is False
        assert parsed['search_calls'] == 0
        assert parsed['sources'] == [] and parsed['search_queries'] == []
        assert parsed['cost_usd'] is None


class TestExecuteQuery:
    def test_payload_without_locale_is_plain_input(self):
        payload = _provider().build_payload('hola', None)
        assert payload == {'preset': 'fast', 'input': 'hola', 'max_output_tokens': 16000}

    def test_locale_goes_as_system_message_and_user_location(self):
        payload = _provider().build_payload('hola', create_locale_context('fr', 'FR'))
        # `instructions` sustituye el prompt del preset (pierde las citas): no usarlo
        assert 'instructions' not in payload
        assert [m['role'] for m in payload['input']] == ['system', 'user']
        assert payload['input'][1]['content'] == 'hola'
        assert payload['tools'] == [{'type': 'web_search', 'user_location': {'country': 'FR'}}]

    @patch('services.llm_providers.perplexity_provider.requests.post')
    def test_success_returns_standard_contract(self, mock_post):
        mock_post.return_value = _http_response(200, _fixture('low'))
        result = _provider().execute_query('q', locale=create_locale_context('es', 'ES'))

        assert result['success'] is True
        assert result['model_used'] == 'sonar'
        assert result['api_model_reported'] == 'openai/gpt-5.6-luna'
        assert result['cost_usd'] == 0.01337
        assert result['prompt_strategy'] == 'system_user_geo'
        assert result['search_country'] == 'ES'
        assert len(result['search_queries']) == 6
        for key in ('content', 'sources', 'tokens', 'input_tokens', 'output_tokens', 'response_time_ms'):
            assert key in result

    @patch('services.llm_providers.perplexity_provider.requests.post')
    def test_http_error_keeps_status_for_retry_classification(self, mock_post):
        mock_post.return_value = _http_response(
            401, {'error': {'message': 'Invalid API key provided.', 'type': 'invalid_api_key', 'code': 401}}
        )
        result = _provider().execute_query('q')

        assert result['success'] is False
        assert 'HTTP 401' in result['error'] and 'invalid_api_key' in result['error']
        assert mock_post.call_count == 1   # no reintentable

    @patch('services.llm_providers.perplexity_provider.requests.post')
    def test_timeout_is_reported_as_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout()
        with patch('services.llm_providers.retry_handler.time.sleep'):
            result = _provider().execute_query('q')

        assert result['success'] is False
        assert 'timed out' in result['error'].lower()

    @patch('services.llm_providers.perplexity_provider.requests.post')
    def test_health_check_does_not_pay_a_search(self, mock_post):
        mock_post.return_value = _http_response(200, _fixture('fast'))
        assert _provider().test_connection() is True
        assert mock_post.call_args.kwargs['json']['max_tool_calls'] == 0
