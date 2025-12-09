#!/usr/bin/env python3
"""
Migración: Añadir columnas de Share of Voice ponderado

Añade las siguientes columnas a llm_monitoring_snapshots:
- weighted_share_of_voice: DECIMAL(5,2) - Porcentaje de SoV ponderado por posición
- weighted_competitor_breakdown: JSONB - Menciones ponderadas por competidor
"""

import logging
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate():
    """Añade columnas de weighted SoV a la tabla de snapshots"""
    logger.info("\n" + "="*70)
    logger.info("🔧 MIGRACIÓN: Añadir columnas de Weighted Share of Voice")
    logger.info("="*70 + "\n")
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar si las columnas ya existen
        logger.info("1️⃣ Verificando columnas existentes...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_snapshots'
                AND column_name IN ('weighted_share_of_voice', 'weighted_competitor_breakdown')
        """)
        
        existing_columns = [row['column_name'] for row in cur.fetchall()]
        logger.info(f"   Columnas ya existentes: {existing_columns}")
        
        # Añadir weighted_share_of_voice si no existe
        if 'weighted_share_of_voice' not in existing_columns:
            logger.info("\n2️⃣ Añadiendo columna 'weighted_share_of_voice'...")
            cur.execute("""
                ALTER TABLE llm_monitoring_snapshots
                ADD COLUMN weighted_share_of_voice DECIMAL(5,2) DEFAULT NULL
            """)
            logger.info("   ✅ Columna 'weighted_share_of_voice' añadida")
        else:
            logger.info("\n2️⃣ ⏭️ Columna 'weighted_share_of_voice' ya existe")
        
        # Añadir weighted_competitor_breakdown si no existe
        if 'weighted_competitor_breakdown' not in existing_columns:
            logger.info("\n3️⃣ Añadiendo columna 'weighted_competitor_breakdown'...")
            cur.execute("""
                ALTER TABLE llm_monitoring_snapshots
                ADD COLUMN weighted_competitor_breakdown JSONB DEFAULT NULL
            """)
            logger.info("   ✅ Columna 'weighted_competitor_breakdown' añadida")
        else:
            logger.info("\n3️⃣ ⏭️ Columna 'weighted_competitor_breakdown' ya existe")
        
        # Commit
        conn.commit()
        
        # Verificar estructura final
        logger.info("\n4️⃣ Verificando estructura final...")
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_snapshots'
                AND column_name IN ('weighted_share_of_voice', 'weighted_competitor_breakdown')
            ORDER BY column_name
        """)
        
        final_columns = cur.fetchall()
        logger.info("\n   📋 Columnas de Weighted SoV:")
        for col in final_columns:
            logger.info(f"      {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
        
        logger.info("\n" + "="*70)
        logger.info("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("="*70)
        logger.info("""
📝 PRÓXIMOS PASOS:

1. Los análisis futuros calcularán automáticamente el Weighted SoV
2. Los snapshots existentes tendrán NULL en estas columnas
3. El frontend mostrará SoV normal como fallback cuando weighted sea NULL
4. Ejecuta un análisis manual para un proyecto y verifica los nuevos campos

🔄 Para repoblar snapshots antiguos con datos ponderados:
   - Necesitarías ejecutar un script de backfill (opcional)
   - O simplemente espera a que se ejecute el análisis diario automático
""")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error en migración: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    import sys
    success = migrate()
    sys.exit(0 if success else 1)




