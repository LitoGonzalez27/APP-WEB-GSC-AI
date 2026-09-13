"""
Proveedor Anthropic (Claude)

- Modelo: el `is_current` de llm_model_registry (fallback en base_provider.DEFAULT_MODELS).
- Precios: siempre desde BD, nunca hardcodeados.
"""

import logging
import time
from typing import Dict, List, Optional
import anthropic
from .base_provider import (
    BaseLLMProvider,
    get_model_pricing_from_db,
    resolve_model_id,
    extract_urls_from_text
)
from .locale_helpers import LocaleContext, build_system_instruction
from .retry_handler import with_retry, RetryConfig, note_health_check_failure
from .web_search import (
    SourceCollector,
    build_search_result,
    is_search_enabled,
    post_json,
    search_tool_cost,
    token_cost,
)

logger = logging.getLogger(__name__)

MESSAGES_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 8000
# Versión básica (llamada directa): las de filtrado dinámico triplican el coste y
# lanzan búsquedas desde código que no son comparables con otros proveedores (P1).
WEB_SEARCH_TOOL = "web_search_20250305"
WEB_SEARCH_MAX_USES = 5
# Turnos largos de búsqueda: la API devuelve stop_reason=pause_turn y hay que
# reenviar el mensaje del asistente tal cual para que continúe.
MAX_PAUSE_TURN_CONTINUATIONS = 3


def extract_response_text(blocks) -> str:
    """
    Texto de la respuesta: concatena solo los bloques `text`.

    Claude Sonnet 5 puede anteponer un bloque `thinking` (y con herramientas hay
    varios bloques de texto). Antes se leía `content[0].text`: con el SDK de
    producción (0.39) el bloque thinking llega como TextBlock con text=None, la
    tarea reventaba al medir el contenido y la respuesta se perdía sin dejar fila
    de error (5-10 % de las respuestas de Anthropic en los crons de sept. 2026).
    """
    return ''.join(
        getattr(block, 'text', None) or ''
        for block in (blocks or [])
        if getattr(block, 'type', None) == 'text'
    )


def merge_turns(responses: List[Dict]) -> Dict:
    """
    Une las respuestas de un turno partido por `pause_turn`: bloques de contenido en
    orden y uso de tokens y búsquedas sumado (cada petición se factura entera).
    """
    last = responses[-1]
    usage: Dict = {'input_tokens': 0, 'output_tokens': 0, 'server_tool_use': {'web_search_requests': 0}}
    for response in responses:
        u = response.get('usage') or {}
        usage['input_tokens'] += (int(u.get('input_tokens') or 0)
                                  + int(u.get('cache_creation_input_tokens') or 0)
                                  + int(u.get('cache_read_input_tokens') or 0))
        usage['output_tokens'] += int(u.get('output_tokens') or 0)
        usage['server_tool_use']['web_search_requests'] += int(
            (u.get('server_tool_use') or {}).get('web_search_requests') or 0)
    return {
        **last,
        'content': [block for response in responses for block in (response.get('content') or [])],
        'usage': usage,
    }


def parse_messages_response(data: Dict) -> Dict:
    """
    Convierte una respuesta de Messages API con `web_search` al formato común.

    Función pura (tests con respuestas reales en tests/fixtures/fanout/).

    - Texto: concatena todos los bloques `text` (con búsqueda hay muchos, intercalados
      con `thinking`, `server_tool_use` y resultados).
    - Cada `server_tool_use` de `web_search` es una ronda; sus resultados llegan en el
      `web_search_tool_result` con el mismo `tool_use_id` (si la búsqueda falló, `content`
      es un objeto de error y la ronda queda sin fuentes).
    - `sources` son solo las URLs citadas (`citations` de los bloques de texto), con la
      ronda que las trajo; todas las recuperadas quedan en `search_queries[].sources`.
    """
    blocks = data.get('content') or []
    results_by_tool_use: Dict[str, List[Dict]] = {
        block.get('tool_use_id'): block.get('content')
        for block in blocks
        if block.get('type') == 'web_search_tool_result' and isinstance(block.get('content'), list)
    }

    search_queries: List[Dict] = []
    sources = SourceCollector('anthropic')

    search_round = 0
    for block in blocks:
        if block.get('type') != 'server_tool_use' or block.get('name') != 'web_search':
            continue
        search_round += 1
        round_urls = [
            url for url in (sources.add(result.get('url'), title=result.get('title'), query_round=search_round)
                            for result in results_by_tool_use.get(block.get('id')) or []) if url
        ]
        search_queries.append({'round': search_round, 'action': 'search',
                               'query': (block.get('input') or {}).get('query'),
                               'url': None, 'sources': round_urls})

    text_blocks = [block for block in blocks if block.get('type') == 'text']
    for block in text_blocks:
        for citation in block.get('citations') or []:
            sources.add(citation.get('url'), title=citation.get('title'), cited=True)

    usage = data.get('usage') or {}
    input_tokens = (int(usage.get('input_tokens') or 0)
                    + int(usage.get('cache_creation_input_tokens') or 0)
                    + int(usage.get('cache_read_input_tokens') or 0))
    output_tokens = int(usage.get('output_tokens') or 0)
    billable = (usage.get('server_tool_use') or {}).get('web_search_requests')
    return {
        'content': ''.join(block.get('text') or '' for block in text_blocks),
        'sources': sources.cited(),
        'search_queries': search_queries,
        'search_used': search_round > 0,
        'search_calls': search_round,
        'page_opens': 0,
        'billable_search_calls': int(search_round if billable is None else billable),
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'tokens': input_tokens + output_tokens,
        'api_model_reported': data.get('model'),
    }


