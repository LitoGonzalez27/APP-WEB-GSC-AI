#!/usr/bin/env python3
"""
🎭 Verificador de Configuración de Staging
Diagnóstica problemas específicos del entorno de staging
"""

import os
import sys
import json
import requests
from urllib.parse import urlparse

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🎭 {title}")
    print('='*60)

def print_section(title):
    print(f"\n🔍 {title}")
    print('-'*40)

def check_environment():
    print_section("Verificación de Entorno")
    
    railway_env = os.getenv('RAILWAY_ENVIRONMENT', '')
    if railway_env == 'staging':
        print("✅ RAILWAY_ENVIRONMENT configurado correctamente: staging")
    elif railway_env == 'production':
        print("⚠️  RAILWAY_ENVIRONMENT está en 'production' - ¿Seguro que es staging?")
    elif not railway_env:
        print("❌ RAILWAY_ENVIRONMENT no está configurado")
        print("   Configura: RAILWAY_ENVIRONMENT=staging")
    else:
        print(f"⚠️  RAILWAY_ENVIRONMENT valor inesperado: '{railway_env}'")
    
    return railway_env

def check_oauth_config():
    print_section("Configuración OAuth de Google")
    
    try:
        with open('client_secret.json', 'r') as f:
            config = json.load(f)
        
        web_config = config.get('web', {})
        redirect_uris = web_config.get('redirect_uris', [])
        javascript_origins = web_config.get('javascript_origins', [])
        
        staging_redirect = 'https://clicandseo.up.railway.app/auth/callback'
        staging_origin = 'https://clicandseo.up.railway.app'
        
        print(f"📂 client_secret.json encontrado")
        print(f"🔗 Redirect URIs configurados: {len(redirect_uris)}")
        
        if staging_redirect in redirect_uris:
            print(f"✅ Staging redirect URI configurado: {staging_redirect}")
        else:
            print(f"❌ Staging redirect URI FALTANTE: {staging_redirect}")
            print(f"   URIs actuales: {redirect_uris}")
        
        if staging_origin in javascript_origins:
            print(f"✅ Staging origin configurado: {staging_origin}")
        else:
            print(f"❌ Staging origin FALTANTE: {staging_origin}")
            print(f"   Origins actuales: {javascript_origins}")
            
    except FileNotFoundError:
        print("❌ client_secret.json no encontrado")
    except json.JSONDecodeError:
        print("❌ client_secret.json tiene formato JSON inválido")
    except Exception as e:
        print(f"❌ Error leyendo client_secret.json: {e}")

def check_environment_variables():
    print_section("Variables de Entorno")
    
    required_vars = {
        'RAILWAY_ENVIRONMENT': 'staging',
        'GOOGLE_REDIRECT_URI': 'https://clicandseo.up.railway.app/auth/callback',
        'FLASK_SECRET_KEY': 'Clave secreta de Flask',
        'SERPAPI_KEY': 'Clave de SerpAPI'
    }
    
    optional_vars = {
        'DATABASE_URL': 'URL de PostgreSQL (automática)',
        'PORT': 'Puerto del servidor (automático)',
        'CLIENT_SECRETS_FILE': 'client_secret.json',
        'SESSION_TIMEOUT_MINUTES': '45',
        'SESSION_WARNING_MINUTES': '5'
    }
    
    print("📋 Variables Críticas:")
    for var, description in required_vars.items():
        value = os.getenv(var, '')
        if value:
            if var == 'FLASK_SECRET_KEY':
                display_value = f"[{len(value)} caracteres]"
            elif var == 'SERPAPI_KEY':
                display_value = f"[{value[:10]}...]" if len(value) > 10 else "[valor corto]"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: NO CONFIGURADO")
            print(f"   Descripción: {description}")
    
    print("\n📋 Variables Opcionales:")
    for var, default in optional_vars.items():
        value = os.getenv(var, '')
        if value:
            if 'URL' in var and len(value) > 50:
                display_value = f"{value[:30]}...{value[-10:]}"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"⚪ {var}: usando default ({default})")

