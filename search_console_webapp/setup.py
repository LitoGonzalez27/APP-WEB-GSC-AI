#!/usr/bin/env python3
# setup.py - Script de configuración para SearchScope

import os
import sys
import secrets
import subprocess

def print_banner():
    print("🔧 SearchScope - Configuración de Autenticación OAuth2")
    print("=" * 55)
    print()

def check_python_version():
    if sys.version_info < (3, 8):
        print("❌ Error: Se requiere Python 3.8 o superior")
        print(f"   Versión actual: {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detectado")

def install_dependencies():
    print("\n📦 Instalando dependencias...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencias instaladas correctamente")
    except subprocess.CalledProcessError:
        print("❌ Error instalando dependencias")
        print("   Ejecuta manualmente: pip install -r requirements.txt")
        return False
    return True

def generate_secret_key():
    """Genera una clave secreta segura para Flask"""
    return secrets.token_urlsafe(32)

def create_env_file():
    """Crea el archivo de variables de entorno"""
    print("\n🔐 Configurando variables de entorno...")
    
    env_file = "serpapi.env"
    secret_key = generate_secret_key()
    
    # Leer archivo existente si existe
    existing_vars = {}
    if os.path.exists(env_file):
        print(f"   Archivo {env_file} existente encontrado")
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    existing_vars[key] = value
    
    # Variables requeridas
    required_vars = {
        'SECRET_KEY': secret_key,
        'CLIENT_SECRETS_FILE': 'client_secret.json',
        'TOKEN_FILE': 'token.json',
        'ENVIRONMENT': 'development',
        'BASE_URL': 'http://localhost:5001',
        'LOG_LEVEL': 'INFO',
        'FLASK_ENV': 'development',
        'FLASK_DEBUG': 'True',
        'PORT': '5001'
    }
    
    # Mantener valores existentes, añadir nuevos
    for key, default_value in required_vars.items():
        if key not in existing_vars:
            existing_vars[key] = default_value
    
    # Escribir archivo actualizado
    with open(env_file, 'w') as f:
        f.write("# SearchScope - Variables de entorno\n")
        f.write("# Generado automáticamente por setup.py\n\n")
        
        f.write("# ================================\n")
        f.write("# API Keys\n")
        f.write("# ================================\n")
        serpapi_key = existing_vars.get('SERPAPI_KEY', 'tu_serpapi_key_aqui')
        f.write(f"SERPAPI_KEY={serpapi_key}\n\n")
        
        f.write("# ================================\n")
        f.write("# Configuración OAuth2\n")
        f.write("# ================================\n")
        f.write(f"SECRET_KEY={existing_vars['SECRET_KEY']}\n")
        f.write(f"CLIENT_SECRETS_FILE={existing_vars['CLIENT_SECRETS_FILE']}\n")
        f.write(f"TOKEN_FILE={existing_vars['TOKEN_FILE']}\n\n")
        
        f.write("# ================================\n")
        f.write("# Configuración de aplicación\n")
        f.write("# ================================\n")
        f.write(f"ENVIRONMENT={existing_vars['ENVIRONMENT']}\n")
        f.write(f"BASE_URL={existing_vars['BASE_URL']}\n")
        f.write(f"LOG_LEVEL={existing_vars['LOG_LEVEL']}\n")
        f.write(f"FLASK_ENV={existing_vars['FLASK_ENV']}\n")
        f.write(f"FLASK_DEBUG={existing_vars['FLASK_DEBUG']}\n")
        f.write(f"PORT={existing_vars['PORT']}\n")
        
        # Añadir otras variables existentes
        other_vars = {k: v for k, v in existing_vars.items() 
                     if k not in required_vars and k != 'SERPAPI_KEY'}
        if other_vars:
            f.write("\n# ================================\n")
            f.write("# Otras configuraciones\n")
            f.write("# ================================\n")
            for key, value in other_vars.items():
                f.write(f"{key}={value}\n")
    
    print(f"✅ Archivo {env_file} actualizado")
    return True

