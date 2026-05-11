-- ============================================================================
-- LLM Monitoring — manual lock cleanup script
-- ============================================================================
-- Use this ONLY if the function-bun-LLMs cron is returning 409
-- "Analysis already running" and you suspect a zombie lock (the backend was
-- redeployed / OOM-killed while an analysis was in progress).
--
-- Run the diagnosis block first. If you confirm there is no real analysis
-- in flight, run the cleanup block. The cleanup is non-destructive:
--   - never deletes rows
--   - only flips is_running and marks orphan runs as 'failed'
--
-- After the backend boot cleanup (cleanup_stale_analysis_lock_on_boot) is
-- deployed, this script becomes a safety net rather than a routine fix.
-- ============================================================================

-- 1) DIAGNOSIS — run first, inspect output
SELECT id, is_running, started_at, started_by,
       EXTRACT(EPOCH FROM (NOW() - started_at))/60 AS minutes_held
FROM llm_monitoring_analysis_lock
WHERE id = 1;

SELECT id, status, triggered_by, started_at, completed_at, error_message
FROM llm_monitoring_analysis_runs
ORDER BY started_at DESC
LIMIT 10;

-- 2) CLEANUP — only run if diagnosis shows a stale lock with no real worker
--    behind it. Wrap in a transaction so you can roll back if needed.
-- BEGIN;
--
-- UPDATE llm_monitoring_analysis_runs
--    SET status        = 'failed',
--        completed_at  = NOW(),
--        error_message = COALESCE(error_message, 'Manual cleanup — backend restart suspected')
--  WHERE status = 'running';
--
-- UPDATE llm_monitoring_analysis_lock
--    SET is_running = FALSE,
--        started_at = NULL,
--        started_by = NULL
--  WHERE id = 1;
--
-- -- Verify before commit:
-- SELECT * FROM llm_monitoring_analysis_lock WHERE id = 1;
-- SELECT id, status, completed_at FROM llm_monitoring_analysis_runs
--   ORDER BY started_at DESC LIMIT 5;
--
-- COMMIT;  -- or ROLLBACK if anything looks wrong
