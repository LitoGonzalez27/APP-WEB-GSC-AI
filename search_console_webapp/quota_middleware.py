#!/usr/bin/env python3
"""
QUOTA MIDDLEWARE - FASE 4
========================

Middleware central para controlar todas las llamadas a SerpAPI.
Implementa el patrón 'reserva y confirmación' para evitar sobreconsumo.

Flujo:
1. Pre-check: Validar quota disponible antes de la llamada
2. Reserve: Reservar RU temporalmente
3. Execute: Ejecutar llamada SerpAPI  
4. Confirm: Confirmar consumo RU o devolver reserva si falla
"""

import os
import logging
import time
import hashlib
from collections import OrderedDict
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from flask import g, session
from serpapi import GoogleSearch
from quota_manager import (
    get_user_quota_status, 
    can_user_consume_ru, 
    get_user_access_permissions
)
from database import track_quota_consumption

logger = logging.getLogger(__name__)

# Cache para detectar si una llamada es repetida (mismos parámetros) - LRU + TTL
CALL_CACHE = OrderedDict()
CACHE_DURATION = int(os.getenv('SERP_CALL_CACHE_TTL_SECONDS', '3600'))  # 1 hora
CALL_CACHE_MAX = int(os.getenv('SERP_CALL_CACHE_MAX', '5000'))

def _get_cache_key(params: dict) -> str:
    """Genera una clave de caché única para los parámetros SERP"""
    # Excluir api_key del cache key por seguridad
    cache_params = {k: v for k, v in params.items() if k != 'api_key'}
    cache_string = str(sorted(cache_params.items()))
    return hashlib.md5(cache_string.encode()).hexdigest()

def _is_cached_call(params: dict) -> bool:
    """Verifica si esta llamada ya está en caché (no consume RU)"""
    cache_key = _get_cache_key(params)
    now = time.time()
    
    if cache_key in CALL_CACHE:
        cached_time = CALL_CACHE[cache_key]
        if now - cached_time < CACHE_DURATION:
            logger.info(f"🔄 CACHE HIT: Llamada SerpAPI en caché (0 RU)")
            CALL_CACHE.move_to_end(cache_key)
            return True
        # Cache expirado, eliminar entrada
        CALL_CACHE.pop(cache_key, None)
    
    return False

def _mark_call_cached(params: dict):
    """Marca una llamada como cacheada"""
    cache_key = _get_cache_key(params)
    CALL_CACHE[cache_key] = time.time()
    CALL_CACHE.move_to_end(cache_key)
    while CALL_CACHE_MAX > 0 and len(CALL_CACHE) > CALL_CACHE_MAX:
        CALL_CACHE.popitem(last=False)

def _should_retry_serp_error(error_message: str) -> bool:
    if not error_message:
        return False
    msg = error_message.lower()
    if "invalid api key" in msg or "invalid api_key" in msg:
        return False
    transient_markers = [
        "timeout",
        "temporarily",
        "rate limit",
        "too many requests",
        "429",
        "502",
        "503",
        "504",
        "connection",
        "network",
        "reset",
        "unavailable",
    ]
    return any(marker in msg for marker in transient_markers)

def get_current_user_id() -> Optional[int]:
    """Obtiene el ID del usuario actual desde la sesión Flask"""
    try:
        # Intentar obtener desde Flask g (si está disponible)
        if hasattr(g, 'user_id'):
            return g.user_id
        
        # Intentar obtener desde la sesión
        if 'user_id' in session:
            return session['user_id']
        
        # Si no hay usuario autenticado
        logger.warning("No se pudo obtener user_id - usuario no autenticado")
        return None
        
    except Exception as e:
        logger.error(f"Error obteniendo user_id: {e}")
        return None

