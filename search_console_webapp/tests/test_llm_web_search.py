"""
Búsqueda web en los providers de LLM Monitoring (P3, 2026-09-13).

- Parsers puros contra respuestas reales guardadas en tests/fixtures/fanout/ (P1).
- Regresión del interruptor: con search_mode 'off' (o cualquier valor que no sea
  'auto') cada provider hace exactamente la llamada de siempre, sin herramientas.
- Llamadas con búsqueda: cuerpo enviado, coste (tokens + búsquedas), fallback de
  modelo en OpenAI, continuación de pause_turn en Anthropic y URLs de Gemini.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.llm_providers.anthropic_provider import (
    AnthropicProvider,
    merge_turns,
    parse_messages_response,
)
from services.llm_providers.google_provider import (
    GoogleProvider,
    parse_generate_content,
    resolve_grounding_sources,
)
from services.llm_providers.locale_helpers import build_system_instruction, create_locale_context
from services.llm_providers.openai_provider import OpenAIProvider, parse_responses_output
from services.llm_providers.perplexity_provider import PerplexityProvider, preset_for_search_mode
from services.llm_providers.retry_handler import circuit_breaker
from services.llm_providers.web_search import build_search_result, normalize_search_mode

FIXTURES = Path(__file__).parent / 'fixtures' / 'fanout'
PRICING = {'input': 2 / 1_000_000, 'output': 10 / 1_000_000, 'search': 10 / 1_000}
LOCALE_ES = create_locale_context('es', 'ES')


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def _isolate_circuit_breaker():
    yield
    for provider in ('openai', 'anthropic', 'google', 'perplexity'):
        circuit_breaker.record_success(provider)


@pytest.fixture(autouse=True)
def _no_retry_sleep():
    with patch('services.llm_providers.retry_handler.time.sleep'):
        yield


# ─── Interruptor ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('value,expected', [
    ('auto', 'auto'), ('off', 'off'), (None, 'off'), ('', 'off'), ('AUTO', 'off'), ('memory', 'off'),
])
def test_only_exact_auto_enables_search(value, expected):
    assert normalize_search_mode(value) == expected


# ─── Parsers con respuestas reales ────────────────────────────────────────────

class TestOpenAIParser:
    def test_gpt55_search_calls_queries_and_pages(self):
        parsed = parse_responses_output(_fixture('p1-openai-gpt-5.5-comercial-es.json'))
        searches = [q for q in parsed['search_queries'] if q['action'] == 'search']

        assert parsed['search_used'] is True
        assert parsed['search_calls'] == 7            # llamadas de tipo search (rondas)
        assert len(searches) == 28                    # sub-consultas de action.queries
        assert parsed['page_opens'] == 4              # open_page + find_in_page
        assert parsed['billable_search_calls'] == 11  # todas las llamadas a la herramienta
        assert parsed['input_tokens'] == 75298 and parsed['output_tokens'] == 3232
        assert parsed['api_model_reported'] == 'gpt-5.5-2026-04-23'

        # Todas las sub-consultas de una llamada comparten sus fuentes
        first_round = [q for q in searches if q['round'] == 1]
        assert len(first_round) == 4 and len({tuple(q['sources']) for q in first_round}) == 1
        assert first_round[0]['sources'][0] == 'https://negociosypymes.es/mejor-software-facturacion'

        find = next(q for q in parsed['search_queries'] if q['action'] == 'find_in_page')
        assert find['query'] == 'declaración responsable' and find['url'].startswith('https://www.billin.net/')

    def test_sources_are_only_cited_urls(self):
        parsed = parse_responses_output(_fixture('p1-openai-gpt-5.5-comercial-es.json'))
        assert len(parsed['sources']) == 8
        assert all(s['cited'] and s['provider'] == 'openai' for s in parsed['sources'])
        assert all('utm_' not in s['url'] for s in parsed['sources'])
        quipu = next(s for s in parsed['sources'] if s['url'] == 'https://getquipu.com/es/plan-de-precios')
        assert quipu['query_round'] == 4 and quipu['title'] == 'Plan de precios | Quipu'

    def test_older_fixture_with_single_query(self):
        parsed = parse_responses_output(_fixture('app-openai-gpt-5-mini-web-search.json'))
        assert parsed['search_calls'] == 7 and parsed['page_opens'] == 0
        assert parsed['content'] and parsed['sources']

    def test_no_search(self):
        data = {'model': 'gpt-5.5', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': 'Hola', 'annotations': []}]}],
            'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}}
        parsed = parse_responses_output(data)
        assert parsed['search_used'] is False and parsed['search_queries'] == [] and parsed['sources'] == []
        assert parsed['billable_search_calls'] == 0 and parsed['content'] == 'Hola'


class TestAnthropicParser:
    def test_sonnet5_searches_results_and_citations(self):
        parsed = parse_messages_response(
            _fixture('p1-anthropic-claude-sonnet-5-web_search_20250305-comercial-es.json'))

        assert parsed['search_calls'] == 2 and parsed['billable_search_calls'] == 2
        assert [q['query'] for q in parsed['search_queries']] == [
            'mejor software facturación autónomos España 2026 comparativa',
            'Verifactu software facturación obligatorio autónomos 2026',
        ]
        assert len(parsed['search_queries'][0]['sources']) == 8
        assert len(parsed['search_queries'][1]['sources']) == 9
        assert len(parsed['sources']) == 7 and all(s['cited'] for s in parsed['sources'])
        # El texto junta todos los bloques text e ignora thinking y bloques de herramienta
        assert len(parsed['content']) == 4848
        assert parsed['input_tokens'] == 22000 and parsed['output_tokens'] == 2895

    def test_failed_search_has_no_sources(self):
        data = {'content': [
            {'type': 'server_tool_use', 'id': 's1', 'name': 'web_search', 'input': {'query': 'q'}},
            {'type': 'web_search_tool_result', 'tool_use_id': 's1',
             'content': {'type': 'web_search_tool_result_error', 'error_code': 'unavailable'}},
            {'type': 'text', 'text': 'respuesta'},
        ], 'usage': {'input_tokens': 5, 'output_tokens': 3, 'server_tool_use': {'web_search_requests': 0}}}
        parsed = parse_messages_response(data)
        assert parsed['search_queries'] == [{'round': 1, 'action': 'search', 'query': 'q', 'url': None, 'sources': []}]
        assert parsed['billable_search_calls'] == 0  # una búsqueda con error no se factura

    def test_merge_turns_sums_usage_and_keeps_block_order(self):
        first = {'content': [{'type': 'text', 'text': 'a'}], 'stop_reason': 'pause_turn',
                 'usage': {'input_tokens': 100, 'cache_read_input_tokens': 20, 'output_tokens': 10,
                           'server_tool_use': {'web_search_requests': 2}}}
        second = {'content': [{'type': 'text', 'text': 'b'}], 'stop_reason': 'end_turn', 'model': 'm',
                  'usage': {'input_tokens': 150, 'output_tokens': 30, 'server_tool_use': {'web_search_requests': 1}}}
        merged = merge_turns([first, second])
        assert [b['text'] for b in merged['content']] == ['a', 'b']
        assert merged['usage'] == {'input_tokens': 270, 'output_tokens': 40,
                                   'server_tool_use': {'web_search_requests': 3}}
        assert merged['stop_reason'] == 'end_turn' and merged['model'] == 'm'


class TestGeminiParser:
    def test_grounded_response(self):
        parsed = parse_generate_content(_fixture('p1-google-gemini-3.6-flash-comercial-es.json'))
        assert parsed['search_used'] is True and parsed['search_calls'] == 2
        assert all(q['sources'] == [] and q['round'] == 1 for q in parsed['search_queries'])
        assert len(parsed['sources']) == 14
        assert parsed['input_tokens'] == 544
        assert parsed['output_tokens'] == 1615 + 1666  # respuesta + razonamiento
        assert parsed['api_model_reported'] == 'gemini-3.6-flash'

    def test_model_chose_not_to_search(self):
        parsed = parse_generate_content(_fixture('p1-google-gemini-3.6-flash-sin-busqueda.json'))
        assert parsed['search_used'] is False and parsed['search_queries'] == [] and parsed['sources'] == []
        assert parsed['billable_search_calls'] == 0 and parsed['content']

    def test_billing_counts_repeated_queries(self):
        data = {'candidates': [{'content': {'parts': [{'text': 'x'}, {'text': 'razonando', 'thought': True}]},
                                'groundingMetadata': {'webSearchQueries': ['a', 'a', 'b']}}]}
        parsed = parse_generate_content(data)
        assert parsed['search_calls'] == 2 and parsed['billable_search_calls'] == 3
        assert parsed['content'] == 'x'

    def test_resolve_grounding_sources_merges_same_page(self):
        redirect = 'https://vertexaisearch.cloud.google.com/grounding-api-redirect/'
        sources = [
            {'url': redirect + 'A', 'provider': 'google', 'title': 'a.com', 'query_round': 1, 'cited': True},
            {'url': redirect + 'B', 'provider': 'google', 'title': 'a.com', 'query_round': 1, 'cited': True},
            {'url': redirect + 'C', 'provider': 'google', 'title': 'c.com', 'query_round': 1, 'cited': True},
        ]
        resolver = MagicMock(return_value={redirect + 'A': 'https://a.com/x', redirect + 'B': 'https://a.com/x'})
        merged = resolve_grounding_sources(sources, resolver=resolver)
        assert [s['url'] for s in merged] == ['https://a.com/x', redirect + 'C']


def test_build_search_result_falls_back_to_text_urls_when_no_sources():
    parsed = parse_generate_content(_fixture('p1-google-gemini-3.6-flash-sin-busqueda.json'))
    parsed['content'] += ' Más info en https://example.com/guia.'
    result = build_search_result(parsed, provider='google', cost_usd=0.01, search_cost_usd=0.0,
                                 model_used='gemini-3.6-flash', prompt_strategy='system_user',
                                 search_tool='gemini_google_search', search_country=None, started_at=0)
    assert result['sources'] == [{'url': 'https://example.com/guia', 'provider': 'extracted'}]
    assert result['search_used'] is False and result['success'] is True


# ─── Providers ────────────────────────────────────────────────────────────────

def _openai():
    with patch('services.llm_providers.openai_provider.get_model_pricing_from_db', return_value=PRICING), \
         patch.dict('os.environ', {'OPENAI_PREFERRED_MODEL': ''}):
        provider = OpenAIProvider(api_key='sk-test', model='gpt-5.5')
    provider.client = MagicMock()
    return provider


def _anthropic():
    with patch('services.llm_providers.anthropic_provider.get_model_pricing_from_db', return_value=PRICING):
        provider = AnthropicProvider(api_key='sk-ant-test', model='claude-sonnet-5')
    provider.client = MagicMock()
    return provider


def _google():
    with patch('services.llm_providers.google_provider.get_model_pricing_from_db', return_value=PRICING), \
         patch('services.llm_providers.google_provider.genai'):
        provider = GoogleProvider(api_key='g-test', model='gemini-3.6-flash')
    provider.model = MagicMock()
    return provider


class TestSearchOffKeepsTheOldCall:
    """Con 'off' no se toca la red por REST ni se envían herramientas."""

    @pytest.mark.parametrize('mode', ['off', None, 'AUTO', 'memory'])
    def test_openai(self, mode):
        provider = _openai()
        provider.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='hola'))],
            usage=MagicMock(prompt_tokens=1, completion_tokens=2, total_tokens=3))
        with patch('requests.post') as http:
            result = provider.execute_query('q', locale=LOCALE_ES, search_mode=mode)
        http.assert_not_called()
        kwargs = provider.client.chat.completions.create.call_args.kwargs
        assert 'tools' not in kwargs and kwargs['model'] == 'gpt-5.5'
        assert result['success'] and 'search_queries' not in result

    def test_openai_default_is_off(self):
        provider = _openai()
        provider.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='hola'))],
            usage=MagicMock(prompt_tokens=1, completion_tokens=2, total_tokens=3))
        with patch('requests.post') as http:
            provider.execute_query('q')
        http.assert_not_called()

    def test_anthropic(self):
        provider = _anthropic()
        provider.client.messages.create.return_value = MagicMock(
            content=[MagicMock(type='text', text='hola')], usage=MagicMock(input_tokens=1, output_tokens=2))
        with patch('requests.post') as http:
            result = provider.execute_query('q', locale=LOCALE_ES, search_mode='off')
        http.assert_not_called()
        assert 'tools' not in provider.client.messages.create.call_args.kwargs
        assert result['success'] and 'search_queries' not in result

    def test_google(self):
        provider = _google()
        provider.model.generate_content.return_value = MagicMock(text='hola', usage_metadata=None)
        with patch('requests.post') as http:
            result = provider.execute_query('q', locale=LOCALE_ES, search_mode='off')
        http.assert_not_called()
        assert result['success'] and result['prompt_strategy'] == 'prepended_system'

    def test_perplexity_preset(self):
        assert preset_for_search_mode('fast', 'off') == 'fast'
        assert preset_for_search_mode('fast', 'auto') == 'low'
        assert preset_for_search_mode('medium', 'auto') == 'medium'  # nunca rebaja
        assert preset_for_search_mode('fast', 'AUTO') == 'fast'


class TestOpenAISearch:
    def test_request_body_and_cost(self):
        provider = _openai()
        data = _fixture('p1-openai-gpt-5.5-comercial-es.json')
        with patch('services.llm_providers.openai_provider.post_json', return_value=(data, None)) as post:
            result = provider.execute_query('q', locale=LOCALE_ES, search_mode='auto')

        provider.client.chat.completions.create.assert_not_called()
        body = post.call_args.kwargs['body']
        assert body['model'] == 'gpt-5.5' and body['tool_choice'] == 'auto'
        assert body['tools'] == [{'type': 'web_search', 'user_location': {'type': 'approximate', 'country': 'ES'}}]
        assert body['include'] == ['web_search_call.action.sources']
        # Sin instrucción de buscar: solo la de idioma/país de siempre
        assert body['instructions'] == build_system_instruction(LOCALE_ES)
        assert post.call_args.kwargs['headers']['Authorization'] == 'Bearer sk-test'

        assert result['success'] and result['search_tool'] == 'openai_web_search'
        assert result['search_cost_usd'] == pytest.approx(11 * 0.01)
        assert result['cost_usd'] == pytest.approx(75298 * 2e-6 + 3232 * 10e-6 + 0.11, abs=1e-6)
        assert result['search_country'] == 'ES' and len(result['search_queries']) == 32

    def test_fallback_model_when_current_is_unavailable(self):
        provider = _openai()
        data = _fixture('app-openai-gpt-5-mini-web-search.json')
        responses = [(None, 'OpenAI API Error: HTTP 404 - model_not_found: The model does not exist'), (data, None)]
        with patch('services.llm_providers.openai_provider.post_json', side_effect=responses) as post, \
             patch('services.llm_providers.openai_provider.get_model_pricing_from_db', return_value=PRICING), \
             patch.dict('os.environ', {'OPENAI_FALLBACK_MODEL': 'gpt-4o'}):
            result = provider.execute_query('q', search_mode='auto')
        assert [c.kwargs['body']['model'] for c in post.call_args_list] == ['gpt-5.5', 'gpt-4o']
        assert result['success'] and result['model_used'] == 'gpt-4o'

    def test_http_error_is_returned_for_retry_classification(self):
        provider = _openai()
        error = 'OpenAI API Error: HTTP 429 - rate_limit_exceeded: slow down'
        with patch('services.llm_providers.openai_provider.post_json', return_value=(None, error)):
            result = provider.execute_query('q', search_mode='auto')
        assert result['success'] is False and '429' in result['error']


class TestAnthropicSearch:
    def test_request_body_and_cost(self):
        provider = _anthropic()
        data = _fixture('p1-anthropic-claude-sonnet-5-web_search_20250305-comercial-es.json')
        with patch('services.llm_providers.anthropic_provider.post_json', return_value=(data, None)) as post:
            result = provider.execute_query('q', locale=LOCALE_ES, search_mode='auto')

        provider.client.messages.create.assert_not_called()
        body = post.call_args.kwargs['body']
        assert body['tools'] == [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 5,
                                  'user_location': {'type': 'approximate', 'country': 'ES'}}]
        assert body['system'] and body['messages'] == [{'role': 'user', 'content': 'q'}]
        assert result['search_cost_usd'] == pytest.approx(0.02)
        assert result['cost_usd'] == pytest.approx(22000 * 2e-6 + 2895 * 10e-6 + 0.02, abs=1e-6)
        assert result['search_calls'] == 2 and len(result['sources']) == 7

    def test_pause_turn_is_continued_with_the_assistant_content(self):
        provider = _anthropic()
        paused = {'content': [{'type': 'server_tool_use', 'id': 's1', 'name': 'web_search', 'input': {'query': 'q1'}}],
                  'stop_reason': 'pause_turn', 'usage': {'input_tokens': 10, 'output_tokens': 1}}
        final = {'content': [{'type': 'text', 'text': 'respuesta'}], 'stop_reason': 'end_turn',
                 'usage': {'input_tokens': 20, 'output_tokens': 5, 'server_tool_use': {'web_search_requests': 1}}}
        with patch('services.llm_providers.anthropic_provider.post_json',
                   side_effect=[(paused, None), (final, None)]) as post:
            result = provider.execute_query('q', search_mode='auto')

        second_body = post.call_args_list[1].kwargs['body']
        assert second_body['messages'][-1] == {'role': 'assistant', 'content': paused['content']}
        assert result['success'] and result['content'] == 'respuesta'
        assert result['input_tokens'] == 30 and result['search_calls'] == 1


class TestGeminiSearch:
    def test_request_body_resolved_urls_and_cost(self):
        provider = _google()
        data = _fixture('p1-google-gemini-3.6-flash-comercial-es.json')
        with patch('services.llm_providers.google_provider.post_json', return_value=(data, None)) as post, \
             patch('services.llm_providers.google_provider.resolve_redirects',
                   side_effect=lambda urls: {u: f'https://site{i}.com/' for i, u in enumerate(urls)}):
            result = provider.execute_query('q', locale=LOCALE_ES, search_mode='auto')

        provider.model.generate_content.assert_not_called()
        body = post.call_args.kwargs['body']
        assert body['tools'] == [{'google_search': {}}]
        assert body['systemInstruction']['parts'][0]['text']
        assert body['generationConfig'] == {'maxOutputTokens': 65536, 'temperature': 0.7}
        assert 'gemini-3.6-flash:generateContent' in post.call_args.args[0]
        assert post.call_args.kwargs['headers']['x-goog-api-key'] == 'g-test'

        assert all('vertexaisearch' not in s['url'] for s in result['sources'])
        assert result['prompt_strategy'] == 'system_user' and result['search_country'] is None
        assert result['search_cost_usd'] == pytest.approx(0.02)

    def test_blocked_response_is_an_error(self):
        provider = _google()
        data = {'candidates': [], 'promptFeedback': {'blockReason': 'SAFETY'}}
        with patch('services.llm_providers.google_provider.post_json', return_value=(data, None)):
            result = provider.execute_query('q', search_mode='auto')
        assert result['success'] is False and 'safety' in result['error'].lower()


class TestPerplexitySearchMode:
    def test_auto_uses_low_preset_and_off_keeps_fast(self):
        with patch('services.llm_providers.perplexity_provider.get_model_pricing_from_db', return_value=PRICING):
            provider = PerplexityProvider(api_key='pplx-test', model='sonar')
        response = MagicMock(status_code=200)
        response.json.return_value = _fixture('app-perplexity-agent-api-low.json')
        with patch.object(provider, '_post', return_value=response) as post:
            auto = provider.execute_query('q', search_mode='auto')
            provider.execute_query('q', search_mode='off')
        presets = [c.args[0]['preset'] for c in post.call_args_list]
        assert presets == ['low', 'fast']
        assert auto['search_tool'] == 'perplexity_agent_low' and 'search_mode' not in auto


def test_missing_search_price_logs_and_costs_zero(caplog):
    provider = _anthropic()
    provider.pricing = {'input': 0.0, 'output': 0.0}
    data = _fixture('p1-anthropic-claude-sonnet-5-web_search_20250305-comercial-es.json')
    with patch('services.llm_providers.anthropic_provider.post_json', return_value=(data, None)):
        result = provider.execute_query('q', search_mode='auto')
    assert result['success'] and result['search_cost_usd'] == 0.0
    assert 'cost_per_1k_search_calls' in caplog.text
