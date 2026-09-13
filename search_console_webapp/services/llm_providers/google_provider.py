"""
Proveedor Google (Gemini)

- Modelo: el `is_current` de llm_model_registry (fallback en base_provider.DEFAULT_MODELS).
- Precios: siempre desde BD, nunca hardcodeados. Gemini 3.x factura el
  razonamiento como salida (ver cálculo de output_tokens).
"""

import os
import logging
import time
from typing import Dict, List, Optional
from urllib.parse import quote
import google.generativeai as genai
from .base_provider import (
    BaseLLMProvider,
    get_model_pricing_from_db,
    resolve_model_id,
    extract_urls_from_text
)
from .fanout_utils import (
    GROUNDING_REDIRECT_HOST,
    dedupe_preserving_order,
    normalize_domain,
    normalize_url,
    resolve_redirects,
)
from .locale_helpers import LocaleContext, build_system_instruction
from .retry_handler import with_retry, note_health_check_failure
from .web_search import (
    build_search_result,
    is_search_enabled,
    post_json,
    search_tool_cost,
    token_cost,
)

logger = logging.getLogger(__name__)

GENERATE_CONTENT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Misma configuración que el camino sin búsqueda: cambiar el muestreo entre modos
# añadiría una diferencia que no es la búsqueda.
GENERATION_CONFIG = {
    'max_output_tokens': 65536,
    'temperature': 0.7,
}


def parse_generate_content(data: Dict) -> Dict:
    """
    Convierte una respuesta de generateContent con `google_search` al formato común.

    Función pura (tests con respuestas reales en tests/fixtures/fanout/).

    - Texto: partes del primer candidato que no son razonamiento (`thought`).
    - `webSearchQueries` es una lista plana sin atribución de fuentes: todas las
      sub-consultas van en la ronda 1 con `sources=[]` (el fan-out guarda NULL en
      `brand_in_sources`). Las fuentes son los `groundingChunks` que usa el texto
      (`groundingSupports`): como en OpenAI y Anthropic, solo las citadas. Sus URIs son
      redirecciones que caducan: el provider las resuelve (`resolve_grounding_sources`).
    - Gemini 3.x factura cada consulta de búsqueda y el razonamiento como salida.
    """
    candidate = (data.get('candidates') or [{}])[0]
    parts = (candidate.get('content') or {}).get('parts') or []
    grounding = candidate.get('groundingMetadata') or {}

    raw_queries = [q for q in (grounding.get('webSearchQueries') or []) if q]
    queries = dedupe_preserving_order(raw_queries)
    cited_chunks = {
        index
        for support in (grounding.get('groundingSupports') or [])
        for index in (support.get('groundingChunkIndices') or [])
    }
    sources = []
    for index, chunk in enumerate(grounding.get('groundingChunks') or []):
        web = chunk.get('web') or {}
        if web.get('uri') and index in cited_chunks:
            sources.append({'url': web['uri'], 'provider': 'google', 'title': web.get('title'),
                            'query_round': 1 if queries else None, 'cited': True})

    usage = data.get('usageMetadata') or {}
    input_tokens = int(usage.get('promptTokenCount') or 0) + int(usage.get('toolUsePromptTokenCount') or 0)
    total_tokens = int(usage.get('totalTokenCount') or 0)
    output_tokens = max(
        int(usage.get('candidatesTokenCount') or 0) + int(usage.get('thoughtsTokenCount') or 0),
        total_tokens - input_tokens,
    )
    return {
        'content': ''.join(p.get('text') or '' for p in parts if not p.get('thought')),
        'sources': sources,
        'search_queries': [{'round': 1, 'action': 'search', 'query': q, 'url': None, 'sources': []}
                           for q in queries],
        'search_used': bool(queries),
        'search_calls': len(queries),
        'page_opens': 0,
        'billable_search_calls': len(raw_queries),
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'tokens': total_tokens or input_tokens + output_tokens,
        'api_model_reported': data.get('modelVersion'),
        'finish_reason': candidate.get('finishReason'),
        'block_reason': (data.get('promptFeedback') or {}).get('blockReason'),
    }