def check_network_connectivity():
    print_section("Conectividad de Red")
    
    test_urls = [
        'https://clicandseo.up.railway.app/auth/status',
        'https://clicandseo.up.railway.app/login',
        'https://accounts.google.com/o/oauth2/auth'
    ]
    
    for url in test_urls:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ {url} - Accesible (200)")
            elif response.status_code == 401:
                print(f"✅ {url} - Responde correctamente (401 - auth required)")
            elif response.status_code == 404:
                print(f"⚠️  {url} - Página no encontrada (404)")
            else:
                print(f"⚠️  {url} - Código {response.status_code}")
        except requests.exceptions.ConnectTimeout:
            print(f"❌ {url} - Timeout de conexión")
        except requests.exceptions.ConnectionError:
            print(f"❌ {url} - Error de conexión")
        except Exception as e:
            print(f"❌ {url} - Error: {e}")

def check_oauth_flow():
    print_section("Flujo OAuth")
    
    google_redirect = os.getenv('GOOGLE_REDIRECT_URI', '')
    
    if not google_redirect:
        print("❌ GOOGLE_REDIRECT_URI no configurado")
        return
    
    parsed = urlparse(google_redirect)
    
    print(f"🔗 Redirect URI: {google_redirect}")
    print(f"   Protocolo: {parsed.scheme}")
    print(f"   Dominio: {parsed.netloc}")
    print(f"   Ruta: {parsed.path}")
    
    if parsed.scheme != 'https':
        print("❌ El protocolo debe ser HTTPS en staging")
    else:
        print("✅ Protocolo HTTPS correcto")
    
    if 'clicandseo.up.railway.app' not in parsed.netloc:
        print("⚠️  El dominio no coincide con la URL de staging")
    else:
        print("✅ Dominio correcto para staging")
    
    if parsed.path != '/auth/callback':
        print("❌ La ruta debe ser /auth/callback")
    else:
        print("✅ Ruta correcta")

def generate_recommendations():
    print_section("Recomendaciones")
    
    railway_env = os.getenv('RAILWAY_ENVIRONMENT', '')
    google_redirect = os.getenv('GOOGLE_REDIRECT_URI', '')
    flask_secret = os.getenv('FLASK_SECRET_KEY', '')
    
    recommendations = []
    
    if railway_env != 'staging':
        recommendations.append("🔧 Configurar RAILWAY_ENVIRONMENT=staging en Railway")
    
    if not google_redirect or 'clicandseo.up.railway.app' not in google_redirect:
        recommendations.append("🔧 Configurar GOOGLE_REDIRECT_URI=https://clicandseo.up.railway.app/auth/callback")
    
    if not flask_secret or len(flask_secret) < 32:
        recommendations.append("🔧 Generar una FLASK_SECRET_KEY de al menos 32 caracteres")
    
    try:
        with open('client_secret.json', 'r') as f:
            config = json.load(f)
        redirect_uris = config.get('web', {}).get('redirect_uris', [])
        if 'https://clicandseo.up.railway.app/auth/callback' not in redirect_uris:
            recommendations.append("🔧 Agregar staging URL en Google Cloud Console redirect_uris")
    except:
        recommendations.append("🔧 Verificar client_secret.json")
    
    if recommendations:
        for rec in recommendations:
            print(rec)
    else:
        print("✅ No se encontraron problemas críticos de configuración")

def main():
    print_header("DIAGNÓSTICO DE STAGING")
    print("Verificando configuración para: https://clicandseo.up.railway.app/")
    
    railway_env = check_environment()
    check_environment_variables()
    check_oauth_config()
    check_oauth_flow()
    
    # Solo verificar conectividad si parece que estamos en el entorno correcto
    if railway_env == 'staging':
        check_network_connectivity()
    
    generate_recommendations()
    
    print_header("FIN DEL DIAGNÓSTICO")
    print("📧 Si persisten los problemas, revisa los logs de Railway")
    print("🔗 Railway Dashboard: https://railway.app/dashboard")

if __name__ == "__main__":
    main() 