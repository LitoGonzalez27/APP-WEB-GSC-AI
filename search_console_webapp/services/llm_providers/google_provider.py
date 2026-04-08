"""
Proveedor Google - Gemini 3 Flash Preview
Versión: gemini-3-flash-preview (Marzo 2026)

IMPORTANTE:
- Modelo Flash optimizado para alto volumen y bajo coste
- RPD mucho mayor que Pro (evita quota_exhausted en cron diario)
- 4x más barato que Pro: $0.50/$3.00 vs $2/$12 per 1M tokens

MODEL IDs disponibles:
- gemini-3-flash-preview (principal — alto RPD, bajo coste)
- gemini-3.1-pro-preview (premium — bajo RPD, más razonamiento)

Docs: https://ai.google.dev/gemini-api/docs/models
"""

import logging
import time
from typing import Dict, Optional
import google.generativeai as genai
from .base_provider import (
    BaseLLMProvider,
    get_model_pricing_from_db,
    get_current_model_for_provider,
    extract_urls_from_text
)
from .locale_helpers import LocaleContext, build_system_instruction
from .retry_handler import with_retry

logger = logging.getLogger(__name__)


class GoogleProvider(BaseLLMProvider):
    """
    Proveedor para Gemini 3 Flash (Google)

    Características:
    - Modelo Flash optimizado para alto volumen
    - RPD muy superior al Pro (ideal para cron con muchos proyectos)
    - Multimodal (texto, imágenes, audio, video)
    - 4x más barato que Gemini Pro
    """

    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor Google

        Args:
            api_key: API key de Google (obtener en aistudio.google.com)
            model: Modelo específico a usar (opcional)
        """
        genai.configure(api_key=api_key)

        if model:
            self.model_name = model
        else:
            self.model_name = get_current_model_for_provider('google')
            if not self.model_name:
                self.model_name = 'gemini-3-flash-preview'
                logger.warning("⚠️ No se encontró modelo actual en BD, usando gemini-3-flash-preview por defecto")
        
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
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
                total_tokens = getattr(response.usage_metadata, 'total_token_count', 0)
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
    
    def get_model_display_name(self) -> str:
        display_names = {
            'gemini-3-flash-preview': 'Gemini 3 Flash',
            'gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
            'gemini-3-pro-preview': 'Gemini 3 Pro',
            'gemini-3-pro-image-preview': 'Gemini 3 Pro Image',
            'gemini-3.1-flash-lite-preview': 'Gemini 3.1 Flash Lite',
            'gemini-1.5-flash': 'Gemini 1.5 Flash',
            'gemini-pro': 'Gemini Pro'
        }
        return display_names.get(self.model_name, self.model_name)
    
    def test_connection(self) -> bool:
        """
        Verifica que la API key funcione
        """
        try:
            test_response = self.model.generate_content(
                "Hi",
                request_options={"timeout": 15}  # Health check: 15s max
            )
            if test_response and test_response.text:
                logger.info("✅ Google connection test successful")
                return True
            else:
                logger.error("❌ Google connection test failed: No response")
                return False
        except Exception as e:
            logger.error(f"❌ Google connection test failed: {e}")
            return False
