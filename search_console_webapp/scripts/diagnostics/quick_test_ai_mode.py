#!/usr/bin/env python3
"""
🚀 QUICK TEST - AI Mode Monitoring System
Script rápido para verificar que todo está listo antes de testing manual
"""

import sys
import os

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_check(passed, message):
    icon = "✅" if passed else "❌"
    print(f"{icon} {message}")

def main():
    print_header("🧪 VERIFICACIÓN RÁPIDA - AI MODE SYSTEM")
    
    all_checks_passed = True
    
    # 1. Verificar archivos clave existen
    print("\n📁 Verificando archivos creados...")
    
    critical_files = [
        'create_ai_mode_tables.py',
        'ai_mode_system_bridge.py',
        'daily_ai_mode_cron.py',
        'test_ai_mode_system.py',
        'ai_mode_projects/__init__.py',
        'ai_mode_projects/config.py',
        'ai_mode_projects/services/analysis_service.py',
        'ai_mode_projects/routes/projects.py',
        'templates/ai_mode_dashboard.html'
    ]
    
    for file in critical_files:
        exists = os.path.exists(file)
        print_check(exists, f"Archivo: {file}")
        if not exists:
            all_checks_passed = False
    
    # 2. Verificar imports
    print("\n🔗 Verificando imports de Python...")
    
    try:
        from ai_mode_system_bridge import ai_mode_bp, USING_AI_MODE_SYSTEM
        print_check(True, f"Bridge importado (USING_AI_MODE_SYSTEM={USING_AI_MODE_SYSTEM})")
    except Exception as e:
        print_check(False, f"Error importando bridge: {e}")
        all_checks_passed = False
    
    try:
        from ai_mode_projects.config import AI_MODE_KEYWORD_ANALYSIS_COST
        print_check(True, f"Config importada (Cost: {AI_MODE_KEYWORD_ANALYSIS_COST} RU)")
    except Exception as e:
        print_check(False, f"Error importando config: {e}")
        all_checks_passed = False
    
    try:
        from ai_mode_projects.services.project_service import ProjectService
        service = ProjectService()
        print_check(True, "ProjectService instanciado")
    except Exception as e:
        print_check(False, f"Error con ProjectService: {e}")
        all_checks_passed = False
    
    # 3. Verificar base de datos
    print("\n🗄️  Verificando conexión a base de datos...")
    
    try:
        from database import get_db_connection
        conn = get_db_connection()
        if conn:
            print_check(True, "Conexión a BD establecida")
            
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'ai_mode_%'
            """)
            tables = cur.fetchall()
            
            expected_tables = ['ai_mode_projects', 'ai_mode_keywords', 'ai_mode_results', 
                              'ai_mode_snapshots', 'ai_mode_events']
            
            existing_tables = [t['table_name'] for t in tables]
            
            for table in expected_tables:
                exists = table in existing_tables
                print_check(exists, f"Tabla: {table}")
                if not exists:
                    all_checks_passed = False
                    print(f"      ⚠️  Ejecuta: python3 -m scripts.migrations.create_ai_mode_tables")
            
            cur.close()
            conn.close()
        else:
            print_check(False, "No se pudo conectar a BD")
            all_checks_passed = False
    except Exception as e:
        print_check(False, f"Error de BD: {e}")
        all_checks_passed = False
    
    # 4. Verificar variables de entorno
    print("\n🔑 Verificando variables de entorno...")
    
    serpapi_key = os.getenv('SERPAPI_API_KEY') or os.getenv('SERPAPI_KEY')
    print_check(bool(serpapi_key), f"SERPAPI_API_KEY configurada: {'Sí' if serpapi_key else 'No'}")
    if not serpapi_key:
        all_checks_passed = False
        print("      ⚠️  Configura SERPAPI_API_KEY en .env o Railway")
    
    # 5. Resumen final
    print_header("📊 RESUMEN FINAL")
    
    if all_checks_passed:
        print("\n🎉 ¡TODAS LAS VERIFICACIONES PASARON!")
        print("\n✅ El sistema AI Mode está listo para testing")
        print("\n🚀 PRÓXIMOS PASOS:")
        print("   1. python3 -m scripts.migrations.create_ai_mode_tables  (si no ejecutaste aún)")
        print("   2. python3 -m scripts.manual_checks.test_ai_mode_system    (tests completos)")
        print("   3. python3 app.py                    (iniciar aplicación)")
        print("   4. Abrir: http://localhost:5001/ai-mode-projects")
        print("\n📖 Ver documentación completa en: AI_MODE_IMPLEMENTATION_COMPLETE.md")
        return 0
    else:
        print("\n⚠️  ALGUNAS VERIFICACIONES FALLARON")
        print("\n❌ Revisa los errores arriba y corrígelos antes de continuar")
        print("\n📖 Consulta: AI_MODE_IMPLEMENTATION_COMPLETE.md")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n💥 Error crítico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

