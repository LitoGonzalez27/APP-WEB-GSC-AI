# -*- coding: utf-8 -*-
"""Suite de regresión OFFLINE del scanner: `python3 -m agent_scanner.selftest`.

Cada test corresponde a un bug REAL encontrado en calibración o en las baterías
de dominios (jul 2026). Si un cambio futuro reintroduce uno de estos fallos,
esta suite lo caza sin tocar la red. Complemento de la calibración con dominios
vivos (CALIBRACION.md en el proyecto web-agentica), no sustituto.

Sin dependencias de test externas: asserts planos, exit code 1 si algo falla.
"""
import os
import re
import sys
import time

from . import checks, discovery, engine, scoring
from .agents import _aggregate, hitos_aplicables

FALLOS = []
PASADOS = 0


def t(nombre, cond, detalle=""):
    global PASADOS
    if cond:
        PASADOS += 1
    else:
        FALLOS.append(f"{nombre}: {detalle}")


def ctx_base():
    """Contexto sintético mínimo que satisface a todos los run_cX."""
    html_pagina = ("<html><head><title>x</title></head><body><h1>Guia</h1>"
                   "<h2>Que es</h2><p>" + "palabra " * 80 + "</p>"
                   "<h2>Como funciona</h2><p>" + "dato " * 80 + "</p></body></html>")
    return {
        "base": "https://test.example",
        "trail": [],
        "robots": {"status": 200, "raw": "User-agent: *\nAllow: /\n",
                   "is_html": False, "sitemaps": []},
        "sitemap": {"urls": ["https://test.example/blog/a"], "lastmods": [], "found": True},
        "sitemap_fresh": True,
        "home": {"status": 200, "body": "<html><body><h1>Hola</h1>" + "texto " * 200 + "</body></html>",
                 "headers": "content-type: text/html", "ttfb": 0.2, "_via": "http"},
        "bot_matrix": {"GPTBot": 200, "ClaudeBot": 200, "_human": 200},
        "rapid": [200] * 10,
        "wellknown": {}, "wellknown_meta": {},
        "pages": [{"url": "https://test.example/blog/a", "bucket": "blog",
                   "fetch": {"status": 200, "body": html_pagina, "ttfb": 0.2,
                             "headers": ""}}],
        "typology": "corporativo", "typology_evidence": {},
        "rendered_home": None, "rendered_pages": [],
        "md_negotiation": {"content_type": "text/html", "is_markdown": False},
        "dns_aid": None, "jina_home_excerpt": "", "jina_ok": True,
        "psi_cls": None, "error_probe": None, "login_probe": {"found": False},
        "agent_tests": None, "buckets_size": {},
    }


def by_id(results, cid):
    return next(r for r in results if r["id"] == cid)


# ---------------------------------------------------------- buckets y tipología

def test_buckets_plurales():
    """Bug: /products/ (Shopify) y /productos/ (WooCommerce ES) no eran fichas."""
    casos = {"/products/gafas-sol": "producto", "/productos/jamon": "producto",
             "/product/item": "producto", "/categorias/verano": "categoria",
             "/collections/gafas": "categoria", "/p/123": "producto",
             "/press/nota": None, "/pricing": None}
    for path, want in casos.items():
        got = next((n for n, p in discovery.BUCKET_PATTERNS if p.search(path)), None)
        t("buckets_plurales", got == want, f"{path}: esperado {want}, obtenido {got}")


def test_tipologia_catalogo_shopify():
    """Bug: home JS-vacía + catálogo /products/ no se declaraba e-commerce."""
    urls = [f"https://x.com/products/item-{i}" for i in range(30)]
    typ, _ = discovery.detect_typology("", urls)
    t("tipologia_catalogo_shopify", typ == "ecommerce", f"obtenido {typ}")


def test_catalogo_vs_seccion_informativa():
    """Bug: administracion.gob.es salía e-commerce por 45 URLs tipo
    /empresas/productos/normas-especificaciones/productos-industriales —
    contenido que HABLA de productos, no un catálogo."""
    gob = [f"https://x.gob.es/empresas/productos/normas-especificaciones/sector-{i}"
           for i in range(45)]
    typ, ev = discovery.detect_typology("Portal de la administracion", gob)
    t("gob_no_es_tienda", typ != "ecommerce", f"obtenido {typ}")
    t("gob_sin_senal_catalogo",
      not any("catalogo_urls" in s for s in ev["ecommerce"]["fuertes"]),
      str(ev["ecommerce"]["fuertes"]))
    # fichas reales (el slug es el último tramo) sí son catálogo
    tienda = [f"https://x.es/productos/jamon-iberico-{i}" for i in range(25)]
    typ, _ = discovery.detect_typology("", tienda)
    t("catalogo_real", typ == "ecommerce", f"obtenido {typ}")


def test_tipologia_jerga_pagos_no_es_tienda():
    """Bug: stripe.com salía e-commerce por hablar de checkout/add-to-cart y
    mencionar WooCommerce/Shopify como CLIENTES (prosa, no assets)."""
    corpus = ("Somos una plataforma SaaS de pagos. Add to cart optimizado. "
              "Empieza gratis con /signup/. Nuestros clientes usan WooCommerce "
              "y Shopify. Visita /es/checkout/ para ver la demo. 1,40 € por "
              "transaccion. /pricing/ /login/")
    typ, _ = discovery.detect_typology(corpus, [])
    t("tipologia_jerga_pagos", typ == "saas", f"obtenido {typ}")


def test_tipologia_woocommerce_real():
    """Una tienda WooCommerce real (assets, no prosa) sí es e-commerce."""
    corpus = ('<link href="/wp-content/plugins/woocommerce/style.css">'
              '<body class="woocommerce-page">Añadir al carrito. /carrito/')
    typ, _ = discovery.detect_typology(corpus, [])
    t("tipologia_woocommerce_real", typ == "ecommerce", f"obtenido {typ}")


def test_tipologia_offer_no_es_tienda():
    """Bug: BBVA salía e-commerce por un Offer suelto (su app) + precios."""
    corpus = ('{"@type": "Offer", "priceCurrency": "EUR"} nuestra /tienda/ '
              'de recuerdos 12,50 € — banco corporativo, no vendemos online')
    typ, _ = discovery.detect_typology(corpus, [])
    t("tipologia_offer_no_tienda", typ == "corporativo", f"obtenido {typ}")


def test_tipologia_sin_senales():
    """Sin señales → corporativo (default explícito, nunca adivinar)."""
    typ, ev = discovery.detect_typology("", [])
    t("tipologia_sin_senales", typ == "corporativo"
      and ev["ecommerce"]["puntos"] == 0, f"obtenido {typ}")


def test_sitemap_cdata():
    """Bug: All in One SEO envuelve <loc> en CDATA y el sitemap se leía vacío."""
    xml = ('<url><loc><![CDATA[https://x.com/a]]></loc>'
           '<lastmod><![CDATA[2026-07-06T06:50:22+00:00]]></lastmod></url>'
           '<url><loc>https://x.com/b</loc><lastmod>2026-01-01</lastmod></url>')
    locs = discovery._LOC_RE.findall(xml)
    lastmods = discovery._LASTMOD_RE.findall(xml)
    t("sitemap_cdata", locs == ["https://x.com/a", "https://x.com/b"], f"locs={locs}")
    t("sitemap_cdata_lastmod", len(lastmods) == 2, f"lastmods={lastmods}")


def test_dns_wildcard_ruido():
    """Bug: _aid.hubspot.com devolvía un SPF wildcard y contaba como DNS-AID."""
    t("dns_ruido_spf", bool(discovery._TXT_RUIDO.search('"v=spf1 ~all"')),
      "el SPF no se reconoce como ruido")
    t("dns_ruido_real", not discovery._TXT_RUIDO.search('"aid=https://x.com/agent.json"'),
      "un registro agentico real se descarta por error")


def test_sitemap_bloqueado_no_es_ausente():
    """Bug: el sitemap de zalando.es está bloqueado (timeout/403) y el check
    afirmaba 'sin sitemap' — una carencia no comprobada."""
    ctx = ctx_base()
    ctx["sitemap"] = {"urls": [], "lastmods": [], "found": False,
                      "bloqueado": True, "estados": [0, 403]}
    r = by_id(checks.run_c1(ctx), "1.4")
    t("sitemap_bloqueado", r["score"] is None and "no es afirmable" in r["evidence"],
      f"score={r['score']}")
    ctx["sitemap"] = {"urls": [], "lastmods": [], "found": False,
                      "bloqueado": False, "estados": [404]}
    r = by_id(checks.run_c1(ctx), "1.4")
    t("sitemap_ausente_real", r["score"] == 0, f"score={r['score']}")


def test_trio_debil_necesita_estructura():
    """Bug: eldiario.es (prensa) salía e-commerce por el trío débil de
    vocabulario — menciona carrito, precios y tiene /tienda/ de merchandising."""
    prensa = ("Ultima hora. Nuestro carrito de la compra sube. Ver /tienda/ "
              "de camisetas. Suscripcion 5,99 € al mes. /login/ /registro/")
    urls_prensa = [f"https://x.es/politica/noticia-{i}" for i in range(40)]
    typ, _ = discovery.detect_typology(prensa, urls_prensa)
    t("trio_sin_estructura", typ != "ecommerce", f"obtenido {typ}")
    # la misma jerga CON catálogo real sí es tienda
    urls_tienda = [f"https://x.es/producto/item-{i}" for i in range(10)]
    typ, _ = discovery.detect_typology(prensa, urls_tienda)
    t("trio_con_estructura", typ == "ecommerce", f"obtenido {typ}")


def test_ficha_vs_articulo_afiliacion():
    """Bug: eldiario.es acababa e-commerce porque DOS NOTICIAS llevaban Product
    schema de afiliación y se promovían como fichas de producto."""
    articulo = [{"@type": "NewsArticle", "headline": "Los mejores ventiladores"},
                {"@type": "Product", "name": "Ventilador X",
                 "offers": {"@type": "Offer", "price": "49.99"}}]
    t("afiliacion_no_es_ficha", not engine._es_ficha_producto(articulo),
      "un artículo con Product embebido se acepta como ficha")
    ficha = [{"@type": "Product", "name": "Gafas",
              "offers": {"@type": "Offer", "price": "29.90", "priceCurrency": "EUR"}}]
    t("ficha_real", engine._es_ficha_producto(ficha), "una ficha real se rechaza")
    mencion = [{"@type": "Product", "name": "Producto sin precio"}]
    t("mencion_sin_precio", not engine._es_ficha_producto(mencion),
      "un Product sin oferta cuenta como ficha")


def test_muestreo_rellena_otras():
    """Bug: si todas las URLs caen en 'otras' (wikipedia, github) solo se
    muestreaba 1 página y los checks de contenido quedaban ciegos."""
    urls = [f"https://x.org/tema-{i}" for i in range(30)]
    _b, sample = discovery.classify_and_sample(urls)
    t("muestreo_rellena", len(sample) >= 5, f"solo {len(sample)} páginas")


def test_harvest_links():
    """Bug de cobertura: sin sitemap (wikipedia, github) se auditaba SOLO la
    home. El plan B extrae enlaces internos de la portada."""
    html = ('<a href="/wiki/Portada">a</a> <a href="/wiki/Ciencia?x=1#top">b</a> '
            '<a href="https://es.wikipedia.org/wiki/Arte">c</a> '
            '<a href="https://otro-dominio.com/fuera">externo</a> '
            '<a href="mailto:x@y.com">mail</a> <a href="/wiki/Portada">dup</a> '
            '<a href="/w/load.php">script</a> <a href="/api/v1/data.json">api</a> '
            '<a href="/static/main.css">css</a>')
    urls = discovery.harvest_links("https://es.wikipedia.org", html)
    t("harvest_internas", len(urls) == 3 and all("wikipedia.org" in u for u in urls),
      str(urls))
    t("harvest_sin_query", not any("?" in u or "#" in u for u in urls), str(urls))
    # bug: se muestreaba /w/load.php como si fuera una página del sitio
    t("harvest_sin_assets",
      not any(re.search(r"\.php|\.json|\.css|/w/|/api/", u) for u in urls), str(urls))


# ---------------------------------------------------------- checks C1/C2

