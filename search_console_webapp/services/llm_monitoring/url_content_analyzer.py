"""
Análisis de contenido de URLs citadas por LLMs (Fase 1 — determinista)

Para el Top de "Top Mentioned URLs by LLMs", descarga el HTML de cada URL de
forma segura (validación anti-SSRF) y detecta, sin usar ningún LLM:

    - Si la página menciona la marca del proyecto (brand_name + brand_keywords)
    - Si enlaza al dominio de la marca, y con qué anchor texts
    - Lo mismo para cada competidor configurado
    - Clasificación de oportunidad:
        mentioned       → la página ya te menciona/enlaza
        quick_win       → menciona a competidores pero no a ti
        competitor_page → la página ES de un competidor (no accionable)
        no_mentions     → no menciona ninguna marca
        error           → no se pudo descargar/analizar

IMPORTANTE (seguridad): las URLs provienen de texto generado por LLMs, es
input no confiable. Nunca se descargan destinos internos (IPs privadas,
localhost, metadata endpoints), solo http/https en puertos estándar, con
límite de tamaño y timeout. El contenido descargado jamás se renderiza como
HTML en el frontend: solo se extraen textos que el cliente escapa.
"""

import hashlib
import ipaddress
import json
import logging
import re
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from database import get_db_connection
from services.llm_monitoring_stats import LLMMonitoringStatsService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

USER_AGENT = 'Mozilla/5.0 (compatible; ClicandseoBot/1.0; +https://clicandseo.com)'
FETCH_TIMEOUT_SECONDS = 10
MAX_CONTENT_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_REDIRECTS = 3
MAX_ANCHOR_TEXTS = 10
MAX_ANCHOR_TEXT_LENGTH = 120
MAX_TEXT_SCAN_CHARS = 500_000
ALLOWED_PORTS = (None, 80, 443)
CACHE_TTL_DAYS = 7
TOP_URLS_LIMIT = 30
MAX_WORKERS = 4

_CGNAT_NET = ipaddress.ip_network('100.64.0.0/10')

# Progreso en memoria por proyecto (misma instancia de app). La fuente de
# verdad de los resultados es la tabla llm_url_content_analysis.
_PROGRESS: Dict[int, Dict] = {}
_PROGRESS_LOCK = threading.Lock()


class UnsafeURLError(ValueError):
    """URL rechazada por la validación anti-SSRF"""


# ---------------------------------------------------------------------------
# Validación anti-SSRF y fetch seguro
# ---------------------------------------------------------------------------

def _validate_ip(ip_str: str) -> None:
    """Rechaza IPs privadas/reservadas/loopback/link-local/CGNAT"""
    ip = ipaddress.ip_address(ip_str)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in _CGNAT_NET)
    ):
        raise UnsafeURLError(f'IP no pública: {ip_str}')


