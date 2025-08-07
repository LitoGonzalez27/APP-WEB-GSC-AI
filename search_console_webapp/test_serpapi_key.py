#!/usr/bin/env python3
"""
Script de verificación para SERPAPI_KEY
Uso: python3 test_serpapi_key.py
"""

import os
import json
from services.serp_service import get_serp_json

def test_serpapi_key():
    """Verificar si SERPAPI_KEY está configurada y funciona"""
    
    print("🔍 VERIFICANDO CONFIGURACIÓN SERPAPI_KEY")
    print("=" * 50)
    
    # 1. Verificar variable de entorno
    api_key = os.getenv('SERPAPI_KEY')
    
    if not api_key:
        print("❌ SERPAPI_KEY no está configurada")
        print(f"📊 Variables disponibles con 'API' o 'KEY': {[k for k in os.environ.keys() if 'API' in k or 'KEY' in k]}")
        return False
    
    print(f"✅ SERPAPI_KEY encontrada: {api_key[:10]}...{api_key[-10:]}")
    
    # 2. Probar una búsqueda simple
    print("\n🧪 Probando búsqueda de prueba...")
    
    test_params = {
        'engine': 'google',
        'q': 'test query',
        'api_key': api_key,
        'num': 5,
        'location': 'Spain',
        'gl': 'es',
        'hl': 'es'
    }
    
    try:
        serp_data = get_serp_json(test_params)
        
        if serp_data and not serp_data.get('error'):
            print("✅ API Key funciona correctamente")
            print(f"📊 Resultados obtenidos: {len(serp_data.get('organic_results', []))}")
            
            # Verificar si hay AI Overview
            ai_overview = serp_data.get('ai_overview')
            if ai_overview:
                print("🤖 AI Overview detectado en resultados de prueba")
            else:
                print("ℹ️  No hay AI Overview en esta búsqueda de prueba (normal)")
                
            return True
        else:
            print(f"❌ Error en API: {serp_data.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Excepción al probar API: {e}")
        return False

def main():
    """Función principal"""
    success = test_serpapi_key()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SERPAPI_KEY está configurada y funciona correctamente")
        print("✅ El análisis Manual AI debería funcionar")
    else:
        print("⚠️  SERPAPI_KEY tiene problemas")
        print("📋 Revisa la configuración en Railway:")
        print("   1. Settings → Environment → Variables")
        print("   2. Verificar SERPAPI_KEY sin comillas ni espacios")
        print("   3. Redeploy después de cambios")

if __name__ == '__main__':
    main()