"""
Tests de CARACTERIZACIÓN de los webhooks de Stripe (stripe_webhooks.py).

Fijan el comportamiento ACTUAL de POST /webhooks/stripe, incluidos sus defectos,
para que una refactorización no lo cambie sin que nadie se entere. No arreglan
nada: donde el comportamiento parece un fallo, el test lo fija igualmente y lo
marca con un comentario "COMPORTAMIENTO ACTUAL (posible defecto)".

Cada caso comprueba lo observable:
  - código HTTP y cuerpo JSON de la respuesta,
  - estado final de las filas de `users` implicadas (y de las que no deben cambiar),
  - filas de `stripe_webhook_events` (tabla de idempotencia).

Cómo se construye:
  - La petición pasa por la app Flask real (test client) y por la verificación
    de firma real de la librería stripe: la cabecera Stripe-Signature se calcula
    con el secreto FICTICIO de tests/docker/test.env.
  - Las llamadas a la API de Stripe (Customer.retrieve, Subscription.retrieve) y
    los envíos de email se sustituyen por mocks. Por defecto la API de Stripe
    "falla" (como fallaría sin red); cada test que la necesita fija su respuesta.
  - Base desechable de Docker vaciada antes de cada test, con los usuarios
    semilla: 1 gratuito, 2 admin, 3 de pago (business, cus_test_seed, sub_test_seed).
  - Fechas: los eventos usan timestamps fijos. El código convierte con
    datetime.fromtimestamp() sin zona, así que las comparaciones asumen que el
    contenedor y Postgres corren en UTC (lo hacen en scripts/run_tests_docker.sh).
    Donde el código usa NOW() se compara solo presencia o que no cambia.

Ejecutar:
    TEST_RUN_ID=stripe scripts/run_tests_docker.sh -q tests/test_char_stripe_webhooks.py
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

import psycopg2
import psycopg2.errors
import pytest
from psycopg2.extras import RealDictCursor

from tests.conftest import SEED_PAID_EMAIL, SEED_USER_EMAIL, seed_users

URL = "/webhooks/stripe"

ID_GRATUITO, ID_ADMIN, ID_PAGO = 1, 2, 3
CUSTOMER_PAGO = "cus_test_seed"
SUB_PAGO = "sub_test_seed"

COLUMNAS_USUARIO = (
    "id", "email", "plan", "current_plan", "billing_status", "quota_limit", "quota_used",
    "quota_reset_date", "stripe_customer_id", "subscription_id", "current_period_start",
    "current_period_end", "trial_used", "custom_quota_limit", "ai_overview_paused_until",
)

TABLAS_PROYECTOS = ("manual_ai_projects", "ai_mode_projects", "llm_monitoring_projects")


def ts(anio, mes, dia):
    """Timestamp Unix (UTC) de una fecha fija."""
    return int(datetime(anio, mes, dia, tzinfo=timezone.utc).timestamp())


def utc(marca):
    return datetime.fromtimestamp(marca, tz=timezone.utc)


# Periodos fijos de los eventos.
# Renovación de octubre de 2026: 31 días, para distinguir "inicio + 30 días" de "fin del periodo".
OCT_INICIO, OCT_FIN = ts(2026, 10, 1), ts(2026, 11, 1)
# Ciclo anterior (el que factura una renovación; Stripe lo pone en la raíz del invoice).
SEP_INICIO, SEP_FIN = ts(2026, 9, 1), ts(2026, 10, 1)
# Periodo lejano en el futuro: _update_subscription calcula quota_reset_date con la
# hora real (utcnow); con un periodo futuro el resultado no depende del día en que corra.
FUTURO_INICIO, FUTURO_FIN = ts(2098, 3, 1), ts(2098, 4, 1)


# ---------------------------------------------------------------------------
# Base de datos (conexiones propias, autocommit, siempre cerradas)
# ---------------------------------------------------------------------------

def consultar(url, sql, params=None):
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=5)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(fila) for fila in cur.fetchall()] if cur.description else []
    finally:
        conn.close()


def usuario(url, user_id):
    filas = consultar(url, f"SELECT {', '.join(COLUMNAS_USUARIO)} FROM users WHERE id = %s", (user_id,))
    return filas[0]


def todos_los_usuarios(url):
    return {
        fila["id"]: fila
        for fila in consultar(url, f"SELECT {', '.join(COLUMNAS_USUARIO)} FROM users ORDER BY id")
    }


def eventos(url):
    return consultar(
        url,
        """
        SELECT event_id, event_type, status, error_message,
               received_at IS NOT NULL AS recibido, processed_at
          FROM stripe_webhook_events
         ORDER BY received_at, event_id
        """,
    )


def resumen_eventos(url):
    """Lo estable de cada fila de idempotencia (sin fechas)."""
    return [
        (e["event_id"], e["event_type"], e["status"], e["error_message"], e["processed_at"] is not None)
        for e in eventos(url)
    ]


def crear_proyectos(url, user_id, pausados=False, tablas=TABLAS_PROYECTOS):
    """Un proyecto por tabla para el usuario. Devuelve {tabla: id}."""
    if pausados:
        pausa = (True, datetime(2026, 12, 1, tzinfo=timezone.utc),
                 datetime(2026, 9, 20, tzinfo=timezone.utc), "quota_exceeded")
    else:
        pausa = (False, None, None, None)
    sentencias = {
        "manual_ai_projects": (
            "INSERT INTO manual_ai_projects (user_id, name, domain, is_active, is_paused_by_quota,"
            " paused_until, paused_at, paused_reason) VALUES (%s, %s, 'ejemplo.invalid', true, %s, %s, %s, %s)"
            " RETURNING id"
        ),
        "ai_mode_projects": (
            "INSERT INTO ai_mode_projects (user_id, name, brand_name, is_active, is_paused_by_quota,"
            " paused_until, paused_at, paused_reason) VALUES (%s, %s, 'Marca', true, %s, %s, %s, %s)"
            " RETURNING id"
        ),
        "llm_monitoring_projects": (
            "INSERT INTO llm_monitoring_projects (user_id, name, brand_name, industry, is_active,"
            " is_paused_by_quota, paused_until, paused_at, paused_reason)"
            " VALUES (%s, %s, 'Marca', 'SEO', true, %s, %s, %s, %s) RETURNING id"
        ),
    }
    ids = {}
    for tabla in tablas:
        fila = consultar(url, sentencias[tabla], (user_id, f"proyecto-{user_id}-{tabla}") + pausa)
        ids[tabla] = fila[0]["id"]
    return ids


def estado_proyectos(url, user_id):
    estado = {}
    for tabla in TABLAS_PROYECTOS:
        estado[tabla] = consultar(
            url,
            f"SELECT is_active, is_paused_by_quota, paused_until, paused_at, paused_reason"
            f" FROM {tabla} WHERE user_id = %s ORDER BY id",
            (user_id,),
        )
    return estado


def _sesiones_en_transaccion(url):
    return consultar(
        url,
        """
        SELECT DISTINCT a.pid
          FROM pg_stat_activity a
         WHERE a.datname = current_database()
           AND a.pid <> pg_backend_pid()
           AND a.state IN ('idle in transaction', 'idle in transaction (aborted)')
        """,
    )


# ---------------------------------------------------------------------------
# Eventos de Stripe (estructura de la API 2025-06-30.basil)
# ---------------------------------------------------------------------------

def evento(tipo, objeto, event_id="evt_char_0001"):
    datos = {
        "object": "event",
        "api_version": "2025-06-30.basil",
        "created": ts(2026, 9, 27),
        "livemode": False,
        "pending_webhooks": 1,
        "request": {"id": None, "idempotency_key": None},
        "type": tipo,
        "data": {"object": objeto},
    }
    if event_id is not None:
        datos["id"] = event_id
    return datos


def suscripcion(customer=CUSTOMER_PAGO, sub_id=SUB_PAGO, price="price_test_premium_monthly",
                product="prod_test_premium", status="active", inicio=OCT_INICIO, fin=OCT_FIN,
                periodo_en="items", cancel_at_period_end=False, trial_end=None, con_items=True):
    """Objeto subscription. periodo_en: 'items' (API basil), 'raiz' (API antigua) o None."""
    item = {
        "id": "si_char_1",
        "object": "subscription_item",
        "price": {"id": price, "object": "price", "product": product},
        "quantity": 1,
    }
    datos = {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "cancel_at": FUTURO_FIN if cancel_at_period_end else None,
        "trial_end": trial_end,
        "items": {"object": "list", "data": [item] if con_items else []},
    }
    if periodo_en == "items":
        item["current_period_start"], item["current_period_end"] = inicio, fin
    elif periodo_en == "raiz":
        datos["current_period_start"], datos["current_period_end"] = inicio, fin
    return datos


def factura(customer=CUSTOMER_PAGO, sub_id=SUB_PAGO, periodo_lines=(OCT_INICIO, OCT_FIN),
            periodo_raiz=(SEP_INICIO, SEP_FIN), billing_reason="subscription_cycle"):
    """Objeto invoice, por defecto de renovación (billing_reason=subscription_cycle),
    API basil: la suscripción va en parent.subscription_details."""
    datos = {
        "id": "in_char_1",
        "object": "invoice",
        "customer": customer,
        "billing_reason": billing_reason,
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": sub_id},
        },
        "lines": {"object": "list", "data": []},
    }
    if periodo_lines:
        datos["lines"]["data"].append({
            "id": "il_char_1",
            "object": "line_item",
            "period": {"start": periodo_lines[0], "end": periodo_lines[1]},
        })
    if periodo_raiz:
        datos["period_start"], datos["period_end"] = periodo_raiz
    return datos


def sesion_checkout(client_reference_id="1", customer="cus_char_nuevo", subscription="sub_char_nueva",
                    email=SEED_USER_EMAIL):
    datos = {
        "id": "cs_test_char_1",
        "object": "checkout.session",
        "mode": "subscription",
        "status": "complete",
        "payment_status": "paid",
        "customer": customer,
        "subscription": subscription,
        "customer_email": email,
        "customer_details": {"email": email},
        "metadata": {"user_email": email},
    }
    if client_reference_id is not None:
        datos["client_reference_id"] = client_reference_id
    return datos


# ---------------------------------------------------------------------------
# Firma y envío
# ---------------------------------------------------------------------------

def secreto_test():
    return os.environ["STRIPE_WEBHOOK_SECRET"]


def cabecera_firma(payload: bytes, secreto=None, marca=None):
    """Stripe-Signature: t=<ts>,v1=<hex hmac_sha256(secreto, f'{ts}.{payload}')>."""
    marca = int(time.time()) if marca is None else marca
    firmado = f"{marca}.{payload.decode('utf-8')}".encode("utf-8")
    firma = hmac.new((secreto or secreto_test()).encode("utf-8"), firmado, hashlib.sha256).hexdigest()
    return f"t={marca},v1={firma}"


def enviar(ctx, datos_evento, firma=None):
    payload = json.dumps(datos_evento).encode("utf-8")
    headers = {"Stripe-Signature": firma if firma is not None else cabecera_firma(payload)}
    return ctx.client.post(URL, data=payload, headers=headers, content_type="application/json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def esquema_original(test_db_url):
    """El código crea en caliente una columna y una tabla que no están en el
    esquema de staging (comportamiento actual, no se evita). Al terminar el
    módulo se quitan solo si las creó este módulo, para no alterar a los demás tests."""
    habia_columna = bool(consultar(
        test_db_url,
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_name = 'users' AND column_name = 'trial_started_email_sent_at'",
    ))
    habia_tabla = consultar(
        test_db_url, "SELECT to_regclass('public.stripe_webhook_alerts_sent') IS NOT NULL AS hay"
    )[0]["hay"]
    yield
    sentencias = ["SET lock_timeout = '10s'"]
    if not habia_columna:
        sentencias.append("ALTER TABLE users DROP COLUMN IF EXISTS trial_started_email_sent_at")
    if not habia_tabla:
        sentencias.append("DROP TABLE IF EXISTS stripe_webhook_alerts_sent")
    consultar(test_db_url, "; ".join(sentencias))


@pytest.fixture(autouse=True)
def ctx(flask_app, clean_db, monkeypatch):
    import stripe
    import email_service
    import stripe_webhooks

    seed_users()
    # Alertas activas y destinatario por defecto, sin depender de la shell.
    monkeypatch.setenv("CRON_ALERTS_ENABLED", "true")
    monkeypatch.delenv("CRON_ALERTS_EMAIL", raising=False)

    sin_red = stripe.error.APIConnectionError("API de Stripe no disponible en tests")
    with mock.patch.object(stripe.Customer, "retrieve", side_effect=sin_red) as customer_retrieve, \
            mock.patch.object(stripe.Subscription, "retrieve", side_effect=sin_red) as subscription_retrieve, \
            mock.patch.object(stripe_webhooks, "send_trial_started_email", return_value=True) as email_trial, \
            mock.patch.object(stripe_webhooks, "send_email", return_value=True) as email_modulo, \
            mock.patch.object(email_service, "send_email", return_value=True) as email_alerta:
        yield SimpleNamespace(
            client=flask_app.app.test_client(),
            db=clean_db,
            modulo=stripe_webhooks,
            customer_retrieve=customer_retrieve,
            subscription_retrieve=subscription_retrieve,
            email_trial=email_trial,
            email_modulo=email_modulo,
            email_alerta=email_alerta,
        )

    # Red de seguridad: ninguna conexión debe quedar con una transacción abierta
    # (bloquearía el TRUNCATE del test siguiente). Si queda alguna, se corta, se
    # rehace el pool y el test falla para que se vea.
    huerfanas = _sesiones_en_transaccion(clean_db)
    if huerfanas:
        import database
        for fila in huerfanas:
            consultar(clean_db, "SELECT pg_terminate_backend(%s)", (fila["pid"],))
        database.close_db_pool()
        pytest.fail(f"Conexiones con transacción abierta tras el test: {len(huerfanas)}")


# ===========================================================================
# 1. Firma
# ===========================================================================

def test_get_de_salud_responde_200(ctx):
    resp = ctx.client.get(URL)
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "message": "Stripe webhook endpoint is up"}


def test_sin_cabecera_de_firma_responde_400_y_no_toca_nada(ctx):
    antes = todos_los_usuarios(ctx.db)
    payload = json.dumps(evento("invoice.payment_failed", factura())).encode()

    resp = ctx.client.post(URL, data=payload, content_type="application/json")

    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Missing signature"}
    assert todos_los_usuarios(ctx.db) == antes
    assert eventos(ctx.db) == []


@pytest.mark.parametrize("caso", ["otro_secreto", "cabecera_malformada", "sin_v1", "caducada", "payload_alterado"])
def test_firma_invalida_responde_400_y_no_toca_nada(ctx, caso):
    antes = todos_los_usuarios(ctx.db)
    datos = evento("invoice.payment_failed", factura())
    payload = json.dumps(datos).encode()
    if caso == "otro_secreto":
        firma = cabecera_firma(payload, secreto="whsec_otro_secreto_que_no_es_el_de_test")
    elif caso == "cabecera_malformada":
        firma = "esto-no-es-una-firma"
    elif caso == "sin_v1":
        firma = f"t={int(time.time())}"
    elif caso == "caducada":
        # HMAC correcto pero con más de 300 s de antigüedad (tolerancia por defecto de stripe).
        firma = cabecera_firma(payload, marca=int(time.time()) - 600)
    else:
        firma = cabecera_firma(payload)
        datos["data"]["object"]["customer"] = "cus_manipulado"
        payload = json.dumps(datos).encode()

    resp = ctx.client.post(URL, data=payload, headers={"Stripe-Signature": firma}, content_type="application/json")

    # La firma inválida no se distingue en la respuesta: la excepción de
    # verificación cae en el except general de handle_webhook.
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "internal_error"}
    assert todos_los_usuarios(ctx.db) == antes
    assert eventos(ctx.db) == []


def test_payload_firmado_que_no_es_json_responde_400(ctx):
    payload = b"esto no es json"
    resp = ctx.client.post(URL, data=payload, headers={"Stripe-Signature": cabecera_firma(payload)},
                           content_type="application/json")
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "internal_error"}
    assert eventos(ctx.db) == []


def test_firma_valida_con_el_secreto_de_test_responde_200(ctx):
    resp = enviar(ctx, evento("customer.created", {"id": "cus_char_x", "object": "customer"}))
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "customer.created", "processed", "", True)]


def test_firma_con_secreto_alternativo_se_acepta(ctx):
    # STRIPE_WEBHOOK_SECRET_ALT (rotación de secretos) se lee al arrancar; aquí se
    # simula que está configurado.
    secreto_alt = "whsec_test_alternativo_notreal000"
    datos = evento("customer.created", {"id": "cus_char_x", "object": "customer"})
    payload = json.dumps(datos).encode()
    with mock.patch.object(ctx.modulo.webhook_handler.config, "webhook_secret_alt", secreto_alt):
        resp = ctx.client.post(URL, data=payload,
                               headers={"Stripe-Signature": cabecera_firma(payload, secreto=secreto_alt)},
                               content_type="application/json")
    assert resp.status_code == 200
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "customer.created", "processed", "", True)]


# ===========================================================================
# 2. checkout.session.completed
# ===========================================================================

def test_checkout_usuario_gratuito_solo_graba_customer_y_suscripcion(ctx):
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento("checkout.session.completed", sesion_checkout(client_reference_id=str(ID_GRATUITO))))

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Checkout completed successfully"}
    despues = usuario(ctx.db, ID_GRATUITO)
    # El usuario se resuelve SOLO por client_reference_id (= users.id). Se graban
    # customer y suscripción; plan, cuota y periodo NO cambian (los fija
    # customer.subscription.created/updated).
    esperado = dict(antes[ID_GRATUITO], stripe_customer_id="cus_char_nuevo", subscription_id="sub_char_nueva")
    assert despues == esperado
    assert despues["plan"] == "free" and despues["quota_limit"] == 0
    assert despues["current_period_start"] is None and despues["current_period_end"] is None
    assert todos_los_usuarios(ctx.db)[ID_ADMIN] == antes[ID_ADMIN]
    assert todos_los_usuarios(ctx.db)[ID_PAGO] == antes[ID_PAGO]
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "checkout.session.completed", "processed", "", True)]


def test_checkout_sin_client_reference_id_no_asocia_por_email(ctx):
    antes = todos_los_usuarios(ctx.db)
    # El email y la metadata coinciden con el usuario gratuito, pero el código no los usa.
    resp = enviar(ctx, evento("checkout.session.completed", sesion_checkout(client_reference_id=None)))

    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "No user reference found"}
    assert todos_los_usuarios(ctx.db) == antes
    assert resumen_eventos(ctx.db) == [
        ("evt_char_0001", "checkout.session.completed", "failed", "No user reference found", True)
    ]


@pytest.mark.parametrize("referencia, error", [
    # id numérico que no existe: el UPDATE no toca filas.
    ("999", "User not found"),
    # id no numérico: el UPDATE lanza excepción. El error interno sale como 400.
    ("abc", "internal_error"),
])
def test_checkout_de_usuario_inexistente_devuelve_la_conexion_al_pool(ctx, referencia, error):
    # ARREGLADO (2026-09-28): antes la conexión se quedaba fuera del pool con la
    # transacción abierta y, con "999", con un AccessExclusiveLock sobre users
    # (el ALTER TABLE ... IF NOT EXISTS de cada checkout) hasta 15 minutos.
    resp = enviar(ctx, evento("checkout.session.completed", sesion_checkout(client_reference_id=referencia)))

    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": error}
    # Ninguna sesión queda en transacción y nadie retiene bloqueos sobre users
    assert _sesiones_en_transaccion(ctx.db) == []
    assert consultar(
        ctx.db,
        """
        SELECT l.mode FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid
         WHERE l.relation = 'public.users'::regclass AND l.granted AND a.pid <> pg_backend_pid()
        """,
    ) == []
    consultar(ctx.db, "SET lock_timeout = '300ms'; SELECT count(*) FROM users")
    assert resumen_eventos(ctx.db) == [
        ("evt_char_0001", "checkout.session.completed", "failed", error, True)
    ]


def test_alta_completa_de_usuario_gratuito_checkout_y_suscripcion_creada(ctx):
    enviar(ctx, evento("checkout.session.completed", sesion_checkout(client_reference_id=str(ID_GRATUITO)),
                       event_id="evt_char_checkout"))

    resp = enviar(ctx, evento(
        "customer.subscription.created",
        suscripcion(customer="cus_char_nuevo", sub_id="sub_char_nueva", price="price_test_basic_annual",
                    product="prod_test_basic", inicio=FUTURO_INICIO, fin=FUTURO_FIN),
        event_id="evt_char_created",
    ))

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Subscription created processed"}
    u = usuario(ctx.db, ID_GRATUITO)
    assert u["plan"] == "basic" and u["current_plan"] == "basic"
    assert u["quota_limit"] == 1225
    assert u["billing_status"] == "active"
    assert u["subscription_id"] == "sub_char_nueva"
    assert u["stripe_customer_id"] == "cus_char_nuevo"
    assert u["current_period_start"] == utc(FUTURO_INICIO)
    assert u["current_period_end"] == utc(FUTURO_FIN)
    # quota_reset_date estaba vacío: se rellena con inicio + 30 días (periodo de 31 días,
    # así que no coincide con el fin del periodo).
    assert u["quota_reset_date"] == utc(FUTURO_INICIO) + timedelta(days=30)
    assert u["trial_used"] is False
    assert u["quota_used"] == 0
    ctx.email_trial.assert_not_called()
    assert resumen_eventos(ctx.db) == [
        ("evt_char_checkout", "checkout.session.completed", "processed", "", True),
        ("evt_char_created", "customer.subscription.created", "processed", "", True),
    ]


def test_alta_con_prueba_gratuita_envia_un_solo_email_de_trial(ctx):
    trial_end = ts(2098, 3, 15)
    enviar(ctx, evento("checkout.session.completed", sesion_checkout(client_reference_id=str(ID_GRATUITO)),
                       event_id="evt_char_checkout"))
    datos_sub = suscripcion(customer="cus_char_nuevo", sub_id="sub_char_nueva", price="price_test_basic_monthly",
                            product="prod_test_basic", status="trialing", inicio=FUTURO_INICIO, fin=FUTURO_FIN,
                            trial_end=trial_end)

    resp1 = enviar(ctx, evento("customer.subscription.created", datos_sub, event_id="evt_char_trial_1"))
    resp2 = enviar(ctx, evento("customer.subscription.updated", datos_sub, event_id="evt_char_trial_2"))

    assert resp1.status_code == 200 and resp2.status_code == 200
    u = usuario(ctx.db, ID_GRATUITO)
    assert u["plan"] == "basic" and u["quota_limit"] == 1225
    assert u["billing_status"] == "trialing"
    assert u["trial_used"] is True
    # Email de inicio de trial: una sola vez aunque lleguen dos eventos trialing.
    # Recibe el fin del trial como datetime sin zona (fromtimestamp local = UTC aquí).
    ctx.email_trial.assert_called_once_with(SEED_USER_EMAIL, "basic", utc(trial_end).replace(tzinfo=None))
    marca = consultar(ctx.db, "SELECT trial_started_email_sent_at FROM users WHERE id = %s", (ID_GRATUITO,))
    assert marca[0]["trial_started_email_sent_at"] is not None


# ===========================================================================
# 3. customer.subscription.updated / deleted (usuario de pago)
# ===========================================================================

def _poner_plan_basic(ctx):
    consultar(ctx.db, "UPDATE users SET plan = 'basic', current_plan = 'basic', quota_limit = 1225, quota_used = 300"
                      " WHERE id = %s", (ID_PAGO,))


@pytest.mark.parametrize("periodo_en", ["items", "raiz", "api"])
def test_updated_cambio_de_basic_a_premium(ctx, periodo_en):
    _poner_plan_basic(ctx)
    antes = todos_los_usuarios(ctx.db)
    if periodo_en == "api":
        # Evento sin periodo en ningún nivel: se pide la suscripción a la API de Stripe.
        ctx.subscription_retrieve.side_effect = None
        ctx.subscription_retrieve.return_value = {
            "id": SUB_PAGO, "object": "subscription",
            "items": {"data": [{"current_period_start": OCT_INICIO, "current_period_end": OCT_FIN}]},
        }
    datos = suscripcion(periodo_en=None if periodo_en == "api" else periodo_en)

    resp = enviar(ctx, evento("customer.subscription.updated", datos))

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Subscription updated processed"}
    esperado = dict(
        antes[ID_PAGO],
        plan="premium", current_plan="premium", quota_limit=2950, billing_status="active",
        current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN),
    )
    # quota_used no se toca y quota_reset_date se conserva (COALESCE con el valor previo).
    assert usuario(ctx.db, ID_PAGO) == esperado
    assert todos_los_usuarios(ctx.db)[ID_GRATUITO] == antes[ID_GRATUITO]
    if periodo_en == "api":
        ctx.subscription_retrieve.assert_called_once_with(SUB_PAGO)
    else:
        ctx.subscription_retrieve.assert_not_called()
    ctx.customer_retrieve.assert_not_called()
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "customer.subscription.updated", "processed", "", True)]


def test_updated_sin_periodo_y_sin_api_conserva_el_periodo_guardado(ctx):
    antes = usuario(ctx.db, ID_PAGO)
    assert antes["current_period_end"] is not None

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(price="price_test_business_monthly", periodo_en=None)))

    assert resp.status_code == 200
    despues = usuario(ctx.db, ID_PAGO)
    # ARREGLADO (2026-09-28): antes se escribía NULL encima del periodo bueno.
    assert despues["current_period_start"] == antes["current_period_start"]
    assert despues["current_period_end"] == antes["current_period_end"]
    assert despues["quota_reset_date"] == antes["quota_reset_date"]
    ctx.subscription_retrieve.assert_called_once_with(SUB_PAGO)


def test_updated_cancel_at_period_end_no_deja_rastro(ctx):
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(price="price_test_business_monthly", cancel_at_period_end=True)))

    assert resp.status_code == 200
    # COMPORTAMIENTO ACTUAL (posible defecto): la cancelación programada se ignora.
    # users no tiene columna cancel_at_period_end (el manual la menciona) y el
    # usuario queda igual que con una actualización normal: activo y con su plan.
    esperado = dict(antes, plan="business", current_plan="business", billing_status="active",
                    # El webhook reescribe quota_limit con la tabla de planes (8000),
                    # aunque la semilla tenía 15000.
                    quota_limit=8000,
                    current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN))
    assert usuario(ctx.db, ID_PAGO) == esperado


def test_updated_past_due(ctx):
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(price="price_test_business_monthly", status="past_due")))

    assert resp.status_code == 200
    esperado = dict(antes, billing_status="past_due", quota_limit=8000,
                    current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN))
    assert usuario(ctx.db, ID_PAGO) == esperado


def test_updated_con_precio_desconocido_degrada_a_free(ctx):
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(price="price_char_desconocido", product="prod_char_desconocido")))

    assert resp.status_code == 200
    # COMPORTAMIENTO ACTUAL (posible defecto): un price_id que no está en la
    # configuración (p. ej. precio rotado sin PRICE_ID_LEGACY_MAP) deja al cliente
    # que paga en plan free con cuota 0 pero billing_status 'active'
    # (stripe_webhooks.py:634 devuelve 'free').
    esperado = dict(antes, plan="free", current_plan="free", quota_limit=0, billing_status="active",
                    current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN))
    assert usuario(ctx.db, ID_PAGO) == esperado


def test_updated_producto_enterprise_deja_quota_limit_nulo(ctx):
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(price="price_char_enterprise_a_medida", product="prod_test_enterprise")))

    assert resp.status_code == 200
    # Enterprise se reconoce por product_id; su límite en la tabla de planes es None,
    # así que quota_limit queda NULL (la cuota real va en custom_quota_limit).
    esperado = dict(antes, plan="enterprise", current_plan="enterprise", quota_limit=None,
                    billing_status="active",
                    current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN))
    assert usuario(ctx.db, ID_PAGO) == esperado


def test_updated_sin_items_responde_400(ctx):
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento("customer.subscription.updated", suscripcion(con_items=False)))

    # Error "permanente" para la ruta: 400, Stripe no reintenta.
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "No subscription items found"}
    assert todos_los_usuarios(ctx.db) == antes
    assert resumen_eventos(ctx.db) == [
        ("evt_char_0001", "customer.subscription.updated", "failed", "No subscription items found", True)
    ]


def test_deleted_vuelve_a_free_y_desactiva_proyectos(ctx):
    crear_proyectos(ctx.db, ID_PAGO)
    crear_proyectos(ctx.db, ID_GRATUITO)
    consultar(ctx.db, "UPDATE users SET quota_used = 700 WHERE id = %s", (ID_PAGO,))
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(price="price_test_business_monthly", status="canceled")))

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Subscription deleted processed"}
    esperado = dict(
        antes[ID_PAGO],
        plan="free", current_plan="free", billing_status="canceled", quota_limit=0,
        subscription_id=None, current_period_start=None, current_period_end=None,
    )
    # stripe_customer_id, quota_used y quota_reset_date se conservan.
    assert usuario(ctx.db, ID_PAGO) == esperado
    for tabla, filas in estado_proyectos(ctx.db, ID_PAGO).items():
        assert [f["is_active"] for f in filas] == [False], tabla
    for tabla, filas in estado_proyectos(ctx.db, ID_GRATUITO).items():
        assert [f["is_active"] for f in filas] == [True], tabla
    assert todos_los_usuarios(ctx.db)[ID_GRATUITO] == antes[ID_GRATUITO]
    ctx.customer_retrieve.assert_not_called()
    ctx.email_alerta.assert_not_called()
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "customer.subscription.deleted", "processed", "", True)]


@pytest.mark.parametrize("stripe_responde", ["api_caida", "email_de_otro", "email_coincide"])
def test_deleted_de_usuario_sin_proyectos_llm(ctx, stripe_responde):
    # Solo proyectos de Manual AI y AI Mode; ninguno de LLM Monitoring.
    crear_proyectos(ctx.db, ID_PAGO, tablas=("manual_ai_projects", "ai_mode_projects"))
    antes = usuario(ctx.db, ID_PAGO)
    if stripe_responde != "api_caida":
        ctx.customer_retrieve.side_effect = None
        email = SEED_PAID_EMAIL.upper() if stripe_responde == "email_coincide" else "otra.persona@example.invalid"
        ctx.customer_retrieve.return_value = {"id": CUSTOMER_PAGO, "object": "customer", "email": email}

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(price="price_test_business_monthly", status="canceled")))

    # ARREGLADO (2026-09-28): la comprobación usa las filas de USERS actualizadas,
    # no el rowcount del último UPDATE de proyectos. Antes, sin proyectos LLM se
    # respondía 503 + alerta de customer_not_found aunque la cancelación se guardaba.
    ctx.customer_retrieve.assert_not_called()
    esperado = dict(antes, plan="free", current_plan="free", billing_status="canceled", quota_limit=0,
                    subscription_id=None, current_period_start=None, current_period_end=None)
    assert usuario(ctx.db, ID_PAGO) == esperado
    for tabla, filas in estado_proyectos(ctx.db, ID_PAGO).items():
        assert [f["is_active"] for f in filas] == ([] if tabla == "llm_monitoring_projects" else [False]), tabla
    assert resp.status_code == 200
    ctx.email_alerta.assert_not_called()
    assert resumen_eventos(ctx.db) == [
        ("evt_char_0001", "customer.subscription.deleted", "processed", "", True)
    ]


def test_deleted_de_una_suscripcion_antigua_no_toca_la_vigente(ctx):
    crear_proyectos(ctx.db, ID_PAGO)
    antes = usuario(ctx.db, ID_PAGO)
    proyectos_antes = estado_proyectos(ctx.db, ID_PAGO)
    assert antes["subscription_id"] == SUB_PAGO

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(sub_id="sub_char_antigua", price="price_test_basic_monthly",
                                          status="canceled")))

    # ARREGLADO (2026-09-28): antes la cancelación filtraba solo por cliente y
    # dejaba sin plan al usuario que paga la suscripción vigente.
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Deleted subscription is not the current one; ignored"}
    assert usuario(ctx.db, ID_PAGO) == antes
    assert estado_proyectos(ctx.db, ID_PAGO) == proyectos_antes
    ctx.email_alerta.assert_not_called()


def test_deleted_no_cancela_a_un_usuario_beta_sin_suscripcion(ctx):
    consultar(ctx.db, "UPDATE users SET billing_status = 'beta', subscription_id = NULL WHERE id = %s",
              (ID_PAGO,))
    crear_proyectos(ctx.db, ID_PAGO)
    antes = todos_los_usuarios(ctx.db)
    proyectos_antes = estado_proyectos(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(price="price_test_business_monthly", status="canceled")))

    # ARREGLADO (2026-09-28): la cancelación alcanzaba a cualquier usuario del
    # cliente sin suscripción, también a los beta, cuyo acceso no viene de Stripe.
    # El cliente es conocido: 200 sin alerta, no "customer no encontrado".
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Deleted subscription is not the current one; ignored"}
    assert todos_los_usuarios(ctx.db) == antes
    assert estado_proyectos(ctx.db, ID_PAGO) == proyectos_antes
    ctx.email_alerta.assert_not_called()


def test_deleted_encontrado_por_subscription_id_desactiva_proyectos(ctx):
    crear_proyectos(ctx.db, ID_PAGO)
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(customer="cus_char_otro", status="canceled")))

    # ARREGLADO (2026-09-28): los fallbacks cancelaban al usuario pero dejaban
    # sus proyectos activos.
    assert resp.status_code == 200
    assert usuario(ctx.db, ID_PAGO) == dict(
        antes, plan="free", current_plan="free", billing_status="canceled", quota_limit=0,
        subscription_id=None, current_period_start=None, current_period_end=None)
    for tabla, filas in estado_proyectos(ctx.db, ID_PAGO).items():
        assert [f["is_active"] for f in filas] == [False], tabla
    ctx.customer_retrieve.assert_not_called()
    ctx.email_alerta.assert_not_called()


def test_deleted_encontrado_por_email_desactiva_proyectos(ctx):
    crear_proyectos(ctx.db, ID_GRATUITO)
    antes = usuario(ctx.db, ID_GRATUITO)
    ctx.customer_retrieve.side_effect = None
    ctx.customer_retrieve.return_value = {"id": "cus_char_desconocido", "object": "customer",
                                          "email": SEED_USER_EMAIL}

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(customer="cus_char_desconocido", sub_id="sub_char_x",
                                          status="canceled")))

    assert resp.status_code == 200
    assert usuario(ctx.db, ID_GRATUITO) == dict(
        antes, plan="free", current_plan="free", billing_status="canceled", quota_limit=0,
        subscription_id=None, current_period_start=None, current_period_end=None,
        stripe_customer_id="cus_char_desconocido")
    for tabla, filas in estado_proyectos(ctx.db, ID_GRATUITO).items():
        assert [f["is_active"] for f in filas] == [False], tabla


def test_deleted_por_email_no_pisa_el_customer_de_otro_usuario(ctx):
    consultar(ctx.db, "UPDATE users SET stripe_customer_id = 'cus_char_suyo' WHERE id = %s", (ID_GRATUITO,))
    crear_proyectos(ctx.db, ID_GRATUITO)
    antes = todos_los_usuarios(ctx.db)
    ctx.customer_retrieve.side_effect = None
    ctx.customer_retrieve.return_value = {"id": "cus_char_desconocido", "object": "customer",
                                          "email": SEED_USER_EMAIL}

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(customer="cus_char_desconocido", sub_id="sub_char_x",
                                          status="canceled")))

    # ARREGLADO (2026-09-28): el fallback por email reescribía el
    # stripe_customer_id de un usuario que ya tenía otro cliente de Stripe.
    assert resp.status_code == 503
    assert resp.get_json()["error"] == "customer_not_found"
    assert todos_los_usuarios(ctx.db) == antes
    for tabla, filas in estado_proyectos(ctx.db, ID_GRATUITO).items():
        assert [f["is_active"] for f in filas] == [True], tabla


def test_fallback_por_email_de_una_suscripcion_no_vigente_se_ignora_sin_alerta(ctx):
    consultar(ctx.db, "UPDATE users SET subscription_id = 'sub_char_suya' WHERE id = %s", (ID_GRATUITO,))
    antes = todos_los_usuarios(ctx.db)
    ctx.customer_retrieve.side_effect = None
    ctx.customer_retrieve.return_value = {"id": "cus_char_desconocido", "object": "customer",
                                          "email": SEED_USER_EMAIL}

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(customer="cus_char_desconocido", sub_id="sub_char_x",
                                          status="past_due")))

    # Mismo trato que el camino principal: 200 sin tocar al usuario ni alertar.
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Subscription is not the current one; ignored"}
    assert todos_los_usuarios(ctx.db) == antes
    ctx.email_alerta.assert_not_called()


def test_fallo_al_desactivar_una_tabla_no_deshace_la_cancelacion(ctx):
    crear_proyectos(ctx.db, ID_PAGO)
    antes = usuario(ctx.db, ID_PAGO)
    consultar(ctx.db, """
        CREATE FUNCTION test_char_fallo_simulado() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'fallo simulado'; END $$ LANGUAGE plpgsql;
        CREATE TRIGGER test_char_fallo_simulado BEFORE UPDATE ON ai_mode_projects
            FOR EACH ROW EXECUTE FUNCTION test_char_fallo_simulado();
    """)
    try:
        resp = enviar(ctx, evento("customer.subscription.deleted",
                                  suscripcion(price="price_test_business_monthly", status="canceled")))
    finally:
        consultar(ctx.db, "DROP TRIGGER IF EXISTS test_char_fallo_simulado ON ai_mode_projects;"
                          " DROP FUNCTION IF EXISTS test_char_fallo_simulado()")

    # ARREGLADO (2026-09-28): el error abortaba la transacción y el commit
    # deshacía en silencio también la cancelación (el usuario seguía de pago).
    # Con un SAVEPOINT por tabla solo se pierde la tabla que falla.
    assert resp.status_code == 200
    assert usuario(ctx.db, ID_PAGO) == dict(
        antes, plan="free", current_plan="free", billing_status="canceled", quota_limit=0,
        subscription_id=None, current_period_start=None, current_period_end=None)
    activos = {tabla: [f["is_active"] for f in filas] for tabla, filas in estado_proyectos(ctx.db, ID_PAGO).items()}
    assert activos == {"manual_ai_projects": [False], "ai_mode_projects": [True],
                       "llm_monitoring_projects": [False]}


@pytest.mark.parametrize("tipo,status", [
    ("customer.subscription.updated", "past_due"),
    ("customer.subscription.updated", "unpaid"),
    ("customer.subscription.created", "incomplete"),
])
def test_evento_no_activo_de_una_suscripcion_antigua_no_pisa_la_vigente(ctx, tipo, status):
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento(tipo, suscripcion(sub_id="sub_char_antigua", price="price_test_basic_monthly",
                                                product="prod_test_basic", status=status)))

    # ARREGLADO (2026-09-28): el UPDATE filtraba solo por cliente y el estado de
    # la suscripción antigua (o de un checkout a medias) pisaba el de la vigente.
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Subscription is not the current one; ignored"}
    assert todos_los_usuarios(ctx.db) == antes


def test_suscripcion_nueva_activa_sustituye_a_la_guardada(ctx):
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.updated", suscripcion(sub_id="sub_char_nueva")))

    # Un estado activo de otra suscripción sí se aplica: así se cambia de plan
    # (p. ej. contratar otro tras quedar en past_due).
    assert resp.status_code == 200
    assert usuario(ctx.db, ID_PAGO) == dict(
        antes, plan="premium", current_plan="premium", quota_limit=2950, billing_status="active",
        subscription_id="sub_char_nueva",
        current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN))


# ===========================================================================
# 4. invoice.payment_succeeded / invoice.payment_failed
# ===========================================================================

@pytest.mark.parametrize("origen_periodo", ["lines", "raiz", "api"])
def test_payment_succeeded_resetea_cuota_y_despausa(ctx, origen_periodo):
    consultar(ctx.db, "UPDATE users SET quota_used = 900, billing_status = 'past_due',"
                      " ai_overview_paused_until = '2026-12-01T00:00:00Z' WHERE id = %s", (ID_PAGO,))
    crear_proyectos(ctx.db, ID_PAGO, pausados=True)
    crear_proyectos(ctx.db, ID_GRATUITO, pausados=True)
    antes = todos_los_usuarios(ctx.db)
    pausa_otro_usuario = estado_proyectos(ctx.db, ID_GRATUITO)

    if origen_periodo == "lines":
        # Renovación: en la raíz viene el ciclo ANTERIOR (septiembre) y en
        # lines.data[0].period el nuevo (octubre). Manda lines.
        datos = factura()
    elif origen_periodo == "raiz":
        datos = factura(periodo_lines=None, periodo_raiz=(OCT_INICIO, OCT_FIN))
    else:
        datos = factura(periodo_lines=None, periodo_raiz=None)
        ctx.subscription_retrieve.side_effect = None
        ctx.subscription_retrieve.return_value = {
            "id": SUB_PAGO, "object": "subscription",
            "items": {"data": [{"current_period_start": OCT_INICIO, "current_period_end": OCT_FIN}]},
        }

    resp = enviar(ctx, evento("invoice.payment_succeeded", datos))

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Payment succeeded processed"}
    esperado = dict(
        antes[ID_PAGO],
        quota_used=0, billing_status="active",
        current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN),
        # Reset = inicio + 30 días (calculado con now = inicio del periodo), no el
        # fin del periodo: con un periodo de 31 días queda un día antes.
        quota_reset_date=utc(OCT_INICIO) + timedelta(days=30),
        # resume_quota_pauses_for_user limpia también la pausa de AI Overview.
        ai_overview_paused_until=None,
    )
    # plan, quota_limit, subscription_id y stripe_customer_id no se tocan.
    assert usuario(ctx.db, ID_PAGO) == esperado
    for tabla, filas in estado_proyectos(ctx.db, ID_PAGO).items():
        assert filas == [{"is_active": True, "is_paused_by_quota": False, "paused_until": None,
                          "paused_at": None, "paused_reason": None}], tabla
    assert estado_proyectos(ctx.db, ID_GRATUITO) == pausa_otro_usuario
    assert todos_los_usuarios(ctx.db)[ID_GRATUITO] == antes[ID_GRATUITO]
    if origen_periodo == "api":
        # La suscripción se saca de parent.subscription_details (API basil).
        ctx.subscription_retrieve.assert_called_once_with(SUB_PAGO)
    else:
        ctx.subscription_retrieve.assert_not_called()
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "invoice.payment_succeeded", "processed", "", True)]


def test_payment_succeeded_sin_periodo_resoluble_responde_200_sin_resetear(ctx):
    consultar(ctx.db, "UPDATE users SET quota_used = 900 WHERE id = %s", (ID_PAGO,))
    crear_proyectos(ctx.db, ID_PAGO, pausados=True)
    antes = todos_los_usuarios(ctx.db)
    pausa = estado_proyectos(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("invoice.payment_succeeded", factura(periodo_lines=None, periodo_raiz=None)))

    # Se responde 200 para que Stripe no reintente, pero la cuota NO se resetea
    # ni se despausa nada (solo queda un log de error).
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Payment succeeded processed"}
    assert todos_los_usuarios(ctx.db) == antes
    assert estado_proyectos(ctx.db, ID_PAGO) == pausa
    ctx.subscription_retrieve.assert_called_once_with(SUB_PAGO)
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "invoice.payment_succeeded", "processed", "", True)]


def test_payment_failed_marca_past_due(ctx):
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento("invoice.payment_failed", factura()))

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Payment failed processed"}
    # Solo cambia billing_status; plan, cuota y periodo se quedan como estaban.
    assert usuario(ctx.db, ID_PAGO) == dict(antes[ID_PAGO], billing_status="past_due")
    assert todos_los_usuarios(ctx.db)[ID_GRATUITO] == antes[ID_GRATUITO]
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "invoice.payment_failed", "processed", "", True)]


@pytest.mark.parametrize("tipo", ["invoice.payment_succeeded", "invoice.payment_failed"])
def test_factura_de_una_suscripcion_antigua_no_toca_la_vigente(ctx, tipo):
    consultar(ctx.db, "UPDATE users SET quota_used = 900 WHERE id = %s", (ID_PAGO,))
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento(tipo, factura(sub_id="sub_char_antigua")))

    # ARREGLADO (2026-09-28): la factura de otra suscripción del cliente (p. ej.
    # un reintento de cobro de la antigua) reseteaba la cuota o marcaba past_due
    # al usuario que paga la vigente.
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Invoice is not for the current subscription; ignored"}
    assert todos_los_usuarios(ctx.db) == antes


def test_primer_cobro_de_una_suscripcion_nueva_con_la_antigua_en_past_due(ctx):
    consultar(ctx.db, "UPDATE users SET quota_used = 900, billing_status = 'past_due' WHERE id = %s", (ID_PAGO,))
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("invoice.payment_succeeded", factura(sub_id="sub_char_nueva")))

    # Con la antigua en past_due el checkout deja contratar otra y su primer
    # cobro suele llegar antes que el checkout: no se ignora.
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Payment succeeded processed"}
    assert usuario(ctx.db, ID_PAGO) == dict(
        antes, quota_used=0, billing_status="active",
        current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN),
        quota_reset_date=utc(OCT_INICIO) + timedelta(days=30))


def test_primera_factura_de_suscripcion_nueva_se_aplica_aunque_la_guardada_figure_activa(ctx):
    # Usuario bajado a free desde el admin: conserva billing_status 'active' y
    # el subscription_id antiguo, y el checkout le deja contratar de nuevo.
    consultar(ctx.db, "UPDATE users SET plan = 'free', current_plan = 'free', quota_used = 900"
                      " WHERE id = %s", (ID_PAGO,))
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("invoice.payment_succeeded",
                              factura(sub_id="sub_char_nueva", billing_reason="subscription_create")))

    # La primera factura de una suscripción nueva nunca es un reintento de la
    # antigua: se aplica aunque llegue antes que el checkout.
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Payment succeeded processed"}
    assert usuario(ctx.db, ID_PAGO) == dict(
        antes, quota_used=0, billing_status="active",
        current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN),
        quota_reset_date=utc(OCT_INICIO) + timedelta(days=30))


# ===========================================================================
# 5. Cliente desconocido
# ===========================================================================

def test_subscription_updated_de_cliente_desconocido_503_y_una_alerta_por_hora(ctx):
    antes = todos_los_usuarios(ctx.db)
    ctx.customer_retrieve.side_effect = None
    ctx.customer_retrieve.return_value = {"id": "cus_char_fantasma", "object": "customer",
                                          "email": "nadie@example.invalid"}
    datos = suscripcion(customer="cus_char_fantasma", sub_id="sub_char_fantasma")

    resp1 = enviar(ctx, evento("customer.subscription.updated", datos, event_id="evt_char_fantasma_1"))
    resp2 = enviar(ctx, evento("customer.subscription.updated", datos, event_id="evt_char_fantasma_2"))

    for resp in (resp1, resp2):
        # 503 para que Stripe reintente (posible carrera en el registro).
        assert resp.status_code == 503
        cuerpo = resp.get_json()
        assert (cuerpo["success"], cuerpo["error"], cuerpo["customer_id"], cuerpo["subscription_id"]) == \
            (False, "customer_not_found", "cus_char_fantasma", "sub_char_fantasma")
    assert todos_los_usuarios(ctx.db) == antes
    assert ctx.customer_retrieve.call_args_list == [mock.call("cus_char_fantasma")] * 2
    # Alerta por email: una sola para el mismo customer en una hora.
    ctx.email_alerta.assert_called_once()
    destinatario, asunto, _html = ctx.email_alerta.call_args.args
    assert destinatario == "info@soycarlosgonzalez.com"
    assert asunto.endswith("Stripe webhook customer_not_found")
    alertas = consultar(ctx.db, "SELECT alert_key FROM stripe_webhook_alerts_sent")
    assert alertas == [{"alert_key": "unmatched_customer:cus_char_fantasma"}]
    assert resumen_eventos(ctx.db) == [
        ("evt_char_fantasma_1", "customer.subscription.updated", "failed", "customer_not_found", True),
        ("evt_char_fantasma_2", "customer.subscription.updated", "failed", "customer_not_found", True),
    ]


def test_subscription_deleted_de_cliente_desconocido_503(ctx):
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento("customer.subscription.deleted",
                              suscripcion(customer="cus_char_fantasma", sub_id="sub_char_fantasma",
                                          status="canceled")))

    assert resp.status_code == 503
    assert resp.get_json()["error"] == "customer_not_found"
    assert todos_los_usuarios(ctx.db) == antes
    ctx.email_alerta.assert_called_once()


def test_subscription_updated_fallback_por_subscription_id(ctx):
    antes = usuario(ctx.db, ID_PAGO)

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(customer="cus_char_otro", sub_id=SUB_PAGO)))

    assert resp.status_code == 200
    # Se encuentra al usuario por subscription_id; su stripe_customer_id no cambia.
    esperado = dict(antes, plan="premium", current_plan="premium", quota_limit=2950, billing_status="active",
                    current_period_start=utc(OCT_INICIO), current_period_end=utc(OCT_FIN))
    assert usuario(ctx.db, ID_PAGO) == esperado
    ctx.customer_retrieve.assert_not_called()


def test_subscription_updated_fallback_por_email_del_customer_en_stripe(ctx):
    antes = usuario(ctx.db, ID_GRATUITO)
    assert antes["quota_reset_date"] is None
    ctx.customer_retrieve.side_effect = None
    # El email se compara sin distinguir mayúsculas.
    ctx.customer_retrieve.return_value = {"id": "cus_char_desconocido", "object": "customer",
                                          "email": SEED_USER_EMAIL.upper()}

    resp = enviar(ctx, evento("customer.subscription.updated",
                              suscripcion(customer="cus_char_desconocido", sub_id="sub_char_nueva",
                                          price="price_test_basic_monthly", product="prod_test_basic",
                                          inicio=FUTURO_INICIO, fin=FUTURO_FIN)))

    assert resp.status_code == 200
    esperado = dict(antes, plan="basic", current_plan="basic", quota_limit=1225, billing_status="active",
                    subscription_id="sub_char_nueva", stripe_customer_id="cus_char_desconocido",
                    current_period_start=utc(FUTURO_INICIO), current_period_end=utc(FUTURO_FIN))
    # COMPORTAMIENTO ACTUAL (posible defecto): los UPDATE de los fallbacks
    # (stripe_webhooks.py:318-332 y 362-377) no rellenan quota_reset_date, a
    # diferencia del camino principal (línea 292). El usuario queda con plan de
    # pago y quota_reset_date NULL.
    assert usuario(ctx.db, ID_GRATUITO) == esperado
    assert usuario(ctx.db, ID_GRATUITO)["quota_reset_date"] is None
    ctx.customer_retrieve.assert_called_once_with("cus_char_desconocido")


@pytest.mark.parametrize("tipo", ["invoice.payment_succeeded", "invoice.payment_failed"])
def test_factura_de_cliente_desconocido_responde_200_sin_cambios(ctx, tipo):
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento(tipo, factura(customer="cus_char_fantasma", sub_id="sub_char_fantasma")))

    # A diferencia de los eventos de suscripción, no hay 503 ni alerta por email:
    # el pago de un cliente que no casa se da por procesado (solo log).
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert todos_los_usuarios(ctx.db) == antes
    ctx.email_alerta.assert_not_called()
    ctx.customer_retrieve.assert_not_called()
    assert resumen_eventos(ctx.db) == [("evt_char_0001", tipo, "processed", "", True)]


# ===========================================================================
# 6. Idempotencia
# ===========================================================================

def test_mismo_evento_dos_veces_no_reprocesa(ctx):
    consultar(ctx.db, "UPDATE users SET quota_used = 900 WHERE id = %s", (ID_PAGO,))
    datos = evento("invoice.payment_succeeded", factura())

    resp1 = enviar(ctx, datos)
    assert resp1.status_code == 200
    assert usuario(ctx.db, ID_PAGO)["quota_used"] == 0
    fila1 = eventos(ctx.db)
    # Consumo entre la primera entrega y el reenvío.
    consultar(ctx.db, "UPDATE users SET quota_used = 50 WHERE id = %s", (ID_PAGO,))
    antes = todos_los_usuarios(ctx.db)

    resp2 = enviar(ctx, datos)

    assert resp2.status_code == 200
    assert resp2.get_json() == {"success": True, "message": "Event already processed", "idempotent": True}
    assert todos_los_usuarios(ctx.db) == antes
    assert usuario(ctx.db, ID_PAGO)["quota_used"] == 50
    # Una sola fila, sin cambios (processed_at incluido).
    assert eventos(ctx.db) == fila1
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "invoice.payment_succeeded", "processed", "", True)]


def test_evento_que_respondio_503_se_reprocesa_cuando_stripe_reintenta(ctx):
    datos = evento("customer.subscription.updated",
                   suscripcion(customer="cus_char_carrera", sub_id="sub_char_carrera",
                               price="price_test_basic_monthly", product="prod_test_basic"))

    resp1 = enviar(ctx, datos)
    assert resp1.status_code == 503
    # Se resuelve la "carrera": el usuario ya tiene ese customer en la BD.
    consultar(ctx.db, "UPDATE users SET stripe_customer_id = 'cus_char_carrera' WHERE id = %s", (ID_GRATUITO,))

    resp2 = enviar(ctx, datos)

    # ARREGLADO (2026-09-28): antes el reintento recibía 200 "already processed"
    # y el usuario no recibía nunca su plan.
    assert resp2.status_code == 200
    assert resp2.get_json()["success"] is True
    u = usuario(ctx.db, ID_GRATUITO)
    assert (u["plan"], u["subscription_id"]) == ("basic", "sub_char_carrera")
    assert resumen_eventos(ctx.db) == [
        ("evt_char_0001", "customer.subscription.updated", "processed", "", True)
    ]


def test_evento_que_fallo_por_error_permanente_no_se_reprocesa(ctx):
    # Sin cambios con el arreglo: un fallo permanente (checkout sin usuario) se
    # sigue confirmando en el reintento sin volver a procesarse.
    datos = evento("checkout.session.completed", sesion_checkout(client_reference_id="999"))
    assert enviar(ctx, datos).status_code == 400
    antes = todos_los_usuarios(ctx.db)

    resp2 = enviar(ctx, datos)

    assert resp2.status_code == 200
    assert resp2.get_json() == {"success": True, "message": "Event already processed", "idempotent": True}
    assert todos_los_usuarios(ctx.db) == antes
    assert resumen_eventos(ctx.db) == [
        ("evt_char_0001", "checkout.session.completed", "failed", "User not found", True)
    ]


def test_evento_en_curso_reciente_pide_reintento(ctx):
    # Otro proceso lo está tratando ahora mismo (fila 'in_progress' reciente).
    consultar(ctx.db, "INSERT INTO stripe_webhook_events (event_id, event_type, status)"
                      " VALUES ('evt_char_0001', 'invoice.payment_failed', 'in_progress')")
    antes = todos_los_usuarios(ctx.db)

    resp = enviar(ctx, evento("invoice.payment_failed", factura()))

    # ARREGLADO (2026-09-28): antes se confirmaba como "ya procesado" y no se
    # procesaba nunca. Ahora se responde 503 para que Stripe reintente luego.
    assert resp.status_code == 503
    assert resp.get_json() == {"success": False, "error": "cannot_claim_event"}
    assert todos_los_usuarios(ctx.db) == antes


def test_evento_abandonado_en_curso_se_reprocesa(ctx):
    # Entrega anterior que murió a mitad hace más de 10 minutos.
    consultar(ctx.db, "INSERT INTO stripe_webhook_events (event_id, event_type, status, received_at)"
                      " VALUES ('evt_char_0001', 'invoice.payment_failed', 'in_progress',"
                      " NOW() - INTERVAL '11 minutes')")

    resp = enviar(ctx, evento("invoice.payment_failed", factura()))

    assert resp.status_code == 200
    assert usuario(ctx.db, ID_PAGO)["billing_status"] == "past_due"
    assert resumen_eventos(ctx.db) == [("evt_char_0001", "invoice.payment_failed", "processed", "", True)]


def test_reclamar_un_evento_no_espera_a_otra_transaccion_sobre_la_tabla(ctx):
    import threading

    # Otra transacción con un claim sin confirmar (ROW EXCLUSIVE sobre la tabla).
    bloqueo = psycopg2.connect(ctx.db, connect_timeout=5)
    resultado = {}
    hilo = threading.Thread(target=lambda: resultado.update(
        resp=enviar(ctx, evento("invoice.payment_failed", factura(), event_id="evt_char_concurrente"))))
    try:
        with bloqueo.cursor() as cur:
            cur.execute("INSERT INTO stripe_webhook_events (event_id, event_type)"
                        " VALUES ('evt_char_ajeno', 'invoice.payment_failed')")
        hilo.start()
        hilo.join(10)
        esperaba = hilo.is_alive()
    finally:
        bloqueo.rollback()
        bloqueo.close()
    hilo.join(30)

    # ARREGLADO (2026-09-28): cada claim lanzaba CREATE INDEX IF NOT EXISTS, que
    # pide un bloqueo SHARE aunque el índice exista; esperaba a cualquier claim
    # sin confirmar y dos webhooks simultáneos podían quedar en deadlock.
    assert not esperaba, "El claim esperó al bloqueo de otra transacción"
    assert resultado["resp"].status_code == 200


def test_bd_no_disponible_al_reclamar_el_evento_responde_503(ctx):
    antes = todos_los_usuarios(ctx.db)

    with mock.patch.object(ctx.modulo, "get_db_connection", return_value=None):
        resp = enviar(ctx, evento("invoice.payment_failed", factura()))

    assert resp.status_code == 503
    assert resp.get_json() == {"success": False, "error": "cannot_claim_event"}
    assert todos_los_usuarios(ctx.db) == antes
    assert eventos(ctx.db) == []


def test_evento_sin_id_se_procesa_siempre_y_no_se_registra(ctx):
    datos = evento("invoice.payment_failed", factura(), event_id=None)

    resp1 = enviar(ctx, datos)
    resp2 = enviar(ctx, datos)

    # Sin id no hay deduplicación: se procesa cada vez y no deja fila.
    assert resp1.status_code == 200 and resp2.status_code == 200
    assert resp2.get_json() == {"success": True, "message": "Payment failed processed"}
    assert usuario(ctx.db, ID_PAGO)["billing_status"] == "past_due"
    assert eventos(ctx.db) == []


# ===========================================================================
# 7. Tipos de evento no manejados
# ===========================================================================

@pytest.mark.parametrize("tipo", ["customer.created", "invoice.paid", "customer.subscription.trial_will_end",
                                  "charge.refunded"])
def test_tipo_no_manejado_responde_200_y_queda_registrado(ctx, tipo):
    antes = todos_los_usuarios(ctx.db)
    objeto = suscripcion() if tipo.startswith("customer.subscription") else factura()

    resp = enviar(ctx, evento(tipo, objeto))

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": f"Event {tipo} received but not processed"}
    assert todos_los_usuarios(ctx.db) == antes
    assert resumen_eventos(ctx.db) == [("evt_char_0001", tipo, "processed", "", True)]
    ctx.customer_retrieve.assert_not_called()
    ctx.subscription_retrieve.assert_not_called()
