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


def render(url, timeout=90, interactive=False):
    backend = render_backend()
    if backend == "playwright":
        return _render_playwright(url, timeout, interactive)
    if backend == "camoufox":
        return _render_camoufox(url, timeout)
    return {"ok": False, "error": "sin backend de render disponible", "html": "", "status": 0}


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
            boxes = None
            if interactive:
                try:
                    boxes = page.evaluate(INTERACTIVE_JS)
                except Exception:
                    boxes = None
            browser.close()
            return {"ok": True, "status": status, "html": html[:2_000_000],
                    "boxes": boxes, "error": None}
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
