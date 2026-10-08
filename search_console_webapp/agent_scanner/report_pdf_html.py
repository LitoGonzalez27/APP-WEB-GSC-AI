# -*- coding: utf-8 -*-
"""Informe PDF del Agent-Ready Scanner con la identidad de Clicandseo.

El informe se maqueta como HTML (plantilla templates/informe_pdf.html, con las
fuentes y los tokens del brandbook) y Chromium lo imprime a PDF. Railway ya
tiene Chromium: lo instala nixpacks.toml para el render y los agentes del
propio scanner.

Por qué HTML y no ReportLab: ReportLab no carga Inter Tight ni Libre
Baskerville sin empaquetar los TTF y cada componente había que dibujarlo a
mano; el resultado (Helvetica, barras naranja/amarillo fuera de paleta,
bloques de color de relleno) no se parecía a la marca. Con HTML el informe usa
exactamente el mismo sistema visual que el panel.

Estructura (la misma que el PDF anterior, para el mismo flujo: un CMO lo lee y
se lo pasa a su equipo técnico):
  portada · 01 resumen ejecutivo · 02 comparativa · 03 plan de acción ·
  04 pruebas con agentes · 05 anexo técnico · 06 metodología y fiabilidad

build_pdf() en report_pdf.py llama aquí y, si Chromium no está disponible o
falla, cae al generador ReportLab de siempre: un informe feo es mejor que
ningún informe.
"""
import os
import re
from datetime import datetime

from .catalog import CATEGORIES as CAT_NAMES

IMPORD = {"Crítico": 0, "Alto": 1, "Alto (apuesta de futuro)": 1,
          "Alto (ventana de oportunidad)": 1, "Medio": 2, "Medio (creciente)": 2,
          "Bajo": 3, "Bajo (hoy)": 3, "Diagnóstico": 4}
TIERS = [(0, "Crítico", "Está frenando a los agentes hoy. Arreglar lo primero."),
         (1, "Importante", "Alto impacto en visibilidad y en la capacidad de ser usado."),
         (2, "Mejoras recomendadas", "Suman puntos y pulen la experiencia del agente."),
         (3, "Menor", "Poca urgencia: para cuando el resto esté hecho.")]
STAGES = [("¿Te leen?", "Acceso y rastreo", ["C1", "C2"]),
          ("¿Te entienden?", "Datos y contenido", ["C3", "C4", "C5"]),
          ("¿Pueden usarte?", "Acciones y compra", ["C6", "C7"])]
SCALE = [(0, 25, "Invisible para agentes", "Ni te leen ni te usan."),
         (26, 50, "Legible, no operable", "Te leen, no te entienden bien, no te usan."),
         (51, 75, "Agent-aware", "Bien posicionado; faltan capacidades ejecutables."),
         (76, 100, "Agent-ready", "Ventaja competitiva real.")]
