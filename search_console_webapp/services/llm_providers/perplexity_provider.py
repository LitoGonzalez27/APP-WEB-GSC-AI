"""
Proveedor Perplexity - Agent API (POST /v1/agent)

Migrado desde /chat/completions (Sonar) el 2026-09-13: Perplexity retira
Sonar por Chat Completions el 2026-09-27. Guía oficial:
https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/how-to

- El `model_id` del registry sigue siendo el id lógico (`sonar`, `sonar-pro`...)
  y se traduce al `preset` equivalente del Agent API (PRESET_BY_MODEL).
- El coste real lo devuelve la API en `usage.cost.total_cost` (USD): no se
  recalcula con precios por token salvo que falte.
- Expone el query fan-out: cada paso `search_results` trae las sub-consultas
  (`queries`) y sus resultados.
- Busca siempre. El `search_mode` del proyecto solo elige la profundidad: `off` usa
  el preset del registry (`fast`, 1 sola búsqueda con el prompt literal) y `auto`
  sube como mínimo a `low` (5 sub-consultas en 2 rondas), que es lo que da fan-out.
"""

import logging
import re
import time
from typing import Dict, List, Optional

import requests

from .base_provider import BaseLLMProvider, get_model_pricing_from_db, resolve_model_id
from .fanout_utils import normalize_url
from .locale_helpers import LocaleContext, build_system_instruction
from .retry_handler import with_retry, RetryConfig, note_health_check_failure
from .web_search import http_error_message, is_search_enabled

logger = logging.getLogger(__name__)

AGENT_API_URL = "https://api.perplexity.ai/v1/agent"

# Equivalencias oficiales Sonar → preset (guía de migración de Perplexity)
PRESET_BY_MODEL = {
    'sonar': 'fast',
    'sonar-pro': 'low',
    'sonar-reasoning': 'medium',
    'sonar-reasoning-pro': 'medium',
    'sonar-deep-research': 'high',
    # ids legacy que aún pueden quedar en BD
    'llama-3.1-sonar-large-128k-online': 'fast',
    'llama-3.1-sonar-small-128k-online': 'fast',
}
PRESET_ORDER = ('fast', 'low', 'medium', 'high')
VALID_PRESETS = set(PRESET_ORDER)
# Preset mínimo con búsqueda activada: `fast` lanza una sola query (sin fan-out)
SEARCH_MIN_PRESET = 'low'

MAX_OUTPUT_TOKENS = 16000
_CITATION_MARKER = re.compile(r'\[(\d+)\]')


def resolve_preset(model_id: Optional[str]) -> str:
    """Traduce el id del registry al preset del Agent API (acepta presets directos)."""
    if model_id in VALID_PRESETS:
        return model_id
    return PRESET_BY_MODEL.get(model_id or '', 'fast')


def preset_for_search_mode(base_preset: str, search_mode: Optional[str]) -> str:
    """`auto` garantiza al menos SEARCH_MIN_PRESET sin rebajar un preset más profundo del registry."""
    if not is_search_enabled(search_mode):
        return base_preset
    return max(base_preset, SEARCH_MIN_PRESET, key=PRESET_ORDER.index)


def parse_agent_response(data: Dict) -> Dict:
    """
    Convierte la respuesta JSON del Agent API al formato estándar del provider.

    Función pura (sin I/O) para poder testearla con respuestas reales guardadas.

    - `content`: texto de los pasos `message`.
    - `sources`: todas las URLs devueltas por las búsquedas, en orden y sin
      duplicados, con `cited=True` si el texto final las referencia como `[n]`.
      Es el equivalente directo de `citations` de Sonar, que también devolvía
      la lista completa de resultados de búsqueda.
    - `search_queries`: una entrada por sub-consulta de cada ronda de búsqueda
      (con las URLs de esa ronda) y una por cada página leída (`fetch_url`).
    """
    output = data.get('output') or []

    content = ''.join(
        part.get('text', '')
        for step in output if step.get('type') == 'message'
        for part in (step.get('content') or [])
        if part.get('type') in (None, 'output_text', 'text')
    )
    cited_ids = {int(n) for n in _CITATION_MARKER.findall(content)}

    sources: List[Dict] = []
    seen_urls = set()
    search_queries: List[Dict] = []
    search_round = 0

    for step in output:
        step_type = step.get('type')

        if step_type == 'search_results':
            search_round += 1
            round_urls = []
            for result in step.get('results') or []:
                url = normalize_url(result.get('url'))
                if not url:
                    continue
                round_urls.append(url)
                if url not in seen_urls:
                    seen_urls.add(url)
                    sources.append({
                        'url': url,
                        'provider': 'perplexity',
                        'title': result.get('title'),
                        'query_round': search_round,
                        'cited': result.get('id') in cited_ids,
                    })
                elif result.get('id') in cited_ids:
                    next(s for s in sources if s['url'] == url)['cited'] = True
            for query in step.get('queries') or [None]:
                search_queries.append({
                    'round': search_round,
                    'action': 'search',
                    'query': query,
                    'url': None,
                    'sources': round_urls,
                })

        elif step_type == 'fetch_url_results':
            for page in step.get('contents') or []:
                search_queries.append({
                    'round': search_round,
                    'action': 'fetch_url',
                    'query': None,
                    'url': normalize_url(page.get('url')),
                    'sources': [],
                })

    usage = data.get('usage') or {}
    cost = usage.get('cost') or {}
    tool_details = usage.get('tool_calls_details') or {}
    search_calls = (tool_details.get('search_web') or {}).get('invocation')
    if search_calls is None:
        search_calls = search_round

    return {
        'content': content,
        'sources': sources,
        'search_queries': search_queries,
        'search_used': search_round > 0,
        'search_calls': int(search_calls),
        'page_opens': sum(1 for q in search_queries if q['action'] == 'fetch_url'),
        'input_tokens': int(usage.get('input_tokens') or 0),
        'output_tokens': int(usage.get('output_tokens') or 0),
        'tokens': int(usage.get('total_tokens') or 0),
        'cost_usd': cost.get('total_cost'),
        'search_cost_usd': float(cost.get('tool_calls_cost') or 0.0),
        'api_model_reported': data.get('model'),
    }


