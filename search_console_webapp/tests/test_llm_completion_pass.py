"""
Tests de la pasada de completitud del cron LLM Monitoring (Fase B).

La pasada reintenta SOLO los pares (query, llm) que faltan tras un análisis
incompleto (huecos por 529/circuit breaker/timeouts) y reconstruye los
snapshots afectados desde BD. Debe tener coste cero cuando todo está completo
y estar acotada en tiempo y número de pares.
"""

import json
import os
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from services.llm_monitoring.completion import (
    compute_missing_pairs,
    count_planned_tasks,
    get_completion_config,
    task_allowed,
)


class TestTaskAllowed(unittest.TestCase):
    def test_no_restriction_allows_everything(self):
        self.assertTrue(task_allowed(None, 'anthropic', 42))

    def test_pair_in_restriction_allowed(self):
        self.assertTrue(task_allowed({'anthropic': [42, 43]}, 'anthropic', 42))

    def test_pair_not_in_restriction_blocked(self):
        self.assertFalse(task_allowed({'anthropic': [42, 43]}, 'anthropic', 99))

    def test_llm_absent_from_restriction_blocked(self):
        # google completó todo → no está en el dict → no ejecuta nada
        self.assertFalse(task_allowed({'anthropic': [42]}, 'google', 42))

    def test_empty_list_blocked(self):
        self.assertFalse(task_allowed({'anthropic': []}, 'anthropic', 42))


class TestCountPlannedTasks(unittest.TestCase):
    QUERIES = [{'id': 1}, {'id': 2}, {'id': 3}]

    def test_normal_mode_full_product(self):
        self.assertEqual(count_planned_tasks(self.QUERIES, ['a', 'b'], None), 6)

    def test_restricted_counts_only_listed_pairs(self):
        restrict = {'a': [1, 3]}
        self.assertEqual(count_planned_tasks(self.QUERIES, ['a', 'b'], restrict), 2)

    def test_restricted_ignores_stale_query_ids(self):
        # id 99 ya no es una query activa → no cuenta para la cuota
        restrict = {'a': [1, 99]}
        self.assertEqual(count_planned_tasks(self.QUERIES, ['a'], restrict), 1)

    def test_restricted_ignores_inactive_provider(self):
        # provider 'c' no está activo → sus pares no cuentan
        restrict = {'a': [1], 'c': [1, 2, 3]}
        self.assertEqual(count_planned_tasks(self.QUERIES, ['a', 'b'], restrict), 1)


class TestComputeMissingPairs(unittest.TestCase):
    def test_detects_missing_pairs(self):
        missing, truncated = compute_missing_pairs(
            active_query_ids=[1, 2, 3],
            ok_pairs={(1, 'anthropic'), (2, 'anthropic')},
            llms=['anthropic'],
        )
        self.assertEqual(missing, {'anthropic': [3]})
        self.assertEqual(truncated, 0)

    def test_error_rows_count_as_missing(self):
        # Las filas con has_error=TRUE no entran en ok_pairs → se reintentan
        missing, _ = compute_missing_pairs(
            active_query_ids=[1, 2],
            ok_pairs={(1, 'anthropic')},  # la 2 quedó como fila de error
            llms=['anthropic'],
        )
        self.assertEqual(missing, {'anthropic': [2]})

    def test_complete_project_returns_empty(self):
        missing, truncated = compute_missing_pairs(
            active_query_ids=[1, 2],
            ok_pairs={(1, 'a'), (2, 'a'), (1, 'b'), (2, 'b')},
            llms=['a', 'b'],
        )
        self.assertEqual(missing, {})
        self.assertEqual(truncated, 0)

    def test_provider_with_zero_results_gets_all(self):
        # Provider excluido por health-check o caído: 0/N → todos los pares
        missing, _ = compute_missing_pairs(
            active_query_ids=[1, 2, 3],
            ok_pairs=set(),
            llms=['perplexity'],
        )
        self.assertEqual(missing, {'perplexity': [1, 2, 3]})

    def test_cap_truncates_deterministically_and_reports(self):
        missing, truncated = compute_missing_pairs(
            active_query_ids=[1, 2, 3, 4, 5],
            ok_pairs=set(),
            llms=['a', 'b'],
            max_pairs=6,
        )
        total = sum(len(v) for v in missing.values())
        self.assertEqual(total, 6)
        self.assertEqual(truncated, 4)
        # Orden preservado: primero se completa 'a' entera
        self.assertEqual(missing['a'], [1, 2, 3, 4, 5])
        self.assertEqual(missing['b'], [1])

    def test_multiple_llms_independent(self):
        missing, _ = compute_missing_pairs(
            active_query_ids=[1, 2],
            ok_pairs={(1, 'a'), (2, 'b')},
            llms=['a', 'b'],
        )
        self.assertEqual(missing, {'a': [2], 'b': [1]})


