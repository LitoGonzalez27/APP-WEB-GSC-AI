"""
Tests de la expansión de AI Overviews "collapsed" en Manual AI.

Regresión 2026-09: la expansión repetía la búsqueda con engine=google +
page_token, que SerpAPI ignora; el AIO seguía collapsed (~30% de los AIO sin
contenido). Ahora se usa engine=google_ai_overview y, si falla (token caducado
~1 min), se repite la búsqueda para obtener un token nuevo.

Ejecutar:  python3 -m pytest tests/test_manual_ai_aio_expansion.py -q
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")
os.environ.setdefault("SERPAPI_KEY", "test-key")

import pytest  # noqa: E402

from manual_ai.services import analysis_service as mod  # noqa: E402
from manual_ai.services.analysis_service import AnalysisService  # noqa: E402

COLLAPSED = {'page_token': 'TOKEN1', 'serpapi_link': 'https://serpapi.com/search.json?engine=google_ai_overview'}
EXPANDED = {
    'text_blocks': [{'type': 'paragraph', 'snippet': 'x'}],
    'references': [{'link': 'https://example.com/a', 'title': 'A', 'index': 0}],
}


def _svc():
    return AnalysisService.__new__(AnalysisService)


def _detect(serp_data, domain):
    aio = serp_data.get('ai_overview')
    if not aio:
        return {'has_ai_overview': False, 'debug_info': {}}
    if aio.get('page_token') and not aio.get('text_blocks') and not aio.get('references'):
        return {'has_ai_overview': True,
                'debug_info': {'requires_additional_request': True, 'page_token': aio['page_token']}}
    return {'has_ai_overview': True, 'domain_is_ai_source': True, 'debug_info': {}}


@pytest.fixture
def svc(monkeypatch):
    s = _svc()
    monkeypatch.setattr(s, '_detect_ai_overview', _detect)
    return s


def _run(svc):
    serp = {'ai_overview': dict(COLLAPSED)}
    return svc._expand_collapsed_aio('kw', 'esp', serp, _detect(serp, 'd.com'), 'd.com')


def test_fetch_expanded_uses_ai_overview_engine(monkeypatch):
    calls = []

    def fake_get_serp_json(params):
        calls.append(dict(params))
        return {'ai_overview': EXPANDED}

    import services.serp_service as serp_service
    monkeypatch.setattr(serp_service, 'get_serp_json', fake_get_serp_json)

    aio = _svc()._fetch_expanded_aio('kw', 'esp', 'TOKEN1')

    assert aio == EXPANDED
    assert len(calls) == 1
    assert calls[0]['engine'] == 'google_ai_overview'
    assert calls[0]['page_token'] == 'TOKEN1'


@pytest.mark.parametrize('response', [
    {'ai_overview': dict(COLLAPSED)},            # lo que devolvía engine=google
    {'error': "Google hasn't returned any results for this query."},  # token caducado
    {},
])
def test_fetch_expanded_raises_without_content(monkeypatch, response):
    import services.serp_service as serp_service
    monkeypatch.setattr(serp_service, 'get_serp_json', lambda p: response)
    with pytest.raises(RuntimeError):
        _svc()._fetch_expanded_aio('kw', 'esp', 'TOKEN1')


def test_expands_on_first_attempt(svc, monkeypatch):
    monkeypatch.setattr(svc, '_fetch_expanded_aio', lambda k, c, t: dict(EXPANDED))
    monkeypatch.setattr(svc, '_fetch_serp_data', lambda k, c: pytest.fail('no refetch expected'))

    serp, ai = _run(svc)

    assert serp['ai_overview'] == EXPANDED
    assert ai['domain_is_ai_source'] is True
    assert ai['aio_expansion'] == {'status': 'expanded', 'attempts': 1, 'refetches': 0, 'error': None}


def test_refetches_new_token_when_first_expansion_fails(svc, monkeypatch):
    tokens = []

    def fake_expand(k, c, token):
        tokens.append(token)
        if token == 'TOKEN1':
            raise RuntimeError("Google hasn't returned any results for this query.")
        return dict(EXPANDED)

    monkeypatch.setattr(svc, '_fetch_expanded_aio', fake_expand)
    monkeypatch.setattr(svc, '_fetch_serp_data',
                        lambda k, c: {'ai_overview': {'page_token': 'TOKEN2'}})

    serp, ai = _run(svc)

    assert tokens == ['TOKEN1', 'TOKEN2']
    assert serp['ai_overview'] == EXPANDED
    assert ai['aio_expansion']['status'] == 'expanded'
    assert ai['aio_expansion']['attempts'] == 2
    assert ai['aio_expansion']['refetches'] == 1


def test_refetch_returning_full_aio_counts_as_refetched(svc, monkeypatch):
    def fail(k, c, t):
        raise RuntimeError('boom')

    monkeypatch.setattr(svc, '_fetch_expanded_aio', fail)
    monkeypatch.setattr(svc, '_fetch_serp_data', lambda k, c: {'ai_overview': dict(EXPANDED)})

    serp, ai = _run(svc)

    assert serp['ai_overview'] == EXPANDED
    assert ai['aio_expansion']['status'] == 'refetched'


def test_keeps_collapsed_and_marks_failed(svc, monkeypatch):
    def fail(k, c, t):
        raise RuntimeError('boom')

    monkeypatch.setattr(svc, '_fetch_expanded_aio', fail)
    monkeypatch.setattr(svc, '_fetch_serp_data',
                        lambda k, c: {'ai_overview': {'page_token': 'TOKEN2'}})

    serp, ai = _run(svc)

    assert ai['has_ai_overview'] is True
    assert ai['aio_expansion']['status'] == 'failed'
    assert ai['aio_expansion']['attempts'] == 2
    assert ai['aio_expansion']['error'] == 'boom'


def test_refetch_disabled_by_env(svc, monkeypatch):
    monkeypatch.setenv('MANUAL_AI_AIO_REFETCH_ATTEMPTS', '0')

    def fail(k, c, t):
        raise RuntimeError('boom')

    monkeypatch.setattr(svc, '_fetch_expanded_aio', fail)
    monkeypatch.setattr(svc, '_fetch_serp_data', lambda k, c: pytest.fail('no refetch expected'))

    _, ai = _run(svc)

    assert ai['aio_expansion'] == {'status': 'failed', 'attempts': 1, 'refetches': 0, 'error': 'boom'}


def test_quota_error_propagates(svc, monkeypatch):
    def quota(k, c, t):
        e = RuntimeError('QUOTA_EXCEEDED')
        e.is_quota_error = True
        raise e

    monkeypatch.setattr(svc, '_fetch_expanded_aio', quota)
    with pytest.raises(RuntimeError, match='QUOTA_EXCEEDED'):
        _run(svc)


def test_analyze_keyword_calls_expansion_for_collapsed(monkeypatch):
    s = _svc()
    monkeypatch.setattr(mod, 'ai_cache', None)
    monkeypatch.setattr(s, '_fetch_serp_data', lambda k, c: {'ai_overview': dict(COLLAPSED)})
    monkeypatch.setattr(s, '_detect_ai_overview', _detect)
    monkeypatch.setattr(s, '_fetch_expanded_aio', lambda k, c, t: dict(EXPANDED))

    ai, serp = s._analyze_keyword('kw', {'country_code': 'ES', 'domain': 'd.com'}, 1)

    assert serp['ai_overview'] == EXPANDED
    assert ai['aio_expansion']['status'] == 'expanded'
