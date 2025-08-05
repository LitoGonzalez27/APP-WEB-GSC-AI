import os
import sys
import json
import time
import logging
import traceback
import zipfile
from io import BytesIO
from datetime import datetime, timedelta # Importación añadida
from flask import Flask, render_template, request, jsonify, send_file, Response, session, redirect, url_for
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
from services.serp_service import get_serp_json, get_serp_html, get_page_screenshot, SCREENSHOT_CACHE
from services.ai_analysis import detect_ai_overview_elements
from services.utils import extract_domain, normalize_search_console_url, urls_match
from services.country_config import get_country_config

# --- NUEVO: Sistema de autenticación ---
from auth import (
    setup_auth_routes,
    login_required,
    auth_required,
    admin_required,
    is_user_authenticated,
    get_authenticated_service,
    get_user_credentials,
    get_current_user
)

# --- NUEVO: Detector de dispositivos móviles ---
from mobile_detector import (
    should_block_mobile_access,
    get_device_info,
    get_device_type,
    log_device_access
)

# --- NUEVO: Base de datos y caché para AI Overview ---
from database import (
    init_database, 
    save_ai_overview_analysis, 
    get_ai_overview_stats,
    get_ai_overview_history
)
from services.ai_cache import ai_cache

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

# Configuración automática según entorno
railway_env = os.getenv('RAILWAY_ENVIRONMENT', '')
is_production = railway_env == 'production'
is_staging = railway_env == 'staging'
is_development = not railway_env or railway_env == 'development'

logger.info(f"🌍 Entorno detectado: {railway_env or 'development'}")
logger.info(f"📊 Configuración: Production={is_production}, Staging={is_staging}, Development={is_development}")

# Configurar cookies de sesión según el entorno
app.config['SESSION_COOKIE_SECURE'] = is_production or is_staging  # HTTPS en producción y staging
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configuraciones adicionales para producción y staging
if is_production or is_staging:
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    logger.info("✅ Configuración HTTPS habilitada para entorno no-development")

# --- NUEVO: Configurar rutas de autenticación ---
setup_auth_routes(app)

# --- Funciones auxiliares con geolocalización (sin cambios) ---
def get_top_country_for_site(site_url):
    """
    Determina dinámicamente el país con más clics para un sitio específico
    para usar como geolocalización en SERP API cuando no se especifica país.
    """
    try:
        gsc_service = get_authenticated_service('searchconsole', 'v1')
        if not gsc_service:
            logger.warning("No se pudo obtener servicio autenticado para determinar país principal")
            return 'esp'  # fallback
            
        # Obtener datos de los últimos 3 meses
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
        
        if not countries_data:
            logger.info(f"[DYNAMIC COUNTRY] Sin datos de países para {site_url}, usando España")
            return 'esp'
            
        # Ordenar por clics y obtener el país principal
        sorted_countries = sorted(countries_data, key=lambda x: x['clicks'], reverse=True)
        top_country = sorted_countries[0]['keys'][0]
        
        # Validar que el país esté en nuestra configuración
        country_config = get_country_config(top_country)
        if not country_config:
            logger.warning(f"[DYNAMIC COUNTRY] País {top_country} no configurado, usando España")
            return 'esp'
            
        logger.info(f"[DYNAMIC COUNTRY] País con más clics detectado: {country_config['name']} ({top_country}) con {sorted_countries[0]['clicks']:,} clics")
        return top_country
        
    except Exception as e:
        logger.error(f"Error determinando país principal para {site_url}: {e}")
        return 'esp'  # fallback seguro

