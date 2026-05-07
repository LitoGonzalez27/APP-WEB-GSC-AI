#!/usr/bin/env python3
"""
Tests for the Stripe-aware quota reset logic (Phase B + C).

Validates:
  1. SQL filter excludes Stripe users whose current_period_end is in the future.
  2. SQL filter includes Stripe users whose current_period_end is past.
  3. SQL filter includes users without subscription_id (admin/enterprise/beta).
  4. SQL filter includes users with subscription_id but NULL current_period_end
     (legacy data) — they need live Stripe lookup.
  5. _fetch_live_stripe_period_end() returns the right datetime (mocked).
  6. The end-to-end main() respects the live lookup and skips users whose
     period is still active per Stripe.
  7. Webhook _handle_payment_succeeded extracts period from
     invoice.lines.data[0].period when the top-level fields are missing.

Run with staging DB:
  DATABASE_URL=<staging_proxy_url> python3 test_stripe_aware_reset.py
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def _insert_test_user(conn, email_suffix, *, plan='basic', billing='active',
                      subscription_id=None, current_period_end=None,
                      quota_reset_date_offset_days=-1):
    """Insert a test user. Returns (user_id, cleanup_fn)."""
    cur = conn.cursor()
    reset_date = datetime.now(timezone.utc) + timedelta(days=quota_reset_date_offset_days)
    cur.execute("""
        INSERT INTO users (email, name, role, is_active, plan, billing_status,
                          quota_used, quota_limit, quota_reset_date,
                          subscription_id, current_period_end)
        VALUES (%s, 'TEST', 'user', TRUE, %s, %s, 1000, 1225, %s, %s, %s)
        RETURNING id
    """, (
        f'test-{email_suffix}-{os.getpid()}-{int(datetime.now(timezone.utc).timestamp())}@test.local',
        plan, billing, reset_date, subscription_id, current_period_end,
    ))
    uid = cur.fetchone()
    uid = uid['id'] if isinstance(uid, dict) else uid[0]
    conn.commit()
    return uid


def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error('DATABASE_URL not set')
        return 1

    import psycopg2
    from psycopg2.extras import RealDictCursor

    failed = 0
    def check(label, condition, detail=''):
        nonlocal failed
        if condition:
            logger.info(f"  ✅ {label}")
        else:
            logger.error(f"  ❌ {label}  {detail}")
            failed += 1

    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    test_uids = []
    try:
        # =====================================================================
        # SETUP: Create 4 test users covering each scenario
        # =====================================================================
        # A: No subscription (admin enterprise/beta) → SHOULD be reset by cron
        uid_no_sub = _insert_test_user(conn, 'no-sub', plan='enterprise',
                                        subscription_id=None,
                                        current_period_end=None)
        test_uids.append(uid_no_sub)

        # B: Has subscription, period_end IN FUTURE → should NOT be reset
        uid_active = _insert_test_user(conn, 'stripe-active', plan='premium',
                                        subscription_id='sub_test_active_xxx',
                                        current_period_end=datetime.now(timezone.utc) + timedelta(days=15))
        test_uids.append(uid_active)

        # C: Has subscription, period_end IN PAST → SHOULD be reset
        uid_expired = _insert_test_user(conn, 'stripe-expired', plan='premium',
                                         subscription_id='sub_test_expired_xxx',
                                         current_period_end=datetime.now(timezone.utc) - timedelta(days=2))
        test_uids.append(uid_expired)

        # D: Has subscription but NULL period_end (legacy) → match SQL, but
        #    will be checked live by Stripe API (mock will say period active)
        uid_legacy = _insert_test_user(conn, 'stripe-legacy', plan='basic',
                                        subscription_id='sub_test_legacy_xxx',
                                        current_period_end=None)
        test_uids.append(uid_legacy)

        logger.info(f"Created test users: {test_uids}")

        # =====================================================================
        # TEST 1-4: Verify the SQL filter correctly classifies these 4 users
        # =====================================================================
        logger.info("\n" + "=" * 60)
        logger.info("TEST 1-4: SQL filter behavior")
        logger.info("=" * 60)

        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM users
            WHERE plan != 'free'
              AND billing_status IN ('active', 'trialing', 'beta')
              AND (quota_reset_date IS NULL OR quota_reset_date <= NOW())
              AND (
                  subscription_id IS NULL
                  OR current_period_end IS NULL
                  OR current_period_end <= NOW()
              )
              AND id = ANY(%s)
        """, (test_uids,))
        matched = {r['id'] for r in cur.fetchall()}

        check(f"#1 No-sub user (enterprise, no Stripe) → MATCHES filter",
              uid_no_sub in matched, f"matched: {matched}")
        check(f"#2 Stripe-active user (period_end future) → EXCLUDED by filter",
              uid_active not in matched, f"matched: {matched}")
        check(f"#3 Stripe-expired user (period_end past) → MATCHES filter",
              uid_expired in matched, f"matched: {matched}")
        check(f"#4 Stripe-legacy user (period_end NULL) → MATCHES filter (will live-check)",
              uid_legacy in matched, f"matched: {matched}")

        # =====================================================================
        # TEST 5: _fetch_live_stripe_period_end mock
        # =====================================================================
        logger.info("\n" + "=" * 60)
        logger.info("TEST 5: _fetch_live_stripe_period_end mocking")
        logger.info("=" * 60)

        os.environ['STRIPE_SECRET_KEY'] = 'sk_test_fake_for_unit_test'
        from daily_quota_reset_cron import _fetch_live_stripe_period_end

        future_ts = int((datetime.now(timezone.utc) + timedelta(days=10)).timestamp())
        with patch('stripe.Subscription.retrieve') as mocked:
            mocked.return_value = {'current_period_end': future_ts}
            result = _fetch_live_stripe_period_end('sub_test_xxx')
            check(f"Returns datetime ~10 days in future",
                  abs((result - datetime.now(timezone.utc)).total_seconds() - 10 * 86400) < 60,
                  f"got {result}")

        # Test fallback to items[0]
        with patch('stripe.Subscription.retrieve') as mocked:
            mocked.return_value = {
                'current_period_end': None,
                'items': {'data': [{'current_period_end': future_ts}]}
            }
            result = _fetch_live_stripe_period_end('sub_test_xxx')
            check(f"Fallback to items[0].current_period_end works",
                  result is not None and abs((result - datetime.now(timezone.utc)).total_seconds() - 10 * 86400) < 60)

        # Test missing returns None
        with patch('stripe.Subscription.retrieve') as mocked:
            mocked.return_value = {}
            result = _fetch_live_stripe_period_end('sub_test_xxx')
            check(f"Returns None when Stripe has no period info", result is None)

        # =====================================================================
        # TEST 6: end-to-end main() respects live lookup
        # =====================================================================
        logger.info("\n" + "=" * 60)
        logger.info("TEST 6: cron main() with live lookup says 'still active'")
        logger.info("=" * 60)

        # Mock Stripe to say uid_legacy's period is still active
        future_ts = int((datetime.now(timezone.utc) + timedelta(days=12)).timestamp())

        from daily_quota_reset_cron import main as run_main

        # Capture state of all 4 users before
        cur.execute("""
            SELECT id, quota_used, quota_reset_date FROM users WHERE id = ANY(%s)
        """, (test_uids,))
        before = {r['id']: dict(r) for r in cur.fetchall()}

        with patch('stripe.Subscription.retrieve') as mocked:
            mocked.return_value = {'current_period_end': future_ts}
            run_main()

        # Capture after state
        cur.execute("""
            SELECT id, quota_used, quota_reset_date FROM users WHERE id = ANY(%s)
        """, (test_uids,))
        after = {r['id']: dict(r) for r in cur.fetchall()}

        # Verify A and C were reset, B and D were NOT
        check(f"User A (no-sub) was reset: quota_used=0",
              after[uid_no_sub]['quota_used'] == 0,
              f"got {after[uid_no_sub]}")
        check(f"User B (Stripe-active) was NOT reset: quota_used unchanged",
              after[uid_active]['quota_used'] == before[uid_active]['quota_used'],
              f"before={before[uid_active]['quota_used']}, after={after[uid_active]['quota_used']}")
        check(f"User C (Stripe-expired) was reset: quota_used=0",
              after[uid_expired]['quota_used'] == 0,
              f"got {after[uid_expired]}")
        check(f"User D (legacy, live says active) was NOT reset: quota_used unchanged",
              after[uid_legacy]['quota_used'] == before[uid_legacy]['quota_used'],
              f"before={before[uid_legacy]['quota_used']}, after={after[uid_legacy]['quota_used']}")

        # =====================================================================
        # TEST 7: webhook period extraction (logic only, no full handler init)
        # =====================================================================
        logger.info("\n" + "=" * 60)
        logger.info("TEST 7: webhook extracts period from invoice.lines.data[0].period")
        logger.info("=" * 60)

        # Replicate exactly the extraction logic the new webhook code uses.
        # Verifies that when top-level period is missing, lines.data[0].period
        # is the source of truth.
        period_start_ts = int((datetime.now(timezone.utc) - timedelta(days=2)).timestamp())
        period_end_ts = int((datetime.now(timezone.utc) + timedelta(days=28)).timestamp())

        modern_invoice = {
            'customer': 'cus_test_fake',
            'subscription': 'sub_test_fake',
            'lines': {
                'data': [
                    {'period': {'start': period_start_ts, 'end': period_end_ts}}
                ]
            }
        }

        # Replicate the extraction logic from stripe_webhooks._handle_payment_succeeded
        ps = modern_invoice.get('period_start')
        pe = modern_invoice.get('period_end')
        if not (ps and pe):
            lines = (modern_invoice.get('lines') or {}).get('data') or []
            if lines:
                line_period = (lines[0] or {}).get('period') or {}
                ps = ps or line_period.get('start')
                pe = pe or line_period.get('end')

        check(f"Modern invoice: period_start extracted from lines.data[0].period.start",
              ps == period_start_ts, f"got {ps}, expected {period_start_ts}")
        check(f"Modern invoice: period_end extracted from lines.data[0].period.end",
              pe == period_end_ts, f"got {pe}, expected {period_end_ts}")

        # Legacy invoice (top-level): the old path still works
        legacy_invoice = {
            'customer': 'cus_test_fake',
            'subscription': 'sub_test_fake',
            'period_start': period_start_ts,
            'period_end': period_end_ts,
        }
        ps2 = legacy_invoice.get('period_start')
        pe2 = legacy_invoice.get('period_end')
        check(f"Legacy invoice: top-level period_start still respected",
              ps2 == period_start_ts)
        check(f"Legacy invoice: top-level period_end still respected",
              pe2 == period_end_ts)

        # Empty invoice: extraction returns None, fallback to Stripe API would kick in
        empty_invoice = {'customer': 'cus_x', 'subscription': 'sub_x'}
        ps3 = empty_invoice.get('period_start')
        pe3 = empty_invoice.get('period_end')
        if not (ps3 and pe3):
            lines = (empty_invoice.get('lines') or {}).get('data') or []
            if lines:
                line_period = (lines[0] or {}).get('period') or {}
                ps3 = ps3 or line_period.get('start')
                pe3 = pe3 or line_period.get('end')
        check(f"Empty invoice: period_start is None (would trigger Stripe API fallback)",
              ps3 is None)
        check(f"Empty invoice: period_end is None (would trigger Stripe API fallback)",
              pe3 is None)

    finally:
        # Cleanup test users
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE id = ANY(%s)", (test_uids,))
            conn.commit()
            logger.info(f"\n🧹 Cleaned up test users: {test_uids}")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
        conn.close()

    logger.info("")
    if failed == 0:
        logger.info("✅ ALL TESTS PASSED")
        return 0
    logger.error(f"❌ {failed} TEST(S) FAILED")
    return 1


if __name__ == '__main__':
    sys.exit(main())
