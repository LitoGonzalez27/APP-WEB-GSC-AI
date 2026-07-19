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
    # OJO con los plurales: Shopify usa SIEMPRE /products/ y WooCommerce en
    # español /productos/. Sin ellos, ninguna tienda Shopify tenía ficha de
    # producto en el muestreo y 3.3/4.2/7.x salían como "sin ficha accesible".
    # Idiomas: los patrones eran solo ES/EN y por eso zalando.de no tuvo NI UNA
    # ficha en el muestreo (buckets producto=0) y 3.3/4.2/C7 salieron a 0 "por
    # ausencia" cuando en realidad era ceguera nuestra. DE/FR/IT/PT/NL añadidos.
    ("producto", re.compile(
        r"/(productos?|products?|item|dp|p"
        # OJO: "artikel"/"article"/"articolo" NO se incluyen aquí aunque en DE/FR/IT
        # signifiquen también "artículo de venta": son homógrafos de "artículo de
        # blog" y robarían URLs editoriales al bucket blog, que se evalúa después.
        r"|produkte?"                              # DE
        r"|produits?"                              # FR
        r"|prodotti?"                              # IT
        r"|produtos?"                              # PT
        r"|producten?"                             # NL
        r")/|/prod-", re.I)),
    ("categoria", re.compile(
        r"/(categor[ií]as?|categor(?:y|ies)|collections?|tienda|shop|c"
        r"|kategorien?|marken?"                    # DE
        r"|cat[eé]gorie?s?|boutique|rayon"         # FR
        r"|categorie?|negozio|reparto"             # IT
        r"|categoria?s?|loja"                      # PT
        r"|categorie|winkel"                       # NL
        r")/", re.I)),
    ("blog", re.compile(
        r"/(blog|noticias|news|articulo|article|magazine|revista|guia|guide|recursos"
        r"|nachrichten|ratgeber|magazin"           # DE
        r"|actualit[eé]s?|conseils?"               # FR
        r"|notizie|guida|consigli"                 # IT
        r"|not[ií]cias"                            # PT
        r"|nieuws"                                 # NL
        r")s?/", re.I)),
    ("servicio", re.compile(
        r"/(servicio|service|soluciones|solutions|features|funcionalidades|tratamiento"
        r"|dienstleistung|leistungen|l[oö]sungen"  # DE
        r"|services?|solutions?|prestations?"      # FR
        r"|servizi|soluzioni"                      # IT
        r"|servi[çc]os|solu[çc][õo]es"             # PT
        r"|diensten|oplossingen"                   # NL
        r")s?", re.I)),
    ("legal", re.compile(
        r"/(aviso-legal|privacidad|privacy|terminos|terms|condiciones|cookies"
        r"|impressum|datenschutz|agb|widerruf"     # DE
        r"|mentions-legales|confidentialite|cgv|cgu"  # FR
        r"|note-legali|privacy-policy|condizioni"  # IT
        r"|termos|privacidade"                     # PT
        r"|voorwaarden"                            # NL
        r")", re.I)),
]

# Detección de tipología por señales DISCRIMINANTES y ponderadas.
# Regla de diseño: se cuentan señales DISTINTAS (no repeticiones) y las fuertes
# valen doble. Ante la duda, "corporativo" (el error menos dañino: C7 no aplica).
# Señales descartadas por falsos positivos: "/api" (lo tiene cualquier web con JS)
# y "demo" suelto (matchea "demostración", "demográfico"…).

