#!/usr/bin/env python3
"""
Verificación de Variables de Entorno
===================================

Script para verificar que todas las variables necesarias están configuradas.
"""

import os

def check_environment_variables():
    """Verificar variables de entorno necesarias"""
    print("🔍 VERIFICACIÓN DE VARIABLES DE ENTORNO")
    print("=" * 50)
    
    required_vars = {
        'RAILWAY_ENVIRONMENT': 'Entorno de Railway (staging/production)',
        'DATABASE_URL': 'URL de conexión a PostgreSQL',
        'FLASK_SECRET_KEY': 'Clave secreta de Flask',
        'SERPAPI_KEY': 'Clave de SerpAPI',
        'GOOGLE_CLIENT_ID': 'ID de cliente Google OAuth',
        'GOOGLE_CLIENT_SECRET': 'Secret de cliente Google OAuth',
        'GOOGLE_REDIRECT_URI': 'URI de redirección OAuth'
    }
    
    optional_vars = {
        'CRON_TOKEN': 'Token para tareas cron'
    }
    
    print("\n📋 Variables requeridas:")
    all_ok = True
    
    for var_name, description in required_vars.items():
        value = os.getenv(var_name)
        if value:
            # Ocultar valores sensibles
            if 'SECRET' in var_name or 'KEY' in var_name or 'TOKEN' in var_name:
                display_value = f"[{len(value)} caracteres]"
            elif 'URL' in var_name:
                display_value = f"[{value[:20]}...]"
            else:
                display_value = f"[configurado]"
            
            print(f"  ✅ {var_name}: {display_value}")
        else:
            print(f"  ❌ {var_name}: NO CONFIGURADO - {description}")
            all_ok = False
    
    print("\n📋 Variables opcionales:")
    for var_name, description in optional_vars.items():
        value = os.getenv(var_name)
        if value:
            print(f"  ✅ {var_name}: [configurado]")
        else:
            print(f"  ⚪ {var_name}: no configurado (opcional)")
    
    # Verificar configuración específica
    print("\n🎯 Verificaciones específicas:")
    
    railway_env = os.getenv('RAILWAY_ENVIRONMENT')
    if railway_env:
        if railway_env in ['staging', 'production']:
            print(f"  ✅ RAILWAY_ENVIRONMENT válido: {railway_env}")
        else:
            print(f"  ⚠️  RAILWAY_ENVIRONMENT valor inválido: {railway_env}")
            print("      Debe ser: staging o production")
            all_ok = False
    
    google_redirect = os.getenv('GOOGLE_REDIRECT_URI')
    if google_redirect:
        if railway_env == 'staging' and 'staging' not in google_redirect.lower():
            print(f"  ⚠️  GOOGLE_REDIRECT_URI podría no ser para staging")
        elif railway_env == 'production' and any(x in google_redirect.lower() for x in ['staging', 'test', 'dev']):
            print(f"  ⚠️  GOOGLE_REDIRECT_URI podría no ser para production")
        else:
            print(f"  ✅ GOOGLE_REDIRECT_URI parece correcto para {railway_env}")
    
    # Resumen
    print(f"\n📊 RESUMEN:")
    if all_ok:
        print("  🎉 Todas las variables requeridas están configuradas")
        print("  ✅ Listo para continuar con las migraciones")
    else:
        print("  ❌ Faltan variables requeridas")
        print("  ⏳ Configura las variables faltantes antes de continuar")
    
    return all_ok

if __name__ == "__main__":
    check_environment_variables()