TYPOLOGY = {"ecommerce": "E-commerce", "saas": "SaaS", "corporativo": "Corporativo"}
AGENT_NAMES = {"chatgpt": "ChatGPT", "claude": "Claude", "gemini": "Gemini",
               "perplexity": "Perplexity"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# Tokens del brandbook (brand-dashboard-tokens.css / brand_palette.py).
# Slot 1 = tu web, siempre; competidores en violeta y magenta (slots 4 y 6):
# verde, ámbar y rojo quedan para el semáforo de estado, como en el panel.
SERIES = ["#2a78d6", "#4a3aa7", "#e87ba4"]
TEXT, TEXT2, TEXT3 = "#0F172A", "#64748B", "#94A3B8"
GRID, BORDER = "#EEF2F7", "#E2E8F0"
OK, BAD, ACCENT = "#3CB371", "#E05252", "#d9f9b8"
WARN = "#eda100"            # --cs-series-5, el "regular" del semáforo
OK_TEXT, WARN_TEXT, BAD_TEXT = "#287A4C", "#8F6100", "#D13B3B"


def _tone(p):
    """Semáforo de porcentajes: ≥75 bien, 50-74 regular, <50 mal."""
    return "good" if p >= 75 else "warn" if p >= 50 else "bad"


def _score_tone(s):
    """Semáforo de la nota global por tramos: 0-50 mal, 51-75 regular, 76+ bien."""
    s = s or 0
    return "good" if s > 75 else "warn" if s > 50 else "bad"

_TEMPLATE = os.path.join(os.path.dirname(__file__), "templates", "informe_pdf.html")


# ----------------------------------------------------------------- utilidades

def _pct(v):
    return round((v or 0) * 100)


def _band(score):
    s = score or 0
    return 0 if s <= 25 else 1 if s <= 50 else 2 if s <= 75 else 3


def _fecha_larga(iso):
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    except ValueError:
        return str(iso)[:10]


def _estado(p):
    if p >= 75:
        return "Fuerte", "good"
    if p >= 50:
        return "Mejorable", "warn"
    if p >= 25:
        return "Flojo", "bad"
    return "Crítico", "bad"


def _stages(audit):
    cs = audit.get("category_scores") or {}
    out = []
    for name, desc, cats in STAGES:
        vals = [cs[c] for c in cats if cs.get(c) is not None]
        if vals:
            p = round(sum(vals) / len(vals) * 100)
            out.append({"name": name, "desc": desc, "cats": " + ".join(cats), "p": p, "tone": _tone(p)})
    if len(out) > 1:
        weakest = min(out, key=lambda s: s["p"])
        weakest["weak"] = True
    return out


def _balance(audit):
    ch = audit.get("checks") or []
    n = {"ok": sum(1 for c in ch if (c.get("score") is not None and c["score"] >= 1)),
         "part": sum(1 for c in ch if c.get("score") is not None and 0 < c["score"] < 1),
         "bad": sum(1 for c in ch if c.get("score") == 0),
         "na": sum(1 for c in ch if c.get("score") is None)}
    n["total"] = len(ch) or 1
    return n


def _mark(score):
    if score is None:
        return ("–", "na")
    if score >= 1:
        return ("✓", "ok")
    if score > 0:
        return ("◐", "part")
    return ("✕", "bad")


# ------------------------------------------------------------------ gráficos

def gauge_svg(score, parcial=False, dark=False, size=220):
    """Semicírculo de la puntuación. En la portada (oscura) el arco va en
    Bio-Lime, que solo es legible sobre #0A0A0B."""
    import math
    w, h, r = size, size * 0.62, size * 0.4
    cx, cy = w / 2, h - 12
    frac = max(0.0, min(1.0, (score or 0) / 100))
    length = math.pi * r
    if dark:
        track, col, num, sub, tick = "rgba(255,255,255,0.08)", ACCENT, "#F8FAFC", "rgba(255,255,255,0.4)", "#0A0A0B"
    else:
        col = TEXT3 if parcial else {"good": OK, "warn": WARN, "bad": BAD}[_score_tone(score)]
        track, num, sub, tick = GRID, TEXT, TEXT3, "#FFFFFF"
    arc = f"M {cx - r:.1f} {cy:.1f} A {r:.1f} {r:.1f} 0 0 1 {cx + r:.1f} {cy:.1f}"
    ticks = ""
    for t in (25, 50, 75):
        a = math.pi * (1 - t / 100)
        ticks += (f'<line x1="{cx + (r - 9) * math.cos(a):.1f}" y1="{cy - (r - 9) * math.sin(a):.1f}" '
                  f'x2="{cx + (r + 9) * math.cos(a):.1f}" y2="{cy - (r + 9) * math.sin(a):.1f}" '
                  f'stroke="{tick}" stroke-width="3"/>')
    etiqueta = "nota parcial" if parcial else "de 100"
    return (f'<svg width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}" role="img">'
            f'<path d="{arc}" fill="none" stroke="{track}" stroke-width="15" stroke-linecap="round"/>'
            f'<path d="{arc}" fill="none" stroke="{col}" stroke-width="15" stroke-linecap="round" '
            f'stroke-dasharray="{frac * length:.1f} {length:.1f}"/>{ticks}'
            f'<text x="{cx:.1f}" y="{cy - 22:.1f}" text-anchor="middle" fill="{num}" '
            f'font-family="Inter Tight" font-size="{size * 0.2:.0f}" font-weight="800" letter-spacing="-2">{score:g}</text>'
            f'<text x="{cx:.1f}" y="{cy - 2:.1f}" text-anchor="middle" fill="{sub}" font-family="Inter Tight" '
            f'font-size="11" font-weight="600">{etiqueta}</text></svg>')


def radar_svg(audits, size=300):
    import math
    cats = [c for c in CAT_NAMES if any((a.get("category_scores") or {}).get(c) is not None for a in audits)]
    if len(cats) < 3:
        return ""
    cx = cy = size / 2
    rad, n = size / 2 - 36, len(cats)

    def pt(i, r):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + r * math.cos(a), cy + r * math.sin(a)

    out = [f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img">']
    for ring in (0.25, 0.5, 0.75, 1):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, rad * ring) for i in range(n)))
        out.append(f'<polygon points="{pts}" fill="none" stroke="{GRID}" stroke-width="1"/>')
    for i, c in enumerate(cats):
        x, y = pt(i, rad)
        lx, ly = pt(i, rad + 18)
        anchor = "end" if lx < cx - 8 else "start" if lx > cx + 8 else "middle"
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{GRID}"/>'
                   f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{TEXT2}" font-family="Inter Tight" font-size="10" '
                   f'font-weight="600" text-anchor="{anchor}" dominant-baseline="middle">{c}</text>')
    for idx, a in enumerate(audits):
        col, cs = SERIES[idx % 3], a.get("category_scores") or {}
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, rad * (cs.get(c) or 0)) for i, c in enumerate(cats)))
        out.append(f'<polygon points="{pts}" fill="{col}" fill-opacity="{0.14 if idx == 0 else 0.06}" '
                   f'stroke="{col}" stroke-width="{2.2 if idx == 0 else 1.5}" stroke-linejoin="round"/>')
    out.append("</svg>")
    return "".join(out)


