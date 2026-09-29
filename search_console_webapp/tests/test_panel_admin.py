"""
Panel de admin (/admin/users): ficha "Ver" de un usuario y tarjeta "De pago".

Corre contra la base desechable de Docker (scripts/run_tests_docker.sh).
"""

import re
from datetime import datetime
from pathlib import Path

import psycopg2
import pytest

from tests.conftest import seed_users

PLANTILLA = Path(__file__).resolve().parent.parent / "templates" / "admin_simple.html"


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["user_email"] = user["email"]
        sess["user_name"] = user["name"]
        sess["last_activity"] = datetime.now().isoformat()


def _sql(url, sql, params=()):
    conn = psycopg2.connect(url, connect_timeout=5)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, params)
    finally:
        conn.close()


@pytest.mark.parametrize("quota_used", [1350, None])
def test_ficha_de_usuario_con_quota_limit_nulo(flask_app, clean_db, quota_used):
    # Enterprise con cuota a medida y sin quota_limit de plan (así lo deja el
    # webhook de Stripe con el producto enterprise).
    _user, admin, paid = seed_users()
    _sql(clean_db, "UPDATE users SET plan = 'enterprise', current_plan = 'enterprise', quota_limit = NULL,"
                   " custom_quota_limit = 3500, quota_used = %s WHERE id = %s", (quota_used, paid["id"]))
    client = flask_app.app.test_client()
    _login(client, admin)

    resp = client.get(f"/admin/users/{paid['id']}/billing-details")

    # ARREGLADO (2026-09-29): `quota_limit > 0` con NULL lanzaba TypeError y el
    # modal "Ver" respondía 404 "Usuario no encontrado".
    assert resp.status_code == 200
    u = resp.get_json()["user"]
    assert (u["id"], u["quota_limit"], u["custom_quota_limit"], u["quota_used"], u["quota_percentage"]) == (
        paid["id"], None, 3500, quota_used, 0)


@pytest.mark.parametrize("quota_used,porcentaje", [(495, 40.4), (None, 0)])
def test_ficha_de_usuario_con_quota_limit_calcula_el_porcentaje(flask_app, clean_db, quota_used, porcentaje):
    _user, admin, paid = seed_users()
    _sql(clean_db, "UPDATE users SET quota_limit = 1225, quota_used = %s WHERE id = %s", (quota_used, paid["id"]))
    client = flask_app.app.test_client()
    _login(client, admin)

    resp = client.get(f"/admin/users/{paid['id']}/billing-details")

    # Con quota_used NULL también saltaba TypeError (None / 1225).
    assert resp.status_code == 200
    assert resp.get_json()["user"]["quota_percentage"] == porcentaje


def test_tarjetas_del_resumen_con_los_valores_del_servidor(flask_app, clean_db):
    _user, admin, _paid = seed_users()  # 3 usuarios activos, uno de pago (business)
    client = flask_app.app.test_client()
    _login(client, admin)

    html = client.get("/admin/users").get_data(as_text=True)

    tarjetas = dict((etiqueta, int(numero)) for numero, etiqueta in re.findall(
        r'<div class="stat-number">\s*(\d+)\s*</div>\s*<div class="stat-label">([^<]+)</div>', html))
    assert tarjetas == {"Total usuarios": 3, "Activos": 3, "Inactivos": 0, "De pago": 1}


def test_ningun_script_reescribe_las_tarjetas_del_resumen():
    # ARREGLADO (2026-09-29): al cargar la página un script recontaba las filas
    # de la página visible (la tabla está paginada) y reescribía las tarjetas;
    # en la cuarta, "De pago", ponía los registros de hoy (antes era "Hoy"), así
    # que mostraba 0. Las tarjetas son las del servidor y ningún script las toca.
    src = PLANTILLA.read_text(encoding="utf-8")
    scripts = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", src, flags=re.S))
    assert "stat-number" not in scripts
    assert "stat-number" in src  # las tarjetas siguen en la plantilla