def validate_quota_access(user_id: int, operation_type: str = "serp_call") -> Dict[str, Any]:
    """
    Valida si el usuario puede realizar una operación que consume RU
    
    Returns:
        dict: {
            'allowed': bool,
            'reason': str,
            'quota_info': dict,
            'action_required': str  # 'upgrade', 'contact_support', 'wait'
        }
    """
    try:
        # Obtener permisos de acceso del usuario
        permissions = get_user_access_permissions(user_id)
        quota_status = permissions['quota_status']
        plan = quota_status.get('plan', 'unknown')

        # Ramas por tipo de operación
        is_serp = str(operation_type).startswith('serp_')

        if is_serp:
            # Política: SERP está permitido para plan Free (no consume RU),
            # y para planes de pago si tienen RU disponible
            if plan == 'free':
                return {
                    'allowed': True,
                    'reason': 'Plan Free: SERP permitido (sin consumo de RU)',
                    'quota_info': quota_status,
                    'action_required': None
                }

            # Para planes de pago, verificar RU disponible
            can_consume_bool = can_user_consume_ru(user_id, 1)
            if not can_consume_bool:
                # Diferenciar mensaje de agotamiento
                if quota_status['quota_limit'] is not None and quota_status['quota_used'] >= quota_status['quota_limit']:
                    return {
                        'allowed': False,
                        'reason': f'Cuota agotada ({quota_status["quota_used"]}/{quota_status["quota_limit"]} RU)',
                        'quota_info': quota_status,
                        'action_required': 'upgrade' if quota_status['plan'] != 'enterprise' else 'contact_support'
                    }
                return {
                    'allowed': False,
                    'reason': 'No hay cuota suficiente',
                    'quota_info': quota_status,
                    'action_required': 'contact_support'
                }

            return {
                'allowed': True,
                'reason': 'Quota disponible',
                'quota_info': quota_status,
                'action_required': None
            }

        # Para módulos de IA, requerir permisos explícitos
        if not permissions['can_use_ai_overview'] and not permissions['can_use_manual_ai']:
            return {
                'allowed': False,
                'reason': 'Plan actual no tiene acceso a módulos de IA',
                'quota_info': quota_status,
                'action_required': 'upgrade'
            }

        # Verificar RU para módulos de IA
        can_consume_bool = can_user_consume_ru(user_id, 1)
        if not can_consume_bool:
            if quota_status['quota_limit'] is not None and quota_status['quota_used'] >= quota_status['quota_limit']:
                return {
                    'allowed': False,
                    'reason': f'Cuota agotada ({quota_status["quota_used"]}/{quota_status["quota_limit"]} RU)',
                    'quota_info': quota_status,
                    'action_required': 'upgrade' if quota_status['plan'] != 'enterprise' else 'contact_support'
                }
            return {
                'allowed': False,
                'reason': 'No hay cuota suficiente',
                'quota_info': quota_status,
                'action_required': 'contact_support'
            }

        return {
            'allowed': True,
            'reason': 'Quota disponible',
            'quota_info': quota_status,
            'action_required': None
        }
        
    except Exception as e:
        logger.error(f"Error validando acceso quota para user {user_id}: {e}")
        return {
            'allowed': False,
            'reason': f'Error de sistema: {str(e)}',
            'quota_info': {},
            'action_required': 'contact_support'
        }

def quota_protected_serp_call(params: dict, call_type: str = "json") -> Tuple[bool, Dict[str, Any]]:
    """
    Ejecuta una llamada SerpAPI protegida por quotas usando patrón reserva/confirmación.
    
    Args:
        params: Parámetros para la llamada SerpAPI
        call_type: 'json', 'html', o 'screenshot'
        
    Returns:
        Tuple[bool, dict]: (success, data_or_error)
    """
    
    # ✅ FEATURE FLAG: Verificar si enforcement está activado
    enforce_quotas = os.getenv('ENFORCE_QUOTAS', 'false').lower() == 'true'
    
    if not enforce_quotas:
        logger.info("🔓 ENFORCE_QUOTAS=false - Ejecutando sin control de quotas")
        return _execute_serp_call(params, call_type)
    
    logger.info(f"🔒 ENFORCE_QUOTAS=true - Validando quotas para llamada {call_type}")
    
    # 🔍 PASO 1: Obtener usuario actual
    user_id = get_current_user_id()
    if not user_id:
        logger.warning("Llamada SerpAPI sin usuario autenticado - permitiendo (modo desarrollo)")
        return _execute_serp_call(params, call_type)
    
    # 🔍 PASO 2: Verificar si es llamada cacheada (0 RU)
    if _is_cached_call(params):
        logger.info(f"📦 Ejecutando llamada cacheada para user {user_id} (0 RU)")
        success, result = _execute_serp_call(params, call_type)
        return success, result
    
    # 🔍 PASO 3: Validar acceso y quota
    quota_validation = validate_quota_access(user_id, f"serp_{call_type}")
    
    if not quota_validation['allowed']:
        logger.warning(f"🚫 Quota bloqueada para user {user_id}: {quota_validation['reason']}")
        return False, {
            'error': 'Quota exceeded',
            'message': quota_validation['reason'],
            'quota_info': quota_validation['quota_info'],
            'action_required': quota_validation['action_required'],
            'blocked': True
        }
    
    # 🔍 PASO 4: Ejecutar llamada SerpAPI (ya validada)
    logger.info(f"✅ Ejecutando llamada SerpAPI para user {user_id} (1 RU)")
    
    success, result = _execute_serp_call(params, call_type)
    
    # 🔍 PASO 5: Registrar consumo si fue exitosa
    if success:
        try:
            status = get_user_quota_status(user_id)
            update_user_quota = enforce_quotas and status.get('plan') != 'free'
            track_quota_consumption(
                user_id=user_id,
                ru_consumed=1,
                source='serp_api',
                keyword=params.get('q', 'unknown'),
                country_code=params.get('gl', 'unknown'),
                metadata={
                    'call_type': call_type,
                    'cached': False
                },
                update_user_quota=update_user_quota
            )
            if update_user_quota:
                logger.info(f"📊 RU registrado: user {user_id} consumió 1 RU ({call_type})")
            else:
                logger.info("🧾 SERP registrado sin afectar RU (tracking-only)")

            # Marcar en caché para futuras llamadas
            _mark_call_cached(params)
            
        except Exception as e:
            logger.error(f"Error registrando consumo RU/caché para user {user_id}: {e}")
    
    return success, result

