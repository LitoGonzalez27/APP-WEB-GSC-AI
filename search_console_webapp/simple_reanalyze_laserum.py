#!/usr/bin/env python3
"""
Re-análisis SIMPLE Y DIRECTO de Laserum
Usa la API interna en lugar de servicios complejos
"""

import sys
import psycopg2
import requests
import time
from datetime import date

# Configuración
DB_CONFIG = {
    'host': 'switchyard.proxy.rlwy.net',
    'port': 18167,
    'database': 'railway',
    'user': 'postgres',
    'password': 'HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS'
}

APP_URL = "https://app.clicandseo.com"

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def find_laserum_manual_ai():
    """Encuentra proyecto Laserum en Manual AI"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, name, domain
            FROM manual_ai_projects
            WHERE domain ILIKE '%laserum%' AND is_active = true
            LIMIT 1
        """)
        
        row = cur.fetchone()
        return row if row else None
        
    finally:
        cur.close()
        conn.close()

def delete_today_results(project_id):
    """Elimina resultados de hoy para permitir re-análisis"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    today = date.today()
    
    try:
        cur.execute("""
            DELETE FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
        """, (project_id, today))
        
        deleted = cur.rowcount
        conn.commit()
        
        return deleted
        
    finally:
        cur.close()
        conn.close()

def trigger_manual_analysis_via_cron():
    """Trigger análisis completo vía endpoint de cron"""
    
    print("\n🚀 Triggering análisis vía cron endpoint...")
    
    endpoint = f"{APP_URL}/manual-ai/api/cron/daily-analysis?async=1"
    
    try:
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=60
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
        if response.status_code in [200, 202]:
            return True
        else:
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def check_results_progress(project_id, expected_count=100):
    """Verifica el progreso del análisis"""
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    today = date.today()
    
    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
        """, (project_id, today))
        
        count = cur.fetchone()[0]
        return count
        
    finally:
        cur.close()
        conn.close()

def show_sample_results(project_id, limit=15):
    """Muestra muestra de resultados"""
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    today = date.today()
    
    try:
        cur.execute("""
            SELECT keyword, has_ai_overview, domain_mentioned, domain_position
            FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
            ORDER BY keyword
            LIMIT %s
        """, (project_id, today, limit))
        
        results = cur.fetchall()
        
        if results:
            print(f"\n📊 Muestra de resultados (primeros {len(results)}):")
            for i, r in enumerate(results, 1):
                kw = r[0]
                ai = "AI:✅" if r[1] else "AI:❌"
                mentioned = "Marca:✅" if r[2] else "Marca:❌"
                pos = f"Pos:#{r[3]}" if r[3] else "Pos:-"
                
                print(f"   {i:2d}. '{kw}' → {ai} {mentioned} {pos}")
        else:
            print("\n⚠️  Aún no hay resultados")
        
        return len(results)
        
    finally:
        cur.close()
        conn.close()

def main():
    """Función principal"""
    
    print("\n" + "="*80)
    print("  🎯 RE-ANÁLISIS SIMPLE DE LASERUM (Manual AI)")
    print("  🔧 Código mejorado: Detección de acentos activada")
    print("="*80)
    
    # 1. Buscar proyecto
    print("\n1️⃣ Buscando proyecto Laserum...")
    project = find_laserum_manual_ai()
    
    if not project:
        print("❌ Proyecto no encontrado")
        return 1
    
    project_id, project_name, domain = project
    
    print(f"✅ Proyecto encontrado:")
    print(f"   ID: {project_id}")
    print(f"   Nombre: {project_name}")
    print(f"   Dominio: {domain}")
    
    # 2. Limpiar resultados anteriores
    print("\n2️⃣ Limpiando resultados anteriores de hoy...")
    deleted = delete_today_results(project_id)
    print(f"   Eliminados: {deleted} resultados")
    
    # 3. Trigger análisis
    print("\n3️⃣ Triggering análisis completo...")
    print("   ⚠️ Nota: El cron ejecutará el análisis en background")
    print("   ⚠️ Esto puede tardar 10-15 minutos para 100 keywords")
    
    success = trigger_manual_analysis_via_cron()
    
    if not success:
        print("\n❌ No se pudo trigger el análisis")
        print("\n💡 ALTERNATIVA:")
        print("   1. Ve a https://app.clicandseo.com/manual-ai")
        print("   2. Abre proyecto 'Laserum'")
        print("   3. Click en botón de análisis")
        return 1
    
    print("\n✅ Análisis iniciado en background!")
    
    # 4. Monitorear progreso
    print("\n4️⃣ Monitoreando progreso...")
    print("   (Revisando cada 60 segundos)")
    
    for i in range(15):  # Máximo 15 minutos
        time.sleep(60)
        
        count = check_results_progress(project_id)
        print(f"\n   [{i+1}/15] Resultados actuales: {count}/~100")
        
        if count > 0:
            show_sample_results(project_id, limit=5)
        
        if count >= 80:  # Si tiene al menos 80%, consideramos que está casi listo
            print("\n✅ Análisis prácticamente completado!")
            break
    
    # 5. Resultados finales
    print_section("📊 RESULTADOS FINALES")
    
    final_count = check_results_progress(project_id)
    
    print(f"\n✅ Total de análisis completados: {final_count}")
    
    if final_count > 0:
        show_sample_results(project_id, limit=15)
        
        print("\n🎉 RE-ANÁLISIS COMPLETADO!")
        print("\n💡 PRÓXIMOS PASOS:")
        print("   1. Recarga tu app (Ctrl+F5 o Cmd+Shift+R)")
        print("   2. Ve al proyecto Laserum")
        print("   3. Verifica 'depilacion ingles brasileñas' → Debería decir SÍ ✅")
        print("   4. Verifica 'clinica laser' → Debería decir SÍ ✅")
    else:
        print("\n⚠️  El análisis aún no ha completado")
        print("   Espera unos minutos más y recarga tu app")
    
    print("\n" + "="*80 + "\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelado por usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



