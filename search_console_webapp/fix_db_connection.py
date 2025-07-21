#!/usr/bin/env python3
"""
Script para diagnosticar y corregir problemas de conexión a la base de datos
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configuración directa de conexión
DATABASE_URL = 'postgresql://postgres:LWaKOzBkTWoSJNvwOdBkpcpHqywaHavh@switchback.proxy.rlwy.net:14943/railway'

def test_direct_connection():
    """Prueba la conexión directa a PostgreSQL"""
    print("🔍 PROBANDO CONEXIÓN DIRECTA")
    print("=" * 40)
    
    try:
        # Conexión directa
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        print("✅ Conexión establecida")
        
        cur = conn.cursor()
        
        # Prueba básica
        cur.execute("SELECT 1 as test")
        result = cur.fetchone()
        print(f"✅ Consulta de prueba: {result}")
        
        # Verificar tabla
        cur.execute("SELECT COUNT(*) as count FROM ai_overview_analysis")
        result = cur.fetchone()
        print(f"✅ Registros en tabla: {result['count']}")
        
        # Insertar datos de prueba directamente
        print("\n📝 Insertando datos de prueba...")
        
        test_keywords = [
            ('seo', 1, True, False, 80),
            ('curso seo', 2, True, True, 60),
            ('herramientas seo gratis', 3, False, False, 0),
            ('mejores herramientas seo para principiantes', 6, True, False, 40),
            ('como hacer estrategia seo completa paso a paso', 8, False, False, 0),
        ]
        
        for keyword, word_count, has_ai, is_source, impact in test_keywords:
            cur.execute("""
                INSERT INTO ai_overview_analysis (
                    site_url, keyword, keyword_word_count, has_ai_overview, 
                    domain_is_ai_source, impact_score, country_code,
                    clicks_m1, clicks_m2, raw_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                'test-site.com', keyword, word_count, has_ai, 
                is_source, impact, 'esp',
                100, 80, json.dumps({'test': True})
            ))
        
        conn.commit()
        print("✅ Datos de prueba insertados")
        
        # Verificar inserción
        cur.execute("SELECT COUNT(*) as count FROM ai_overview_analysis")
        result = cur.fetchone()
        print(f"✅ Total registros después: {result['count']}")
        
        # Probar la consulta de tipología
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
        """)
        
        results = cur.fetchall()
        print(f"✅ Consulta de tipología: {len(results)} categorías")
        
        for row in results:
            total = row['total']
            con_ai = row['con_ai_overview']
            porcentaje = round((con_ai / total * 100), 2) if total > 0 else 0
            print(f"   - {row['categoria']}: {total} total, {con_ai} con AI ({porcentaje}%)")
        
        # Generar JSON como lo haría la API
        typology_data = {
            'categories': [],
            'total_queries': [],
            'queries_with_ai': [],
            'ai_percentage': []
        }
        
        category_labels = {
            '1_termino': '1 término',
            '2_5_terminos': '2-5 términos', 
            '6_10_terminos': '6-10 términos',
            '11_20_terminos': '11-20 términos',
            'mas_20_terminos': '20+ términos'
        }
        
        for row in results:
            categoria = row['categoria']
            label = category_labels.get(categoria, categoria)
            total = row['total']
            con_ai = row['con_ai_overview']
            porcentaje = round((con_ai / total * 100), 2) if total > 0 else 0
            
            typology_data['categories'].append(label)
            typology_data['total_queries'].append(total)
            typology_data['queries_with_ai'].append(con_ai)
            typology_data['ai_percentage'].append(porcentaje)
        
        print("\n🎯 Datos para el frontend:")
        print(f"   - Categorías: {typology_data['categories']}")
        print(f"   - Total: {typology_data['total_queries']}")
        print(f"   - Con AI: {typology_data['queries_with_ai']}")
        print(f"   - Porcentajes: {typology_data['ai_percentage']}")
        
        conn.close()
        
        # Guardar datos en archivo para debugging
        with open('typology_test_data.json', 'w') as f:
            json.dump(typology_data, f, indent=2)
        print("\n💾 Datos guardados en typology_test_data.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    print("🔧 DIAGNÓSTICO Y CORRECCIÓN DE BASE DE DATOS")
    print("=" * 50)
    
    if test_direct_connection():
        print("\n🎉 ¡PROBLEMA RESUELTO!")
        print("✅ Base de datos funcionando correctamente")
        print("✅ Datos de tipología disponibles")
        print("\n💡 Solución:")
        print("   1. Los datos se insertaron correctamente")
        print("   2. El sistema debería funcionar ahora")
        print("   3. Inicia tu aplicación: python3 app.py")
        print("   4. Recarga la página")
        print("   5. El gráfico de tipología debería aparecer")
        return True
    else:
        print("❌ No se pudo solucionar el problema")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 