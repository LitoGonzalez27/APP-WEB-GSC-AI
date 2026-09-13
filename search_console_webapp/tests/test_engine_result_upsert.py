"""
Guardado de un resultado en el engine (_execute_single_query_task).

- Con el esquema de fan-out migrado: escribe search_queries y las filas de fan-out.
- Sin migrar: el INSERT es el de siempre (sin la columna) y no se toca el fan-out.
- Regresión: un reintento con éxito limpia has_error/error_message de la fila del día
  (en producción había 31 respuestas válidas marcadas como error).
"""

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.llm_monitoring.engine import _EngineMixin  # noqa: E402

SEARCH_QUERIES = [{'round': 1, 'action': 'search', 'query': 'q', 'url': None, 'sources': ['https://a.com/x']}]


class _Engine(_EngineMixin):
    provider_semaphores = {}

    def analyze_brand_mention(self, **kwargs):
        return {
            'brand_mentioned': False, 'mention_count': 0, 'mention_contexts': [],
            'appears_in_numbered_list': False, 'position_in_list': None, 'total_items_in_list': None,
            'position_source': None, 'competitors_mentioned': {},
        }


def _task(provider_result):
    provider = MagicMock()
    provider.execute_query.return_value = provider_result
    return {
        'project_id': 1, 'query_id': 2, 'query_text': 'q', 'execution_query': 'q', 'locale': None,
        'llm_name': 'perplexity', 'provider': provider, 'brand_name': 'Quipu',
        'brand_domain': 'getquipu.com', 'competitor_domains': [], 'analysis_date': date(2026, 9, 13),
    }


def _llm_result():
    return {
        'success': True, 'content': 'respuesta', 'sources': [], 'tokens': 3, 'input_tokens': 1,
        'output_tokens': 2, 'cost_usd': 0.004, 'response_time_ms': 900, 'model_used': 'sonar',
        'api_model_reported': 'openai/gpt-5.6-luna', 'search_used': True, 'search_calls': 1,
        'search_mode': 'auto', 'search_queries': SEARCH_QUERIES,
    }


@pytest.fixture
def db():
    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.fetchone.return_value = {'id': 555}
    with patch('services.llm_monitoring.engine.get_db_connection', return_value=conn):
        yield conn, cur


@pytest.mark.parametrize('schema_ready', [True, False])
def test_upsert_with_and_without_fanout_schema(db, schema_ready):
    conn, cur = db
    with patch('services.llm_monitoring.engine.fanout_schema_available', return_value=schema_ready), \
         patch('services.llm_monitoring.engine.save_fanout') as save_fanout:
        result = _Engine()._execute_single_query_task(_task(_llm_result()))

    assert result['success'] is True
    sql, params = cur.execute.call_args.args
    assert 'has_error = FALSE' in sql and 'error_message = NULL' in sql
    assert 'RETURNING id' in sql
    assert ('search_queries' in sql) is schema_ready
    assert sql.count('%s') == len(params)

    metadata = next(p for p in params if isinstance(p, str) and 'model_reported' in p)
    assert '"search_calls": 1' in metadata and 'gpt-5.6-luna' in metadata

    if schema_ready:
        save_fanout.assert_called_once()
        assert save_fanout.call_args.kwargs['result_id'] == 555
        assert save_fanout.call_args.kwargs['search_queries'] == SEARCH_QUERIES
    else:
        save_fanout.assert_not_called()
    conn.commit.assert_called_once()


class TestNoSilentTaskLoss:
    """Una tarea nunca debe desaparecer sin dejar fila (resultado o error) en BD."""

    def test_empty_content_is_saved_as_error(self, db):
        result = _llm_result()
        result['content'] = None
        engine = _Engine()
        with patch.object(engine, '_save_error_result') as save_error:
            out = engine._execute_single_query_task(_task(result))

        assert out['success'] is False
        save_error.assert_called_once()
        assert 'Empty content from perplexity' in save_error.call_args.args[1]

    def test_unexpected_exception_before_saving_leaves_error_row(self, db):
        engine = _Engine()
        with patch.object(engine, 'analyze_brand_mention', side_effect=RuntimeError('boom')), \
             patch.object(engine, '_save_error_result') as save_error:
            out = engine._execute_single_query_task(_task(_llm_result()))

        assert out['success'] is False
        save_error.assert_called_once()
        assert 'boom' in save_error.call_args.args[1]

    def test_exception_after_commit_does_not_overwrite_good_row(self, db):
        conn, cur = db
        conn.close.side_effect = RuntimeError('close failed')   # tras el commit
        engine = _Engine()
        with patch('services.llm_monitoring.engine.fanout_schema_available', return_value=False), \
             patch.object(engine, '_save_error_result') as save_error:
            engine._execute_single_query_task(_task(_llm_result()))

        conn.commit.assert_called_once()
        save_error.assert_not_called()
