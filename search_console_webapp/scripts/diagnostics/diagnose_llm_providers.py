"""
Script de diagnóstico para LLM Providers

Testea cada proveedor LLM con un prompt específico para identificar problemas.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Importar providers
from services.llm_providers import LLMProviderFactory


def test_single_provider(provider_name: str, prompt: str):
    """
    Testea un proveedor específico con un prompt
    """
    print("\n" + "="*80)
    print(f"🧪 TESTEANDO {provider_name.upper()}")
    print("="*80)
    
    # Verificar API key
    api_key_env = {
        'openai': 'OPENAI_API_KEY',
        'google': 'GOOGLE_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'perplexity': 'PERPLEXITY_API_KEY'
    }
    
    env_var = api_key_env.get(provider_name)
    if not env_var:
        print(f"❌ Provider {provider_name} no reconocido")
        return False
    
    api_key = os.getenv(env_var)
    if not api_key:
        print(f"❌ Variable de entorno {env_var} no configurada")
        return False
    
    print(f"✅ API Key encontrada: {api_key[:15]}...")
    
    # Crear provider
    try:
        providers = LLMProviderFactory.create_all_providers(validate_connections=False)
        
        if provider_name not in providers:
            print(f"❌ No se pudo crear el provider {provider_name}")
            return False
        
        provider = providers[provider_name]
        print(f"✅ Provider creado correctamente")
        print(f"   Modelo: {provider.get_model_display_name()}")
        
    except Exception as e:
        print(f"❌ Error creando provider: {e}")
        logger.exception("Error detallado:")
        return False
    
    # Testear conexión
    print("\n🔌 Testeando conexión...")
    try:
        if provider.test_connection():
            print("✅ Conexión exitosa")
        else:
            print("⚠️ Test de conexión falló")
    except Exception as e:
        print(f"❌ Error en test de conexión: {e}")
    
    # Ejecutar query
    print(f"\n📝 Ejecutando query:")
    print(f"   '{prompt[:70]}...'")
    print()
    
    try:
        result = provider.execute_query(prompt)
        
        if result['success']:
            print("✅ Query ejecutada exitosamente")
            print(f"\n📄 RESPUESTA:")
            print("-" * 80)
            content = result.get('content', '')
            print(content[:500] + ("..." if len(content) > 500 else ""))
            print("-" * 80)
            print(f"\n📊 MÉTRICAS:")
            print(f"   Tokens: {result.get('tokens', 0)}")
            print(f"   Costo: ${result.get('cost_usd', 0):.6f}")
            print(f"   Tiempo: {result.get('response_time_ms', 0)}ms")
            print(f"   Modelo usado: {result.get('model_used', 'N/A')}")
            if result.get('sources'):
                print(f"   Fuentes: {len(result.get('sources', []))} URLs encontradas")
            return True
        else:
            print(f"❌ Query falló")
            print(f"   Error: {result.get('error', 'Sin mensaje de error')}")
            return False
            
    except Exception as e:
        print(f"❌ Excepción durante ejecución: {e}")
        logger.exception("Error detallado:")
        return False


def main():
    """
    Función principal
    """
    print("\n" + "🔬 DIAGNÓSTICO DE LLM PROVIDERS ".center(80, "="))
    print()
    
    # Prompt de prueba
    test_prompt = "¿Qué alternativas a la FIV existen para parejas con problemas de fertilidad?"
    
    print(f"📝 Prompt de prueba:")
    print(f"   {test_prompt}")
    
    # Providers a testear
    providers_to_test = ['openai', 'google', 'anthropic', 'perplexity']
    
    results = {}
    
    for provider_name in providers_to_test:
        success = test_single_provider(provider_name, test_prompt)
        results[provider_name] = success
    
    # Resumen
    print("\n" + "📊 RESUMEN ".center(80, "="))
    print()
    
    for provider_name, success in results.items():
        status = "✅ OK" if success else "❌ FALLÓ"
        print(f"{provider_name.ljust(20)} {status}")
    
    successful = sum(1 for s in results.values() if s)
    total = len(results)
    
    print()
    print(f"Total exitosos: {successful}/{total}")
    
    if successful < total:
        print("\n⚠️ Algunos providers fallaron. Revisa los logs arriba para más detalles.")
        return 1
    else:
        print("\n✅ Todos los providers funcionan correctamente")
        return 0


if __name__ == '__main__':
    sys.exit(main())

