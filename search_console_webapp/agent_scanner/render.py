# -*- coding: utf-8 -*-
"""Render de páginas con JavaScript, con backend enchufable.

- playwright: en servidor (Railway ya tiene Chromium instalado).
- camoufox:   en local vía el venv de scraping (antidetección).
- none:       sin render; el check 4.1 degrada a heurístico.

Todos devuelven: {"ok": bool, "status": int, "html": str, "error": str}
"""
import json
import os
import subprocess

from .config import render_backend

_CAMOUFOX_PY = os.path.expanduser("~/Desktop/proyectos/.venv-seo-scraping/bin/python3")
_CAMOUFOX_PROBE = os.path.join(os.path.dirname(__file__), "_camoufox_probe.py")


def render(url, timeout=90):
    backend = render_backend()
    if backend == "playwright":
        return _render_playwright(url, timeout)
    if backend == "camoufox":
        return _render_camoufox(url, timeout)
    return {"ok": False, "error": "sin backend de render disponible", "html": "", "status": 0}


def _render_playwright(url, timeout):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright no instalado", "html": "", "status": 0}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            resp = page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            html = page.content()
            status = resp.status if resp else 200
            browser.close()
            return {"ok": True, "status": status, "html": html[:2_000_000], "error": None}
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