def dot_grid_svg(w=210, h=297):
    """Textura de puntos de la portada (Brandbook §11.3) como patrón SVG plano."""
    return (f'<svg class="cover-dots" width="{w}mm" height="{h}mm" viewBox="0 0 {w * 4} {h * 4}" '
            f'preserveAspectRatio="none"><defs><pattern id="d" width="32" height="32" '
            f'patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#FFFFFF" '
            f'fill-opacity="0.09"/></pattern></defs><rect width="100%" height="100%" fill="url(#d)"/></svg>')


# ------------------------------------------------------------------ contexto

def _aviso_fiabilidad(dom, etiqueta):
    """Mismo aviso que el panel: sale del veredicto (scoring.py) e informa sin
    alarmar. Un bloqueo desde nuestra red no es un veredicto sobre la web."""
    deg = dom.get("acceso_degradado")
    if dom.get("score_fiable", True) or not deg:
        return None
    lvl = dom.get("level") or {}
    if lvl.get("cobertura_parcial"):
        titulo = lvl.get("name", "No evaluable desde nuestra red")
        cuerpo = lvl.get("msg", "")
    else:
        titulo = "Lectura limitada"
        cuerpo = deg.get("motivo", "")
    cob = dom.get("cobertura_score")
    return {"titulo": titulo, "etiqueta": etiqueta, "cuerpo": cuerpo,
            "degradados": deg.get("degradados", 0),
            "cobertura": round(cob * 100) if isinstance(cob, (int, float)) else None}


def _findings(checks):
    items = [c for c in checks if c.get("advice") and c.get("score") is not None and c["score"] < 1]
    items.sort(key=lambda c: (IMPORD.get(c["advice"].get("impacto"), 3), c["score"],
                              0 if c["advice"].get("esfuerzo") == "Bajo" else 1))
    tiers = []
    for ord_, name, hint in TIERS:
        t_items = [c for c in items if min(IMPORD.get(c["advice"].get("impacto"), 3), 3) == ord_]
        if t_items:
            tiers.append({"ord": ord_, "name": name, "hint": hint, "hallazgos": [{
                "id": c.get("id"), "name": c.get("name"),
                "titulo": c["advice"].get("titulo", ""), "por_que": c["advice"].get("por_que", ""),
                "como": c["advice"].get("como", ""), "impacto": c["advice"].get("impacto", ""),
                "esfuerzo": c["advice"].get("esfuerzo", ""),
                "qw": c["advice"].get("esfuerzo") == "Bajo" and IMPORD.get(c["advice"].get("impacto"), 3) <= 2,
            } for c in t_items]})
    return tiers, len(items)


