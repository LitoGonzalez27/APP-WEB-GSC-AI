"""
Foto de cómo responde cada ruta según quién llama: visitante sin sesión,
usuario gratuito, usuario de pago (plan business) y admin. Caracteriza la autenticación y los permisos de la app
entera; cualquier cambio de código que abra o cierre una ruta sale aquí.

Cómo se construye:
  - Parámetros de ruta con valores que no existen (ids 999999, textos 'zz-test'),
    así que no se lee ni modifica nada de nadie.
  - Visitante, gratuito y de pago: todos los métodos. Admin: solo GET y nunca rutas /cron/
    (un admin puede lanzar análisis completos; no aporta a la foto de permisos).
  - Antes de CADA petición se vacía la base desechable y se vuelven a crear los
    usuarios semilla, para que una petición no condicione a la siguiente.
  - Se guarda el código HTTP y, en redirecciones, la ruta de destino.

Regenerar la foto (solo tras un cambio de permisos intencionado y revisado):
    UPDATE_SNAPSHOTS=1 scripts/run_tests_docker.sh tests/test_zz_route_auth_matrix.py
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest

from tests.conftest import seed_users, truncate_all_tables

SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "route_auth_matrix.json"
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

_CONVERTER_VALUES = {
    "int": "999999",
    "float": "1.5",
    "path": "zz/test",
    "uuid": "00000000-0000-0000-0000-000000000000",
}


def _concrete_url(rule_text):
    def repl(match):
        converter = (match.group(1) or "string").split("(")[0]
        return _CONVERTER_VALUES.get(converter, "zz-test")
    return re.sub(r"<(?:([^:<>]+):)?[^<>]+>", repl, rule_text)


def _describe(response):
    code = response.status_code
    if 300 <= code < 400:
        return f"{code} -> {urlparse(response.headers.get('Location', '')).path}"
    return str(code)


def _request(app, url, method, session_user):
    client = app.test_client()
    if session_user:
        with client.session_transaction() as sess:
            sess["user_id"] = session_user["id"]
            sess["user_email"] = session_user["email"]
            sess["user_name"] = session_user["name"]
            sess["last_activity"] = datetime.now().isoformat()
    kwargs = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
    return client.open(url, method=method, **kwargs)


def build_matrix(flask_app_module, db_url):
    app = flask_app_module.app
    matrix = {}
    rules = sorted(app.url_map.iter_rules(), key=lambda r: (r.rule, r.endpoint))
    for rule in rules:
        url = _concrete_url(rule.rule)
        for method in METHODS:
            if method not in rule.methods:
                continue
            entry = {}
            for role in ("anon", "user", "paid", "admin"):
                if role == "admin" and (method != "GET" or "/cron/" in rule.rule):
                    continue
                truncate_all_tables(db_url)
                user, admin, paid = seed_users()
                session_user = {"anon": None, "user": user, "paid": paid, "admin": admin}[role]
                entry[role] = _describe(_request(app, url, method, session_user))
            matrix[f"{method} {rule.rule} [{rule.endpoint}]"] = entry
    return matrix


def test_route_auth_matrix_matches_snapshot(flask_app, test_db_url):
    current = build_matrix(flask_app, test_db_url)

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip(f"Foto regenerada: {len(current)} combinaciones ruta/método")

    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    diffs = []
    for key in sorted(set(expected) | set(current)):
        if expected.get(key) != current.get(key):
            diffs.append(f"{key}\n    antes: {expected.get(key)}\n    ahora: {current.get(key)}")
    assert not diffs, "Cambian respuestas por rol:\n" + "\n".join(diffs)
