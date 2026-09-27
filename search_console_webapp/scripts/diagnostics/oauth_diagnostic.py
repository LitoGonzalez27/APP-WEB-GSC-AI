#!/usr/bin/env python3
# oauth_diagnostic.py - Diagnóstico de configuración OAuth

import os
import json
import sys
from urllib.parse import urlparse

def print_header(title):
    print(f"\n{'='*50}")
    print(f"🔍 {title}")
    print('='*50)

def check_client_secret():
    print_header("VERIFICACIÓN CLIENT_SECRET.JSON")
    
    if not os.path.exists('client_secret.json'):
        print("❌ client_secret.json NO encontrado")
        print("📋 SOLUCIÓN:")
        print("   1. Ve a Google Cloud Console")
        print("   2. APIs & Services > Credentials")
        print("   3. Crea 'OAuth 2.0 Client ID' tipo 'Web application'")
        print("   4. Descarga el JSON y renómbralo a 'client_secret.json'")
        return False
    
    try:
        with open('client_secret.json', 'r') as f:
            config = json.load(f)
        
        if 'web' not in config:
            print("❌ Formato incorrecto - debe ser tipo 'Web application'")
            print("📋 SOLUCIÓN: Crear credenciales de tipo 'Aplicación web' en lugar de 'Aplicación de escritorio'")
            return False
        
        web_config = config['web']
        
        # Verificar campos requeridos
        required_fields = ['client_id', 'client_secret', 'redirect_uris']
        missing = [field for field in required_fields if field not in web_config]
        
        if missing:
            print(f"❌ Faltan campos: {missing}")
            return False
        
        # Verificar redirect URIs
        redirect_uris = web_config.get('redirect_uris', [])
        expected_uri = 'http://localhost:5001/auth/callback'
        
        print("✅ client_secret.json encontrado y válido")
        print(f"📍 Client ID: {web_config['client_id'][:20]}...")
        print(f"📍 Redirect URIs configurados: {redirect_uris}")
        
        if expected_uri not in redirect_uris:
            print("⚠️  URI de redirección incorrecto")
            print(f"❌ Esperado: {expected_uri}")
            print(f"🔧 Actual: {redirect_uris}")
            print("📋 SOLUCIÓN:")
            print("   1. Ve a Google Cloud Console > Credentials")
            print("   2. Edita tu OAuth 2.0 Client ID")
            print("   3. En 'Authorized redirect URIs' añade:")
            print(f"      {expected_uri}")
            return False
        
        print("✅ URI de redirección correcto")
        return True
        
    except json.JSONDecodeError:
        print("❌ client_secret.json no es un JSON válido")
        return False
    except Exception as e:
        print(f"❌ Error leyendo client_secret.json: {e}")
        return False

def check_env_file():
    print_header("VERIFICACIÓN VARIABLES DE ENTORNO")
    
    env_file = 'serpapi.env'
    if not os.path.exists(env_file):
        print(f"❌ {env_file} no encontrado")
        return False
    
    # Leer variables
    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                env_vars[key] = value
    
    # Verificar SECRET_KEY
    secret_key = env_vars.get('SECRET_KEY', '')
    if not secret_key or len(secret_key) < 32:
        print("❌ SECRET_KEY falta o es muy corta")
        print("📋 SOLUCIÓN: Ejecutar python setup.py para generar una nueva")
        return False
    
    print("✅ SECRET_KEY válida")
    print(f"📍 Longitud: {len(secret_key)} caracteres")
    
    # Verificar otras variables importantes
    base_url = env_vars.get('BASE_URL', '')
    if base_url != 'http://localhost:5001':
        print(f"⚠️  BASE_URL: {base_url} (debería ser http://localhost:5001)")
    else:
        print("✅ BASE_URL correcta")
    
    return True

