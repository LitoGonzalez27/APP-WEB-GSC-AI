"""
Migración: Añadir campo sources a llm_monitoring_results
Para almacenar URLs/fuentes citadas por cada LLM
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def migrate():
    """Añade campo sources para almacenar fuentes/URLs citadas"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("=" * 70)
        logger.info("🔧 MIGRACIÓN: Añadir campo sources a llm_monitoring_results")
        logger.info("=" * 70)
        
        # Verificar si el campo ya existe
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_results' 
                AND column_name = 'sources'
        """)
        
        if cur.fetchone():
            logger.info("ℹ️  El campo 'sources' ya existe, no es necesario migrarlo")
            return True
        
        # Añadir campo sources (JSONB array de objetos)
        logger.info("📝 Añadiendo campo 'sources'...")
        cur.execute("""
            ALTER TABLE llm_monitoring_results 
            ADD COLUMN sources JSONB DEFAULT '[]'::jsonb
        """)
        
        conn.commit()
        logger.info("✅ Campo 'sources' añadido exitosamente")
        
        # Verificar
        cur.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_results' 
                AND column_name = 'sources'
        """)
        
        result = cur.fetchone()
        logger.info(f"✅ Verificación:")
        logger.info(f"   - Campo: {result['column_name']}")
        logger.info(f"   - Tipo: {result['data_type']}")
        logger.info(f"   - Default: {result['column_default']}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ MIGRACIÓN COMPLETADA")
        logger.info("=" * 70)
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en migración: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False


if __name__ == '__main__':
    success = migrate()
    exit(0 if success else 1)

