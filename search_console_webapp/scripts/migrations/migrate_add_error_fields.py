"""
Migración: Agregar campos de error a llm_monitoring_results

Permite almacenar información de errores cuando un LLM falla al responder
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """
    Agregar campos has_error y error_message a llm_monitoring_results
    """
    print("\n" + "="*80)
    print("🔧 MIGRACIÓN: Agregar campos de error a llm_monitoring_results")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar si los campos ya existen
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_results' 
            AND column_name IN ('has_error', 'error_message')
        """)
        
        existing_columns = {row['column_name'] for row in cur.fetchall()}
        
        if 'has_error' in existing_columns and 'error_message' in existing_columns:
            print("\n✅ Los campos ya existen, no es necesario migrar")
            return True
        
        print("\n📝 Agregando campos...")
        
        # Agregar campo has_error si no existe
        if 'has_error' not in existing_columns:
            print("  • Agregando campo has_error...")
            cur.execute("""
                ALTER TABLE llm_monitoring_results
                ADD COLUMN IF NOT EXISTS has_error BOOLEAN DEFAULT FALSE
            """)
            print("    ✅ Campo has_error agregado")
        
        # Agregar campo error_message si no existe
        if 'error_message' not in existing_columns:
            print("  • Agregando campo error_message...")
            cur.execute("""
                ALTER TABLE llm_monitoring_results
                ADD COLUMN IF NOT EXISTS error_message TEXT
            """)
            print("    ✅ Campo error_message agregado")
        
        # Crear índice para consultas de errores
        print("  • Creando índice para has_error...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_results_has_error 
            ON llm_monitoring_results(has_error) 
            WHERE has_error = TRUE
        """)
        print("    ✅ Índice creado")
        
        conn.commit()
        
        print("\n✅ Migración completada exitosamente")
        print("\nAhora el sistema puede:")
        print("  • Guardar información de errores cuando un LLM falla")
        print("  • Diferenciar entre 'no mencionado' y 'error al consultar'")
        print("  • Mostrar errores específicos en el frontend")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import sys
    success = migrate()
    sys.exit(0 if success else 1)

