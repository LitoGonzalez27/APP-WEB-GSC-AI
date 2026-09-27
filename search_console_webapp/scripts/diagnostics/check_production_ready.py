#!/usr/bin/env python3
"""
Script para verificar que la aplicación está lista para producción en Railway
"""

import os
import sys
import json
from database import get_db_connection, get_user_by_email

def check_environment_variables():
    """Verifica que todas las variables de entorno necesarias estén configuradas"""
    print("🔍 Verificando variables de entorno...")
    
    required_vars = {
        'DATABASE_URL': 'URL de conexión a PostgreSQL',
        'FLASK_SECRET_KEY': 'Clave secreta de Flask',
        'SERPAPI_KEY': 'Clave de SerpAPI',
        'CLIENT_SECRETS_FILE': 'Archivo de credenciales de Google'
    }
    
    missing_vars = []
    weak_vars = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f"❌ {var}: {description}")
        else:
            # Verificar calidad de las variables críticas
            if var == 'FLASK_SECRET_KEY':
                if len(value) < 32:
                    weak_vars.append(f"⚠️  {var}: Muy corta (mínimo 32 caracteres)")
                elif value == 'your-secret-key-here-change-in-production':
                    weak_vars.append(f"⚠️  {var}: Usando valor por defecto")
            
            print(f"✅ {var}: Configurada")
    
    if missing_vars:
        print("\n❌ Variables de entorno faltantes:")
        for var in missing_vars:
            print(f"   {var}")
        return False
    
    if weak_vars:
        print("\n⚠️  Advertencias de seguridad:")
        for var in weak_vars:
            print(f"   {var}")
    
    print("✅ Todas las variables de entorno están configuradas")
    return True

def check_google_credentials():
    """Verifica que las credenciales de Google estén disponibles"""
    print("\n🔍 Verificando credenciales de Google...")
    
    client_secrets_file = os.getenv('CLIENT_SECRETS_FILE', 'client_secret.json')
    
    if not os.path.exists(client_secrets_file):
        print(f"❌ Archivo {client_secrets_file} no encontrado")
        return False
    
    try:
        with open(client_secrets_file, 'r') as f:
            credentials = json.load(f)
        
        # Verificar estructura básica
        if 'web' not in credentials:
            print("❌ Estructura de credenciales inválida")
            return False
        
        web_config = credentials['web']
        required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
        
        for field in required_fields:
            if field not in web_config:
                print(f"❌ Campo faltante en credenciales: {field}")
                return False
        
        print("✅ Credenciales de Google válidas")
        return True
        
    except json.JSONDecodeError:
        print("❌ Archivo de credenciales con formato JSON inválido")
        return False
    except Exception as e:
        print(f"❌ Error leyendo credenciales: {e}")
        return False

def check_database_connection():
    """Verifica la conexión a la base de datos"""
    print("\n🔍 Verificando conexión a base de datos...")
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ No se pudo conectar a la base de datos")
            return False
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        if result[0] == 1:
            print("✅ Conexión a base de datos exitosa")
            conn.close()
            return True
        else:
            print("❌ Respuesta inesperada de la base de datos")
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Error de conexión a base de datos: {e}")
        return False

def check_database_schema():
    """Verifica que las tablas necesarias existan"""
    print("\n🔍 Verificando esquema de base de datos...")
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # Verificar que la tabla users existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            )
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("❌ Tabla 'users' no existe")
            conn.close()
            return False
        
        # Verificar columnas esenciales
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users'
        """)
        
        columns = [row[0] for row in cursor.fetchall()]
        required_columns = ['id', 'email', 'name', 'role', 'is_active', 'created_at']
        
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            print(f"❌ Columnas faltantes en tabla users: {missing_columns}")
            conn.close()
            return False
        
        print("✅ Esquema de base de datos correcto")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verificando esquema: {e}")
        return False

def check_admin_user():
    """Verifica que exista un usuario administrador"""
    print("\n🔍 Verificando usuario administrador...")
    
    try:
        admin_user = get_user_by_email("admin@clicandseo.com")
        
        if not admin_user:
            print("❌ Usuario administrador no encontrado")
            return False
        
        if admin_user['role'] != 'admin':
            print("❌ Usuario admin no tiene rol de administrador")
            return False
        
        if not admin_user['is_active']:
            print("⚠️  Usuario administrador está inactivo")
            return False
        
        print("✅ Usuario administrador configurado correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error verificando usuario admin: {e}")
        return False

def check_file_permissions():
    """Verifica permisos de archivos críticos"""
    print("\n🔍 Verificando permisos de archivos...")
    
    critical_files = [
        'app.py',
        'auth.py', 
        'database.py',
        'requirements.txt',
        'Procfile'
    ]
    
    for filename in critical_files:
        if not os.path.exists(filename):
            print(f"❌ Archivo crítico faltante: {filename}")
            return False
        
        if not os.access(filename, os.R_OK):
            print(f"❌ Sin permisos de lectura: {filename}")
            return False
    
    print("✅ Todos los archivos críticos están presentes y accesibles")
    return True

def generate_deployment_summary():
    """Genera un resumen para el despliegue"""
    print("\n📋 RESUMEN DE DESPLIEGUE")
    print("=" * 50)
    
    # Información del entorno
    # Detección de entorno mejorada
    railway_env = os.getenv('RAILWAY_ENVIRONMENT', '')
    is_production = railway_env == 'production'
    is_staging = railway_env == 'staging'
    is_development = not railway_env or railway_env == 'development'
    
    environment_name = 'PRODUCCIÓN' if is_production else ('STAGING' if is_staging else 'DESARROLLO')
    print(f"🌍 Entorno: {environment_name} ({railway_env or 'local'})")
    print(f"🐍 Python: {sys.version.split()[0]}")
    
    # Variables configuradas
    database_url = os.getenv('DATABASE_URL', '')
    if database_url:
        # Ocultar credenciales en el resumen
        db_host = database_url.split('@')[-1].split(':')[0] if '@' in database_url else 'local'
        print(f"🗄️  Base de datos: PostgreSQL en {db_host}")
    
    google_redirect = os.getenv('GOOGLE_REDIRECT_URI', '')
    if google_redirect:
        print(f"🔐 OAuth redirect: {google_redirect}")
    
    port = os.getenv('PORT', '5001')
    print(f"🌐 Puerto: {port}")
    
    print("\n🚀 READY PARA DESPLIEGUE!")

def main():
    """Función principal"""
    print("🔧 VERIFICACIÓN DE PRODUCCIÓN - Clicandseo")
    print("=" * 60)
    
    checks = [
        check_environment_variables,
        check_google_credentials,
        check_database_connection,
        check_database_schema,
        check_admin_user,
        check_file_permissions
    ]
    
    all_passed = True
    
    for check in checks:
        try:
            if not check():
                all_passed = False
        except Exception as e:
            print(f"❌ Error ejecutando verificación: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 ¡TODAS LAS VERIFICACIONES PASARON!")
        print("✅ Tu aplicación está lista para producción")
        generate_deployment_summary()
        sys.exit(0)
    else:
        print("❌ ALGUNAS VERIFICACIONES FALLARON")
        print("⚠️  Revisa los errores antes de desplegar")
        print("\n💡 Consejos:")
        print("   1. Configura todas las variables de entorno en Railway")
        print("   2. Asegúrate de que client_secret.json esté en el repositorio")
        print("   3. Verifica que PostgreSQL esté ejecutándose")
        print("   4. Ejecuta 'python init_database.py' si es necesario")
        sys.exit(1)

if __name__ == "__main__":
    main() 