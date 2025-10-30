#!/usr/bin/env python3
"""
Script para corregir la configuración del proyecto 3 (Test 3 LLM)

PROBLEMA: Brand name está como 'ivi.es' cuando debería ser 'ginemed.es'
SOLUCIÓN: Invertir brand_name con ginemed.es y poner IVI en competidores
"""

from database import get_db_connection

def fix_project_config():
    """Corrige la configuración del proyecto 3"""
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cursor = conn.cursor()
        
        print("="*80)
        print("🔧 CORRIGIENDO CONFIGURACIÓN DEL PROYECTO 3")
        print("="*80)
        print()
        
        # 1. Mostrar configuración actual
        cursor.execute("""
            SELECT brand_name, competitors
            FROM llm_monitoring_projects
            WHERE id = 3
        """)
        
        current = cursor.fetchone()
        
        if not current:
            print("❌ No se encontró proyecto con ID=3")
            return False
        
        print("📋 CONFIGURACIÓN ACTUAL:")
        print(f"   Brand Name: '{current['brand_name']}'")
        print(f"   Competidores: {current['competitors']}")
        print()
        
        # 2. Nueva configuración
        new_brand_name = 'ginemed.es'
        new_competitors = [
            'ivi.es',
            'hmfertilitycenter.com',
            'ginefiv.com',
            'reproduccionasistida.org'
        ]
        
        print("🎯 NUEVA CONFIGURACIÓN:")
        print(f"   Brand Name: '{new_brand_name}'")
        print(f"   Competidores: {new_competitors}")
        print()
        
        # 3. Confirmar
        confirm = input("¿Aplicar estos cambios? (s/n): ")
        
        if confirm.lower() != 's':
            print("❌ Operación cancelada")
            return False
        
        # 4. Actualizar (convertir competitors a JSON)
        import json
        cursor.execute("""
            UPDATE llm_monitoring_projects
            SET 
                brand_name = %s,
                competitors = %s::jsonb,
                updated_at = NOW()
            WHERE id = 3
        """, (new_brand_name, json.dumps(new_competitors)))
        
        conn.commit()
        
        print()
        print("="*80)
        print("✅ CONFIGURACIÓN ACTUALIZADA EXITOSAMENTE")
        print("="*80)
        print()
        print("📋 PRÓXIMOS PASOS:")
        print("   1. Volver a LLM Monitoring")
        print("   2. Click en 'Run Analysis' para re-ejecutar con la configuración correcta")
        print("   3. Ahora deberías ver:")
        print("      ✅ Ginemed como TU marca (mention rate correcto)")
        print("      ✅ IVI como competidor en Share of Voice")
        print("      ✅ Datos correctos de OpenAI")
        print()
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    fix_project_config()

