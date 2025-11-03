#!/usr/bin/env python3
"""
Re-análisis completo de Laserum en AMBOS módulos:
1. Manual AI
2. AI Mode Projects

Con código mejorado de detección de acentos
"""

import sys
import os
import psycopg2
from datetime import date
import time

# Setup path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db_connection

# Configuración de base de datos de producción
DB_CONFIG = {
    'host': 'switchyard.proxy.rlwy.net',
    'port': 18167,
    'database': 'railway',
    'user': 'postgres',
    'password': 'HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS'
}

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

# ============================================================================
# MÓDULO 1: MANUAL AI
# ============================================================================

def reanalyze_manual_ai():
    """Re-analiza proyecto Laserum en Manual AI"""
    
    print_section("1️⃣ RE-ANÁLISIS MANUAL AI - LASERUM")
    
    try:
        from manual_ai.services.analysis_service import AnalysisService
        from manual_ai.models.project_repository import ProjectRepository
        from manual_ai.models.result_repository import ResultRepository
        
        # Conectar a BD
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Buscar proyecto Laserum
        cur.execute("""
            SELECT id, name, domain, country_code
            FROM manual_ai_projects
            WHERE domain ILIKE '%laserum%' AND is_active = true
            LIMIT 1
        """)
        
        project_row = cur.fetchone()
        
        if not project_row:
            print("❌ Proyecto Laserum NO encontrado en Manual AI")
            cur.close()
            conn.close()
            return False
        
        project_id = project_row[0]
        project_name = project_row[1]
        project_domain = project_row[2]
        
        print(f"\n✅ Proyecto encontrado:")
        print(f"   ID: {project_id}")
        print(f"   Nombre: {project_name}")
        print(f"   Dominio: {project_domain}")
        
        # Contar keywords activas
        cur.execute("""
            SELECT COUNT(*) 
            FROM manual_ai_keywords 
            WHERE project_id = %s AND is_active = true
        """, (project_id,))
        
        kw_count = cur.fetchone()[0]
        print(f"   Keywords activas: {kw_count}")
        
        cur.close()
        conn.close()
        
        # Eliminar resultados de hoy para forzar re-análisis
        print(f"\n🗑️  Limpiando resultados anteriores de hoy...")
        
        result_repo = ResultRepository()
        today = date.today()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
        """, (project_id, today))
        
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"   Eliminados {deleted} resultados anteriores")
        
        # Ejecutar análisis completo
        print(f"\n🚀 Iniciando re-análisis de {kw_count} keywords...")
        print(f"   ⚠️ Esto tomará aproximadamente {kw_count * 2} segundos (~{kw_count * 2 / 60:.1f} minutos)")
        print(f"   💰 Consumirá ~{kw_count} créditos de SerpAPI\n")
        
        # Obtener proyecto completo
        project_repo = ProjectRepository()
        project = project_repo.get_project_with_details(project_id)
        
        if not project:
            print("❌ No se pudo obtener detalles del proyecto")
            return False
        
        # Ejecutar análisis con force_overwrite
        analysis_service = AnalysisService()
        
        print("⏳ Ejecutando análisis... (esto puede tardar varios minutos)\n")
        
        # Nota: Necesitamos user_id, vamos a buscar el owner del proyecto
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT user_id FROM manual_ai_projects WHERE id = %s
        """, (project_id,))
        
        user_id = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        results = analysis_service.run_project_analysis(
            project_id=project_id,
            force_overwrite=True,
            user_id=user_id
        )
        
        if isinstance(results, dict) and 'error' in results:
            print(f"\n❌ Error en análisis: {results.get('error')}")
            return False
        
        print(f"\n✅ Manual AI: Análisis completado!")
        print(f"   Keywords analizadas: {len(results)}")
        
        # Mostrar muestra de resultados
        print(f"\n📊 Muestra de resultados (primeros 10):")
        for i, result in enumerate(results[:10]):
            kw = result.get('keyword', 'N/A')
            has_ai = "AI:✅" if result.get('has_ai_overview', False) else "AI:❌"
            mentioned = "Marca:✅" if result.get('domain_mentioned', False) else "Marca:❌"
            pos = f"Pos:#{result.get('position', '-')}" if result.get('position') else "Pos:-"
            
            print(f"   {i+1}. '{kw}' → {has_ai} {mentioned} {pos}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error en Manual AI: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# MÓDULO 2: AI MODE PROJECTS
# ============================================================================

def reanalyze_ai_mode():
    """Re-analiza proyecto Laserum en AI Mode Projects"""
    
    print_section("2️⃣ RE-ANÁLISIS AI MODE - LASERUM")
    
    try:
        # Conectar a BD
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Buscar proyecto Laserum en AI Mode
        cur.execute("""
            SELECT id, name, domain, country_code
            FROM ai_mode_projects
            WHERE domain ILIKE '%laserum%' AND is_active = true
            LIMIT 1
        """)
        
        project_row = cur.fetchone()
        
        if not project_row:
            print("⚠️  Proyecto Laserum NO encontrado en AI Mode")
            print("   (Esto es normal si solo usas Manual AI)")
            cur.close()
            conn.close()
            return True  # No es error, simplemente no existe
        
        project_id = project_row[0]
        project_name = project_row[1]
        project_domain = project_row[2]
        
        print(f"\n✅ Proyecto encontrado:")
        print(f"   ID: {project_id}")
        print(f"   Nombre: {project_name}")
        print(f"   Dominio: {project_domain}")
        
        # Contar keywords
        cur.execute("""
            SELECT COUNT(*) 
            FROM ai_mode_keywords 
            WHERE project_id = %s AND is_active = true
        """, (project_id,))
        
        kw_count = cur.fetchone()[0]
        print(f"   Keywords activas: {kw_count}")
        
        cur.close()
        conn.close()
        
        if kw_count == 0:
            print("⚠️  No hay keywords activas en este proyecto de AI Mode")
            return True
        
        # Eliminar resultados de hoy
        print(f"\n🗑️  Limpiando resultados anteriores de hoy...")
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        today = date.today()
        
        cur.execute("""
            DELETE FROM ai_mode_results
            WHERE project_id = %s AND analysis_date = %s
        """, (project_id, today))
        
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"   Eliminados {deleted} resultados anteriores")
        
        # Ejecutar análisis
        print(f"\n🚀 Iniciando re-análisis de AI Mode...")
        print(f"   ⚠️ Esto tomará aproximadamente {kw_count * 2} segundos\n")
        
        # Import AI Mode service
        from ai_mode_projects.services.cron_service import execute_daily_analysis
        
        print("⏳ Ejecutando análisis de AI Mode...\n")
        
        # Ejecutar análisis solo para este proyecto
        result = execute_daily_analysis(project_ids=[project_id])
        
        print(f"\n✅ AI Mode: Análisis completado!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error en AI Mode: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Función principal"""
    
    print("\n" + "="*80)
    print("  🎯 RE-ANÁLISIS COMPLETO DE LASERUM")
    print("  📦 Módulos: Manual AI + AI Mode")
    print("  🔧 Código: Detección mejorada de acentos")
    print("="*80)
    
    print("\n⚠️  IMPORTANTE:")
    print("   • Este proceso puede tardar 10-15 minutos")
    print("   • Consumirá cuota de SerpAPI (~100-200 créditos)")
    print("   • Actualizará la base de datos de PRODUCCIÓN")
    
    confirm = input("\n👉 ¿Continuar? (escribe 'SI' para confirmar): ")
    
    if confirm.upper() != 'SI':
        print("\n❌ Re-análisis cancelado")
        return 1
    
    start_time = time.time()
    
    # Ejecutar re-análisis de ambos módulos
    success_manual = reanalyze_manual_ai()
    time.sleep(2)  # Pausa entre módulos
    success_ai_mode = reanalyze_ai_mode()
    
    elapsed = time.time() - start_time
    
    # Resumen final
    print_section("📊 RESUMEN FINAL")
    
    print(f"\n✅ Manual AI: {'OK' if success_manual else 'FALLÓ'}")
    print(f"✅ AI Mode: {'OK' if success_ai_mode else 'FALLÓ'}")
    print(f"\n⏱️  Tiempo total: {elapsed / 60:.1f} minutos")
    
    if success_manual or success_ai_mode:
        print("\n🎉 RE-ANÁLISIS COMPLETADO!")
        print("\n💡 PRÓXIMOS PASOS:")
        print("   1. Recarga tu app web (Ctrl+F5)")
        print("   2. Verifica 'depilacion ingles brasileñas' → Debería decir SÍ ✅")
        print("   3. Verifica 'clinica laser' → Debería decir SÍ ✅")
        print("   4. La gráfica 'Domain Visibility' debería actualizarse")
    else:
        print("\n⚠️  Hubo errores durante el re-análisis")
        print("   Revisa los logs arriba para más detalles")
    
    print("\n" + "="*80 + "\n")
    
    return 0 if (success_manual or success_ai_mode) else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Re-análisis cancelado por usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



