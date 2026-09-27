#!/usr/bin/env python3
"""
Unit tests for project_timeout.run_project_with_timeout.

Validates:
  1. Fast call returns the real result dict.
  2. Slow call (sleeps longer than timeout) returns synthetic timeout dict.
  3. Exception in target propagates to error dict (not raised).
  4. Disabled timeout (timeout_sec=0) calls directly without thread.
  5. The orchestrator receives a list-friendly dict on every path.
  6. Multiple projects in a row: one timing out doesn't break the next one.

No DB needed for these tests.
"""

import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def main():
    from project_timeout import run_project_with_timeout

    failed = 0
    def check(label, condition, detail=''):
        nonlocal failed
        if condition:
            logger.info(f"  ✅ {label}")
        else:
            logger.error(f"  ❌ {label}  {detail}")
            failed += 1

    logger.info("=" * 70)
    logger.info("TEST 1: Fast call returns real result")
    logger.info("=" * 70)
    def fast_target():
        return {'project_id': 1, 'success': True, 'queries': 42}
    r = run_project_with_timeout(fast_target, project_id=1, timeout_sec=5.0)
    check("Returns success dict", r.get('success') is True, f"got {r}")
    check("Queries count preserved", r.get('queries') == 42, f"got {r}")
    check("Not flagged as timed_out", not r.get('timed_out'), f"got {r}")

    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 2: Slow call exceeds timeout → synthetic result")
    logger.info("=" * 70)
    def slow_target():
        time.sleep(3.0)
        return {'project_id': 2, 'success': True}
    t0 = time.monotonic()
    r = run_project_with_timeout(slow_target, project_id=2, timeout_sec=0.5)
    elapsed = time.monotonic() - t0
    check("Timed out within ~0.5s", 0.4 < elapsed < 1.0, f"elapsed={elapsed:.2f}")
    check("project_id preserved", r.get('project_id') == 2, f"got {r}")
    check("success=False", r.get('success') is False, f"got {r}")
    check("timed_out=True flag set", r.get('timed_out') is True, f"got {r}")
    check("error mentions timeout", 'timeout' in r.get('error', '').lower(), f"got {r}")

    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 3: Exception in target → error dict (not raised)")
    logger.info("=" * 70)
    def bad_target():
        raise RuntimeError("simulated provider failure")
    try:
        r = run_project_with_timeout(bad_target, project_id=3, timeout_sec=2.0)
        check("Did not re-raise", True)
        check("project_id preserved", r.get('project_id') == 3, f"got {r}")
        check("success=False", r.get('success') is False, f"got {r}")
        check("error message present",
              'simulated provider failure' in r.get('error', ''),
              f"got {r}")
        check("Not flagged as timed_out", not r.get('timed_out'), f"got {r}")
    except Exception as e:
        check("Did not re-raise", False, f"raised {e}")

    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 4: timeout_sec=0 disables timeout (direct call)")
    logger.info("=" * 70)
    def normal_target():
        return {'project_id': 4, 'success': True, 'mode': 'direct'}
    r = run_project_with_timeout(normal_target, project_id=4, timeout_sec=0)
    check("Returns real result without timeout layer",
          r.get('mode') == 'direct', f"got {r}")

    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 5: Disabled timeout still catches exceptions")
    logger.info("=" * 70)
    r = run_project_with_timeout(bad_target, project_id=5, timeout_sec=0)
    check("Returns error dict on disabled timeout + exception",
          r.get('success') is False and 'simulated provider failure' in r.get('error', ''),
          f"got {r}")

    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 6: Sequence — slow project doesn't break next fast one")
    logger.info("=" * 70)
    results = []
    # Project A: fast OK
    results.append(run_project_with_timeout(
        lambda: {'project_id': 'A', 'success': True}, project_id='A', timeout_sec=2.0))
    # Project B: slow → timeout
    results.append(run_project_with_timeout(
        lambda: (time.sleep(3) or {'project_id': 'B', 'success': True}),
        project_id='B', timeout_sec=0.4))
    # Project C: fast OK after timeout
    results.append(run_project_with_timeout(
        lambda: {'project_id': 'C', 'success': True}, project_id='C', timeout_sec=2.0))

    check("3 results collected", len(results) == 3)
    check("A succeeded", results[0].get('success') is True)
    check("B timed out", results[1].get('timed_out') is True)
    check("C succeeded after timeout", results[2].get('success') is True)

    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 7: Env var LLM_PROJECT_TIMEOUT_MINUTES is read")
    logger.info("=" * 70)
    import os
    from project_timeout import get_project_timeout_seconds
    os.environ['LLM_PROJECT_TIMEOUT_MINUTES'] = '0.01'  # 0.6 seconds
    timeout_s = get_project_timeout_seconds()
    check("Env override applied", abs(timeout_s - 0.6) < 0.01, f"got {timeout_s}")
    # Verify timeout actually fires using env-configured value
    r = run_project_with_timeout(slow_target, project_id=7)  # uses env default
    check("Env-configured timeout triggers", r.get('timed_out') is True, f"got {r}")
    os.environ.pop('LLM_PROJECT_TIMEOUT_MINUTES', None)

    logger.info("")
    if failed == 0:
        logger.info(f"✅ ALL TESTS PASSED")
        return 0
    else:
        logger.error(f"❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
