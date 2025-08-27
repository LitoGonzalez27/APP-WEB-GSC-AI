# auth.py - Sistema de autenticación con PostgreSQL y Google OAuth2

import os
import json
import secrets
from functools import wraps
from datetime import datetime, timedelta
from flask import session, redirect, request, jsonify, url_for, flash, render_template
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging
from dotenv import load_dotenv

# Importar funciones de base de datos
from database import (
    init_database, 
    get_user_by_email, 
    get_user_by_google_id, 
    get_user_by_id,
    create_user, 
    authenticate_user,
    get_all_users,
    update_user_activity,
    update_user_role,
    get_user_stats,
    get_db_connection,
    change_password,
    admin_reset_password,
    update_user_profile,
    get_user_activity_log,
    get_detailed_user_stats,
    migrate_user_timestamps,
    ensure_sample_data
)

# Carga las variables de entorno desde el .env
load_dotenv()

# Permitir HTTP en desarrollo
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

logger = logging.getLogger(__name__)

# Configuración OAuth2
SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

CLIENT_SECRETS_FILE = os.getenv('CLIENT_SECRETS_FILE', 'client_secret.json')
REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5001/auth/callback')

# ✅ Configuración de inactividad (en minutos)
SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT_MINUTES', '45'))  # 45 minutos por defecto
WARNING_MINUTES = int(os.getenv('SESSION_WARNING_MINUTES', '5'))  # Advertir 5 minutos antes

def create_flow():
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        return flow
    except Exception as e:
        logger.error(f"Error creando flow OAuth2: {e}")
        return None

def update_last_activity():
    """Actualiza el timestamp de última actividad del usuario"""
    session['last_activity'] = datetime.now().isoformat()

def is_session_expired():
    """Verifica si la sesión ha expirado por inactividad"""
    if 'last_activity' not in session:
        return True
    
    try:
        last_activity = datetime.fromisoformat(session['last_activity'])
        now = datetime.now()
        time_diff = now - last_activity
        
        return time_diff > timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    except Exception as e:
        logger.error(f"Error verificando expiración de sesión: {e}")
        return True

def get_session_time_remaining():
    """Obtiene el tiempo restante antes de que expire la sesión (en segundos)"""
    if 'last_activity' not in session:
        return 0
    
    try:
        last_activity = datetime.fromisoformat(session['last_activity'])
        now = datetime.now()
        time_diff = now - last_activity
        
        timeout_seconds = SESSION_TIMEOUT_MINUTES * 60
        elapsed_seconds = int(time_diff.total_seconds())
        
        remaining = timeout_seconds - elapsed_seconds
        return max(0, remaining)
    except Exception as e:
        logger.error(f"Error calculando tiempo restante: {e}")
        return 0

def get_current_user():
    """Obtiene el usuario actual desde la sesión"""
    if 'user_id' not in session:
        return None
    
    return get_user_by_id(session['user_id'])

def is_user_authenticated():
    """Verifica si el usuario está autenticado"""
    return 'user_id' in session and session['user_id'] is not None

def is_user_active():
    """Verifica si el usuario está activo"""
    user = get_current_user()
    return user and user['is_active']

def is_user_admin():
    """Verifica si el usuario es administrador"""
    user = get_current_user()
    return user and user['role'] == 'admin'

def is_user_ai_enabled():
    """Verifica si el usuario tiene acceso a funcionalidades AI (admin o AI User)"""
    user = get_current_user()
    return user and user['role'] in ['admin', 'AI User']