def test_bloqueo_5xx():
    """Bug: GPTBot=503 (elpozo) se daba por 'todo coincide' (solo miraba 4xx)."""
    ctx = ctx_base()
    ctx["bot_matrix"] = {"GPTBot": 503, "ClaudeBot": 200, "_human": 200}
    r = by_id(checks.run_c1(ctx), "1.3")
    t("bloqueo_5xx_score", r["score"] == 0, f"score={r['score']}")
    t("bloqueo_5xx_reintento", "reintentara" in r["evidence"],
      "no explica el peligro del 503")


def test_politica_bots_secundario():
    """Bug: Notion sacaba nota máxima nombrando solo a Amazonbot."""
    ctx = ctx_base()
    ctx["robots"]["raw"] = "User-agent: Amazonbot\nDisallow: /\nUser-agent: *\nAllow: /\n"
    r = by_id(checks.run_c1(ctx), "1.2")
    t("politica_solo_secundario", r["score"] == 0.5, f"score={r['score']}")
    ctx["robots"]["raw"] = ("User-agent: GPTBot\nAllow: /\n"
                            "User-agent: ClaudeBot\nAllow: /\nUser-agent: *\nAllow: /\n")
    r = by_id(checks.run_c1(ctx), "1.2")
    t("politica_principales", r["score"] == 1, f"score={r['score']}")


def test_content_signals():
    """Detección positiva validada con cloudflare.com."""
    ctx = ctx_base()
    ctx["robots"]["raw"] += "Content-Signal: search=yes, ai-train=no\n"
    r = by_id(checks.run_c2(ctx), "2.1")
    t("content_signals", r["score"] == 1 and "search=yes" in r["evidence"],
      f"score={r['score']} ev={r['evidence'][:60]}")


# ---------------------------------------------------------- checks C4/C5/C6/C7

def test_soft404():
    """El soft-404 es el fallo agéntico silencioso; 404 con salida es correcto."""
    ctx = ctx_base()
    ctx["error_probe"] = {"status": 200, "looks_missing": True, "has_recovery": True}
    t("soft404_detectado", by_id(checks.run_c4(ctx), "4.8")["score"] == 0, "200 no penalizado")
    ctx["error_probe"] = {"status": 404, "looks_missing": True, "has_recovery": True}
    t("404_correcto", by_id(checks.run_c4(ctx), "4.8")["score"] == 1, "404 con salida no premia")


def test_zonas_clic_inline():
    """Bug: los enlaces en línea (exentos en WCAG 2.2) contaban como fallo y
    argal pasaba de 1 a 0 por puro ruido."""
    inline = [{"tag": "a", "w": 200, "h": 19, "cursor": "pointer",
               "inline": True, "native": True, "name": f"enlace{i}"} for i in range(10)]
    controles = [{"tag": "button", "w": 120, "h": 40, "cursor": "pointer",
                  "inline": False, "native": True, "name": f"btn{i}"} for i in range(5)]
    ctx = ctx_base()
    ctx["rendered_home"] = {"ok": True, "html": "<html></html>", "boxes": inline + controles}
    r = by_id(checks.run_c4(ctx), "4.7")
    t("clic_inline_excluidos", r["score"] == 1 and "10 enlaces en linea excluidos" in r["evidence"],
      f"score={r['score']} ev={r['evidence'][:80]}")


def test_llms_calidad():
    """Bug: 941 KB autogenerados (elpozo) puntuaban igual que 30 KB curados
    (hubspot), invirtiendo el ranking real."""
    ctx = ctx_base()
    ctx["wellknown"] = {"/llms.txt": 200}
    ctx["wellknown_meta"] = {"/llms.txt": {"bytes": 941_000, "lineas": 9000,
                                           "enlaces": 3000, "autogenerado": True}}
    t("llms_volcado", by_id(checks.run_c5(ctx), "5.5")["score"] == 0.5, "volcado no penalizado")
    ctx["wellknown_meta"] = {"/llms.txt": {"bytes": 30_000, "lineas": 400,
                                           "enlaces": 200, "autogenerado": False}}
    t("llms_curado", by_id(checks.run_c5(ctx), "5.5")["score"] == 1, "curado penalizado")


def test_auth_agentica():
    """6.4: OAuth > formulario marcado > CAPTCHA; sin login = N/A, no fallo."""
    ctx = ctx_base()
    t("auth_na", by_id(checks.run_c6(ctx), "6.4")["score"] is None, "sin login no es N/A")
    ctx["wellknown"] = {"/.well-known/oauth-authorization-server": 200}
    t("auth_oauth", by_id(checks.run_c6(ctx), "6.4")["score"] == 1, "OAuth no puntua 1")
    ctx["wellknown"] = {}
    ctx["login_probe"] = {"found": True, "url": "https://test.example/login", "status": 200,
                          "body": '<input type="password"> recaptcha'}
    t("auth_captcha", by_id(checks.run_c6(ctx), "6.4")["score"] == 0, "CAPTCHA no puntua 0")


def test_politicas_comercio():
    """7.5/7.6 distinguen 'existe para humano pero no en schema' de 'no existe'."""
    ctx = ctx_base()
    ctx["typology"] = "ecommerce"
    ctx["pages"] = [{"url": "https://test.example/products/a", "bucket": "producto",
                     "fetch": {"status": 200, "ttfb": 0.2, "headers": "", "body":
                               "<html><body>Ficha. Envio gratis en 24h. "
                               "Devolucion en 30 dias.</body></html>"}}]
    res = checks.run_c7(ctx)
    r75, r76 = by_id(res, "7.5"), by_id(res, "7.6")
    t("envio_humano_no_schema", r75["score"] == 0 and "existe para un humano" in r75["evidence"],
      f"s={r75['score']} ev={r75['evidence'][:60]}")
    t("devol_humano_no_schema", r76["score"] == 0 and "existe para un humano" in r76["evidence"],
      f"s={r76['score']} ev={r76['evidence'][:60]}")


# ---------------------------------------------------------- idiomas no cubiertos

def test_buckets_multiidioma():
    """Bug (batería 5, zalando.de): los patrones de bucket eran solo ES/EN.

    zalando.de terminó el muestreo con buckets producto=0 de 36 URLs internas
    y el informe puntuó 3.3/4.2/C7 a 0 "por ausencia" sobre fichas que nunca
    abrimos. Un /produkte/, /produits/ o /prodotti/ debe ser tan reconocible
    como un /productos/.
    """
    casos = {"/produkte/hemd": "producto", "/produits/chemise": "producto",
             "/prodotti/camicia": "producto", "/produtos/camisa": "producto",
             "/kategorien/herren": "categoria", "/boutique/femme": "categoria",
             "/negozio/uomo": "categoria",
             "/ratgeber/mode-tipps": "blog", "/actualites/mode": "blog",
             "/notizie/moda": "blog",
             "/impressum": "legal", "/datenschutz": "legal",
             "/mentions-legales": "legal", "/note-legali": "legal"}
    for path, want in casos.items():
        got = next((n for n, p in discovery.BUCKET_PATTERNS if p.search(path)), None)
        t("bucket_i18n_" + path, got == want, f"{path} -> {got}, esperado {want}")
    # y NO debe robar URLs editoriales al bucket blog: "artikel"/"article" son
    # homógrafos de "artículo de blog" y por eso quedaron fuera de producto
    for path in ("/artikel/moda-2026", "/article/tendances"):
        got = next((n for n, p in discovery.BUCKET_PATTERNS if p.search(path)), None)
        t("bucket_i18n_no_roba_" + path, got != "producto",
          f"{path} clasificado como producto (robaría al blog)")


def test_tipologia_tienda_extranjera():
    """Bug (batería 5): una tienda DE/FR/IT sin vocabulario ES/EN caía a
    'corporativo', y con ella TODA la categoría C7 a 'N/A (no es e-commerce)'.

    zalando.de solo se salvó por casualidad: su HTML contiene la cadena "/cart".
    Sin ese accidente habría sido corporativo.
    """
    casos = {
        "de": '<html lang="de"><button>In den Warenkorb</button>'
              '<a href="/warenkorb">Warenkorb</a><span>19,99 €</span></html>',
        "fr": '<html lang="fr"><button>Ajouter au panier</button>'
              '<a href="/panier">Panier</a><span>19,99 €</span></html>',
        "it": '<html lang="it"><button>Aggiungi al carrello</button>'
              '<a href="/carrello">Carrello</a><span>19,99 €</span></html>',
    }
    for idioma, html in casos.items():
        tip, ev = discovery.detect_typology(html, [])
        t("tipologia_shop_" + idioma, tip == "ecommerce",
          f"{idioma} -> {tip} (ecom={ev['ecommerce']['puntos']} pts "
          f"{ev['ecommerce']['fuertes']})")
    # el precio en libras también es precio: johnlewis.com y cualquier tienda UK
    # perdían la señal porque el patrón solo aceptaba el símbolo DETRÁS y en €
    for muestra in ("£19.99", "19.99 GBP", "$24.50", "CHF 12,00"):
        t("precio_i18n_" + muestra,
          bool(re.search(discovery.ECOM_WEAK["price_tag"], muestra, re.I)),
          f"{muestra} no reconocido como precio")


def test_politicas_comercio_multiidioma():
    """Bug (batería 5, zalando.de): a una tienda alemana le dijimos "Sin
    informacion de envio detectable, ni estructurada ni visible. Un agente que
    compare opciones descartara esta tienda por falta de datos".

    Es la acusación más dura del informe y describía nuestros patrones ES/EN,
    no su web. Con texto alemán/francés/italiano visible, el veredicto correcto
    es "existe para un humano pero no está en schema" (0 con explicación justa),
    nunca "no existe".
    """
    textos = {
        "de": "Versandkosten und Lieferzeit. Rückgabe innerhalb von 30 Tagen.",
        "fr": "Frais de livraison et délai de livraison. Retours sous 30 jours.",
        "it": "Spese di spedizione e tempi di consegna. Resi entro 30 giorni.",
    }
    for idioma, texto in textos.items():
        ctx = ctx_base()
        ctx["typology"] = "ecommerce"
        ctx["pages"] = [{"url": "https://test.example/produkte/a", "bucket": "producto",
                         "fetch": {"status": 200, "ttfb": 0.2, "headers": "",
                                   "body": f"<html><body>{texto}</body></html>"}}]
        res = checks.run_c7(ctx)
        for cid in ("7.5", "7.6"):
            r = by_id(res, cid)
            t(f"politica_{cid}_{idioma}", "existe para un humano" in r["evidence"],
              f"{idioma} {cid}: {r['evidence'][:90]}")


def test_guardarrailes_agente_multiidioma():
    """Bug (batería 5): FORBIDDEN_CLICK y CARD_FIELD son la defensa EN CÓDIGO
    contra comprar de verdad o teclear una tarjeta, y estaban solo en ES/EN.

    En una tienda alemana el botón legalmente obligatorio de compra se llama
    "Kostenpflichtig bestellen" y el campo de tarjeta "Kartennummer": ninguno
    de los dos matcheaba, así que la defensa no existía. Es el único bug de
    esta batería que podía causar daño real (un pedido de verdad), no solo un
    informe injusto.
    """
    from .agents import CARD_FIELD, FORBIDDEN_CLICK, SUBMIT_HINT
    compra = ["Kostenpflichtig bestellen", "Jetzt kaufen", "Konto erstellen",
              "Payer maintenant", "Valider la commande", "Créer un compte",
              "Acquista ora", "Conferma ordine", "Registrati",
              "Comprar agora", "Nu betalen"]
    for label in compra:
        t("forbidden_i18n_" + label, bool(FORBIDDEN_CLICK.search(label)),
          f"{label!r} NO bloqueado: el agente podría pulsarlo")
    tarjeta = ["Kartennummer", "Karteninhaber", "Prüfziffer",
               "Numéro de carte", "Titulaire", "Cryptogramme",
               "Numero della carta", "Scadenza", "Número do cartão", "Kaartnummer"]
    for label in tarjeta:
        t("card_i18n_" + label, bool(CARD_FIELD.search(label)),
          f"{label!r} NO reconocido como campo de tarjeta: el agente escribiría en él")
    for label in ("Absenden", "Envoyer", "Invia", "Verzenden"):
        t("submit_i18n_" + label, bool(SUBMIT_HINT.search(label)),
          f"{label!r} no reconocido como botón de envío")
    # y lo que NO debe bloquearse: navegar por el catálogo sigue permitido
    for label in ("Herren", "Zum Produkt", "Voir le produit", "Vedi prodotto"):
        t("forbidden_i18n_no_falso_positivo_" + label,
          not FORBIDDEN_CLICK.search(label),
          f"{label!r} bloqueado por error: el agente no podría ni navegar")