def check_oauth_files():
    """Verifica archivos necesarios para OAuth"""
    print("\n🔍 Verificando archivos OAuth...")
    
    files_status = {}
    
    # client_secret.json
    if os.path.exists('client_secret.json'):
        print("✅ client_secret.json encontrado")
        files_status['client_secret'] = True
    else:
        print("⚠️  client_secret.json NO encontrado")
        print("   📋 Sigue las instrucciones en SETUP_OAUTH.md para configurarlo")
        files_status['client_secret'] = False
    
    # Verificar estructura del client_secret.json
    if files_status['client_secret']:
        try:
            import json
            with open('client_secret.json', 'r') as f:
                client_config = json.load(f)
            
            if 'web' in client_config:
                required_fields = ['client_id', 'client_secret', 'redirect_uris']
                missing_fields = [field for field in required_fields 
                                if field not in client_config['web']]
                if missing_fields:
                    print(f"⚠️  client_secret.json incompleto. Faltan: {missing_fields}")
                else:
                    print("✅ client_secret.json tiene estructura correcta")
            else:
                print("⚠️  client_secret.json tiene formato incorrecto")
        except json.JSONDecodeError:
            print("❌ client_secret.json no es un JSON válido")
        except Exception as e:
            print(f"⚠️  Error leyendo client_secret.json: {e}")
    
    return files_status

def create_gitignore():
    """Crea o actualiza .gitignore"""
    print("\n📝 Configurando .gitignore...")
    
    gitignore_entries = [
        "# Archivos de autenticación",
        "client_secret.json",
        "token.json",
        "*.env",
        ".env",
        "",
        "# Archivos de sesión",
        "flask_session/",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "",
        "# Logs",
        "*.log",
        "logs/",
        "",
        "# IDE",
        ".vscode/",
        ".idea/",
        "",
        "# OS",
        ".DS_Store",
        "Thumbs.db"
    ]
    
    # Leer gitignore existente
    existing_lines = []
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            existing_lines = [line.strip() for line in f.readlines()]
    
    # Añadir solo las líneas que no existen
    new_lines = []
    for entry in gitignore_entries:
        if entry not in existing_lines:
            new_lines.append(entry)
    
    if new_lines:
        with open('.gitignore', 'a') as f:
            if existing_lines:  # Si el archivo ya tenía contenido
                f.write('\n')
            f.write('\n'.join(new_lines))
        print("✅ .gitignore actualizado")
    else:
        print("✅ .gitignore ya está configurado")

def print_next_steps(oauth_status):
    """Imprime los próximos pasos"""
    print("\n" + "=" * 55)
    print("🎉 Configuración completada!")
    print("=" * 55)
    
    if not oauth_status['client_secret']:
        print("\n📋 PRÓXIMOS PASOS OBLIGATORIOS:")
        print("1. Sigue las instrucciones en SETUP_OAUTH.md")
        print("2. Descarga client_secret.json de Google Cloud Console")
        print("3. Coloca el archivo en la raíz del proyecto")
        print("4. Ejecuta este script de nuevo para verificar")
    else:
        print("\n🚀 LISTO PARA USAR:")
        print("1. python app.py")
        print("2. Abre http://localhost:5001")
        print("3. Haz clic en 'Login' para probar la autenticación")
    
    print("\n📚 RECURSOS:")
    print("- Documentación OAuth: SETUP_OAUTH.md")
    print("- Variables de entorno: serpapi.env")
    print("- Logs de la aplicación: Revisar consola al ejecutar app.py")
    
    print("\n🆘 SOPORTE:")
    print("- Errores comunes: Ver SETUP_OAUTH.md")
    print("- Logs detallados: Cambiar LOG_LEVEL=DEBUG en serpapi.env")

def main():
    print_banner()
    
    # Verificaciones básicas
    check_python_version()
    
    # Instalar dependencias
    if not install_dependencies():
        sys.exit(1)
    
    # Configurar variables de entorno
    if not create_env_file():
        sys.exit(1)
    
    # Verificar archivos OAuth
    oauth_status = check_oauth_files()
    
    # Configurar .gitignore
    create_gitignore()
    
    # Próximos pasos
    print_next_steps(oauth_status)

if __name__ == "__main__":
    main()