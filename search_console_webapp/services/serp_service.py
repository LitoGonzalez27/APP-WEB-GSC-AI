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

# ✅ NUEVO: Importar middleware de quotas para Fase 4
from quota_middleware import quota_protected_serp_call

logger = logging.getLogger(__name__)

# Caché en memoria para capturas de pantalla
SCREENSHOT_CACHE = {}
CACHE_DURATION = 3600  # segundos

def get_serp_json(params: dict) -> dict:
    """
    Devuelve el JSON crudo de la búsqueda SERP.
    ✅ FASE 4: Ahora protegido por sistema de quotas.
    """
    logger.info(f"🔍 SERP JSON request para keyword: {params.get('q')}")
    
    # ✅ NUEVO: Usar middleware de quotas
    success, result = quota_protected_serp_call(params, "json")
    
    if not success:
        # Si hay error de quota, devolver estructura esperada con info de error
        if isinstance(result, dict) and result.get('blocked'):
            logger.warning(f"🚫 Llamada bloqueada por quota: {result.get('message')}")
            return {
                "error": result.get('message', 'Quota exceeded'),
                "quota_blocked": True,
                "quota_info": result.get('quota_info', {}),
                "action_required": result.get('action_required'),
                "organic_results": [], 
                "ads": []
            }
        else:
            # Error normal de SerpAPI
            logger.error(f"❌ Error en SerpAPI: {result}")
            return {
                "error": result.get('error', 'Unknown SerpAPI error'),
                "organic_results": [], 
                "ads": []
            }
    
    # ✅ Llamada exitosa
    logger.info(f"✅ SERP JSON exitoso para keyword: {params.get('q')}")
    return result


def get_serp_html(params: dict) -> str:
    """
    Devuelve el HTML crudo de la búsqueda SERP.
    ✅ FASE 4: Ahora protegido por sistema de quotas.
    """
    logger.info(f"🔍 SERP HTML request para keyword: {params.get('q')}")
    
    # ✅ NUEVO: Usar middleware de quotas
    success, result = quota_protected_serp_call(params, "html")
    
    if not success:
        # Si hay error de quota, devolver HTML con mensaje de error
        if isinstance(result, dict) and result.get('blocked'):
            logger.warning(f"🚫 Llamada HTML bloqueada por quota: {result.get('message')}")
            return f"""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                    <h2>🚫 Quota Limit Reached</h2>
                    <p>{result.get('message', 'Quota exceeded')}</p>
                    <p><strong>Action Required:</strong> {result.get('action_required', 'Contact support')}</p>
                </body>
            </html>
            """
        else:
            # Error normal de SerpAPI
            error_msg = result.get('error', 'Unknown SerpAPI error')
            logger.error(f"❌ Error en SerpAPI HTML: {error_msg}")
            return f"<html><body>Error de SerpAPI: {error_msg}</body></html>"
    
    # ✅ Llamada exitosa - extraer HTML del resultado
    html_content = result.get('html', '')
    
    if not html_content:
        logger.warning(f"SerpAPI devolvió HTML vacío para keyword: {params.get('q')}")
        return "<html><body>No content returned from SerpAPI</body></html>"
    
    logger.info(f"✅ SERP HTML exitoso para keyword: {params.get('q')}")
    return html_content

def get_page_screenshot(keyword: str, site_url_to_highlight: str, api_key: str, country: str = None, site_url: str = None) -> Response:
    """
    Obtiene el HTML de SERP, lo mejora para resaltar el dominio,
    captura la pantalla con Playwright, cachea el PNG y devuelve un Response de Flask.
    Genera screenshot de SERP con geolocalización opcional.
    Si no se especifica country, determina dinámicamente el país con más clics.
    """
    if not api_key:
        logger.error("API Key de SerpAPI no proporcionada para get_page_screenshot.")
        return Response("Unexpected error, please contact support", status=500, mimetype='text/plain')

    # ✅ NUEVA LÓGICA: Si no hay país específico y tenemos site_url, determinar dinámicamente
    if not country and site_url:
        # Importar función desde app para evitar dependencia circular
        from app import get_top_country_for_site
        country = get_top_country_for_site(site_url)
        logger.info(f"[SCREENSHOT DYNAMIC] Usando país con más clics: {country}")

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

    # Crear cache key que incluya el país y site_url (para cache dinámico)
    domain_norm = normalize_search_console_url(site_url_to_highlight)
    site_key = site_url or 'no-site'
    cache_key_hash = hashlib.md5(f"screenshot:{keyword}:{domain_norm}:{country or 'default'}:{site_key}".encode()).hexdigest()
    now = time.time()

    if cache_key_hash in SCREENSHOT_CACHE and now - SCREENSHOT_CACHE[cache_key_hash][1] < CACHE_DURATION:
        logger.info(f"📥 Screenshot desde caché para keyword '{keyword}', domain '{domain_norm}' (país: {country or 'España'})")
        # La lógica original de cacheo ya devuelve un Response de Flask
        return SCREENSHOT_CACHE[cache_key_hash][0]

    logger.info(f"🛠️  Generando nuevo screenshot para keyword '{keyword}', domain '{domain_norm}' (país: {country or 'España'})")
    
    # ✅ FASE 4: Verificar quotas antes de generar screenshot
    # Nota: get_serp_html() ya incluye validación de quotas internamente
    html_content = get_serp_html(params)
    
    # ✅ NUEVO: Verificar si HTML contiene error de quota
    if "Quota Limit Reached" in html_content:
        logger.warning(f"🚫 Screenshot bloqueado por quota para keyword '{keyword}'")
        return Response(
            "Screenshot unavailable: Quota limit reached. Please upgrade your plan to continue.",
            status=429,  # Too Many Requests
            mimetype='text/plain'
        )

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

