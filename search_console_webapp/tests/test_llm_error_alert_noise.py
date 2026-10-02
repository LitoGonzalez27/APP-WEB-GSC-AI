"""
Avisos de error (services/alertas_errores.py) solo para fallos DEFINITIVOS de un provider.

Contexto: el 2026-10-02 llegaron 3 emails "[PRODUCTION] Clicandseo: N error(es)" por
HTTP 429 de Perplexity durante el cron, pero los reintentos de `with_retry` los
recuperaron todos (221/221 respuestas guardadas). El provider registraba con
logger.error CADA intento fallido y el handler de alertas (nivel ERROR) los contaba.

Regla fijada aquí: cada intento fallido es un warning; el ERROR lo emite `with_retry`
una vez, cuando la query falla definitivamente.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.llm_providers.perplexity_provider import PerplexityProvider
from services.llm_providers.retry_handler import circuit_breaker

RATE_LIMIT_429 = {'error': {'message': 'Request rate limit exceeded, please try again later.',
                            'type': 'request_rate_limit_exceeded', 'code': 429}}
OK_200 = {'status': 'completed', 'model': 'sonar',
          'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'respuesta'}]}],
          'usage': {'input_tokens': 10, 'output_tokens': 5}}


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """El breaker es un singleton global: aislar cada test."""
    yield
    circuit_breaker.record_success('perplexity')


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch('services.llm_providers.retry_handler.time.sleep'):
        yield


def _provider() -> PerplexityProvider:
    with patch('services.llm_providers.perplexity_provider.get_model_pricing_from_db',
               return_value={'input': 0.000001, 'output': 0.000001}):
        return PerplexityProvider(api_key='pplx-test', model='sonar')


def _http_response(status, payload):
    response = MagicMock(spec=requests.Response)
    response.status_code = status
    response.text = json.dumps(payload)
    response.json.return_value = payload
    return response


def _errors(caplog):
    return [r for r in caplog.records
            if r.levelno >= logging.ERROR and r.name.startswith('services.llm_providers')]


@patch('services.llm_providers.perplexity_provider.requests.post')
def test_429_recovered_by_retry_does_not_log_error(mock_post, caplog):
    mock_post.side_effect = [_http_response(429, RATE_LIMIT_429), _http_response(200, OK_200)]
    with caplog.at_level(logging.WARNING):
        result = _provider().execute_query('q')

    assert result['success'] is True
    assert mock_post.call_count == 2
    assert _errors(caplog) == []
    assert any('HTTP 429' in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


@patch('services.llm_providers.perplexity_provider.requests.post')
def test_429_exhausting_retries_logs_error_once_per_query(mock_post, caplog):
    mock_post.return_value = _http_response(429, RATE_LIMIT_429)
    with caplog.at_level(logging.WARNING):
        result = _provider().execute_query('q')

    assert result['success'] is False
    assert mock_post.call_count == 3
    errors = _errors(caplog)
    assert errors and all(r.name.endswith('retry_handler') for r in errors)
    assert any('Falló después de 3 intentos' in r.getMessage() for r in errors)


@patch('services.llm_providers.perplexity_provider.requests.post')
def test_non_retryable_error_still_logs_error(mock_post, caplog):
    mock_post.return_value = _http_response(
        401, {'error': {'message': 'Invalid API key provided.', 'type': 'invalid_api_key', 'code': 401}}
    )
    with caplog.at_level(logging.WARNING):
        result = _provider().execute_query('q')

    assert result['success'] is False
    errors = _errors(caplog)
    assert len(errors) == 1
    assert 'HTTP 401' in errors[0].getMessage()
