# -*- coding: utf-8 -*-
"""Orquestador del scanner: recoge evidencias de un dominio y ejecuta los checks.

Portable y sin estado global salvo un LOG_SINK opcional para progreso en vivo.
El check 6.3 (agentes reales) NO se ejecuta aquí: requiere browser-use, que
choca con las dependencias fijadas de la app. En servidor queda como manual;
en local se inyecta vía ctx["agent_tests"] desde la herramienta standalone.
"""
import json
import re
from urllib.parse import urlparse

from . import checks as checks_mod
from . import discovery, scoring
from .config import WELLKNOWN_PATHS, UA_HUMAN, BOT_UAS, get_key
from .httpfetch import (bot_access_matrix, fetch, jina_read, rapid_fire,
                        status_only, assert_public_url, BlockedURLError)
from .render import render as render_page

LOG_SINK = None


def _log(msg):
    if LOG_SINK is not None:
        LOG_SINK.append(msg)


def probe_wellknown(base):
    """Sondea rutas agénticas validando CONTENIDO (evita soft-404 de los CMS)."""
    out = {}
    for p in WELLKNOWN_PATHS:
        res = fetch(base + p, timeout=12)
        code = res["status"]
        if code == 200:
            body = (res["body"] or "").strip()
            is_html = "<html" in body[:400].lower() or "<!doctype" in body[:200].lower()
            text_paths = ("/llms.txt", "/llms-full.txt", "/auth.md", "/.well-known/skills")
            if p in text_paths or p.endswith(".md"):
                valid = not is_html and len(body) > 20
            elif p.endswith(".json") or p in ("/mcp", "/ask") or p.startswith("/.well-known/"):
                try:
                    json.loads(body)
                    valid = True
                except (json.JSONDecodeError, ValueError):
                    valid = not is_html and any(k in body[:500]
                                                for k in ("jsonrpc", "mcp", "openapi"))
            elif p == "/api-docs":
                valid = "swagger" in body.lower()[:3000] or "openapi" in body.lower()[:3000]
            else:
                valid = not is_html
            out[p] = 200 if valid else 0
        else:
            out[p] = code
    return out


def psi_cls(url):
    """CLS vía PageSpeed Insights (opcional). Requiere key para cuota decente."""
    api = ("https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
           f"?url={url}&category=PERFORMANCE&strategy=mobile")
    key = get_key("pagespeed")
    if key:
        api += f"&key={key}"
    res = fetch(api, timeout=90, verify_public=False)
    if res["status"] != 200:
        return None
    try:
        data = json.loads(res["body"])
        return float(data["lighthouseResult"]["audits"]
                     ["cumulative-layout-shift"]["numericValue"])
    except (KeyError, ValueError, TypeError):
        return None


