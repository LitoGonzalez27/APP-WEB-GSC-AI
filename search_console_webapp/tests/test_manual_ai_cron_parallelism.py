"""Cron de Manual AI: proyectos en paralelo y timeout real de SerpAPI.

1. `MANUAL_AI_PROJECT_PARALLELISM` (por defecto 1) reparte proyectos entre
   hilos; las estadísticas agregadas son las mismas que en serie y un proyecto
   que revienta cuenta como fallido sin tumbar al resto.
2. Las llamadas a SerpAPI llevan un timeout en segundos (la librería pasa
   60000 a requests, que son ~17 h).
"""
import os
import threading
import time

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5/dummy")

from manual_ai.services.cron_service import CronService  # noqa: E402
import quota_middleware  # noqa: E402


def _cron_with(outcomes, delay=0.0):
    """CronService sin __init__ (no toca BD) con _process_single_project simulado."""
    cron = CronService.__new__(CronService)
    seen_threads = set()
    lock = threading.Lock()

    def fake_single(project):
        with lock:
            seen_threads.add(threading.current_thread().name)
        time.sleep(delay)
        outcome = outcomes[project['id']]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    cron._process_single_project = fake_single
    return cron, seen_threads


PROJECTS = [{'id': i} for i in range(1, 7)]
OUTCOMES = {
    1: ('successful', 200), 2: ('successful', 150), 3: ('skipped', 0),
    4: ('failed', 0), 5: ('successful', 45), 6: ('successful', 30),
}
EXPECTED = {'successful': 4, 'failed': 1, 'skipped': 1, 'total_keywords': 425}


class TestProjectParallelism:
    def test_default_is_sequential(self, monkeypatch):
        monkeypatch.delenv('MANUAL_AI_PROJECT_PARALLELISM', raising=False)
        cron, threads = _cron_with(OUTCOMES)
        assert cron._process_projects(PROJECTS) == EXPECTED
        assert threads == {threading.current_thread().name}

    @pytest.mark.parametrize('value', ['0', '-3', 'abc', ''])
    def test_invalid_values_fall_back_to_sequential(self, monkeypatch, value):
        monkeypatch.setenv('MANUAL_AI_PROJECT_PARALLELISM', value)
        cron, threads = _cron_with(OUTCOMES)
        assert cron._process_projects(PROJECTS) == EXPECTED
        assert threads == {threading.current_thread().name}

    def test_parallel_same_stats_and_faster(self, monkeypatch):
        monkeypatch.setenv('MANUAL_AI_PROJECT_PARALLELISM', '3')
        cron, threads = _cron_with(OUTCOMES, delay=0.2)
        started = time.time()
        assert cron._process_projects(PROJECTS) == EXPECTED
        assert time.time() - started < 0.2 * len(PROJECTS) * 0.75
        assert len(threads) == 3
        assert all(name.startswith('manual-ai-cron') for name in threads)

    def test_real_single_project_never_raises(self, monkeypatch):
        """El camino real convierte cualquier error del proyecto en 'failed'."""
        monkeypatch.setenv('MANUAL_AI_PROJECT_PARALLELISM', '2')
        import manual_ai.services.cron_service as mod
        monkeypatch.setattr(mod, 'get_db_connection', lambda: None)
        cron = CronService.__new__(CronService)
        stats = cron._process_projects([(1, 'a', 'a.com', 'ES', 7, 10),
                                        (2, 'b', 'b.com', 'ES', 7, 10)])
        assert stats == {'successful': 0, 'failed': 2, 'skipped': 0, 'total_keywords': 0}


class TestSerpapiTimeout:
    def test_search_gets_timeout_in_seconds(self):
        search = quota_middleware._google_search({'q': 'x', 'api_key': 'k'})
        assert search.timeout == quota_middleware.SERPAPI_TIMEOUT_SECONDS
        # Por encima del corte interno de SerpAPI (~90 s) y muy lejos de 60000
        assert 90 < search.timeout <= 300

    def test_timeout_error_is_retried(self):
        msg = "HTTPSConnectionPool(host='serpapi.com', port=443): Read timed out. (read timeout=120.0)"
        assert quota_middleware._should_retry_serp_error(msg)

    def test_execute_uses_timeout(self, monkeypatch):
        captured = {}

        class FakeSearch:
            def __init__(self, params):
                self.timeout = 60000

            def get_dict(self):
                captured['timeout'] = self.timeout
                return {'organic_results': []}

        monkeypatch.setattr(quota_middleware, 'GoogleSearch', FakeSearch)
        ok, _ = quota_middleware._execute_serp_call({'q': 'x'}, 'json')
        assert ok and captured['timeout'] == quota_middleware.SERPAPI_TIMEOUT_SECONDS