def auth_required(f):
    """Decorador que requiere autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar autenticación básica
        if not is_user_authenticated():
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Authentication required', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?auth_required=true')
        
        # Verificar expiración por inactividad
        if is_session_expired():
            session.clear()
            logger.info("Sesión expirada por inactividad")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Session expired due to inactivity', 'session_expired': True}), 401
            return redirect(url_for('login_page') + '?session_expired=true')
        
        # Verificar si el usuario está en la base de datos
        user = get_current_user()
        if not user:
            session.clear()
            logger.warning("Usuario no encontrado en base de datos")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'User not found', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?auth_error=user_not_found')
        
        # Verificar si el usuario está activo
        if not user['is_active']:
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Account suspended', 'account_suspended': True}), 403
            return redirect(url_for('login_page') + '?account_suspended=true')
        
        # Actualizar última actividad
        update_last_activity()
        
        return f(*args, **kwargs)
    return decorated_function

def cron_or_auth_required(f):
    """Decorador que permite:
    - Acceso con token de cron vía header Authorization: Bearer <CRON_TOKEN>
    - O bien, acceso con sesión autenticada normal (fallback a auth_required)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1) Intentar autenticar por token de cron
        try:
            auth_header = request.headers.get('Authorization', '') or ''
            token = auth_header[7:].strip() if auth_header.lower().startswith('bearer ') else ''
            cron_secret = os.environ.get('CRON_TOKEN') or os.environ.get('CRON_SECRET')
            if cron_secret and token and secrets.compare_digest(token, cron_secret):
                return f(*args, **kwargs)
        except Exception:
            # En caso de cualquier problema con el header, continuar con auth normal
            pass

        # 2) Fallback a autenticación habitual
        return auth_required(f)(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorador que requiere privilegios de administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar autenticación básica
        if not is_user_authenticated():
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Authentication required', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?auth_required=true')
        
        # Verificar expiración por inactividad
        if is_session_expired():
            session.clear()
            logger.info("Sesión expirada por inactividad")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Session expired due to inactivity', 'session_expired': True}), 401
            return redirect(url_for('login_page') + '?session_expired=true')
        
        # Verificar si el usuario está en la base de datos
        user = get_current_user()
        if not user:
            session.clear()
            logger.warning("Usuario no encontrado en base de datos")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'User not found', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?user_not_found=true')
        
        # Verificar si el usuario está activo
        if not user['is_active']:
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Account suspended', 'account_suspended': True}), 403
            return redirect(url_for('login_page') + '?account_suspended=true')
        
        # Verificar si el usuario es administrador
        if not user['role'] == 'admin':
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Admin privileges required', 'admin_required': True}), 403
            return redirect(url_for('dashboard') + '?admin_required=true')
        
        # Actualizar última actividad
        update_last_activity()
        
        return f(*args, **kwargs)
    return decorated_function

def ai_user_required(f):
    """Decorador que requiere privilegios de AI User (admin o AI User)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar autenticación básica
        if not is_user_authenticated():
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Authentication required', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?auth_required=true')
        
        # Verificar expiración por inactividad
        if is_session_expired():
            session.clear()
            logger.info("Sesión expirada por inactividad")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Session expired due to inactivity', 'session_expired': True}), 401
            return redirect(url_for('login_page') + '?session_expired=true')
        
        # Verificar si el usuario está en la base de datos
        user = get_current_user()
        if not user:
            session.clear()
            logger.warning("Usuario no encontrado en base de datos")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'User not found', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?user_not_found=true')
        
        # Verificar si el usuario está activo
        if not user['is_active']:
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Account suspended', 'account_suspended': True}), 403
            return redirect(url_for('login_page') + '?account_suspended=true')
        
        # Verificar si el usuario tiene acceso a funcionalidades AI
        if not user['role'] in ['admin', 'AI User']:
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({
                    'error': 'AI User privileges required',
                    'ai_user_required': True
                }), 403
            # Para acceso directo via navegador, redirigir a /app
            return redirect(url_for('app_main'))
        
        # Actualizar última actividad
        update_last_activity()
        
        return f(*args, **kwargs)
    return decorated_function

# Mantener compatibilidad con el decorador anterior
def login_required(f):
    """Decorador de compatibilidad - alias para auth_required"""
    return auth_required(f)

def auth_required_no_activity_update(f):
    """
    Decorador que requiere autenticación pero NO actualiza la última actividad.
    Usado para endpoints que solo consultan estado sin representar actividad real del usuario.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar autenticación básica
        if not is_user_authenticated():
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Authentication required', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?auth_required=true')
        
        # Verificar expiración por inactividad
        if is_session_expired():
            session.clear()
            logger.info("Sesión expirada por inactividad")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Session expired due to inactivity', 'session_expired': True}), 401
            return redirect(url_for('login_page') + '?session_expired=true')
        
        # Verificar si el usuario está en la base de datos
        user = get_current_user()
        if not user:
            session.clear()
            logger.warning("Usuario no encontrado en base de datos")
            
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'User not found', 'auth_required': True}), 401
            return redirect(url_for('login_page') + '?auth_error=user_not_found')
        
        # Verificar si el usuario está activo
        if not user['is_active']:
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Account suspended', 'account_suspended': True}), 403
            return redirect(url_for('login_page') + '?account_suspended=true')
        
        # ⚠️ NO actualizar última actividad - solo verificar autenticación
        
        return f(*args, **kwargs)
    return decorated_function