def test_hitos_ecommerce_multiidioma():
    """Bug (batería 5): los hitos de e-commerce eran ES/EN, así que un agente
    que SÍ añadía al carrito en una tienda alemana quedaba registrado como
    "no lo consiguió" — acusar a la web de un atasco que estaba en nosotros."""
    from .agents import MILESTONES, _check_milestones
    hitos = MILESTONES["ecommerce"]
    casos = [
        ("de", "https://x.de/produkte/hemd", "<html>In den Warenkorb</html>",
         "click 3: In den Warenkorb"),
        ("fr", "https://x.fr/produits/chemise", "<html>Ajouter au panier</html>",
         "click 3: Ajouter au panier"),
        ("it", "https://x.it/prodotti/camicia", "<html>Aggiungi al carrello</html>",
         "click 3: Aggiungi al carrello"),
    ]
    for idioma, url, html, accion in casos:
        reached = {}
        _check_milestones(hitos, reached, url, html, accion)
        t("hito_ficha_" + idioma, "ficha_producto" in reached,
          f"{idioma}: ficha no detectada ({sorted(reached)})")
        t("hito_carrito_" + idioma, "anadir_carrito" in reached,
          f"{idioma}: añadir al carrito no detectado ({sorted(reached)})")


def test_vtex_no_matchea_camelcase():
    """Bug (batería 5, bahn.de): "vtex" estaba en ECOM_STRONG como PALABRA
    SUELTA, y la subcadena aparece dentro de identificadores camelCase de lo
    más corrientes: genericSrOnlyPrev·Text·, Prev·Text·, nav·Text·.

    Deutsche Bahn —un operador ferroviario— salía clasificada como e-commerce
    por una clave de i18n de su JavaScript, y a continuación el informe le
    decía "Un agente que compare opciones descartara esta tienda por falta de
    datos" de envío y devoluciones. El propio módulo ya avisaba de esta clase
    de error ("marcadores a nivel de ASSET, nunca la palabra suelta"): VTEX
    fue el que se coló.
    """
    pat = discovery.ECOM_STRONG["ecom_platform"]
    for ident in ("genericSrOnlyPrevText", "PrevText", "navTextLabel",
                  "srOnlyPrevTextButton"):
        t("vtex_no_camelcase_" + ident, not re.search(pat, ident, re.I),
          f"{ident!r} detectado como plataforma de e-commerce")
    # pero un VTEX de verdad sí debe detectarse (por marcador de asset)
    for real in ("https://foo.vtexassets.com/arquivos/x.js",
                 "vtexcommercestable.com.br", "/_v/public/assets/v1"):
        t("vtex_real_" + real[:24], bool(re.search(pat, real, re.I)),
          f"{real!r} es VTEX real y no se detecta")
    # comprobación de fondo: el HTML real de bahn.de no es una tienda
    html_bahn = ('<html lang="de"><script>{"srOnly":{"genericSrOnlyPrevText":'
                 '"Weitere Informationen"}}</script><span>ab 17,90 €</span></html>')
    tip, ev = discovery.detect_typology(html_bahn, [])
    t("bahn_no_es_tienda", tip != "ecommerce",
      f"operador ferroviario clasificado como {tip}: {ev['ecommerce']}")


def test_plataformas_ecom_coherentes():
    """Bug (batería 5): VTEX estaba en ECOM_STRONG de discovery pero NO en el
    detector de plataforma de 7.1. Una tienda VTEX se clasificaba como
    e-commerce y luego 7.1 respondía "Sin plataforma reconocible"."""
    import os
    ruta = os.path.join(os.path.dirname(__file__), "checks.py")
    with open(ruta) as f:
        cuerpo = f.read()
    for marcador in ("vtexassets", "shopware", "demandware"):
        t("plataforma_71_" + marcador, marcador in cuerpo.lower(),
          f"{marcador} reconocido en discovery pero ausente del detector de 7.1")
    # Squarespace y Wix NO deben estar en ECOM_STRONG: son constructores de
    # webs, no prueba de tienda; incluirlos convertiría cualquier web
    # corporativa hecha con ellos en "ecommerce" y con ella toda la C7.
    for constructor in ("squarespace", "wixstatic"):
        t("plataforma_no_constructor_" + constructor,
          constructor not in discovery.ECOM_STRONG["ecom_platform"].lower(),
          f"{constructor} en ECOM_STRONG: haría e-commerce a webs corporativas")


def test_sin_ficha_producto_no_puntua_cero():
    """Bug (batería 5, zalando.de): una tienda cuyo catálogo no alcanzamos
    puntuaba 0 en los checks de ficha y el score salía 14.4 con
    score_fiable=True, listo para entregarse.

    El informe afirmaba "Sin JSON-LD Product en fichas de producto muestreadas"
    y "Ninguna ficha de producto accesible" sobre páginas que NUNCA abrimos.
    Ampliar los patrones reduce el caso pero no lo elimina: la regla de
    fidelidad no puede depender de acertar el idioma.
    """
    def resultados():
        return [{"id": cid, "cat": "C7", "name": "x", "score": 0,
                 "evidence": "Sin ficha", "manual": False}
                for cid in ("3.3", "4.2", "7.1", "7.2", "7.5", "7.6")] + \
               [{"id": "7.3", "cat": "C7", "name": "x", "score": 0,
                 "evidence": "Sin PSP", "manual": False},
                {"id": "3.1", "cat": "C3", "name": "x", "score": 0,
                 "evidence": "Sin JSON-LD", "manual": False}]
    # tienda SIN ficha alcanzada: los checks de ficha no se afirman
    ctx = ctx_base()
    ctx["typology"] = "ecommerce"
    ctx["sin_ficha_producto"] = True
    res = engine._degradar_sin_ficha_producto(resultados(), ctx)
    d = {r["id"]: r["score"] for r in res}
    for cid in ("3.3", "4.2", "7.1", "7.2", "7.5", "7.6"):
        t("sin_ficha_degrada_" + cid, d[cid] is None,
          f"{cid} sigue puntuando {d[cid]} sobre una ficha que no vimos")
    # 7.3 mira el PSP en la home y 3.1 el marcado general: NO dependen de ficha
    t("sin_ficha_conserva_73", d["7.3"] == 0, f"7.3={d['7.3']}")
    t("sin_ficha_conserva_31", d["3.1"] == 0, f"3.1={d['3.1']}")
    t("sin_ficha_avisa", bool(ctx.get("cobertura_producto_degradada")),
      "no se registró la degradación de cobertura")
    t("sin_ficha_trail", any("cobertura de catálogo" in x.get("step", "")
                             for x in ctx["trail"]), "sin rastro en el trail")
    t("sin_ficha_evidencia_honesta",
      all("NO VERIFICABLE" in r["evidence"]
          for r in res if r["id"] in ("7.5", "7.6")),
      "la evidencia sigue afirmando una ausencia no comprobada")
    # tienda CON ficha alcanzada: nada se toca
    ctx = ctx_base()
    ctx["typology"] = "ecommerce"
    ctx["sin_ficha_producto"] = False
    res = engine._degradar_sin_ficha_producto(resultados(), ctx)
    t("con_ficha_no_degrada", all(r["score"] == 0 for r in res),
      "se degradaron checks de una tienda cuya ficha SÍ vimos")


# ---------------------------------------------------------- guardarraíl y agentes

def test_degradacion_niveles():
    """Bugs: se afirmaban ausencias sin haber visto el sitio (BBVA) y se
    sobre-degradaba cuando solo fallaron sondas posteriores (elpais)."""
    def resultados():
        return [
            {"id": "3.1", "cat": "C3", "name": "x", "score": 0, "evidence": "e", "manual": False},
            {"id": "5.5", "cat": "C5", "name": "x", "score": 0, "evidence": "e", "manual": False},
            {"id": "2.3", "cat": "C2", "name": "x", "score": 0, "evidence": "e", "manual": False},
            {"id": "1.6", "cat": "C1", "name": "x", "score": 0, "evidence": "e", "manual": False},
            {"id": "2.4", "cat": "C2", "name": "x", "score": 0, "evidence": "e", "manual": False},
        ]
    # nivel TOTAL: bloqueo completo → cae todo lo de ausencia, pero 1.6/2.4
    # (hostilidad al acceso) siguen puntuando: ese bloqueo ES el hallazgo
    ctx = ctx_base()
    ctx["bot_matrix"]["_human"] = 403
    ctx["home"]["body"] = "x"
    res = engine._degradar_si_bloqueado(resultados(), ctx)
    d = {r["id"]: r["score"] for r in res}
    t("degrada_total", d["3.1"] is None and d["5.5"] is None and d["2.3"] is None,
      f"{d}")
    t("degrada_conserva_hostilidad", d["1.6"] == 0 and d["2.4"] == 0, f"{d}")
    t("degrada_total_nivel", ctx["acceso_degradado"]["nivel"] == "total",
      str(ctx["acceso_degradado"]))
    # nivel SONDAS: la portada se vio; solo caen las ausencias de sonda
    ctx = ctx_base()
    ctx["bot_matrix"]["_human"] = 403          # sondas bloqueadas...
    res = engine._degradar_si_bloqueado(resultados(), ctx)  # ...pero home ok via http
    d = {r["id"]: r["score"] for r in res}
    t("degrada_sondas_conserva_marcado", d["3.1"] == 0, f"{d}")
    t("degrada_sondas_degrada_sonda", d["5.5"] is None, f"{d}")
    t("degrada_sondas_nivel", ctx["acceso_degradado"]["nivel"] == "sondas",
      str(ctx["acceso_degradado"]))
    # acceso limpio: nada degradado
    ctx = ctx_base()
    res = engine._degradar_si_bloqueado(resultados(), ctx)
    t("degrada_limpio", ctx["acceso_degradado"] is None, str(ctx["acceso_degradado"]))


def test_cascara_no_es_web_vacia():
    """Bug (batería 5, zalando.de en la segunda pasada): HTTP 200, 11 KB de
    portada, robots.txt correcto, _human=200… y CERO enlaces internos, CERO
    páginas muestreadas, CERO señales de tipología.

    El motor YA avisaba en el trail ("SIN señales: la web devuelve poco/ningún
    contenido a accesos automatizados") y aun así entregaba score 20.3 con
    score_fiable=True, con todos los checks de contenido a 0 "por ausencia"
    sin haber visto una sola página. _degradar_si_bloqueado no lo cazaba
    porque solo mira que la portada pese >=500 bytes y que el humano reciba
    200 — y una cáscara anti-bot cumple las dos cosas. La señal buena no es el
    peso: es que no hay NADA que rastrear.
    """
    def resultados():
        return [
            {"id": "3.1", "cat": "C3", "name": "x", "score": 0, "evidence": "e", "manual": False},
            {"id": "5.1", "cat": "C5", "name": "x", "score": 0, "evidence": "e", "manual": False},
            {"id": "1.6", "cat": "C1", "name": "x", "score": 0, "evidence": "e", "manual": False},
        ]
    # cáscara: 200, bytes de sobra, pero sin enlaces, sin páginas y sin señales
    ctx = ctx_base()
    ctx["home"]["body"] = "<html><body>" + "x" * 11000 + "</body></html>"
    ctx["cobertura_ciega"] = True
    ctx["pages"] = []
    ctx["typology_evidence"] = {"ecommerce": {"puntos": 0}, "saas": {"puntos": 0}}
    t("cascara_detectada", engine._cobertura_ciega(ctx), "la cáscara no se detecta")
    res = engine._degradar_si_bloqueado(resultados(), ctx)
    d = {r["id"]: r["score"] for r in res}
    t("cascara_degrada_contenido", d["3.1"] is None and d["5.1"] is None,
      f"se siguen afirmando ausencias sin haber visto la web: {d}")
    t("cascara_conserva_hostilidad", d["1.6"] == 0,
      "1.6 mide justo esa hostilidad: debe seguir puntuando")
    t("cascara_nivel_total", ctx["acceso_degradado"]["nivel"] == "total",
      str(ctx["acceso_degradado"]))
    t("cascara_score_no_fiable",
      ctx["acceso_degradado"]["nivel"] in ("total", "marcado"),
      "el score seguiría marcándose como entregable")
    # web pequeña pero REAL: pocas páginas, pero con enlaces y señales -> no toca
    ctx = ctx_base()
    ctx["cobertura_ciega"] = False
    ctx["typology_evidence"] = {"ecommerce": {"puntos": 0}, "saas": {"puntos": 3}}
    res = engine._degradar_si_bloqueado(resultados(), ctx)
    t("web_pequena_no_degrada", ctx["acceso_degradado"] is None,
      f"web real degradada por error: {ctx['acceso_degradado']}")
    # sin enlaces PERO con señales de tipología: la home sí se vio, no es cáscara
    ctx = ctx_base()
    ctx["cobertura_ciega"] = True
    ctx["pages"] = []
    ctx["typology_evidence"] = {"ecommerce": {"puntos": 4}, "saas": {"puntos": 0}}
    t("cascara_no_falso_positivo", not engine._cobertura_ciega(ctx),
      "una home con señales claras se trató como cáscara")


