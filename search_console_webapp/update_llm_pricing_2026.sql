-- ============================================================================
-- ACTUALIZACIÓN DE PRICING LLM - Febrero 2026
-- ============================================================================
-- Actualiza precios por 1M tokens (input/output) en llm_model_registry.
-- No modifica is_current para evitar cambios de modelo activos.
-- ============================================================================

-- ============================================================================
-- OPENAI
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    is_available
) VALUES
    ('openai', 'gpt-5.2', 'GPT-5.2', 1.75, 14.00, TRUE),
    ('openai', 'gpt-5.1', 'GPT-5.1', 1.25, 10.00, TRUE),
    ('openai', 'gpt-5', 'GPT-5', 1.25, 10.00, TRUE),
    ('openai', 'gpt-5-mini', 'GPT-5 Mini', 0.25, 2.00, TRUE),
    ('openai', 'gpt-5-nano', 'GPT-5 Nano', 0.05, 0.40, TRUE),
    ('openai', 'gpt-5.2-chat-latest', 'GPT-5.2 Chat Latest', 1.75, 14.00, TRUE),
    ('openai', 'gpt-5.1-chat-latest', 'GPT-5.1 Chat Latest', 1.25, 10.00, TRUE),
    ('openai', 'gpt-5-chat-latest', 'GPT-5 Chat Latest', 1.25, 10.00, TRUE),
    ('openai', 'gpt-5.2-codex', 'GPT-5.2 Codex', 1.75, 14.00, TRUE),
    ('openai', 'gpt-5.1-codex-max', 'GPT-5.1 Codex Max', 1.25, 10.00, TRUE),
    ('openai', 'gpt-5.1-codex', 'GPT-5.1 Codex', 1.25, 10.00, TRUE),
    ('openai', 'gpt-5-codex', 'GPT-5 Codex', 1.25, 10.00, TRUE),
    ('openai', 'gpt-5.2-pro', 'GPT-5.2 Pro', 21.00, 168.00, TRUE),
    ('openai', 'gpt-5-pro', 'GPT-5 Pro', 15.00, 120.00, TRUE)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    is_available = EXCLUDED.is_available,
    updated_at = NOW();

-- ============================================================================
-- ANTHROPIC (Claude)
-- Nota: se ignoran precios de cache/hits, solo input/output base.
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    is_available
) VALUES
    ('anthropic', 'claude-opus-4-6', 'Claude Opus 4.6', 5.00, 25.00, TRUE),
    ('anthropic', 'claude-opus-4-5', 'Claude Opus 4.5', 5.00, 25.00, TRUE),
    ('anthropic', 'claude-opus-4-1', 'Claude Opus 4.1', 15.00, 75.00, TRUE),
    ('anthropic', 'claude-opus-4', 'Claude Opus 4', 15.00, 75.00, TRUE),
    ('anthropic', 'claude-opus-3', 'Claude Opus 3', 15.00, 75.00, TRUE),
    ('anthropic', 'claude-sonnet-4-5', 'Claude Sonnet 4.5', 3.00, 15.00, TRUE),
    ('anthropic', 'claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5', 3.00, 15.00, TRUE),
    ('anthropic', 'claude-sonnet-4', 'Claude Sonnet 4', 3.00, 15.00, TRUE),
    ('anthropic', 'claude-sonnet-3-7', 'Claude Sonnet 3.7 (deprecated)', 3.00, 15.00, TRUE),
    ('anthropic', 'claude-haiku-4-5', 'Claude Haiku 4.5', 1.00, 5.00, TRUE),
    ('anthropic', 'claude-haiku-3-5', 'Claude Haiku 3.5', 0.80, 4.00, TRUE),
    ('anthropic', 'claude-haiku-3', 'Claude Haiku 3', 0.25, 1.25, TRUE)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    is_available = EXCLUDED.is_available,
    updated_at = NOW();

-- ============================================================================
-- GOOGLE (Gemini)
-- Nota: precios usando tier <= 200k tokens (texto/imagen/video).
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    is_available
) VALUES
    ('google', 'gemini-3-pro-preview', 'Gemini 3 Pro Preview', 2.00, 12.00, TRUE),
    ('google', 'gemini-3-flash-preview', 'Gemini 3 Flash Preview', 0.50, 3.00, TRUE)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    is_available = EXCLUDED.is_available,
    updated_at = NOW();

-- ============================================================================
-- PERPLEXITY
-- Nota: no se modelan citation/reasoning/search tokens en el esquema actual.
-- ============================================================================
INSERT INTO llm_model_registry (
    llm_provider, model_id, model_display_name,
    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
    is_available
) VALUES
    ('perplexity', 'sonar', 'Perplexity Sonar', 1.00, 1.00, TRUE),
    ('perplexity', 'sonar-pro', 'Perplexity Sonar Pro', 3.00, 15.00, TRUE),
    ('perplexity', 'sonar-reasoning', 'Perplexity Sonar Reasoning', 2.00, 8.00, TRUE),
    ('perplexity', 'sonar-deep-research', 'Perplexity Sonar Deep Research', 2.00, 8.00, TRUE)
ON CONFLICT (llm_provider, model_id) DO UPDATE SET
    model_display_name = EXCLUDED.model_display_name,
    cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
    cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
    is_available = EXCLUDED.is_available,
    updated_at = NOW();