def validate_public_http_url(url: str) -> None:
    """
    Valida que la URL sea http(s) público y resoluble a IPs públicas.

    Nota: la resolución DNS se valida antes de la petición; queda un riesgo
    residual TOCTOU (DNS rebinding) aceptado para esta fase — el fetch no
    reenvía credenciales ni expone la respuesta cruda al usuario.
    """
    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise UnsafeURLError(f'URL no parseable: {e}')

    if parsed.scheme not in ('http', 'https'):
        raise UnsafeURLError(f'Esquema no permitido: {parsed.scheme or "(vacío)"}')

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError('URL sin hostname')

    if parsed.username or parsed.password:
        raise UnsafeURLError('URL con credenciales embebidas')

    try:
        port = parsed.port
    except ValueError:
        raise UnsafeURLError('Puerto inválido')
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError(f'Puerto no permitido: {port}')

    hostname_lower = hostname.lower().rstrip('.')
    if hostname_lower == 'localhost' or hostname_lower.endswith(('.local', '.internal', '.localhost')):
        raise UnsafeURLError(f'Hostname interno: {hostname_lower}')

    # Host que ya es una IP literal
    try:
        _validate_ip(hostname_lower)
        return
    except UnsafeURLError:
        raise
    except ValueError:
        pass  # no es IP literal, seguir con DNS

    if '.' not in hostname_lower:
        raise UnsafeURLError(f'Hostname sin dominio: {hostname_lower}')

    try:
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        addr_infos = socket.getaddrinfo(hostname_lower, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeURLError(f'Hostname no resoluble: {hostname_lower}')

    if not addr_infos:
        raise UnsafeURLError(f'Hostname sin IPs: {hostname_lower}')

    for info in addr_infos:
        _validate_ip(info[4][0])


def fetch_url_safely(url: str) -> Dict:
    """
    Descarga una URL con validación anti-SSRF en cada salto de redirect.

    Returns:
        {'ok': bool, 'http_status': int|None, 'content': bytes|None,
         'final_url': str, 'error_reason': str|None}
    """
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.1',
        'Accept-Language': 'en;q=0.9,es;q=0.8',
    }

    current_url = url
    result = {'ok': False, 'http_status': None, 'content': None,
              'final_url': url, 'error_reason': None}

    try:
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_http_url(current_url)
            result['final_url'] = current_url

            response = requests.get(
                current_url,
                headers=headers,
                timeout=FETCH_TIMEOUT_SECONDS,
                stream=True,
                allow_redirects=False,
            )

            try:
                result['http_status'] = response.status_code

                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location')
                    if not location:
                        result['error_reason'] = 'redirect_sin_location'
                        return result
                    current_url = urljoin(current_url, location)
                    continue

                if response.status_code != 200:
                    result['error_reason'] = f'http_{response.status_code}'
                    return result

                content_type = (response.headers.get('Content-Type') or '').lower()
                if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                    result['error_reason'] = 'not_html'
                    return result

                declared_length = response.headers.get('Content-Length')
                if declared_length and declared_length.isdigit() and int(declared_length) > MAX_CONTENT_BYTES:
                    result['error_reason'] = 'too_large'
                    return result

                # Lectura por chunks con tope duro: si excede, se analiza lo leído
                chunks = []
                total = 0
                for chunk in response.iter_content(chunk_size=65536):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= MAX_CONTENT_BYTES:
                        break

                content = b''.join(chunks)[:MAX_CONTENT_BYTES]
                if not content:
                    result['error_reason'] = 'empty_content'
                    return result

                result['ok'] = True
                result['content'] = content
                return result
            finally:
                response.close()

        result['error_reason'] = 'too_many_redirects'
        return result

    except UnsafeURLError as e:
        logger.warning(f"🚫 URL rechazada por SSRF-guard: {url} ({e})")
        result['error_reason'] = 'unsafe_url'
        return result
    except requests.exceptions.SSLError:
        result['error_reason'] = 'ssl_error'
        return result
    except requests.exceptions.Timeout:
        result['error_reason'] = 'timeout'
        return result
    except requests.exceptions.RequestException as e:
        logger.info(f"⚠️ Error de red descargando {url}: {e}")
        result['error_reason'] = 'fetch_error'
        return result


# ---------------------------------------------------------------------------
# Matching de marca / competidores
# ---------------------------------------------------------------------------

def normalize_domain(value: Optional[str]) -> str:
    """Normaliza 'https://www.Foo.com/x' → 'foo.com'"""
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    if not raw.startswith(('http://', 'https://')):
        raw = f'https://{raw}'
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ''
    host = (parsed.netloc or '').split('@')[-1].split(':')[0].strip()
    if host.startswith('www.'):
        host = host[4:]
    return host


def _host_matches_domain(host: str, domain: str) -> bool:
    """True si host es el dominio o un subdominio suyo"""
    if not host or not domain:
        return False
    return host == domain or host.endswith(f'.{domain}')


def _compile_term_patterns(terms: List[str]) -> List[re.Pattern]:
    """Regex por término con límites de palabra (evita falsos positivos en substrings)"""
    patterns = []
    seen = set()
    for term in terms:
        cleaned = str(term or '').strip()
        key = cleaned.lower()
        if len(cleaned) < 2 or key in seen:
            continue
        seen.add(key)
        patterns.append(re.compile(
            r'(?<!\w)' + re.escape(cleaned) + r'(?!\w)',
            re.IGNORECASE | re.UNICODE
        ))
    return patterns


