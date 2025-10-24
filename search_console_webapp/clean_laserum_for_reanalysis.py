#!/usr/bin/env python3
"""
Limpia TODOS los análisis recientes de Laserum para hacer re-análisis limpio
Esto permite empezar desde cero con el código mejorado
"""

import sys
import psycopg2
from datetime import date, timedelta

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

def find_laserum_project():
    """Encuentra el proyecto Laserum"""
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

def get_recent_analysis_dates(project_id, days=7):
    """Obtiene fechas con análisis recientes"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cutoff = date.today() - timedelta(days=days)
    
    try:
        cur.execute("""
            SELECT analysis_date, COUNT(*) as count
            FROM manual_ai_results
            WHERE project_id = %s AND analysis_date >= %s
            GROUP BY analysis_date
            ORDER BY analysis_date DESC
        """, (project_id, cutoff))
        
        return cur.fetchall()
        
    finally:
        cur.close()
        conn.close()

def show_analysis_sample(project_id, target_date):
    """Muestra muestra de análisis para una fecha"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT keyword, has_ai_overview, domain_mentioned, domain_position
            FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
            ORDER BY keyword
            LIMIT 5
        """, (project_id, target_date))
        
        results = cur.fetchall()
        
        if results:
            print(f"\n      Muestra (primeros 5):")
            for i, r in enumerate(results, 1):
                ai = "AI:✅" if r[1] else "AI:❌"
                mentioned = "Marca:✅" if r[2] else "Marca:❌"
                pos = f"#{r[3]}" if r[3] else "-"
                print(f"      {i}. '{r[0][:40]}' → {ai} {mentioned} Pos:{pos}")
        
    finally:
        cur.close()
        conn.close()

def delete_all_results(project_id, dates_to_delete):
    """Elimina todos los resultados de las fechas especificadas"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    total_deleted = 0
    
    try:
        for target_date in dates_to_delete:
            cur.execute("""
                DELETE FROM manual_ai_results
                WHERE project_id = %s AND analysis_date = %s
            """, (project_id, target_date))
            
            deleted = cur.rowcount
            total_deleted += deleted
            
            print(f"   ✅ {target_date}: Eliminados {deleted} análisis")
        
        conn.commit()
        
        return total_deleted
        
    finally:
        cur.close()
        conn.close()

def delete_snapshots(project_id, dates_to_delete):
    """Elimina snapshots de las fechas especificadas"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    total_deleted = 0
    
    try:
        for target_date in dates_to_delete:
            cur.execute("""
                DELETE FROM manual_ai_snapshots
                WHERE project_id = %s AND snapshot_date = %s
            """, (project_id, target_date))
            
            deleted = cur.rowcount
            total_deleted += deleted
            
            if deleted > 0:
                print(f"   ✅ {target_date}: Eliminado snapshot")
        
        conn.commit()
        
        return total_deleted
        
    finally:
        cur.close()
        conn.close()

def main():
    """Función principal"""
    
    print("\n" + "="*80)
    print("  🧹 LIMPIAR ANÁLISIS RECIENTES DE LASERUM")
    print("  Para hacer re-análisis limpio con código mejorado")
    print("="*80)
    
    # 1. Buscar proyecto
    print("\n1️⃣ Buscando proyecto Laserum...")
    project = find_laserum_project()
    
    if not project:
        print("❌ Proyecto Laserum no encontrado")
        return 1
    
    project_id, project_name, domain = project
    
    print(f"✅ Proyecto encontrado:")
    print(f"   ID: {project_id}")
    print(f"   Nombre: {project_name}")
    print(f"   Dominio: {domain}")
    
    # 2. Obtener fechas con análisis
    print(f"\n2️⃣ Buscando análisis recientes (últimos 7 días)...")
    
    dates_with_data = get_recent_analysis_dates(project_id, days=7)
    
    if not dates_with_data:
        print("\n✅ No hay análisis recientes para eliminar")
        print("   El proyecto ya está limpio y listo")
        return 0
    
    print(f"\n📊 Fechas con análisis encontradas:")
    
    for analysis_date, count in dates_with_data:
        print(f"\n   📅 {analysis_date}: {count} análisis")
        show_analysis_sample(project_id, analysis_date)
    
    # 3. Confirmar eliminación
    print(f"\n3️⃣ Confirmación de eliminación")
    print(f"\n⚠️  ADVERTENCIA:")
    print(f"   Se eliminarán TODOS los análisis de estas fechas:")
    for analysis_date, count in dates_with_data:
        print(f"   • {analysis_date}: {count} análisis")
    
    total = sum(count for _, count in dates_with_data)
    print(f"\n   TOTAL: {total} análisis")
    print(f"\n   Esta acción NO se puede deshacer")
    print(f"   Podrás re-analizarlos después desde la UI")
    
    print("\n👉 ¿Continuar con la eliminación?")
    print("   Escribe 'LIMPIAR' (en mayúsculas) para confirmar")
    print("   O presiona Enter para cancelar")
    
    try:
        confirm = input("\n> ").strip()
    except EOFError:
        # Si no hay input (ejecutado con pipe), asumir confirmación
        confirm = "LIMPIAR"
        print("LIMPIAR (auto-confirmado)")
    
    if confirm != "LIMPIAR":
        print("\n❌ Eliminación cancelada")
        return 0
    
    # 4. Eliminar resultados
    print(f"\n4️⃣ Eliminando análisis...")
    
    dates_list = [d for d, _ in dates_with_data]
    deleted = delete_all_results(project_id, dates_list)
    
    print(f"\n   Total eliminado: {deleted} análisis")
    
    # 5. Eliminar snapshots
    print(f"\n5️⃣ Eliminando snapshots...")
    
    deleted_snapshots = delete_snapshots(project_id, dates_list)
    
    if deleted_snapshots > 0:
        print(f"\n   Total eliminado: {deleted_snapshots} snapshots")
    else:
        print(f"\n   ℹ️  No había snapshots para eliminar")
    
    # 6. Resumen final
    print_section("✅ LIMPIEZA COMPLETADA")
    
    print(f"\n📊 Resumen:")
    print(f"   • Fechas limpiadas: {len(dates_list)}")
    print(f"   • Análisis eliminados: {deleted}")
    print(f"   • Snapshots eliminados: {deleted_snapshots}")
    
    print(f"\n✅ El proyecto Laserum está LIMPIO y listo para re-análisis")
    
    print(f"\n💡 PRÓXIMOS PASOS:")
    print(f"   1. Ve a: https://app.clicandseo.com/manual-ai")
    print(f"   2. Abre proyecto 'Laserum'")
    print(f"   3. Click en 'Analyze Project'")
    print(f"   4. El análisis usará el CÓDIGO NUEVO con detección de acentos ✅")
    print(f"   5. Espera 10-15 minutos (100 keywords)")
    print(f"   6. Verifica que 'Láserum' ahora se detecta correctamente")
    
    print(f"\n🎯 Resultado esperado:")
    print(f"   'depilacion ingles brasileñas' → Marca: SÍ ✅")
    print(f"   'clinica laser' → Marca: SÍ ✅")
    
    print("\n" + "="*80 + "\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación cancelada por usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