def _agentes(audits):
    out = []
    for i, a in enumerate(audits):
        at = a.get("agent_tests") or {}
        if not at.get("agents"):
            continue
        agentes = []
        for name, r in at["agents"].items():
            o = str(r.get("outcome") or "?")
            tone = ("ok" if o == "conseguido" else "na" if o == "no_disponible"
                    else "warn" if o in ("conseguido_con_friccion", "inconsistente") else "bad")
            p = r.get("progreso") or {}
            hechos = {h.get("nombre") for h in (p.get("hitos") or [])}
            todos = at.get("hitos_tarea") or [h.get("nombre") for h in (p.get("hitos") or [])] + list(p.get("pendientes") or [])
            agentes.append({
                "name": AGENT_NAMES.get(name, name), "outcome": o.replace("_", " "), "tone": tone,
                "steps": r.get("steps"), "detail": r.get("detail") or "",
                "intentos": r.get("intentos") or 0, "exitos": r.get("exitos") or 0,
                "runs": [str(x.get("outcome") or "").startswith("conseguido") for x in (r.get("runs") or [])],
                "alcanzados": p.get("alcanzados"), "total": p.get("total"),
                "hitos": [{"nombre": h, "ok": h in hechos} for h in todos] if p.get("total") else [],
            })
        out.append({"host": a.get("host"), "color": SERIES[i % 3], "typology": TYPOLOGY.get(at.get("typology"), at.get("typology")),
                    "allow_submit": at.get("allow_submit"), "agentes": agentes})
    return out


def _veredicto_fiabilidad(audit):
    trail = audit.get("trail") or []
    if not trail:
        return None
    n = {"ok": 0, "warn": 0, "fail": 0, "skipped": 0}
    for t in trail:
        n[t.get("status")] = n.get(t.get("status"), 0) + 1
    if n["fail"]:
        return {"tone": "bad", "titulo": "Análisis incompleto",
                "msg": f"{n['fail']} proceso(s) fallaron y hay checks sin evidencia."}
    if n["warn"] or n["skipped"]:
        return {"tone": "warn", "titulo": "Fiable con avisos",
                "msg": f"Todos los procesos corrieron; {n['warn']} con evidencia degradada y {n['skipped']} desactivados."}
    return {"tone": "good", "titulo": "Análisis completo y fiable",
            "msg": "Todos los procesos se ejecutaron con evidencia directa."}


