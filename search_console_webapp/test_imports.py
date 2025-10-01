#!/usr/bin/env python3
"""
Script de diagnóstico para verificar imports del Manual AI System
"""

import sys
import traceback

print("=" * 80)
print("🔍 DIAGNÓSTICO DE IMPORTS - MANUAL AI SYSTEM")
print("=" * 80)

# Test 1: Import básico de database
print("\n1️⃣ Testeando import de database...")
try:
    from database import get_db_connection
    print("✅ database.get_db_connection: OK")
except Exception as e:
    print(f"❌ database.get_db_connection: FAILED")
    print(f"   Error: {e}")
    traceback.print_exc()

# Test 2: Import de quota_manager
print("\n2️⃣ Testeando import de quota_manager...")
try:
    from quota_manager import get_user_quota_status
    print("✅ quota_manager: OK")
except Exception as e:
    print(f"❌ quota_manager: FAILED")
    print(f"   Error: {e}")
    traceback.print_exc()

# Test 3: Import de quota_middleware
print("\n3️⃣ Testeando import de quota_middleware...")
try:
    from quota_middleware import quota_protected_serp_call
    print("✅ quota_middleware: OK")
except Exception as e:
    print(f"❌ quota_middleware: FAILED")
    print(f"   Error: {e}")
    traceback.print_exc()

# Test 4: Import de serp_service
print("\n4️⃣ Testeando import de services.serp_service...")
try:
    from services.serp_service import get_serp_json
    print("✅ services.serp_service.get_serp_json: OK")
    print(f"   Tipo: {type(get_serp_json)}")
    print(f"   Callable: {callable(get_serp_json)}")
except Exception as e:
    print(f"❌ services.serp_service.get_serp_json: FAILED")
    print(f"   Error: {e}")
    print(f"\n📋 Traceback completo:")
    traceback.print_exc()

# Test 5: Import de ai_analysis
print("\n5️⃣ Testeando import de services.ai_analysis...")
try:
    from services.ai_analysis import detect_ai_overview_elements
    print("✅ services.ai_analysis.detect_ai_overview_elements: OK")
except Exception as e:
    print(f"❌ services.ai_analysis: FAILED")
    print(f"   Error: {e}")
    traceback.print_exc()

# Test 6: Import de ai_cache
print("\n6️⃣ Testeando import de services.ai_cache...")
try:
    from services.ai_cache import ai_cache
    print("✅ services.ai_cache: OK")
except Exception as e:
    print(f"❌ services.ai_cache: FAILED")
    print(f"   Error: {e}")
    traceback.print_exc()

# Test 7: Import completo de manual_ai_system
print("\n7️⃣ Testeando import completo de manual_ai_system...")
try:
    import manual_ai_system
    print("✅ manual_ai_system: OK")
    print(f"   get_serp_json disponible: {manual_ai_system.get_serp_json is not None}")
    print(f"   Valor de get_serp_json: {manual_ai_system.get_serp_json}")
except Exception as e:
    print(f"❌ manual_ai_system: FAILED")
    print(f"   Error: {e}")
    traceback.print_exc()

print("\n" + "=" * 80)
print("🏁 DIAGNÓSTICO COMPLETADO")
print("=" * 80)

