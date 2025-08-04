import pandas as pd
from io import BytesIO
import logging
from urllib.parse import urlparse
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
        # ❌ ELIMINADO: Clics Perdidos Estimados (no se requiere)
        {'Métrica': 'Análisis Exitosos', 'Valor': summary.get('successful_analyses', 0)},
        {'Métrica': 'Total Candidatos Filtrados', 'Valor': candidates.get('total_candidates', 0) if candidates else 0},
        {'Métrica': 'Fecha Análisis', 'Valor': pd.Timestamp.fromtimestamp(summary.get('analysis_timestamp', pd.Timestamp.now().timestamp())).strftime('%Y-%m-%d')},
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
        {'range': 'top20', 'title': 'Keywords Posiciones 11-20', 'description': 'Posiciones 11 a 20'}
        # ❌ ELIMINADO: 'top20plus' (Keywords Posiciones 20+) - no se requiere
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
            
            # 🚀 MEJORADO: Obtener la URL específica donde posiciona esta keyword
            url = k.get('url', '')
            
            # Si no hay URL directa, buscar en la estructura de URLs del análisis
            if not url:
                # Intentar obtener de la estructura de páginas si está disponible
                if 'page_url' in k:
                    url = k.get('page_url', '')
                elif 'urls' in k and k['urls']:
                    # Si hay múltiples URLs, tomar la que posiciona mejor
                    urls = k.get('urls', [])
                    if urls:
                        urls.sort(key=lambda x: x.get('position', float('inf')))
                        url = urls[0].get('url', '')
                elif 'landing_page' in k:
                    url = k.get('landing_page', '')
                else:
                    # Como último recurso, usar la keyword para buscar su URL en los datos del análisis
                    # Esta información debería estar disponible desde el endpoint /api/url-keywords
                    url = f"[URL específica para: {keyword}]"
            
            # Si aún no tenemos URL específica, mostrar que es análisis de propiedad completa
            if not url or url == '':
                url = "sc-domain:acertare.com (propiedad completa)"
            
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

        # ❌ ELIMINADO: Executive Dashboard (no se requiere)

        # ✅ MODIFICADO: Hoja 2 - Información del análisis (CON información de AI Overview solicitada)
        info_data = [
            ['Parámetro', 'Valor'],
            ['País/Región analizada', country_info],
            ['Contexto del país', country_context],
            ['Fecha de generación', pd.Timestamp.now().strftime('%Y-%m-%d')],
            ['Total páginas analizadas', len(data.get('pages', []))],
            ['Total keywords comparadas', len(data.get('keyword_comparison_data', []))],
            ['', ''], # Separador
            ['LÓGICA DE PAÍS', ''],
            ['Método de selección', 'Datos de Google Search Console'],
            ['Criterio', 'País con más clics (principal del negocio)'],
            ['Beneficio', 'Análisis desde mercado más importante'],
        ]
        
        # 🚀 NUEVO: Añadir información de AI Overview si está disponible
        if ai_overview_data and ai_overview_data.get('results'):
            keyword_results_aio = ai_overview_data.get('results', [])
            total_keywords_aio = len([r for r in keyword_results_aio if r.get('ai_analysis', {}).get('has_ai_overview', False)])
            
            info_data.extend([
                ['', ''], # Separador
                ['ANÁLISIS AI OVERVIEW', ''],
                ['Keywords con AIO', total_keywords_aio],
                ['Total Keywords en el análisis', len(keyword_results_aio)],
                ['Porcentaje con AI Overview', f"{(total_keywords_aio / len(keyword_results_aio) * 100):.1f}%" if len(keyword_results_aio) > 0 else "0.0%"]
            ])
        
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

        # Hoja 3: Keywords consolidadas (mejores de cada URL)
        keyword_rows = []
        for k in data.get('keyword_comparison_data', []):
            keyword = k.get('keyword', '')
            
            # 🚀 MEJORADO: Obtener la URL específica donde posiciona esta keyword
            url = k.get('url', '')
            
            # Si no hay URL directa, buscar en la estructura de URLs del análisis
            if not url:
                # Intentar obtener de la estructura de páginas si está disponible
                if 'page_url' in k:
                    url = k.get('page_url', '')
                elif 'urls' in k and k['urls']:
                    # Si hay múltiples URLs, tomar la que posiciona mejor
                    urls = k.get('urls', [])
                    if urls:
                        urls.sort(key=lambda x: x.get('position', float('inf')))
                        url = urls[0].get('url', '')
                elif 'landing_page' in k:
                    url = k.get('landing_page', '')
                else:
                    # Como último recurso, usar la keyword para buscar su URL en los datos del análisis
                    url = f"[URL específica para: {keyword}]"
            
            # Si aún no tenemos URL específica, mostrar que es análisis de propiedad completa
            if not url or url == '':
                url = "sc-domain:acertare.com (propiedad completa)"
            
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
                    'URL que Posiciona': url,  # Ya mejorado arriba
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

        # ✅ PROCESAMIENTO DE AIO: Hojas de AI Overview (solo si hay datos)
        if ai_overview_data:
            # 1. Hoja de análisis principal (sin competidores)
            create_aio_consolidated_sheet(writer, ai_overview_data, header_format, selected_country)
            
            # 2. Hoja específica de competidores (refleja exactamente la info del SaaS)
            create_competitors_analysis_sheet(writer, ai_overview_data, header_format)

    output.seek(0)
    return output


