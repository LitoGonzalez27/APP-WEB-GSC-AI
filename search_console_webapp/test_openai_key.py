#!/usr/bin/env python3
"""
Script para probar la API key de OpenAI

Uso:
    export OPENAI_API_KEY="tu-api-key"
    python3 test_openai_key.py
    
O pasar como argumento:
    python3 test_openai_key.py sk-proj-...
"""

import sys
import os

def test_openai_key(api_key=None):
    # Obtener API key
    if not api_key:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ ERROR: No se proporcionó API key")
        print()
        print("Opciones:")
        print("1. Exportar variable de entorno:")
        print("   export OPENAI_API_KEY='tu-api-key'")
        print()
        print("2. Pasar como argumento:")
        print("   python3 test_openai_key.py sk-proj-...")
        return False
    
    print("=" * 80)
    print("🧪 TESTING OPENAI API KEY")
    print("=" * 80)
    print()
    
    print("🔑 API Key:")
    print(f"   Primeros 20 caracteres: {api_key[:20]}...")
    print(f"   Últimos 20 caracteres: ...{api_key[-20:]}")
    print(f"   Longitud: {len(api_key)} caracteres")
    print()
    
    try:
        print("📦 Importando librería OpenAI...")
        import openai
        print("   ✅ Librería importada correctamente")
        print()
        
        print("🔧 Configurando cliente...")
        client = openai.OpenAI(api_key=api_key)
        print("   ✅ Cliente configurado")
        print()
        
        print("🚀 Haciendo llamada de prueba...")
        print("   Modelo: gpt-4o-mini")
        print("   Prompt: '¿Qué es Python?'")
        print()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Di solo 'OK' si puedes leer esto"}
            ],
            max_tokens=10
        )
        
        print("   ✅ RESPUESTA RECIBIDA:")
        print(f"      {response.choices[0].message.content}")
        print()
        
        print("📊 Detalles de la respuesta:")
        print(f"   ID: {response.id}")
        print(f"   Modelo: {response.model}")
        print(f"   Tokens usados: {response.usage.total_tokens}")
        print(f"   - Input: {response.usage.prompt_tokens}")
        print(f"   - Output: {response.usage.completion_tokens}")
        print()
        
        print("=" * 80)
        print("✅ LA API KEY DE OPENAI ES VÁLIDA Y FUNCIONA CORRECTAMENTE")
        print("=" * 80)
        
        return True
        
    except openai.AuthenticationError as e:
        print("=" * 80)
        print("❌ ERROR DE AUTENTICACIÓN")
        print("=" * 80)
        print(f"   {str(e)}")
        print()
        print("   Posibles causas:")
        print("   1. La API key es inválida o está mal copiada")
        print("   2. La API key ha sido revocada")
        print("   3. La API key ha expirado")
        print()
        return False
        
    except openai.RateLimitError as e:
        print("=" * 80)
        print("⚠️ ERROR DE RATE LIMIT")
        print("=" * 80)
        print(f"   {str(e)}")
        print()
        print("   La API key es válida pero:")
        print("   - Has excedido tu cuota de uso")
        print("   - Necesitas esperar o aumentar tu límite")
        print()
        return False
        
    except openai.APIError as e:
        print("=" * 80)
        print("❌ ERROR DE API")
        print("=" * 80)
        print(f"   {str(e)}")
        print()
        return False
        
    except Exception as e:
        print("=" * 80)
        print("💥 ERROR INESPERADO")
        print("=" * 80)
        print(f"   {type(e).__name__}: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Obtener API key de argumento o variable de entorno
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    success = test_openai_key(api_key)
    sys.exit(0 if success else 1)

