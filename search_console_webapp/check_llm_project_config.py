#!/usr/bin/env python3
"""
Script para verificar la configuración de un proyecto LLM Monitoring
"""

from database import get_db_connection
import sys

def check_project_config(project_id: int):
    """Verifica la configuración de un proyecto"""
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la BD")
        return
    
    try:
        cursor = conn.cursor()
        
        print("="*80)
        print(f"🔍 VERIFICANDO CONFIGURACIÓN DEL PROYECTO ID={project_id}")
        print("="*80)
        print()
        
        # Obtener info del proyecto
        cursor.execute("""
            SELECT 
                id, 
                name as project_name, 
                brand_name, 
                industry, 
                competitors,
                enabled_llms,
                language,
                created_at
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cursor.fetchone()
        
        if not project:
            print(f"❌ No se encontró proyecto con ID={project_id}")
            return
        
        print("📋 CONFIGURACIÓN DEL PROYECTO:")
        print(f"   ID: {project['id']}")
        print(f"   Nombre: {project['project_name']}")
        print(f"   🎯 Brand Name: '{project['brand_name']}'")
        print(f"   Industria: {project['industry']}")
        print(f"   Idioma: {project['language']}")
        print(f"   Created: {project['created_at']}")
        print()
        
        print("👥 COMPETIDORES CONFIGURADOS:")
        competitors = project['competitors'] if project['competitors'] else []
        if competitors:
            for i, comp in enumerate(competitors, 1):
                print(f"   {i}. {comp}")
        else:
            print("   ⚠️ NO HAY COMPETIDORES CONFIGURADOS")
        print()
        
        print("🤖 LLMs HABILITADOS:")
        enabled_llms = project['enabled_llms'] if project['enabled_llms'] else []
        if enabled_llms:
            for llm in enabled_llms:
                print(f"   ✅ {llm}")
        else:
            print("   ⚠️ NO HAY LLMs HABILITADOS")
        print()
        
        # Obtener últimos snapshots
        cursor.execute("""
            SELECT 
                llm_provider,
                snapshot_date,
                total_queries,
                total_mentions,
                mention_rate,
                share_of_voice,
                competitor_breakdown
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
            ORDER BY snapshot_date DESC, llm_provider
            LIMIT 10
        """, (project_id,))
        
        snapshots = cursor.fetchall()
        
        if snapshots:
            print("📊 ÚLTIMOS SNAPSHOTS:")
            print()
            for snap in snapshots:
                print(f"   🤖 {snap['llm_provider'].upper()} ({snap['snapshot_date']})")
                print(f"      Queries: {snap['total_queries']}")
                print(f"      Menciones: {snap['total_mentions']}")
                print(f"      Mention Rate: {snap['mention_rate']}%")
                print(f"      Share of Voice: {snap['share_of_voice']}%")
                if snap['competitor_breakdown']:
                    print(f"      Competidores: {snap['competitor_breakdown']}")
                print()
        else:
            print("⚠️ NO HAY SNAPSHOTS (todavía no se ha ejecutado análisis)")
        
        print("="*80)
        print("✅ VERIFICACIÓN COMPLETADA")
        print("="*80)
        
        # Diagnóstico
        print()
        print("🔧 DIAGNÓSTICO:")
        
        if not project['brand_name'] or project['brand_name'].lower() == 'ivi.es':
            print("   ❌ PROBLEMA: Brand Name está configurado como 'ivi.es'")
            print("   ✅ SOLUCIÓN: Cambiar a 'Ginemed' o 'ginemed.com'")
        
        if not competitors or len(competitors) == 0:
            print("   ❌ PROBLEMA: No hay competidores configurados")
            print("   ✅ SOLUCIÓN: Agregar competidores: ['IVI', 'Reproducción Asistida', ...]")
        
        cursor.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    # Por defecto verificar proyecto 3 (Test 3 LLM)
    project_id = 3
    
    if len(sys.argv) > 1:
        project_id = int(sys.argv[1])
    
    check_project_config(project_id)

