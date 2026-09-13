"""Normalización compartida del query fan-out (services/llm_providers/fanout_utils.py)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from services.llm_providers.fanout_utils import (
    dedupe_preserving_order,
    host_matches_domain,
    normalize_domain,
    normalize_query,
    normalize_url,
    resolve_redirects,
)


class TestNormalizeUrl:
    @pytest.mark.parametrize('raw,expected', [
        ('https://getquipu.com/es/precios?utm_source=openai', 'https://getquipu.com/es/precios'),
        ('HTTPS://Holded.com/es/blog/#precios', 'https://holded.com/es/blog'),
        ('https://a.com/?utm_medium=x&page=2', 'https://a.com/?page=2'),
        ('https://a.com/', 'https://a.com/'),
        ('https://www.a.com/x', 'https://www.a.com/x'),
    ])
    def test_canonical_form(self, raw, expected):
        assert normalize_url(raw) == expected

    @pytest.mark.parametrize('raw', [None, '', 'getquipu.com/precios', 'mailto:a@b.com'])
    def test_non_http_values_are_returned_untouched(self, raw):
        assert normalize_url(raw) == raw


class TestDomains:
    @pytest.mark.parametrize('raw,expected', [
        ('https://www.Foo.com/x?a=1', 'foo.com'),
        ('foo.com', 'foo.com'),
        ('http://sub.foo.com:8080/path', 'sub.foo.com'),
        ('', ''),
        (None, ''),
    ])
    def test_normalize_domain(self, raw, expected):
        assert normalize_domain(raw) == expected

    def test_host_matches_domain_and_subdomains_only(self):
        assert host_matches_domain('blog.getquipu.com', 'getquipu.com')
        assert host_matches_domain('getquipu.com', 'getquipu.com')
        assert not host_matches_domain('notgetquipu.com', 'getquipu.com')
        assert not host_matches_domain('', 'getquipu.com')


class TestNormalizeQuery:
    def test_same_intent_same_key(self):
        variants = [
            'Mejor software facturación autónomos España 2026',
            'mejor software facturacion autonomos España',
            'mejor software facturación autónomos España site:holded.com',
            '"mejor software" facturación autónomos España 2025 OR 2026',
        ]
        assert {normalize_query(v) for v in variants} == {'mejor software facturacion autonomos espana'}

    def test_excluded_terms_are_dropped(self):
        assert normalize_query('software facturación -gratis') == 'software facturacion'

    def test_empty(self):
        assert normalize_query(None) == '' and normalize_query('   ') == ''


def test_dedupe_preserving_order():
    assert dedupe_preserving_order(['b', 'a', 'b', 'c', 'a']) == ['b', 'a', 'c']


class TestResolveRedirects:
    @staticmethod
    def _head(status, location=None):
        response = MagicMock()
        response.is_redirect = status in (301, 302, 303, 307, 308)
        response.headers = {'Location': location} if location else {}
        return response

    @patch('services.llm_providers.fanout_utils.requests.head')
    def test_reads_location_without_following(self, head):
        head.return_value = self._head(302, 'https://holded.com/es/blog/?utm_source=x')
        result = resolve_redirects(['https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc'])

        assert result == {'https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc': 'https://holded.com/es/blog'}
        assert head.call_args.kwargs['allow_redirects'] is False

    @patch('services.llm_providers.fanout_utils.requests.head')
    def test_failures_are_omitted(self, head):
        head.side_effect = [requests.Timeout(), self._head(200)]
        assert resolve_redirects(['https://x/1', 'https://x/2']) == {}

    @patch('services.llm_providers.fanout_utils.requests.head')
    def test_limit_and_dedupe(self, head):
        head.return_value = self._head(302, 'https://a.com/')
        resolve_redirects(['https://x/1', 'https://x/1', 'https://x/2', 'https://x/3'], limit=2)
        assert head.call_count == 2

    def test_empty_input_makes_no_requests(self):
        assert resolve_redirects([]) == {}
