"""
Interruptor de búsqueda web y ponderación de unidades (P3, 2026-09-13).

- Pesos por modo del proyecto: 'off' siempre 1 unidad; 'auto' el peso del proveedor.
- Sin la columna units_consumed migrada se cuenta como antes (COUNT(*)).
- El engine pasa search_mode a cada provider, lo guarda en metadata y escribe
  units_consumed; las filas con error cuentan 1.
- El admin cambia search_mode con validación estricta y fecha de activación.
"""

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import llm_monitoring_limits  # noqa: E402
from llm_monitoring_limits import (  # noqa: E402
    DEFAULT_SEARCH_UNIT_WEIGHTS,
    llm_units_sql,
    units_by_provider,
    units_per_task,
)
from services.llm_monitoring.completion import count_planned_tasks  # noqa: E402
from services.llm_monitoring.engine import _EngineMixin  # noqa: E402
from services.llm_monitoring.search_settings import set_project_search_mode  # noqa: E402


# ─── Pesos ────────────────────────────────────────────────────────────────────

class TestUnitWeights:
    def test_off_is_always_one_unit(self):
        for provider in DEFAULT_SEARCH_UNIT_WEIGHTS:
            assert units_per_task(provider, 'off') == 1
            assert units_per_task(provider, None) == 1
            assert units_per_task(provider, 'AUTO') == 1

    def test_auto_uses_provider_weight(self):
        assert units_by_provider(['openai', 'anthropic', 'google', 'perplexity'], 'auto') == {
            'openai': 7, 'anthropic': 10, 'google': 3, 'perplexity': 3,
        }
        assert units_per_task('unknown', 'auto') == 1

    def test_env_override_and_invalid_values(self, monkeypatch):
        monkeypatch.setenv('LLM_SEARCH_UNIT_WEIGHTS', '{"openai": 5}')
        assert llm_monitoring_limits._load_search_unit_weights()['openai'] == 5
        assert llm_monitoring_limits._load_search_unit_weights()['anthropic'] == 10

        for bad in ('{"openai": 0}', '{"desconocido": 2}', 'no-json', '[1, 2]'):
            monkeypatch.setenv('LLM_SEARCH_UNIT_WEIGHTS', bad)
            assert llm_monitoring_limits._load_search_unit_weights() == DEFAULT_SEARCH_UNIT_WEIGHTS

    def test_planned_units(self):
        queries = [{'id': 1}, {'id': 2}, {'id': 3}]
        weights = units_by_provider(['openai', 'google'], 'auto')
        assert count_planned_tasks(queries, ['openai', 'google']) == 6  # como antes
        assert count_planned_tasks(queries, ['openai', 'google'], None, weights) == 3 * 7 + 3 * 3
        restrict = {'openai': [1, 99], 'google': [2, 3]}
        assert count_planned_tasks(queries, ['openai', 'google'], restrict, weights) == 7 + 2 * 3


class TestUnitsSql:
    @pytest.fixture(autouse=True)
    def _reset(self):
        llm_monitoring_limits.UNITS_SCHEMA.reset()
        yield
        llm_monitoring_limits.UNITS_SCHEMA.reset()

    def test_counts_rows_until_migrated(self):
        with patch.object(llm_monitoring_limits.UNITS_SCHEMA, 'available', return_value=False):
            assert llm_units_sql('r') == 'COUNT(*)'

    def test_sums_weights_once_migrated(self):
        with patch.object(llm_monitoring_limits.UNITS_SCHEMA, 'available', return_value=True):
            assert llm_units_sql('r') == 'SUM(r.units_consumed)'
            assert llm_units_sql() == 'SUM(units_consumed)'


# ─── Engine ───────────────────────────────────────────────────────────────────

class _Engine(_EngineMixin):
    provider_semaphores = {}

    def analyze_brand_mention(self, **kwargs):
        return {
            'brand_mentioned': False, 'mention_count': 0, 'mention_contexts': [],
            'appears_in_numbered_list': False, 'position_in_list': None, 'total_items_in_list': None,
            'position_source': None, 'competitors_mentioned': {},
        }


def _task(llm_name='openai', search_mode='auto', result=None):
    provider = MagicMock()
    provider.execute_query.return_value = result or {
        'success': True, 'content': 'respuesta', 'sources': [], 'tokens': 3, 'input_tokens': 1,
        'output_tokens': 2, 'cost_usd': 0.3, 'response_time_ms': 900, 'model_used': 'gpt-5.5',
        'search_used': True, 'search_calls': 3, 'search_queries': [],
    }
    return {
        'project_id': 1, 'query_id': 2, 'query_text': 'q', 'execution_query': 'q', 'locale': None,
        'llm_name': llm_name, 'provider': provider, 'brand_name': 'Quipu', 'brand_domain': 'getquipu.com',
        'competitor_domains': [], 'analysis_date': date(2026, 9, 13), 'search_mode': search_mode,
    }


@pytest.fixture
def db():
    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.fetchone.return_value = {'id': 555}
    with patch('services.llm_monitoring.engine.get_db_connection', return_value=conn), \
         patch('services.llm_monitoring.engine.fanout_schema_available', return_value=True), \
         patch('services.llm_monitoring.engine.save_fanout'):
        yield cur


