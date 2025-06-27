import os
import sys
import json
import time
import logging
import traceback
import zipfile
from io import BytesIO
from datetime import datetime, timedelta # Importación añadida
from flask import Flask, render_template, request, jsonify, send_file, Response, session
import pandas as pd
from excel_generator import generate_excel_from_data
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ✅ NUEVO: Permitir HTTP para desarrollo local con OAuth2
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# ✅ NUEVO: Relajar validación de scopes para evitar errores de orden
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# --- Servicios extraídos ---
from services.search_console import authenticate, fetch_searchconsole_data_single_call
from services.serp_service import get_serp_json, get_serp_html, get_page_screenshot
from services.ai_analysis import detect_ai_overview_elements
from services.utils import extract_domain, normalize_search_console_url, urls_match
from services.country_config import get_country_config

# --- NUEVO: Sistema de autenticación ---
from auth import (
    setup_auth_routes,
    login_required,
    is_user_authenticated,
    get_authenticated_service,
    get_user_credentials
)

# Configurar logging mejorado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carga variables de entorno
if os.getenv("RAILWAY_ENVIRONMENT"):
    logger.info("Entorno Railway detectado, no se carga .env local")
else:
    load_dotenv('serpapi.env')


app = Flask(__name__)

# --- NUEVO: Configuración de sesión para autenticación ---
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True en producción con HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# --- NUEVO: Configurar rutas de autenticación ---
setup_auth_routes(app)

# --- Funciones auxiliares con geolocalización (sin cambios) ---
def get_serp_params_with_location(keyword, api_key, country_code=None):
    """
    Genera parámetros para SERP API con geolocalización según el país.
    ✅ DEBE SER IDÉNTICA a serp_service.py
    """
    # Parámetros base
    params = {
        'engine': 'google',
        'q': keyword,
        'api_key': api_key,
        'gl': 'es',
        'hl': 'es',
        'num': 20
    }
    
    # ✅ AÑADIR: Si se especifica un país, usar su configuración
    if country_code:
        country_config = get_country_config(country_code)
        if country_config:
            params.update({
                'location': country_config['serp_location'],
                'gl': country_config['serp_gl'],
                'hl': country_config['serp_hl'],
                'google_domain': country_config['google_domain']  # 👈 CRÍTICO
            })
            logger.info(f"[AI ANALYSIS] Usando configuración para {country_config['name']}")
    else:
        # ✅ NUEVO: Si no hay país, usar España como fallback para consistencia
        country_config = get_country_config('esp')
        if country_config:
            params.update({
                'location': country_config['serp_location'],
                'google_domain': country_config['google_domain']
            })
            logger.info(f"[AI ANALYSIS] Sin país especificado, usando España por defecto")
    
    return params

def get_site_position_from_serp(keyword, site_url, organic_results, serp_data=None):
    """
    Función mejorada que detecta posición en resultados orgánicos Y resultados enriquecidos
    """
    matches = []
    first = None
    
    logger.info(f"[POSITION SEARCH] Buscando '{site_url}' para keyword '{keyword}' en {len(organic_results)} resultados + resultados enriquecidos")
    
    # PRIMERO: Buscar en resultados enriquecidos (posición 0)
    if serp_data:
        enhanced_results = []
        
        # 1. Featured Snippet
        featured_snippet = serp_data.get('featured_snippet', {})
        if featured_snippet and featured_snippet.get('link'):
            if urls_match(featured_snippet['link'], site_url):
                detail = {
                    'position': 0,
                    'title': featured_snippet.get('title', 'Featured Snippet'),
                    'link': featured_snippet['link'],
                    'snippet': featured_snippet.get('snippet', ''),
                    'displayed_link': featured_snippet.get('displayed_link', featured_snippet['link']),
                    'type': 'Featured Snippet'
                }
                enhanced_results.append(detail)
                logger.info(f"[POSITION FOUND] ✅ Featured Snippet (Pos #0): {featured_snippet['link']}")
        
        # 2. Answer Box
        answer_box = serp_data.get('answer_box', {})
        if answer_box and answer_box.get('link'):
            if urls_match(answer_box['link'], site_url):
                detail = {
                    'position': 0,
                    'title': answer_box.get('title', 'Answer Box'),
                    'link': answer_box['link'],
                    'snippet': answer_box.get('answer', ''),
                    'displayed_link': answer_box.get('displayed_link', answer_box['link']),
                    'type': 'Answer Box'
                }
                enhanced_results.append(detail)
                logger.info(f"[POSITION FOUND] ✅ Answer Box (Pos #0): {answer_box['link']}")
        
        # 3. Knowledge Graph
        knowledge_graph = serp_data.get('knowledge_graph', {})
        if knowledge_graph and knowledge_graph.get('website'):
            if urls_match(knowledge_graph['website'], site_url):
                detail = {
                    'position': 0,
                    'title': knowledge_graph.get('title', 'Knowledge Graph'),
                    'link': knowledge_graph['website'],
                    'snippet': knowledge_graph.get('description', ''),
                    'displayed_link': knowledge_graph.get('website', ''),
                    'type': 'Knowledge Graph'
                }
                enhanced_results.append(detail)
                logger.info(f"[POSITION FOUND] ✅ Knowledge Graph (Pos #0): {knowledge_graph['website']}")
        
        # 4. Buscar en sources del AI Overview
        ai_overview = serp_data.get('ai_overview', {})
        if ai_overview and ai_overview.get('sources'):
            for source in ai_overview.get('sources', []):
                if source.get('link') and urls_match(source['link'], site_url):
                    detail = {
                        'position': 0,
                        'title': source.get('title', 'AI Overview Source'),
                        'link': source['link'],
                        'snippet': 'Citado en AI Overview',
                        'displayed_link': source.get('link', ''),
                        'type': 'AI Overview Source'
                    }
                    enhanced_results.append(detail)
                    logger.info(f"[POSITION FOUND] ✅ AI Overview Source (Pos #0): {source['link']}")
                    break
        
        if enhanced_results:
            first = enhanced_results[0]
            matches.extend(enhanced_results)
    
    if not first:
        for i, res in enumerate(organic_results, start=1):
            result_link = res.get('link', '')
            
            if not result_link:
                continue
                
            if urls_match(result_link, site_url):
                detail = {
                    'position': i,
                    'title': res.get('title'),
                    'link': result_link,
                    'snippet': res.get('snippet'),
                    'displayed_link': res.get('displayed_link', result_link),
                    'type': 'Organic Result'
                }
                matches.append(detail)
                if first is None:
                    first = detail
                    logger.info(f"[POSITION FOUND] ✅ Resultado orgánico posición #{i}: {result_link}")
                    break
    
    if not first:
        logger.warning(f"[POSITION NOT FOUND] No se encontró '{site_url}' en ningún tipo de resultado para '{keyword}'")
        for i, res in enumerate(organic_results[:3], start=1):
            debug_link = res.get('link', '')
            if debug_link:
                debug_domain = extract_domain(debug_link)
                logger.info(f"[POSITION DEBUG] Resultado orgánico #{i}: {debug_domain} ({debug_link})")
    
    return {
        'found': bool(matches),
        'position': first['position'] if first else None,
        'result': first,
        'all_matches': matches,
        'total_results': len(organic_results),
        'result_type': first.get('type', 'Unknown') if first else None
    }

