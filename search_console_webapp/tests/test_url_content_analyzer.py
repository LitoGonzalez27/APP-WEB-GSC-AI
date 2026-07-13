"""
Tests del análisis de contenido de URLs citadas por LLMs (Fase 1 determinista)

Cubre:
    - Validación anti-SSRF del fetcher (esquemas, hosts internos, IPs privadas,
      DNS que resuelve a IP privada, puertos, credenciales embebidas)
    - Matching determinista de marca/competidores sobre HTML
    - Clasificación de oportunidad (mentioned / quick_win / competitor_page /
      no_mentions)
    - Política de refresco de caché

No requiere red ni base de datos: el DNS se mockea.
"""

import os
from datetime import datetime, timedelta

import pytest

# Igual que el resto de tests del repo: BD dummy para poder importar database.py
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.llm_monitoring import url_content_analyzer as analyzer
from services.llm_monitoring.url_content_analyzer import (
    UnsafeURLError,
    analyze_html,
    validate_public_http_url,
    _needs_refresh,
    normalize_domain,
)


def _fake_getaddrinfo(ip):
    def fake(host, port, **kwargs):
        return [(2, 1, 6, '', (ip, port))]
    return fake


BRAND_CONFIG = {
    'brand_domain': 'clicandseo.com',
    'brand_terms': ['Clicandseo', 'Clic&SEO'],
    'competitors': [
        {'name': 'Semrush', 'domain': 'semrush.com', 'terms': ['Semrush']},
        {'name': 'Ahrefs', 'domain': 'ahrefs.com', 'terms': ['Ahrefs']},
    ],
    'enabled_llms': ['openai'],
}


# ---------------------------------------------------------------------------
# Anti-SSRF
# ---------------------------------------------------------------------------

class TestValidatePublicHttpUrl:

    def test_rejects_non_http_schemes(self):
        for url in ('ftp://example.com/x', 'file:///etc/passwd', 'gopher://x.com', 'javascript:alert(1)'):
            with pytest.raises(UnsafeURLError):
                validate_public_http_url(url)

    def test_rejects_localhost_and_internal_hostnames(self):
        for url in ('http://localhost/admin', 'https://foo.local/x',
                    'https://app.internal/x', 'http://intranet/x'):
            with pytest.raises(UnsafeURLError):
                validate_public_http_url(url)

    def test_rejects_private_and_reserved_ip_literals(self):
        for url in ('http://127.0.0.1/', 'http://10.0.0.5/x', 'http://192.168.1.1/',
                    'http://169.254.169.254/latest/meta-data/', 'http://0.0.0.0/',
                    'http://[::1]/', 'http://100.64.0.1/'):
            with pytest.raises(UnsafeURLError):
                validate_public_http_url(url)

    def test_rejects_embedded_credentials(self):
        with pytest.raises(UnsafeURLError):
            validate_public_http_url('https://user:pass@example.com/')

    def test_rejects_non_standard_ports(self):
        for url in ('https://example.com:8080/', 'http://example.com:22/'):
            with pytest.raises(UnsafeURLError):
                validate_public_http_url(url)

    def test_rejects_dns_resolving_to_private_ip(self, monkeypatch):
        """DNS rebinding básico: hostname público que resuelve a IP interna"""
        monkeypatch.setattr(analyzer.socket, 'getaddrinfo', _fake_getaddrinfo('127.0.0.1'))
        with pytest.raises(UnsafeURLError):
            validate_public_http_url('https://evil-rebind.example.com/')

    def test_accepts_public_url(self, monkeypatch):
        monkeypatch.setattr(analyzer.socket, 'getaddrinfo', _fake_getaddrinfo('93.184.216.34'))
        validate_public_http_url('https://example.com/page')  # no debe lanzar

    def test_accepts_public_ip_literal(self):
        validate_public_http_url('https://93.184.216.34/page')  # no debe lanzar


# ---------------------------------------------------------------------------
# Análisis de HTML
# ---------------------------------------------------------------------------

