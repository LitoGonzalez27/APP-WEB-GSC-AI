"""Checks C1-C7 del framework de auditoria (seccion 11 del informe).

Cada check devuelve:
  {id, cat, name, score (0 | 0.5 | 1 | None=N/A), evidence, manual (bool)}

`manual=True` marca checks heuristicos que conviene revisar con ojo humano
antes de entregar al cliente.
"""
import json
import re

from .discovery import parse_robots_groups, robots_allows
from .config import BOT_UAS

# ---------------------------------------------------------------- helpers

def visible_text(html):
    """Texto visible aproximado: fuera scripts/estilos/tags."""
    if not html:
        return ""
    html = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def jsonld_blocks(html):
    """Extrae y parsea los bloques JSON-LD. Devuelve (validos, invalidos)."""
    valid, invalid = [], 0
    for raw in re.findall(
            r'(?is)<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html or ""):
        try:
            data = json.loads(raw.strip())
            valid.extend(data if isinstance(data, list) else [data])
        except (json.JSONDecodeError, ValueError):
            invalid += 1
    return valid, invalid


def flatten_types(blocks):
    types = []
    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if t:
                types.extend(t if isinstance(t, list) else [t])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(blocks)
    return types


def find_nodes(blocks, wanted_type):
    found = []
    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            tlist = t if isinstance(t, list) else [t]
            if wanted_type in tlist:
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(blocks)
    return found


def R(cid, cat, name, score, evidence, manual=False):
    return {"id": cid, "cat": cat, "name": name, "score": score,
            "evidence": evidence[:400], "manual": manual}


# ---------------------------------------------------------------- C1 acceso

def run_c1(ctx):
    out = []
    rb = ctx["robots"]

    # 1.1 robots.txt existe y es parseable
    if rb["status"] == 200 and rb["raw"] and not rb["is_html"]:
        score, ev = 1, "robots.txt 200 y parseable"
    elif rb["status"] == 200 and rb["is_html"]:
        score, ev = 0, "robots.txt devuelve HTML (error tipico de SPA que enruta todo)"
    else:
        score, ev = 0, f"robots.txt HTTP {rb['status']}"
    out.append(R("1.1", "C1", "robots.txt valido", score, ev))

    # 1.2 politica de bots de IA explicita y selectiva
    groups = parse_robots_groups(rb["raw"])
    ai_bots_named = [ua for ua in groups if any(
        b.lower() in ua for b in list(BOT_UAS) + ["anthropic-ai", "claude-searchbot",
                                                  "amazonbot", "applebot-extended",
                                                  "meta-externalagent", "bytespider", "ccbot"])]
    live_blocked = [b for b in ("oai-searchbot", "chatgpt-user", "perplexitybot")
                    if not robots_allows(groups, b)]
    # Nota maxima solo si se pronuncia sobre los bots QUE IMPORTAN. Nombrar a
    # un secundario (p.ej. Amazonbot) y callar sobre GPTBot/ClaudeBot no es una
    # politica: Notion sacaba un 1 sin decir nada de los crawlers relevantes.
    PRINCIPALES = ("gptbot", "claudebot", "oai-searchbot", "chatgpt-user",
                   "perplexitybot", "google-extended")
    principales_nombrados = [ua for ua in groups
                             if any(b in ua for b in PRINCIPALES)]
    if live_blocked:
        score, ev = 0, f"Bloquea bots de busqueda EN VIVO: {', '.join(live_blocked)} (autoexclusion de respuestas IA)"
    elif len(principales_nombrados) >= 2:
        score = 1
        ev = (f"Politica explicita sobre los bots que importan "
              f"({len(principales_nombrados)}): {', '.join(principales_nombrados[:6])}")
    elif ai_bots_named:
        score = 0.5
        faltan = [b for b in PRINCIPALES
                  if not any(b in ua for ua in groups)]
        ev = (f"Solo nombra a {', '.join(ai_bots_named[:4])}, pero NO se pronuncia sobre "
              f"los crawlers que deciden tu presencia en respuestas de IA "
              f"({', '.join(faltan[:4])}): decision a medias")
    else:
        score, ev = 0.5, "Sin reglas nominales para bots de IA (todo permitido por defecto, sin decision consciente)"
    out.append(R("1.2", "C1", "Politica de bots de IA", score, ev))

    # 1.3 bloqueo declarado vs real (WAF)
    matrix = ctx["bot_matrix"]
    # Cualquier respuesta que no sea exito ni redireccion normal es un bloqueo.
    # Antes se listaban codigos concretos y se escapaban los 5xx: un 503 a GPTBot
    # (bloqueo silencioso muy comun en WAF de hosting) se daba por bueno.
    # Detectado en el set de calibracion: elpozo.com devolvia GPTBot=503 y el
    # check decia "todo coincide". Es ademas el peor bloqueo posible: un 503 le
    # dice al bot "vuelve luego" en vez de "no entres", asi que reintenta siempre.
    def _bloqueado(code):
        return code == 0 or code >= 400

    mismatches = []
    for bot, code in matrix.items():
        if bot == "_human":
            continue
        if robots_allows(groups, bot) and _bloqueado(code):
            mismatches.append(f"{bot}={code}")
    human_ok = matrix.get("_human", 0) == 200
    if mismatches and human_ok:
        score = 0
        ev = f"robots.txt permite pero el servidor bloquea: {', '.join(mismatches)} (humano=200)"
        if any(c.endswith(("=503", "=429", "=500", "=502")) for c in mismatches):
            ev += (". Ademas responde con un error de servidor en vez de un 403: el bot "
                   "lo interpreta como 'vuelve mas tarde' y reintentara indefinidamente, "
                   "sin que nadie se entere de que esta bloqueado")
    elif not human_ok:
        score, ev = 0.5, f"Ni el UA humano recibe 200 ({matrix.get('_human')}): WAF muy agresivo, revisar"
    else:
        score = 1
        codes = ", ".join(f"{k}={v}" for k, v in matrix.items() if k != "_human")
        ev = f"Acceso declarado coincide con el real ({codes})"
    out.append(R("1.3", "C1", "Bloqueo declarado vs real", score, ev))

    # 1.4 sitemap presente y fresco. "Bloqueado" != "ausente": si las rutas de
    # sitemap devuelven 403/timeout no podemos afirmar que falte (zalando.es).
    sm = ctx["sitemap"]
    if sm["found"] and ctx["sitemap_fresh"]:
        out.append(R("1.4", "C1", "sitemap.xml fresco", 1,
                     f"Sitemap con {len(sm['urls'])} URLs y lastmod reciente (<90 dias)"))
    elif sm["found"]:
        out.append(R("1.4", "C1", "sitemap.xml fresco", 0.5,
                     f"Sitemap con {len(sm['urls'])} URLs pero sin lastmod reciente"))
    elif sm.get("bloqueado"):
        out.append(R("1.4", "C1", "sitemap.xml fresco", None,
                     f"Las rutas de sitemap no responden a acceso automatizado "
                     f"(HTTP {sm.get('estados')}): puede existir y estar bloqueado, "
                     "no es afirmable que falte", manual=True))
    else:
        out.append(R("1.4", "C1", "sitemap.xml fresco", 0, "Sin sitemap.xml localizable"))

    # 1.5 Link headers (RFC 8288)
    link_h = re.search(r"(?im)^link:\s*(.+)$", ctx["home"]["headers"] or "")
    out.append(R("1.5", "C1", "Link headers (RFC 8288)",
                 1 if link_h else 0,
                 link_h.group(1)[:120] if link_h else "Sin cabeceras Link (minoria hoy; oportunidad, no error)"))

    # 1.6 contenido clave accesible sin login
    pages = ctx["pages"]
    ok = sum(1 for p in pages if p["fetch"]["status"] == 200
             and len(visible_text(p["fetch"]["body"])) > 500)
    total = max(len(pages), 1)
    ratio = ok / total
    score = 1 if ratio >= 0.85 else 0.5 if ratio >= 0.5 else 0
    out.append(R("1.6", "C1", "Contenido accesible sin login",
                 score, f"{ok}/{total} paginas muestreadas devuelven contenido util sin sesion"))

    # 1.7 DNS para descubrimiento de agentes (DNS-AID, experimental — peso bajo)
    aid = ctx.get("dns_aid")
    out.append(R("1.7", "C1", "DNS-AID (descubrimiento via DNS)",
                 1 if aid else 0,
                 aid or "Sin registros TXT _aid/_agent (estandar experimental: casi nadie lo tiene aun)"))
    return out


# ---------------------------------------------------------------- C2 bots

def run_c2(ctx):
    out = []
    rb_raw = ctx["robots"]["raw"] or ""

    # 2.1 Content Signals (search / ai-input / ai-train: cada señal autoriza un uso distinto)
    parsed = dict(re.findall(r"(?i)\b(search|ai-input|ai-train)\s*[=:]\s*(yes|no)", rb_raw))
    legacy = re.findall(r"(?im)^\s*#?\s*(?:noai|noimageai)\b[^\n]*", rb_raw)
    if parsed:
        detail = ", ".join(f"{k}={v}" for k, v in parsed.items())
        if parsed.get("ai-input") == "no":
            score, ev = 0.5, f"Señales declaradas ({detail}) pero ai-input=no: renuncias a ser citado en respuestas IA"
        else:
            score, ev = 1, f"Content Signals declarados con proposito: {detail}"
    elif legacy:
        score, ev = 0.5, "Solo señales legacy (noai) sin granularidad de proposito"
    else:
        score, ev = 0, "Sin Content Signals (solo el 4% de sitios los tiene: quick win)"
    out.append(R("2.1", "C2", "Content Signals declarados", score, ev))

    # 2.2 gestion activa de crawl (CDN/WAF)
    headers = (ctx["home"]["headers"] or "").lower()
    cdn = None
    for marker, name in (("cf-ray", "Cloudflare"), ("x-served-by", "Fastly/Varnish"),
                         ("akamai", "Akamai"), ("x-cache", "CDN con cache")):
        if marker in headers:
            cdn = name
            break
    saw_402 = any(code == 402 for code in ctx["bot_matrix"].values())
    if saw_402:
        score, ev = 1, "Devuelve HTTP 402 a bots: gestion/monetizacion activa del crawl"
    elif cdn:
        score, ev = 0.5, f"{cdn} detectado (capacidad disponible; confirmar con el cliente si AI Crawl Control esta configurado)"
    else:
        score, ev = 0, "Sin CDN/WAF detectado: probablemente nadie vigila que bots de IA entran"
    out.append(R("2.2", "C2", "Gestion activa de crawl", score, ev, manual=bool(cdn)))

    # 2.3 Web Bot Auth (verificacion criptografica)
    wba = ctx["wellknown"].get("/.well-known/http-message-signatures-directory", 0)
    out.append(R("2.3", "C2", "Web Bot Auth", 1 if wba == 200 else 0,
                 f"Directorio de firmas HTTP {wba}" if wba == 200
                 else "Sin soporte Web Bot Auth (normal en 2026; anotar como roadmap)"))

    # 2.4 rate limiting razonable
    rapid = ctx["rapid"]
    if not rapid:
        out.append(R("2.4", "C2", "Rate limiting razonable", None, "No medido"))
        return out
    n200 = rapid.count(200)
    n429 = rapid.count(429)
    hard = sum(1 for c in rapid if c in (403, 0))
    if hard >= len(rapid) // 2:
        score, ev = 0, f"Baneo tras pocas peticiones: {rapid}"
    elif n200 == len(rapid) or n429 > 0:
        score, ev = 1, f"Estable o throttling suave: {n200}x200, {n429}x429"
    else:
        score, ev = 0.5, f"Comportamiento mixto: {rapid}"
    out.append(R("2.4", "C2", "Rate limiting razonable", score, ev))
    return out


# ---------------------------------------------------------------- C3 schema

def run_c3(ctx):
    out = []
    # La HOME cuenta como pagina: es la plantilla mas marcada de casi cualquier
    # sitio y dejarla fuera daba falsos negativos (el marcado existia y el check
    # decia que no). Detectado en el set de calibracion contra verificacion manual.
    pages = [p for p in ctx["pages"] if p["fetch"]["status"] == 200]
    if len(ctx["home"].get("body") or "") > 200:
        pages = [{"url": ctx["base"], "bucket": "home", "fetch": ctx["home"]}] + pages
    per_page = [(p, *jsonld_blocks(p["fetch"]["body"])) for p in pages]

    # 3.1 JSON-LD presente y valido
    with_valid = sum(1 for _, valid, _inv in per_page if valid)
    invalid_total = sum(inv for _, _v, inv in per_page)
    total = max(len(per_page), 1)
    ratio = with_valid / total
    score = 1 if ratio >= 0.7 and invalid_total == 0 else 0.5 if ratio >= 0.4 else 0
    out.append(R("3.1", "C3", "JSON-LD presente y valido", score,
                 f"{with_valid}/{total} paginas con JSON-LD valido; {invalid_total} bloques invalidos"))

    # 3.2 Organization / entidad
    home_valid, _ = jsonld_blocks(ctx["home"]["body"])
    orgs = find_nodes(home_valid, "Organization") + find_nodes(home_valid, "LocalBusiness")
    if orgs:
        org = orgs[0]
        fields = [f for f in ("name", "url", "logo", "sameAs", "contactPoint") if org.get(f)]
        score = 1 if len(fields) >= 4 else 0.5
        ev = f"Organization con {len(fields)}/5 campos clave ({', '.join(fields)})"
    else:
        score, ev = 0, "Sin Organization/LocalBusiness en la home: la entidad no esta declarada"
    out.append(R("3.2", "C3", "Entidad Organization completa", score, ev))

    # 3.3 Product/Offer operativo (solo ecommerce)
    if ctx["typology"] == "ecommerce":
        prod_pages = [(p, v) for p, v, _ in per_page if p["bucket"] == "producto" and v]
        best_score, best_ev = 0, "Sin JSON-LD Product en fichas de producto muestreadas"
        for p, valid in prod_pages:
            prods = find_nodes(valid, "Product")
            for prod in prods:
                offers = prod.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                have = [f for f in ("price", "priceCurrency", "availability") if offers.get(f)]
                base = [f for f in ("name", "image", "description", "brand") if prod.get(f)]
                if len(have) == 3 and len(base) >= 3:
                    best_score, best_ev = 1, f"Product completo en {p['url'][:80]} (offers: {', '.join(have)})"
                elif len(have) >= 1 and best_score < 1:
                    best_score = max(best_score, 0.5)
                    best_ev = f"Product incompleto en {p['url'][:80]}: offers solo con {', '.join(have)}"
        out.append(R("3.3", "C3", "Product/Offer operativo", best_score, best_ev))
    else:
        out.append(R("3.3", "C3", "Product/Offer operativo", None, "N/A (no es e-commerce)"))

    # 3.4 atributos ricos
    all_valid = [v for _, v, _ in per_page for v in [v]][0:] if per_page else []
    rich_fields = ("gtin", "gtin13", "sku", "mpn", "brand", "aggregateRating", "review",
                   "material", "color", "size", "author", "datePublished", "dateModified")
    corpus = json.dumps([v for _, v, _ in per_page], ensure_ascii=False) if per_page else ""
    present = [f for f in rich_fields if f'"{f}"' in corpus]
    score = 1 if len(present) >= 6 else 0.5 if len(present) >= 3 else 0
    out.append(R("3.4", "C3", "Atributos ricos en el marcado", score,
                 f"{len(present)} tipos de atributo rico presentes: {', '.join(present[:8]) or 'ninguno'}"))

    # 3.5 HTML semantico
    html = ctx["home"]["body"] or ""
    h1s = len(re.findall(r"(?i)<h1[\s>]", html))
    h2s = len(re.findall(r"(?i)<h2[\s>]", html))
    semantic = sum(1 for t in ("main", "nav", "article", "header", "footer")
                   if re.search(rf"(?i)<{t}[\s>]", html))
    buttons = len(re.findall(r"(?i)<button[\s>]", html))
    divs_click = len(re.findall(r"(?i)<div[^>]+onclick", html))
    good = (h1s == 1) + (h2s >= 2) + (semantic >= 3) + (buttons > divs_click)
    score = 1 if good >= 4 else 0.5 if good >= 2 else 0
    out.append(R("3.5", "C3", "HTML semantico", score,
                 f"h1={h1s}, h2={h2s}, landmarks={semantic}/5, button={buttons} vs div-onclick={divs_click}"))

    # 3.6 controles que el agente ve pero no entiende.
    #
    # Se mide sobre el ARBOL DE ACCESIBILIDAD REAL cuando hay render: es el mismo
    # que consumen los agentes de navegacion (el nuestro incluido, que nombra
    # cada control con innerText/aria-label/alt, o sea el nombre accesible).
    # Antes solo existia el heuristico de regex sobre HTML crudo de mas abajo, y
    # se parecia poco al arbol de verdad: r=0.35 medido sobre 14 dominios. Un
    # check que dice medir el arbol de accesibilidad tiene que leerlo.
    ax = (ctx.get("rendered_home") or {}).get("ax")
    if ax and ax.get("accionables"):
        n = ax["accionables"]
        ciegos = ax["sin_nombre"] + ax["nombre_generico"]
        pct = ciegos / n
        # Umbrales calibrados con los 23 dominios medidos: la mediana de
        # controles sin nombre es 0% y la media 2%. Exigir literalmente CERO
        # castigaba a webs impecables — stripe.com bajaba a 0.5 por UN nombre
        # generico entre 189 controles (0.5%), que no atasca a ningun agente.
        # Por encima del 10% ya es una anomalia clara frente a lo que hace todo
        # el mundo, y ahi si merece salir como fallo en el informe.
        if pct <= 0.02:
            score = 1
        elif pct <= 0.10:
            score = 0.5
        else:
            score = 0
        muestra = "; ".join(
            f"<{e['rol']}> {e['problema']}" + (f" ('{e['nombre']}')" if e.get("nombre") else "")
            for e in (ax.get("ejemplos") or [])[:3])
        ev = (f"Arbol de accesibilidad real: {n} controles accionables, "
              f"{ax['sin_nombre']} sin nombre y {ax['nombre_generico']} con nombre "
              f"generico ({pct:.0%}). Un agente los ve pero no sabe que hacen.")
        if muestra:
            ev += f" Ejemplos: {muestra}."
        if score == 1:
            # Sin afirmar "todos": con el umbral en 2% puede quedar alguno suelto,
            # y decir que estan todos seria afirmar lo que no hemos comprobado.
            ev = (f"Arbol de accesibilidad real: {n - ciegos} de {n} controles "
                  f"accionables tienen nombre propio ({1 - pct:.0%}). Un agente "
                  f"puede saber que hace cada uno.")
            if ciegos:
                ev += (f" Quedan {ciegos} sin nombre util, por debajo de lo que "
                       f"atasca a un agente.")
        out.append(R("3.6", "C3", "Controles legibles por un agente", score, ev))
        return out

    # Sin render no hay arbol: se cae al heuristico de HTML crudo, que aproxima
    # peor pero no deja el check sin medir.
    ghost, mitigated, native = 0, 0, 0
    corpus_pages = [ctx["home"]] + [p["fetch"] for p in pages[:5]]
    for f in corpus_pages:
        body = f["body"] or ""
        for tag_match in re.findall(r"(?is)<(?:div|span)\b[^>]{0,400}>", body):
            clickable = "onclick" in tag_match.lower() or re.search(
                r'class=["\'][^"\']*\b(btn|button|clickable)\b', tag_match, re.I)
            if not clickable:
                continue
            if re.search(r'role=["\']button', tag_match, re.I) and "tabindex" in tag_match.lower():
                mitigated += 1
            else:
                ghost += 1
        native += len(re.findall(r"(?i)<button[\s>]|<a\s[^>]*href=", body))
    if ghost == 0:
        score, ev = 1, f"Sin elementos fantasma; {native} controles nativos, {mitigated} mitigados con role+tabindex"
    elif ghost <= 3 or (mitigated and ghost <= mitigated):
        score, ev = 0.5, f"{ghost} elementos fantasma (div/span clicables sin semantica) vs {native} nativos"
    else:
        score, ev = 0, f"{ghost} elementos fantasma: invisibles como interactivos ({native} nativos)"
    ev += (" [APROXIMADO: sin render no se pudo leer el arbol de accesibilidad real; "
           "esto se estima con el HTML crudo y aproxima peor. Activa el render JS "
           "para medirlo de verdad]")
    out.append(R("3.6", "C3", "Controles legibles por un agente", score, ev))
    return out


# ---------------------------------------------------------------- C4 render

def run_c4(ctx):
    out = []

    # 4.1 contenido en HTML sin ejecutar JS (EL critico)
    raw_len = len(visible_text(ctx["home"]["body"]))
    rendered = ctx.get("rendered_home")
    if rendered and rendered.get("ok"):
        ren_len = len(visible_text(rendered.get("html", "")))
        ratio = raw_len / ren_len if ren_len > 200 else 1
        if ratio >= 0.7:
            score, ev = 1, f"El HTML crudo contiene el {ratio:.0%} del contenido renderizado ({raw_len} vs {ren_len} chars)"
        elif ratio >= 0.3:
            score, ev = 0.5, f"Solo el {ratio:.0%} del contenido esta en el HTML crudo: parte del sitio es invisible para crawlers de IA"
        else:
            score, ev = 0, f"CRITICO: solo el {ratio:.0%} del contenido existe sin JS. Para GPTBot/ClaudeBot este sitio esta casi vacio"
        out.append(R("4.1", "C4", "Contenido sin ejecutar JS", score, ev))
    else:
        # fallback heuristico sin render
        shell = raw_len < 800 and re.search(r'(?i)id=["\'](root|app|__next)["\']', ctx["home"]["body"] or "")
        score = 0 if shell else 0.5
        ev = ("Patron de SPA vacia detectado (div#root con <800 chars de texto)" if shell
              else f"Sin render disponible; el HTML crudo tiene {raw_len} chars de texto (revisar manualmente)")
        out.append(R("4.1", "C4", "Contenido sin ejecutar JS", score, ev, manual=True))

    # 4.2 precio/CTA presentes en el crudo (ecommerce)
    if ctx["typology"] == "ecommerce":
        prod = next((p for p in ctx["pages"] if p["bucket"] == "producto"
                     and p["fetch"]["status"] == 200), None)
        if prod:
            text = visible_text(prod["fetch"]["body"])
            has_price = bool(re.search(
                r"\d+[.,]\d{2}\s*(€|EUR|\$|USD|£|GBP|CHF)|(€|\$|£|CHF)\s*\d+", text))
            has_cta = bool(re.search(
                r"(?i)añadir|comprar|add to cart|buy now|cesta"
                r"|warenkorb|kaufen|einkaufswagen"     # DE
                r"|panier|acheter"                     # FR
                r"|carrello|acquista"                  # IT
                r"|carrinho"                           # PT
                r"|winkelwagen", text))                # NL
            score = 1 if has_price and has_cta else 0.5 if has_price or has_cta else 0
            ev = f"Ficha de producto sin JS: precio={'si' if has_price else 'NO'}, CTA compra={'si' if has_cta else 'NO'}"
        else:
            score, ev = 0, "Ninguna ficha de producto accesible en el muestreo"
        out.append(R("4.2", "C4", "Precio y CTA sin JS", score, ev))
    else:
        out.append(R("4.2", "C4", "Precio y CTA sin JS", None, "N/A (no es e-commerce)"))

    # 4.3 velocidad para bots (TTFB)
    ttfbs = [p["fetch"]["ttfb"] for p in ctx["pages"] if p["fetch"]["ttfb"]]
    if ctx["home"]["ttfb"]:
        ttfbs.append(ctx["home"]["ttfb"])
    if ttfbs:
        avg = sum(ttfbs) / len(ttfbs)
        score = 1 if avg < 0.8 else 0.5 if avg < 2 else 0
        ev = f"TTFB medio {avg:.2f}s en {len(ttfbs)} paginas (los fetchers en vivo abandonan >2s)"
    else:
        score, ev = None, "No medido"
    out.append(R("4.3", "C4", "Velocidad para bots (TTFB)", score, ev))

    # 4.4 deep-linking
    ok = sum(1 for p in ctx["pages"] if p["fetch"]["status"] == 200)
    total = max(len(ctx["pages"]), 1)
    score = 1 if ok == total else 0.5 if ok / total >= 0.7 else 0
    out.append(R("4.4", "C4", "Deep-linking estable", score,
                 f"{ok}/{total} URLs profundas responden 200 en acceso directo sin sesion"))

    # 4.5 API detectable
    api_hits = [p for p, c in ctx["wellknown"].items()
                if c == 200 and p in ("/openapi.json", "/swagger.json", "/api-docs")]
    out.append(R("4.5", "C4", "API publica detectable",
                 1 if api_hits else 0,
                 f"Spec encontrada: {', '.join(api_hits)}" if api_hits
                 else "Sin OpenAPI/Swagger en rutas estandar"))

    # 4.6 estabilidad visual (CLS): los rediseños dinamicos confunden a agentes
    # que toman capturas entre acciones. Se prefiere PageSpeed (dato de campo);
    # si no, el CLS que midio el navegador durante el render (dato de
    # laboratorio, siempre disponible cuando hay render). Antes solo existia PSI
    # y en produccion nunca se activaba: 4.6 era un factor que jamas puntuaba.
    cls = ctx.get("psi_cls")
    fuente = "PageSpeed (campo)"
    if cls is None:
        cls = ctx.get("render_cls")
        fuente = "medido en el navegador (laboratorio)"
    if cls is None:
        out.append(R("4.6", "C4", "Estabilidad visual (CLS)", None,
                     "No medido: sin render disponible en este analisis", manual=True))
    else:
        score = 1 if cls <= 0.1 else 0.5 if cls <= 0.25 else 0
        out.append(R("4.6", "C4", "Estabilidad visual (CLS)", score,
                     f"CLS={cls:.3f} (bueno <=0.1, {fuente}): los saltos de layout "
                     "confunden a un agente que captura pantalla entre acciones"))

    # 4.7 zonas de clic operables — medidas en el LAYOUT REAL, no en el HTML.
    # Un agente que pilota un navegador clica por coordenadas: un control de
    # 15px es un fallo de ejecucion aunque el marcado sea perfecto.
    # Se mide en la home Y en otras plantillas: la home suele ser la pagina mas
    # cuidada, y medir solo ahi daria un veredicto optimista que no representa
    # las fichas donde el agente realmente opera.
    medidas = []
    if (ctx.get("rendered_home") or {}).get("boxes"):
        medidas.append(("home", ctx["rendered_home"]["boxes"]))
    for rp in (ctx.get("rendered_pages") or []):
        medidas.append((rp["bucket"], rp["boxes"]))
    if not medidas:
        out.append(R("4.7", "C4", "Zonas de clic operables", None,
                     "Sin geometria de render disponible (requiere backend Playwright): "
                     "no se puede medir el tamano real de los controles", manual=True))
    else:
        MIN = 24  # px CSS: umbral WCAG 2.2 'Target Size (Minimum)'
        # Los enlaces en linea dentro de texto corrido quedan fuera: WCAG los
        # exceptua y un agente los acierta sin problema (son anchos). Contarlos
        # inflaria el fallo con falsos positivos.
        per_page, tot_targets, tot_problems, tot_inline = [], 0, 0, 0
        ejemplos = []
        for nombre, boxes in medidas:
            targets = [b for b in boxes if not b.get("inline")]
            tot_inline += len(boxes) - len(targets)
            if not targets:
                continue
            small = [b for b in targets if b["w"] < MIN or b["h"] < MIN]
            ambiguous = [b for b in targets
                         if not b["native"] and b.get("cursor") != "pointer"]
            problems = {id(b) for b in small} | {id(b) for b in ambiguous}
            tot_targets += len(targets)
            tot_problems += len(problems)
            per_page.append((nombre, len(targets), len(problems),
                             1 - len(problems) / len(targets)))
            ejemplos += [(nombre, b) for b in small[:2]]
        if not tot_targets:
            out.append(R("4.7", "C4", "Zonas de clic operables", None,
                         f"Solo se detectaron {tot_inline} enlaces en linea (exentos de "
                         "WCAG): sin controles medibles", manual=True))
        else:
            ratio_ok = 1 - (tot_problems / tot_targets)
            score = 1 if ratio_ok >= 0.95 else 0.5 if ratio_ok >= 0.8 else 0
            desglose = ", ".join(f"{n} {r:.0%} ({t} controles)"
                                 for n, t, _p, r in per_page)
            ev = (f"{tot_targets} controles medidos en {len(per_page)} plantilla(s) "
                  f"[{desglose}] ({tot_inline} enlaces en linea excluidos por la "
                  f"excepcion de WCAG): {ratio_ok:.0%} sin problemas")
            if ejemplos:
                muestra = ", ".join(f"{n}: {b['tag']} {b['w']}x{b['h']}px"
                                    + (f" ('{b['name'][:28]}')" if b["name"] else "")
                                    for n, b in ejemplos[:4])
                ev += (f". Por debajo de {MIN}x{MIN}px: {muestra}"
                       " — un agente que clica por coordenadas falla o pulsa el de al lado")
            # una plantilla claramente peor que el resto es un hallazgo por si mismo
            if len(per_page) > 1:
                peor = min(per_page, key=lambda x: x[3])
                mejor = max(per_page, key=lambda x: x[3])
                if mejor[3] - peor[3] >= 0.15:
                    ev += (f". La plantilla '{peor[0]}' esta notablemente peor que "
                           f"'{mejor[0]}' ({peor[3]:.0%} vs {mejor[3]:.0%})")
            if tot_problems == 0:
                ev += ". Todos los controles son accionables con fiabilidad"
            out.append(R("4.7", "C4", "Zonas de clic operables", score, ev))

    # 4.8 estados de error correctos — el soft-404 es el fallo agentico silencioso:
    # el humano lee "no encontrado", el agente solo mira el codigo de estado.
    ep = ctx.get("error_probe") or {}
    st = ep.get("status")
    if not st:
        out.append(R("4.8", "C4", "Estados de error correctos", None,
                     "La sonda de URL inexistente no obtuvo respuesta", manual=True))
    elif st == 200:
        out.append(R("4.8", "C4", "Estados de error correctos", 0,
                     f"SOFT-404: una URL inexistente devuelve HTTP 200"
                     + (" con texto de 'no encontrado' en el cuerpo" if ep.get("looks_missing") else "")
                     + ". Un agente interpreta 200 como exito y sigue operando con una "
                       "pagina vacia; el error se propaga sin que nadie lo detecte"))
    elif st in (301, 302, 307, 308):
        out.append(R("4.8", "C4", "Estados de error correctos", 0.5,
                     f"Una URL inexistente redirige (HTTP {st}) en lugar de devolver 404. "
                     "El agente acaba en otra pagina creyendo que llego a la pedida"))
    elif st in (404, 410):
        score = 1 if ep.get("has_recovery") else 0.5
        ev = (f"Correcto: HTTP {st} en URL inexistente. "
              + ("La pagina de error ofrece navegacion o buscador para recuperarse"
                 if ep.get("has_recovery")
                 else "Pero la pagina de error no ofrece navegacion ni buscador: "
                      "el agente se queda sin salida"))
        out.append(R("4.8", "C4", "Estados de error correctos", score, ev))
    else:
        out.append(R("4.8", "C4", "Estados de error correctos", 0.5,
                     f"Una URL inexistente devuelve HTTP {st}, que no es un 404/410 claro"))
    return out


# ---------------------------------------------------------------- C5 GEO

def run_c5(ctx):
    out = []
    content_pages = [p for p in ctx["pages"]
                     if p["bucket"] in ("blog", "servicio", "otras")
                     and p["fetch"]["status"] == 200] or \
                    [p for p in ctx["pages"] if p["fetch"]["status"] == 200]

    # 5.1 respuesta directa arriba — analisis de densidad informativa vs relleno.
    # Un LLM cita el bloque tras el H1 si contiene RESPUESTA (datos, definiciones),
    # no marketing. Medimos ambos de forma determinista y reproducible.
    FLUFF = re.compile(
        r"(?i)\b(bienvenid[oa]s?|l[ií]der(es)?|pasi[oó]n|comprometid[oa]s?|excelencia|"
        r"innovador(a|es)?|referentes?|de confianza|soluciones? integrales?|a tu medida|"
        r"desde hace mas de|los mejores)\b")
    INFO = re.compile(r"\d[\d.,]*\s*(%|€|\$|años|dias|min)?|\b(es una?|son|significa|"
                      r"consiste en|se define|sirve para|permite)\b", re.I)
    page_results = []
    for p in content_pages[:5]:
        body = p["fetch"]["body"]
        m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>(.*?)(?=<h2[\s>]|$)", body)
        if not m:
            page_results.append((p["url"], 0, "sin H1 localizable"))
            continue
        first = visible_text(m.group(2))[:900]
        words = len(first.split())
        info_hits = len(INFO.findall(first))
        fluff_hits = len(FLUFF.findall(first))
        if 25 <= words <= 320 and info_hits >= 2 and fluff_hits <= 1:
            page_results.append((p["url"], 1, f"{words} palabras, {info_hits} datos, {fluff_hits} relleno"))
        elif words > 0 and info_hits >= 1:
            page_results.append((p["url"], 0.5, f"{words} palabras, {info_hits} datos, {fluff_hits} relleno"))
        else:
            page_results.append((p["url"], 0, f"{words} palabras, {info_hits} datos, {fluff_hits} relleno"))
    if page_results:
        avg = sum(s for _, s, _ in page_results) / len(page_results)
        score = 1 if avg >= 0.8 else 0.5 if avg >= 0.4 else 0
        worst = min(page_results, key=lambda x: x[1])
        ev = (f"{sum(1 for _, s, _ in page_results if s == 1)}/{len(page_results)} paginas con "
              f"respuesta directa tras el H1 (datos>=2, relleno<=1). "
              f"Peor: {worst[0].split('/')[-1] or worst[0][-40:]} ({worst[2]})")
    else:
        score, ev = 0, "Sin paginas de contenido analizables"
    out.append(R("5.1", "C5", "Respuesta directa arriba", score, ev))

    # 5.2 estructura chunkeable — secciones autocontenidas + jerarquia de headings.
    # Medimos cada seccion H2/H3: titulo descriptivo (>=3 palabras o pregunta) y
    # cuerpo sustancial (30-400 palabras), mas saltos de jerarquia (h2->h4).
    page_results = []
    for p in content_pages[:5]:
        body = p["fetch"]["body"]
        heads = [(m.group(1), visible_text(m.group(2)), m.end())
                 for m in re.finditer(r"(?is)<h([23])[^>]*>(.*?)</h\1>", body)]
        if not heads:
            page_results.append((p["url"], 0, "sin H2/H3"))
            continue
        ok_sections = 0
        for i, (_lvl, htext, end) in enumerate(heads):
            nxt = heads[i + 1][2] if i + 1 < len(heads) else len(body)
            sec_words = len(visible_text(body[end:nxt]).split())
            descriptive = len(htext.split()) >= 3 or htext.strip().endswith("?")
            if descriptive and 25 <= sec_words <= 450:
                ok_sections += 1
        levels = [int(m.group(1)) for m in re.finditer(r"(?i)<h([1-4])[\s>]", body)]
        jumps = sum(1 for a, b in zip(levels, levels[1:]) if b - a > 1)
        ratio = ok_sections / len(heads)
        s = 1 if ratio >= 0.6 and jumps == 0 else 0.5 if ratio >= 0.35 else 0
        page_results.append((p["url"], s,
                             f"{ok_sections}/{len(heads)} secciones autocontenidas, {jumps} saltos de jerarquia"))
    if page_results:
        avg = sum(s for _, s, _ in page_results) / len(page_results)
        score = 1 if avg >= 0.8 else 0.5 if avg >= 0.4 else 0
        detail = "; ".join(f"{u.split('/')[-1] or u[-30:]}: {d}" for u, _, d in page_results[:3])
        ev = f"Analizadas {len(page_results)} paginas seccion a seccion. {detail}"
    else:
        score, ev = 0, "Sin paginas de contenido analizables"
    out.append(R("5.2", "C5", "Estructura chunkeable (H2/H3)", score, ev))

    # 5.3 E-E-A-T verificable
    blog_pages = [p for p in ctx["pages"] if p["bucket"] == "blog" and p["fetch"]["status"] == 200]
    if blog_pages:
        hits = 0
        for p in blog_pages:
            body = p["fetch"]["body"]
            valid, _ = jsonld_blocks(body)
            has_author = bool(find_nodes(valid, "Person")) or '"author"' in json.dumps(valid) \
                or re.search(r"(?i)class=[\"'][^\"']*(author|byline)", body)
            has_date = '"datePublished"' in json.dumps(valid) or re.search(r"(?i)<time[\s>]", body)
            hits += 1 if (has_author and has_date) else 0.5 if (has_author or has_date) else 0
        ratio = hits / len(blog_pages)
        score = 1 if ratio >= 0.85 else 0.5 if ratio >= 0.4 else 0
        ev = f"Autoria+fecha verificables en {hits}/{len(blog_pages)} articulos muestreados"
    else:
        score, ev = None, "Sin paginas de blog en el muestreo"
    out.append(R("5.3", "C5", "E-E-A-T verificable", score, ev))

    # (la citacion real en respuestas de IA — el antiguo 5.4 — se mide con Clicandseo)

    # 5.5 llms.txt (higiene, peso bajo). Se mide CALIDAD, no solo presencia:
    # un volcado automatico de cientos de KB cumple la letra del estandar y
    # falla su proposito, que es ser un indice curado.
    llms = ctx["wellknown"].get("/llms.txt", 0)
    if llms != 200:
        out.append(R("5.5", "C5", "llms.txt (higiene)", 0,
                     "Sin llms.txt (peso bajo: el 97% nunca se leen, pero es higiene barata)"))
    else:
        m = (ctx.get("wellknown_meta") or {}).get("/llms.txt") or {}
        kb = (m.get("bytes") or 0) / 1024
        volcado = kb > 200 or m.get("autogenerado")
        if volcado:
            motivos = []
            if kb > 200:
                motivos.append(f"{kb:.0f} KB")
            if m.get("autogenerado"):
                motivos.append("declara estar generado por un plugin")
            out.append(R("5.5", "C5", "llms.txt (higiene)", 0.5,
                         f"llms.txt presente pero parece un volcado automatico "
                         f"({', '.join(motivos)}, {m.get('enlaces', 0)} enlaces). El estandar "
                         "pide un indice CURADO que oriente al modelo; un dump de todas las "
                         "URLs cumple la forma y no la funcion"))
        else:
            out.append(R("5.5", "C5", "llms.txt (higiene)", 1,
                         f"llms.txt presente y con pinta de estar curado "
                         f"({kb:.0f} KB, {m.get('enlaces', 0)} enlaces)"))

    # 5.6 negociacion de contenido Markdown (Accept: text/markdown)
    mdn = ctx.get("md_negotiation") or {}
    if mdn.get("is_markdown"):
        score, ev = 1, f"Sirve Markdown a agentes via content negotiation (Content-Type: {mdn.get('content_type')})"
    else:
        score, ev = 0, (f"Con Accept: text/markdown responde {mdn.get('content_type') or 'HTML'} "
                        "(solo el 3,9% de sitios lo soporta: diferenciador barato)")
    out.append(R("5.6", "C5", "Negociacion de contenido Markdown", score, ev))
    return out


# ---------------------------------------------------------------- C6 capacidades

def run_c6(ctx):
    out = []
    wk = ctx["wellknown"]

    # 6.1 superficie agentica (.well-known + endpoints + protocolos emergentes)
    agentic_paths = ["/.well-known/mcp.json", "/.well-known/api-catalog",
                     "/.well-known/oauth-authorization-server",
                     "/.well-known/oauth-protected-resource",
                     "/.well-known/ai-plugin.json", "/mcp", "/ask", "/agents.json",
                     "/.well-known/agent.json", "/.well-known/agent-card.json",
                     "/auth.md", "/.well-known/skills"]
    hits = [p for p in agentic_paths if wk.get(p) == 200]
    home_html = ctx["home"]["body"] or ""
    webmcp = bool(re.search(r"(?i)webmcp|navigator\.modelContext|model-context-protocol",
                            home_html))
    if webmcp:
        hits.append("WebMCP (en pagina)")
    out.append(R("6.1", "C6", "Superficie agentica (MCP/A2A/WebMCP)",
                 1 if hits else 0,
                 f"Expone: {', '.join(hits)}" if hits
                 else "Sin superficie agentica: ni MCP, ni A2A agent.json, ni WebMCP (<15 sitios del top 200k la tienen: ventaja de primero)"))

    # 6.2 operabilidad de formularios — analisis estatico PROFUNDO por formulario:
    # vinculacion label for=id VERIFICADA contra los id reales, autocomplete,
    # boton de envio real y CAPTCHA. No se envian formularios reales (etica:
    # generaria leads/spam en sitios de terceros); se declara en metodologia.
    forms = []
    for src in [ctx["home"]] + [p["fetch"] for p in ctx["pages"][:4]]:
        forms += re.findall(r"(?is)<form[^>]*>.*?</form>", src["body"] or "")
    if forms:
        total_fields = bound_fields = aria_fields = autocomp = with_submit = captcha = 0
        for f in forms[:12]:
            fields = re.findall(
                r"(?is)<(input(?![^>]*type=[\"'](?:hidden|submit|button))|select|textarea)\b[^>]*>", f)
            ids = set(re.findall(r"(?i)<(?:input|select|textarea)[^>]+id=[\"']([^\"']+)", f))
            label_fors = set(re.findall(r"(?i)<label[^>]+for=[\"']([^\"']+)", f))
            bound_fields += len(ids & label_fors)  # vinculacion REAL for=id
            aria_fields += len(re.findall(r"(?i)<(?:input|select|textarea)[^>]+aria-label=", f))
            total_fields += len(fields)
            autocomp += len(re.findall(r"(?i)autocomplete=[\"'](?!off)", f))
            if re.search(r"(?i)<button[^>]*type=[\"']submit|<input[^>]+type=[\"']submit|<button(?![^>]*type=)", f):
                with_submit += 1
            if re.search(r"(?i)recaptcha|hcaptcha|turnstile", f):
                captcha += 1
        n = len(forms[:12])
        labeled = bound_fields + aria_fields
        coverage = labeled / total_fields if total_fields else 0
        submit_ratio = with_submit / n if n else 0
        if coverage >= 0.7 and submit_ratio >= 0.7 and captcha == 0:
            score = 1
        elif coverage >= 0.35 and submit_ratio >= 0.5:
            score = 0.5
        else:
            score = 0
        ev = (f"{n} formularios, {total_fields} campos: {bound_fields} vinculados for=id (verificado), "
              f"{aria_fields} aria-label, {autocomp} autocomplete, {with_submit}/{n} con submit real, "
              f"{captcha} con CAPTCHA. [No se envian formularios reales por etica]")
    else:
        score, ev = 0.5, "Sin formularios detectados en las paginas muestreadas"
    out.append(R("6.2", "C6", "Formularios operables por agentes", score, ev))

    # 6.3 tarea completada por agentes REALES (browser-use con ChatGPT/Gemini/Claude)
    at = ctx.get("agent_tests")
    agents = (at or {}).get("agents") or {}
    # "no_verificable" fuera junto a "no_disponible": en ambos casos NO hemos
    # medido nada. Si el navegador solo recibio una pagina de bloqueo, puntuar
    # 6.3 a 0 seria afirmar "un agente no puede usar tu web" sin haberlo visto.
    valid = {k: v for k, v in agents.items()
             if v.get("outcome") not in ("no_disponible", "no_verificable", None)}
    if valid:
        ok = sum(1 for v in valid.values() if v["outcome"] == "conseguido")
        okf = sum(1 for v in valid.values() if v["outcome"] == "conseguido_con_friccion")
        total = len(valid)
        # progreso medio por hitos: distingue "se atasca al entrar" de
        # "llega al final y falla en el ultimo paso", que no son lo mismo
        progs = [v.get("progreso") or {} for v in valid.values()]
        ratios = [p["alcanzados"] / p["total"] for p in progs if p.get("total")]
        avg = sum(ratios) / len(ratios) if ratios else None
        # consistencia entre repeticiones: un agente LLM no es determinista, asi
        # que "funciono una vez" no es evidencia de que la web funcione.
        consist = [v.get("consistencia") for v in valid.values()
                   if v.get("consistencia") is not None]
        tasa = sum(consist) / len(consist) if consist else None
        inconsistentes = [k for k, v in valid.items() if v["outcome"] == "inconsistente"]
        if tasa is not None:
            # el score sale de la tasa real de exito sobre TODOS los intentos
            score = 1 if tasa >= 0.95 else 0.5 if tasa >= 0.4 else 0
            if score == 0 and avg is not None and avg >= 0.5:
                score = 0.5
        elif ok == total:
            score = 1
        elif (ok + okf) > 0:
            score = 0.5
        elif avg is not None and avg >= 0.5:
            score = 0.5  # ningun agente termino, pero todos recorrieron medio camino
        else:
            score = 0
        per = ", ".join(
            f"{k}: {v['outcome']}"
            + (f" {v['exitos']}/{v['intentos']}" if v.get("intentos") else "")
            + (f" ({(v.get('progreso') or {}).get('alcanzados')}/"
               f"{(v.get('progreso') or {}).get('total')} pasos)"
               if (v.get("progreso") or {}).get("total") else "")
            for k, v in valid.items())
        reps = at.get("repeticiones")
        ev = (f"Tarea '{at['typology']}' ejecutada por {total} agente(s) reales"
              + (f", {reps} intentos cada uno" if reps and reps > 1 else "") + f" — {per}.")
        if tasa is not None and reps and reps > 1:
            ev += f" Tasa de exito global: {tasa:.0%}."
        if inconsistentes:
            ev += (f" ATENCION: {', '.join(inconsistentes)} completo la tarea solo en "
                   "algunos intentos. Una web que funciona a veces es, para un agente, "
                   "peor que una que falla siempre: el resultado no es predecible.")
        if avg is not None:
            ev += f" Recorrido medio: {avg:.0%} de los pasos de la tarea."
        # donde se atascan todos = el cuello de botella real del sitio
        atascos = [p["pendientes"][0] for p in progs if p.get("pendientes")]
        if atascos and len(set(atascos)) == 1 and len(atascos) > 1:
            ev += f" Todos se atascan en el mismo punto: {atascos[0]}."
        # Si TODOS los agentes se cayeron por controles que no responden al clic
        # programatico, no afirmamos que la web sea inoperable: puede ser un
        # limite de nuestro harness. Se marca para revision manual.
        if valid and all(v.get("limite_de_metodo") for v in valid.values()):
            out[-1] = R("6.3", "C6", "Tarea completada por un agente real", None,
                        ev + " AVISO DE METODO: todos los intentos se cayeron por "
                             "controles que no respondieron al clic programatico "
                             "(selectores a medida, componentes JS). Nuestro harness "
                             "clica por selector; los agentes comerciales usan vision "
                             "y los toleran mejor. NO es concluyente: requiere prueba "
                             "manual antes de afirmar que la web no es operable.",
                        manual=True)
            return out
        # honestidad: lo que NO evaluamos por politica propia no se cuenta como fallo
        no_eval = at.get("hitos_no_evaluados") or []
        if no_eval:
            ev += (f" No evaluado por politica de la prueba (no por fallo de la web): "
                   f"{', '.join(no_eval)}.")
        ev += " Detalle y registro de pasos en la pestaña Evidencias."
        out.append(R("6.3", "C6", "Tarea completada por un agente real", score, ev))
    else:
        # Se ejecutaron y NINGUNA pudo ver la web. Decir "no ejecutado" aqui
        # seria falso, y decir "no conseguido" seria peor: acusaria a la web.
        noverif = [k for k, v in agents.items()
                   if v.get("outcome") == "no_verificable"]
        if noverif:
            det = next(v.get("detail") for v in agents.values()
                       if v.get("outcome") == "no_verificable")
            out.append(R("6.3", "C6", "Tarea completada por un agente real", None,
                         f"Ejecutado con {', '.join(noverif)}, sin resultado medible: "
                         f"{det} No se puntua: no hay evidencia agentica en ningun "
                         "sentido, ni a favor ni en contra.", manual=True))
            return out
        # el mensaje cambia si el usuario YA las pidió: decirle "actívalas"
        # cuando acaba de activarlas seria desconcertante
        if ctx.get("agentes_pendientes"):
            ev_63 = ("Pendiente de ejecutar: pulsa «Simular agentes» en el informe. "
                     "Corre en segundo plano (10-15 min) y al terminar actualiza este "
                     "check y la puntuacion global sin repetir el resto del analisis")
        else:
            ev_63 = ("No ejecutado (activar 'Pruebas agenticas' en el analisis, o hacerlo "
                     "manual con Operator/Claude)")
        out.append(R("6.3", "C6", "Tarea completada por un agente real", None,
                     ev_63, manual=True))

    # 6.4 autenticacion operable por un agente. Jerarquia: OAuth delegado (el
    # agente actua en nombre del usuario SIN manejar su contrasena) > formulario
    # estandar bien marcado > formulario opaco o con CAPTCHA (agente bloqueado).
    oauth = [p for p in ("/.well-known/oauth-authorization-server",
                         "/.well-known/oauth-protected-resource") if wk.get(p) == 200]
    lp = ctx.get("login_probe") or {}
    if oauth:
        out.append(R("6.4", "C6", "Autenticacion operable por agentes", 1,
                     f"OAuth descubrible en {', '.join(oauth)}: un agente puede obtener "
                     "permiso delegado sin manejar la contrasena del usuario (el patron correcto)"))
    elif not lp.get("found"):
        out.append(R("6.4", "C6", "Autenticacion operable por agentes", None,
                     "El sitio no expone area de acceso: no aplica"))
    else:
        body = lp.get("body") or ""
        has_pwd = bool(re.search(r'(?i)<input[^>]+type=["\']password', body))
        ac_user = bool(re.search(r'(?i)autocomplete=["\'](username|email)', body))
        ac_pwd = bool(re.search(r'(?i)autocomplete=["\'](current-password|password)', body))
        captcha = bool(re.search(r"(?i)recaptcha|hcaptcha|turnstile", body))
        social = bool(re.search(r"(?i)(sign|log)[ -]?in with (google|apple|microsoft)|"
                                r"continuar con (google|apple)", body))
        n_cand = len(lp.get("intentos") or [])
        via = " (formulario visible solo tras renderizar JS)" if lp.get("via") == "render" else ""
        if not has_pwd:
            out.append(R("6.4", "C6", "Autenticacion operable por agentes", None,
                         f"Probados {n_cand} candidatos de acceso; en {lp['url']} no hay "
                         "formulario de contrasena ni siquiera tras renderizar (login via "
                         "terceros o muro externo): no evaluable automaticamente", manual=True))
            return out
        if captcha:
            score = 0
            ev = ("El acceso esta protegido por CAPTCHA: un agente legitimo del propio "
                  "usuario no puede autenticarse. Sin OAuth ni alternativa, el area "
                  "privada es territorio cerrado para agentes")
        elif ac_user and ac_pwd:
            score = 0.5
            ev = ("Formulario de acceso correctamente marcado (autocomplete username + "
                  "current-password): un agente con credenciales puede rellenarlo. "
                  "Falta OAuth para permiso delegado sin compartir contrasena")
        else:
            score = 0
            faltan = [n for n, v in (("autocomplete de usuario", ac_user),
                                     ("autocomplete de contrasena", ac_pwd)) if not v]
            ev = (f"Formulario de acceso sin {' ni '.join(faltan)}: un agente no puede "
                  "identificar con fiabilidad que campo es cual")
        if social:
            ev += ". Ofrece acceso social (Google/Apple), que anade una capa mas de friccion al agente"
        ev += f". Evaluado en {lp['url']}{via}"
        out.append(R("6.4", "C6", "Autenticacion operable por agentes", score, ev))
    return out


# ---------------------------------------------------------------- C7 comercio

def run_c7(ctx):
    out = []

    # 7.4 protocolos de comercio emergentes — INFORMATIVO, no puntua (score None).
    # Ni Cloudflare los puntua: no hay ruta de descubrimiento estandarizada consolidada.
    wk = ctx["wellknown"]
    proto_hits = [p for p in ("/.well-known/x402", "/.well-known/ucp", "/.well-known/mpp")
                  if wk.get(p) == 200]
    saw_402 = any(code == 402 for code in ctx["bot_matrix"].values())
    if saw_402:
        proto_hits.append("respuestas HTTP 402 a bots (señal x402/pay-per-crawl)")
    out.append(R("7.4", "C7", "Protocolos de comercio emergentes (x402/UCP/MPP)", None,
                 ("Detectado: " + ", ".join(proto_hits)) if proto_hits
                 else "Sondeados x402/UCP/MPP sin hallazgos (informativo: estos protocolos aun no puntuan, tampoco en Cloudflare)"))

    if ctx["typology"] != "ecommerce":
        out.append(R("7.1", "C7", "Comercio agentico", None, "N/A (no es e-commerce)"))
        out.append(R("7.5", "C7", "Politica de envio legible por maquina", None, "N/A (no es e-commerce)"))
        out.append(R("7.6", "C7", "Politica de devoluciones legible por maquina", None, "N/A (no es e-commerce)"))
        return out

    prod_pages = [p for p in ctx["pages"] if p["bucket"] == "producto"
                  and p["fetch"]["status"] == 200]
    corpus = " ".join(p["fetch"]["body"] for p in prod_pages) + (ctx["home"]["body"] or "")

    # 7.1 plataforma con feed / catalogo estructurado
    platform = None
    # marcadores a nivel de asset, no la palabra suelta (stripe.com menciona
    # "WooCommerce" como cliente y salia detectada como tienda WooCommerce)
    # VTEX estaba en ECOM_STRONG de discovery pero NO aquí: una tienda VTEX se
    # clasificaba como e-commerce y luego 7.1 decía "sin plataforma reconocible".
    # Shopware y Salesforce Commerce (demandware) añadidos por la misma razón.
    for marker, name in (("cdn.shopify", "Shopify"), ("plugins/woocommerce", "WooCommerce"),
                         ("woocommerce-page", "WooCommerce"),
                         ("prestashop", "PrestaShop"), ("magento", "Magento"),
                         ("bigcommerce", "BigCommerce"),
                         ("vtexassets", "VTEX"), ("vtexcommercestable", "VTEX"),
                         ("/widgets/emotion", "Shopware"), ("shopware.", "Shopware"),
                         ("demandware.static", "Salesforce Commerce Cloud"),
                         ("/on/demandware", "Salesforce Commerce Cloud")):
        if marker in corpus.lower():
            platform = name
            break
    prods_ok = 0
    for p in prod_pages:
        valid, _ = jsonld_blocks(p["fetch"]["body"])
        if find_nodes(valid, "Product"):
            prods_ok += 1
    if platform and prods_ok:
        score, ev = 1, f"Plataforma {platform} (feed disponible) + Product schema en {prods_ok} fichas"
    elif platform or prods_ok:
        score, ev = 0.5, f"Plataforma={platform or 'custom'}, fichas con Product schema={prods_ok}"
    else:
        score, ev = 0, "Sin plataforma reconocible ni catalogo estructurado detectable"
    out.append(R("7.1", "C7", "Feed/catalogo estructurado", score, ev))

    # 7.2 consistencia precio JSON-LD vs visible (anti-alucinacion)
    checked, consistent = 0, 0
    for p in prod_pages:
        valid, _ = jsonld_blocks(p["fetch"]["body"])
        for prod in find_nodes(valid, "Product"):
            offers = prod.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = str(offers.get("price", "")).strip()
            if not price:
                continue
            checked += 1
            page_text = visible_text(p["fetch"]["body"])
            variants = {price, price.replace(".", ","), price.rstrip("0").rstrip(".,")}
            if any(v and v in page_text for v in variants):
                consistent += 1
            break
    result_72 = None
    if checked:
        score = 1 if consistent == checked else 0
        ev = f"Precio del schema coincide con el visible en {consistent}/{checked} fichas"
        if score == 0:
            ev += " -> RIESGO de que un agente sirva un precio equivocado"
        result_72 = R("7.2", "C7", "Consistencia de precio (anti-alucinacion)", score, ev)
        result_72["inconsistent"] = consistent < checked
    else:
        result_72 = R("7.2", "C7", "Consistencia de precio (anti-alucinacion)", 0,
                      "Ningun precio en JSON-LD que verificar (ausencia, no inconsistencia)")
        result_72["inconsistent"] = False
    out.append(result_72)

    # 7.3 preparacion ACP (PSP compatible)
    has_stripe = "js.stripe.com" in corpus or "stripe.com/v3" in corpus
    is_shopify = platform == "Shopify"
    if is_shopify:
        score, ev = 0.5, "Shopify: en el pipeline tecnico de Instant Checkout; falta alta en el programa de OpenAI (confirmar con cliente)"
    elif has_stripe:
        score, ev = 0.5, "Stripe detectado: PSP compatible con la Delegated Payment Spec de ACP; integracion no iniciada"
    else:
        score, ev = 0, "Sin PSP compatible con ACP detectado (Stripe/Shopify)"
    out.append(R("7.3", "C7", "Preparacion ACP / checkout agentico", score, ev, manual=True))

    # 7.5 / 7.6 datos operativos de la compra. Un agente que decide por el usuario
    # necesita plazo, coste y condiciones de devolucion ANTES de comprar. Si solo
    # estan en un PDF o en prosa legal, el agente los ignora o los inventa.
    def _policy_check(cid, nombre, schema_keys, schema_type, text_re, url_re, humano):
        found_schema, sample = [], None
        for p in prod_pages + [{"fetch": ctx["home"]}]:
            valid, _ = jsonld_blocks(p["fetch"]["body"])
            for node in find_nodes(valid, "Product") + find_nodes(valid, "Offer"):
                offers = node.get("offers") or node
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if not isinstance(offers, dict):
                    continue
                for key in schema_keys:
                    val = offers.get(key) or node.get(key)
                    if val:
                        found_schema.append(key)
                        sample = val if isinstance(val, dict) else {"_": val}
            if find_nodes(valid, schema_type):
                found_schema.append(schema_type)
        if found_schema:
            campos = []
            if isinstance(sample, dict):
                campos = [k for k in sample.keys() if not k.startswith("@") and k != "_"]
            score = 1 if campos else 0.5
            ev = (f"Marcado {schema_type} presente ({', '.join(sorted(set(found_schema))[:3])})"
                  + (f" con campos: {', '.join(campos[:6])}" if campos
                     else " pero sin detalle interno (plazo/coste): un agente lo lee pero no puede usarlo"))
            return R(cid, "C7", nombre, score, ev)
        # sin schema: ¿al menos existe la informacion para un humano?
        page_text = visible_text(corpus)
        has_text = bool(re.search(text_re, page_text))
        has_page = bool(re.search(url_re, corpus, re.I))
        if has_text or has_page:
            return R(cid, "C7", nombre, 0,
                     f"La informacion de {humano} existe para un humano "
                     f"({'texto en la ficha' if has_text else 'pagina dedicada'}) pero NO esta "
                     f"en {schema_type}: un agente no puede leerla ni compararla antes de comprar")
        return R(cid, "C7", nombre, 0,
                 f"Sin informacion de {humano} detectable, ni estructurada ni visible. "
                 f"Un agente que compare opciones descartara esta tienda por falta de datos")

    out.append(_policy_check(
        "7.5", "Politica de envio legible por maquina",
        ["shippingDetails"], "OfferShippingDetails",
        # Multiidioma: con solo ES/EN, a zalando.de le dijimos "Sin informacion
        # de envio detectable, ni estructurada ni visible" — una acusacion
        # que describia nuestros patrones, no su web.
        r"(?i)(gastos de env[ií]o|env[ií]o gratis|plazo de entrega|free shipping|delivery time"
        r"|versandkosten|kostenloser versand|lieferzeit|lieferung"        # DE
        r"|frais de (port|livraison)|livraison gratuite|d[ée]lai de livraison"  # FR
        r"|spese di spedizione|spedizione gratuita|tempi di consegna"     # IT
        r"|portes de envio|envio gr[áa]tis|prazo de entrega"              # PT
        r"|verzendkosten|gratis verzending)",                             # NL
        r"/(envios?|shipping|entrega|gastos-de-envio"
        r"|versand|lieferung|versandkosten"          # DE
        r"|livraison|frais-de-port"                  # FR
        r"|spedizion\w*|consegna"                    # IT
        r"|entregas?"                                # PT
        r"|verzending|bezorging)", "envio"))         # NL

    out.append(_policy_check(
        "7.6", "Politica de devoluciones legible por maquina",
        ["hasMerchantReturnPolicy"], "MerchantReturnPolicy",
        r"(?i)(devoluci[oó]n|derecho de desistimiento|return policy|30 d[ií]as|14 d[ií]as"
        r"|r[üu]ckgabe|widerruf|r[üu]cksendung|retoure|30 tage|14 tage"    # DE
        r"|retours?|droit de r[ée]tractation|30 jours|14 jours"            # FR
        r"|resi|reso|diritto di recesso|30 giorni|14 giorni"               # IT
        r"|devolu[çc][õo]es|30 dias|14 dias"                               # PT
        r"|retourneren|herroepingsrecht)",                                 # NL
        r"/(devoluciones?|returns?|cambios-y-devoluciones"
        r"|rueckgabe|r%C3%BCckgabe|retoure|widerruf|ruecksendung"  # DE
        r"|retours?|retractation"                                  # FR
        r"|resi|recesso"                                           # IT
        r"|devolucoes|devolu%C3%A7%C3%B5es"                        # PT
        r"|retourneren)", "devoluciones"))                         # NL
    return out


def run_all(ctx):
    results = []
    for fn in (run_c1, run_c2, run_c3, run_c4, run_c5, run_c6, run_c7):
        results.extend(fn(ctx))
    return results
