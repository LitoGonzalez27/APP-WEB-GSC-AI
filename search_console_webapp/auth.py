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
    get_user_stats
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

    @app.route('/signup', methods=['POST'])
    def signup_manual():
        """Registro manual con email y contraseña"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            name = data.get('name', '').strip()
            password = data.get('password', '')
            
            # Validar datos
            if not email or not name or not password:
                return jsonify({'error': 'Todos los campos son obligatorios'}), 400
            
            if len(password) < 8:
                return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400
            
            # Verificar si el usuario ya existe
            existing_user = get_user_by_email(email)
            if existing_user:
                return jsonify({'error': 'Ya existe un usuario con este email'}), 400
            
            # Crear usuario
            user = create_user(email, name, password)
            if not user:
                return jsonify({'error': 'Error creando usuario'}), 500
            
            logger.info(f"Usuario registrado manualmente: {email}")
            
            return jsonify({
                'success': True,
                'message': 'Usuario registrado exitosamente. Ahora puedes iniciar sesión.',
                'redirect': url_for('login_page')
            })
            
        except Exception as e:
            logger.error(f"Error en registro manual: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/login', methods=['POST'])
    def login_manual():
        """Inicio de sesión manual con email y contraseña"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            
            # Validar datos
            if not email or not password:
                return jsonify({'error': 'Email y contraseña son obligatorios'}), 400
            
            # Autenticar usuario
            user = authenticate_user(email, password)
            if not user:
                return jsonify({'error': 'Email o contraseña incorrectos'}), 401
            
            # Verificar si el usuario está activo
            if not user['is_active']:
                return jsonify({'error': 'Tu cuenta está suspendida. Contacta con soporte.'}), 403
            
            # Iniciar sesión
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            update_last_activity()
            
            logger.info(f"Usuario autenticado manualmente: {email}")
            
            return jsonify({
                'success': True,
                'message': 'Inicio de sesión exitoso',
                'redirect': url_for('dashboard')
            })
            
        except Exception as e:
            logger.error(f"Error en login manual: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/auth/login/manual', methods=['POST'])
    def auth_login_manual():
        """Inicio de sesión manual con email y contraseña - nueva ruta"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            remember = data.get('remember', False)
            
            # Validar datos
            if not email or not password:
                return jsonify({'error': 'Email y contraseña son obligatorios'}), 400
            
            # Verificar si el usuario existe
            user = get_user_by_email(email)
            if not user:
                return jsonify({'error': 'user_not_found'}), 404
            
            # Autenticar usuario
            auth_user = authenticate_user(email, password)
            if not auth_user:
                return jsonify({'error': 'invalid_credentials'}), 401
            
            # Verificar si el usuario está activo
            if not auth_user['is_active']:
                return jsonify({'error': 'account_suspended'}), 403
            
            # Iniciar sesión
            session['user_id'] = auth_user['id']
            session['user_email'] = auth_user['email']
            session['user_name'] = auth_user['name']
            
            # Extender sesión si se marca "recordar"
            if remember:
                session.permanent = True
            
            update_last_activity()
            
            logger.info(f"Usuario autenticado manualmente: {email}")
            
            return jsonify({
                'success': True,
                'message': 'Inicio de sesión exitoso',
                'redirect': url_for('dashboard')
            })
            
        except Exception as e:
            logger.error(f"Error en login manual: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/auth/login')
    def auth_login():
        """Inicio de sesión con Google OAuth"""
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
        """Callback de Google OAuth"""
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
            
            # Guardar credenciales en sesión
            session['credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Obtener información del usuario
            user_info = get_user_info()
            if not user_info:
                return redirect('/login?auth_error=user_info_failed')
            
            # Verificar si el usuario ya existe en la base de datos
            existing_user = get_user_by_google_id(user_info['id'])
            if not existing_user:
                existing_user = get_user_by_email(user_info['email'])
            
            if existing_user:
                # Usuario existe - verificar si está activo
                if not existing_user['is_active']:
                    return redirect('/login?auth_error=account_suspended')
                
                # Iniciar sesión
                session['user_id'] = existing_user['id']
                session['user_email'] = existing_user['email']
                session['user_name'] = existing_user['name']
                update_last_activity()
                
                logger.info(f"Usuario autenticado con Google: {user_info['email']}")
                return redirect('/dashboard?auth_success=true')
            else:
                # Usuario no existe - redirigir a registro
                session['pending_google_signup'] = {
                    'google_id': user_info['id'],
                    'email': user_info['email'],
                    'name': user_info['name'],
                    'picture': user_info.get('picture')
                }
                return redirect('/signup?google_signup=true')
                
        except Exception as e:
            logger.error(f"Error en auth_callback: {e}")
            return redirect('/login?auth_error=callback_failed')

    @app.route('/auth/pending-google-signup')
    def get_pending_google_signup():
        """Obtiene los datos pendientes de registro con Google"""
        try:
            if 'pending_google_signup' not in session:
                return jsonify({'pending': False})
            
            google_data = session['pending_google_signup']
            
            return jsonify({
                'pending': True,
                'data': {
                    'name': google_data['name'],
                    'email': google_data['email'],
                    'picture': google_data.get('picture')
                }
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo datos pendientes: {e}")
            return jsonify({'pending': False})

    @app.route('/auth/complete-google-signup', methods=['POST'])
    def complete_google_signup():
        """Completa el registro con Google OAuth"""
        try:
            if 'pending_google_signup' not in session:
                return jsonify({'error': 'No hay registro pendiente'}), 400
            
            google_data = session['pending_google_signup']
            
            # Crear usuario en la base de datos
            user = create_user(
                email=google_data['email'],
                name=google_data['name'],
                google_id=google_data['google_id'],
                picture=google_data.get('picture')
            )
            
            if not user:
                return jsonify({'error': 'Error creando usuario'}), 500
            
            # ✅ MODIFICADO: NO iniciar sesión automáticamente, redirigir al login
            # Limpiar datos pendientes
            session.pop('pending_google_signup', None)
            
            logger.info(f"Usuario registrado con Google: {google_data['email']} - Redirigiendo al login")
            
            return jsonify({
                'success': True,
                'message': 'Usuario registrado exitosamente. Ahora puedes iniciar sesión.',
                'redirect': url_for('login_page') + '?registration_success=true'
            })
            
        except Exception as e:
            logger.error(f"Error completando registro con Google: {e}")
            return jsonify({'error': 'Error interno del servidor'}), 500

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
        """Panel de administración de usuarios"""
        users = get_all_users()
        stats = get_user_stats()
        return render_template('admin_users.html', users=users, stats=stats)

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
            
            if new_role not in ['user', 'admin']:
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