def resolve_grounding_sources(sources: List[Dict], resolver=resolve_redirects) -> List[Dict]:
    """
    Sustituye las URIs de redirección de grounding por la URL final y une las fuentes
    que resultan ser la misma página. Si una no se resuelve se conserva la redirección.
    """
    redirects = [s['url'] for s in sources if normalize_domain(s['url']) == GROUNDING_REDIRECT_HOST]
    resolved = resolver(redirects) if redirects else {}
    merged: List[Dict] = []
    by_url: Dict[str, Dict] = {}
    for source in sources:
        url = resolved.get(source['url']) or normalize_url(source['url'])
        if url in by_url:
            by_url[url]['cited'] = by_url[url]['cited'] or source['cited']
            continue
        by_url[url] = {**source, 'url': url}
        merged.append(by_url[url])
    return merged


class GoogleProvider(BaseLLMProvider):
    """Proveedor para Gemini (Google)."""

    def __init__(self, api_key: str, model: str = None):
        """
        Inicializa el proveedor Google

        Args:
            api_key: API key de Google (obtener en aistudio.google.com)
            model: Modelo específico a usar (opcional)
        """
        self.api_key = api_key
        genai.configure(api_key=api_key)

        self.model_name = resolve_model_id('google', model)
        
        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config=GENERATION_CONFIG
        )
        
        self.pricing = get_model_pricing_from_db('google', self.model_name)
        
        logger.info(f"🤖 Google Provider inicializado")
        logger.info(f"   Modelo: {self.model_name}")
        logger.info(f"   Pricing: ${self.pricing['input']*1000000:.2f}/${self.pricing['output']*1000000:.2f} per 1M tokens")
    
    @with_retry
    def execute_query(self, query: str, *,
                      locale: Optional[LocaleContext] = None,
                      search_mode: str = 'off') -> Dict:
        """
        Ejecuta una query contra Gemini.

        Con search_mode='auto' va por REST con la herramienta `google_search`
        (el SDK legacy no la soporta; ver web_search.py). Con 'off', el SDK de siempre.

        Args:
            query: Pregunta a enviar a Gemini.
            locale: LocaleContext opcional. Cuando se pasa, se prepende
                    un bloque [SYSTEM INSTRUCTION] al contenido antes de
                    enviarlo. Esto es necesario porque el SDK
                    google.generativeai acepta system_instruction solo a
                    nivel de modelo (en __init__), no per-call. Prepender
                    con estructura clara es empíricamente efectivo para
                    corregir sesgos de región (ej: sesgo brasileño con
                    portugués).

        Returns:
            Dict con respuesta estandarizada (incluye 'prompt_strategy').
        """
        if is_search_enabled(search_mode):
            return self._execute_with_search(query, locale)

        start_time = time.time()

        # ─── Construir final_prompt con bloque SYSTEM si hay locale ───
        if locale is not None:
            system_text = build_system_instruction(locale)
            final_prompt = (
                f"[SYSTEM INSTRUCTION]\n{system_text}\n\n"
                f"[USER QUERY]\n{query}"
            )
            prompt_strategy = 'prepended_system'
            logger.info(
                f"🌍 Google: locale applied [{locale.fingerprint()}] "
                f"strategy={prompt_strategy}"
            )
        else:
            final_prompt = query
            prompt_strategy = 'legacy_user_only'

        try:
            response = self.model.generate_content(
                final_prompt,
                request_options={"timeout": 60}  # Hard cap 60s, evita gRPC defaults de 300s+
            )
            response_time = int((time.time() - start_time) * 1000)

            content = response.text

            input_tokens = 0
            output_tokens = 0
            total_tokens = 0

            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                total_tokens = getattr(response.usage_metadata, 'total_token_count', 0)
                # Gemini 3.x factura el razonamiento (thoughtsTokenCount) como
                # salida, pero candidates_token_count no lo incluye y el SDK
                # legacy no expone el campo: se deriva de total - prompt.
                output_tokens = max(
                    getattr(response.usage_metadata, 'candidates_token_count', 0),
                    total_tokens - input_tokens,
                )
            else:
                # Estimación sobre final_prompt (no query) para reflejar coste real
                input_tokens = int(len(final_prompt.split()) * 1.3)
                output_tokens = int(len(content.split()) * 1.3)
                total_tokens = input_tokens + output_tokens
                logger.debug(f"ℹ️ Gemini no expuso usage_metadata, usando estimación")

            sources = extract_urls_from_text(content)

            cost = (input_tokens * self.pricing['input'] +
                   output_tokens * self.pricing['output'])

            return {
                'success': True,
                'content': content,
                'sources': sources,
                'tokens': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': round(cost, 8),
                'response_time_ms': response_time,
                'model_used': self.model_name,
                'prompt_strategy': prompt_strategy,  # ✨ NUEVO
            }
            
        except Exception as e:
            logger.error(f"❌ Google (Gemini) Error: {e}", exc_info=True)
            
            error_msg = str(e)
            if 'API key' in error_msg or 'api_key' in error_msg:
                error_msg = "Invalid API key or API not enabled"
            elif 'quota' in error_msg.lower():
                error_msg = "Quota exceeded. Check your Google Cloud quotas."
            elif 'safety' in error_msg.lower():
                error_msg = "Content blocked by safety filters"
            
            return {
                'success': False,
                'error': f"Google API Error: {error_msg}"
            }
    
    def _execute_with_search(self, query: str, locale: Optional[LocaleContext]) -> Dict:
        """generateContent por REST con `google_search` disponible (el modelo decide si busca)."""
        start_time = time.time()
        body: Dict = {
            'contents': [{'role': 'user', 'parts': [{'text': query}]}],
            'tools': [{'google_search': {}}],
            'generationConfig': {
                'maxOutputTokens': GENERATION_CONFIG['max_output_tokens'],
                'temperature': GENERATION_CONFIG['temperature'],
            },
        }
        if locale is not None:
            # Por REST sí hay systemInstruction por llamada (el SDK legacy obligaba a anteponerlo)
            body['systemInstruction'] = {'parts': [{'text': build_system_instruction(locale)}]}
        prompt_strategy = 'system_user' if locale is not None else 'legacy_user_only'

        data, error = post_json(
            GENERATE_CONTENT_URL.format(model=quote(self.model_name, safe='')),
            headers={'x-goog-api-key': self.api_key, 'Content-Type': 'application/json'},
            body=body,
            provider_label='Google',
        )
        if error:
            logger.error(f"❌ {error}")
            return {'success': False, 'error': error}

        parsed = parse_generate_content(data)
        if not parsed['content'].strip():
            reason = parsed['block_reason'] or parsed['finish_reason']
            detail = 'Content blocked by safety filters' if reason and 'SAFETY' in str(reason) else 'Empty content'
            return {'success': False, 'error': f"Google API Error: {detail} (reason={reason})"}
        parsed['sources'] = resolve_grounding_sources(parsed['sources'])

        search_cost = search_tool_cost(parsed['billable_search_calls'], self.pricing,
                                       provider='google', model=self.model_name)
        return build_search_result(
            parsed,
            provider='google',
            cost_usd=token_cost(parsed['input_tokens'], parsed['output_tokens'], self.pricing) + search_cost,
            search_cost_usd=search_cost,
            model_used=self.model_name,
            prompt_strategy=prompt_strategy,
            search_tool='gemini_google_search',
            # google_search no acepta país: el locale solo llega por systemInstruction
            search_country=None,
            started_at=start_time,
        )

    def get_provider_name(self) -> str:
        return 'google'
    
    
    def test_connection(self) -> bool:
        """
        Verifica que la API key funcione
        """
        try:
            # Gemini 3.x es un modelo "thinking": un "Hi" puede tardar más que un
            # chat clásico. 15s era demasiado agresivo y, bajo la carga concurrente
            # del cron, el health-check fallaba y excluía a Google del run entero.
            # Timeout configurable (default 30s).
            timeout_s = int(os.getenv('GOOGLE_HEALTHCHECK_TIMEOUT', '30'))
            test_response = self.model.generate_content(
                "Hi",
                request_options={"timeout": timeout_s}
            )
            if test_response and test_response.text:
                logger.info("✅ Google connection test successful")
                return True
            else:
                logger.error("❌ Google connection test failed: No response")
                return False
        except Exception as e:
            note_health_check_failure(self.get_provider_name(), e)
            logger.error(f"❌ Google connection test failed: {e}")
            return False
