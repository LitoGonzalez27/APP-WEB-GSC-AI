#!/usr/bin/env python3
"""
Script para exportar keywords únicas del proyecto HM Fertility Center
"""

import psycopg2
import pandas as pd
from datetime import datetime

DATABASE_URL = "postgresql://postgres:HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS@switchyard.proxy.rlwy.net:18167/railway"

def export_hm_fertility_keywords_unique():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("🔍 Buscando keywords únicas del proyecto HM Fertility (ID: 4)\n")
        
        # Obtener información del proyecto
        cursor.execute("""
            SELECT id, name, domain, country_code, created_at
            FROM manual_ai_projects
            WHERE id = 4
        """)
        project = cursor.fetchone()
        project_id, project_name, domain, country_code, created_at = project
        
        print(f"📋 Proyecto: {project_name}")
        print(f"   Dominio: {domain}")
        print(f"   País: {country_code}")
        print(f"   Creado: {created_at}")
        
        # Obtener keywords únicas con el análisis más reciente
        print("\n🔍 Obteniendo keywords únicas con su análisis más reciente...")
        cursor.execute("""
            WITH latest_analysis AS (
                SELECT 
                    keyword_id,
                    has_ai_overview,
                    domain_mentioned,
                    domain_position,
                    ai_elements_count,
                    impact_score,
                    analysis_date,
                    ROW_NUMBER() OVER (PARTITION BY keyword_id ORDER BY analysis_date DESC) as rn
                FROM manual_ai_results
                WHERE project_id = 4
            )
            SELECT 
                k.id,
                k.keyword,
                k.is_active,
                k.added_at,
                la.has_ai_overview,
                la.domain_mentioned,
                la.domain_position,
                la.ai_elements_count,
                la.impact_score,
                la.analysis_date
            FROM manual_ai_keywords k
            LEFT JOIN latest_analysis la ON k.id = la.keyword_id AND la.rn = 1
            WHERE k.project_id = 4
            ORDER BY k.keyword
        """)
        
        keywords = cursor.fetchall()
        print(f"✅ Total keywords únicas encontradas: {len(keywords)}")
        
        if len(keywords) == 0:
            print("❌ No se encontraron keywords para este proyecto")
            return None
        
        # Crear DataFrame
        df_final = pd.DataFrame(keywords, columns=[
            'ID',
            'Keyword',
            'Activa',
            'Fecha Agregada',
            'Tiene AI Overview',
            'Dominio Mencionado',
            'Posición Dominio',
            'Elementos AI',
            'Puntuación Impacto',
            'Último Análisis'
        ])
        
        # Reorganizar columnas
        df_final = df_final[[
            'Keyword',
            'Tiene AI Overview',
            'Dominio Mencionado',
            'Posición Dominio',
            'Elementos AI',
            'Puntuación Impacto',
            'Activa',
            'Último Análisis',
            'Fecha Agregada'
        ]]
        
        # Convertir booleanos a texto más legible
        df_final['Tiene AI Overview'] = df_final['Tiene AI Overview'].apply(
            lambda x: 'Sí' if x else 'No' if x is not None else 'No analizada'
        )
        df_final['Dominio Mencionado'] = df_final['Dominio Mencionado'].apply(
            lambda x: 'Sí' if x else 'No' if x is not None else 'N/A'
        )
        df_final['Activa'] = df_final['Activa'].apply(
            lambda x: 'Sí' if x else 'No'
        )
        
        # Crear nombre de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"HM_Fertility_Keywords_Unicas_{timestamp}.xlsx"
        
        # Exportar a Excel con múltiples hojas
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Hoja principal con todas las keywords únicas
            df_final.to_excel(writer, sheet_name='Keywords Únicas', index=False)
            
            # Hoja resumen
            resumen = {
                'Métrica': [
                    'Total Keywords Únicas',
                    'Keywords con AI Overview',
                    'Keywords sin AI Overview',
                    'Dominio mencionado en AI',
                    'Dominio NO mencionado en AI',
                    'Keywords activas',
                    'Keywords inactivas',
                    'Keywords no analizadas'
                ],
                'Valor': [
                    len(df_final),
                    len(df_final[df_final['Tiene AI Overview'] == 'Sí']),
                    len(df_final[df_final['Tiene AI Overview'] == 'No']),
                    len(df_final[df_final['Dominio Mencionado'] == 'Sí']),
                    len(df_final[df_final['Dominio Mencionado'] == 'No']),
                    len(df_final[df_final['Activa'] == 'Sí']),
                    len(df_final[df_final['Activa'] == 'No']),
                    len(df_final[df_final['Tiene AI Overview'] == 'No analizada'])
                ]
            }
            df_resumen = pd.DataFrame(resumen)
            df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            # Hoja de información del proyecto
            info_proyecto = {
                'Campo': ['Proyecto', 'Dominio', 'País', 'Fecha Creación', 'Total Keywords', 'Fecha Exportación'],
                'Valor': [project_name, domain, country_code, created_at, len(df_final), datetime.now()]
            }
            df_info = pd.DataFrame(info_proyecto)
            df_info.to_excel(writer, sheet_name='Info Proyecto', index=False)
            
            # Hoja con keywords ordenadas por puntuación de impacto
            df_por_impacto = df_final.copy()
            df_por_impacto = df_por_impacto.sort_values('Puntuación Impacto', ascending=False, na_position='last')
            df_por_impacto.to_excel(writer, sheet_name='Por Impacto', index=False)
            
            # Hoja solo con keywords que tienen AI Overview
            df_con_ai = df_final[df_final['Tiene AI Overview'] == 'Sí'].copy()
            if len(df_con_ai) > 0:
                df_con_ai = df_con_ai.sort_values('Puntuación Impacto', ascending=False, na_position='last')
                df_con_ai.to_excel(writer, sheet_name='Con AI Overview', index=False)
            
            # Hoja solo con keywords donde el dominio aparece
            df_dominio_mencionado = df_final[df_final['Dominio Mencionado'] == 'Sí'].copy()
            if len(df_dominio_mencionado) > 0:
                df_dominio_mencionado = df_dominio_mencionado.sort_values('Posición Dominio', na_position='last')
                df_dominio_mencionado.to_excel(writer, sheet_name='Dominio Mencionado', index=False)
        
        print(f"\n✅ ¡Archivo exportado exitosamente!")
        print(f"   📄 {filename}")
        print(f"   📊 {len(df_final)} keywords únicas exportadas")
        print(f"\n📈 Estadísticas:")
        print(f"   - Keywords con AI Overview: {len(df_final[df_final['Tiene AI Overview'] == 'Sí'])}")
        print(f"   - Keywords sin AI Overview: {len(df_final[df_final['Tiene AI Overview'] == 'No'])}")
        print(f"   - Dominio mencionado en AI: {len(df_final[df_final['Dominio Mencionado'] == 'Sí'])}")
        print(f"   - Keywords activas: {len(df_final[df_final['Activa'] == 'Sí'])}")
        print(f"   - Keywords no analizadas: {len(df_final[df_final['Tiene AI Overview'] == 'No analizada'])}")
        
        # Mostrar algunas keywords de ejemplo
        print(f"\n👀 Top 10 keywords por impacto:")
        top_keywords = df_final.sort_values('Puntuación Impacto', ascending=False, na_position='last').head(10)
        print(top_keywords[['Keyword', 'Tiene AI Overview', 'Dominio Mencionado', 'Puntuación Impacto']].to_string(index=False))
        
        cursor.close()
        conn.close()
        
        return filename
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    export_hm_fertility_keywords_unique()