ECOM_STRONG = {
    "schema_product": r'"@type"\s*:\s*"Product"',
    # Multiidioma: zalando.de solo se salvó de ser "corporativo" porque su HTML
    # tiene "/cart"; su botón real ("In den Warenkorb") no lo veía nada. Un shop
    # DE/FR/IT sin la palabra inglesa por casualidad caía a corporativo y con él
    # toda la categoría C7 a "N/A (no es e-commerce)".
    "add_to_cart": r'a[ñn]adir al carrito|a[ñn]adir a la cesta|add to cart|comprar ahora'
                   r'|in den warenkorb|in den einkaufswagen|jetzt kaufen'          # DE
                   r'|ajouter au panier|mettre au panier|acheter maintenant'       # FR
                   r'|aggiungi al carrello|acquista ora'                           # IT
                   r'|adicionar ao carrinho|comprar agora'                         # PT
                   r'|in winkelwagen|voeg toe aan winkelwagen',                    # NL
    "cart_url": r'/(carrito|cart|cesta|checkout'
                r'|warenkorb|einkaufswagen|kasse'      # DE
                r'|panier|commande'                    # FR
                r'|carrello'                           # IT
                r'|carrinho'                           # PT
                r'|winkelwagen|winkelmandje'           # NL
                r')(/|"|\'|\?|$)',
    # Solo marcadores a nivel de ASSET, nunca la palabra suelta: stripe.com
    # menciona "WooCommerce" y "Shopify" como clientes en su marketing y se
    # clasificaba como tienda. Una tienda real deja huellas técnicas
    # (plugins/woocommerce, cdn.shopify, clases woocommerce-page).
    "ecom_platform": r'plugins/woocommerce|woocommerce-page|cdn\.shopify'
                     r'|prestashop|magento|bigcommerce'
                     # marcadores de asset, nunca la palabra suelta (ver 7.1).
                     # Squarespace y Wix se dejan FUERA a propósito: son
                     # constructores de webs, no prueba de tienda. Un Wix
                     # corporativo pasaría a "ecommerce" y con él C7 entero.
                     r'|vtexassets|vtexcommercestable|/_v/public/'
                     r'|/widgets/emotion|shopware\.'
                     r'|demandware\.static|/on/demandware',
}
ECOM_WEAK = {
    "cart_word": r'\b(carrito|cesta|warenkorb|panier|carrello|carrinho|winkelwagen)\b',
    "shop_url": r'/(tienda|shop|store|productos?'
                r'|produkte|kategorien'      # DE
                r'|boutique|produits'        # FR
                r'|negozio|prodotti'         # IT
                r'|loja|produtos'            # PT
                r')(/|"|\'|$)',
    # El precio no siempre lleva el símbolo DETRÁS ni es el euro: UK usa "£19.99"
    # y muchos sitios internacionales "$19.99". Con el patrón anterior (solo
    # sufijo €/EUR) johnlewis.com y cualquier tienda en libras perdían la señal.
    "price_tag": r'\d+[.,]\d{2}\s*(€|EUR|£|GBP|CHF|USD|\$)'
                 r'|(€|£|\$|CHF)\s?\d+[.,]\d{2}',
    # Un Offer suelto NO es señal de tienda: lo llevan SoftwareApplication,
    # Service, Event, Course… La app de BBVA tiene Offer y es un banco.
    # Solo cuenta como fuerte cuando va acompañado de Product (ver ECOM_STRONG).
    "schema_offer": r'"@type"\s*:\s*"Offer"|"priceCurrency"',
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


# Una FICHA de producto termina en el slug del producto: /productos/<slug>.
# "/productos/" a media ruta suele ser una sección informativa jerárquica —
# administracion.gob.es tiene 45 URLs tipo
# /empresas/productos/normas-especificaciones/productos-industriales y salía
# clasificada como e-commerce. Exigir que el slug sea el ÚLTIMO tramo separa
# el catálogo real del contenido que habla "de productos".
_FICHA_URL_RE = re.compile(
    r"/(?:productos?|products?|p|produkte?|produits?|prodotti?|produtos?)/[^/?#]+/?$"
    r"|/(?:comprar|buy|kaufen|acheter|acquista)-[^/?#]+/?$"
    r"|-p-\d+/?$"
    r"|/dp/[^/?#]+/?$", re.I)


def _hits(patterns, corpus):
    """Devuelve el conjunto de señales DISTINTAS que aparecen (no repeticiones)."""
    return {name for name, pat in patterns.items() if re.search(pat, corpus, re.I)}


# Registros que NO son de descubrimiento agéntico aunque respondan en _aid/_agent.
# Muchos dominios tienen un TXT wildcard (típicamente SPF) que contesta a
# CUALQUIER subdominio: sin este filtro, hubspot.com daba _aid "encontrado".
_TXT_RUIDO = re.compile(r"(?i)v=spf1|v=DKIM1|v=DMARC1|google-site-verification|"
                        r"MS=|facebook-domain-verification|_globalsign|amazonses")


def dns_aid(base):
    """DNS for AI Discovery (experimental): registros TXT _aid/_agent.

    Valida el CONTENIDO y descarta wildcards: se consulta un subdominio
    inventado como control y, si devuelve lo mismo, es un comodín y no un
    registro real. Detectado en el set de calibración con hubspot.com.
    """
    host = urlparse(base).netloc.replace("www.", "")
    try:
        import dns.resolver
    except ImportError:
        return None

    def _txt(name):
        try:
            answers = dns.resolver.resolve(name, "TXT", lifetime=8)
            return " ".join(r.to_text() for r in answers).strip()
        except Exception:
            return ""

    # control de comodín: un subdominio que no puede existir
    wildcard = _txt("_control-no-existe-agentready." + host)
    for label in ("_aid.", "_agent."):
        txt = _txt(label + host)
        if not txt:
            continue
        if wildcard and txt == wildcard:
            continue  # comodín DNS, no un registro real
        if _TXT_RUIDO.search(txt):
            continue  # SPF/DKIM/verificaciones: no es descubrimiento agéntico
        return f"TXT {label}{host} -> {txt[:120]}"
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


# Los sitemaps de All in One SEO (y otros plugins de WordPress) envuelven las
# URLs en CDATA: <loc><![CDATA[https://…]]></loc>. Sin contemplarlo, el sitemap
# se leía como vacío y reportábamos "sin sitemap" en webs que sí lo tenían.
_LOC_RE = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^<\s\]]+)\s*(?:\]\]>)?\s*</loc>", re.I)
_LASTMOD_RE = re.compile(r"<lastmod>\s*(?:<!\[CDATA\[)?\s*([^<\s\]]+)\s*(?:\]\]>)?\s*</lastmod>", re.I)