def _execute_serp_call(params: dict, call_type: str) -> Tuple[bool, Dict[str, Any]]:
    """Ejecuta la llamada real a SerpAPI"""
    max_attempts = int(os.getenv('SERPAPI_RETRY_ATTEMPTS', '3'))
    base_delay = float(os.getenv('SERPAPI_RETRY_BACKOFF_SECONDS', '1.0'))
    
    for attempt in range(1, max_attempts + 1):
        try:
            if call_type == "json":
                data = GoogleSearch(params).get_dict()
                if "error" in data:
                    error_msg = str(data.get("error", ""))
                    logger.warning(f"SerpAPI error: {error_msg}")
                    if attempt < max_attempts and _should_retry_serp_error(error_msg):
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.info(f"⏳ Reintentando SerpAPI JSON en {delay:.1f}s (intento {attempt}/{max_attempts})")
                        time.sleep(delay)
                        continue
                    return False, data
                return True, data
                
            if call_type == "html":
                html_content = GoogleSearch({**params, 'output': 'html'}).get_html()
                if not html_content:
                    error_msg = "No HTML content returned"
                    if attempt < max_attempts and _should_retry_serp_error(error_msg):
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.info(f"⏳ Reintentando SerpAPI HTML en {delay:.1f}s (intento {attempt}/{max_attempts})")
                        time.sleep(delay)
                        continue
                    return False, {"error": error_msg}
                if isinstance(html_content, dict) and "error" in html_content:
                    error_msg = str(html_content.get("error", ""))
                    if attempt < max_attempts and _should_retry_serp_error(error_msg):
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.info(f"⏳ Reintentando SerpAPI HTML en {delay:.1f}s (intento {attempt}/{max_attempts})")
                        time.sleep(delay)
                        continue
                    return False, html_content
                return True, {"html": html_content}
                
            return False, {"error": f"Unsupported call type: {call_type}"}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error en llamada SerpAPI ({call_type}): {error_msg}")
            if attempt < max_attempts and _should_retry_serp_error(error_msg):
                delay = base_delay * (2 ** (attempt - 1))
                logger.info(f"⏳ Reintentando SerpAPI ({call_type}) en {delay:.1f}s (intento {attempt}/{max_attempts})")
                time.sleep(delay)
                continue
            return False, {"error": error_msg}

def get_quota_warning_info(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene información de advertencia si el usuario está cerca del límite de quota
    
    Returns:
        dict o None: Información de advertencia si aplica
    """
    try:
        quota_status = get_user_quota_status(user_id)
        
        if quota_status['quota_limit'] == 0:
            return None  # Plan Free o Enterprise sin límite
        
        usage_percentage = (quota_status['quota_used'] / quota_status['quota_limit']) * 100
        
        # Soft limit al 80%
        if usage_percentage >= 80:
            remaining_ru = quota_status['quota_limit'] - quota_status['quota_used']
            
            return {
                'type': 'warning' if usage_percentage < 100 else 'danger',
                'percentage': round(usage_percentage, 1),
                'remaining_ru': remaining_ru,
                'quota_limit': quota_status['quota_limit'],
                'quota_used': quota_status['quota_used'],
                'plan': quota_status['plan'],
                'message': (
                    f"Has usado {usage_percentage:.0f}% de tu cuota mensual ({remaining_ru} RU restantes)"
                    if usage_percentage < 100
                    else f"Has alcanzado tu límite mensual de {quota_status['quota_limit']} RU"
                )
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error obteniendo info de advertencia quota para user {user_id}: {e}")
        return None
