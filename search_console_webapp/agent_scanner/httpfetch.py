# -*- coding: utf-8 -*-
"""Fetcher HTTP portable (requests). Sustituye al fetcher basado en curl del
prototipo local: sin dependencias del sistema, testeable y apto para servidor.

Incluye validación anti-SSRF: rechaza URLs a IPs privadas/loopback/link-local,
imprescindible cuando la URL la mete un usuario en un servidor público.
"""
import ipaddress
import socket
import time
from urllib.parse import urlparse

import requests

from .config import BOT_UAS, TIMEOUT_DEFAULT, UA_HUMAN

_SESSION = requests.Session()
_SESSION.max_redirects = 5


class BlockedURLError(Exception):
    """La URL apunta a un destino no permitido (IP privada, esquema inválido…)."""


def assert_public_url(url):
    """Anti-SSRF: solo http/https a hosts que resuelven a IPs públicas."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise BlockedURLError(f"esquema no permitido: {p.scheme}")
    host = p.hostname
    if not host:
        raise BlockedURLError("URL sin host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise BlockedURLError(f"el dominio no resuelve: {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            raise BlockedURLError(f"destino no público bloqueado: {ip}")


# Perfil de cabeceras de un Chrome real. Solo se usa para la línea base humana.
BROWSER_HEADERS = {
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}


# Códigos que NO son una respuesta del sitio sino un tropiezo del camino: no hay
# servicio ahora mismo, o nos han frenado por ritmo. Un 403/404/418 SÍ es una
# respuesta deliberada y no se reintenta: reintentarlo sería insistir a quien ya
# nos ha dicho que no, y además borraría un hallazgo real del informe.
TRANSITORIOS = {0, 429, 502, 503, 504, 408, 425}
REINTENTOS = 1          # un segundo intento basta para el ruido de red
PAUSA_REINTENTO = 1.5


def _es_transitorio(status):
    return status in TRANSITORIOS


def fetch(url, ua=UA_HUMAN, timeout=TIMEOUT_DEFAULT, headers=None, verify_public=True,
          reintentar=True):
    """GET con requests. Devuelve dict homogéneo (compatible con el motor)."""
    result = {"status": 0, "body": "", "headers": "", "ttfb": None,
              "total": None, "size": 0, "url": url, "error": None}
    if verify_public:
        try:
            assert_public_url(url)
        except BlockedURLError as exc:
            result["error"] = str(exc)
            return result
    hdrs = {"User-Agent": ua, "Accept-Encoding": "gzip, deflate, br"}
    # La medición de referencia "como un humano" necesita el perfil de cabeceras
    # completo: WAF tipo Akamai (BBVA, Mango) devuelven 403 a un UA de navegador
    # que llega sin Sec-Fetch/sec-ch-ua, y entonces reportábamos como "no existe"
    # cosas que sí existían. Detectado en el set de calibración.
    # Las peticiones con UA de bot NO llevan esto: un bot real no las envía, y
    # falsearlo daría una matriz de acceso que no refleja lo que le pasa al bot.
    if ua == UA_HUMAN:
        hdrs.update(BROWSER_HEADERS)
    for h in (headers or []):
        if ":" in h:
            k, v = h.split(":", 1)
            hdrs[k.strip()] = v.strip()
    t0 = time.monotonic()
    try:
        resp = _SESSION.get(url, headers=hdrs, timeout=timeout, allow_redirects=True)
        ttfb = time.monotonic() - t0
        result.update({
            "status": resp.status_code,
            "body": resp.text,
            "headers": "\n".join(f"{k}: {v}" for k, v in resp.headers.items()),
            "ttfb": round(ttfb, 4),
            "total": round(time.monotonic() - t0, 4),
            "size": len(resp.content),
            "url": resp.url,
        })
    except requests.exceptions.RequestException as exc:
        result["error"] = type(exc).__name__
    # Sin esto, una petición perdida se leía como "la web no tiene esa cosa".
    # En un análisis salen ~50 peticiones por dominio (21 rutas .well-known, la
    # matriz de bots, el muestreo de páginas…): basta que UNA se pierda para
    # reportar como ausente algo que sí está. Es el sesgo del proyecto —
    # confundir "no está" con "no lo he podido mirar" — a escala de factor.
    if reintentar and _es_transitorio(result["status"]):
        time.sleep(PAUSA_REINTENTO)
        segundo = fetch(url, ua=ua, timeout=timeout, headers=headers,
                        verify_public=verify_public, reintentar=False)
        if not _es_transitorio(segundo["status"]):
            segundo["_reintentado"] = True
            return segundo
    return result


def status_only(url, ua=UA_HUMAN, timeout=12, verify_public=True, reintentar=True):
    """Solo el código HTTP (más rápido). 0 si falla.

    Reintenta una vez ante códigos transitorios. Importa especialmente en la
    matriz de acceso de bots: un ClaudeBot=0 por timeout (visto en noel.es) o un
    GPTBot=503 pasajero (visto en elpozo.com) se publicaban como si el sitio
    bloqueara a ese bot a propósito. Eso es una acusación, no una medición.
    """
    if verify_public:
        try:
            assert_public_url(url)
        except BlockedURLError:
            return 0
    hdrs = {"User-Agent": ua}
    if ua == UA_HUMAN:
        hdrs.update(BROWSER_HEADERS)  # misma línea base que fetch(), o no comparan
    try:
        resp = _SESSION.get(url, headers=hdrs, timeout=timeout,
                            allow_redirects=True, stream=True)
        code = resp.status_code
        resp.close()
    except requests.exceptions.RequestException:
        code = 0
    if reintentar and _es_transitorio(code):
        time.sleep(PAUSA_REINTENTO)
        return status_only(url, ua=ua, timeout=timeout,
                           verify_public=verify_public, reintentar=False)
    return code


def bot_access_matrix(url):
    """Código HTTP que recibe cada UA de bot de IA + el humano."""
    matrix = {name: status_only(url, ua=ua) for name, ua in BOT_UAS.items()}
    matrix["_human"] = status_only(url, ua=UA_HUMAN)
    return matrix


def rapid_fire(url, ua, n=10, timeout=10):
    """N peticiones seguidas para observar rate limiting.

    SIN reintentos, y es deliberado: aquí un 429 no es un tropiezo del camino,
    es EL hallazgo que venimos a medir. Reintentar con pausa destruiría las dos
    cosas que hacen válida la sonda —el ritmo y el significado— y el check 2.4
    dejaría de ver el baneo que sí está ocurriendo.
    """
    return [status_only(url, ua=ua, timeout=timeout, reintentar=False)
            for _ in range(n)]


def jina_read(url, timeout=90):
    """Vista LLM vía Jina Reader (r.jina.ai). Fallback de contenido."""
    res = fetch("https://r.jina.ai/" + url, ua=UA_HUMAN, timeout=timeout,
                verify_public=False)  # r.jina.ai es el destino, ya es público
    if res["status"] == 200 and len(res["body"]) > 200:
        return res["body"]
    return None