def build_context(data):
    client = data.get("client") or {}
    comps = [c for c in (data.get("competitors") or []) if "error" not in c]
    audits = [client] + comps
    checks = client.get("checks") or []
    lvl = client.get("level") or {}
    parcial = bool(lvl.get("cobertura_parcial"))
    score = client.get("score", 0) or 0
    cs = client.get("category_scores") or {}

    categorias = []
    for c, nombre in CAT_NAMES.items():
        if cs.get(c) is None:
            continue
        p = _pct(cs[c])
        est, tone = _estado(p)
        categorias.append({"id": c, "name": nombre, "p": p, "estado": est, "tone": tone})

    quick = [c for c in checks if c.get("advice") and c.get("score") is not None
             and c["score"] < 1 and c["advice"].get("esfuerzo") == "Bajo"
             and IMPORD.get(c["advice"].get("impacto"), 3) <= 2]

    tipos = sorted({a.get("typology") for a in audits})
    mixto = len(tipos) > 1
    con_nota = [a for a in audits if not (a.get("level") or {}).get("cobertura_parcial")]
    best = max((a.get("score", 0) for a in con_nota), default=None) if (not mixto and con_nota) else None
    ranking = [{"host": a.get("host"), "color": SERIES[i % 3], "rol": "Tu web" if i == 0 else f"Competidor {i}",
                "typology": TYPOLOGY.get(a.get("typology"), a.get("typology")),
                "level": (a.get("level") or {}).get("name", ""), "score": a.get("score", 0),
                "tone": _score_tone(a.get("score", 0)),
                "win": best is not None and len(audits) > 1 and a.get("score") == best
                and not (a.get("level") or {}).get("cobertura_parcial")} for i, a in enumerate(audits)]
    matriz = []
    for c, nombre in CAT_NAMES.items():
        vals = [(a.get("category_scores") or {}).get(c) for a in audits]
        if all(v is None for v in vals):
            continue
        con_valor = [v for v in vals if v is not None]
        mx = max(con_valor)
        resalta = len(con_valor) > 1 and mx > 0
        matriz.append({"id": c, "name": nombre, "celdas": [
            None if v is None else {"p": _pct(v), "best": resalta and v == mx, "color": SERIES[i % 3],
                                    "tone": _tone(_pct(v))}
            for i, v in enumerate(vals)]})
    gaps = []
    for c, nombre in CAT_NAMES.items():
        mine = cs.get(c)
        if mine is None:
            continue
        for comp in comps:
            v = (comp.get("category_scores") or {}).get(c)
            if v is not None and v - mine >= 0.15:
                gaps.append({"id": c, "name": nombre, "host": comp.get("host"),
                             "diff": _pct(v - mine), "v": _pct(v), "mine": _pct(mine)})
    gaps.sort(key=lambda g: -g["diff"])

    tiers, n_findings = _findings(checks)
    avisos = [w for w in [_aviso_fiabilidad(client, "Tu dominio")]
              + [_aviso_fiabilidad(c, c.get("host", "competidor")) for c in comps] if w]

    anexo = []
    for c in checks:
        g, tone = _mark(c.get("score"))
        ev = str(c.get("evidence") or "")
        anexo.append({"id": c.get("id"), "name": c.get("name"), "glyph": g, "tone": tone,
                      "evidence": ev if len(ev) <= 320 else ev[:317] + "…",
                      "manual": c.get("manual")})

    cov = client.get("coverage") or {}
    trail = [{"step": t.get("step"), "status": t.get("status"),
              "glyph": {"ok": "✓", "warn": "◐", "fail": "✕", "skipped": "○"}.get(t.get("status"), "?"),
              "tone": {"ok": "ok", "warn": "part", "fail": "bad", "skipped": "na"}.get(t.get("status"), "na"),
              "detail": (str(t.get("detail") or "")[:220])} for t in (client.get("trail") or [])]
    pesos = [{"id": k, "name": CAT_NAMES.get(k, k), "v": v}
             for k, v in (client.get("category_weights") or {}).items()]
    ag = data.get("agentes") or {}
    band = _band(score)

    return {
        "host": client.get("host", "—"),
        "fecha": _fecha_larga(data.get("generated")),
        "typology": TYPOLOGY.get(client.get("typology"), client.get("typology") or "—"),
        "competidores": [c.get("host") for c in comps],
        "score": score, "parcial": parcial, "score_tone": _score_tone(score),
        "level_name": lvl.get("name", ""), "level_msg": lvl.get("msg", ""),
        "band": band, "scale": SCALE, "marker": max(0, min(100, score)),
        "gauge_cover": gauge_svg(score, parcial, dark=True, size=250),
        "gauge": gauge_svg(score, parcial, size=210),
        "dots": dot_grid_svg(),
        "via_lectura": client.get("via_lectura") if client.get("via_lectura") not in (None, "http") else None,
        "cobertura": round(client["cobertura_score"] * 100) if parcial and isinstance(client.get("cobertura_score"), (int, float)) else None,
        "avisos": avisos,
        "balance": _balance(client),
        "penalties": [{"name": p[0], "v": p[1]} for p in (client.get("penalties") or [])],
        "stages": _stages(client),
        "categorias": categorias,
        "quick": [{"titulo": c["advice"]["titulo"], "como": c["advice"]["como"],
                   "tier": min(IMPORD.get(c["advice"].get("impacto"), 3), 3),
                   "impacto": c["advice"].get("impacto"), "esfuerzo": c["advice"].get("esfuerzo")}
                  for c in sorted(quick, key=lambda c: IMPORD.get(c["advice"].get("impacto"), 3))[:6]],
        "n_checks": len(checks),
        "competencia": len(audits) > 1,
        "mixto": mixto, "tipos": [TYPOLOGY.get(t, t) for t in tipos],
        "ranking": ranking, "matriz": matriz, "gaps": gaps,
        "radar": radar_svg(audits) if len(audits) > 1 else "",
        "audits_head": [{"host": a.get("host"), "color": SERIES[i % 3]} for i, a in enumerate(audits)],
        "tiers": tiers, "n_findings": n_findings,
        "agentes": _agentes(audits), "agentes_detalle": ag.get("detalle") if ag.get("estado") in ("completado", "error") else None,
        "anexo": anexo,
        "fiabilidad": _veredicto_fiabilidad(client),
        "manual": [{"id": c.get("id"), "name": c.get("name")} for c in checks if c.get("manual")],
        "coverage": cov, "trail": trail, "pesos": pesos,
        "framework": data.get("framework_version", ""),
    }