def _host_base(netloc):
    """Host normalizado. `replace("www.", "")` borra la subcadena DONDE SEA:
    'shop.wwwidgets.com' se convertia en 'shop.idgets.com'. Aqui solo se quita
    el prefijo."""
    host = (netloc or "").lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def mismo_sitio(base, url):
    """¿`url` pertenece al sitio auditado?

    El filtro del sitemap era `host in urlparse(u).netloc`, una comparacion por
    SUBCADENA: para host='ikea.com' aceptaba 'notikea.com', 'ikea.com.mx' y
    'ikea.com.evil.net' como si fueran del cliente. Esas paginas se muestreaban
    y se puntuaban dentro del informe del cliente, que es afirmar sobre su web
    cosas medidas en la web de otro. `harvest_links` ya comparaba por igualdad
    exacta, asi que las dos vias de descubrimiento no coincidian.

    La frontera correcta es el host exacto o un subdominio propio: se acepta
    'shop.ikea.com', se rechaza 'notikea.com' y 'ikea.com.mx'.
    """
    host = _host_base(urlparse(base).netloc)
    otro = _host_base(urlparse(url).netloc)
    return bool(host) and (otro == host or otro.endswith("." + host))


def get_sitemap_urls(base, robots, cap=800):
    """Recoge URLs de sitemaps (indices incluidos) hasta `cap`. Tambien lastmods."""
    # Las rutas convencionales SIEMPRE se prueban, aunque robots declare otra:
    # elpozo.com declara un sitemap.rss (que no lleva <loc>) y tiene un
    # sitemap.xml perfectamente válido que así se nos escapaba.
    convencionales = [base + "/sitemap.xml", base + "/sitemap_index.xml",
                      base + "/sitemap-index.xml", base + "/wp-sitemap.xml"]
    candidates = list(dict.fromkeys((robots["sitemaps"] or []) + convencionales))
    urls, lastmods, seen_maps, estados = [], [], set(), []
    queue = list(candidates)[:6]
    while queue and len(urls) < cap:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        res = fetch(sm, timeout=25)
        estados.append(res["status"])
        if res["status"] != 200:
            continue
        body = res["body"]
        if "<sitemapindex" in body[:2000]:
            children = _LOC_RE.findall(body)
            queue.extend(children[:10])
            continue
        urls.extend(_LOC_RE.findall(body))
        lastmods.extend(_LASTMOD_RE.findall(body))
    urls = [u for u in urls if mismo_sitio(base, u)][:cap]
    # "No encontrado" y "bloqueado" NO son lo mismo: el sitemap de zalando.es
    # existe pero la conexión se corta (status 0). Afirmar "sin sitemap" en ese
    # caso sería atribuir una carencia no comprobada (guardarraíl de fidelidad).
    bloqueado = (not urls) and any(
        s == 0 or s in (401, 403, 406, 429) or s >= 500 for s in estados)
    return {"urls": urls, "lastmods": lastmods, "found": bool(urls),
            "bloqueado": bloqueado, "estados": estados}


