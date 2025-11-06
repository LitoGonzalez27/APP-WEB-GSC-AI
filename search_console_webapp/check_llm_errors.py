#!/usr/bin/env python3
"""
Script para revisar errores en el sistema LLM Monitoring
"""

from datetime import datetime, timedelta
from database import get_db_connection

def main():
    print("=" * 80)
    print("🔍 REVISANDO ERRORES EN LLM MONITORING")
    print("=" * 80)
    print()
    
    conn = get_db_connection()
    if not conn:
        print("   ❌ ERROR: No se pudo conectar a la base de datos")
        return
    
    try:
        cur = conn.cursor()
        
        # 1. Revisar errores en la tabla results
        print("1️⃣ ERRORES EN RESULTADOS (ÚLTIMOS 7 DÍAS)")
        print("-" * 80)
        
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        cur.execute("""
            SELECT 
                project_id,
                query_id,
                llm_provider,
                error_message,
                analysis_date,
                created_at
            FROM llm_monitoring_results
            WHERE error_message IS NOT NULL
                AND created_at >= %s
            ORDER BY created_at DESC
            LIMIT 50
        """, (seven_days_ago,))
        
        errors = cur.fetchall()
        
        if not errors:
            print("   ✅ No hay errores registrados en los últimos 7 días")
        else:
            print(f"   ⚠️  {len(errors)} errores encontrados:")
            print()
            
            # Agrupar por provider
            by_provider = {}
            for err in errors:
                provider = err['llm_provider']
                if provider not in by_provider:
                    by_provider[provider] = []
                by_provider[provider].append(err)
            
            for provider, provider_errors in by_provider.items():
                print(f"   🤖 {provider.upper()}: {len(provider_errors)} errores")
                
                # Mostrar primeros 3 errores de cada provider
                for err in provider_errors[:3]:
                    print(f"      📅 {err['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"      Proyecto: #{err['project_id']} | Query: #{err['query_id']}")
                    print(f"      Error: {err['error_message'][:200]}")
                    print()
                
                if len(provider_errors) > 3:
                    print(f"      ... y {len(provider_errors) - 3} errores más")
                    print()
        
        print()
        
        # 2. Revisar snapshots con queries = 0
        print("2️⃣ SNAPSHOTS CON QUERIES = 0")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                project_id,
                llm_provider,
                snapshot_date,
                total_queries,
                total_mentions,
                created_at
            FROM llm_monitoring_snapshots
            WHERE snapshot_date >= %s
                AND total_queries = 0
            ORDER BY snapshot_date DESC
        """, (seven_days_ago.date(),))
        
        problem_snapshots = cur.fetchall()
        
        if not problem_snapshots:
            print("   ✅ No hay snapshots con queries = 0")
        else:
            print(f"   ⚠️  {len(problem_snapshots)} snapshots con queries = 0:")
            print()
            
            for snap in problem_snapshots:
                print(f"   📅 {snap['snapshot_date']} | Proyecto #{snap['project_id']} | {snap['llm_provider'].upper()}")
                print(f"      Queries: {snap['total_queries']} | Menciones: {snap['total_mentions']}")
                print()
        
        print()
        
        # 3. Detectar gaps en análisis
        print("3️⃣ DETECTAR GAPS EN ANÁLISIS POR PROVEEDOR")
        print("-" * 80)
        
        # Obtener proyecto activo
        cur.execute("""
            SELECT id, name
            FROM llm_monitoring_projects
            WHERE is_active = TRUE
            LIMIT 1
        """)
        
        active_project = cur.fetchone()
        
        if not active_project:
            print("   ⚠️  No hay proyectos activos")
        else:
            project_id = active_project['id']
            print(f"   Proyecto activo: #{project_id} - {active_project['name']}")
            print()
            
            # Ver snapshots de los últimos 7 días por proveedor
            cur.execute("""
                SELECT 
                    snapshot_date,
                    llm_provider,
                    total_queries
                FROM llm_monitoring_snapshots
                WHERE project_id = %s
                    AND snapshot_date >= %s
                ORDER BY snapshot_date DESC, llm_provider
            """, (project_id, seven_days_ago.date()))
            
            snapshots = cur.fetchall()
            
            if not snapshots:
                print("   ⚠️  No hay snapshots en los últimos 7 días")
            else:
                # Agrupar por fecha
                by_date = {}
                for snap in snapshots:
                    date_str = snap['snapshot_date'].strftime('%Y-%m-%d')
                    if date_str not in by_date:
                        by_date[date_str] = {}
                    by_date[date_str][snap['llm_provider']] = snap['total_queries']
                
                expected_providers = ['openai', 'anthropic', 'google', 'perplexity']
                
                for date_str in sorted(by_date.keys(), reverse=True):
                    providers_data = by_date[date_str]
                    missing = [p for p in expected_providers if p not in providers_data]
                    
                    if missing:
                        print(f"   ⚠️  {date_str}: Faltan {', '.join(missing).upper()}")
                    else:
                        print(f"   ✅ {date_str}: Todos los proveedores presentes")
                        # Mostrar queries
                        for provider in expected_providers:
                            print(f"      {provider}: {providers_data[provider]} queries")
        
        print()
        
        # 4. Revisar configuración de proyectos
        print("4️⃣ CONFIGURACIÓN DE PROYECTOS ACTIVOS")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                id,
                name,
                brand_name,
                enabled_llms,
                last_analysis_date
            FROM llm_monitoring_projects
            WHERE is_active = TRUE
        """)
        
        active_projects = cur.fetchall()
        
        if not active_projects:
            print("   ⚠️  No hay proyectos activos")
        else:
            for proj in active_projects:
                print(f"   Proyecto #{proj['id']}: {proj['name']}")
                print(f"      LLMs habilitados: {proj['enabled_llms']}")
                
                # Verificar si OpenAI está habilitado
                if 'openai' not in proj['enabled_llms']:
                    print(f"      ⚠️  OpenAI NO está habilitado en este proyecto")
                else:
                    print(f"      ✅ OpenAI está habilitado")
                
                print()
        
        print()
        
        print("=" * 80)
        print("✅ Revisión de errores completada")
        print("=" * 80)
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

