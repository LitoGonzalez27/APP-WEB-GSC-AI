"""
Comprobaciones del email de fin de run del cron LLM (cron_alerts._run_checks).

- provider_incomplete: respuestas que faltan en un LLM (caso real sept. 2026: el
  5-10 % de Claude desaparecía sin error y el email salía como OK).
- El email que se envía de verdad (send_run_completion_email) usa la misma lista
  de checks que check_and_send_cron_alerts, incluidos billing y completitud.
"""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import cron_alerts  # noqa: E402

RUN = {
    'id': 69, 'status': 'completed', 'error_message': None,
    'started_at': datetime(2026, 9, 11, 4, 0), 'completed_at': datetime(2026, 9, 11, 5, 0),
    'total_projects': 8, 'successful_projects': 8, 'failed_projects': 0, 'project_results': None,
}


def _conn_returning(rows):
    cur = MagicMock()
    cur.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


class TestProviderCompleteness:
    def test_real_september_gap_is_high(self):
        conn, _ = _conn_returning([
            {'llm_provider': 'anthropic', 'expected': 230, 'ok': 208},
            {'llm_provider': 'google', 'expected': 230, 'ok': 230},
        ])
        alert = cron_alerts._check_provider_completeness(RUN, lambda: conn)

        assert alert['type'] == 'provider_incomplete'
        assert alert['severity'] == 'high'
        assert 'anthropic 208/230' in alert['metric'] and 'google' not in alert['metric']

    def test_small_gap_is_medium(self):
        conn, _ = _conn_returning([{'llm_provider': 'openai', 'expected': 230, 'ok': 229}])
        assert cron_alerts._check_provider_completeness(RUN, lambda: conn)['severity'] == 'medium'

    def test_complete_run_has_no_alert(self):
        conn, _ = _conn_returning([
            {'llm_provider': p, 'expected': 149, 'ok': 149} for p in ('openai', 'anthropic', 'google', 'perplexity')
        ])
        assert cron_alerts._check_provider_completeness(RUN, lambda: conn) is None

    def test_uses_run_window(self):
        conn, cur = _conn_returning([])
        cron_alerts._check_provider_completeness(RUN, lambda: conn)
        assert cur.execute.call_args.args[1] == (RUN['started_at'], RUN['completed_at'])

    def test_db_error_never_raises(self):
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError('db down')
        assert cron_alerts._check_provider_completeness(RUN, lambda: conn) is None


class TestRunChecks:
    CFG = {'duration_min_threshold': 150, 'error_rate_threshold': 0.2, 'cost_multiplier_threshold': 2.0}

    def test_includes_every_check_and_survives_failures(self):
        names = ('_check_duration', '_check_error_rate', '_check_cost_spike', '_check_provider_coverage',
                 '_check_provider_completeness', '_check_provider_billing')
        patches = {n: patch.object(cron_alerts, n, return_value={'type': n, 'severity': 'medium'}) for n in names}
        with patches['_check_duration'], patches['_check_error_rate'], patches['_check_cost_spike'], \
             patches['_check_provider_coverage'], patches['_check_provider_completeness'], \
             patch.object(cron_alerts, '_check_provider_billing', side_effect=RuntimeError('boom')):
            alerts = cron_alerts._run_checks(RUN, self.CFG, lambda: None)

        assert [a['type'] for a in alerts] == list(names[:-1])   # el que revienta no tumba a los demás

    def test_completion_email_uses_all_checks(self):
        incomplete = {'type': 'provider_incomplete', 'severity': 'high', 'metric': 'anthropic 208/230',
                      'threshold': '100%', 'message': 'faltan'}
        with patch.object(cron_alerts, '_get_config', return_value={**self.CFG, 'enabled': True,
                                                                  'email': 'x@y.z', 'environment': 'production'}), \
             patch.object(cron_alerts, '_load_run', return_value=RUN), \
             patch.object(cron_alerts, '_run_checks', return_value=[incomplete]) as run_checks, \
             patch.object(cron_alerts, '_load_run_cost', return_value=17.0), \
             patch.object(cron_alerts, '_load_top_errors', return_value=[]), \
             patch('email_service.send_email', return_value=True) as send_email:
            result = cron_alerts.send_run_completion_email(69, get_db_connection_fn=lambda: None)

        run_checks.assert_called_once()
        assert result['severity'] == 'critical'
        assert result['alerts'] == ['provider_incomplete']
        subject = send_email.call_args.args[1]
        assert 'CRITICAL' in subject
