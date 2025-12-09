#!/usr/bin/env python3
"""
Auditoría completa del sistema Manual AI y AI Mode
Diagnostica problemas de cron, datos faltantes y detección de marca
"""

import sys
import os
import psycopg2
from datetime import datetime, date, timedelta
import json

# Configuración de base de datos
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

def audit_database():
    """Auditar estado de la base de datos"""
    
    print("\n🔍 AUDITORÍA COMPLETA DEL SISTEMA AI MODE")
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # 1. Verificar proyectos activos
        print_section("1. PROYECTOS MANUAL AI")
        
        cur.execute("""
            SELECT id, name, domain, is_active, created_at
            FROM manual_ai_projects
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        projects = cur.fetchall()
        if projects:
            print(f"Total proyectos: {len(projects)}")
            for p in projects:
                status = "✅ ACTIVO" if p[3] else "❌ INACTIVO"
                print(f"  {status} ID:{p[0]} | {p[1]} | {p[2]} | Creado: {p[4]}")
        else:
            print("⚠️  No hay proyectos en manual_ai_projects")
        
        # 2. Verificar keywords
        print_section("2. KEYWORDS POR PROYECTO")
        
        for project in projects[:3]:  # Solo primeros 3 proyectos
            project_id = project[0]
            project_name = project[1]
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM manual_ai_keywords 
                WHERE project_id = %s AND is_active = true
            """, (project_id,))
            
            kw_count = cur.fetchone()[0]
            print(f"  Proyecto '{project_name}' (ID:{project_id}): {kw_count} keywords activas")
        
        # 3. Verificar resultados recientes
        print_section("3. RESULTADOS DE ANÁLISIS (ÚLTIMOS 7 DÍAS)")
        
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        cur.execute("""
            SELECT analysis_date, COUNT(*) as count
            FROM manual_ai_results
            WHERE analysis_date >= %s
            GROUP BY analysis_date
            ORDER BY analysis_date DESC
        """, (week_ago,))
        
        results_by_date = cur.fetchall()
        
        if results_by_date:
            print(f"\nResultados encontrados:")
            for row in results_by_date:
                print(f"  📅 {row[0]}: {row[1]} análisis")
        else:
            print(f"  ⚠️  NO HAY RESULTADOS desde {week_ago}")
        
        # 4. Verificar resultados específicos del 21 y 22 octubre
        print_section("4. DETALLE 21-22 OCTUBRE 2025")
        
        for day in [21, 22]:
            check_date = date(2025, 10, day)
            
            cur.execute("""
                SELECT COUNT(*)
                FROM manual_ai_results
                WHERE analysis_date = %s
            """, (check_date,))
            
            count = cur.fetchone()[0]
            
            if count > 0:
                print(f"  ✅ {check_date}: {count} resultados")
                
                # Mostrar detalles
                cur.execute("""
                    SELECT project_id, keyword, domain_mentioned, has_ai_overview
                    FROM manual_ai_results
                    WHERE analysis_date = %s
                    LIMIT 5
                """, (check_date,))
                
                samples = cur.fetchall()
                for s in samples:
                    mentioned = "SÍ" if s[2] else "NO"
                    ai = "SÍ" if s[3] else "NO"
                    print(f"      '{s[1]}' → AI:{ai}, Mencionado:{mentioned}")
            else:
                print(f"  ❌ {check_date}: SIN DATOS")
        
        # 5. Verificar snapshots
        print_section("5. SNAPSHOTS DIARIOS")
        
        cur.execute("""
            SELECT snapshot_date, COUNT(*) as count
            FROM manual_ai_snapshots
            WHERE snapshot_date >= %s
            GROUP BY snapshot_date
            ORDER BY snapshot_date DESC
        """, (week_ago,))
        
        snapshots = cur.fetchall()
        
        if snapshots:
            print(f"\nSnapshots encontrados:")
            for row in snapshots:
                print(f"  📸 {row[0]}: {row[1]} snapshots")
        else:
            print(f"  ⚠️  NO HAY SNAPSHOTS desde {week_ago}")
        
        # 6. Verificar proyecto Láserum específicamente
        print_section("6. PROYECTO LÁSERUM - ANÁLISIS ESPECÍFICO")
        
        cur.execute("""
            SELECT id, name, domain 
            FROM manual_ai_projects 
            WHERE domain ILIKE '%laserum%'
            LIMIT 1
        """)
        
        laserum = cur.fetchone()
        
        if laserum:
            laserum_id = laserum[0]
            print(f"  ✅ Proyecto encontrado: ID {laserum_id} - {laserum[1]} ({laserum[2]})")
            
            # Keywords del proyecto
            cur.execute("""
                SELECT keyword, is_active
                FROM manual_ai_keywords
                WHERE project_id = %s
            """, (laserum_id,))
            
            keywords = cur.fetchall()
            print(f"\n  Keywords ({len(keywords)} total):")
            for kw in keywords:
                status = "✅" if kw[1] else "❌"
                print(f"    {status} '{kw[0]}'")
            
            # Resultados recientes
            cur.execute("""
                SELECT analysis_date, keyword, has_ai_overview, domain_mentioned, domain_position
                FROM manual_ai_results
                WHERE project_id = %s
                ORDER BY analysis_date DESC, keyword
                LIMIT 10
            """, (laserum_id,))
            
            results = cur.fetchall()
            
            if results:
                print(f"\n  Resultados recientes:")
                for r in results:
                    ai = "AI:✅" if r[2] else "AI:❌"
                    mentioned = "Mencionado:✅" if r[3] else "Mencionado:❌"
                    pos = f"Pos:{r[4]}" if r[4] else "Pos:-"
                    print(f"    {r[0]} | '{r[1]}' | {ai} | {mentioned} | {pos}")
            else:
                print(f"  ⚠️  NO HAY RESULTADOS para Láserum")
        else:
            print("  ❌ Proyecto Láserum NO ENCONTRADO")
        
        # 7. Verificar usuarios y quotas
        print_section("7. USUARIOS Y QUOTAS")
        
        cur.execute("""
            SELECT id, email, role, quota_limit, quota_used, is_active
            FROM users
            WHERE is_active = true
            ORDER BY id DESC
            LIMIT 5
        """)
        
        users = cur.fetchall()
        
        if users:
            print(f"Usuarios activos ({len(users)} mostrados):")
            for u in users:
                quota_pct = (u[4] / u[3] * 100) if u[3] > 0 else 0
                print(f"  ID:{u[0]} | {u[1]} | {u[2]} | Quota: {u[4]}/{u[3]} ({quota_pct:.1f}%)")
        else:
            print("  ⚠️  No hay usuarios activos")
        
        # 8. Verificar logs de cron (si existe tabla)
        print_section("8. LOGS DE CRON (si disponible)")
        
        try:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%cron%'
            """)
            
            cron_tables = cur.fetchall()
            
            if cron_tables:
                print(f"  Tablas de cron encontradas: {[t[0] for t in cron_tables]}")
            else:
                print("  ℹ️  No hay tablas específicas de cron")
        except Exception as e:
            print(f"  ℹ️  No se pudo verificar: {e}")
        
        # 9. Verificar análisis de AI Mode Projects (otro módulo)
        print_section("9. AI MODE PROJECTS (otro módulo)")
        
        try:
            cur.execute("""
                SELECT COUNT(*) 
                FROM ai_mode_projects 
                WHERE is_active = true
            """)
            
            ai_projects = cur.fetchone()[0]
            print(f"  Proyectos AI Mode activos: {ai_projects}")
            
            cur.execute("""
                SELECT analysis_date, COUNT(*) 
                FROM ai_mode_snapshots
                WHERE analysis_date >= %s
                GROUP BY analysis_date
                ORDER BY analysis_date DESC
            """, (week_ago,))
            
            ai_snapshots = cur.fetchall()
            
            if ai_snapshots:
                print(f"\n  Snapshots AI Mode:")
                for row in ai_snapshots:
                    print(f"    📸 {row[0]}: {row[1]} snapshots")
            else:
                print(f"  ⚠️  NO HAY SNAPSHOTS de AI Mode desde {week_ago}")
                
        except Exception as e:
            print(f"  ℹ️  Módulo AI Mode no verificable: {e}")
        
        # 10. Resumen y diagnóstico
        print_section("10. DIAGNÓSTICO Y RECOMENDACIONES")
        
        issues = []
        
        # Check 1: Datos recientes
        if not results_by_date or len(results_by_date) == 0:
            issues.append("❌ NO HAY ANÁLISIS RECIENTES - El cron no está guardando datos")
        
        # Check 2: Datos 21-22 octubre
        dates_to_check = [date(2025, 10, 21), date(2025, 10, 22)]
        for d in dates_to_check:
            cur.execute("SELECT COUNT(*) FROM manual_ai_results WHERE analysis_date = %s", (d,))
            if cur.fetchone()[0] == 0:
                issues.append(f"❌ SIN DATOS del {d} - Cron ejecutó pero no guardó")
        
        # Check 3: Proyecto Láserum
        if laserum and not results:
            issues.append("❌ Proyecto Láserum existe pero SIN RESULTADOS recientes")
        
        if issues:
            print("\n🚨 PROBLEMAS DETECTADOS:")
            for issue in issues:
                print(f"  {issue}")
            
            print("\n💡 RECOMENDACIONES:")
            print("  1. Verificar endpoint del cron: /manual-ai/api/cron/daily-analysis")
            print("  2. Revisar logs de la aplicación para ver errores")
            print("  3. Verificar quotas de usuarios (puede estar bloqueando análisis)")
            print("  4. Ejecutar análisis manual para verificar que funciona")
            print("  5. Re-analizar proyecto Láserum con código mejorado")
        else:
            print("\n✅ Sistema operando normalmente")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("✅ Auditoría completada")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR durante la auditoría: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    try:
        audit_database()
    except KeyboardInterrupt:
        print("\n\n⚠️  Auditoría cancelada por usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        sys.exit(1)






