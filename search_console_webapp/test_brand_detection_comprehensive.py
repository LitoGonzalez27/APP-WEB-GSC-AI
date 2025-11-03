"""
Test Comprehensivo de Detección de Marcas
==========================================

Tests exhaustivos para asegurar detección sólida de:
- Variaciones de marca con/sin acentos
- Dominios completos y parciales
- Keywords personalizados (incluso frases largas)
- Sources/URLs
- Casos edge (palabras similares, posiciones, etc.)
"""

import logging
from services.llm_monitoring_service import MultiLLMMonitoringService

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class TestCase:
    """Clase para definir casos de test"""
    def __init__(self, name, text, sources, should_detect, description):
        self.name = name
        self.text = text
        self.sources = sources
        self.should_detect = should_detect
        self.description = description


def run_comprehensive_tests():
    """
    Ejecuta batería completa de tests de detección de marca
    """
    
    # Configuración de marca (caso real: Quipu)
    brand_domain = "getquipu.com"
    brand_keywords = ["quipu", "getquipu", "youtube de quipu"]
    
    # Crear servicio
    service = MultiLLMMonitoringService.__new__(MultiLLMMonitoringService)
    service.logger = logger
    
    logger.info("=" * 80)
    logger.info("🧪 TEST COMPREHENSIVO: Detección de Marcas")
    logger.info("=" * 80)
    logger.info(f"\n📋 Configuración de Marca:")
    logger.info(f"   • Domain: {brand_domain}")
    logger.info(f"   • Keywords: {brand_keywords}")
    logger.info("")
    
    # ============================================================================
    # DEFINIR CASOS DE TEST
    # ============================================================================
    
    test_cases = [
        # ========== GRUPO 1: VARIACIONES BÁSICAS ==========
        TestCase(
            name="Marca con mayúscula inicial",
            text="Quipu es una buena opción para autónomos.",
            sources=[],
            should_detect=True,
            description="Keyword 'quipu' con mayúscula inicial"
        ),
        
        TestCase(
            name="Marca todo minúsculas",
            text="He probado quipu y me gusta mucho.",
            sources=[],
            should_detect=True,
            description="Keyword 'quipu' en minúsculas"
        ),
        
        TestCase(
            name="Marca todo mayúsculas",
            text="QUIPU es el mejor software de facturación.",
            sources=[],
            should_detect=True,
            description="Keyword 'QUIPU' en mayúsculas"
        ),
        
        TestCase(
            name="Marca con acento (Quipú)",
            text="Quipú encaja muy bien para autónomos.",
            sources=[],
            should_detect=True,
            description="Variación con acento debe detectarse"
        ),
        
        # ========== GRUPO 2: VARIACIONES CON 'GET' ==========
        TestCase(
            name="Keyword getquipu (junto)",
            text="Usa getquipu para facturar fácilmente.",
            sources=[],
            should_detect=True,
            description="Keyword 'getquipu' junto"
        ),
        
        TestCase(
            name="Frase 'get quipu' (separado)",
            text="Puedes get quipu desde su web oficial.",
            sources=[],
            should_detect=True,
            description="'get quipu' separado debe detectarse"
        ),
        
        # ========== GRUPO 3: FRASES LARGAS (KEYWORDS PERSONALIZADOS) ==========
        TestCase(
            name="Keyword frase: 'youtube de quipu'",
            text="Mira el youtube de quipu para tutoriales.",
            sources=[],
            should_detect=True,
            description="Frase larga como keyword"
        ),
        
        TestCase(
            name="Keyword frase con mayúsculas",
            text="Suscríbete al YouTube de Quipu para aprender más.",
            sources=[],
            should_detect=True,
            description="Frase con mayúsculas mezcladas"
        ),
        
        # ========== GRUPO 4: POSICIONES EN TEXTO ==========
        TestCase(
            name="Marca al inicio del texto",
            text="Quipu te permite facturar de manera sencilla.",
            sources=[],
            should_detect=True,
            description="Marca en primera palabra"
        ),
        
        TestCase(
            name="Marca al final del texto",
            text="El mejor software de facturación es Quipu",
            sources=[],
            should_detect=True,
            description="Marca en última palabra"
        ),
        
        TestCase(
            name="Marca en medio de texto largo",
            text="Para autónomos y pymes en España, Quipu ofrece una solución completa de facturación y contabilidad.",
            sources=[],
            should_detect=True,
            description="Marca en medio de párrafo"
        ),
        
        # ========== GRUPO 5: MÚLTIPLES MENCIONES ==========
        TestCase(
            name="Marca mencionada 3 veces",
            text="Quipu es genial. Uso Quipu todos los días. Recomiendo Quipu.",
            sources=[],
            should_detect=True,
            description="Múltiples menciones en el texto"
        ),
        
        TestCase(
            name="Diferentes variaciones en mismo texto",
            text="QUIPU es excelente. getquipu.com tiene precios buenos. El youtube de quipu ayuda mucho.",
            sources=[],
            should_detect=True,
            description="Múltiples keywords diferentes"
        ),
        
        # ========== GRUPO 6: SOURCES/URLS ==========
        TestCase(
            name="Dominio completo en source",
            text="Los mejores softwares de facturación para 2025.",
            sources=[{'url': 'https://getquipu.com', 'provider': 'perplexity'}],
            should_detect=True,
            description="Dominio exacto en URL"
        ),
        
        TestCase(
            name="Dominio con path en source",
            text="Guía de facturación electrónica en España.",
            sources=[{'url': 'https://getquipu.com/es/blog/facturacion', 'provider': 'perplexity'}],
            should_detect=True,
            description="Dominio en URL con path"
        ),
        
        TestCase(
            name="Dominio con subdominio",
            text="Información sobre facturación.",
            sources=[{'url': 'https://blog.getquipu.com/articulo', 'provider': 'perplexity'}],
            should_detect=True,
            description="Dominio en subdominio"
        ),
        
        TestCase(
            name="Solo keyword en URL (sin dominio completo)",
            text="Software de facturación recomendado.",
            sources=[{'url': 'https://getquipu.es/pricing', 'provider': 'extracted'}],
            should_detect=True,
            description="'getquipu' en URL con .es"
        ),
        
        TestCase(
            name="Marca en texto Y en source",
            text="Quipu es la mejor opción para autónomos.",
            sources=[{'url': 'https://getquipu.com', 'provider': 'perplexity'}],
            should_detect=True,
            description="Doble detección: texto + source"
        ),
        
        # ========== GRUPO 7: CASOS EDGE (NO DEBE DETECTAR) ==========
        TestCase(
            name="Palabra similar: 'quipus' (plural)",
            text="Los quipus eran sistemas de contabilidad incas.",
            sources=[],
            should_detect=False,  # ❌ No debe detectar (diferente contexto)
            description="Palabra similar pero diferente"
        ),
        
        TestCase(
            name="Marca dentro de palabra compuesta",
            text="El antiquipu es un sistema antiguo de contabilidad.",
            sources=[],
            should_detect=False,  # ❌ No debe detectar (no es word boundary)
            description="Keyword dentro de palabra más larga"
        ),
        
        TestCase(
            name="Solo competidores, sin marca",
            text="Holded y Sage son las mejores opciones del mercado.",
            sources=[],
            should_detect=False,
            description="Solo competidores mencionados"
        ),
        
        TestCase(
            name="Dominio diferente en source",
            text="Software de facturación para empresas.",
            sources=[{'url': 'https://holded.com', 'provider': 'perplexity'}],
            should_detect=False,
            description="Source con competidor, no con marca"
        ),
        
        TestCase(
            name="Texto vacío",
            text="",
            sources=[],
            should_detect=False,
            description="Caso edge: texto vacío"
        ),
        
        # ========== GRUPO 8: CONTEXTO REAL DE LLMs ==========
        TestCase(
            name="Respuesta real de ChatGPT",
            text="""Sí, suele ser una buena opción para autónomos que quieren algo sencillo y "todo en uno" para facturar y cumplir con Hacienda en España.

Lo mejor:
- Fácil de usar: crear facturas/rectificativas/recurrentes, presupuestos y albaranes sin complicaciones.
- Impuestos guiados: calcula IVA/IRPF y genera los modelos (303, 130, etc.) automáticamente.

Recomendación práctica:
- Si tu prioridad es emitir facturas, registrar gastos, conciliar el banco y presentar impuestos sin líos, Quipu encaja muy bien para autónomos y microempresas.""",
            sources=[],
            should_detect=True,
            description="Texto real de ChatGPT con mención"
        ),
        
        TestCase(
            name="Respuesta de Perplexity sin mención pero con source",
            text="La factura electrónica en España será obligatoria a partir de 2025, pero su entrada en vigor efectiva dependerá de la aprobación del reglamento específico.",
            sources=[
                {'url': 'https://nimoerp.com', 'provider': 'perplexity'},
                {'url': 'https://getquipu.com/blog/verifactu', 'provider': 'perplexity'},
                {'url': 'https://declarando.es', 'provider': 'perplexity'}
            ],
            should_detect=True,
            description="Perplexity: no en texto pero sí en sources"
        ),
        
        TestCase(
            name="Comparativa con competidores (mención neutral)",
            text="Comparando Quipu vs Holded: ambos son buenas opciones. Holded tiene más funciones pero Quipu es más simple.",
            sources=[],
            should_detect=True,
            description="Mención en comparativa con competidores"
        ),
    ]
    
    # ============================================================================
    # EJECUTAR TESTS
    # ============================================================================
    
    total_tests = len(test_cases)
    passed = 0
    failed = 0
    failed_tests = []
    
    for i, test in enumerate(test_cases, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST {i}/{total_tests}: {test.name}")
        logger.info(f"{'='*80}")
        logger.info(f"📝 Descripción: {test.description}")
        logger.info(f"✅ Debe detectar: {'SÍ' if test.should_detect else 'NO'}")
        logger.info(f"\n📄 Texto ({len(test.text)} chars):")
        if len(test.text) > 200:
            logger.info(f'   "{test.text[:200]}..."')
        else:
            logger.info(f'   "{test.text}"')
        
        if test.sources:
            logger.info(f"\n🔗 Sources ({len(test.sources)}):")
            for source in test.sources:
                logger.info(f'   • {source["url"]}')
        
        # Ejecutar análisis
        result = service.analyze_brand_mention(
            response_text=test.text,
            brand_domain=brand_domain,
            brand_keywords=brand_keywords,
            sources=test.sources
        )
        
        detected = result['brand_mentioned']
        mention_count = result['mention_count']
        contexts = result['mention_contexts']
        
        # Verificar resultado
        success = (detected == test.should_detect)
        
        logger.info(f"\n📊 Resultado:")
        logger.info(f"   brand_mentioned: {detected}")
        logger.info(f"   mention_count: {mention_count}")
        logger.info(f"   contexts: {len(contexts)}")
        
        if contexts:
            for j, ctx in enumerate(contexts[:2], 1):  # Mostrar máximo 2 contextos
                preview = ctx[:100] + '...' if len(ctx) > 100 else ctx
                logger.info(f"   Contexto {j}: \"{preview}\"")
        
        if success:
            logger.info(f"\n✅ TEST PASSED")
            passed += 1
        else:
            logger.info(f"\n❌ TEST FAILED")
            logger.info(f"   Expected: {test.should_detect}, Got: {detected}")
            failed += 1
            failed_tests.append({
                'name': test.name,
                'expected': test.should_detect,
                'got': detected
            })
    
    # ============================================================================
    # RESUMEN FINAL
    # ============================================================================
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 RESUMEN FINAL")
    logger.info("=" * 80)
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"✅ Passed: {passed} ({passed/total_tests*100:.1f}%)")
    logger.info(f"❌ Failed: {failed} ({failed/total_tests*100:.1f}%)")
    
    if failed_tests:
        logger.info(f"\n❌ Tests fallidos:")
        for ft in failed_tests:
            logger.info(f"   • {ft['name']}")
            logger.info(f"     Expected: {ft['expected']}, Got: {ft['got']}")
    
    logger.info("")
    
    if failed == 0:
        logger.info("🎉 ¡TODOS LOS TESTS PASARON! Sistema de detección es SÓLIDO.")
        return True
    else:
        logger.error(f"⚠️  {failed} tests fallaron. Revisar implementación.")
        return False


if __name__ == '__main__':
    success = run_comprehensive_tests()
    exit(0 if success else 1)

