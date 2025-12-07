-- ============================================================================
-- ACTUALIZACIÓN DE MODELOS LLM - Diciembre 2025
-- ============================================================================
-- Este script actualiza los modelos a las versiones más recientes:
-- - OpenAI: gpt-5-2025-08-07 (GPT-5)
-- - Google: gemini-3-pro-preview (Gemini 3 Pro)
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
    input_cost_per_token, output_cost_per_token,
    context_window, max_output_tokens,
    is_current, is_available, notes
) VALUES (
    'openai', 'gpt-5-2025-08-07', 'GPT-5',
    0.000005, 0.000015,  -- $5/$15 per 1M tokens
    1000000, 64000,
    TRUE, TRUE, 'GPT-5 - Agosto 2025. Modelo más avanzado de OpenAI.'
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    input_cost_per_token = EXCLUDED.input_cost_per_token,
    output_cost_per_token = EXCLUDED.output_cost_per_token,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- ============================================================================
-- GOOGLE - Gemini 3
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    input_cost_per_token, output_cost_per_token,
    context_window, max_output_tokens,
    is_current, is_available, notes
) VALUES (
    'google', 'gemini-3', 'Gemini 3',
    0.000001, 0.000004,  -- $1/$4 per 1M tokens (estimado)
    1000000, 64000,
    TRUE, TRUE, 'Gemini 3 - Diciembre 2025. Modelo inteligente de Google con razonamiento avanzado.'
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    input_cost_per_token = EXCLUDED.input_cost_per_token,
    output_cost_per_token = EXCLUDED.output_cost_per_token,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- ============================================================================
-- ANTHROPIC - Claude Sonnet 4.5
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    input_cost_per_token, output_cost_per_token,
    context_window, max_output_tokens,
    is_current, is_available, notes
) VALUES (
    'anthropic', 'claude-sonnet-4-5', 'Claude Sonnet 4.5',
    0.000003, 0.000015,  -- $3/$15 per 1M tokens
    200000, 64000,
    TRUE, TRUE, 'Claude Sonnet 4.5 - Septiembre 2025. Mejor balance calidad/precio de Anthropic.'
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    input_cost_per_token = EXCLUDED.input_cost_per_token,
    output_cost_per_token = EXCLUDED.output_cost_per_token,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- ============================================================================
-- PERPLEXITY - Sonar
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    input_cost_per_token, output_cost_per_token,
    context_window, max_output_tokens,
    is_current, is_available, notes
) VALUES (
    'perplexity', 'sonar', 'Perplexity Sonar',
    0.000001, 0.000001,  -- $1/$1 per 1M tokens
    128000, 16000,
    TRUE, TRUE, 'Perplexity Sonar - Octubre 2025. Búsqueda en tiempo real con citación de fuentes.'
)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    is_current = TRUE,
    is_available = TRUE,
    model_display_name = EXCLUDED.model_display_name,
    input_cost_per_token = EXCLUDED.input_cost_per_token,
    output_cost_per_token = EXCLUDED.output_cost_per_token,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================
SELECT 
    llm_provider,
    model_id,
    model_display_name,
    CONCAT('$', ROUND(input_cost_per_token * 1000000, 2), ' / $', ROUND(output_cost_per_token * 1000000, 2)) as "Pricing (per 1M)",
    is_current,
    notes
FROM llm_model_registry
WHERE is_current = TRUE
ORDER BY llm_provider;

