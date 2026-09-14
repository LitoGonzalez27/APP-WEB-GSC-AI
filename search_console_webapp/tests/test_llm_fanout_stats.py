"""
Query fan-out en el panel y las exportaciones (P7, 2026-09-14).

Regla de Carlos: todo existe solo para proyectos con search_mode='auto'. Con 'off' no se
consulta nada nuevo y el panel, el modal y las exportaciones quedan como estaban.
"""

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.llm_monitoring.fanout_stats import (  # noqa: E402
    aggregate_fanout,
    collect_fanout_metrics,
    fanout_export_tables,
    project_competitor_domains,
    response_search_detail,
)
from services.llm_monitoring.fanout_store import build_fanout_rows  # noqa: E402
from services.llm_providers.anthropic_provider import parse_messages_response  # noqa: E402
from services.llm_providers.google_provider import parse_generate_content  # noqa: E402
from services.llm_providers.openai_provider import parse_responses_output  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures' / 'fanout'
ROOT = Path(__file__).parent.parent


def _fixture(name):
    return json.loads((FIXTURES / name).read_text())


def _rows(result_id, provider, query_id, parsed, brand='getquipu.com', competitors=('holded.com', 'billin.net')):
    rows = build_fanout_rows(parsed['search_queries'], brand_domain=brand, competitor_domains=list(competitors))
    return [{**r, 'result_id': result_id, 'llm_provider': provider, 'query_id': query_id,
             'url': r['url'], 'url_host': r['url_host']} for r in rows]


@pytest.fixture
def real_dataset():
    """3 respuestas reales (OpenAI, Claude, Gemini) al mismo prompt + 1 de Gemini que no buscó."""
    openai = parse_responses_output(_fixture('p1-openai-gpt-5.5-comercial-es.json'))
    claude = parse_messages_response(_fixture('p1-anthropic-claude-sonnet-5-web_search_20250305-comercial-es.json'))
    gemini = parse_generate_content(_fixture('p1-google-gemini-3.6-flash-comercial-es.json'))
    results = [
        {'id': 1, 'llm_provider': 'openai', 'query_id': 10, 'search_used': True, 'search_calls': 7, 'page_opens': 4},
        {'id': 2, 'llm_provider': 'anthropic', 'query_id': 10, 'search_used': True, 'search_calls': 2, 'page_opens': 0},
        {'id': 3, 'llm_provider': 'google', 'query_id': 10, 'search_used': True, 'search_calls': 2, 'page_opens': 0},
        {'id': 4, 'llm_provider': 'google', 'query_id': 11, 'search_used': False, 'search_calls': 0, 'page_opens': 0},
    ]
    fanout = _rows(1, 'openai', 10, openai) + _rows(2, 'anthropic', 10, claude) + _rows(3, 'google', 10, gemini)
    return results, fanout


