#!/usr/bin/env python3
"""
Script de diagnóstico para LLM Monitoring - Problema de queries desiguales

Este script verifica:
1. Cuántas queries tiene el proyecto
2. Cuántos resultados hay por LLM 
3. Si hay queries faltantes en algún LLM
4. El cálculo del mention_rate en snapshots
"""

import sys
import logging
from datetime import datetime, timedelta
from database import get_db_connection

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def diagnose_project(project_id):
    """Diagnostica un proyecto específico"""
    logger.info("\n" + "="*80)
    logger.info(f"🔍 DIAGNÓSTICO DE PROYECTO #{project_id}")
    logger.info("="*80)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Información del proyecto
        logger.info("\n📋 1. INFORMACIÓN DEL PROYECTO")
        logger.info("-" * 80)
        
        cur.execute("""
            SELECT 
                id, name, brand_name, 
                enabled_llms, queries_per_llm,
                last_analysis_date
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        if not project:
            logger.error(f"❌ Proyecto {project_id} no encontrado")
            return False
        
        logger.info(f"Nombre: {project['name']}")
        logger.info(f"Marca: {project['brand_name']}")
        logger.info(f"LLMs habilitados: {', '.join(project['enabled_llms'])}")
        logger.info(f"Queries por LLM configuradas: {project['queries_per_llm']}")
        logger.info(f"Último análisis: {project['last_analysis_date']}")
        
        # 2. Queries totales
        logger.info("\n📊 2. QUERIES/PROMPTS DEL PROYECTO")
        logger.info("-" * 80)
        
        cur.execute("""
            SELECT COUNT(*) as total
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
        """, (project_id,))
        
        total_queries = cur.fetchone()['total']
        logger.info(f"Total de queries activas: {total_queries}")
        
        if total_queries == 0:
            logger.warning("⚠️  No hay queries para este proyecto!")
            return True
        
        # 3. Resultados por LLM (últimos 7 días)
        logger.info("\n🤖 3. RESULTADOS POR LLM (últimos 7 días)")
        logger.info("-" * 80)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        cur.execute("""
            SELECT 
                llm_provider,
                COUNT(DISTINCT query_id) as queries_analizadas,
                COUNT(*) as total_resultados,
                SUM(CASE WHEN brand_mentioned THEN 1 ELSE 0 END) as queries_con_mencion,
                SUM(CASE WHEN error_message IS NOT NULL THEN 1 ELSE 0 END) as queries_con_error,
                MAX(analysis_date) as ultimo_analisis
            FROM llm_monitoring_results
            WHERE project_id = %s 
                AND analysis_date >= %s
            GROUP BY llm_provider
            ORDER BY llm_provider
        """, (project_id, start_date))
        
        results_by_llm = cur.fetchall()
        
        if not results_by_llm:
            logger.warning("⚠️  No hay resultados recientes (últimos 7 días)")
            return True
        
        logger.info(f"\n{'LLM':<15} {'Queries':<10} {'Menciones':<12} {'Errores':<10} {'Último Análisis'}")
        logger.info("-" * 80)
        
        max_queries = total_queries
        llms_with_issues = []
        
        for row in results_by_llm:
            llm = row['llm_provider']
            queries_analyzed = row['queries_analizadas']
            menciones = row['queries_con_mencion']
            errores = row['queries_con_error']
            ultimo = row['ultimo_analisis'].strftime('%Y-%m-%d')
            
            status = "✅" if queries_analyzed == max_queries else "⚠️ "
            
            logger.info(f"{status} {llm:<13} {queries_analyzed:<10} {menciones:<12} {errores:<10} {ultimo}")
            
            if queries_analyzed < max_queries:
                llms_with_issues.append({
                    'llm': llm,
                    'queries_analyzed': queries_analyzed,
                    'queries_missing': max_queries - queries_analyzed
                })
        
        # 4. Snapshots (últimos 7 días)
        logger.info("\n📸 4. SNAPSHOTS (últimos 7 días)")
        logger.info("-" * 80)
        
        cur.execute("""
            SELECT 
                snapshot_date,
                llm_provider,
                total_queries,
                total_mentions,
                mention_rate
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
                AND snapshot_date >= %s
            ORDER BY snapshot_date DESC, llm_provider
        """, (project_id, start_date))
        
        snapshots = cur.fetchall()
        
        if not snapshots:
            logger.warning("⚠️  No hay snapshots recientes")
            return True
        
        logger.info(f"\n{'Fecha':<12} {'LLM':<15} {'Queries':<10} {'Menciones':<12} {'Mention Rate'}")
        logger.info("-" * 80)
        
        snapshot_issues = []
        
        for snap in snapshots:
            fecha = snap['snapshot_date'].strftime('%Y-%m-%d')
            llm = snap['llm_provider']
            total_q = snap['total_queries']
            total_m = snap['total_mentions']
            mention_r = snap['mention_rate']
            
            # Verificar si el mention_rate es correcto
            expected_rate = (total_m / total_q * 100) if total_q > 0 else 0
            rate_diff = abs(float(mention_r) - float(expected_rate))
            
            status = "✅" if rate_diff < 0.1 else "⚠️ "
            
            logger.info(f"{status} {fecha:<10} {llm:<15} {total_q:<10} {total_m:<12} {mention_r:.1f}%")
            
            if rate_diff >= 0.1:
                snapshot_issues.append({
                    'fecha': fecha,
                    'llm': llm,
                    'total_queries': total_q,
                    'total_mentions': total_m,
                    'mention_rate_stored': mention_r,
                    'mention_rate_expected': expected_rate
                })
        
        # 5. Queries faltantes por LLM
        if llms_with_issues:
            logger.info("\n⚠️  5. QUERIES FALTANTES POR LLM")
            logger.info("-" * 80)
            
            for issue in llms_with_issues:
                llm = issue['llm']
                missing = issue['queries_missing']
                
                logger.info(f"\n{llm}: Faltan {missing} queries")
                
                # Obtener IDs de queries analizadas
                cur.execute("""
                    SELECT DISTINCT query_id
                    FROM llm_monitoring_results
                    WHERE project_id = %s 
                        AND llm_provider = %s
                        AND analysis_date >= %s
                """, (project_id, llm, start_date))
                
                analyzed_ids = {row['query_id'] for row in cur.fetchall()}
                
                # Obtener todas las queries
                cur.execute("""
                    SELECT id, query_text
                    FROM llm_monitoring_queries
                    WHERE project_id = %s AND is_active = TRUE
                """, (project_id,))
                
                all_queries = cur.fetchall()
                
                # Encontrar queries faltantes
                missing_queries = [q for q in all_queries if q['id'] not in analyzed_ids]
                
                if missing_queries:
                    logger.info(f"  Queries no analizadas en {llm}:")
                    for q in missing_queries[:5]:  # Mostrar máximo 5
                        logger.info(f"    - ID {q['id']}: {q['query_text'][:60]}...")
                    if len(missing_queries) > 5:
                        logger.info(f"    ... y {len(missing_queries) - 5} más")
        
        # 6. Problemas de mention_rate en snapshots
        if snapshot_issues:
            logger.info("\n⚠️  6. PROBLEMAS DE MENTION_RATE EN SNAPSHOTS")
            logger.info("-" * 80)
            
            for issue in snapshot_issues:
                logger.info(f"\nFecha: {issue['fecha']}, LLM: {issue['llm']}")
                logger.info(f"  Total queries: {issue['total_queries']}")
                logger.info(f"  Total menciones: {issue['total_mentions']}")
                logger.info(f"  Mention rate guardado: {issue['mention_rate_stored']:.2f}%")
                logger.info(f"  Mention rate esperado: {issue['mention_rate_expected']:.2f}%")
                logger.info(f"  ❌ Diferencia: {abs(issue['mention_rate_stored'] - issue['mention_rate_expected']):.2f}%")
        
        # 7. Recomendaciones
        logger.info("\n💡 7. RECOMENDACIONES")
        logger.info("-" * 80)
        
        if llms_with_issues:
            logger.info("\n⚠️  Algunos LLMs no han analizado todas las queries:")
            logger.info("   Posibles causas:")
            logger.info("   1. Errores en las llamadas a la API (rate limits, timeouts)")
            logger.info("   2. Health check excluyendo providers")
            logger.info("   3. Queries añadidas después del último análisis")
            logger.info("\n   Solución:")
            logger.info("   → Ejecutar un nuevo análisis desde el dashboard")
            logger.info("   → Verificar logs del análisis para ver errores")
        
        if snapshot_issues:
            logger.info("\n⚠️  Hay inconsistencias en los snapshots:")
            logger.info("   → Esto puede causar que se muestren porcentajes incorrectos")
            logger.info("   → Solución: Ejecutar un nuevo análisis para recalcular")
        
        if not llms_with_issues and not snapshot_issues:
            logger.info("\n✅ Todo parece estar en orden")
            logger.info("   Todos los LLMs han analizado todas las queries")
            logger.info("   Los snapshots tienen datos correctos")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()
        conn.close()


def main():
    """Función principal"""
    if len(sys.argv) < 2:
        logger.error("Uso: python3 diagnose_llm_queries.py <project_id>")
        logger.info("\nEjemplo: python3 diagnose_llm_queries.py 5")
        return 1
    
    try:
        project_id = int(sys.argv[1])
    except ValueError:
        logger.error("❌ El project_id debe ser un número")
        return 1
    
    success = diagnose_project(project_id)
    
    logger.info("\n" + "="*80)
    logger.info("✅ DIAGNÓSTICO COMPLETADO" if success else "❌ DIAGNÓSTICO FALLÓ")
    logger.info("="*80 + "\n")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

