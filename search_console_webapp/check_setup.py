#!/usr/bin/env python3
# check_setup.py - Verificar configuración de autenticación

import os
import json

def check_files():
    """Verifica que todos los archivos necesarios existan"""
    print("🔍 Verificando archivos necesarios...")
    
    required_files = {
        'serpapi.env': '✅ Encontrado',
        'client_secret.json': '✅ Encontrado', 
        'auth.py': '❌ FALTA - Crear sistema de autenticación',
        'static/navbar.css': '❌ FALTA - Crear estilos del navbar',
        'static/js/navbar.js': '❌ FALTA - Crear lógica del navbar',
        'static/js/ui-core.js': '✅ Actualizado'
    }
    
    for file_path, status in required_files.items():
        if os.path.exists(file_path):
            print(f"  {status}: {file_path}")
        else:
            print(f"  ❌ FALTA: {file_path}")

def check_client_secret():
    """Verifica la configuración de client_secret.json"""
    print("\n🔐 Verificando client_secret.json...")
    
    if not os.path.exists('client_secret.json'):
        print("  ❌ client_secret.json no encontrado")
        return False
    
    try:
        with open('client_secret.json', 'r') as f:
            config = json.load(f)
        
        if 'web' in config:
            print("  ✅ Configurado como aplicación WEB (correcto)")
            
            web_config = config['web']
            redirect_uris = web_config.get('redirect_uris', [])
            
            if 'http://localhost:5001/auth/callback' in redirect_uris:
                print("  ✅ URI de redirección correcto")
                return True
            else:
                print("  ⚠️  URI de redirección incorrecto")
                print(f"     Actual: {redirect_uris}")
                print("     Esperado: ['http://localhost:5001/auth/callback']")
                return False
                
        elif 'installed' in config:
            print("  ❌ Configurado como aplicación INSTALADA (incorrecto)")
            print("     Necesitas crear credenciales de tipo 'Aplicación web'")
            return False
        else:
            print("  ❌ Formato de archivo incorrecto")
            return False
            
    except json.JSONDecodeError:
        print("  ❌ client_secret.json no es un JSON válido")
        return False
    except Exception as e:
        print(f"  ❌ Error leyendo archivo: {e}")
        return False

def check_dependencies():
    """Verifica dependencias de Python"""
    print("\n📦 Verificando dependencias...")
    
    required_packages = [
        'flask',
        'google-auth',
        'google-auth-oauthlib',
        'google-api-python-client',
        'pandas',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - FALTA")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n💡 Para instalar: pip install {' '.join(missing_packages)}")
    
    return len(missing_packages) == 0

def main():
    print("🔧 SearchScope - Verificación de configuración OAuth2")
    print("=" * 55)
    
    check_files()
    client_secret_ok = check_client_secret()
    deps_ok = check_dependencies()
    
    print("\n" + "=" * 55)
    print("📊 RESUMEN:")
    
    if client_secret_ok and deps_ok:
        print("✅ Configuración OAuth2 lista")
        print("🚀 Próximo paso: Crear archivos faltantes de la implementación")
    else:
        print("⚠️  Configuración incompleta")
        
        if not client_secret_ok:
            print("📋 ACCIÓN REQUERIDA:")
            print("   1. Ve a Google Cloud Console")
            print("   2. Crea credenciales de 'Aplicación web'")
            print("   3. Configura URI: http://localhost:5001/auth/callback")
            print("   4. Descarga y reemplaza client_secret.json")
        
        if not deps_ok:
            print("📦 Instala dependencias faltantes")

if __name__ == "__main__":
    main()