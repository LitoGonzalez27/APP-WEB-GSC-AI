-- ============================================================
-- Migration: Switch is_current to free-tier-equivalent text models
-- Date: 2026-05-05
-- Strategy: SOFT (no DELETE) - flip is_current/is_available only.
--           Historical results and project configs preserved.
--
-- Goal: align analyzed models with what end-users see on free
-- tiers of ChatGPT, Gemini app, Claude.ai, Perplexity.
--
-- Active models (is_current=TRUE):
--   openai     → gpt-5.3-chat-latest      ($1.75 / $14.00)
--   anthropic  → claude-sonnet-4-6        ($3.00 / $15.00)
--   google     → gemini-3-flash-preview   ($0.50 / $3.00)
--   perplexity → sonar                    ($1.00 / $1.00)
-- ============================================================

BEGIN;

-- =====================================================================
-- 1. OPENAI: switch to gpt-5.3-chat-latest (mirrors ChatGPT Free default)
-- =====================================================================
-- Ensure target model exists with correct pricing
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    is_current, is_available
) VALUES (
    'openai', 'gpt-5.3-chat-latest', 'GPT-5.3 Instant (Free Default)',
    1.75, 14.00, FALSE, TRUE
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    model_display_name = 'GPT-5.3 Instant (Free Default)',
    cost_per_1m_input_tokens = 1.75,
    cost_per_1m_output_tokens = 14.00,
    is_available = TRUE,
    updated_at = NOW();

-- Unset is_current and is_available for ALL openai models (clear slate)
UPDATE llm_model_registry
SET is_current = FALSE, is_available = FALSE, updated_at = NOW()
WHERE llm_provider = 'openai';

-- Activate the chosen one
UPDATE llm_model_registry
SET is_current = TRUE, is_available = TRUE, updated_at = NOW()
WHERE llm_provider = 'openai' AND model_id = 'gpt-5.3-chat-latest';

-- =====================================================================
-- 2. ANTHROPIC: keep claude-sonnet-4-6 (already current, mirrors Claude.ai Free)
-- =====================================================================
UPDATE llm_model_registry
SET cost_per_1m_input_tokens = 3.00,
    cost_per_1m_output_tokens = 15.00,
    model_display_name = 'Claude Sonnet 4.6 (Free Default)',
    updated_at = NOW()
WHERE llm_provider = 'anthropic' AND model_id = 'claude-sonnet-4-6';

UPDATE llm_model_registry
SET is_current = FALSE, is_available = FALSE, updated_at = NOW()
WHERE llm_provider = 'anthropic';

UPDATE llm_model_registry
SET is_current = TRUE, is_available = TRUE, updated_at = NOW()
WHERE llm_provider = 'anthropic' AND model_id = 'claude-sonnet-4-6';

-- =====================================================================
-- 3. GOOGLE: keep gemini-3-flash-preview (already current, mirrors Gemini app Free)
-- =====================================================================
UPDATE llm_model_registry
SET cost_per_1m_input_tokens = 0.50,
    cost_per_1m_output_tokens = 3.00,
    model_display_name = 'Gemini 3 Flash (Free Default)',
    updated_at = NOW()
WHERE llm_provider = 'google' AND model_id = 'gemini-3-flash-preview';

UPDATE llm_model_registry
SET is_current = FALSE, is_available = FALSE, updated_at = NOW()
WHERE llm_provider = 'google';

UPDATE llm_model_registry
SET is_current = TRUE, is_available = TRUE, updated_at = NOW()
WHERE llm_provider = 'google' AND model_id = 'gemini-3-flash-preview';

-- =====================================================================
-- 4. PERPLEXITY: switch to plain sonar (mirrors free Best mode w/ citations)
-- =====================================================================
-- Ensure pricing for sonar is correct (some envs had it as NULL or wrong)
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    is_current, is_available
) VALUES (
    'perplexity', 'sonar', 'Perplexity Sonar (Free Default)',
    1.00, 1.00, FALSE, TRUE
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    model_display_name = 'Perplexity Sonar (Free Default)',
    cost_per_1m_input_tokens = 1.00,
    cost_per_1m_output_tokens = 1.00,
    is_available = TRUE,
    updated_at = NOW();

UPDATE llm_model_registry
SET is_current = FALSE, is_available = FALSE, updated_at = NOW()
WHERE llm_provider = 'perplexity';

UPDATE llm_model_registry
SET is_current = TRUE, is_available = TRUE, updated_at = NOW()
WHERE llm_provider = 'perplexity' AND model_id = 'sonar';

-- =====================================================================
-- Verification (must show exactly 4 rows, one per provider)
-- =====================================================================
SELECT llm_provider, model_id, model_display_name,
       cost_per_1m_input_tokens AS in_cost,
       cost_per_1m_output_tokens AS out_cost,
       is_current, is_available
FROM llm_model_registry
WHERE is_current = TRUE
ORDER BY llm_provider;

COMMIT;
