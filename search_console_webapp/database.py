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
        
        # ✅ CORREGIDO: Usuarios con Google se crean como activos por defecto
        # Los usuarios con registro manual requieren verificación
        is_active = True if google_id else False
        
        cur.execute('''
            INSERT INTO users (email, name, password_hash, google_id, picture, role, is_active)
            VALUES (%s, %s, %s, %s, %s, 'user', %s)
            RETURNING id, email, name, picture, role, is_active, created_at
        ''', (email, name, password_hash, google_id, picture, is_active))
        
        user = cur.fetchone()
        conn.commit()
        
        logger.info(f"Usuario creado exitosamente: {email} (activo: {is_active})")
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
    logger.info("🔍 INICIANDO get_user_stats()")
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("❌ CRÍTICO: No se pudo conectar a la base de datos para estadísticas")
            return {
                'total_users': 0,
                'active_users': 0,
                'inactive_users': 0,
                'today_registrations': 0,
                'week_registrations': 0
            }
        
        logger.info("✅ Conexión a base de datos exitosa")
            
        cur = conn.cursor()
        
        # Total de usuarios
        logger.info("📊 Iniciando obtención de estadísticas...")
        try:
            cur.execute('SELECT COUNT(*) FROM users')
            total_users_result = cur.fetchone()
            total_users = total_users_result[0] if total_users_result else 0
            logger.info(f"✅ Total usuarios: {total_users}")
        except Exception as e:
            logger.error(f"❌ Error query total usuarios: {str(e)}")
            total_users = 0
        
        # Usuarios activos
        try:
            cur.execute('SELECT COUNT(*) FROM users WHERE is_active = TRUE')
            active_users_result = cur.fetchone()
            active_users = active_users_result[0] if active_users_result else 0
            logger.info(f"✅ Usuarios activos: {active_users}")
        except Exception as e:
            logger.error(f"❌ Error query usuarios activos: {str(e)}")
            active_users = 0
        
        # ✅ ARREGLADO: Usuarios registrados hoy (mejorar consulta de timezone)
        try:
            # Usar timezone explícito y rango de tiempo más específico
            cur.execute('''
                SELECT COUNT(*) FROM users 
                WHERE created_at IS NOT NULL 
                AND created_at >= CURRENT_DATE 
                AND created_at < CURRENT_DATE + INTERVAL '1 day'
            ''')
            today_result = cur.fetchone()
            today_registrations = today_result[0] if today_result else 0
            logger.info(f"✅ Registros hoy: {today_registrations}")
            
            # ✅ DEBUG: Mostrar usuarios de hoy para verificar
            if today_registrations > 0:
                cur.execute('''
                    SELECT email, created_at FROM users 
                    WHERE created_at IS NOT NULL 
                    AND created_at >= CURRENT_DATE 
                    AND created_at < CURRENT_DATE + INTERVAL '1 day'
                    ORDER BY created_at DESC
                ''')
                today_users = cur.fetchall()
                logger.info(f"🔍 Usuarios registrados hoy: {[dict(user) for user in today_users]}")
                
        except Exception as e:
            logger.error(f"❌ Error query registros hoy: {str(e)}")
            today_registrations = 0
        
        # Usuarios registrados en los últimos 7 días (considerar NULL en created_at)
        try:
            cur.execute('SELECT COUNT(*) FROM users WHERE created_at IS NOT NULL AND created_at >= NOW() - INTERVAL \'7 days\'')
            week_result = cur.fetchone()
            week_registrations = week_result[0] if week_result else 0
            logger.info(f"✅ Registros semana: {week_registrations}")
        except Exception as e:
            logger.error(f"❌ Error query registros semana: {str(e)}")
            week_registrations = 0
        
        inactive_users = max(0, total_users - active_users)
        
        stats = {
            'total_users': int(total_users),
            'active_users': int(active_users),
            'inactive_users': int(inactive_users),
            'today_registrations': int(today_registrations),
            'week_registrations': int(week_registrations)
        }
        
        logger.info(f"Estadísticas finales: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de usuarios: {e}")
        # Retornar valores por defecto en caso de error
        return {
            'total_users': 0,
            'active_users': 0,
            'inactive_users': 0,
            'today_registrations': 0,
            'week_registrations': 0
        }
    finally:
        if conn:
            conn.close() 

