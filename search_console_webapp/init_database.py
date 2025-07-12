#!/usr/bin/env python3
"""
Script para inicializar la base de datos y crear un usuario administrador inicial
"""

import os
import sys
from database import init_database, create_user, get_user_by_email, update_user_role, update_user_activity

def create_admin_user():
    """Crea un usuario administrador inicial"""
    admin_email = "admin@clicandseo.com"
    admin_name = "Administrador"
    admin_password = "admin123456"  # Cambiar en producción
    
    # Verificar si el admin ya existe
    existing_admin = get_user_by_email(admin_email)
    if existing_admin:
        print(f"✅ Usuario administrador ya existe: {admin_email}")
        
        # Asegurar que sea admin y esté activo
        if existing_admin['role'] != 'admin':
            update_user_role(existing_admin['id'], 'admin')
            print(f"✅ Rol actualizado a administrador")
        
        if not existing_admin['is_active']:
            update_user_activity(existing_admin['id'], True)
            print(f"✅ Usuario activado")
        
        return existing_admin
    
    # Crear nuevo usuario administrador
    print(f"📝 Creando usuario administrador: {admin_email}")
    user = create_user(
        email=admin_email,
        name=admin_name,
        password=admin_password
    )
    
    if user:
        # Actualizar rol a admin
        update_user_role(user['id'], 'admin')
        # Activar usuario
        update_user_activity(user['id'], True)
        
        print(f"✅ Usuario administrador creado exitosamente")
        print(f"   Email: {admin_email}")
        print(f"   Contraseña: {admin_password}")
        print(f"   ⚠️  IMPORTANTE: Cambiar la contraseña en producción")
        
        return user
    else:
        print(f"❌ Error creando usuario administrador")
        return None

def main():
    """Función principal"""
    print("🚀 Inicializando base de datos...")
    
    # Inicializar base de datos
    if init_database():
        print("✅ Base de datos inicializada correctamente")
    else:
        print("❌ Error inicializando base de datos")
        sys.exit(1)
    
    # Crear usuario administrador
    admin_user = create_admin_user()
    if not admin_user:
        print("❌ Error creando usuario administrador")
        sys.exit(1)
    
    print("\n🎉 Inicialización completada!")
    print("\n📋 Resumen:")
    print("   - Base de datos inicializada")
    print("   - Usuario administrador creado/verificado")
    print("   - Sistema listo para usar")
    print(f"\n🔗 Puedes acceder en: http://localhost:5001/login")
    print(f"   Email: admin@clicandseo.com")
    print(f"   Contraseña: admin123456")

if __name__ == "__main__":
    main() 