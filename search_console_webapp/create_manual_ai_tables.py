#!/usr/bin/env python3
"""
Script para crear las tablas del sistema Manual AI Analysis
SEGURO: Solo crea tablas nuevas, no modifica nada existente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_manual_ai_tables():
    """Crear todas las tablas necesarias para el sistema Manual AI Analysis"""
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        logger.info("🚀 Creando tablas para Manual AI Analysis...")
        
        # Tabla de proyectos manuales
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual_ai_projects (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                domain VARCHAR(255) NOT NULL,
                country_code VARCHAR(3) DEFAULT 'US',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                
                -- Constraints
                UNIQUE(user_id, name),
                CHECK (char_length(name) >= 1),
                CHECK (char_length(domain) >= 4)
            )
        """)
        logger.info("✅ Tabla manual_ai_projects creada")
        
        # Tabla de keywords por proyecto
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual_ai_keywords (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES manual_ai_projects(id) ON DELETE CASCADE,
                keyword VARCHAR(500) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                added_at TIMESTAMP DEFAULT NOW(),
                
                -- Constraints
                UNIQUE(project_id, keyword),
                CHECK (char_length(keyword) >= 1)
            )
        """)
        logger.info("✅ Tabla manual_ai_keywords creada")
        
        # Tabla de resultados de análisis
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual_ai_results (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES manual_ai_projects(id) ON DELETE CASCADE,
                keyword_id INTEGER REFERENCES manual_ai_keywords(id) ON DELETE CASCADE,
                analysis_date DATE NOT NULL,
                keyword VARCHAR(500) NOT NULL, -- Denormalizado para queries rápidas
                domain VARCHAR(255) NOT NULL,  -- Denormalizado para queries rápidas
                
                -- Resultados AI Overview
                has_ai_overview BOOLEAN DEFAULT FALSE,
                domain_mentioned BOOLEAN DEFAULT FALSE,
                domain_position INTEGER,
                ai_elements_count INTEGER DEFAULT 0,
                impact_score INTEGER DEFAULT 0,
                
                -- Raw data para debugging
                raw_serp_data JSONB,
                ai_analysis_data JSONB,
                
                -- Metadata
                country_code VARCHAR(3) DEFAULT 'US',
                created_at TIMESTAMP DEFAULT NOW(),
                
                -- Constraints
                UNIQUE(project_id, keyword_id, analysis_date),
                CHECK (ai_elements_count >= 0),
                CHECK (impact_score >= 0)
            )
        """)
        logger.info("✅ Tabla manual_ai_results creada")
        
        # Tabla de snapshots para tracking de cambios
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual_ai_snapshots (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES manual_ai_projects(id) ON DELETE CASCADE,
                snapshot_date DATE NOT NULL,
                
                -- Métricas del snapshot
                total_keywords INTEGER NOT NULL,
                active_keywords INTEGER NOT NULL,
                keywords_with_ai INTEGER DEFAULT 0,
                domain_mentions INTEGER DEFAULT 0,
                avg_position DECIMAL(5,2),
                visibility_percentage DECIMAL(5,2),
                
                -- Metadata del cambio
                change_type VARCHAR(50), -- 'daily_analysis', 'keywords_added', 'keywords_removed'
                change_description TEXT,
                keywords_added INTEGER DEFAULT 0,
                keywords_removed INTEGER DEFAULT 0,
                
                created_at TIMESTAMP DEFAULT NOW(),
                
                -- Constraints
                UNIQUE(project_id, snapshot_date),
                CHECK (total_keywords >= 0),
                CHECK (active_keywords >= 0),
                CHECK (keywords_with_ai >= 0)
            )
        """)
        logger.info("✅ Tabla manual_ai_snapshots creada")
        
        # Tabla de eventos para anotaciones
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual_ai_events (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES manual_ai_projects(id) ON DELETE CASCADE,
                event_date DATE NOT NULL,
                event_type VARCHAR(50) NOT NULL, -- 'keywords_added', 'keywords_removed', 'analysis_completed'
                event_title VARCHAR(255) NOT NULL,
                event_description TEXT,
                
                -- Metadata del evento
                keywords_affected INTEGER DEFAULT 0,
                user_id INTEGER REFERENCES users(id),
                
                created_at TIMESTAMP DEFAULT NOW(),
                
                -- Constraints
                CHECK (char_length(event_title) >= 1)
            )
        """)
        logger.info("✅ Tabla manual_ai_events creada")
        
        # Crear índices para optimización
        logger.info("🔧 Creando índices para optimización...")
        
        # Índices para manual_ai_projects
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_projects_user ON manual_ai_projects(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_projects_active ON manual_ai_projects(is_active)")
        
        # Índices para manual_ai_keywords  
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_keywords_project ON manual_ai_keywords(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_keywords_active ON manual_ai_keywords(is_active)")
        
        # Índices para manual_ai_results
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_results_project_date ON manual_ai_results(project_id, analysis_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_results_date ON manual_ai_results(analysis_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_results_ai_overview ON manual_ai_results(has_ai_overview)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_results_domain_mentioned ON manual_ai_results(domain_mentioned)")
        
        # Índices para manual_ai_snapshots
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_snapshots_project_date ON manual_ai_snapshots(project_id, snapshot_date)")
        
        # Índices para manual_ai_events
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_events_project_date ON manual_ai_events(project_id, event_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_events_type ON manual_ai_events(event_type)")
        
        logger.info("✅ Índices creados")
        
        # Commit todas las operaciones
        conn.commit()
        
        logger.info("🎉 Todas las tablas del sistema Manual AI Analysis creadas exitosamente")
        
        # Verificar que las tablas existen
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'manual_ai_%'
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        logger.info(f"📋 Tablas creadas: {[table['table_name'] for table in tables]}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creando tablas: {e}")
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()

def main():
    """Función principal"""
    logger.info("=" * 60)
    logger.info("🤖 CREACIÓN DE TABLAS - MANUAL AI ANALYSIS SYSTEM")
    logger.info("=" * 60)
    
    success = create_manual_ai_tables()
    
    if success:
        logger.info("🎯 SISTEMA LISTO: Las tablas han sido creadas correctamente")
        logger.info("✅ Puedes proceder con la implementación del sistema")
    else:
        logger.error("❌ FALLO: No se pudieron crear las tablas")
        logger.error("🔍 Revisa los logs arriba para ver el error específico")

if __name__ == "__main__":
    main()