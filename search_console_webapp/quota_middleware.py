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
import config
import logging
import time
import hashlib
import threading
from collections import OrderedDict
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from flask import g, session, has_request_context
from serpapi import GoogleSearch
from quota_manager import (
    get_user_quota_status, 
    can_user_consume_ru, 
    get_user_access_permissions
)
from database import track_quota_consumption

logger = logging.getLogger(__name__)

# Detección de entorno desplegado (para gates de seguridad).
_IS_DEPLOYED = config.desplegado()

# Cache para detectar si una llamada es repetida (mismos parámetros) - LRU + TTL
CALL_CACHE = OrderedDict()
# La escriben a la vez las rutas y los hilos de los análisis (pool de AI Overview).
_CALL_CACHE_LOCK = threading.Lock()
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

    with _CALL_CACHE_LOCK:
        cached_time = CALL_CACHE.get(cache_key)
        if cached_time is not None:
            if now - cached_time < CACHE_DURATION:
                logger.info(f"🔄 CACHE HIT: Llamada SerpAPI en caché (0 RU)")
                CALL_CACHE.move_to_end(cache_key)
                return True
            # Cache expirado, eliminar entrada
            CALL_CACHE.pop(cache_key, None)

    return False

# Candados por búsqueda (repartidos en franjas fijas): dos peticiones iguales a la
# vez (doble clic en el icono de SERP) no cobran dos veces; la segunda espera y
# sale de la caché.
_CANDADOS = [threading.Lock() for _ in range(256)]


def _candado_de(params: dict) -> threading.Lock:
    return _CANDADOS[int(_get_cache_key(params), 16) % len(_CANDADOS)]


def _mark_call_cached(params: dict):
    """Marca una llamada como cacheada"""
    cache_key = _get_cache_key(params)
    with _CALL_CACHE_LOCK:
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
            # Política (Carlos, 30-sep-2026): la vista de SERP es de pago; el
            # plan Free queda bloqueado. Los planes de pago necesitan RU disponible.
            if plan == 'free':
                return {
                    'allowed': False,
                    'reason': 'Plan Free: la vista de SERP es de pago',
                    'quota_info': quota_status,
                    'action_required': 'upgrade'
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
            'reason': 'Error de sistema',  # el detalle, solo en el log
            'quota_info': {},
            'action_required': 'contact_support'
        }

OPCIONES_DE_PLAN = ['basic', 'premium', 'business']


def _usuario(user_id: int) -> Optional[Dict[str, Any]]:
    """Usuario (plan y rol): el leído al empezar la petición si es el de la
    sesión (sin volver a la BD); si no, de la BD. None si no se puede leer."""
    try:
        from auth import get_current_user
        from database import get_user_by_id
        usuario = None
        if has_request_context() and session.get('user_id') == user_id:
            usuario = get_current_user()
        return usuario if usuario is not None else get_user_by_id(user_id)
    except Exception as e:
        logger.error(f"No se pudo leer el usuario {user_id}: {e}")
        return None


def _es_admin(user_id: int) -> bool:
    usuario = _usuario(user_id)
    return bool(usuario) and usuario.get('role') == 'admin'


def bloqueo_serp_por_plan(user_id: int) -> Optional[Dict[str, Any]]:
    """La vista de SERP es de pago (Carlos, 30-sep-2026): devuelve el cuerpo del
    bloqueo para un usuario del plan Free (salvo admin), o None si puede usarla.
    El plan sale del registro del usuario, no del estado de cuota (que ante un
    fallo parcial de la BD devuelve plan 'unknown' y dejaría pasar)."""
    usuario = _usuario(user_id)
    if usuario is not None:
        if usuario.get('role') == 'admin':
            return None
        plan = usuario.get('plan')
    else:
        plan = get_user_quota_status(user_id).get('plan')
    if plan != 'free':
        return None
    return {
        'error': 'paywall',
        'message': 'SERP view is available on paid plans.',
        'blocked': True,
        'paywall': True,
        'upgrade_options': OPCIONES_DE_PLAN,
        'quota_info': {'plan': 'free'},
        'action_required': 'upgrade',
    }


