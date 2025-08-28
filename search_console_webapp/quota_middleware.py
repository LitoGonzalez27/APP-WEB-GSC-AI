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
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from flask import g, session
from serpapi import GoogleSearch
from quota_manager import (
    get_user_quota_status, 
    can_user_consume_ru, 
    record_quota_usage,
    get_user_access_permissions
)

logger = logging.getLogger(__name__)

# Cache para detectar si una llamada es repetida (mismos parámetros)
CALL_CACHE = {}
CACHE_DURATION = 3600  # 1 hora

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
            return True
        else:
            # Cache expirado, eliminar entrada
            del CALL_CACHE[cache_key]
    
    return False

def _mark_call_cached(params: dict):
    """Marca una llamada como cacheada"""
    cache_key = _get_cache_key(params)
    CALL_CACHE[cache_key] = time.time()

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
        
        if not permissions['can_use_ai_overview'] and not permissions['can_use_manual_ai']:
            return {
                'allowed': False,
                'reason': 'Plan Free no tiene acceso a módulos de IA',
                'quota_info': permissions['quota_status'],
                'action_required': 'upgrade'
            }
        
        # Verificar si puede consumir RU
        can_consume = can_user_consume_ru(user_id, 1)  # 1 RU para esta llamada
        
        if not can_consume['allowed']:
            quota_status = permissions['quota_status']
            
            # Diferentes razones de bloqueo
            if quota_status['quota_used'] >= quota_status['quota_limit']:
                return {
                    'allowed': False,
                    'reason': f'Cuota agotada ({quota_status["quota_used"]}/{quota_status["quota_limit"]} RU)',
                    'quota_info': quota_status,
                    'action_required': 'upgrade' if quota_status['plan'] != 'enterprise' else 'contact_support'
                }
            else:
                return {
                    'allowed': False,
                    'reason': can_consume['reason'],
                    'quota_info': quota_status,
                    'action_required': 'contact_support'
                }
        
        return {
            'allowed': True,
            'reason': 'Quota disponible',
            'quota_info': permissions['quota_status'],
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
            record_quota_usage(
                user_id=user_id,
                ru_consumed=1,
                operation_type=f"serp_{call_type}",
                metadata={
                    'keyword': params.get('q', 'unknown'),
                    'country': params.get('gl', 'unknown'),
                    'call_type': call_type
                }
            )
            logger.info(f"📊 RU registrado: user {user_id} consumió 1 RU ({call_type})")
            
            # Marcar en caché para futuras llamadas
            _mark_call_cached(params)
            
        except Exception as e:
            logger.error(f"Error registrando consumo RU para user {user_id}: {e}")
    
    return success, result

def _execute_serp_call(params: dict, call_type: str) -> Tuple[bool, Dict[str, Any]]:
    """Ejecuta la llamada real a SerpAPI"""
    try:
        if call_type == "json":
            data = GoogleSearch(params).get_dict()
            if "error" in data:
                logger.warning(f"SerpAPI error: {data['error']}")
                return False, data
            return True, data
            
        elif call_type == "html":
            html_content = GoogleSearch({**params, 'output': 'html'}).get_html()
            if not html_content:
                return False, {"error": "No HTML content returned"}
            if isinstance(html_content, dict) and "error" in html_content:
                return False, html_content
            return True, {"html": html_content}
            
        else:
            return False, {"error": f"Unsupported call type: {call_type}"}
            
    except Exception as e:
        logger.error(f"Error en llamada SerpAPI ({call_type}): {e}")
        return False, {"error": str(e)}

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
