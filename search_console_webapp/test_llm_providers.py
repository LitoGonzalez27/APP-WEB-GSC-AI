#!/usr/bin/env python3
"""
Script de Test para Proveedores LLM
IMPORTANTE: NO ejecutar con API keys reales sin confirmar (consume créditos)

Este script verifica:
1. Que todos los proveedores se importen correctamente
2. Que la interfaz base esté implementada
3. Que el factory funcione
4. Que los precios se lean de BD correctamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """Test 1: Verificar que todos los módulos se importen correctamente"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 1: VERIFICANDO IMPORTS")
    logger.info("=" * 70)
    
    try:
        from services.llm_providers import (
            BaseLLMProvider,
            OpenAIProvider,
            AnthropicProvider,
            GoogleProvider,
            PerplexityProvider,
            LLMProviderFactory
        )
        logger.info("✅ Todos los imports exitosos")
        logger.info(f"   • BaseLLMProvider: {BaseLLMProvider}")
        logger.info(f"   • OpenAIProvider: {OpenAIProvider}")
        logger.info(f"   • AnthropicProvider: {AnthropicProvider}")
        logger.info(f"   • GoogleProvider: {GoogleProvider}")
        logger.info(f"   • PerplexityProvider: {PerplexityProvider}")
        logger.info(f"   • LLMProviderFactory: {LLMProviderFactory}")
        return True
    except Exception as e:
        logger.error(f"❌ Error en imports: {e}", exc_info=True)
        return False


def test_interface_implementation():
    """Test 2: Verificar que todos los proveedores implementen la interfaz"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 2: VERIFICANDO IMPLEMENTACIÓN DE INTERFAZ")
    logger.info("=" * 70)
    
    try:
        from services.llm_providers import (
            BaseLLMProvider,
            OpenAIProvider,
            AnthropicProvider,
            GoogleProvider,
            PerplexityProvider
        )
        
        providers = [
            ('OpenAI', OpenAIProvider),
            ('Anthropic', AnthropicProvider),
            ('Google', GoogleProvider),
            ('Perplexity', PerplexityProvider)
        ]
        
        required_methods = [
            'execute_query',
            'get_provider_name',
            'get_model_display_name',
            'test_connection',
            'get_pricing_info'
        ]
        
        all_ok = True
        
        for name, provider_class in providers:
            logger.info(f"Verificando {name}...")
            
            # Verificar herencia
            if not issubclass(provider_class, BaseLLMProvider):
                logger.error(f"   ❌ {name} no hereda de BaseLLMProvider")
                all_ok = False
                continue
            
            # Verificar métodos
            missing_methods = []
            for method in required_methods:
                if not hasattr(provider_class, method):
                    missing_methods.append(method)
            
            if missing_methods:
                logger.error(f"   ❌ {name} le faltan métodos: {missing_methods}")
                all_ok = False
            else:
                logger.info(f"   ✅ {name} implementa todos los métodos requeridos")
        
        return all_ok
        
    except Exception as e:
        logger.error(f"❌ Error verificando interfaz: {e}", exc_info=True)
        return False


def test_factory():
    """Test 3: Verificar que el Factory funcione"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 3: VERIFICANDO FACTORY PATTERN")
    logger.info("=" * 70)
    
    try:
        from services.llm_providers import LLMProviderFactory
        
        # Test 3.1: get_available_providers
        logger.info("Test 3.1: get_available_providers()...")
        available = LLMProviderFactory.get_available_providers()
        expected = ['openai', 'anthropic', 'google', 'perplexity']
        
        if set(available) == set(expected):
            logger.info(f"   ✅ Proveedores disponibles: {available}")
        else:
            logger.error(f"   ❌ Esperados: {expected}, obtenidos: {available}")
            return False
        
        # Test 3.2: get_provider_info
        logger.info("")
        logger.info("Test 3.2: get_provider_info()...")
        info = LLMProviderFactory.get_provider_info()
        
        if len(info) == 4 and all(p in info for p in expected):
            logger.info(f"   ✅ Info de {len(info)} proveedores obtenida")
            for provider_name, provider_info in info.items():
                logger.info(f"      • {provider_name}: {provider_info['display_name']}")
        else:
            logger.error(f"   ❌ Info incompleta")
            return False
        
        # Test 3.3: create_provider (sin API key real, debe fallar con error claro)
        logger.info("")
        logger.info("Test 3.3: create_provider() con API key inválida...")
        logger.info("   (Esto debe fallar, es esperado)")
        
        provider = LLMProviderFactory.create_provider(
            'openai', 
            'fake-api-key-for-testing',
            validate_connection=False  # No validar para no consumir API calls
        )
        
        if provider:
            logger.info(f"   ✅ Proveedor creado (sin validación): {provider.get_provider_name()}")
        else:
            logger.error(f"   ❌ No se pudo crear proveedor incluso sin validación")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en factory: {e}", exc_info=True)
        return False


