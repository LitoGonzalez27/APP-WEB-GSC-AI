"""
Interfaz Base para Proveedores LLM + Helpers de Base de Datos

IMPORTANTE: 
- Todos los proveedores deben heredar de BaseLLMProvider
- Los precios SOLO se leen de la base de datos (no hardcodeados)
- El modelo actual se obtiene de la BD (is_current=TRUE)
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================
# FUNCIONES HELPER PARA BASE DE DATOS
# ============================================

def get_model_pricing_from_db(llm_provider: str, model_id: str) -> Dict:
    """
    Obtiene el pricing de un modelo desde la base de datos
    
    IMPORTANTE: Esta es la ÚNICA fuente de verdad para precios.
    No hardcodees precios en los proveedores.
    
    Args:
        llm_provider: Nombre del proveedor ('openai', 'anthropic', 'google', 'perplexity')
        model_id: ID del modelo ('gpt-5', 'claude-sonnet-4-5-20250929', etc.)
        
    Returns:
        Dict con pricing por token:
        {
            'input': float,   # Coste por 1 token de entrada
            'output': float   # Coste por 1 token de salida
        }
        
    Example:
        >>> pricing = get_model_pricing_from_db('openai', 'gpt-5')
        >>> print(pricing)
        {'input': 0.000015, 'output': 0.000045}
    """
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        logger.warning("⚠️ No hay conexión a BD, usando pricing por defecto (0.0)")
        return {'input': 0.0, 'output': 0.0}
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens
            FROM llm_model_registry
            WHERE llm_provider = %s AND model_id = %s
        """, (llm_provider, model_id))
        
        result = cur.fetchone()
        
        if result:
            # Convertir de "por 1M tokens" a "por 1 token"
            input_cost = float(result['cost_per_1m_input_tokens']) / 1_000_000
            output_cost = float(result['cost_per_1m_output_tokens']) / 1_000_000
            
            logger.debug(f"✅ Pricing obtenido de BD para {llm_provider}/{model_id}")
            logger.debug(f"   Input: ${input_cost * 1_000_000:.2f}/1M | Output: ${output_cost * 1_000_000:.2f}/1M")
            
            return {
                'input': input_cost,
                'output': output_cost
            }
        else:
            logger.warning(f"⚠️ No se encontró pricing para {llm_provider}/{model_id} en BD")
            return {'input': 0.0, 'output': 0.0}
            
    except Exception as e:
        logger.error(f"❌ Error obteniendo pricing de BD: {e}")
        return {'input': 0.0, 'output': 0.0}
    finally:
        cur.close()
        conn.close()


def get_current_model_for_provider(llm_provider: str) -> Optional[str]:
    """
    Obtiene el modelo actual (is_current=TRUE) para un proveedor desde BD
    
    IMPORTANTE: El modelo "actual" se define en BD, no en código.
    Esto permite cambiar el modelo sin redesplegar código.
    
    Args:
        llm_provider: Nombre del proveedor
        
    Returns:
        model_id del modelo actual o None si no se encuentra
        
    Example:
        >>> model = get_current_model_for_provider('openai')
        >>> print(model)
        'gpt-5'
    """
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        logger.warning(f"⚠️ No hay conexión a BD para obtener modelo actual de {llm_provider}")
        return None
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT model_id, model_display_name
            FROM llm_model_registry
            WHERE llm_provider = %s AND is_current = TRUE
            LIMIT 1
        """, (llm_provider,))
        
        result = cur.fetchone()
        
        if result:
            logger.debug(f"✅ Modelo actual para {llm_provider}: {result['model_id']} ({result['model_display_name']})")
            return result['model_id']
        else:
            logger.warning(f"⚠️ No hay modelo marcado como 'current' para {llm_provider}")
            return None
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo modelo actual: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ============================================
# INTERFAZ BASE PARA PROVEEDORES
# ============================================

class BaseLLMProvider(ABC):
    """
    Clase base abstracta para todos los proveedores LLM
    
    Todos los proveedores (OpenAI, Anthropic, Google, Perplexity)
    DEBEN implementar estos métodos para mantener consistencia.
    
    Esto permite:
    - Tratar todos los LLMs de forma uniforme
    - Cambiar fácilmente entre proveedores
    - Añadir nuevos proveedores sin cambiar el resto del código
    """
    
    @abstractmethod
    def execute_query(self, query: str) -> Dict:
        """
        Ejecuta una query contra el LLM y retorna respuesta estandarizada
        
        Args:
            query: La pregunta/prompt a enviar al LLM
            
        Returns:
            Dict con estructura ESTANDARIZADA:
            {
                'success': bool,              # True si la query fue exitosa
                'content': str,               # Respuesta del LLM (solo si success=True)
                'tokens': int,                # Total tokens usados
                'input_tokens': int,          # Tokens de entrada (prompt)
                'output_tokens': int,         # Tokens de salida (respuesta)
                'cost_usd': float,            # Coste en USD
                'response_time_ms': int,      # Tiempo de respuesta en milisegundos
                'model_used': str,            # Modelo específico usado
                'error': str                  # Mensaje de error (solo si success=False)
            }
            
        Example:
            >>> provider = OpenAIProvider(api_key='sk-...')
            >>> result = provider.execute_query("¿Qué es Python?")
            >>> if result['success']:
            ...     print(result['content'])
            ...     print(f"Coste: ${result['cost_usd']:.6f}")
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Retorna el nombre del proveedor
        
        Returns:
            str: Debe ser uno de: 'openai', 'anthropic', 'google', 'perplexity'
            
        Example:
            >>> provider.get_provider_name()
            'openai'
        """
        pass
    
    @abstractmethod
    def get_model_display_name(self) -> str:
        """
        Retorna el nombre del modelo para mostrar en UI
        
        Returns:
            str: Nombre legible para humanos
            
        Example:
            >>> provider.get_model_display_name()
            'GPT-5'
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Verifica que la API key funcione correctamente
        
        Hace una llamada de prueba mínima a la API para verificar
        que la autenticación es correcta.
        
        Returns:
            bool: True si la conexión es exitosa, False si falla
            
        Example:
            >>> provider = OpenAIProvider(api_key='sk-...')
            >>> if provider.test_connection():
            ...     print("✅ API key válida")
            ... else:
            ...     print("❌ API key inválida")
        """
        pass
    
    def get_pricing_info(self) -> Dict:
        """
        Retorna información de pricing del modelo actual
        
        Returns:
            Dict con info de pricing por 1M tokens:
            {
                'input_per_1m': float,   # USD por 1M tokens de entrada
                'output_per_1m': float   # USD por 1M tokens de salida
            }
            
        Example:
            >>> pricing = provider.get_pricing_info()
            >>> print(f"Entrada: ${pricing['input_per_1m']}/1M tokens")
            >>> print(f"Salida: ${pricing['output_per_1m']}/1M tokens")
        """
        if hasattr(self, 'pricing'):
            return {
                'input_per_1m': self.pricing['input'] * 1_000_000,
                'output_per_1m': self.pricing['output'] * 1_000_000
            }
        return {
            'input_per_1m': 0.0,
            'output_per_1m': 0.0
        }