class TestAnalyzeHtml:

    def test_detects_brand_mention_and_link(self):
        html = b"""
        <html><head><title>Best SEO tools 2026</title></head><body>
            <p>We recommend Clicandseo for AI visibility.</p>
            <p>clicandseo is great. But CLICANDSEO2 should not match as a word.</p>
            <a href="https://www.clicandseo.com/pricing">Clicandseo pricing</a>
            <script>var clicandseo = 'no debe contarse';</script>
        </body></html>
        """
        result = analyze_html(html, 'https://blog.example.com/seo-tools', BRAND_CONFIG)

        assert result['page_title'] == 'Best SEO tools 2026'
        assert result['brand_mentioned'] is True
        # 2 en <p> + 1 como anchor text; el del <script> no cuenta
        assert result['brand_mention_count'] == 3
        assert result['brand_linked'] is True
        assert 'Clicandseo pricing' in result['brand_anchor_texts']
        assert result['opportunity'] == 'mentioned'

    def test_quick_win_when_only_competitors_mentioned(self):
        html = b"""
        <html><body>
            <p>Top tools: Semrush and Ahrefs are the leaders.</p>
            <a href="https://ahrefs.com/blog">Ahrefs blog</a>
        </body></html>
        """
        result = analyze_html(html, 'https://blog.example.com/tools', BRAND_CONFIG)

        assert result['brand_mentioned'] is False
        assert result['opportunity'] == 'quick_win'

        semrush = next(c for c in result['competitors_found'] if c['name'] == 'Semrush')
        ahrefs = next(c for c in result['competitors_found'] if c['name'] == 'Ahrefs')
        assert semrush['mentioned'] is True and semrush['linked'] is False
        assert ahrefs['mentioned'] is True and ahrefs['linked'] is True
        assert 'Ahrefs blog' in ahrefs['anchor_texts']

    def test_competitor_own_page_is_not_quick_win(self):
        html = b'<html><body><p>Semrush features and pricing.</p></body></html>'
        result = analyze_html(html, 'https://www.semrush.com/features/', BRAND_CONFIG)
        assert result['opportunity'] == 'competitor_page'

    def test_no_mentions(self):
        html = '<html><body><p>Un post sobre recetas de cocina.</p></body></html>'.encode('utf-8')
        result = analyze_html(html, 'https://recetas.example.com/', BRAND_CONFIG)
        assert result['opportunity'] == 'no_mentions'
        assert result['brand_mention_count'] == 0

    def test_own_brand_page_counts_as_mentioned(self):
        html = '<html><body><p>Página sin texto de marca.</p></body></html>'.encode('utf-8')
        result = analyze_html(html, 'https://www.clicandseo.com/blog/post', BRAND_CONFIG)
        assert result['opportunity'] == 'mentioned'

    def test_word_boundaries_avoid_substring_false_positives(self):
        html = b'<html><body><p>El semrushista no es Semrush-like ni ahrefsx.</p></body></html>'
        result = analyze_html(html, 'https://blog.example.com/x', BRAND_CONFIG)
        semrush = next(c for c in result['competitors_found'] if c['name'] == 'Semrush')
        ahrefs = next(c for c in result['competitors_found'] if c['name'] == 'Ahrefs')
        # 'Semrush-like' sí es palabra completa delimitada por '-', 'semrushista' no
        assert semrush['mention_count'] == 1
        assert ahrefs['mention_count'] == 0


# ---------------------------------------------------------------------------
# Fallback Jina Reader
# ---------------------------------------------------------------------------

class TestJinaFallback:

    def test_should_fallback_on_bot_protection_and_network_errors(self):
        for reason in ('http_403', 'http_429', 'http_503', 'timeout',
                       'ssl_error', 'fetch_error', 'empty_content'):
            assert analyzer._should_fallback_to_jina(reason) is True

    def test_should_not_fallback_on_unsafe_or_non_html(self):
        for reason in ('unsafe_url', 'not_html', 'too_large', None):
            assert analyzer._should_fallback_to_jina(reason) is False

    def test_fetch_via_jina_builds_request_correctly(self, monkeypatch):
        captured = {}

        class FakeResponse:
            status_code = 200
            def iter_content(self, chunk_size):
                yield b'<html><body>Semrush</body></html>'
            def close(self):
                pass

        def fake_get(url, headers=None, timeout=None, stream=None):
            captured.update({'url': url, 'headers': headers, 'timeout': timeout})
            return FakeResponse()

        monkeypatch.delenv('JINA_API_KEY', raising=False)
        monkeypatch.setattr(analyzer.requests, 'get', fake_get)

        result = analyzer.fetch_url_via_jina('https://blocked.example.com/page')

        assert result['ok'] is True
        assert b'Semrush' in result['content']
        assert captured['url'] == 'https://r.jina.ai/https://blocked.example.com/page'
        assert captured['headers']['X-Return-Format'] == 'html'
        # Sin JINA_API_KEY no debe enviarse Authorization
        assert 'Authorization' not in captured['headers']

    def test_fetch_via_jina_uses_api_key_when_present(self, monkeypatch):
        captured = {}

        class FakeResponse:
            status_code = 200
            def iter_content(self, chunk_size):
                yield b'<html></html>'
            def close(self):
                pass

        monkeypatch.setenv('JINA_API_KEY', 'jina_test_key')
        monkeypatch.setattr(analyzer.requests, 'get',
                            lambda url, **kw: captured.update(kw) or FakeResponse())

        result = analyzer.fetch_url_via_jina('https://blocked.example.com/')
        assert result['ok'] is True
        assert captured['headers']['Authorization'] == 'Bearer jina_test_key'

    def test_fetch_via_jina_propagates_http_error(self, monkeypatch):
        class FakeResponse:
            status_code = 451
            def iter_content(self, chunk_size):
                return iter(())
            def close(self):
                pass

        monkeypatch.setattr(analyzer.requests, 'get', lambda url, **kw: FakeResponse())
        result = analyzer.fetch_url_via_jina('https://blocked.example.com/')
        assert result['ok'] is False
        assert result['error_reason'] == 'jina_http_451'


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_normalize_domain(self):
        assert normalize_domain('https://www.Foo.com/x?a=1') == 'foo.com'
        assert normalize_domain('foo.com') == 'foo.com'
        assert normalize_domain('http://sub.foo.com:8080/path') == 'sub.foo.com'
        assert normalize_domain('') == ''
        assert normalize_domain(None) == ''

    def test_needs_refresh(self):
        assert _needs_refresh(None) is True
        assert _needs_refresh({'status': 'error', 'fetched_at': datetime.now()}) is True
        assert _needs_refresh({'status': 'completed', 'fetched_at': None}) is True

        fresh = {'status': 'completed', 'fetched_at': datetime.now() - timedelta(days=1)}
        assert _needs_refresh(fresh) is False

        stale = {'status': 'completed',
                 'fetched_at': datetime.now() - timedelta(days=analyzer.CACHE_TTL_DAYS + 1)}
        assert _needs_refresh(stale) is True