def gather_context(base, typology_override=None, skip_render=False, with_psi=False):
    """Pipeline de recogida. Cada etapa deja rastro en ctx['trail'] (fiabilidad)."""
    ctx = {"base": base, "trail": []}

    def T(step, status, detail=""):
        ctx["trail"].append({"step": step, "status": status, "detail": str(detail)[:300]})

    _log("robots.txt…")
    ctx["robots"] = discovery.get_robots(base)
    rb = ctx["robots"]
    if rb["status"] == 0:
        T("robots.txt", "fail", "sin respuesta: checks 1.1-1.3 y 2.1 sin evidencia directa")
    else:
        T("robots.txt", "ok", f"HTTP {rb['status']}, {len(rb['raw'])} bytes"
          + (", devuelve HTML (hallazgo del sitio)" if rb["is_html"] else ""))

    _log("sitemap…")
    ctx["sitemap"] = discovery.get_sitemap_urls(base, ctx["robots"])
    ctx["sitemap_fresh"] = discovery.sitemap_freshness(ctx["sitemap"]["lastmods"])
    if ctx["sitemap"]["found"]:
        T("sitemap", "ok", f"{len(ctx['sitemap']['urls'])} URLs, {len(ctx['sitemap']['lastmods'])} lastmod")
    else:
        T("sitemap", "warn", "no localizado: muestreo limitado a la home (cobertura reducida)")

    _log("home…")
    ctx["home"] = fetch(base + "/", ua=UA_HUMAN)
    if ctx["home"]["status"] != 200 or len(ctx["home"]["body"]) < 500:
        if not skip_render:
            rendered = render_page(base + "/")
            if rendered.get("ok") and rendered.get("html"):
                ctx["home"]["body"] = rendered["html"]
                ctx["home"]["_via"] = "render"
        if len(ctx["home"].get("body", "")) < 500:
            jina = jina_read(base + "/")
            if jina:
                ctx["home"]["body"] = jina
                ctx["home"]["_via"] = "jina"
    via = ctx["home"].get("_via", "http")
    if len(ctx["home"].get("body", "")) < 500:
        T("home", "fail", "sin contenido por ninguna vía: checks de contenido sin evidencia")
    elif via != "http":
        T("home", "warn", f"obtenida vía {via} (acceso simple bloqueado/vacío): dato relevante")
    else:
        T("home", "ok", f"HTTP {ctx['home']['status']}, {len(ctx['home']['body'])} bytes, TTFB {ctx['home']['ttfb']}s")

    _log("matriz de acceso de bots de IA…")
    ctx["bot_matrix"] = bot_access_matrix(base + "/")
    human = ctx["bot_matrix"].get("_human", 0)
    codes = ", ".join(f"{k}={v}" for k, v in ctx["bot_matrix"].items())
    T("matriz de acceso de bots", "ok" if human == 200 else "warn",
      codes + ("" if human == 200 else " — el UA humano no recibe 200: WAF puede distorsionar"))

    if ctx["home"]["status"] == 0 and all(v == 0 for v in ctx["bot_matrix"].values()):
        raise RuntimeError(f"{base} no responde (DNS/conexión). Verifica el dominio.")

    _log("rate limiting…")
    ctx["rapid"] = rapid_fire(base + "/", BOT_UAS["GPTBot"], n=10)
    T("rate limiting", "ok", f"10 peticiones como GPTBot: {ctx['rapid']}")

    _log("superficie agéntica (.well-known)…")
    ctx["wellknown"] = probe_wellknown(base)
    hits = [p for p, c in ctx["wellknown"].items() if c == 200]
    T("superficie agéntica", "ok",
      f"{len(WELLKNOWN_PATHS)} rutas con validación de contenido; válidas: {', '.join(hits) or 'ninguna'}")

    all_urls = ctx["sitemap"]["urls"]
    typ, typ_ev = discovery.detect_typology(ctx["home"]["body"], all_urls)
    ctx["typology"] = typology_override or typ
    ctx["typology_evidence"] = typ_ev
    _log(f"tipología: {ctx['typology']}")
    T("detección de tipología", "ok",
      f"{ctx['typology']}" + (" (forzada)" if typology_override else f" — señales: {typ_ev}"))

    _log("muestreo de páginas…")
    buckets, sample = discovery.classify_and_sample(all_urls)
    ctx["buckets_size"] = {k: len(v) for k, v in buckets.items()}
    pages = []
    for item in sample:
        res = fetch(item["url"], ua=UA_HUMAN, timeout=20)
        if res["status"] != 200 or len(res["body"]) < 300:
            jina = jina_read(item["url"], timeout=60)
            if jina:
                res["body"] = jina
                res["status"] = res["status"] or 200
                res["_via"] = "jina"
        pages.append({"url": item["url"], "bucket": item["bucket"], "fetch": res})
    ctx["pages"] = pages
    ok_pages = sum(1 for p in pages if p["fetch"]["status"] == 200)
    via_fb = sum(1 for p in pages if p["fetch"].get("_via"))
    if not pages:
        T("muestreo de páginas", "warn", "0 páginas (sin sitemap): checks de contenido solo con la home")
    elif ok_pages < len(pages):
        T("muestreo de páginas", "warn",
          f"{ok_pages}/{len(pages)} accesibles ({via_fb} vía fallback); inaccesibles = hallazgo en 1.6")
    else:
        T("muestreo de páginas", "ok",
          f"{len(pages)} páginas de {len(all_urls)} URLs del sitemap ({via_fb} vía fallback)")
    if ctx["typology"] == "ecommerce" and not any(p["bucket"] == "producto" for p in pages):
        T("cobertura de producto", "warn",
          "e-commerce sin ficha de producto en el muestreo: 3.3/4.2/C7 por ausencia")

    if not skip_render:
        _log("render de la home (crudo vs JS)…")
        ctx["rendered_home"] = render_page(base + "/")
        if ctx["rendered_home"].get("ok"):
            T("render JS", "ok",
              f"{len(ctx['rendered_home'].get('html', ''))} bytes: check 4.1 con comparación real")
        else:
            T("render JS", "fail",
              f"{ctx['rendered_home'].get('error', '?')[:150]} — 4.1 degrada a heurístico")
    else:
        ctx["rendered_home"] = None
        T("render JS", "skipped", "desactivado: check 4.1 heurístico")

    _log("negociación Markdown y DNS-AID…")
    md = fetch(base + "/", timeout=15, headers=["Accept: text/markdown"])
    ct = ""
    m = re.search(r"(?im)^content-type:\s*([^\r\n;]+)", md["headers"] or "")
    if m:
        ct = m.group(1).strip()
    body_is_md = (md["status"] == 200 and "<html" not in (md["body"] or "")[:300].lower()
                  and bool(re.search(r"(?m)^#{1,3} \S", (md["body"] or "")[:2000])))
    ctx["md_negotiation"] = {"content_type": ct, "is_markdown": "markdown" in ct.lower() or body_is_md}
    T("negociación Markdown", "ok" if md["status"] else "fail",
      f"Accept: text/markdown -> HTTP {md['status']}, {ct or '?'}")

    ctx["dns_aid"] = discovery.dns_aid(base)
    T("DNS-AID", "ok" if ctx["dns_aid"] else "ok",
      ctx["dns_aid"] or "consultados TXT _aid/_agent: sin registros (evidencia negativa válida)")

    _log("vista LLM (Jina)…")
    jina = jina_read(base + "/")
    ctx["jina_home_excerpt"] = (jina or "")[:3000]
    ctx["jina_ok"] = bool(jina)
    T("vista LLM (Jina)", "ok" if jina else "warn",
      f"{len(jina)} chars" if jina else "Jina sin contenido (rate limit/bloqueo)")

    ctx["psi_cls"] = psi_cls(base + "/") if with_psi else None
    if with_psi:
        T("PageSpeed (CLS)", "ok" if ctx["psi_cls"] is not None else "fail",
          f"CLS={ctx['psi_cls']}" if ctx["psi_cls"] is not None else "PSI sin respuesta")
    ctx.setdefault("agent_tests", None)
    return ctx