# --- ACTUALIZADO: Función para obtener sitios validados usando autenticación ---
def fetch_validated_sites():
    """Obtiene sitios validados usando las credenciales del usuario autenticado"""
    try:
        gsc_service = get_authenticated_service('searchconsole', 'v1')
        if not gsc_service:
            logger.error("No se pudo obtener servicio autenticado de Search Console")
            return []
        
        resp = gsc_service.sites().list().execute()
        return resp.get('siteEntry', [])
    except Exception as e:
        logger.error(f"Error obteniendo sitios validados: {e}", exc_info=True)
        return []

@app.route('/get-properties')
@login_required  # NUEVO: Requiere autenticación
def get_properties():
    """Obtiene propiedades de Search Console del usuario autenticado"""
    sites = fetch_validated_sites()
    props = [{'siteUrl': s['siteUrl']} for s in sites if s.get('siteUrl')]
    return jsonify({'properties': props})

@app.route('/')
def index():
# ✅ CORREGIDO: Obtener información del usuario si está logueado
    user_info = None
    user_email = None
    
    if is_user_authenticated():
        from auth import get_user_info
        user_info = get_user_info()
        user_email = user_info.get('email') if user_info else None
    
    return render_template('index.html', user_email=user_email, authenticated=is_user_authenticated())

