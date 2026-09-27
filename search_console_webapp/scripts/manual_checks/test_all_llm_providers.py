#!/usr/bin/env python3
"""
Script de diagnóstico para verificar que todos los proveedores LLM funcionan correctamente.
Ejecuta una prueba real con cada proveedor (OpenAI, Anthropic, Google, Perplexity).

USO:
    python3 -m scripts.manual_checks.test_all_llm_providers
    
    # En Railway:
    railway run python3 -m scripts.manual_checks.test_all_llm_providers
"""

import os
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_all_providers():
    """Prueba todos los proveedores LLM"""
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🧪 DIAGNÓSTICO DE PROVEEDORES LLM")
    logger.info("=" * 70)
    logger.info(f"   Fecha: {datetime.now().isoformat()}")
    logger.info("")
    
    # Verificar API keys
    logger.info("1️⃣ VERIFICANDO API KEYS...")
    logger.info("-" * 50)
    
    api_keys = {
        'openai': os.getenv('OPENAI_API_KEY'),
        'anthropic': os.getenv('ANTHROPIC_API_KEY'),
        'google': os.getenv('GOOGLE_API_KEY'),
        'perplexity': os.getenv('PERPLEXITY_API_KEY')
    }
    
    available_providers = []
    for name, key in api_keys.items():
        if key:
            masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
            logger.info(f"   ✅ {name.upper()}_API_KEY: {masked_key}")
            available_providers.append(name)
        else:
            logger.warning(f"   ❌ {name.upper()}_API_KEY: No configurada")
    
    if not available_providers:
        logger.error("")
        logger.error("❌ No hay API keys configuradas. No se puede continuar.")
        return False
    
    logger.info("")
    logger.info(f"   📊 {len(available_providers)}/4 proveedores disponibles")
    logger.info("")
    
    # Importar el factory
    logger.info("2️⃣ IMPORTANDO MÓDULOS...")
    logger.info("-" * 50)
    
    try:
        from services.llm_providers import LLMProviderFactory
        logger.info("   ✅ LLMProviderFactory importado correctamente")
    except Exception as e:
        logger.error(f"   ❌ Error importando: {e}")
        return False
    
    logger.info("")
    
    # Probar cada proveedor
    logger.info("3️⃣ PROBANDO CADA PROVEEDOR...")
    logger.info("-" * 50)
    logger.info("")
    
    results = {}
    test_query = "Responde únicamente con la palabra 'OK' si me escuchas correctamente."
    
    for provider_name in available_providers:
        logger.info(f"🔧 Probando {provider_name.upper()}...")
        
        try:
            # Crear proveedor
            provider = LLMProviderFactory.create_provider(
                provider_name,
                api_keys[provider_name],
                validate_connection=True
            )
            
            if not provider:
                logger.error(f"   ❌ No se pudo crear el proveedor {provider_name}")
                results[provider_name] = {
                    'success': False,
                    'error': 'Failed to create provider'
                }
                continue
            
            logger.info(f"   📋 Modelo: {provider.model}")
            logger.info(f"   📋 Display: {provider.get_model_display_name()}")
            
            # Ejecutar query de prueba
            logger.info(f"   📤 Enviando query de prueba...")
            result = provider.execute_query(test_query)
            
            if result.get('success'):
                content = result.get('content', '')[:100]
                logger.info(f"   ✅ ÉXITO")
                logger.info(f"   📥 Respuesta: {content}")
                logger.info(f"   🔢 Tokens: {result.get('tokens', 0)}")
                logger.info(f"   💰 Coste: ${result.get('cost_usd', 0):.6f}")
                logger.info(f"   ⏱️  Tiempo: {result.get('response_time_ms', 0)}ms")
                logger.info(f"   🤖 Modelo usado: {result.get('model_used', 'N/A')}")
                
                results[provider_name] = {
                    'success': True,
                    'model': result.get('model_used'),
                    'tokens': result.get('tokens'),
                    'cost': result.get('cost_usd'),
                    'time_ms': result.get('response_time_ms')
                }
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"   ❌ FALLÓ: {error}")
                results[provider_name] = {
                    'success': False,
                    'error': error
                }
                
        except Exception as e:
            logger.error(f"   ❌ EXCEPCIÓN: {e}")
            results[provider_name] = {
                'success': False,
                'error': str(e)
            }
        
        logger.info("")
    
    # Resumen final
    logger.info("=" * 70)
    logger.info("📊 RESUMEN DE RESULTADOS")
    logger.info("=" * 70)
    logger.info("")
    
    successful = [name for name, r in results.items() if r.get('success')]
    failed = [name for name, r in results.items() if not r.get('success')]
    
    logger.info(f"   ✅ Exitosos: {len(successful)}/{len(results)}")
    for name in successful:
        r = results[name]
        logger.info(f"      • {name}: {r.get('model')} ({r.get('time_ms')}ms)")
    
    if failed:
        logger.info("")
        logger.info(f"   ❌ Fallidos: {len(failed)}/{len(results)}")
        for name in failed:
            r = results[name]
            logger.info(f"      • {name}: {r.get('error', 'Unknown')[:50]}")
    
    logger.info("")
    logger.info("=" * 70)
    
    # Verificar específicamente OpenAI
    if 'openai' in results:
        if results['openai'].get('success'):
            logger.info("🎉 OpenAI GPT-5.2 FUNCIONA CORRECTAMENTE")
            logger.info("   El próximo cron debería incluir análisis de ChatGPT")
        else:
            logger.error("⚠️  OpenAI FALLÓ - Revisar configuración")
            logger.error(f"   Error: {results['openai'].get('error')}")
    else:
        logger.warning("⚠️  OpenAI no fue probado (API key no configurada)")
    
    logger.info("=" * 70)
    logger.info("")
    
    # Determinar resultado global
    all_success = len(failed) == 0
    openai_success = results.get('openai', {}).get('success', False)
    
    if all_success:
        logger.info("✅ TODOS LOS PROVEEDORES FUNCIONAN CORRECTAMENTE")
        logger.info("   El próximo cron ejecutará análisis con todos los LLMs")
        return True
    elif openai_success:
        logger.warning("⚠️  ALGUNOS PROVEEDORES FALLARON, PERO OPENAI FUNCIONA")
        logger.warning("   El próximo cron incluirá ChatGPT pero puede faltar algún otro LLM")
        return True
    else:
        logger.error("❌ OPENAI NO FUNCIONA")
        logger.error("   Verifica la API key y la configuración")
        return False