CAT_NAMES = {
    "C1": "Descubribilidad y acceso", "C2": "Identidad y control de bots",
    "C3": "Datos estructurados", "C4": "Renderizado y arquitectura",
    "C5": "Contenido para LLMs", "C6": "Capacidades y acciones",
    "C7": "Comercio agéntico",
}


def audit_domain(base, typology_override=None, skip_render=False, with_psi=False,
                 categories=None, with_agents=False, allow_submit=False,
                 check_ids=None):
    """Audita un dominio y devuelve el dict de resultados (apto para JSON/UI)."""
    base = discovery.normalize(base)
    assert_public_url(base)  # anti-SSRF antes de nada
    ctx = gather_context(base, typology_override, skip_render, with_psi)

    if with_agents:
        _log("pruebas agénticas reales (varios minutos)…")
        try:
            from .agents import run_agent_tests
            ctx["agent_tests"] = run_agent_tests(
                base, ctx["typology"], allow_submit=allow_submit, log=LOG_SINK)
            agents = ctx["agent_tests"].get("agents", {})
            ran = [k for k, v in agents.items() if v.get("outcome") != "no_disponible"]
            det = f"agentes ejecutados: {', '.join(ran) or 'ninguno'}"
            if allow_submit:
                det += " [envío de formularios AUTORIZADO en este dominio]"
            ctx["trail"].append({"step": "pruebas agénticas (6.3)",
                                 "status": "ok" if ran else "fail", "detail": det})
        except Exception as exc:
            ctx["agent_tests"] = None
            ctx["trail"].append({"step": "pruebas agénticas (6.3)", "status": "fail",
                                 "detail": str(exc)[:200]})
    else:
        ctx["trail"].append({"step": "pruebas agénticas (6.3)", "status": "skipped",
                             "detail": "desactivadas: el check 6.3 queda como manual"})

    results = checks_mod.run_all(ctx)
    if categories:
        results = [r for r in results if r["cat"] in categories]
    if check_ids:
        results = [r for r in results if r["id"] in check_ids]

    total, cat_scores, weights = scoring.total_score(results, ctx["typology"])
    adjusted, penalties = scoring.apply_governance_gate(total, results, ctx["typology"])
    level = scoring.level_for(adjusted)

    from .knowledge import advice_for
    for r in results:
        if r["score"] is not None and r["score"] < 1:
            r["advice"] = advice_for(r["id"])

    return {
        "domain": base,
        "host": urlparse(base).netloc.replace("www.", ""),
        "typology": ctx["typology"],
        "typology_evidence": ctx["typology_evidence"],
        "score": adjusted,
        "score_pre_gate": total,
        "penalties": penalties,
        "level": level,
        "category_scores": cat_scores,
        "category_weights": {k: round(v, 1) for k, v in weights.items()},
        "checks": results,
        "bot_matrix": ctx["bot_matrix"],
        "buckets": ctx["buckets_size"],
        "pages_sampled": [{"url": p["url"], "bucket": p["bucket"],
                           "status": p["fetch"]["status"],
                           "via": p["fetch"].get("_via", "http")} for p in ctx["pages"]],
        "wellknown": {k: v for k, v in ctx["wellknown"].items() if v == 200},
        "jina_ok": ctx["jina_ok"],
        "render_ok": bool(ctx.get("rendered_home") and ctx["rendered_home"].get("ok")),
        "agent_tests": ctx.get("agent_tests"),
        "trail": ctx["trail"],
        "coverage": {
            "sitemap_urls": len(ctx["sitemap"]["urls"]),
            "sampled": len(ctx["pages"]),
            "sampled_ok": sum(1 for p in ctx["pages"] if p["fetch"]["status"] == 200),
            "fallbacks": sum(1 for p in ctx["pages"] if p["fetch"].get("_via")),
            "buckets": ctx["buckets_size"],
        },
    }


def run_audit(urls, typology=None, skip_render=False, with_psi=False,
              categories=None, log=None):
    """Audita cliente + competidores. Devuelve el dict 'data' completo para la UI."""
    global LOG_SINK
    if log is not None:
        LOG_SINK = log
    audits = []
    try:
        for u in urls[:3]:
            try:
                audits.append(audit_domain(u, typology, skip_render, with_psi, categories))
            except Exception as exc:
                audits.append({"domain": u, "error": str(exc)[:200]})
    finally:
        LOG_SINK = None
    return {
        "client": audits[0] if audits else None,
        "competitors": audits[1:],
        "framework_version": "2.0 (agent_scanner, integrado en clicandseo)",
    }
