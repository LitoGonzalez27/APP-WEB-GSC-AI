"""
Piezas comunes de las plantillas (estructura, sep-2026).

Favicons y Google Tag Manager estaban copiados en 12-13 plantillas; ahora
viven en templates/partials/ y se incluyen. Al cambiarlo se comprobó que cada
plantilla produce el mismo HTML que antes (login y signup ganan el comentario
de cierre de GTM que les faltaba). Estos tests impiden volver a copiarlos y
comprueban que las piezas se renderizan con la app real.
"""

import pathlib
import re

import pytest

PLANTILLAS = pathlib.Path(__file__).resolve().parent.parent / "templates"
GTM_ID = "GTM-NXJS74ZQ"
PIEZAS = ("partials/favicons.html", "partials/gtm_head.html", "partials/gtm_body.html")

# Qué páginas llevan cada pieza. Perder una (o ganarla sin querer) hace fallar el test.
CON_GTM = {
    "ai_mode_dashboard.html", "ai_summary.html", "dashboard.html", "forgot_password.html", "index.html",
    "landing.html", "llm_monitoring.html", "login.html", "manual_ai_dashboard.html", "reset_password.html",
    "signup.html", "user_profile.html",
}
CON_FAVICONS = CON_GTM | {"mobile_error.html"}
# Copias propias permitidas: billing_success.html tiene 3 favicons suyos (sin manifest).
COPIAS_PERMITIDAS = {("billing_success.html", "images/favicons/")}


def _include(pieza):
    return re.compile(r"""\{%-?\s*include\s+['"]""" + re.escape(pieza) + r"""['"]\s*-?%\}""")


def _paginas():
    return sorted(PLANTILLAS.glob("*.html"))


def test_cada_pieza_esta_en_las_paginas_que_toca():
    for pieza, esperadas in (("partials/favicons.html", CON_FAVICONS), ("partials/gtm_head.html", CON_GTM),
                             ("partials/gtm_body.html", CON_GTM)):
        tienen = {p.name for p in _paginas() if _include(pieza).search(p.read_text(encoding="utf-8"))}
        assert tienen == esperadas, (pieza, "faltan", esperadas - tienen, "sobran", tienen - esperadas)


def test_gtm_body_justo_tras_abrir_body():
    for nombre in CON_GTM:
        texto = (PLANTILLAS / nombre).read_text(encoding="utf-8")
        tras_body = texto.index(">", texto.index("<body")) + 1
        resto = texto[tras_body:]
        assert _include("partials/gtm_body.html").match(texto, tras_body + len(resto) - len(resto.lstrip())), nombre
        assert _include("partials/gtm_head.html").search(texto[:texto.index("</head>")]), nombre


def test_nadie_vuelve_a_copiar_gtm_ni_favicons():
    copias = []
    for p in _paginas():
        texto = p.read_text(encoding="utf-8")
        for marca in ("googletagmanager.com", GTM_ID, "images/favicons/", "manifest.json"):
            if marca in texto and (p.name, marca) not in COPIAS_PERMITIDAS:
                copias.append(f"{p.name}: {marca}")
    assert not copias, f"Usa {{% include 'partials/...' %}} en vez de copiar el bloque: {copias}"


def test_las_piezas_existen_y_llevan_lo_suyo():
    favicons = (PLANTILLAS / "partials/favicons.html").read_text(encoding="utf-8")
    assert favicons.count("<link ") == 5 and "manifest.json" in favicons
    for pieza in ("partials/gtm_head.html", "partials/gtm_body.html"):
        assert GTM_ID in (PLANTILLAS / pieza).read_text(encoding="utf-8")


def _render_pieza(pieza):
    # App mínima con la carpeta de plantillas real: no necesita base de datos.
    from flask import Flask, render_template_string
    app = Flask("piezas", template_folder=str(PLANTILLAS), static_folder=str(PLANTILLAS.parent / "static"))
    with app.test_request_context("/"):
        return render_template_string("{% include '" + pieza + "' %}")


@pytest.mark.parametrize("pieza", PIEZAS)
def test_las_piezas_se_renderizan(pieza):
    html = _render_pieza(pieza)
    assert "{{" not in html and "{%" not in html and "{#" not in html
    assert not html.startswith("\n")  # el comentario no deja una línea en blanco
    if pieza.endswith("favicons.html"):
        assert '/static/images/favicons/favicon.svg"' in html
    else:
        assert GTM_ID in html


@pytest.mark.parametrize("ruta", ["/login", "/signup", "/forgot-password"])
def test_paginas_publicas_con_gtm_y_favicons(flask_app, ruta):
    r = flask_app.app.test_client().get(ruta)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count(GTM_ID) == 2  # <head> y <noscript>
    assert html.index(GTM_ID) < html.index("</head>") < html.index("ns.html?id=" + GTM_ID)
    assert 'rel="apple-touch-icon"' in html and "<!-- End Google Tag Manager (noscript) -->" in html


def test_la_pagina_de_movil_sigue_sin_gtm(flask_app):
    r = flask_app.app.test_client().get("/mobile-not-supported")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert GTM_ID not in html and 'rel="apple-touch-icon"' in html