class TestEngineSearchMode:
    @pytest.mark.parametrize('mode,expected', [('auto', 'auto'), ('off', 'off'), (None, 'off'), ('AUTO', 'off')])
    def test_provider_receives_normalized_mode(self, db, mode, expected):
        task = _task(search_mode=mode)
        with patch.object(llm_monitoring_limits.UNITS_SCHEMA, 'available', return_value=True):
            _Engine()._execute_single_query_task(task)
        assert task['provider'].execute_query.call_args.kwargs['search_mode'] == expected

    def test_weighted_units_and_metadata(self, db):
        with patch('services.llm_monitoring.engine.UNITS_SCHEMA.available', return_value=True):
            result = _Engine()._execute_single_query_task(_task('anthropic', 'auto'))

        assert result['success'] is True
        sql, params = db.execute.call_args.args
        assert 'units_consumed' in sql and 'units_consumed = EXCLUDED.units_consumed' in sql
        assert sql.count('%s') == len(params)
        assert params[-1] == 10  # peso de Anthropic con búsqueda
        metadata = next(p for p in params if isinstance(p, str) and 'model_reported' in p)
        assert '"search_mode": "auto"' in metadata and '"search_calls": 3' in metadata

    def test_off_writes_one_unit(self, db):
        with patch('services.llm_monitoring.engine.UNITS_SCHEMA.available', return_value=True):
            _Engine()._execute_single_query_task(_task('openai', 'off'))
        sql, params = db.execute.call_args.args
        assert params[-1] == 1

    def test_without_units_migration_the_insert_is_unchanged(self, db):
        with patch('services.llm_monitoring.engine.UNITS_SCHEMA.available', return_value=False):
            _Engine()._execute_single_query_task(_task('openai', 'auto'))
        sql, params = db.execute.call_args.args
        assert 'units_consumed' not in sql and sql.count('%s') == len(params)

    def test_error_rows_count_one_unit(self, db):
        task = _task('openai', 'auto', result={'success': False, 'error': 'boom'})
        with patch('services.llm_monitoring.engine.UNITS_SCHEMA.available', return_value=True):
            _Engine()._execute_single_query_task(task)
        sql = db.execute.call_args.args[0]
        assert 'has_error = TRUE' in sql and 'units_consumed = 1' in sql


# ─── Interruptor en el admin ──────────────────────────────────────────────────

@pytest.fixture
def settings_db():
    conn = MagicMock()
    cur = conn.cursor.return_value
    with patch('services.llm_monitoring.search_settings.get_db_connection', return_value=conn):
        yield conn, cur


class TestSetProjectSearchMode:
    @pytest.mark.parametrize('bad', [None, '', 'AUTO', 'on', 'memory'])
    def test_rejects_unknown_values(self, bad):
        with pytest.raises(ValueError):
            set_project_search_mode(1, bad)

    def test_enable_sets_activation_date(self, settings_db):
        conn, cur = settings_db
        enabled_at = MagicMock(isoformat=MagicMock(return_value='2026-09-14T10:00:00+00:00'))
        cur.fetchone.side_effect = [
            {'id': 7, 'user_id': 5, 'name': 'Fini', 'search_mode': 'off', 'search_enabled_at': None},
            {'search_enabled_at': enabled_at},
        ]
        result = set_project_search_mode(7, 'auto')

        update_sql, params = cur.execute.call_args_list[1].args
        assert 'UPDATE llm_monitoring_projects' in update_sql and 'RETURNING search_enabled_at' in update_sql
        assert params == ('auto', True, 7)
        conn.commit.assert_called_once()
        assert result == {
            'success': True, 'project_id': 7, 'user_id': 5, 'name': 'Fini',
            'previous_search_mode': 'off', 'search_mode': 'auto',
            'search_enabled_at': '2026-09-14T10:00:00+00:00', 'changed': True,
        }

    def test_disable_keeps_activation_date(self, settings_db):
        _conn, cur = settings_db
        cur.fetchone.side_effect = [
            {'id': 7, 'user_id': 5, 'name': 'Fini', 'search_mode': 'auto', 'search_enabled_at': None},
            {'search_enabled_at': None},
        ]
        result = set_project_search_mode(7, 'off')
        assert cur.execute.call_args_list[1].args[1] == ('off', False, 7)
        assert result['changed'] is True and result['search_mode'] == 'off'

    def test_same_mode_does_not_write(self, settings_db):
        conn, cur = settings_db
        cur.fetchone.return_value = {'id': 7, 'user_id': 5, 'name': 'Fini', 'search_mode': 'off',
                                     'search_enabled_at': None}
        result = set_project_search_mode(7, 'off')
        assert cur.execute.call_count == 1 and result['changed'] is False

    def test_unknown_project(self, settings_db):
        conn, cur = settings_db
        cur.fetchone.return_value = None
        assert set_project_search_mode(99, 'auto') == {'success': False, 'error': 'Project not found'}
        conn.rollback.assert_called_once()


def test_user_project_update_route_cannot_change_search_mode():
    """Solo el admin cambia el interruptor: la ruta de edición del usuario no lo acepta."""
    src = open(os.path.join(os.path.dirname(__file__), '..', 'llm_monitoring_routes.py')).read()
    assert 'search_mode' not in src


def test_admin_route_is_admin_only():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'auth.py')).read()
    route = src.index("/admin/projects/llm_monitoring/<int:project_id>/search-mode")
    assert src.index('@admin_required', route) < src.index('def admin_set_llm_search_mode', route)
