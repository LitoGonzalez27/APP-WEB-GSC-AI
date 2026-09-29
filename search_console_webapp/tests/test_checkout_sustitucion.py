"""
Checkout de Stripe: la suscripción nueva queda marcada con la que sustituye.

Si el usuario ya tiene una suscripción (p. ej. en past_due), el checkout añade
`subscription_data.metadata.replaces_subscription`; el webhook la usa para
cancelar la antigua cuando la nueva queda activa (orden de Carlos, 29-sep-2026).
La API de Stripe se sustituye por mocks. Corre contra la base desechable de
Docker (scripts/run_tests_docker.sh).
"""

from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import psycopg2
import pytest

from tests.conftest import seed_users

SUB_PAGO = "sub_test_seed"


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


@pytest.fixture
def stripe_simulado():
    import stripe
    sesion = SimpleNamespace(id="cs_test_char", url="https://checkout.stripe.test/cs_test_char")
    with mock.patch.object(stripe.Price, "retrieve", return_value={"id": "price_x"}), \
            mock.patch.object(stripe.Customer, "retrieve", return_value={"id": "cus_test_seed"}), \
            mock.patch.object(stripe.Customer, "create", return_value=SimpleNamespace(id="cus_char_nuevo")), \
            mock.patch.object(stripe.Subscription, "list", return_value=SimpleNamespace(data=[{"id": "sub_x"}])), \
            mock.patch.object(stripe.checkout.Session, "create", return_value=sesion) as crear:
        yield crear


def _checkout(flask_app, user, plan="premium"):
    client = flask_app.app.test_client()
    _login(client, user)
    return client.get(f"/billing/checkout/{plan}")


def test_usuario_con_suscripcion_en_past_due_marca_la_nueva_como_sustituta(flask_app, clean_db, stripe_simulado):
    _user, _admin, paid = seed_users()
    _sql(clean_db, "UPDATE users SET billing_status = 'past_due' WHERE id = %s", (paid["id"],))

    resp = _checkout(flask_app, paid)

    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://checkout.stripe.test/cs_test_char"
    params = stripe_simulado.call_args.kwargs
    assert params["subscription_data"]["metadata"] == {"replaces_subscription": SUB_PAGO}
    assert params["client_reference_id"] == str(paid["id"])


def test_usuario_sin_suscripcion_no_lleva_marca(flask_app, clean_db, stripe_simulado):
    user, _admin, _paid = seed_users()

    resp = _checkout(flask_app, user)

    assert resp.status_code == 302
    params = stripe_simulado.call_args.kwargs
    assert "metadata" not in (params.get("subscription_data") or {})


def test_la_marca_convive_con_la_prueba_gratuita(flask_app, clean_db, stripe_simulado):
    import stripe
    _user, _admin, paid = seed_users()
    _sql(clean_db, "UPDATE users SET billing_status = 'past_due', trial_used = false WHERE id = %s", (paid["id"],))

    with mock.patch.object(stripe.Subscription, "list", return_value=SimpleNamespace(data=[])):
        resp = _checkout(flask_app, paid)

    assert resp.status_code == 302
    datos = stripe_simulado.call_args.kwargs["subscription_data"]
    assert datos["metadata"] == {"replaces_subscription": SUB_PAGO}
    assert datos["trial_period_days"] > 0


def test_el_ultimo_reintento_sin_prueba_conserva_la_marca(flask_app, clean_db, stripe_simulado):
    _user, _admin, paid = seed_users()
    _sql(clean_db, "UPDATE users SET billing_status = 'past_due' WHERE id = %s", (paid["id"],))
    sesion = SimpleNamespace(id="cs_test_char", url="https://checkout.stripe.test/cs_test_char")
    # Fallan el intento normal y el que va sin códigos promocionales; el tercero
    # quita subscription_data (la prueba gratuita) y debe volver a poner la marca.
    stripe_simulado.side_effect = [RuntimeError("uno"), RuntimeError("dos"), sesion]

    resp = _checkout(flask_app, paid)

    assert resp.status_code == 302
    assert stripe_simulado.call_count == 3
    assert stripe_simulado.call_args.kwargs["subscription_data"] == {
        "metadata": {"replaces_subscription": SUB_PAGO}}