class TestAggregateFanout:
    def test_by_model(self, real_dataset):
        results, fanout = real_dataset
        data = aggregate_fanout(results, fanout, prompt_texts={10: 'mejor software', 11: 'qué es'},
                                brand_domain='getquipu.com', competitor_domains=['holded.com'])
        by_llm = {row['llm_provider']: row for row in data['by_llm']}

        assert data['responses'] == 4 and data['responses_with_search'] == 3
        assert by_llm['openai']['search_rate'] == 1.0 and by_llm['openai']['avg_searches'] == 7.0
        assert by_llm['openai']['avg_page_opens'] == 4.0
        assert by_llm['openai']['brand_in_results_rate'] == 1.0   # Quipu sale en los resultados
        assert by_llm['google']['search_rate'] == 0.5            # 1 de 2 respuestas buscó
        assert by_llm['google']['brand_in_results_rate'] is None  # Gemini no atribuye fuentes

    def test_top_queries_group_variants_and_prompts(self, real_dataset):
        results, fanout = real_dataset
        data = aggregate_fanout(results, fanout, prompt_texts={10: 'mejor software'},
                                brand_domain='getquipu.com', competitor_domains=[])
        assert data['top_queries_total'] == len({r['query_normalized'] for r in fanout if r['action'] == 'search'})
        top = data['top_queries'][0]
        assert top['responses'] >= 1 and top['share'] == round(top['responses'] / 4, 4)
        assert top['prompts'][0] == {'query_id': 10, 'prompt': 'mejor software', 'count': top['count']}
        assert all(q['variants'] for q in data['top_queries'])
        # Orden: más respuestas primero
        responses = [q['responses'] for q in data['top_queries']]
        assert responses == sorted(responses, reverse=True)

    def test_same_intent_written_differently_is_one_group(self):
        rows = [
            {'result_id': 1, 'llm_provider': 'openai', 'query_id': 1, 'action': 'search',
             'query_text': 'Mejor software facturación 2026', 'query_normalized': 'mejor software facturacion',
             'brand_in_sources': True},
            {'result_id': 2, 'llm_provider': 'anthropic', 'query_id': 1, 'action': 'search',
             'query_text': 'mejor software de facturacion', 'query_normalized': 'mejor software facturacion',
             'brand_in_sources': False},
        ]
        results = [{'id': 1, 'llm_provider': 'openai', 'query_id': 1, 'search_used': True},
                   {'id': 2, 'llm_provider': 'anthropic', 'query_id': 1, 'search_used': True}]
        data = aggregate_fanout(results, rows, prompt_texts={}, brand_domain='x.com', competitor_domains=[])
        assert data['top_queries_total'] == 1
        group = data['top_queries'][0]
        assert group['responses'] == 2 and group['share'] == 1.0 and group['brand_in_results_rate'] == 0.5
        assert group['providers'] == {'openai': 1, 'anthropic': 1} and group['variants_total'] == 2

    def test_pages_split_by_owner(self, real_dataset):
        results, fanout = real_dataset
        extra = [{'result_id': 1, 'llm_provider': 'openai', 'query_id': 10, 'action': 'open_page',
                  'url': 'https://www.holded.com/es/precios', 'url_host': 'holded.com', 'query_text': None}]
        data = aggregate_fanout(results, fanout + extra, prompt_texts={},
                                brand_domain='getquipu.com', competitor_domains=['holded.com'])
        assert data['brand_pages'][0]['url'] == 'https://getquipu.com/es/plan-de-precios'
        assert data['brand_pages'][0]['count'] == 2  # open_page dos veces en la respuesta real
        assert data['competitor_pages'] == [{'url': 'https://www.holded.com/es/precios', 'host': 'holded.com',
                                             'count': 1, 'providers': {'openai': 1}, 'competitor': 'holded.com'}]

    def test_empty(self):
        data = aggregate_fanout([], [], prompt_texts={}, brand_domain=None, competitor_domains=[])
        assert data['responses'] == 0 and data['by_llm'] == [] and data['top_queries'] == []
        assert data['brand_pages'] == [] and data['competitor_pages'] == []


