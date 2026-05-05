"""
Hard per-project timeout wrapper for the LLM Monitoring cron.

When the cron iterates over many projects, a single project that gets stuck
(provider rate-limit cascade, runaway model, network hang) used to block the
entire run. This module wraps the per-project call in a daemon thread and
returns a synthetic timeout result if the project exceeds a configurable
deadline, allowing the orchestrator to continue with the next project.

Why a daemon thread + join(timeout) instead of forced kill?
-----------------------------------------------------------
Python doesn't have a clean way to forcibly terminate a thread. Forcing a
kill at the OS level can leave database transactions, file handles, and
locks in inconsistent state. Instead we:

  1. Run the worker in a daemon thread (so the process can exit even if
     the worker is still alive).
  2. Wait up to LLM_PROJECT_TIMEOUT_MINUTES (default 30) for it to finish.
  3. If the timeout fires we abandon the thread but the orchestrator keeps
     going.
  4. The abandoned thread will exit on its own within ~90 seconds because
     every LLM API call has a 60-90s socket-level timeout in
     services/retry_handler.py. When it exits, any borrowed DB connections
     are returned to the pool naturally.

So in the worst case the cron carries one or two "ghost" threads for ~90s
after a timeout — far better than a multi-hour stall.
"""

import os
import threading
import logging
from typing import Callable, Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_project_timeout_seconds() -> float:
    """Return the configured per-project timeout in seconds.

    LLM_PROJECT_TIMEOUT_MINUTES env var, defaults to 30 minutes. Setting it
    to 0 disables the timeout (the worker is awaited indefinitely — useful
    for debugging only).
    """
    minutes = float(os.getenv('LLM_PROJECT_TIMEOUT_MINUTES', '30'))
    return minutes * 60.0


def run_project_with_timeout(
    target: Callable[[], Dict[str, Any]],
    project_id: int,
    timeout_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """Run `target()` with a hard wall-clock timeout.

    Args:
        target: zero-argument callable returning the project's result dict.
                Typical usage: ``lambda: service.analyze_project(project_id=…, …)``.
        project_id: used only for logging and the synthetic timeout result.
        timeout_sec: override the env-configured timeout. Pass 0 to disable.

    Returns:
        The dict produced by ``target()``, or a synthetic failure dict if the
        timeout fires or the callable raises.
    """
    if timeout_sec is None:
        timeout_sec = get_project_timeout_seconds()

    # Disabled timeout: just call directly, bubble up the result/exception
    # exactly as before. This preserves the previous behavior when ops want
    # to opt out without redeploying.
    if timeout_sec <= 0:
        try:
            return target()
        except Exception as e:
            logger.error(f"Project #{project_id} raised: {e}")
            return {'project_id': project_id, 'success': False, 'error': str(e)}

    result_holder: list = []
    error_holder: list = []

    def _runner():
        try:
            r = target()
            result_holder.append(r)
        except Exception as e:
            error_holder.append(e)

    t = threading.Thread(
        target=_runner,
        daemon=True,
        name=f"llm-project-{project_id}",
    )
    t.start()
    t.join(timeout=timeout_sec)

    if t.is_alive():
        elapsed_min = timeout_sec / 60.0
        logger.warning(
            f"⏱️ Project #{project_id} exceeded {elapsed_min:.0f} min timeout. "
            f"Marking as failed and continuing. The runaway thread will exit on "
            f"its own as per-call timeouts (60-90s) take effect."
        )
        return {
            'project_id': project_id,
            'success': False,
            'timed_out': True,
            'error': f'project_timeout: exceeded {elapsed_min:.0f} minutes',
        }

    if error_holder:
        e = error_holder[0]
        logger.error(f"❌ Project #{project_id} raised: {e}")
        return {
            'project_id': project_id,
            'success': False,
            'error': str(e),
        }

    if result_holder:
        return result_holder[0]

    # Should be unreachable: thread completed without exception or result
    logger.error(f"❌ Project #{project_id}: thread completed but produced no result")
    return {
        'project_id': project_id,
        'success': False,
        'error': 'no_result',
    }
