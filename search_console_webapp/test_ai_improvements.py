#!/usr/bin/env python3
"""
Script de prueba para verificar las mejoras de AI Overview
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    get_db_connection,
    get_ai_overview_stats,
    save_ai_overview_analysis
)
from services.ai_cache import ai_cache
import json
import time

def test_database_connection():
    """Prueba la conexión a la base de datos"""
    print("🔍 Probando conexión a la base de datos...")
    
    try:
        conn = get_db_connection()
        if conn:
            print("✅ Conexión a PostgreSQL exitosa")
            
            # Verificar tabla ai_overview_analysis
            cur = conn.cursor()
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'ai_overview_analysis'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            
            print(f"✅ Tabla ai_overview_analysis tiene {len(columns)} columnas:")
            for col in columns[:5]:  # Mostrar solo las primeras 5
                print(f"   - {col[0]} ({col[1]})")
            if len(columns) > 5:
                print(f"   ... y {len(columns) - 5} más")
            
            conn.close()
            return True
        else:
            print("❌ Error de conexión a la base de datos")
            return False
            
    except Exception as e:
        print(f"❌ Error probando base de datos: {e}")
        return False

def test_cache_system():
    """Prueba el sistema de caché"""
    print("\n💾 Probando sistema de caché...")
    
    try:
        cache_stats = ai_cache.get_cache_stats()
        
        if cache_stats.get('cache_available'):
            print("✅ Redis disponible y funcionando")
            print(f"   - Versión Redis: {cache_stats.get('redis_version', 'unknown')}")
            print(f"   - Memoria usada: {cache_stats.get('used_memory', 'unknown')}")
            print(f"   - Análisis en caché: {cache_stats.get('ai_analyses_cached', 0)}")
            
            # Prueba de guardado/recuperación
            test_keyword = "test keyword"
            test_site = "test.com"
            test_country = "esp"
            test_analysis = {
                'keyword': test_keyword,
                'ai_analysis': {'has_ai_overview': True, 'impact_score': 50},
                'timestamp': time.time()
            }
            
            # Guardar en caché
            if ai_cache.cache_analysis(test_keyword, test_site, test_country, test_analysis):
                print("✅ Prueba de guardado en caché exitosa")
                
                # Recuperar del caché
                cached_data = ai_cache.get_cached_analysis(test_keyword, test_site, test_country)
                if cached_data:
                    print("✅ Prueba de recuperación de caché exitosa")
                else:
                    print("⚠️ No se pudo recuperar del caché")
            else:
                print("⚠️ No se pudo guardar en caché")
                
        else:
            print("⚠️ Redis no disponible - sistema funcionará sin caché")
            print("   Esto es normal si Redis no está instalado localmente")
            
        return True
        
    except Exception as e:
        print(f"❌ Error probando caché: {e}")
        return False

def test_ai_stats():
    """Prueba las estadísticas de AI Overview"""
    print("\n📊 Probando estadísticas de AI Overview...")
    
    try:
        stats = get_ai_overview_stats()
        
        print("✅ Estadísticas obtenidas correctamente:")
        print(f"   - Total análisis: {stats.get('total_analyses', 0)}")
        print(f"   - Con AI Overview: {stats.get('with_ai_overview', 0)}")
        print(f"   - Como fuente AI: {stats.get('as_ai_source', 0)}")
        print(f"   - Porcentaje AI: {stats.get('ai_overview_percentage', 0)}%")
        
        word_count_stats = stats.get('word_count_stats', [])
        if word_count_stats:
            print(f"   - Categorías de tipología: {len(word_count_stats)}")
        else:
            print("   - Sin datos de tipología (normal en instalación nueva)")
            
        return True
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        return False

def test_save_analysis():
    """Prueba guardar un análisis de muestra"""
    print("\n💾 Probando guardado de análisis...")
    
    try:
        # Crear análisis de muestra
        sample_analysis = {
            'results': [
                {
                    'keyword': 'keyword de prueba',
                    'ai_analysis': {
                        'has_ai_overview': True,
                        'domain_is_ai_source': False,
                        'impact_score': 75,
                        'total_elements': 1
                    },
                    'clicks_m1': 100,
                    'clicks_m2': 80,
                    'delta_clicks_absolute': -20,
                    'delta_clicks_percent': -20.0,
                    'impressions_m1': 1000,
                    'impressions_m2': 900,
                    'country_analyzed': 'esp',
                    'timestamp': time.time()
                }
            ],
            'summary': {
                'total_keywords_analyzed': 1,
                'keywords_with_ai_overview': 1
            },
            'site_url': 'test-domain.com'
        }
        
        # Intentar guardar
        if save_ai_overview_analysis(sample_analysis):
            print("✅ Análisis de muestra guardado exitosamente")
            
            # Verificar que se guardó
            stats_after = get_ai_overview_stats()
            total_after = stats_after.get('total_analyses', 0)
            print(f"✅ Total análisis en BD: {total_after}")
            
            return True
        else:
            print("❌ Error guardando análisis de muestra")
            return False
            
    except Exception as e:
        print(f"❌ Error probando guardado: {e}")
        return False

def main():
    """Función principal de pruebas"""
    print("🧪 INICIANDO PRUEBAS DEL SISTEMA AI OVERVIEW")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 4
    
    # Ejecutar pruebas
    if test_database_connection():
        tests_passed += 1
        
    if test_cache_system():
        tests_passed += 1
        
    if test_ai_stats():
        tests_passed += 1
        
    if test_save_analysis():
        tests_passed += 1
    
    # Resumen final
    print("\n" + "=" * 50)
    print(f"🏁 RESUMEN DE PRUEBAS: {tests_passed}/{total_tests} exitosas")
    
    if tests_passed == total_tests:
        print("🎉 ¡Todas las pruebas pasaron! Sistema completamente funcional.")
        print("\n💡 Próximos pasos:")
        print("   1. Inicia la aplicación: python3 app.py")
        print("   2. Ve a http://localhost:5001")
        print("   3. Ejecuta un análisis AI Overview")
        print("   4. Verifica el gráfico de tipología")
        return True
    else:
        print(f"⚠️ {total_tests - tests_passed} pruebas fallaron. Revisa los errores arriba.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 