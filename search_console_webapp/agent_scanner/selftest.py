# -*- coding: utf-8 -*-
"""Suite de regresión OFFLINE del scanner: `python3 -m agent_scanner.selftest`.

Cada test corresponde a un bug REAL encontrado en calibración o en las baterías
de dominios (jul 2026). Si un cambio futuro reintroduce uno de estos fallos,
esta suite lo caza sin tocar la red. Complemento de la calibración con dominios
vivos (CALIBRACION.md en el proyecto web-agentica), no sustituto.

Sin dependencias de test externas: asserts planos, exit code 1 si algo falla.
"""
import re
import sys

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