# ❌ FUNCIÓN ELIMINADA: create_executive_dashboard (no se requiere)


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
        
        # ✅ MEJORADO: Si no hay país específico, intentar obtener país principal del negocio
        if not country_analyzed:
            # Intentar obtener el país principal desde los datos AI Overview
            main_country = summary.get('main_business_country')
            if main_country:
                country_analyzed = main_country
                
        country_analyzed_name = get_country_name(country_analyzed) if country_analyzed else 'País principal del negocio detectado automáticamente'
        
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
            ['RESUMEN EJECUTIVO AI OVERVIEW', ''],
            ['Total Keywords Analizadas', summary.get('total_keywords_analyzed', 0)],
            ['Keywords con AI Overview', summary.get('keywords_with_ai_overview', 0)],
            ['Tu dominio como Fuente AI', summary.get('keywords_as_ai_source', 0)],
            # ❌ ELIMINADO: Clics Perdidos Estimados (no se requiere)
            ['País Analizado', country_analyzed_name],
            ['Fecha Análisis', pd.Timestamp.fromtimestamp(summary.get('analysis_timestamp', pd.Timestamp.now().timestamp())).strftime('%Y-%m-%d')],
            ['', ''],
        ]
        
        # 2) TIPOLOGÍA DE KEYWORDS
        tipologia_section = [
            ['TIPOLOGÍA DE KEYWORDS', ''],
            ['Tipo de Keyword', 'Keywords con AIO'],
        ]
        
        for category in categories.values():
            percentage = (category['withAI'] / total_with_ai * 100) if total_with_ai > 0 else 0
            tipologia_section.append([f"{category['label']} ({category['description']})", f"{category['withAI']} ({percentage:.1f}%)"])
        
        tipologia_section.extend([
            ['Resumen Tipología', ''],
            ['Total con AI Overview', total_with_ai],
            ['Total sin AI Overview', total_keywords - total_with_ai],
            ['', ''],
        ])
        
        # 3) POSICIONES EN AIO
        posiciones_section = [
            ['POSICIONES EN AI OVERVIEW', ''],
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
                ['Resumen Posiciones', ''],
                ['Total menciones', total_with_aio_position],
                ['Con AIO sin mención', total_with_ai_positions - total_with_aio_position],
            ])
        
        posiciones_section.extend([['', ''], ['', '']])  # Espaciado
        
        # 4) TABLA COMPLETA DE KEYWORDS CON DATOS EXPANDIDOS
        keywords_section = [
            ['DETALLE COMPLETO POR KEYWORD', '', '', '', '', '', '', ''],
            ['Keyword', 'With AIO', 'Your Domain in AIO', 'AIO Position', 'Organic Position', 'Clicks (P1)', 'Impressions (P1)', 'CTR (P1)'],
        ]
        
        for result in keyword_results:
            ai_analysis = result.get('ai_analysis', {})
            keyword = result.get('keyword', '')
            has_ai_overview = 'Sí' if ai_analysis.get('has_ai_overview', False) else 'No'
            organic_position = result.get('site_position', 'No encontrado')
            domain_in_aio = 'Sí' if ai_analysis.get('domain_is_ai_source', False) else 'No'
            aio_position = ai_analysis.get('domain_ai_source_position', '') or 'N/A'
            
            # ✅ NUEVO: Datos de tráfico
            clicks_p1 = result.get('clicks_p1') or result.get('clicks_m1', 0)
            impressions_p1 = result.get('impressions_p1') or result.get('impressions_m1', 0)
            ctr_p1 = result.get('ctr_p1') or result.get('ctr_m1', 0)
            if isinstance(ctr_p1, (int, float)) and ctr_p1 > 0:
                ctr_formatted = f"{(ctr_p1 * 100):.2f}%" if ctr_p1 < 1 else f"{ctr_p1:.2f}%"
            else:
                ctr_formatted = "0.00%"
            
            # ❌ ELIMINADO: Datos de competidores en AIO (no requeridos en página de análisis)
            
            keywords_section.append([
                keyword, 
                has_ai_overview, 
                domain_in_aio, 
                aio_position, 
                organic_position,
                clicks_p1,
                impressions_p1,
                ctr_formatted
            ])
        
        # ===== COMBINAR TODAS LAS SECCIONES =====
        # Normalizar todas las secciones a 8 columnas para que coincidan con la tabla final sin competidores
        
        def normalize_to_8_columns(section):
            normalized = []
            for row in section:
                if len(row) < 8:
                    # Rellenar con strings vacíos hasta 8 columnas
                    row_normalized = row + [''] * (8 - len(row))
                else:
                    row_normalized = row[:8]  # Truncar si tiene más de 8
                normalized.append(row_normalized)
            return normalized
        
        # Normalizar cada sección
        executive_normalized = normalize_to_8_columns(executive_section)
        tipologia_normalized = normalize_to_8_columns(tipologia_section)
        posiciones_normalized = normalize_to_8_columns(posiciones_section)
        keywords_normalized = normalize_to_8_columns(keywords_section)
        
        # Combinar todas las secciones
        all_data = executive_normalized + tipologia_normalized + posiciones_normalized + keywords_normalized
        
        # Crear DataFrame y exportar
        df_aio = pd.DataFrame(all_data[1:], columns=all_data[0])
        df_aio.to_excel(writer, sheet_name='AI Overview Analysis', index=False)
        
        # Formatear hoja expandida (sin columnas de competidores)
        worksheet = writer.sheets['AI Overview Analysis']
        worksheet.set_column('A:A', 35)  # Keyword
        worksheet.set_column('B:B', 12)  # With AIO
        worksheet.set_column('C:C', 18)  # Your Domain in AIO
        worksheet.set_column('D:D', 15)  # AIO Position
        worksheet.set_column('E:E', 18)  # Organic Position
        worksheet.set_column('F:F', 12)  # Clicks P1
        worksheet.set_column('G:G', 15)  # Impressions P1
        worksheet.set_column('H:H', 12)  # CTR P1
        
        # Aplicar formatos especiales
        workbook = writer.book
        section_format = workbook.add_format({'bold': True, 'bg_color': '#FFE6E6', 'border': 1})
        
        # Encontrar filas de sección para formatear
        section_rows = []
        for i, row in enumerate(all_data[1:], start=1):
            if row[0] in ['RESUMEN EJECUTIVO AI OVERVIEW', 'TIPOLOGÍA DE KEYWORDS', 'POSICIONES EN AI OVERVIEW', 'DETALLE COMPLETO POR KEYWORD']:
                section_rows.append(i)
        
        for row_num in section_rows:
            worksheet.set_row(row_num, None, section_format)
        
        # Aplicar header format para las 8 columnas
        column_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        for col_num, col_name in enumerate(column_letters):
            if col_num < len(df_aio.columns):
                worksheet.write(f'{col_name}1', df_aio.columns[col_num], header_format)
        
        # ❌ ELIMINADO: La hoja de competidores se crea desde la función principal
        
        # ❌ ELIMINADO: AIO Impact Analysis (no se requiere)
                
    except Exception as e:
        logger.error(f"Error creando hoja consolidada AIO: {e}")
        # No fallar silenciosamente, pero continuar con el resto del Excel


