#!/usr/bin/env python3
"""
Script para crear la tabla ai_overview_analysis manualmente
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configuración directa de conexión
DATABASE_URL = 'postgresql://postgres:LWaKOzBkTWoSJNvwOdBkpcpHqywaHavh@switchback.proxy.rlwy.net:14943/railway'

def create_ai_overview_table():
    """Crea la tabla ai_overview_analysis"""
    print("🔧 CREANDO TABLA AI_OVERVIEW_ANALYSIS")
    print("=" * 50)
    
    try:
        # Conexión directa
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        print("✅ Conexión establecida")
        
        cur = conn.cursor()
        
        # Crear tabla
        print("📋 Creando tabla ai_overview_analysis...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_overview_analysis (
                id SERIAL PRIMARY KEY,
                site_url VARCHAR(255) NOT NULL,
                keyword VARCHAR(255) NOT NULL,
                analysis_date TIMESTAMP DEFAULT NOW(),
                has_ai_overview BOOLEAN DEFAULT FALSE,
                domain_is_ai_source BOOLEAN DEFAULT FALSE,
                impact_score INTEGER DEFAULT 0,
                country_code VARCHAR(3),
                keyword_word_count INTEGER,
                clicks_m1 INTEGER DEFAULT 0,
                clicks_m2 INTEGER DEFAULT 0,
                delta_clicks_absolute INTEGER DEFAULT 0,
                delta_clicks_percent DECIMAL(10,2),
                impressions_m1 INTEGER DEFAULT 0,
                impressions_m2 INTEGER DEFAULT 0,
                ctr_m1 DECIMAL(5,2),
                ctr_m2 DECIMAL(5,2),
                position_m1 DECIMAL(5,2),
                position_m2 DECIMAL(5,2),
                ai_elements_count INTEGER DEFAULT 0,
                domain_ai_source_position INTEGER,
                raw_data JSONB,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("✅ Tabla creada")
        
        # Crear índices
        print("📋 Creando índices...")
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_ai_analysis_site_date ON ai_overview_analysis(site_url, analysis_date)",
            "CREATE INDEX IF NOT EXISTS idx_ai_analysis_keyword ON ai_overview_analysis(keyword)",
            "CREATE INDEX IF NOT EXISTS idx_ai_analysis_country ON ai_overview_analysis(country_code)",
            "CREATE INDEX IF NOT EXISTS idx_ai_analysis_user ON ai_overview_analysis(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_analysis_word_count ON ai_overview_analysis(keyword_word_count)",
            "CREATE INDEX IF NOT EXISTS idx_ai_analysis_has_ai ON ai_overview_analysis(has_ai_overview)"
        ]
        
        for index_sql in indices:
            cur.execute(index_sql)
        
        print("✅ Índices creados")
        
        # Insertar datos de prueba
        print("📝 Insertando datos de muestra...")
        
        test_keywords = [
            ('seo', 1, True, False, 80),
            ('curso seo', 2, True, True, 60),
            ('herramientas seo gratis', 3, False, False, 0),
            ('mejores herramientas seo para principiantes', 6, True, False, 40),
            ('como hacer estrategia seo completa paso a paso', 8, False, False, 0),
            ('marketing', 1, True, False, 75),
            ('estrategia de marketing digital', 4, True, True, 55),
            ('herramientas de analisis web para empresas pequeñas', 7, False, False, 0),
            ('curso completo de seo técnico avanzado para profesionales', 9, True, False, 35),
            ('factura', 1, True, False, 90),
            ('factura proforma', 2, True, True, 70),
            ('estado de flujo de efectivo', 5, True, False, 45),
            ('recibo de pago', 3, False, False, 0),
        ]
        
        for keyword, word_count, has_ai, is_source, impact in test_keywords:
            cur.execute("""
                INSERT INTO ai_overview_analysis (
                    site_url, keyword, keyword_word_count, has_ai_overview, 
                    domain_is_ai_source, impact_score, country_code,
                    clicks_m1, clicks_m2, delta_clicks_absolute,
                    impressions_m1, impressions_m2, raw_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'delfinultracongelados.es', keyword, word_count, has_ai, 
                is_source, impact, 'esp',
                100 + (word_count * 10), 80 + (word_count * 8), -20 if has_ai else 5,
                1000 + (word_count * 100), 900 + (word_count * 90),
                json.dumps({'test': True, 'analysis_type': 'sample'})
            ))
        
        conn.commit()
        print(f"✅ Insertados {len(test_keywords)} registros de muestra")
        
        # Verificar tabla
        cur.execute("SELECT COUNT(*) as count FROM ai_overview_analysis")
        result = cur.fetchone()
        print(f"✅ Total registros: {result['count']}")
        
        # Probar consulta de tipología
        print("\n📊 Probando consulta de tipología...")
        cur.execute("""
            SELECT 
                CASE 
                    WHEN keyword_word_count = 1 THEN '1_termino'
                    WHEN keyword_word_count BETWEEN 2 AND 5 THEN '2_5_terminos'
                    WHEN keyword_word_count BETWEEN 6 AND 10 THEN '6_10_terminos'
                    WHEN keyword_word_count BETWEEN 11 AND 20 THEN '11_20_terminos'
                    ELSE 'mas_20_terminos'
                END as categoria,
                COUNT(*) as total,
                SUM(CASE WHEN has_ai_overview THEN 1 ELSE 0 END) as con_ai_overview
            FROM ai_overview_analysis 
            WHERE keyword_word_count > 0
            GROUP BY categoria
            ORDER BY 
                CASE categoria
                    WHEN '1_termino' THEN 1
                    WHEN '2_5_terminos' THEN 2
                    WHEN '6_10_terminos' THEN 3
                    WHEN '11_20_terminos' THEN 4
                    ELSE 5
                END
        """)
        
        results = cur.fetchall()
        print(f"✅ Consulta de tipología: {len(results)} categorías")
        
        for row in results:
            total = row['total']
            con_ai = row['con_ai_overview']
            porcentaje = round((con_ai / total * 100), 2) if total > 0 else 0
            print(f"   - {row['categoria']}: {total} total, {con_ai} con AI ({porcentaje}%)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    print("🚀 CREACIÓN DE TABLA AI OVERVIEW")
    print("=" * 50)
    
    if create_ai_overview_table():
        print("\n🎉 ¡TABLA CREADA EXITOSAMENTE!")
        print("✅ Tabla ai_overview_analysis creada")
        print("✅ Índices optimizados creados")
        print("✅ Datos de muestra insertados")
        print("✅ Sistema de tipología funcional")
        print("\n💡 Próximos pasos:")
        print("   1. Inicia tu aplicación: python3 app.py")
        print("   2. Ve a tu navegador y recarga la página")
        print("   3. Ejecuta un análisis AI Overview")
        print("   4. ¡Deberías ver el gráfico de tipología funcionando!")
        return True
    else:
        print("\n❌ Error creando la tabla")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 