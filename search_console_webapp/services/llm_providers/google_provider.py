"""
Proveedor Google (Gemini)

- Modelo: el `is_current` de llm_model_registry (fallback en base_provider.DEFAULT_MODELS).
- Precios: siempre desde BD, nunca hardcodeados. Gemini 3.x factura el
  razonamiento como salida (ver cálculo de output_tokens).
"""

import os
import logging
import time
from typing import Dict, Optional
import google.generativeai as genai
from .base_provider import (
    BaseLLMProvider,
    get_model_pricing_from_db,
    resolve_model_id,
    extract_urls_from_text
)
from .locale_helpers import LocaleContext, build_system_instruction
from .retry_handler import with_retry, note_health_check_failure

logger = logging.getLogger(__name__)


class GoogleProvider(BaseLLMProvider):
    """Proveedor para Gemini (Google)."""

    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor Google

        Args:
            api_key: API key de Google (obtener en aistudio.google.com)
            model: Modelo específico a usar (opcional)
        """
        genai.configure(api_key=api_key)

        self.model_name = resolve_model_id('google', model)
        
        generation_config = {
            'max_output_tokens': 65536,
            'temperature': 0.7,
        }
        
        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config=generation_config
        )
        
        self.pricing = get_model_pricing_from_db('google', self.model_name)
        
        logger.info(f"🤖 Google Provider inicializado")
        logger.info(f"   Modelo: {self.model_name}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    @with_retry
    def execute_query(self, query: str, *,
                      locale: Optional[LocaleContext] = None) -> Dict:
        """
        Ejecuta una query contra Gemini.

        Args:
            query: Pregunta a enviar a Gemini.
            locale: LocaleContext opcional. Cuando se pasa, se prepende
                    un bloque [SYSTEM INSTRUCTION] al contenido antes de
                    enviarlo. Esto es necesario porque el SDK
                    google.generativeai acepta system_instruction solo a
                    nivel de modelo (en __init__), no per-call. Prepender
                    con estructura clara es empíricamente efectivo para
                    corregir sesgos de región (ej: sesgo brasileño con
                    portugués).

        Returns:
            Dict con respuesta estandarizada (incluye 'prompt_strategy').
        """
        start_time = time.time()

        # ─── Construir final_prompt con bloque SYSTEM si hay locale ───
        if locale is not None:
            system_text = build_system_instruction(locale)
            final_prompt = (
                f"[SYSTEM INSTRUCTION]\n{system_text}\n\n"
                f"[USER QUERY]\n{query}"
            )
            prompt_strategy = 'prepended_system'
            logger.info(
                f"🌍 Google: locale applied [{locale.fingerprint()}] "
                f"strategy={prompt_strategy}"
            )
        else:
            final_prompt = query
            prompt_strategy = 'legacy_user_only'

        try:
            response = self.model.generate_content(
                final_prompt,
                request_options={"timeout": 60}  # Hard cap 60s, evita gRPC defaults de 300s+
            )
            response_time = int((time.time() - start_time) * 1000)

            content = response.text

            input_tokens = 0
            output_tokens = 0
            total_tokens = 0

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                total_tokens = getattr(response.usage_metadata, 'total_token_count', 0)
                # Gemini 3.x factura el razonamiento (thoughtsTokenCount) como
                # salida, pero candidates_token_count no lo incluye y el SDK
                # legacy no expone el campo: se deriva de total - prompt.
                output_tokens = max(
                    getattr(response.usage_metadata, 'candidates_token_count', 0),
                    total_tokens - input_tokens,
                )
            else:
                # Estimación sobre final_prompt (no query) para reflejar coste real
                input_tokens = int(len(final_prompt.split()) * 1.3)
                output_tokens = int(len(content.split()) * 1.3)
                total_tokens = input_tokens + output_tokens
                logger.debug(f"ℹ️ Gemini no expuso usage_metadata, usando estimación")

            sources = extract_urls_from_text(content)

            cost = (input_tokens * self.pricing['input'] +
                   output_tokens * self.pricing['output'])

            return {
                'success': True,
                'content': content,
                'sources': sources,
                'tokens': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': round(cost, 8),
                'response_time_ms': response_time,
                'model_used': self.model_name,
                'prompt_strategy': prompt_strategy,  # ✨ NUEVO
            }
            
        except Exception as e:
            logger.error(f"❌ Google (Gemini) Error: {e}", exc_info=True)
            
            error_msg = str(e)
            if 'API key' in error_msg or 'api_key' in error_msg:
                error_msg = "Invalid API key or API not enabled"
            elif 'quota' in error_msg.lower():
                error_msg = "Quota exceeded. Check your Google Cloud quotas."
            elif 'safety' in error_msg.lower():
                error_msg = "Content blocked by safety filters"
            
            return {
                'success': False,
                'error': f"Google API Error: {error_msg}"
            }
    
    def get_provider_name(self) -> str:
        return 'google'
    
    
    def test_connection(self) -> bool:
        """
        Verifica que la API key funcione
        """
        try:
            # Gemini 3.x es un modelo "thinking": un "Hi" puede tardar más que un
            # chat clásico. 15s era demasiado agresivo y, bajo la carga concurrente
            # del cron, el health-check fallaba y excluía a Google del run entero.
            # Timeout configurable (default 30s).
            timeout_s = int(os.getenv('GOOGLE_HEALTHCHECK_TIMEOUT', '30'))
            test_response = self.model.generate_content(
                "Hi",
                request_options={"timeout": timeout_s}
            )
            if test_response and test_response.text:
                logger.info("✅ Google connection test successful")
                return True
            else:
                logger.error("❌ Google connection test failed: No response")
                return False
        except Exception as e:
            note_health_check_failure(self.get_provider_name(), e)
            logger.error(f"❌ Google connection test failed: {e}")
            return False
