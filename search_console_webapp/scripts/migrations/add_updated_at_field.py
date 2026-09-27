"""
Migración: Agregar campo updated_at a llm_monitoring_results
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """
    Agregar campo updated_at a llm_monitoring_results
    """
    print("\n🔧 Agregando campo updated_at a llm_monitoring_results...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar si el campo ya existe
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_results' 
            AND column_name = 'updated_at'
        """)
        
        if cur.fetchone():
            print("✅ El campo updated_at ya existe")
            return True
        
        # Agregar campo updated_at
        cur.execute("""
            ALTER TABLE llm_monitoring_results
            ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()
        """)
        
        conn.commit()
        
        print("✅ Campo updated_at agregado exitosamente")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False


if __name__ == '__main__':
    import sys
    success = migrate()
    sys.exit(0 if success else 1)

