"""
Proveedor OpenAI - GPT-5
Última actualización: Octubre 2025

IMPORTANTE:
- NO hardcodees precios aquí (se leen de BD)
- El modelo actual se obtiene de BD (is_current=TRUE)
"""

import logging
import time
from typing import Dict
import openai
from .base_provider import BaseLLMProvider, get_model_pricing_from_db, get_current_model_for_provider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    Proveedor para ChatGPT (OpenAI GPT-5)
    
    Características:
    - Modelo más potente disponible
    - Razonamiento complejo
    - Ventana de contexto de 1M tokens
    """
    
    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor OpenAI
        
        Args:
            api_key: API key de OpenAI (obtener en platform.openai.com)
            model: Modelo específico a usar (opcional)
                   Si no se especifica, se usa el modelo actual de BD
                   
        Example:
            >>> provider = OpenAIProvider(api_key='sk-proj-...')
            >>> # Usará el modelo marcado como 'current' en BD
            
            >>> provider = OpenAIProvider(api_key='sk-proj-...', model='gpt-4o')
            >>> # Usará específicamente gpt-4o
        """
        self.client = openai.OpenAI(api_key=api_key)
        
        # ✅ CORRECCIÓN: Obtener modelo actual de BD (no hardcodeado)
        if model:
            self.model = model
        else:
            # Obtener modelo marcado como 'current' en BD
            self.model = get_current_model_for_provider('openai')
            if not self.model:
                # Fallback a gpt-4o si no hay nada en BD (modelo real más reciente)
                self.model = 'gpt-4o'
                logger.warning("⚠️ No se encontró modelo actual en BD, usando 'gpt-4o' por defecto")
        
        # ✅ CORRECCIÓN: Obtener pricing de BD (SINGLE SOURCE OF TRUTH)
        self.pricing = get_model_pricing_from_db('openai', self.model)
        
        logger.info(f"🤖 OpenAI Provider inicializado")
        logger.info(f"   Modelo: {self.model}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    def execute_query(self, query: str) -> Dict:
        """
        Ejecuta una query contra GPT-5
        
        Args:
            query: Pregunta a hacer a ChatGPT
            
        Returns:
            Dict con respuesta estandarizada
        """
        start_time = time.time()
        
        try:
            # ✅ CORRECCIÓN: GPT-4o solo acepta parámetros específicos
            # - max_completion_tokens (NO max_tokens)
            # - temperature debe ser 1 (o omitirse)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": query}
                ],
                max_completion_tokens=2000
            )
            
            # Calcular tiempo de respuesta
            response_time = int((time.time() - start_time) * 1000)
            
            # Extraer datos
            content = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # Calcular coste usando pricing de BD
            cost = (input_tokens * self.pricing['input'] + 
                   output_tokens * self.pricing['output'])
            
            return {
                'success': True,
                'content': content,
                'tokens': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': round(cost, 6),
                'response_time_ms': response_time,
                'model_used': self.model
            }
            
        except openai.APIError as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return {
                'success': False,
                'error': f"OpenAI API Error: {str(e)}"
            }
        except openai.RateLimitError as e:
            logger.error(f"❌ OpenAI Rate Limit: {e}")
            return {
                'success': False,
                'error': "Rate limit exceeded. Please try again later."
            }
        except Exception as e:
            logger.error(f"❌ OpenAI Unexpected Error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_provider_name(self) -> str:
        return 'openai'
    
    def get_model_display_name(self) -> str:
        # Mapeo de IDs a nombres legibles
        display_names = {
            'gpt-4o': 'GPT-4o',
            'gpt-4o-mini': 'GPT-4o Mini',
            'gpt-4-turbo': 'GPT-4 Turbo',
            'gpt-4': 'GPT-4'
        }
        return display_names.get(self.model, self.model)
    
    def test_connection(self) -> bool:
        """
        Verifica que la API key funcione
        """
        try:
            # Intentar listar modelos (operación ligera)
            self.client.models.list()
            logger.info("✅ OpenAI connection test successful")
            return True
        except Exception as e:
            logger.error(f"❌ OpenAI connection test failed: {e}")
            return False