class TestCollectFanoutMetrics:
    @pytest.mark.parametrize('mode', ['off', None, 'AUTO'])
    def test_off_projects_do_not_touch_the_database(self, mode):
        cur = MagicMock()
        project = {'id': 1, 'search_mode': mode, 'search_enabled_at': datetime(2026, 9, 1, tzinfo=timezone.utc)}
        assert collect_fanout_metrics(cur, project, start_date=date(2026, 8, 1), end_date=date(2026, 9, 14)) == {'enabled': False}
        cur.execute.assert_not_called()

    def test_auto_project_counts_only_answers_with_search_since_activation(self):
        cur = MagicMock()
        cur.fetchall.side_effect = [
            [{'id': 1, 'llm_provider': 'openai', 'query_id': 5, 'search_used': True, 'search_calls': 3, 'page_opens': 1}],
            [{'result_id': 1, 'llm_provider': 'openai', 'query_id': 5, 'action': 'search', 'query_text': 'q',
              'query_normalized': 'q', 'url': None, 'url_host': None, 'brand_in_sources': True}],
            [{'id': 5, 'query_text': 'prompt'}],
        ]
        project = {'id': 7, 'search_mode': 'auto', 'search_enabled_at': datetime(2026, 9, 10, 8, tzinfo=timezone.utc),
                   'brand_domain': 'quipu.com', 'selected_competitors': [{'domain': 'www.Holded.com'}]}
        data = collect_fanout_metrics(cur, project, start_date=date(2026, 8, 15), end_date=date(2026, 9, 14),
                                      enabled_llms=['openai'], query_ids=[5])

        sql, params = cur.execute.call_args_list[0].args
        assert "execution_metadata->>'search_mode' = 'auto'" in sql and 'has_error' in sql
        assert params == [7, date(2026, 9, 10), date(2026, 9, 14), ['openai'], [5]]  # desde la activación
        assert data['enabled'] is True and data['period']['start_date'] == '2026-09-10'
        assert data['top_queries'][0]['prompts'][0]['prompt'] == 'prompt'

    def test_no_answers_skips_detail_queries(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        project = {'id': 7, 'search_mode': 'auto', 'search_enabled_at': datetime(2026, 9, 10, tzinfo=timezone.utc)}
        data = collect_fanout_metrics(cur, project, start_date=date(2026, 9, 1), end_date=date(2026, 9, 14))
        assert cur.execute.call_count == 1 and data['responses'] == 0


def test_competitor_domains_merge_new_and_legacy_fields():
    project = {'selected_competitors': [{'domain': 'https://www.Holded.com/'}, {'name': 'sin dominio'}],
               'competitor_domains': ['billin.net', 'holded.com']}
    assert project_competitor_domains(project) == ['holded.com', 'billin.net']


class TestResponseSearchDetail:
    def test_answers_without_search_mode_have_no_block(self):
        assert response_search_detail({'search_mode': 'off'}, [{'action': 'search', 'query': 'q'}]) is None
        assert response_search_detail(None, None) is None
        # Filas de Perplexity anteriores a P3: search_mode 'auto' guardado por el provider,
        # pero el endpoint solo lo usa en proyectos que ahora están en auto.
        assert response_search_detail({'search_mode': 'auto', 'search_used': True}, [])['used'] is True

    def test_detail_from_real_openai_answer(self):
        parsed = parse_responses_output(_fixture('p1-openai-gpt-5.5-comercial-es.json'))
        meta = {'search_mode': 'auto', 'search_used': True, 'search_calls': 7, 'page_opens': 4,
                'search_tool': 'openai_web_search', 'model_reported': 'gpt-5.5-2026-04-23'}
        detail = response_search_detail(meta, parsed['search_queries'])
        assert detail['calls'] == 7 and len(detail['searches']) == 28 and len(detail['pages']) == 4
        assert detail['pages'][-1] == {'round': 7, 'action': 'find_in_page',
                                       'url': 'https://www.contasimple.com/precios', 'pattern': 'Gratis de por vida'}


def test_export_tables_share_one_source(real_dataset):
    results, fanout = real_dataset
    data = aggregate_fanout(results, fanout, prompt_texts={}, brand_domain='getquipu.com',
                            competitor_domains=['holded.com'])
    tables = fanout_export_tables(data)
    assert tables['by_llm'][0][0] == 'Model' and len(tables['by_llm']) == 4
    gemini = next(r for r in tables['by_llm'] if r[0] == 'Gemini')
    assert gemini[2] == '50%' and gemini[5] == 'Not reported'
    assert len(tables['queries']) == 1 + len(data['top_queries'])
    assert tables['pages'][1][0] == 'Your brand'


class TestOffProjectsStayUnchanged:
    """Blindaje en el código de las rutas y del panel (no hay BD en los tests)."""

    routes = (ROOT / 'llm_monitoring_routes.py').read_text()

    def test_fanout_endpoint_short_circuits_when_off(self):
        body = self.routes[self.routes.index('def get_project_fanout'):]
        body = body[:body.index('\n@llm_monitoring_bp.route')]
        assert "if not is_search_enabled(project.get('search_mode')):" in body
        assert "return jsonify({'success': True, 'enabled': False}), 200" in body
        assert body.index("'enabled': False") < body.index('collect_fanout_metrics(')

    def test_responses_only_add_search_columns_and_field_when_on(self):
        body = self.routes[self.routes.index('def get_project_responses'):]
        body = body[:body.index('\n@llm_monitoring_bp.route')]
        assert '""" if include_search else "")' in body
        assert "if include_search:\n                item['search'] = response_search_detail(" in body

    def test_exports_only_add_fanout_when_on(self):
        helper = self.routes[self.routes.index('def _safe_fanout_metrics'):]
        helper = helper[:helper.index('\ndef ')]
        assert "if not is_search_enabled(project.get('search_mode')):\n        return None" in helper
        assert 'if excel_fanout:' in self.routes and 'if pdf_fanout:' in self.routes

    def test_panel_mixin_exits_before_fetching_when_off(self):
        js = (ROOT / 'static/js/llm_monitoring/llm-monitoring-fanout.js').read_text()
        load = js[js.index('async loadFanout(projectId)'):]
        assert load.index('if (!this.isSearchProject())') < load.index('fetch(')
        assert "this.currentProject?.search_mode === 'auto'" in js
        assert "if (!search) return '';" in js