def get_user_credentials():
    """Obtiene las credenciales de Google OAuth del usuario actual"""
    if not is_user_authenticated():
        return None
    
    if 'credentials' not in session:
        return None
        
    try:
        credentials_dict = session['credentials']
        return Credentials(
            token=credentials_dict['token'],
            refresh_token=credentials_dict.get('refresh_token'),
            token_uri=credentials_dict['token_uri'],
            client_id=credentials_dict['client_id'],
            client_secret=credentials_dict['client_secret'],
            scopes=credentials_dict['scopes']
        )
    except Exception as e:
        logger.error(f"Error obteniendo credenciales: {e}")
        return None

def get_user_info():
    """Obtiene información del usuario desde Google OAuth"""
    credentials = get_user_credentials()
    if not credentials:
        return None
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return {
            'id': user_info.get('id'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'verified_email': user_info.get('verified_email', False)
        }
    except Exception as e:
        logger.error(f"Error obteniendo información del usuario: {e}")
        return None

def get_user_info_from_temp_credentials():
    """Obtiene información del usuario desde credenciales temporales"""
    if 'temp_credentials' not in session:
        return None
        
    try:
        credentials_dict = session['temp_credentials']
        credentials = Credentials(
            token=credentials_dict['token'],
            refresh_token=credentials_dict.get('refresh_token'),
            token_uri=credentials_dict['token_uri'],
            client_id=credentials_dict['client_id'],
            client_secret=credentials_dict['client_secret'],
            scopes=credentials_dict['scopes']
        )
        
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return {
            'id': user_info.get('id'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'verified_email': user_info.get('verified_email', False)
        }
    except Exception as e:
        logger.error(f"Error obteniendo información del usuario desde credenciales temporales: {e}")
        return None

def refresh_credentials_if_needed(credentials):
    """Actualiza las credenciales si es necesario"""
    try:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            session['credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
        return credentials
    except Exception as e:
        logger.error(f"Error refrescando credenciales: {e}")
        return None

def setup_auth_routes(app):
    """Configura todas las rutas de autenticación"""
    
    # Inicializar base de datos
    init_database()
    migrate_user_timestamps() # Ejecutar la migración de timestamps

    @app.route('/login')
    def login_page():
        """Página de inicio de sesión"""
        if is_user_authenticated():
            user = get_current_user()
            if user and user['is_active']:
                return redirect(url_for('dashboard'))
        
        return render_template('login.html')

    @app.route('/signup')
    def signup_page():
        """Página de registro"""
        if is_user_authenticated():
            user = get_current_user()
            if user and user['is_active']:
                return redirect(url_for('dashboard'))
        
        return render_template('signup.html')





    @app.route('/auth/login')
    def auth_login():
        """Inicio de sesión con Google OAuth - Solo para usuarios existentes"""
        try:
            flow = create_flow()
            if not flow:
                return jsonify({'error': 'OAuth configuration error'}), 500
            
            session['state'] = secrets.token_urlsafe(32)
            session['oauth_action'] = 'login'  # ✅ MARCAR como LOGIN
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=session['state']
            )
            return redirect(authorization_url)
        except Exception as e:
            logger.error(f"Error en auth_login: {e}")
            return jsonify({'error': 'Authentication initiation failed'}), 500

    @app.route('/auth/signup')
    def auth_signup():
        """Registro con Google OAuth - Para usuarios nuevos"""
        try:
            flow = create_flow()
            if not flow:
                return jsonify({'error': 'OAuth configuration error'}), 500
            
            session['state'] = secrets.token_urlsafe(32)
            session['oauth_action'] = 'signup'  # ✅ MARCAR como REGISTRO
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=session['state']
            )
            return redirect(authorization_url)
        except Exception as e:
            logger.error(f"Error en auth_signup: {e}")
            return jsonify({'error': 'Authentication initiation failed'}), 500

    @app.route('/auth/callback')
    def auth_callback():
        """Callback de Google OAuth - Maneja registro y login por separado"""
        try:
            if request.args.get('state') != session.get('state'):
                return redirect('/login?auth_error=invalid_state')
            
            # Manejar si el usuario negó el acceso
            if request.args.get('error') == 'access_denied':
                return redirect('/login?auth_error=access_denied')
            
            flow = create_flow()
            if not flow:
                return redirect('/login?auth_error=oauth_config')
            
            flow.fetch_token(authorization_response=request.url)
            credentials = flow.credentials
            
            # Guardar credenciales en sesión temporalmente (para obtener info del usuario)
            session['temp_credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Obtener información del usuario
            user_info = get_user_info_from_temp_credentials()
            if not user_info:
                session.pop('temp_credentials', None)
                return redirect('/login?auth_error=user_info_failed')
            
            # Verificar si el usuario ya existe en la base de datos
            existing_user = get_user_by_google_id(user_info['id'])
            if not existing_user:
                existing_user = get_user_by_email(user_info['email'])
            
            # ✅ DETERMINAR ACCIÓN: registro vs login
            oauth_action = session.pop('oauth_action', 'login')  # Por defecto es login
            
            if oauth_action == 'signup':
                # ===============================================
                # FLUJO DE REGISTRO: Crear cuenta SIN iniciar sesión
                # ===============================================
                if existing_user:
                    # Usuario ya existe, no se puede registrar de nuevo
                    session.pop('temp_credentials', None)
                    logger.warning(f"Usuario {user_info['email']} ya existe, no se puede registrar de nuevo")
                    return redirect('/login?auth_error=user_already_exists')
                
                # Crear nuevo usuario
                try:
                    new_user = create_user(
                        email=user_info['email'],
                        name=user_info['name'],
                        google_id=user_info['id'],
                        picture=user_info.get('picture')
                    )
                    
                    if not new_user:
                        session.pop('temp_credentials', None)
                        logger.error(f"Error creando usuario en registro: {user_info['email']}")
                        return redirect('/signup?auth_error=user_creation_failed')
                    
                    # NO ACTIVAR automáticamente - dejar inactivo para revisión admin
                    
                    # ✅ NO INICIAR SESIÓN - Solo limpiar credenciales temporales
                    session.pop('temp_credentials', None)
                    
                    logger.info(f"Usuario registrado con Google (sin iniciar sesión): {user_info['email']}")
                    return redirect('/login?registration_success=true&with_google=true')
                    
                except Exception as e:
                    session.pop('temp_credentials', None)
                    logger.error(f"Error en registro con Google: {e}")
                    return redirect('/signup?auth_error=registration_failed')
            
            else:
                # ===============================================
                # FLUJO DE LOGIN: Solo permitir si ya existe
                # ===============================================
                if not existing_user:
                    # Usuario no existe, no puede hacer login
                    session.pop('temp_credentials', None)
                    logger.warning(f"Usuario {user_info['email']} no existe, no puede hacer login")
                    return redirect('/login?auth_error=user_not_registered')
                
                # Usuario existe - verificar si está activo
                if not existing_user['is_active']:
                    session.pop('temp_credentials', None)
                    return redirect('/login?auth_error=account_suspended')
                
                # ✅ VINCULAR cuenta existente con Google ID si es necesario
                if not existing_user['google_id'] and user_info['id']:
                    try:
                        conn = get_db_connection()
                        if conn:
                            cur = conn.cursor()
                            cur.execute('''
                                UPDATE users 
                                SET google_id = %s, picture = %s, updated_at = NOW()
                                WHERE id = %s
                            ''', (user_info['id'], user_info.get('picture'), existing_user['id']))
                            conn.commit()
                            conn.close()
                            logger.info(f"Vinculada cuenta existente {user_info['email']} con Google ID")
                    except Exception as e:
                        logger.error(f"Error vinculando cuenta con Google: {e}")
                
                # ✅ INICIAR SESIÓN
                session['credentials'] = session.pop('temp_credentials')  # Mover credenciales a permanentes
                session['user_id'] = existing_user['id']
                session['user_email'] = existing_user['email']
                session['user_name'] = existing_user['name']
                update_last_activity()
                
                logger.info(f"Usuario autenticado con Google: {user_info['email']}")
                return redirect('/dashboard?auth_success=true&action=login')
                
        except Exception as e:
            session.pop('temp_credentials', None)
            session.pop('oauth_action', None)
            logger.error(f"Error en auth_callback: {e}")
            return redirect('/login?auth_error=callback_failed')

    # ✅ ELIMINADAS: Rutas innecesarias de pending-google-signup y complete-google-signup
    # El registro con Google ahora es automático en auth_callback

    @app.route('/auth/logout', methods=['POST', 'GET'])
    def auth_logout():
        """Cerrar sesión"""
        try:
            user_email = session.get('user_email', 'Unknown')
            
            # Limpiar sesión
            session.clear()
            
            logger.info(f"Usuario desconectado: {user_email}")
            
            if request.method == 'POST':
                return jsonify({'success': True, 'message': 'Sesión cerrada exitosamente'})
            else:
                flash('Sesión cerrada exitosamente', 'success')
                return redirect(url_for('login_page'))
                
        except Exception as e:
            logger.error(f"Error en logout: {e}")
            return redirect(url_for('login_page'))

    @app.route('/auth/status')
    def auth_status():
        """Estado de autenticación - Versión robusta para evitar bucles"""
        try:
            # ✅ NUEVO: Verificación básica sin side effects
            if 'user_id' not in session or session['user_id'] is None:
                return jsonify({
                    'authenticated': False,
                    'session_expired': False,
                    'time_remaining': 0
                })
            
            # ✅ NUEVO: Verificar expiración sin limpiar sesión (solo consulta)
            if 'last_activity' not in session:
                return jsonify({
                    'authenticated': False,
                    'session_expired': True,
                    'time_remaining': 0
                })
            
            try:
                last_activity = datetime.fromisoformat(session['last_activity'])
                now = datetime.now()
                time_diff = now - last_activity
                
                if time_diff > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    return jsonify({
                        'authenticated': False,
                        'session_expired': True,
                        'time_remaining': 0
                    })
            except Exception:
                # Si hay error en las fechas, considerar expirada
                return jsonify({
                    'authenticated': False,
                    'session_expired': True,
                    'time_remaining': 0
                })
            
            # ✅ NUEVO: Obtener usuario sin side effects
            user = get_user_by_id(session['user_id'])
            if not user:
                return jsonify({
                    'authenticated': False,
                    'user_not_found': True,
                    'time_remaining': 0
                })
            
            # ✅ NUEVO: Verificar si está activo
            if not user['is_active']:
                return jsonify({
                    'authenticated': False,
                    'account_suspended': True,
                    'time_remaining': 0
                })
            
            # ✅ NUEVO: Todo OK, retornar estado completo
            return jsonify({
                'authenticated': True,
                'session_expired': False,
                'time_remaining': get_session_time_remaining(),
                'session': {
                    'remaining_seconds': get_session_time_remaining(),
                    'timeout_minutes': SESSION_TIMEOUT_MINUTES,
                    'warning_minutes': WARNING_MINUTES
                },
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'name': user['name'],
                    'picture': user.get('picture'),
                    'role': user['role'],
                    'is_active': user['is_active']
                }
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de autenticación: {e}")
            return jsonify({
                'authenticated': False,
                'error': 'Error interno del servidor'
            }), 500

    @app.route('/auth/keepalive', methods=['POST'])
    @auth_required_no_activity_update
    def auth_keepalive():
        """Mantener sesión activa"""
        try:
            return jsonify({
                'success': True,
                'time_remaining': get_session_time_remaining(),
                'session_timeout_minutes': SESSION_TIMEOUT_MINUTES,
                'warning_minutes': WARNING_MINUTES
            })
        except Exception as e:
            logger.error(f"Error en keepalive: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/auth/user')
    @auth_required
    def auth_user():
        """Información del usuario actual"""
        try:
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            return jsonify({
                'id': user['id'],
                'email': user['email'],
                'name': user['name'],
                'picture': user.get('picture'),
                'role': user['role'],
                'is_active': user['is_active'],
                'created_at': user['created_at'].isoformat() if user['created_at'] else None
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo información del usuario: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500



    @app.route('/admin/users')
    @admin_required
    def admin_users():
        """Panel de administración de usuarios - MEJORADO con datos de billing"""
        try:
            # ✅ Asegurar que hay datos de prueba si la base de datos está vacía
            ensure_sample_data()
            
            # 🚀 MEJORA: Usar funciones de billing para datos completos
            try:
                from admin_billing_panel import get_users_with_billing, get_billing_stats
                users = get_users_with_billing()
                # Fusionar stats básicos con stats de billing
                basic_stats = get_user_stats()
                billing_stats = get_billing_stats()
                stats = {**basic_stats, **billing_stats}
                logger.info(f"✅ Admin panel mejorado - Usuarios con billing: {len(users)}")
            except ImportError as e:
                logger.warning(f"⚠️ Fallback a función básica - admin_billing_panel no disponible: {e}")
                users = get_all_users()
                stats = get_user_stats()
            
            current_user = get_current_user()
            
            # Debug logging
            logger.info(f"Admin panel cargado - Usuarios: {len(users)}, Stats: {list(stats.keys())}")
            
            # ✅ TEMPLATE MEJORADO CON DATOS COMPLETOS DE BILLING
            return render_template('admin_simple.html', users=users, stats=stats, current_user=current_user)
            
        except Exception as e:
            logger.error(f"Error en panel admin: {e}")
            # Fallback básico en caso de error
            users = get_all_users() if 'get_all_users' in globals() else []
            stats = get_user_stats() if 'get_user_stats' in globals() else {}
            current_user = get_current_user()
            return render_template('admin_simple.html', users=users, stats=stats, current_user=current_user)

    @app.route('/admin/users/<int:user_id>/billing-details')
    @admin_required
    def user_billing_details(user_id):
        """Obtener detalles completos de billing de un usuario para el modal Ver"""
        try:
            from admin_billing_panel import get_user_billing_details
            user_details = get_user_billing_details(user_id)
            
            if not user_details:
                return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
            
            return jsonify({'success': True, 'user': user_details})
            
        except ImportError:
            # Fallback a datos básicos si admin_billing_panel no está disponible
            logger.warning("⚠️ admin_billing_panel no disponible, usando datos básicos")
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute('''
                    SELECT id, email, name, picture, role, is_active, created_at,
                           plan, quota_limit, quota_used, current_period_start, current_period_end
                    FROM users WHERE id = %s
                ''', (user_id,))
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
                
                user_dict = dict(user)
                return jsonify({'success': True, 'user': user_dict})
                
            except Exception as fallback_error:
                logger.error(f"Error en fallback de detalles usuario: {fallback_error}")
                return jsonify({'success': False, 'error': 'Error obteniendo datos del usuario'}), 500
            finally:
                if conn:
                    conn.close()
            
        except Exception as e:
            logger.error(f"Error obteniendo detalles billing usuario {user_id}: {e}")
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/admin/debug-stats')
    @admin_required 
    def debug_stats():
        """Debug de estadísticas para solucionar problema"""
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        debug_info = {
            'database_connection': False,
            'users_data': [],
            'raw_queries': {},
            'stats_function_result': {},
            'error_details': []
        }
        
        try:
            # 1. Probar conexión directa
            conn = get_db_connection()
            if conn:
                debug_info['database_connection'] = True
                cur = conn.cursor()
                
                # 2. Consulta directa de usuarios
                cur.execute('SELECT id, email, name, is_active, created_at, role FROM users ORDER BY id')
                users_raw = cur.fetchall()
                debug_info['users_data'] = [dict(user) for user in users_raw]
                
                # 3. Consultas individuales de estadísticas
                queries = {
                    'total_users': 'SELECT COUNT(*) FROM users',
                    'active_users': 'SELECT COUNT(*) FROM users WHERE is_active = TRUE',
                    'inactive_users': 'SELECT COUNT(*) FROM users WHERE is_active = FALSE',
                    'today_registrations': '''
                        SELECT COUNT(*) FROM users 
                        WHERE created_at IS NOT NULL 
                        AND created_at >= CURRENT_DATE 
                        AND created_at < CURRENT_DATE + INTERVAL '1 day'
                    ''',
                    'week_registrations': '''
                        SELECT COUNT(*) FROM users 
                        WHERE created_at IS NOT NULL 
                        AND created_at >= NOW() - INTERVAL '7 days'
                    '''
                }
                
                for key, query in queries.items():
                    try:
                        cur.execute(query)
                        result = cur.fetchone()
                        debug_info['raw_queries'][key] = result[0] if result else 0
                    except Exception as e:
                        debug_info['raw_queries'][key] = f"ERROR: {str(e)}"
                        debug_info['error_details'].append(f"{key}: {str(e)}")
                
                # 4. Resultado de la función get_user_stats()
                debug_info['stats_function_result'] = get_user_stats()
                
                conn.close()
            else:
                debug_info['error_details'].append("No se pudo conectar a la base de datos")
                
        except Exception as e:
            debug_info['error_details'].append(f"Error general: {str(e)}")
        
        return jsonify(debug_info)

    @app.route('/admin/fix-dates')
    @admin_required 
    def fix_user_dates():
        """Arreglar fechas created_at que están en NULL"""
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({'error': 'No se pudo conectar a la base de datos'})
            
            cur = conn.cursor()
            
            # Actualizar usuarios con created_at NULL
            cur.execute('''
                UPDATE users 
                SET created_at = NOW() - INTERVAL '1 day' * (id - 1),
                    updated_at = NOW()
                WHERE created_at IS NULL
            ''')
            
            affected_rows = cur.rowcount
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Se actualizaron {affected_rows} usuarios con fechas válidas',
                'affected_rows': affected_rows
            })
            
        except Exception as e:
            return jsonify({'error': f'Error: {str(e)}'})

    @app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
    @admin_required
    def toggle_user_status(user_id):
        """Activar/desactivar usuario"""
        try:
            user = get_user_by_id(user_id)
            if not user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            new_status = not user['is_active']
            success = update_user_activity(user_id, new_status)
            
            if success:
                action = 'activado' if new_status else 'desactivado'
                logger.info(f"Usuario {user['email']} {action} por admin")
                return jsonify({
                    'success': True,
                    'message': f'Usuario {action} exitosamente',
                    'is_active': new_status
                })
            else:
                return jsonify({'error': 'Error actualizando usuario'}), 500
                
        except Exception as e:
            logger.error(f"Error toggling user status: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/admin/users/<int:user_id>/update-role', methods=['POST'])
    @admin_required
    def update_user_role_route(user_id):
        """Actualizar rol de usuario"""
        try:
            data = request.get_json()
            new_role = data.get('role')
            
            if new_role not in ['user', 'admin', 'AI User']:
                return jsonify({'error': 'Rol inválido'}), 400
            
            user = get_user_by_id(user_id)
            if not user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            success = update_user_role(user_id, new_role)
            
            if success:
                logger.info(f"Rol de usuario {user['email']} actualizado a {new_role}")
                return jsonify({
                    'success': True,
                    'message': f'Rol actualizado a {new_role}',
                    'role': new_role
                })
            else:
                return jsonify({'error': 'Error actualizando rol'}), 500
                
        except Exception as e:
            logger.error(f"Error updating user role: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    # ================================
    # RUTAS DE PERFIL DE USUARIO
    # ================================

    @app.route('/profile')
    @auth_required
    def user_profile():
        """Página de perfil de usuario"""
        user = get_current_user()
        if not user:
            return redirect(url_for('login_page'))
        
        # Obtener estadísticas del usuario
        activity_log = get_user_activity_log(user['id'])
        
        return render_template('user_profile.html', 
                             user=user, 
                             activity_log=activity_log)

    @app.route('/profile/update', methods=['POST'])
    @auth_required
    def update_profile():
        """Actualizar información del perfil"""
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            email = data.get('email', '').strip().lower()
            
            current_user = get_current_user()
            if not current_user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            # Validaciones
            if not name:
                return jsonify({'error': 'El nombre es obligatorio'}), 400
            
            if not email:
                return jsonify({'error': 'El email es obligatorio'}), 400
            
            # Verificar formato de email básico
            if '@' not in email or '.' not in email:
                return jsonify({'error': 'Formato de email inválido'}), 400
            
            # Actualizar perfil
            result = update_user_profile(current_user['id'], name=name, email=email)
            
            if result['success']:
                # Actualizar sesión si el email cambió
                if email != current_user['email']:
                    session['user_email'] = email
                if name != current_user['name']:
                    session['user_name'] = name
                
                logger.info(f"Perfil actualizado para usuario {current_user['email']}")
                return jsonify(result)
            else:
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Error actualizando perfil: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/profile/change-password', methods=['POST'])
    @auth_required
    def change_user_password():
        """Cambiar contraseña del usuario"""
        try:
            data = request.get_json()
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            confirm_password = data.get('confirm_password')
            
            # Validaciones
            if not current_password or not new_password or not confirm_password:
                return jsonify({'error': 'Todos los campos son obligatorios'}), 400
            
            if new_password != confirm_password:
                return jsonify({'error': 'Las contraseñas nuevas no coinciden'}), 400
            
            if len(new_password) < 8:
                return jsonify({'error': 'La nueva contraseña debe tener al menos 8 caracteres'}), 400
            
            current_user = get_current_user()
            if not current_user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            # Cambiar contraseña
            result = change_password(current_user['id'], current_password, new_password)
            
            if result['success']:
                logger.info(f"Contraseña cambiada para usuario {current_user['email']}")
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error cambiando contraseña: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    # ================================
    # RUTAS DE ADMINISTRACIÓN AVANZADA
    # ================================

    @app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
    @admin_required
    def admin_reset_user_password(user_id):
        """Restablecer contraseña de usuario por administrador"""
        try:
            data = request.get_json()
            new_password = data.get('new_password')
            
            if not new_password:
                return jsonify({'error': 'Nueva contraseña es requerida'}), 400
            
            if len(new_password) < 8:
                return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400
            
            current_admin = get_current_user()
            if not current_admin:
                return jsonify({'error': 'Administrador no encontrado'}), 404
            
            # Restablecer contraseña
            result = admin_reset_password(current_admin['id'], user_id, new_password)
            
            if result['success']:
                logger.info(f"Contraseña restablecida por admin {current_admin['email']} para usuario ID {user_id}")
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error restableciendo contraseña: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
    @admin_required
    def admin_delete_user(user_id):
        """Eliminar usuario por administrador"""
        try:
            # Verificar que el usuario objetivo existe
            target_user = get_user_by_id(user_id)
            if not target_user:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            
            current_admin = get_current_user()
            if not current_admin:
                return jsonify({'error': 'Administrador no encontrado'}), 404
                
            # No permitir que el admin se elimine a sí mismo
            if user_id == current_admin['id']:
                return jsonify({'error': 'No puedes eliminar tu propia cuenta'}), 400
            
            # Usar la función de database.py para eliminar
            from database import delete_user
            success = delete_user(user_id)
            
            if success:
                logger.info(f"Usuario {target_user['email']} eliminado por admin {current_admin['email']}")
                return jsonify({
                    'success': True,
                    'message': f'Usuario {target_user["name"]} eliminado exitosamente'
                })
            else:
                return jsonify({'error': 'Error eliminando usuario'}), 500
                
        except Exception as e:
            logger.error(f"Error eliminando usuario: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/admin/stats/detailed')
    @admin_required
    def admin_detailed_stats():
        """Estadísticas detalladas para administradores"""
        try:
            stats = get_detailed_user_stats()
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas detalladas: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/admin/users/<int:user_id>/change-plan', methods=['POST'])
    @admin_required
    def admin_change_user_plan(user_id):
        """Cambiar plan de un usuario desde admin panel"""
        try:
            from admin_billing_panel import update_user_plan_manual
            
            data = request.get_json()
            new_plan = data.get('plan')
            current_user = get_current_user()
            
            if not new_plan:
                return jsonify({'success': False, 'error': 'Plan no especificado'}), 400
            
            # Usar función del admin billing panel
            result = update_user_plan_manual(user_id, new_plan, current_user['id'])
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Error cambiando plan de usuario {user_id}: {e}")
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/admin/users/<int:user_id>/assign-custom-quota', methods=['POST'])
    @admin_required  
    def admin_assign_custom_quota(user_id):
        """Asignar quota personalizada (Enterprise) desde admin panel"""
        try:
            from admin_billing_panel import assign_custom_quota
            
            data = request.get_json()
            custom_limit = data.get('custom_limit')
            notes = data.get('notes', '')
            current_user = get_current_user()
            
            if custom_limit is None:
                return jsonify({'success': False, 'error': 'Custom limit no especificado'}), 400
            
            # Usar función del admin billing panel
            result = assign_custom_quota(user_id, custom_limit, notes, current_user['id'])
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Error asignando custom quota a usuario {user_id}: {e}")
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/admin/users/<int:user_id>/remove-custom-quota', methods=['POST'])
    @admin_required
    def admin_remove_custom_quota(user_id):
        """Remover quota personalizada y volver a plan estándar"""
        try:
            from admin_billing_panel import remove_custom_quota
            
            current_user = get_current_user()
            
            # Usar función del admin billing panel
            result = remove_custom_quota(user_id, current_user['id'])
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Error removiendo custom quota de usuario {user_id}: {e}")
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.route('/admin/users/<int:user_id>/reset-quota', methods=['POST'])
    @admin_required
    def admin_reset_quota(user_id):
        """Resetear manualmente la quota de un usuario (admin override)"""
        try:
            from admin_billing_panel import reset_user_quota_manual
            
            current_user = get_current_user()
            
            # Usar función del admin billing panel
            result = reset_user_quota_manual(user_id, current_user['id'])
            
            if result['success']:
                return jsonify(result)
            else:
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"Error reseteando quota de usuario {user_id}: {e}")
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

def get_authenticated_service(service_name, version):
    """Obtiene un servicio autenticado de Google API"""
    credentials = get_user_credentials()
    if not credentials:
        return None
    
    try:
        credentials = refresh_credentials_if_needed(credentials)
        if not credentials:
            return None
            
        return build(service_name, version, credentials=credentials)
    except Exception as e:
        logger.error(f"Error obteniendo servicio autenticado: {e}")
        return None

