"""
Script para probar la corrección de detección de menciones de marca
Usa datos reales del proyecto 4 (Quipu)
"""

import logging
from services.llm_monitoring_service import MultiLLMMonitoringService
from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def test_brand_detection():
    """Prueba la detección de marca con datos reales"""
    
    logger.info("=" * 70)
    logger.info("🧪 TEST: Brand Detection Fix")
    logger.info("=" * 70)
    
    # Configuración del proyecto 4 (Quipu)
    brand_name = "quipu"
    brand_domain = "getquipu.com"
    brand_keywords = ["quipu", "getquipu", "youtube de quipu"]
    
    # Crear servicio con API keys dummy (solo necesitamos la función de análisis)
    # No vamos a ejecutar queries, solo análisis de menciones
    service = MultiLLMMonitoringService.__new__(MultiLLMMonitoringService)
    # Inicializar solo lo necesario
    service.logger = logger
    
    # ==================================================
    # TEST 1: OpenAI - Texto con "Quipu"
    # ==================================================
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: OpenAI - Texto con 'Quipu encaja muy bien...'")
    logger.info("=" * 70)
    
    openai_text = """Sí, suele ser una buena opción para autónomos que quieren algo sencillo y "todo en uno" para facturar y cumplir con Hacienda en España.

Lo mejor
- Fácil de usar: crear facturas/rectificativas/recurrentes, presupuestos y albaranes sin complicaciones.
- Impuestos guiados: calcula IVA/IRPF y genera los modelos (303, 130, etc.) automáticamente.
- Sincronización bancaria: importa movimientos para cuadrar ingresos y gastos fácilmente.
- Interfaz clara: panel sencillo, sin exceso de funciones que confundan.
- Soporte específico para autónomos en España: preparado para AEAT, SII, etc.

A mejorar
- Integraciones limitadas: no tantas conexiones con tiendas online o herramientas externas como otros.
- Funciones avanzadas: si necesitas gestión de inventario profunda, automatizaciones complejas o CRM, puede quedarse corto.

Alternativas a considerar (según necesidad)
- Holded: más completo (inventario, CRM, proyectos), pero también más complejo.
- Sage: si buscas algo más robusto para crecer, pero con curva de aprendizaje mayor.
- Zoho Invoice (freemium): si solo necesitas facturación sin contabilidad completa.

Recomendación práctica
- Si tu prioridad es emitir facturas, registrar gastos, conciliar el banco y presentar impuestos sin líos, Quipu encaja muy bien para autónomos y microempresas.
- Si dependes de integraciones avanzadas (tienda online, stock, automatizaciones) quizá te convenga mirar alternativas."""
    
    result_1 = service.analyze_brand_mention(
        response_text=openai_text,
        brand_name=brand_name,
        brand_domain=brand_domain,
        brand_keywords=brand_keywords,
        sources=[]  # OpenAI no tiene sources
    )
    
    logger.info(f"\n📊 Resultado:")
    logger.info(f"  brand_mentioned: {result_1['brand_mentioned']}")
    logger.info(f"  mention_count: {result_1['mention_count']}")
    logger.info(f"  mention_contexts: {len(result_1['mention_contexts'])} contextos")
    if result_1['mention_contexts']:
        logger.info(f"  Primer contexto: \"{result_1['mention_contexts'][0][:150]}...\"")
    
    if result_1['brand_mentioned']:
        logger.info("  ✅ CORRECTO: Marca detectada en texto")
    else:
        logger.error("  ❌ ERROR: Marca NO detectada (debería detectarse)")
    
    # ==================================================
    # TEST 2: Perplexity - Sources con getquipu.com
    # ==================================================
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Perplexity - Source con getquipu.com")
    logger.info("=" * 70)
    
    perplexity_text = """La factura electrónica en España será obligatoria a partir de 2025, pero su entrada en vigor efectiva dependerá de la aprobación del reglamento específico que desarrolla la Ley Crea y Crece, aún pendiente."""
    
    perplexity_sources = [
        {'url': 'https://nimoerp.com', 'provider': 'perplexity'},
        {'url': 'https://getquipu.com/es', 'provider': 'perplexity'},
        {'url': 'https://asesoriapremium.com', 'provider': 'perplexity'}
    ]
    
    result_2 = service.analyze_brand_mention(
        response_text=perplexity_text,
        brand_name=brand_name,
        brand_domain=brand_domain,
        brand_keywords=brand_keywords,
        sources=perplexity_sources
    )
    
    logger.info(f"\n📊 Resultado:")
    logger.info(f"  brand_mentioned: {result_2['brand_mentioned']}")
    logger.info(f"  mention_count: {result_2['mention_count']}")
    logger.info(f"  mention_contexts: {len(result_2['mention_contexts'])} contextos")
    if result_2['mention_contexts']:
        for i, ctx in enumerate(result_2['mention_contexts'], 1):
            logger.info(f"  Contexto {i}: \"{ctx}\"")
    
    if result_2['brand_mentioned']:
        logger.info("  ✅ CORRECTO: Marca detectada en sources")
    else:
        logger.error("  ❌ ERROR: Marca NO detectada en sources (debería detectarse)")
    
    # ==================================================
    # TEST 3: Caso negativo - Sin marca
    # ==================================================
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Caso negativo - Sin marca")
    logger.info("=" * 70)
    
    negative_text = "Los mejores softwares de facturación son Holded, Sage y Zoho Invoice."
    negative_sources = [
        {'url': 'https://holded.com', 'provider': 'extracted'},
        {'url': 'https://sage.com', 'provider': 'extracted'}
    ]
    
    result_3 = service.analyze_brand_mention(
        response_text=negative_text,
        brand_name=brand_name,
        brand_domain=brand_domain,
        brand_keywords=brand_keywords,
        sources=negative_sources
    )
    
    logger.info(f"\n📊 Resultado:")
    logger.info(f"  brand_mentioned: {result_3['brand_mentioned']}")
    logger.info(f"  mention_count: {result_3['mention_count']}")
    
    if not result_3['brand_mentioned']:
        logger.info("  ✅ CORRECTO: No hay marca (correcto)")
    else:
        logger.error("  ❌ ERROR: Detectó marca donde no la hay")
    
    # ==================================================
    # RESUMEN
    # ==================================================
    logger.info("\n" + "=" * 70)
    logger.info("📊 RESUMEN DE TESTS")
    logger.info("=" * 70)
    
    tests_passed = 0
    tests_total = 3
    
    if result_1['brand_mentioned']:
        logger.info("✅ TEST 1: OpenAI text detection - PASSED")
        tests_passed += 1
    else:
        logger.error("❌ TEST 1: OpenAI text detection - FAILED")
    
    if result_2['brand_mentioned']:
        logger.info("✅ TEST 2: Perplexity sources detection - PASSED")
        tests_passed += 1
    else:
        logger.error("❌ TEST 2: Perplexity sources detection - FAILED")
    
    if not result_3['brand_mentioned']:
        logger.info("✅ TEST 3: Negative case - PASSED")
        tests_passed += 1
    else:
        logger.error("❌ TEST 3: Negative case - FAILED")
    
    logger.info(f"\n🎯 RESULTADO FINAL: {tests_passed}/{tests_total} tests passed")
    
    if tests_passed == tests_total:
        logger.info("✅ ¡TODOS LOS TESTS PASADOS! La corrección funciona correctamente.")
        return True
    else:
        logger.error("❌ ALGUNOS TESTS FALLARON. Revisa la implementación.")
        return False


if __name__ == '__main__':
    success = test_brand_detection()
    exit(0 if success else 1)

