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


def _paginas():
    return sorted(p for p in PLANTILLAS.glob("*.html"))


def test_nadie_vuelve_a_copiar_gtm_ni_favicons():
    copias = []
    for p in _paginas():
        texto = p.read_text(encoding="utf-8")
        if GTM_ID in texto or 'rel="apple-touch-icon"' in texto or 'filename=\'manifest.json\'' in texto:
            copias.append(p.name)
    assert not copias, f"Usa {{% include 'partials/...' %}} en vez de copiar el bloque: {copias}"


def test_gtm_completo_donde_se_usa():
    # Si una página carga GTM en el <head>, también lleva la parte de <body>, justo tras abrirlo.
    for p in _paginas():
        texto = p.read_text(encoding="utf-8")
        cabeza = "{% include 'partials/gtm_head.html' %}" in texto
        cuerpo = re.search(r"<body[^>]*>\s*\{% include 'partials/gtm_body.html' %\}", texto)
        assert bool(cabeza) == bool(cuerpo), p.name


def test_las_piezas_existen_y_llevan_lo_suyo():
    favicons = (PLANTILLAS / "partials/favicons.html").read_text(encoding="utf-8")
    assert favicons.count("<link ") == 5 and "manifest.json" in favicons
    for pieza in ("partials/gtm_head.html", "partials/gtm_body.html"):
        assert GTM_ID in (PLANTILLAS / pieza).read_text(encoding="utf-8")


@pytest.mark.parametrize("pieza", PIEZAS)
def test_las_piezas_se_renderizan_con_la_app(flask_app, pieza):
    from flask import render_template_string

    with flask_app.app.test_request_context("/"):
        html = render_template_string("{% include '" + pieza + "' %}")
    assert "{{" not in html and "{%" not in html
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
    assert 'rel="apple-touch-icon"' in html and "<!-- End Google Tag Manager (noscript) -->" in html
