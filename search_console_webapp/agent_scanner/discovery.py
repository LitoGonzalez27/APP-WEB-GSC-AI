"""Descubrimiento del dominio: robots, sitemaps, muestreo de plantillas y tipologia.

No rastreamos el dominio entero: muestreamos N paginas representativas por
tipo de plantilla (producto, categoria, blog, servicio, legal). Una web de
50.000 URLs se audita con ~12 paginas bien elegidas.
"""
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from .httpfetch import fetch
from .config import UA_HUMAN

BUCKET_PATTERNS = [
    ("producto", re.compile(r"/(producto|product|item|dp|p)/|/prod-", re.I)),
    ("categoria", re.compile(r"/(categoria|category|collections|tienda|shop|c)/", re.I)),
    ("blog", re.compile(r"/(blog|noticias|news|articulo|article|magazine|revista|guia|guide|recursos)s?/", re.I)),
    ("servicio", re.compile(r"/(servicio|service|soluciones|solutions|features|funcionalidades|tratamiento)s?", re.I)),
    ("legal", re.compile(r"/(aviso-legal|privacidad|privacy|terminos|terms|condiciones|cookies)", re.I)),
]

# Detección de tipología por señales DISCRIMINANTES y ponderadas.
# Regla de diseño: se cuentan señales DISTINTAS (no repeticiones) y las fuertes
# valen doble. Ante la duda, "corporativo" (el error menos dañino: C7 no aplica).
# Señales descartadas por falsos positivos: "/api" (lo tiene cualquier web con JS)
# y "demo" suelto (matchea "demostración", "demográfico"…).

ECOM_STRONG = {
    "schema_product": r'"@type"\s*:\s*"Product"',
    "add_to_cart": r'a[ñn]adir al carrito|a[ñn]adir a la cesta|add to cart|comprar ahora',
    "cart_url": r'/(carrito|cart|cesta|checkout)(/|"|\'|\?|$)',
    "ecom_platform": r'woocommerce|cdn\.shopify|shopify\.com|prestashop|magento|bigcommerce|vtex',
    "schema_offer": r'"@type"\s*:\s*"Offer"|"priceCurrency"',
}
ECOM_WEAK = {
    "cart_word": r'\bcarrito\b|\bcesta\b',
    "shop_url": r'/(tienda|shop|store|productos?)(/|"|\'|$)',
    "price_tag": r'\d+[.,]\d{2}\s*(€|EUR)',
}
SAAS_STRONG = {
    "free_trial": r'prueba gratis|pru[eé]balo gratis|free trial|empieza gratis|start free|comienza gratis',
    "no_card": r'sin tarjeta de cr[eé]dito|no credit card',
    "schema_software": r'"@type"\s*:\s*"SoftwareApplication"',
    "signup_url": r'/(signup|sign-up|registro|register|crear-cuenta|get-started)(/|"|\'|\?|$)',
    "request_demo": r'(solicita|solicitar|agenda|agendar|pide|pedir|request|book)\s+(una\s+|a\s+|tu\s+)?demo\b',
    "per_user_pricing": r'(€|\$|usd|eur)\s*\d+\s*(\/|por\s+)(mes|month|usuario|user|mo\b)',
    "saas_words": r'\bSaaS\b|software as a service|plataforma en la nube',
}
SAAS_WEAK = {
    "pricing_url": r'/(pricing|precios|planes|plans)(/|"|\'|$)',
    "login_url": r'/(login|signin|iniciar-sesion|acceso)(/|"|\'|\?|$)',
    "docs_url": r'/(docs|documentation|developers)(/|"|\'|$)',
    "integrations": r'/(integraciones|integrations)(/|"|\'|$)|\bAPI\s+(key|docs|REST)\b',
}


def _hits(patterns, corpus):
    """Devuelve el conjunto de señales DISTINTAS que aparecen (no repeticiones)."""
    return {name for name, pat in patterns.items() if re.search(pat, corpus, re.I)}


def dns_aid(base):
    """DNS for AI Discovery (experimental): registros TXT _aid/_agent.
    Usa dnspython (portable), con fallback a `dig` si estuviera disponible."""
    host = urlparse(base).netloc.replace("www.", "")
    try:
        import dns.resolver
        for label in ("_aid.", "_agent."):
            try:
                answers = dns.resolver.resolve(label + host, "TXT", lifetime=8)
                txt = " ".join(r.to_text() for r in answers)
                if txt:
                    return f"TXT {label}{host} -> {txt[:120]}"
            except Exception:
                continue
        return None
    except ImportError:
        return None


def normalize(url):
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def get_robots(base):
    res = fetch(base + "/robots.txt", timeout=15)
    is_html = "<html" in res["body"][:400].lower()
    return {
        "status": res["status"],
        "raw": "" if is_html else res["body"],
        "is_html": is_html,
        "sitemaps": re.findall(r"(?im)^\s*sitemap:\s*(\S+)", res["body"] or ""),
    }