def test_consistencia_agentes():
    """Los agentes LLM son estocásticos: 'funcionó una vez' no es evidencia."""
    run_ok = {"outcome": "conseguido", "steps": 5, "detail": "ok", "action_log": [],
              "progreso": {"alcanzados": 4, "total": 4, "pendientes": []}}
    run_ko = {"outcome": "no_conseguido", "steps": 7, "detail": "x", "action_log": [],
              "progreso": {"alcanzados": 2, "total": 4, "pendientes": ["Abrir el carrito"]}}
    a = _aggregate([run_ok, run_ko, run_ok])
    t("agentes_inconsistente", a["outcome"] == "inconsistente" and a["consistencia"] == 0.67,
      f"{a['outcome']} {a.get('consistencia')}")
    a = _aggregate([run_ok, run_ok, run_ok])
    t("agentes_consistente", a["outcome"] == "conseguido" and a["consistencia"] == 1.0,
      f"{a['outcome']}")


def test_checkout_nunca_toca_la_tarjeta():
    """El agente rellena contacto y envío en el checkout, pero los campos de
    pago son territorio prohibido por código, no por instrucción al modelo."""
    from .agents import CARD_FIELD
    for campo in ("Número de tarjeta", "CVV", "Card number", "Fecha de caducidad",
                  "Titular de la tarjeta", "IBAN"):
        t("card_bloqueado", bool(CARD_FIELD.search(campo)), f"'{campo}' no se bloquea")
    for campo in ("Email", "Nombre", "Dirección", "Código postal", "Teléfono"):
        t("card_permite_envio", not CARD_FIELD.search(campo),
          f"'{campo}' se bloquea y no debería")


def test_datos_prueba_dominio_reservado():
    """El email por defecto usa example.com (RFC 2606): no puede pertenecer a
    nadie, así que ningún tercero recibe correo por accidente."""
    from .agents import datos_prueba, build_task
    d = datos_prueba()
    t("email_reservado", d["email"].endswith("example.com"), d["email"])
    tarea = build_task("ecommerce", False)
    t("checkout_pide_datos", d["email"] in tarea and d["cp"] in tarea,
      "la tarea de e-commerce no incluye los datos de checkout")
    t("checkout_prohibe_pago", "NO introduzcas" in tarea and "tarjeta" in tarea,
      "la tarea no prohíbe explícitamente el pago")


def test_un_solo_envio_real():
    """Bug propio: con 3 agentes x 3 repeticiones se enviaban hasta 9
    formularios. Quien marca la casilla espera uno, no nueve."""
    from . import agents as A
    envios, orig_task, orig_key = [], A._browser_task, A.get_key
    try:
        A._browser_task = lambda url, task, ask, key, allow_submit, typology: (
            envios.append(allow_submit) or
            {"outcome": "conseguido", "steps": 1, "detail": "", "action_log": [],
             "progreso": {"alcanzados": 1, "total": 1, "pendientes": [],
                          "no_evaluados": []}})
        A.get_key = lambda p: "k"
        r = A.run_agent_tests("https://x.com", "corporativo",
                              providers=("chatgpt", "gemini", "claude"),
                              allow_submit=True, repeticiones=3)
        t("envio_unico", sum(1 for e in envios if e) == 1,
          f"{sum(1 for e in envios if e)} envíos de {len(envios)} pasadas")
        t("envio_es_el_primero", envios and envios[0] is True, str(envios[:3]))
        t("envio_declarado", r["envios_reales"] == 1, str(r.get("envios_reales")))
    finally:
        A._browser_task, A.get_key = orig_task, orig_key


def test_guardarrail_sin_recorrido_no_es_exito():
    """Bug: tiendaanimal.es salía 'conseguido_con_friccion' con 0/5 hitos porque
    el agente topó con un botón 'Send' (newsletter) en el primer paso y el
    guardarraíl daba la prueba por buena. Sin recorrido no hay éxito."""
    from .agents import _aggregate
    sin_recorrido = {"outcome": "no_conseguido", "steps": 2, "detail": "", "action_log": [],
                     "progreso": {"alcanzados": 0, "total": 5,
                                  "pendientes": ["Abrir una ficha"], "no_evaluados": []}}
    a = _aggregate([sin_recorrido])
    t("sin_recorrido_no_exito", a["outcome"] == "no_conseguido", a["outcome"])
    con_recorrido = dict(sin_recorrido, outcome="conseguido",
                         progreso={"alcanzados": 4, "total": 5, "pendientes": [],
                                   "no_evaluados": []})
    a = _aggregate([con_recorrido])
    t("con_recorrido_si_exito", a["outcome"] == "conseguido", a["outcome"])


def test_hitos_submit():
    """Bug: 'alcanzar el botón de envío' contaba como atasco de la web cuando
    éramos NOSOTROS quienes prohibíamos enviar."""
    sin = [m["nombre"] for m in hitos_aplicables("corporativo", False)]
    con = [m["nombre"] for m in hitos_aplicables("corporativo", True)]
    t("hitos_sin_submit", len(sin) == 3 and "Alcanzar el botón de envío" not in sin, str(sin))
    t("hitos_con_submit", len(con) == 4, str(con))


# ---------------------------------------------------------- scoring y catálogo

def _audit_ficticia(**extra):
    """Auditoría mínima pero completa, para ejercitar los generadores de informe."""
    checks = [
        {"id": "1.1", "cat": "C1", "name": "robots.txt", "score": 1,
         "evidence": "ok", "manual": False},
        {"id": "3.1", "cat": "C3", "name": "JSON-LD", "score": 0.5,
         "evidence": "parcial", "manual": False,
         "advice": {"titulo": "Falta marcado", "por_que": "Los agentes no te entienden",
                    "como": "Añadir JSON-LD", "impacto": "Alto", "esfuerzo": "Bajo"}},
        {"id": "6.3", "cat": "C6", "name": "Agente real", "score": None,
         "evidence": "no ejecutado", "manual": True},
    ]
    base = {
        "domain": "https://test.example", "host": "test.example",
        "typology": "ecommerce", "score": 42.0, "score_pre_gate": 47.0,
        "penalties": [["Precio inconsistente", -5]],
        "level": {"emoji": "🟠", "name": "Legible, no operable", "msg": "Te leen, no te usan."},
        "category_scores": {"C1": 0.8, "C3": 0.5, "C6": 0.2},
        "category_weights": {"C1": 15.0, "C3": 18.0, "C6": 12.0},
        "checks": checks, "bot_matrix": {"GPTBot": 200, "_human": 200},
        "pages_sampled": [{"url": "https://test.example/a", "bucket": "otras",
                           "status": 200, "via": "http"}],
        "wellknown": {}, "coverage": {"sitemap_urls": 10, "sampled": 1,
                                      "sampled_ok": 1, "fallbacks": 0},
        "trail": [{"step": "robots.txt", "status": "ok", "detail": "200"}],
        "score_fiable": True, "agent_tests": None,
    }
    base.update(extra)
    return base


def test_informes_no_revientan():
    """El PDF y el JSON no tenían NINGUNA prueba: por eso partir build_pdf era
    arriesgado. Se ejercitan sus rutas condicionales (con y sin competidores,
    fiable y degradado, con y sin pruebas agénticas)."""
    from .report_pdf import build_pdf
    from .report_json import build_json
    degradada = _audit_ficticia(
        host="bloqueada.example", score_fiable=False,
        acceso_degradado={"nivel": "total", "motivo": "bloqueo", "degradados": 8,
                          "human_status": 403, "via": "http"})
    con_agentes = _audit_ficticia(agent_tests={
        "typology": "ecommerce", "repeticiones": 3, "hitos_tarea": ["Abrir ficha"],
        "hitos_no_evaluados": [], "allow_submit": False,
        "agents": {"chatgpt": {"outcome": "conseguido", "intentos": 3, "exitos": 3,
                               "consistencia": 1.0, "steps": 5, "detail": "ok",
                               "action_log": ["click [1] 'Comprar'"],
                               "runs": [{"outcome": "conseguido"}],
                               "progreso": {"alcanzados": 4, "total": 4,
                                            "pendientes": [], "hitos": []}}}})
    escenarios = {
        "solo cliente": {"client": _audit_ficticia(), "competitors": []},
        "con competidores": {"client": _audit_ficticia(),
                             "competitors": [_audit_ficticia(host="comp1.example"),
                                             degradada]},
        "cliente degradado": {"client": degradada, "competitors": [_audit_ficticia()]},
        "con agentes": {"client": con_agentes, "competitors": []},
        "competidor con error": {"client": _audit_ficticia(),
                                 "competitors": [{"domain": "x", "error": "no responde"}]},
    }
    for nombre, data in escenarios.items():
        data["generated"] = "2026-07-19"
        try:
            pdf = build_pdf(data).getvalue()
            t("pdf_" + nombre.replace(" ", "_"), len(pdf) > 5000,
              f"PDF sospechosamente pequeño ({len(pdf)} bytes)")
        except Exception as exc:
            t("pdf_" + nombre.replace(" ", "_"), False,
              f"EXCEPCIÓN {type(exc).__name__}: {exc}")
        try:
            j = build_json(data)
            t("json_" + nombre.replace(" ", "_"),
              "cliente" in j and "fiabilidad" in j["cliente"], "JSON incompleto")
        except Exception as exc:
            t("json_" + nombre.replace(" ", "_"), False,
              f"EXCEPCIÓN {type(exc).__name__}: {exc}")


def test_persistencia_degrada_sin_bd():
    """La persistencia MEJORA el producto pero nunca puede ser el motivo de que
    un análisis falle: si Postgres no responde, todo debe devolver un valor
    neutro sin propagar excepciones."""
    from . import storage
    casos = [
        ("ensure_table", lambda: storage.ensure_table(), False),
        ("guardar", lambda: storage.guardar("t", {"client": {}}, "a@b.c"), False),
        ("cargar", lambda: storage.cargar("t"), None),
        ("historial", lambda: storage.historial("a@b.c"), []),
        ("borrar", lambda: storage.borrar("t"), False),
    ]
    for nombre, fn, esperado in casos:
        try:
            got = fn()
            t("persist_" + nombre, got == esperado,
              f"devolvió {got!r}, se esperaba {esperado!r}")
        except Exception as exc:
            t("persist_" + nombre, False,
              f"PROPAGÓ EXCEPCIÓN {type(exc).__name__}: {exc}")


def test_agentes_fallidos_no_dicen_completado():
    """Bug (batería 5): _run_agents_job marcaba estado="completado" pasara lo
    que pasara. Si la simulación reventaba en TODOS los dominios (los fallos se
    capturan por dominio y solo se registran), el panel pintaba igualmente el
    botón verde "✓ Agentes simulados" — afirmar que algo se comprobó sin
    haberlo comprobado.

    Se comprueba sobre el CÓDIGO porque la función es un job de Flask con
    _JOBS y hilos: lo que se blinda es que el estado dependa de los éxitos.
    """
    import os
    ruta = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent_routes.py")
    if not os.path.exists(ruta):
        return  # el paquete puede usarse fuera de la app web
    with open(ruta) as f:
        cuerpo = f.read()
    t("agentes_cuenta_logros", "logrados" in cuerpo,
      "no se cuentan los dominios en los que la simulación SÍ funcionó")
    t("agentes_estado_condicional",
      'if logrados == 0:' in cuerpo and 'data["agentes"]["estado"] = "error"' in cuerpo,
      'estado="completado" incondicional: se afirma una simulación que no ocurrió')
    t("agentes_status_condicional", '"done" if logrados else "error"' in cuerpo,
      "agents_status se marca done aunque no se lograra ningún dominio")


