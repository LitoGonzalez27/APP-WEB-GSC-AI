#!/usr/bin/env python3
"""
Script para el cron job diario del Multi-LLM Brand Monitoring System
Este script debe ejecutarse diariamente para analizar todos los proyectos activos.

CONFIGURACIÓN CRON:
# Ejecutar todos los días a las 4:00 AM (después del AI Mode a las 3:00 AM)
0 4 * * * cd /path/to/your/app && python3 daily_llm_monitoring_cron.py >> /var/log/llm_monitoring_cron.log 2>&1

RAILWAY SETUP:
Se configura en railway.json como job separado

MODELO DE NEGOCIO:
- Las API keys son GLOBALES, gestionadas por el dueño del servicio
- Se obtienen de variables de entorno (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- Los usuarios NO configuran sus propias API keys
- Los costes son operativos del dueño del servicio

IMPORTANTE:
- Usa variables de entorno para API keys
- No requiere configuración por usuario
- Ejecuta análisis para todos los proyectos activos
"""

import sys
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('llm_monitoring_cron')


def main():
    try:
        logger.info("")
        logger.info("=" * 70)
        logger.info("🕒 === MULTI-LLM BRAND MONITORING CRON JOB STARTED ===")
        logger.info("=" * 70)
        logger.info(f"⏰ Timestamp: {datetime.now().isoformat()}")
        logger.info("")
        
        # 1. Verificar que las API keys estén configuradas
        logger.info("🔑 Verificando API keys en variables de entorno...")
        
        api_keys_available = {
            'OPENAI_API_KEY': bool(os.getenv('OPENAI_API_KEY')),
            'ANTHROPIC_API_KEY': bool(os.getenv('ANTHROPIC_API_KEY')),
            'GOOGLE_API_KEY': bool(os.getenv('GOOGLE_API_KEY')),
            'PERPLEXITY_API_KEY': bool(os.getenv('PERPLEXITY_API_KEY'))
        }
        
        available_count = sum(api_keys_available.values())
        
        if available_count == 0:
            logger.error("❌ No hay API keys configuradas en variables de entorno")
            logger.error("   Configura al menos una de: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, PERPLEXITY_API_KEY")
            logger.error("💥 LLM MONITORING CRON JOB FAILED: NO API KEYS")
            sys.exit(1)
        
        logger.info(f"✅ {available_count}/4 proveedores disponibles:")
        for key, available in api_keys_available.items():
            status = "✅" if available else "❌"
            logger.info(f"   {status} {key}")
        
        logger.info("")
        
        # 2. Importar el servicio
        logger.info("📦 Importando servicio de monitorización...")
        try:
            from services.llm_monitoring_service import analyze_all_active_projects
            logger.info("✅ Servicio importado correctamente")
        except ImportError as e:
            logger.error(f"❌ Error importando servicio: {e}")
            logger.error("   Sugerencia: verifica que services/llm_monitoring_service.py exista")
            sys.exit(1)
        
        logger.info("")
        
        # 3. Ejecutar análisis de todos los proyectos
        logger.info("🚀 Iniciando análisis de todos los proyectos activos...")
        logger.info("   Configuración optimizada para CRON diario:")
        logger.info("   • Prioridad: COMPLETITUD > Velocidad")
        logger.info("   • Max workers: 8 (conservador)")
        logger.info("   • Reintentos: 4 intentos con delays incrementales")
        logger.info("   • Tiempo estimado: 15-30 minutos por proyecto")
        logger.info("")
        
        # analyze_all_active_projects() usará variables de entorno automáticamente
        results = analyze_all_active_projects(
            api_keys=None,  # None = usar variables de entorno
            max_workers=8   # Reducido de 10 a 8 para más estabilidad
        )
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 RESULTADOS DEL ANÁLISIS")
        logger.info("=" * 70)
        
        # 4. Procesar resultados
        successful = 0
        failed = 0
        total_queries = 0
        total_duration = 0.0
        
        for result in results:
            if 'error' in result:
                failed += 1
                logger.error(f"❌ Proyecto #{result['project_id']}: {result['error']}")
            else:
                successful += 1
                total_queries += result.get('total_queries_executed', 0)
                total_duration += result.get('duration_seconds', 0)
                
                logger.info(f"✅ Proyecto #{result['project_id']}")
                logger.info(f"   Duración: {result.get('duration_seconds', 0):.1f}s")
                logger.info(f"   Queries: {result.get('total_queries_executed', 0)}")
                logger.info(f"   LLMs: {result.get('llms_analyzed', 0)}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("📈 RESUMEN FINAL")
        logger.info("=" * 70)
        logger.info(f"   Total proyectos: {len(results)}")
        logger.info(f"   ✅ Exitosos: {successful}")
        logger.info(f"   ❌ Fallidos: {failed}")
        logger.info(f"   📊 Total queries: {total_queries}")
        logger.info(f"   ⏱️  Duración total: {total_duration:.1f}s")
        
        # 5. Informe de completitud.
        # La pasada de completitud (Fase B) ya corre DENTRO de
        # analyze_all_active_projects: reintenta solo los pares (query, llm)
        # que faltan y reconstruye los snapshots afectados. La antigua
        # reconciliación de este script re-analizaba proyectos ENTEROS
        # (doble coste API) y solo existía en este entrypoint — el cron real
        # de Railway usa el endpoint HTTP y nunca la ejecutaba.
        projects_with_incomplete = [r for r in results if isinstance(r, dict) and r.get('incomplete_llms')]
        if projects_with_incomplete:
            logger.warning("")
            logger.warning("=" * 70)
            logger.warning("⚠️  PROYECTOS AÚN INCOMPLETOS TRAS LA PASADA DE COMPLETITUD")
            logger.warning("=" * 70)
            for r in projects_with_incomplete:
                incomplete_llms = r.get('incomplete_llms', [])
                completeness = r.get('completeness_by_llm', {})
                completion_info = r.get('completion_pass') or {}
                logger.warning(f"   • Proyecto #{r.get('project_id')}:")
                for llm in incomplete_llms:
                    llm_data = completeness.get(llm, {})
                    analyzed = llm_data.get('queries_analyzed', 0)
                    expected = llm_data.get('queries_expected', 0)
                    pct = llm_data.get('completeness_pct', 0)
                    logger.warning(f"      - {llm}: {analyzed}/{expected} ({pct}%)")
                if completion_info:
                    logger.warning(f"      (pasada de completitud: {completion_info})")
        
        if total_duration > 0 and total_queries > 0:
            queries_per_second = total_queries / total_duration
            logger.info(f"   🚀 Velocidad: {queries_per_second:.2f} queries/segundo")
        
        logger.info("=" * 70)
        logger.info("")
        
        # 5. Determinar exit code
        if failed > 0 and successful == 0:
            # Todos fallaron
            logger.error("❌ TODOS LOS PROYECTOS FALLARON")
            logger.error("💥 LLM MONITORING CRON JOB FAILED")
            sys.exit(1)
        elif failed > 0:
            # Algunos fallaron, pero otros funcionaron
            logger.warning(f"⚠️ {failed} proyecto(s) fallaron, pero {successful} exitosos")
            logger.warning("🔔 LLM MONITORING CRON JOB COMPLETED WITH WARNINGS")
            sys.exit(0)
        else:
            # Todos exitosos
            logger.info("🎉 LLM MONITORING CRON JOB COMPLETED SUCCESSFULLY")
            sys.exit(0)
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}", exc_info=True)
        logger.error("   Sugerencia: verifica que services/llm_monitoring_service.py exista")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        logger.error("💥 LLM MONITORING CRON JOB CRASHED")
        sys.exit(1)


if __name__ == "__main__":
    main()
