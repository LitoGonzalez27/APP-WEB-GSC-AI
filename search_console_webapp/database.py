# database.py - Gestión de base de datos PostgreSQL

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logging
from dotenv import load_dotenv
import hashlib
import secrets
import json

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

# Configuración de la base de datos
# Railway proporciona DATABASE_URL automáticamente en producción
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway')

# Detectar si estamos en producción
# Detección de entorno mejorada
railway_env = os.getenv('RAILWAY_ENVIRONMENT', '')
is_production = railway_env == 'production'
is_staging = railway_env == 'staging' 
is_development = not railway_env or railway_env == 'development'

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
        
        # ✅ NUEVO: Crear tabla de análisis AI Overview
        cur.execute('''
            CREATE TABLE IF NOT EXISTS ai_overview_analysis (
                id SERIAL PRIMARY KEY,
                site_url VARCHAR(255) NOT NULL,
                keyword VARCHAR(255) NOT NULL,
                analysis_date TIMESTAMP DEFAULT NOW(),
                has_ai_overview BOOLEAN DEFAULT FALSE,
                domain_is_ai_source BOOLEAN DEFAULT FALSE,
                impact_score INTEGER DEFAULT 0,
                country_code VARCHAR(3),
                keyword_word_count INTEGER,
                clicks_m1 INTEGER DEFAULT 0,
                clicks_m2 INTEGER DEFAULT 0,
                delta_clicks_absolute INTEGER DEFAULT 0,
                delta_clicks_percent DECIMAL(10,2),
                impressions_m1 INTEGER DEFAULT 0,
                impressions_m2 INTEGER DEFAULT 0,
                ctr_m1 DECIMAL(5,2),
                ctr_m2 DECIMAL(5,2),
                position_m1 DECIMAL(5,2),
                position_m2 DECIMAL(5,2),
                ai_elements_count INTEGER DEFAULT 0,
                domain_ai_source_position INTEGER,
                raw_data JSONB,
                user_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Índices para consultas rápidas de AI Overview
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_site_date ON ai_overview_analysis(site_url, analysis_date)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_keyword ON ai_overview_analysis(keyword)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_country ON ai_overview_analysis(country_code)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_user ON ai_overview_analysis(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_word_count ON ai_overview_analysis(keyword_word_count)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_has_ai ON ai_overview_analysis(has_ai_overview)')
        
        conn.commit()
        logger.info("Todas las tablas inicializadas correctamente")
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

def create_user(email, name, password=None, google_id=None, picture=None, auto_activate=True):
    """Crea un nuevo usuario en la base de datos - FASE 4.5: auto_activate=True para self-service"""
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
        
        # ✅ NUEVO FASE 4.5: Activación automática para self-service
        is_active = auto_activate  # True para SaaS, False para enterprise
        plan = 'free' if auto_activate else None  # Plan por defecto para SaaS
        
        # Verificar si las columnas de billing existen
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name IN ('plan', 'quota_limit', 'quota_used')
        """)
        billing_columns = [row['column_name'] for row in cur.fetchall()]
        has_billing_columns = len(billing_columns) >= 3
        
        if has_billing_columns:
            # Insertar con campos de billing (Fase 1 aplicada)
            cur.execute('''
                INSERT INTO users (email, name, password_hash, google_id, picture, 
                                  role, is_active, plan, quota_limit, quota_used)
                VALUES (%s, %s, %s, %s, %s, 'user', %s, %s, 0, 0)
                RETURNING id, email, name, picture, role, is_active, created_at, plan
            ''', (email, name, password_hash, google_id, picture, is_active, plan))
        else:
            # Insertar sin campos de billing (compatibilidad)
            cur.execute('''
                INSERT INTO users (email, name, password_hash, google_id, picture, role, is_active)
                VALUES (%s, %s, %s, %s, %s, 'user', %s)
                RETURNING id, email, name, picture, role, is_active, created_at
            ''', (email, name, password_hash, google_id, picture, is_active))
        
        user = cur.fetchone()
        
        if user:
            conn.commit()
            logger.info(f"Usuario creado exitosamente: {email} (activo: {is_active}, plan: {plan})")
            return dict(user)
        else:
            logger.error(f"INSERT no retornó usuario para: {email}")
            return None
        
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
    """Obtiene todos los usuarios (para administración) - INCLUYE BILLING INFO"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cur = conn.cursor()
        cur.execute('''
            SELECT 
                id, email, name, picture, role, is_active, created_at, updated_at,
                -- Billing fields
                COALESCE(plan, 'free') as plan,
                COALESCE(current_plan, plan, 'free') as current_plan,
                COALESCE(billing_status, 'active') as billing_status,
                COALESCE(quota_limit, 0) as quota_limit,
                COALESCE(quota_used, 0) as quota_used,
                quota_reset_date,
                stripe_customer_id,
                subscription_id,
                -- Custom quota fields
                custom_quota_limit,
                custom_quota_notes,
                custom_quota_assigned_by,
                custom_quota_assigned_date
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
    logger.info("🔍 INICIANDO get_user_stats() - VERSIÓN SIMPLIFICADA")
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("❌ CRÍTICO: No se pudo conectar a la base de datos")
            return {
                'total_users': 0,
                'active_users': 0,
                'inactive_users': 0,
                'today_registrations': 0,
                'week_registrations': 0
            }
        
        cur = conn.cursor()
        
        # 📊 CONSULTAS DIRECTAS Y SIMPLES
        
        # Total de usuarios
        cur.execute('SELECT COUNT(*) FROM users')
        total_users = cur.fetchone()[0]
        logger.info(f"✅ Total usuarios: {total_users}")
        
        # Usuarios activos e inactivos
        cur.execute('SELECT COUNT(*) FROM users WHERE is_active = true')
        active_users = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM users WHERE is_active = false')
        inactive_users = cur.fetchone()[0]
        
        logger.info(f"✅ Usuarios activos: {active_users}, inactivos: {inactive_users}")
        
        # Registros de hoy (solo si tienen created_at válido)
        cur.execute('''
            SELECT COUNT(*) FROM users 
            WHERE created_at IS NOT NULL 
            AND created_at::date = CURRENT_DATE
        ''')
        today_registrations = cur.fetchone()[0]
        
        # Registros de esta semana
        cur.execute('''
            SELECT COUNT(*) FROM users 
            WHERE created_at IS NOT NULL 
            AND created_at >= CURRENT_DATE - INTERVAL '7 days'
        ''')
        week_registrations = cur.fetchone()[0]
        
        logger.info(f"✅ Registros hoy: {today_registrations}, esta semana: {week_registrations}")
        
        stats = {
            'total_users': int(total_users),
            'active_users': int(active_users),
            'inactive_users': int(inactive_users),
            'today_registrations': int(today_registrations),
            'week_registrations': int(week_registrations)
        }
        
        logger.info(f"📈 Estadísticas finales: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ ERROR EN get_user_stats: {str(e)}")
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

# ====================================
# 💾 SISTEMA AI OVERVIEW ANALYSIS
# ====================================

def init_ai_overview_tables():
    """Inicializa las tablas necesarias para el análisis de AI Overview (versión independiente)"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        
        # Tabla principal de análisis AI Overview
        cur.execute('''
            CREATE TABLE IF NOT EXISTS ai_overview_analysis (
                id SERIAL PRIMARY KEY,
                site_url VARCHAR(255) NOT NULL,
                keyword VARCHAR(255) NOT NULL,
                analysis_date TIMESTAMP DEFAULT NOW(),
                has_ai_overview BOOLEAN DEFAULT FALSE,
                domain_is_ai_source BOOLEAN DEFAULT FALSE,
                impact_score INTEGER DEFAULT 0,
                country_code VARCHAR(3),
                keyword_word_count INTEGER,
                clicks_m1 INTEGER DEFAULT 0,
                clicks_m2 INTEGER DEFAULT 0,
                delta_clicks_absolute INTEGER DEFAULT 0,
                delta_clicks_percent DECIMAL(10,2),
                impressions_m1 INTEGER DEFAULT 0,
                impressions_m2 INTEGER DEFAULT 0,
                ctr_m1 DECIMAL(5,2),
                ctr_m2 DECIMAL(5,2),
                position_m1 DECIMAL(5,2),
                position_m2 DECIMAL(5,2),
                ai_elements_count INTEGER DEFAULT 0,
                domain_ai_source_position INTEGER,
                raw_data JSONB,
                user_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Índices para consultas rápidas
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_site_date ON ai_overview_analysis(site_url, analysis_date)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_keyword ON ai_overview_analysis(keyword)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_country ON ai_overview_analysis(country_code)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_user ON ai_overview_analysis(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_word_count ON ai_overview_analysis(keyword_word_count)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_has_ai ON ai_overview_analysis(has_ai_overview)')
        
        conn.commit()
        logger.info("Tablas de AI Overview Analysis inicializadas correctamente")
        return True
        
    except Exception as e:
        logger.error(f"Error inicializando tablas de AI Overview: {e}")
        return False
    finally:
        if conn:
            conn.close()

def save_ai_overview_analysis(analysis_data, user_id=None):
    """Guarda un análisis de AI Overview en la base de datos"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        saved_count = 0
        
        results = analysis_data.get('results', [])
        
        for result in results:
            try:
                # Extraer datos del resultado
                keyword = result.get('keyword', '')
                site_url = analysis_data.get('site_url', '')
                country_code = result.get('country_analyzed', '')
                
                # Calcular número de palabras en la keyword
                keyword_word_count = len(keyword.split()) if keyword else 0
                
                # Datos de AI Overview
                ai_analysis = result.get('ai_analysis', {})
                has_ai_overview = ai_analysis.get('has_ai_overview', False)
                domain_is_ai_source = ai_analysis.get('domain_is_ai_source', False)
                impact_score = ai_analysis.get('impact_score', 0)
                ai_elements_count = ai_analysis.get('total_elements', 0)
                domain_ai_source_position = ai_analysis.get('domain_ai_source_position')
                
                # Métricas de GSC
                clicks_m1 = result.get('clicks_m1', 0)
                clicks_m2 = result.get('clicks_m2', 0) 
                delta_clicks_absolute = result.get('delta_clicks_absolute', 0)
                delta_clicks_percent = result.get('delta_clicks_percent')
                impressions_m1 = result.get('impressions_m1', 0)
                impressions_m2 = result.get('impressions_m2', 0)
                ctr_m1 = result.get('ctr_m1')
                ctr_m2 = result.get('ctr_m2')
                position_m1 = result.get('position_m1')
                position_m2 = result.get('position_m2')
                
                # Datos raw como JSON
                raw_data = {
                    'ai_analysis': ai_analysis,
                    'serp_features': result.get('serp_features', []),
                    'organic_position': result.get('site_position'),
                    'timestamp': result.get('timestamp'),
                    'analysis_summary': analysis_data.get('summary', {})
                }
                
                cur.execute('''
                    INSERT INTO ai_overview_analysis (
                        site_url, keyword, has_ai_overview, domain_is_ai_source, 
                        impact_score, country_code, keyword_word_count,
                        clicks_m1, clicks_m2, delta_clicks_absolute, delta_clicks_percent,
                        impressions_m1, impressions_m2, ctr_m1, ctr_m2,
                        position_m1, position_m2, ai_elements_count,
                        domain_ai_source_position, raw_data, user_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                ''', (
                    site_url, keyword, has_ai_overview, domain_is_ai_source,
                    impact_score, country_code, keyword_word_count,
                    clicks_m1, clicks_m2, delta_clicks_absolute, delta_clicks_percent,
                    impressions_m1, impressions_m2, ctr_m1, ctr_m2,
                    position_m1, position_m2, ai_elements_count,
                    domain_ai_source_position, json.dumps(raw_data), user_id
                ))
                
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error guardando análisis para keyword '{keyword}': {e}")
                continue
        
        conn.commit()
        logger.info(f"✅ Guardados {saved_count} análisis de AI Overview en la base de datos")
        return saved_count > 0
        
    except Exception as e:
        logger.error(f"Error guardando análisis de AI Overview: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_ai_overview_stats():
    """Obtiene estadísticas generales de análisis de AI Overview"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}
            
        cur = conn.cursor()
        
        # Estadísticas básicas
        cur.execute('SELECT COUNT(*) FROM ai_overview_analysis')
        total_analyses = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM ai_overview_analysis WHERE has_ai_overview = true')
        with_ai_overview = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM ai_overview_analysis WHERE domain_is_ai_source = true')
        as_ai_source = cur.fetchone()[0]
        
        # Análisis por tipología de palabras
        cur.execute('''
            SELECT 
                CASE 
                    WHEN keyword_word_count = 1 THEN '1_termino'
                    WHEN keyword_word_count BETWEEN 2 AND 5 THEN '2_5_terminos'
                    WHEN keyword_word_count BETWEEN 6 AND 10 THEN '6_10_terminos'
                    WHEN keyword_word_count BETWEEN 11 AND 20 THEN '11_20_terminos'
                    ELSE 'mas_20_terminos'
                END as categoria,
                COUNT(*) as total,
                SUM(CASE WHEN has_ai_overview THEN 1 ELSE 0 END) as con_ai_overview
            FROM ai_overview_analysis 
            WHERE keyword_word_count > 0
            GROUP BY categoria
            ORDER BY 
                CASE categoria
                    WHEN '1_termino' THEN 1
                    WHEN '2_5_terminos' THEN 2
                    WHEN '6_10_terminos' THEN 3
                    WHEN '11_20_terminos' THEN 4
                    ELSE 5
                END
        ''')
        word_count_stats = cur.fetchall()
        
        # Países más analizados
        cur.execute('''
            SELECT country_code, COUNT(*) as total
            FROM ai_overview_analysis 
            WHERE country_code IS NOT NULL
            GROUP BY country_code
            ORDER BY total DESC
            LIMIT 10
        ''')
        country_stats = cur.fetchall()
        
        # Análisis por fecha (últimos 30 días)
        cur.execute('''
            SELECT 
                DATE(analysis_date) as fecha,
                COUNT(*) as total_analisis,
                SUM(CASE WHEN has_ai_overview THEN 1 ELSE 0 END) as con_ai_overview
            FROM ai_overview_analysis 
            WHERE analysis_date >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(analysis_date)
            ORDER BY fecha DESC
        ''')
        daily_stats = cur.fetchall()
        
        return {
            'total_analyses': total_analyses,
            'with_ai_overview': with_ai_overview,
            'as_ai_source': as_ai_source,
            'ai_overview_percentage': round((with_ai_overview / total_analyses * 100), 2) if total_analyses > 0 else 0,
            'word_count_stats': [
                {
                    'categoria': row[0],
                    'total': row[1],
                    'con_ai_overview': row[2],
                    'porcentaje_ai': round((row[2] / row[1] * 100), 2) if row[1] > 0 else 0
                }
                for row in word_count_stats
            ],
            'country_stats': [{'country': row[0], 'total': row[1]} for row in country_stats],
            'daily_stats': [
                {
                    'fecha': row[0].strftime('%Y-%m-%d'),
                    'total_analisis': row[1],
                    'con_ai_overview': row[2]
                }
                for row in daily_stats
            ]
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de AI Overview: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def get_ai_overview_history(site_url=None, keyword=None, days=30, limit=100):
    """Obtiene el historial de análisis de AI Overview"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cur = conn.cursor()
        
        query = '''
            SELECT 
                id, site_url, keyword, analysis_date, has_ai_overview,
                domain_is_ai_source, impact_score, country_code, keyword_word_count,
                clicks_m1, clicks_m2, delta_clicks_absolute, ai_elements_count
            FROM ai_overview_analysis 
            WHERE analysis_date >= NOW() - INTERVAL '%s days'
        '''
        params = [days]
        
        if site_url:
            query += ' AND site_url = %s'
            params.append(site_url)
            
        if keyword:
            query += ' AND keyword ILIKE %s'
            params.append(f'%{keyword}%')
        
        query += ' ORDER BY analysis_date DESC LIMIT %s'
        params.append(limit)
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        return [dict(row) for row in results]
        
    except Exception as e:
        logger.error(f"Error obteniendo historial de AI Overview: {e}")
        return []
    finally:
        if conn:
            conn.close()

# ====================================
# 📊 SISTEMA DE TRACKING DE CONSUMO
# ====================================

def track_quota_consumption(user_id, ru_consumed, source, keyword=None, country_code=None, metadata=None):
    """
    Registra el consumo de RU (Recursos Únicos) de un usuario
    
    Args:
        user_id (int): ID del usuario que consume RU
        ru_consumed (int): Cantidad de RU consumidas (típicamente 1 por keyword)
        source (str): Fuente del consumo ('ai_overview', 'manual_ai', 'serp_api')
        keyword (str, optional): Keyword analizada
        country_code (str, optional): Código del país
        metadata (dict, optional): Datos adicionales del análisis
    
    Returns:
        bool: True si se registró correctamente, False si hubo error
    """
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("No se pudo conectar a la base de datos para tracking")
            return False
            
        cur = conn.cursor()
        
        # 1. Registrar evento en quota_usage_events
        cur.execute('''
            INSERT INTO quota_usage_events (
                user_id, ru_consumed, source, keyword, country_code, metadata, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ''', (
            user_id,
            ru_consumed,
            source,
            keyword,
            country_code,
            json.dumps(metadata) if metadata else None
        ))
        
        # 2. Actualizar quota_used en users
        cur.execute('''
            UPDATE users 
            SET 
                quota_used = COALESCE(quota_used, 0) + %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (ru_consumed, user_id))
        
        # 3. Verificar que el usuario fue actualizado
        if cur.rowcount == 0:
            logger.warning(f"Usuario {user_id} no encontrado para actualizar quota")
            conn.rollback()
            return False
        
        conn.commit()
        
        # Log de éxito
        logger.info(f"✅ Quota tracking - Usuario {user_id}: +{ru_consumed} RU ({source})")
        if keyword:
            logger.info(f"   📝 Keyword: {keyword}")
        if country_code:
            logger.info(f"   🌍 País: {country_code}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en track_quota_consumption: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_user_quota_usage(user_id, days=30):
    """
    Obtiene el uso de quota de un usuario en los últimos N días
    
    Args:
        user_id (int): ID del usuario
        days (int): Días hacia atrás para consultar (default: 30)
    
    Returns:
        dict: Estadísticas de uso de quota
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {}
            
        cur = conn.cursor()
        
        # Uso total en el período
        cur.execute('''
            SELECT 
                COALESCE(SUM(ru_consumed), 0) as total_ru,
                COUNT(*) as total_events,
                COUNT(DISTINCT source) as sources_used,
                MAX(timestamp) as last_usage
            FROM quota_usage_events 
            WHERE user_id = %s AND timestamp >= NOW() - INTERVAL '%s days'
        ''', (user_id, days))
        
        stats = cur.fetchone()
        
        # Uso por fuente
        cur.execute('''
            SELECT 
                source,
                COALESCE(SUM(ru_consumed), 0) as ru_consumed,
                COUNT(*) as events_count
            FROM quota_usage_events 
            WHERE user_id = %s AND timestamp >= NOW() - INTERVAL '%s days'
            GROUP BY source
            ORDER BY ru_consumed DESC
        ''', (user_id, days))
        
        usage_by_source = [dict(row) for row in cur.fetchall()]
        
        # Uso diario (últimos 7 días)
        cur.execute('''
            SELECT 
                DATE(timestamp) as date,
                COALESCE(SUM(ru_consumed), 0) as daily_ru
            FROM quota_usage_events 
            WHERE user_id = %s AND timestamp >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        ''', (user_id,))
        
        daily_usage = [dict(row) for row in cur.fetchall()]
        
        return {
            'period_days': days,
            'total_ru': stats['total_ru'],
            'total_events': stats['total_events'],
            'sources_used': stats['sources_used'],
            'last_usage': stats['last_usage'],
            'usage_by_source': usage_by_source,
            'daily_usage': daily_usage
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo uso de quota para usuario {user_id}: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def ensure_quota_table_exists():
    """
    Asegura que la tabla quota_usage_events existe
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        
        # Crear tabla si no existe
        cur.execute('''
            CREATE TABLE IF NOT EXISTS quota_usage_events (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                ru_consumed INTEGER DEFAULT 1,
                source VARCHAR(50),
                keyword VARCHAR(255),
                country_code VARCHAR(3),
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                metadata JSONB,
                
                -- Constraints
                CONSTRAINT chk_ru_consumed CHECK (ru_consumed > 0),
                CONSTRAINT chk_source CHECK (source IN ('ai_overview', 'manual_ai', 'serp_api'))
            )
        ''')
        
        # Crear índices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_quota_events_user_date ON quota_usage_events(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_quota_events_source ON quota_usage_events(source)",
            "CREATE INDEX IF NOT EXISTS idx_quota_events_timestamp ON quota_usage_events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_quota_events_user_month ON quota_usage_events(user_id, DATE_TRUNC('month', timestamp))"
        ]
        
        for index_sql in indices:
            try:
                cur.execute(index_sql)
            except Exception:
                pass  # Index might already exist
        
        conn.commit()
        logger.info("✅ Tabla quota_usage_events verificada/creada")
        return True
        
    except Exception as e:
        logger.error(f"Error creando tabla quota_usage_events: {e}")
        return False
    finally:
        if conn:
            conn.close() 