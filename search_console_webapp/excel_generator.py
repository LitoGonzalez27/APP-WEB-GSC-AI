import pandas as pd
from io import BytesIO
from services.country_config import get_country_name # Importar la función get_country_name

def format_percent_or_infinity(value):
    """
    Convierte un valor numérico a porcentaje con un decimal,
    o maneja cadenas de infinitos.
    """
    if value in ("Infinity", "+Inf"):
        return "+Inf"
    if value in ("-Infinity",):
        return "-Inf"
    if isinstance(value, (int, float)):
        return f"{value:.1f}%"
    return "N/A"


def format_ai_overview_data(ai_overview_results):
    """
    Formatea los datos de AI Overview para Excel según la estructura real del frontend
    """
    if not ai_overview_results:
        return []
    
    formatted_data = []
    
    results = ai_overview_results.get('results', [])
    
    for result in results:
        ai_analysis = result.get('ai_analysis', {})
        ai_detected = ai_analysis.get('ai_overview_detected', [])
        
        base_data = {
            'Keyword': result.get('keyword', ''),
            'Clics_M1': result.get('clicks_m1', 0),
            'Clics_M2': result.get('clicks_m2', 0),
            'Delta_Clics_%': format_percent_or_infinity(result.get('delta_clicks_percent', 0)),
            'Delta_Clics_Absoluto': result.get('delta_clicks_absolute', 0),
            'Impresiones_M1': result.get('impressions_m1', 0),
            'Impresiones_M2': result.get('impressions_m2', 0),
            'Delta_Impresiones_%': format_percent_or_infinity(result.get('delta_impressions_percent', 0)),
            'CTR_M1_%': f"{result.get('ctr_m1', 0):.2f}%",
            'CTR_M2_%': f"{result.get('ctr_m2', 0):.2f}%",
            'Delta_CTR_%': format_percent_or_infinity(result.get('delta_ctr_percent', 0)),
            'Posicion_M1': result.get('position_m1', ''),
            'Posicion_M2': result.get('position_m2', ''),
            'Delta_Posicion': result.get('delta_position_absolute', ''),
            'URL_Analizada': result.get('url', ''),
            'Posicion_Organica_Actual': result.get('site_position', 'No encontrado'),
            'Tiene_AI_Overview': 'Sí' if ai_analysis.get('has_ai_overview', False) else 'No',
            'Total_Elementos_AI': ai_analysis.get('total_elements', 0),
            'Dominio_como_Fuente_AI': 'Sí' if ai_analysis.get('domain_is_ai_source', False) else 'No',
            'Posicion_como_Fuente_AI': ai_analysis.get('domain_ai_source_position', ''),
            'Impact_Score': ai_analysis.get('impact_score', 0),
            'Timestamp_Analisis': pd.to_datetime(
                result.get('timestamp', 0), unit='s'
            ).strftime('%Y-%m-%d %H:%M:%S') if result.get('timestamp') else '',
            'País_Analizado': get_country_name(result.get('country_analyzed', '')) # NUEVO: País analizado
        }
        
        if ai_detected and len(ai_detected) > 0:
            for i, element in enumerate(ai_detected):
                row_data = base_data.copy()
                row_data.update({
                    'Tipo_Elemento_AI': element.get('type', ''),
                    'Posicion_Elemento_AI': element.get('position', ''),
                    'Longitud_Contenido': element.get('content_length', ''),
                    'Fuentes_Elemento': element.get('sources_count', ''),
                    'Elemento_Numero': i + 1
                })
                formatted_data.append(row_data)
        else:
            base_data.update({
                'Tipo_Elemento_AI': 'Sin elementos detectados',
                'Posicion_Elemento_AI': '',
                'Longitud_Contenido': '',
                'Fuentes_Elemento': '',
                'Elemento_Numero': ''
            })
            formatted_data.append(base_data)
    
    return formatted_data


