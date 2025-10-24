#!/usr/bin/env python3
"""
Limpia análisis recientes de Laserum en AI Mode Projects
Permite re-análisis limpio con código mejorado
"""

import sys
import psycopg2
from datetime import date, timedelta

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

def find_laserum_ai_mode():
    """Encuentra proyecto Laserum en AI Mode"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Buscar por name o brand_name
        cur.execute("""
            SELECT id, name, brand_name, is_active, created_at
            FROM ai_mode_projects
            WHERE (name ILIKE '%laserum%' OR brand_name ILIKE '%laserum%')
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        row = cur.fetchone()
        return row if row else None
        
    finally:
        cur.close()
        conn.close()

def get_recent_snapshots(project_id, days=7):
    """Obtiene snapshots recientes"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cutoff = date.today() - timedelta(days=days)
    
    try:
        cur.execute("""
            SELECT snapshot_date
            FROM ai_mode_snapshots
            WHERE project_id = %s AND snapshot_date >= %s
            ORDER BY snapshot_date DESC
        """, (project_id, cutoff))
        
        return [row[0] for row in cur.fetchall()]
        
    finally:
        cur.close()
        conn.close()

def get_recent_results(project_id, days=7):
    """Obtiene fechas con resultados recientes"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cutoff = date.today() - timedelta(days=days)
    
    try:
        # Verificar si hay columna analysis_date o created_at
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ai_mode_results'
            AND column_name IN ('analysis_date', 'created_at', 'snapshot_date')
        """)
        
        date_columns = [row[0] for row in cur.fetchall()]
        
        if not date_columns:
            print("   ⚠️  No se encontró columna de fecha en ai_mode_results")
            return []
        
        date_col = date_columns[0]  # Usar la primera disponible
        
        cur.execute(f"""
            SELECT DATE({date_col}) as date_only, COUNT(*) as count
            FROM ai_mode_results
            WHERE project_id = %s AND {date_col} >= %s
            GROUP BY DATE({date_col})
            ORDER BY date_only DESC
        """, (project_id, cutoff))
        
        return cur.fetchall()
        
    finally:
        cur.close()
        conn.close()

def show_result_sample(project_id, target_date):
    """Muestra muestra de resultados"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Obtener columnas disponibles
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ai_mode_results'
            ORDER BY ordinal_position
            LIMIT 20
        """)
        
        cols = [row[0] for row in cur.fetchall()]
        
        # Intentar obtener muestra
        date_col = 'created_at' if 'created_at' in cols else 'analysis_date'
        
        query = f"""
            SELECT *
            FROM ai_mode_results
            WHERE project_id = %s 
            AND DATE({date_col}) = %s
            LIMIT 3
        """
        
        cur.execute(query, (project_id, target_date))
        results = cur.fetchall()
        
        if results:
            print(f"\n      Muestra (primeros 3 resultados)")
            for i, r in enumerate(results, 1):
                print(f"      {i}. ID: {r[0]}")  # Mostrar solo ID por ahora
        
    except Exception as e:
        print(f"      ℹ️  No se pudo mostrar muestra: {e}")
    finally:
        cur.close()
        conn.close()

def delete_results(project_id, dates_to_delete):
    """Elimina resultados de las fechas especificadas"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    total_deleted = 0
    
    try:
        # Determinar columna de fecha
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ai_mode_results'
            AND column_name IN ('analysis_date', 'created_at', 'snapshot_date')
        """)
        
        date_columns = [row[0] for row in cur.fetchall()]
        if not date_columns:
            print("   ❌ No se puede determinar columna de fecha")
            return 0
        
        date_col = date_columns[0]
        
        for target_date in dates_to_delete:
            cur.execute(f"""
                DELETE FROM ai_mode_results
                WHERE project_id = %s AND DATE({date_col}) = %s
            """, (project_id, target_date))
            
            deleted = cur.rowcount
            total_deleted += deleted
            
            if deleted > 0:
                print(f"   ✅ {target_date}: Eliminados {deleted} resultados")
        
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
                DELETE FROM ai_mode_snapshots
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
    print("  🧹 LIMPIAR AI MODE - LASERUM")
    print("  Para hacer re-análisis limpio con código mejorado")
    print("="*80)
    
    # 1. Buscar proyecto
    print("\n1️⃣ Buscando proyecto Laserum en AI Mode...")
    project = find_laserum_ai_mode()
    
    if not project:
        print("\n⚠️  Proyecto Laserum NO encontrado en AI Mode Projects")
        print("   Esto puede ser normal si solo usas Manual AI")
        print("   No hay nada que limpiar en AI Mode")
        return 0
    
    project_id, name, brand_name, is_active, created_at = project
    
    print(f"✅ Proyecto encontrado:")
    print(f"   ID: {project_id}")
    print(f"   Nombre: {name}")
    print(f"   Brand: {brand_name}")
    print(f"   Activo: {'SÍ' if is_active else 'NO'}")
    print(f"   Creado: {created_at}")
    
    # 2. Verificar resultados recientes
    print(f"\n2️⃣ Buscando datos recientes (últimos 7 días)...")
    
    results_dates = get_recent_results(project_id, days=7)
    
    if not results_dates:
        print("\n✅ No hay resultados recientes para eliminar")
        
        # Verificar snapshots de todas formas
        snapshot_dates = get_recent_snapshots(project_id, days=7)
        
        if snapshot_dates:
            print(f"\n⚠️  Pero hay snapshots:")
            for snap_date in snapshot_dates:
                print(f"   📸 {snap_date}")
            
            print("\n   ¿Eliminar estos snapshots?")
            try:
                confirm = input("   Escribe 'SI' para confirmar: ").strip()
            except EOFError:
                confirm = "SI"
                print("SI (auto-confirmado)")
            
            if confirm == "SI":
                deleted = delete_snapshots(project_id, snapshot_dates)
                print(f"\n   ✅ Eliminados {deleted} snapshots")
                print("\n✅ Limpieza completada")
            else:
                print("\n❌ Limpieza cancelada")
        else:
            print("   Tampoco hay snapshots recientes")
            print("   El proyecto AI Mode ya está limpio")
        
        return 0
    
    # 3. Mostrar datos encontrados
    print(f"\n📊 Fechas con datos encontradas:")
    
    for result_date, count in results_dates:
        print(f"\n   📅 {result_date}: {count} resultados")
        show_result_sample(project_id, result_date)
    
    # 4. Confirmar eliminación
    print(f"\n3️⃣ Confirmación de eliminación")
    print(f"\n⚠️  ADVERTENCIA:")
    print(f"   Se eliminarán todos los datos de estas fechas:")
    
    for result_date, count in results_dates:
        print(f"   • {result_date}: {count} resultados")
    
    total = sum(count for _, count in results_dates)
    print(f"\n   TOTAL: {total} resultados")
    
    snapshot_dates = get_recent_snapshots(project_id, days=7)
    if snapshot_dates:
        print(f"   + {len(snapshot_dates)} snapshots")
    
    print(f"\n   Esta acción NO se puede deshacer")
    
    print("\n👉 ¿Continuar con la eliminación?")
    print("   Escribe 'LIMPIAR' (en mayúsculas) para confirmar")
    
    try:
        confirm = input("\n> ").strip()
    except EOFError:
        confirm = "LIMPIAR"
        print("LIMPIAR (auto-confirmado)")
    
    if confirm != "LIMPIAR":
        print("\n❌ Eliminación cancelada")
        return 0
    
    # 5. Eliminar datos
    print(f"\n4️⃣ Eliminando resultados...")
    
    dates_list = [d for d, _ in results_dates]
    deleted_results = delete_results(project_id, dates_list)
    
    print(f"\n   Total eliminado: {deleted_results} resultados")
    
    # 6. Eliminar snapshots
    print(f"\n5️⃣ Eliminando snapshots...")
    
    deleted_snapshots = delete_snapshots(project_id, snapshot_dates)
    
    if deleted_snapshots > 0:
        print(f"\n   Total eliminado: {deleted_snapshots} snapshots")
    
    # 7. Resumen
    print_section("✅ LIMPIEZA AI MODE COMPLETADA")
    
    print(f"\n📊 Resumen:")
    print(f"   • Fechas limpiadas: {len(dates_list)}")
    print(f"   • Resultados eliminados: {deleted_results}")
    print(f"   • Snapshots eliminados: {deleted_snapshots}")
    
    print(f"\n✅ Proyecto '{name}' limpio y listo para re-análisis")
    
    print(f"\n💡 PRÓXIMOS PASOS:")
    print(f"   1. El cron diario de AI Mode ejecutará automáticamente")
    print(f"   2. O ejecuta re-análisis manualmente si tienes endpoint")
    print(f"   3. El nuevo análisis usará código mejorado con detección de acentos ✅")
    
    print("\n" + "="*80 + "\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación cancelada")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


