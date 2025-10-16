#!/usr/bin/env python3
"""
Script para agregar columna topic_clusters a ai_mode_projects
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_topic_clusters_column():
    """Agregar columna topic_clusters a ai_mode_projects"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar si la columna ya existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'ai_mode_projects' 
                AND column_name = 'topic_clusters'
            );
        """)
        
        result = cur.fetchone()
        exists = result['exists'] if result else False
        
        if exists:
            logger.info("✅ Columna 'topic_clusters' ya existe")
            return True
        
        logger.info("🚀 Agregando columna 'topic_clusters' a ai_mode_projects...")
        
        # Agregar la columna
        cur.execute("""
            ALTER TABLE ai_mode_projects 
            ADD COLUMN topic_clusters JSONB DEFAULT NULL;
        """)
        
        logger.info("✅ Columna 'topic_clusters' agregada exitosamente")
        
        # Crear índice para búsquedas rápidas
        try:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_mode_projects_topic_clusters 
                ON ai_mode_projects USING GIN (topic_clusters);
            """)
            logger.info("✅ Índice GIN creado para topic_clusters")
        except Exception as e:
            logger.warning(f"⚠️  Error creando índice (puede ser opcional): {e}")
        
        conn.commit()
        logger.info("🎉 Migración completada exitosamente")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en la migración: {e}")
        import traceback
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🔧 MIGRACIÓN: Agregar columna topic_clusters a ai_mode_projects")
    print("="*80 + "\n")
    
    success = add_topic_clusters_column()
    
    if success:
        print("\n✅ Migración completada exitosamente")
        print("🎯 Ahora puedes crear clusters en AI Mode")
        sys.exit(0)
    else:
        print("\n❌ Error en la migración")
        sys.exit(1)

