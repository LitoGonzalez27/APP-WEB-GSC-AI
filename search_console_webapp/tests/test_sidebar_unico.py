"""
Sidebar único (oct-2026).

Había seis copias del sidebar (~110 líneas cada una) que ya no coincidían: una
entrada mal rotulada en AI Mode, cuatro formas de navegar y botones en vez de
enlaces. Ahora todas las páginas incluyen templates/partials/sidebar.html con
`{% set nav_activo = '…' %}`. Estos tests impiden volver a copiarlo y fijan lo
que el JS de /app (sidebar-navigation.js) y el de exportación necesitan.
"""

import pathlib
import re

from jinja2 import Environment, FileSystemLoader

PLANTILLAS = pathlib.Path(__file__).resolve().parent.parent / "templates"
CON_SIDEBAR = {
    "index.html": "gsc",
    "manual_ai_dashboard.html": "aio",
    "ai_mode_dashboard.html": "aimode",
    "llm_monitoring.html": "llm",
    "ai_summary.html": "summary",
    "agent_scanner.html": "agent",
}
PASOS_GSC = ("navConfiguration", "navPerformance", "navKeywords", "navPages", "navAI",
             "statusConfiguration", "statusPerformance", "statusKeywords", "statusPages", "statusAI")


def _render(activo, user={"id": 1}, acceso=True):
    env = Environment(loader=FileSystemLoader(str(PLANTILLAS)))
    return env.get_template("partials/sidebar.html").render(
        nav_activo=activo, user=user, agent_readiness_access=lambda u: acceso and bool(u))


def test_cada_pagina_incluye_el_sidebar_con_su_seccion():
    for nombre, activo in CON_SIDEBAR.items():
        texto = (PLANTILLAS / nombre).read_text(encoding="utf-8")
        assert "{% include 'partials/sidebar.html' %}" in texto, nombre
        assert re.search(r"\{%\s*set nav_activo = '" + activo + r"'\s*%\}", texto), nombre


def test_nadie_vuelve_a_copiar_el_sidebar():
    for p in PLANTILLAS.glob("*.html"):
        texto = p.read_text(encoding="utf-8")
        assert 'class="sidebar-container"' not in texto, p.name
        assert 'id="sidebarMobileOverlay"' not in texto, p.name


def test_una_sola_seccion_activa_y_con_aria_current():
    for activo in ("aio", "aimode", "llm", "summary", "agent"):
        html = _render(activo)
        assert html.count('aria-current="page"') == 1, activo
        assert html.count(" active") == 1, activo


def test_app_despliega_los_pasos_de_search_console_con_sus_ids():
    html = _render("gsc")
    for id_ in PASOS_GSC:
        assert f'id="{id_}"' in html, id_
    assert 'href="/app"' not in html          # en /app no hay entrada plegada
    otra = _render("llm")
    assert 'href="/app"' in otra               # fuera de /app, una sola entrada
    assert not any(f'id="{id_}"' in otra for id_ in PASOS_GSC)


def test_navegacion_con_enlaces_y_sin_onclick():
    html = _render("llm")
    assert "onclick" not in html
    for href in ("/manual-ai/", "/ai-mode-projects/", "/llm-monitoring", "/ai-summary/", "/agent/"):
        assert f'href="{href}"' in html, href


def test_agent_readiness_solo_con_acceso_y_sin_sesion_bloqueado():
    assert 'href="/agent/"' not in _render("llm", acceso=False)
    anonimo = _render("gsc", user=None)
    assert 'href="/manual-ai/"' not in anonimo and 'aria-disabled="true"' in anonimo


def test_exportaciones_fuera_del_sidebar():
    for nombre, ids in (("index.html", ("exportExcelBtn", "exportJsonBtn", "exportPdfBtn")),
                        ("manual_ai_dashboard.html", ("exportExcelBtn", "exportPdfBtn")),
                        ("ai_mode_dashboard.html", ("exportExcelBtn", "exportPdfBtn")),
                        ("llm_monitoring.html", ("llmDownloadExcelBtn", "llmDownloadPdfBtn"))):
        texto = (PLANTILLAS / nombre).read_text(encoding="utf-8")
        assert 'id="exportTools"' in texto, nombre
        for id_ in ids:
            assert f'id="{id_}"' in texto, (nombre, id_)
    assert "export" not in _render("llm").lower()
