# services/serp_service.py
import time
import hashlib
import logging
import os
from serpapi import GoogleSearch
from playwright.sync_api import sync_playwright
from flask import Response
from .utils import normalize_search_console_url
from .country_config import get_country_config # Importar get_country_config
import json # Importar json para los logs de depuración

logger = logging.getLogger(__name__)

# Caché en memoria para capturas de pantalla
SCREENSHOT_CACHE = {}
CACHE_DURATION = 3600  # segundos

def get_serp_json(params: dict) -> dict:
    """Devuelve el JSON crudo de la búsqueda SERP."""
    try:
        data = GoogleSearch(params).get_dict()
        if "error" in data:
            logger.warning(f"Error de SerpAPI para keyword: {params.get('q')} - {data['error']}")
        return data
    except Exception as e:
        logger.error(f"Excepción en get_serp_json para keyword {params.get('q')}: {e}")
        return {"error": str(e), "organic_results": [], "ads": []}


def get_serp_html(params: dict) -> str:
    """Devuelve el HTML crudo de la búsqueda SERP."""
    logger.info(f"Obteniendo SERP HTML para keyword: {params.get('q')}")
    try:
        html_content = GoogleSearch({**params, 'output': 'html'}).get_html()
        if not html_content:
             logger.warning(f"SerpAPI devolvió HTML vacío para keyword: {params.get('q')}")
        if isinstance(html_content, dict) and "error" in html_content:
            logger.error(f"Error de SerpAPI (HTML): {html_content['error']} para params: {params}")
            return f"<html><body>Error de SerpAPI: {html_content['error']}</body></html>"
        return html_content
    except Exception as e:
        logger.error(f"Excepción en get_serp_html para params {params}: {e}", exc_info=True)
        return f"<html><body>Excepción al obtener HTML: {e}</body></html>"

