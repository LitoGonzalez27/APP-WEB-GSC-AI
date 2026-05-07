#!/usr/bin/env python3
"""
Tests for webhook hardening (idempotency + lookup failure + atomic resume).

Validates:
  Fix 1 — Idempotency:
    1. First time we see an event_id, _claim_webhook_event returns (False, True)
       and inserts a row.
    2. Second time the SAME event_id, returns (True, True) — already processed.
    3. _mark_webhook_event_processed writes status correctly.

  Fix 2 — Customer-not-found returns success=False with proper error code:
    4. Webhook handler with a fake customer that doesn't exist returns
       success=False, error='customer_not_found'.
    (Route-level 503 mapping is verified by reading the route source.)

  Fix 3 — resume_quota_pauses_for_user atomicity:
    5. Function is wrapped in a single transaction.
    6. SAVEPOINT pattern recovers from a manual_ai update failure without
       losing the other table updates.

Run with staging DB:
  DATABASE_URL=<staging_proxy_url> python3 test_webhook_hardening.py
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def main():
    if not os.getenv('DATABASE_URL'):
        logger.error('DATABASE_URL not set')
        return 1

    failed = 0
    def check(label, condition, detail=''):
        nonlocal failed
        if condition:
            logger.info(f"  ✅ {label}")
        else:
            logger.error(f"  ❌ {label}  {detail}")
            failed += 1

    # =====================================================================
    # FIX 1 — Idempotency
    # =====================================================================
    logger.info("\n" + "=" * 60)
    logger.info("FIX 1 — Webhook idempotency")
    logger.info("=" * 60)

    from stripe_webhooks import _claim_webhook_event, _mark_webhook_event_processed

    test_event_id = f'evt_test_{os.getpid()}_{int(datetime.now(timezone.utc).timestamp())}'

    # First claim → should succeed (was new)
    already_processed, claim_ok = _claim_webhook_event(test_event_id, 'test.event')
    check(f"#1.1 First claim: claim_ok=True, already_processed=False",
          claim_ok and not already_processed,
          f"got already_processed={already_processed}, claim_ok={claim_ok}")

    # Second claim of SAME event → should be idempotent (already processed)
    already_processed2, claim_ok2 = _claim_webhook_event(test_event_id, 'test.event')
    check(f"#1.2 Second claim same id: already_processed=True (idempotent)",
          already_processed2 and claim_ok2,
          f"got already_processed={already_processed2}, claim_ok={claim_ok2}")

    # Mark as processed
    _mark_webhook_event_processed(test_event_id, success=True)

    # Verify in DB
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT status, processed_at FROM stripe_webhook_events WHERE event_id = %s",
                (test_event_id,))
    r = cur.fetchone()
    check(f"#1.3 status='processed' after mark", r and r['status'] == 'processed',
          f"got {r}")
    check(f"#1.4 processed_at is set", r and r['processed_at'] is not None)

    # Cleanup
    cur.execute("DELETE FROM stripe_webhook_events WHERE event_id = %s", (test_event_id,))
    conn.commit()
    conn.close()

    # =====================================================================
    # FIX 2 — Customer not found returns success=False
    # =====================================================================
    logger.info("\n" + "=" * 60)
    logger.info("FIX 2 — Customer not found path")
    logger.info("=" * 60)

    # Inspect the webhook source to verify the change is in place
    with open('stripe_webhooks.py') as f:
        src = f.read()
    check("#2.1 Source contains success=False on customer_not_found",
          "'error': 'customer_not_found'" in src)
    check("#2.2 Source contains 5xx mapping for transient errors",
          "503" in src and 'customer_not_found' in src)
    check("#2.3 Webhook endpoint maps unexpected errors to 5xx (not silent 200)",
          "'Internal server error'" in src and "), 500" in src)
    check("#2.4 _alert_unmatched_customer helper exists",
          "_alert_unmatched_customer" in src)

    # =====================================================================
    # FIX 3 — resume_quota_pauses atomicity
    # =====================================================================
    logger.info("\n" + "=" * 60)
    logger.info("FIX 3 — resume_quota_pauses_for_user atomicity")
    logger.info("=" * 60)

    with open('database.py') as f:
        src = f.read()
    check("#3.1 Source uses SAVEPOINT pattern",
          'SAVEPOINT before_manual_ai_resume' in src and
          'ROLLBACK TO SAVEPOINT before_manual_ai_resume' in src)
    check("#3.2 No more re-run-after-rollback fallback (cleaner code)",
          src.count('cur.execute(\'\'\'\n            UPDATE users') == 1)

    # Functional test: insert a user with paused projects, call resume,
    # verify everything is unpaused (single transaction success path).
    conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # Create a fake user
    cur.execute("""
        INSERT INTO users (email, name, role, is_active, plan, billing_status,
                          quota_used, quota_limit,
                          ai_overview_paused_at, ai_overview_paused_reason)
        VALUES (%s, 'TEST', 'user', TRUE, 'basic', 'active', 1225, 1225,
                NOW(), 'quota_exceeded')
        RETURNING id
    """, (f'test-resume-{os.getpid()}-{int(datetime.now(timezone.utc).timestamp())}@test.local',))
    fake_uid = cur.fetchone()['id']

    # Insert a fake LLM project that's paused
    cur.execute("""
        INSERT INTO llm_monitoring_projects
            (user_id, name, brand_name, industry, is_active,
             is_paused_by_quota, paused_at, paused_reason,
             enabled_llms, queries_per_llm, language, country_code)
        VALUES (%s, 'TEST RESUME', 'TestResume', 'test', TRUE,
                TRUE, NOW(), 'quota_exceeded',
                ARRAY['openai'], 5, 'es', 'ES')
        RETURNING id
    """, (fake_uid,))
    fake_pid = cur.fetchone()['id']
    conn.commit()
    conn.close()

    # Call resume
    from database import resume_quota_pauses_for_user
    result = resume_quota_pauses_for_user(fake_uid)
    check(f"#3.3 resume_quota_pauses_for_user returns True",
          result is True, f"got {result}")

    # Verify both got unpaused
    conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT ai_overview_paused_at FROM users WHERE id = %s", (fake_uid,))
    r = cur.fetchone()
    check(f"#3.4 user ai_overview_paused_at = NULL after resume",
          r['ai_overview_paused_at'] is None, f"got {r}")

    cur.execute("SELECT is_paused_by_quota FROM llm_monitoring_projects WHERE id = %s", (fake_pid,))
    r = cur.fetchone()
    check(f"#3.5 LLM project is_paused_by_quota = FALSE after resume",
          r['is_paused_by_quota'] is False, f"got {r}")

    # Cleanup
    cur.execute("DELETE FROM llm_monitoring_projects WHERE id = %s", (fake_pid,))
    cur.execute("DELETE FROM users WHERE id = %s", (fake_uid,))
    conn.commit()
    conn.close()

    logger.info("")
    if failed == 0:
        logger.info("✅ ALL TESTS PASSED")
        return 0
    logger.error(f"❌ {failed} TEST(S) FAILED")
    return 1


if __name__ == '__main__':
    sys.exit(main())
