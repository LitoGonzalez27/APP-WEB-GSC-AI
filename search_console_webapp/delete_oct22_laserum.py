#!/usr/bin/env python3
"""
Elimina análisis del 22 de octubre de 2025 para el proyecto Laserum
Esto permite hacer un re-análisis limpio con el código mejorado
"""

import sys
import psycopg2
from datetime import date

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

def check_existing_results(project_id, target_date):
    """Verifica cuántos resultados existen para la fecha"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Contar resultados
        cur.execute("""
            SELECT COUNT(*) 
            FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
        """, (project_id, target_date))
        
        count = cur.fetchone()[0]
        
        if count > 0:
            print(f"\n📊 Resultados del {target_date}:")
            
            # Mostrar muestra
            cur.execute("""
                SELECT keyword, has_ai_overview, domain_mentioned
                FROM manual_ai_results
                WHERE project_id = %s AND analysis_date = %s
                ORDER BY keyword
                LIMIT 10
            """, (project_id, target_date))
            
            results = cur.fetchall()
            
            print(f"   Total: {count} análisis")
            print(f"\n   Muestra (primeros 10):")
            for i, r in enumerate(results, 1):
                ai = "AI:✅" if r[1] else "AI:❌"
                mentioned = "Marca:✅" if r[2] else "Marca:❌"
                print(f"   {i:2d}. '{r[0]}' → {ai} {mentioned}")
        
        return count
        
    finally:
        cur.close()
        conn.close()

def delete_results(project_id, target_date):
    """Elimina los resultados de la fecha especificada"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            DELETE FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
        """, (project_id, target_date))
        
        deleted = cur.rowcount
        conn.commit()
        
        return deleted
        
    finally:
        cur.close()
        conn.close()

def delete_snapshot(project_id, target_date):
    """Elimina el snapshot de la fecha especificada (opcional)"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            DELETE FROM manual_ai_snapshots
            WHERE project_id = %s AND snapshot_date = %s
        """, (project_id, target_date))
        
        deleted = cur.rowcount
        conn.commit()
        
        return deleted
        
    finally:
        cur.close()
        conn.close()

def verify_deletion(project_id, target_date):
    """Verifica que la eliminación fue exitosa"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM manual_ai_results
            WHERE project_id = %s AND analysis_date = %s
        """, (project_id, target_date))
        
        count = cur.fetchone()[0]
        return count == 0
        
    finally:
        cur.close()
        conn.close()

def main():
    """Función principal"""
    
    print("\n" + "="*80)
    print("  🗑️  ELIMINAR ANÁLISIS DEL 22 OCTUBRE 2025 - LASERUM")
    print("="*80)
    
    # Fecha objetivo
    target_date = date(2025, 10, 22)
    
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
    
    # 2. Verificar datos existentes
    print(f"\n2️⃣ Verificando datos del {target_date}...")
    count = check_existing_results(project_id, target_date)
    
    if count == 0:
        print(f"\n✅ No hay datos del {target_date} para eliminar")
        print("   El proyecto ya está listo para un análisis limpio")
        return 0
    
    # 3. Confirmar eliminación
    print(f"\n⚠️  ADVERTENCIA:")
    print(f"   Se eliminarán {count} análisis del {target_date}")
    print(f"   Esta acción NO se puede deshacer")
    print(f"\n   Podrás re-analizarlos después desde la UI")
    
    print("\n👉 ¿Continuar con la eliminación?")
    print("   Escribe 'ELIMINAR' (en mayúsculas) para confirmar")
    print("   O presiona Enter para cancelar")
    
    confirm = input("\n> ").strip()
    
    if confirm != "ELIMINAR":
        print("\n❌ Eliminación cancelada")
        return 0
    
    # 4. Eliminar resultados
    print(f"\n3️⃣ Eliminando análisis del {target_date}...")
    
    deleted = delete_results(project_id, target_date)
    print(f"   ✅ Eliminados {deleted} análisis")
    
    # 5. Eliminar snapshot (opcional)
    print(f"\n4️⃣ Eliminando snapshot del {target_date}...")
    
    deleted_snapshot = delete_snapshot(project_id, target_date)
    if deleted_snapshot > 0:
        print(f"   ✅ Eliminado {deleted_snapshot} snapshot")
    else:
        print(f"   ℹ️  No había snapshot para eliminar")
    
    # 6. Verificar
    print(f"\n5️⃣ Verificando eliminación...")
    
    success = verify_deletion(project_id, target_date)
    
    if success:
        print(f"   ✅ Verificación exitosa: NO quedan datos del {target_date}")
    else:
        print(f"   ⚠️  Aún quedan algunos datos (esto no debería pasar)")
        return 1
    
    # 7. Resumen final
    print_section("✅ ELIMINACIÓN COMPLETADA")
    
    print(f"\n📊 Resumen:")
    print(f"   • Fecha eliminada: {target_date}")
    print(f"   • Análisis eliminados: {deleted}")
    print(f"   • Snapshots eliminados: {deleted_snapshot}")
    
    print(f"\n💡 PRÓXIMOS PASOS:")
    print(f"   1. Ve a: https://app.clicandseo.com/manual-ai")
    print(f"   2. Abre proyecto 'Laserum'")
    print(f"   3. Click en 'Analyze Project' (Force Overwrite)")
    print(f"   4. El análisis usará el CÓDIGO NUEVO con detección de acentos")
    print(f"   5. Verás resultados correctos para 'Láserum' ✅")
    
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