def _count_mentions(text: str, patterns: List[re.Pattern]) -> int:
    return sum(len(pattern.findall(text)) for pattern in patterns)


def _collect_anchors_for_domain(anchors: List[Dict], domain: str) -> Dict:
    """Filtra los anchors ya extraídos que apuntan a un dominio concreto"""
    linked = False
    texts = []
    seen = set()
    for anchor in anchors:
        if not _host_matches_domain(anchor['host'], domain):
            continue
        linked = True
        text = anchor['text']
        key = text.lower()
        if text and key not in seen and len(texts) < MAX_ANCHOR_TEXTS:
            seen.add(key)
            texts.append(text)
    return {'linked': linked, 'anchor_texts': texts}


def analyze_html(content: bytes, page_url: str, brand_config: Dict) -> Dict:
    """
    Análisis determinista del HTML descargado.

    Args:
        content: HTML crudo (bytes; BeautifulSoup detecta el encoding)
        page_url: URL final de la página (para resolver hrefs relativos)
        brand_config: salida de load_project_brand_config()

    Returns:
        Dict con page_title, brand_*, competitors_found y opportunity
    """
    soup = BeautifulSoup(content, 'html.parser')

    page_title = ''
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()[:300]

    # Extraer anchors una sola vez (href absoluto + texto visible)
    anchors = []
    for a_tag in soup.find_all('a', href=True):
        try:
            absolute = urljoin(page_url, a_tag['href'])
            host = normalize_domain(urlparse(absolute).netloc)
        except ValueError:
            continue
        if not host:
            continue
        text = a_tag.get_text(' ', strip=True)[:MAX_ANCHOR_TEXT_LENGTH]
        anchors.append({'host': host, 'text': text})

    # Texto visible (sin scripts/estilos) para el matching de menciones
    for tag in soup(['script', 'style', 'noscript', 'template', 'svg']):
        tag.decompose()
    visible_text = soup.get_text(' ', strip=True)[:MAX_TEXT_SCAN_CHARS]

    # --- Marca del proyecto ---
    brand_patterns = _compile_term_patterns(brand_config['brand_terms'])
    brand_mention_count = _count_mentions(visible_text, brand_patterns)
    brand_links = _collect_anchors_for_domain(anchors, brand_config['brand_domain'])

    # --- Competidores ---
    competitors_found = []
    any_competitor_present = False
    for competitor in brand_config['competitors']:
        comp_patterns = _compile_term_patterns(competitor['terms'])
        mention_count = _count_mentions(visible_text, comp_patterns)
        comp_links = _collect_anchors_for_domain(anchors, competitor['domain'])
        present = mention_count > 0 or comp_links['linked']
        if present:
            any_competitor_present = True
        competitors_found.append({
            'name': competitor['name'],
            'domain': competitor['domain'],
            'mentioned': mention_count > 0,
            'mention_count': mention_count,
            'linked': comp_links['linked'],
            'anchor_texts': comp_links['anchor_texts'],
        })

    # --- Clasificación de oportunidad ---
    page_host = normalize_domain(urlparse(page_url).netloc)
    brand_present = brand_mention_count > 0 or brand_links['linked'] \
        or _host_matches_domain(page_host, brand_config['brand_domain'])

    if brand_present:
        opportunity = 'mentioned'
    elif any(_host_matches_domain(page_host, c['domain']) for c in brand_config['competitors'] if c['domain']):
        # La página pertenece a un competidor: no es accionable como quick win
        opportunity = 'competitor_page'
    elif any_competitor_present:
        opportunity = 'quick_win'
    else:
        opportunity = 'no_mentions'

    return {
        'page_title': page_title,
        'brand_mentioned': brand_mention_count > 0,
        'brand_mention_count': brand_mention_count,
        'brand_linked': brand_links['linked'],
        'brand_anchor_texts': brand_links['anchor_texts'],
        'competitors_found': competitors_found,
        'opportunity': opportunity,
    }


# ---------------------------------------------------------------------------
# Configuración de marca del proyecto
# ---------------------------------------------------------------------------

