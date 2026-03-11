"""
Proveedor OpenAI - GPT-5.3 Chat Latest
Última actualización: 11 Marzo 2026

IMPORTANTE:
- Modelo: gpt-5.3-chat-latest (último snapshot de ChatGPT)
- NO hardcodees precios aquí (se leen de BD)
- El modelo actual se obtiene de BD (is_current=TRUE)

MODEL IDs disponibles:
- gpt-5.3-chat-latest (último snapshot de ChatGPT, 128K context, 16K output)
- gpt-5.2 (flagship estable anterior)
- gpt-5-mini (versión económica y rápida)

Docs: https://platform.openai.com/docs/models/gpt-5
"""

import logging
import time
from typing import Dict
import os
import openai
from .base_provider import (
    BaseLLMProvider, 
    get_model_pricing_from_db, 
    get_current_model_for_provider,
    extract_urls_from_text
)
from .retry_handler import with_retry  # Sistema de retry

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    Proveedor para ChatGPT (OpenAI GPT-5.3 Chat Latest)

    Características:
    - Último snapshot de ChatGPT (GPT-5.3)
    - Ventana de contexto de 128K tokens
    - Max output: 16,384 tokens
    - Knowledge cutoff: Aug 31, 2025
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
            
            >>> provider = OpenAIProvider(api_key='sk-proj-...', model='gpt-5.3-chat-latest')
            >>> # Usará específicamente gpt-5.3-chat-latest
        """
        self.client = openai.OpenAI(api_key=api_key)
        
        # ✅ CORRECCIÓN: Priorizar variable de entorno, luego parámetro, luego BD
        preferred = os.getenv('OPENAI_PREFERRED_MODEL')
        if preferred:
            self.model = preferred
            logger.info(f"ℹ️ OPENAI_PREFERRED_MODEL detectado: {self.model}")
        elif model:
            self.model = model
        else:
            # Obtener modelo marcado como 'current' en BD
            self.model = get_current_model_for_provider('openai')
            if not self.model:
                # Fallback a GPT-5.3 Chat Latest
                self.model = 'gpt-5.3-chat-latest'
                logger.warning("⚠️ No se encontró modelo actual en BD, usando 'gpt-5.3-chat-latest' por defecto")
        
        # ✅ CORRECCIÓN: Obtener pricing de BD (SINGLE SOURCE OF TRUTH)
        self.pricing = get_model_pricing_from_db('openai', self.model)
        
        logger.info(f"🤖 OpenAI Provider inicializado")
        logger.info(f"   Modelo: {self.model}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    @with_retry  # ✨ NUEVO: Retry automático con exponential backoff
    def execute_query(self, query: str) -> Dict:
        """
        Ejecuta una query contra GPT-5.3 Chat Latest
        
        Args:
            query: Pregunta a hacer a ChatGPT
            
        Returns:
            Dict con respuesta estandarizada
        """
        start_time = time.time()
        
        try:
            # Usar Chat Completions API directamente (más compatible)
            # La Responses API requiere permisos especiales que no todos los proyectos tienen
            content = None
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0

            # Chat Completions con el modelo configurado
            # GPT-5.x usa max_completion_tokens, GPT-4o usa max_tokens
            is_gpt5 = self.model.startswith('gpt-5')
            completion_params = {
                "model": self.model,
                "messages": [{"role": "user", "content": query}],
                "timeout": 120
            }
            
            # Añadir el parámetro correcto según el modelo
            if is_gpt5:
                completion_params["max_completion_tokens"] = 16000
            else:
                completion_params["max_tokens"] = 16000

            actual_model_used = self.model  # Track qué modelo se usó realmente
            actual_pricing = self.pricing  # Track pricing correcto

            try:
                response = self.client.chat.completions.create(**completion_params)
                content = getattr(response.choices[0].message, 'content', None) or getattr(response.choices[0], 'text', '')
                input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                output_tokens = getattr(response.usage, 'completion_tokens', 0)
                total_tokens = getattr(response.usage, 'total_tokens', (input_tokens + output_tokens))
            except Exception as e_chat:
                # Si el modelo no está disponible o hay error de parámetros, hacer fallback a gpt-4o
                err_msg = str(e_chat).lower()
                if 'model' in err_msg or 'not found' in err_msg or 'does not exist' in err_msg or 'not have access' in err_msg or 'unsupported' in err_msg:
                    fallback_model = os.getenv('OPENAI_FALLBACK_MODEL', 'gpt-4o')
                    logger.warning(f"⚠️ Error con '{self.model}': {e_chat}. Usando fallback: {fallback_model}")
                    # gpt-4o usa max_tokens
                    fallback_params = {
                        "model": fallback_model,
                        "messages": [{"role": "user", "content": query}],
                        "max_tokens": 16000,
                        "timeout": 120
                    }
                    response = self.client.chat.completions.create(**fallback_params)
                    content = getattr(response.choices[0].message, 'content', None) or getattr(response.choices[0], 'text', '')
                    input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                    output_tokens = getattr(response.usage, 'completion_tokens', 0)
                    total_tokens = getattr(response.usage, 'total_tokens', (input_tokens + output_tokens))
                    actual_model_used = fallback_model
                    actual_pricing = get_model_pricing_from_db('openai', fallback_model)
                else:
                    raise e_chat
            
            # Calcular tiempo de respuesta
            response_time = int((time.time() - start_time) * 1000)

            # Si a estas alturas no hay contenido, tratar como error real
            if not content or len(content.strip()) == 0:
                logger.error("❌ OpenAI devolvió contenido vacío tras intentos (Responses/Chat).")
                return {
                    'success': False,
                    'error': 'Empty content from OpenAI response'
                }

            # ✨ NUEVO: Extraer URLs del texto
            sources = extract_urls_from_text(content)

            # Calcular coste usando pricing del modelo que realmente se usó
            cost = (input_tokens * actual_pricing['input'] +
                   output_tokens * actual_pricing['output'])

            return {
                'success': True,
                'content': content,
                'sources': sources,
                'tokens': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': round(cost, 6),
                'response_time_ms': response_time,
                'model_used': actual_model_used
            }
            
        except (getattr(openai, 'APIStatusError', Exception), getattr(openai, 'BadRequestError', Exception), getattr(openai, 'NotFoundError', Exception), openai.APIError) as e:
            # Fallback automático si el modelo no existe/no está permitido
            err_msg = str(e)
            if ('model' in err_msg.lower() and 'does not exist' in err_msg.lower()) or ('not found' in err_msg.lower() and 'model' in err_msg.lower()):
                logger.warning(f"⚠️ Modelo '{self.model}' no disponible. Reintentando con 'gpt-4o' como fallback...")
                try:
                    fallback_model = 'gpt-4o'
                    # gpt-4o usa max_tokens (no max_completion_tokens)
                    response = self.client.chat.completions.create(
                        model=fallback_model,
                        messages=[
                            {"role": "user", "content": query}
                        ],
                        max_tokens=16000  # GPT-4o máximo es 16K de salida
                    )
                    response_time = int((time.time() - start_time) * 1000)
                    content = getattr(response.choices[0].message, 'content', None) or getattr(response.choices[0], 'text', '')
                    if not content:
                        logger.warning("⚠️ OpenAI (fallback gpt-4o) devolvió contenido vacío")
                    input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                    output_tokens = getattr(response.usage, 'completion_tokens', 0)
                    total_tokens = getattr(response.usage, 'total_tokens', (input_tokens + output_tokens))
                    sources = extract_urls_from_text(content)
                    cost = (input_tokens * self.pricing['input'] + output_tokens * self.pricing['output'])
                    return {
                        'success': True,
                        'content': content,
                        'sources': sources,
                        'tokens': total_tokens,
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                        'cost_usd': round(cost, 6),
                        'response_time_ms': response_time,
                        'model_used': fallback_model
                    }
                except Exception as e2:
                    logger.error(f"❌ OpenAI fallback gpt-4o también falló: {e2}")
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
            'gpt-5.3-chat-latest': 'GPT-5.3 Chat Latest',
            'gpt-5.2': 'GPT-5.2',
            'gpt-5.2-chat-latest': 'GPT-5.2 Chat Latest',
            'gpt-5.2-pro': 'GPT-5.2 Pro',
            'gpt-5.2-codex': 'GPT-5.2 Codex',
            'gpt-5-mini': 'GPT-5 Mini',
            'gpt-5-2025-08-07': 'GPT-5',
            'gpt-5': 'GPT-5',
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
