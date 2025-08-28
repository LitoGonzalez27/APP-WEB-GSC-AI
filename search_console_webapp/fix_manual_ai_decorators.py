#!/usr/bin/env python3
"""
Script para cambiar @ai_user_required por @auth_required + control de plan
en todas las rutas de Manual AI
"""

import re

def fix_manual_ai_decorators():
    """Cambia todos los decoradores de Manual AI"""
    
    # Leer el archivo
    with open('manual_ai_system.py', 'r') as f:
        content = f.read()
    
    # Patrón para encontrar rutas con @ai_user_required
    pattern = r'(@manual_ai_bp\.route\([^)]+\)\s*\n)@ai_user_required(\s*\ndef\s+\w+\([^)]*\):\s*\n\s*"""[^"]*"""\s*\n\s*user = get_current_user\(\))'
    
    # Replacement con el nuevo patrón
    replacement = r'\1@auth_required\2\n    \n    # ✅ NUEVO FASE 4.5: Control por plan, no por rol\n    has_access, error_response = check_manual_ai_access(user)\n    if not has_access:\n        return jsonify(error_response), 402'
    
    # Hacer el reemplazo
    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Verificar cuántos cambios se hicieron
    original_count = content.count('@ai_user_required')
    new_count = new_content.count('@ai_user_required')
    changed = original_count - new_count
    
    print(f"📊 Rutas cambiadas: {changed}")
    print(f"📊 Rutas restantes con @ai_user_required: {new_count}")
    
    if changed > 0:
        # Escribir el archivo actualizado
        with open('manual_ai_system.py', 'w') as f:
            f.write(new_content)
        print("✅ Archivo actualizado")
    else:
        print("⚠️ No se encontraron patrones para cambiar")
    
    # Mostrar las rutas que quedaron sin cambiar (si las hay)
    if new_count > 0:
        remaining_matches = re.findall(r'@ai_user_required.*?def\s+(\w+)', new_content, re.DOTALL)
        print(f"🔍 Rutas restantes: {remaining_matches}")

if __name__ == "__main__":
    print("🔧 CAMBIANDO DECORADORES DE MANUAL AI")
    print("="*50)
    fix_manual_ai_decorators()
