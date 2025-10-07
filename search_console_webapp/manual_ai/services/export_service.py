"""
Servicio para exportación de datos a Excel
"""

import logging
import pandas as pd
import pytz
from io import BytesIO
from datetime import datetime, date, timedelta
from typing import Dict, Optional
from database import get_db_connection

logger = logging.getLogger(__name__)


class ExportService:
    """Servicio para generar exportaciones de Manual AI"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def generate_manual_ai_excel(project_id: int, project_info: Dict, days: int, user_id: int) -> BytesIO:
        """
        Generar Excel con todas las hojas para Manual AI:
        1. Resumen
        2. Domain Visibility Over Time  
        3. Competitive Analysis
        4. AI Overview Keywords Details
        5. Global AI Overview Domains
        6. Thematic Clusters Summary
        7. Clusters Keywords Detail
        """
        from manual_ai.services.statistics_service import StatisticsService
        from manual_ai.services.cluster_service import ClusterService
        
        output = BytesIO()
        stats_service = StatisticsService()
        cluster_service = ClusterService()
        
        try:
            # Obtener datos usando los mismos endpoints que la UI
            logger.info(f"Fetching UI analytics data for project {project_id}")
            
            # 1. Obtener estadísticas principales (igual que la UI)
            stats_response = stats_service.get_project_statistics(project_id, days)
            logger.info(f"Main statistics fetched successfully")
            
            # 2. Obtener datos de Global Domains (igual que la UI)  
            global_domains = stats_service.get_project_global_domains_ranking(project_id, days)
            logger.info(f"Found {len(global_domains) if global_domains else 0} global domains")
            
            # 3. Obtener datos de AI Overview Keywords (igual que la UI)
            ai_overview_data = stats_service.get_project_ai_overview_keywords_latest(project_id)
            logger.info(f"AI Overview keywords data fetched successfully: {len(ai_overview_data.get('keywordResults', []))} keywords")
            
            # 4. Obtener datos de Clusters Temáticos (igual que la UI)
            clusters_data = cluster_service.get_cluster_statistics(project_id, days)
            logger.info(f"Clusters data fetched successfully: enabled={clusters_data.get('enabled', False)}, clusters={len(clusters_data.get('table_data', []))}")
            
            # Configuración de zona horaria
            madrid_tz = pytz.timezone('Europe/Madrid')
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Formatos comunes
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#4472C4',
                    'font_color': 'white',
                    'border': 1
                })
                
                date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
                percent_format = workbook.add_format({'num_format': '0.00%'})
                number_format = workbook.add_format({'num_format': '0.0'})
                
                # HOJA 1: Resumen
                logger.info("Creating summary sheet")
                ExportService._create_summary_sheet(writer, workbook, header_format, project_info, stats_response, days, madrid_tz, clusters_data)
                logger.info("Summary sheet created successfully")
                
                # HOJA 2: Domain Visibility Over Time
                logger.info("Creating domain visibility sheet")
                ExportService._create_domain_visibility_sheet(writer, workbook, header_format, date_format, 
                                              percent_format, project_id, project_info, days)
                logger.info("Domain visibility sheet created successfully")
                
                # HOJA 3: Competitive Analysis
                logger.info("Creating competitive analysis sheet")
                ExportService._create_competitive_analysis_sheet(writer, workbook, header_format, date_format,
                                                percent_format, project_id, project_info, days)
                logger.info("Competitive analysis sheet created successfully")
                
                # HOJA 4: AI Overview Keywords Details
                logger.info("Creating keywords details sheet")
                ExportService._create_keywords_details_sheet(writer, workbook, header_format, date_format,
                                            ai_overview_data, project_id, days)
                logger.info("Keywords details sheet created successfully")
                
                # HOJA 5: Global AI Overview Domains
                logger.info("Creating global domains sheet")
                ExportService._create_global_domains_sheet(writer, workbook, header_format, percent_format,
                                          number_format, global_domains, project_info)
                logger.info("Global domains sheet created successfully")
                
                # HOJA 6: Thematic Clusters Summary
                logger.info("Creating clusters summary sheet")
                ExportService._create_clusters_summary_sheet(writer, workbook, header_format, percent_format,
                                                            clusters_data, project_info, days)
                logger.info("Clusters summary sheet created successfully")
                
                # HOJA 7: Clusters Keywords Detail
                logger.info("Creating clusters keywords detail sheet")
                ExportService._create_clusters_keywords_detail_sheet(writer, workbook, header_format,
                                                                     project_id, clusters_data, days)
                logger.info("Clusters keywords detail sheet created successfully")
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error generating manual AI Excel: {e}", exc_info=True)
            raise

    @staticmethod
    def _create_summary_sheet(writer, workbook, header_format, project_info, stats, days, madrid_tz, clusters_data=None):
        """Crear Hoja 1: Resumen - usando datos exactos de la UI"""
        # Usar métricas exactas de la UI (mismo endpoint que usa la interfaz)
        main_stats = stats.get('main_stats', {})
        
        total_keywords = main_stats.get('total_keywords', 0)
        ai_overview_results = main_stats.get('total_ai_keywords', 0)  
        ai_overview_weight = main_stats.get('aio_weight_percentage', 0)
        domain_mentions = main_stats.get('total_mentions', 0)
        visibility_pct = main_stats.get('visibility_percentage', 0)
        avg_position = main_stats.get('avg_position')
        
        # Información de clusters
        clusters_enabled = clusters_data.get('enabled', False) if clusters_data else False
        clusters_count = len(clusters_data.get('table_data', [])) if clusters_data and clusters_enabled else 0
        
        summary_data = [
            ['Métrica', 'Valor'],
            ['Total Keywords', total_keywords],
            ['AI Overview Results', ai_overview_results],
            ['AI Overview Weight (%)', f"{ai_overview_weight:.2f}%"],
            ['Domain Mentions', domain_mentions],
            ['Visibility (%)', f"{visibility_pct:.2f}%"],
            ['Average Position', f"{avg_position:.1f}" if avg_position else "N/A"],
            ['', ''],
            ['NOTAS', ''],
            [f'Proyecto: {project_info["name"]}', ''],
            [f'Dominio: {project_info["domain"]}', ''],
            [f'Rango de fechas: Últimos {days} días', ''],
            [f'Competidores: {len(project_info.get("selected_competitors", []))}', ''],
            [f'Thematic Clusters: {"Enabled" if clusters_enabled else "Disabled"}', ''],
            [f'Active Clusters: {clusters_count}' if clusters_enabled else 'Active Clusters: 0', ''],
            [f'Generado: {datetime.now(madrid_tz).strftime("%Y-%m-%d %H:%M")} Europe/Madrid', '']
        ]
        
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Resumen', index=False, header=False)
        
        # Aplicar formato
        worksheet = writer.sheets['Resumen']
        worksheet.write_row(0, 0, ['Métrica', 'Valor'], header_format)
        worksheet.set_column('A:A', 40)
        worksheet.set_column('B:B', 20)

    @staticmethod
    def _create_domain_visibility_sheet(writer, workbook, header_format, date_format, percent_format, project_id, project_info, days):
        """Crear Hoja 2: Domain Visibility Over Time - usando datos exactos de la UI"""
        # Usar la misma lógica que la UI
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        cur.execute("""
            SELECT 
                r.analysis_date,
                COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.keyword_id END) as aio_keywords,
                COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.keyword_id END) as project_mentions
            FROM manual_ai_results r
            JOIN manual_ai_keywords k ON r.keyword_id = k.id
            WHERE r.project_id = %s 
            AND r.analysis_date >= %s 
            AND r.analysis_date <= %s
            AND k.is_active = true
            GROUP BY r.analysis_date
            ORDER BY r.analysis_date
        """, (project_id, start_date, end_date))
        
        daily_data = cur.fetchall()
        cur.close()
        conn.close()
        
        # Preparar datos para Excel usando la misma lógica que la UI
        rows = []
        for row in daily_data:
            aio_keywords = row['aio_keywords']
            project_mentions = row['project_mentions']
            # Lógica correcta: menciones del proyecto/total keywords con AIO * 100
            visibility_pct = (project_mentions / aio_keywords * 100) if aio_keywords > 0 else 0
            # Nunca puede ser mayor al 100%
            visibility_pct = min(visibility_pct, 100.0)
            
            rows.append({
                'date': row['analysis_date'],
                'aio_keywords': aio_keywords,
                'project_mentions': project_mentions,
                'project_visibility_pct': visibility_pct
            })
        
        # Crear DataFrame con datos o vacío con columnas definidas
        if rows:
            df_visibility = pd.DataFrame(rows)
        else:
            # Crear DataFrame vacío con las columnas requeridas
            df_visibility = pd.DataFrame(columns=['date', 'aio_keywords', 'project_mentions', 'project_visibility_pct'])
        
        df_visibility.to_excel(writer, sheet_name='Domain Visibility Over Time', index=False)
        
        worksheet = writer.sheets['Domain Visibility Over Time']
        worksheet.write_row(0, 0, ['date', 'aio_keywords', 'project_mentions', 'project_visibility_pct'], header_format)
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:D', 20)
        
        # Si no hay datos, agregar nota
        if not rows:
            worksheet.write(1, 0, 'Sin datos para los filtros aplicados')

    @staticmethod
    def _create_competitive_analysis_sheet(writer, workbook, header_format, date_format, percent_format, project_id, project_info, days):
        """Crear Hoja 3: Competitive Analysis - lógica corregida según especificaciones"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Primero obtener keywords con AIO por día (dato base)
        cur.execute("""
            SELECT 
                r.analysis_date,
                COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN r.keyword_id END) as aio_keywords
            FROM manual_ai_results r
            JOIN manual_ai_keywords k ON r.keyword_id = k.id
            WHERE r.project_id = %s 
            AND r.analysis_date >= %s 
            AND r.analysis_date <= %s
            AND k.is_active = true
            GROUP BY r.analysis_date
            ORDER BY r.analysis_date
        """, (project_id, start_date, end_date))
        
        aio_keywords_by_date = {str(row['analysis_date']): row['aio_keywords'] for row in cur.fetchall()}
        
        # Obtener menciones del dominio del proyecto
        cur.execute("""
            SELECT 
                r.analysis_date,
                COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN r.keyword_id END) as project_mentions
            FROM manual_ai_results r
            JOIN manual_ai_keywords k ON r.keyword_id = k.id
            WHERE r.project_id = %s 
            AND r.analysis_date >= %s 
            AND r.analysis_date <= %s
            AND k.is_active = true
            GROUP BY r.analysis_date
            ORDER BY r.analysis_date
        """, (project_id, start_date, end_date))
        
        project_mentions_by_date = {str(row['analysis_date']): row['project_mentions'] for row in cur.fetchall()}
        
        # Obtener menciones de competidores
        competitors_mentions = {}
        selected_competitors = project_info.get('selected_competitors', [])
        
        for competitor in selected_competitors:
            cur.execute("""
                SELECT 
                    gd.analysis_date,
                    COUNT(DISTINCT gd.keyword_id) as competitor_mentions
                FROM manual_ai_global_domains gd
                JOIN manual_ai_results r ON gd.keyword_id = r.keyword_id AND gd.analysis_date = r.analysis_date
                JOIN manual_ai_keywords k ON r.keyword_id = k.id
                WHERE gd.project_id = %s 
                AND gd.detected_domain = %s
                AND gd.analysis_date >= %s 
                AND gd.analysis_date <= %s
                AND k.is_active = true
                AND r.has_ai_overview = true
                GROUP BY gd.analysis_date
                ORDER BY gd.analysis_date
            """, (project_id, competitor, start_date, end_date))
            
            competitors_mentions[competitor] = {str(row['analysis_date']): row['competitor_mentions'] for row in cur.fetchall()}
        
        cur.close()
        conn.close()
        
        # Preparar datos para Excel usando lógica correcta
        rows = []
        
        # Agregar datos del proyecto
        for date_str, aio_keywords in aio_keywords_by_date.items():
            project_mentions = project_mentions_by_date.get(date_str, 0)
            # Lógica correcta: menciones del proyecto/total keywords con AIO * 100
            visibility_pct = (project_mentions / aio_keywords * 100) if aio_keywords > 0 else 0
            # Nunca puede ser mayor al 100%
            visibility_pct = min(visibility_pct, 100.0)
            
            rows.append({
                'date': date_str,
                'domain': project_info['domain'],
                'aio_keywords': aio_keywords,
                'domain_mentions': project_mentions,
                'visibility_pct': visibility_pct
            })
        
        # Agregar datos de competidores
        for competitor in selected_competitors:
            for date_str, aio_keywords in aio_keywords_by_date.items():
                competitor_mentions = competitors_mentions.get(competitor, {}).get(date_str, 0)
                # Lógica correcta: menciones del competidor/total keywords con AIO * 100
                visibility_pct = (competitor_mentions / aio_keywords * 100) if aio_keywords > 0 else 0
                # Nunca puede ser mayor al 100%
                visibility_pct = min(visibility_pct, 100.0)
                
                rows.append({
                    'date': date_str,
                    'domain': competitor,
                    'aio_keywords': aio_keywords,
                    'domain_mentions': competitor_mentions,
                    'visibility_pct': visibility_pct
                })
        
        # Crear DataFrame con datos o vacío con columnas definidas
        if rows:
            df_competitive = pd.DataFrame(rows)
            df_competitive = df_competitive.sort_values(['date', 'visibility_pct'], ascending=[True, False])
        else:
            # Crear DataFrame vacío con las columnas requeridas
            df_competitive = pd.DataFrame(columns=['date', 'domain', 'aio_keywords', 'domain_mentions', 'visibility_pct'])
        
        df_competitive.to_excel(writer, sheet_name='Competitive Analysis', index=False)
        
        worksheet = writer.sheets['Competitive Analysis']
        worksheet.write_row(0, 0, ['date', 'domain', 'aio_keywords', 'domain_mentions', 'visibility_pct'], header_format)
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:E', 20)
        
        # Si no hay datos, agregar nota
        if not rows:
            worksheet.write(1, 0, 'Sin datos para los filtros aplicados')

    @staticmethod
    def _create_keywords_details_sheet(writer, workbook, header_format, date_format, ai_overview_data, project_id, days):
        """Crear Hoja 4: AI Overview Keywords Details - EXACTAMENTE igual que la UI"""
        # Obtener datos exactos de la UI
        keyword_results = ai_overview_data.get('keywordResults', [])
        competitor_domains = ai_overview_data.get('competitorDomains', [])
        
        logger.info(f"📊 Creating keywords details sheet: {len(keyword_results)} keywords, {len(competitor_domains)} competitors")
        
        # Definir columnas base exactamente como en la UI
        columns = ['Keyword', 'Your Domain in AIO', 'Your Position in AIO']
        
        # Agregar columnas dinámicas para cada competidor (igual que la UI)
        for domain in competitor_domains:
            columns.append(f'{domain} in AIO')
            columns.append(f'Position of {domain}')
        
        # Preparar datos exactamente como la UI
        rows = []
        for result in keyword_results:
            keyword = result.get('keyword', '')
            user_domain_in_aio = result.get('user_domain_in_aio', False)
            user_domain_position = result.get('user_domain_position')
            competitors_data = result.get('competitors', [])
            
            # Datos base (igual que la UI)
            row_data = {
                'Keyword': keyword,
                'Your Domain in AIO': 'Yes' if user_domain_in_aio else 'No',
                'Your Position in AIO': user_domain_position if user_domain_position else 'N/A'
            }
            
            # Agregar datos de cada competidor (igual que la UI)
            # Crear un diccionario de competidores para búsqueda rápida
            competitors_dict = {comp['domain']: comp for comp in competitors_data}
            
            for domain in competitor_domains:
                comp_info = competitors_dict.get(domain)
                if comp_info:
                    row_data[f'{domain} in AIO'] = 'Yes'
                    row_data[f'Position of {domain}'] = comp_info.get('position') or 'N/A'
                else:
                    row_data[f'{domain} in AIO'] = 'No'
                    row_data[f'Position of {domain}'] = 'N/A'
            
            rows.append(row_data)
        
        # Crear DataFrame con columnas dinámicas
        if rows:
            df_keywords = pd.DataFrame(rows)
        else:
            # DataFrame vacío con columnas base
            df_keywords = pd.DataFrame(columns=columns)
        
        df_keywords.to_excel(writer, sheet_name='AI Overview Keywords Details', index=False)
        
        worksheet = writer.sheets['AI Overview Keywords Details']
        worksheet.write_row(0, 0, list(df_keywords.columns), header_format)
        worksheet.set_column('A:A', 30)  # keyword
        worksheet.set_column('B:G', 20)  # otras columnas
        
        # Si no hay datos, agregar nota
        if not rows:
            worksheet.write(1, 0, 'Sin datos para los filtros aplicados')

    @staticmethod
    def _create_global_domains_sheet(writer, workbook, header_format, percent_format, number_format, global_domains, project_info):
        """Crear Hoja 5: Global AI Overview Domains - usando datos exactos de la UI"""
        
        # Calcular AIO_Events_total según especificaciones
        aio_events_total = sum(domain.get('appearances', 0) for domain in global_domains) if global_domains else 0
        
        # Preparar datos con ranking
        rows = []
        if global_domains:
            for idx, domain in enumerate(global_domains, 1):
                appearances = domain.get('appearances', 0)
                avg_position = domain.get('avg_position')
                visibility_pct = (appearances / aio_events_total * 100) if aio_events_total > 0 else 0
                
                rows.append({
                    'Rank': idx,
                    'Domain': domain.get('detected_domain', ''),
                    'Appearances': appearances,
                    'Avg Position': f"{avg_position:.1f}" if avg_position and avg_position > 0 else "",
                    'Visibility %': f"{visibility_pct:.2f}%"
                })
        
        # Crear DataFrame con datos o vacío con columnas definidas
        if rows:
            df_domains = pd.DataFrame(rows)
        else:
            # Crear DataFrame vacío con las columnas requeridas
            df_domains = pd.DataFrame(columns=['Rank', 'Domain', 'Appearances', 'Avg Position', 'Visibility %'])
        
        df_domains.to_excel(writer, sheet_name='Global AI Overview Domains', index=False)
        
        worksheet = writer.sheets['Global AI Overview Domains']
        worksheet.write_row(0, 0, list(df_domains.columns), header_format)
        worksheet.set_column('A:A', 10)  # Rank
        worksheet.set_column('B:B', 40)  # Domain
        worksheet.set_column('C:E', 20)  # Metrics
        
        # Agregar nota
        note_row = len(df_domains) + 3
        worksheet.write(note_row, 0, f"Proyecto: {project_info['name']}")
        worksheet.write(note_row + 1, 0, f"AIO_Events_total: {aio_events_total}")
        worksheet.write(note_row + 2, 0, "Average Position: Media simple de posiciones")
        
        # Si no hay datos, agregar nota
        if not rows:
            worksheet.write(1, 0, 'Sin datos para los filtros aplicados')

    @staticmethod
    def _create_clusters_summary_sheet(writer, workbook, header_format, percent_format, clusters_data, project_info, days):
        """Crear Hoja 6: Thematic Clusters Summary - Tabla transpuesta igual que la UI"""
        
        if not clusters_data.get('enabled', False):
            # Crear hoja vacía con mensaje
            df_empty = pd.DataFrame([
                ['Thematic Clusters are not enabled for this project'],
                ['Enable clusters in project settings to see analysis by topic']
            ])
            df_empty.to_excel(writer, sheet_name='Thematic Clusters Summary', index=False, header=False)
            worksheet = writer.sheets['Thematic Clusters Summary']
            worksheet.set_column('A:A', 60)
            return
        
        table_data = clusters_data.get('table_data', [])
        
        if not table_data:
            # Crear hoja vacía con mensaje
            df_empty = pd.DataFrame([
                ['No cluster data available'],
                ['Clusters are enabled but no keywords have been classified yet']
            ])
            df_empty.to_excel(writer, sheet_name='Thematic Clusters Summary', index=False, header=False)
            worksheet = writer.sheets['Thematic Clusters Summary']
            worksheet.set_column('A:A', 60)
            return
        
        # Preparar datos transpuestos (métricas como filas, clusters como columnas)
        metrics = [
            {'label': 'Total Keywords', 'key': 'total_keywords'},
            {'label': 'AI Overview', 'key': 'ai_overview_count'},
            {'label': 'Brand Mentions', 'key': 'mentions_count'},
            {'label': '% AI Overview', 'key': 'ai_overview_percentage', 'is_percent': True},
            {'label': '% Mentions', 'key': 'mentions_percentage', 'is_percent': True}
        ]
        
        # Crear estructura transpuesta
        rows = []
        
        # Header row: Métrica | Cluster1 | Cluster2 | ...
        header_row = ['Metric'] + [cluster['cluster_name'] for cluster in table_data]
        rows.append(header_row)
        
        # Filas de métricas
        for metric in metrics:
            row = [metric['label']]
            for cluster in table_data:
                value = cluster.get(metric['key'], 0)
                if metric.get('is_percent', False):
                    row.append(f"{value:.1f}%")
                else:
                    row.append(value)
            rows.append(row)
        
        # Crear DataFrame y escribir
        df_clusters = pd.DataFrame(rows[1:], columns=rows[0])
        df_clusters.to_excel(writer, sheet_name='Thematic Clusters Summary', index=False)
        
        worksheet = writer.sheets['Thematic Clusters Summary']
        
        # Aplicar formato al header
        for col_num, value in enumerate(rows[0]):
            worksheet.write(0, col_num, value, header_format)
        
        # Ajustar columnas
        worksheet.set_column('A:A', 20)  # Métrica
        for i in range(1, len(header_row)):
            worksheet.set_column(i, i, 18)  # Clusters
        
        # Agregar nota al final
        note_row = len(rows) + 2
        worksheet.write(note_row, 0, f"Project: {project_info['name']}")
        worksheet.write(note_row + 1, 0, f"Date range: Last {days} days")
        worksheet.write(note_row + 2, 0, f"Total clusters: {len(table_data)}")

    @staticmethod
    def _create_clusters_keywords_detail_sheet(writer, workbook, header_format, project_id, clusters_data, days):
        """Crear Hoja 7: Clusters Keywords Detail - Listado detallado de keywords por cluster"""
        from datetime import date, timedelta
        
        if not clusters_data.get('enabled', False):
            # Crear hoja vacía con mensaje
            df_empty = pd.DataFrame([
                ['Thematic Clusters are not enabled for this project'],
                ['Enable clusters in project settings to see keywords by cluster']
            ])
            df_empty.to_excel(writer, sheet_name='Clusters Keywords Detail', index=False, header=False)
            worksheet = writer.sheets['Clusters Keywords Detail']
            worksheet.set_column('A:A', 60)
            return
        
        # Obtener configuración de clusters y clasificar keywords
        from manual_ai.services.cluster_service import ClusterService
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            clusters_config = ClusterService.get_project_clusters(project_id)
            
            # Obtener todas las keywords con sus últimos resultados
            cur.execute("""
                WITH latest_results AS (
                    SELECT DISTINCT ON (k.id)
                        k.id as keyword_id,
                        k.keyword,
                        r.has_ai_overview,
                        r.domain_mentioned,
                        r.analysis_date
                    FROM manual_ai_keywords k
                    LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
                        AND r.analysis_date >= %s AND r.analysis_date <= %s
                    WHERE k.project_id = %s AND k.is_active = true
                    ORDER BY k.id, r.analysis_date DESC
                )
                SELECT 
                    keyword_id,
                    keyword,
                    has_ai_overview,
                    domain_mentioned,
                    analysis_date
                FROM latest_results
                ORDER BY keyword
            """, (start_date, end_date, project_id))
            
            keywords_data = cur.fetchall()
            
            # Clasificar keywords en clusters
            rows = []
            for kw_data in keywords_data:
                keyword = kw_data['keyword']
                has_ai_overview = 'Yes' if kw_data.get('has_ai_overview') else 'No'
                domain_mentioned = 'Yes' if kw_data.get('domain_mentioned') else 'No'
                last_analysis = kw_data.get('analysis_date')
                last_analysis_str = str(last_analysis) if last_analysis else 'Never'
                
                # Clasificar keyword
                matching_clusters = ClusterService.classify_keyword(keyword, clusters_config)
                
                if matching_clusters:
                    # Añadir una fila por cada cluster al que pertenece
                    for cluster_name in matching_clusters:
                        rows.append({
                            'Cluster': cluster_name,
                            'Keyword': keyword,
                            'Has AI Overview': has_ai_overview,
                            'Domain Mentioned': domain_mentioned,
                            'Last Analysis': last_analysis_str
                        })
                else:
                    # Keyword no clasificada
                    rows.append({
                        'Cluster': 'Unclassified',
                        'Keyword': keyword,
                        'Has AI Overview': has_ai_overview,
                        'Domain Mentioned': domain_mentioned,
                        'Last Analysis': last_analysis_str
                    })
            
            # Ordenar por cluster y luego por keyword
            if rows:
                df_keywords = pd.DataFrame(rows)
                df_keywords = df_keywords.sort_values(['Cluster', 'Keyword'])
            else:
                # DataFrame vacío
                df_keywords = pd.DataFrame(columns=['Cluster', 'Keyword', 'Has AI Overview', 'Domain Mentioned', 'Last Analysis'])
            
            df_keywords.to_excel(writer, sheet_name='Clusters Keywords Detail', index=False)
            
            worksheet = writer.sheets['Clusters Keywords Detail']
            worksheet.write_row(0, 0, list(df_keywords.columns), header_format)
            worksheet.set_column('A:A', 20)  # Cluster
            worksheet.set_column('B:B', 40)  # Keyword
            worksheet.set_column('C:D', 18)  # Has AI Overview, Domain Mentioned
            worksheet.set_column('E:E', 15)  # Last Analysis
            
            # Si no hay datos, agregar nota
            if not rows:
                worksheet.write(1, 0, 'No keywords found for this project')
        
        finally:
            cur.close()
            conn.close()

