#!/usr/bin/env python3
"""
Script para crear tabla de detección global de dominios en AI Overview
SEGURO: Solo crea tabla nueva si no existe
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_global_domains_table():
    """Crear tabla para almacenar todos los dominios detectados en AI Overview"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("🚀 Creando tabla para detección global de dominios...")
        
        # Tabla para almacenar TODOS los dominios encontrados en AI Overview
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual_ai_global_domains (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES manual_ai_projects(id) ON DELETE CASCADE,
                keyword_id INTEGER REFERENCES manual_ai_keywords(id) ON DELETE CASCADE,
                analysis_date DATE NOT NULL,
                
                -- Información de la keyword y proyecto (denormalizado para queries rápidas)
                keyword VARCHAR(500) NOT NULL,
                project_domain VARCHAR(255) NOT NULL,
                
                -- Información del dominio detectado
                detected_domain VARCHAR(255) NOT NULL,
                domain_position INTEGER NOT NULL,
                domain_title TEXT,
                domain_source_url TEXT,
                
                -- Metadata del análisis
                country_code VARCHAR(3) DEFAULT 'US',
                is_project_domain BOOLEAN DEFAULT FALSE,
                is_selected_competitor BOOLEAN DEFAULT FALSE,
                
                -- Timestamp
                created_at TIMESTAMP DEFAULT NOW(),
                
                -- Constraints
                UNIQUE(project_id, keyword_id, analysis_date, detected_domain),
                CHECK (domain_position > 0),
                CHECK (char_length(detected_domain) >= 3)
            )
        """)
        logger.info("✅ Tabla manual_ai_global_domains creada")
        
        # Índices para búsquedas rápidas
        try:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_global_domains_project_date 
                ON manual_ai_global_domains (project_id, analysis_date)
            """)
            logger.info("✅ Índice idx_global_domains_project_date creado")
        except Exception as e:
            logger.warning(f"⚠️ Error creando índice: {e}")
        
        try:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_global_domains_domain 
                ON manual_ai_global_domains (detected_domain)
            """)
            logger.info("✅ Índice idx_global_domains_domain creado")
        except Exception as e:
            logger.warning(f"⚠️ Error creando índice: {e}")
        
        try:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_global_domains_competitor_flag 
                ON manual_ai_global_domains (project_id, is_selected_competitor, analysis_date)
            """)
            logger.info("✅ Índice idx_global_domains_competitor_flag creado")
        except Exception as e:
            logger.warning(f"⚠️ Error creando índice: {e}")
        
        # Verificar la estructura
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'manual_ai_global_domains'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        logger.info("✅ Estructura de tabla manual_ai_global_domains:")
        for col in columns:
            logger.info(f"   - {col['column_name']} ({col['data_type']})")
        
        conn.commit()
        logger.info("🎉 Tabla de dominios globales creada exitosamente")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creando tabla: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    success = create_global_domains_table()
    if success:
        print("✅ Tabla de dominios globales creada exitosamente")
        sys.exit(0)
    else:
        print("❌ Error creando tabla de dominios globales")
        sys.exit(1)