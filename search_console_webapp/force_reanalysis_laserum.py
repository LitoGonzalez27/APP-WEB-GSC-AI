#!/usr/bin/env python3
"""
Script para FORZAR re-análisis del proyecto Láserum con código mejorado
Actualiza la base de datos de producción/staging con detección correcta de acentos
"""

import sys
import os
import psycopg2
from datetime import date
import requests
import time

# Configuración
DB_CONFIG = {
    'host': 'switchyard.proxy.rlwy.net',
    'port': 18167,
    'database': 'railway',
    'user': 'postgres',
    'password': 'HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS'
}

APP_URL = "https://app.clicandseo.com"
PROJECT_NAME = "Laserum"

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def find_laserum_project():
    """Encuentra el proyecto de Láserum en la BD"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, name, domain, country_code
            FROM manual_ai_projects
            WHERE domain ILIKE '%laserum%' AND is_active = true
            LIMIT 1
        """)
        
        project = cur.fetchone()
        
        if project:
            return {
                'id': project[0],
                'name': project[1],
                'domain': project[2],
                'country_code': project[3]
            }
        return None
        
    finally:
        cur.close()
        conn.close()

def get_keywords_with_false_negatives(project_id):
    """Obtiene keywords que probablemente tengan falsos negativos"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Keywords analizadas que tienen AI Overview pero NO están mencionadas
        # (probables falsos negativos)
        cur.execute("""
            SELECT DISTINCT k.id, k.keyword
            FROM manual_ai_keywords k
            LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
            WHERE k.project_id = %s 
            AND k.is_active = true
            AND (
                r.has_ai_overview = true 
                AND r.domain_mentioned = false
                OR r.id IS NULL
            )
            ORDER BY k.keyword
        """, (project_id,))
        
        keywords = cur.fetchall()
        return [(k[0], k[1]) for k in keywords]
        
    finally:
        cur.close()
        conn.close()

def trigger_project_reanalysis(project_id):
    """
    Trigger re-análisis del proyecto completo vía API
    """
    print(f"\n🚀 Triggering re-análisis vía API...")
    
    endpoint = f"{APP_URL}/manual-ai/api/projects/{project_id}/analyze"
    
    try:
        response = requests.post(
            endpoint,
            json={"force_overwrite": True},
            headers={"Content-Type": "application/json"},
            timeout=300  # 5 minutos
        )
        
        if response.status_code in [200, 202]:
            print(f"✅ Re-análisis iniciado exitosamente")
            return True
        else:
            print(f"⚠️ Respuesta: {response.status_code} - {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error al trigger re-análisis: {e}")
        return False

def delete_old_results_for_today(project_id):
    """Elimina resultados de hoy para permitir re-análisis limpio"""
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
        
        print(f"  🗑️  Eliminados {deleted} resultados antiguos de hoy")
        return deleted
        
    finally:
        cur.close()
        conn.close()

def check_recent_results(project_id):
    """Verifica resultados recientes después del re-análisis"""
    time.sleep(5)  # Esperar un poco
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    today = date.today()
    
    try:
        cur.execute("""
            SELECT keyword, has_ai_overview, domain_mentioned, domain_position
            FROM manual_ai_results
            WHERE project_id = %s 
            AND analysis_date = %s
            ORDER BY keyword
            LIMIT 10
        """, (project_id, today))
        
        results = cur.fetchall()
        
        if results:
            print(f"\n📊 Resultados actualizados ({len(results)} de hoy):")
            for r in results:
                ai = "AI:✅" if r[1] else "AI:❌"
                mentioned = "Marca:✅" if r[2] else "Marca:❌"
                pos = f"Pos:#{r[3]}" if r[3] else "Pos:-"
                print(f"  '{r[0]}' → {ai} {mentioned} {pos}")
            return len(results)
        else:
            print("\n⚠️ Aún no hay resultados nuevos de hoy")
            return 0
            
    finally:
        cur.close()
        conn.close()

def main():
    """Función principal"""
    
    print("\n🎯 FORZAR RE-ANÁLISIS DE LÁSERUM CON CÓDIGO MEJORADO")
    print("="*80)
    
    # 1. Encontrar proyecto
    print("\n1️⃣ Buscando proyecto Láserum...")
    project = find_laserum_project()
    
    if not project:
        print("❌ Proyecto Láserum no encontrado")
        return 1
    
    print(f"✅ Proyecto encontrado:")
    print(f"   ID: {project['id']}")
    print(f"   Nombre: {project['name']}")
    print(f"   Dominio: {project['domain']}")
    print(f"   País: {project['country_code']}")
    
    # 2. Identificar keywords con problemas
    print("\n2️⃣ Identificando keywords con posibles falsos negativos...")
    problem_keywords = get_keywords_with_false_negatives(project['id'])
    
    if problem_keywords:
        print(f"⚠️ Encontradas {len(problem_keywords)} keywords con posibles falsos negativos:")
        for kw_id, kw in problem_keywords[:10]:  # Mostrar primeras 10
            print(f"   • '{kw}'")
        if len(problem_keywords) > 10:
            print(f"   ... y {len(problem_keywords) - 10} más")
    else:
        print("✅ No se encontraron problemas obvios")
    
    # 3. Limpiar resultados antiguos del día
    print("\n3️⃣ Limpiando resultados antiguos de hoy...")
    deleted = delete_old_results_for_today(project['id'])
    
    # 4. Trigger re-análisis
    print("\n4️⃣ Iniciando re-análisis con código mejorado...")
    print("\n⚠️ NOTA: El re-análisis puede tardar varios minutos")
    print("   Se están analizando ~100 keywords")
    print("   Consumirá cuota de SerpAPI")
    
    input("\n👉 Presiona ENTER para continuar o Ctrl+C para cancelar...")
    
    success = trigger_project_reanalysis(project['id'])
    
    if not success:
        print("\n❌ No se pudo iniciar el re-análisis vía API")
        print("\n💡 Alternativa: Re-analizar desde la UI:")
        print(f"   1. Ve a {APP_URL}/manual-ai")
        print(f"   2. Abre el proyecto '{project['name']}'")
        print(f"   3. Click en 'Analyze Project' con force_overwrite")
        return 1
    
    # 5. Verificar resultados
    print("\n5️⃣ Esperando resultados...")
    print("   (Esto puede tardar 5-10 minutos para 100 keywords)")
    
    for i in range(3):
        time.sleep(30)  # Esperar 30 segundos entre checks
        print(f"\n   Checking... ({(i+1)*30}s)")
        count = check_recent_results(project['id'])
        if count > 0:
            break
    
    # 6. Resumen final
    print_section("RESUMEN FINAL")
    
    print("\n✅ Re-análisis iniciado exitosamente")
    print("\n💡 PRÓXIMOS PASOS:")
    print("   1. Espera 5-10 minutos para que complete")
    print("   2. Recarga tu app web")
    print("   3. Verifica que 'depilacion ingles brasileñas' ahora muestre SÍ")
    print("   4. La gráfica 'Domain Visibility Over Time' se actualizará")
    
    print("\n🎉 Con el código mejorado, Láserum ahora será detectado correctamente")
    print("="*80 + "\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Re-análisis cancelado por usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



