-- ============================================================================
-- ACTUALIZACIÓN DE MODELOS LLM - Diciembre 2025
-- ============================================================================
-- Este script actualiza los modelos a las versiones más recientes:
-- - OpenAI: gpt-5-2025-08-07 (GPT-5)
-- - Google: gemini-3 (Gemini 3)
-- - Anthropic: claude-sonnet-4-5 (Claude Sonnet 4.5)
-- - Perplexity: sonar (Perplexity Sonar)
-- ============================================================================

-- Primero, marcar todos los modelos como NO actuales
UPDATE llm_model_registry SET is_current = FALSE WHERE is_current = TRUE;

-- ============================================================================
-- OPENAI - GPT-5
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name, 
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    max_tokens, is_current, is_available
) VALUES (
    'openai', 'gpt-5-2025-08-07', 'GPT-5',
    5.00, 15.00,  -- $5/$15 per 1M tokens
    1000000,
    TRUE, TRUE
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    updated_at = NOW();

-- ============================================================================
-- GOOGLE - Gemini 3
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    max_tokens, is_current, is_available
) VALUES (
    'google', 'gemini-3', 'Gemini 3',
    1.00, 4.00,  -- $1/$4 per 1M tokens (estimado)
    1000000,
    TRUE, TRUE
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    updated_at = NOW();

-- ============================================================================
-- ANTHROPIC - Claude Sonnet 4.5
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    max_tokens, is_current, is_available
) VALUES (
    'anthropic', 'claude-sonnet-4-5', 'Claude Sonnet 4.5',
    3.00, 15.00,  -- $3/$15 per 1M tokens
    200000,
    TRUE, TRUE
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    updated_at = NOW();

-- ============================================================================
-- PERPLEXITY - Sonar
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    max_tokens, is_current, is_available
) VALUES (
    'perplexity', 'sonar', 'Perplexity Sonar',
    1.00, 1.00,  -- $1/$1 per 1M tokens
    128000,
    TRUE, TRUE
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    updated_at = NOW();

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================
SELECT 
    llm_provider,
    model_id,
    model_display_name,
    CONCAT('$', cost_per_1m_input_tokens, ' / $', cost_per_1m_output_tokens) as "Pricing (per 1M)",
    is_current,
    is_available
FROM llm_model_registry
WHERE is_current = TRUE
ORDER BY llm_provider;
