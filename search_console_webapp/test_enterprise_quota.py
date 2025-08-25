#!/usr/bin/env python3
"""
SCRIPT DE TESTING ENTERPRISE QUOTA
==================================

Asigna temporalmente una custom quota a un usuario para testing
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from admin_billing_panel import assign_custom_quota

def test_assign_enterprise():
    """Asigna custom quota a un usuario para testing"""
    
    # Usar usuario free para testing
    user_id = 30  # c.gonzalez@koomori.com
    custom_limit = 5000
    notes = "Testing Enterprise quota - CLI script"
    admin_id = 5  # cgonalba@gmail.com (admin)
    
    print("🧪 TESTING ENTERPRISE QUOTA ASSIGNMENT")
    print("=" * 50)
    print(f"Usuario: ID {user_id}")
    print(f"Custom limit: {custom_limit} RU")
    print(f"Admin: ID {admin_id}")
    print(f"Notes: {notes}")
    
    result = assign_custom_quota(user_id, custom_limit, notes, admin_id)
    
    if result['success']:
        print(f"\n✅ SUCCESS: {result['message']}")
        print(f"📅 Assigned date: {result['assigned_date']}")
        print(f"👨‍💼 Assigned by: {result['assigned_by']}")
        print(f"\n🔍 Verifica ahora en /admin/users")
        print(f"   Deberías ver el usuario con badge 'Enterprise' y custom quota")
    else:
        print(f"\n❌ ERROR: {result['error']}")

if __name__ == "__main__":
    test_assign_enterprise()
