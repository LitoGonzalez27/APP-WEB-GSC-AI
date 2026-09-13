"""Persistencia del fan-out (services/llm_monitoring/fanout_store.py)."""

import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.llm_monitoring import fanout_store  # noqa: E402
from services.llm_monitoring.fanout_store import build_fanout_rows, save_fanout  # noqa: E402
from services.llm_monitoring.schema_check import SCHEMA_RECHECK_SECONDS  # noqa: E402
from services.llm_providers.perplexity_provider import parse_agent_response  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures' / 'fanout'


def _perplexity_low_search_queries():
    data = json.loads((FIXTURES / 'app-perplexity-agent-api-low.json').read_text())
    return parse_agent_response(data)['search_queries']


class TestBuildFanoutRows:
    def test_real_perplexity_response(self):
        rows = build_fanout_rows(
            _perplexity_low_search_queries(),
            brand_domain='https://www.getquipu.com',
            competitor_domains=['holded.com', 'billin.net', ''],
        )
        searches = [r for r in rows if r['action'] == 'search']
        pages = [r for r in rows if r['action'] == 'fetch_url']

        assert len(searches) == 5 and len(pages) == 1
        assert [r['position'] for r in rows] == list(range(len(rows)))
        assert all(r['query_normalized'] for r in searches)
        assert all(r['brand_in_sources'] in (True, False) for r in searches)
        assert pages[0]['url_host'] == 'guiafiscal.es'
        assert pages[0]['brand_in_sources'] is None

    def test_brand_and_competitors_detected_in_round_sources(self):
        rows = build_fanout_rows([
            {'round': 1, 'action': 'search', 'query': 'mejor software facturación 2026',
             'sources': ['https://blog.getquipu.com/x', 'https://www.holded.com/es']},
            {'round': 1, 'action': 'search', 'query': 'otra', 'sources': ['https://boe.es/a']},
        ], brand_domain='getquipu.com', competitor_domains=['holded.com', 'billin.net'])

        assert rows[0]['brand_in_sources'] is True
        assert rows[0]['competitor_hosts'] == ['holded.com']
        assert rows[1]['brand_in_sources'] is False and rows[1]['competitor_hosts'] == []

    def test_non_attributable_provider_leaves_brand_null(self):
        # Gemini: sub-consultas sin fuentes por búsqueda
        rows = build_fanout_rows([
            {'round': 1, 'action': 'search', 'query': 'a', 'sources': []},
            {'round': 1, 'action': 'search', 'query': 'b', 'sources': []},
        ], brand_domain='getquipu.com', competitor_domains=[])
        assert [r['brand_in_sources'] for r in rows] == [None, None]

    def test_open_page_of_competitor(self):
        rows = build_fanout_rows([
            {'round': 2, 'action': 'open_page', 'url': 'https://www.holded.com/es/precios', 'sources': []},
        ], brand_domain='getquipu.com', competitor_domains=['holded.com'])
        assert rows[0]['url_host'] == 'holded.com'
        assert rows[0]['competitor_hosts'] == ['holded.com']

    def test_unknown_actions_are_skipped(self):
        assert build_fanout_rows([{'action': 'weird'}], brand_domain=None, competitor_domains=None) == []


class TestSaveFanout:
    TASK = {'project_id': 7, 'query_id': 99, 'llm_name': 'perplexity', 'analysis_date': date(2026, 9, 13),
            'brand_domain': 'getquipu.com', 'competitor_domains': ['holded.com']}

    @patch('services.llm_monitoring.fanout_store.execute_values')
    def test_replaces_rows_of_the_result(self, execute_values):
        cur = MagicMock()
        n = save_fanout(cur, result_id=123, task=self.TASK, search_queries=_perplexity_low_search_queries())

        assert n == 6
        cur.execute.assert_called_once_with(
            "DELETE FROM llm_monitoring_fanout_queries WHERE result_id = %s", (123,))
        values = execute_values.call_args.args[2]
        assert len(values) == 6
        assert values[0][:5] == (123, 7, 99, 'perplexity', date(2026, 9, 13))

    @patch('services.llm_monitoring.fanout_store.execute_values')
    def test_no_search_deletes_previous_rows_and_inserts_nothing(self, execute_values):
        cur = MagicMock()
        assert save_fanout(cur, result_id=5, task=self.TASK, search_queries=[]) == 0
        cur.execute.assert_called_once()
        execute_values.assert_not_called()


class TestSchemaCheck:
    @pytest.fixture(autouse=True)
    def _reset_cache(self):
        fanout_store.FANOUT_SCHEMA.reset()
        yield
        fanout_store.FANOUT_SCHEMA.reset()

    @staticmethod
    def _conn(available):
        conn = MagicMock()
        conn.cursor.return_value.fetchone.return_value = {'available': available}
        return conn

    def test_available_is_cached_forever(self):
        get_conn = MagicMock(return_value=self._conn(True))
        assert fanout_store.fanout_schema_available(get_conn)
        assert fanout_store.fanout_schema_available(get_conn)
        assert get_conn.call_count == 1

    def test_missing_schema_is_rechecked_only_after_ttl(self):
        get_conn = MagicMock(return_value=self._conn(False))
        assert not fanout_store.fanout_schema_available(get_conn)
        assert not fanout_store.fanout_schema_available(get_conn)
        assert get_conn.call_count == 1

        fanout_store.FANOUT_SCHEMA._checked_at -= SCHEMA_RECHECK_SECONDS + 1
        get_conn.return_value = self._conn(True)
        assert fanout_store.fanout_schema_available(get_conn)
        assert get_conn.call_count == 2

    def test_query_error_counts_as_missing(self):
        conn = MagicMock()
        conn.cursor.return_value.execute.side_effect = RuntimeError('boom')
        assert not fanout_store.fanout_schema_available(MagicMock(return_value=conn))
        conn.close.assert_called_once()