# ------------------------------------------------------------------- render

def render_html(data):
    """HTML completo del informe (portada + cuerpo)."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(loader=FileSystemLoader(os.path.dirname(_TEMPLATE)),
                      autoescape=select_autoescape(["html"]))
    return env.get_template(os.path.basename(_TEMPLATE)).render(**build_context(data))


_FOOTER = """<div style="width:100%;padding:0 16mm;font-family:'Inter Tight',Helvetica,Arial,sans-serif;
font-size:7.5px;color:#94A3B8;display:flex;justify-content:space-between;">
<span>Clicandseo · Agent Readiness · {host}</span><span>Página <span class="pageNumber"></span></span></div>"""


def html_to_pdf(html, host="", timeout_ms=45000):
    """Imprime el HTML con Chromium. La portada se imprime aparte (a sangre y sin
    pie de página) y se une al cuerpo; si pypdf no estuviera, se entrega el
    documento en una pieza con la portada incluida."""
    from playwright.sync_api import sync_playwright

    portada, cuerpo = _split(html)
    try:
        import pypdf  # noqa: F401  (une portada y cuerpo)
    except ImportError:
        # sin pypdf no se pueden unir dos PDFs: una sola pieza, portada incluida
        portada, cuerpo = None, html
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page()

            def _print(doc, **kw):
                page.set_content(doc, wait_until="networkidle", timeout=timeout_ms)
                page.evaluate("document.fonts.ready.then(() => true)")
                return page.pdf(format="A4", print_background=True, **kw)

            footer = _FOOTER.format(host=_esc(host))
            body_pdf = _print(cuerpo, display_header_footer=True,
                              header_template="<div></div>", footer_template=footer,
                              margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
            if portada is None:
                return body_pdf
            cover_pdf = _print(portada, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        finally:
            browser.close()
    return _merge(cover_pdf, body_pdf)


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


_COVER_RE = re.compile(r"<!--\s*PORTADA\s*-->(.*?)<!--\s*/PORTADA\s*-->", re.S)


def _split(html):
    """La plantilla marca la portada entre comentarios: se generan dos
    documentos con el mismo <head> (estilos y fuentes)."""
    m = _COVER_RE.search(html)
    if not m:
        return None, html
    head_end = html.index("<body")
    head = html[:head_end]
    portada = head + '<body class="is-cover">' + m.group(1) + "</body></html>"
    cuerpo = html[:m.start()] + html[m.end():]
    return portada, cuerpo


def _merge(cover_pdf, body_pdf):
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for src in (cover_pdf, body_pdf):
        for pg in PdfReader(BytesIO(src)).pages:
            w.add_page(pg)
    out = BytesIO()
    w.write(out)
    return out.getvalue()


def build_pdf_html(data):
    """Bytes del PDF con la identidad de marca. Lanza excepción si Chromium no
    está disponible: quien llama decide el respaldo."""
    host = (data.get("client") or {}).get("host", "")
    return html_to_pdf(render_html(data), host=host)