def test_dns_vs_bloqueo_total():
    """Bug (batería 5, fnac.fr): el dominio resuelve perfectamente
    (165.160.13.20) y su WAF descarta nuestras conexiones en silencio, pero le
    decíamos al cliente "no responde (DNS/conexión). Verifica el dominio" —
    mandándole a revisar un DNS que está bien, mientras el hallazgo real era el
    contrario: bloquea el acceso automatizado por completo."""
    import os
    ruta = os.path.join(os.path.dirname(__file__), "engine.py")
    with open(ruta) as f:
        cuerpo = f.read()
    t("dns_distingue_no_resuelve", "no resuelve en DNS" in cuerpo,
      "no se distingue 'no resuelve' de 'resuelve y nos bloquea'")
    t("dns_no_culpa_al_dominio",
      "no responde (DNS/conexión). Verifica el dominio." not in cuerpo,
      "sigue el mensaje que manda a revisar un DNS correcto")
    t("dns_explica_bloqueo", "rechaza o deja sin respuesta" in cuerpo,
      "el bloqueo total no se explica como lo que es")


def test_scoring_y_catalogo():
    for cid in ("4.7", "4.8", "6.4", "7.5", "7.6"):
        t("peso_" + cid, scoring.CHECK_WEIGHTS.get(cid, 0) > 0, f"{cid} sin peso")
    t("peso_74_informativo", scoring.CHECK_WEIGHTS.get("7.4") == 0, "7.4 debe pesar 0")
    # catálogo sincronizado con el motor (mismo validador que el módulo catalog)
    import os
    import re as _re
    from . import catalog
    path = os.path.join(os.path.dirname(__file__), "checks.py")
    with open(path) as f:
        reales = set(_re.findall(r'R\("(\d+\.\d+)"', f.read()))
    mios = set(catalog.check_ids())
    t("catalogo_sincronizado", reales == mios,
      f"faltan={sorted(reales - mios)} sobran={sorted(mios - reales)}")


def test_pagina_de_bloqueo_no_es_portada():
    """Bug (batería 5, mediamarkt.es): el WAF devolvió HTTP 403 a TODAS las
    peticiones —incluido el UA humano— con 13.656 bytes de "Access Denied".

    `_degradar_si_bloqueado` daba la portada por vista porque solo miraba el
    PESO del cuerpo (>=500 bytes), y una página de bloqueo pesa de sobra. Como
    la vía seguía siendo "http", caía en la rama `else` y etiquetaba nivel
    "sondas", cuyo texto afirma "la portada se obtuvo con normalidad" y deja
    score_fiable=True. Lo entregable quedó así: mediamarkt.es = 🔴 "Invisible
    para agentes. Ni te leen ni te usan. Riesgo alto", score 20.8 marcado como
    fiable, calculado sobre la página de error del WAF. Cero páginas
    muestreadas, cero enlaces, cero señales de tipología.

    Es el sesgo de la casa: culpar a la web ajena de nuestra propia ceguera.
    """
    def resultados():
        return [
            {"id": "3.1", "cat": "C3", "name": "x", "score": 0, "evidence": "e", "manual": False},
            {"id": "5.1", "cat": "C5", "name": "x", "score": 0, "evidence": "e", "manual": False},
        ]
    ctx = ctx_base()
    ctx["home"] = {"status": 403, "body": "<html><body>Access Denied" + "x" * 13600 + "</body></html>",
                   "headers": "", "ttfb": 0.06, "_via": "http"}
    ctx["bot_matrix"] = {"GPTBot": 403, "ClaudeBot": 403, "_human": 403}
    ctx["pages"] = []
    ctx["typology_evidence"] = {"ecommerce": {"puntos": 0}, "saas": {"puntos": 0}}
    engine._degradar_si_bloqueado(resultados(), ctx)
    deg = ctx["acceso_degradado"]
    t("bloqueo_no_es_portada_nivel", deg and deg["nivel"] == "total",
      f"una página de bloqueo de 13 KB se tomó por portada válida: {deg}")
    t("bloqueo_no_es_portada_no_fiable",
      deg and deg["nivel"] in ("total", "marcado"),
      "el score se entregaría como fiable habiendo leído solo el error del WAF")
    t("bloqueo_no_es_portada_sin_normalidad",
      deg and "con normalidad" not in deg["motivo"],
      f"el informe afirma que la portada se obtuvo con normalidad: {deg['motivo']}")

    # Contraprueba: 403 al humano pero portada RESCATADA por jina. El cuerpo sí
    # es contenido real, así que no debe tratarse como bloqueo total.
    ctx = ctx_base()
    ctx["home"] = {"status": 403, "body": "texto real " * 200, "headers": "",
                   "ttfb": 0.2, "_via": "jina"}
    ctx["bot_matrix"] = {"GPTBot": 403, "ClaudeBot": 403, "_human": 403}
    engine._degradar_si_bloqueado(resultados(), ctx)
    t("rescate_jina_sigue_siendo_marcado",
      ctx["acceso_degradado"]["nivel"] == "marcado",
      f"el rescate vía jina se degradó de más: {ctx['acceso_degradado']['nivel']}")

    # Contraprueba: web sana (200 por http) no se degrada.
    ctx = ctx_base()
    engine._degradar_si_bloqueado(resultados(), ctx)
    t("web_sana_no_se_degrada", ctx["acceso_degradado"] is None,
      f"web con HTTP 200 degradada por error: {ctx['acceso_degradado']}")


def test_sitemap_no_muestrea_dominios_ajenos():
    """Bug (batería 5, revisando el filtro de host que ejercita blog.hubspot.es):
    `get_sitemap_urls` filtraba con `host in urlparse(u).netloc`, una comparación
    por SUBCADENA. Para host='ikea.com' aceptaba 'notikea.com', 'ikea.com.mx' y
    'ikea.com.evil.net'. Esas páginas se muestreaban y se puntuaban dentro del
    informe del cliente: afirmar sobre su web cosas medidas en la web de otro.

    `harvest_links` ya comparaba por igualdad exacta, así que las dos vías de
    descubrimiento no coincidían entre sí.
    """
    base = "https://www.ikea.com"
    t("sitemap_acepta_host_propio", discovery.mismo_sitio(base, "https://www.ikea.com/es/es/p/x/"),
      "se rechaza una URL del propio sitio")
    t("sitemap_acepta_subdominio_propio", discovery.mismo_sitio(base, "https://shop.ikea.com/x"),
      "se rechaza un subdominio propio")
    t("sitemap_rechaza_dominio_que_contiene_host",
      not discovery.mismo_sitio(base, "https://notikea.com/fake/"),
      "'notikea.com' se cuela como si fuera del cliente")
    t("sitemap_rechaza_otro_ccTLD",
      not discovery.mismo_sitio(base, "https://www.ikea.com.mx/otro/"),
      "'ikea.com.mx' es otra entidad y se cuela como del cliente")
    t("sitemap_rechaza_sufijo_malicioso",
      not discovery.mismo_sitio(base, "https://ikea.com.evil.net/x"),
      "'ikea.com.evil.net' se cuela como del cliente")
    # subdominio como base (blog.hubspot.es): no debe arrastrar el dominio padre
    t("subdominio_base_no_arrastra_padre",
      not discovery.mismo_sitio("https://blog.hubspot.es", "https://www.hubspot.es/x"),
      "auditando el subdominio se muestrea el dominio padre")
    t("subdominio_base_acepta_lo_suyo",
      discovery.mismo_sitio("https://blog.hubspot.es", "https://blog.hubspot.es/marketing"),
      "se rechaza una URL del propio subdominio")
    # 'www.' es un prefijo, no una subcadena a borrar donde sea
    t("www_solo_como_prefijo",
      discovery._host_base("shop.wwwidgets.com") == "shop.wwwidgets.com",
      "replace('www.','') corrompe hosts que contienen 'www.' en medio")


def test_dominio_pelado_no_es_fallo_de_dns():
    """Bug (batería 5, montando la regresión de tipologías): a gather_context se
    le pasa el dominio pelado ('cloudflare.com') y no normalizaba, así que
    urlparse dejaba netloc vacío, assert_public_url fallaba con "esquema no
    permitido" y el motor lo traducía a "cloudflare.com no resuelve en DNS.
    Verifica el dominio". Es decir: mandábamos al cliente a revisar un DNS
    impecable por un fallo de formato NUESTRO. Falló en los 15 dominios de la
    regresión, incluidos cloudflare.com y stripe.com.

    Se comprueba sin red: normalize es idempotente y assert_public_url acepta
    lo que produce.
    """
    from .httpfetch import assert_public_url, BlockedURLError
    for pelado in ("cloudflare.com", "www.bbva.es", "https://stripe.com"):
        norm = discovery.normalize(pelado)
        t(f"normaliza_{pelado}", norm.startswith("http"),
          f"'{pelado}' no adquiere esquema: {norm}")
        t(f"idempotente_{pelado}", discovery.normalize(norm) == norm,
          "normalize no es idempotente: gather_context la aplicaría dos veces")
        try:
            assert_public_url(norm)
            ok = True
        except BlockedURLError as exc:
            ok = f"BlockedURLError: {exc}"
        t(f"url_normalizada_valida_{pelado}", ok is True,
          f"la URL normalizada se rechaza y acabaría como 'no resuelve en DNS': {ok}")
    # El mensaje ya no puede afirmar DNS sin haberlo comprobado.
    # Se mira el cuerpo de gather_context en concreto: audit_domain YA
    # normalizaba, así que buscar la llamada en todo el módulo no distingue.
    import inspect
    cuerpo = inspect.getsource(engine.gather_context)
    src = open(os.path.join(os.path.dirname(__file__), "engine.py")).read()
    t("gather_context_normaliza", "discovery.normalize(base)" in cuerpo,
      "gather_context vuelve a confiar en que le den la base ya normalizada")
    t("sin_mensaje_dns_generico", 'no resuelve en DNS. Verifica el dominio.' not in src,
      "se sigue atribuyendo a DNS cualquier BlockedURLError (esquema, IP privada)")


def test_sitemap_homogeneo_no_deja_muestra_de_dos():
    """Bug (batería 5, ikea.com): sitemap de 800 URLs, las 800 de producto y el
    resto de buckets a cero. Se tomaban 2 de producto, ningún otro bucket
    aportaba y el respaldo de relleno solo miraba "otras", que estaba vacía.
    Resultado: 2 páginas de 800 sosteniendo TODOS los checks de contenido, con
    score 49,8 y score_fiable=True — se generaliza a un catálogo entero desde
    dos fichas sin avisar de que la muestra es esa.
    """
    urls = [f"https://www.ikea.com/es/es/p/articulo-{i}/" for i in range(800)]
    buckets, sample = discovery.classify_and_sample(urls)
    t("sitemap_homogeneo_bucket_unico", len(buckets["producto"]) == 800,
      "el escenario ya no reproduce el caso de ikea.com")
    t("sitemap_homogeneo_muestra_suficiente", len(sample) >= 5,
      f"solo {len(sample)} páginas muestreadas de 800 disponibles")
    # el caso que ya cubría el respaldo original (wikipedia: todo en "otras")
    # debe seguir funcionando igual
    urls2 = [f"https://es.wikipedia.org/wiki/Tema_{i}" for i in range(50)]
    _, sample2 = discovery.classify_and_sample(urls2)
    t("relleno_otras_sigue_funcionando", len(sample2) >= 5,
      f"se rompió el relleno desde 'otras': {len(sample2)} páginas")
    # sitio realmente pequeño: no se inventan páginas que no existen
    _, sample3 = discovery.classify_and_sample(["https://x.example/a"])
    t("sitio_pequeno_no_infla_muestra", len(sample3) == 1,
      f"se muestrean {len(sample3)} páginas de 1 URL disponible")


def test_render_espera_domcontentloaded():
    """Medición (batería 5, 6 dominios × 3 variantes): con wait_until=networkidle,
    mediamarkt.es y gymshark.com agotaban los 90 s y devolvían CERO bytes —sus
    sockets de analítica nunca dejan la red en reposo—, así que gymshark salió
    con render_ok=False y mediamarkt con el check 4.1 degradado a heurístico.
    Con domcontentloaded + 3 s: 942 KB y 2,9 MB en ~4 s.

    En los dominios donde networkidle SÍ terminaba (veepee.es, ikea.com) el HTML
    resultó idéntico: mismo texto, mismos <a href>, mismos bloques JSON-LD. El
    check 4.1 compara HTML crudo contra renderizado, así que este test fija que
    no volvemos a una espera que se salda sin render.
    """
    src = open(os.path.join(os.path.dirname(__file__), "render.py")).read()
    t("render_no_usa_networkidle", 'wait_until="networkidle"' not in src,
      "networkidle deja sin render a los sitios con analítica persistente")
    t("render_usa_domcontentloaded", 'wait_until="domcontentloaded"' in src,
      "falta la espera medida como equivalente en contenido")
    t("render_espera_tras_domcontentloaded", "wait_for_timeout" in src,
      "sin margen tras domcontentloaded, el 4.1 compararía contra HTML sin pintar")