def change_password(user_id, old_password, new_password):
    """Cambia la contraseña de un usuario verificando la contraseña actual"""
    try:
        # Primero verificar que el usuario existe y tiene contraseña
        user = get_user_by_id(user_id)
        if not user:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        if not user['password_hash']:
            return {'success': False, 'error': 'Este usuario no tiene contraseña configurada. Usa login con Google.'}
        
        # Verificar contraseña actual
        if not verify_password(old_password, user['password_hash']):
            return {'success': False, 'error': 'La contraseña actual es incorrecta'}
        
        # Generar nueva contraseña hash
        new_password_hash = hash_password(new_password)
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Error de conexión a la base de datos'}
            
        cur = conn.cursor()
        cur.execute('''
            UPDATE users 
            SET password_hash = %s, updated_at = NOW()
            WHERE id = %s
        ''', (new_password_hash, user_id))
        
        conn.commit()
        
        if cur.rowcount > 0:
            logger.info(f"Contraseña cambiada exitosamente para usuario ID: {user_id}")
            return {'success': True, 'message': 'Contraseña cambiada exitosamente'}
        else:
            return {'success': False, 'error': 'No se pudo actualizar la contraseña'}
        
    except Exception as e:
        logger.error(f"Error cambiando contraseña: {e}")
        return {'success': False, 'error': 'Error interno del servidor'}
    finally:
        if conn:
            conn.close()

def admin_reset_password(admin_user_id, target_user_id, new_password):
    """Permite a un administrador restablecer la contraseña de otro usuario"""
    try:
        # Verificar que el admin es realmente admin
        admin = get_user_by_id(admin_user_id)
        if not admin or admin['role'] != 'admin':
            return {'success': False, 'error': 'Permisos insuficientes'}
        
        # Verificar que el usuario objetivo existe
        target_user = get_user_by_id(target_user_id)
        if not target_user:
            return {'success': False, 'error': 'Usuario objetivo no encontrado'}
        
        # Generar nueva contraseña hash
        new_password_hash = hash_password(new_password)
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Error de conexión a la base de datos'}
            
        cur = conn.cursor()
        cur.execute('''
            UPDATE users 
            SET password_hash = %s, updated_at = NOW()
            WHERE id = %s
        ''', (new_password_hash, target_user_id))
        
        conn.commit()
        
        if cur.rowcount > 0:
            logger.info(f"Contraseña restablecida por admin {admin_user_id} para usuario {target_user_id}")
            return {'success': True, 'message': f'Contraseña restablecida para {target_user["name"]}'}
        else:
            return {'success': False, 'error': 'No se pudo restablecer la contraseña'}
        
    except Exception as e:
        logger.error(f"Error restableciendo contraseña: {e}")
        return {'success': False, 'error': 'Error interno del servidor'}
    finally:
        if conn:
            conn.close()

def update_user_profile(user_id, name=None, email=None):
    """Actualiza información del perfil de usuario"""
    try:
        user = get_user_by_id(user_id)
        if not user:
            return {'success': False, 'error': 'Usuario no encontrado'}
        
        # Preparar datos para actualizar
        updates = []
        params = []
        
        if name and name != user['name']:
            updates.append('name = %s')
            params.append(name)
        
        if email and email != user['email']:
            # Verificar que el nuevo email no esté en uso
            existing_user = get_user_by_email(email)
            if existing_user and existing_user['id'] != user_id:
                return {'success': False, 'error': 'El email ya está en uso por otro usuario'}
            
            updates.append('email = %s')
            params.append(email)
        
        if not updates:
            return {'success': False, 'error': 'No hay cambios para aplicar'}
        
        updates.append('updated_at = NOW()')
        params.append(user_id)
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Error de conexión a la base de datos'}
            
        cur = conn.cursor()
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        cur.execute(query, params)
        
        conn.commit()
        
        if cur.rowcount > 0:
            logger.info(f"Perfil actualizado para usuario ID: {user_id}")
            return {'success': True, 'message': 'Perfil actualizado exitosamente'}
        else:
            return {'success': False, 'error': 'No se pudo actualizar el perfil'}
        
    except Exception as e:
        logger.error(f"Error actualizando perfil: {e}")
        return {'success': False, 'error': 'Error interno del servidor'}
    finally:
        if conn:
            conn.close()

def get_user_activity_log(user_id, limit=10):
    """Obtiene un registro de actividad del usuario (placeholder para futura implementación)"""
    try:
        # Por ahora retornamos datos básicos del usuario
        user = get_user_by_id(user_id)
        if not user:
            return []
        
        # En una implementación futura, aquí tendríamos una tabla de logs
        return [
            {
                'activity': 'Cuenta creada',
                'timestamp': user['created_at'],
                'details': 'Usuario registrado en el sistema'
            },
            {
                'activity': 'Última actualización',
                'timestamp': user.get('updated_at', user['created_at']),
                'details': 'Información del perfil actualizada'
            }
        ]
        
    except Exception as e:
        logger.error(f"Error obteniendo log de actividad: {e}")
        return []

