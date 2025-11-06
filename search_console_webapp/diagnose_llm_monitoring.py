#!/usr/bin/env python3
"""
Script de diagnóstico para el sistema LLM Monitoring
Verifica el estado del sistema, proyectos activos y análisis recientes
"""

import os
import sys
from datetime import datetime, timedelta
from database import get_db_connection

def main():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO DEL SISTEMA LLM MONITORING")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Verificar variables de entorno
    print("🔑 1. VERIFICANDO API KEYS")
    print("-" * 80)
    
    api_keys = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
        'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),
        'PERPLEXITY_API_KEY': os.getenv('PERPLEXITY_API_KEY')
    }
    
    for key_name, key_value in api_keys.items():
        if key_value:
            # Mostrar solo primeros y últimos caracteres
            masked = f"{key_value[:10]}...{key_value[-10:]}" if len(key_value) > 20 else "***"
            print(f"   ✅ {key_name}: {masked}")
        else:
            print(f"   ❌ {key_name}: NO CONFIGURADA")
    
    print()
    
    # 2. Conectar a la base de datos
    print("🗄️  2. CONECTANDO A LA BASE DE DATOS")
    print("-" * 80)
    
    conn = get_db_connection()
    if not conn:
        print("   ❌ ERROR: No se pudo conectar a la base de datos")
        sys.exit(1)
    
    print("   ✅ Conexión establecida")
    print()
    
    try:
        cur = conn.cursor()
        
        # 3. Verificar proyectos activos
        print("📊 3. PROYECTOS ACTIVOS")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                id,
                name,
                brand_name,
                enabled_llms,
                is_active,
                last_analysis_date,
                created_at
            FROM llm_monitoring_projects
            ORDER BY last_analysis_date DESC NULLS LAST
        """)
        
        projects = cur.fetchall()
        
        if not projects:
            print("   ⚠️  No hay proyectos en el sistema")
        else:
            print(f"   Total de proyectos: {len(projects)}")
            print()
            
            active_count = 0
            for proj in projects:
                status = "✅ ACTIVO" if proj['is_active'] else "❌ INACTIVO"
                last_analysis = proj['last_analysis_date'].strftime('%Y-%m-%d %H:%M') if proj['last_analysis_date'] else "NUNCA"
                
                if proj['is_active']:
                    active_count += 1
                
                print(f"   [{status}] Proyecto #{proj['id']}: {proj['name']}")
                print(f"      Marca: {proj['brand_name']}")
                print(f"      LLMs habilitados: {proj['enabled_llms']}")
                print(f"      Último análisis: {last_analysis}")
                print(f"      Creado: {proj['created_at'].strftime('%Y-%m-%d')}")
                print()
            
            print(f"   📈 Resumen: {active_count} activos de {len(projects)} totales")
        
        print()
        
        # 4. Verificar análisis recientes
        print("📈 4. ANÁLISIS RECIENTES (ÚLTIMOS 7 DÍAS)")
        print("-" * 80)
        
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        cur.execute("""
            SELECT 
                project_id,
                llm_provider,
                snapshot_date,
                total_queries,
                total_mentions,
                mention_rate,
                created_at
            FROM llm_monitoring_snapshots
            WHERE snapshot_date >= %s
            ORDER BY snapshot_date DESC, project_id, llm_provider
        """, (seven_days_ago.date(),))
        
        snapshots = cur.fetchall()
        
        if not snapshots:
            print("   ⚠️  NO HAY ANÁLISIS EN LOS ÚLTIMOS 7 DÍAS")
            print()
            print("   🔍 Esto puede indicar:")
            print("      - El cron job no se está ejecutando")
            print("      - Los proyectos no tienen prompts configurados")
            print("      - Hay errores en las API keys")
        else:
            print(f"   Total de snapshots: {len(snapshots)}")
            print()
            
            # Agrupar por fecha y proveedor
            by_date = {}
            by_provider = {}
            
            for snap in snapshots:
                date_str = snap['snapshot_date'].strftime('%Y-%m-%d')
                provider = snap['llm_provider']
                
                if date_str not in by_date:
                    by_date[date_str] = []
                by_date[date_str].append(snap)
                
                if provider not in by_provider:
                    by_provider[provider] = 0
                by_provider[provider] += 1
            
            # Mostrar por fecha
            for date_str in sorted(by_date.keys(), reverse=True):
                day_snaps = by_date[date_str]
                print(f"   📅 {date_str}:")
                
                for snap in day_snaps:
                    print(f"      - Proyecto #{snap['project_id']} | {snap['llm_provider'].upper()}")
                    print(f"        Queries: {snap['total_queries']} | Menciones: {snap['total_mentions']} | Mention Rate: {snap['mention_rate']:.1f}%")
                
                print()
            
            # Resumen por proveedor
            print("   📊 Análisis por proveedor:")
            for provider, count in by_provider.items():
                print(f"      {provider.upper()}: {count} snapshots")
        
        print()
        
        # 5. Verificar queries/prompts
        print("📝 5. PROMPTS CONFIGURADOS")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                p.id as project_id,
                p.name as project_name,
                COUNT(q.id) as total_prompts,
                COUNT(CASE WHEN q.is_active THEN 1 END) as active_prompts
            FROM llm_monitoring_projects p
            LEFT JOIN llm_monitoring_queries q ON p.id = q.project_id
            WHERE p.is_active = TRUE
            GROUP BY p.id, p.name
            ORDER BY p.id
        """)
        
        project_prompts = cur.fetchall()
        
        if not project_prompts:
            print("   ⚠️  No hay proyectos activos")
        else:
            for pp in project_prompts:
                if pp['active_prompts'] == 0:
                    print(f"   ⚠️  Proyecto #{pp['project_id']} ({pp['project_name']}): SIN PROMPTS ACTIVOS")
                else:
                    print(f"   ✅ Proyecto #{pp['project_id']} ({pp['project_name']}): {pp['active_prompts']} prompts activos")
        
        print()
        
        # 6. Verificar resultados recientes por LLM
        print("🤖 6. RESULTADOS RECIENTES POR LLM (ÚLTIMAS 24 HORAS)")
        print("-" * 80)
        
        yesterday = datetime.now() - timedelta(days=1)
        
        cur.execute("""
            SELECT 
                llm_provider,
                COUNT(*) as total_results,
                COUNT(CASE WHEN brand_mentioned THEN 1 END) as brand_mentions,
                AVG(CASE WHEN brand_mentioned THEN 1.0 ELSE 0.0 END) * 100 as mention_rate
            FROM llm_monitoring_results
            WHERE created_at >= %s
            GROUP BY llm_provider
            ORDER BY llm_provider
        """, (yesterday,))
        
        recent_results = cur.fetchall()
        
        if not recent_results:
            print("   ⚠️  NO HAY RESULTADOS EN LAS ÚLTIMAS 24 HORAS")
        else:
            for res in recent_results:
                print(f"   {res['llm_provider'].upper()}:")
                print(f"      Total resultados: {res['total_results']}")
                print(f"      Menciones de marca: {res['brand_mentions']}")
                print(f"      Mention Rate: {res['mention_rate']:.1f}%")
                print()
        
        print()
        
        # 7. Diagnóstico específico de OpenAI
        print("🔍 7. DIAGNÓSTICO ESPECÍFICO DE OPENAI")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                DATE(created_at) as analysis_date,
                COUNT(*) as total_calls
            FROM llm_monitoring_results
            WHERE llm_provider = 'openai'
                AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY analysis_date DESC
        """)
        
        openai_history = cur.fetchall()
        
        if not openai_history:
            print("   ⚠️  NO HAY LLAMADAS A OPENAI EN LOS ÚLTIMOS 30 DÍAS")
        else:
            print("   Últimas llamadas a OpenAI:")
            for oh in openai_history[:10]:  # Mostrar últimos 10 días
                print(f"      {oh['analysis_date']}: {oh['total_calls']} llamadas")
        
        print()
        
        # 8. Recomendaciones
        print("💡 8. RECOMENDACIONES")
        print("-" * 80)
        
        issues = []
        
        if not api_keys['OPENAI_API_KEY']:
            issues.append("   ❌ OPENAI_API_KEY no está configurada")
        
        if not snapshots:
            issues.append("   ❌ No hay análisis recientes - revisar cron job")
        
        if project_prompts:
            for pp in project_prompts:
                if pp['active_prompts'] == 0:
                    issues.append(f"   ⚠️  Proyecto #{pp['project_id']} no tiene prompts configurados")
        
        if not recent_results:
            issues.append("   ❌ No hay resultados en 24h - posible problema con las APIs")
        
        if issues:
            print("   Problemas detectados:")
            for issue in issues:
                print(issue)
        else:
            print("   ✅ No se detectaron problemas obvios")
        
        print()
        print("=" * 80)
        print("✅ Diagnóstico completado")
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