def test_bloqueo_no_regala_presencias():
    """Bug (batería 6, bol.com y allegro.pl): un sitio que nos bloquea del todo
    puntuaba MÁS ALTO que uno legible.

    Ambos devuelven HTTP 403 a todo, incluido el UA humano. El guardarraíl solo
    degradaba los checks con `score == 0` ("la ausencia no es afirmable"), así
    que el 3.6 —que leyó la página de "Access Denied" del WAF, no vio elementos
    fantasma en ella y se anotó un 1— sobrevivía intacto. Como era el único
    check de C3 que quedaba, C3 salía 1.0 con el peso mayor del modelo (25):
    allegro.pl = 64.5 y nivel "Agent-aware", la mejor nota de los 22 dominios de
    la batería, sobre una web que no llegamos a ver. Una PRESENCIA medida sobre
    la página de bloqueo es tan inafirmable como una ausencia.
    """
    def resultados():
        return [
            # medidos sobre el cuerpo del WAF: ni el 1 ni el 0 son afirmables
            {"id": "3.6", "cat": "C3", "name": "x", "score": 1, "evidence": "e", "manual": False},
            {"id": "6.2", "cat": "C6", "name": "x", "score": 0.5, "evidence": "e", "manual": False},
            {"id": "3.1", "cat": "C3", "name": "x", "score": 0, "evidence": "e", "manual": False},
            # evidencia INDEPENDIENTE de la portada: la sonda del sitemap sí
            # respondió, así que su 1 es real y debe conservarse
            {"id": "1.4", "cat": "C1", "name": "x", "score": 1, "evidence": "e", "manual": False},
        ]
    ctx = ctx_base()
    ctx["bot_matrix"]["_human"] = 403
    ctx["home"]["status"] = 403
    ctx["home"]["body"] = "<html><body>Access Denied</body></html>" + "x" * 600
    res = engine._degradar_si_bloqueado(resultados(), ctx)
    d = {r["id"]: r["score"] for r in res}
    t("bloqueo_nivel_total", ctx["acceso_degradado"]["nivel"] == "total",
      str(ctx.get("acceso_degradado")))
    t("bloqueo_degrada_presencia_de_marcado", d["3.6"] is None,
      f"3.6=1 medido sobre la página de bloqueo del WAF debe ser NO VERIFICABLE: {d}")
    t("bloqueo_degrada_presencia_parcial", d["6.2"] is None,
      f"6.2=0.5 sobre el cuerpo del WAF debe ser NO VERIFICABLE: {d}")
    t("bloqueo_degrada_ausencia", d["3.1"] is None, f"{d}")
    t("bloqueo_conserva_evidencia_independiente", d["1.4"] == 1,
      f"1.4 sale del sitemap, que sí respondió: degradarlo sería sobre-corregir: {d}")

    # nivel SONDAS (la portada SÍ se vio): un >0 procede de una sonda que
    # respondió, así que se respeta. Este es el lado que no debe cambiar.
    ctx = ctx_base()
    ctx["bot_matrix"]["_human"] = 403           # sondas bloqueadas, home ok
    res = engine._degradar_si_bloqueado(resultados(), ctx)
    d = {r["id"]: r["score"] for r in res}
    t("sondas_no_toca_marcado_visto", d["3.6"] == 1 and d["6.2"] == 0.5,
      f"con portada vista el marcado es evidencia buena: {d}")


def test_sin_senales_no_culpa_al_acceso():
    """Bug (batería 6): a dnb.no le leímos 1,17 MB de portada por HTTP 200 y el
    informe decía "la web devuelve poco/ningún contenido a accesos automatizados".

    Mismo caso en rijksoverheid.nl (318 KB), vg.no (431 KB), uu.nl y
    greenpeace.nl: todos servidos con normalidad, todos sin señales de tienda ni
    de SaaS, porque un banco, un ministerio, un periódico, una universidad y una
    ONG no son ninguna de las dos cosas. "Cero señales" tenía una única lectura
    ("nos bloquean") y se afirmaba aunque la portada se hubiera leído entera:
    culpar a la web ajena de una ausencia que es correcta.
    """
    def trail_de(home_body, status):
        ctx = {"home": {"body": home_body, "status": status, "_via": "http"},
               "typology_evidence": {"ecommerce": {"puntos": 0, "fuertes": []},
                                     "saas": {"puntos": 0, "fuertes": []}},
               "typology": "corporativo", "trail": []}
        engine._trail_tipologia(ctx, None)
        return ctx["trail"][-1]

    visto = trail_de("<html>" + "contenido " * 2000 + "</html>", 200)
    t("sin_senales_portada_vista_no_es_warn", visto["status"] == "ok",
      f"portada de 20 KB leída con 200: no es un aviso de acceso: {visto}")
    t("sin_senales_portada_vista_no_acusa",
      "poco/ningún contenido" not in visto["detail"],
      f"afirmar que no sirve contenido una web que sí lo sirvió: {visto['detail']}")
    t("sin_senales_portada_vista_explica",
      "corporativo" in visto["detail"], visto["detail"])

    # y cuando de verdad estamos ciegos, el aviso se mantiene
    ciego = trail_de("x", 403)
    t("sin_senales_bloqueado_sigue_avisando",
      ciego["status"] == "warn" and "poco/ningún contenido" in ciego["detail"],
      f"con la portada bloqueada el aviso debe seguir: {ciego}")


def test_senales_tienda_pl_y_nordicas():
    """Bug (batería 6): ninguna señal de e-commerce cubría polaco ni nórdicos.

    empik.com (gran retailer polaco) sirve "dodaj do koszyka", "koszyk" 11 veces
    y 8 precios en zł: las tres regex fallaban y solo se salvó de ser
    "corporativo" porque su HTML lleva un "/cart" inglés suelto. komputronik.pl,
    igual, con 17 precios en zł. Una tienda PL/nórdica sin esa casualidad caía a
    corporativo y arrastraba toda la categoría C7 a "N/A (no es e-commerce)".
    Cadenas tomadas del HTML real de esos dominios.
    """
    add = re.compile(discovery.ECOM_STRONG["add_to_cart"], re.I)
    for frase in ["dodaj do koszyka", "Legg i handlekurv", "Lägg i varukorgen",
                  "Læg i kurven", "Lisää ostoskoriin"]:
        t(f"add_to_cart_{frase[:12]}", bool(add.search(frase)), frase)

    url = re.compile(discovery.ECOM_STRONG["cart_url"], re.I)
    for u in ['href="/koszyk/"', 'href="/handlekurv"', 'href="/varukorg"',
              'href="/ostoskori/"']:
        t(f"cart_url_{u[8:18]}", bool(url.search(u)), u)

    word = re.compile(discovery.ECOM_WEAK["cart_word"], re.I)
    t("cart_word_koszyk", bool(word.search("Twój koszyk jest pusty")), "koszyk")

    price = re.compile(discovery.ECOM_WEAK["price_tag"], re.I)
    for p in ["129,99 zł", "1299,00 PLN", "249,50 kr", "199,00 DKK"]:
        t(f"price_tag_{p}", bool(price.search(p)), p)
    # el precio SIN decimales no cuenta: "\d+ kr" convertiría en tienda a
    # cualquier web escandinava que cite un número seguido de esas dos letras
    t("price_tag_sin_decimales_no_cuenta", not price.search("dnb 1299 kr"),
      "un número suelto + kr no es prueba de tienda")


def test_peso_no_medido_no_se_reparte():
    """Bug (batería 6, allegro.pl): el peso de lo que NO pudimos medir se
    repartía entre lo que sí, inflando la nota de los sitios opacos.

    El reparto existe para las categorías que NO APLICAN (C7 en una web
    corporativa: no tiene fichas de producto, no hay nada que medir y la nota
    sigue siendo sobre 100). Se estaba aplicando también a las que no pudimos
    medir, que es otra cosa: allegro.pl nos bloqueó C3 entera (peso 20), su peso
    se repartió, las demás subieron un 25% y las dos categorías que allegro
    tenía perfectas (llms.txt y OAuth) pasaron a aportar 43.75 de 64.6 puntos.
    Cuanto menos podíamos medir, más pesaba lo poco medido.
    """
    def check(cid, cat, score, no_verif=False):
        r = {"id": cid, "cat": cat, "name": "x", "score": score, "evidence": "e"}
        if no_verif:
            r["no_verificable"] = True
        return r

    # C3 entera NO VERIFICABLE (ceguera), C5 y C6 perfectas
    ciego = [check("3.1", "C3", None, no_verif=True),
             check("3.2", "C3", None, no_verif=True),
             check("5.1", "C5", 1), check("6.1", "C6", 1)]
    total, cats, pesos, cob = scoring.total_score(ciego, "corporativo")
    t("ciego_no_reparte_peso_de_C3", "C3" not in pesos,
      f"C3 no se midió: su peso no puede repartirse: {pesos}")
    t("ciego_cobertura_menor_que_1", cob < 1.0,
      f"si falta una categoría por ceguera, la nota no cubre el modelo: cob={cob}")
    # el mismo perfil pero con C3 AUSENTE por no aplicar (sin la marca) sí
    # reparte, y por tanto puntúa MÁS: es la diferencia que se había perdido
    na = [check("5.1", "C5", 1), check("6.1", "C6", 1)]
    total_na, _, _, cob_na = scoring.total_score(na, "corporativo")
    t("no_aplica_si_reparte", cob_na == 1.0 and total_na > total,
      f"'no aplica' reparte y llega a 100; 'no lo sé' no: "
      f"ciego={total}/cob{cob} vs na={total_na}/cob{cob_na}")


def test_veredicto_de_acceso_usa_la_matriz_de_bots():
    """Bug en producción: argal.com y noel.es salían "Puerta cerrada a agentes"
    desde el servidor, y desde otra red servían 136 KB y 85 KB sin problema.

    El veredicto se decidía SOLO con nuestro UA de navegador, ignorando la matriz
    de bots — que ya tenía media respuesta. Estábamos describiendo el bloqueo del
    rango de IPs de Railway como si fuera la política del cliente hacia los
    agentes. Tres situaciones que no son la misma:
      - humano 200 y bots bloqueados -> puerta cerrada, EVIDENCIADO
      - todo bloqueado               -> no evaluable desde nuestra red
      - humano bloqueado, bots 200   -> se lee como bot y se analiza normal
    """
    def ctx_con(matrix, nivel=None):
        c = {"bot_matrix": matrix}
        if nivel:
            c["acceso_degradado"] = {"nivel": nivel}
        return c

    cerrada = ctx_con({"_human": 200, "GPTBot": 403, "ClaudeBot": 403})
    t("veredicto_puerta_cerrada", engine._veredicto_de_acceso(cerrada) == "puerta_cerrada",
      "vimos la web Y la vimos rechazar bots: eso sí es un hallazgo agéntico")

    todo = ctx_con({"_human": 403, "GPTBot": 403, "ClaudeBot": 403}, nivel="total")
    t("veredicto_no_evaluable", engine._veredicto_de_acceso(todo) == "no_evaluable",
      "si nos bloquean a todos no se puede afirmar nada sobre agentes")

    solo_a_nosotros = ctx_con({"_human": 403, "GPTBot": 200, "ClaudeBot": 200})
    t("veredicto_bots_entran_no_es_bloqueo",
      engine._veredicto_de_acceso(solo_a_nosotros) is None,
      "si los bots de IA entran con 200, la web NO está cerrada a agentes")

    normal = ctx_con({"_human": 200, "GPTBot": 200})
    t("veredicto_normal", engine._veredicto_de_acceso(normal) is None, "acceso correcto")

    # y los niveles resultantes dicen cosas distintas
    lv_c = scoring.level_for(30.0, veredicto="puerta_cerrada")
    lv_n = scoring.level_for(30.0, veredicto="no_evaluable")
    t("nivel_cerrada_no_es_parcial", not lv_c.get("cobertura_parcial"),
      "la puerta cerrada está evidenciada: la nota es real, no parcial")
    t("nivel_no_evaluable_es_parcial", lv_n.get("cobertura_parcial") is True, str(lv_n))
    t("nivel_no_evaluable_no_acusa", "no podemos distinguirlo" in lv_n["msg"],
      "no se puede afirmar que el sitio bloquee si puede ser nuestra IP")