def check_db_model_config():
    """Verifica la configuración del modelo en la base de datos"""
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🗄️  VERIFICANDO CONFIGURACIÓN EN BASE DE DATOS")
    logger.info("=" * 70)
    
    try:
        from database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            logger.error("   ❌ No se pudo conectar a la BD")
            return
        
        cur = conn.cursor()
        
        # Verificar modelo actual de OpenAI
        cur.execute("""
            SELECT model_id, model_display_name, is_current,
                   cost_per_1m_input_tokens, cost_per_1m_output_tokens
            FROM llm_model_registry
            WHERE llm_provider = 'openai' AND is_current = TRUE
        """)
        
        result = cur.fetchone()
        
        if result:
            logger.info("")
            logger.info("   📋 Modelo actual de OpenAI en BD:")
            logger.info(f"      • ID: {result['model_id']}")
            logger.info(f"      • Display: {result['model_display_name']}")
            logger.info(f"      • Pricing: ${result['cost_per_1m_input_tokens'] or 0:.2f}/${result['cost_per_1m_output_tokens'] or 0:.2f} per 1M")
            
            if result['model_id'] == 'gpt-5.2':
                logger.info("      ✅ GPT-5.2 está correctamente configurado")
            else:
                logger.warning(f"      ⚠️  El modelo actual NO es gpt-5.2, es {result['model_id']}")
                logger.warning("      Ejecuta: python update_to_gpt52.py")
        else:
            logger.warning("   ⚠️  No hay modelo de OpenAI marcado como actual")
            logger.warning("   Ejecuta: python update_to_gpt52.py")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"   ❌ Error verificando BD: {e}")


if __name__ == "__main__":
    logger.info("")
    logger.info("🚀 SCRIPT DE DIAGNÓSTICO DE PROVEEDORES LLM")
    logger.info("")
    
    # Verificar configuración en BD
    check_db_model_config()
    
    logger.info("")
    
    # Probar proveedores
    success = test_all_providers()
    
    sys.exit(0 if success else 1)

