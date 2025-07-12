# database.py - Gestión de base de datos PostgreSQL

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logging
from dotenv import load_dotenv
import hashlib
import secrets

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

# Configuración de la base de datos
# Railway proporciona DATABASE_URL automáticamente en producción
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:sRZcCViicJDQsgFZnVeiDsLHEzWBbvIB@yamanote.proxy.rlwy.net:15620/railway')

# Detectar si estamos en producción
is_production = os.getenv('RAILWAY_ENVIRONMENT') == 'production'

def get_db_connection():
    """Obtiene una conexión a la base de datos PostgreSQL"""
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"Error conectando a la base de datos: {e}")
        return None

def init_database():
    """Inicializa la base de datos creando las tablas necesarias"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        
        # Crear tabla users si no existe
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                google_id TEXT UNIQUE,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                picture TEXT,
                password_hash TEXT,
                role TEXT DEFAULT 'user',
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Crear índices para optimizar consultas
        cur.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)')
        
        conn.commit()
        logger.info("Base de datos inicializada correctamente")
        return True
        
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}")
        return False
    finally:
        if conn:
            conn.close()

def hash_password(password):
    """Genera un hash seguro de la contraseña"""
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

def verify_password(password, stored_hash):
    """Verifica si la contraseña coincide con el hash almacenado"""
    if not stored_hash:
        return False
    
    salt = stored_hash[:64]
    stored_password_hash = stored_hash[64:]
    
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    
    return password_hash.hex() == stored_password_hash

def create_user(email, name, password=None, google_id=None, picture=None):
    """Crea un nuevo usuario en la base de datos"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        
        # Verificar si el usuario ya existe
        cur.execute('SELECT id FROM users WHERE email = %s', (email,))
        if cur.fetchone():
            logger.warning(f"Usuario con email {email} ya existe")
            return None
        
        # Preparar datos del usuario
        password_hash = hash_password(password) if password else None
        
        cur.execute('''
            INSERT INTO users (email, name, password_hash, google_id, picture, role, is_active)
            VALUES (%s, %s, %s, %s, %s, 'user', FALSE)
            RETURNING id, email, name, picture, role, is_active, created_at
        ''', (email, name, password_hash, google_id, picture))
        
        user = cur.fetchone()
        conn.commit()
        
        logger.info(f"Usuario creado exitosamente: {email}")
        return dict(user)
        
    except Exception as e:
        logger.error(f"Error creando usuario: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_by_email(email):
    """Obtiene un usuario por su email"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        
        return dict(user) if user else None
        
    except Exception as e:
        logger.error(f"Error obteniendo usuario por email: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_by_google_id(google_id):
    """Obtiene un usuario por su Google ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE google_id = %s', (google_id,))
        user = cur.fetchone()
        
        return dict(user) if user else None
        
    except Exception as e:
        logger.error(f"Error obteniendo usuario por Google ID: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_by_id(user_id):
    """Obtiene un usuario por su ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        
        return dict(user) if user else None
        
    except Exception as e:
        logger.error(f"Error obteniendo usuario por ID: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_user_activity(user_id, is_active=True):
    """Actualiza el estado de actividad de un usuario"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        cur.execute('''
            UPDATE users 
            SET is_active = %s, updated_at = NOW()
            WHERE id = %s
        ''', (is_active, user_id))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        logger.error(f"Error actualizando actividad del usuario: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_users():
    """Obtiene todos los usuarios (para administración)"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cur = conn.cursor()
        cur.execute('''
            SELECT id, email, name, picture, role, is_active, created_at, updated_at
            FROM users
            ORDER BY created_at DESC
        ''')
        
        users = cur.fetchall()
        return [dict(user) for user in users]
        
    except Exception as e:
        logger.error(f"Error obteniendo todos los usuarios: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_user_role(user_id, role):
    """Actualiza el rol de un usuario"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        cur.execute('''
            UPDATE users 
            SET role = %s, updated_at = NOW()
            WHERE id = %s
        ''', (role, user_id))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        logger.error(f"Error actualizando rol del usuario: {e}")
        return False
    finally:
        if conn:
            conn.close()

def authenticate_user(email, password):
    """Autentica un usuario con email y contraseña"""
    try:
        user = get_user_by_email(email)
        if not user:
            return None
            
        if not user['password_hash']:
            logger.warning(f"Usuario {email} no tiene contraseña configurada")
            return None
            
        if not verify_password(password, user['password_hash']):
            logger.warning(f"Contraseña incorrecta para usuario {email}")
            return None
            
        return user
        
    except Exception as e:
        logger.error(f"Error autenticando usuario: {e}")
        return None

def delete_user(user_id):
    """Elimina un usuario de la base de datos"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        logger.error(f"Error eliminando usuario: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_user_stats():
    """Obtiene estadísticas de usuarios para el panel de administración"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}
            
        cur = conn.cursor()
        
        # Total de usuarios
        cur.execute('SELECT COUNT(*) FROM users')
        total_users = cur.fetchone()[0]
        
        # Usuarios activos
        cur.execute('SELECT COUNT(*) FROM users WHERE is_active = TRUE')
        active_users = cur.fetchone()[0]
        
        # Usuarios registrados hoy
        cur.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE')
        today_registrations = cur.fetchone()[0]
        
        # Usuarios registrados en los últimos 7 días
        cur.execute('SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL \'7 days\'')
        week_registrations = cur.fetchone()[0]
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'today_registrations': today_registrations,
            'week_registrations': week_registrations
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de usuarios: {e}")
        return {}
    finally:
        if conn:
            conn.close() 