def test_nota_parcial_se_entrega():
    """Nos pasamos de frenada: al dejar de puntuar los sitios que no podíamos
    leer, el cliente se quedaba SIN informe. En argal.com se verifican robots,
    sitemap, cabeceras, .well-known y DNS sin necesidad de ver la portada: eso
    es entregable si se dice qué cubre.
    """
    from . import report_json
    lv = scoring.level_for(22.5, veredicto="no_evaluable")
    payload = report_json.build_json({
        "client": {"host": "h", "score": 22.5, "score_pre_gate": 27.5, "level": lv,
                   "checks": [], "category_scores": {}, "cobertura_score": 0.45,
                   "score_fiable": False,
                   "acceso_degradado": {"nivel": "total", "motivo": "m", "degradados": 12}},
        "competitors": [], "generated": "2026-07-19"})
    p = payload["cliente"]["puntuacion"]
    t("json_entrega_la_nota_parcial", p["global_0_a_100"] == 22.5,
      f"la nota de lo verificado SÍ se entrega: {p}")
    t("json_marca_cobertura_parcial", p["cobertura_parcial"] is True, str(p))
    t("json_dice_que_cubre", p["cobertura_del_modelo"] == 0.45, str(p))
    t("json_explica_el_limite", bool(p["aviso_cobertura"]), str(p))


def test_agente_bloqueado_no_es_fallo_de_la_web():
    """Bug (validación jul 2026): el check 6.3 acusaba a la web de fallos nuestros.

    Al validar el modelo contra agentes reales, mango.com y coolblue.nl salieron
    con 0% de recorrido y "no_conseguido" ATRIBUIDO A LA WEB. Mirando qué recibió
    el navegador: mango devolvió un "Access Denied" de 294 bytes y coolblue una
    cáscara de 257 bytes que nunca hidrata. Nunca vimos esas webs. El flag
    `limite_de_metodo` no lo cazaba porque solo miraba timeouts de clic, y sin un
    solo elemento no se llega a clicar nada: cero timeouts. Es el sesgo central
    del proyecto, en el único check que dice literalmente "un agente no pudo usar
    tu web" — el más caro de equivocar.
    """
    nv = {"outcome": "no_verificable", "detail": "NO VERIFICABLE — bloqueo",
          "progreso": {"alcanzados": 0, "total": 5}, "steps": 1}
    agg = _aggregate([nv, dict(nv)])
    t("agg_no_verificable_se_propaga", agg["outcome"] == "no_verificable", str(agg))
    t("agg_no_verificable_marca_limite", agg.get("limite_de_metodo") is True, str(agg))

    # un intento ciego NO puede promediarse con uno real: eso convertiría
    # nuestra ceguera en media baja para el dominio
    real = {"outcome": "conseguido", "detail": "ok", "steps": 6,
            "progreso": {"alcanzados": 5, "total": 5}}
    mixto = _aggregate([nv, real])
    t("agg_mezcla_ignora_el_ciego",
      mixto["outcome"].startswith("conseguido") and mixto["intentos"] == 1,
      f"solo debe contar el intento que sí se pudo hacer: {mixto}")

    # y el check 6.3 no puede puntuarlo como 0
    ctx = ctx_base()
    ctx["agent_tests"] = {"agents": {"gemini": agg}, "hitos_no_evaluados": []}
    c63 = by_id(checks.run_c6(ctx), "6.3")
    t("check63_bloqueado_no_puntua", c63["score"] is None,
      f"sin haber visto la web, 6.3 no puede valer 0: {c63}")
    t("check63_bloqueado_es_manual", c63.get("manual") is True, str(c63))
    t("check63_bloqueado_no_dice_no_ejecutado",
      "No ejecutado" not in c63["evidence"],
      f"se ejecutó y nos bloquearon: decir 'no ejecutado' es falso: {c63['evidence']}")
    t("check63_bloqueado_explica",
      "NO VERIFICABLE" in c63["evidence"] or "sin resultado medible" in c63["evidence"],
      c63["evidence"])


def test_saas_una_fuerte_con_tres_debiles():
    """Bug (validación jul 2026): SaaS de manual clasificados "corporativo".

    Exigir DOS señales fuertes dejaba fuera a asana.com (free_trial + docs +
    login + pricing), canva.com (signup_url + los mismos tres) y monday.com
    (schema_software, o sea "@type":"SoftwareApplication", + 4 débiles). No era
    un fallo de render: con el HTML crudo ya sumaban 5-6 puntos. Cuesta doble:
    pesos equivocados y, en el 6.3, la TAREA equivocada (buscar la página de
    contacto en vez de los precios).
    """
    # 1 fuerte + 3 débiles = SaaS (perfil real de monday.com)
    corpus = ('"@type": "SoftwareApplication" '
              'href="/pricing/" href="/login" href="/docs" href="/integrations"')
    typ, ev = discovery.detect_typology(corpus, [])
    t("saas_1fuerte_3debiles", typ == "saas",
      f"una fuerte respaldada por tres débiles es concluyente: {typ} {ev['saas']}")

    # las débiles SOLAS siguen sin bastar: eso lo tiene cualquier corporativa
    solo_debiles = 'href="/pricing/" href="/login" href="/docs" href="/integrations"'
    typ2, ev2 = discovery.detect_typology(solo_debiles, [])
    t("saas_solo_debiles_no_basta", typ2 == "corporativo",
      f"/login + /precios + /docs los tiene cualquier web corporativa: {typ2} {ev2['saas']}")

    # y una tienda con evidencia ESTRUCTURAL no se convierte en SaaS por
    # mencionar precios y login (stripe.com fue el caso original)
    tienda = ('"@type": "Product" plugins/woocommerce añadir al carrito '
              'href="/pricing/" href="/login" href="/docs"')
    typ3, _ = discovery.detect_typology(tienda, [])
    t("tienda_estructural_no_se_vuelve_saas", typ3 == "ecommerce", typ3)


def test_comparativa_no_corona_entre_tipologias():
    """Hallazgo de la validación (jul 2026): el panel comparativo coronaba a la
    "mejor" aunque las tipologías fueran distintas, y no miden lo mismo.

    Con agentes reales sobre 21 dominios, la tarea de e-commerce
    (producto → carrito → checkout → datos) resultó mucho más dura que la de
    SaaS (precios → plan): los SaaS recorrieron 25-100% y las tiendas 0-55%.
    Los pesos por categoría tampoco coinciden (C7 solo puntúa en e-commerce).
    Coronar a la mejor de una mezcla le daba al cliente un ganador que no
    significaba nada. Verificado además en navegador: con tipologías mezcladas
    se pinta el aviso y ninguna tarjeta lleva .win; con la misma tipología, una.
    """
    src = open(os.path.join(os.path.dirname(__file__), "web", "index.html")).read()
    assert "function paneComparativa" in src, "cambió el nombre del panel"
    frag = src[src.index("function paneComparativa"):]
    frag = frag[:frag.index("const heatCats")]
    t("comparativa_detecta_tipologias", "new Set(audits.map(a=>a.typology))" in frag,
      "el panel debe mirar cuántas tipologías distintas hay")
    t("comparativa_corona_solo_si_homogenea", "!mixto&&conNota.length" in frag,
      "el 'mejor' solo puede calcularse cuando todas comparten tipología")
    t("comparativa_avisa_al_usuario", "no son comparables" in frag,
      "sin aviso, el usuario compara dos varas distintas sin saberlo")
    # el aviso tiene que llegar al HTML devuelto, no quedarse en una variable
    t("comparativa_pinta_el_aviso", "return avisoMixto+" in src,
      "el aviso se calculaba pero no se insertaba en el panel")


def test_presupuesto_de_salida_para_modelos_que_razonan():
    """Bug: el 39% de los pasos de Gemini se perdían y la web cargaba la culpa.

    Los modelos con razonamiento gastan tokens PENSANDO y salen del mismo
    presupuesto de salida. Con max_output_tokens=400, gemini-3.5-flash devolvía
    un fragmento del medio del JSON ('": "59,99 EUR",\\n "contacto": "info') que
    no se podía parsear. Medido sobre la validación de jul 2026: 70 de 178 pasos
    de Gemini perdidos así (39%), frente al 0% de ChatGPT; mailchimp.com perdió
    13 de 14 pasos, es decir que el agente nunca llegó a intentar la tarea, y se
    registró como "no conseguido" del sitio.
    """
    src = open(os.path.join(os.path.dirname(__file__), "agents.py")).read()
    t("presupuesto_salida_generoso", "_MAX_SALIDA = 2000" in src,
      "un JSON de acción ocupa ~80 tokens, pero el pensamiento sale del mismo saco")
    t("gemini_usa_el_presupuesto", "max_output_tokens\": _MAX_SALIDA" in src,
      "gemini tenía 400 cableado")
    t("no_quedan_presupuestos_de_400", '"max_output_tokens": 400' not in src
      and "max_tokens=400" not in src, "queda algún límite viejo que trunca")


def test_ruido_del_llm_no_es_fallo_de_la_web():
    """Mismo bug, la otra cara: un paso quemado porque NUESTRO modelo devolvió
    algo ilegible no dice absolutamente nada sobre la web auditada.

    El flag `limite_de_metodo` solo miraba timeouts de clic, así que un intento
    arruinado por respuestas ilegibles salía como fallo limpio del sitio.
    """
    src = open(os.path.join(os.path.dirname(__file__), "agents.py")).read()
    t("detecta_ruido_llm", "ilegibles / len(steps) >= 0.3" in src,
      "hay que medir qué parte del intento se fue en respuestas ilegibles")
    t("ruido_llm_marca_limite", "timeouts >= 2 or ruido_llm" in src,
      "el ruido del LLM tiene que marcar límite de método, como los timeouts")
    t("ruido_llm_se_explica", "límite NUESTRO, no un problema de la web" in src,
      "el informe debe decir de quién es el problema")


def test_cierre_de_cookies_multiidioma():
    """Bug (estudio 4, jul 2026): el banner de cookies interceptaba TODOS los
    clics y la web se llevaba el "no conseguido".

    El patrón exigía coincidencia EXACTA de una palabra suelta (/^aceptar$/) y
    máximo 20 caracteres. Los botones reales casi nunca son así: dnb.no ofrece
    "Godta alle" y hawkersco.com "Allow all cookies" — en ambos se cerraban CERO
    banners, el overlay tapaba la página y los 5 pasos se iban en timeouts que
    se apuntaban como fallo del sitio. 13 de 37 dominios se quedaron sin una
    sola observación. Tras el arreglo, hawkersco.com pasa de 0 clics a operar.
    """
    src = open(os.path.join(os.path.dirname(__file__), "agents.py")).read()
    ini = src.index("_CERRAR_JS")
    js = src[ini:src.index("def _despejar")]
    t("cookies_no_exige_texto_exacto", "^(aceptar|accept|entendido" not in js,
      "el patrón anclado a una palabra no casa con 'Allow all cookies'")
    for frase, etq in [("godta", "noruego (dnb.no: 'Godta alle')"),
                       ("allow all", "inglés (hawkersco: 'Allow all cookies')"),
                       ("aceitar", "portugués"), ("akkoord", "neerlandés"),
                       ("hyväksy", "finés"), ("zaakceptuj", "polaco")]:
        t(f"cookies_cubre_{frase[:9]}", frase in js.lower(), f"falta {etq}")
    # privacidad: si hay opción de rechazar, se pulsa esa
    t("cookies_prefiere_rechazar", js.index("RECHAZO") < js.index("ACEPTA")
      and "for (const patron of [RECHAZO, ACEPTA])" in js,
      "hay que intentar rechazar antes que aceptar")
    # los selectores exactos de plataforma no pueden pulsar otra cosa por error
    t("cookies_usa_selectores_conocidos", "onetrust" in js.lower()
      and "cookiebot" in js.lower(), "faltan los selectores de OneTrust/Cookiebot")


