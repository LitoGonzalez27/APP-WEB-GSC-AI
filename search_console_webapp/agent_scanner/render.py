# -*- coding: utf-8 -*-
"""Render de páginas con JavaScript, con backend enchufable.

- playwright: en servidor (Railway ya tiene Chromium instalado).
- camoufox:   en local vía el venv de scraping (antidetección).
- none:       sin render; el check 4.1 degrada a heurístico.

Todos devuelven: {"ok": bool, "status": int, "html": str, "error": str}
y, cuando el backend lo permite, "boxes": geometria real de los controles
interactivos (para el check 4.7 de zonas de clic).
"""
import json
import os
import subprocess

from .config import render_backend

_CAMOUFOX_PY = os.path.expanduser("~/Desktop/proyectos/.venv-seo-scraping/bin/python3")
_CAMOUFOX_PROBE = os.path.join(os.path.dirname(__file__), "_camoufox_probe.py")

# Mide los controles que un agente intentaria accionar. Solo cuentan los que
# ocupan espacio real: los de 0x0 o display:none no son clicables por nadie.
INTERACTIVE_JS = """
() => {
  const SEL = 'a[href], button, input:not([type=hidden]), select, textarea,' +
              '[role=button], [role=link], [role=tab], [onclick]';
  const NATIVE = ['A','BUTTON','INPUT','SELECT','TEXTAREA'];
  const out = [];
  for (const el of Array.from(document.querySelectorAll(SEL)).slice(0, 500)) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || cs.opacity === '0') continue;
    out.push({
      tag: el.tagName.toLowerCase(),
      w: Math.round(r.width),
      h: Math.round(r.height),
      cursor: cs.cursor,
      // WCAG 2.2 exceptua los enlaces en linea dentro de texto corrido: su
      // altura la marca el line-height, no el diseno, y son faciles de acertar
      inline: cs.display === 'inline' && el.tagName === 'A',
      native: NATIVE.includes(el.tagName),
      name: (el.getAttribute('aria-label') || el.innerText || el.value || '')
              .trim().replace(/\\s+/g, ' ').slice(0, 50)
    });
  }
  return out;
}
"""


# Cumulative Layout Shift real: suma los saltos de layout que NO responden a una
# interacción (hadRecentInput=false), que son los que descolocan a un agente que
# captura pantalla entre acciones. buffered:true recoge también los saltos
# ocurridos antes de instalar el observer.
_CLS_JS = """
() => new Promise(resolve => {
  let cls = 0;
  try {
    new PerformanceObserver(list => {
      for (const e of list.getEntries()) { if (!e.hadRecentInput) cls += e.value; }
    }).observe({type: 'layout-shift', buffered: true});
  } catch (e) { return resolve(null); }
  setTimeout(() => resolve(Math.round(cls * 1000) / 1000), 2000);
})
"""


def render(url, timeout=90, interactive=False):
    backend = render_backend()
    if backend == "playwright":
        return _render_playwright(url, timeout, interactive)
    if backend == "camoufox":
        return _render_camoufox(url, timeout)
    return {"ok": False, "error": "sin backend de render disponible", "html": "", "status": 0}


# Roles del árbol que un agente puede ACCIONAR. Un nodo con uno de estos roles
# y sin nombre accesible es un control que el agente ve pero no sabe para qué
# sirve: puede pulsarlo, no puede decidir si debe.
ROLES_ACCIONABLES = {"button", "link", "textbox", "combobox", "checkbox",
                     "radio", "menuitem", "tab", "searchbox", "switch",
                     "slider", "spinbutton", "listbox", "option"}
# Nombres que existen pero no dicen nada: el agente sigue sin saber qué hace.
NOMBRES_VACIOS = {"", "link", "button", "enlace", "botón", "boton", "más",
                  "mas", "more", "click here", "clic aquí", "leer más",
                  "read more", "ver más", "ver mas", "aquí", "aqui", "here",
                  "…", "...", ">", "<", "→", "x"}


