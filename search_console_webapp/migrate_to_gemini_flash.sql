-- ============================================================
-- Migration: Switch Google model from Gemini 3.1 Pro → Gemini 3 Flash
-- Date: 2026-03-04
-- Reason: Gemini 3.1 Pro has 250 RPD limit (Tier 1), causing
--         quota exhaustion with daily cron. Flash has much higher
--         RPD and is 4x cheaper ($0.50/$3.00 vs $2/$12 per 1M).
-- ============================================================

BEGIN;

-- 1. Ensure gemini-3-flash-preview exists in the registry
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    is_current, is_available
) VALUES (
    'google', 'gemini-3-flash-preview', 'Gemini 3 Flash',
    0.50, 3.00,
    FALSE, TRUE
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    model_display_name = 'Gemini 3 Flash',
    cost_per_1m_input_tokens = 0.50,
    cost_per_1m_output_tokens = 3.00,
    is_available = TRUE,
    updated_at = NOW();

-- 2. Unset is_current from ALL Google models
UPDATE llm_model_registry
SET is_current = FALSE, updated_at = NOW()
WHERE llm_provider = 'google';

-- 3. Set gemini-3-flash-preview as the current model
UPDATE llm_model_registry
SET is_current = TRUE, updated_at = NOW()
WHERE llm_provider = 'google' AND model_id = 'gemini-3-flash-preview';

-- 4. Create new resilience tables (if not exist)

-- Singleton lock to prevent concurrent analyses
CREATE TABLE IF NOT EXISTS llm_monitoring_analysis_lock (
    id INTEGER PRIMARY KEY DEFAULT 1,
    is_running BOOLEAN DEFAULT FALSE,
    started_at TIMESTAMP,
    started_by TEXT,
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO llm_monitoring_analysis_lock (id, is_running)
VALUES (1, FALSE)
ON CONFLICT (id) DO NOTHING;

-- Analysis run history
CREATE TABLE IF NOT EXISTS llm_monitoring_analysis_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'running',
    total_projects INTEGER DEFAULT 0,
    successful_projects INTEGER DEFAULT 0,
    failed_projects INTEGER DEFAULT 0,
    total_queries INTEGER DEFAULT 0,
    error_message TEXT,
    triggered_by TEXT DEFAULT 'cron'
);

-- 5. Verify
SELECT llm_provider, model_id, model_display_name, is_current,
       cost_per_1m_input_tokens, cost_per_1m_output_tokens
FROM llm_model_registry
WHERE llm_provider = 'google'
ORDER BY is_current DESC;

COMMIT;
