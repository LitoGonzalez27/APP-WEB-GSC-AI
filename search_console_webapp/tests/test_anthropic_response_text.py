"""
Texto de las respuestas de Claude (regresión 2026-09-13).

Claude Sonnet 5 puede anteponer un bloque `thinking`. El provider leía
`content[0].text` y, con el SDK de producción (0.39), ese bloque llega como
TextBlock con text=None: la respuesta se perdía sin fila de error.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic

from services.llm_providers.anthropic_provider import AnthropicProvider, extract_response_text

FIXTURE = Path(__file__).parent / 'fixtures' / 'fanout' / 'p1-anthropic-claude-sonnet-5-web_search_20250305-comercial-es.json'


def _block(type_, text=None):
    return SimpleNamespace(type=type_, text=text)


def test_thinking_block_parsed_as_text_none_is_ignored():
    # Forma exacta del SDK 0.39: bloque thinking con type='thinking' y text=None
    blocks = [_block('thinking', None), _block('text', 'Hola '), _block('text', 'mundo')]
    assert extract_response_text(blocks) == 'Hola mundo'


def test_tool_blocks_are_ignored_and_all_text_blocks_joined():
    data = json.loads(FIXTURE.read_text())
    message = anthropic.types.Message.model_validate(data)
    text = extract_response_text(message.content)

    expected = ''.join(b['text'] for b in data['content'] if b['type'] == 'text')
    assert text == expected and len(text) > 1000


def test_empty_or_missing_content():
    assert extract_response_text(None) == ''
    assert extract_response_text([_block('thinking')]) == ''


@patch('services.llm_providers.anthropic_provider.get_model_pricing_from_db',
       return_value={'input': 0.000002, 'output': 0.00001})
def test_provider_returns_error_instead_of_empty_success(_pricing):
    provider = AnthropicProvider(api_key='sk-ant-test', model='claude-sonnet-5')
    response = MagicMock()
    response.content = [_block('thinking', None)]
    response.stop_reason = 'max_tokens'
    provider.client = MagicMock()
    provider.client.messages.create.return_value = response

    with patch('services.llm_providers.retry_handler.time.sleep'):
        result = provider.execute_query('hola')

    assert result['success'] is False
    assert 'Empty content' in result['error'] and 'max_tokens' in result['error']