def harvest_links(base, home_html, cap=60):
    """Fallback de cobertura cuando no hay sitemap: URLs internas de la portada.

    Sin esto, sitios sin sitemap público (es.wikipedia.org, github.com) se
    auditaban SOLO con la home y los checks de contenido quedaban ciegos.
    """
    out, seen = [], set()
    for href in re.findall(r'href=["\']([^"\'#]+)', home_html or ""):
        if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        # descartar lo que no es una página de contenido: assets y endpoints
        # internos (wikipedia enlaza /w/load.php en la portada y se muestreaba
        # ESE fichero como si fuera una página del sitio)
        if re.search(r"\.(php|json|xml|css|js|rss|atom|pdf|jpe?g|png|gif|svg|webp|ico|zip)"
                     r"(\?|$)|/(w|wp-json|api|cdn-cgi|static|assets)/", href, re.I):
            continue
        if href.startswith("//"):
            url = "https:" + href
        elif href.startswith("/"):
            url = base + href
        elif href.startswith("http"):
            url = href
        else:
            continue
        if not mismo_sitio(base, url):
            continue
        url = url.split("?")[0].rstrip("/")
        if url and url != base and url not in seen:
            seen.add(url)
            out.append(url)
        if len(out) >= cap:
            break
    return out


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
    # Relleno cuando la muestra se queda corta. Nació mirando solo "otras": en
    # sitios cuyas URLs no encajan en ningún patrón (wikipedia, github, muchas
    # SPAs) TODO cae ahí y solo se tomaba 1 página.
    #
    # Pero el mismo agujero aparece al revés, con el sitemap HOMOGÉNEO. Caso
    # real (batería 5, ikea.com): 800 URLs, las 800 de producto y el resto de
    # buckets a cero. Se tomaban 2 de producto, los demás buckets no aportaban
    # nada y el respaldo miraba "otras", que estaba vacía: 2 páginas de 800
    # para sostener TODOS los checks de contenido, con score 49,8 y
    # score_fiable=True. Generalizar a "rellena desde donde haya sobrante"
    # cubre los dos extremos con la misma regla.
    if len(sample) < 5:
        ya = {s["url"] for s in sample}
        for name in ("otras", "producto", "categoria", "servicio", "blog", "legal"):
            for u in buckets.get(name, []):
                if u in ya:
                    continue
                ya.add(u)
                sample.append({"url": u, "bucket": name})
                if len(sample) >= 5:
                    break
            if len(sample) >= 5:
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
    prod_urls = sum(1 for u in all_urls if _FICHA_URL_RE.search(u))
    if prod_urls >= 20:
        e_s = e_s | {f"catalogo_urls_producto({prod_urls})"}

    ecom_score = 2 * len(e_s) + len(e_w)
    saas_score = 2 * len(s_s) + len(s_w)
    ev = {
        "ecommerce": {"puntos": ecom_score, "fuertes": sorted(e_s), "debiles": sorted(e_w)},
        "saas": {"puntos": saas_score, "fuertes": sorted(s_s), "debiles": sorted(s_w)},
    }
    # e-commerce: una señal fuerte, o el trío débil PERO con carrito de por medio.
    # Sin carrito no hay tienda: "shop_url + precio + Offer" lo cumple cualquier
    # web corporativa que venda algo puntual o liste una app con precio.
    # El trío débil es SOLO vocabulario, y un medio grande lo cumple sin ser
    # tienda: eldiario.es menciona "carrito", precios y tiene /tienda/ de
    # merchandising, y salía clasificado como e-commerce. Exigimos que el
    # vocabulario venga respaldado por estructura (URLs con patrón de ficha).
    trio_con_carrito = (len(e_w) >= 3 and "cart_word" in e_w and prod_urls >= 5)
    # Evidencia ESTRUCTURAL de tienda (schema Product, assets de plataforma,
    # catálogo de URLs) pesa más que el vocabulario: una SaaS de pagos habla de
    # "checkout" y "add to cart" todo el día sin vender nada (stripe.com se
    # clasificaba como e-commerce por su propia jerga).
    structural = bool(e_s & {"schema_product", "ecom_platform"}) \
        or any(s.startswith("catalogo_urls") for s in e_s)
    if len(s_s) >= 2 and not structural and saas_score >= ecom_score - 2:
        return "saas", ev
    if (e_s or trio_con_carrito) and ecom_score >= saas_score:
        return "ecommerce", ev
    # saas: exige >=2 señales FUERTES (las débiles las tiene cualquier corporativa)
    if len(s_s) >= 2 and saas_score > ecom_score:
        return "saas", ev
    return "corporativo", ev
