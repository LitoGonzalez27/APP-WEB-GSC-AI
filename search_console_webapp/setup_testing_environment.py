#!/usr/bin/env python3
"""
Setup Testing Environment - Configuración interactiva del entorno de testing
===========================================================================

Script para configurar fácilmente el entorno de testing de manera interactiva.
"""

import os
import subprocess
import sys

def print_header():
    """Imprimir header"""
    print("="*70)
    print("🔧 CONFIGURACIÓN DEL ENTORNO DE TESTING")
    print("="*70)
    print("Este script te ayudará a configurar todo lo necesario para testing")
    print("="*70)

def check_python_dependencies():
    """Verificar e instalar dependencias de Python"""
    print("\n📦 VERIFICANDO DEPENDENCIAS PYTHON...")
    
    required_packages = ['psycopg2', 'stripe', 'requests']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}: Instalado")
        except ImportError:
            print(f"  ❌ {package}: No encontrado")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📥 INSTALANDO PAQUETES FALTANTES: {', '.join(missing_packages)}")
        
        # Usar psycopg2-binary que es más fácil de instalar
        if 'psycopg2' in missing_packages:
            missing_packages.remove('psycopg2')
            missing_packages.append('psycopg2-binary')
        
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install'
            ] + missing_packages)
            print("✅ Paquetes instalados exitosamente")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error instalando paquetes: {e}")
            print("💡 Intenta manualmente: pip install psycopg2-binary stripe requests")
            return False
    else:
        print("✅ Todas las dependencias están instaladas")
        return True

def setup_database_url():
    """Configurar DATABASE_URL"""
    print("\n🗄️ CONFIGURANDO DATABASE_URL...")
    
    current_url = os.getenv('DATABASE_URL')
    
    if current_url:
        print(f"  ✅ DATABASE_URL ya configurado: {current_url[:50]}...")
        response = input("  ¿Quieres cambiarlo? (y/N): ").strip().lower()
        if response != 'y':
            return True
    
    print("\n📋 INSTRUCCIONES para obtener DATABASE_URL:")
    print("  1. Ve a tu proyecto de Railway")
    print("  2. Selecciona el servicio de base de datos")
    print("  3. Ve a 'Variables' tab")
    print("  4. Copia el valor de DATABASE_URL")
    print("  5. Debería empezar con: postgresql://postgres:...")
    
    while True:
        url = input("\n🔗 Pega tu DATABASE_URL aquí: ").strip()
        
        if not url:
            print("❌ URL no puede estar vacía")
            continue
        
        if not url.startswith('postgresql://'):
            print("⚠️ La URL debería empezar con 'postgresql://'")
            response = input("¿Continuar de todas formas? (y/N): ").strip().lower()
            if response != 'y':
                continue
        
        # Configurar la variable
        os.environ['DATABASE_URL'] = url
        print("✅ DATABASE_URL configurado")
        
        # Intentar conexión de prueba
        try:
            import psycopg2
            conn = psycopg2.connect(url)
            conn.close()
            print("✅ Conexión a base de datos exitosa")
            return True
        except Exception as e:
            print(f"⚠️ Error conectando a base de datos: {e}")
            response = input("¿Continuar de todas formas? (y/N): ").strip().lower()
            if response == 'y':
                return True
            # Si no, continuar el loop para pedir URL otra vez