class AnthropicProvider(BaseLLMProvider):
    """Proveedor para Claude (Anthropic)."""
    
    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor Anthropic
        
        Args:
            api_key: API key de Anthropic (obtener en console.anthropic.com)
            model: Modelo específico a usar (opcional)
        """
        self.api_key = api_key
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
                      locale: Optional[LocaleContext] = None,
                      search_mode: str = 'off') -> Dict:
        """
        Ejecuta una query contra Claude.

        Args:
            query: Pregunta a enviar a Claude.
            locale: LocaleContext opcional. Cuando se pasa, se usa el
                    parámetro top-level `system=` del método
                    client.messages.create() con la instrucción en lengua
                    destino. Claude da alto peso al parámetro system y
                    produce respuestas más fieles al locale objetivo.
            search_mode: 'off' (sin herramientas, como siempre) o 'auto'
                    (herramienta `web_search`, ver web_search.py).

        Returns:
            Dict con respuesta estandarizada (incluye 'prompt_strategy').
        """
        if is_search_enabled(search_mode):
            return self._execute_with_search(query, locale)

        start_time = time.time()

        # ─── Construir parámetros de la llamada ───────────────────────
        create_params = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,  # Reducido de 64K para evitar error de streaming requerido
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

            content = extract_response_text(response.content)
            if not content.strip():
                return {
                    'success': False,
                    'error': f"Empty content from Anthropic response (stop_reason={getattr(response, 'stop_reason', None)})",
                }

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
    
    def _execute_with_search(self, query: str, locale: Optional[LocaleContext]) -> Dict:
        """Messages API por REST con `web_search` disponible (el modelo decide si busca)."""
        start_time = time.time()
        tool: Dict = {'type': WEB_SEARCH_TOOL, 'name': 'web_search', 'max_uses': WEB_SEARCH_MAX_USES}
        messages: List[Dict] = [{'role': 'user', 'content': query}]
        body: Dict = {'model': self.model, 'max_tokens': MAX_TOKENS, 'messages': messages, 'tools': [tool]}
        if locale is not None:
            body['system'] = build_system_instruction(locale)
            tool['user_location'] = {'type': 'approximate', 'country': locale.country_code}
        prompt_strategy = 'system_user_geo' if locale is not None else 'legacy_user_only'

        responses: List[Dict] = []
        while True:
            data, error = post_json(
                MESSAGES_API_URL,
                headers={'x-api-key': self.api_key, 'anthropic-version': ANTHROPIC_VERSION,
                         'content-type': 'application/json'},
                body=body,
                provider_label='Anthropic',
            )
            if error:
                logger.error(f"❌ {error}")
                return {'success': False, 'error': error}
            responses.append(data)
            if data.get('stop_reason') != 'pause_turn' or len(responses) > MAX_PAUSE_TURN_CONTINUATIONS:
                break
            messages.append({'role': 'assistant', 'content': data.get('content') or []})

        merged = merge_turns(responses)
        parsed = parse_messages_response(merged)
        if not parsed['content'].strip():
            return {
                'success': False,
                'error': f"Empty content from Anthropic response (stop_reason={merged.get('stop_reason')})",
            }

        search_cost = search_tool_cost(parsed['billable_search_calls'], self.pricing,
                                       provider='anthropic', model=self.model)
        return build_search_result(
            parsed,
            provider='anthropic',
            cost_usd=token_cost(parsed['input_tokens'], parsed['output_tokens'], self.pricing) + search_cost,
            search_cost_usd=search_cost,
            model_used=self.model,
            prompt_strategy=prompt_strategy,
            search_tool=f'anthropic_{WEB_SEARCH_TOOL}',
            search_country=locale.country_code if locale is not None else None,
            started_at=start_time,
        )

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
