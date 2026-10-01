"""Rutas de modelos de LLM Monitoring: listado y cambio de modelo activo (/models),
descubrimiento de modelos nuevos por cron con aprobación por email
(/cron/model-discovery, /models/approve, /models/reject) y changelog (/models/changelog).

Sacadas tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros gigantes).
Registran sus rutas en el blueprint de llm_monitoring_base al importarse;
llm_monitoring_routes importa este módulo y vuelve a exponer sus nombres. Para
parchear algo que usen estas rutas en un test, hazlo en este módulo.
"""

import logging
from auth import admin_required, cron_or_auth_required, login_required
from database import get_db_connection
from datetime import datetime, timedelta
from flask import jsonify, request
import config
import os
import secrets
from llm_monitoring_base import (
    _ensure_cron_token_or_admin,
    _safe_notify_email,
    llm_monitoring_bp,
)
from llm_monitoring_informes import (
    MODEL_FALLBACKS,
    fetch_current_models,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENDPOINTS: MODELOS
# ============================================================================

@llm_monitoring_bp.route('/models', methods=['GET'])
@login_required
def get_models():
    """
    Lista todos los modelos LLM disponibles
    
    Query params opcionales:
        provider: Filtrar por proveedor (openai, anthropic, google, perplexity)
        is_current: Filtrar solo modelos actuales (true/false)
    
    Returns:
        JSON con lista de modelos y sus precios
    """
    provider = request.args.get('provider')
    is_current = request.args.get('is_current')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        query = "SELECT * FROM llm_model_registry WHERE 1=1"
        params = []
        
        if provider:
            query += " AND llm_provider = %s"
            params.append(provider)
        
        if is_current is not None:
            query += " AND is_current = %s"
            params.append(is_current.lower() == 'true')
        
        query += " ORDER BY llm_provider, is_current DESC, model_display_name"
        
        cur.execute(query, params)
        models = cur.fetchall()
        
        # Formatear modelos
        models_list = []
        for m in models:
            models_list.append({
                'id': m['id'],
                'llm_provider': m['llm_provider'],
                'model_id': m['model_id'],
                'model_display_name': m['model_display_name'],
                'cost_per_1m_input_tokens': float(m['cost_per_1m_input_tokens']) if m['cost_per_1m_input_tokens'] else 0,
                'cost_per_1m_output_tokens': float(m['cost_per_1m_output_tokens']) if m['cost_per_1m_output_tokens'] else 0,
                'max_tokens': m['max_tokens'],
                'is_current': m['is_current'],
                'is_available': m['is_available'],
                'created_at': m['created_at'].isoformat() if m['created_at'] else None,
                'updated_at': m['updated_at'].isoformat() if m['updated_at'] else None
            })
        
        return jsonify({
            'success': True,
            'models': models_list,
            'total': len(models_list)
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo modelos: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/models/current', methods=['GET'])
@login_required
def get_current_models():
    """
    Obtiene los modelos actuales (is_current=TRUE) de cada proveedor
    
    Returns:
        JSON con los modelos actuales por proveedor
        
    Example response:
        {
            "success": true,
            "models": {
                "openai": {"model_id": "gpt-5.5", "display_name": "GPT-5.5"},
                "anthropic": {"model_id": "claude-sonnet-5", "display_name": "Claude Sonnet 5"},
                "google": {"model_id": "gemini-3.6-flash", "display_name": "Gemini 3.6 Flash"},
                "perplexity": {"model_id": "sonar", "display_name": "Perplexity (Agent API)"}
            }
        }
    """
    fallbacks = MODEL_FALLBACKS
    
    conn = get_db_connection()
    if not conn:
        # Si no hay BD, devolver fallbacks
        return jsonify({
            'success': True,
            'models': fallbacks,
            'source': 'fallback'
        }), 200
    
    try:
        cur = conn.cursor()

        models_dict, from_db = fetch_current_models(cur)

        return jsonify({
            'success': True,
            'models': models_dict,
            'source': 'database' if from_db else 'fallback'
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo modelos actuales: {e}", exc_info=True)
        # En caso de error, devolver fallbacks
        return jsonify({
            'success': True,
            'models': fallbacks,
            'source': 'fallback_error'
        }), 200
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/models/<int:model_id>', methods=['PUT'])
@admin_required
def update_model(model_id):
    """
    Actualiza un modelo LLM (solo admin)
    
    Body:
    {
        "cost_per_1m_input_tokens": 15.0,
        "cost_per_1m_output_tokens": 45.0,
        "is_current": true,
        "is_available": true
    }
    
    Returns:
        JSON con el modelo actualizado
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is empty'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        updates = []
        params = []
        
        if 'cost_per_1m_input_tokens' in data:
            updates.append("cost_per_1m_input_tokens = %s")
            params.append(data['cost_per_1m_input_tokens'])
        
        if 'cost_per_1m_output_tokens' in data:
            updates.append("cost_per_1m_output_tokens = %s")
            params.append(data['cost_per_1m_output_tokens'])
        
        if 'is_current' in data:
            updates.append("is_current = %s")
            params.append(data['is_current'])
        
        if 'is_available' in data:
            updates.append("is_available = %s")
            params.append(data['is_available'])
        
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        
        updates.append("updated_at = NOW()")
        params.append(model_id)
        
        query = f"""
            UPDATE llm_model_registry
            SET {', '.join(updates)}
            WHERE id = %s
            RETURNING *
        """
        
        cur.execute(query, params)
        model = cur.fetchone()
        
        if not model:
            return jsonify({'error': 'Modelo no encontrado'}), 404
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'model': {
                'id': model['id'],
                'llm_provider': model['llm_provider'],
                'model_id': model['model_id'],
                'model_display_name': model['model_display_name'],
                'cost_per_1m_input_tokens': float(model['cost_per_1m_input_tokens']),
                'cost_per_1m_output_tokens': float(model['cost_per_1m_output_tokens']),
                'is_current': model['is_current'],
                'is_available': model['is_available'],
                'updated_at': model['updated_at'].isoformat() if model['updated_at'] else None
            }
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando modelo: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# CRON: Model Discovery v2 - Smart Chat-Only con Aprobación por Email
# ============================================================================

# Filtros para identificar modelos elegibles como "current".
#
# POLÍTICA (2026-08): monitorizamos el modelo de TEXTO que cada proveedor sirve
# GRATIS a su público general — lo que ve la mayoría de usuarios — nunca tiers
# de pago (Pro/Opus), variantes especializadas (codex, tts, live, lite,
# realtime...) ni snapshots con fecha (esos son alias de API, no lo que usa el
# público).
#   - OpenAI     → alias gpt-X.Y-chat-latest (el modelo de ChatGPT gratuito)
#   - Google     → familia Gemini Flash estable (sin lite/live/tts/preview)
#   - Anthropic  → Claude Sonnet (el modelo de claude.ai gratuito)
#   - Perplexity → sonar base
CHAT_MODEL_FILTERS = {
    'openai': {
        'include_patterns': ['chat-latest'],
        'exclude_patterns': [
            'pro', 'codex', 'mini', 'nano',              # tiers de pago / reducidos
            'o1', 'o3', 'o4',                            # reasoning
            'dall-e', 'gpt-image', 'whisper', 'tts',     # imagen / audio
            'audio', 'realtime', 'transcribe', 'diarize',
            'embedding', 'moderation', 'search',         # utilitarios
            'davinci', 'babbage', 'instruct',            # legacy
        ],
    },
    'google': {
        'include_patterns': ['gemini'],
        'require_patterns': ['gemini', 'flash'],
        'exclude_patterns': [
            'pro',                                        # tier de pago
            'lite', 'live', 'tts', 'image', 'thinking',   # variantes especializadas
            'preview', 'exp', 'customtools',              # inestables
            'embedding', 'imagen', 'veo', 'chirp',
            'codey', 'medlm', 'gemma', 'aqa',
        ],
    },
    'anthropic': {
        'include_patterns': ['claude-sonnet'],
        'exclude_patterns': ['opus', 'haiku', 'instant'],
    },
    'perplexity': {
        'include_patterns': ['sonar'],
        'exclude_patterns': ['pro', 'reasoning', 'deep-research'],
    },
}

# Pricing estimado por tier de modelo (input, output por 1M tokens)
DEFAULT_PRICING_BY_TIER = {
    'openai': {
        'gpt-5': (2.50, 10.00), 'gpt-4o': (2.50, 10.00), 'gpt-4.1': (2.00, 8.00),
    },
    'anthropic': {
        'claude-sonnet': (3.00, 15.00), 'claude-opus': (15.00, 75.00), 'claude-haiku': (0.25, 1.25),
    },
    # Claves genéricas por tier: 'gemini-3-flash' no matchea versiones con
    # punto (gemini-3.6-flash) y dejaba el pricing a NULL.
    'google': {
        'flash': (0.50, 3.00), 'pro': (1.25, 5.00),
    },
    'perplexity': {
        'sonar': (1.00, 1.00), 'sonar-pro': (3.00, 15.00),
    },
}


def is_chat_model(provider: str, model_id: str) -> bool:
    """
    Determina si un modelo es elegible como modelo "current" según la política
    de CHAT_MODEL_FILTERS (texto, tier gratuito, público general).
    """
    import re
    model_lower = model_id.lower()
    filters = CHAT_MODEL_FILTERS.get(provider, {})

    # Los snapshots con fecha (gpt-5.5-2026-04-23, claude-sonnet-4-5-20250929)
    # son alias de API congelados, no el modelo que sirve el proveedor al público.
    if re.search(r'\d{4}-\d{2}-\d{2}|\d{8}', model_lower):
        return False

    # Exclusiones primero (mayor prioridad)
    for pattern in filters.get('exclude_patterns', []):
        if pattern.lower() in model_lower:
            return False

    # Patrones que deben estar TODOS presentes (p.ej. google: gemini + flash)
    required = filters.get('require_patterns')
    if required and not all(p.lower() in model_lower for p in required):
        return False

    # Inclusiones (basta una)
    for pattern in filters.get('include_patterns', []):
        if pattern.lower() in model_lower:
            return True

    return False


def estimate_pricing_for_model(provider: str, model_id: str) -> tuple:
    """
    Estima pricing para un modelo nuevo basado en su tier/familia.
    Returns: (cost_per_1m_input, cost_per_1m_output) o (None, None) si no se puede estimar.
    """
    model_lower = model_id.lower()
    tier_pricing = DEFAULT_PRICING_BY_TIER.get(provider, {})

    # Buscar el tier más específico que coincida
    best_match = None
    best_match_len = 0
    for tier_key, pricing in tier_pricing.items():
        if tier_key.lower() in model_lower and len(tier_key) > best_match_len:
            best_match = pricing
            best_match_len = len(tier_key)

    return best_match if best_match else (None, None)


def validate_model_before_switch(provider: str, model_id: str) -> dict:
    """
    Ejecuta una query de prueba al modelo para verificar que funciona
    antes de activarlo como modelo actual.

    Returns: dict con 'success', 'response_length', 'error'
    """
    test_prompt = "What is SEO? Answer in one sentence."
    try:
        from services.llm_providers.provider_factory import LLMProviderFactory

        # create_provider exige la API key como posicional; se resuelve desde el
        # entorno con los mismos nombres que usa create_all_providers.
        env_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'anthropic': os.getenv('ANTHROPIC_API_KEY'),
            'google': os.getenv('GOOGLE_API_KEY') or os.getenv('GOOGLE_AI_API_KEY'),
            'perplexity': os.getenv('PERPLEXITY_API_KEY'),
        }
        api_key = env_keys.get(provider)
        if not api_key:
            return {'success': False, 'response_length': 0,
                    'error': f'No API key configured for provider {provider}'}

        provider_instance = LLMProviderFactory.create_provider(provider, api_key, model=model_id)
        if not provider_instance:
            return {'success': False, 'response_length': 0,
                    'error': f'Could not create provider for {provider}/{model_id}'}

        result = provider_instance.execute_query(test_prompt)
        # Los providers devuelven el texto en 'content' (BaseLLMProvider);
        # 'response' se mantiene como fallback defensivo.
        response_text = (result.get('content') or result.get('response') or '') if result else ''

        if result and not result.get('success', True):
            return {'success': False, 'response_length': len(response_text),
                    'error': str(result.get('error') or 'Provider reported failure')[:200]}

        if len(response_text) > 10:
            return {'success': True, 'response_length': len(response_text), 'error': None}
        else:
            return {'success': False, 'response_length': len(response_text), 'error': 'Response too short'}

    except Exception as e:
        logger.error(f"Pre-switch validation failed for {provider}/{model_id}: {e}")
        return {'success': False, 'response_length': 0, 'error': str(e)[:200]}


def _log_model_change(cur, provider, old_model_id, new_model_id, old_display, new_display,
                      change_type, changed_by, reason=None, metadata=None):
    """Registra un cambio de modelo en llm_model_changelog."""
    import json
    cur.execute("""
        INSERT INTO llm_model_changelog
            (llm_provider, old_model_id, new_model_id, old_display_name, new_display_name,
             change_type, changed_by, reason, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (provider, old_model_id, new_model_id, old_display, new_display,
          change_type, changed_by, reason, json.dumps(metadata or {})))


def get_model_version_score(model_id: str) -> tuple:
    """
    Calcula un score de versión para comparar modelos.
    Retorna una tupla (major_version, sub_version, date_score, model_id) para ordenar.

    Los números de versión se parsean del propio id — sin familias hardcodeadas —
    para que gemini-4-flash, gpt-6-chat-latest o claude-sonnet-5 puntúen
    correctamente el día que existan (con listas fijas puntuarían 0 y el
    discovery jamás los consideraría "más nuevos").
    """
    import re

    model_lower = model_id.lower()

    major = 0.0
    sub_version = 0
    version_match = re.search(r'(?:gpt|gemini)-(\d+)(?:\.(\d+))?', model_lower)
    if not version_match:
        version_match = re.search(r'claude-(?:sonnet|opus|haiku)-(\d+)(?:[.-](\d+))?', model_lower)
    if version_match:
        major = float(version_match.group(1))
        sub_version = int(version_match.group(2) or 0)
    elif 'sonar' in model_lower:
        # Perplexity no versiona sonar; el tier base puntúa 1 fijo.
        major = 1.0

    date_score = 0
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', model_id)
    if date_match:
        date_score = int(f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}")
    else:
        if 'preview' in model_lower or 'latest' in model_lower:
            date_score = 99999998
        else:
            date_score = 99999999

    return (major, sub_version, date_score, model_id)


def is_model_newer(new_model_id: str, current_model_id: str) -> bool:
    """Determina si new_model_id es más nuevo que current_model_id."""
    new_score = get_model_version_score(new_model_id)
    current_score = get_model_version_score(current_model_id)
    return (new_score[0], new_score[1], new_score[2]) > (current_score[0], current_score[1], current_score[2])


@llm_monitoring_bp.route('/cron/model-discovery', methods=['POST'])
@cron_or_auth_required
def cron_model_discovery():
    """
    Endpoint para CRON de descubrimiento de modelos LLM v2.

    Mejoras v2:
    - Filtra modelos NO-CHAT (reasoning, imagen, video, embedding, etc.)
    - Flujo de aprobación por email con tokens seguros
    - Validación pre-switch antes de activar un modelo
    - Estimación automática de pricing
    - Registro en llm_model_changelog

    Query params:
        - notify_email: Email para notificación (default: info@soycarlosgonzalez.com)
        - auto_update: true/false - Aprobar automáticamente (con validación pre-switch)
    """
    auth_error = _ensure_cron_token_or_admin()
    if auth_error:
        return auth_error

    import openai
    import google.generativeai as genai

    notify_email = _safe_notify_email(request.args.get('notify_email'))
    auto_update = request.args.get('auto_update', 'false').lower() == 'true'

    logger.info("=" * 60)
    logger.info("🔍 CRON: Smart Model Discovery v2...")
    logger.info(f"   Notify email: {notify_email}")
    logger.info(f"   Auto-update: {auto_update}")
    logger.info("=" * 60)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        # 1. Obtener modelos actuales de BD
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name, is_current,
                   is_available, pending_approval, approval_token_expires_at
            FROM llm_model_registry
            ORDER BY llm_provider, is_current DESC
        """)
        db_models = cur.fetchall()

        current_models = {}
        current_display_names = {}
        known_model_ids = set()
        # Un modelo conocido solo se salta si está rechazado (is_available=FALSE),
        # es el current, o tiene un token de aprobación aún vigente. Los demás
        # (token caducado, o pending perdido p.ej. por una validación fallida)
        # vuelven a ser candidatos: el ON CONFLICT del insert les regenera el
        # token y se re-ofertan en el email. Sin esto, un email no atendido a
        # tiempo enterraba el modelo para siempre.
        skip_model_ids = set()
        for m in db_models:
            known_model_ids.add(m['model_id'])
            if m['is_current']:
                current_models[m['llm_provider']] = m['model_id']
                current_display_names[m['llm_provider']] = m['model_display_name'] or m['model_id']
                skip_model_ids.add(m['model_id'])
            if m.get('is_available') is False:
                skip_model_ids.add(m['model_id'])
            token_alive = (m.get('pending_approval')
                           and m.get('approval_token_expires_at')
                           and m['approval_token_expires_at'] > datetime.now())
            if token_alive:
                skip_model_ids.add(m['model_id'])

        logger.info(f"📊 Modelos actuales en BD: {current_models}")

        # 2. Descubrir modelos de cada proveedor (SOLO CHAT)
        discovered_models = []
        newer_chat_models = []
        skipped_non_chat = []
        older_models = []
        same_or_known = []
        errors = []

        # --- OpenAI ---
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                client = openai.OpenAI(api_key=openai_key)
                models = client.models.list()
                current_openai = current_models.get('openai', 'gpt-5.4')

                for m in models.data:
                    discovered_models.append({'provider': 'openai', 'model_id': m.id})

                    if m.id in skip_model_ids:
                        same_or_known.append({'provider': 'openai', 'model_id': m.id})
                        continue

                    if not is_chat_model('openai', m.id):
                        skipped_non_chat.append({'provider': 'openai', 'model_id': m.id, 'reason': 'non-chat'})
                        continue

                    model_info = {'provider': 'openai', 'model_id': m.id, 'display_name': m.id}
                    if is_model_newer(m.id, current_openai):
                        model_info['status'] = 'NEWER'
                        newer_chat_models.append(model_info)
                    else:
                        older_models.append(model_info)

                logger.info(f"✅ OpenAI: Consultado correctamente")
        except Exception as e:
            errors.append(f"OpenAI: {str(e)[:100]}")
            logger.error(f"❌ OpenAI error: {e}")

        # --- Google ---
        try:
            google_key = os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GOOGLE_API_KEY')
            if google_key:
                genai.configure(api_key=google_key)
                models = genai.list_models()
                current_google = current_models.get('google', 'gemini-3-flash-preview')

                for m in models:
                    model_id = m.name.split('/')[-1] if '/' in m.name else m.name
                    display = getattr(m, 'display_name', model_id)
                    discovered_models.append({'provider': 'google', 'model_id': model_id})

                    if model_id in skip_model_ids:
                        same_or_known.append({'provider': 'google', 'model_id': model_id})
                        continue

                    if not is_chat_model('google', model_id):
                        skipped_non_chat.append({'provider': 'google', 'model_id': model_id, 'reason': 'non-chat'})
                        continue

                    model_info = {'provider': 'google', 'model_id': model_id, 'display_name': display}
                    if is_model_newer(model_id, current_google):
                        model_info['status'] = 'NEWER'
                        newer_chat_models.append(model_info)
                    else:
                        older_models.append(model_info)

                logger.info(f"✅ Google: Consultado correctamente")
        except Exception as e:
            errors.append(f"Google: {str(e)[:100]}")
            logger.error(f"❌ Google error: {e}")

        # --- Anthropic ---
        # Vía HTTP directa: el endpoint /v1/models no existe en el SDK 0.39.0
        # pineado en requirements, y así no dependemos de la versión del SDK.
        try:
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if anthropic_key:
                import requests as _requests
                current_anthropic = current_models.get('anthropic', 'claude-sonnet-4-6')
                resp = _requests.get(
                    'https://api.anthropic.com/v1/models?limit=100',
                    headers={'x-api-key': anthropic_key, 'anthropic-version': '2023-06-01'},
                    timeout=30,
                )
                resp.raise_for_status()

                for m in resp.json().get('data', []):
                    model_id = m.get('id', '')
                    if not model_id:
                        continue
                    display = m.get('display_name') or model_id
                    discovered_models.append({'provider': 'anthropic', 'model_id': model_id})

                    if model_id in skip_model_ids:
                        same_or_known.append({'provider': 'anthropic', 'model_id': model_id})
                        continue

                    if not is_chat_model('anthropic', model_id):
                        skipped_non_chat.append({'provider': 'anthropic', 'model_id': model_id, 'reason': 'non-chat'})
                        continue

                    model_info = {'provider': 'anthropic', 'model_id': model_id, 'display_name': display}
                    if is_model_newer(model_id, current_anthropic):
                        model_info['status'] = 'NEWER'
                        newer_chat_models.append(model_info)
                    else:
                        older_models.append(model_info)

                logger.info(f"✅ Anthropic: Consultado correctamente")
        except Exception as e:
            errors.append(f"Anthropic: {str(e)[:100]}")
            logger.error(f"❌ Anthropic error: {e}")

        # --- Perplexity (lista estática, solo chat) ---
        perplexity_models = ['sonar', 'sonar-pro']
        current_perplexity = current_models.get('perplexity', 'sonar')
        for model_id in perplexity_models:
            discovered_models.append({'provider': 'perplexity', 'model_id': model_id})
            if model_id not in skip_model_ids and is_chat_model('perplexity', model_id):
                model_info = {'provider': 'perplexity', 'model_id': model_id,
                              'display_name': f'Perplexity {model_id.replace("-", " ").title()}'}
                if is_model_newer(model_id, current_perplexity):
                    model_info['status'] = 'NEWER'
                    newer_chat_models.append(model_info)
                else:
                    older_models.append(model_info)

        logger.info(f"📊 Resultados: {len(newer_chat_models)} chat models nuevos, "
                    f"{len(skipped_non_chat)} no-chat descartados")

        # 3. Procesar modelos nuevos de chat
        models_added = []
        models_auto_approved = []
        approval_tokens_generated = []
        public_base_url = config.url_publica()

        for model in newer_chat_models:
            try:
                # Estimar pricing
                est_input, est_output = estimate_pricing_for_model(model['provider'], model['model_id'])

                # Generar token de aprobación
                approval_token = secrets.token_urlsafe(64)
                token_expires = datetime.now() + timedelta(days=7)

                if auto_update:
                    # Auto-update: validar y activar directamente
                    validation = validate_model_before_switch(model['provider'], model['model_id'])

                    if validation['success']:
                        # Insertar como current
                        cur.execute("""
                            INSERT INTO llm_model_registry
                                (llm_provider, model_id, model_display_name, is_current, is_available,
                                 model_category, cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                                 pre_switch_validated)
                            VALUES (%s, %s, %s, TRUE, TRUE, 'chat', %s, %s, TRUE)
                            ON CONFLICT (llm_provider, model_id) DO UPDATE SET
                                is_current = TRUE, pre_switch_validated = TRUE, updated_at = NOW()
                        """, (model['provider'], model['model_id'], model['display_name'],
                              est_input, est_output))

                        # Desactivar modelo anterior
                        cur.execute("""
                            UPDATE llm_model_registry SET is_current = FALSE, updated_at = NOW()
                            WHERE llm_provider = %s AND model_id != %s AND is_current = TRUE
                        """, (model['provider'], model['model_id']))

                        # Registrar en changelog
                        old_model = current_models.get(model['provider'])
                        old_display = current_display_names.get(model['provider'])
                        _log_model_change(cur, model['provider'], old_model, model['model_id'],
                                         old_display, model['display_name'], 'auto_approved', 'cron',
                                         'Auto-approved after successful validation',
                                         {'validation': validation, 'estimated_pricing': {'input': est_input, 'output': est_output}})

                        models_auto_approved.append(model)
                        models_added.append(model)
                        logger.info(f"   ✅ Auto-aprobado: {model['provider']} / {model['model_id']}")
                    else:
                        logger.warning(f"   ⚠️ Validación fallida para {model['model_id']}: {validation['error']}")
                        errors.append(f"Validation failed for {model['model_id']}: {validation['error']}")
                else:
                    # Insertar como pendiente de aprobación
                    cur.execute("""
                        INSERT INTO llm_model_registry
                            (llm_provider, model_id, model_display_name, is_current, is_available,
                             model_category, cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                             pending_approval, approval_token, approval_token_expires_at)
                        VALUES (%s, %s, %s, FALSE, TRUE, 'chat', %s, %s, TRUE, %s, %s)
                        ON CONFLICT (llm_provider, model_id) DO UPDATE SET
                            pending_approval = TRUE, approval_token = EXCLUDED.approval_token,
                            approval_token_expires_at = EXCLUDED.approval_token_expires_at,
                            updated_at = NOW()
                    """, (model['provider'], model['model_id'], model['display_name'],
                          est_input, est_output, approval_token, token_expires))

                    # Registrar en changelog como discovery
                    old_model = current_models.get(model['provider'])
                    old_display = current_display_names.get(model['provider'])
                    _log_model_change(cur, model['provider'], old_model, model['model_id'],
                                     old_display, model['display_name'], 'discovery', 'cron',
                                     'New chat model discovered, pending email approval')

                    model['approval_token'] = approval_token
                    model['estimated_pricing'] = {'input': est_input, 'output': est_output}
                    approval_tokens_generated.append(model)
                    models_added.append(model)
                    logger.info(f"   ⏳ Pendiente aprobación: {model['provider']} / {model['model_id']}")

            except Exception as e:
                logger.error(f"   ❌ Error procesando {model['model_id']}: {e}")
                errors.append(f"Processing {model['model_id']}: {str(e)[:100]}")

        conn.commit()

        # 4. Obtener estado final
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name
            FROM llm_model_registry
            WHERE is_current = TRUE
            ORDER BY llm_provider
        """)
        final_models = {row['llm_provider']: row['model_id'] for row in cur.fetchall()}

        # 5. Enviar email con botones de aprobación
        email_sent = False
        if notify_email:
            try:
                from email_service import send_email

                if newer_chat_models and not auto_update:
                    subject = f"🆕 {len(newer_chat_models)} nuevo(s) modelo(s) de Chat detectados - Aprobación requerida"
                elif models_auto_approved:
                    subject = f"✅ {len(models_auto_approved)} modelo(s) auto-aprobados y activados"
                else:
                    subject = "🤖 LLM Model Discovery - Todo actualizado ✅"

                html_body = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 650px; margin: 0 auto;">
                    <h1 style="color: #161616; border-bottom: 3px solid #D8F9B8; padding-bottom: 10px;">
                        🔍 LLM Model Discovery Report v2
                    </h1>
                    <p style="color: #666;">Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC</p>
                """

                # Modelos actuales
                html_body += """
                    <h2 style="color: #161616;">📊 Modelos Actuales</h2>
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                        <tr style="background: #161616; color: #D8F9B8;">
                            <th style="padding: 10px; text-align: left;">Proveedor</th>
                            <th style="padding: 10px; text-align: left;">Modelo Activo</th>
                        </tr>
                """
                for provider, mid in final_models.items():
                    html_body += f"""
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px;">{provider.upper()}</td>
                            <td style="padding: 10px;"><code>{mid}</code></td>
                        </tr>
                    """
                html_body += "</table>"

                # Modelos auto-aprobados
                if models_auto_approved:
                    html_body += f"""
                    <h2 style="color: #22c55e;">✅ Modelos Auto-Aprobados ({len(models_auto_approved)})</h2>
                    <p style="color: #666; font-size: 14px;">Validados y activados automáticamente:</p>
                    <ul style="background: #f0fdf4; padding: 15px 15px 15px 35px; border-radius: 8px; border-left: 4px solid #22c55e;">
                    """
                    for m in models_auto_approved:
                        html_body += f"<li><strong>{m['provider'].upper()}</strong>: <code>{m['model_id']}</code> ✅ Validación exitosa</li>"
                    html_body += "</ul>"

                # Modelos pendientes de aprobación (con botones)
                if approval_tokens_generated:
                    html_body += f"""
                    <h2 style="color: #f59e0b;">⏳ Modelos Pendientes de Aprobación ({len(approval_tokens_generated)})</h2>
                    <p style="color: #666; font-size: 14px;">Nuevos modelos de Chat detectados. Aprueba o rechaza cada uno:</p>
                    """
                    for m in approval_tokens_generated:
                        approve_url = f"{public_base_url}/api/llm-monitoring/models/approve?token={m['approval_token']}"
                        reject_url = f"{public_base_url}/api/llm-monitoring/models/reject?token={m['approval_token']}"
                        pricing_text = ""
                        if m.get('estimated_pricing', {}).get('input'):
                            pricing_text = f"Pricing estimado: ${m['estimated_pricing']['input']}/{m['estimated_pricing']['output']} por 1M tokens"

                        html_body += f"""
                        <div style="background: #fffbeb; padding: 20px; border-radius: 12px; border-left: 4px solid #f59e0b; margin-bottom: 16px;">
                            <h3 style="margin: 0 0 8px 0; color: #161616;">
                                {m['provider'].upper()}: <code>{m['model_id']}</code>
                            </h3>
                            <p style="color: #666; font-size: 13px; margin: 4px 0;">
                                Reemplazaría a: <code>{current_models.get(m['provider'], 'N/A')}</code>
                            </p>
                            <p style="color: #666; font-size: 13px; margin: 4px 0;">
                                Tipo: Chat | {pricing_text}
                            </p>
                            <p style="color: #92400e; font-size: 12px; margin: 4px 0;">
                                Token expira en 7 días
                            </p>
                            <div style="margin-top: 16px; display: flex; gap: 12px;">
                                <a href="{approve_url}" style="display: inline-block; background: #22c55e; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
                                    ✅ Aprobar y Activar
                                </a>
                                <a href="{reject_url}" style="display: inline-block; background: #ef4444; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
                                    ❌ Rechazar
                                </a>
                            </div>
                        </div>
                        """

                # No hay nuevos modelos
                if not newer_chat_models:
                    html_body += """
                    <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #22c55e;">
                        <p style="color: #166534; margin: 0; font-weight: 600;">
                            ✅ ¡Tu APP está usando los modelos de chat más recientes!
                        </p>
                    </div>
                    """

                # Non-chat models descartados
                if skipped_non_chat:
                    html_body += f"""
                    <details style="margin-top: 20px;">
                        <summary style="cursor: pointer; color: #666; font-size: 14px;">
                            🚫 {len(skipped_non_chat)} modelos no-chat descartados (reasoning, imagen, etc.)
                        </summary>
                        <ul style="background: #f9fafb; padding: 15px 15px 15px 35px; border-radius: 8px; color: #666; font-size: 13px; margin-top: 10px;">
                    """
                    for m in skipped_non_chat[:15]:
                        html_body += f"<li>{m['provider']}: {m['model_id']}</li>"
                    if len(skipped_non_chat) > 15:
                        html_body += f"<li>... y {len(skipped_non_chat) - 15} más</li>"
                    html_body += "</ul></details>"

                if errors:
                    html_body += f"""
                    <h3 style="color: #dc2626; margin-top: 20px;">⚠️ Errores</h3>
                    <ul style="color: #666; font-size: 14px;">
                    """
                    for err in errors:
                        html_body += f"<li>{err}</li>"
                    html_body += "</ul>"

                html_body += f"""
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                    <p style="color: #999; font-size: 12px; text-align: center;">
                        ClicAndSEO - LLM Visibility Monitor v2<br>
                        Smart Model Discovery con filtro de Chat y aprobación por email.<br>
                        <small>Total escaneados: {len(discovered_models)} | Chat nuevos: {len(newer_chat_models)} | No-chat descartados: {len(skipped_non_chat)}</small>
                    </p>
                </div>
                """

                send_email(notify_email, subject, html_body)
                email_sent = True
                logger.info(f"📧 Email enviado a {notify_email}")

            except Exception as e:
                logger.error(f"❌ Error enviando email: {e}")

        logger.info("=" * 60)
        logger.info(f"✅ Smart Discovery v2 completado")
        logger.info(f"   Modelos escaneados: {len(discovered_models)}")
        logger.info(f"   Nuevos modelos de Chat: {len(newer_chat_models)}")
        logger.info(f"   No-chat descartados: {len(skipped_non_chat)}")
        logger.info(f"   Auto-aprobados: {len(models_auto_approved)}")
        logger.info(f"   Pendientes aprobación: {len(approval_tokens_generated)}")
        logger.info("=" * 60)

        return jsonify({
            'success': True,
            'message': 'Smart Model Discovery v2 completed',
            'discovered_count': len(discovered_models),
            'newer_chat_models': [{'provider': m['provider'], 'model_id': m['model_id'], 'display_name': m.get('display_name')} for m in newer_chat_models],
            'skipped_non_chat_count': len(skipped_non_chat),
            'older_models_count': len(older_models),
            'models_added': [{'provider': m['provider'], 'model_id': m['model_id']} for m in models_added],
            'auto_approved': [{'provider': m['provider'], 'model_id': m['model_id']} for m in models_auto_approved],
            'pending_approval': len(approval_tokens_generated),
            'current_models': final_models,
            'email_sent': email_sent,
            'errors': errors,
            'summary': {
                'app_is_updated': len(newer_chat_models) == 0,
                'action_required': len(approval_tokens_generated) > 0
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en model discovery: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# Model Approval/Rejection Endpoints (clickable from email)
# ============================================================================

@llm_monitoring_bp.route('/models/approve', methods=['GET'])
def approve_model_by_token():
    """
    Aprueba y activa un modelo pendiente usando el token del email.
    Ejecuta validación pre-switch antes de activar.
    Devuelve HTML para que el admin vea el resultado en el navegador.
    """
    token = request.args.get('token', '')
    if not token or len(token) < 20:
        return _render_approval_result('error', 'Invalid or missing token.')

    conn = get_db_connection()
    if not conn:
        return _render_approval_result('error', 'Database connection error. Please try again.')

    try:
        cur = conn.cursor()

        # Buscar modelo con este token
        cur.execute("""
            SELECT id, llm_provider, model_id, model_display_name,
                   approval_token_expires_at, pending_approval
            FROM llm_model_registry
            WHERE approval_token = %s
        """, (token,))
        model = cur.fetchone()

        if not model:
            return _render_approval_result('error', 'Token not found. It may have expired or already been used.')

        if not model['pending_approval']:
            return _render_approval_result('info', f"Model {model['model_id']} has already been processed.")

        # Verificar expiración
        if model['approval_token_expires_at'] and datetime.now() > model['approval_token_expires_at']:
            return _render_approval_result('error',
                f"The approval token for {model['model_id']} has expired. "
                f"Run a new discovery to generate a fresh token.")

        # Validación pre-switch
        logger.info(f"🔄 Validando modelo antes de activar: {model['llm_provider']}/{model['model_id']}")
        validation = validate_model_before_switch(model['llm_provider'], model['model_id'])

        if not validation['success']:
            # Un fallo de validación puede ser transitorio (API caída, cuota,
            # bug nuestro). Mantener el modelo pendiente y su token para poder
            # reintentar desde el mismo email, y dejar rastro en el changelog.
            cur.execute("""
                UPDATE llm_model_registry
                SET pre_switch_validated = FALSE, updated_at = NOW()
                WHERE id = %s
            """, (model['id'],))
            _log_model_change(
                cur, model['llm_provider'], None, model['model_id'],
                None, model['model_display_name'],
                'validation_failed', 'admin:email',
                f"Pre-switch validation failed: {validation['error']}",
                {'validation': validation}
            )
            conn.commit()

            return _render_approval_result('error',
                f"Pre-switch validation failed for {model['model_id']}. "
                f"Error: {validation['error']}. The model has NOT been activated. "
                f"The approval link remains valid — you can retry once the issue is fixed.")

        # Obtener modelo actual antes de desactivar
        cur.execute("""
            SELECT model_id, model_display_name
            FROM llm_model_registry
            WHERE llm_provider = %s AND is_current = TRUE
        """, (model['llm_provider'],))
        old_model = cur.fetchone()

        # Desactivar modelos anteriores del mismo provider
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = FALSE, updated_at = NOW()
            WHERE llm_provider = %s AND is_current = TRUE
        """, (model['llm_provider'],))

        # Activar nuevo modelo
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = TRUE, pending_approval = FALSE, approval_token = NULL,
                approval_token_expires_at = NULL, pre_switch_validated = TRUE,
                updated_at = NOW()
            WHERE id = %s
        """, (model['id'],))

        # Registrar en changelog
        _log_model_change(
            cur, model['llm_provider'],
            old_model['model_id'] if old_model else None,
            model['model_id'],
            old_model['model_display_name'] if old_model else None,
            model['model_display_name'],
            'email_approved', 'admin:email',
            'Approved via email link after successful pre-switch validation',
            {'validation': validation}
        )

        conn.commit()

        logger.info(f"✅ Modelo aprobado y activado: {model['llm_provider']}/{model['model_id']}")

        # Enviar email de confirmación
        try:
            from email_service import send_email
            notify_email = config.email_modelo_activado()
            old_name = old_model['model_id'] if old_model else 'N/A'
            send_email(notify_email,
                      f"✅ Modelo activado: {model['llm_provider'].upper()} → {model['model_id']}",
                      f"""
                      <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
                          <h2 style="color: #22c55e;">✅ Modelo Activado Exitosamente</h2>
                          <p><strong>Proveedor:</strong> {model['llm_provider'].upper()}</p>
                          <p><strong>Nuevo modelo:</strong> <code>{model['model_id']}</code></p>
                          <p><strong>Modelo anterior:</strong> <code>{old_name}</code></p>
                          <p><strong>Validación pre-switch:</strong> ✅ Exitosa</p>
                          <p style="color: #666; font-size: 13px;">
                              El modal de modelos en la APP se actualizará automáticamente.
                          </p>
                      </div>
                      """)
        except Exception as e:
            logger.error(f"Error enviando email de confirmación: {e}")

        return _render_approval_result('success',
            f"Model {model['model_display_name'] or model['model_id']} approved and activated successfully "
            f"for {model['llm_provider'].upper()}. "
            f"Pre-switch validation: passed.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error aprobando modelo: {e}", exc_info=True)
        return _render_approval_result('error', 'Internal error — revisa los logs del servidor')
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/models/reject', methods=['GET'])
def reject_model_by_token():
    """
    Rechaza un modelo pendiente usando el token del email.
    Devuelve HTML para el navegador.
    """
    token = request.args.get('token', '')
    if not token or len(token) < 20:
        return _render_approval_result('error', 'Invalid token.')

    conn = get_db_connection()
    if not conn:
        return _render_approval_result('error', 'Database connection error. Please try again.')

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, llm_provider, model_id, model_display_name, pending_approval
            FROM llm_model_registry
            WHERE approval_token = %s
        """, (token,))
        model = cur.fetchone()

        if not model:
            return _render_approval_result('error', 'Token not found.')

        if not model['pending_approval']:
            return _render_approval_result('info', f"Model {model['model_id']} has already been processed.")

        # Rechazar: limpiar token y desactivar approval
        cur.execute("""
            UPDATE llm_model_registry
            SET pending_approval = FALSE, approval_token = NULL,
                approval_token_expires_at = NULL, is_available = FALSE,
                updated_at = NOW()
            WHERE id = %s
        """, (model['id'],))

        # Registrar en changelog
        _log_model_change(
            cur, model['llm_provider'], None, model['model_id'],
            None, model['model_display_name'],
            'rejected', 'admin:email',
            'Rejected via email link'
        )

        conn.commit()
        logger.info(f"❌ Modelo rechazado: {model['llm_provider']}/{model['model_id']}")

        return _render_approval_result('rejected',
            f"Model {model['model_display_name'] or model['model_id']} rejected for "
            f"{model['llm_provider'].upper()}. No changes were made.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error rechazando modelo: {e}", exc_info=True)
        return _render_approval_result('error', 'Internal error — revisa los logs del servidor')
    finally:
        cur.close()
        conn.close()


def _render_approval_result(status: str, message: str) -> str:
    """Renderiza una página HTML simple con el resultado de la aprobación/rechazo."""
    colors = {
        'success': ('#22c55e', '#f0fdf4', '✅'),
        'error': ('#ef4444', '#fef2f2', '❌'),
        'rejected': ('#f59e0b', '#fffbeb', '🚫'),
        'info': ('#3b82f6', '#eff6ff', 'ℹ️'),
    }
    color, bg, icon = colors.get(status, colors['info'])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Model {status.title()} - ClicAndSEO</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                 display: flex; justify-content: center; align-items: center;
                 min-height: 100vh; margin: 0; background: #f9fafb;">
        <div style="max-width: 500px; background: white; border-radius: 16px; padding: 40px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1); text-align: center;">
            <div style="font-size: 48px; margin-bottom: 16px;">{icon}</div>
            <h1 style="color: {color}; margin: 0 0 16px 0; font-size: 24px;">
                Model {status.replace('_', ' ').title()}
            </h1>
            <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                {message}
            </p>
            <div style="padding: 16px; background: {bg}; border-radius: 8px; border-left: 4px solid {color};">
                <p style="color: #666; font-size: 13px; margin: 0;">
                    Puedes cerrar esta pestaña. Los cambios ya se han aplicado.
                </p>
            </div>
            <p style="color: #999; font-size: 12px; margin-top: 24px;">
                ClicAndSEO - LLM Visibility Monitor
            </p>
        </div>
    </body>
    </html>
    """
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


# ============================================================================
# Model Changelog Endpoint
# ============================================================================

@llm_monitoring_bp.route('/models/changelog', methods=['GET'])
@login_required
def get_model_changelog():
    """
    Obtiene el historial de cambios de modelos.

    Query params:
        - limit: número máximo de entradas (default 50, max 200)
        - provider: filtrar por proveedor (opcional)
    """
    limit = min(int(request.args.get('limit', 50)), 200)
    provider = request.args.get('provider')

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        query = """
            SELECT id, llm_provider, old_model_id, new_model_id,
                   old_display_name, new_display_name, change_type,
                   changed_by, reason, metadata, created_at
            FROM llm_model_changelog
        """
        params = []
        if provider:
            query += " WHERE llm_provider = %s"
            params.append(provider)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()

        changelog = []
        for row in rows:
            entry = {
                'id': row['id'],
                'llm_provider': row['llm_provider'],
                'old_model_id': row['old_model_id'],
                'new_model_id': row['new_model_id'],
                'old_display_name': row['old_display_name'],
                'new_display_name': row['new_display_name'],
                'change_type': row['change_type'],
                'changed_by': row['changed_by'],
                'reason': row['reason'],
                'metadata': row['metadata'] if row['metadata'] else {},
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            }
            changelog.append(entry)

        return jsonify({
            'success': True,
            'changelog': changelog,
            'count': len(changelog)
        }), 200

    except Exception as e:
        logger.error(f"Error obteniendo changelog: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()