def format_ai_summary_data(ai_overview_results):
    """
    Formatea el resumen de AI Overview para Excel según datos reales
    """
    if not ai_overview_results:
        return []
    
    summary = ai_overview_results.get('summary', {})
    candidates = ai_overview_results.get('candidates', {})
    
    summary_data = [
        {'Métrica': 'Total Keywords Analizadas', 'Valor': summary.get('total_keywords_analyzed', 0)},
        {'Métrica': 'Keywords con AI Overview', 'Valor': summary.get('keywords_with_ai_overview', 0)},
        {'Métrica': 'Keywords como Fuente AI', 'Valor': summary.get('keywords_as_ai_source', 0)},
        {'Métrica': 'Clics Perdidos Estimados', 'Valor': summary.get('total_estimated_clicks_lost', 0)},
        {'Métrica': 'Análisis Exitosos', 'Valor': summary.get('successful_analyses', 0)},
        {'Métrica': 'Total Candidatos Filtrados', 'Valor': candidates.get('total_candidates', 0) if candidates else 0},
        {'Métrica': 'Fecha Análisis', 'Valor': pd.Timestamp.fromtimestamp(summary.get('analysis_timestamp', pd.Timestamp.now().timestamp())).strftime('%Y-%m-%d %H:%M:%S')},
        {'Métrica': 'País Analizado', 'Valor': get_country_name(summary.get('country_analyzed', ''))} # NUEVO: País analizado
    ]
    
    return summary_data


def filter_keywords_by_position(keyword_data, position_range):
    """
    Filtra keywords por rango de posición específico
    """
    if not keyword_data:
        return []
    
    filtered_keywords = []
    for k in keyword_data:
        position = k.get('position_m1')
        if not isinstance(position, (int, float)):
            continue
            
        include_keyword = False
        if position_range == 'top3' and 1 <= position <= 3:
            include_keyword = True
        elif position_range == 'top10' and 4 <= position <= 10:
            include_keyword = True
        elif position_range == 'top20' and 11 <= position <= 20:
            include_keyword = True
        elif position_range == 'top20plus' and position > 20:
            include_keyword = True
            
        if include_keyword:
            filtered_keywords.append(k)
    
    # Ordenar por clics descendente
    filtered_keywords.sort(key=lambda x: x.get('clicks_m1', 0), reverse=True)
    return filtered_keywords