def check_google_cloud_project():
    print_header("VERIFICACIÓN PROYECTO GOOGLE CLOUD")
    
    try:
        with open('client_secret.json', 'r') as f:
            config = json.load(f)
        
        project_id = config['web'].get('project_id', 'No definido')
        client_id = config['web'].get('client_id', '')
        
        print(f"📍 Project ID: {project_id}")
        print(f"📍 Client ID: {client_id}")
        
        # Verificar que las APIs estén habilitadas
        print("\n🔧 APIS QUE DEBEN ESTAR HABILITADAS:")
        apis_required = [
            "Google Search Console API",
            "Google OAuth2 API"
        ]
        
        for api in apis_required:
            print(f"   • {api}")
        
        print("\n📋 PARA VERIFICAR/HABILITAR APIS:")
        print("   1. Ve a Google Cloud Console")
        print("   2. APIs & Services > Library")
        print("   3. Busca y habilita cada API")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando proyecto: {e}")
        return False

def check_flask_session():
    print_header("VERIFICACIÓN CONFIGURACIÓN FLASK")
    
    try:
        from dotenv import load_dotenv
        load_dotenv('serpapi.env')
        
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            print("❌ SECRET_KEY no se carga desde .env")
            return False
        
        print("✅ SECRET_KEY se carga correctamente")
        
        # Verificar que Flask pueda usar la clave
        from flask import Flask
        app = Flask(__name__)
        app.secret_key = secret_key
        
        print("✅ Flask puede usar la SECRET_KEY")
        return True
        
    except ImportError as e:
        print(f"❌ Dependencia faltante: {e}")
        print("📋 SOLUCIÓN: pip install flask python-dotenv")
        return False
    except Exception as e:
        print(f"❌ Error configurando Flask: {e}")
        return False

def print_troubleshooting_steps():
    print_header("PASOS DE RESOLUCIÓN DE PROBLEMAS")
    
    print("🔧 PASOS PARA RESOLVER ERRORES DE CALLBACK:")
    print()
    print("1. VERIFICAR URLS DE REDIRECCIÓN:")
    print("   • Ve a Google Cloud Console > Credentials")
    print("   • Edita tu OAuth 2.0 Client ID")
    print("   • Asegúrate de que esté configurado:")
    print("     - http://localhost:5001/auth/callback")
    print()
    print("2. VERIFICAR TIPO DE APLICACIÓN:")
    print("   • Debe ser 'Web application', NO 'Desktop application'")
    print("   • Si es incorrecto, crea nuevas credenciales")
    print()
    print("3. REGENERAR CREDENCIALES:")
    print("   • Descarga un nuevo client_secret.json")
    print("   • Reemplaza el archivo actual")
    print()
    print("4. LIMPIAR SESIÓN:")
    print("   • Borra todas las cookies del navegador para localhost:5001")
    print("   • Cierra y reabre el navegador")
    print()
    print("5. VERIFICAR CONSOLA DEL NAVEGADOR:")
    print("   • Abre F12 > Console")
    print("   • Busca errores específicos durante el callback")
    print()
    print("6. REVISAR LOGS DEL SERVIDOR:")
    print("   • Mira la terminal donde ejecutas python app.py")
    print("   • Busca errores específicos durante el callback")

def main():
    print("🔧 SearchScope - Diagnóstico de OAuth2")
    print("Este script verificará tu configuración de autenticación")
    
    checks = [
        ("Client Secret", check_client_secret),
        ("Variables de Entorno", check_env_file),
        ("Proyecto Google Cloud", check_google_cloud_project),
        ("Configuración Flask", check_flask_session)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error en {name}: {e}")
            results.append((name, False))
    
    # Resumen
    print_header("RESUMEN")
    all_passed = True
    for name, passed in results:
        status = "✅ CORRECTO" if passed else "❌ PROBLEMA"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Configuración OAuth parece correcta")
        print("📋 Si sigues teniendo problemas:")
        print("   1. Reinicia el servidor (python app.py)")
        print("   2. Usa navegador en modo incógnito")
        print("   3. Verifica logs del servidor durante el login")
    else:
        print("\n⚠️ Se encontraron problemas de configuración")
        print_troubleshooting_steps()
    
    print(f"\n📁 Directorio actual: {os.getcwd()}")
    print("📁 Archivos en directorio:")
    for file in ['client_secret.json', 'serpapi.env', 'auth.py', 'app.py']:
        exists = "✅" if os.path.exists(file) else "❌"
        print(f"   {exists} {file}")

if __name__ == "__main__":
    main()