def get_serp_params_with_location(keyword, api_key, country_code=None, site_url=None):
    """
    Genera parámetros para SERP API con geolocalización según el país.
    Si no se especifica country_code, determina dinámicamente el país con más clics.
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
    
    # ✅ NUEVA LÓGICA: Si no hay país específico, usar país con más clics dinámicamente
    if not country_code and site_url:
        country_code = get_top_country_for_site(site_url)
        logger.info(f"[SERP DYNAMIC] Usando país con más clics: {country_code}")
    
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
            logger.info(f"[SERP GEOLOCATION] Usando configuración para {country_config['name']}")
    else:
        # ✅ FALLBACK: Si no hay país, usar España como fallback para consistencia
        country_config = get_country_config('esp')
        if country_config:
            params.update({
                'location': country_config['serp_location'],
                'google_domain': country_config['google_domain']
            })
            logger.info(f"[SERP GEOLOCATION] Sin país especificado, usando España por defecto")
    
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
@auth_required  # NUEVO: Requiere autenticación
def get_properties():
    """Obtiene propiedades de Search Console del usuario autenticado"""
    sites = fetch_validated_sites()
    props = [{'siteUrl': s['siteUrl']} for s in sites if s.get('siteUrl')]
    return jsonify({'properties': props})

@app.route('/mobile-not-supported')
def mobile_not_supported():
    """
    Página de error para dispositivos móviles no compatibles.
    """
    # Registrar el acceso desde dispositivo móvil
    log_device_access(logger)
    
    device_info = get_device_info()
    logger.info(f"Usuario redirigido a página de error móvil - "
                f"Tipo: {get_device_type()}, "
                f"IP: {device_info['remote_addr']}")
    
    return render_template('mobile_error.html')


@app.route('/')
def landing():
    """
    Landing page - página de bienvenida sin autenticación requerida
    """
    # Si ya está autenticado, redirigir al dashboard
    if is_user_authenticated():
        return redirect(url_for('dashboard'))
    
    return render_template('landing.html')

@app.route('/dashboard')
@auth_required
def dashboard():
    """
    Dashboard principal - requiere autenticación y bloquea dispositivos móviles
    """
    # Registrar información del dispositivo
    log_device_access(logger)
    
    # Verificar si es un dispositivo móvil
    if should_block_mobile_access():
        device_type = get_device_type()
        logger.info(f"Acceso bloqueado desde dispositivo móvil - Tipo: {device_type}")
        return redirect(url_for('mobile_not_supported'))
    
    # Si no es móvil, mostrar el dashboard
    device_type = get_device_type()
    logger.info(f"Acceso permitido desde dispositivo: {device_type}")
    
    # Obtener información completa del usuario
    user = get_current_user()
    if not user:
        return redirect(url_for('login_page'))
    
    return render_template('dashboard.html', user=user, authenticated=True)

@app.route('/app')
@auth_required
def app_main():
    """
    Aplicación principal de análisis SEO - requiere autenticación
    """
    # Registrar información del dispositivo
    log_device_access(logger)
    
    # Verificar si es un dispositivo móvil
    if should_block_mobile_access():
        device_type = get_device_type()
        logger.info(f"Acceso bloqueado desde dispositivo móvil - Tipo: {device_type}")
        return redirect(url_for('mobile_not_supported'))
    
    # Si no es móvil, mostrar la aplicación de análisis
    device_type = get_device_type()
    logger.info(f"Acceso permitido desde dispositivo: {device_type}")
    
    user = get_current_user()
    user_email = user['email'] if user else None
    
    return render_template('index.html', user_email=user_email, authenticated=True)

@app.route('/get-data', methods=['POST'])
@auth_required
def get_data():
    """Obtiene datos de Search Console con fechas específicas y comparación opcional"""
    
    # ✅ NUEVO: Detectar dispositivos móviles para ajustar timeouts
    user_agent = request.headers.get('User-Agent', '')
    is_mobile = any(device in user_agent.lower() for device in ['android', 'iphone', 'ipad', 'mobile', 'blackberry'])
    x_requested_with = request.headers.get('X-Requested-With')
    
    if is_mobile:
        logger.info(f"[MOBILE] Dispositivo móvil detectado: {user_agent[:50]}...")
    
    try:
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
            error_msg = 'Fechas del período principal son requeridas.'
            if is_mobile:
                error_msg += ' Asegúrate de seleccionar fechas válidas en el selector.'
            return jsonify({'error': error_msg}), 400
        
        if not site_url_sc:
            error_msg = 'Debes seleccionar un dominio antes de continuar.'
            if is_mobile:
                error_msg += ' Usa el selector de dominios en la parte superior.'
            return jsonify({'error': error_msg}), 400

        # ✅ NUEVO: Validaciones específicas para móviles
        if is_mobile and form_urls and len(form_urls) > 10:
            return jsonify({
                'error': 'En dispositivos móviles, se recomienda analizar máximo 10 URLs a la vez para evitar timeouts. Reduce el número de URLs e inténtalo de nuevo.'
            }), 400

        # ✅ NUEVO: Validar formato de fechas
        try:
            current_start = datetime.strptime(current_start_date, '%Y-%m-%d').date()
            current_end = datetime.strptime(current_end_date, '%Y-%m-%d').date()
            
            if current_start >= current_end:
                return jsonify({'error': 'La fecha de inicio debe ser anterior a la fecha de fin.'}), 400
                
            # ✅ NUEVO: Validación específica para móviles sobre períodos largos
            period_days = (current_end - current_start).days + 1
            if is_mobile and period_days > 90:
                return jsonify({
                    'error': 'En dispositivos móviles, se recomienda analizar períodos de máximo 90 días para evitar timeouts. Selecciona un período más corto.'
                }), 400
                
            # Validar que las fechas estén dentro del rango permitido por GSC
            max_date = datetime.now().date() - timedelta(days=3)  # GSC tiene delay
            min_date = max_date - timedelta(days=16*30)  # ~16 meses atrás
            
            if current_start < min_date or current_end > max_date:
                return jsonify({'error': f'Las fechas deben estar entre {min_date} y {max_date}.'}), 400
                
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD.'}), 400

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
            error_msg = 'Error de autenticación con Google Search Console.'
            if is_mobile:
                error_msg += ' Tu sesión puede haber expirado. Intenta recargar la página.'
            return jsonify({'error': error_msg, 'auth_required': True}), 401

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

        # ✅ CORREGIDO: Combinar datos asegurando que hay métricas para ambos períodos si se seleccionó comparación
        combined_urls_data = {}
        
        if has_comparison and comparison_start and comparison_end:
            # Si hay comparación, asegurar que todas las URLs tengan datos para ambos períodos
            all_urls = set(current_urls_data.keys()) | set(comparison_urls_data.keys())
            
            for page_url in all_urls:
                current_metric = current_urls_data.get(page_url, [])
                comparison_metric = comparison_urls_data.get(page_url, [])
                
                # Si no hay datos para el período actual, crear entrada con 0s
                if not current_metric:
                    current_metric = [{
                        'Period': f"{current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')} (Current)",
                        'StartDate': current_start.strftime('%Y-%m-%d'),
                        'EndDate': current_end.strftime('%Y-%m-%d'),
                        'Clicks': 0,
                        'Impressions': 0,
                        'CTR': 0.0,
                        'Position': 0.0
                    }]
                
                # Si no hay datos para el período de comparación, crear entrada con 0s
                if not comparison_metric:
                    comparison_metric = [{
                        'Period': f"{comparison_start.strftime('%Y-%m-%d')} to {comparison_end.strftime('%Y-%m-%d')} (Comparison)",
                        'StartDate': comparison_start.strftime('%Y-%m-%d'),
                        'EndDate': comparison_end.strftime('%Y-%m-%d'),
                        'Clicks': 0,
                        'Impressions': 0,
                        'CTR': 0.0,
                        'Position': 0.0
                    }]
                
                # Combinar ambos períodos (actual + comparación)
                combined_urls_data[page_url] = current_metric + comparison_metric
        else:
            # Sin comparación, usar solo datos actuales
            combined_urls_data = current_urls_data

        # Datos para métricas agregadas (summary)
        current_summary_data = fetch_summary_data(current_start, current_end, " (Current)")
        comparison_summary_data = {}
        if has_comparison and comparison_start and comparison_end:
            comparison_summary_data = fetch_summary_data(comparison_start, comparison_end, " (Comparison)")

        # ✅ CORREGIDO: Combinar datos de summary asegurando que hay métricas para ambos períodos si se seleccionó comparación
        combined_summary_data = {}
        
        if has_comparison and comparison_start and comparison_end:
            # Si hay comparación, asegurar que hay datos para ambos períodos
            all_summary_keys = set(current_summary_data.keys()) | set(comparison_summary_data.keys())
            
            for summary_key in all_summary_keys:
                current_summary_metric = current_summary_data.get(summary_key, [])
                comparison_summary_metric = comparison_summary_data.get(summary_key, [])
                
                # Si no hay datos para el período actual, crear entrada con 0s
                if not current_summary_metric:
                    current_summary_metric = [{
                        'Period': f"{current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')} (Current)",
                        'StartDate': current_start.strftime('%Y-%m-%d'),
                        'EndDate': current_end.strftime('%Y-%m-%d'),
                        'Clicks': 0,
                        'Impressions': 0,
                        'CTR': 0.0,
                        'Position': 0.0
                    }]
                
                # Si no hay datos para el período de comparación, crear entrada con 0s
                if not comparison_summary_metric:
                    comparison_summary_metric = [{
                        'Period': f"{comparison_start.strftime('%Y-%m-%d')} to {comparison_end.strftime('%Y-%m-%d')} (Comparison)",
                        'StartDate': comparison_start.strftime('%Y-%m-%d'),
                        'EndDate': comparison_end.strftime('%Y-%m-%d'),
                        'Clicks': 0,
                        'Impressions': 0,
                        'CTR': 0.0,
                        'Position': 0.0
                    }]
                
                # Combinar ambos períodos
                combined_summary_data[summary_key] = current_summary_metric + comparison_summary_metric
        else:
            # Sin comparación, usar solo datos actuales
            combined_summary_data = current_summary_data

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
                        delta_position = current_pos - comparison_pos  # KEYWORDS: P1 - P2 (como estaba originalmente)
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
                        'delta_position_absolute': current_pos - comparison_pos if current_pos is not None and comparison_pos is not None else ('New' if current_pos is not None else 'Lost')
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

    except Exception as e:
        logger.error(f"Error general en get_data: {e}", exc_info=True)
        return jsonify({'error': f'Error procesando solicitud: {str(e)}'}), 500

@app.route('/download-excel', methods=['POST'])
@auth_required  # NUEVO: Requiere autenticación
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
    country_param = request.args.get('country', '')  # Puede estar vacío para "All countries"
    site_url_param = request.args.get('site_url', '')
    api_key_val = os.getenv('SERPAPI_KEY')
    
    if not keyword_query: 
        return jsonify({'error':'keyword es requerido'}), 400
    if not site_url_param:
        return jsonify({'error':'site_url es requerido para determinar geolocalización'}), 400
    if not api_key_val:
        return jsonify({'error':'Unexpected error, please contact support'}), 500
    
    # ✅ NUEVA LÓGICA: Si no hay país, usar None para activar detección dinámica
    country_to_use = country_param if country_param else None
    
    logger.info(f"[SERP API] Keyword: '{keyword_query}', País: {country_to_use or 'DINÁMICO'}, Site: {site_url_param}")
    
    params_serp = get_serp_params_with_location(keyword_query, api_key_val, country_to_use, site_url_param)
    
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
    country_param = request.args.get('country', '')  # Puede estar vacío para "All countries"
    api_key_serp = os.getenv('SERPAPI_KEY')
    
    if not keyword_val or not site_url_val:
        return jsonify({'error': 'keyword y site_url son requeridos'}), 400
    if not api_key_serp:
        return jsonify({'error': 'Unexpected error, please contact support'}), 500
    
    # ✅ NUEVA LÓGICA: Si no hay país, usar None para activar detección dinámica
    country_to_use = country_param if country_param else None
    
    logger.info(f"[SERP POSITION] Iniciando búsqueda para '{keyword_val}' en '{site_url_val}' (País: {country_to_use or 'DINÁMICO'})")
    
    params_serp = get_serp_params_with_location(keyword_val, api_key_serp, country_to_use, site_url_val)
    
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
    country_param = request.args.get('country', '')  # Puede estar vacío para "All countries"
    api_key_env = os.getenv('SERPAPI_KEY')

    if not keyword_param or not site_url_param:
        return jsonify({'error': 'keyword y site_url son requeridos'}), 400
    if not api_key_env:
         logger.error("API key de SerpAPI no configurada para screenshot.")
         return jsonify({'error': 'Unexpected error, please contact support'}), 500
    
    # ✅ NUEVA LÓGICA: Si no hay país, usar None para activar detección dinámica
    country_to_use = country_param if country_param else None
    
    try:
        logger.info(f"[SCREENSHOT] Keyword: '{keyword_param}', Site: '{site_url_param}', País: {country_to_use or 'DINÁMICO'}")
        return get_page_screenshot(keyword=keyword_param, site_url_to_highlight=site_url_param, api_key=api_key_env, country=country_to_use, site_url=site_url_param)
    except Exception as e:
        logger.error(f"[SCREENSHOT ROUTE] Error para keyword '{keyword_param}': {e}", exc_info=True)
        return jsonify({'error': f'Error general al generar screenshot: {e}'}), 500

def analyze_single_keyword_ai_impact(keyword_arg, site_url_arg, country_code=None):
    """
    Analiza el impacto de AI Overview para una keyword específica con sistema de caché
    """
    
    if not keyword_arg or not site_url_arg:
        raise ValueError("keyword_arg y site_url_arg son requeridos")
    
    logger.info(f"🤖 Analizando AI Overview para '{keyword_arg}' en {site_url_arg}")
    
    # ✅ NUEVO: Verificar caché primero
    cached_result = ai_cache.get_cached_analysis(keyword_arg, site_url_arg, country_code or '')
    if cached_result and cached_result.get('analysis'):
        logger.info(f"💾 Usando resultado cacheado para '{keyword_arg}'")
        return cached_result['analysis']
    
    api_key_env_val = os.getenv('SERPAPI_KEY')
    if not api_key_env_val:
        logger.error("SERPAPI_KEY no está configurada para analyze_single_keyword_ai_impact")
        error_result = {
            'keyword': keyword_arg, 
            'error': "SERPAPI_KEY no está configurada",
            'ai_analysis': {'has_ai_overview': False, 'debug_info': {'error': "API key missing"}},
            'site_position': 'Error', 
            'serp_features': [], 
            'timestamp': time.time(), 
            'country_analyzed': country_code or 'esp'
        }
        return error_result
    
    # ✅ LÓGICA: Pasar site_url para detección dinámica de país
    params_ai = get_serp_params_with_location(keyword_arg, api_key_env_val, country_code, site_url_arg)
    
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

        result_data = {
            'keyword': keyword_arg,
            'ai_analysis': ai_analysis_data,
            'site_position': site_pos_info.get('position', 'No encontrado'),
            'organic_url': site_pos_info.get('url', ''),
            'serp_features': serp_features_output_list,
            'timestamp': time.time(),
            'country_analyzed': country_code or 'esp'  # Añadir país al resultado
        }
        
        # ✅ NUEVO: Guardar en caché para futuras consultas
        ai_cache.cache_analysis(keyword_arg, site_url_arg, country_code or '', result_data)
        
        return result_data
        
    except Exception as e_single_keyword:
        logger.error(f"Error analizando keyword '{keyword_arg}': {str(e_single_keyword)}")
        
        # ✅ NUEVO: Para errores, también cachear brevemente para evitar re-intentos inmediatos
        error_result = {
            'keyword': keyword_arg,
            'ai_analysis': {'has_ai_overview': False, 'error': str(e_single_keyword)},
            'site_position': 'Error',
            'serp_features': [],
            'timestamp': time.time(),
            'country_analyzed': country_code or 'esp'
        }
        
        ai_cache.cache_analysis(keyword_arg, site_url_arg, country_code or '', error_result)
        
        raise Exception(f"Error analizando {keyword_arg}: {str(e_single_keyword)}")

def calculate_average_ai_position(results_list):
    """
    Calcula la posición promedio del dominio en AI Overview
    Solo considera keywords donde el dominio aparece como fuente (domain_is_ai_source = True)
    """
    valid_positions = []
    
    for result in results_list:
        ai_analysis = result.get('ai_analysis', {})
        domain_is_source = ai_analysis.get('domain_is_ai_source', False)
        position = ai_analysis.get('domain_ai_source_position')
        
        # Solo incluir si el dominio es fuente AI y tiene una posición válida
        if domain_is_source and position is not None and position > 0:
            valid_positions.append(position)
    
    if not valid_positions:
        return None  # No hay posiciones válidas
    
    # Calcular promedio y redondear a 1 decimal
    average = sum(valid_positions) / len(valid_positions)
    return round(average, 1)

def detect_top_competitor_domains(results_list, site_url, min_competitors=4):
    """
    Detecta automáticamente los dominios que más aparecen en AI Overview.
    Esta función se usa cuando el usuario no ha proporcionado competidores manualmente.
    
    IMPORTANTE: Esta función ya recibe results_list filtrado por exclusiones de keywords,
    por lo que automáticamente respeta las keywords excluidas por el usuario.
    
    Args:
        results_list: Lista de resultados de análisis de keywords (ya filtrada por exclusiones)
        site_url: URL del sitio principal (para excluirlo de competidores)
        min_competitors: Número mínimo de competidores a devolver
    
    Returns:
        List: Lista de dominios competidores ordenados por frecuencia de aparición
    """
    if not results_list:
        logger.info("[AUTO-COMPETITOR] No hay resultados para analizar")
        return []
    
    logger.info(f"[AUTO-COMPETITOR] 🔍 Iniciando detección automática de competidores (mínimo {min_competitors})")
    
    # Normalizar el dominio principal para excluirlo
    from services.utils import normalize_search_console_url
    main_domain = normalize_search_console_url(site_url)
    
    # Recopilar todos los dominios y sus métricas
    competitors_data = {}
    
    for result in results_list:
        keyword = result.get('keyword', '')
        ai_analysis = result.get('ai_analysis', {})
        
        if ai_analysis.get('has_ai_overview'):
            # Extraer referencias de AI Overview usando la misma lógica del Excel
            debug_info = ai_analysis.get('debug_info', {})
            references_found = debug_info.get('references_found', [])
            
            for ref in references_found:
                link = ref.get('link', '')
                if link:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(link)
                        domain = parsed.netloc.replace('www.', '').lower()
                        
                        # Excluir dominio principal y dominios vacíos
                        if domain and domain != main_domain:
                            if domain not in competitors_data:
                                competitors_data[domain] = {
                                    'total_appearances': 0,
                                    'total_position_sum': 0,
                                    'positions': [],
                                    'keywords': []
                                }
                            
                            competitors_data[domain]['total_appearances'] += 1
                            position = ref.get('index', 0) + 1  # +1 porque index empieza en 0
                            
                            if position > 0:
                                competitors_data[domain]['total_position_sum'] += position
                                competitors_data[domain]['positions'].append(position)
                            
                            competitors_data[domain]['keywords'].append(keyword)
                            
                    except Exception as e:
                        logger.warning(f"[AUTO-COMPETITOR] Error parsing URL {link}: {e}")
                        continue
    
    # Ordenar competidores por número de apariciones (más relevantes primero)
    sorted_competitors = sorted(competitors_data.items(), 
                              key=lambda x: x[1]['total_appearances'], 
                              reverse=True)
    
    # Obtener exactamente min_competitors dominios más frecuentes
    top_competitors = [domain for domain, data in sorted_competitors]
    
    # Seleccionar exactamente min_competitors (no más)
    selected_competitors = top_competitors[:min_competitors]
    
    logger.info(f"[AUTO-COMPETITOR] ✅ Detectados {len(competitors_data)} dominios únicos")
    logger.info(f"[AUTO-COMPETITOR] 🎯 Seleccionados top {len(selected_competitors)} como competidores:")
    
    for i, domain in enumerate(selected_competitors, 1):
        if domain in competitors_data:
            appearances = competitors_data[domain]['total_appearances']
            avg_pos = competitors_data[domain]['total_position_sum'] / len(competitors_data[domain]['positions']) if competitors_data[domain]['positions'] else 0
            logger.info(f"[AUTO-COMPETITOR]   {i}. {domain} - {appearances} apariciones, pos. promedio: {avg_pos:.1f}")
    
    return selected_competitors

def analyze_competitor_domains(results_list, competitor_domains):
    """
    Analiza las métricas de competidores en AI Overview
    """
    if not competitor_domains or not results_list:
        logger.info("[COMPETITOR] No hay dominios o resultados para analizar")
        return []
    
    competitor_stats = []
    
    for domain in competitor_domains:
        logger.info(f"[COMPETITOR] Analizando dominio: {domain}")
        domain_mentions = 0
        domain_positions = []
        total_keywords_with_ai = 0
        
        # Analizar cada resultado de keyword
        for result in results_list:
            keyword = result.get('keyword', 'unknown')
            ai_analysis = result.get('ai_analysis', {})
            has_ai_overview = ai_analysis.get('has_ai_overview', False)
            
            if has_ai_overview:
                total_keywords_with_ai += 1
                
                # Buscar el dominio en las fuentes AI
                if check_domain_in_ai_sources(ai_analysis, domain):
                    domain_mentions += 1
                    
                    # Obtener posición si está disponible
                    position = get_domain_position_in_ai(ai_analysis, domain)
                    if position and position > 0:
                        domain_positions.append(position)
        
        # Calcular métricas
        visibility_percentage = (domain_mentions / total_keywords_with_ai * 100) if total_keywords_with_ai > 0 else 0
        average_position = (sum(domain_positions) / len(domain_positions)) if domain_positions else None
        
        logger.info(f"[COMPETITOR] Dominio {domain}: {domain_mentions} menciones de {total_keywords_with_ai} con AI, {visibility_percentage:.1f}% visibilidad, posición media: {average_position}")
        
        # Debug: verificar que tenemos referencias para analizar
        if domain_mentions == 0 and total_keywords_with_ai > 0:
            # Revisar una keyword de ejemplo para ver qué referencias hay
            for result in results_list[:1]:  # Solo la primera
                ai_analysis = result.get('ai_analysis', {})
                if ai_analysis.get('has_ai_overview', False):
                    debug_info = ai_analysis.get('debug_info', {})
                    refs = debug_info.get('references_found', [])
                    logger.info(f"[COMPETITOR] DEBUG ejemplo: {len(refs)} referencias en primera keyword con AI")
                    if refs:
                        first_ref = refs[0]
                        logger.info(f"[COMPETITOR] DEBUG ref[0]: link={first_ref.get('link', 'None')[:100]}")
                    break
        
        competitor_stats.append({
            'domain': domain,
            'mentions': domain_mentions,
            'visibility_percentage': round(visibility_percentage, 1),
            'average_position': round(average_position, 1) if average_position else None
        })
    
    return competitor_stats

def check_domain_in_ai_sources(ai_analysis, target_domain):
    """
    Verifica si un dominio aparece en las fuentes de AI Overview
    Reutiliza exactamente la misma lógica que ya fue probada
    """
    from services.utils import urls_match, normalize_search_console_url
    
    # Normalizar el dominio objetivo
    normalized_target = normalize_search_console_url(target_domain)
    if not normalized_target:
        return False
    
    # Si es el dominio principal, usar la información ya calculada
    debug_info = ai_analysis.get('debug_info', {})
    site_url_normalized = debug_info.get('site_url_normalized', '')
    
    if site_url_normalized and site_url_normalized == normalized_target:
        # Es el dominio principal, devolver el resultado ya calculado
        return ai_analysis.get('domain_is_ai_source', False)
    
    # Para competidores, usar exactamente la misma lógica que en services/ai_analysis.py
    # pero simplificada para buscar cualquier dominio
    references = debug_info.get('references_found', [])
    
    if not references:
        return False
    
    # MÉTODO 1: Buscar en referencias oficiales (igual que en detect_ai_overview_elements)
    for ref in references:
        ref_link = ref.get('link', '')
        ref_source = ref.get('source', '')
        ref_title = ref.get('title', '')
        
        # Verificar coincidencia de dominio (igual que en la función original)
        if ref_link and urls_match(ref_link, normalized_target):
            return True
        
        # También verificar en source y title (igual que en la función original)
        if (ref_source and normalized_target.lower() in ref_source.lower()) or \
           (ref_title and normalized_target.lower() in ref_title.lower()):
            return True
    
    return False

def get_domain_position_in_ai(ai_analysis, target_domain):
    """
    Obtiene la posición de un dominio específico en AI Overview
    Reutiliza exactamente la misma lógica que ya fue probada
    """
    from services.utils import urls_match, normalize_search_console_url
    
    # Normalizar el dominio objetivo
    normalized_target = normalize_search_console_url(target_domain)
    if not normalized_target:
        return None
    
    # Si es el dominio principal, usar la posición ya calculada
    debug_info = ai_analysis.get('debug_info', {})
    site_url_normalized = debug_info.get('site_url_normalized', '')
    
    if site_url_normalized and site_url_normalized == normalized_target:
        # Es el dominio principal, devolver el resultado ya calculado
        return ai_analysis.get('domain_ai_source_position')
    
    # Para competidores, usar exactamente la misma lógica que en services/ai_analysis.py
    references = debug_info.get('references_found', [])
    
    if not references:
        return None
    
    # Buscar en referencias oficiales (igual que en detect_ai_overview_elements)
    for ref in references:
        ref_index = ref.get('index')
        ref_link = ref.get('link', '')
        ref_source = ref.get('source', '')
        ref_title = ref.get('title', '')
        
        # Verificar coincidencia de dominio
        if ref_link and urls_match(ref_link, normalized_target):
            return ref_index + 1 if ref_index is not None else None  # Posición 1-based
        
        # También verificar en source y title
        if (ref_source and normalized_target.lower() in ref_source.lower()) or \
           (ref_title and normalized_target.lower() in ref_title.lower()):
            return ref_index + 1 if ref_index is not None else None  # Posición 1-based
    
    return None


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
@auth_required  # NUEVO: Requiere autenticación
def analyze_ai_overview_route():
    try:
        request_payload = request.get_json()
        keywords_data_list = request_payload.get('keywords', [])
        site_url_req = request_payload.get('site_url', '')
        country_req = request_payload.get('country', '')
        
        # 🆕 NUEVO: Obtener dominios de competidores
        competitor_domains = request_payload.get('competitor_domains', [])
        
        # 🔍 NUEVO: Obtener configuración de exclusión de keywords
        keyword_exclusions = request_payload.get('keyword_exclusions', {})
        exclusions_enabled = keyword_exclusions.get('enabled', False)
        
        # 🆕 NUEVO: Obtener cantidad solicitada por usuario
        requested_count = request_payload.get('keyword_count', 50)  # Default 50
        
        # 🆕 NUEVO: Validar límites razonables
        if requested_count > 200:  # Límite máximo de seguridad
            logger.warning(f"Cantidad solicitada {requested_count} excede límite máximo. Usando 200.")
            requested_count = 200
        elif requested_count < 10:  # Límite mínimo
            logger.warning(f"Cantidad solicitada {requested_count} es muy baja. Usando 10.")
            requested_count = 10
        
        logger.info(f"=== INICIANDO ANÁLISIS AI OVERVIEW - {requested_count} KEYWORDS ===")
        
        # 🔍 NUEVO: Logging de exclusiones
        if exclusions_enabled:
            exclusion_terms = keyword_exclusions.get('terms', [])
            exclusion_method = keyword_exclusions.get('method', 'contains')
            logger.info(f"[AI ANALYSIS] 🔍 Exclusiones habilitadas: {len(exclusion_terms)} términos con método '{exclusion_method}'")
            logger.info(f"[AI ANALYSIS] 🔍 Términos a excluir: {exclusion_terms[:5]}{'...' if len(exclusion_terms) > 5 else ''}")
        else:
            logger.info(f"[AI ANALYSIS] ⚪ Sin exclusiones de keywords")

        # 🔍 DEBUGGING: ¿Qué país se está usando?
        logger.info(f"=== AI OVERVIEW COUNTRY DEBUG ===")
        logger.info(f"Country from payload: '{country_req}'")
        logger.info(f"Country is empty: {not country_req}")
        logger.info(f"Country fallback logic needed: {not country_req}")
        logger.info("==================================")
        
        # ✅ NUEVO: Logging mejorado sobre la lógica de país
        if country_req:
            country_config = get_country_config(country_req)
            if country_config:
                logger.info(f"[AI ANALYSIS] 🎯 Usando país específico: {country_config['name']} ({country_req})")
                logger.info(f"[AI ANALYSIS] 📍 Simulando búsquedas desde: {country_config['serp_location']}")
            else:
                logger.warning(f"[AI ANALYSIS] ⚠️ País no reconocido: {country_req}")
        else:
            logger.info("[AI ANALYSIS] 🌍 Sin país especificado - usando detección dinámica del país con más clics")
        
        if not keywords_data_list:
            return jsonify({'error': 'No se proporcionaron keywords para analizar'}), 400
        if not site_url_req:
            return jsonify({'error': 'site_url es requerido'}), 400
        
        serpapi_key = os.getenv('SERPAPI_KEY')
        if not serpapi_key:
            logger.error("SERPAPI_KEY no configurada para ruta analyze-ai-overview")
            return jsonify({'error': 'Unexpected error, please contact support'}), 500
        
        original_count = len(keywords_data_list)
        
        # 🔍 NUEVO: Aplicar exclusiones de keywords si están habilitadas
        if exclusions_enabled:
            exclusion_terms = keyword_exclusions.get('terms', [])
            exclusion_method = keyword_exclusions.get('method', 'contains')
            
            keywords_before_exclusion = len(keywords_data_list)
            keywords_data_list = apply_keyword_exclusions(keywords_data_list, exclusion_terms, exclusion_method)
            keywords_after_exclusion = len(keywords_data_list)
            excluded_count = keywords_before_exclusion - keywords_after_exclusion
            
            logger.info(f"[AI ANALYSIS] 🔍 Exclusiones aplicadas: {keywords_before_exclusion} → {keywords_after_exclusion} (excluidas: {excluded_count})")
            
            # Actualizar el recuento original después de las exclusiones
            original_count = len(keywords_data_list)
        
        # 🔄 MODIFICADO: Usar cantidad solicitada
        keywords_to_process_list = keywords_data_list[:requested_count]
        if original_count > requested_count:
            logger.warning(f"Se truncaron {original_count - requested_count} keywords. Analizando solo las primeras {requested_count}.")
        
        # 🆕 MODIFICADO: Optimizar workers basado en cantidad solicitada
        num_keywords = len(keywords_to_process_list)
        if num_keywords <= 25:
            max_workers = 2  # Análisis pequeño
        elif num_keywords <= 75:
            max_workers = 3  # Análisis medio
        elif num_keywords <= 125:
            max_workers = 4  # Análisis grande
        else:
            max_workers = 5  # Análisis muy grande (máximo para evitar rate limiting)
            
        logger.info(f"🚀 Iniciando análisis paralelo de {num_keywords} keywords con {max_workers} workers")
        
        results_list_overview, errors_list_overview, successful_analyses_overview = analyze_keywords_parallel(
            keywords_to_process_list, 
            site_url_req, 
            country_req, 
            max_workers
        )
        
        results_list_overview.sort(key=lambda x_item_sort: x_item_sort.get('delta_clicks_absolute', 0))

        total_analyzed_overview = len(results_list_overview)
        # 🆕 NUEVO: Analizar competidores incluyendo el dominio principal
        competitor_analysis = []
        domains_to_analyze = []
        
        # Añadir dominio principal normalizado
        from services.utils import normalize_search_console_url
        main_domain = normalize_search_console_url(site_url_req)
        if main_domain:
            domains_to_analyze.append(main_domain)
        
        # 🚀 NUEVA FUNCIONALIDAD: Detección automática de competidores
        if competitor_domains:
            # Caso 1: Competidores proporcionados manualmente
            domains_to_analyze.extend(competitor_domains)
            logger.info(f"[COMPETITOR] 👤 Usando competidores manuales: {competitor_domains}")
        else:
            # Caso 2: Detección automática de competidores
            logger.info("[AUTO-COMPETITOR] 🤖 No se proporcionaron competidores manuales. Iniciando detección automática...")
            auto_competitors = detect_top_competitor_domains(results_list_overview, site_url_req, min_competitors=4)
            
            if auto_competitors:
                domains_to_analyze.extend(auto_competitors)
                logger.info(f"[AUTO-COMPETITOR] ✅ Detectados automáticamente {len(auto_competitors)} competidores: {auto_competitors}")
                
                # Actualizar competitor_domains para el resumen final
                competitor_domains = auto_competitors
            else:
                logger.warning("[AUTO-COMPETITOR] ⚠️ No se pudieron detectar competidores automáticamente")
        
        if domains_to_analyze:
            total_domains = len(domains_to_analyze)
            manual_count = len(competitor_domains) if competitor_domains else 0
            logger.info(f"[COMPETITOR] 📊 Analizando {total_domains} dominios total (1 principal + {manual_count} competidores)")
            logger.info(f"[COMPETITOR] 🔍 Dominios a analizar: {domains_to_analyze}")
            
            competitor_analysis = analyze_competitor_domains(results_list_overview, domains_to_analyze)
            logger.info(f"[COMPETITOR] ✅ Análisis completado para {len(competitor_analysis)} dominios")

        # 🚀 NUEVA INFO: Determinar si los competidores fueron detectados automáticamente
        original_competitor_domains = request_payload.get('competitor_domains', [])
        competitors_auto_detected = len(original_competitor_domains) == 0 and len(competitor_domains) > 0
        
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
            'country_analyzed': country_req, # NUEVO: País analizado
            'requested_keyword_count': requested_count,  # 🆕 NUEVO: registrar cantidad solicitada
            'average_ai_position': calculate_average_ai_position(results_list_overview),  # 🆕 NUEVO: Posición promedio en AIO
            'competitor_analysis': competitor_analysis,  # 🆕 NUEVO: Análisis de competidores
            'competitors_auto_detected': competitors_auto_detected,  # 🚀 NUEVA FUNCIONALIDAD: Indica si fueron auto-detectados
            'competitor_domains_analyzed': competitor_domains if competitor_domains else []  # 🚀 NUEVA FUNCIONALIDAD: Lista de dominios competidores
        }

        # ✅ NUEVO: Guardar análisis en la base de datos
        current_user = get_current_user()
        user_id = current_user.get('id') if current_user else None
        
        analysis_data = {
            'results': results_list_overview,
            'summary': summary_overview_stats,
            'site_url': site_url_req
        }
        
        # Intentar guardar en base de datos (no crítico si falla)
        try:
            if save_ai_overview_analysis(analysis_data, user_id):
                logger.info("✅ Análisis guardado en base de datos correctamente")
            else:
                logger.warning("⚠️ No se pudo guardar el análisis en base de datos")
        except Exception as e:
            logger.error(f"❌ Error guardando análisis en BD: {e}")

        # ✅ NUEVO: Guardar múltiples análisis en caché por lotes
        try:
            cached_count = ai_cache.cache_analysis_batch(results_list_overview)
            logger.info(f"💾 {cached_count} análisis guardados en caché por lotes")
        except Exception as e:
            logger.warning(f"⚠️ Error guardando lote en caché: {e}")

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
@auth_required  # NUEVO: Requiere autenticación
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
    country = request.args.get('country', '')  # Puede estar vacío
    site_url = request.args.get('site_url', '')
    
    serpapi_key = os.getenv('SERPAPI_KEY')
    
    if not site_url:
        return jsonify({'error': 'site_url es requerido para test dinámico'}), 400
    
    # ✅ NUEVA LÓGICA: Probar detección dinámica
    country_to_use = country if country else None
    
    # Parámetros para AI Analysis (con nueva lógica)
    ai_params = get_serp_params_with_location(keyword, serpapi_key, country_to_use, site_url)
    
    # Información adicional para debug
    debug_info = {
        'inputs': {
            'keyword': keyword,
            'country_param': country,
            'site_url': site_url,
            'country_to_use': country_to_use
        },
        'serp_params': ai_params,
        'logic_applied': {
            'has_specific_country': bool(country),
            'will_use_dynamic_detection': not bool(country),
            'detected_country': None
        }
    }
    
    # Si no hay país específico, mostrar qué país se detectaría
    if not country:
        try:
            detected_country = get_top_country_for_site(site_url)
            debug_info['logic_applied']['detected_country'] = detected_country
            debug_info['logic_applied']['detection_successful'] = True
            
            # Obtener información del país detectado
            country_config = get_country_config(detected_country)
            if country_config:
                debug_info['detected_country_info'] = {
                    'code': detected_country,
                    'name': country_config['name'],
                    'serp_location': country_config['serp_location'],
                    'google_domain': country_config['google_domain']
                }
        except Exception as e:
            debug_info['logic_applied']['detection_error'] = str(e)
            debug_info['logic_applied']['detection_successful'] = False
    
    return jsonify(debug_info)

# ✅ NUEVO ENDPOINT: Obtener keywords de una URL específica
@app.route('/api/url-keywords', methods=['POST'])
@auth_required
def get_url_keywords():
    """Obtiene las keywords de una URL específica con las mismas fechas del último análisis"""
    try:
        data = request.get_json()
        target_url = data.get('url', '').strip()
        site_url_sc = data.get('site_url', '').strip()
        selected_country = data.get('country', '')
        
        # Fechas del análisis (usando las mismas que el frontend)
        current_start_date = data.get('current_start_date')
        current_end_date = data.get('current_end_date')
        comparison_start_date = data.get('comparison_start_date')
        comparison_end_date = data.get('comparison_end_date')
        has_comparison = data.get('has_comparison', False)
        
        if not target_url:
            return jsonify({'error': 'URL es requerida'}), 400
        if not site_url_sc:
            return jsonify({'error': 'site_url es requerido'}), 400
        if not current_start_date or not current_end_date:
            return jsonify({'error': 'Fechas son requeridas'}), 400
        
        logger.info(f"[URL KEYWORDS] Buscando keywords para URL: {target_url}")
        
        # Obtener servicio autenticado
        gsc_service = get_authenticated_service('searchconsole', 'v1')
        if not gsc_service:
            return jsonify({'error': 'Error de autenticación con Search Console'}), 401
        
        # Configurar filtros base (país)
        def get_base_filters_url_keywords(additional_filters=None):
            filter_groups = []
            
            # Filtro de país si está seleccionado
            if selected_country:
                filter_groups.append({
                    'filters': [{'dimension': 'country', 'operator': 'equals', 'expression': selected_country}]
                })
            
            # Filtros adicionales (URL específica)
            if additional_filters:
                filter_groups.extend(additional_filters)
            
            return filter_groups
        
        # Función para procesar keywords de una URL específica
        def get_keywords_for_url(start_date, end_date, url):
            keyword_data = {}
            
            # Filtro para la URL específica (usar 'equals' para exactitud)
            url_filter = [{'filters': [{'dimension': 'page', 'operator': 'equals', 'expression': url}]}]
            combined_filters = get_base_filters_url_keywords(url_filter)
            
            # Obtener datos de Search Console
            rows_data = fetch_searchconsole_data_single_call(
                gsc_service, site_url_sc,
                start_date, end_date,
                ['page', 'query'],  # Dimensiones: página y keyword
                combined_filters
            )
            
            logger.info(f"[URL KEYWORDS] Obtenidas {len(rows_data)} filas para URL: {url}")
            
            for r_item in rows_data:
                if len(r_item.get('keys', [])) >= 2:
                    page_url = r_item['keys'][0]
                    query = r_item['keys'][1]
                    
                    # Solo incluir si la página coincide exactamente con nuestra URL objetivo
                    if page_url.lower() == url.lower():
                        if query not in keyword_data:
                            keyword_data[query] = {
                                'clicks': 0, 'impressions': 0, 'ctr_sum': 0.0,
                                'pos_sum': 0.0, 'count': 0, 'url': page_url
                            }
                        
                        kw_entry = keyword_data[query]
                        kw_entry['clicks'] += r_item['clicks']
                        kw_entry['impressions'] += r_item['impressions']
                        kw_entry['ctr_sum'] += r_item['ctr'] * r_item['impressions']
                        kw_entry['pos_sum'] += r_item['position'] * r_item['impressions']
                        kw_entry['count'] += r_item['impressions']
            
            return keyword_data
        
        # Función para calcular cambio porcentual
        def calculate_percentage_change_url_keywords(current, comparison):
            if comparison == 0:
                return "Infinity" if current > 0 else 0
            return ((current - comparison) / comparison) * 100
        
        # Convertir fechas
        from datetime import datetime
        current_start = datetime.strptime(current_start_date, '%Y-%m-%d')
        current_end = datetime.strptime(current_end_date, '%Y-%m-%d')
        
        # Obtener keywords del período actual
        current_keywords = get_keywords_for_url(
            current_start.strftime('%Y-%m-%d'),
            current_end.strftime('%Y-%m-%d'),
            target_url
        )
        
        comparison_keywords = {}
        if has_comparison and comparison_start_date and comparison_end_date:
            comparison_start = datetime.strptime(comparison_start_date, '%Y-%m-%d')
            comparison_end = datetime.strptime(comparison_end_date, '%Y-%m-%d')
            
            comparison_keywords = get_keywords_for_url(
                comparison_start.strftime('%Y-%m-%d'),
                comparison_end.strftime('%Y-%m-%d'),
                target_url
            )
        
        # Generar datos de comparación
        comparison_data = []
        
        if not comparison_keywords:
            # Solo período actual
            for query, current_data in current_keywords.items():
                current_clicks = current_data['clicks']
                current_impressions = current_data['impressions']
                current_ctr = (current_data['ctr_sum'] / current_data['count'] * 100) if current_data['count'] > 0 else 0
                current_pos = (current_data['pos_sum'] / current_data['count']) if current_data['count'] > 0 else None
                
                comparison_data.append({
                    'keyword': query,
                    'url': current_data.get('url', target_url),
                    'clicks_m1': current_clicks,
                    'clicks_m2': 0,
                    'delta_clicks_percent': 'New',
                    'impressions_m1': current_impressions,
                    'impressions_m2': 0,
                    'delta_impressions_percent': 'New',
                    'ctr_m1': current_ctr,
                    'ctr_m2': 0,
                    'delta_ctr_percent': 'New',
                    'position_m1': current_pos,
                    'position_m2': None,
                    'delta_position_absolute': 'New'
                })
        else:
            # Con comparación
            all_queries = set(current_keywords.keys()) | set(comparison_keywords.keys())
            
            for query in all_queries:
                current_data = current_keywords.get(query, {})
                comparison_data_kw = comparison_keywords.get(query, {})
                
                # Métricas del período actual
                current_clicks = current_data.get('clicks', 0)
                current_impressions = current_data.get('impressions', 0)
                current_ctr = (current_data.get('ctr_sum', 0) / current_data.get('count', 1) * 100) if current_data.get('count', 0) > 0 else 0
                current_pos = (current_data.get('pos_sum', 0) / current_data.get('count', 1)) if current_data.get('count', 0) > 0 else None
                
                # Métricas del período de comparación
                comparison_clicks = comparison_data_kw.get('clicks', 0)
                comparison_impressions = comparison_data_kw.get('impressions', 0)
                comparison_ctr = (comparison_data_kw.get('ctr_sum', 0) / comparison_data_kw.get('count', 1) * 100) if comparison_data_kw.get('count', 0) > 0 else 0
                comparison_pos = (comparison_data_kw.get('pos_sum', 0) / comparison_data_kw.get('count', 1)) if comparison_data_kw.get('count', 0) > 0 else None
                
                # Calcular deltas
                if query in comparison_keywords and query in current_keywords:
                    delta_clicks = calculate_percentage_change_url_keywords(current_clicks, comparison_clicks)
                    delta_impressions = calculate_percentage_change_url_keywords(current_impressions, comparison_impressions)
                    delta_ctr = current_ctr - comparison_ctr
                    
                    if current_pos is not None and comparison_pos is not None:
                        delta_position = current_pos - comparison_pos  # URL KEYWORDS: P1 - P2 (igual que keywords principales)
                    elif current_pos is not None:
                        delta_position = 'New'
                    else:
                        delta_position = 'Lost'
                elif query in current_keywords:
                    delta_clicks = 'New'
                    delta_impressions = 'New'
                    delta_ctr = 'New'
                    delta_position = 'New'
                else:
                    delta_clicks = 'Lost'
                    delta_impressions = 'Lost'
                    delta_ctr = 'Lost'
                    delta_position = 'Lost'
                
                comparison_data.append({
                    'keyword': query,
                    'url': current_data.get('url') or comparison_data_kw.get('url') or target_url,
                    'clicks_m1': current_clicks,
                    'clicks_m2': comparison_clicks,
                    'delta_clicks_percent': delta_clicks,
                    'impressions_m1': current_impressions,
                    'impressions_m2': comparison_impressions,
                    'delta_impressions_percent': delta_impressions,
                    'ctr_m1': current_ctr,
                    'ctr_m2': comparison_ctr,
                    'delta_ctr_percent': delta_ctr,
                    'position_m1': current_pos,
                    'position_m2': comparison_pos,
                    'delta_position_absolute': delta_position
                })
        
        # Ordenar por clicks descendente
        comparison_data.sort(key=lambda x: x.get('clicks_m1', 0), reverse=True)
        
        logger.info(f"[URL KEYWORDS] Devolviendo {len(comparison_data)} keywords para URL: {target_url}")
        
        return jsonify({
            'keywords': comparison_data,
            'url': target_url,
            'total_keywords': len(comparison_data),
            'has_comparison': has_comparison,
            'periods': {
                'current': {
                    'start_date': current_start_date,
                    'end_date': current_end_date,
                    'label': f"{current_start_date} to {current_end_date}"
                },
                'comparison': {
                    'start_date': comparison_start_date,
                    'end_date': comparison_end_date,
                    'label': f"{comparison_start_date} to {comparison_end_date}"
                } if has_comparison else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error en get_url_keywords: {e}", exc_info=True)
        return jsonify({'error': f'Error obteniendo keywords de URL: {str(e)}'}), 500

# ====================================
# 📊 NUEVAS RUTAS AI OVERVIEW ANALYTICS
# ====================================

@app.route('/api/ai-overview-stats', methods=['GET'])
@auth_required
def get_ai_overview_stats_route():
    """Obtiene estadísticas generales de AI Overview"""
    try:
        stats = get_ai_overview_stats()
        
        # Añadir estadísticas del caché
        try:
            cache_stats = ai_cache.get_cache_stats()
            stats['cache_stats'] = cache_stats
        except Exception as e:
            logger.warning(f"Error obteniendo stats de caché: {e}")
            stats['cache_stats'] = {'cache_available': False}
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas AI Overview: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-overview-typology', methods=['GET'])
@auth_required  
def get_ai_overview_typology_route():
    """Obtiene datos de tipología de consultas para el gráfico de barras"""
    try:
        stats = get_ai_overview_stats()
        word_count_stats = stats.get('word_count_stats', [])
        
        # Transformar datos para el gráfico
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
        
        return jsonify({
            'success': True,
            'typology_data': typology_data,
            'summary': {
                'total_categories': len(word_count_stats),
                'total_queries_analyzed': sum(item['total'] for item in word_count_stats),
                'total_with_ai_overview': sum(item['con_ai_overview'] for item in word_count_stats)
            },
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de tipología: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai-overview-history', methods=['GET'])
@auth_required
def get_ai_overview_history_route():
    """Obtiene historial de análisis de AI Overview"""
    try:
        # Parámetros opcionales
        site_url = request.args.get('site_url')
        keyword = request.args.get('keyword')
        days = int(request.args.get('days', 30))
        limit = int(request.args.get('limit', 100))
        
        history = get_ai_overview_history(site_url, keyword, days, limit)
        
        return jsonify({
            'success': True,
            'history': history,
            'filters': {
                'site_url': site_url,
                'keyword': keyword,
                'days': days,
                'limit': limit
            },
            'count': len(history),
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo historial AI Overview: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cache-management', methods=['POST'])
@admin_required  # Solo administradores pueden gestionar caché
def cache_management_route():
    """Gestiona operaciones de caché (limpiar, invalidar, estadísticas)"""
    try:
        action = request.get_json().get('action')
        
        if action == 'clear':
            # Limpiar caché de AI Overview (Redis)
            deleted = ai_cache.clear_cache()
            # Limpiar caché de screenshots in-memory
            screenshot_deleted = len(SCREENSHOT_CACHE)
            SCREENSHOT_CACHE.clear()
            return jsonify({
                'success': True,
                'message': f'Caché limpiado: {deleted} entradas de AI + {screenshot_deleted} screenshots eliminados',
                'deleted_count': deleted + screenshot_deleted
            })
            
        elif action == 'stats':
            stats = ai_cache.get_cache_stats()
            return jsonify({
                'success': True,
                'cache_stats': stats
            })
            
        elif action == 'invalidate_site':
            site_url = request.get_json().get('site_url')
            if not site_url:
                return jsonify({'success': False, 'error': 'site_url requerido'}), 400
                
            deleted = ai_cache.invalidate_site_cache(site_url)
            return jsonify({
                'success': True,
                'message': f'Caché invalidado para {site_url}: {deleted} entradas eliminadas',
                'deleted_count': deleted
            })
            
        else:
            return jsonify({
                'success': False,
                'error': 'Acción no reconocida. Acciones válidas: clear, stats, invalidate_site'
            }), 400
            
    except Exception as e:
        logger.error(f"Error en gestión de caché: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug-ai-detection', methods=['POST'])
@auth_required
def debug_ai_detection():
    """
    Ruta de debugging para probar el sistema de detección de AI Overview mejorado.
    Permite testear keywords específicas y ver el proceso detallado.
    """
    try:
        data = request.get_json()
        keyword = data.get('keyword', '')
        site_url = data.get('site_url', '')
        country = data.get('country', '')
        
        if not keyword:
            return jsonify({'error': 'keyword es requerido'}), 400
        if not site_url:
            return jsonify({'error': 'site_url es requerido'}), 400
            
        logger.info(f"=== DEBUG AI DETECTION ===")
        logger.info(f"Keyword: {keyword}")
        logger.info(f"Site URL: {site_url}")
        logger.info(f"Country: {country or 'AUTO-DETECT'}")
        logger.info("==========================")
        
        # Configurar parámetros SERP
        api_key = os.getenv('SERPAPI_KEY')
        if not api_key:
            return jsonify({'error': 'SERPAPI_KEY no configurada'}), 500
            
        params = get_serp_params_with_location(keyword, api_key, country, site_url)
        
        # Obtener datos SERP
        logger.info(f"[DEBUG] Obteniendo datos SERP con parámetros: {params}")
        serp_data = get_serp_json(params)
        
        if not serp_data or "error" in serp_data:
            error_msg = serp_data.get("error", "Error obteniendo datos SERP") if serp_data else "Sin datos SERP"
            logger.error(f"[DEBUG] Error SERP: {error_msg}")
            return jsonify({'error': f'Error SERP: {error_msg}'}), 500
        
        # Analizar AI Overview con el sistema mejorado
        logger.info(f"[DEBUG] Analizando AI Overview para dominio: {site_url}")
        ai_analysis = detect_ai_overview_elements(serp_data, site_url)
        
        # Información adicional para debugging
        debug_info = {
            'serp_keys_available': list(serp_data.keys()),
            'ai_overview_keys_checked': [
                'ai_overview', 'ai_overview_first_person_singular', 'ai_overview_complete', 
                'ai_overview_inline', 'ai_overview_sticky', 'generative_ai', 
                'generative_ai_overview', 'google_ai_overview', 'answer_box', 
                'bard_answer', 'chatgpt_answer', 'ai_powered_overview', 
                'search_generative_experience', 'sge_content', 'ai_enhanced_snippet', 
                'generative_snippet'
            ],
            'ai_overview_keys_found': [],
            'serp_params_used': params,
            'domain_normalized': normalize_search_console_url(site_url),
            'domain_extracted': extract_domain(site_url)
        }
        
        # Verificar qué claves de AI Overview están presentes
        for key in debug_info['ai_overview_keys_checked']:
            if key in serp_data and serp_data[key]:
                debug_info['ai_overview_keys_found'].append({
                    'key': key,
                    'type': type(serp_data[key]).__name__,
                    'has_content': bool(serp_data[key])
                })
        
        # Respuesta de debugging
        response = {
            'success': True,
            'keyword': keyword,
            'site_url': site_url,
            'country_used': country or 'auto-detected',
            'ai_analysis': ai_analysis,
            'debug_info': debug_info,
            'raw_serp_keys': list(serp_data.keys()),
            'interpretation': {
                'has_ai_overview': ai_analysis['has_ai_overview'],
                'domain_found_as_source': ai_analysis['domain_is_ai_source'],
                'total_ai_elements': ai_analysis['total_elements'],
                'ai_overview_position': ai_analysis['domain_ai_source_position'] if ai_analysis['domain_is_ai_source'] else None
            }
        }
        
        # Si se encontró AI Overview, incluir información detallada
        if ai_analysis['has_ai_overview']:
            response['ai_details'] = {
                'elements_detected': ai_analysis['ai_overview_detected'],
                'impact_score': ai_analysis['impact_score'],
                'elements_before_organic': ai_analysis['elements_before_organic']
            }
            
            # Si el dominio fue encontrado como fuente
            if ai_analysis['domain_is_ai_source']:
                response['domain_analysis'] = {
                    'found_as_source': True,
                    'position_in_sources': ai_analysis['domain_ai_source_position'],
                    'source_link': ai_analysis['domain_ai_source_link'],
                    'message': f"¡Éxito! Tu dominio fue encontrado como fuente #{ai_analysis['domain_ai_source_position']} en AI Overview"
                }
            else:
                response['domain_analysis'] = {
                    'found_as_source': False,
                    'message': "Tu dominio NO fue encontrado como fuente en AI Overview",
                    'suggestion': "Verifica que la URL del dominio sea correcta y que realmente aparezca en las fuentes de AI Overview"
                }
        else:
            response['ai_details'] = {
                'message': "No se detectó AI Overview en esta búsqueda",
                'possible_reasons': [
                    "La keyword no genera AI Overview",
                    "El país/ubicación no muestra AI Overview para esta query",
                    "AI Overview no está disponible para este tipo de consulta",
                    "Configuración de parámetros SERP incorrecta"
                ]
            }
        
        logger.info(f"[DEBUG] Análisis completado: AI Overview = {ai_analysis['has_ai_overview']}, Dominio como fuente = {ai_analysis['domain_is_ai_source']}")
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"[DEBUG] Error en debug_ai_detection: {e}", exc_info=True)
        return jsonify({
            'error': f'Error interno: {str(e)}',
            'success': False
        }), 500

# ====================================
# FUNCIONES DE UTILIDAD PARA EXCLUSIONES
# ====================================

def apply_keyword_exclusions(keywords_list, exclusion_terms, exclusion_method='contains'):
    """
    Aplica exclusiones a una lista de keywords basado en términos y método especificados.
    
    Args:
        keywords_list (list): Lista de keywords (objetos con atributo 'keyword')
        exclusion_terms (list): Lista de términos a excluir (case insensitive)
        exclusion_method (str): Método de exclusión ('contains', 'equals', 'startsWith', 'endsWith')
    
    Returns:
        list: Lista filtrada de keywords
    """
    if not keywords_list or not exclusion_terms:
        return keywords_list
    
    # Normalizar términos de exclusión (case insensitive)
    exclusion_terms_lower = [term.lower() for term in exclusion_terms]
    
    filtered_keywords = []
    excluded_count = 0
    
    for keyword_obj in keywords_list:
        # Obtener el texto de la keyword
        keyword_text = keyword_obj.get('keyword', '') if isinstance(keyword_obj, dict) else str(keyword_obj)
        keyword_text_lower = keyword_text.lower()
        
        # Verificar si debe ser excluida
        should_exclude = False
        
        for exclusion_term in exclusion_terms_lower:
            if exclusion_method == 'contains':
                if exclusion_term in keyword_text_lower:
                    should_exclude = True
                    break
            elif exclusion_method == 'equals':
                if keyword_text_lower == exclusion_term:
                    should_exclude = True
                    break
            elif exclusion_method == 'startsWith':
                if keyword_text_lower.startswith(exclusion_term):
                    should_exclude = True
                    break
            elif exclusion_method == 'endsWith':
                if keyword_text_lower.endswith(exclusion_term):
                    should_exclude = True
                    break
        
        if should_exclude:
            excluded_count += 1
            logger.debug(f"[EXCLUSION] Excluyendo keyword: '{keyword_text}' (método: {exclusion_method})")
        else:
            filtered_keywords.append(keyword_obj)
    
    logger.info(f"[EXCLUSION] Filtrado completado: {len(keywords_list)} → {len(filtered_keywords)} (excluidas: {excluded_count})")
    
    return filtered_keywords

# ================================
# MANUAL AI ANALYSIS SYSTEM - INDEPENDENT REGISTRATION
# ================================

# Register Manual AI Analysis Blueprint (completely independent)
try:
    from manual_ai_system import manual_ai_bp
    app.register_blueprint(manual_ai_bp)
    logger.info("✅ Manual AI Analysis system registered successfully")
except ImportError as e:
    logger.warning(f"⚠️ Manual AI Analysis system not available: {e}")
except Exception as e:
    logger.error(f"❌ Error registering Manual AI Analysis system: {e}")

if __name__ == '__main__':
    # Railway proporciona el puerto automáticamente
    port = int(os.environ.get('PORT', 5001))
    
    # Configurar debug según entorno
    debug_mode = not is_production
    
    logger.info(f"🚀 Iniciando aplicación en puerto {port}")
    logger.info(f"📊 Entorno: {'PRODUCCIÓN' if is_production else 'DESARROLLO'}")
    logger.info(f"🐛 Debug mode: {debug_mode}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