class PerplexityProvider(BaseLLMProvider):
    """Proveedor Perplexity sobre el Agent API (búsqueda web en cada consulta)."""

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.timeout = float(RetryConfig.PROVIDER_TIMEOUTS['perplexity'])

        self.model = resolve_model_id('perplexity', model)
        self.preset = resolve_preset(self.model)

        # Solo como respaldo: el Agent API devuelve el coste real en cada respuesta
        self.pricing = get_model_pricing_from_db('perplexity', self.model)

        logger.info(f"🤖 Perplexity Provider inicializado (Agent API)")
        logger.info(f"   Modelo: {self.model} → preset '{self.preset}'")

    def _post(self, payload: Dict, timeout: Optional[float] = None) -> requests.Response:
        return requests.post(
            AGENT_API_URL,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=timeout or self.timeout,
        )

    def build_payload(self, query: str, locale: Optional[LocaleContext], preset: Optional[str] = None) -> Dict:
        payload: Dict = {
            'preset': preset or self.preset,
            'input': query,
            'max_output_tokens': MAX_OUTPUT_TOKENS,
        }
        if locale is not None:
            # El idioma va como mensaje `system` dentro de `input`, NO en
            # `instructions`: `instructions` sustituye el prompt del preset y el
            # modelo deja de citar [n] y cambia su patrón de búsqueda
            # (comprobado con la API el 2026-09-13).
            payload['input'] = [
                {'type': 'message', 'role': 'system', 'content': build_system_instruction(locale)},
                {'type': 'message', 'role': 'user', 'content': query},
            ]
            payload['tools'] = [{
                'type': 'web_search',
                'user_location': {'country': locale.country_code},
            }]
        return payload

    @with_retry
    def execute_query(self, query: str, *,
                      locale: Optional[LocaleContext] = None,
                      search_mode: str = 'off') -> Dict:
        """
        Ejecuta una query contra el Agent API.

        Con `locale`, el idioma va como mensaje `system` en `input` y el país en
        `tools[web_search].user_location` (geo-enruta la búsqueda real).
        `search_mode` elige el preset (ver preset_for_search_mode).
        """
        start_time = time.time()
        prompt_strategy = 'system_user_geo' if locale is not None else 'legacy_user_only'
        preset = preset_for_search_mode(self.preset, search_mode)

        try:
            response = self._post(self.build_payload(query, locale, preset))
        except requests.Timeout:
            return {'success': False, 'error': f"Perplexity request timed out after {self.timeout:.0f}s"}
        except requests.RequestException as e:
            return {'success': False, 'error': f"Perplexity connection error: {e}"}

        if response.status_code != 200:
            error = http_error_message('Perplexity', response)
            logger.error(f"❌ {error}")
            return {'success': False, 'error': error}

        try:
            data = response.json()
        except ValueError:
            return {'success': False, 'error': 'Perplexity API Error: invalid JSON response'}

        if data.get('status') not in (None, 'completed') or data.get('error'):
            return {
                'success': False,
                'error': f"Perplexity API Error: status={data.get('status')} error={data.get('error')}",
            }

        parsed = parse_agent_response(data)
        if not parsed['content'].strip():
            return {'success': False, 'error': 'Empty content from Perplexity response'}

        cost = parsed['cost_usd']
        if cost is None:
            cost = (parsed['input_tokens'] * self.pricing['input']
                    + parsed['output_tokens'] * self.pricing['output'])

        return {
            'success': True,
            'content': parsed['content'],
            'sources': parsed['sources'],
            'tokens': parsed['tokens'],
            'input_tokens': parsed['input_tokens'],
            'output_tokens': parsed['output_tokens'],
            'cost_usd': round(float(cost), 6),
            'response_time_ms': int((time.time() - start_time) * 1000),
            'model_used': self.model,
            'prompt_strategy': prompt_strategy,
            'api_model_reported': parsed['api_model_reported'],
            'search_tool': f'perplexity_agent_{preset}',
            'search_country': locale.country_code if locale is not None else None,
            'search_used': parsed['search_used'],
            'search_calls': parsed['search_calls'],
            'page_opens': parsed['page_opens'],
            'search_cost_usd': parsed['search_cost_usd'],
            'search_queries': parsed['search_queries'],
        }

    def get_provider_name(self) -> str:
        return 'perplexity'


    def test_connection(self) -> bool:
        """
        Llamada mínima real: verifica clave, crédito y endpoint.
        `max_tool_calls=0` evita pagar una búsqueda por el health-check.
        """
        try:
            response = self._post(
                {'preset': 'fast', 'input': 'Hi', 'max_output_tokens': 20, 'max_tool_calls': 0},
                timeout=30,
            )
            if response.status_code == 200:
                logger.info("✅ Perplexity connection test successful")
                return True
            raise RuntimeError(http_error_message('Perplexity', response))
        except Exception as e:
            note_health_check_failure(self.get_provider_name(), e)
            logger.error(f"❌ Perplexity connection test failed: {e}")
            return False
