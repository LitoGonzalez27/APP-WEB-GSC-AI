import pandas as pd
from io import BytesIO
import logging
from services.country_config import get_country_name # Importar la función get_country_name

logger = logging.getLogger(__name__)

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

        # ✅ NUEVO: Hoja 1 - Executive Dashboard
        create_executive_dashboard(writer, data, ai_overview_data, header_format, country_info)

        # ✅ MODIFICADO: Hoja 2 - Información del análisis (SIN información de AI Overview)
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
                # ✅ CORREGIDO: Ordenar por fecha para determinar P1 (actual) y P2 (comparación)
                sorted_metrics = sorted(metrics, key=lambda x: x.get('StartDate', ''))
                p2_metrics = sorted_metrics[0]  # Período de comparación (más antiguo)
                p1_metrics = sorted_metrics[-1]  # Período principal (más reciente)
                
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

        # ✅ PROCESAMIENTO DE AIO: UNA SOLA HOJA CONSOLIDADA (solo si hay datos)
        if ai_overview_data:
            create_aio_consolidated_sheet(writer, ai_overview_data, header_format, selected_country)

        # ✅ NOTA: AIO Keywords ahora está integrado en la hoja consolidada AIO

    output.seek(0)
    return output


def create_executive_dashboard(writer, data, ai_overview_data, header_format, country_info):
    """
    Crea la hoja Executive Dashboard con métricas clave y insights automatizados
    """
    try:
        # Datos básicos
        pages = data.get('pages', [])
        keywords = data.get('keyword_comparison_data', [])
        
        # Calcular métricas ejecutivas
        total_clicks_p1 = sum(k.get('clicks_m1', 0) for k in keywords)
        total_impressions_p1 = sum(k.get('impressions_m1', 0) for k in keywords)
        avg_position_p1 = sum(k.get('position_m1', 0) for k in keywords if k.get('position_m1', 0) > 0) / max(len([k for k in keywords if k.get('position_m1', 0) > 0]), 1)
        avg_ctr_p1 = (total_clicks_p1 / total_impressions_p1 * 100) if total_impressions_p1 > 0 else 0
        
        # Comparación período anterior si existe
        has_comparison = any(k.get('clicks_m2') is not None for k in keywords)
        comparison_metrics = []
        
        if has_comparison:
            total_clicks_p2 = sum(k.get('clicks_m2', 0) for k in keywords)
            delta_clicks = ((total_clicks_p1 - total_clicks_p2) / max(total_clicks_p2, 1)) * 100
            total_impressions_p2 = sum(k.get('impressions_m2', 0) for k in keywords)
            delta_impressions = ((total_impressions_p1 - total_impressions_p2) / max(total_impressions_p2, 1)) * 100
            
            comparison_metrics = [
                ['', ''],
                ['COMPARACIÓN TEMPORAL', ''],
                ['Variación Clics (%)', f"{delta_clicks:+.1f}%"],
                ['Variación Impresiones (%)', f"{delta_impressions:+.1f}%"],
                ['Tendencia', 'Positiva' if delta_clicks > 0 else 'Negativa' if delta_clicks < 0 else 'Estable']
            ]
        
        # Top y Bottom performers
        top_keywords = sorted(keywords, key=lambda x: x.get('clicks_m1', 0), reverse=True)[:5]
        bottom_keywords = sorted([k for k in keywords if k.get('clicks_m1', 0) > 0], key=lambda x: x.get('clicks_m1', 0))[:5]
        
        # AI Overview metrics si están disponibles
        ai_metrics = []
        if ai_overview_data:
            summary = ai_overview_data.get('summary', {})
            ai_metrics = [
                ['', ''],
                ['AI OVERVIEW IMPACT', ''],
                ['Keywords con AIO', summary.get('keywords_with_ai_overview', 0)],
                ['Tu dominio mencionado', summary.get('keywords_as_ai_source', 0)],
                ['Clics perdidos estimados', summary.get('total_estimated_clicks_lost', 0)],
                ['Impacto en visibilidad', f"{(summary.get('keywords_as_ai_source', 0) / max(summary.get('keywords_with_ai_overview', 1), 1) * 100):.1f}%"]
            ]
        
        # Estructurar datos del dashboard
        dashboard_data = [
            ['Métrica', 'Valor'],
            ['MÉTRICAS PRINCIPALES', ''],
            ['País analizado', country_info],
            ['Total Keywords', len(keywords)],
            ['Total URLs', len(pages)],
            ['Total Clics', f"{total_clicks_p1:,}"],
            ['Total Impresiones', f"{total_impressions_p1:,}"],
            ['CTR Promedio (%)', f"{avg_ctr_p1:.2f}%"],
            ['Posición Media', f"{avg_position_p1:.1f}"],
        ] + comparison_metrics + ai_metrics + [
            ['', ''],
            ['TOP 5 KEYWORDS (por clics)', ''],
        ]
        
        # Añadir top keywords
        for i, kw in enumerate(top_keywords, 1):
            dashboard_data.append([f"{i}. {kw.get('keyword', '')[:50]}", f"{kw.get('clicks_m1', 0)} clics"])
        
        dashboard_data.extend([
            ['', ''],
            ['KEYWORDS CON MENOR RENDIMIENTO', ''],
        ])
        
        # Añadir bottom keywords
        for i, kw in enumerate(bottom_keywords, 1):
            dashboard_data.append([f"{i}. {kw.get('keyword', '')[:50]}", f"{kw.get('clicks_m1', 0)} clics"])
        
        # Crear DataFrame y exportar
        df_dashboard = pd.DataFrame(dashboard_data[1:], columns=dashboard_data[0])
        df_dashboard.to_excel(writer, sheet_name='📊 Executive Dashboard', index=False)
        
        # Formatear hoja
        worksheet = writer.sheets['📊 Executive Dashboard']
        worksheet.set_column('A:A', 40)  # Métrica
        worksheet.set_column('B:B', 20)  # Valor
        
        # Aplicar formatos especiales
        workbook = writer.book
        section_format = workbook.add_format({'bold': True, 'bg_color': '#E7E6E6', 'border': 1})
        
        # Formatear secciones
        section_rows = []
        for i, row in enumerate(dashboard_data[1:], start=1):
            if row[0] in ['MÉTRICAS PRINCIPALES', 'COMPARACIÓN TEMPORAL', 'AI OVERVIEW IMPACT', 'TOP 5 KEYWORDS (por clics)', 'KEYWORDS CON MENOR RENDIMIENTO']:
                section_rows.append(i)
        
        for row_num in section_rows:
            worksheet.set_row(row_num, None, section_format)
        
        # Aplicar header format
        for col_num, col_name in enumerate(['A', 'B']):
            worksheet.write(f'{col_name}1', df_dashboard.columns[col_num], header_format)
            
    except Exception as e:
        logger.error(f"Error creando Executive Dashboard: {e}")


