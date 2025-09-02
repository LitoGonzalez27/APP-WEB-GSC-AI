#!/usr/bin/env python3
# test_email_config.py - Script para probar la configuración de email

import sys
import os
from email_service import send_test_email

def main():
    print("🧪 ClicandSEO - Test de Configuración SMTP")
    print("=" * 50)
    
    # Verificar variables de entorno
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    print(f"📧 Servidor SMTP: {smtp_server}")
    print(f"🔌 Puerto: {smtp_port}")
    print(f"👤 Usuario: {smtp_username}")
    print(f"🔑 Contraseña: {'✅ Configurada' if smtp_password else '❌ No configurada'}")
    print()
    
    if not smtp_password:
        print("❌ Error: SMTP_PASSWORD no está configurada")
        print()
        print("Para configurar:")
        print("1. Copia el archivo .env.smtp.example como .env")
        print("2. Edita .env y agrega tu contraseña de email")
        print("3. Ejecuta este script nuevamente")
        return False
    
    # Solicitar email de prueba
    test_email = input("Ingresa tu email para enviar prueba: ").strip()
    
    if not test_email or '@' not in test_email:
        print("❌ Email inválido")
        return False
    
    print(f"\n📤 Enviando email de prueba a {test_email}...")
    
    try:
        success = send_test_email(test_email)
        
        if success:
            print("✅ ¡Email de prueba enviado exitosamente!")
            print()
            print("🎉 Configuración SMTP funcionando correctamente")
            print("💡 El sistema de password reset ya está listo para usar")
        else:
            print("❌ Error enviando email de prueba")
            print()
            print("Posibles causas:")
            print("- Contraseña incorrecta")
            print("- Configuración del servidor incorrecta")
            print("- Problemas de conectividad")
            
        return success
        
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
