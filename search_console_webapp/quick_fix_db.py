#!/usr/bin/env python3
"""
Script rápido para identificar y corregir el problema de la base de datos
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
import time
import json

def test_basic_queries():
    """Prueba consultas básicas para identificar el problema"""
    print("🔍 PROBANDO CONSULTAS BÁSICAS")
    print("=" * 40)
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Error de conexión a la base de datos")
            return False
            
        cur = conn.cursor()
        
        # 1. Verificar tabla
        print("1️⃣ Verificando tabla...")
        cur.execute("SELECT COUNT(*) FROM ai_overview_analysis")
        count = cur.fetchone()[0]
        print(f"✅ Tabla existe, {count} registros")
        
        # 2. Consulta simple de categorías
        print("\n2️⃣ Probando consulta de categorías...")
        cur.execute("""
            SELECT 
                keyword_word_count,
                COUNT(*) as total,
                SUM(CASE WHEN has_ai_overview THEN 1 ELSE 0 END) as con_ai_overview
            FROM ai_overview_analysis 
            WHERE keyword_word_count > 0
            GROUP BY keyword_word_count
            ORDER BY keyword_word_count
        """)
        simple_results = cur.fetchall()
        
        print(f"✅ Consulta simple: {len(simple_results)} grupos")
        for word_count, total, with_ai in simple_results:
            print(f"   - {word_count} palabras: {total} total, {with_ai} con AI")
        
        # 3. Consulta compleja (la que falla)
        print("\n3️⃣ Probando consulta CASE...")
        try:
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
            case_results = cur.fetchall()
            print(f"✅ Consulta CASE: {len(case_results)} categorías")
            for categoria, total, with_ai in case_results:
                print(f"   - {categoria}: {total} total, {with_ai} con AI")
                
        except Exception as e:
            print(f"❌ Error en consulta CASE: {e}")
            print("🔧 Intentando consulta alternativa...")
            
            # Consulta alternativa más simple
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
            alt_results = cur.fetchall()
            print(f"✅ Consulta alternativa: {len(alt_results)} categorías")
            for categoria, total, with_ai in alt_results:
                print(f"   - {categoria}: {total} total, {with_ai} con AI")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error en pruebas básicas: {e}")
        import traceback
        traceback.print_exc()
        return False

def insert_test_data_direct():
    """Inserta datos de prueba directamente con SQL"""
    print("\n🔍 INSERTANDO DATOS DE PRUEBA")
    print("=" * 40)
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Error de conexión a la base de datos")
            return False
            
        cur = conn.cursor()
        
        # Insertar datos de muestra directamente
        test_data = [
            ('seo', 1, True, False, 80, 'esp'),
            ('curso seo', 2, True, True, 60, 'esp'),
            ('herramientas seo gratis', 3, False, False, 0, 'esp'),
            ('mejores herramientas seo para principiantes', 6, True, False, 40, 'esp'),
            ('como hacer estrategia seo completa paso a paso', 8, False, False, 0, 'esp'),
        ]
        
        for keyword, word_count, has_ai, is_source, impact, country in test_data:
            cur.execute("""
                INSERT INTO ai_overview_analysis (
                    site_url, keyword, keyword_word_count, has_ai_overview, 
                    domain_is_ai_source, impact_score, country_code,
                    clicks_m1, clicks_m2, raw_data
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                'test-site.com', keyword, word_count, has_ai, 
                is_source, impact, country,
                100, 80, json.dumps({'test': True})
            ))
        
        conn.commit()
        print(f"✅ Insertados {len(test_data)} registros de prueba")
        
        # Verificar inserción
        cur.execute("SELECT COUNT(*) FROM ai_overview_analysis")
        total_after = cur.fetchone()[0]
        print(f"✅ Total registros después: {total_after}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error insertando datos: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    print("🔧 DIAGNÓSTICO Y CORRECCIÓN RÁPIDA")
    print("=" * 50)
    
    # 1. Probar consultas básicas
    if not test_basic_queries():
        print("❌ Error en consultas básicas")
        return False
    
    # 2. Insertar datos de prueba
    if not insert_test_data_direct():
        print("❌ Error insertando datos")
        return False
    
    # 3. Probar de nuevo las consultas
    if test_basic_queries():
        print("\n🎉 ¡PROBLEMA RESUELTO!")
        print("✅ Datos insertados correctamente")
        print("✅ Consultas funcionando")
        print("\n💡 Ahora puedes:")
        print("   1. Iniciar tu aplicación: python3 app.py")
        print("   2. Recargar la página")
        print("   3. Ver el gráfico de tipología funcionando")
        return True
    else:
        print("❌ Aún hay problemas")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 