def load_project_brand_config(project_id: int) -> Optional[Dict]:
    """
    Carga marca y competidores del proyecto para el matching.

    Returns:
        {'brand_domain', 'brand_terms', 'competitors': [{name, domain, terms}],
         'enabled_llms'} o None si el proyecto no existe
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT brand_name, brand_domain, brand_keywords,
                   selected_competitors, competitor_domains, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    if not project:
        return None

    brand_domain = normalize_domain(project.get('brand_domain'))

    brand_terms = []
    keywords = project.get('brand_keywords') or []
    if isinstance(keywords, list):
        brand_terms.extend(str(k) for k in keywords if k)
    if project.get('brand_name'):
        brand_terms.append(str(project['brand_name']))
    if not brand_terms and brand_domain:
        brand_terms.append(brand_domain.split('.')[0])

    competitors = []
    selected = project.get('selected_competitors') or []
    if isinstance(selected, list) and selected:
        for entry in selected:
            if isinstance(entry, dict):
                domain = normalize_domain(entry.get('domain') or entry.get('competitor_domain'))
                terms = [str(k) for k in (entry.get('keywords') or []) if k]
                name = str(entry.get('name') or '').strip()
            else:
                domain = normalize_domain(entry)
                terms = []
                name = ''
            if not domain and not terms:
                continue
            if not name:
                name = (terms[0] if terms else domain.split('.')[0]).strip()
            if not terms and domain:
                terms = [domain.split('.')[0]]
            competitors.append({'name': name, 'domain': domain, 'terms': terms})
    else:
        # Fallback legacy: solo dominios
        for raw_domain in (project.get('competitor_domains') or []):
            domain = normalize_domain(raw_domain)
            if not domain:
                continue
            label = domain.split('.')[0]
            competitors.append({'name': label, 'domain': domain, 'terms': [label]})

    return {
        'brand_domain': brand_domain,
        'brand_terms': brand_terms,
        'competitors': competitors,
        'enabled_llms': project.get('enabled_llms') or [],
    }


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def _url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode('utf-8')).hexdigest()


def _upsert_analysis(project_id: int, url: str, fields: Dict) -> None:
    conn = get_db_connection()
    if not conn:
        logger.error(f"❌ Sin conexión a BD para guardar análisis de {url}")
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO llm_url_content_analysis (
                project_id, url, url_hash, status, http_status, page_title,
                brand_mentioned, brand_mention_count, brand_linked, brand_anchor_texts,
                competitors_found, opportunity, error_reason, fetched_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb,
                %s::jsonb, %s, %s, NOW(), NOW()
            )
            ON CONFLICT (project_id, url_hash) DO UPDATE SET
                status = EXCLUDED.status,
                http_status = EXCLUDED.http_status,
                page_title = EXCLUDED.page_title,
                brand_mentioned = EXCLUDED.brand_mentioned,
                brand_mention_count = EXCLUDED.brand_mention_count,
                brand_linked = EXCLUDED.brand_linked,
                brand_anchor_texts = EXCLUDED.brand_anchor_texts,
                competitors_found = EXCLUDED.competitors_found,
                opportunity = EXCLUDED.opportunity,
                error_reason = EXCLUDED.error_reason,
                fetched_at = EXCLUDED.fetched_at,
                updated_at = NOW()
        """, (
            project_id, url, _url_hash(url),
            fields.get('status', 'completed'),
            fields.get('http_status'),
            fields.get('page_title'),
            bool(fields.get('brand_mentioned')),
            int(fields.get('brand_mention_count') or 0),
            bool(fields.get('brand_linked')),
            json.dumps(fields.get('brand_anchor_texts') or []),
            json.dumps(fields.get('competitors_found') or []),
            fields.get('opportunity'),
            fields.get('error_reason'),
        ))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"❌ Error guardando análisis de {url}: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()


