"""
Script para agregar la columna selected_competitors a la tabla ai_mode_projects
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_selected_competitors_column():
    """Agregar columna selected_competitors a ai_mode_projects"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Verificar si la columna ya existe
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ai_mode_projects' 
            AND column_name = 'selected_competitors'
        """)
        
        if cur.fetchone():
            logger.info("✅ La columna 'selected_competitors' ya existe en ai_mode_projects")
            return True
        
        # Agregar la columna
        logger.info("🔧 Agregando columna 'selected_competitors' a ai_mode_projects...")
        cur.execute("""
            ALTER TABLE ai_mode_projects
            ADD COLUMN IF NOT EXISTS selected_competitors JSONB DEFAULT '[]'::jsonb
        """)
        
        conn.commit()
        logger.info("✅ Columna 'selected_competitors' agregada exitosamente")
        
        # Verificar que se agregó correctamente
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = 'ai_mode_projects' 
            AND column_name = 'selected_competitors'
        """)
        
        result = cur.fetchone()
        if result:
            logger.info(f"✅ Verificación: {result['column_name']} ({result['data_type']}) - Default: {result['column_default']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error agregando columna selected_competitors: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    logger.info("🚀 Iniciando migración: agregar selected_competitors a ai_mode_projects")
    
    if add_selected_competitors_column():
        logger.info("✅ Migración completada exitosamente")
    else:
        logger.error("❌ Migración falló")

