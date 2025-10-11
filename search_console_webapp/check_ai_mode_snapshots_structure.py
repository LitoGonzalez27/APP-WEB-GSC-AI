"""
Script para verificar la estructura de ai_mode_snapshots
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway"

def check_table_structure():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    logger.info("=" * 80)
    logger.info("VERIFICANDO ESTRUCTURA DE ai_mode_snapshots")
    logger.info("=" * 80)
    
    # Verificar columnas de la tabla
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'ai_mode_snapshots'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    
    if columns:
        logger.info("\n📋 Columnas en ai_mode_snapshots:")
        for col in columns:
            logger.info(f"   • {col['column_name']} ({col['data_type']}) - Nullable: {col['is_nullable']}")
    else:
        logger.error("❌ Tabla ai_mode_snapshots no existe o no tiene columnas")
    
    # Comparar con manual_ai_snapshots
    logger.info("\n📋 Columnas en manual_ai_snapshots (para comparar):")
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'manual_ai_snapshots'
        ORDER BY ordinal_position
    """)
    
    manual_columns = cur.fetchall()
    for col in manual_columns:
        logger.info(f"   • {col['column_name']} ({col['data_type']})")
    
    logger.info("\n" + "=" * 80)
    logger.info("ANÁLISIS COMPLETADO")
    logger.info("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_table_structure()

