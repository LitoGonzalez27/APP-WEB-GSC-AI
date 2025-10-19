#!/usr/bin/env python3
"""
Agregar columnas faltantes a ai_mode_projects en producción
"""
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PRODUCTION_URL = "postgresql://postgres:HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS@switchyard.proxy.rlwy.net:18167/railway"

def add_missing_columns():
    """Agregar columnas topic_clusters y selected_competitors a ai_mode_projects"""
    
    logger.info("🔌 Conectando a PRODUCCIÓN...")
    try:
        conn = psycopg2.connect(PRODUCTION_URL)
        logger.info("✅ Conectado a PRODUCCIÓN")
    except Exception as e:
        logger.error(f"❌ Error conectando: {e}")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("\n🔧 Agregando columnas faltantes a ai_mode_projects...")
        
        # Agregar topic_clusters
        logger.info("   📝 Agregando columna topic_clusters...")
        cur.execute("""
            ALTER TABLE ai_mode_projects 
            ADD COLUMN IF NOT EXISTS topic_clusters JSONB
        """)
        logger.info("   ✅ Columna topic_clusters agregada")
        
        # Agregar selected_competitors
        logger.info("   📝 Agregando columna selected_competitors...")
        cur.execute("""
            ALTER TABLE ai_mode_projects 
            ADD COLUMN IF NOT EXISTS selected_competitors JSONB
        """)
        logger.info("   ✅ Columna selected_competitors agregada")
        
        conn.commit()
        
        # Verificar
        logger.info("\n🔍 Verificando estructura actualizada...")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'ai_mode_projects'
            AND column_name IN ('topic_clusters', 'selected_competitors')
        """)
        
        columns = cur.fetchall()
        logger.info(f"\n📋 Columnas verificadas:")
        for col in columns:
            logger.info(f"   ✅ {col[0]} ({col[1]})")
        
        logger.info("\n🎉 Columnas agregadas exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def main():
    logger.info("=" * 80)
    logger.info("🔧 AGREGAR COLUMNAS FALTANTES - AI MODE PRODUCTION")
    logger.info("=" * 80)
    
    success = add_missing_columns()
    
    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ ÉXITO: Estructura completamente sincronizada")
    else:
        logger.error("❌ FALLO: Revisar logs")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()