@app.route('/get-data', methods=['POST'])
@login_required
def get_data():
    """Obtiene datos de Search Console con fechas específicas y comparación opcional"""
    
    # Obtener parámetros del formulario
    form_urls = [u.strip() for u in request.form.get('urls','').splitlines() if u.strip()]
    site_url_sc = request.form.get('site_url','')
    match_type = request.form.get('match_type','contains')
    selected_country = request.form.get('country', '')
    
    # ✅ NUEVO: Obtener fechas específicas en lugar de meses
    current_start_date = request.form.get('current_start_date')
    current_end_date = request.form.get('current_end_date')
    
    # Datos de comparación (opcionales)
    has_comparison = request.form.get('has_comparison', 'false').lower() == 'true'
    comparison_start_date = request.form.get('comparison_start_date')
    comparison_end_date = request.form.get('comparison_end_date')
    comparison_mode = request.form.get('comparison_mode', 'none')
    
    # Validaciones básicas
    if not current_start_date or not current_end_date:
        return jsonify({'error': 'Fechas del período principal son requeridas.'}), 400
    
    if not site_url_sc:
        return jsonify({'error': 'site_url es requerido.'}), 400

    # ✅ NUEVO: Validar formato de fechas
    try:
        current_start = datetime.strptime(current_start_date, '%Y-%m-%d').date()
        current_end = datetime.strptime(current_end_date, '%Y-%m-%d').date()
        
        if current_start >= current_end:
            return jsonify({'error': 'La fecha de inicio debe ser anterior a la fecha de fin.'}), 400
            
        # Validar que las fechas estén dentro del rango permitido por GSC
        max_date = datetime.now().date() - timedelta(days=3)  # GSC tiene delay
        min_date = max_date - timedelta(days=16*30)  # ~16 meses atrás
        
        if current_start < min_date or current_end > max_date:
            return jsonify({'error': f'Las fechas deben estar entre {min_date} y {max_date}.'}), 400
            
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. UsebeginPath-MM-DD.'}), 400

    # Validar fechas de comparación si están presentes
    comparison_start = None
    comparison_end = None
    if has_comparison and comparison_start_date and comparison_end_date:
        try:
            comparison_start = datetime.strptime(comparison_start_date, '%Y-%m-%d').date()
            comparison_end = datetime.strptime(comparison_end_date, '%Y-%m-%d').date()
            
            if comparison_start >= comparison_end:
                return jsonify({'error': 'Las fechas de comparación no son válidas.'}), 400
                
            if comparison_start < min_date or comparison_end > max_date:
                return jsonify({'error': 'Las fechas de comparación están fuera del rango permitido.'}), 400
                
        except ValueError:
            return jsonify({'error': 'Formato de fecha de comparación inválido.'}), 400

    # Logging descriptivo
    logger.info(f"[GSC REQUEST] Período principal: {current_start_date} a {current_end_date}")
    if has_comparison:
        logger.info(f"[GSC REQUEST] Comparación ({comparison_mode}): {comparison_start_date} a {comparison_end_date}")
    
    if selected_country:
        country_config = get_country_config(selected_country)
        country_name = country_config['name'] if country_config else selected_country
        logger.info(f"[GSC REQUEST] País filtrado: {country_name} ({selected_country})")

    # Obtener servicio autenticado
    gsc_service = get_authenticated_service('searchconsole', 'v1')
    if not gsc_service:
        return jsonify({'error': 'Error de autenticación con Google Search Console.', 'auth_required': True}), 401

    def get_base_filters(url_filters=None):
        filters = []
        
        if url_filters:
            filters.extend(url_filters)
        
        if selected_country:
            country_filter = {
                'filters': [{
                    'dimension': 'country',
                    'operator': 'equals',
                    'expression': selected_country
                }]
            }
            filters.append(country_filter)
        
        return filters

    # ✅ NUEVO: Determinar modo de análisis
    analysis_mode = "property" if not form_urls else "page"
    logger.info(f"[GSC REQUEST] Modo de análisis: {analysis_mode}")
    
    # ✅ NUEVA: Obtener datos para tabla de URLs (siempre muestra páginas individuales)
    def fetch_urls_data(start_date, end_date, label_suffix=""):
        period_data = {}
        
        if analysis_mode == "property":
            # SIN filtro de página - obtener TODAS las páginas de la propiedad
            combined_filters = get_base_filters()  # Solo filtros de país si aplica
            
            # Obtener datos de TODAS las páginas de la propiedad (como GSC sin filtros)
            rows_data = fetch_searchconsole_data_single_call(
                gsc_service, site_url_sc, 
                start_date.strftime('%Y-%m-%d'), 
                end_date.strftime('%Y-%m-%d'), 
                ['page'],  # Usar 'page' para obtener todas las páginas individuales
                combined_filters
            )
            
            # Para datos de propiedad completa, procesar cada página individualmente
            for r_item in rows_data:
                page_url = r_item['keys'][0]
                period_label = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}{label_suffix}"
                
                if page_url not in period_data:
                    period_data[page_url] = []
                
                period_data[page_url].append({
                    'Period': period_label,
                    'StartDate': start_date.strftime('%Y-%m-%d'),
                    'EndDate': end_date.strftime('%Y-%m-%d'),
                    'Clicks': r_item['clicks'], 
                    'Impressions': r_item['impressions'],
                    'CTR': r_item['ctr'], 
                    'Position': r_item['position']
                })
            
            logger.info(f"[GSC URLS] Obtenidas {len(period_data)} páginas de la propiedad completa")
        else:
            # CON filtro de página - modo tradicional
            for val_url in form_urls:
                url_filter = [{'filters':[{'dimension':'page','operator':match_type,'expression':val_url}]}]
                combined_filters = get_base_filters(url_filter)
                
                # Obtener datos para este período
                rows_data = fetch_searchconsole_data_single_call(
                    gsc_service, site_url_sc, 
                    start_date.strftime('%Y-%m-%d'), 
                    end_date.strftime('%Y-%m-%d'), 
                    ['page'], 
                    combined_filters
                )
                
                for r_item in rows_data:
                    page_url = r_item['keys'][0]
                    period_label = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}{label_suffix}"
                    
                    if page_url not in period_data:
                        period_data[page_url] = []
                    
                    period_data[page_url].append({
                        'Period': period_label,
                        'StartDate': start_date.strftime('%Y-%m-%d'),
                        'EndDate': end_date.strftime('%Y-%m-%d'),
                        'Clicks': r_item['clicks'], 
                        'Impressions': r_item['impressions'],
                        'CTR': r_item['ctr'], 
                        'Position': r_item['position']
                    })
        
        return period_data

    # ✅ NUEVA: Obtener datos agregados para métricas generales (sin dimensión de página)
    def fetch_summary_data(start_date, end_date, label_suffix=""):
        summary_data = {}
        
        if analysis_mode == "property":
            # SIN filtro de página - obtener datos agregados de toda la propiedad
            combined_filters = get_base_filters()  # Solo filtros de país si aplica
            
            # Obtener datos agregados sin dimensión de página
            rows_data = fetch_searchconsole_data_single_call(
                gsc_service, site_url_sc, 
                start_date.strftime('%Y-%m-%d'), 
                end_date.strftime('%Y-%m-%d'), 
                ['date'],  # Usar 'date' para obtener datos agregados por día
                combined_filters
            )
            
            # Para métricas agregadas, crear una entrada única con totales
            if rows_data:
                # Sumar todos los datos
                total_clicks = sum(r.get('clicks', 0) for r in rows_data)
                total_impressions = sum(r.get('impressions', 0) for r in rows_data)
                total_ctr_weighted = sum(r.get('ctr', 0) * r.get('impressions', 0) for r in rows_data)
                total_pos_weighted = sum(r.get('position', 0) * r.get('impressions', 0) for r in rows_data)
                
                avg_ctr = total_ctr_weighted / total_impressions if total_impressions > 0 else 0
                avg_position = total_pos_weighted / total_impressions if total_impressions > 0 else 0
                
                property_url = f"{site_url_sc} (propiedad completa)"
                period_label = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}{label_suffix}"
                
                summary_data[property_url] = [{
                    'Period': period_label,
                    'StartDate': start_date.strftime('%Y-%m-%d'),
                    'EndDate': end_date.strftime('%Y-%m-%d'),
                    'Clicks': total_clicks, 
                    'Impressions': total_impressions,
                    'CTR': avg_ctr, 
                    'Position': avg_position
                }]
                
                logger.info(f"[GSC SUMMARY] {property_url}: {total_clicks} clicks, {total_impressions} impressions")
        else:
            # Para páginas específicas, usar la misma lógica que URLs
            summary_data = fetch_urls_data(start_date, end_date, label_suffix)
        
        return summary_data

    # ✅ SEPARADO: Obtener datos de URLs (para tabla) y datos de summary (para métricas)
    
    # Datos para tabla de URLs (páginas individuales)
    current_urls_data = fetch_urls_data(current_start, current_end, " (Current)")
    comparison_urls_data = {}
    if has_comparison and comparison_start and comparison_end:
        comparison_urls_data = fetch_urls_data(comparison_start, comparison_end, " (Comparison)")

    # Combinar datos de URLs de ambos períodos
    combined_urls_data = {}
    for page_url, metrics in current_urls_data.items():
        combined_urls_data[page_url] = metrics
    for page_url, metrics in comparison_urls_data.items():
        if page_url in combined_urls_data:
            combined_urls_data[page_url].extend(metrics)
        else:
            combined_urls_data[page_url] = metrics

    # Datos para métricas agregadas (summary)
    current_summary_data = fetch_summary_data(current_start, current_end, " (Current)")
    comparison_summary_data = {}
    if has_comparison and comparison_start and comparison_end:
        comparison_summary_data = fetch_summary_data(comparison_start, comparison_end, " (Comparison)")

    # Combinar datos de summary de ambos períodos
    combined_summary_data = {}
    for page_url, metrics in current_summary_data.items():
        combined_summary_data[page_url] = metrics
    for page_url, metrics in comparison_summary_data.items():
        if page_url in combined_summary_data:
            combined_summary_data[page_url].extend(metrics)
        else:
            combined_summary_data[page_url] = metrics

    # Convertir a formato esperado por el frontend
    pages_payload_list = [{'URL': url, 'Metrics': metrics} for url, metrics in combined_urls_data.items()]
    summary_payload_list = [{'URL': url, 'Metrics': metrics} for url, metrics in combined_summary_data.items()]

    # ✅ ACTUALIZADA: Procesar keywords con soporte para análisis de propiedad completa
    def process_keywords_for_period(start_date, end_date):
        keyword_data = {}
        
        if analysis_mode == "property":
            # SIN filtro de página - obtener keywords agregadas de TODA la propiedad
            combined_filters_kw = get_base_filters()  # Solo filtros de país si aplica
            
            rows_data = fetch_searchconsole_data_single_call(
                gsc_service, site_url_sc,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                ['query'],  # Solo query para obtener keywords agregadas de toda la propiedad
                combined_filters_kw
            )
            
            for r_item in rows_data:
                if len(r_item.get('keys', [])) >= 1:
                    query = r_item['keys'][0]
                    if query not in keyword_data:
                        keyword_data[query] = {
                            'clicks': 0, 'impressions': 0, 'ctr_sum': 0.0, 
                            'pos_sum': 0.0, 'count': 0, 'url': f"{site_url_sc} (propiedad completa)"
                        }
                    
                    kw_entry = keyword_data[query]
                    kw_entry['clicks'] += r_item['clicks']
                    kw_entry['impressions'] += r_item['impressions']
                    kw_entry['ctr_sum'] += r_item['ctr'] * r_item['impressions']
                    kw_entry['pos_sum'] += r_item['position'] * r_item['impressions']
                    kw_entry['count'] += r_item['impressions']
            
            logger.info(f"[GSC KEYWORDS PROPERTY] Obtenidas {len(keyword_data)} keywords agregadas de propiedad completa")
        else:
            # CON filtro de página - modo tradicional
            for val_url_kw in form_urls:
                url_filter_kw = [{'filters':[{'dimension':'page','operator':match_type,'expression':val_url_kw}]}]
                combined_filters_kw = get_base_filters(url_filter_kw)
                
                rows_data = fetch_searchconsole_data_single_call(
                    gsc_service, site_url_sc,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    ['page','query'], 
                    combined_filters_kw
                )
                
                for r_item in rows_data:
                    if len(r_item.get('keys', [])) >= 2:
                        query = r_item['keys'][1]
                        if query not in keyword_data:
                            keyword_data[query] = {
                                'clicks': 0, 'impressions': 0, 'ctr_sum': 0.0, 
                                'pos_sum': 0.0, 'count': 0, 'url': ''
                            }
                        
                        kw_entry = keyword_data[query]
                        kw_entry['url'] = val_url_kw
                        kw_entry['clicks'] += r_item['clicks']
                        kw_entry['impressions'] += r_item['impressions']
                        kw_entry['ctr_sum'] += r_item['ctr'] * r_item['impressions']
                        kw_entry['pos_sum'] += r_item['position'] * r_item['impressions']
                        kw_entry['count'] += r_item['impressions']
        
        return keyword_data

    # Procesar keywords para el período actual SIEMPRE
    current_keywords = process_keywords_for_period(current_start, current_end)
    comparison_keywords = {}
    
    # Solo procesar comparación si existe
    if has_comparison and comparison_start and comparison_end:
        comparison_keywords = process_keywords_for_period(comparison_start, comparison_end)

    # ✅ ACTUALIZADA: Generar estadísticas de keywords (funciona con o sin comparación)
    def generate_keyword_stats(current_kw, comparison_kw=None):
        def process_kw_by_position(kw_data):
            stats = {'total': set(), 'pos1_3': set(), 'pos4_10': set(), 'pos11_20': set(), 'pos20_plus': set()}
            
            for query, data in kw_data.items():
                if data['count'] > 0:
                    avg_pos = data['pos_sum'] / data['count']
                    stats['total'].add(query)
                    
                    if avg_pos <= 3:
                        stats['pos1_3'].add(query)
                    elif avg_pos <= 10:
                        stats['pos4_10'].add(query)
                    elif avg_pos <= 20:
                        stats['pos11_20'].add(query)
                    else:
                        stats['pos20_plus'].add(query)
            
            return stats

        current_stats = process_kw_by_position(current_kw)
        
        # ✅ NUEVO: Estadísticas básicas para período único
        keyword_stats = {
            'overall': {'total': len(current_stats['total'])},
            'total': {'current': len(current_stats['total'])},
            'top3': {'current': len(current_stats['pos1_3'])},
            'top10': {'current': len(current_stats['pos4_10'])},
            'top20': {'current': len(current_stats['pos11_20'])},
            'top20plus': {'current': len(current_stats['pos20_plus'])}
        }
        
        # ✅ NUEVO: Solo calcular comparaciones si hay datos de comparación
        if comparison_kw and len(comparison_kw) > 0:
            comparison_stats = process_kw_by_position(comparison_kw)
            
            # Calcular cambios entre períodos
            for key, label in [('total', 'total'), ('pos1_3', 'top3'), ('pos4_10', 'top10'), 
                               ('pos11_20', 'top20'), ('pos20_plus', 'top20plus')]:
                current_set = current_stats[key]
                comparison_set = comparison_stats[key]
                
                keyword_stats[label].update({
                    'previous': len(comparison_set),
                    'new': len(current_set - comparison_set),
                    'lost': len(comparison_set - current_set),
                    'stay': len(current_set & comparison_set)
                })
            
            # Estadísticas generales de cambio de posiciones
            current_positions = {q: d['pos_sum']/d['count'] for q, d in current_kw.items() if d['count'] > 0}
            comparison_positions = {q: d['pos_sum']/d['count'] for q, d in comparison_kw.items() if d['count'] > 0}
            
            common_queries = set(current_positions.keys()) & set(comparison_positions.keys())
            
            improved = sum(1 for q in common_queries if current_positions[q] < comparison_positions[q])
            worsened = sum(1 for q in common_queries if current_positions[q] > comparison_positions[q])
            same = sum(1 for q in common_queries if current_positions[q] == comparison_positions[q])
            
            keyword_stats['overall'] = {
                'total': len(current_positions),
                'improved': improved,
                'worsened': worsened,
                'same': same,
                'new': len(set(current_positions.keys()) - set(comparison_positions.keys())),
                'lost': len(set(comparison_positions.keys()) - set(current_positions.keys()))
            }
        else:
            # ✅ NUEVO: Para período único, agregar valores por defecto
            for label in ['total', 'top3', 'top10', 'top20', 'top20plus']:
                keyword_stats[label].update({
                    'previous': 0,
                    'new': 0,
                    'lost': 0,
                    'stay': keyword_stats[label]['current']  # Todas las keywords "se mantienen"
                })
            
            # Estadísticas overall para período único
            keyword_stats['overall'].update({
                'improved': 0,
                'worsened': 0,
                'same': 0,
                'new': len(current_stats['total']),  # Todas son "nuevas" para el análisis
                'lost': 0
            })
        
        return keyword_stats

    kw_stats_data = generate_keyword_stats(current_keywords, comparison_keywords)

    # ✅ ACTUALIZADA: Generar datos de comparación de keywords (funciona con período único)
    def generate_keyword_comparison(current_kw, comparison_kw=None):
        comparison_data = []
        
        # ✅ NUEVO: Para período único, mostrar datos del período actual
        if not comparison_kw or len(comparison_kw) == 0:
            for query, current_data in current_kw.items():
                # Calcular métricas del período actual
                current_clicks = current_data['clicks']
                current_impressions = current_data['impressions']
                current_ctr = (current_data['ctr_sum'] / current_data['count'] * 100) if current_data['count'] > 0 else 0
                current_pos = (current_data['pos_sum'] / current_data['count']) if current_data['count'] > 0 else None
                
                comparison_data.append({
                    'keyword': query,
                    'url': current_data.get('url', ''),
                    'clicks_m1': current_clicks,  # Sin período de comparación
                    'clicks_m2': 0,  # Período actual
                    'delta_clicks_percent': 'New',  # Marcado como nuevo
                    'impressions_m1': current_impressions,
                    'impressions_m2': 0,
                    'delta_impressions_percent': 'New',
                    'ctr_m1': current_ctr,
                    'ctr_m2':0 ,
                    'delta_ctr_percent': 'New',
                    'position_m1': current_pos,
                    'position_m2': None,
                    'delta_position_absolute': 'New'
                })
        else:
            # ✅ MANTENER: Lógica original para comparación entre períodos
            all_queries = set(current_kw.keys()) | set(comparison_kw.keys())
            
            for query in all_queries:
                current_data = current_kw.get(query, {'clicks': 0, 'impressions': 0, 'ctr_sum': 0, 'pos_sum': 0, 'count': 0, 'url': ''})
                comparison_data_kw = comparison_kw.get(query, {'clicks': 0, 'impressions': 0, 'ctr_sum': 0, 'pos_sum': 0, 'count': 0, 'url': ''})
                
                # Calcular métricas
                current_clicks = current_data['clicks']
                comparison_clicks = comparison_data_kw['clicks']
                
                current_impressions = current_data['impressions']
                comparison_impressions = comparison_data_kw['impressions']
                
                current_ctr = (current_data['ctr_sum'] / current_data['count'] * 100) if current_data['count'] > 0 else 0
                comparison_ctr = (comparison_data_kw['ctr_sum'] / comparison_data_kw['count'] * 100) if comparison_data_kw['count'] > 0 else 0
                
                current_pos = (current_data['pos_sum'] / current_data['count']) if current_data['count'] > 0 else None
                comparison_pos = (comparison_data_kw['pos_sum'] / comparison_data_kw['count']) if comparison_data_kw['count'] > 0 else None
                
                # Calcular cambios
                def calculate_percentage_change(new_val, old_val):
                    if old_val == 0:
                        return 'Infinity' if new_val > 0 else 0
                    return ((new_val / old_val) - 1) * 100
                
                delta_clicks = calculate_percentage_change(current_clicks, comparison_clicks)
                delta_impressions = calculate_percentage_change(current_impressions, comparison_impressions)
                delta_ctr = current_ctr - comparison_ctr  # Diferencia absoluta en puntos porcentuales
                
                if current_pos is not None and comparison_pos is not None:
                    delta_position = comparison_pos - current_pos  # Positivo = mejora
                elif current_pos is not None:
                    delta_position = 'New'
                else:
                    delta_position = 'Lost'
                
                comparison_data.append({
                    'keyword': query,
                    'url': current_data.get('url') or comparison_data_kw.get('url'),
                    'clicks_m1': current_clicks,      # ✅ Actual en P1
                    'clicks_m2': comparison_clicks,   # ✅ Comparación en P2
                    'delta_clicks_percent': calculate_percentage_change(current_clicks, comparison_clicks),  # ✅ (P1 / P2 - 1) * 100
                    'impressions_m1': current_impressions,
                    'impressions_m2': comparison_impressions,
                    'delta_impressions_percent': calculate_percentage_change(current_impressions, comparison_impressions),
                    'ctr_m1': current_ctr,
                    'ctr_m2': comparison_ctr,
                    'delta_ctr_percent': current_ctr - comparison_ctr,  # Diferencia absoluta en puntos porcentuales
                    'position_m1': current_pos,
                    'position_m2': comparison_pos,
                    'delta_position_absolute': comparison_pos - current_pos if current_pos is not None and comparison_pos is not None else ('New' if current_pos is not None else 'Lost')
                })
        
        return comparison_data

    # ✅ NUEVO: Generar datos de keywords SIEMPRE (con o sin comparación)
    keyword_comparison_data = generate_keyword_comparison(current_keywords, comparison_keywords)

    # ✅ ACTUALIZADA: Respuesta con información de períodos y modo de análisis
    response_data = {
        'pages': pages_payload_list,  # Para tabla de URLs (páginas individuales)
        'summary': summary_payload_list,  # Para métricas agregadas 
        'keywordStats': kw_stats_data,
        'keyword_comparison_data': keyword_comparison_data,  # ✅ NUEVO: Siempre incluido
        'selected_country': selected_country,
        'analysis_mode': analysis_mode,  # ✅ NUEVO: Modo de análisis
        'analysis_info': {
            'mode': analysis_mode,
            'is_property_analysis': analysis_mode == "property",
            'domain': site_url_sc,
            'url_count': len(form_urls)
        },
        'periods': {
            'current': {
                'start_date': current_start_date,
                'end_date': current_end_date,
                'label': f"{current_start_date} to {current_end_date}"
            },
            'has_comparison': has_comparison,
            'comparison_mode': comparison_mode
        }
    }
    
    if has_comparison and comparison_start_date and comparison_end_date:
        response_data['periods']['comparison'] = {
            'start_date': comparison_start_date,
            'end_date': comparison_end_date,
            'label': f"{comparison_start_date} to {comparison_end_date}"
        }
    
    logger.info(f"[RESPONSE] Keywords encontradas: {len(keyword_comparison_data)}")
    logger.info(f"[RESPONSE] Total KWs: {kw_stats_data.get('overall', {}).get('total', 0)}")
    
    return jsonify(response_data)