def _load_existing_analyses(project_id: int, urls: List[str]) -> Dict[str, Dict]:
    """Devuelve {url: fila} para las URLs ya analizadas del proyecto"""
    if not urls:
        return {}
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        hashes = [_url_hash(u) for u in urls]
        cur.execute("""
            SELECT url, url_hash, status, http_status, page_title,
                   brand_mentioned, brand_mention_count, brand_linked,
                   brand_anchor_texts, competitors_found, opportunity,
                   error_reason, fetched_at
            FROM llm_url_content_analysis
            WHERE project_id = %s AND url_hash = ANY(%s)
        """, (project_id, hashes))
        rows = cur.fetchall()
        cur.close()
        by_hash = {row['url_hash'].strip(): row for row in rows}
        return {url: by_hash[h] for url, h in zip(urls, hashes) if h in by_hash}
    except Exception as e:
        logger.error(f"❌ Error cargando análisis existentes: {e}", exc_info=True)
        return {}
    finally:
        conn.close()


def _needs_refresh(row: Optional[Dict]) -> bool:
    if not row:
        return True
    if row.get('status') != 'completed':
        return True
    fetched_at = row.get('fetched_at')
    if not fetched_at:
        return True
    return fetched_at < datetime.now() - timedelta(days=CACHE_TTL_DAYS)


# ---------------------------------------------------------------------------
# Progreso en memoria
# ---------------------------------------------------------------------------

def try_begin_analysis(project_id: int) -> bool:
    """Marca el proyecto como 'analizando'. False si ya hay un análisis en curso."""
    with _PROGRESS_LOCK:
        current = _PROGRESS.get(project_id)
        if current and current.get('running'):
            return False
        _PROGRESS[project_id] = {
            'running': True, 'total': 0, 'done': 0,
            'started_at': datetime.now().isoformat(),
        }
        return True


def get_progress(project_id: int) -> Dict:
    with _PROGRESS_LOCK:
        progress = _PROGRESS.get(project_id)
        if not progress:
            return {'running': False, 'total': 0, 'done': 0}
        return dict(progress)


def _set_progress(project_id: int, **fields) -> None:
    with _PROGRESS_LOCK:
        if project_id in _PROGRESS:
            _PROGRESS[project_id].update(fields)


def _increment_done(project_id: int) -> None:
    with _PROGRESS_LOCK:
        if project_id in _PROGRESS:
            _PROGRESS[project_id]['done'] += 1


def _finish_analysis(project_id: int) -> None:
    with _PROGRESS_LOCK:
        if project_id in _PROGRESS:
            _PROGRESS[project_id]['running'] = False


def release_analysis_guard(project_id: int) -> None:
    """Libera el guard si el análisis no llegó a arrancar (fallo al crear el thread)"""
    _finish_analysis(project_id)


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def _analyze_single_url(project_id: int, url: str, brand_config: Dict) -> None:
    """Descarga, analiza y persiste una URL. Nunca lanza (guarda el error)."""
    try:
        fetch = fetch_url_safely(url)
        if not fetch['ok']:
            _upsert_analysis(project_id, url, {
                'status': 'error',
                'http_status': fetch['http_status'],
                'opportunity': 'error',
                'error_reason': fetch['error_reason'],
            })
            return

        analysis = analyze_html(fetch['content'], fetch['final_url'], brand_config)
        analysis.update({'status': 'completed', 'http_status': fetch['http_status']})
        _upsert_analysis(project_id, url, analysis)
    except Exception as e:
        logger.error(f"❌ Error analizando {url}: {e}", exc_info=True)
        _upsert_analysis(project_id, url, {
            'status': 'error',
            'opportunity': 'error',
            'error_reason': 'analysis_error',
        })


