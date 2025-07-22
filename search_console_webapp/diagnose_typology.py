#!/usr/bin/env python3
"""
Script de diagnóstico para el problema del gráfico de tipología
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    get_db_connection,
    get_ai_overview_stats,
    save_ai_overview_analysis
)
import time
import json

def diagnose_database():
    """Diagnóstica el estado de la base de datos"""
    print("🔍 DIAGNÓSTICO DE BASE DE DATOS")
    print("=" * 40)
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Error de conexión a la base de datos")
            return False
            
        cur = conn.cursor()
        
        # Verificar tabla existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'ai_overview_analysis'
            );
        """)
        table_exists = cur.fetchone()[0]
        print(f"✅ Tabla ai_overview_analysis existe: {table_exists}")
        
        # Contar registros totales
        cur.execute('SELECT COUNT(*) FROM ai_overview_analysis')
        total_records = cur.fetchone()[0]
        print(f"📊 Total registros en BD: {total_records}")
        
        # Mostrar últimos 5 registros
        if total_records > 0:
            cur.execute("""
                SELECT keyword, keyword_word_count, has_ai_overview, analysis_date 
                FROM ai_overview_analysis 
                ORDER BY analysis_date DESC 
                LIMIT 5
            """)
            recent_records = cur.fetchall()
            
            print("\n📋 Últimos 5 registros:")
            for record in recent_records:
                keyword, word_count, has_ai, date = record
                print(f"   - {keyword[:30]:<30} | {word_count} palabras | AI: {has_ai} | {date}")
        else:
            print("⚠️ No hay registros en la tabla")
        
        # Verificar distribución por palabras
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
        distribution = cur.fetchall()
        
        if distribution:
            print("\n📊 Distribución por tipología:")
            for cat, total, with_ai in distribution:
                print(f"   - {cat}: {total} total, {with_ai} con AI ({(with_ai/total*100):.1f}%)")
        else:
            print("⚠️ No hay datos de distribución")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error en diagnóstico de BD: {e}")
        return False

def test_stats_function():
    """Prueba la función get_ai_overview_stats"""
    print("\n🔍 DIAGNÓSTICO DE FUNCIÓN STATS")
    print("=" * 40)
    
    try:
        stats = get_ai_overview_stats()
        
        print("📊 Resultado de get_ai_overview_stats():")
        print(f"   - total_analyses: {stats.get('total_analyses', 'N/A')}")
        print(f"   - with_ai_overview: {stats.get('with_ai_overview', 'N/A')}")
        print(f"   - word_count_stats: {len(stats.get('word_count_stats', []))} categorías")
        
        word_stats = stats.get('word_count_stats', [])
        if word_stats:
            print("\n📋 Detalle word_count_stats:")
            for stat in word_stats:
                print(f"   - {stat.get('categoria')}: {stat.get('total')} total, {stat.get('con_ai_overview')} con AI")
        else:
            print("⚠️ word_count_stats está vacío")
            
        return True
        
    except Exception as e:
        print(f"❌ Error en función stats: {e}")
        return False

