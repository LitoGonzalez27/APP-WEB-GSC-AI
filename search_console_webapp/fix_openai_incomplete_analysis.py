#!/usr/bin/env python3
"""
Script para completar el análisis incompleto de OpenAI

Ejecuta un nuevo análisis completo que debería procesar las 22 queries.
Con el fix de _save_error_result, ahora los errores se registrarán correctamente.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from services.llm_monitoring_service import MultiLLMMonitoringService
import logging
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fix_openai_analysis():
    """Ejecuta un nuevo análisis para completar las queries faltantes de OpenAI"""
    
    print("\n" + "="*80)
    print("🔧 SOLUCIÓN: Completar análisis incompleto de OpenAI")
    print("="*80)
    
    # Obtener el proyecto activo
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a BD")
        return False
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name 
            FROM llm_monitoring_projects
            WHERE is_active = TRUE
            LIMIT 1
        """)
        
        project = cur.fetchone()
        
        if not project:
            print("❌ No hay proyectos activos")
            return False
        
        project_id = project['id']
        project_name = project['name']
        
        print(f"\n📋 Proyecto: {project_name} (ID: {project_id})")
        
        # Estado actual
        cur.execute("""
            SELECT 
                llm_provider,
                COUNT(*) as queries_ejecutadas
            FROM llm_monitoring_results
            WHERE project_id = %s
            AND analysis_date = %s
            GROUP BY llm_provider
            ORDER BY llm_provider
        """, (project_id, date.today()))
        
        current_state = cur.fetchall()
        
        print("\n📊 Estado actual (hoy):")
        for row in current_state:
            print(f"   • {row['llm_provider']}: {row['queries_ejecutadas']} queries")
        
        cur.close()
        conn.close()
        
        # Confirmar ejecución
        print("\n" + "="*80)
        print("⚠️ ADVERTENCIA:")
        print("   Este script ejecutará un análisis COMPLETO de todos los LLMs")
        print("   • OpenAI procesará las queries faltantes (puede tardar varios minutos)")
        print("   • Los demás LLMs actualizarán sus resultados del día")
        print("   • Consumirá tokens de API")
        print("="*80)
        
        response = input("\n¿Deseas continuar? (s/n): ").strip().lower()
        
        if response not in ['s', 'si', 'sí', 'y', 'yes']:
            print("❌ Operación cancelada")
            return False
        
        # Crear servicio con fix aplicado
        print("\n🚀 Inicializando servicio...")
        service = MultiLLMMonitoringService()
        
        print(f"✅ Servicio inicializado")
        print(f"   Providers disponibles: {', '.join(service.providers.keys())}")
        
        # Configuración de concurrencia
        print("\n⚙️ Configuración de concurrencia:")
        for pname, limit in service.provider_concurrency.items():
            if pname in service.providers:
                print(f"   • {pname}: {limit} workers concurrentes")
        
        # Ejecutar análisis
        print("\n" + "="*80)
        print("⚡ EJECUTANDO ANÁLISIS...")
        print("="*80)
        print("")
        
        result = service.analyze_project(
            project_id=project_id,
            max_workers=10
        )
        
        print("\n" + "="*80)
        print("📊 RESULTADOS:")
        print("="*80)
        
        print(f"\n⏱️  Duración: {result['duration_seconds']}s")
        print(f"📈 Queries ejecutadas: {result['total_queries_executed']}")
        print(f"❌ Queries fallidas: {result['failed_queries']}")
        print(f"🤖 LLMs analizados: {result['llms_analyzed']}")
        
        print("\n📊 Completitud por LLM:")
        print("-"*80)
        print(f"{'LLM':<15} {'Queries':<15} {'Completitud':<15} {'Estado'}")
        print("-"*80)
        
        all_complete = True
        
        for llm, completeness in result['completeness_by_llm'].items():
            analyzed = completeness['queries_analyzed']
            expected = completeness['queries_expected']
            pct = completeness['completeness_pct']
            
            if pct == 100:
                status = "✅ COMPLETO"
            else:
                status = "⚠️ INCOMPLETO"
                all_complete = False
            
            print(f"{llm:<15} {analyzed}/{expected:<13} {pct}%{' '*(12-len(str(pct)))} {status}")
        
        # Verificación específica de OpenAI
        print("\n" + "="*80)
        print("🎯 VERIFICACIÓN DE OPENAI:")
        print("="*80)
        
        openai_completeness = result['completeness_by_llm'].get('openai', {})
        openai_pct = openai_completeness.get('completeness_pct', 0)
        openai_analyzed = openai_completeness.get('queries_analyzed', 0)
        openai_expected = openai_completeness.get('queries_expected', 0)
        
        if openai_pct == 100:
            print(f"\n✅ ¡ÉXITO! OpenAI ejecutó TODAS las {openai_analyzed} queries")
            print("✅ El problema está resuelto")
        else:
            print(f"\n⚠️ OpenAI ejecutó {openai_analyzed}/{openai_expected} queries ({openai_pct}%)")
            print(f"⚠️ Aún faltan {openai_expected - openai_analyzed} queries")
            
            # Verificar errores
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT COUNT(*) as error_count
                FROM llm_monitoring_results
                WHERE llm_provider = 'openai'
                AND analysis_date = %s
                AND has_error = TRUE
            """, (date.today(),))
            
            error_count = cur.fetchone()['error_count']
            
            if error_count > 0:
                print(f"\n❌ Hay {error_count} queries con error registrado")
                print("   Ejecuta: python3 diagnose_openai_queries.py para ver detalles")
            
            cur.close()
            conn.close()
        
        print("\n" + "="*80)
        
        return openai_pct == 100
        
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = fix_openai_analysis()
    
    if success:
        print("\n🎉 ANÁLISIS COMPLETADO EXITOSAMENTE")
    else:
        print("\n⚠️ El análisis se completó pero OpenAI no procesó todas las queries")
        print("   Posibles causas:")
        print("   • Rate limit de OpenAI")
        print("   • Timeout en queries muy lentas")
        print("   • Errores de API")
        print("\n   Verifica los logs para más detalles")
    
    sys.exit(0 if success else 1)

