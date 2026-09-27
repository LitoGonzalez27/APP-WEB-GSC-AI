#!/usr/bin/env python3
"""
Script para verificar si las tablas de LLM Monitoring existen en la base de datos
"""

import sys
from database import get_db_connection

def check_llm_tables():
    """
    Verifica si las tablas del sistema LLM Monitoring existen
    """
    print("\n" + "="*70)
    print("🔍 VERIFICANDO TABLAS DE LLM MONITORING")
    print("="*70 + "\n")
    
    # Tablas que deberían existir
    required_tables = [
        'llm_monitoring_projects',
        'llm_monitoring_queries',
        'llm_monitoring_results',
        'llm_monitoring_snapshots',
        'llm_model_registry'
    ]
    
    conn = get_db_connection()
    if not conn:
        print("❌ Error: No se pudo conectar a la base de datos")
        sys.exit(1)
    
    try:
        cur = conn.cursor()
        
        print("📊 Verificando tablas existentes...\n")
        
        missing_tables = []
        existing_tables = []
        
        for table_name in required_tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table_name,))
            
            exists = cur.fetchone()['exists']
            
            if exists:
                print(f"  ✅ {table_name}")
                existing_tables.append(table_name)
            else:
                print(f"  ❌ {table_name} - NO EXISTE")
                missing_tables.append(table_name)
        
        print("\n" + "="*70)
        print("📈 RESUMEN")
        print("="*70)
        print(f"  Tablas existentes:  {len(existing_tables)}/{len(required_tables)}")
        print(f"  Tablas faltantes:   {len(missing_tables)}/{len(required_tables)}")
        
        if missing_tables:
            print("\n" + "="*70)
            print("❌ PROBLEMA DETECTADO")
            print("="*70)
            print("\n  Las siguientes tablas NO existen:")
            for table in missing_tables:
                print(f"    • {table}")
            
            print("\n  📝 SOLUCIÓN:")
            print("  Ejecuta el script de creación de tablas:")
            print("\n    python3 -m scripts.migrations.create_llm_monitoring_tables\n")
            
            sys.exit(1)
        else:
            print("\n✅ Todas las tablas existen correctamente")
            
            # Verificar si hay modelos LLM registrados
            print("\n" + "="*70)
            print("🤖 VERIFICANDO MODELOS LLM")
            print("="*70 + "\n")
            
            cur.execute("SELECT COUNT(*) as count FROM llm_model_registry")
            model_count = cur.fetchone()['count']
            
            if model_count == 0:
                print("  ⚠️  No hay modelos LLM registrados")
                print("\n  📝 SOLUCIÓN:")
                print("  Ejecuta el script de creación de tablas:")
                print("\n    python3 -m scripts.migrations.create_llm_monitoring_tables\n")
                sys.exit(1)
            else:
                print(f"  ✅ {model_count} modelos LLM registrados")
                
                # Mostrar modelos
                cur.execute("""
                    SELECT llm_provider, model_id, is_current
                    FROM llm_model_registry
                    ORDER BY llm_provider, model_id
                """)
                
                models = cur.fetchall()
                print("\n  Modelos disponibles:")
                for model in models:
                    status = "🟢 ACTIVO" if model['is_current'] else "⚪ Disponible"
                    print(f"    • {model['llm_provider']:12} | {model['model_id']:35} | {status}")
        
        print("\n" + "="*70)
        print("✅ SISTEMA LISTO PARA USAR")
        print("="*70 + "\n")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error verificando tablas: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    check_llm_tables()