def get_detailed_user_stats():
    """Obtiene estadísticas detalladas de usuarios para administradores"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}
            
        cur = conn.cursor()
        
        # Estadísticas básicas existentes
        stats = get_user_stats()
        
        # Usuarios con Google OAuth vs password
        cur.execute('SELECT COUNT(*) FROM users WHERE google_id IS NOT NULL')
        google_users = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL')
        password_users = cur.fetchone()[0]
        
        # Usuarios por rol
        cur.execute('SELECT role, COUNT(*) FROM users GROUP BY role')
        role_stats = dict(cur.fetchall())
        
        # Registros por mes (últimos 6 meses)
        cur.execute('''
            SELECT 
                DATE_TRUNC('month', created_at) as month,
                COUNT(*) as registrations
            FROM users 
            WHERE created_at >= NOW() - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY month DESC
        ''')
        monthly_registrations = cur.fetchall()
        
        stats.update({
            'google_users': google_users,
            'password_users': password_users,
            'role_stats': role_stats,
            'monthly_registrations': [
                {
                    'month': row[0].strftime('%Y-%m'),
                    'registrations': row[1]
                } for row in monthly_registrations
            ]
        })
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas detalladas: {e}")
        return get_user_stats()  # Fallback a estadísticas básicas
    finally:
        if conn:
            conn.close() 

def migrate_user_timestamps():
    """Migrar usuarios existentes para agregar timestamps faltantes"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("No se pudo conectar a la base de datos para migración")
            return False
            
        cur = conn.cursor()
        
        # Verificar si existen usuarios sin created_at
        cur.execute('SELECT COUNT(*) FROM users WHERE created_at IS NULL')
        users_without_created_at = cur.fetchone()[0]
        
        if users_without_created_at > 0:
            logger.info(f"Migrando {users_without_created_at} usuarios sin fecha de creación")
            
            # Actualizar usuarios sin created_at
            cur.execute('''
                UPDATE users 
                SET created_at = NOW(), updated_at = NOW() 
                WHERE created_at IS NULL
            ''')
            
            conn.commit()
            logger.info("Migración de timestamps completada exitosamente")
        
        # Verificar si existen usuarios sin updated_at
        cur.execute('SELECT COUNT(*) FROM users WHERE updated_at IS NULL')
        users_without_updated_at = cur.fetchone()[0]
        
        if users_without_updated_at > 0:
            logger.info(f"Migrando {users_without_updated_at} usuarios sin fecha de actualización")
            
            # Actualizar usuarios sin updated_at (usar created_at si existe, sino NOW())
            cur.execute('''
                UPDATE users 
                SET updated_at = COALESCE(created_at, NOW()) 
                WHERE updated_at IS NULL
            ''')
            
            conn.commit()
            logger.info("Migración de updated_at completada exitosamente")
        
        return True
        
    except Exception as e:
        logger.error(f"Error en migración de timestamps: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def ensure_sample_data():
    """Asegurar que hay datos de prueba si la base de datos está vacía"""
    try:
        # Verificar si ya hay suficientes usuarios
        users = get_all_users()
        if len(users) >= 3:
            logger.info(f"Base de datos tiene {len(users)} usuarios - datos suficientes")
            return True
        
        logger.info("Base de datos con pocos usuarios - creando datos de prueba...")
        
        # Crear usuarios de prueba
        sample_users = [
            {
                'email': 'admin@clicandseo.com',
                'name': 'Administrador Principal',
                'password': 'admin123456',
                'role': 'admin',
                'is_active': True
            },
            {
                'email': 'usuario1@ejemplo.com',
                'name': 'María García',
                'password': 'usuario123',
                'role': 'user',
                'is_active': True
            },
            {
                'email': 'usuario2@ejemplo.com',
                'name': 'Carlos López',
                'password': 'usuario123',
                'role': 'user',
                'is_active': True
            },
            {
                'email': 'usuario3@ejemplo.com',
                'name': 'Ana Martínez',
                'password': 'usuario123',
                'role': 'user',
                'is_active': False  # Usuario inactivo para testing
            }
        ]
        
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        created_count = 0
        
        for user_data in sample_users:
            # Verificar si ya existe
            cur.execute('SELECT id FROM users WHERE email = %s', (user_data['email'],))
            if cur.fetchone():
                continue
            
            # Crear usuario
            try:
                password_hash = hash_password(user_data['password'])
                
                cur.execute('''
                    INSERT INTO users (email, name, password_hash, role, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW() - INTERVAL '%s days')
                ''', (
                    user_data['email'],
                    user_data['name'],
                    password_hash,
                    user_data['role'],
                    user_data['is_active'],
                    created_count  # Distribuir fechas
                ))
                
                created_count += 1
                logger.info(f"Usuario de prueba creado: {user_data['name']}")
                
            except Exception as e:
                logger.error(f"Error creando usuario {user_data['email']}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Se crearon {created_count} usuarios de prueba")
        return True
        
    except Exception as e:
        logger.error(f"Error creando datos de prueba: {e}")
        return False 