def parse_robots_groups(raw):
    """Devuelve {ua_lower: [(directiva, ruta)]} de forma tolerante."""
    groups, current_uas = {}, []
    for line in (raw or "").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        m = re.match(r"(?i)^user-agent:\s*(.+)$", line)
        if m:
            ua = m.group(1).strip().lower()
            current_uas = current_uas + [ua] if current_uas and groups.get(current_uas[-1]) == [] else [ua]
            groups.setdefault(ua, [])
            continue
        m = re.match(r"(?i)^(allow|disallow):\s*(.*)$", line)
        if m and current_uas:
            for ua in current_uas:
                groups.setdefault(ua, []).append((m.group(1).lower(), m.group(2).strip()))
    return groups


def robots_allows(groups, bot_name, path="/"):
    """Aproximacion suficiente: mira el grupo especifico del bot, si no, '*'. """
    rules = None
    for ua in groups:
        if bot_name.lower() in ua:
            rules = groups[ua]
            break
    if rules is None:
        rules = groups.get("*")
    if not rules:
        return True
    verdict = True
    best_len = -1
    for directive, rule_path in rules:
        if not rule_path:
            continue
        clean = rule_path.replace("*", "")
        if path.startswith(clean) and len(clean) > best_len:
            best_len = len(clean)
            verdict = directive == "allow"
    return verdict


def get_sitemap_urls(base, robots, cap=800):
    """Recoge URLs de sitemaps (indices incluidos) hasta `cap`. Tambien lastmods."""
    candidates = robots["sitemaps"] or [base + "/sitemap.xml", base + "/sitemap_index.xml"]
    urls, lastmods, seen_maps = [], [], set()
    queue = list(candidates)[:6]
    while queue and len(urls) < cap:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        res = fetch(sm, timeout=25)
        if res["status"] != 200:
            continue
        body = res["body"]
        if "<sitemapindex" in body[:2000]:
            children = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
            queue.extend(children[:10])
            continue
        urls.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body))
        lastmods.extend(re.findall(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", body))
    host = urlparse(base).netloc.replace("www.", "")
    urls = [u for u in urls if host in urlparse(u).netloc][:cap]
    return {"urls": urls, "lastmods": lastmods, "found": bool(urls)}


def sitemap_freshness(lastmods, days=90):
    cutoff = datetime.now() - timedelta(days=days)
    for lm in lastmods[:400]:
        try:
            if datetime.fromisoformat(lm.strip()[:10]) >= cutoff:
                return True
        except ValueError:
            continue
    return False


def classify_and_sample(urls, per_bucket=2, max_total=10):
    """Clasifica URLs por plantilla y devuelve una muestra representativa."""
    buckets = {name: [] for name, _ in BUCKET_PATTERNS}
    buckets["otras"] = []
    for u in urls:
        path = urlparse(u).path or "/"
        if path in ("", "/"):
            continue
        for name, pattern in BUCKET_PATTERNS:
            if pattern.search(path):
                buckets[name].append(u)
                break
        else:
            buckets["otras"].append(u)
    sample = []
    for name in ("producto", "categoria", "servicio", "blog", "otras", "legal"):
        take = 1 if name in ("legal", "otras") else per_bucket
        for u in buckets[name][:take]:
            sample.append({"url": u, "bucket": name})
        if len(sample) >= max_total:
            break
    return buckets, sample[:max_total]


def detect_typology(home_html, all_urls):
    """ecommerce / saas / corporativo por señales distintas y ponderadas.

    Fuertes valen 2, débiles 1. Para declarar SaaS se exigen >=2 señales FUERTES
    (las débiles solas —/login, /precios— las tiene cualquier web corporativa).
    Para e-commerce basta 1 fuerte con ventaja. Si no, corporativo.
    """
    corpus = (home_html or "") + " " + " ".join(all_urls[:300])
    e_s, e_w = _hits(ECOM_STRONG, corpus), _hits(ECOM_WEAK, corpus)
    s_s, s_w = _hits(SAAS_STRONG, corpus), _hits(SAAS_WEAK, corpus)

    # Señal estructural: muchas URLs con patrón de ficha de producto en el sitemap.
    # Un catálogo grande es evidencia fuerte de e-commerce aunque la home sea JS.
    prod_urls = sum(1 for u in all_urls if re.search(
        r"/(producto|product|p)/|/(comprar|buy)-|-p-\d+|/dp/", u, re.I))
    if prod_urls >= 20:
        e_s = e_s | {f"catalogo_urls_producto({prod_urls})"}

    ecom_score = 2 * len(e_s) + len(e_w)
    saas_score = 2 * len(s_s) + len(s_w)
    ev = {
        "ecommerce": {"puntos": ecom_score, "fuertes": sorted(e_s), "debiles": sorted(e_w)},
        "saas": {"puntos": saas_score, "fuertes": sorted(s_s), "debiles": sorted(s_w)},
    }
    # e-commerce: una señal fuerte, o el trío débil completo (carrito + tienda + precios)
    if (e_s or len(e_w) >= 3) and ecom_score >= saas_score:
        return "ecommerce", ev
    # saas: exige >=2 señales FUERTES (las débiles las tiene cualquier corporativa)
    if len(s_s) >= 2 and saas_score > ecom_score:
        return "saas", ev
    return "corporativo", ev
