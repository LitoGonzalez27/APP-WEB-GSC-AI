# database.py - Gestión de base de datos PostgreSQL

import os
import time
import psycopg2
from psycopg2 import errorcodes
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import hashlib
import secrets
import json
from typing import Optional, List, Dict, Any

# Cifrado opcional de tokens
try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None  # type: ignore

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

# Configuración de la base de datos
# Railway proporciona DATABASE_URL automáticamente en producción
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada en el entorno")

# Detectar si estamos en producción
# Detección de entorno mejorada
railway_env = os.getenv('RAILWAY_ENVIRONMENT', '')
is_production = railway_env == 'production'
is_staging = railway_env == 'staging' 
is_development = not railway_env or railway_env == 'development'

def get_db_connection():
    """Obtiene una conexión a la base de datos PostgreSQL.

    Hardening (añadido 2026-04-08 tras incidente de zombies idle-in-transaction):
    - idle_in_transaction_session_timeout=900000 (15 min): Postgres aborta
      automáticamente cualquier conexión que mantenga una transacción
      `idle in transaction` más de 15 min. Previene que futuros bugs o
      SIGTERMs dejen transacciones colgadas acumulándose en la BD.
    - connect_timeout=10: fallar rápido si la BD está inalcanzable.
    - TCP keepalives: detectar conexiones muertas en ~80 segundos en vez
      del default del kernel (~2 horas). Útil cuando Railway u otros
      reverse proxies cortan conexiones sin notificar.

    Todos los parámetros son aditivos — el comportamiento funcional de la
    conexión no cambia, sólo las salvaguardas.
    """
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            options='-c idle_in_transaction_session_timeout=900000',
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
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

        # ✅ NUEVO: Asegurar columna last_login_at para tracking de último acceso
        try:
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP NULL")
        except Exception:
            pass

        # ================================
        # Tablas para conexiones OAuth y propiedades GSC
        # ================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS oauth_connections (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL DEFAULT 'google',
                google_account_id TEXT,
                google_email TEXT,
                access_token TEXT,
                refresh_token_encrypted TEXT NOT NULL,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (user_id, provider, google_account_id)
            )
        ''')

        cur.execute('CREATE INDEX IF NOT EXISTS idx_oauth_connections_user ON oauth_connections(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_oauth_connections_provider ON oauth_connections(provider)')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS gsc_properties (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                connection_id INTEGER REFERENCES oauth_connections(id) ON DELETE CASCADE,
                site_url TEXT NOT NULL,
                permission_level TEXT,
                verified BOOLEAN,
                last_seen TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (user_id, site_url)
            )
        ''')

        cur.execute('CREATE INDEX IF NOT EXISTS idx_gsc_props_user ON gsc_properties(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_gsc_props_conn ON gsc_properties(connection_id)')
        
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
        
        # Crear tabla password reset tokens
        cur.execute('''
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Crear índices para la tabla de reset tokens
        cur.execute('CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_password_reset_user_id ON password_reset_tokens(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_password_reset_expires ON password_reset_tokens(expires_at)')

        # ================================
        # Tablas para LLM Monitoring Analysis Lock & Runs
        # ================================

        # Singleton lock para prevenir análisis concurrentes
        cur.execute('''
            CREATE TABLE IF NOT EXISTS llm_monitoring_analysis_lock (
                id INTEGER PRIMARY KEY DEFAULT 1,
                is_running BOOLEAN DEFAULT FALSE,
                started_at TIMESTAMP,
                started_by TEXT,
                CONSTRAINT single_row CHECK (id = 1)
            )
        ''')
        # Insertar la fila singleton si no existe
        cur.execute('''
            INSERT INTO llm_monitoring_analysis_lock (id, is_running)
            VALUES (1, FALSE)
            ON CONFLICT (id) DO NOTHING
        ''')

        # Historial de ejecuciones de análisis
        cur.execute('''
            CREATE TABLE IF NOT EXISTS llm_monitoring_analysis_runs (
                id SERIAL PRIMARY KEY,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                status TEXT DEFAULT 'running',
                total_projects INTEGER DEFAULT 0,
                successful_projects INTEGER DEFAULT 0,
                failed_projects INTEGER DEFAULT 0,
                total_queries INTEGER DEFAULT 0,
                error_message TEXT,
                triggered_by TEXT DEFAULT 'cron'
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON llm_monitoring_analysis_runs(status)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_analysis_runs_started ON llm_monitoring_analysis_runs(started_at DESC)')

        # ── Migración: Google → Gemini 3 Flash (2026-03-04) ──
        # Asegurar que gemini-3-flash-preview exista y sea el modelo current
        cur.execute("""
            INSERT INTO llm_model_registry (
                llm_provider, model_id, model_display_name,
                cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                is_current, is_available
            ) VALUES (
                'google', 'gemini-3-flash-preview', 'Gemini 3 Flash',
                0.50, 3.00, FALSE, TRUE
            )
            ON CONFLICT (llm_provider, model_id) DO UPDATE SET
                model_display_name = 'Gemini 3 Flash',
                cost_per_1m_input_tokens = 0.50,
                cost_per_1m_output_tokens = 3.00,
                is_available = TRUE,
                updated_at = NOW()
        """)
        # Quitar is_current de todos los modelos Google
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = FALSE, updated_at = NOW()
            WHERE llm_provider = 'google'
        """)
        # Marcar Flash como current
        cur.execute("""
            UPDATE llm_model_registry
            SET is_current = TRUE, updated_at = NOW()
            WHERE llm_provider = 'google' AND model_id = 'gemini-3-flash-preview'
        """)
        logger.info("✅ Google model migrado a gemini-3-flash-preview")

        # ── Admin Audit Log ──
        cur.execute('''
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id SERIAL PRIMARY KEY,
                admin_user_id INTEGER REFERENCES users(id),
                action TEXT NOT NULL,
                target_user_id INTEGER,
                details JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit_log(created_at DESC)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_admin_audit_target ON admin_audit_log(target_user_id)')

        conn.commit()
        logger.info("Todas las tablas inicializadas correctamente")
        return True
        
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ================================
# Utilidades de cifrado de tokens
# ================================

def _get_fernet() -> Optional["Fernet"]:
    try:
        if Fernet is None:
            return None
        key = os.getenv('TOKEN_ENCRYPTION_KEY', '').strip()
        if not key:
            return None
        # Permitir clave sin base64 padding
        return Fernet(key)
    except Exception as e:
        logger.warning(f"TOKEN_ENCRYPTION_KEY inválida o no disponible: {e}")
        return None

def _encrypt(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    f = _get_fernet()
    if not f:
        return text
    try:
        return f.encrypt(text.encode('utf-8')).decode('utf-8')
    except Exception:
        return text

def _decrypt(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    f = _get_fernet()
    if not f:
        return text
    try:
        return f.decrypt(text.encode('utf-8')).decode('utf-8')
    except Exception:
        return text

# ================================
# Funciones para conexiones OAuth
# ================================

def create_or_update_oauth_connection(user_id: int, google_account_id: str, google_email: str, creds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Crea o actualiza una conexión OAuth de Google para un usuario.
    Almacena de forma segura el refresh_token (cifrado si hay clave).
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()

        refresh_token = creds.get('refresh_token')
        token = creds.get('token')
        token_uri = creds.get('token_uri')
        client_id = creds.get('client_id')
        client_secret = creds.get('client_secret')
        scopes = creds.get('scopes')
        expires_at = None
        # Algunas libs pasan expiry como datetime o seconds; aceptar ambos via creds.get('expiry')
        expiry = creds.get('expiry') or creds.get('expires_at')
        if expiry and isinstance(expiry, str):
            try:
                # Intento simple: ISO
                from datetime import datetime as _dt
                expires_at = _dt.fromisoformat(expiry)
            except Exception:
                expires_at = None
        elif expiry:
            expires_at = expiry

        # ¿Existe conexión?
        cur.execute('''
            SELECT id FROM oauth_connections 
            WHERE user_id = %s AND provider = 'google' AND google_account_id = %s
        ''', (user_id, google_account_id))
        existing = cur.fetchone()

        if existing:
            connection_id = existing['id']
            cur.execute('''
                UPDATE oauth_connections
                SET google_email = %s,
                    access_token = %s,
                    refresh_token_encrypted = %s,
                    token_uri = %s,
                    client_id = %s,
                    client_secret = %s,
                    scopes = %s,
                    expires_at = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
            ''', (
                google_email,
                token,
                _encrypt(refresh_token),
                token_uri,
                client_id,
                client_secret,
                json.dumps(scopes) if isinstance(scopes, (list, dict)) else (scopes or None),
                expires_at,
                connection_id
            ))
        else:
            cur.execute('''
                INSERT INTO oauth_connections (
                    user_id, provider, google_account_id, google_email,
                    access_token, refresh_token_encrypted, token_uri,
                    client_id, client_secret, scopes, expires_at
                ) VALUES (
                    %s, 'google', %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s
                ) RETURNING *
            ''', (
                user_id, google_account_id, google_email,
                token, _encrypt(refresh_token), token_uri,
                client_id, client_secret,
                json.dumps(scopes) if isinstance(scopes, (list, dict)) else (scopes or None),
                expires_at
            ))

        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error creando/actualizando conexión OAuth: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_oauth_connections_for_user(user_id: int) -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute('''
            SELECT * FROM oauth_connections 
            WHERE user_id = %s AND provider = 'google'
            ORDER BY created_at DESC
        ''', (user_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error obteniendo conexiones OAuth: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_oauth_connection_by_id(connection_id: int) -> Optional[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute('SELECT * FROM oauth_connections WHERE id = %s', (connection_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error obteniendo conexión OAuth por id: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_oauth_connection_tokens(connection_id: int, token: Optional[str], refresh_token: Optional[str], expires_at=None) -> bool:
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cur = conn.cursor()
        if refresh_token:
            cur.execute('''
                UPDATE oauth_connections
                SET access_token = %s,
                    refresh_token_encrypted = %s,
                    expires_at = %s,
                    updated_at = NOW()
                WHERE id = %s
            ''', (token, _encrypt(refresh_token), expires_at, connection_id))
        else:
            cur.execute('''
                UPDATE oauth_connections
                SET access_token = %s,
                    expires_at = %s,
                    updated_at = NOW()
                WHERE id = %s
            ''', (token, expires_at, connection_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Error actualizando tokens de conexión OAuth: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ================================
# Funciones para propiedades de GSC
# ================================

def upsert_gsc_properties_for_connection(user_id: int, connection_id: int, site_entries: List[Dict[str, Any]]) -> int:
    """Inserta/actualiza propiedades de GSC para una conexión. Retorna cantidad procesada."""
    try:
        if not site_entries:
            return 0
        conn = get_db_connection()
        if not conn:
            return 0
        cur = conn.cursor()
        processed = 0
        for s in site_entries:
            site_url = s.get('siteUrl') or s.get('site_url')
            if not site_url:
                continue
            permission_level = s.get('permissionLevel') or s.get('permission_level')
            verified = None
            # Heurística: si tiene permissionLevel, considerarlo verificado
            if permission_level:
                verified = True
            cur.execute('''
                INSERT INTO gsc_properties (user_id, connection_id, site_url, permission_level, verified, last_seen)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, site_url)
                DO UPDATE SET connection_id = EXCLUDED.connection_id,
                              permission_level = COALESCE(EXCLUDED.permission_level, gsc_properties.permission_level),
                              verified = COALESCE(EXCLUDED.verified, gsc_properties.verified),
                              last_seen = NOW(),
                              updated_at = NOW()
            ''', (user_id, connection_id, site_url, permission_level, verified))
            processed += 1
        conn.commit()
        return processed
    except Exception as e:
        logger.error(f"Error upsert de propiedades GSC: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def list_gsc_properties_for_user(user_id: int) -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute('''
            SELECT p.id, p.site_url, p.permission_level, p.verified, p.connection_id,
                   c.google_email, c.google_account_id
            FROM gsc_properties p
            JOIN oauth_connections c ON c.id = p.connection_id
            WHERE p.user_id = %s
            ORDER BY p.site_url
        ''', (user_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error listando propiedades GSC: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_connection_for_site(user_id: int, site_url: str) -> Optional[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute('''
            SELECT c.* FROM gsc_properties p
            JOIN oauth_connections c ON c.id = p.connection_id
            WHERE p.user_id = %s AND p.site_url = %s
            LIMIT 1
        ''', (user_id, site_url))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error obteniendo conexión para site_url: {e}")
        return None
    finally:
        if conn:
            conn.close()

def user_owns_site_url(user_id: int, site_url: str) -> bool:
    """Valida si el usuario es dueño del site_url (GSC o análisis previo)."""
    if not site_url:
        return False
    try:
        from services.utils import normalize_search_console_url
        normalized = normalize_search_console_url(site_url)
    except Exception:
        normalized = site_url

    try:
        conn = get_db_connection()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute('''
            SELECT 1
            FROM gsc_properties
            WHERE user_id = %s
              AND (site_url = %s OR site_url = %s)
            LIMIT 1
        ''', (user_id, site_url, normalized))
        row = cur.fetchone()
        if row:
            return True

        cur.execute('''
            SELECT 1
            FROM ai_overview_analysis
            WHERE user_id = %s
              AND (site_url = %s OR site_url = %s)
            LIMIT 1
        ''', (user_id, site_url, normalized))
        return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Error validando ownership de site_url: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ================================
# Funciones para Password Reset
# ================================

def create_password_reset_token(user_id: int) -> Optional[str]:
    """Crea un token de reset de contraseña para un usuario"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor()
        
        # Generar token único
        token = secrets.token_urlsafe(32)
        
        # Token expira en 1 hora
        expires_at = datetime.now() + timedelta(hours=1)
        
        # Invalidar tokens existentes no usados del usuario
        cur.execute('''
            UPDATE password_reset_tokens 
            SET used_at = NOW() 
            WHERE user_id = %s AND used_at IS NULL
        ''', (user_id,))
        
        # Crear nuevo token
        cur.execute('''
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
            RETURNING token
        ''', (user_id, token, expires_at))
        
        result = cur.fetchone()
        conn.commit()
        
        return result['token'] if result else None
        
    except Exception as e:
        logger.error(f"Error creando token de reset: {e}")
        return None
    finally:
        if conn:
            conn.close()

def validate_password_reset_token(token: str) -> Optional[Dict[str, Any]]:
    """Valida un token de reset de contraseña y retorna información del usuario"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor()
        
        # Buscar token válido (no usado y no expirado)
        cur.execute('''
            SELECT prt.id as token_id, prt.user_id, prt.expires_at,
                   u.email, u.name
            FROM password_reset_tokens prt
            JOIN users u ON u.id = prt.user_id
            WHERE prt.token = %s 
            AND prt.used_at IS NULL 
            AND prt.expires_at > NOW()
        ''', (token,))
        
        result = cur.fetchone()
        return dict(result) if result else None
        
    except Exception as e:
        logger.error(f"Error validando token de reset: {e}")
        return None
    finally:
        if conn:
            conn.close()

def use_password_reset_token(token: str, new_password: str) -> bool:
    """Usa un token de reset para cambiar la contraseña del usuario"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        # Verificar token válido
        token_info = validate_password_reset_token(token)
        if not token_info:
            return False
        
        user_id = token_info['user_id']
        
        # Hashear nueva contraseña
        new_password_hash = hash_password(new_password)
        
        # Actualizar contraseña del usuario
        cur.execute('''
            UPDATE users 
            SET password_hash = %s, updated_at = NOW()
            WHERE id = %s
        ''', (new_password_hash, user_id))
        
        # Marcar token como usado
        cur.execute('''
            UPDATE password_reset_tokens 
            SET used_at = NOW()
            WHERE token = %s
        ''', (token,))
        
        conn.commit()
        
        logger.info(f"Contraseña reseteada exitosamente para usuario {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error usando token de reset: {e}")
        return False
    finally:
        if conn:
            conn.close()

def cleanup_expired_reset_tokens():
    """Limpia tokens de reset expirados (para ejecutar periódicamente)"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        # Eliminar tokens expirados
        cur.execute('''
            DELETE FROM password_reset_tokens 
            WHERE expires_at < NOW() - INTERVAL '1 day'
        ''')
        
        deleted_count = cur.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info(f"Limpiados {deleted_count} tokens de reset expirados")
        
        return True
        
    except Exception as e:
        logger.error(f"Error limpiando tokens expirados: {e}")
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
        
        if not user:
            return None
        user_dict = dict(user)
        # Normalizar is_active cuando sea NULL → True (backward-compat)
        if user_dict.get('is_active') is None:
            user_dict['is_active'] = True
        return user_dict
        
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
        
        if not user:
            return None
        user_dict = dict(user)
        if user_dict.get('is_active') is None:
            user_dict['is_active'] = True
        return user_dict
        
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
        
        if not user:
            return None
        user_dict = dict(user)
        if user_dict.get('is_active') is None:
            user_dict['is_active'] = True
        return user_dict
        
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
                id, email, name, picture, role,
                COALESCE(is_active, TRUE) as is_active,
                created_at, updated_at, last_login_at,
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

        def table_exists(tbl: str) -> bool:
            try:
                cur.execute("SELECT to_regclass(%s) AS reg", (f"public.{tbl}",))
                row = cur.fetchone()
                return bool(row['reg'] if isinstance(row, dict) else row[0])
            except Exception:
                return False

        def safe_delete(sql: str, params: tuple, savepoint_name: str) -> None:
            try:
                cur.execute(f"SAVEPOINT {savepoint_name}")
                cur.execute(sql, params)
                cur.execute(f"RELEASE SAVEPOINT {savepoint_name}")
            except Exception as e:
                # Revertir solo esta operación y continuar
                try:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    cur.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                except Exception:
                    pass
                logger.warning(f"delete_user: omitiendo error en '{savepoint_name}': {e}")

        # Eliminar dependencias en orden seguro (algunas tablas no tienen ON DELETE CASCADE)
        if table_exists('ai_overview_analysis'):
            safe_delete('DELETE FROM ai_overview_analysis WHERE user_id = %s', (user_id,), 'sp_ai_overview')

        if table_exists('quota_usage_events'):
            safe_delete('DELETE FROM quota_usage_events WHERE user_id = %s', (user_id,), 'sp_quota_events')

        if table_exists('password_reset_tokens'):
            safe_delete('DELETE FROM password_reset_tokens WHERE user_id = %s', (user_id,), 'sp_reset_tokens')

        if table_exists('manual_ai_projects'):
            safe_delete('DELETE FROM manual_ai_projects WHERE user_id = %s', (user_id,), 'sp_manual_ai_projects')

        if table_exists('gsc_properties'):
            safe_delete('DELETE FROM gsc_properties WHERE user_id = %s', (user_id,), 'sp_gsc_props')

        if table_exists('oauth_connections'):
            safe_delete('DELETE FROM oauth_connections WHERE user_id = %s', (user_id,), 'sp_oauth_conns')

        if table_exists('subscriptions'):
            safe_delete('DELETE FROM subscriptions WHERE user_id = %s', (user_id,), 'sp_subs')

        # Finalmente, eliminar el usuario
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
        
        # Usuarios activos e inactivos (tratar NULL como TRUE para compatibilidad)
        cur.execute('SELECT COUNT(*) FROM users WHERE COALESCE(is_active, TRUE) = TRUE')
        active_users = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM users WHERE COALESCE(is_active, TRUE) = FALSE')
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

        # Fix #2: Add aio_serp_position column (top/middle/bottom)
        try:
            cur.execute("ALTER TABLE ai_overview_analysis ADD COLUMN IF NOT EXISTS aio_serp_position VARCHAR(10)")
        except Exception:
            pass  # Column may already exist

        # Fix #3: Unique index for UPSERT — one row per (site, keyword, country, date, user)
        # First, check if the index already exists to avoid re-deduplicating
        cur.execute("""
            SELECT 1 FROM pg_indexes
            WHERE indexname = 'idx_ai_analysis_upsert'
        """)
        if not cur.fetchone():
            # Deduplicate existing data: keep only the most recent row per unique key
            logger.info("Deduplicating ai_overview_analysis before creating unique index...")
            cur.execute('''
                DELETE FROM ai_overview_analysis a
                USING ai_overview_analysis b
                WHERE a.id < b.id
                  AND a.site_url = b.site_url
                  AND a.keyword = b.keyword
                  AND COALESCE(a.country_code, '') = COALESCE(b.country_code, '')
                  AND CAST(a.analysis_date AS DATE) = CAST(b.analysis_date AS DATE)
                  AND COALESCE(a.user_id, 0) = COALESCE(b.user_id, 0)
            ''')
            deduped = cur.rowcount
            logger.info(f"Removed {deduped} duplicate rows from ai_overview_analysis")
            conn.commit()

            # Now create the unique index
            cur.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_analysis_upsert
                ON ai_overview_analysis(
                    site_url, keyword, COALESCE(country_code, ''),
                    CAST(analysis_date AS DATE), COALESCE(user_id, 0)
                )
            ''')

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
    """Guarda un análisis de AI Overview en la base de datos (UPSERT: actualiza si ya existe hoy)"""
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
                aio_serp_position = ai_analysis.get('aio_serp_position')  # Fix #2

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

                # Fix #3: UPSERT — delete existing row for same day, then insert
                # This is safer than ON CONFLICT with expression indexes
                cur.execute('''
                    DELETE FROM ai_overview_analysis
                    WHERE site_url = %s
                      AND keyword = %s
                      AND COALESCE(country_code, '') = COALESCE(%s, '')
                      AND CAST(analysis_date AS DATE) = CURRENT_DATE
                      AND COALESCE(user_id, 0) = COALESCE(%s, 0)
                ''', (site_url, keyword, country_code, user_id))

                cur.execute('''
                    INSERT INTO ai_overview_analysis (
                        site_url, keyword, has_ai_overview, domain_is_ai_source,
                        impact_score, country_code, keyword_word_count,
                        clicks_m1, clicks_m2, delta_clicks_absolute, delta_clicks_percent,
                        impressions_m1, impressions_m2, ctr_m1, ctr_m2,
                        position_m1, position_m2, ai_elements_count,
                        domain_ai_source_position, aio_serp_position, raw_data, user_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                ''', (
                    site_url, keyword, has_ai_overview, domain_is_ai_source,
                    impact_score, country_code, keyword_word_count,
                    clicks_m1, clicks_m2, delta_clicks_absolute, delta_clicks_percent,
                    impressions_m1, impressions_m2, ctr_m1, ctr_m2,
                    position_m1, position_m2, ai_elements_count,
                    domain_ai_source_position, aio_serp_position, json.dumps(raw_data), user_id
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

def track_quota_consumption(user_id, ru_consumed, source, keyword=None, country_code=None, metadata=None, update_user_quota=True):
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
    max_attempts = int(os.getenv('DB_RETRY_ATTEMPTS', '3'))
    base_delay = float(os.getenv('DB_RETRY_BACKOFF_SECONDS', '0.5'))
    
    for attempt in range(1, max_attempts + 1):
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                logger.error("No se pudo conectar a la base de datos para tracking")
                return False
                
            cur = conn.cursor()
            # Asegurar existencia de tabla quota_usage_events antes de insertar
            try:
                cur.execute("SELECT to_regclass('public.quota_usage_events') AS reg")
                row = cur.fetchone()
                if not (row['reg'] if isinstance(row, dict) else row[0]):
                    ensure_quota_table_exists()
            except Exception:
                try:
                    ensure_quota_table_exists()
                except Exception:
                    pass
            
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
            
            # 2. Actualizar quota_used en users (opcional)
            if update_user_quota:
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
            retryable = getattr(e, 'pgcode', None) in (
                errorcodes.DEADLOCK_DETECTED,
                errorcodes.SERIALIZATION_FAILURE,
            )
            logger.error(f"❌ Error en track_quota_consumption: {e}")
            if conn:
                conn.rollback()
            if retryable and attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"🔁 Reintentando operación DB en {delay:.1f}s (intento {attempt}/{max_attempts})")
                time.sleep(delay)
                continue
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


def get_user_llm_monthly_cost(user_id, month_date=None):
    """
    Devuelve el coste mensual LLM (USD) para un usuario.
    Se calcula desde llm_monitoring_results.
    """
    try:
        from datetime import date as _date
        month_date = month_date or _date.today()
        month_start = month_date.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)

        conn = get_db_connection()
        if not conn:
            return 0.0
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.llm_monitoring_results') AS reg")
        row = cur.fetchone()
        if not (row['reg'] if isinstance(row, dict) else row[0]):
            return 0.0

        cur.execute("""
            SELECT COALESCE(SUM(r.cost_usd), 0) AS total_cost
            FROM llm_monitoring_results r
            JOIN llm_monitoring_projects p ON p.id = r.project_id
            WHERE p.user_id = %s
              AND r.analysis_date >= %s
              AND r.analysis_date < %s
        """, (user_id, month_start, next_month))
        result = cur.fetchone()
        return float(result['total_cost']) if result and result['total_cost'] is not None else 0.0
    except Exception as e:
        logger.error(f"Error obteniendo coste mensual LLM para usuario {user_id}: {e}")
        return 0.0
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


# ====================================
# ⏸️ PAUSAS POR CUOTA (AI Overview / AI Mode / LLM)
# ====================================

def pause_ai_overview_for_quota(user_id, paused_until=None, reason="quota_exceeded"):
    """Pausa AI Overview para un usuario hasta la fecha indicada."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute('''
            UPDATE users
            SET ai_overview_paused_until = %s,
                ai_overview_paused_at = NOW(),
                ai_overview_paused_reason = %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (paused_until, reason, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error pausando AI Overview para user {user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def pause_ai_mode_projects_for_quota(user_id, paused_until=None, reason="quota_exceeded"):
    """Pausa proyectos AI Mode activos del usuario por cuota."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute('''
            UPDATE ai_mode_projects
            SET is_paused_by_quota = TRUE,
                paused_until = %s,
                paused_at = NOW(),
                paused_reason = %s,
                updated_at = NOW()
            WHERE user_id = %s
              AND is_active = TRUE
        ''', (paused_until, reason, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error pausando AI Mode para user {user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def pause_llm_projects_for_quota(user_id, paused_until=None, reason="quota_exceeded"):
    """Pausa proyectos LLM Monitoring activos del usuario por cuota."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute('''
            UPDATE llm_monitoring_projects
            SET is_paused_by_quota = TRUE,
                paused_until = %s,
                paused_at = NOW(),
                paused_reason = %s,
                updated_at = NOW()
            WHERE user_id = %s
              AND is_active = TRUE
        ''', (paused_until, reason, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error pausando LLM Monitoring para user {user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def pause_manual_ai_projects_for_quota(user_id, paused_until=None, reason="quota_exceeded"):
    """Pausa proyectos Manual AI activos del usuario por cuota."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute('''
            UPDATE manual_ai_projects
            SET is_paused_by_quota = TRUE,
                paused_until = %s,
                paused_at = NOW(),
                paused_reason = %s,
                updated_at = NOW()
            WHERE user_id = %s
              AND is_active = TRUE
        ''', (paused_until, reason, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error pausando Manual AI para user {user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def resume_quota_pauses_for_user(user_id):
    """Rehabilita módulos pausados por cuota tras nuevo ciclo de pago."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cur = conn.cursor()

        cur.execute('''
            UPDATE users
            SET ai_overview_paused_until = NULL,
                ai_overview_paused_at = NULL,
                ai_overview_paused_reason = NULL,
                updated_at = NOW()
            WHERE id = %s
        ''', (user_id,))

        cur.execute('''
            UPDATE ai_mode_projects
            SET is_paused_by_quota = FALSE,
                paused_until = NULL,
                paused_at = NULL,
                paused_reason = NULL,
                updated_at = NOW()
            WHERE user_id = %s
        ''', (user_id,))

        cur.execute('''
            UPDATE llm_monitoring_projects
            SET is_paused_by_quota = FALSE,
                paused_until = NULL,
                paused_at = NULL,
                paused_reason = NULL,
                updated_at = NOW()
            WHERE user_id = %s
        ''', (user_id,))

        try:
            cur.execute('''
                UPDATE manual_ai_projects
                SET is_paused_by_quota = FALSE,
                    paused_until = NULL,
                    paused_at = NULL,
                    paused_reason = NULL,
                    updated_at = NOW()
                WHERE user_id = %s
            ''', (user_id,))
        except Exception as manual_resume_exc:
            # Tolerate older deployments where the migration has not run yet.
            logger.warning(
                f"Manual AI quota-resume skipped for user {user_id}: {manual_resume_exc}"
            )
            conn.rollback()
            # Re-run the previous statements that succeeded so we still commit them.
            cur.execute('''
                UPDATE users
                SET ai_overview_paused_until = NULL,
                    ai_overview_paused_at = NULL,
                    ai_overview_paused_reason = NULL,
                    updated_at = NOW()
                WHERE id = %s
            ''', (user_id,))
            cur.execute('''
                UPDATE ai_mode_projects
                SET is_paused_by_quota = FALSE,
                    paused_until = NULL,
                    paused_at = NULL,
                    paused_reason = NULL,
                    updated_at = NOW()
                WHERE user_id = %s
            ''', (user_id,))
            cur.execute('''
                UPDATE llm_monitoring_projects
                SET is_paused_by_quota = FALSE,
                    paused_until = NULL,
                    paused_at = NULL,
                    paused_reason = NULL,
                    updated_at = NOW()
                WHERE user_id = %s
            ''', (user_id,))

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error rehabilitando pausas por cuota para user {user_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


# ====================================
# 🔒 ANALYSIS LOCK & RUN TRACKING
# ====================================

def acquire_analysis_lock(triggered_by: str = 'cron', stale_timeout_minutes: int = 30) -> Optional[int]:
    """
    Intenta adquirir el lock de análisis.

    Si el lock está libre, lo toma y crea un run en llm_monitoring_analysis_runs.
    Si el lock está tomado pero lleva más de stale_timeout_minutes, lo fuerza (crash recovery).
    Si el lock está tomado y es reciente, retorna None (análisis en curso).

    Returns:
        run_id (int) si se adquirió el lock, None si ya hay un análisis en curso.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()

        # Asegurar que la tabla y fila singleton existen
        cur.execute('''
            CREATE TABLE IF NOT EXISTS llm_monitoring_analysis_lock (
                id INTEGER PRIMARY KEY DEFAULT 1,
                is_running BOOLEAN DEFAULT FALSE,
                started_at TIMESTAMP,
                started_by TEXT,
                CONSTRAINT single_row CHECK (id = 1)
            )
        ''')
        cur.execute('''
            INSERT INTO llm_monitoring_analysis_lock (id, is_running)
            VALUES (1, FALSE)
            ON CONFLICT (id) DO NOTHING
        ''')

        # Intentar adquirir lock
        cur.execute('SELECT is_running, started_at FROM llm_monitoring_analysis_lock WHERE id = 1 FOR UPDATE')
        row = cur.fetchone()

        if row and row['is_running']:
            # Lock está tomado - verificar si es stale
            started_at = row['started_at']
            if started_at:
                from datetime import timezone
                now = datetime.now(timezone.utc) if started_at.tzinfo else datetime.now()
                elapsed = (now - started_at).total_seconds() / 60
                if elapsed < stale_timeout_minutes:
                    # Lock reciente, análisis en curso
                    logger.warning(f"🔒 Analysis lock held since {started_at} ({elapsed:.0f}min ago). Skipping.")
                    conn.rollback()
                    return None
                else:
                    # Lock stale (posible crash), forzar liberación
                    logger.warning(f"🔓 Stale lock detected ({elapsed:.0f}min). Force releasing.")

        # Adquirir lock
        cur.execute('''
            UPDATE llm_monitoring_analysis_lock
            SET is_running = TRUE, started_at = NOW(), started_by = %s
            WHERE id = 1
        ''', (triggered_by,))

        # Crear run record
        cur.execute('''
            INSERT INTO llm_monitoring_analysis_runs (status, triggered_by)
            VALUES ('running', %s)
            RETURNING id
        ''', (triggered_by,))
        run_id = cur.fetchone()['id']

        conn.commit()
        logger.info(f"🔒 Analysis lock acquired (run_id={run_id}, by={triggered_by})")
        return run_id

    except Exception as e:
        logger.error(f"Error acquiring analysis lock: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


def release_analysis_lock(run_id: int, total_projects: int = 0, successful: int = 0,
                          failed: int = 0, total_queries: int = 0, error_message: str = None):
    """
    Libera el lock de análisis y actualiza el run con resultados.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return
        cur = conn.cursor()

        # Liberar lock
        cur.execute('''
            UPDATE llm_monitoring_analysis_lock
            SET is_running = FALSE, started_at = NULL, started_by = NULL
            WHERE id = 1
        ''')

        # Actualizar run
        status = 'failed' if error_message else 'completed'
        cur.execute('''
            UPDATE llm_monitoring_analysis_runs
            SET completed_at = NOW(),
                status = %s,
                total_projects = %s,
                successful_projects = %s,
                failed_projects = %s,
                total_queries = %s,
                error_message = %s
            WHERE id = %s
        ''', (status, total_projects, successful, failed, total_queries, error_message, run_id))

        conn.commit()
        logger.info(f"🔓 Analysis lock released (run_id={run_id}, status={status})")

    except Exception as e:
        logger.error(f"Error releasing analysis lock: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    # Cron alert hook — fully isolated. Any error here MUST NOT affect lock state.
    # The lock has already been released above; this just sends a notification email
    # if any of the configured thresholds (duration / error rate / cost spike) was hit.
    try:
        from cron_alerts import check_and_send_cron_alerts
        result = check_and_send_cron_alerts(run_id)
        if result.get('alerts_triggered', 0) > 0:
            logger.info(
                f"📧 Cron alerts: {result['alerts_triggered']} triggered "
                f"(email_sent={result.get('email_sent')}, types={result.get('alerts', [])})"
            )
    except Exception as e:
        logger.warning(f"Cron alerts hook failed (non-fatal): {e}")


def get_latest_analysis_run() -> Optional[Dict]:
    """
    Retorna información del último análisis ejecutado.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute('''
            SELECT * FROM llm_monitoring_analysis_runs
            ORDER BY started_at DESC
            LIMIT 1
        ''')
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting latest analysis run: {e}")
        return None
    finally:
        if conn:
            conn.close()