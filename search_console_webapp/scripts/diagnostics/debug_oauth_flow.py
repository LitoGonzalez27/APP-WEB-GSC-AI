#!/usr/bin/env python3
# debug_oauth_flow.py - Debug del flujo OAuth completo

import requests
import json

def check_google_apis():
    """Verifica que las APIs de Google estén respondiendo"""
    print("🔍 VERIFICANDO APIS DE GOOGLE...")
    
    # Verificar Search Console API
    try:
        # Endpoint público de Search Console API
        response = requests.get('https://searchconsole.googleapis.com/$discovery/rest?version=v1', timeout=10)
        if response.status_code == 200:
            print("✅ Google Search Console API está accesible")
        else:
            print(f"⚠️ Google Search Console API responde con código: {response.status_code}")
    except Exception as e:
        print(f"❌ Error accediendo a Search Console API: {e}")
    
    # Verificar OAuth2 API
    try:
        response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', timeout=10)
        if response.status_code in [401, 403]:  # Esperamos 401/403 sin token
            print("✅ Google OAuth2 API está accesible")
        else:
            print(f"⚠️ Google OAuth2 API respuesta inesperada: {response.status_code}")
    except Exception as e:
        print(f"❌ Error accediendo a OAuth2 API: {e}")

def test_local_auth_endpoints():
    """Verifica que los endpoints locales respondan correctamente"""
    print("\n🔍 VERIFICANDO ENDPOINTS LOCALES...")
    
    base_url = "http://localhost:5001"
    
    endpoints = [
        "/auth/status",
        "/auth/login", 
        "/",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5, allow_redirects=False)
            print(f"✅ {endpoint} - Código: {response.status_code}")
            
            if endpoint == "/auth/login" and response.status_code == 302:
                redirect_url = response.headers.get('Location', '')
                if 'accounts.google.com' in redirect_url:
                    print(f"   → Redirige correctamente a Google: {redirect_url[:50]}...")
                else:
                    print(f"   ⚠️ Redirección inesperada: {redirect_url}")
                    
        except requests.exceptions.ConnectionError:
            print(f"❌ {endpoint} - Servidor no responde. ¿Está ejecutándose python app.py?")
        except Exception as e:
            print(f"❌ {endpoint} - Error: {e}")

def get_google_oauth_url():
    """Obtiene la URL de OAuth de Google para verificar que sea correcta"""
    try:
        with open('client_secret.json', 'r') as f:
            config = json.load(f)
        
        client_id = config['web']['client_id']
        redirect_uri = 'http://localhost:5001/auth/callback'
        
        # URL que Google OAuth debería generar
        expected_url = f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope=https://www.googleapis.com/auth/webmasters.readonly%20https://www.googleapis.com/auth/userinfo.email%20https://www.googleapis.com/auth/userinfo.profile&access_type=offline&include_granted_scopes=true"
        
        print(f"\n🔗 URL DE OAUTH ESPERADA:")
        print(f"https://accounts.google.com/o/oauth2/auth?...")
        print(f"📍 Client ID: {client_id}")
        print(f"📍 Redirect URI: {redirect_uri}")
        
        return expected_url
        
    except Exception as e:
        print(f"❌ Error generando URL OAuth: {e}")
        return None

def check_session_configuration():
    """Verifica la configuración de sesiones de Flask"""
    print("\n🔍 VERIFICANDO CONFIGURACIÓN DE SESIÓN...")
    
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv('serpapi.env')
        
        secret_key = os.getenv('SECRET_KEY')
        if secret_key and len(secret_key) >= 32:
            print("✅ SECRET_KEY tiene longitud adecuada")
        else:
            print("❌ SECRET_KEY muy corta o faltante")
        
        # Verificar otras configuraciones de sesión
        session_configs = {
            'SESSION_COOKIE_SECURE': os.getenv('SESSION_COOKIE_SECURE', 'False'),
            'SESSION_COOKIE_HTTPONLY': os.getenv('SESSION_COOKIE_HTTPONLY', 'True'),
            'SESSION_COOKIE_SAMESITE': os.getenv('SESSION_COOKIE_SAMESITE', 'Lax'),
        }
        
        print("📍 Configuración de cookies de sesión:")
        for key, value in session_configs.items():
            print(f"   {key}: {value}")
        
        if session_configs['SESSION_COOKIE_SECURE'] == 'True':
            print("⚠️ SESSION_COOKIE_SECURE=True puede causar problemas en HTTP local")
            print("   Recomendación: Cambiar a False para desarrollo local")
            
    except Exception as e:
        print(f"❌ Error verificando configuración de sesión: {e}")

def print_debugging_steps():
    """Imprime pasos específicos para debuggear"""
    print("\n" + "="*60)
    print("🐛 PASOS DE DEBUGGING ESPECÍFICOS")
    print("="*60)
    
    print("\n1. 📺 REVISAR LOGS DEL SERVIDOR:")
    print("   • Ejecuta: python app.py")
    print("   • Intenta hacer login")
    print("   • Busca errores específicos en la terminal")
    print("   • Especialmente líneas que contengan 'callback' o 'auth'")
    
    print("\n2. 🌐 REVISAR CONSOLA DEL NAVEGADOR:")
    print("   • Abre http://localhost:5001")
    print("   • Presiona F12 → Console tab")
    print("   • Intenta hacer login")
    print("   • Busca errores en rojo")
    
    print("\n3. 📡 REVISAR NETWORK TAB:")
    print("   • F12 → Network tab")
    print("   • Intenta hacer login")
    print("   • Busca requests que fallen (color rojo)")
    print("   • Especialmente /auth/login y /auth/callback")
    
    print("\n4. 🧪 PROBAR EN MODO INCÓGNITO:")
    print("   • Cierra todas las ventanas del navegador")
    print("   • Abre en modo incógnito/privado")
    print("   • Ve a http://localhost:5001")
    print("   • Intenta hacer login")
    
    print("\n5. 🔄 SI NADA FUNCIONA - REINICIO COMPLETO:")
    print("   • Detén el servidor (Ctrl+C)")
    print("   • Borra cookies de localhost:5001 en el navegador")
    print("   • python app.py")
    print("   • Prueba en modo incógnito")

def main():
    print("🐛 SearchScope - Debug OAuth Flow")
    print("="*60)
    
    print("📋 Este script verificará todo el flujo OAuth paso a paso")
    
    # Verificar APIs de Google
    check_google_apis()
    
    # Verificar endpoints locales
    test_local_auth_endpoints()
    
    # Verificar URL OAuth
    get_google_oauth_url()
    
    # Verificar configuración de sesión
    check_session_configuration()
    
    # Pasos de debugging
    print_debugging_steps()
    
    print("\n" + "="*60)
    print("🎯 SIGUIENTE PASO RECOMENDADO:")
    print("="*60)
    print("1. Ejecuta: python app.py")
    print("2. Abre modo incógnito en el navegador")
    print("3. Ve a: http://localhost:5001")
    print("4. Haz clic en Login")
    print("5. Copia y pega TODOS los logs que aparezcan en la terminal")
    print("6. También copia cualquier error de la consola del navegador (F12)")
    
    print("\n🔍 LOGS IMPORTANTES A BUSCAR:")
    print("• 'Error en auth_callback'")
    print("• 'OAuth configuration error'") 
    print("• 'Token exchange failed'")
    print("• 'Invalid state'")
    print("• Cualquier traceback de Python")

if __name__ == "__main__":
    main()