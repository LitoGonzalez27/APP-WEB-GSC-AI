#!/usr/bin/env python3
"""
Migración: Añadir campos de Share of Voice ponderado
=====================================================

Este script añade las siguientes columnas a llm_monitoring_snapshots:
- weighted_share_of_voice: DECIMAL(5,2) - Share of Voice ponderado por posición
- weighted_competitor_breakdown: JSONB - Desglose de menciones ponderadas por competidor

CONTEXTO:
Las menciones en posiciones top (1-3) ahora valen más que las menciones en 
posiciones bajas (>10), para reflejar mejor la visibilidad real.

PONDERACIÓN:
- Top 3: peso 2.0 (cuenta doble)
- Top 5: peso 1.5 
- Top 10: peso 1.2
- Posición > 10: peso 0.8
- Sin posición: peso 1.0

Ejecutar:
    python3 migrate_add_weighted_sov.py
"""

import sys
import logging
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_migration():
    """Ejecuta la migración de base de datos"""
    
    logger.info("=" * 70)
    logger.info("🚀 MIGRACIÓN: Añadir campos de Share of Voice ponderado")
    logger.info("=" * 70)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Verificar si las columnas ya existen
        logger.info("\n📋 Verificando columnas existentes...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_snapshots'
            AND column_name IN ('weighted_share_of_voice', 'weighted_competitor_breakdown')
        """)
        
        existing_columns = [row[0] for row in cur.fetchall()]
        
        if 'weighted_share_of_voice' in existing_columns and 'weighted_competitor_breakdown' in existing_columns:
            logger.warning("⚠️  Las columnas ya existen. Migración no necesaria.")
            return True
        
        # 2. Añadir columna weighted_share_of_voice
        if 'weighted_share_of_voice' not in existing_columns:
            logger.info("\n➕ Añadiendo columna 'weighted_share_of_voice'...")
            cur.execute("""
                ALTER TABLE llm_monitoring_snapshots
                ADD COLUMN IF NOT EXISTS weighted_share_of_voice DECIMAL(5,2) DEFAULT 0.0
            """)
            logger.info("   ✅ Columna 'weighted_share_of_voice' añadida")
        else:
            logger.info("   ℹ️  Columna 'weighted_share_of_voice' ya existe")
        
        # 3. Añadir columna weighted_competitor_breakdown
        if 'weighted_competitor_breakdown' not in existing_columns:
            logger.info("\n➕ Añadiendo columna 'weighted_competitor_breakdown'...")
            cur.execute("""
                ALTER TABLE llm_monitoring_snapshots
                ADD COLUMN IF NOT EXISTS weighted_competitor_breakdown JSONB DEFAULT '{}'::jsonb
            """)
            logger.info("   ✅ Columna 'weighted_competitor_breakdown' añadida")
        else:
            logger.info("   ℹ️  Columna 'weighted_competitor_breakdown' ya existe")
        
        # 4. Añadir índice para consultas rápidas
        logger.info("\n📊 Creando índices para optimizar consultas...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_weighted_sov 
            ON llm_monitoring_snapshots(project_id, weighted_share_of_voice DESC)
        """)
        logger.info("   ✅ Índice creado")
        
        # 5. Actualizar snapshots existentes con valor inicial
        logger.info("\n🔄 Inicializando valores para snapshots existentes...")
        cur.execute("""
            UPDATE llm_monitoring_snapshots
            SET 
                weighted_share_of_voice = share_of_voice,
                weighted_competitor_breakdown = competitor_breakdown
            WHERE weighted_share_of_voice IS NULL OR weighted_share_of_voice = 0
        """)
        
        updated_rows = cur.rowcount
        logger.info(f"   ✅ {updated_rows} snapshots actualizados con valores iniciales")
        logger.info("   ℹ️  Nota: Los valores ponderados reales se calcularán en el próximo análisis")
        
        # 6. Verificar estructura final
        logger.info("\n✅ Verificando estructura final...")
        cur.execute("""
            SELECT 
                column_name, 
                data_type, 
                column_default,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'llm_monitoring_snapshots'
            AND column_name IN ('weighted_share_of_voice', 'weighted_competitor_breakdown')
            ORDER BY column_name
        """)
        
        columns = cur.fetchall()
        logger.info("\n📋 Columnas añadidas:")
        for col in columns:
            logger.info(f"   • {col[0]}: {col[1]} (default: {col[2]}, nullable: {col[3]})")
        
        # Commit
        conn.commit()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 70)
        logger.info("\n📝 PRÓXIMOS PASOS:")
        logger.info("   1. Ejecuta un nuevo análisis para calcular valores ponderados reales")
        logger.info("   2. Los valores aparecerán en el dashboard automáticamente")
        logger.info("   3. Share of Voice ponderado refleja mejor la visibilidad real")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ ERROR durante la migración: {e}", exc_info=True)
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)




