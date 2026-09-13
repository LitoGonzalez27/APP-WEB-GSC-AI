"""
Proveedor OpenAI (GPT)

- Modelo: `OPENAI_PREFERRED_MODEL` o el `is_current` de llm_model_registry
  (fallback en base_provider.DEFAULT_MODELS).
- Precios: siempre desde BD, nunca hardcodeados.
"""

import logging
import time
from typing import Dict, List, Optional
import os
import openai
from .base_provider import (
    BaseLLMProvider,
    get_model_pricing_from_db,
    resolve_model_id,
    extract_urls_from_text
)
from .fanout_utils import dedupe_preserving_order, normalize_url
from .locale_helpers import LocaleContext, build_system_instruction
from .retry_handler import with_retry, note_health_check_failure
from .web_search import (
    SourceCollector,
    build_search_result,
    is_search_enabled,
    post_json,
    search_tool_cost,
    token_cost,
)

logger = logging.getLogger(__name__)

RESPONSES_API_URL = "https://api.openai.com/v1/responses"
MAX_OUTPUT_TOKENS = 16000
PAGE_ACTIONS = ('open_page', 'find_in_page')


def parse_responses_output(data: Dict) -> Dict:
    """
    Convierte una respuesta de la Responses API con `web_search` al formato común.

    Función pura (tests con respuestas reales en tests/fixtures/fanout/).

    - Cada `web_search_call` de tipo `search` es una ronda: con gpt-5.5 trae varias
      sub-consultas en `action.queries` y las fuentes (`action.sources`) son de la
      llamada entera, así que todas sus sub-consultas comparten esas URLs.
    - `open_page` / `find_in_page` son páginas leídas (`find_in_page` guarda el patrón
      buscado en `query`).
    - `sources` son solo las URLs citadas en el texto final (`url_citation`), con la
      ronda de búsqueda que las trajo (ver SourceCollector).
    - `billable_search_calls` cuenta todas las llamadas a la herramienta (criterio
      conservador: OpenAI factura por llamada).
    """
    output = data.get('output') or []
    search_queries: List[Dict] = []
    sources = SourceCollector('openai')
    search_round = 0
    tool_calls = 0

    for item in output:
        if item.get('type') != 'web_search_call':
            continue
        tool_calls += 1
        action = item.get('action') or {}
        action_type = action.get('type')

        if action_type == 'search':
            search_round += 1
            round_urls = dedupe_preserving_order(
                url for url in (sources.add(s.get('url'), query_round=search_round)
                                for s in (action.get('sources') or [])) if url
            )
            queries = dedupe_preserving_order(q for q in (action.get('queries') or [action.get('query')]) if q)
            for query in queries or [None]:
                search_queries.append({'round': search_round, 'action': 'search', 'query': query,
                                       'url': None, 'sources': round_urls})
        elif action_type in PAGE_ACTIONS:
            search_queries.append({'round': search_round, 'action': action_type, 'query': action.get('pattern'),
                                   'url': normalize_url(action.get('url')), 'sources': []})

    content_parts = []
    for item in output:
        if item.get('type') != 'message':
            continue
        for part in item.get('content') or []:
            if part.get('type') != 'output_text':
                continue
            content_parts.append(part.get('text') or '')
            for annotation in part.get('annotations') or []:
                if annotation.get('type') == 'url_citation':
                    sources.add(annotation.get('url'), title=annotation.get('title'), cited=True)

    usage = data.get('usage') or {}
    input_tokens = int(usage.get('input_tokens') or 0)
    output_tokens = int(usage.get('output_tokens') or 0)  # incluye razonamiento
    return {
        'content': ''.join(content_parts),
        'sources': sources.cited(),
        'search_queries': search_queries,
        'search_used': search_round > 0,
        'search_calls': search_round,
        'page_opens': sum(1 for q in search_queries if q['action'] in PAGE_ACTIONS),
        'billable_search_calls': tool_calls,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'tokens': int(usage.get('total_tokens') or input_tokens + output_tokens),
        'api_model_reported': data.get('model'),
    }


