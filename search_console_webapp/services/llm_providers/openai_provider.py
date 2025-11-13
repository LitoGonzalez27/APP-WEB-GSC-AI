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
import os
import openai
from .base_provider import (
    BaseLLMProvider, 
    get_model_pricing_from_db, 
    get_current_model_for_provider,
    extract_urls_from_text
)
from .retry_handler import with_retry, classify_error  # ✨ NUEVO: Sistema de retry

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
                # Fallback a gpt-4o si no hay nada en BD (modelo real más reciente)
                self.model = 'gpt-4o'
                logger.warning("⚠️ No se encontró modelo actual en BD, usando 'gpt-4o' por defecto")
        
        # ✅ CORRECCIÓN: Obtener pricing de BD (SINGLE SOURCE OF TRUTH)
        self.pricing = get_model_pricing_from_db('openai', self.model)
        
        logger.info(f"🤖 OpenAI Provider inicializado")
        logger.info(f"   Modelo: {self.model}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    @with_retry  # ✨ NUEVO: Retry automático con exponential backoff
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
            # Para modelos GPT-5 preferimos Responses API; fallback a Chat Completions
            use_responses = self.model.startswith('gpt-5') or os.getenv('OPENAI_USE_RESPONSES') == '1'
            content = None
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0

            if use_responses:
                try:
                    resp = self.client.responses.create(
                        model=self.model,
                        input=query,
                        max_output_tokens=2000,
                        timeout=60
                    )
                    # Extraer texto
                    content = getattr(resp, 'output_text', None)
                    if not content:
                        # Reconstrucción robusta desde bloques de salida
                        try:
                            parts = []
                            output_list = getattr(resp, 'output', None) or []
                            for item in output_list:
                                item_type = getattr(item, 'type', '') or ''
                                # Bloques directos de texto
                                if item_type in ('output_text', 'text'):
                                    text_val = getattr(item, 'text', '') or ''
                                    if text_val:
                                        parts.append(text_val)
                                # Mensajes con contenido anidado
                                if item_type == 'message':
                                    message_obj = getattr(item, 'message', None)
                                    if message_obj and hasattr(message_obj, 'content'):
                                        for block in (message_obj.content or []):
                                            btype = getattr(block, 'type', '') or ''
                                            if btype in ('output_text', 'text'):
                                                btext = getattr(block, 'text', '') or ''
                                                if btext:
                                                    parts.append(btext)
                            content = ''.join(parts).strip() if parts else None
                        except Exception:
                            content = None
                    # Tokens
                    if hasattr(resp, 'usage') and resp.usage:
                        input_tokens = getattr(resp.usage, 'input_tokens', 0)
                        output_tokens = getattr(resp.usage, 'output_tokens', 0)
                        total_tokens = getattr(resp.usage, 'total_tokens', input_tokens + output_tokens)
                except Exception as e_resp:
                    # Clasificar error para decidir si reintentamos con GPT-5 o hacemos fallback inmediato
                    err_type = classify_error(e_resp)
                    if err_type in ('rate_limit', 'timeout', 'server_error', 'network'):
                        # Reintentará el decorator with_retry para insistir con GPT-5
                        logger.warning(f"ℹ️ Responses API falló ({err_type}) para {self.model}. Reintentaremos con GPT-5 (sin fallback aún). Detalle: {e_resp}")
                        raise e_resp
                    # Errores no retriables (p.ej. invalid_request/model_not_found): hacemos fallback
                    logger.warning(f"ℹ️ Responses API fallo no-retriable para {self.model}: {e_resp}. Haciendo fallback a Chat Completions...")

            if not content:
                # Chat Completions clásico
                # ✅ Usar siempre max_tokens en Chat Completions para máxima compatibilidad
                # 🛡️ IMPORTANTE: Si el modelo principal es GPT-5 (Responses),
                # no intentamos Chat Completions con ese mismo modelo.
                # Hacemos fallback explícito a un modelo compatible (gpt-4o por defecto).
                completion_model = self.model
                if use_responses:
                    completion_model = os.getenv('OPENAI_FALLBACK_MODEL', 'gpt-4o')
                    logger.info(f"ℹ️ Fallback a Chat Completions con modelo compatible: {completion_model}")
                completion_params = {
                    "model": completion_model,
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 2000,
                    "timeout": 60
                }

                response = self.client.chat.completions.create(**completion_params)
                content = getattr(response.choices[0].message, 'content', None) or getattr(response.choices[0], 'text', '')
                input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                output_tokens = getattr(response.usage, 'completion_tokens', 0)
                total_tokens = getattr(response.usage, 'total_tokens', (input_tokens + output_tokens))
            
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
            
            # Calcular coste usando pricing de BD
            cost = (input_tokens * self.pricing['input'] + 
                   output_tokens * self.pricing['output'])
            
            return {
                'success': True,
                'content': content,
                'sources': sources,
                'tokens': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': round(cost, 6),
                'response_time_ms': response_time,
                'model_used': self.model
            }
            
        except (getattr(openai, 'APIStatusError', Exception), getattr(openai, 'BadRequestError', Exception), getattr(openai, 'NotFoundError', Exception), openai.APIError) as e:
            # Fallback automático si el modelo no existe/no está permitido
            err_msg = str(e)
            if ('model' in err_msg.lower() and 'does not exist' in err_msg.lower()) or ('not found' in err_msg.lower() and 'model' in err_msg.lower()):
                logger.warning(f"⚠️ Modelo '{self.model}' no disponible. Reintentando con 'gpt-4o'...")
                try:
                    fallback_model = 'gpt-4o'
                    # gpt-4o usa max_tokens (no max_completion_tokens)
                    response = self.client.chat.completions.create(
                        model=fallback_model,
                        messages=[
                            {"role": "user", "content": query}
                        ],
                        max_tokens=2000
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