@app.route('/download-excel', methods=['POST'])
@login_required  # NUEVO: Requiere autenticación
def download_excel():
    # ... (el resto del código permanece igual)
    try:
        if not request.is_json:
            return jsonify({'error': 'Se esperaba contenido JSON'}), 400
            
        json_payload = request.get_json()
        
        data_processed = json_payload.get('data')
        ai_overview_data_excel = json_payload.get('ai_overview_data')
        metadata = json_payload.get('metadata', {})
        
        if not data_processed:
            return jsonify({'error': 'No se proporcionaron datos para generar el Excel'}), 400
            
        if not isinstance(data_processed, dict) or 'pages' not in data_processed:
            return jsonify({'error': 'Estructura de datos inválida'}), 400
        
        logger.info(f"Generando Excel con {len(data_processed.get('pages', []))} páginas y {len(data_processed.get('keyword_comparison_data', []))} keywords")
        
        if ai_overview_data_excel:
            logger.info("Incluyendo datos de AI Overview en el Excel")
        
        try:
            xlsx_file = generate_excel_from_data(data_processed, ai_overview_data_excel)
            
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            ai_suffix = "_con_AI" if ai_overview_data_excel else ""
            filename = f'search_console_report{ai_suffix}_{timestamp}.xlsx'
            
            return send_file(
                xlsx_file,
                download_name=filename,
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        except Exception as e:
            logger.error(f"Error generando Excel: {e}", exc_info=True)
            return jsonify({'error': f'Error generando Excel: {str(e)}'}), 500
    
    except Exception as e:
        logger.error(f"Error general en download_excel: {e}", exc_info=True)
        return jsonify({'error': f'Error procesando solicitud: {str(e)}'}), 500

# --- Las rutas de SERP no requieren autenticación (son públicas) ---
@app.route('/api/serp')
def get_serp_raw_json():
    keyword_query = request.args.get('keyword')
    country_param = request.args.get('country', '')
    api_key_val = os.getenv('SERPAPI_KEY')
    
    if not keyword_query: 
        return jsonify({'error':'keyword es requerido'}), 400
    if not api_key_val:
        return jsonify({'error':'API key de SerpAPI no configurada'}), 500
        
    params_serp = get_serp_params_with_location(keyword_query, api_key_val, country_param)
    
    try:
        serp_data_json = get_serp_json(params_serp)
        return jsonify({
            'organic_results': serp_data_json.get('organic_results', []), 
            'ads': serp_data_json.get('ads', [])
        })
    except Exception as e:
        logger.error(f"Error en /api/serp para keyword '{keyword_query}': {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/serp/position')
def get_serp_position():
    keyword_val = request.args.get('keyword')
    site_url_val = request.args.get('site_url', '')
    country_param = request.args.get('country', '')
    api_key_serp = os.getenv('SERPAPI_API_KEY')
    
    if not keyword_val or not site_url_val:
        return jsonify({'error': 'keyword y site_url son requeridos'}), 400
    if not api_key_serp:
        return jsonify({'error': 'API key de SerpAPI no configurada'}), 500
    
    logger.info(f"[SERP POSITION] Iniciando búsqueda para '{keyword_val}' en '{site_url_val}' (País: {country_param or 'España'})")
    
    params_serp = get_serp_params_with_location(keyword_val, api_key_serp, country_param)
    
    try:
        serp_data_pos = get_serp_json(params_serp)
        
        if not serp_data_pos:
            logger.error(f"[SERP POSITION] No se obtuvo respuesta de SerpAPI para '{keyword_val}'")
            return jsonify({'error': 'No se obtuvo respuesta de SerpAPI'}), 500
        
        organic_results_list = serp_data_pos.get('organic_results', [])
        logger.info(f"[SERP POSITION] Obtenidos {len(organic_results_list)} resultados orgánicos para '{keyword_val}'")
        
        if not organic_results_list:
            logger.warning(f"[SERP POSITION] No hay resultados orgánicos para '{keyword_val}'")
            return jsonify({
                'keyword': keyword_val,
                'domain': normalize_search_console_url(site_url_val),
                'found': False,
                'position': None,
                'result': None,
                'result_type': None,
                'all_matches': [],
                'total_results': 0,
                'timestamp': time.time(),
                'error': 'No se encontraron resultados orgánicos'
            })
        
        position_info = get_site_position_from_serp(keyword_val, site_url_val, organic_results_list, serp_data_pos)
        
        result_type = position_info.get('result_type', 'Unknown')
        position = position_info['position']
        if position == 0:
            logger.info(f"[SERP POSITION] Resultado: found={position_info['found']}, position=#0 ({result_type} - Resultado Enriquecido)")
        elif position:
            logger.info(f"[SERP POSITION] Resultado: found={position_info['found']}, position=#{position} ({result_type})")
        else:
            logger.info(f"[SERP POSITION] Resultado: found={position_info['found']}, position=No encontrado")
        
        return jsonify({
            'keyword': keyword_val,
            'domain': normalize_search_console_url(site_url_val),
            'found': position_info['found'],
            'position': position_info['position'],
            'result': position_info['result'],
            'result_type': position_info.get('result_type', 'Unknown'),
            'all_matches': position_info['all_matches'],
            'total_results': position_info['total_results'],
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"[SERP POSITION] Error para keyword '{keyword_val}': {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'keyword': keyword_val,
            'domain': normalize_search_console_url(site_url_val),
            'found': False,
            'position': None,
            'result': None,
            'result_type': None,
            'all_matches': [],
            'total_results': 0,
            'timestamp': time.time()
        }), 500

@app.route('/api/serp/screenshot')
def get_serp_screenshot_route():
    keyword_param = request.args.get('keyword')
    site_url_param = request.args.get('site_url', '')
    country_param = request.args.get('country', '')
    api_key_env = os.getenv('SERPAPI_API_KEY')

    if not keyword_param or not site_url_param:
        return jsonify({'error': 'keyword y site_url son requeridos'}), 400
    if not api_key_env:
         logger.error("API key de SerpAPI no configurada para screenshot.")
         return jsonify({'error': 'API key de SerpAPI no configurada en el servidor'}), 500
    
    try:
        logger.info(f"Solicitando screenshot para keyword: '{keyword_param}', site_url: '{site_url_param}', país: {country_param or 'España'}")
        return get_page_screenshot(keyword=keyword_param, site_url_to_highlight=site_url_param, api_key=api_key_env, country=country_param)
    except Exception as e:
        logger.error(f"[SCREENSHOT ROUTE] Error para keyword '{keyword_param}': {e}", exc_info=True)
        return jsonify({'error': f'Error general al generar screenshot: {e}'}), 500

def analyze_single_keyword_ai_impact(keyword_arg, site_url_arg, country_code=None):
    api_key_env_val = os.getenv('SERPAPI_API_KEY')
    if not api_key_env_val:
        logger.error("SERPAPI_API_KEY no está configurada para analyze_single_keyword_ai_impact")
        return {
            'keyword': keyword_arg, 'error': "SERPAPI_API_KEY no está configurada",
            'ai_analysis': {'has_ai_overview': False, 'debug_info': {'error': "API key missing"}},
            'site_position': None, 'site_result': None, 'organic_results_count': 0,
            'serp_features': [], 'timestamp': time.time(), 'serpapi_success': False
        }
    
    params_ai = get_serp_params_with_location(keyword_arg, api_key_env_val, country_code)
    
    try:
        serp_data_from_service = get_serp_json(params_ai)
            
        if not serp_data_from_service or "error" in serp_data_from_service:
            error_msg = serp_data_from_service.get("error", "El servicio get_serp_json devolvió datos vacíos o con error")
            logger.warning(f"Error SERP para '{keyword_arg}': {error_msg}")
            raise Exception(error_msg)

        ai_analysis_data = detect_ai_overview_elements(serp_data_from_service, site_url_arg)
        organic_results_data = serp_data_from_service.get('organic_results', [])
        site_pos_info = get_site_position_from_serp(keyword_arg, site_url_arg, organic_results_data, serp_data_from_service)
        
        # Procesar SERP features de forma más eficiente
        serp_features_output_list = []
        feature_type_keys = [
            'ads', 'shopping_results', 'local_results', 'news_results', 
            'video_results', 'images_results', 'people_also_ask', 
            'related_questions', 'knowledge_graph', 'featured_snippet'
        ]
        for feature_key_item in feature_type_keys:
            if feature_key_item in serp_data_from_service and serp_data_from_service[feature_key_item]:
                feature_data_val = serp_data_from_service[feature_key_item]
                if isinstance(feature_data_val, list):
                    serp_features_output_list.append(f"{feature_key_item}: {len(feature_data_val)} elementos")
                else:
                    serp_features_output_list.append(f"{feature_key_item}: presente")
        
        final_result_dict = {
            'keyword': keyword_arg, 
            'ai_analysis': ai_analysis_data,
            'site_position': site_pos_info['position'],
            'site_result': site_pos_info['result'],
            'result_type': site_pos_info.get('result_type', 'Unknown'),
            'organic_results_count': len(organic_results_data),
            'serp_features': serp_features_output_list,
            'timestamp': time.time(), 
            'serpapi_success': True
        }
        
        return final_result_dict
        
    except Exception as e:
        logger.error(f"Error analizando keyword '{keyword_arg}': {str(e)}")
        return {
            'keyword': keyword_arg, 'error': str(e),
            'ai_analysis': {
                'has_ai_overview': False, 'ai_overview_detected': [], 'total_elements': 0,
                'impact_score': 0, 'domain_is_ai_source': False,
                'domain_ai_source_position': None, 'domain_ai_source_link': None,
                'debug_info': {'error': str(e)}
            },
            'site_position': None, 'site_result': None, 'result_type': None,
            'organic_results_count': 0, 'serp_features': [], 'timestamp': time.time(), 'serpapi_success': False
        }

def analyze_keywords_parallel(keywords_data_list, site_url_req, country_req, max_workers=3):
    """
    Analiza múltiples keywords en paralelo para mejorar la velocidad del análisis de AI Overview.
    
    Args:
        keywords_data_list: Lista de datos de keywords a analizar
        site_url_req: URL del sitio para analizar
        country_req: Código de país para el análisis
        max_workers: Número máximo de hilos concurrentes (default: 3)
    
    Returns:
        tuple: (results_list, errors_list, successful_analyses_count)
    """
    results_list = []
    errors_list = []
    successful_analyses = 0
    
    # Usar ThreadPoolExecutor para procesamiento paralelo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Crear un mapeo de futuros a datos de keyword
        future_to_keyword = {
            executor.submit(analyze_single_keyword_ai_impact, kw_data['keyword'], site_url_req, country_req): kw_data
            for kw_data in keywords_data_list
        }
        
        # Procesar resultados conforme van completándose
        for i, future in enumerate(as_completed(future_to_keyword), 1):
            kw_data_item = future_to_keyword[future]
            keyword_str = kw_data_item.get('keyword', '')
            
            try:
                ai_result_item = future.result()
                current_ai_analysis = ai_result_item.get('ai_analysis', {})
                
                # Log de progreso cada 5 keywords procesadas
                if i % 5 == 0 or i == len(keywords_data_list):
                    logger.info(f"✅ Progreso: {i}/{len(keywords_data_list)} keywords procesadas")
                    # TODO: En futuras versiones, enviar progreso real al frontend via SSE
                
                if 'ai_analysis' not in ai_result_item:
                    ai_result_item['ai_analysis'] = {
                        'has_ai_overview': False,
                        'ai_overview_detected': [],
                        'total_elements': 0,
                        'impact_score': 0,
                        'domain_is_ai_source': False,
                        'domain_ai_source_position': None,
                        'domain_ai_source_link': None
                    }

                combined_result = {
                    **kw_data_item,
                    **ai_result_item,
                    'delta_clicks_absolute': kw_data_item.get('clicks_m2', 0) - kw_data_item.get('clicks_m1', 0),
                    'analysis_successful': ai_result_item.get('serpapi_success', True),
                    'country_analyzed': country_req
                }
                
                results_list.append(combined_result)
                
                if ai_result_item.get('serpapi_success', True):
                    successful_analyses += 1

            except Exception as e:
                error_msg = f"❌ Keyword falló: '{keyword_str}' - Error: {e}"
                logger.error(error_msg)
                errors_list.append(error_msg)
                
                error_result = {
                    **kw_data_item,
                    'error': str(e),
                    'ai_analysis': {},
                    'analysis_successful': False,
                    'country_analyzed': country_req
                }
                results_list.append(error_result)
    
    return results_list, errors_list, successful_analyses

@app.route('/api/analyze-ai-overview', methods=['POST'])
@login_required  # NUEVO: Requiere autenticación
def analyze_ai_overview_route():
    try:
        request_payload = request.get_json()
        keywords_data_list = request_payload.get('keywords', [])
        site_url_req = request_payload.get('site_url', '')
        country_req = request_payload.get('country', '')
        
        logger.info("=== INICIANDO ANÁLISIS AI OVERVIEW ===")

        # 🔍 DEBUGGING: ¿Qué país se está usando?
        logger.info(f"=== AI OVERVIEW COUNTRY DEBUG ===")
        logger.info(f"Country from payload: '{country_req}'")
        logger.info(f"Country is empty: {not country_req}")
        logger.info(f"Country fallback logic needed: {not country_req}")
        logger.info("==================================")
        
        # NUEVO: Logging que explica la lógica de negocio 
        if country_req:
            country_config = get_country_config(country_req)
            if country_config:
                if country_req == 'esp':
                    logger.info(f"[AI BUSINESS LOGIC] 🔄 Analizando desde España (fallback o país principal)")
                else:
                    logger.info(f"[AI BUSINESS LOGIC] 👑 Analizando desde país principal del negocio: {country_config['name']} ({country_req})")
                logger.info(f"[AI BUSINESS LOGIC] 📍 Simulando búsquedas desde: {country_config['serp_location']}")
            else:
                logger.warning(f"[AI BUSINESS LOGIC] ⚠️ País no reconocido: {country_req}")
        else:
            logger.info("[AI BUSINESS LOGIC] 🌍 Sin país especificado (análisis global)")
        
        if not keywords_data_list:
            return jsonify({'error': 'No se proporcionaron keywords para analizar'}), 400
        if not site_url_req:
            return jsonify({'error': 'site_url es requerido'}), 400
        
        serpapi_key = os.getenv('SERPAPI_API_KEY')
        if not serpapi_key:
            logger.error("SERPAPI_API_KEY no configurada para ruta analyze-ai-overview")
            return jsonify({'error': 'API key de SerpAPI no configurada en el servidor'}), 500
        
        original_count = len(keywords_data_list)
        keywords_to_process_list = keywords_data_list[:30] # Aumentado a 30 para permitir más pruebas
        if original_count > 30:
            logger.warning(f"Se truncaron {original_count - 30} keywords. Analizando solo las primeras 30.")
        
        # Optimizar workers basado en el número de keywords
        num_keywords = len(keywords_to_process_list)
        if num_keywords <= 10:
            max_workers = 2  # Análisis pequeño
        elif num_keywords <= 20:
            max_workers = 3  # Análisis medio
        else:
            max_workers = 4  # Análisis grande (máximo para evitar rate limiting)
            
        logger.info(f"🚀 Iniciando análisis paralelo de {num_keywords} keywords con {max_workers} workers")
        
        results_list_overview, errors_list_overview, successful_analyses_overview = analyze_keywords_parallel(
            keywords_to_process_list, 
            site_url_req, 
            country_req, 
            max_workers
        )
        
        results_list_overview.sort(key=lambda x_item_sort: x_item_sort.get('delta_clicks_absolute', 0))

        total_analyzed_overview = len(results_list_overview)
        summary_overview_stats = {
            'total_keywords_analyzed': total_analyzed_overview,
            'successful_analyses': successful_analyses_overview,
            'keywords_with_ai_overview': sum(1 for r_item in results_list_overview if r_item.get('ai_analysis', {}).get('has_ai_overview', False)),
            'keywords_with_ai_elements': sum(1 for r_item in results_list_overview if r_item.get('ai_analysis', {}).get('total_elements', 0) > 0),
            'keywords_as_ai_source': sum(1 for r_item in results_list_overview if r_item.get('ai_analysis', {}).get('domain_is_ai_source', False)),
            'total_estimated_clicks_lost': abs(sum(
                r_item.get('delta_clicks_absolute', 0)
                for r_item in results_list_overview
                if r_item.get('delta_clicks_absolute', 0) < 0
            )),
            'analysis_timestamp': time.time(),
            'country_analyzed': country_req # NUEVO: País analizado
        }

        response_data_overview = {
            'results': results_list_overview,
            'summary': summary_overview_stats,
            'timestamp': time.time(),
            'debug_mode': True
        }
        if errors_list_overview:
            response_data_overview['warnings'] = errors_list_overview
        return jsonify(response_data_overview)

    except Exception as e_overview_critical:
        logger.error(f"Error crítico en analyze_ai_overview_route: {str(e_overview_critical)}", exc_info=True)
        return jsonify({
            'error': str(e_overview_critical),
            'results': [],
            'summary': {}
        }), 500


    
@app.route('/api/test-url-matching', methods=['POST'])
def test_url_matching_route():
    # Esta ruta puede permanecer pública para testing
    try:
        data_req_match = request.get_json()
        serp_url_req = data_req_match.get('serp_url', '')
        site_url_req_match = data_req_match.get('site_url', '')

        if not serp_url_req or not site_url_req_match:
            return jsonify({'error': 'serp_url y site_url son requeridos'}), 400

        serp_domain_res = extract_domain(serp_url_req)
        sc_domain_res = normalize_search_console_url(site_url_req_match)
        matches_res = urls_match(serp_url_req, site_url_req_match)

        result_match_test = {
            'serp_domain': serp_domain_res,
            'sc_domain': sc_domain_res,
            'matches': matches_res
        }
        return jsonify(result_match_test)

    except Exception as e_match_test_route:
        logger.error(f"Error en test_url_matching_route: {e_match_test_route}", exc_info=True)
        return jsonify({'error': str(e_match_test_route)}), 500

@app.route('/get-available-countries', methods=['POST'])
@login_required  # NUEVO: Requiere autenticación
def get_available_countries():
    site_url = request.json.get('site_url', '')
    if not site_url:
        return jsonify({'error': 'site_url es requerido'}), 400
    
    gsc_service = get_authenticated_service('searchconsole', 'v1')
    if not gsc_service:
        return jsonify({'error': 'Error de autenticación'}), 401
    
    try:
        end_date = pd.Timestamp.now()
        start_date = end_date - pd.DateOffset(months=3)
        
        countries_data = fetch_searchconsole_data_single_call(
            gsc_service, 
            site_url, 
            start_date.strftime('%Y-%m-%d'), 
            end_date.strftime('%Y-%m-%d'), 
            ['country'],
            []
        )
        
        countries_summary = {}
        for row in countries_data:
            country_code = row['keys'][0]
            countries_summary[country_code] = {
                'impressions': row['impressions'],
                'clicks': row['clicks']
            }
        
        # Ordenar por clics descendente 
        sorted_countries = sorted(
            countries_summary.items(), 
            key=lambda x: x[1]['clicks'], 
            reverse=True
        )
        
        # NUEVO: Logging para entender la lógica de negocio 
        if sorted_countries:
            top_country = sorted_countries[0]
            top_country_config = get_country_config(top_country[0])
            top_country_name = top_country_config['name'] if top_country_config else top_country[0]
            
            logger.info(f"[BUSINESS LOGIC] 👑 País principal del negocio detectado: {top_country_name} ({top_country[0]}) con {top_country[1]['clicks']:,} clics")
            logger.info(f"[BUSINESS LOGIC] 📊 Total países con tráfico: {len(sorted_countries)}")
            
            # Mostrar top 3 para contexto 
            for i, (code, data) in enumerate(sorted_countries[:3]):
                config = get_country_config(code)
                name = config['name'] if config else code
                logger.info(f"[BUSINESS LOGIC] #{i+1}: {name} ({code}) - {data['clicks']:,} clics")
        else:
            logger.warning(f"[BUSINESS LOGIC] ⚠️ No se encontraron países con tráfico para {site_url}")
        
        return jsonify({
            'countries': [
                {
                    'code': code,
                    'impressions': data['impressions'],
                    'clicks': data['clicks']
                }
                for code, data in sorted_countries
            ]
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo países: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    
@app.route('/debug-serp-params')
def debug_serp_params():
    keyword = request.args.get('keyword', 'test')
    country = request.args.get('country', 'esp')
    
    # Parámetros para AI Analysis
    ai_params = get_serp_params_with_location(keyword, os.getenv('SERPAPI_API_KEY'), country)
    
    # Parámetros para Screenshot (simulando serp_service.py)
    screenshot_params = {
        'engine': 'google',
        'q': keyword,
        'api_key': os.getenv('SERPAPI_API_KEY'),
        'gl': 'es',
        'hl': 'es',
        'num': 20
    }
    
    if country:
        country_config = get_country_config(country)
        if country_config:
            screenshot_params.update({
                'location': country_config['serp_location'],
                'gl': country_config['serp_gl'],
                'hl': country_config['serp_hl'],
                'google_domain': country_config['google_domain']
            })
    
    return jsonify({
        'ai_params': ai_params,
        'screenshot_params': screenshot_params,
        'are_identical': ai_params == screenshot_params
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Railway lo asigna automáticamente
    app.run(host='0.0.0.0', port=port, debug=False)