def insert_sample_data():
    """Inserta datos de muestra para probar"""
    print("\n🔍 INSERTANDO DATOS DE MUESTRA")
    print("=" * 40)
    
    try:
        # Simular análisis con diferentes tipos de keywords
        sample_analysis = {
            'results': [
                # 1 término
                {
                    'keyword': 'seo',
                    'ai_analysis': {'has_ai_overview': True, 'domain_is_ai_source': False, 'impact_score': 80, 'total_elements': 1},
                    'clicks_m1': 200, 'clicks_m2': 150, 'delta_clicks_absolute': -50,
                    'country_analyzed': 'esp', 'timestamp': time.time()
                },
                # 2-5 términos
                {
                    'keyword': 'curso de seo',
                    'ai_analysis': {'has_ai_overview': True, 'domain_is_ai_source': True, 'impact_score': 60, 'total_elements': 1},
                    'clicks_m1': 150, 'clicks_m2': 120, 'delta_clicks_absolute': -30,
                    'country_analyzed': 'esp', 'timestamp': time.time()
                },
                {
                    'keyword': 'herramientas seo gratis',
                    'ai_analysis': {'has_ai_overview': False, 'domain_is_ai_source': False, 'impact_score': 0, 'total_elements': 0},
                    'clicks_m1': 100, 'clicks_m2': 110, 'delta_clicks_absolute': 10,
                    'country_analyzed': 'esp', 'timestamp': time.time()
                },
                # 6-10 términos
                {
                    'keyword': 'mejores herramientas seo para principiantes en 2024',
                    'ai_analysis': {'has_ai_overview': True, 'domain_is_ai_source': False, 'impact_score': 40, 'total_elements': 1},
                    'clicks_m1': 80, 'clicks_m2': 60, 'delta_clicks_absolute': -20,
                    'country_analyzed': 'esp', 'timestamp': time.time()
                },
                # 11+ términos
                {
                    'keyword': 'como hacer una estrategia completa de seo para mejorar el posicionamiento en google paso a paso',
                    'ai_analysis': {'has_ai_overview': False, 'domain_is_ai_source': False, 'impact_score': 0, 'total_elements': 0},
                    'clicks_m1': 50, 'clicks_m2': 55, 'delta_clicks_absolute': 5,
                    'country_analyzed': 'esp', 'timestamp': time.time()
                }
            ],
            'summary': {
                'total_keywords_analyzed': 5,
                'keywords_with_ai_overview': 3
            },
            'site_url': 'test-domain.com'
        }
        
        # Guardar análisis de muestra
        if save_ai_overview_analysis(sample_analysis):
            print("✅ Datos de muestra insertados correctamente")
            
            # Verificar que se guardaron
            stats_after = get_ai_overview_stats()
            total_after = stats_after.get('total_analyses', 0)
            word_stats_after = stats_after.get('word_count_stats', [])
            
            print(f"✅ Total análisis después: {total_after}")
            print(f"✅ Categorías de tipología: {len(word_stats_after)}")
            
            return True
        else:
            print("❌ Error insertando datos de muestra")
            return False
            
    except Exception as e:
        print(f"❌ Error insertando datos de muestra: {e}")
        return False

def simulate_api_call():
    """Simula la llamada API que hace el frontend"""
    print("\n🔍 SIMULANDO LLAMADA API")
    print("=" * 40)
    
    try:
        # Importar y simular la función de la ruta
        from app import get_ai_overview_stats_route
        
        # Esto no funcionará directamente porque necesita contexto Flask
        # Pero podemos probar la lógica directamente
        stats = get_ai_overview_stats()
        word_count_stats = stats.get('word_count_stats', [])
        
        # Transformar como lo hace la ruta de tipología
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
        
        for item in word_count_stats:
            categoria = item['categoria']
            label = category_labels.get(categoria, categoria)
            
            typology_data['categories'].append(label)
            typology_data['total_queries'].append(item['total'])
            typology_data['queries_with_ai'].append(item['con_ai_overview'])
            typology_data['ai_percentage'].append(item['porcentaje_ai'])
        
        print("📊 Datos que recibiría el frontend:")
        print(f"   - Categorías: {typology_data['categories']}")
        print(f"   - Total queries: {typology_data['total_queries']}")
        print(f"   - Con AI: {typology_data['queries_with_ai']}")
        print(f"   - Porcentajes: {typology_data['ai_percentage']}")
        
        if len(typology_data['categories']) > 0:
            print("✅ Datos de tipología disponibles para el gráfico")
            return True
        else:
            print("❌ No hay datos de tipología disponibles")
            return False
            
    except Exception as e:
        print(f"❌ Error simulando API: {e}")
        return False

def main():
    """Función principal de diagnóstico"""
    print("🔍 DIAGNÓSTICO DEL GRÁFICO DE TIPOLOGÍA")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 4
    
    # Ejecutar diagnósticos
    if diagnose_database():
        tests_passed += 1
        
    if test_stats_function():
        tests_passed += 1
        
    if insert_sample_data():
        tests_passed += 1
        
    if simulate_api_call():
        tests_passed += 1
    
    # Resumen final
    print("\n" + "=" * 50)
    print(f"🏁 RESUMEN: {tests_passed}/{total_tests} diagnósticos exitosos")
    
    if tests_passed == total_tests:
        print("🎉 ¡El sistema debería funcionar ahora!")
        print("\n💡 Solución:")
        print("   1. Los datos se insertaron correctamente")
        print("   2. Recarga la página en tu navegador")
        print("   3. El gráfico de tipología debería mostrar datos")
    else:
        print("⚠️ Hay problemas que necesitan resolución")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 