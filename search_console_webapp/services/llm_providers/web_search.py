"""
Búsqueda web en los providers de LLM Monitoring (query fan-out).

El interruptor es `llm_monitoring_projects.search_mode` y solo lo cambia el admin:

- `off` (por defecto): OpenAI, Anthropic y Gemini se llaman exactamente como antes,
  sin herramientas (miden la memoria del modelo). Perplexity busca siempre con su
  preset barato.
- `auto`: se ofrece la herramienta de búsqueda de cada proveedor sin forzarla ni
  pedirla en las instrucciones; el modelo decide si busca.

Cualquier valor distinto de 'auto' se trata como 'off'. Las llamadas con búsqueda
van por REST (mismo formato que las pruebas de P1 y que Perplexity) para no depender
de la versión de cada SDK. Cada provider convierte la respuesta con un parser puro y
`build_search_result` la lleva al contrato común (PLAN-fanout-y-modelos-2026-09.md §3).
"""

import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import requests

from .base_provider import extract_urls_from_text
from .fanout_utils import normalize_url

logger = logging.getLogger(__name__)

SEARCH_MODE_OFF = 'off'
SEARCH_MODE_AUTO = 'auto'
SEARCH_MODES = (SEARCH_MODE_OFF, SEARCH_MODE_AUTO)

# Con búsqueda una respuesta tarda 10-60 s (P1); el margen cubre picos y rondas largas
SEARCH_TIMEOUT_SECONDS = float(os.getenv('LLM_SEARCH_TIMEOUT_SECONDS', '240'))


def normalize_search_mode(value: Optional[str]) -> str:
    """Solo 'auto' activa la búsqueda: cualquier otro valor (None, typo, '') es 'off'."""
    return SEARCH_MODE_AUTO if value == SEARCH_MODE_AUTO else SEARCH_MODE_OFF


def is_search_enabled(value: Optional[str]) -> bool:
    return normalize_search_mode(value) == SEARCH_MODE_AUTO


def http_error_message(provider_label: str, response: requests.Response) -> str:
    """
    Mensaje de error que conserva el código HTTP y el tipo de error de la API, para
    que `classify_error()` distinga rate limit, cuenta sin crédito o error permanente.
    Acepta los formatos {"error": {"type", "message"}} (OpenAI, Anthropic, Perplexity)
    y {"error": {"status", "message"}} (Gemini).
    """
    detail = response.text[:500]
    try:
        err = (response.json() or {}).get('error') or {}
        if isinstance(err, dict):
            detail = err.get('message') or detail
            kind = err.get('type') or err.get('code') or err.get('status')
            if kind:
                detail = f"{kind}: {detail}"
    except ValueError:
        pass
    return f"{provider_label} API Error: HTTP {response.status_code} - {detail}"


def post_json(url: str, *, headers: Dict, body: Dict, provider_label: str,
              timeout: float = SEARCH_TIMEOUT_SECONDS) -> Tuple[Optional[Dict], Optional[str]]:
    """POST JSON. Devuelve (data, None) si HTTP 200 con JSON válido; si no, (None, error)."""
    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.Timeout:
        return None, f"{provider_label} request timed out after {timeout:.0f}s"
    except requests.RequestException as e:
        return None, f"{provider_label} connection error: {e}"

    if response.status_code != 200:
        return None, http_error_message(provider_label, response)
    try:
        return response.json(), None
    except ValueError:
        return None, f"{provider_label} API Error: invalid JSON response"


class SourceCollector:
    """
    Fuentes de una respuesta con búsqueda, sin duplicados y en orden de aparición.

    Se añaden primero los resultados de cada búsqueda (con su ronda) y después las
    citas del texto; `cited()` devuelve solo las citadas, que es lo que va a `sources`:
    la detección de marca cuenta un enlace como mención y una página recuperada pero no
    citada no la ve el usuario (las recuperadas quedan en el fan-out).
    """

    def __init__(self, provider: str):
        self.provider = provider
        self._by_url: Dict[str, Dict] = {}

    def add(self, url: Optional[str], *, title: Optional[str] = None,
            query_round: Optional[int] = None, cited: bool = False) -> Optional[str]:
        url = normalize_url(url)
        if not url:
            return None
        existing = self._by_url.get(url)
        if existing:
            existing['cited'] = existing['cited'] or cited
            existing['title'] = existing['title'] or title
        else:
            self._by_url[url] = {'url': url, 'provider': self.provider, 'title': title,
                                 'query_round': query_round, 'cited': cited}
        return url

    def cited(self) -> List[Dict]:
        return [source for source in self._by_url.values() if source['cited']]


def token_cost(input_tokens: int, output_tokens: int, pricing: Dict) -> float:
    return input_tokens * pricing.get('input', 0.0) + output_tokens * pricing.get('output', 0.0)


def search_tool_cost(billable_calls: int, pricing: Dict, *, provider: str, model: str) -> float:
    """Coste de la herramienta de búsqueda (aparte de los tokens), con el precio del registry."""
    per_call = pricing.get('search')
    if billable_calls and not per_call:
        logger.warning(
            f"⚠️ {provider}/{model} sin cost_per_1k_search_calls en llm_model_registry: "
            f"{billable_calls} búsquedas sin coste (ejecutar migrate_llm_search_p3.py)"
        )
        return 0.0
    return billable_calls * (per_call or 0.0)


def build_search_result(parsed: Dict, *, provider: str, cost_usd: float, search_cost_usd: float,
                        model_used: str, prompt_strategy: str, search_tool: str,
                        search_country: Optional[str], started_at: float) -> Dict:
    """
    Resultado estándar de una llamada con búsqueda (contrato §3).

    `parsed` es la salida de un parser de respuesta: content, sources, search_queries,
    search_used, search_calls, page_opens, input_tokens, output_tokens, tokens y
    api_model_reported. Si el modelo no aportó fuentes (no buscó), las URLs se extraen
    del texto como en el modo sin búsqueda (`provider='extracted'`).
    """
    sources = parsed['sources'] or extract_urls_from_text(parsed['content'])
    logger.debug(
        f"🔎 {provider}: search_used={parsed['search_used']} calls={parsed['search_calls']} "
        f"pages={parsed['page_opens']} sources={len(sources)}"
    )
    return {
        'success': True,
        'content': parsed['content'],
        'sources': sources,
        'tokens': parsed['tokens'],
        'input_tokens': parsed['input_tokens'],
        'output_tokens': parsed['output_tokens'],
        'cost_usd': round(float(cost_usd), 6),
        'response_time_ms': int((time.time() - started_at) * 1000),
        'model_used': model_used,
        'prompt_strategy': prompt_strategy,
        'api_model_reported': parsed.get('api_model_reported'),
        'search_tool': search_tool,
        'search_country': search_country,
        'search_used': parsed['search_used'],
        'search_calls': parsed['search_calls'],
        'page_opens': parsed['page_opens'],
        'search_cost_usd': round(float(search_cost_usd), 6),
        'search_queries': parsed['search_queries'],
    }
