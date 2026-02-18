#!/usr/bin/env python3
"""
Sistema Multi-LLM Brand Monitoring - Setup Base de Datos
Crear todas las tablas necesarias

IMPORTANTE: 
- Este script es idempotente (se puede ejecutar múltiples veces sin problemas)
- Usa CREATE TABLE IF NOT EXISTS
- No modifica datos existentes

Soporta: ChatGPT (GPT-5), Claude Sonnet 4.5, Gemini 3 Pro Preview, Perplexity
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_llm_monitoring_tables():
    """
    Crear todas las tablas necesarias para Multi-LLM Brand Monitoring
    
    Tablas que se crearán:
    1. llm_monitoring_projects - Proyectos de monitorización
    2. llm_monitoring_queries - Queries por proyecto
    3. llm_monitoring_results - Resultados por query y LLM
    4. llm_monitoring_snapshots - Métricas agregadas diarias
    5. user_llm_api_keys - API keys de usuario
    6. llm_model_registry - Registro de modelos y precios
    """
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos")
        logger.error("   Verifica DATABASE_URL en .env")
        return False
    
    try:
        cur = conn.cursor()
        logger.info("=" * 70)
        logger.info("🚀 CREANDO TABLAS PARA MULTI-LLM BRAND MONITORING")
        logger.info("=" * 70)
        logger.info("")
        
        # ===================================
        # TABLA 1: PROYECTOS
        # ===================================
        logger.info("📋 [1/6] Creando tabla: llm_monitoring_projects...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_monitoring_projects (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                brand_name VARCHAR(255) NOT NULL,
                industry VARCHAR(255) NOT NULL,
                
                -- LLMs habilitados para este proyecto
                -- Valores: 'openai', 'anthropic', 'google', 'perplexity'
                enabled_llms TEXT[] DEFAULT ARRAY['openai', 'anthropic', 'google', 'perplexity'],
                
                -- Competidores (JSON array)
                competitors JSONB DEFAULT '[]'::jsonb,
                
                -- Configuración
                language VARCHAR(10) DEFAULT 'es',
                queries_per_llm INTEGER DEFAULT 15,
                
                -- Estado
                is_active BOOLEAN DEFAULT TRUE,
                last_analysis_date TIMESTAMP,
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                
                -- Constraints
                UNIQUE(user_id, name),
                CHECK (char_length(brand_name) >= 2),
                CHECK (queries_per_llm BETWEEN 5 AND 60)
            )
        """)
        logger.info("   ✅ Tabla llm_monitoring_projects creada")
        
        # ===================================
        # TABLA 2: QUERIES
        # ===================================
        logger.info("📋 [2/6] Creando tabla: llm_monitoring_queries...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_monitoring_queries (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES llm_monitoring_projects(id) ON DELETE CASCADE,
                query_text TEXT NOT NULL,
                language VARCHAR(10) DEFAULT 'es',
                query_type VARCHAR(50) DEFAULT 'general',
                is_active BOOLEAN DEFAULT TRUE,
                added_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(project_id, query_text),
                CHECK (char_length(query_text) >= 1)
            )
        """)
        logger.info("   ✅ Tabla llm_monitoring_queries creada")
        
        # ===================================
        # TABLA 3: RESULTADOS
        # ===================================
        logger.info("📋 [3/6] Creando tabla: llm_monitoring_results...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_monitoring_results (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES llm_monitoring_projects(id) ON DELETE CASCADE,
                query_id INTEGER REFERENCES llm_monitoring_queries(id) ON DELETE CASCADE,
                analysis_date DATE NOT NULL,
                
                -- Identificación del LLM
                llm_provider VARCHAR(50) NOT NULL,
                model_used VARCHAR(100),
                
                -- Query y marca
                query_text TEXT NOT NULL,
                brand_name VARCHAR(255) NOT NULL,
                
                -- Resultados de mención
                brand_mentioned BOOLEAN DEFAULT FALSE,
                mention_count INTEGER DEFAULT 0,
                mention_contexts TEXT[] DEFAULT ARRAY[]::TEXT[],
                
                -- Posicionamiento
                appears_in_numbered_list BOOLEAN DEFAULT FALSE,
                position_in_list INTEGER,
                total_items_in_list INTEGER,
                
                -- Sentimiento
                sentiment VARCHAR(50),
                sentiment_score DECIMAL(3,2),
                
                -- Competidores
                competitors_mentioned JSONB DEFAULT '{}'::jsonb,
                
                -- Respuesta completa
                full_response TEXT,
                response_length INTEGER,
                
                -- Metadata de performance
                tokens_used INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost_usd DECIMAL(10,6),
                response_time_ms INTEGER,
                
                created_at TIMESTAMP DEFAULT NOW(),
                
                -- Un resultado por proyecto, query, LLM y fecha
                UNIQUE(project_id, query_id, llm_provider, analysis_date),
                
                CHECK (mention_count >= 0),
                CHECK (cost_usd >= 0)
            )
        """)
        logger.info("   ✅ Tabla llm_monitoring_results creada")
        
        # ===================================
        # TABLA 4: SNAPSHOTS (MÉTRICAS AGREGADAS)
        # ===================================
        logger.info("📋 [4/6] Creando tabla: llm_monitoring_snapshots...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_monitoring_snapshots (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES llm_monitoring_projects(id) ON DELETE CASCADE,
                snapshot_date DATE NOT NULL,
                llm_provider VARCHAR(50) NOT NULL,
                
                -- Métricas principales
                total_queries INTEGER NOT NULL,
                total_mentions INTEGER DEFAULT 0,
                mention_rate DECIMAL(5,2),
                
                -- Posicionamiento
                avg_position DECIMAL(5,2),
                appeared_in_top3 INTEGER DEFAULT 0,
                appeared_in_top5 INTEGER DEFAULT 0,
                appeared_in_top10 INTEGER DEFAULT 0,
                
                -- Share of Voice
                total_competitor_mentions INTEGER DEFAULT 0,
                share_of_voice DECIMAL(5,2),
                competitor_breakdown JSONB DEFAULT '{}'::jsonb,
                
                -- Sentimiento
                positive_mentions INTEGER DEFAULT 0,
                neutral_mentions INTEGER DEFAULT 0,
                negative_mentions INTEGER DEFAULT 0,
                avg_sentiment_score DECIMAL(3,2),
                
                -- Performance
                avg_response_time_ms INTEGER,
                total_cost_usd DECIMAL(10,4),
                total_tokens INTEGER,
                
                created_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(project_id, llm_provider, snapshot_date),
                
                CHECK (total_queries >= 0),
                CHECK (mention_rate >= 0 AND mention_rate <= 100),
                CHECK (share_of_voice >= 0 AND share_of_voice <= 100)
            )
        """)
        logger.info("   ✅ Tabla llm_monitoring_snapshots creada")
        
        # ===================================
        # TABLA 5: API KEYS DE USUARIO
        # ===================================
        logger.info("📋 [5/6] Creando tabla: user_llm_api_keys...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_llm_api_keys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
                
                -- API Keys encriptadas (una por proveedor)
                openai_api_key_encrypted TEXT,
                anthropic_api_key_encrypted TEXT,
                google_api_key_encrypted TEXT,
                perplexity_api_key_encrypted TEXT,
                
                -- Control de gasto mensual
                monthly_budget_usd DECIMAL(10,2) DEFAULT 100.00,
                current_month_spend DECIMAL(10,4) DEFAULT 0,
                spending_alert_threshold DECIMAL(5,2) DEFAULT 80.0,
                last_spend_reset TIMESTAMP DEFAULT NOW(),
                
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                
                CHECK (monthly_budget_usd > 0),
                CHECK (current_month_spend >= 0),
                CHECK (spending_alert_threshold BETWEEN 0 AND 100)
            )
        """)
        logger.info("   ✅ Tabla user_llm_api_keys creada")
        
        # ===================================
        # TABLA 6: REGISTRO DE MODELOS
        # ===================================
        logger.info("📋 [6/6] Creando tabla: llm_model_registry...")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_model_registry (
                id SERIAL PRIMARY KEY,
                
                -- Identificación
                llm_provider VARCHAR(50) NOT NULL,
                model_id VARCHAR(100) NOT NULL,
                model_display_name VARCHAR(255),
                
                -- Pricing (SINGLE SOURCE OF TRUTH)
                cost_per_1m_input_tokens DECIMAL(10,4),
                cost_per_1m_output_tokens DECIMAL(10,4),
                
                -- Capacidades
                max_tokens INTEGER,
                max_output_tokens INTEGER,
                supports_vision BOOLEAN DEFAULT FALSE,
                supports_functions BOOLEAN DEFAULT FALSE,
                
                -- Estado
                is_current BOOLEAN DEFAULT FALSE,
                is_available BOOLEAN DEFAULT TRUE,
                
                -- Detección automática
                detected_at TIMESTAMP DEFAULT NOW(),
                last_used_at TIMESTAMP,
                
                -- Estadísticas de uso
                total_queries INTEGER DEFAULT 0,
                total_tokens_consumed BIGINT DEFAULT 0,
                total_cost DECIMAL(12,4) DEFAULT 0,
                
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(llm_provider, model_id)
            )
        """)
        logger.info("   ✅ Tabla llm_model_registry creada")
        
        # ===================================
        # INSERTAR MODELOS INICIALES
        # ===================================
        logger.info("")
        logger.info("📦 Insertando modelos iniciales...")
        
        cur.execute("""
            INSERT INTO llm_model_registry (
                llm_provider, model_id, model_display_name,
                cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                max_tokens, is_current
            ) VALUES 
                -- OpenAI GPT-5
                ('openai', 'gpt-5', 'GPT-5', 
                 15.00, 45.00, 1000000, TRUE),
                
                -- Anthropic Claude Sonnet 4.5
                ('anthropic', 'claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5',
                 3.00, 15.00, 200000, TRUE),
                
                -- Google Gemini 3 Pro Preview
                ('google', 'gemini-3-pro-preview', 'Gemini 3 Pro Preview',
                 2.00, 12.00, 1000000, TRUE),
                
                -- Perplexity Sonar Large
                ('perplexity', 'llama-3.1-sonar-large-128k-online', 'Perplexity Sonar Large',
                 1.00, 1.00, 128000, TRUE)
                
            ON CONFLICT (llm_provider, model_id) DO UPDATE SET
                is_current = EXCLUDED.is_current,
                cost_per_1m_input_tokens = EXCLUDED.cost_per_1m_input_tokens,
                cost_per_1m_output_tokens = EXCLUDED.cost_per_1m_output_tokens,
                updated_at = NOW()
        """)
        logger.info("   ✅ 4 modelos insertados (GPT-5, Claude 4.5, Gemini 3 Pro, Perplexity)")
        
        # ===================================
        # CREAR ÍNDICES
        # ===================================
        logger.info("")
        logger.info("🔧 Creando índices para optimización...")
        
        indices = [
            ("idx_llm_proj_user", "llm_monitoring_projects(user_id)"),
            ("idx_llm_proj_active", "llm_monitoring_projects(is_active)"),
            ("idx_llm_queries_proj", "llm_monitoring_queries(project_id)"),
            ("idx_llm_results_proj_date", "llm_monitoring_results(project_id, analysis_date)"),
            ("idx_llm_results_provider", "llm_monitoring_results(llm_provider)"),
            ("idx_llm_results_mentioned", "llm_monitoring_results(brand_mentioned)"),
            ("idx_llm_snapshots_proj_date", "llm_monitoring_snapshots(project_id, snapshot_date)"),
            ("idx_llm_snapshots_provider", "llm_monitoring_snapshots(llm_provider)"),
            ("idx_llm_models_provider", "llm_model_registry(llm_provider)"),
            ("idx_llm_models_current", "llm_model_registry(is_current)"),
        ]
        
        for idx_name, idx_def in indices:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
        
        logger.info(f"   ✅ {len(indices)} índices creados")
        
        # ===================================
        # CREAR VISTA DE COMPARATIVA
        # ===================================
        logger.info("")
        logger.info("📊 Creando vista: llm_visibility_comparison...")
        
        cur.execute("""
            CREATE OR REPLACE VIEW llm_visibility_comparison AS
            SELECT 
                s.project_id,
                s.snapshot_date,
                p.brand_name,
                p.industry,
                
                -- Métricas por LLM (pivoted)
                MAX(CASE WHEN s.llm_provider = 'openai' THEN s.mention_rate END) as chatgpt_mention_rate,
                MAX(CASE WHEN s.llm_provider = 'anthropic' THEN s.mention_rate END) as claude_mention_rate,
                MAX(CASE WHEN s.llm_provider = 'google' THEN s.mention_rate END) as gemini_mention_rate,
                MAX(CASE WHEN s.llm_provider = 'perplexity' THEN s.mention_rate END) as perplexity_mention_rate,
                
                -- Promedios
                AVG(s.mention_rate) as avg_mention_rate_all_llms,
                AVG(s.share_of_voice) as avg_share_of_voice,
                AVG(s.avg_sentiment_score) as avg_sentiment_score,
                
                -- Costes
                SUM(s.total_cost_usd) as total_cost_all_llms,
                
                -- Mejor y peor LLM
                (SELECT llm_provider FROM llm_monitoring_snapshots s2 
                 WHERE s2.project_id = s.project_id AND s2.snapshot_date = s.snapshot_date 
                 ORDER BY s2.mention_rate DESC LIMIT 1) as best_llm_for_mentions,
                 
                (SELECT llm_provider FROM llm_monitoring_snapshots s2 
                 WHERE s2.project_id = s.project_id AND s2.snapshot_date = s.snapshot_date 
                 ORDER BY s2.mention_rate ASC LIMIT 1) as worst_llm_for_mentions
                
            FROM llm_monitoring_snapshots s
            JOIN llm_monitoring_projects p ON s.project_id = p.id
            GROUP BY s.project_id, s.snapshot_date, p.brand_name, p.industry
        """)
        logger.info("   ✅ Vista llm_visibility_comparison creada")
        
        # ===================================
        # COMMIT Y VERIFICACIÓN
        # ===================================
        conn.commit()
        
        logger.info("")
        logger.info("✅ Verificando tablas creadas...")
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND (table_name LIKE 'llm_%' OR table_name LIKE 'user_llm_%')
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        table_names = [t['table_name'] for t in tables]
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("🎉 SISTEMA MULTI-LLM BRAND MONITORING CREADO EXITOSAMENTE")
        logger.info("=" * 70)
        logger.info(f"📋 Tablas creadas: {len(table_names)}")
        for table in table_names:
            logger.info(f"   ✓ {table}")
        logger.info("=" * 70)
        logger.info("")
        logger.info("🎯 SIGUIENTE PASO:")
        logger.info("   → Instalar dependencias: pip install openai anthropic google-generativeai")
        logger.info("   → Crear proveedores LLM en: services/llm_providers/")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ ERROR CREANDO TABLAS")
        logger.error("=" * 70)
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("")
        logger.error("💡 Posibles causas:")
        logger.error("   • La base de datos no está corriendo")
        logger.error("   • DATABASE_URL está mal configurada")
        logger.error("   • No tienes permisos para crear tablas")
        logger.error("")
        conn.rollback()
        return False
        
    finally:
        cur.close()
        conn.close()


def main():
    """Función principal"""
    logger.info("")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 15 + "MULTI-LLM BRAND MONITORING SETUP" + " " * 21 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    logger.info("Modelos soportados:")
    logger.info("  • GPT-5 (OpenAI) - $15/$45 per 1M tokens")
    logger.info("  • Claude Sonnet 4.5 (Anthropic) - $3/$15 per 1M tokens")
    logger.info("  • Gemini 3 Pro Preview (Google) - $2/$12 per 1M tokens")
    logger.info("  • Perplexity Sonar Large - $1/$1 per 1M tokens")
    logger.info("")
    
    success = create_llm_monitoring_tables()
    
    if not success:
        logger.error("❌ Setup falló. Revisa los errores arriba.")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
