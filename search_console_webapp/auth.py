# auth.py - Sistema de autenticación con Google OAuth2

import os
import json
import secrets
from functools import wraps
from datetime import datetime, timedelta
from flask import session, redirect, request, jsonify, url_for
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging
from dotenv import load_dotenv

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

# ✅ NUEVA: Configuración de inactividad (en minutos)
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar autenticación básica
        if not is_user_authenticated():
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Authentication required', 'auth_required': True}), 401
            # Si es una petición del navegador, redirigir a login
            return redirect(url_for('login_page') + '?auth_required=true')
        
        # ✅ NUEVA: Verificar expiración por inactividad
        if is_session_expired():
            # Limpiar sesión expirada
            session.clear()
            logger.info("Sesión expirada por inactividad")
            
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Session expired due to inactivity', 'session_expired': True}), 401
            # Si es una petición del navegador, redirigir a login
            return redirect(url_for('login_page') + '?session_expired=true')
        
        # ✅ NUEVA: Actualizar última actividad para peticiones válidas
        update_last_activity()
        
        return f(*args, **kwargs)
    return decorated_function

def auth_required_no_activity_update(f):
    """
    Decorador que requiere autenticación pero NO actualiza la última actividad.
    Usado para endpoints que solo consultan estado sin representar actividad real del usuario.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar autenticación básica
        if not is_user_authenticated():
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Authentication required', 'auth_required': True}), 401
            # Si es una petición del navegador, redirigir a login
            return redirect(url_for('login_page') + '?auth_required=true')
        
        # ✅ NUEVA: Verificar expiración por inactividad
        if is_session_expired():
            # Limpiar sesión expirada
            session.clear()
            logger.info("Sesión expirada por inactividad")
            
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Session expired due to inactivity', 'session_expired': True}), 401
            # Si es una petición del navegador, redirigir a login
            return redirect(url_for('login_page') + '?session_expired=true')
        
        # ⚠️ NO actualizar última actividad - solo verificar autenticación
        
        return f(*args, **kwargs)
    return decorated_function

def is_user_authenticated():
    return 'credentials' in session and session['credentials'] is not None

def get_user_credentials():
    if not is_user_authenticated():
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

def refresh_credentials_if_needed(credentials):
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

    @app.route('/auth/login')
    def auth_login():
        try:
            flow = create_flow()
            if not flow:
                return jsonify({'error': 'OAuth configuration error'}), 500
            session['state'] = secrets.token_urlsafe(32)
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=session['state']
            )
            return redirect(authorization_url)
        except Exception as e:
            logger.error(f"Error en auth_login: {e}")
            return jsonify({'error': 'Authentication initiation failed'}), 500

    @app.route('/auth/callback')
    def auth_callback():
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
            
            session['credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            user_info = get_user_info()
            if user_info:
                session['user_info'] = user_info
                logger.info(f"Usuario autenticado: {user_info.get('email')}")
            
            # ✅ NUEVA: Establecer última actividad al autenticarse
            update_last_activity()
            
            session.pop('state', None)
            return redirect('/?auth_success=true')
        except Exception as e:
            logger.error(f"Error en auth_callback: {e}")
            return redirect('/login?auth_error=callback_failed')

    @app.route('/auth/logout', methods=['POST', 'GET'])
    def auth_logout():
        try:
            user_email = session.get('user_info', {}).get('email', 'usuario')
            session.clear()
            logger.info(f"Usuario desconectado: {user_email}")
            
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'success': True, 'message': 'Logout successful'})
            
            # Si es una petición del navegador, redirigir a login
            return redirect('/login?session_expired=true')
        except Exception as e:
            logger.error(f"Error en logout: {e}")
            
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'error': 'Logout failed'}), 500
            
            # Si es una petición del navegador, redirigir a login con error
            return redirect('/login?auth_error=logout_failed')

    @app.route('/auth/status')
    def auth_status():
        try:
            if is_user_authenticated():
                # ✅ NUEVA: Verificar si la sesión ha expirado por inactividad
                if is_session_expired():
                    session.clear()
                    return jsonify({
                        'authenticated': False, 
                        'session_expired': True,
                        'reason': 'Session expired due to inactivity'
                    })
                
                user_info = session.get('user_info', {})
                remaining_seconds = get_session_time_remaining()
                
                return jsonify({
                    'authenticated': True,
                    'user': {
                        'email': user_info.get('email'),
                        'name': user_info.get('name'),
                        'picture': user_info.get('picture')
                    },
                    'session': {
                        'remaining_seconds': remaining_seconds,
                        'timeout_minutes': SESSION_TIMEOUT_MINUTES,
                        'warning_minutes': WARNING_MINUTES
                    }
                })
            return jsonify({'authenticated': False})
        except Exception as e:
            logger.error(f"Error en auth_status: {e}")
            return jsonify({'error': 'Status check failed'}), 500

    # ✅ NUEVA: Endpoint para renovar la sesión (mantener activa)
    @app.route('/auth/keepalive', methods=['POST'])
    @auth_required_no_activity_update
    def auth_keepalive():
        """Mantiene la sesión activa actualizando la última actividad SOLO si se confirma actividad"""
        try:
            # ✅ SOLO actualizar actividad si se envía confirmación explícita
            request_data = request.get_json() or {}
            user_active = request_data.get('user_active', False)
            
            if user_active:
                update_last_activity()
                message = 'Session refreshed - user activity confirmed'
                logger.info("Keep-alive con actividad del usuario confirmada")
            else:
                message = 'Session checked - no activity update'
                logger.info("Keep-alive sin actividad del usuario")
            
            remaining_seconds = get_session_time_remaining()
            
            return jsonify({
                'success': True,
                'remaining_seconds': remaining_seconds,
                'user_active': user_active,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error en auth_keepalive: {e}")
            return jsonify({'error': 'Failed to refresh session'}), 500

    @app.route('/auth/user')
    @login_required
    def auth_user():
        try:
            user_info = get_user_info()
            if user_info:
                return jsonify({'user': user_info})
            return jsonify({'error': 'User information not available'}), 400
        except Exception as e:
            logger.error(f"Error en auth_user: {e}")
            return jsonify({'error': 'Failed to get user information'}), 500

def get_authenticated_service(service_name, version):
    credentials = get_user_credentials()
    if not credentials:
        return None
    credentials = refresh_credentials_if_needed(credentials)
    if not credentials:
        return None
    try:
        return build(service_name, version, credentials=credentials)
    except Exception as e:
        logger.error(f"Error creando servicio {service_name}: {e}")
        return None