def create_competitors_analysis_sheet(writer, ai_overview_data, header_format):
    """
    Crea una hoja específica para análisis detallado de competidores en AI Overview
    Refleja exactamente la información disponible en el SaaS:
    - Visibilidad de competidores (%)
    - Menciones en AI Overview
    - Posición media
    - Tabla detallada de competidores
    """
    if not ai_overview_data or not ai_overview_data.get('results'):
        return
    
    try:
        keyword_results = ai_overview_data.get('results', [])
        
        # 🔍 DEBUG: Log para investigar estructura de datos
        logger.info(f"[COMPETITORS DEBUG] Total keywords analizadas: {len(keyword_results)}")
        logger.info(f"[COMPETITORS DEBUG] Estructura ai_overview_data keys: {list(ai_overview_data.keys())}")
        
        # 🚀 MEJORA: Verificar si tenemos competitor_analysis ya procesado en summary
        summary = ai_overview_data.get('summary', {})
        competitor_analysis_processed = summary.get('competitor_analysis', [])
        
        logger.info(f"[COMPETITORS DEBUG] Summary keys: {list(summary.keys())}")
        logger.info(f"[COMPETITORS DEBUG] Competitor analysis procesado: {len(competitor_analysis_processed)} dominios")
        
        if competitor_analysis_processed:
            logger.info(f"[COMPETITORS DEBUG] Datos procesados encontrados: {competitor_analysis_processed}")
        else:
            logger.warning(f"[COMPETITORS DEBUG] No se encontró competitor_analysis en summary")
        
        # 🚀 MEJORADO: Usar datos procesados de competitor_analysis si están disponibles
        if competitor_analysis_processed:
            logger.info("[COMPETITORS DEBUG] Usando datos ya procesados de competitor_analysis")
            
            # Convertir formato del backend al formato esperado por el Excel
            competitors_data = {}
            for comp_data in competitor_analysis_processed:
                domain = comp_data.get('domain', '')
                if domain:
                    competitors_data[domain] = {
                        'total_appearances': comp_data.get('mentions', 0),
                        'avg_position': comp_data.get('average_position', 0) or 0,
                        'visibility_percentage': comp_data.get('visibility_percentage', 0)
                    }
            
            # Ordenar competidores por número de apariciones (más relevantes primero)
            sorted_competitors = sorted(competitors_data.items(), 
                                      key=lambda x: x[1]['total_appearances'], 
                                      reverse=True)
            
            logger.info(f"[COMPETITORS DEBUG] Procesados {len(sorted_competitors)} competidores desde summary")
            
        else:
            # Fallback: Procesamiento manual (código original)
            logger.info("[COMPETITORS DEBUG] No hay datos procesados, usando procesamiento manual")
            competitors_data = {}
            
            for result in keyword_results:
                keyword = result.get('keyword', '')
                ai_analysis = result.get('ai_analysis', {})
                
                if ai_analysis.get('has_ai_overview'):
                    # 🔍 DEBUG: Investigar todas las posibles estructuras de fuentes
                    logger.info(f"[COMPETITORS DEBUG] Keyword '{keyword}' - AI Analysis keys: {list(ai_analysis.keys())}")
                    
                    # 🎯 ESTRUCTURA REAL: Las fuentes están en debug_info.references_found
                    debug_info = ai_analysis.get('debug_info', {})
                    references_found = debug_info.get('references_found', [])
                    logger.info(f"[COMPETITORS DEBUG] Keyword '{keyword}' - references_found count: {len(references_found)}")
                    
                    # Convertir references_found al formato esperado
                    ai_sources = []
                    if references_found:
                        for ref in references_found:
                            # Extraer dominio del link
                            link = ref.get('link', '')
                            if link:
                                # Extraer dominio de la URL
                                try:
                                    parsed = urlparse(link)
                                    domain = parsed.netloc.replace('www.', '')
                                    
                                    ai_sources.append({
                                        'domain': domain,
                                        'position': ref.get('index', 0) + 1,  # +1 porque index empieza en 0
                                        'link': link,
                                        'source_name': ref.get('source', ''),
                                        'title': ref.get('title', '')
                                    })
                                except Exception as e:
                                    logger.warning(f"[COMPETITORS DEBUG] Error parsing URL {link}: {e}")
                                    continue
                    
                    # 🔍 DEBUG: Log específico para cada keyword con AIO
                    if ai_sources:
                        logger.info(f"[COMPETITORS DEBUG] Keyword '{keyword}' tiene {len(ai_sources)} fuentes AI: {ai_sources}")
                    else:
                        logger.warning(f"[COMPETITORS DEBUG] Keyword '{keyword}' con AIO pero SIN fuentes - ai_analysis completo: {ai_analysis}")
                    
                    for source in ai_sources:
                        # 🔍 DEBUG: Log estructura completa de cada fuente
                        logger.info(f"[COMPETITORS DEBUG] Fuente completa: {source}")
                        
                        domain = source.get('domain', '')
                        position = source.get('position', 0)
                        source_name = source.get('source_name', '')
                        
                        # 🔍 DEBUG: Log cada fuente encontrada
                        logger.info(f"[COMPETITORS DEBUG] Fuente procesada: {domain} ({source_name}) (posición: {position})")
                        
                        if domain and domain != result.get('site_domain', ''):  # Excluir dominio propio
                            if domain not in competitors_data:
                                competitors_data[domain] = {
                                    'total_appearances': 0,
                                    'total_position_sum': 0,
                                    'keywords': [],
                                    'positions': [],
                                    'avg_position': 0
                                }
                            
                            competitors_data[domain]['total_appearances'] += 1
                            if position and position > 0:
                                competitors_data[domain]['total_position_sum'] += position
                                competitors_data[domain]['positions'].append(position)
                            
                            competitors_data[domain]['keywords'].append({
                                'keyword': keyword,
                                'position': position or 'N/A'
                            })
        
            # Calcular métricas finales para cada competidor
            for domain, data in competitors_data.items():
                if data['positions']:
                    data['avg_position'] = data['total_position_sum'] / len(data['positions'])
                else:
                    data['avg_position'] = 0
            
            # 🔍 DEBUG: Log final de competidores encontrados
            logger.info(f"[COMPETITORS DEBUG] Competidores únicos encontrados: {len(competitors_data)}")
            for domain, data in competitors_data.items():
                logger.info(f"[COMPETITORS DEBUG] - {domain}: {data['total_appearances']} apariciones")
            
            # Ordenar competidores por número de apariciones (más relevantes primero)
            sorted_competitors = sorted(competitors_data.items(), 
                                      key=lambda x: x[1]['total_appearances'], 
                                      reverse=True)
            
            logger.info(f"[COMPETITORS DEBUG] Procesamiento manual completado: {len(sorted_competitors)} competidores")
        
        # ===== ESTRUCTURA DE LA HOJA DE COMPETIDORES =====
        # 🚀 NUEVO: Solo información solicitada por el usuario
        
        # 1) RESUMEN DE COMPETIDORES (Dominio, apariciones, posición promedio, presencia %)
        competitors_summary = [
            ['RESUMEN COMPETIDORES', '', '', ''],
            ['Dominio', 'Apariciones en AIO', 'Posición Promedio', 'Presencia (%)'],
        ]
        
        # Generar datos de resumen
        total_keywords_with_aio = len([r for r in keyword_results if r.get('ai_analysis', {}).get('has_ai_overview')])
        
        for domain, data in sorted_competitors[:10]:  # Top 10 competidores
            presence_percentage = (data['total_appearances'] / total_keywords_with_aio * 100) if total_keywords_with_aio > 0 else 0
            avg_pos_formatted = f"{data['avg_position']:.1f}" if data['avg_position'] > 0 else 'N/A'
            
            competitors_summary.append([
                domain,
                data['total_appearances'],
                avg_pos_formatted,
                f"{presence_percentage:.1f}%"
            ])
        
        # Espaciado
        competitors_summary.extend([['', '', '', ''], ['', '', '', '']])
        
        # 2) TABLA IGUAL A "DETAILS OF KEYWORDS WITH AIO"
        # Obtener dominios de competidores para las columnas dinámicas
        top_competitor_domains = [domain for domain, _ in sorted_competitors[:5]]  # Top 5 para no hacer la tabla muy ancha
        
        # Crear headers de la tabla similar al frontend
        aio_table_headers = ['Keyword', 'Your Domain in AIO', 'Your Position in AIO']
        
        # Añadir columnas para cada competidor
        for domain in top_competitor_domains:
            truncated_domain = domain[:15] + '...' if len(domain) > 15 else domain
            aio_table_headers.extend([f"{truncated_domain} in AIO", f"Position of {truncated_domain}"])
        
        # Crear la tabla
        aio_table_section = [
            ['DETAILS OF KEYWORDS WITH AIO', ''] + [''] * (len(aio_table_headers) - 2),
            aio_table_headers
        ]
        
        # Llenar datos de la tabla - solo keywords que tienen AI Overview
        keywords_with_aio = [result for result in keyword_results if result.get('ai_analysis', {}).get('has_ai_overview', False)]
        
        for result in keywords_with_aio:
            keyword = result.get('keyword', '')
            ai_analysis = result.get('ai_analysis', {})
            
            # Datos del dominio principal
            your_domain_in_aio = 'Yes' if ai_analysis.get('domain_is_ai_source', False) else 'No'
            your_position = ai_analysis.get('domain_ai_source_position', 'N/A')
            if your_position == '' or your_position is None:
                your_position = 'N/A'
            
            # Crear fila base
            row_data = [keyword, your_domain_in_aio, your_position]
            
            # Añadir datos de competidores
            debug_info = ai_analysis.get('debug_info', {})
            references_found = debug_info.get('references_found', [])
            
            # Crear diccionario de dominios competidores y sus posiciones para esta keyword
            competitor_positions = {}
            for ref in references_found:
                link = ref.get('link', '')
                if link:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(link)
                        domain = parsed.netloc.replace('www.', '')
                        position = ref.get('index', 0) + 1  # +1 porque index empieza en 0
                        
                        if domain in top_competitor_domains:
                            competitor_positions[domain] = position
                    except:
                        continue
            
            # Añadir datos de cada competidor a la fila
            for domain in top_competitor_domains:
                if domain in competitor_positions:
                    row_data.extend(['Yes', competitor_positions[domain]])
                else:
                    row_data.extend(['No', 'N/A'])
            
            aio_table_section.append(row_data)
        
        # Combinar secciones
        all_competitors_data = competitors_summary + aio_table_section
        
        # Crear DataFrame y exportar
        df_competitors = pd.DataFrame(all_competitors_data[1:], columns=all_competitors_data[0])
        df_competitors.to_excel(writer, sheet_name='AIO Competitors Analysis', index=False)
        
        # Formatear hoja - dinámico según número de columnas
        worksheet = writer.sheets['AIO Competitors Analysis']
        
        # Calcular número de columnas total
        num_columns = len(aio_table_headers)
        
        # Formatear columnas base
        worksheet.set_column('A:A', 35)  # Keyword/Dominio
        worksheet.set_column('B:B', 18)  # Apariciones/Your Domain in AIO
        worksheet.set_column('C:C', 18)  # Posición Promedio/Your Position in AIO
        worksheet.set_column('D:D', 15)  # Presencia %
        
        # Formatear columnas adicionales para competidores si existen
        if num_columns > 4:
            for i in range(4, min(num_columns, 26)):  # Máximo hasta columna Z
                col_letter = chr(ord('A') + i)
                worksheet.set_column(f'{col_letter}:{col_letter}', 15)
        
        # Aplicar formatos especiales
        workbook = writer.book
        section_format = workbook.add_format({'bold': True, 'bg_color': '#E6F3FF', 'border': 1})
        
        # Encontrar filas de sección para formatear
        section_rows = []
        for i, row in enumerate(all_competitors_data[1:], start=1):
            if row[0] in ['RESUMEN COMPETIDORES', 'DETAILS OF KEYWORDS WITH AIO']:
                section_rows.append(i)
        
        for row_num in section_rows:
            worksheet.set_row(row_num, None, section_format)
        
        # Aplicar header format para todas las columnas necesarias
        for col_num in range(min(num_columns, len(df_competitors.columns))):
            col_letter = chr(ord('A') + col_num)
            worksheet.write(f'{col_letter}1', df_competitors.columns[col_num], header_format)
                
    except Exception as e:
        logger.error(f"Error creando hoja de análisis de competidores: {e}")


# ❌ FUNCIÓN ELIMINADA: create_aio_organic_correlation_sheet (AIO Impact Analysis - no se requiere)