def test_escalera_de_lectura():
    """Idea de Carlos: si nos bloquean, probar otras identidades para poder
    verificar los 40 factores — como hace Screaming Frog.

    Se implementa con tres condiciones que la hacen honesta:
      1. Solo afecta a la capa 1 (QUÉ tiene la web). La matriz de acceso y los
         checks 1.6/2.4/4.4 siguen midiendo con el UA real de cada bot: si un
         sitio deja entrar a Googlebot y rechaza a GPTBot, ESE es el hallazgo y
         no puede quedar tapado por haber entrado por otra puerta.
      2. Googlebot va DESACTIVADO por defecto: suplantarlo desde una IP que no
         es de Google es una firma de spoofing que los WAF serios penalizan, y
         esto audita también dominios de terceros.
      3. Se registran TODOS los intentos con su código. Ese registro es el que
         dirá si el bloqueo de producción es por user agent o por rango de IP,
         que hoy no lo sabemos.
    """
    from .config import UA_ESCALERA, UA_GOOGLEBOT, BOT_UAS, UA_HUMAN
    t("escalera_tiene_bingbot", any("bingbot" in v.lower() for v in UA_ESCALERA.values()),
      "falta un peldaño intermedio antes de recurrir a Googlebot")
    t("googlebot_va_aparte", "Googlebot-Smartphone" in UA_GOOGLEBOT
      and not any("googlebot" in v.lower() for v in UA_ESCALERA.values()),
      "Googlebot no puede estar en la escalera por defecto")
    t("googlebot_fuera_de_la_matriz",
      not any("googlebot" in v.lower() for v in BOT_UAS.values()),
      "la matriz mide bots de IA: meter a Googlebot ahí falsearía el acceso")

    src = open(os.path.join(os.path.dirname(__file__), "engine.py")).read()
    t("escalera_googlebot_es_opt_in", "if ua_googlebot:" in src,
      "Googlebot solo entra en la escalera si quien audita lo activa")
    t("escalera_registra_intentos", 'ctx["escalera_intentos"] = intentos' in src,
      "sin el registro de intentos no sabremos si el bloqueo es por IP o por UA")
    t("escalera_distingue_ip_de_ua", "RANGO DE IP" in src and "por USER AGENT" in src,
      "el trail debe decir cuál de las dos cosas está pasando")
    t("escalera_no_tapa_el_bloqueo", "sigue medido aparte en la matriz" in src,
      "hay que dejar dicho que el acceso real se mide con el UA de cada bot")

    # la vía usada viaja al informe: un 40 leído como Googlebot no es un 40
    # leído como Chrome, y quien lo lee tiene que poder distinguirlo
    t("via_lectura_en_el_resultado", '"via_lectura":' in src, "falta exponer la vía")


def test_reintento_solo_en_fallos_transitorios():
    """Una petición perdida se leía como "la web no tiene esa cosa".

    En un análisis salen ~50 peticiones por dominio y `fetch` no reintentaba
    ninguna. Visto hoy en vivo: noel.es devolvió ClaudeBot=0 (timeout) y
    elpozo.com GPTBot=503 pasajero, mientras el resto de UAs recibía 200. Eso se
    publicaba como si esos sitios bloquearan a esos bots a propósito, que es una
    acusación y no una medición.

    La distinción que hace esto correcto: un 403/404/418 ES una respuesta
    deliberada del sitio y no se reintenta —insistir borraría un hallazgo real—;
    un timeout o un 503 es la AUSENCIA de respuesta y sí se reintenta.
    """
    from . import httpfetch as hf
    for code in (0, 429, 503, 502, 504):
        t(f"transitorio_{code}", hf._es_transitorio(code),
          f"{code} es un tropiezo del camino, hay que reintentarlo")
    for code in (200, 403, 404, 418, 301):
        t(f"deliberado_{code}", not hf._es_transitorio(code),
          f"{code} es una respuesta del sitio: reintentarla borraría el hallazgo")

    src = open(os.path.join(os.path.dirname(__file__), "httpfetch.py")).read()
    # rapid_fire mide el baneo por ritmo: ahí un 429 es EL dato, no ruido
    ini = src.index("def rapid_fire")
    cuerpo = src[ini:src.index("def jina_read")]
    t("rapid_fire_sin_reintento", "reintentar=False" in cuerpo,
      "reintentar en la sonda de rate limiting destruiría lo que mide")
    # y el segundo intento no puede quedarse peor que el primero
    t("reintento_solo_si_mejora", "if not _es_transitorio(segundo[\"status\"]):" in src,
      "si el reintento vuelve a fallar hay que conservar el resultado original")


def test_36_lee_el_arbol_de_accesibilidad_real():
    """El check que decía medir el árbol de accesibilidad no lo leía.

    Se estimaba con regex sobre el HTML crudo (contando div/span clicables).
    Medido contra el árbol REAL de Chrome en 14 dominios: r=0.35. Un check que
    afirma medir el árbol de accesibilidad tiene que leerlo, no aproximarlo.

    Y lo que importa a un agente NO es que el control sea un <div> o un
    <button>: es que TENGA NOMBRE. Nuestro propio harness nombra cada control
    con innerText/aria-label/alt —el nombre accesible— y con ese nombre decide
    qué pulsar. Un botón sin nombre le llega como una casilla en blanco.
    """
    def con_ax(ax):
        ctx = ctx_base()
        ctx["rendered_home"] = {"ok": True, "ax": ax}
        return by_id(checks.run_c3(ctx), "3.6")

    perfecto = con_ax({"nodos": 303, "accionables": 189, "sin_nombre": 0,
                       "nombre_generico": 0, "ejemplos": []})
    t("ax_perfecto_puntua_1", perfecto["score"] == 1, str(perfecto))
    t("ax_cita_el_arbol_real", "Arbol de accesibilidad real" in perfecto["evidence"],
      "la evidencia debe dejar claro que se leyó el árbol, no una estimación")

    # caso real medido: noel.es, 13 de 82 controles sin nombre
    malo = con_ax({"nodos": 124, "accionables": 82, "sin_nombre": 13,
                   "nombre_generico": 0,
                   "ejemplos": [{"rol": "link", "nombre": None, "problema": "sin nombre"}]})
    t("ax_16pct_suspende", malo["score"] == 0, f"16% sin nombre es un fallo: {malo}")
    t("ax_da_ejemplos", "Ejemplos:" in malo["evidence"],
      "sin ejemplos concretos el cliente no sabe qué arreglar")

    leve = con_ax({"nodos": 50, "accionables": 40, "sin_nombre": 2,
                   "nombre_generico": 1, "ejemplos": []})
    t("ax_leve_es_parcial", leve["score"] == 0.5, str(leve))

    # Calibración: exigir CERO castigaba a webs impecables. stripe.com bajaba a
    # 0.5 por UN nombre genérico entre 189 controles (0.5%), que no atasca a
    # nadie. Con la mediana medida en 0% y la media en 2%, el corte va en 2%.
    casi = con_ax({"nodos": 300, "accionables": 189, "sin_nombre": 0,
                   "nombre_generico": 1, "ejemplos": []})
    t("ax_1_de_189_sigue_siendo_bueno", casi["score"] == 1,
      f"0.5% de controles flojos no es un fallo: {casi}")
    t("ax_no_afirma_que_esten_todos", "de 189 controles" in casi["evidence"],
      f"con el umbral en 2% no se puede decir 'todos': {casi['evidence'][:120]}")

    # un nombre que existe pero no dice nada cuenta como ilegible
    from .render import _resumen_ax
    r = _resumen_ax({"role": "WebArea", "name": "x", "children": [
        {"role": "link", "name": "ver más"}, {"role": "button", "name": ""},
        {"role": "button", "name": "Añadir al carrito"}]})
    t("ax_generico_cuenta", r["nombre_generico"] == 1 and r["sin_nombre"] == 1,
      f"'ver más' no le dice nada a un agente: {r}")
    t("ax_nombre_bueno_no_penaliza", r["accionables"] == 3, str(r))

    # sin render no se inventa: se avisa de que es aproximado
    ctx = ctx_base()
    ctx["rendered_home"] = None
    sin = by_id(checks.run_c3(ctx), "3.6")
    t("ax_sin_render_avisa", "APROXIMADO" in sin["evidence"],
      f"sin árbol hay que decir que la medida es peor: {sin['evidence'][-80:]}")


def test_429_se_respeta_el_ritmo_que_pide_el_sitio():
    """Un 429 es el servidor pidiendo calma, y lo reintentábamos a 1.5s.

    Caso real (finistore.es desde el servidor de producción): tienda Shopify
    sana —desde otra red da HTTP 200, 592 KB y nota 65.8— que devolvía 429 con
    su página de error de 79 KB. El guardarraíl hacía bien en no puntuar esa
    página, pero el análisis se perdía entero. Y nosotros no ayudábamos: un
    análisis lanza ~52 peticiones al mismo dominio, así que tras el primer 429
    seguíamos disparando y alargando el castigo.

    Dos arreglos: respetar `Retry-After` cuando el servidor lo manda, y espaciar
    las sondas siguientes al mismo host.
    """
    from . import httpfetch as hf

    # el servidor manda: si dice cuánto esperar, se le hace caso
    t("429_respeta_retry_after", hf._espera_indicada(429, "12") == 12.0,
      "si el servidor dice 12 segundos, son 12")
    t("429_retry_after_con_espacios", hf._espera_indicada(429, " 5 ") == 5.0, "")
    # ...pero con tope: un Retry-After de 300 colgaría el análisis 5 min por sonda
    t("429_retry_after_con_tope",
      hf._espera_indicada(429, "300") == hf.RETRY_AFTER_MAX,
      f"hay que topar en {hf.RETRY_AFTER_MAX}s o el análisis no termina nunca")
    # formato de fecha HTTP: no se interpreta, se cae al valor por defecto
    t("429_fecha_http_no_rompe",
      hf._espera_indicada(429, "Wed, 21 Oct 2026 07:28:00 GMT") == hf.PAUSA_429, "")
    # sin cabecera, un 429 espera MUCHO más que un timeout: no es lo mismo
    t("429_sin_cabecera_espera_mas",
      hf._espera_indicada(429, None) == hf.PAUSA_429
      and hf.PAUSA_429 > hf.PAUSA_REINTENTO,
      f"429={hf.PAUSA_429}s vs transitorio={hf.PAUSA_REINTENTO}s")
    t("timeout_no_espera_de_mas",
      hf._espera_indicada(0, None) == hf.PAUSA_REINTENTO, "")

    # espaciado por host: tras un 429 se va más despacio con ESE host
    hf._HOSTS_FRENADOS.clear()
    hf._marcar_frenado("https://ejemplo.test/x")
    t("freno_es_por_host", "ejemplo.test" in hf._HOSTS_FRENADOS, str(hf._HOSTS_FRENADOS))
    t("freno_no_afecta_a_otros",
      hf._host_de("https://otro.test/") not in hf._HOSTS_FRENADOS,
      "frenar un host no puede ralentizar el análisis de otro")
    # y caduca solo: un 429 de hace media hora no debe seguir penalizando
    hf._HOSTS_FRENADOS["ejemplo.test"] = time.monotonic() - hf.VENTANA_FRENO - 1
    hf._esperar_si_frenado("https://ejemplo.test/x")
    t("freno_caduca", "ejemplo.test" not in hf._HOSTS_FRENADOS,
      "pasada la ventana hay que olvidar el freno")
    hf._HOSTS_FRENADOS.clear()

    # la sonda que MIDE el rate limiting no puede ir espaciada ni reintentar:
    # ahí el 429 es el hallazgo, no un tropiezo
    src = open(os.path.join(os.path.dirname(__file__), "httpfetch.py")).read()
    cuerpo = src[src.index("def rapid_fire"):src.index("def jina_read")]
    t("rapid_fire_sigue_sin_frenos", "reintentar=False" in cuerpo, "")
    so = src[src.index("def status_only"):src.index("def bot_access_matrix")]
    t("espaciado_solo_si_reintenta", "if reintentar:\n        _esperar_si_frenado" in so,
      "rapid_fire pasa reintentar=False, así que no debe espaciarse")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        try:
            fn()
        except Exception as exc:  # un crash del test también es un fallo
            FALLOS.append(f"{fn.__name__}: EXCEPCION {type(exc).__name__}: {exc}")
    print(f"selftest: {PASADOS} asserts OK · {len(FALLOS)} fallos")
    for f in FALLOS:
        print("  FALLO", f)
    sys.exit(1 if FALLOS else 0)


if __name__ == "__main__":
    main()
