#!/usr/bin/env python3
"""
Buscar usuario por ID en base de datos
======================================
"""

import os
import sys
from database import get_db_connection

def find_user_by_id(user_id: int):
    """Busca usuario por ID"""
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Error conectando a base de datos")
            return None
        
        cur = conn.cursor()
        cur.execute('''
            SELECT 
                id, email, name, role, is_active, 
                plan, billing_status, quota_limit, quota_used,
                stripe_customer_id, subscription_id,
                created_at, updated_at
            FROM users 
            WHERE id = %s
        ''', (user_id,))
        
        user = cur.fetchone()
        conn.close()
        
        if not user:
            print(f"❌ Usuario ID {user_id} no encontrado")
            return None
        
        user_dict = dict(user)
        
        print(f"📊 USUARIO ID {user_id}:")
        print(f"   Email: {user_dict['email']}")
        print(f"   Nombre: {user_dict['name']}")
        print(f"   Plan: {user_dict.get('plan', 'N/A')}")
        print(f"   Billing Status: {user_dict.get('billing_status', 'N/A')}")
        print(f"   Quota Limit: {user_dict.get('quota_limit', 'N/A')}")
        print(f"   Stripe Customer ID: {user_dict.get('stripe_customer_id', 'N/A')}")
        print(f"   Creado: {user_dict['created_at']}")
        
        return user_dict
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 find_user_by_id.py <user_id>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    find_user_by_id(user_id)