def run_analysis_for_project(project_id: int, days: int = 30, force: bool = False) -> Dict:
    """
    Analiza el contenido del Top de URLs citadas de un proyecto.

    Debe llamarse DESPUÉS de try_begin_analysis(project_id) (el endpoint hace
    el guard). Pensado para ejecutarse en un thread de background.
    """
    processed = 0
    skipped = 0
    try:
        brand_config = load_project_brand_config(project_id)
        if not brand_config:
            logger.error(f"❌ Proyecto {project_id} no encontrado para análisis de URLs")
            return {'success': False, 'error': 'project_not_found'}

        top_urls = LLMMonitoringStatsService.get_project_urls_ranking(
            project_id=project_id,
            days=days,
            enabled_llms=brand_config['enabled_llms'] or None,
            limit=TOP_URLS_LIMIT,
        )
        urls = [item['url'] for item in top_urls]
        if not urls:
            logger.info(f"ℹ️ Proyecto {project_id}: sin URLs citadas que analizar")
            return {'success': True, 'processed': 0, 'skipped': 0}

        existing = _load_existing_analyses(project_id, urls)
        pending = [u for u in urls if force or _needs_refresh(existing.get(u))]
        skipped = len(urls) - len(pending)
        _set_progress(project_id, total=len(pending))

        logger.info(
            f"🔍 Análisis de contenido proyecto {project_id}: "
            f"{len(pending)} URLs a procesar, {skipped} en caché"
        )

        if pending:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [
                    executor.submit(_analyze_single_url, project_id, url, brand_config)
                    for url in pending
                ]
                for future in as_completed(futures):
                    future.result()  # _analyze_single_url no lanza
                    processed += 1
                    _increment_done(project_id)

        logger.info(f"✅ Análisis de contenido completado para proyecto {project_id}: {processed} URLs")
        return {'success': True, 'processed': processed, 'skipped': skipped}

    except Exception as e:
        logger.error(f"❌ Error en análisis de contenido del proyecto {project_id}: {e}", exc_info=True)
        return {'success': False, 'error': 'internal_error'}
    finally:
        _finish_analysis(project_id)


def _serialize_row(row: Dict) -> Dict:
    fetched_at = row.get('fetched_at')
    return {
        'status': row.get('status'),
        'http_status': row.get('http_status'),
        'page_title': row.get('page_title'),
        'brand_mentioned': bool(row.get('brand_mentioned')),
        'brand_mention_count': int(row.get('brand_mention_count') or 0),
        'brand_linked': bool(row.get('brand_linked')),
        'brand_anchor_texts': row.get('brand_anchor_texts') or [],
        'competitors_found': row.get('competitors_found') or [],
        'opportunity': row.get('opportunity'),
        'error_reason': row.get('error_reason'),
        'fetched_at': fetched_at.isoformat() if fetched_at else None,
    }


def get_analysis_overview(project_id: int, days: int = 30) -> Dict:
    """
    Estado + resultados del análisis para el Top actual de URLs del proyecto.
    Usado por el endpoint GET (el frontend hace polling con esto).
    """
    brand_config = load_project_brand_config(project_id)
    if not brand_config:
        return {'success': False, 'error': 'project_not_found'}

    top_urls = LLMMonitoringStatsService.get_project_urls_ranking(
        project_id=project_id,
        days=days,
        enabled_llms=brand_config['enabled_llms'] or None,
        limit=TOP_URLS_LIMIT,
    )
    urls = [item['url'] for item in top_urls]
    existing = _load_existing_analyses(project_id, urls)

    results = []
    summary = {'analyzed': 0, 'mentioned': 0, 'quick_wins': 0,
               'competitor_pages': 0, 'no_mentions': 0, 'errors': 0, 'pending': 0}

    for item in top_urls:
        row = existing.get(item['url'])
        if row:
            serialized = _serialize_row(row)
            if serialized['status'] == 'completed':
                summary['analyzed'] += 1
                opportunity = serialized['opportunity']
                if opportunity == 'mentioned':
                    summary['mentioned'] += 1
                elif opportunity == 'quick_win':
                    summary['quick_wins'] += 1
                elif opportunity == 'competitor_page':
                    summary['competitor_pages'] += 1
                elif opportunity == 'no_mentions':
                    summary['no_mentions'] += 1
            else:
                summary['errors'] += 1
        else:
            serialized = None
            summary['pending'] += 1

        results.append({'url': item['url'], 'rank': item.get('rank'), 'analysis': serialized})

    return {
        'success': True,
        'project_id': project_id,
        'days': days,
        'top_limit': TOP_URLS_LIMIT,
        'progress': get_progress(project_id),
        'summary': summary,
        'results': results,
    }
