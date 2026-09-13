"""
Proveedor Anthropic (Claude)

- Modelo: el `is_current` de llm_model_registry (fallback en base_provider.DEFAULT_MODELS).
- Precios: siempre desde BD, nunca hardcodeados.
"""

import logging
import time
from typing import Dict, Optional
import anthropic
from .base_provider import (
    BaseLLMProvider,
    get_model_pricing_from_db,
    resolve_model_id,
    extract_urls_from_text
)
from .locale_helpers import LocaleContext, build_system_instruction
from .retry_handler import with_retry, RetryConfig, note_health_check_failure

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Proveedor para Claude (Anthropic)."""
    
    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor Anthropic
        
        Args:
            api_key: API key de Anthropic (obtener en console.anthropic.com)
            model: Modelo específico a usar (opcional)
        """
        # timeout explícito: el default del SDK son 600s y una llamada colgada
        # retiene un slot de concurrencia todo ese tiempo
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=float(RetryConfig.PROVIDER_TIMEOUTS['anthropic'])
        )
        
        self.model = resolve_model_id('anthropic', model)
        
        # ✅ CORRECCIÓN: Obtener pricing de BD
        self.pricing = get_model_pricing_from_db('anthropic', self.model)
        
        logger.info(f"🤖 Anthropic Provider inicializado")
        logger.info(f"   Modelo: {self.model}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    @with_retry  # ✨ NUEVO: Retry automático con exponential backoff
    def execute_query(self, query: str, *,
                      locale: Optional[LocaleContext] = None) -> Dict:
        """
        Ejecuta una query contra Claude.

        Args:
            query: Pregunta a enviar a Claude.
            locale: LocaleContext opcional. Cuando se pasa, se usa el
                    parámetro top-level `system=` del método
                    client.messages.create() con la instrucción en lengua
                    destino. Claude da alto peso al parámetro system y
                    produce respuestas más fieles al locale objetivo.

        Returns:
            Dict con respuesta estandarizada (incluye 'prompt_strategy').
        """
        start_time = time.time()

        # ─── Construir parámetros de la llamada ───────────────────────
        create_params = {
            "model": self.model,
            "max_tokens": 8000,  # Reducido de 64K para evitar error de streaming requerido
            "messages": [{"role": "user", "content": query}],
        }
        if locale is not None:
            create_params["system"] = build_system_instruction(locale)
            prompt_strategy = 'system_user'
            logger.info(
                f"🌍 Anthropic: locale applied [{locale.fingerprint()}] "
                f"strategy={prompt_strategy}"
            )
        else:
            prompt_strategy = 'legacy_user_only'

        try:
            response = self.client.messages.create(**create_params)

            response_time = int((time.time() - start_time) * 1000)

            # Claude retorna array de content blocks
            content = response.content[0].text

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            # ✨ NUEVO: Extraer URLs del texto
            sources = extract_urls_from_text(content)

            # Calcular coste usando pricing de BD
            cost = (input_tokens * self.pricing['input'] +
                   output_tokens * self.pricing['output'])

            return {
                'success': True,
                'content': content,
                'sources': sources,  # ✨ NUEVO
                'tokens': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': round(cost, 6),
                'response_time_ms': response_time,
                'model_used': self.model,
                'prompt_strategy': prompt_strategy,  # ✨ NUEVO
            }
            
        except anthropic.APIError as e:
            logger.error(f"❌ Anthropic API Error: {e}")
            return {
                'success': False,
                'error': f"Anthropic API Error: {str(e)}"
            }
        except anthropic.RateLimitError as e:
            logger.error(f"❌ Anthropic Rate Limit: {e}")
            return {
                'success': False,
                'error': "Rate limit exceeded. Please try again later."
            }
        except Exception as e:
            logger.error(f"❌ Anthropic Unexpected Error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_provider_name(self) -> str:
        return 'anthropic'
    
    
    def test_connection(self) -> bool:
        """
        Verifica que la API key funcione
        """
        try:
            # Test simple con respuesta mínima
            self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            logger.info("✅ Anthropic connection test successful")
            return True
        except Exception as e:
            note_health_check_failure(self.get_provider_name(), e)
            logger.error(f"❌ Anthropic connection test failed: {e}")
            return False
