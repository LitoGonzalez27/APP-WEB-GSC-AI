#!/usr/bin/env python3
"""
Local test for cron_alerts module.

Strategy:
  1. Connect to STAGING DB.
  2. Insert a fake run row with extreme values (duration ~150 min, 30% failed).
  3. Call check_and_send_cron_alerts(fake_run_id).
  4. Verify the function returns alerts_triggered > 0 and an email is attempted.
  5. Clean up the fake row.

Usage (staging DB connection passed via env var):
  DATABASE_URL=<staging_proxy_url> \\
  CRON_ALERTS_EMAIL=info@soycarlosgonzalez.com \\
  python3 test_cron_alerts.py [--send-real-email]

By default the email is NOT actually sent (we monkey-patch send_email to log only).
Pass --send-real-email to test the full path including SMTP.
"""

import sys
import os
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    send_real = '--send-real-email' in sys.argv

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error('DATABASE_URL not set; aborting')
        return 1

    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Insert fake run in a separate connection so it commits before we read it
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    started = datetime.now() - timedelta(minutes=150)  # 150 min ago → triggers duration
    completed = datetime.now()

    cur.execute(
        """
        INSERT INTO llm_monitoring_analysis_runs
            (started_at, completed_at, status, total_projects,
             successful_projects, failed_projects, total_queries, triggered_by)
        VALUES (%s, %s, 'completed', 10, 7, 3, 600, 'test_cron_alerts')
        RETURNING id
        """,
        (started, completed),
    )
    fake_run_id = cur.fetchone()['id']
    conn.commit()
    conn.close()

    logger.info(f'Inserted fake run id={fake_run_id} (duration ~150min, 30% failure rate)')

    # Patch email_service.send_email if not sending real
    if not send_real:
        import email_service
        original_send = email_service.send_email
        captured = {}

        def fake_send(to_email, subject, html_body, text_body=None):
            captured['to'] = to_email
            captured['subject'] = subject
            captured['html_len'] = len(html_body)
            logger.info(f'[FAKE SEND] to={to_email}, subject="{subject}", html={len(html_body)}b')
            return True

        email_service.send_email = fake_send

    # Run the actual alert check
    try:
        from cron_alerts import check_and_send_cron_alerts
        result = check_and_send_cron_alerts(fake_run_id)
        logger.info(f'Alert result: {result}')

        # Validations
        assert result['alerts_triggered'] >= 1, f"Expected ≥1 alert, got {result}"
        assert 'duration' in result.get('alerts', []), \
            f"Expected 'duration' alert, got {result.get('alerts')}"
        assert 'error_rate' in result.get('alerts', []), \
            f"Expected 'error_rate' alert, got {result.get('alerts')}"
        if not send_real:
            assert captured.get('to') == os.getenv('CRON_ALERTS_EMAIL', 'info@soycarlosgonzalez.com')
            assert captured.get('html_len', 0) > 500, "HTML body unexpectedly short"

        logger.info('✅ All assertions passed')
        return 0

    except AssertionError as e:
        logger.error(f'❌ ASSERTION FAILED: {e}')
        return 1
    except Exception as e:
        logger.error(f'❌ UNEXPECTED ERROR: {e}', exc_info=True)
        return 1
    finally:
        # Clean up fake run
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute(
                'DELETE FROM llm_monitoring_analysis_runs WHERE id = %s', (fake_run_id,)
            )
            conn.commit()
            conn.close()
            logger.info(f'🧹 Cleaned up fake run id={fake_run_id}')
        except Exception as e:
            logger.warning(f'Cleanup failed: {e}')


if __name__ == '__main__':
    sys.exit(main())