def setup_stripe_keys():
    """Configurar claves de Stripe"""
    print("\n💳 CONFIGURANDO STRIPE API KEYS...")
    
    current_secret = os.getenv('STRIPE_SECRET_KEY')
    current_public = os.getenv('STRIPE_PUBLISHABLE_KEY')
    
    if current_secret and current_public:
        print(f"  ✅ STRIPE_SECRET_KEY ya configurado: {current_secret[:12]}...")
        print(f"  ✅ STRIPE_PUBLISHABLE_KEY ya configurado: {current_public[:12]}...")
        response = input("  ¿Quieres cambiarlos? (y/N): ").strip().lower()
        if response != 'y':
            return True
    
    print("\n📋 INSTRUCCIONES para obtener Stripe API Keys:")
    print("  1. Ve a https://dashboard.stripe.com/test/apikeys")
    print("  2. Asegúrate de estar en modo 'Test data'")
    print("  3. Copia 'Publishable key' (pk_test_...)")
    print("  4. Revela y copia 'Secret key' (sk_test_...)")
    print("  ⚠️ IMPORTANTE: Solo usar claves de TEST, nunca de producción")
    
    # Secret Key
    while True:
        secret_key = input("\n🔑 Pega tu STRIPE_SECRET_KEY (sk_test_...): ").strip()
        
        if not secret_key:
            print("❌ Secret key no puede estar vacía")
            continue
        
        if not secret_key.startswith('sk_test_'):
            print("🚨 PELIGRO: Esta clave no parece ser de TEST")
            print("   Las claves de test deben empezar con 'sk_test_'")
            response = input("   ¿Estás seguro que es de TEST? (y/N): ").strip().lower()
            if response != 'y':
                print("   Por favor usa solo claves de TEST para staging")
                continue
        
        os.environ['STRIPE_SECRET_KEY'] = secret_key
        print("✅ STRIPE_SECRET_KEY configurado")
        break
    
    # Publishable Key
    while True:
        public_key = input("\n🔑 Pega tu STRIPE_PUBLISHABLE_KEY (pk_test_...): ").strip()
        
        if not public_key:
            print("❌ Publishable key no puede estar vacía")
            continue
        
        if not public_key.startswith('pk_test_'):
            print("🚨 PELIGRO: Esta clave no parece ser de TEST")
            print("   Las claves de test deben empezar con 'pk_test_'")
            response = input("   ¿Estás seguro que es de TEST? (y/N): ").strip().lower()
            if response != 'y':
                print("   Por favor usa solo claves de TEST para staging")
                continue
        
        os.environ['STRIPE_PUBLISHABLE_KEY'] = public_key
        print("✅ STRIPE_PUBLISHABLE_KEY configurado")
        break
    
    # Verificar conexión con Stripe
    try:
        import stripe
        stripe.api_key = os.environ['STRIPE_SECRET_KEY']
        account = stripe.Account.retrieve()
        print(f"✅ Conexión a Stripe exitosa: {account.display_name}")
        print(f"✅ Modo TEST confirmado: {not account.livemode}")
        return True
    except Exception as e:
        print(f"⚠️ Error conectando a Stripe: {e}")
        response = input("¿Continuar de todas formas? (y/N): ").strip().lower()
        return response == 'y'

def create_env_file():
    """Crear archivo .env para persistir configuración"""
    print("\n💾 CREANDO ARCHIVO .env...")
    
    env_content = f"""# Variables de entorno para testing
# Generado automáticamente por setup_testing_environment.py

DATABASE_URL={os.getenv('DATABASE_URL', '')}
STRIPE_SECRET_KEY={os.getenv('STRIPE_SECRET_KEY', '')}
STRIPE_PUBLISHABLE_KEY={os.getenv('STRIPE_PUBLISHABLE_KEY', '')}

# Para cargar en futuras sesiones:
# source .env  (en bash)
# o usar: python-dotenv
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ Archivo .env creado")
        print("💡 Para futuras sesiones puedes usar: source .env")
        return True
    except Exception as e:
        print(f"⚠️ Error creando .env: {e}")
        return False

def show_next_steps():
    """Mostrar próximos pasos"""
    print("\n" + "="*70)
    print("🎯 CONFIGURACIÓN COMPLETADA")
    print("="*70)
    
    print("\n✅ Tu entorno está configurado. Próximos pasos:")
    print("\n1️⃣ EJECUTAR TESTS AUTOMATIZADOS:")
    print("   python3 run_full_staging_tests.py")
    
    print("\n2️⃣ SI LOS TESTS PASAN → TESTING MANUAL:")
    print("   - Abrir: checklist_manual_testing.md")
    print("   - Ir a: https://clicandseo.up.railway.app/admin/users")
    print("   - Seguir checklist paso a paso")
    
    print("\n3️⃣ REFERENCIAS ÚTILES:")
    print("   - Guía completa: README_TESTING_STAGING.md")
    print("   - Railway Dashboard: https://railway.app/dashboard")
    print("   - Stripe Dashboard: https://dashboard.stripe.com/test")
    
    print("\n🔄 SI NECESITAS RECONFIGURAR:")
    print("   python3 setup_testing_environment.py")
    
    print("\n" + "="*70)

def main():
    """Función principal"""
    print_header()
    
    # Paso 1: Dependencias Python
    if not check_python_dependencies():
        print("\n❌ No se pudieron instalar las dependencias")
        return False
    
    # Paso 2: DATABASE_URL
    if not setup_database_url():
        print("\n❌ No se pudo configurar DATABASE_URL")
        return False
    
    # Paso 3: Stripe Keys
    if not setup_stripe_keys():
        print("\n❌ No se pudieron configurar las claves de Stripe")
        return False
    
    # Paso 4: Crear .env file
    create_env_file()
    
    # Paso 5: Mostrar próximos pasos
    show_next_steps()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🎊 SETUP COMPLETADO EXITOSAMENTE")
        else:
            print("\n⚠️ SETUP INCOMPLETO - Revisar errores arriba")
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup cancelado por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        print("💡 Intenta ejecutar el script de nuevo")
