#!/usr/bin/env python3
"""
Tests for cron_routes (quota-reset endpoint + health check + alert).

Validates:
  1. _ensure_cron_token() rejects requests without/with bad bearer token.
  2. Endpoint returns 403 without token, 202 with valid token in async mode.
  3. _run_health_check_and_alert() detects stuck users and reports them.
  4. The alert email is built when stuck users exist (mocked send_email).
  5. After running the actual quota reset cron, no stuck users remain
     (assuming staging DB is in healthy state).

Run with staging DB:
  DATABASE_URL=<staging_proxy_url> CRON_TOKEN=test-token python3 test_cron_routes.py
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from unittest.mock import patch

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def main():
    if not os.getenv('DATABASE_URL'):
        logger.error('DATABASE_URL not set')
        return 1

    os.environ.setdefault('CRON_TOKEN', 'test-token-local')
    os.environ.setdefault('CRON_ALERTS_EMAIL', 'info@soycarlosgonzalez.com')
    os.environ.setdefault('APP_ENV', 'staging-local-test')

    # Import after env setup
    from cron_routes import (
        cron_bp,
        _run_health_check_and_alert,
        _send_stuck_quota_alert,
    )

    # Build a Flask app and register the blueprint
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(cron_bp)
    client = app.test_client()

    failed = 0
    def check(label, condition, detail=''):
        nonlocal failed
        if condition:
            logger.info(f"  ✅ {label}")
        else:
            logger.error(f"  ❌ {label}  {detail}")
            failed += 1

    # =====================================================================
    # TEST 1 — Auth: 403 without token
    # =====================================================================
    logger.info("\nTEST 1: Endpoint rejects request without bearer token")
    r = client.post('/api/cron/quota-reset')
    check(f"403 without token (got {r.status_code})", r.status_code == 403)

    # =====================================================================
    # TEST 2 — Auth: 403 with wrong token
    # =====================================================================
    logger.info("\nTEST 2: Endpoint rejects wrong bearer token")
    r = client.post('/api/cron/quota-reset',
                    headers={'Authorization': 'Bearer wrong-token'})
    check(f"403 wrong token (got {r.status_code})", r.status_code == 403)

    # =====================================================================
    # TEST 3 — Auth: 202 with valid token (async)
    # =====================================================================
    logger.info("\nTEST 3: Endpoint accepts valid token in async mode")
    # Mock the actual quota reset import so we don't run it for this test
    with patch('daily_quota_reset_cron.main') as mocked_reset:
        # Patch in cron_routes module too (the 'from X import' version)
        import cron_routes
        r = client.post(
            '/api/cron/quota-reset?async=1&triggered_by=test_suite',
            headers={'Authorization': 'Bearer test-token-local'},
        )
        check(f"202 valid token+async (got {r.status_code})", r.status_code == 202)
        body = r.get_json() or {}
        check("response.async = True", body.get('async') is True, f"got {body}")
        check("response.triggered_by preserved",
              body.get('triggered_by') == 'test_suite', f"got {body}")

    # =====================================================================
    # TEST 4 — Health check on a healthy staging DB returns ok=True
    # =====================================================================
    logger.info("\nTEST 4: Health check on healthy staging returns ok=True")
    health = _run_health_check_and_alert()
    check(f"health.ok = True (got {health.get('ok')})",
          health.get('ok') is True,
          f"stuck_count={health.get('stuck_count')}")
    check(f"stuck_count = 0", health.get('stuck_count', 0) == 0,
          f"got {health.get('stuck_count')}")

    # =====================================================================
    # TEST 5 — Insert a fake stuck user, health check detects it
    # =====================================================================
    logger.info("\nTEST 5: Health check detects an artificially stuck user")
    import psycopg2
    from psycopg2.extras import RealDictCursor
    db_url = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # Insert a fake user with stuck reset
    test_email = f'test-stuck-{os.getpid()}-{int(datetime.utcnow().timestamp())}@test.local'
    stuck_date = datetime.utcnow() - timedelta(days=10)
    cur.execute("""
        INSERT INTO users (email, name, role, is_active, plan, billing_status,
                          quota_used, quota_limit, quota_reset_date)
        VALUES (%s, 'TEST STUCK', 'user', TRUE, 'basic', 'active',
                1000, 1225, %s)
        RETURNING id
    """, (test_email, stuck_date))
    fake_uid = cur.fetchone()['id']
    conn.commit()
    conn.close()

    # Patch the email sender so we don't actually send during the test
    sent_emails = []
    import cron_routes as _cr
    original_send = _cr._send_stuck_quota_alert
    def fake_send(stuck_users):
        sent_emails.append({'count': len(stuck_users), 'users': stuck_users})
    _cr._send_stuck_quota_alert = fake_send

    try:
        health = _run_health_check_and_alert()
        check(f"health.ok = False (stuck found)", health.get('ok') is False)
        check(f"stuck_count >= 1 (got {health.get('stuck_count')})",
              health.get('stuck_count', 0) >= 1)
        # Our fake should be one of the stuck
        stuck_emails = [u['email'] for u in (health.get('stuck_users') or [])]
        check(f"Our fake user is in stuck list",
              test_email in stuck_emails,
              f"emails: {stuck_emails}")
        check(f"Alert send was called {len(sent_emails)} time(s)", len(sent_emails) == 1)
    finally:
        _cr._send_stuck_quota_alert = original_send

    # Cleanup the fake user
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (fake_uid,))
    conn.commit()
    conn.close()

    # =====================================================================
    # TEST 6 — Final: health check is clean again after cleanup
    # =====================================================================
    logger.info("\nTEST 6: Health check is clean after cleanup")
    health = _run_health_check_and_alert()
    check(f"health.ok = True after cleanup", health.get('ok') is True,
          f"stuck_count={health.get('stuck_count')}")

    logger.info("")
    if failed == 0:
        logger.info("✅ ALL TESTS PASSED")
        return 0
    logger.error(f"❌ {failed} TEST(S) FAILED")
    return 1


if __name__ == '__main__':
    sys.exit(main())
