#!/usr/bin/env python3
"""
Test del fix aplicado a create_user
"""

import sys
import os

# Añadir el directorio actual al path para importar database
sys.path.append('.')

def test_fixed_create_user():
    """Test de la función create_user corregida"""
    
    print("🧪 TESTING CREATE_USER CORREGIDA")
    print("="*50)
    
    try:
        from database import create_user
        
        # Test con datos similares a los que fallaban
        test_email = "test-fix@example.com"
        test_name = "Test Fix User"
        test_google_id = "999888777666555444"
        test_picture = "https://lh3.googleusercontent.com/test-fix"
        
        print(f"📧 Testing: {test_email}")
        
        result = create_user(
            email=test_email,
            name=test_name,
            google_id=test_google_id,
            picture=test_picture,
            auto_activate=True
        )
        
        if result:
            print(f"✅ SUCCESS!")
            print(f"   👤 Usuario creado: ID {result['id']}")
            print(f"   📧 Email: {result['email']}")
            print(f"   ✅ Activo: {result['is_active']}")
            print(f"   📋 Plan: {result.get('plan', 'N/A')}")
            
            # Limpiar usuario test
            from database import get_db_connection
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute('DELETE FROM users WHERE id = %s', (result['id'],))
                conn.commit()
                conn.close()
                print(f"   🧹 Usuario test eliminado")
            
            return True
        else:
            print(f"❌ FAILURE: create_user retornó None")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_cases():
    """Test múltiples casos para asegurar robustez"""
    
    print(f"\n🔄 TESTING MÚLTIPLES CASOS")
    print("="*40)
    
    test_cases = [
        {
            'email': 'test1-fix@example.com',
            'name': 'Test User 1',
            'google_id': '111111111111111111',
            'picture': 'https://example.com/pic1.jpg'
        },
        {
            'email': 'test2-fix@example.com', 
            'name': 'Test User 2',
            'google_id': '222222222222222222',
            'picture': None  # Test sin picture
        },
        {
            'email': 'test3-fix@example.com',
            'name': 'Test User 3', 
            'google_id': None,  # Test sin google_id
            'picture': 'https://example.com/pic3.jpg'
        }
    ]
    
    success_count = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}️⃣ Test case {i}: {test_case['email']}")
        
        try:
            from database import create_user
            
            result = create_user(
                email=test_case['email'],
                name=test_case['name'],
                google_id=test_case['google_id'],
                picture=test_case['picture'],
                auto_activate=True
            )
            
            if result:
                print(f"   ✅ SUCCESS: ID {result['id']}")
                success_count += 1
                
                # Cleanup
                from database import get_db_connection
                conn = get_db_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute('DELETE FROM users WHERE id = %s', (result['id'],))
                    conn.commit()
                    conn.close()
            else:
                print(f"   ❌ FAILURE")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    print(f"\n📊 RESULTADO: {success_count}/{len(test_cases)} casos exitosos")
    return success_count == len(test_cases)

if __name__ == "__main__":
    print("🔧 TESTING FIX PARA CREATE_USER")
    print("="*60)
    
    # Test básico
    basic_success = test_fixed_create_user()
    
    # Test múltiples casos
    multi_success = test_multiple_cases()
    
    print(f"\n🎯 RESUMEN FINAL:")
    print("="*30)
    print(f"Basic test: {'✅ PASS' if basic_success else '❌ FAIL'}")
    print(f"Multi test: {'✅ PASS' if multi_success else '❌ FAIL'}")
    
    if basic_success and multi_success:
        print(f"\n🎊 ¡FIX EXITOSO!")
        print(f"   La función create_user ahora funciona correctamente")
        print(f"   Los usuarios pueden registrarse sin problemas")
    else:
        print(f"\n⚠️ Aún hay problemas")
        print(f"   Revisar logs para más detalles")