def get_page_screenshot(keyword: str, site_url_to_highlight: str, api_key: str, country: str = None) -> Response:
    """
    Obtiene el HTML de SERP, lo mejora para resaltar el dominio,
    captura la pantalla con Playwright, cachea el PNG y devuelve un Response de Flask.
    Genera screenshot de SERP con geolocalización opcional.
    """
    if not api_key:
        logger.error("API Key de SerpAPI no proporcionada para get_page_screenshot.")
        return Response("API Key de SerpAPI no configurada", status=500, mimetype='text/plain')

    # Parámetros base
    params = {
        'engine': 'google',
        'q': keyword,
        'api_key': api_key,
        'gl': 'es',
        'hl': 'es',
        'num': 20
    }
    
    # Aplicar configuración de país si se especifica
    if country:
        country_config = get_country_config(country) # type: ignore
        if country_config:
            params.update({
                'location': country_config['serp_location'], # type: ignore
                'gl': country_config['serp_gl'], # type: ignore
                'hl': country_config['serp_hl'], # type: ignore
                'google_domain': country_config['google_domain'] # type: ignore
            })
            logger.info(f"[SCREENSHOT] Usando configuración para {country_config['name']}") # type: ignore
    
    # 🔍 DEBUGGING: Log parámetros exactos
    logger.info(f"=== SCREENSHOT PARAMS ===")
    logger.info(f"Keyword: {keyword}")
    logger.info(f"Country: {country}")
    logger.info(f"Params: {json.dumps(params, indent=2)}")
    logger.info(f"========================")

    # Crear cache key que incluya el país
    domain_norm = normalize_search_console_url(site_url_to_highlight)
    cache_key_hash = hashlib.md5(f"screenshot:{keyword}:{domain_norm}:{country or 'default'}".encode()).hexdigest()
    now = time.time()

    if cache_key_hash in SCREENSHOT_CACHE and now - SCREENSHOT_CACHE[cache_key_hash][1] < CACHE_DURATION:
        logger.info(f"📥 Screenshot desde caché para keyword '{keyword}', domain '{domain_norm}' (país: {country or 'España'})")
        # La lógica original de cacheo ya devuelve un Response de Flask
        return SCREENSHOT_CACHE[cache_key_hash][0]


    logger.info(f"🛠️  Generando nuevo screenshot para keyword '{keyword}', domain '{domain_norm}' (país: {country or 'España'})")
    
    # 1. Obtener HTML de SerpAPI usando el servicio local get_serp_html y los params actualizados
    html_content = get_serp_html(params)

    if not html_content or "Error de SerpAPI" in html_content or "Excepción al obtener HTML" in html_content :
        logger.error(f"No se pudo obtener HTML válido para screenshot de keyword: {keyword}")
        return Response(f"Error al obtener HTML de SerpAPI para la keyword: {keyword}", status=500, mimetype='text/plain')

    # 2. JavaScript para inyectar el highlight
    js_script_content = f"""
    document.addEventListener('DOMContentLoaded', () => {{
        const targetDomain = '{domain_norm}';
        let matchesFound = 0;
        const results = document.querySelectorAll('div.yuRUbf');
        results.forEach(res => {{
            const link = res.querySelector('a');
            if (link) {{
                try {{
                    const hostname = new URL(link.href).hostname.replace(/^www\\./, '');
                    if (hostname === targetDomain && matchesFound === 0) {{
                        matchesFound++;
                        res.style.position = 'relative';
                        res.style.outline = '3px solid orange';
                        res.style.borderRadius = '5px';
                        res.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        
                        const badge = document.createElement('div');
                        badge.style.cssText = `
                            position: absolute; 
                            top: -10px; 
                            left: -10px; 
                            background: orange; 
                            color: white; 
                            padding: 3px 6px; 
                            font-size: 10px; 
                            font-weight: bold; 
                            border-radius: 3px;
                            z-index: 1000;`;
                        badge.textContent = 'AQUÍ';
                        res.insertBefore(badge, res.firstChild);
                    }}
                }} catch (e) {{
                    console.error('Error procesando URL en script de resaltado:', link.href, e);
                }}
            }}
        }});
        if (matchesFound === 0) {{
            console.warn('No se encontró el dominio para resaltar:', targetDomain);
        }}
    }});
    """

    # 3. Construir HTML "mejorado"
    enhanced_html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>SERP para {keyword}</title>
        <style>
            body {{ margin:0; padding:0; font-family: Arial, sans-serif; }}
        </style>
    </head>
    <body>
    {html_content}
    <script>
    {js_script_content}
    </script>
    </body>
    </html>"""

    # 4. Capturar screenshot con Playwright
    img_bytes = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 1200, 'height': 800})
            page.set_content(enhanced_html, wait_until='networkidle', timeout=60000)
            
            # ✅ NUEVO: Scroll a la parte superior de la página
            page.evaluate("window.scrollTo(0, 0)")
            
            # ✅ NUEVO: Esperar un breve momento para que el scroll se complete y la página se estabilice
            page.wait_for_timeout(1000)

            img_bytes = page.screenshot(type='png', full_page=True)
            browser.close()
    except Exception as e:
        logger.error(f"[PLAYWRIGHT SERVICE] Error al capturar screenshot para keyword '{keyword}': {e}", exc_info=True)
        return Response(f"Error al capturar screenshot con Playwright para keyword: {keyword}", status=500, mimetype='text/plain')

    if not img_bytes:
        logger.error(f"Playwright no generó bytes de imagen para keyword '{keyword}'")
        return Response("Error: Playwright no generó imagen.", status=500, mimetype='text/plain')

    # 5. Devolver la imagen y cachear
    resp = Response(img_bytes, mimetype='image/png')
    SCREENSHOT_CACHE[cache_key_hash] = (resp, now)
    logger.info(f"✅ Screenshot generado y cacheado para keyword '{keyword}', domain '{domain_norm}' (país: {country or 'España'})")
    return resp

