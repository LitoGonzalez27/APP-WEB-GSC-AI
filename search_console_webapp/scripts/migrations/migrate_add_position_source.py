"""
Migración: Añadir campo position_source para diferenciar origen de posiciones

Añade campo position_source a:
- llm_monitoring_results: 'text', 'link', 'both'
- También mejora la lógica para asignar posición 15 cuando solo está en links
"""

import logging
from database import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def migrate():
    """
    Añade campo position_source a tablas de LLM Monitoring
    """
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("=" * 80)
        logger.info("🔄 MIGRACIÓN: Añadir position_source a LLM Monitoring")
        logger.info("=" * 80)
        logger.info("")
        
        # 1. Añadir columna a llm_monitoring_results
        logger.info("📊 [1/2] Añadiendo position_source a llm_monitoring_results...")
        
        cur.execute("""
            ALTER TABLE llm_monitoring_results
            ADD COLUMN IF NOT EXISTS position_source VARCHAR(10) DEFAULT NULL;
        """)
        
        cur.execute("""
            COMMENT ON COLUMN llm_monitoring_results.position_source IS 
            'Origen de la posición detectada: text (mención en texto), link (solo en URL), both (texto + URL)';
        """)
        
        logger.info("   ✅ Campo position_source añadido a llm_monitoring_results")
        
        # 2. Crear índice para búsquedas eficientes
        logger.info("📊 [2/2] Creando índice para position_source...")
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_results_position_source 
            ON llm_monitoring_results(position_source)
            WHERE position_source IS NOT NULL;
        """)
        
        logger.info("   ✅ Índice creado")
        logger.info("")
        
        # 3. Actualizar registros existentes con heurística
        logger.info("🔄 Actualizando registros existentes con heurística...")
        
        # Si tiene posición y fue mencionado, probablemente fue en texto
        cur.execute("""
            UPDATE llm_monitoring_results
            SET position_source = 'text'
            WHERE position_in_list IS NOT NULL
            AND brand_mentioned = TRUE
            AND position_source IS NULL;
        """)
        
        updated_text = cur.rowcount
        logger.info(f"   ✅ {updated_text} registros marcados como 'text'")
        
        # Si no tiene posición pero fue mencionado, probablemente solo en link
        cur.execute("""
            UPDATE llm_monitoring_results
            SET position_source = 'link',
                position_in_list = 15
            WHERE position_in_list IS NULL
            AND brand_mentioned = TRUE
            AND position_source IS NULL;
        """)
        
        updated_link = cur.rowcount
        logger.info(f"   ✅ {updated_link} registros marcados como 'link' (posición 15)")
        
        logger.info("")
        
        # Commit
        conn.commit()
        
        logger.info("=" * 80)
        logger.info("✅ MIGRACIÓN COMPLETADA")
        logger.info("=" * 80)
        logger.info("")
        logger.info("📋 Resumen:")
        logger.info(f"   • Campo position_source añadido")
        logger.info(f"   • {updated_text} registros marcados como 'text'")
        logger.info(f"   • {updated_link} registros marcados como 'link' (ahora tienen posición 15)")
        logger.info("")
        logger.info("🔄 Próximos pasos:")
        logger.info("   1. Los nuevos análisis usarán automáticamente position_source")
        logger.info("   2. Los snapshots se recalcularán con los nuevos datos")
        logger.info("   3. La UI mostrará badges 📝/🔗/📝🔗 según el source")
        logger.info("")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante la migración: {e}", exc_info=True)
        conn.rollback()
        if conn:
            conn.close()
        return False

if __name__ == '__main__':
    import sys
    
    logger.info("")
    logger.info("⚠️  Esta migración añadirá el campo position_source para diferenciar")
    logger.info("   si una posición proviene de texto, link o ambos.")
    logger.info("")
    
    response = input("¿Continuar? (yes/no): ")
    
    if response.lower() in ['yes', 'y', 'si', 's']:
        success = migrate()
        sys.exit(0 if success else 1)
    else:
        logger.info("❌ Migración cancelada")
        sys.exit(1)

