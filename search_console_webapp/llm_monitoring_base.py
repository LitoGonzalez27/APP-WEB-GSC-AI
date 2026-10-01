"""Base del blueprint de LLM Monitoring: el blueprint, el control de acceso previo a
cada petición (enforce_llm_access), los decoradores de acceso y el estado en memoria
del primer análisis.

Sacado tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros gigantes)
para que las rutas puedan repartirse en varios módulos sin importarse entre sí: cada
módulo de rutas importa de aquí el blueprint y los decoradores. llm_monitoring_routes
vuelve a exponer estos nombres. Este módulo no importa ningún módulo de rutas.

Para parchear en un test lo que usan el control de acceso o los decoradores
(get_current_user, get_db_connection, user_can_view_project...) hay que hacerlo aquí:
un monkeypatch sobre llm_monitoring_routes.X no les llega.

El blueprint se registra en app.py importándolo de llm_monitoring_routes, después de
que se hayan cargado todas sus rutas: importarlo solo de aquí y registrarlo antes haría
fallar los @route posteriores (Flask 3), y app.py se lo tragaría con un aviso.
"""

import logging
import config
import threading
from flask import Blueprint, request, jsonify
from functools import wraps
from auth import get_current_user, get_current_user_strict, respuesta_fallo_tecnico
from database import DatabaseUnavailableError
from llm_monitoring_limits import can_access_llm_monitoring, get_upgrade_options
from services.project_access_service import user_can_view_project, user_has_any_module_access
from database import get_db_connection

# Configurar logging
logger = logging.getLogger(__name__)

# Crear Blueprint
llm_monitoring_bp = Blueprint('llm_monitoring', __name__, url_prefix='/api/llm-monitoring')

# Estado en memoria para evitar dobles disparos del primer análisis
# (misma instancia de app). La fuente de verdad para "ya analizado" sigue en BD.
_INITIAL_ANALYSIS_RUNNING = set()
_INITIAL_ANALYSIS_RUNNING_LOCK = threading.Lock()


def _safe_notify_email(candidate):
    """Evita que los endpoints de cron (protegidos por cron-token/admin) se usen como
    relay de correo hacia destinatarios arbitrarios (spam/phishing desde nuestro dominio).

    Solo se acepta el destinatario si pertenece a un dominio interno de confianza;
    en cualquier otro caso se usa el destinatario configurado por entorno.
    """
    default = config.email_alertas_llm()
    allowed_domains = ('clicandseo.com', 'soycarlosgonzalez.com')
    val = (candidate or '').strip()
    if val and '@' in val and val.rsplit('@', 1)[-1].lower() in allowed_domains:
        return val
    return default

def _is_initial_analysis_running(project_id: int) -> bool:
    with _INITIAL_ANALYSIS_RUNNING_LOCK:
        return int(project_id) in _INITIAL_ANALYSIS_RUNNING


def _mark_initial_analysis_running(project_id: int) -> bool:
    """
    Marca un proyecto como "primer análisis en curso".
    Returns False si ya estaba en curso.
    """
    with _INITIAL_ANALYSIS_RUNNING_LOCK:
        normalized_id = int(project_id)
        if normalized_id in _INITIAL_ANALYSIS_RUNNING:
            return False
        _INITIAL_ANALYSIS_RUNNING.add(normalized_id)
        return True


def _clear_initial_analysis_running(project_id: int):
    with _INITIAL_ANALYSIS_RUNNING_LOCK:
        _INITIAL_ANALYSIS_RUNNING.discard(int(project_id))


# ============================================================================
# DECORADORES AUXILIARES
# ============================================================================

@llm_monitoring_bp.before_request
def enforce_llm_access():
    """
    Bloquea acceso si el usuario no tiene plan válido/billing activo.
    Excepciones: endpoints de cron y health.
    """
    try:
        path = request.path or ""
        if "/api/llm-monitoring/cron/" in path or path.endswith("/health"):
            return None
        # Los enlaces de aprobación/rechazo del email de Model Discovery llevan
        # su propia credencial (token de 64 bytes con caducidad). Sin esta
        # excepción, abrir el email desde un dispositivo sin sesión (móvil)
        # devolvía un 401 JSON en vez de procesar el clic.
        if path.endswith("/models/approve") or path.endswith("/models/reject"):
            return None
        # Fase de fiabilidad (sep-2026): un fallo de la base de datos es 503, no
        # "inicia sesión" (401).
        try:
            user = get_current_user_strict()
        except DatabaseUnavailableError:
            logger.warning("enforce_llm_access: base de datos no disponible", exc_info=True)
            return respuesta_fallo_tecnico(
                503, 'database_unavailable', 'Servicio no disponible temporalmente. Reintenta en unos segundos.',
                True, forzar_json=True)
        if not user:
            return jsonify({'error': 'Authentication required. Please sign in.'}), 401
        if not can_access_llm_monitoring(user):
            # ✅ Permitir invitados con acceso explícito a proyectos compartidos
            if user_has_any_module_access(user['id'], 'llm_monitoring'):
                return None
            return jsonify({
                'error': 'paywall',
                'message': 'LLM Monitoring requires a paid plan',
                'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
                'current_plan': user.get('plan', 'free')
            }), 402
    except Exception as e:
        logger.error(f"Error en enforce_llm_access: {e}", exc_info=True)
        return jsonify({'error': 'Failed to validate access. Please try again.'}), 500

def validate_project_ownership(f):
    """
    Decorador de acceso al proyecto.
    - Owner: acceso total (GET/POST/PUT/DELETE)
    - Colaborador viewer: solo acceso GET
    """
    @wraps(f)
    def decorated_function(project_id, *args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required. Please sign in.'}), 401
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT user_id FROM llm_monitoring_projects
                WHERE id = %s
            """, (project_id,))
            
            project = cur.fetchone()
            
            if not project:
                return jsonify({'error': 'Project not found'}), 404

            is_owner = project['user_id'] == user['id']
            if not is_owner:
                can_view_shared = request.method == 'GET' and user_can_view_project(
                    user['id'],
                    'llm_monitoring',
                    project_id
                )
                if not can_view_shared:
                    return jsonify({'error': 'You do not have permission to access this project'}), 403
            
            return f(project_id, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error validando ownership: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
        finally:
            cur.close()
            conn.close()
    
    return decorated_function


def _ensure_cron_token_or_admin():
    """
    Endurece endpoints sensibles de cron:
    - Permite CRON token válido
    - O usuario autenticado con rol admin
    - Bloquea usuarios autenticados no-admin
    """
    try:
        if config.cabecera_cron_valida(request.headers.get('Authorization')):
            return None

        user = get_current_user()
        if user and user.get('role') == 'admin':
            return None

        return jsonify({
            'success': False,
            'error': 'forbidden',
            'message': 'Se requiere token de cron o rol admin'
        }), 403
    except Exception as e:
        logger.error(f"Error validando acceso cron/admin: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Error validando permisos'}), 500