def create_keyword_position_sheets(writer, data, country_info, header_format):
    """
    Crea hojas separadas para cada rango de posición de keywords
    """
    ranges_config = [
        {'range': 'top3', 'title': 'Keywords Posiciones 1-3', 'description': 'Posiciones 1 a 3'},
        {'range': 'top10', 'title': 'Keywords Posiciones 4-10', 'description': 'Posiciones 4 a 10'},
        {'range': 'top20', 'title': 'Keywords Posiciones 11-20', 'description': 'Posiciones 11 a 20'},
        {'range': 'top20plus', 'title': 'Keywords Posiciones 20+', 'description': 'Posiciones 20 o más'}
    ]
    
    all_keywords = data.get('keyword_comparison_data', [])
    
    for range_config in ranges_config:
        range_name = range_config['range']
        sheet_name = range_config['title']
        description = range_config['description']
        
        # Filtrar keywords para este rango
        filtered_keywords = filter_keywords_by_position(all_keywords, range_name)
        
        # Crear filas para la hoja
        keyword_rows = []
        for k in filtered_keywords:
            keyword = k.get('keyword', '')
            # Obtener la URL específica donde posiciona esta keyword
            url = k.get('url', '')
            if not url and 'urls' in k:  # Si hay múltiples URLs, tomar la que posiciona mejor
                urls = k.get('urls', [])
                if urls:
                    # Ordenar por posición y tomar la mejor
                    urls.sort(key=lambda x: x.get('position', float('inf')))
                    url = urls[0].get('url', '')
            
            if 'clicks_m1' in k and 'clicks_m2' in k:  # Si hay datos de comparación
                keyword_rows.append({
                    'Keyword': keyword,
                    'URL que Posiciona': url,
                    'Clicks P1': k.get('clicks_m1', 0),
                    'Clicks P2': k.get('clicks_m2', 0),
                    'Impresiones P1': k.get('impressions_m1', 0),
                    'Impresiones P2': k.get('impressions_m2', 0),
                    'CTR P1 (%)': f"{k.get('ctr_m1', 0):.2f}%",
                    'CTR P2 (%)': f"{k.get('ctr_m2', 0):.2f}%",
                    'Posición Media P1': k.get('position_m1', ''),
                    'Posición Media P2': k.get('position_m2', '')
                })
            else:  # Si solo hay un período
                keyword_rows.append({
                    'Keyword': keyword,
                    'URL que Posiciona': url,
                    'Clicks P1': k.get('clicks_m1', 0),
                    'Clicks P2': '',
                    'Impresiones P1': k.get('impressions_m1', 0),
                    'Impresiones P2': '',
                    'CTR P1 (%)': f"{k.get('ctr_m1', 0):.2f}%",
                    'CTR P2 (%)': '',
                    'Posición Media P1': k.get('position_m1', ''),
                    'Posición Media P2': ''
                })
        
        # Si no hay keywords para este rango, añadir fila explicativa
        if not keyword_rows:
            keyword_rows = [{
                'Keyword': f'No hay keywords en {description.lower()} para {country_info}.',
                'URL que Posiciona': '',
                'Clicks P1': '', 'Clicks P2': '',
                'Impresiones P1': '', 'Impresiones P2': '',
                'CTR P1 (%)': '', 'CTR P2 (%)': '',
                'Posición Media P1': '', 'Posición Media P2': ''
            }]
        
        # Crear la hoja
        df_keywords_range = pd.DataFrame(keyword_rows)
        df_keywords_range.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Ajustar columnas de la hoja
        worksheet_range = writer.sheets[sheet_name]
        worksheet_range.set_column('A:A', 30)  # Keyword
        worksheet_range.set_column('B:B', 50)  # URL que Posiciona
        worksheet_range.set_column('C:J', 15)  # Métricas
        
        # Aplicar formato de cabecera
        for col_num, col_name in enumerate(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']):
            if col_num < len(df_keywords_range.columns):
                worksheet_range.write(f'{col_name}1', df_keywords_range.columns[col_num], header_format)


def generate_excel_from_data(data, ai_overview_data=None):
    """
    Genera un Excel con datos de páginas, keywords y AI Overview opcional.
    :param data: dict con claves 'pages', 'keywordStats', 'keyword_comparison_data', 'selected_country'
    :param ai_overview_data: dict retornado por el endpoint de AI Overview
    :return: BytesIO con el Excel generado
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Obtener información del país y determinar su origen
        selected_country = data.get('selected_country', '')
        
        if selected_country:
            country_info = get_country_name(selected_country)
            country_context = f"{country_info} (país principal del negocio)"
        else:
            country_info = 'Todos los países'
            country_context = 'Análisis global'
        
        # Formatos comunes
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })

        # ✅ MODIFICADO: Hoja 1 - Información del análisis (SIN información de AI Overview)
        info_data = [
            ['Parámetro', 'Valor'],
            ['País/Región analizada', country_info],
            ['Contexto del país', country_context],
            ['Fecha de generación', pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total páginas analizadas', len(data.get('pages', []))],
            ['Total keywords comparadas', len(data.get('keyword_comparison_data', []))],
            ['', ''], # Separador
            ['LÓGICA DE PAÍS', ''],
            ['Método de selección', 'Datos de Google Search Console'],
            ['Criterio', 'País con más clics (principal del negocio)'],
            ['Beneficio', 'Análisis desde mercado más importante'],
        ]
        
        # ❌ ELIMINADO: Todo el bloque de información de AI Overview se ha eliminado
        
        df_info = pd.DataFrame(info_data[1:], columns=info_data[0])
        df_info.to_excel(writer, sheet_name='Información del Análisis', index=False)
        
        # Ajustar columnas de la hoja de información
        worksheet_info = writer.sheets['Información del Análisis']
        worksheet_info.set_column('A:A', 30) # Parámetro
        worksheet_info.set_column('B:B', 50) # Valor
        
        # Aplicar formato especial a las secciones
        section_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E7E6E6',
            'border': 1
        })
        
        # ✅ MODIFICADO: Solo aplicar formato a la sección de país (ya no hay sección de AI Overview)
        for row_num, row_data in enumerate(info_data[1:], start=1):
            if row_data[0] in ['LÓGICA DE PAÍS']:
                worksheet_info.set_row(row_num, None, section_format)

        # Hoja 2: Resultados por URL (sin cambios)
        rows = []
        for p in data.get('pages', []):
            url = p.get('URL') or p.get('url')
            metrics = p.get('Metrics', []) or p.get('metrics', [])
            
            if len(metrics) >= 2:  # Si hay datos de comparación
                p1_metrics = metrics[1]  # Período principal
                p2_metrics = metrics[0]  # Período de comparación
                
                rows.append({
                    'URL': url,
                    'Clicks P1': p1_metrics.get('Clicks') or p1_metrics.get('clicks', 0),
                    'Clicks P2': p2_metrics.get('Clicks') or p2_metrics.get('clicks', 0),
                    'Impresiones P1': p1_metrics.get('Impressions') or p1_metrics.get('impressions', 0),
                    'Impresiones P2': p2_metrics.get('Impressions') or p2_metrics.get('impressions', 0),
                    'CTR P1 (%)': f"{((p1_metrics.get('CTR') or p1_metrics.get('ctr', 0)) * 100):.1f}%",
                    'CTR P2 (%)': f"{((p2_metrics.get('CTR') or p2_metrics.get('ctr', 0)) * 100):.1f}%",
                    'Posición Media P1': p1_metrics.get('Position') or p1_metrics.get('position', 0),
                    'Posición Media P2': p2_metrics.get('Position') or p2_metrics.get('position', 0)
                })
            else:  # Si solo hay un período
                p1_metrics = metrics[0] if metrics else {}
                rows.append({
                    'URL': url,
                    'Clicks P1': p1_metrics.get('Clicks') or p1_metrics.get('clicks', 0),
                    'Clicks P2': '',
                    'Impresiones P1': p1_metrics.get('Impressions') or p1_metrics.get('impressions', 0),
                    'Impresiones P2': '',
                    'CTR P1 (%)': f"{((p1_metrics.get('CTR') or p1_metrics.get('ctr', 0)) * 100):.1f}%",
                    'CTR P2 (%)': '',
                    'Posición Media P1': p1_metrics.get('Position') or p1_metrics.get('position', 0),
                    'Posición Media P2': ''
                })
        
        if not rows:
            rows = [{
                'URL': f'No hay datos para {country_info}.',
                'Clicks P1': '', 'Clicks P2': '',
                'Impresiones P1': '', 'Impresiones P2': '',
                'CTR P1 (%)': '', 'CTR P2 (%)': '',
                'Posición Media P1': '', 'Posición Media P2': ''
            }]
        
        df_pages = pd.DataFrame(rows)
        df_pages.to_excel(writer, sheet_name='Resultados por URL', index=False)
        
        # Ajustar columnas de la hoja de páginas
        worksheet_pages = writer.sheets['Resultados por URL']
        worksheet_pages.set_column('A:A', 50)  # URL
        worksheet_pages.set_column('B:I', 15)  # Métricas

        # Hoja 3: Keywords (sin cambios)
        keyword_rows = []
        for k in data.get('keyword_comparison_data', []):
            keyword = k.get('keyword', '')
            # Obtener la URL específica donde posiciona esta keyword
            url = k.get('url', '')
            if not url and 'urls' in k:  # Si hay múltiples URLs, tomar la que posiciona mejor
                urls = k.get('urls', [])
                if urls:
                    # Ordenar por posición y tomar la mejor
                    urls.sort(key=lambda x: x.get('position', float('inf')))
                    url = urls[0].get('url', '')
            
            if 'clicks_m1' in k and 'clicks_m2' in k:  # Si hay datos de comparación
                keyword_rows.append({
                    'Keyword': keyword,
                    'URL que Posiciona': url,  # Cambiado para claridad
                    'Clicks P1': k.get('clicks_m1', 0),
                    'Clicks P2': k.get('clicks_m2', 0),
                    'Impresiones P1': k.get('impressions_m1', 0),
                    'Impresiones P2': k.get('impressions_m2', 0),
                    'CTR P1 (%)': f"{k.get('ctr_m1', 0):.2f}%",
                    'CTR P2 (%)': f"{k.get('ctr_m2', 0):.2f}%",
                    'Posición Media P1': k.get('position_m1', ''),
                    'Posición Media P2': k.get('position_m2', '')
                })
            else:  # Si solo hay un período
                keyword_rows.append({
                    'Keyword': keyword,
                    'URL que Posiciona': url,  # Cambiado para claridad
                    'Clicks P1': k.get('clicks_m1', 0),
                    'Clicks P2': '',
                    'Impresiones P1': k.get('impressions_m1', 0),
                    'Impresiones P2': '',
                    'CTR P1 (%)': f"{k.get('ctr_m1', 0):.2f}%",
                    'CTR P2 (%)': '',
                    'Posición Media P1': k.get('position_m1', ''),
                    'Posición Media P2': ''
                })
        
        if not keyword_rows:
            keyword_rows = [{
                'Keyword': f'No hay datos de keywords para {country_info}.',
                'URL que Posiciona': '',
                'Clicks P1': '', 'Clicks P2': '',
                'Impresiones P1': '', 'Impresiones P2': '',
                'CTR P1 (%)': '', 'CTR P2 (%)': '',
                'Posición Media P1': '', 'Posición Media P2': ''
            }]
        
        df_keywords = pd.DataFrame(keyword_rows)
        df_keywords.to_excel(writer, sheet_name='Keywords', index=False)
        
        # Ajustar columnas de la hoja de keywords
        worksheet_keywords = writer.sheets['Keywords']
        worksheet_keywords.set_column('A:A', 30)  # Keyword
        worksheet_keywords.set_column('B:B', 50)  # URL que Posiciona
        worksheet_keywords.set_column('C:J', 15)  # Métricas

        # ✅ NUEVAS HOJAS: Keywords por rangos de posición
        create_keyword_position_sheets(writer, data, country_info, header_format)

        # ✅ PROCESAMIENTO DE HOJAS DE AI OVERVIEW (solo si hay datos)
        if ai_overview_data:
            # Hoja 4: AI Overview Summary (con país analizado mejorado)
            summary = ai_overview_data.get('summary', {})
            country_analyzed = summary.get('country_analyzed', selected_country)
            country_analyzed_name = get_country_name(country_analyzed) if country_analyzed else 'No especificado'
            
            summary_data = [
                {'Métrica': 'Total Keywords Analizadas', 'Valor': summary.get('total_keywords_analyzed', 0)},
                {'Métrica': 'Keywords con AI Overview', 'Valor': summary.get('keywords_with_ai_overview', 0)},
                {'Métrica': 'Tu dominio como Fuente AI', 'Valor': summary.get('keywords_as_ai_source', 0)},
                {'Métrica': 'Clics Perdidos Estimados', 'Valor': summary.get('total_estimated_clicks_lost', 0)},
                {'Métrica': 'Análisis Exitosos', 'Valor': summary.get('successful_analyses', 0)},
                {'Métrica': 'País Analizado', 'Valor': country_analyzed_name},  # ✅ MEJORADO: País analizado
                {'Métrica': 'Fecha Análisis', 'Valor': pd.Timestamp.fromtimestamp(
                    summary.get('analysis_timestamp', pd.Timestamp.now().timestamp())
                ).strftime('%Y-%m-%d %H:%M:%S')}
            ]
            
            df_ai_summary = pd.DataFrame(summary_data)
            df_ai_summary.to_excel(writer, sheet_name='AI Overview Summary', index=False)
            
            # Ajustar columnas de la hoja de resumen AI
            worksheet_ai_summary = writer.sheets['AI Overview Summary']
            worksheet_ai_summary.set_column('A:A', 30)  # Métrica
            worksheet_ai_summary.set_column('B:B', 25)  # Valor

            # Hoja 5: AI Overview Detallado (modificado para simplificar)
            ai_detailed_rows = []
            for result in ai_overview_data.get('results', []):
                ai_analysis = result.get('ai_analysis', {})
                keyword = result.get('keyword', '')
                url = result.get('url', '')
                
                # Crear fila simplificada sin los detalles de elementos
                ai_detailed_rows.append({
                    'Keyword': keyword,
                    'URL': url,
                    'Clics': result.get('clicks_m1', 0),
                    'Aparece AI Overview': 'Sí' if ai_analysis.get('has_ai_overview', False) else 'No',
                    'Posición Orgánica': result.get('site_position', 'No encontrado'),
                    'Tu dominio en AIO': 'Sí' if ai_analysis.get('domain_is_ai_source', False) else 'No',
                    'Posición en AIO': ai_analysis.get('domain_ai_source_position', '') or 'N/A'
                })
            
            if ai_detailed_rows:
                df_ai_detailed = pd.DataFrame(ai_detailed_rows)
                df_ai_detailed.to_excel(writer, sheet_name='AI Overview Detallado', index=False)
                
                # Ajustar columnas de la hoja de AI detallado
                worksheet_ai_detailed = writer.sheets['AI Overview Detallado']
                worksheet_ai_detailed.set_column('A:A', 30)  # Keyword
                worksheet_ai_detailed.set_column('B:B', 50)  # URL
                worksheet_ai_detailed.set_column('C:C', 10)  # Clics
                worksheet_ai_detailed.set_column('D:D', 18)  # Aparece AI Overview
                worksheet_ai_detailed.set_column('E:E', 18)  # Posición Orgánica
                worksheet_ai_detailed.set_column('F:F', 18)  # Tu dominio en AIO
                worksheet_ai_detailed.set_column('G:G', 15)  # Posición en AIO

        # ✅ NUEVA HOJA: AIO Keywords (al final del todo - SIEMPRE se genera)
        aio_rows = []
        
        if ai_overview_data and ai_overview_data.get('results'):
            # Si hay datos de AI Overview, procesarlos
            for result in ai_overview_data.get('results', []):
                keyword = result.get('keyword', '')
                ai_analysis = result.get('ai_analysis', {})
                genera_aio = 'Sí' if ai_analysis.get('has_ai_overview', False) else 'No'
                posicion_organica = result.get('site_position', 'No encontrado')
                aparece_mi_dominio = 'Sí' if ai_analysis.get('domain_is_ai_source', False) else 'No'
                posicion_en_aio = ai_analysis.get('domain_ai_source_position', '') or 'N/A'
                
                aio_rows.append({
                    'Keyword': keyword,
                    '¿Genera AIO?': genera_aio,
                    'Mi Posición Orgánica': posicion_organica,
                    '¿Aparece mi dominio en AIO?': aparece_mi_dominio,
                    'Posición en AIO': posicion_en_aio
                })
        else:
            # Si no hay datos de AI Overview, crear fila explicativa
            aio_rows.append({
                'Keyword': 'No se ha realizado análisis de AI Overview',
                '¿Genera AIO?': '',
                'Mi Posición Orgánica': '',
                '¿Aparece mi dominio en AIO?': '',
                'Posición en AIO': ''
            })
        
        # SIEMPRE crear la hoja, independientemente de si hay datos o no
        df_aio = pd.DataFrame(aio_rows)
        df_aio.to_excel(writer, sheet_name='AIO Keywords', index=False)
        
        # Ajustar columnas de la nueva hoja
        worksheet_aio = writer.sheets['AIO Keywords']
        worksheet_aio.set_column('A:A', 35)  # Keyword (más ancho)
        worksheet_aio.set_column('B:B', 18)  # ¿Genera AIO?
        worksheet_aio.set_column('C:C', 22)  # Mi Posición Orgánica
        worksheet_aio.set_column('D:D', 28)  # ¿Aparece mi dominio en AIO?
        worksheet_aio.set_column('E:E', 18)  # Posición en AIO
        
        # Aplicar formato de cabecera
        for col_num, col_name in enumerate(['A', 'B', 'C', 'D', 'E']):
            worksheet_aio.write(f'{col_name}1', df_aio.columns[col_num], header_format)

    output.seek(0)
    return output
