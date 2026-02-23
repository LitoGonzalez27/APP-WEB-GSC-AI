"""
Proveedor Anthropic - Claude Sonnet 4.6
Última actualización: 23 Febrero 2026

IMPORTANTE:
- NO hardcodees precios aquí (se leen de BD)
- Mejor balance calidad/precio del mercado
"""

import logging
import time
from typing import Dict
import anthropic
from .base_provider import (
    BaseLLMProvider, 
    get_model_pricing_from_db, 
    get_current_model_for_provider,
    extract_urls_from_text
)
from .retry_handler import with_retry  # ✨ NUEVO: Sistema de retry

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Proveedor para Claude Sonnet 4.6 (Anthropic)
    
    Características:
    - Excelente para análisis de texto
    - Mejor en codificación que GPT-5
    - Razonamiento a largo plazo (30+ horas)
    - Hasta 64K tokens de salida
    - Excelente balance precio/calidad
    """
    
    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor Anthropic
        
        Args:
            api_key: API key de Anthropic (obtener en console.anthropic.com)
            model: Modelo específico a usar (opcional)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # ✅ CORRECCIÓN: Obtener modelo actual de BD
        if model:
            self.model = model
        else:
            self.model = get_current_model_for_provider('anthropic')
            if not self.model:
                # Model ID correcto según docs: claude-sonnet-4-6
                self.model = 'claude-sonnet-4-6'
                logger.warning("⚠️ No se encontró modelo actual en BD, usando Claude Sonnet 4.6 por defecto")
        
        # ✅ CORRECCIÓN: Obtener pricing de BD
        self.pricing = get_model_pricing_from_db('anthropic', self.model)
        
        logger.info(f"🤖 Anthropic Provider inicializado")
        logger.info(f"   Modelo: {self.model}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    @with_retry  # ✨ NUEVO: Retry automático con exponential backoff
    def execute_query(self, query: str) -> Dict:
        """
        Ejecuta una query contra Claude Sonnet 4.6
        """
        start_time = time.time()
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,  # Reducido de 64K para evitar error de streaming requerido
                messages=[
                    {"role": "user", "content": query}
                ]
            )
            
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
                'model_used': self.model
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
    
    def get_model_display_name(self) -> str:
        display_names = {
            'claude-sonnet-4-6': 'Claude Sonnet 4.6',
            'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
            'claude-sonnet-4-5': 'Claude Sonnet 4.5',
            'claude-3-5-sonnet-20241022': 'Claude Sonnet 3.5',
            'claude-3-5-sonnet-latest': 'Claude Sonnet 3.5 Latest'
        }
        return display_names.get(self.model, self.model)
    
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
            logger.error(f"❌ Anthropic connection test failed: {e}")
            return False