def _is_model_unavailable(error: str) -> bool:
    err = error.lower()
    return 'model' in err and any(m in err for m in ('not found', 'does not exist', 'not have access', 'unsupported'))


class OpenAIProvider(BaseLLMProvider):
    """Proveedor para OpenAI (GPT)."""
    
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
            
            >>> provider = OpenAIProvider(api_key='sk-proj-...', model='gpt-5.4')
            >>> # Usará específicamente gpt-5.4
        """
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
        
        # ✅ CORRECCIÓN: Priorizar variable de entorno, luego parámetro, luego BD
        preferred = os.getenv('OPENAI_PREFERRED_MODEL')
        if preferred:
            self.model = preferred
            logger.info(f"ℹ️ OPENAI_PREFERRED_MODEL detectado: {self.model}")
        else:
            self.model = resolve_model_id('openai', model)
        
        # ✅ CORRECCIÓN: Obtener pricing de BD (SINGLE SOURCE OF TRUTH)
        self.pricing = get_model_pricing_from_db('openai', self.model)
        
        logger.info(f"🤖 OpenAI Provider inicializado")
        logger.info(f"   Modelo: {self.model}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    @with_retry  # ✨ NUEVO: Retry automático con exponential backoff
    def execute_query(self, query: str, *,
                      locale: Optional[LocaleContext] = None,
                      search_mode: str = 'off') -> Dict:
        """
        Ejecuta una query contra el modelo OpenAI configurado.

        Args:
            query: Pregunta a hacer a ChatGPT (sin contexto de locale
                   concatenado — se inyecta vía system message).
            locale: LocaleContext opcional. Si se pasa, se antepone un
                    system message con la instrucción en la lengua destino
                    construida por build_system_instruction(locale).
                    Si es None, comportamiento idéntico al anterior
                    (solo user message).
            search_mode: 'off' (Chat Completions sin herramientas, como siempre)
                    o 'auto' (Responses API con `web_search`, ver web_search.py).

        Returns:
            Dict con respuesta estandarizada (incluye 'prompt_strategy').
        """
        if is_search_enabled(search_mode):
            return self._execute_with_search(query, locale)

        start_time = time.time()

        # ─── Construir `messages` UNA sola vez ───────────────────────
        # Importante: esta lista se reutiliza en TODOS los paths del
        # método (llamada normal y dos fallback paths a gpt-4o). Así
        # nos aseguramos de que el system message se preserva siempre.
        messages = []
        if locale is not None:
            messages.append({
                "role": "system",
                "content": build_system_instruction(locale),
            })
            prompt_strategy = 'system_user'
            logger.info(
                f"🌍 OpenAI: locale applied [{locale.fingerprint()}] "
                f"strategy={prompt_strategy}"
            )
        else:
            prompt_strategy = 'legacy_user_only'
        messages.append({"role": "user", "content": query})

        try:
            content = None
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0

            # Chat Completions con el modelo configurado
            # GPT-5.x usa max_completion_tokens, GPT-4o usa max_tokens
            is_gpt5 = self.model.startswith('gpt-5')
            completion_params = {
                "model": self.model,
                "messages": messages,  # ← usa la lista construida arriba
                "timeout": 120,
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
                    # gpt-4o usa max_tokens — REUSA `messages` (con system si aplicaba)
                    fallback_params = {
                        "model": fallback_model,
                        "messages": messages,  # ← preserva el system message
                        "max_tokens": 16000,
                        "timeout": 120,
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
                'model_used': actual_model_used,
                'prompt_strategy': prompt_strategy,  # ✨ NUEVO
            }

        except (getattr(openai, 'APIStatusError', Exception), getattr(openai, 'BadRequestError', Exception), getattr(openai, 'NotFoundError', Exception), openai.APIError) as e:
            # Fallback automático si el modelo no existe/no está permitido
            err_msg = str(e)
            if ('model' in err_msg.lower() and 'does not exist' in err_msg.lower()) or ('not found' in err_msg.lower() and 'model' in err_msg.lower()):
                logger.warning(f"⚠️ Modelo '{self.model}' no disponible. Reintentando con 'gpt-4o' como fallback...")
                try:
                    fallback_model = 'gpt-4o'
                    # gpt-4o usa max_tokens — REUSA `messages` (con system si aplicaba)
                    response = self.client.chat.completions.create(
                        model=fallback_model,
                        messages=messages,  # ← preserva el system message
                        max_tokens=16000,
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
                        'model_used': fallback_model,
                        'prompt_strategy': prompt_strategy,  # ✨ NUEVO
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
    
    def _execute_with_search(self, query: str, locale: Optional[LocaleContext]) -> Dict:
        """Responses API con la herramienta `web_search` en modo auto (el modelo decide si busca)."""
        start_time = time.time()
        tool: Dict = {'type': 'web_search'}
        body: Dict = {
            'input': query,
            'tools': [tool],
            'tool_choice': 'auto',
            'include': ['web_search_call.action.sources'],
            'max_output_tokens': MAX_OUTPUT_TOKENS,
        }
        if locale is not None:
            body['instructions'] = build_system_instruction(locale)
            tool['user_location'] = {'type': 'approximate', 'country': locale.country_code}
        prompt_strategy = 'system_user_geo' if locale is not None else 'legacy_user_only'

        fallback_model = os.getenv('OPENAI_FALLBACK_MODEL', 'gpt-4o')
        model = self.model
        data, error = self._post_responses({**body, 'model': model})
        if error and _is_model_unavailable(error) and fallback_model != model:
            logger.warning(f"⚠️ OpenAI (búsqueda): '{model}' no disponible, usando fallback {fallback_model}: {error}")
            model = fallback_model
            data, error = self._post_responses({**body, 'model': model})
        if error:
            logger.error(f"❌ {error}")
            return {'success': False, 'error': error}

        if data.get('error'):
            return {'success': False, 'error': f"OpenAI API Error: {data['error']}"}
        parsed = parse_responses_output(data)
        if not parsed['content'].strip():
            return {
                'success': False,
                'error': f"Empty content from OpenAI response (status={data.get('status')})",
            }

        pricing = self.pricing if model == self.model else get_model_pricing_from_db('openai', model)
        search_cost = search_tool_cost(parsed['billable_search_calls'], pricing, provider='openai', model=model)
        return build_search_result(
            parsed,
            provider='openai',
            cost_usd=token_cost(parsed['input_tokens'], parsed['output_tokens'], pricing) + search_cost,
            search_cost_usd=search_cost,
            model_used=model,
            prompt_strategy=prompt_strategy,
            search_tool='openai_web_search',
            search_country=locale.country_code if locale is not None else None,
            started_at=start_time,
        )

    def _post_responses(self, body: Dict):
        return post_json(
            RESPONSES_API_URL,
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
            body=body,
            provider_label='OpenAI',
        )

    def get_provider_name(self) -> str:
        return 'openai'
    
    
    def test_connection(self) -> bool:
        """
        Llamada mínima real al modelo configurado.

        `models.list()` respondía OK aunque la cuenta no tuviera crédito
        (incidente 2026-09-11): el cron no se enteraba y fallaba prompt a prompt.
        Si el fallo es por falta de crédito se abre ya el circuit breaker.
        """
        token_param = 'max_completion_tokens' if self.model.startswith('gpt-5') else 'max_tokens'
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                timeout=30,
                **{token_param: 16},
            )
            logger.info("✅ OpenAI connection test successful")
            return True
        except Exception as e:
            note_health_check_failure(self.get_provider_name(), e)
            logger.error(f"❌ OpenAI connection test failed: {e}")
            return False