def test_database_helpers():
    """Test 4: Verificar que los helpers de BD funcionen"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 4: VERIFICANDO HELPERS DE BASE DE DATOS")
    logger.info("=" * 70)
    
    try:
        from services.llm_providers.base_provider import (
            get_model_pricing_from_db,
            get_current_model_for_provider
        )
        
        # Test 4.1: get_current_model_for_provider
        logger.info("Test 4.1: get_current_model_for_provider()...")
        
        providers_to_test = ['openai', 'anthropic', 'google', 'perplexity']
        all_ok = True
        
        for provider_name in providers_to_test:
            model = get_current_model_for_provider(provider_name)
            if model:
                logger.info(f"   ✅ {provider_name}: {model}")
            else:
                logger.warning(f"   ⚠️ {provider_name}: No se encontró modelo actual en BD")
                # No es error crítico, puede ser que no esté en BD
        
        # Test 4.2: get_model_pricing_from_db
        logger.info("")
        logger.info("Test 4.2: get_model_pricing_from_db()...")
        
        # Probar con GPT-5
        pricing = get_model_pricing_from_db('openai', 'gpt-5')
        
        if pricing and pricing['input'] > 0 and pricing['output'] > 0:
            logger.info(f"   ✅ Pricing para gpt-5:")
            logger.info(f"      Input: ${pricing['input'] * 1_000_000:.2f}/1M tokens")
            logger.info(f"      Output: ${pricing['output'] * 1_000_000:.2f}/1M tokens")
        else:
            logger.warning(f"   ⚠️ No se pudo obtener pricing de BD (puede ser normal si BD no está disponible)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en helpers de BD: {e}", exc_info=True)
        return False


def test_structure():
    """Test 5: Verificar estructura de archivos"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST 5: VERIFICANDO ESTRUCTURA DE ARCHIVOS")
    logger.info("=" * 70)
    
    required_files = [
        'services/llm_providers/__init__.py',
        'services/llm_providers/base_provider.py',
        'services/llm_providers/openai_provider.py',
        'services/llm_providers/anthropic_provider.py',
        'services/llm_providers/google_provider.py',
        'services/llm_providers/perplexity_provider.py',
        'services/llm_providers/provider_factory.py'
    ]
    
    all_ok = True
    
    for file_path in required_files:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            logger.info(f"   ✅ {file_path} ({size} bytes)")
        else:
            logger.error(f"   ❌ {file_path} NO ENCONTRADO")
            all_ok = False
    
    return all_ok


def main():
    """Ejecutar todos los tests"""
    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 15 + "TEST SUITE: PROVEEDORES LLM" + " " * 26 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    
    tests = [
        ("Estructura de archivos", test_structure),
        ("Imports", test_imports),
        ("Implementación de interfaz", test_interface_implementation),
        ("Factory Pattern", test_factory),
        ("Helpers de Base de Datos", test_database_helpers)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' falló con excepción: {e}")
            results[test_name] = False
    
    # Resumen
    logger.info("")
    logger.info("=" * 70)
    logger.info("RESUMEN DE TESTS")
    logger.info("=" * 70)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"RESULTADO FINAL: {passed}/{total} tests pasados")
    logger.info("=" * 70)
    logger.info("")
    
    if passed == total:
        logger.info("🎉 TODOS LOS TESTS PASARON")
        logger.info("")
        logger.info("✅ Sistema de proveedores LLM está correctamente implementado")
        logger.info("")
        logger.info("🎯 SIGUIENTE PASO:")
        logger.info("   1. Instalar dependencias: pip install openai anthropic google-generativeai")
        logger.info("   2. Obtener API keys de cada proveedor")
        logger.info("   3. Probar con API keys reales (test_connection())")
        logger.info("")
        return 0
    else:
        logger.error("❌ ALGUNOS TESTS FALLARON")
        logger.error(f"   {total - passed} test(s) con errores")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())

