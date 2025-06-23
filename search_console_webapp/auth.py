# auth.py - Sistema de autenticación con Google OAuth2

import os
import json
import secrets
from functools import wraps
from flask import session, redirect, url_for, request, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

# ✅ NUEVO: Permitir HTTP para desarrollo local con OAuth2
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# ✅ NUEVO: Relajar validación de scopes para evitar errores de orden
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

logger = logging.getLogger(__name__)

# Configuración OAuth2
SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',  # Search Console (ya lo tienes)
    'https://www.googleapis.com/auth/userinfo.email',       # Email del usuario
    'https://www.googleapis.com/auth/userinfo.profile'      # Perfil básico del usuario
]

CLIENT_SECRETS_FILE = os.getenv('CLIENT_SECRETS_FILE', 'client_secret.json')

def create_flow():
    """Crea un objeto Flow para OAuth2"""
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES
        )
        # Configurar redirect URI - ajusta según tu dominio
        flow.redirect_uri = request.url_root + 'auth/callback'
        return flow
    except Exception as e:
        logger.error(f"Error creando flow OAuth2: {e}")
        return None

def login_required(f):
    """Decorador para rutas que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_authenticated():
            return jsonify({'error': 'Authentication required', 'auth_required': True}), 401
        return f(*args, **kwargs)
    return decorated_function

def is_user_authenticated():
    """Verifica si el usuario está autenticado"""
    return 'credentials' in session and session['credentials'] is not None

def get_user_credentials():
    """Obtiene las credenciales del usuario de la sesión"""
    if not is_user_authenticated():
        return None
    
    try:
        credentials_dict = session['credentials']
        credentials = Credentials(
            token=credentials_dict['token'],
            refresh_token=credentials_dict.get('refresh_token'),
            token_uri=credentials_dict['token_uri'],
            client_id=credentials_dict['client_id'],
            client_secret=credentials_dict['client_secret'],
            scopes=credentials_dict['scopes']
        )
        return credentials
    except Exception as e:
        logger.error(f"Error obteniendo credenciales: {e}")
        return None

def get_user_info():
    """Obtiene información del usuario autenticado"""
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
    """Refresca las credenciales si es necesario"""
    try:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            # Actualizar en sesión
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
    """Configura las rutas de autenticación en la app Flask"""
    
    @app.route('/auth/login')
    def auth_login():
        """Inicia el flujo de autenticación con Google"""
        try:
            flow = create_flow()
            if not flow:
                return jsonify({'error': 'OAuth configuration error'}), 500
            
            # Generar estado para seguridad
            session['state'] = secrets.token_urlsafe(32)
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=session['state']
            )
            
            logger.info(f"Redirigiendo a Google OAuth: {authorization_url}")
            return redirect(authorization_url)
            
        except Exception as e:
            logger.error(f"Error en auth_login: {e}")
            return jsonify({'error': 'Authentication initiation failed'}), 500

    @app.route('/auth/callback')
    def auth_callback():
        """Maneja el callback de Google OAuth"""
        try:
            # Verificar estado para prevenir CSRF
            if request.args.get('state') != session.get('state'):
                logger.warning("Estado OAuth inválido")
                return redirect('/?auth_error=invalid_state')
            
            flow = create_flow()
            if not flow:
                return redirect('/?auth_error=oauth_config')
            
            # Obtener el token de autorización
            flow.fetch_token(authorization_response=request.url)
            
            # Guardar credenciales en sesión
            credentials = flow.credentials
            session['credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Obtener info del usuario
            user_info = get_user_info()
            if user_info:
                session['user_info'] = user_info
                logger.info(f"Usuario autenticado: {user_info['email']}")
            
            # Limpiar estado
            session.pop('state', None)
            
            return redirect('/?auth_success=true')
            
        except Exception as e:
            logger.error(f"Error en auth_callback: {e}")
            return redirect('/?auth_error=callback_failed')

    @app.route('/auth/logout', methods=['POST'])
    def auth_logout():
        """Cierra la sesión del usuario"""
        try:
            # Limpiar sesión
            session.pop('credentials', None)
            session.pop('user_info', None)
            session.pop('state', None)
            
            logger.info("Usuario desconectado")
            return jsonify({'success': True, 'message': 'Logout successful'})
            
        except Exception as e:
            logger.error(f"Error en logout: {e}")
            return jsonify({'error': 'Logout failed'}), 500

    @app.route('/auth/status')
    def auth_status():
        """Verifica el estado de autenticación del usuario"""
        try:
            if is_user_authenticated():
                user_info = session.get('user_info', {})
                return jsonify({
                    'authenticated': True,
                    'user': {
                        'email': user_info.get('email'),
                        'name': user_info.get('name'),
                        'picture': user_info.get('picture')
                    }
                })
            else:
                return jsonify({'authenticated': False})
                
        except Exception as e:
            logger.error(f"Error en auth_status: {e}")
            return jsonify({'error': 'Status check failed'}), 500

    @app.route('/auth/user')
    @login_required
    def auth_user():
        """Obtiene información detallada del usuario autenticado"""
        try:
            user_info = get_user_info()
            if user_info:
                return jsonify({'user': user_info})
            else:
                return jsonify({'error': 'User information not available'}), 400
                
        except Exception as e:
            logger.error(f"Error en auth_user: {e}")
            return jsonify({'error': 'Failed to get user information'}), 500

# Función auxiliar para obtener servicio autenticado
def get_authenticated_service(service_name, version):
    """Obtiene un servicio de Google API autenticado"""
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