def _resumen_ax(nodo):
    """Resume el árbol de accesibilidad en lo que le importa a un agente.

    No se guarda el árbol entero (son cientos de nodos y acabaría en el JSON del
    informe): solo el recuento y una muestra de los controles problemáticos, que
    es lo accionable para quien tiene que arreglarlo.
    """
    if not nodo:
        return None
    total = accionables = sin_nombre = generico = 0
    ejemplos = []

    def rec(n, profundidad=0):
        nonlocal total, accionables, sin_nombre, generico
        total += 1
        rol = (n.get("role") or "").lower()
        if rol in ROLES_ACCIONABLES:
            accionables += 1
            nombre = (n.get("name") or "").strip()
            if not nombre:
                sin_nombre += 1
                if len(ejemplos) < 8:
                    ejemplos.append({"rol": rol, "nombre": None, "problema": "sin nombre"})
            elif nombre.lower().strip(" .:·-") in NOMBRES_VACIOS:
                generico += 1
                if len(ejemplos) < 8:
                    ejemplos.append({"rol": rol, "nombre": nombre[:40],
                                     "problema": "nombre genérico"})
        for h in (n.get("children") or []):
            rec(h, profundidad + 1)

    rec(nodo)
    return {"nodos": total, "accionables": accionables, "sin_nombre": sin_nombre,
            "nombre_generico": generico, "ejemplos": ejemplos}


def _render_playwright(url, timeout, interactive=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright no instalado", "html": "", "status": 0}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            # MEDIDO, no supuesto (batería 5, 6 dominios × 3 variantes):
            #   veepee.es    networkidle 2.3s / dcl+3s 4.0s → HTML IDÉNTICO
            #   ikea.com     networkidle 4.5s / dcl+3s 4.4s → HTML IDÉNTICO
            #   mediamarkt   networkidle TIMEOUT 90s, 0 bytes / dcl+3s 3.9s, 942 KB
            #   gymshark     networkidle TIMEOUT 90s, 0 bytes / dcl+3s 4.5s, 2,9 MB
            # Mismo texto, mismos <a href> y mismos bloques JSON-LD en los que
            # comparan; en los dos que llevan sockets de analítica siempre
            # abiertos, networkidle NUNCA se cumple y nos quedábamos sin render
            # (gymshark salió con render_ok=False y mediamarkt con 4.1 degradado
            # a heurístico). domcontentloaded no pierde contenido: lo rescata.
            # Esperar 6s en vez de 3s no añadió nada en ningún dominio.
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            # margen para que el JS de cliente pinte lo que el check 4.1 compara
            page.wait_for_timeout(3000)
            html = page.content()
            status = resp.status if resp else 200
            boxes = ax = cls = None
            if interactive:
                try:
                    boxes = page.evaluate(INTERACTIVE_JS)
                except Exception:
                    boxes = None
                # CLS real, medido en el navegador. El check 4.6 dependía de
                # PageSpeed (with_psi), que en producción NUNCA se activa: era un
                # factor de los 40 que jamás puntuaba. Aquí se mide en la misma
                # pasada de render, sin API externa ni clave.
                try:
                    cls = page.evaluate(_CLS_JS)
                except Exception:
                    cls = None
                # Árbol de accesibilidad REAL, el mismo que consumen los agentes
                # de navegación. Se toma en la misma pasada que boxes: no cuesta
                # ni una navegación más. Antes el check 3.6 lo aproximaba con
                # regex sobre el HTML crudo y se parecía poco al árbol de verdad
                # (medido: r=0.35 sobre 14 dominios).
                try:
                    ax = _resumen_ax(page.accessibility.snapshot())
                except Exception:
                    ax = None
            browser.close()
            return {"ok": True, "status": status, "html": html[:2_000_000],
                    "boxes": boxes, "ax": ax, "cls": cls, "error": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300], "html": "", "status": 0}


def _render_camoufox(url, timeout):
    if not os.path.exists(_CAMOUFOX_PY):
        return {"ok": False, "error": "venv camoufox no encontrado", "html": "", "status": 0}
    try:
        proc = subprocess.run([_CAMOUFOX_PY, _CAMOUFOX_PROBE, url],
                              capture_output=True, text=True, timeout=timeout + 90)
        line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
        return json.loads(line)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout renderizando", "html": "", "status": 0}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300], "html": "", "status": 0}