def quota_protected_serp_call(params: dict, call_type: str = "json", cobrar: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """
    Ejecuta una llamada a SerpAPI.

    cobrar=False (por defecto): la hace un proceso que ya cuenta su propio consumo
    (análisis de AI Overview, Manual AI) o que no tiene usuario (crons): se ejecuta
    sin comprobar ni descontar RU.
    cobrar=True: búsquedas que pide el usuario desde los botones de SERP
    (/api/serp, /api/serp/position, /api/serp/screenshot):
      - plan Free (salvo admin): bloqueado, con paywall;
      - búsqueda repetida en la última hora: sin coste (SerpAPI tampoco la cobra);
      - admin: se ejecuta y se registra el evento sin descontar RU;
      - resto: comprueba la cuota, ejecuta y descuenta 1 RU.

    Antes (hasta sep-2026) todo dependía de ENFORCE_QUOTAS: encendido, los
    análisis cobraban dos veces (el análisis y además cada búsqueda); apagado,
    como estaba en producción, los botones de SERP no cobraban nada y los usaba
    también el plan Free.

    Returns:
        Tuple[bool, dict]: (success, data_or_error)
    """

    # 🔒 SEGURIDAD: en entornos desplegados nunca se ejecuta una llamada SerpAPI a
    # partir de una petición HTTP sin usuario autenticado. Esto evita el abuso
    # anónimo de la SERPAPI_KEY de pago. Los procesos server-side (crons/scripts)
    # no tienen contexto de request y sí pueden ejecutar la llamada.
    if _IS_DEPLOYED and has_request_context() and not get_current_user_id():
        logger.warning("🚫 Llamada SerpAPI bloqueada: petición HTTP sin usuario autenticado")
        return False, {
            'error': 'Authentication required',
            'message': 'Debes iniciar sesión para realizar esta operación.',
            'blocked': True
        }

    if not cobrar:
        success, result = _execute_serp_call(params, call_type)
        # La misma búsqueda pedida después desde el modal sale de la caché de
        # SerpAPI: tampoco se le cobra al usuario (AI Overview). Manual AI busca
        # con no_cache y nunca coincide con el modal: no se guarda.
        if success and not params.get('no_cache'):
            try:
                _mark_call_cached(params)
            except Exception as e:
                logger.error(f"No se pudo guardar la búsqueda en la caché: {e}")
        return success, result

    user_id = get_current_user_id()
    if not user_id:
        # Solo fuera de Railway (desarrollo) o sin petición: no hay a quién cobrar.
        logger.info("Llamada SerpAPI sin usuario (contexto server-side/desarrollo) - permitiendo sin cuota")
        return _execute_serp_call(params, call_type)

    bloqueo = bloqueo_serp_por_plan(user_id)
    if bloqueo:
        logger.info(f"🚫 SERP bloqueada para user {user_id}: plan Free")
        return False, bloqueo

    with _candado_de(params):
        return _serp_cobrada(params, call_type, user_id)


def _serp_cobrada(params: dict, call_type: str, user_id: int) -> Tuple[bool, Dict[str, Any]]:
    """Parte de quota_protected_serp_call que cobra; se ejecuta con el candado de la búsqueda."""
    # Búsqueda repetida en la última hora: SerpAPI la sirve de su caché sin cobrar.
    if _is_cached_call(params):
        logger.info(f"📦 Ejecutando llamada cacheada para user {user_id} (0 RU)")
        return _execute_serp_call(params, call_type)

    es_admin = _es_admin(user_id)
    if not es_admin:
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

    success, result = _execute_serp_call(params, call_type)

    if success:
        try:
            registrado = track_quota_consumption(
                user_id=user_id,
                ru_consumed=1,
                source='serp_api',
                keyword=str(params.get('q', 'unknown'))[:255],  # columna VARCHAR(255)
                # Sin 'gl' (búsqueda sin país) va NULL: antes iba 'unknown', no
                # cabía en la columna (3 caracteres) y el cobro fallaba en silencio.
                country_code=params.get('gl') or None,
                metadata={'call_type': call_type, 'cached': False, 'admin': es_admin},
                update_user_quota=not es_admin,
            )
            if not registrado:
                logger.error(f"❌ No se pudo registrar el consumo SERP de user {user_id} ({call_type})")
            elif es_admin:
                logger.info(f"🧾 SERP de admin registrada sin descontar RU (user {user_id})")
            else:
                logger.info(f"📊 RU registrado: user {user_id} consumió 1 RU ({call_type})")
            _mark_call_cached(params)
        except Exception as e:
            logger.error(f"Error registrando consumo RU/caché para user {user_id}: {e}")

    return success, result

# La librería de SerpAPI pasa timeout=60000 a requests, que lo lee en SEGUNDOS
# (~17 h): una llamada colgada bloquearía el cron sin límite. SerpAPI corta sus
# búsquedas fallidas a los ~90 s, así que el tope va por encima para no abandonar
# búsquedas que aún pueden salir bien (SerpAPI las cobra aunque cortemos nosotros).
SERPAPI_TIMEOUT_SECONDS = float(os.getenv('SERPAPI_TIMEOUT_SECONDS', '120'))


def _google_search(params: dict) -> GoogleSearch:
    search = GoogleSearch(params)
    search.timeout = SERPAPI_TIMEOUT_SECONDS
    return search


def _execute_serp_call(params: dict, call_type: str) -> Tuple[bool, Dict[str, Any]]:
    """Ejecuta la llamada real a SerpAPI"""
    max_attempts = int(os.getenv('SERPAPI_RETRY_ATTEMPTS', '3'))
    base_delay = float(os.getenv('SERPAPI_RETRY_BACKOFF_SECONDS', '1.0'))
    
    for attempt in range(1, max_attempts + 1):
        try:
            if call_type == "json":
                data = _google_search(params).get_dict()
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
                html_content = _google_search({**params, 'output': 'html'}).get_html()
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
