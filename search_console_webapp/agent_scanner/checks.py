"""Checks C1-C7 del framework de auditoria (seccion 11 del informe).

Cada check devuelve:
  {id, cat, name, score (0 | 0.5 | 1 | None=N/A), evidence, manual (bool)}

`manual=True` marca checks heuristicos que conviene revisar con ojo humano
antes de entregar al cliente.
"""
import json
import re
from urllib.parse import urlparse

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
        score, ev = 1, "robots.txt 200 and parseable"
    elif rb["status"] == 200 and rb["is_html"]:
        score, ev = 0, "robots.txt returns HTML (typical error of a SPA that routes everything)"
    else:
        score, ev = 0, f"robots.txt HTTP {rb['status']}"
    out.append(R("1.1", "C1", "Valid robots.txt", score, ev))

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
        score, ev = 0, f"Blocks LIVE search bots: {', '.join(live_blocked)} (opting itself out of AI answers)"
    elif len(principales_nombrados) >= 2:
        score = 1
        ev = (f"Explicit policy on the bots that matter "
              f"({len(principales_nombrados)}): {', '.join(principales_nombrados[:6])}")
    elif ai_bots_named:
        score = 0.5
        faltan = [b for b in PRINCIPALES
                  if not any(b in ua for ua in groups)]
        ev = (f"Only names {', '.join(ai_bots_named[:4])}, but says NOTHING about "
              f"the crawlers that decide your presence in AI answers "
              f"({', '.join(faltan[:4])}): a half-made decision")
    else:
        score, ev = 0.5, "No per-bot rules for AI bots (everything allowed by default, no deliberate decision)"
    out.append(R("1.2", "C1", "AI bot policy", score, ev))

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
        ev = f"robots.txt allows it but the server blocks: {', '.join(mismatches)} (human=200)"
        if any(c.endswith(("=503", "=429", "=500", "=502")) for c in mismatches):
            ev += (". It also responds with a server error instead of a 403: the bot "
                   "reads it as 'come back later' and will retry indefinitely, "
                   "without anyone noticing it's blocked")
    elif not human_ok:
        score, ev = 0.5, f"Not even the human UA gets a 200 ({matrix.get('_human')}): very aggressive WAF, review it"
    else:
        score = 1
        codes = ", ".join(f"{k}={v}" for k, v in matrix.items() if k != "_human")
        ev = f"Declared access matches actual access ({codes})"
    out.append(R("1.3", "C1", "Declared vs actual blocking", score, ev))

    # 1.4 sitemap presente y fresco. "Bloqueado" != "ausente": si las rutas de
    # sitemap devuelven 403/timeout no podemos afirmar que falte (zalando.es).
    sm = ctx["sitemap"]
    if sm["found"] and ctx["sitemap_fresh"]:
        out.append(R("1.4", "C1", "Fresh sitemap.xml", 1,
                     f"Sitemap with {len(sm['urls'])} URLs and a recent lastmod (<90 days)"))
    elif sm["found"]:
        out.append(R("1.4", "C1", "Fresh sitemap.xml", 0.5,
                     f"Sitemap with {len(sm['urls'])} URLs but no recent lastmod"))
    elif sm.get("bloqueado"):
        out.append(R("1.4", "C1", "Fresh sitemap.xml", None,
                     f"The sitemap paths don't respond to automated access "
                     f"(HTTP {sm.get('estados')}): it may exist and be blocked, "
                     "so we can't claim it's missing", manual=True))
    else:
        out.append(R("1.4", "C1", "Fresh sitemap.xml", 0, "No sitemap.xml found"))

    # 1.5 Link headers (RFC 8288)
    link_h = re.search(r"(?im)^link:\s*(.+)$", ctx["home"]["headers"] or "")
    out.append(R("1.5", "C1", "Link headers (RFC 8288)",
                 1 if link_h else 0,
                 link_h.group(1)[:120] if link_h else "No Link headers (a minority today; an opportunity, not an error)"))

    # 1.6 contenido clave accesible sin login.
    # Cuenta el acceso DIRECTO (_status_directo): una pagina que solo Jina pudo
    # leer NO es accesible para el agente que la pide sin sesion, aunque su
    # cuerpo este rescatado para los checks de contenido. La politica del
    # proyecto es que en 1.6/2.4/4.4 el bloqueo ES el hallazgo.
    pages = ctx["pages"]
    ok = sum(1 for p in pages
             if p["fetch"].get("_status_directo", p["fetch"]["status"]) == 200
             and len(visible_text(p["fetch"]["body"])) > 500)
    total = max(len(pages), 1)
    ratio = ok / total
    score = 1 if ratio >= 0.85 else 0.5 if ratio >= 0.5 else 0
    out.append(R("1.6", "C1", "Content accessible without login",
                 score, f"{ok}/{total} sampled pages return useful content without a session"))

    # 1.7 DNS para descubrimiento de agentes (DNS-AID, experimental — peso bajo)
    aid = ctx.get("dns_aid")
    out.append(R("1.7", "C1", "DNS-AID",
                 1 if aid else 0,
                 aid or "No _aid/_agent TXT records (experimental standard: almost nobody has it yet)"))

    # 1.8 Metadatos de cita: canonical, idioma y Open Graph. Es lo minimo que
    # un sistema usa para identificar la pagina al citarla; sin canonical las
    # citas se reparten entre variantes de URL, sin lang el idioma se adivina,
    # y sin og:image/og:type el preview sale roto.
    # Solo sobre portada vista en directo (http/render): el rescate de Jina
    # devuelve el DOM limpio SIN las metas del <head>. Caso real
    # (mediamarkt.es, 2026-09-01): su home directa lleva canonical+og:image+
    # og:type y sobre el cuerpo de Jina afirmabamos "faltan" los tres.
    if ctx["home"].get("_via", "http") not in ("http", "render"):
        out.append(R("1.8", "C1", "Citation metadata", None,
                     "The home page could only be read via the fallback (Jina), which doesn't "
                     "keep the <head> metas: not measurable"))
        return out
    home_body = ctx["home"]["body"] or ""
    senales_meta = {
        "canonical": bool(re.search(r"(?i)<link[^>]+rel=[\"']canonical", home_body)),
        "lang": bool(re.search(r"(?i)<html[^>]+lang=[\"']?[a-z]{2}", home_body)),
        "og:image": bool(re.search(r"(?i)(property|name)=[\"']og:image", home_body)),
        "og:type": bool(re.search(r"(?i)(property|name)=[\"']og:type", home_body)),
    }
    presentes = sum(senales_meta.values())
    faltan = [n for n, hay in senales_meta.items() if not hay]
    score = 1 if presentes == 4 else 0.5 if presentes >= 2 else 0
    out.append(R("1.8", "C1", "Citation metadata", score,
                 "canonical + lang + og:image + og:type present on the home page"
                 if not faltan else
                 f"{presentes}/4 citation metadata; missing: {', '.join(faltan)}"))
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
            score, ev = 0.5, f"Signals declared ({detail}) but ai-input=no: you give up being cited in AI answers"
        else:
            score, ev = 1, f"Content Signals declared with purpose: {detail}"
    elif legacy:
        score, ev = 0.5, "Only legacy signals (noai) with no per-purpose granularity"
    else:
        score, ev = 0, "No Content Signals (only 4% of sites have them: quick win)"
    out.append(R("2.1", "C2", "Declared Content Signals", score, ev))

    # 2.2 gestion activa de crawl (CDN/WAF)
    headers = (ctx["home"]["headers"] or "").lower()
    cdn = None
    for marker, name in (("cf-ray", "Cloudflare"), ("x-served-by", "Fastly/Varnish"),
                         ("akamai", "Akamai"), ("x-cache", "CDN with cache")):
        if marker in headers:
            cdn = name
            break
    saw_402 = any(code == 402 for code in ctx["bot_matrix"].values())
    if saw_402:
        score, ev = 1, "Returns HTTP 402 to bots: active crawl management/monetization"
    elif cdn:
        score, ev = 0.5, f"{cdn} detected (capability available; confirm with the client whether AI Crawl Control is configured)"
    else:
        score, ev = 0, "No CDN/WAF detected: probably nobody is monitoring which AI bots come in"
    out.append(R("2.2", "C2", "Active crawl management", score, ev, manual=bool(cdn)))

    # 2.3 Web Bot Auth (verificacion criptografica)
    wba = ctx["wellknown"].get("/.well-known/http-message-signatures-directory", 0)
    out.append(R("2.3", "C2", "Web Bot Auth", 1 if wba == 200 else 0,
                 f"Signatures directory HTTP {wba}" if wba == 200
                 else "No Web Bot Auth support (normal in 2026; note it on the roadmap)"))

    # 2.4 rate limiting razonable
    rapid = ctx["rapid"]
    if not rapid:
        out.append(R("2.4", "C2", "Reasonable rate limiting", None, "Not measured"))
        return out
    n200 = rapid.count(200)
    n429 = rapid.count(429)
    hard = sum(1 for c in rapid if c in (403, 0))
    if hard >= len(rapid) // 2:
        score, ev = 0, f"Ban after a few requests: {rapid}"
    elif n200 == len(rapid):
        score, ev = 1, f"Stable: {n200}x200 with no throttling"
    elif n429 and n200 >= len(rapid) * 0.7:
        # throttling SUAVE de verdad: sirve la mayoria y frena el exceso con
        # 429, que es el comportamiento que el consejo del check recomienda
        score, ev = 1, f"Gentle throttling: {n200}x200, {n429}x429"
    else:
        # Antes `n429 > 0` puntuaba 1 directamente: un sitio que respondia 429 a
        # las DIEZ peticiones (0x200, el bot no obtiene nada) salia con nota
        # perfecta en "rate limiting razonable". Educado si, razonable no: el
        # limite razonable sirve la mayoria del trafico y frena el exceso.
        score, ev = 0.5, (f"Aggressive or mixed throttling: {n200}x200, {n429}x429, "
                          f"{hard}x(403/0) — the bot gets little content during "
                          f"a burst")
    out.append(R("2.4", "C2", "Reasonable rate limiting", score, ev))
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
    out.append(R("3.1", "C3", "JSON-LD present and valid", score,
                 f"{with_valid}/{total} pages with valid JSON-LD; {invalid_total} invalid blocks"))

    # 3.2 Organization / entidad
    home_valid, _ = jsonld_blocks(ctx["home"]["body"])
    orgs = find_nodes(home_valid, "Organization") + find_nodes(home_valid, "LocalBusiness")
    if orgs:
        org = orgs[0]
        fields = [f for f in ("name", "url", "logo", "sameAs", "contactPoint") if org.get(f)]
        score = 1 if len(fields) >= 4 else 0.5
        ev = f"Organization with {len(fields)}/5 key fields ({', '.join(fields)})"
    else:
        score, ev = 0, "No Organization/LocalBusiness on the home page: the entity isn't declared"
    out.append(R("3.2", "C3", "Complete Organization entity", score, ev))

    # 3.3 Product/Offer operativo (solo ecommerce)
    if ctx["typology"] == "ecommerce":
        prod_pages = [(p, v) for p, v, _ in per_page if p["bucket"] == "producto" and v]
        best_score, best_ev = 0, "No Product JSON-LD on the sampled product pages"
        for p, valid in prod_pages:
            prods = find_nodes(valid, "Product")
            for prod in prods:
                offers = prod.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                have = [f for f in ("price", "priceCurrency", "availability") if offers.get(f)]
                base = [f for f in ("name", "image", "description", "brand") if prod.get(f)]
                if len(have) == 3 and len(base) >= 3:
                    best_score, best_ev = 1, f"Complete Product on {p['url'][:80]} (offers: {', '.join(have)})"
                elif len(have) >= 1 and best_score < 1:
                    best_score = max(best_score, 0.5)
                    best_ev = f"Incomplete Product on {p['url'][:80]}: offers only with {', '.join(have)}"
        out.append(R("3.3", "C3", "Operational Product/Offer", best_score, best_ev))
    else:
        out.append(R("3.3", "C3", "Operational Product/Offer", None, "N/A (not e-commerce)"))

    # 3.4 atributos ricos
    all_valid = [v for _, v, _ in per_page for v in [v]][0:] if per_page else []
    rich_fields = ("gtin", "gtin13", "sku", "mpn", "brand", "aggregateRating", "review",
                   "material", "color", "size", "author", "datePublished", "dateModified")
    corpus = json.dumps([v for _, v, _ in per_page], ensure_ascii=False) if per_page else ""
    present = [f for f in rich_fields if f'"{f}"' in corpus]
    score = 1 if len(present) >= 6 else 0.5 if len(present) >= 3 else 0
    out.append(R("3.4", "C3", "Rich attributes in the markup", score,
                 f"{len(present)} rich attribute types present: {', '.join(present[:8]) or 'none'}"))

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
    out.append(R("3.5", "C3", "Semantic HTML", score,
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
        ev = (f"Real accessibility tree: {n} actionable controls, "
              f"{ax['sin_nombre']} without a name and {ax['nombre_generico']} with a generic "
              f"name ({pct:.0%}). An agent sees them but doesn't know what they do.")
        if muestra:
            ev += f" Examples: {muestra}."
        if score == 1:
            # Sin afirmar "todos": con el umbral en 2% puede quedar alguno suelto,
            # y decir que estan todos seria afirmar lo que no hemos comprobado.
            ev = (f"Real accessibility tree: {n - ciegos} of {n} actionable controls "
                  f"have their own name ({1 - pct:.0%}). An agent "
                  f"can tell what each one does.")
            if ciegos:
                ev += (f" {ciegos} remain without a useful name, below the level that "
                       f"gets an agent stuck.")
        out.append(R("3.6", "C3", "Agent-readable controls", score, ev))
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
        score, ev = 1, f"No ghost elements; {native} native controls, {mitigated} mitigated with role+tabindex"
    elif ghost <= 3 or (mitigated and ghost <= mitigated):
        score, ev = 0.5, f"{ghost} ghost elements (clickable div/span without semantics) vs {native} native"
    else:
        score, ev = 0, f"{ghost} ghost elements: invisible as interactive ({native} native)"
    ev += (" [APPROXIMATE: without a render the real accessibility tree couldn't be read; "
           "this is estimated from the raw HTML and is less accurate. Turn on JS rendering "
           "to measure it properly]")
    out.append(R("3.6", "C3", "Agent-readable controls", score, ev))

    # 3.7 Entidad en Wikipedia/Wikidata. Wikipedia es la mayor fuente
    # individual de citas en respuestas de IA; el vinculo NO ambiguo entre
    # dominio y entidad es P856 (sitio oficial) en Wikidata — buscar por nombre
    # de marca daria falsos positivos con homonimos. Fuente EXTERNA: esta
    # evidencia vale incluso si el sitio nos bloquea.
    wd = ctx.get("wikidata") or {}
    if wd.get("error"):
        score, ev = None, f"Wikidata didn't respond ({wd['error']}): not verifiable"
    elif wd.get("qid"):
        n = wd.get("sitelinks") or 0
        score = 1 if n > 0 else 0.5
        ev = (f"Entity {wd['qid']} on Wikidata with an official website (P856) pointing to the domain"
              + (f", linked to {n} Wikipedia article(s)" if n
                 else "; the item exists but has no Wikipedia article yet"))
    else:
        score, ev = 0, ("No Wikidata entity with P856 pointing to the domain "
                        "(external source queried: doesn't depend on our access to the site)")
    out.append(R("3.7", "C3", "Wikipedia/Wikidata entity", score, ev))
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
            score, ev = 1, f"The raw HTML contains {ratio:.0%} of the rendered content ({raw_len} vs {ren_len} chars)"
        elif ratio >= 0.3:
            score, ev = 0.5, f"Only {ratio:.0%} of the content is in the raw HTML: part of the site is invisible to AI crawlers"
        else:
            score, ev = 0, f"CRITICAL: only {ratio:.0%} of the content exists without JS. To GPTBot/ClaudeBot this site is almost empty"
        out.append(R("4.1", "C4", "Content without running JS", score, ev))
    else:
        # fallback heuristico sin render
        shell = raw_len < 800 and re.search(r'(?i)id=["\'](root|app|__next)["\']', ctx["home"]["body"] or "")
        score = 0 if shell else 0.5
        ev = ("Empty SPA pattern detected (div#root with <800 chars of text)" if shell
              else f"No render available; the raw HTML has {raw_len} chars of text (review manually)")
        out.append(R("4.1", "C4", "Content without running JS", score, ev, manual=True))

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
            ev = f"Product page without JS: price={'yes' if has_price else 'NO'}, buy CTA={'yes' if has_cta else 'NO'}"
        else:
            score, ev = 0, "No product page accessible in the sample"
        out.append(R("4.2", "C4", "Price and CTA without JS", score, ev))
    else:
        out.append(R("4.2", "C4", "Price and CTA without JS", None, "N/A (not e-commerce)"))

    # 4.3 velocidad para bots (TTFB)
    ttfbs = [p["fetch"]["ttfb"] for p in ctx["pages"] if p["fetch"]["ttfb"]]
    if ctx["home"]["ttfb"]:
        ttfbs.append(ctx["home"]["ttfb"])
    if ttfbs:
        avg = sum(ttfbs) / len(ttfbs)
        score = 1 if avg < 0.8 else 0.5 if avg < 2 else 0
        ev = f"Average TTFB {avg:.2f}s across {len(ttfbs)} pages (live fetchers give up >2s)"
    else:
        score, ev = None, "Not measured"
    out.append(R("4.3", "C4", "Speed for bots (TTFB)", score, ev))

    # 4.4 deep-linking. Mide el acceso DIRECTO (_status_directo): el rescate por
    # Jina recupera el contenido para otros checks, pero no cambia lo que recibe
    # un agente que pide la URL a pelo. Contarlo como 200 inflaba el check.
    ok = sum(1 for p in ctx["pages"]
             if p["fetch"].get("_status_directo", p["fetch"]["status"]) == 200)
    total = max(len(ctx["pages"]), 1)
    rescatadas = sum(1 for p in ctx["pages"]
                     if str(p["fetch"].get("_via", "")).startswith("jina")
                     and p["fetch"].get("_status_directo") != 200)
    score = 1 if ok == total else 0.5 if ok / total >= 0.7 else 0
    ev = f"{ok}/{total} deep URLs return 200 on direct access without a session"
    if rescatadas:
        ev += (f" ({rescatadas} only readable via Jina: their content exists, "
               f"but direct access is blocked)")
    out.append(R("4.4", "C4", "Stable deep-linking", score, ev))

    # 4.5 API detectable
    api_hits = [p for p, c in ctx["wellknown"].items()
                if c == 200 and p in ("/openapi.json", "/swagger.json", "/api-docs")]
    out.append(R("4.5", "C4", "Detectable public API",
                 1 if api_hits else 0,
                 f"Spec found: {', '.join(api_hits)}" if api_hits
                 else "No OpenAPI/Swagger on standard paths"))

    # 4.6 estabilidad visual (CLS): los rediseños dinamicos confunden a agentes
    # que toman capturas entre acciones. Se prefiere PageSpeed (dato de campo);
    # si no, el CLS que midio el navegador durante el render (dato de
    # laboratorio, siempre disponible cuando hay render). Antes solo existia PSI
    # y en produccion nunca se activaba: 4.6 era un factor que jamas puntuaba.
    cls = ctx.get("psi_cls")
    fuente = "PageSpeed (field)"
    if cls is None:
        cls = ctx.get("render_cls")
        fuente = "measured in the browser (lab)"
    if cls is None:
        out.append(R("4.6", "C4", "Visual stability (CLS)", None,
                     "Not measured: no render available in this analysis", manual=True))
    else:
        score = 1 if cls <= 0.1 else 0.5 if cls <= 0.25 else 0
        out.append(R("4.6", "C4", "Visual stability (CLS)", score,
                     f"CLS={cls:.3f} (good <=0.1, {fuente}): layout shifts "
                     "confuse an agent that takes screenshots between actions"))

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
        out.append(R("4.7", "C4", "Operable click targets", None,
                     "No render geometry available (requires the Playwright backend): "
                     "the actual size of the controls can't be measured", manual=True))
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
            out.append(R("4.7", "C4", "Operable click targets", None,
                         f"Only {tot_inline} inline links were detected (exempt under "
                         "WCAG): no measurable controls", manual=True))
        else:
            ratio_ok = 1 - (tot_problems / tot_targets)
            score = 1 if ratio_ok >= 0.95 else 0.5 if ratio_ok >= 0.8 else 0
            desglose = ", ".join(f"{n} {r:.0%} ({t} controls)"
                                 for n, t, _p, r in per_page)
            ev = (f"{tot_targets} controls measured on {len(per_page)} template(s) "
                  f"[{desglose}] ({tot_inline} inline links excluded under the "
                  f"WCAG exception): {ratio_ok:.0%} without problems")
            if ejemplos:
                muestra = ", ".join(f"{n}: {b['tag']} {b['w']}x{b['h']}px"
                                    + (f" ('{b['name'][:28]}')" if b["name"] else "")
                                    for n, b in ejemplos[:4])
                ev += (f". Below {MIN}x{MIN}px: {muestra}"
                       " — an agent that clicks by coordinates misses or hits the one next to it")
            # una plantilla claramente peor que el resto es un hallazgo por si mismo
            if len(per_page) > 1:
                peor = min(per_page, key=lambda x: x[3])
                mejor = max(per_page, key=lambda x: x[3])
                if mejor[3] - peor[3] >= 0.15:
                    ev += (f". The '{peor[0]}' template is noticeably worse than "
                           f"'{mejor[0]}' ({peor[3]:.0%} vs {mejor[3]:.0%})")
            if tot_problems == 0:
                ev += ". All controls can be operated reliably"
            out.append(R("4.7", "C4", "Operable click targets", score, ev))

    # 4.8 estados de error correctos — el soft-404 es el fallo agentico silencioso:
    # el humano lee "no encontrado", el agente solo mira el codigo de estado.
    ep = ctx.get("error_probe") or {}
    st = ep.get("status")
    if not st:
        out.append(R("4.8", "C4", "Correct error states", None,
                     "The non-existent URL probe got no response", manual=True))
    elif st == 200:
        out.append(R("4.8", "C4", "Correct error states", 0,
                     f"SOFT-404: a non-existent URL returns HTTP 200"
                     + (" with 'not found' text in the body" if ep.get("looks_missing") else "")
                     + ". An agent reads 200 as success and keeps working with an "
                       "empty page; the error spreads without anyone noticing"))
    elif st in (301, 302, 307, 308):
        out.append(R("4.8", "C4", "Correct error states", 0.5,
                     f"A non-existent URL redirects (HTTP {st}) instead of returning 404. "
                     "The agent ends up on another page believing it reached the one it asked for"))
    elif st in (404, 410):
        score = 1 if ep.get("has_recovery") else 0.5
        ev = (f"Correct: HTTP {st} on a non-existent URL. "
              + ("The error page offers navigation or search to recover"
                 if ep.get("has_recovery")
                 else "But the error page offers no navigation or search: "
                      "the agent hits a dead end"))
        out.append(R("4.8", "C4", "Correct error states", score, ev))
    else:
        out.append(R("4.8", "C4", "Correct error states", 0.5,
                     f"A non-existent URL returns HTTP {st}, which isn't a clear 404/410"))

    # 4.9 Higiene de redirecciones. Un agente sin JS se queda tirado en un stub
    # de meta-refresh o de location.href, y un salto a otro dominio le rompe la
    # atribucion. Solo paginas vistas por HTTP directo: sobre un rescate (Jina)
    # o un bloqueo no se puede afirmar higiene, y el fallo aqui exige evidencia
    # POSITIVA — por eso este check no entra en las listas de degradacion.
    directas = [(p["url"], p["fetch"]) for p in ctx["pages"]
                if p["fetch"]["status"] == 200
                and p["fetch"].get("_via", "http") == "http"]
    if ctx["home"].get("status") == 200 and ctx["home"].get("_via", "http") == "http":
        directas.append((ctx["base"] + "/", ctx["home"]))
    if not directas:
        out.append(R("4.9", "C4", "Redirect hygiene", None,
                     "No pages seen via direct HTTP: not measurable"))
    else:
        incidencias = []
        for pedida, f in directas:
            body = f.get("body") or ""
            final = f.get("url") or pedida
            # Se compara el host PEDIDO con el final de ESA peticion, no con el
            # dominio base: una pagina legitima en un subdominio del sitemap no
            # es un salto — el salto es que la URL pedida acabe sirviendose
            # desde otro sitio.
            h_pedida = (urlparse(pedida).hostname or "").lower().removeprefix("www.")
            h_final = (urlparse(final).hostname or "").lower().removeprefix("www.")
            if re.search(r"(?i)<meta[^>]+http-equiv=[\"']?refresh", body):
                incidencias.append(f"{pedida}: stub meta-refresh")
            elif len(body) < 2000 and re.search(r"(?i)location\.(href|replace)", body):
                incidencias.append(f"{pedida}: JS redirect stub")
            elif h_pedida and h_final and h_final != h_pedida:
                incidencias.append(f"{pedida}: ends up on {h_final} (domain hop)")
        score = 1 if not incidencias else 0.5 if len(incidencias) == 1 else 0
        out.append(R("4.9", "C4", "Redirect hygiene", score,
                     f"{len(directas)} pages reach real content without stubs or domain hops"
                     if not incidencias else "; ".join(incidencias)[:350]))
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
            page_results.append((p["url"], 0, "no H1 found"))
            continue
        first = visible_text(m.group(2))[:900]
        words = len(first.split())
        info_hits = len(INFO.findall(first))
        fluff_hits = len(FLUFF.findall(first))
        if 25 <= words <= 320 and info_hits >= 2 and fluff_hits <= 1:
            page_results.append((p["url"], 1, f"{words} words, {info_hits} data points, {fluff_hits} filler"))
        elif words > 0 and info_hits >= 1:
            page_results.append((p["url"], 0.5, f"{words} words, {info_hits} data points, {fluff_hits} filler"))
        else:
            page_results.append((p["url"], 0, f"{words} words, {info_hits} data points, {fluff_hits} filler"))
    if page_results:
        avg = sum(s for _, s, _ in page_results) / len(page_results)
        score = 1 if avg >= 0.8 else 0.5 if avg >= 0.4 else 0
        worst = min(page_results, key=lambda x: x[1])
        ev = (f"{sum(1 for _, s, _ in page_results if s == 1)}/{len(page_results)} pages with a "
              f"direct answer after the H1 (data>=2, filler<=1). "
              f"Worst: {worst[0].split('/')[-1] or worst[0][-40:]} ({worst[2]})")
    else:
        score, ev = 0, "No analyzable content pages"
    out.append(R("5.1", "C5", "Direct answer up top", score, ev))

    # 5.2 estructura chunkeable — secciones autocontenidas + jerarquia de headings.
    # Medimos cada seccion H2/H3: titulo descriptivo (>=3 palabras o pregunta) y
    # cuerpo sustancial (30-400 palabras), mas saltos de jerarquia (h2->h4).
    page_results = []
    for p in content_pages[:5]:
        body = p["fetch"]["body"]
        heads = [(m.group(1), visible_text(m.group(2)), m.end())
                 for m in re.finditer(r"(?is)<h([23])[^>]*>(.*?)</h\1>", body)]
        if not heads:
            page_results.append((p["url"], 0, "no H2/H3"))
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
                             f"{ok_sections}/{len(heads)} self-contained sections, {jumps} hierarchy jumps"))
    if page_results:
        avg = sum(s for _, s, _ in page_results) / len(page_results)
        score = 1 if avg >= 0.8 else 0.5 if avg >= 0.4 else 0
        detail = "; ".join(f"{u.split('/')[-1] or u[-30:]}: {d}" for u, _, d in page_results[:3])
        ev = f"Analyzed {len(page_results)} pages section by section. {detail}"
    else:
        score, ev = 0, "No analyzable content pages"
    out.append(R("5.2", "C5", "Chunkable structure", score, ev))

    # 5.3 E-E-A-T verificable.
    # Con articulos de blog en la muestra se exige lo fuerte: autoria + fecha
    # POR articulo. Sin blog, antes el check se quedaba en N/A — medido en el
    # barrido de factores: sin puntuar en 8 de 12 dominios, dos tercios de los
    # sitios sin este factor. Pero la pregunta de fondo aplica a cualquier web:
    # ¿puede una IA saber QUIEN responde de este contenido y DE CUANDO es?
    # Una web sin fecha ni responsable en ninguna pagina es contenido que un
    # LLM no puede fechar ni atribuir, sea blog o corporativa.
    blog_pages = [p for p in ctx["pages"] if p["bucket"] == "blog" and p["fetch"]["status"] == 200]

    def _senales_eeat(body):
        """(autor, fecha, es_articulo) de una página. Las señales cubren tanto
        el marcado formal (JSON-LD, <time>, metas) como la firma VISIBLE que
        usan muchos blogs reales: "Por <a href=/sobre-mi/>Carlos</a> ·
        Publicado: 28/08/2026" no llevaba class=author ni <time> y salía como
        "sin autoría" — un enlace de byline accesible ES autoría verificable.
        """
        valid, _ = jsonld_blocks(body)
        js = json.dumps(valid)
        autor = (bool(find_nodes(valid, "Person")) or '"author"' in js
                 or bool(re.search(r"(?i)class=[\"'][^\"']*(author|byline)", body))
                 or bool(re.search(r"(?i)<meta[^>]+name=[\"']author", body))
                 or bool(re.search(r"(?i)rel=[\"']author", body))
                 or bool(re.search(r"(?i)(?:>|\s)(por|by|escrito por|written by|"
                                   r"autora?)\s*:?\s*<a\b", body)))
        fecha = ('"datePublished"' in js or '"dateModified"' in js
                 or bool(re.search(r"(?i)<time[\s>]", body))
                 or bool(re.search(r"(?i)(article:published_time|og:updated_time)", body))
                 or bool(re.search(r"(?i)(publicado|actualizado|published|updated)"
                                   r"[^<>]{0,20}\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}", body)))
        # ¿Es un artículo o un hub del blog? El sitemap mete a los dos en el
        # mismo bucket, y a un índice no se le puede exigir firma de artículo.
        es_articulo = (bool(re.search(r'(?i)"@type"\s*:\s*"[^"]*(article|blogposting)',
                                      js)) or autor or fecha)
        return autor, fecha, es_articulo

    articulos, hubs = [], 0
    for p in blog_pages:
        autor, fecha, es_articulo = _senales_eeat(p["fetch"]["body"] or "")
        if es_articulo:
            articulos.append((autor, fecha))
        else:
            hubs += 1
    if articulos:
        hits = sum(1 if (a and f) else 0.5 for a, f in articulos)
        ratio = hits / len(articulos)
        score = 1 if ratio >= 0.85 else 0.5 if ratio >= 0.4 else 0
        ev = (f"Verifiable authorship+date on {hits}/{len(articulos)} sampled articles"
              + (f" ({hubs} blog index page(s) excluded: a listing isn't "
                 f"expected to carry a byline)" if hubs else ""))
    else:
        # Sin ningún artículo reconocible en la muestra (solo hubs, o nada):
        # exigir firma aquí sería culpar a la web de nuestro muestreo. Se cae
        # a la evaluación genérica de frescura/autoría sobre el resto del
        # contenido, cuyo texto ya avisa de que el blog pudo no entrar.
        contenido = [p["fetch"]["body"] for p in ctx["pages"]
                     if p["fetch"]["status"] == 200 and p["bucket"] != "legal"]
        contenido.append(ctx["home"]["body"] or "")
        corpus = " ".join(c or "" for c in contenido[:6])
        if len(corpus) < 500:
            score, ev = None, "No analyzable content pages"
        else:
            valid, _ = jsonld_blocks(corpus)
            js = json.dumps(valid)
            fecha = ('"datePublished"' in js or '"dateModified"' in js
                     or bool(re.search(r"(?i)<time[\s>]", corpus))
                     or bool(re.search(r'(?i)(article:published_time|og:updated_time)', corpus))
                     or bool(re.search(r"(?i)(ultima actualizacion|última actualización|"
                                       r"last updated|actualizado el)", corpus)))
            autoria = (bool(find_nodes(valid, "Person")) or '"author"' in js
                       or bool(re.search(r'(?i)<meta[^>]+name=["\']author', corpus))
                       or bool(re.search(r"(?i)class=[\"'][^\"']*(author|byline)", corpus)))
            senales = [s for s, hay in (("dates", fecha), ("authorship/owner", autoria)) if hay]
            # Sin articulos en la muestra no se puede exigir E-E-A-T pleno: el 1
            # se reserva para quien SI expone frescura (fecha/actualizacion), que
            # es la señal que un agente usa para juzgar vigencia. La ausencia NO
            # baja de 0.5: no sabemos si es que la web no tiene E-E-A-T o que su
            # contenido editorial no entro en el muestreo (caso real: cloudflare
            # tiene blog con autoria y fecha, pero la muestra pillo landings).
            # Castigar con 0 seria culpar a la web de un limite nuestro.
            score = 1 if fecha else 0.5
            ev = ("No articles in the sample: freshness and authorship signals "
                  f"were assessed on {len(contenido)} content pages. Found: "
                  f"{', '.join(senales) or 'none'}. "
                  + ("The content can be dated, which is what an agent needs "
                     "to judge whether it's current." if fecha else
                     "No visible date in what was sampled: if the site publishes "
                     "informational content, it should mark up authorship and date "
                     "(its blog may not have made it into the sample)."))
    out.append(R("5.3", "C5", "Verifiable E-E-A-T", score, ev))

    # (la citacion real en respuestas de IA — el antiguo 5.4 — se mide con Clicandseo)

    # 5.5 llms.txt (higiene, peso bajo). Se mide CALIDAD, no solo presencia:
    # un volcado automatico de cientos de KB cumple la letra del estandar y
    # falla su proposito, que es ser un indice curado.
    llms = ctx["wellknown"].get("/llms.txt", 0)
    if llms != 200:
        out.append(R("5.5", "C5", "llms.txt (higiene)", 0,
                     "No llms.txt (low weight: 97% are never read, but it's cheap hygiene)"))
    else:
        m = (ctx.get("wellknown_meta") or {}).get("/llms.txt") or {}
        kb = (m.get("bytes") or 0) / 1024
        volcado = kb > 200 or m.get("autogenerado")
        if volcado:
            motivos = []
            if kb > 200:
                motivos.append(f"{kb:.0f} KB")
            if m.get("autogenerado"):
                motivos.append("states it was generated by a plugin")
            out.append(R("5.5", "C5", "llms.txt (higiene)", 0.5,
                         f"llms.txt present but it looks like an automatic dump "
                         f"({', '.join(motivos)}, {m.get('enlaces', 0)} links). The standard "
                         "calls for a CURATED index that guides the model; a dump of every "
                         "URL meets the form but not the function"))
        else:
            out.append(R("5.5", "C5", "llms.txt (higiene)", 1,
                         f"llms.txt present and it looks curated "
                         f"({kb:.0f} KB, {m.get('enlaces', 0)} links)"))

    # 5.6 negociacion de contenido Markdown (Accept: text/markdown)
    mdn = ctx.get("md_negotiation") or {}
    if mdn.get("is_markdown"):
        score, ev = 1, f"Serves Markdown to agents via content negotiation (Content-Type: {mdn.get('content_type')})"
    else:
        score, ev = 0, (f"With Accept: text/markdown it responds with {mdn.get('content_type') or 'HTML'} "
                        "(only 3.9% of sites support it: a cheap differentiator)")
    out.append(R("5.6", "C5", "Markdown negotiation", score, ev))

    # 5.7 Paginas de confianza: quien esta detras (About), como contactar y la
    # base legal. Un agente las comprueba antes de recomendar, igual que una
    # persona cuidadosa. Las candidatas salen de la home Y del sitemap con
    # patrones multiidioma, y solo cuentan VERIFICADAS (200 + contenido real):
    # el caso que destapo el factor tenia /sobre-mi/ y /legal/privacidad/ y un
    # scanner solo-EN afirmaba que faltaban About y Privacy.
    tp = ctx.get("trust_pages")
    if tp is None:
        out.append(R("5.7", "C5", "Trust pages", None,
                     "Trust probes not run: not measurable"))
    else:
        nombres = {"quien": "who's-behind-it (About)", "contacto": "contact",
                   "legal": "legal/privacy"}
        oks = [nombres[k] for k, v in tp.items() if v and v.get("ok")]
        rotas = [f"{nombres[k]} ({v['url']} without useful content)"
                 for k, v in tp.items() if v and not v.get("ok")]
        faltan = [nombres[k] for k, v in tp.items() if not v]
        # Las candidatas salen de la home (footer incluido) y del sitemap. Si
        # la portada solo se leyo via rescate, su footer puede no estar en lo
        # que vimos: lo VERIFICADO vale (evidencia positiva), pero afirmar que
        # "falta" lo demas seria describir nuestra via de acceso. Caso real
        # (mediamarkt.es): su home directa enlaza /es/legal/politica-de-
        # privacidad y sobre el cuerpo de Jina la dabamos por inexistente.
        via_home = ctx["home"].get("_via", "http")
        if len(oks) == 3:
            score = 1
        elif faltan and via_home not in ("http", "render"):
            score = None
        else:
            score = 0.5 if len(oks) == 2 else 0
        ev = f"Verified {len(oks)}/3: {', '.join(oks) or 'none'}"
        if rotas:
            ev += f". Found but without content: {'; '.join(rotas)}"
        if faltan:
            ev += (f". Can't claim {', '.join(faltan)} is missing: the home page was only "
                   f"read via the fallback and its footer may not have come through in full"
                   if score is None else
                   f". Not found (home + sitemap): {', '.join(faltan)}")
        out.append(R("5.7", "C5", "Trust pages", score, ev))

    # 5.8 Presupuesto de tokens por pagina (~25K tokens de texto extraido, a
    # ~4 chars/token): una pagina que no cabe en el contexto del agente se lee
    # truncada, y lo truncado se cita mal. El fallo exige evidencia positiva
    # (una pagina medida que se pasa), asi que no entra en degradaciones.
    medibles = [(p["url"], p["fetch"]["body"] or "") for p in ctx["pages"]
                if p["fetch"]["status"] == 200
                and p["fetch"].get("_via", "http") == "http"]
    if ctx["home"].get("status") == 200 and ctx["home"].get("_via", "http") == "http":
        medibles.append((ctx["base"] + "/", ctx["home"].get("body") or ""))
    if not medibles:
        out.append(R("5.8", "C5", "Token budget per page", None,
                     "No pages seen via direct HTTP: not measurable"))
    else:
        PRESUPUESTO = 25000
        tokens = []
        for u, body in medibles:
            texto = re.sub(r"(?s)<(script|style).*?</\1>|<[^>]+>", " ", body)
            tokens.append((u, len(texto) // 4))
        grandes = [(u, t) for u, t in tokens if t > PRESUPUESTO]
        mayor = max(tokens, key=lambda x: x[1])
        if not grandes:
            score, ev = 1, (f"All {len(tokens)} measured pages fit in the budget "
                            f"(~{PRESUPUESTO // 1000}K tokens); the largest is around ~{mayor[1] // 1000}K")
        elif len(grandes) <= len(tokens) // 2:
            score = 0.5
            ev = (f"{len(grandes)}/{len(tokens)} pages exceed ~{PRESUPUESTO // 1000}K tokens "
                  f"(worst: {grandes[0][0]} with ~{grandes[0][1] // 1000}K): they're read truncated")
        else:
            score = 0
            ev = (f"Most measured pages ({len(grandes)}/{len(tokens)}) exceed the "
                  f"~{PRESUPUESTO // 1000}K-token budget: agents read them truncated")
        out.append(R("5.8", "C5", "Token budget per page", score, ev))
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
                     # agents.md: instrucciones para agentes en la raiz (analogo a
                     # llms.txt pero orientado a INTERACCION, no solo lectura). Lo
                     # tienen poquisimos sitios y es una señal fuerte de que la web
                     # piensa en agentes. finistore.es lo expone y lo referencia en
                     # su robots.txt; antes ni lo sondeabamos.
                     "/agents.md",
                     "/.well-known/agent.json", "/.well-known/agent-card.json",
                     "/auth.md", "/.well-known/skills"]
    hits = [p for p in agentic_paths if wk.get(p) == 200]
    home_html = ctx["home"]["body"] or ""
    webmcp = bool(re.search(r"(?i)webmcp|navigator\.modelContext|model-context-protocol",
                            home_html))
    if webmcp:
        hits.append("WebMCP (on page)")
    out.append(R("6.1", "C6", "Agentic surface",
                 1 if hits else 0,
                 f"Exposes: {', '.join(hits)}" if hits
                 else "No agentic surface: no MCP, no A2A agent.json, no WebMCP (<15 of the top 200k sites have one: first-mover advantage)"))

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
        ev = (f"{n} forms, {total_fields} fields: {bound_fields} bound via for=id (verified), "
              f"{aria_fields} aria-label, {autocomp} autocomplete, {with_submit}/{n} with a real submit, "
              f"{captcha} with CAPTCHA. [No real forms are submitted, for ethical reasons]")
    else:
        score, ev = 0.5, "No forms detected on the sampled pages"
    out.append(R("6.2", "C6", "Operable forms", score, ev))

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
               f"{(v.get('progreso') or {}).get('total')} steps)"
               if (v.get("progreso") or {}).get("total") else "")
            for k, v in valid.items())
        reps = at.get("repeticiones")
        ev = (f"Task '{at['typology']}' run by {total} real agent(s)"
              + (f", {reps} attempts each" if reps and reps > 1 else "") + f" — {per}.")
        if tasa is not None and reps and reps > 1:
            ev += f" Overall success rate: {tasa:.0%}."
        if inconsistentes:
            ev += (f" WARNING: {', '.join(inconsistentes)} completed the task only in "
                   "some attempts. For an agent, a site that works sometimes is "
                   "worse than one that always fails: the outcome isn't predictable.")
        if avg is not None:
            ev += f" Average progress: {avg:.0%} of the task steps."
        # donde se atascan todos = el cuello de botella real del sitio
        atascos = [p["pendientes"][0] for p in progs if p.get("pendientes")]
        if atascos and len(set(atascos)) == 1 and len(atascos) > 1:
            ev += f" They all get stuck at the same point: {atascos[0]}."
        # Si TODOS los agentes se cayeron por controles que no responden al clic
        # programatico, no afirmamos que la web sea inoperable: puede ser un
        # limite de nuestro harness. Se marca para revision manual.
        if valid and all(v.get("limite_de_metodo") for v in valid.values()):
            out[-1] = R("6.3", "C6", "Task with a real agent", None,
                        ev + " METHOD NOTICE: every attempt failed on "
                             "controls that didn't respond to programmatic clicks "
                             "(custom selectors, JS components). Our harness "
                             "clicks by selector; commercial agents use vision "
                             "and handle them better. NOT conclusive: needs a manual "
                             "test before claiming the site isn't operable.",
                        manual=True)
            return out
        # honestidad: lo que NO evaluamos por politica propia no se cuenta como fallo
        no_eval = at.get("hitos_no_evaluados") or []
        if no_eval:
            ev += (f" Not evaluated due to the test's policy (not a failure of the site): "
                   f"{', '.join(no_eval)}.")
        ev += " Details and step log in the Evidence tab."
        out.append(R("6.3", "C6", "Task with a real agent", score, ev))
    else:
        # Se ejecutaron y NINGUNA pudo ver la web. Decir "no ejecutado" aqui
        # seria falso, y decir "no conseguido" seria peor: acusaria a la web.
        noverif = [k for k, v in agents.items()
                   if v.get("outcome") == "no_verificable"]
        if noverif:
            det = next(v.get("detail") for v in agents.values()
                       if v.get("outcome") == "no_verificable")
            out.append(R("6.3", "C6", "Task with a real agent", None,
                         f"Run with {', '.join(noverif)}, with no measurable result: "
                         f"{det} Not scored: there's no agentic evidence either "
                         "way, neither for nor against.", manual=True))
            return out
        # el mensaje cambia si el usuario YA las pidió: decirle "actívalas"
        # cuando acaba de activarlas seria desconcertante
        if ctx.get("agentes_pendientes"):
            ev_63 = ("Pending: click «Simulate agents» in the report. "
                     "It runs in the background (10-15 min) and when it finishes it updates this "
                     "check and the overall score without repeating the rest of the analysis")
        else:
            ev_63 = ("Not run (turn on 'Real agentic tests' in the analysis, or do it "
                     "manually with Operator/Claude)")
        out.append(R("6.3", "C6", "Task with a real agent", None,
                     ev_63, manual=True))

    # 6.4 autenticacion operable por un agente. Jerarquia: OAuth delegado (el
    # agente actua en nombre del usuario SIN manejar su contrasena) > formulario
    # estandar bien marcado > formulario opaco o con CAPTCHA (agente bloqueado).
    oauth = [p for p in ("/.well-known/oauth-authorization-server",
                         "/.well-known/oauth-protected-resource") if wk.get(p) == 200]
    lp = ctx.get("login_probe") or {}
    if oauth:
        out.append(R("6.4", "C6", "Agent-operable authentication", 1,
                     f"Discoverable OAuth at {', '.join(oauth)}: an agent can obtain "
                     "delegated permission without handling the user's password (the right pattern)"))
    elif not lp.get("found"):
        out.append(R("6.4", "C6", "Agent-operable authentication", None,
                     "The site has no login area: not applicable"))
    else:
        body = lp.get("body") or ""
        has_pwd = bool(re.search(r'(?i)<input[^>]+type=["\']password', body))
        ac_user = bool(re.search(r'(?i)autocomplete=["\'](username|email)', body))
        ac_pwd = bool(re.search(r'(?i)autocomplete=["\'](current-password|password)', body))
        captcha = bool(re.search(r"(?i)recaptcha|hcaptcha|turnstile", body))
        social = bool(re.search(r"(?i)(sign|log)[ -]?in with (google|apple|microsoft)|"
                                r"continuar con (google|apple)", body))
        n_cand = len(lp.get("intentos") or [])
        via = " (form visible only after rendering JS)" if lp.get("via") == "render" else ""
        if not has_pwd:
            out.append(R("6.4", "C6", "Agent-operable authentication", None,
                         f"Tried {n_cand} login candidates; at {lp['url']} there's no "
                         "password form even after rendering (third-party login "
                         "or external wall): can't be assessed automatically", manual=True))
            return out
        if captcha:
            score = 0
            ev = ("Login is protected by CAPTCHA: the user's own legitimate agent "
                  "can't sign in. With no OAuth or alternative, the private "
                  "area is off-limits to agents")
        elif ac_user and ac_pwd:
            score = 0.5
            ev = ("Login form correctly marked up (autocomplete username + "
                  "current-password): an agent with credentials can fill it in. "
                  "OAuth is missing for delegated permission without sharing the password")
        else:
            score = 0
            faltan = [n for n, v in (("username autocomplete", ac_user),
                                     ("password autocomplete", ac_pwd)) if not v]
            ev = (f"Login form without {' or '.join(faltan)}: an agent can't "
                  "reliably tell which field is which")
        if social:
            ev += ". Offers social login (Google/Apple), which adds another layer of friction for the agent"
        ev += f". Assessed at {lp['url']}{via}"
        out.append(R("6.4", "C6", "Agent-operable authentication", score, ev))
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
        proto_hits.append("HTTP 402 responses to bots (x402/pay-per-crawl signal)")
    out.append(R("7.4", "C7", "Emerging protocols", None,
                 ("Detected: " + ", ".join(proto_hits)) if proto_hits
                 else "Probed x402/UCP/MPP with no findings (informational: these protocols aren't scored yet, not even by Cloudflare)"))

    if ctx["typology"] != "ecommerce":
        out.append(R("7.1", "C7", "Structured feed/catalog", None, "N/A (not e-commerce)"))
        out.append(R("7.5", "C7", "Readable shipping policy", None, "N/A (not e-commerce)"))
        out.append(R("7.6", "C7", "Readable returns policy", None, "N/A (not e-commerce)"))
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
        score, ev = 1, f"{platform} platform (feed available) + Product schema on {prods_ok} product pages"
    elif platform or prods_ok:
        score, ev = 0.5, f"Platform={platform or 'custom'}, product pages with Product schema={prods_ok}"
    else:
        score, ev = 0, "No recognizable platform or detectable structured catalog"
    out.append(R("7.1", "C7", "Structured feed/catalog", score, ev))

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
        ev = f"Schema price matches the visible price on {consistent}/{checked} product pages"
        if score == 0:
            ev += " -> RISK of an agent serving the wrong price"
        result_72 = R("7.2", "C7", "Price consistency", score, ev)
        result_72["inconsistent"] = consistent < checked
    else:
        result_72 = R("7.2", "C7", "Price consistency", 0,
                      "No JSON-LD price to verify (absence, not inconsistency)")
        result_72["inconsistent"] = False
    out.append(result_72)

    # 7.3 preparacion ACP (PSP compatible)
    has_stripe = "js.stripe.com" in corpus or "stripe.com/v3" in corpus
    is_shopify = platform == "Shopify"
    if is_shopify:
        score, ev = 0.5, "Shopify: in the Instant Checkout technical pipeline; enrollment in OpenAI's program is missing (confirm with the client)"
    elif has_stripe:
        score, ev = 0.5, "Stripe detected: PSP compatible with ACP's Delegated Payment Spec; integration not started"
    else:
        score, ev = 0, "No ACP-compatible PSP detected (Stripe/Shopify)"
    out.append(R("7.3", "C7", "ACP readiness", score, ev, manual=True))

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
            ev = (f"{schema_type} markup present ({', '.join(sorted(set(found_schema))[:3])})"
                  + (f" with fields: {', '.join(campos[:6])}" if campos
                     else " but with no inner detail (time/cost): an agent reads it but can't use it"))
            return R(cid, "C7", nombre, score, ev)
        # sin schema: ¿al menos existe la informacion para un humano?
        page_text = visible_text(corpus)
        has_text = bool(re.search(text_re, page_text))
        has_page = bool(re.search(url_re, corpus, re.I))
        if has_text or has_page:
            return R(cid, "C7", nombre, 0,
                     f"The {humano} information exists for a human "
                     f"({'text on the product page' if has_text else 'dedicated page'}) but is NOT "
                     f"in {schema_type}: an agent can't read it or compare it before buying")
        return R(cid, "C7", nombre, 0,
                 f"No {humano} information detectable, neither structured nor visible. "
                 f"An agent comparing options will discard this store for lack of data")

    out.append(_policy_check(
        "7.5", "Readable shipping policy",
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
        r"|verzending|bezorging)", "shipping"))         # NL

    out.append(_policy_check(
        "7.6", "Readable returns policy",
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
        r"|retourneren)", "returns"))                         # NL
    return out


def run_all(ctx):
    results = []
    for fn in (run_c1, run_c2, run_c3, run_c4, run_c5, run_c6, run_c7):
        results.extend(fn(ctx))
    return results
