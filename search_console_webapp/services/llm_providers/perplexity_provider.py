"""
Proveedor Perplexity - Sonar
Versión: sonar (modelo actualizado Oct 2025)

IMPORTANTE:
- NO hardcodees precios aquí (se leen de BD)
- Usa búsqueda en tiempo real (acceso a internet)
- Compatible con SDK de OpenAI (diferente base_url)
- Modelos disponibles: sonar, sonar-pro, sonar-reasoning
"""

import logging
import time
from typing import Dict
import openai
from .base_provider import BaseLLMProvider, get_model_pricing_from_db, get_current_model_for_provider

logger = logging.getLogger(__name__)


class PerplexityProvider(BaseLLMProvider):
    """
    Proveedor para Perplexity Sonar Large
    
    Características:
    - Búsqueda en tiempo real (acceso a internet en cada query)
    - Basado en Llama 3.1
    - 128K tokens de contexto
    - Excelente para información actualizada
    - Cita fuentes automáticamente
    - Precio muy competitivo ($1/$1 por 1M tokens)
    """
    
    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor Perplexity
        
        Args:
            api_key: API key de Perplexity (obtener en perplexity.ai/settings)
            model: Modelo específico a usar (opcional)
                   
        Example:
            >>> provider = PerplexityProvider(api_key='pplx-...')
            >>> result = provider.execute_query("¿Qué pasó hoy en el mundo?")
            >>> # Respuesta incluirá información actualizada de hoy
        """
        # ✅ DIFERENCIA CLAVE: Base URL de Perplexity
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
        
        # ✅ CORRECCIÓN: Obtener modelo actual de BD
        if model:
            self.model = model
        else:
            self.model = get_current_model_for_provider('perplexity')
            if not self.model:
                # ✅ CORRECCIÓN: Usar 'sonar' como fallback (modelo correcto)
                self.model = 'sonar'
                logger.warning("⚠️ No se encontró modelo actual en BD, usando 'sonar' por defecto")
        
        # ✅ CORRECCIÓN: Obtener pricing de BD
        self.pricing = get_model_pricing_from_db('perplexity', self.model)
        
        logger.info(f"🤖 Perplexity Provider inicializado")
        logger.info(f"   Modelo: {self.model}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
        logger.info(f"   ⚡ Búsqueda en tiempo real habilitada")
    
    def execute_query(self, query: str) -> Dict:
        """
        Ejecuta una query contra Perplexity Sonar
        
        IMPORTANTE: Esta query incluirá búsqueda en internet en tiempo real.
        La respuesta puede incluir información muy reciente.
        
        Args:
            query: Pregunta a hacer a Perplexity
            
        Returns:
            Dict con respuesta estandarizada
        """
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Calcular tiempo de respuesta
            response_time = int((time.time() - start_time) * 1000)
            
            # Extraer datos (mismo formato que OpenAI)
            content = response.choices[0].message.content
            
            # Tokens usados
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            
            if hasattr(response, 'usage') and response.usage:
                input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                output_tokens = getattr(response.usage, 'completion_tokens', 0)
                total_tokens = getattr(response.usage, 'total_tokens', 0)
            else:
                # Estimación si no hay usage
                input_tokens = int(len(query.split()) * 1.3)
                output_tokens = int(len(content.split()) * 1.3)
                total_tokens = input_tokens + output_tokens
                logger.debug(f"ℹ️ Perplexity no expuso usage, usando estimación")
            
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
            logger.error(f"❌ Perplexity API Error: {e}")
            return {
                'success': False,
                'error': f"Perplexity API Error: {str(e)}"
            }
        except openai.RateLimitError as e:
            logger.error(f"❌ Perplexity Rate Limit: {e}")
            return {
                'success': False,
                'error': "Rate limit exceeded. Please try again later."
            }
        except Exception as e:
            logger.error(f"❌ Perplexity Unexpected Error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_provider_name(self) -> str:
        return 'perplexity'
    
    def get_model_display_name(self) -> str:
        # Mapeo de IDs a nombres legibles (modelos actualizados Oct 2025)
        display_names = {
            'sonar': 'Perplexity Sonar',
            'sonar-pro': 'Perplexity Sonar Pro',
            'sonar-reasoning': 'Perplexity Sonar Reasoning',
            # Legacy (deprecated)
            'llama-3.1-sonar-large-128k-online': 'Perplexity Sonar Large (Legacy)',
            'llama-3.1-sonar-small-128k-online': 'Perplexity Sonar Small (Legacy)'
        }
        return display_names.get(self.model, self.model)
    
    def test_connection(self) -> bool:
        """
        Verifica que la API key funcione
        """
        try:
            # Test simple con query mínima
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
            
            if response and response.choices:
                logger.info("✅ Perplexity connection test successful")
                return True
            else:
                logger.error("❌ Perplexity connection test failed: No response")
                return False
                
        except Exception as e:
            logger.error(f"❌ Perplexity connection test failed: {e}")
            return False