class TestCompletionConfig(unittest.TestCase):
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            for k in ('LLM_COMPLETION_PASS_ENABLED', 'LLM_COMPLETION_MAX_SECONDS',
                      'LLM_COMPLETION_SETTLE_SECONDS', 'LLM_COMPLETION_MAX_PAIRS'):
                os.environ.pop(k, None)
            config = get_completion_config()
        self.assertTrue(config['enabled'])
        self.assertEqual(config['max_seconds'], 900)
        self.assertEqual(config['settle_seconds'], 120)
        self.assertEqual(config['max_pairs_per_project'], 200)

    def test_env_overrides(self):
        with patch.dict(os.environ, {
            'LLM_COMPLETION_PASS_ENABLED': 'false',
            'LLM_COMPLETION_MAX_SECONDS': '300',
            'LLM_COMPLETION_SETTLE_SECONDS': '0',
            'LLM_COMPLETION_MAX_PAIRS': '50',
        }):
            config = get_completion_config()
        self.assertFalse(config['enabled'])
        self.assertEqual(config['max_seconds'], 300)
        self.assertEqual(config['settle_seconds'], 0)
        self.assertEqual(config['max_pairs_per_project'], 50)

    def test_garbage_env_falls_back_to_defaults(self):
        with patch.dict(os.environ, {'LLM_COMPLETION_MAX_SECONDS': 'banana'}):
            config = get_completion_config()
        self.assertEqual(config['max_seconds'], 900)


class _FakeCursor:
    """Cursor mínimo: devuelve filas preparadas y registra los SQL ejecutados."""

    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


class TestRebuildSnapshotFromDb(unittest.TestCase):
    """El rebuild mapea filas de BD a la forma de _create_snapshot (matemática canónica)."""

    def _subject(self):
        from services.llm_monitoring.engine import _EngineMixin

        captured = {}

        class Subject(_EngineMixin):
            def _create_snapshot(self, cur, project_id, date, llm_provider,
                                 llm_results, competitors, total_queries_expected=None):
                captured['args'] = {
                    'project_id': project_id, 'date': date,
                    'llm_provider': llm_provider, 'llm_results': llm_results,
                    'competitors': competitors,
                    'total_queries_expected': total_queries_expected,
                }

        return Subject(), captured

    def test_maps_db_rows_and_calls_canonical_snapshot(self):
        subject, captured = self._subject()
        rows = [
            {
                'brand_mentioned': True, 'position_in_list': 2,
                'competitors_mentioned': {'Haribo': 3},  # JSONB → dict
                'sentiment': 'positive', 'sentiment_score': Decimal('0.90'),
                'response_time_ms': 1500, 'cost_usd': Decimal('0.0031'),
                'tokens_used': 800,
            },
            {
                'brand_mentioned': False, 'position_in_list': None,
                'competitors_mentioned': json.dumps({'Trolli': 1}),  # string JSON
                'sentiment': 'neutral', 'sentiment_score': None,
                'response_time_ms': 900, 'cost_usd': Decimal('0.0011'),
                'tokens_used': 500,
            },
        ]
        cur = _FakeCursor(rows)

        subject._rebuild_snapshot_from_db(
            cur=cur, project_id=36, analysis_date=date(2026, 8, 22),
            llm_provider='anthropic', competitors=['Haribo', 'Trolli'],
            total_queries_expected=59,
        )

        args = captured['args']
        self.assertEqual(args['llm_provider'], 'anthropic')
        self.assertEqual(args['total_queries_expected'], 59)
        self.assertEqual(len(args['llm_results']), 2)

        first, second = args['llm_results']
        self.assertIs(first['brand_mentioned'], True)
        self.assertEqual(first['competitors_mentioned'], {'Haribo': 3})
        self.assertIsInstance(first['cost_usd'], float)       # Decimal coercionado
        self.assertIsInstance(first['sentiment_score'], float)
        self.assertEqual(second['competitors_mentioned'], {'Trolli': 1})  # str parseado
        self.assertIsNone(second['sentiment_score'])

        # El SELECT debe excluir filas de error
        select_sql = cur.executed[0][0]
        self.assertIn('has_error', select_sql)
        self.assertIn('FALSE', select_sql)

    def test_no_ok_rows_skips_snapshot(self):
        subject, captured = self._subject()
        cur = _FakeCursor([])
        subject._rebuild_snapshot_from_db(
            cur=cur, project_id=36, analysis_date=date(2026, 8, 22),
            llm_provider='anthropic', competitors=[],
        )
        self.assertNotIn('args', captured)  # _create_snapshot no llamado


if __name__ == '__main__':
    unittest.main()