def create_aio_consolidated_sheet(writer, ai_overview_data, header_format, selected_country):
    """
    Crea UNA sola hoja consolidada con todo el análisis de AI Overview
    Estructura: 1) Resumen ejecutivo 2) Tipología 3) Posiciones 4) Tabla completa keywords
    """
    if not ai_overview_data or not ai_overview_data.get('results'):
        return
    
    try:
        keyword_results = ai_overview_data.get('results', [])
        summary = ai_overview_data.get('summary', {})
        country_analyzed = summary.get('country_analyzed', selected_country)
        country_analyzed_name = get_country_name(country_analyzed) if country_analyzed else 'No especificado'
        
        # ===== CALCULAR DATOS DE TIPOLOGÍA =====
        categories = {
            'short_tail': {'label': 'Short Tail', 'description': '1 word', 'min': 1, 'max': 1, 'total': 0, 'withAI': 0},
            'middle_tail': {'label': 'Middle Tail', 'description': '2-3 words', 'min': 2, 'max': 3, 'total': 0, 'withAI': 0},
            'long_tail': {'label': 'Long Tail', 'description': '4-8 words', 'min': 4, 'max': 8, 'total': 0, 'withAI': 0},
            'super_long_tail': {'label': 'Super Long Tail', 'description': '9+ words', 'min': 9, 'max': float('inf'), 'total': 0, 'withAI': 0}
        }
        
        position_ranges = {
            '1-3': {'label': '1 - 3', 'min': 1, 'max': 3, 'count': 0},
            '4-6': {'label': '4 - 6', 'min': 4, 'max': 6, 'count': 0},
            '7-9': {'label': '7 - 9', 'min': 7, 'max': 9, 'count': 0},
            '10+': {'label': '10 or more', 'min': 10, 'max': float('inf'), 'count': 0}
        }
        
        total_with_aio_position = 0
        total_with_ai_positions = 0
        
        # Procesar keywords para tipología y posiciones
        for result in keyword_results:
            keyword = result.get('keyword', '')
            word_count = len(keyword.strip().split()) if keyword.strip() else 0
            has_ai = result.get('ai_analysis', {}).get('has_ai_overview', False)
            aio_position = result.get('ai_analysis', {}).get('domain_ai_source_position')
            
            # Tipología
            for category in categories.values():
                if category['min'] <= word_count <= category['max']:
                    category['total'] += 1
                    if has_ai:
                        category['withAI'] += 1
                    break
            
            # Posiciones
            if has_ai:
                total_with_ai_positions += 1
                if aio_position and aio_position > 0:
                    total_with_aio_position += 1
                    for range_data in position_ranges.values():
                        if range_data['min'] <= aio_position <= range_data['max']:
                            range_data['count'] += 1
                            break
        
        total_keywords = len(keyword_results)
        total_with_ai = sum(cat['withAI'] for cat in categories.values())
        
        # ===== ESTRUCTURA DE LA HOJA CONSOLIDADA =====
        
        # 1) RESUMEN EJECUTIVO
        executive_section = [
            ['SECCIÓN', 'VALOR'],
            ['=== RESUMEN EJECUTIVO AI OVERVIEW ===', ''],
            ['Total Keywords Analizadas', summary.get('total_keywords_analyzed', 0)],
            ['Keywords con AI Overview', summary.get('keywords_with_ai_overview', 0)],
            ['Tu dominio como Fuente AI', summary.get('keywords_as_ai_source', 0)],
            ['Clics Perdidos Estimados', summary.get('total_estimated_clicks_lost', 0)],
            ['País Analizado', country_analyzed_name],
            ['Fecha Análisis', pd.Timestamp.fromtimestamp(summary.get('analysis_timestamp', pd.Timestamp.now().timestamp())).strftime('%Y-%m-%d %H:%M:%S')],
            ['', ''],
        ]
        
        # 2) TIPOLOGÍA DE KEYWORDS
        tipologia_section = [
            ['=== TIPOLOGÍA DE KEYWORDS ===', ''],
            ['Tipo de Keyword', 'Keywords con AIO'],
        ]
        
        for category in categories.values():
            percentage = (category['withAI'] / total_with_ai * 100) if total_with_ai > 0 else 0
            tipologia_section.append([f"{category['label']} ({category['description']})", f"{category['withAI']} ({percentage:.1f}%)"])
        
        tipologia_section.extend([
            ['--- Resumen ---', ''],
            ['Total con AI Overview', total_with_ai],
            ['Total sin AI Overview', total_keywords - total_with_ai],
            ['', ''],
        ])
        
        # 3) POSICIONES EN AIO
        posiciones_section = [
            ['=== POSICIONES EN AI OVERVIEW ===', ''],
            ['Rango de Posición', 'Keywords'],
        ]
        
        for range_data in position_ranges.values():
            if range_data['count'] > 0:
                percentage = (range_data['count'] / total_with_aio_position * 100) if total_with_aio_position > 0 else 0
                posiciones_section.append([range_data['label'], f"{range_data['count']} ({percentage:.1f}%)"])
        
        if total_with_aio_position == 0:
            posiciones_section.append(['No hay menciones', 'Tu dominio no aparece como fuente'])
        else:
            posiciones_section.extend([
                ['--- Resumen ---', ''],
                ['Total menciones', total_with_aio_position],
                ['Con AIO sin mención', total_with_ai_positions - total_with_aio_position],
            ])
        
        posiciones_section.extend([['', ''], ['', '']])  # Espaciado
        
        # 4) TABLA COMPLETA DE KEYWORDS
        keywords_section = [
            ['=== DETALLE COMPLETO POR KEYWORD ===', ''],
            ['Keyword', 'With AIO', 'Organic Position', 'Your Domain in AIO', 'AIO Position'],
        ]
        
        for result in keyword_results:
            ai_analysis = result.get('ai_analysis', {})
            keyword = result.get('keyword', '')
            has_ai_overview = 'Sí' if ai_analysis.get('has_ai_overview', False) else 'No'
            organic_position = result.get('site_position', 'No encontrado')
            domain_in_aio = 'Sí' if ai_analysis.get('domain_is_ai_source', False) else 'No'
            aio_position = ai_analysis.get('domain_ai_source_position', '') or 'N/A'
            
            keywords_section.append([keyword, has_ai_overview, organic_position, domain_in_aio, aio_position])
        
        # ===== COMBINAR TODAS LAS SECCIONES =====
        # Normalizar todas las secciones a 5 columnas para que coincidan con la tabla final
        
        def normalize_to_5_columns(section):
            normalized = []
            for row in section:
                if len(row) < 5:
                    # Rellenar con strings vacíos hasta 5 columnas
                    row_normalized = row + [''] * (5 - len(row))
                else:
                    row_normalized = row[:5]  # Truncar si tiene más de 5
                normalized.append(row_normalized)
            return normalized
        
        # Normalizar cada sección
        executive_normalized = normalize_to_5_columns(executive_section)
        tipologia_normalized = normalize_to_5_columns(tipologia_section)
        posiciones_normalized = normalize_to_5_columns(posiciones_section)
        keywords_normalized = normalize_to_5_columns(keywords_section)
        
        # Combinar todas las secciones
        all_data = executive_normalized + tipologia_normalized + posiciones_normalized + keywords_normalized
        
        # Crear DataFrame y exportar
        df_aio = pd.DataFrame(all_data[1:], columns=all_data[0])
        df_aio.to_excel(writer, sheet_name='🤖 AI Overview Analysis', index=False)
        
        # Formatear hoja
        worksheet = writer.sheets['🤖 AI Overview Analysis']
        worksheet.set_column('A:A', 45)  # Más ancho para keywords
        worksheet.set_column('B:B', 18)  
        worksheet.set_column('C:C', 18)  
        worksheet.set_column('D:D', 20)  
        worksheet.set_column('E:E', 15)  
        
        # Aplicar formatos especiales
        workbook = writer.book
        section_format = workbook.add_format({'bold': True, 'bg_color': '#FFE6E6', 'border': 1})
        
        # Encontrar filas de sección para formatear
        section_rows = []
        for i, row in enumerate(all_data[1:], start=1):
            if row[0].startswith('===') and row[0].endswith('==='):
                section_rows.append(i)
        
        for row_num in section_rows:
            worksheet.set_row(row_num, None, section_format)
        
        # Aplicar header format
        for col_num, col_name in enumerate(['A', 'B', 'C', 'D', 'E']):
            if col_num < len(df_aio.columns):
                worksheet.write(f'{col_name}1', df_aio.columns[col_num], header_format)
                
    except Exception as e:
        logger.error(f"Error creando hoja consolidada AIO: {e}")
        # No fallar silenciosamente, pero continuar con el resto del Excel
