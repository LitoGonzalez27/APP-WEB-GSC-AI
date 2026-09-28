"""
Tests de CARACTERIZACIÓN del sistema de cuotas (fase 0-1 de la limpieza).

Fijan el comportamiento ACTUAL, defectos incluidos, para que una refactorización
posterior no lo cambie sin que nadie se entere. No arreglan nada: donde el
comportamiento parece un defecto, el test lo fija igualmente y lo señala con
"COMPORTAMIENTO ACTUAL (posible defecto)".

Cubre:
1. Estado de cuota por plan (quota_manager.get_user_quota_status y afines).
2. Decisión de consumo: can_user_consume_ru, validate_quota_access,
   quota_protected_serp_call (cuándo una llamada SERP gasta RU), fail-open.
3. Registro de consumo: database.track_quota_consumption,
   quota_manager.record_quota_usage / consume_user_quota, pausas y reanudación.
4. Fechas de reset y ventana de cuota (compute_next_quota_reset_date,
   project_quota.compute_quota_window) y los resets que las usan.
5. Unidades LLM por proveedor y search_mode, límites LLM por plan.
6. Límites por proyecto (project_quota) y topes Enterprise (enterprise_limits).

Los tests con base de datos usan el Postgres desechable de Docker
(scripts/run_tests_docker.sh) y se saltan sin él. Las fechas se fijan siempre
de forma explícita o se comparan en relativo; nada depende del día de ejecución.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import json  # noqa: E402
from datetime import date, datetime, timedelta, timezone  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
import pytest  # noqa: E402
from flask import Flask, g, session  # noqa: E402
from psycopg2 import errorcodes  # noqa: E402

import admin_billing_panel  # noqa: E402
import database  # noqa: E402
import enterprise_limits  # noqa: E402
import llm_monitoring_limits  # noqa: E402
import project_quota  # noqa: E402
import quota_manager  # noqa: E402
import quota_middleware  # noqa: E402
from tests.conftest import seed_users  # noqa: E402

UTC = timezone.utc

# Ventana de cuota fija para los tests con BD: reset el 1-oct-2026 -> ventana
# [2026-09-01, 2026-10-01) con el intervalo por defecto de 30 días.
RESET_FIJO = datetime(2026, 10, 1, tzinfo=UTC)


# ===========================================================================
# Infraestructura
# ===========================================================================

class _Db:
    """Acceso directo (autocommit) a la base desechable para preparar estados y
    leer resultados sin pasar por el código de la app."""

    def __init__(self, conn):
        self.conn = conn

    def exec(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def one(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def all(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def set_user(self, user_id, **fields):
        cols = ", ".join(f"{k} = %s" for k in fields)
        self.exec(f"UPDATE users SET {cols} WHERE id = %s", (*fields.values(), user_id))

    def user(self, user_id):
        return self.one("SELECT * FROM users WHERE id = %s", (user_id,))

    def events(self, user_id=None):
        where, params = ("WHERE user_id = %s", (user_id,)) if user_id is not None else ("", None)
        return self.all(
            f"""SELECT user_id, ru_consumed, source, keyword, country_code, metadata
                FROM quota_usage_events {where} ORDER BY id""",
            params,
        )

    def add_project(self, module, user_id, name="Proyecto", **extra):
        base = {
            "manual_ai": ("manual_ai_projects", {"domain": "example.com"}),
            "ai_mode": ("ai_mode_projects", {"brand_name": "Marca"}),
            "llm_monitoring": ("llm_monitoring_projects", {"brand_name": "Marca", "industry": "SEO"}),
        }
        table, required = base[module]
        fields = {"user_id": user_id, "name": name, **required, **extra}
        cols = ", ".join(fields)
        marks = ", ".join(["%s"] * len(fields))
        return self.one(
            f"INSERT INTO {table} ({cols}) VALUES ({marks}) RETURNING id", tuple(fields.values())
        )["id"]

    def project(self, module, project_id):
        table = project_quota.MODULES[module]["table"]
        return self.one(f"SELECT * FROM {table} WHERE id = %s", (project_id,))

    def add_event(self, user_id, ru, source, ts, metadata=None):
        self.exec(
            """INSERT INTO quota_usage_events (user_id, ru_consumed, source, timestamp, metadata)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, ru, source, ts, json.dumps(metadata) if metadata is not None else None),
        )

    def add_llm_result(self, project_id, analysis_date, provider, units):
        self.exec(
            """INSERT INTO llm_monitoring_results
                   (project_id, analysis_date, llm_provider, query_text, brand_name, units_consumed)
               VALUES (%s, %s, %s, 'consulta de prueba', 'Marca', %s)""",
            (project_id, analysis_date, provider, units),
        )


@pytest.fixture
def db(clean_db):
    """Base vacía + usuarios semilla: 1 gratuito, 2 admin (plan free),
    3 business activo con quota_limit 15000 y periodo Stripe vigente."""
    seed_users()
    conn = psycopg2.connect(clean_db, cursor_factory=psycopg2.extras.RealDictCursor, connect_timeout=5)
    conn.autocommit = True
    try:
        yield _Db(conn)
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _entorno_estable(monkeypatch):
    """Variables que alteran los cálculos: se fijan a sus valores por defecto."""
    for var in ("QUOTA_RESET_INTERVAL_DAYS", "LLM_SEARCH_UNIT_WEIGHTS",
                "DB_RETRY_ATTEMPTS", "DB_RETRY_BACKOFF_SECONDS"):
        monkeypatch.delenv(var, raising=False)
    llm_monitoring_limits.UNITS_SCHEMA.reset()
    yield
    llm_monitoring_limits.UNITS_SCHEMA.reset()


def _sin_conexion():
    return None


def _conexion_que_falla(exc):
    """Conexión falsa cuyo cursor lanza `exc` en el primer execute."""
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = exc
    return conn


# ===========================================================================
# 1. Estado de cuota por plan
# ===========================================================================

# (plan, quota_limit, custom_quota_limit, quota_used) ->
# (quota_limit, quota_used, remaining, percentage, can_consume, is_custom)
CASOS_ESTADO = [
    pytest.param("free", 0, None, 0, (0, 0, 0, 0, False, False), id="free-sin-consumo"),
    pytest.param("free", 0, None, 7, (0, 7, 0, 0, False, False), id="free-con-consumo"),
    # COMPORTAMIENTO ACTUAL (posible defecto): un usuario free con quota_limit
    # residual (> 0) puede consumir; el plan no se mira si quota_limit > 0.
    pytest.param("free", 500, None, 0, (500, 0, 500, 0.0, True, False), id="free-con-quota_limit-residual"),
    pytest.param("basic", 0, None, 0, (1225, 0, 1225, 0.0, True, False), id="basic-limit-0-usa-PLAN_LIMITS"),
    pytest.param("basic", None, None, 0, (1225, 0, 1225, 0.0, True, False), id="basic-limit-NULL-usa-PLAN_LIMITS"),
    pytest.param("basic", -5, None, 0, (1225, 0, 1225, 0.0, True, False), id="basic-limit-negativo-usa-PLAN_LIMITS"),
    pytest.param("basic", 1225, None, 600, (1225, 600, 625, 49.0, True, False), id="basic-parcial"),
    pytest.param("basic", 1225, None, 1224, (1225, 1224, 1, 99.9, True, False), id="basic-a-1-del-limite"),
    pytest.param("basic", 1225, None, 1225, (1225, 1225, 0, 100.0, False, False), id="basic-justo-en-limite"),
    pytest.param("basic", 1225, None, 1300, (1225, 1300, 0, 106.1, False, False), id="basic-por-encima"),
    pytest.param("basic", 1225, None, None, (1225, 0, 1225, 0.0, True, False), id="basic-used-NULL"),
    # COMPORTAMIENTO ACTUAL (posible defecto): quota_used negativo no se
    # corrige y da más remaining que el propio límite.
    pytest.param("basic", 1225, None, -10, (1225, -10, 1235, -0.8, True, False), id="basic-used-negativo"),
    # El porcentaje se redondea a 100.0 aunque aún quede 1 RU y can_consume sea True.
    pytest.param("premium", 2950, None, 2949, (2950, 2949, 1, 100.0, True, False), id="premium-redondeo-100"),
    pytest.param("premium", 0, None, 3000, (2950, 3000, 0, 101.7, False, False), id="premium-plan-default-excedido"),
    # quota_limit manda sobre PLAN_LIMITS (business = 8000 en la tabla).
    pytest.param("business", 15000, None, 7500, (15000, 7500, 7500, 50.0, True, False), id="business-quota_limit-gana"),
    pytest.param("business", 0, None, 8000, (8000, 8000, 0, 100.0, False, False), id="business-plan-default-en-limite"),
    pytest.param("enterprise", 0, None, 0, (0, 0, 0, 0, False, False), id="enterprise-sin-custom-limite-0"),
    pytest.param("enterprise", 0, 3500, 875, (3500, 875, 2625, 25.0, True, True), id="enterprise-custom-parcial"),
    pytest.param("enterprise", 0, 3500, 3500, (3500, 3500, 0, 100.0, False, True), id="enterprise-custom-en-limite"),
    pytest.param("enterprise", 0, 3500, 4000, (3500, 4000, 0, 114.3, False, True), id="enterprise-custom-excedido"),
    # custom_quota_limit = 0 gana a quota_limit (is not None).
    pytest.param("enterprise", 5000, 0, 0, (0, 0, 0, 0, False, True), id="enterprise-custom-0-gana"),
    # El override custom se aplica a cualquier plan, no solo a enterprise.
    pytest.param("basic", 1225, 50, 10, (50, 10, 40, 20.0, True, True), id="basic-con-custom"),
]


class TestEstadoDeCuota:
    @pytest.mark.parametrize("plan,quota_limit,custom,used,esperado", CASOS_ESTADO)
    def test_estado_por_plan(self, db, plan, quota_limit, custom, used, esperado):
        db.set_user(3, plan=plan, quota_limit=quota_limit, custom_quota_limit=custom, quota_used=used)
        status = quota_manager.get_user_quota_status(3)
        limit, used_e, remaining, percentage, can_consume, is_custom = esperado
        assert status == {
            "quota_limit": limit,
            "quota_used": used_e,
            "remaining": remaining,
            "percentage": percentage,
            "can_consume": can_consume,
            "plan": plan,
            "is_custom": is_custom,
            "reset_date": db.user(3)["quota_reset_date"],
        }
        assert isinstance(status["quota_limit"], int)

    @pytest.mark.parametrize("plan,quota_limit,custom,used,esperado", CASOS_ESTADO)
    def test_limite_efectivo_coincide_con_estado(self, db, plan, quota_limit, custom, used, esperado):
        db.set_user(3, plan=plan, quota_limit=quota_limit, custom_quota_limit=custom, quota_used=used)
        assert quota_manager.get_user_effective_quota_limit(3) == esperado[0]

    def test_usuario_inexistente_no_puede_consumir(self, db):
        # Sin fail-open: el usuario no existe de verdad.
        assert quota_manager.get_user_quota_status(999) == {
            "quota_limit": 0, "quota_used": 0, "remaining": 0,
            "percentage": 0, "can_consume": False,
            "plan": "unknown", "is_custom": False, "reset_date": None,
        }
        assert quota_manager.get_user_effective_quota_limit(999) == 0

    @pytest.mark.parametrize("billing_status", ["active", "trialing", "beta", "past_due", "canceled", "incomplete", None])
    def test_billing_status_no_afecta(self, db, billing_status):
        # COMPORTAMIENTO ACTUAL (posible defecto): ni el estado de cuota ni los
        # permisos miran billing_status; un usuario past_due o canceled con plan
        # de pago y RU restantes sigue pudiendo consumir.
        db.set_user(3, billing_status=billing_status, quota_used=100)
        status = quota_manager.get_user_quota_status(3)
        assert (status["quota_limit"], status["remaining"], status["can_consume"]) == (15000, 14900, True)
        perms = quota_manager.get_user_access_permissions(3)
        assert (perms["can_use_ai_overview"], perms["can_use_manual_ai"], perms["can_use_serp_api"]) == (True, True, True)
        assert quota_middleware.validate_quota_access(3, "serp_json")["allowed"] is True
        assert quota_middleware.validate_quota_access(3, "manual_ai")["allowed"] is True

    @pytest.mark.parametrize("pausa", ["futura", "vencida", "sin-pausa"])
    def test_pausas_no_afectan_al_estado(self, db, pausa):
        # La pausa de AI Overview (nivel usuario) y las de proyectos no entran en
        # el cálculo: el gate de pausa vive en cada módulo, no en quota_manager.
        ahora = datetime.now(UTC)
        paused_until = {"futura": ahora + timedelta(days=10), "vencida": ahora - timedelta(days=1), "sin-pausa": None}[pausa]
        db.set_user(3, quota_used=100, ai_overview_paused_until=paused_until,
                    ai_overview_paused_reason="quota_exceeded" if paused_until else None)
        db.add_project("manual_ai", 3, is_paused_by_quota=paused_until is not None, paused_until=paused_until)
        status = quota_manager.get_user_quota_status(3)
        assert (status["remaining"], status["can_consume"]) == (14900, True)
        # reset_date es quota_reset_date, nunca la fecha de la pausa.
        assert status["reset_date"] == db.user(3)["quota_reset_date"]

    def test_estadisticas_globales(self, db):
        db.set_user(1, plan="basic", quota_limit=None, quota_used=5)
        db.set_user(2, plan="enterprise", custom_quota_limit=3500, quota_used=100)
        stats = quota_manager.get_quota_statistics()
        # COMPORTAMIENTO ACTUAL (posible defecto): total_limit no usa PLAN_LIMITS;
        # un basic con quota_limit NULL suma 0 aunque su límite efectivo sea 1225.
        assert stats["plan_statistics"] == [
            {"plan": "basic", "users": 1, "total_used": 5, "total_limit": 0},
            {"plan": "business", "users": 1, "total_used": 0, "total_limit": 15000},
            {"plan": "enterprise", "users": 1, "total_used": 100, "total_limit": 3500},
        ]
        assert stats["custom_quota_users"] == 1


class TestPermisos:
    # (plan, quota_limit, custom, used) -> (can_use_ai_overview, can_use_manual_ai, can_use_serp_api)
    @pytest.mark.parametrize("plan,quota_limit,custom,used,esperado", [
        ("free", 0, None, 0, (False, False, False)),
        # Free con cuota residual: can_consume True pero sin permisos (el plan manda).
        ("free", 500, None, 0, (False, False, False)),
        ("basic", 1225, None, 0, (True, True, True)),
        ("basic", 1225, None, 1225, (False, False, False)),
        ("premium", 2950, None, 100, (True, True, True)),
        ("business", 15000, None, 15000, (False, False, False)),
        ("enterprise", 0, 3500, 10, (True, True, True)),
        ("enterprise", 0, None, 0, (False, False, False)),
    ])
    def test_permisos_por_plan_y_cuota(self, db, plan, quota_limit, custom, used, esperado):
        db.set_user(3, plan=plan, quota_limit=quota_limit, custom_quota_limit=custom, quota_used=used)
        perms = quota_manager.get_user_access_permissions(3)
        assert (perms["can_use_ai_overview"], perms["can_use_manual_ai"], perms["can_use_serp_api"]) == esperado
        assert perms["quota_status"]["plan"] == plan

    def test_rol_admin_no_da_permisos(self, db):
        # COMPORTAMIENTO ACTUAL: quota_manager ignora role; el admin semilla
        # (plan free) no tiene permisos de IA por cuota.
        perms = quota_manager.get_user_access_permissions(2)
        assert (perms["can_use_ai_overview"], perms["can_use_manual_ai"], perms["can_use_serp_api"]) == (False, False, False)


# ===========================================================================
# 2. Decisión de consumo y fail-open
# ===========================================================================

FAIL_OPEN = {
    "quota_limit": 0, "quota_used": 0, "remaining": 1,
    "percentage": 0, "can_consume": True,
    "plan": "unknown", "is_custom": False, "reset_date": None,
}


class TestFailOpen:
    def test_sin_conexion_devuelve_fail_open(self, monkeypatch):
        monkeypatch.setattr(quota_manager, "get_db_connection", _sin_conexion)
        assert quota_manager.get_user_quota_status(3) == {**FAIL_OPEN, "error": "no_db_connection"}

    def test_error_de_bd_devuelve_fail_open_con_el_mensaje(self, monkeypatch):
        conn = _conexion_que_falla(psycopg2.OperationalError("se cayó la conexión"))
        monkeypatch.setattr(quota_manager, "get_db_connection", lambda: conn)
        assert quota_manager.get_user_quota_status(3) == {**FAIL_OPEN, "error": "se cayó la conexión"}
        conn.close.assert_called_once()

    def test_get_db_connection_que_lanza_tambien_es_fail_open(self, monkeypatch):
        def boom():
            raise RuntimeError("pool roto")
        monkeypatch.setattr(quota_manager, "get_db_connection", boom)
        assert quota_manager.get_user_quota_status(3) == {**FAIL_OPEN, "error": "pool roto"}

    @pytest.mark.parametrize("ru,esperado", [
        (0, True),
        (1, True),
        # COMPORTAMIENTO ACTUAL (posible defecto): el fail-open solo cubre 1 RU
        # porque devuelve remaining=1; pedir 2 o más RU con la BD caída es False.
        (2, False),
        (100, False),
    ])
    def test_can_consume_con_bd_caida(self, monkeypatch, ru, esperado):
        monkeypatch.setattr(quota_manager, "get_db_connection", _sin_conexion)
        assert quota_manager.can_user_consume_ru(3, ru) is esperado

    def test_permisos_con_bd_caida_son_fail_closed(self, monkeypatch):
        # COMPORTAMIENTO ACTUAL (posible defecto): el plan 'unknown' del
        # fail-open no está en la lista de planes de pago, así que los permisos
        # de IA salen False aunque can_consume sea True.
        monkeypatch.setattr(quota_manager, "get_db_connection", _sin_conexion)
        perms = quota_manager.get_user_access_permissions(3)
        assert (perms["can_use_ai_overview"], perms["can_use_manual_ai"], perms["can_use_serp_api"]) == (False, False, False)
        assert perms["quota_status"]["can_consume"] is True

    def test_validate_con_bd_caida_serp_abierto_ia_cerrado(self, monkeypatch):
        monkeypatch.setattr(quota_manager, "get_db_connection", _sin_conexion)
        serp = quota_middleware.validate_quota_access(3, "serp_json")
        assert (serp["allowed"], serp["reason"], serp["action_required"]) == (True, "Quota disponible", None)
        ia = quota_middleware.validate_quota_access(3, "manual_ai")
        assert (ia["allowed"], ia["reason"], ia["action_required"]) == (
            False, "Plan actual no tiene acceso a módulos de IA", "upgrade")
        assert ia["quota_info"]["error"] == "no_db_connection"

    def test_aviso_con_bd_caida_es_none(self, monkeypatch):
        monkeypatch.setattr(quota_manager, "get_db_connection", _sin_conexion)
        assert quota_middleware.get_quota_warning_info(3) is None

    @pytest.mark.parametrize("llamada", [
        pytest.param(lambda: quota_manager.get_user_effective_quota_limit(3), id="get_user_effective_quota_limit"),
        pytest.param(lambda: quota_manager.record_quota_usage(3, 1), id="record_quota_usage"),
        pytest.param(lambda: quota_manager.reset_user_quota(3), id="reset_user_quota"),
        pytest.param(lambda: quota_manager.consume_user_quota(3, 1), id="consume_user_quota"),
    ])
    def test_get_db_connection_que_lanza_rompe_con_unboundlocalerror(self, monkeypatch, llamada):
        # COMPORTAMIENTO ACTUAL (posible defecto): estas funciones no inicializan
        # `conn` antes del try; si get_db_connection lanza, el finally
        # `if conn:` provoca UnboundLocalError en lugar del valor de error.
        def boom():
            raise RuntimeError("pool roto")
        monkeypatch.setattr(quota_manager, "get_db_connection", boom)
        with pytest.raises(UnboundLocalError):
            llamada()


class TestPuedeConsumir:
    # Usuario basic con quota_limit 1225: (quota_used, ru_amount) -> bool
    @pytest.mark.parametrize("used,ru,esperado", [
        (0, 1, True),
        (1224, 1, True),
        (1224, 2, False),
        (1225, 1, False),
        (0, 1225, True),
        (0, 1226, False),
        # COMPORTAMIENTO ACTUAL: ru_amount 0 o negativo siempre es True, incluso
        # con la cuota agotada o excedida (remaining 0 >= 0).
        (1225, 0, True),
        (1300, 0, True),
        (1300, -1, True),
    ])
    def test_basic(self, db, used, ru, esperado):
        db.set_user(3, plan="basic", quota_limit=1225, quota_used=used)
        assert quota_manager.can_user_consume_ru(3, ru) is esperado

    @pytest.mark.parametrize("ru,esperado", [(0, True), (1, False)])
    def test_free(self, db, ru, esperado):
        assert quota_manager.can_user_consume_ru(1, ru) is esperado

    def test_usuario_inexistente(self, db):
        assert quota_manager.can_user_consume_ru(999, 1) is False
        assert quota_manager.can_user_consume_ru(999, 0) is True


class TestValidateQuotaAccess:
    # (plan, quota_limit, custom, used, operation) -> (allowed, reason, action_required)
    @pytest.mark.parametrize("plan,quota_limit,custom,used,op,esperado", [
        ("free", 0, None, 0, "serp_json", (True, "Plan Free: SERP permitido (sin consumo de RU)", None)),
        ("free", 0, None, 50, "serp_html", (True, "Plan Free: SERP permitido (sin consumo de RU)", None)),
        ("free", 0, None, 0, "manual_ai", (False, "Plan actual no tiene acceso a módulos de IA", "upgrade")),
        ("free", 500, None, 0, "ai_overview", (False, "Plan actual no tiene acceso a módulos de IA", "upgrade")),
        ("basic", 1225, None, 0, "serp_json", (True, "Quota disponible", None)),
        ("basic", 1225, None, 0, "manual_ai", (True, "Quota disponible", None)),
        ("basic", 1225, None, 1225, "serp_json", (False, "Cuota agotada (1225/1225 RU)", "upgrade")),
        ("basic", 1225, None, 1300, "serp_json", (False, "Cuota agotada (1300/1225 RU)", "upgrade")),
        # COMPORTAMIENTO ACTUAL (posible defecto): en la rama de IA la rama
        # "Cuota agotada" es inalcanzable; un usuario de pago agotado recibe
        # "Plan actual no tiene acceso a módulos de IA" y 'upgrade'.
        ("basic", 1225, None, 1225, "manual_ai", (False, "Plan actual no tiene acceso a módulos de IA", "upgrade")),
        ("enterprise", 0, 3500, 3500, "serp_html", (False, "Cuota agotada (3500/3500 RU)", "contact_support")),
        # Incluso enterprise recibe 'upgrade' en la rama de IA.
        ("enterprise", 0, 3500, 3500, "ai_overview", (False, "Plan actual no tiene acceso a módulos de IA", "upgrade")),
        ("enterprise", 0, None, 0, "serp_json", (False, "Cuota agotada (0/0 RU)", "contact_support")),
        ("enterprise", 0, 3500, 10, "ai_mode", (True, "Quota disponible", None)),
        # Solo el prefijo 'serp_' entra en la rama SERP; 'serp' a secas es IA.
        ("basic", 1225, None, 1225, "serp", (False, "Plan actual no tiene acceso a módulos de IA", "upgrade")),
    ])
    def test_tabla(self, db, plan, quota_limit, custom, used, op, esperado):
        db.set_user(3, plan=plan, quota_limit=quota_limit, custom_quota_limit=custom, quota_used=used)
        res = quota_middleware.validate_quota_access(3, op)
        assert (res["allowed"], res["reason"], res["action_required"]) == esperado
        assert res["quota_info"]["plan"] == plan

    def test_excepcion_es_fail_closed(self, monkeypatch):
        def boom(_user_id):
            raise RuntimeError("boom")
        monkeypatch.setattr(quota_middleware, "get_user_access_permissions", boom)
        assert quota_middleware.validate_quota_access(3, "serp_json") == {
            "allowed": False,
            "reason": "Error de sistema: boom",
            "quota_info": {},
            "action_required": "contact_support",
        }


class TestAvisoDeCuota:
    # Usuario basic con quota_limit 1225
    @pytest.mark.parametrize("used,esperado", [
        (0, None),
        (979, None),  # 79.9 %
        (980, {"type": "warning", "percentage": 80.0, "remaining_ru": 245,
               "message": "Has usado 80% de tu cuota mensual (245 RU restantes)"}),
        # 99.9 % se muestra como "100%" en el mensaje pero sigue siendo 'warning'.
        (1224, {"type": "warning", "percentage": 99.9, "remaining_ru": 1,
                "message": "Has usado 100% de tu cuota mensual (1 RU restantes)"}),
        (1225, {"type": "danger", "percentage": 100.0, "remaining_ru": 0,
                "message": "Has alcanzado tu límite mensual de 1225 RU"}),
        # COMPORTAMIENTO ACTUAL (posible defecto): remaining_ru negativo cuando
        # el consumo supera el límite.
        (1300, {"type": "danger", "percentage": 106.1, "remaining_ru": -75,
                "message": "Has alcanzado tu límite mensual de 1225 RU"}),
    ])
    def test_basic(self, db, used, esperado):
        db.set_user(3, plan="basic", quota_limit=1225, quota_used=used)
        aviso = quota_middleware.get_quota_warning_info(3)
        if esperado is None:
            assert aviso is None
        else:
            assert aviso == {**esperado, "quota_limit": 1225, "quota_used": used, "plan": "basic"}

    def test_limite_cero_sin_aviso(self, db):
        db.set_user(1, quota_used=10)
        assert quota_middleware.get_quota_warning_info(1) is None


# ---------------------------------------------------------------------------
# quota_protected_serp_call: cuándo una llamada SERP consume RU
# ---------------------------------------------------------------------------

_FLASK = Flask("char_quotas")
_FLASK.secret_key = "solo-para-tests"

PARAMS = {"q": "zapatillas running", "gl": "es", "hl": "es", "api_key": "clave-ficticia"}


@pytest.fixture
def serp(monkeypatch):
    """Sustituye la llamada real a SerpAPI por un doble que cuenta ejecuciones."""
    llamadas = []

    def fake(params, call_type):
        llamadas.append((dict(params), call_type))
        return estado.resultado

    estado = SimpleNamespace(llamadas=llamadas, resultado=(True, {"organic_results": []}))
    monkeypatch.setattr(quota_middleware, "_execute_serp_call", fake)
    monkeypatch.setattr(quota_middleware, "_IS_DEPLOYED", False)
    monkeypatch.setenv("ENFORCE_QUOTAS", "true")
    quota_middleware.CALL_CACHE.clear()
    yield estado
    quota_middleware.CALL_CACHE.clear()


def _serp_como(user_id, params=PARAMS, call_type="json", via="g"):
    with _FLASK.test_request_context("/"):
        if user_id is not None and via == "g":
            g.user_id = user_id
        elif user_id is not None and via == "session":
            session["user_id"] = user_id
        return quota_middleware.quota_protected_serp_call(dict(params), call_type)


class TestLlamadaSerpProtegida:
    def test_usuario_de_pago_consume_1_ru_y_registra_evento(self, db, serp):
        ok, data = _serp_como(3)
        assert (ok, data) == (True, {"organic_results": []})
        assert len(serp.llamadas) == 1
        assert db.user(3)["quota_used"] == 1
        assert db.events() == [{
            "user_id": 3, "ru_consumed": 1, "source": "serp_api",
            "keyword": "zapatillas running", "country_code": "es",
            "metadata": {"call_type": "json", "cached": False},
        }]

    def test_usuario_por_sesion(self, db, serp):
        _serp_como(3, via="session")
        assert db.user(3)["quota_used"] == 1

    def test_repetida_en_cache_no_consume(self, db, serp):
        _serp_como(3)
        ok, _ = _serp_como(3)
        assert ok is True
        assert len(serp.llamadas) == 2  # se vuelve a ejecutar la llamada real
        assert db.user(3)["quota_used"] == 1
        assert len(db.events()) == 1

    def test_la_cache_ignora_api_key(self, db, serp):
        _serp_como(3)
        _serp_como(3, params={**PARAMS, "api_key": "otra"})
        assert db.user(3)["quota_used"] == 1

    def test_cache_caducada_vuelve_a_consumir(self, db, serp, monkeypatch):
        monkeypatch.setattr(quota_middleware, "CACHE_DURATION", 0)
        _serp_como(3)
        _serp_como(3)
        assert db.user(3)["quota_used"] == 2
        assert len(db.events()) == 2

    def test_cache_global_entre_usuarios(self, db, serp):
        # COMPORTAMIENTO ACTUAL (posible defecto): la caché no distingue usuario;
        # si otro usuario ya hizo la misma búsqueda, la segunda no gasta RU.
        db.set_user(2, plan="basic", quota_limit=1225, quota_used=0)
        _serp_como(3)
        _serp_como(2)
        assert (db.user(3)["quota_used"], db.user(2)["quota_used"]) == (1, 0)
        assert [e["user_id"] for e in db.events()] == [3]

    def test_cache_se_salta_la_validacion_de_cuota(self, db, serp):
        # COMPORTAMIENTO ACTUAL: la caché se consulta antes que la cuota, así que
        # un usuario agotado puede repetir búsquedas cacheadas.
        _serp_como(3)
        db.set_user(3, quota_used=15000)
        ok, _ = _serp_como(3)
        assert ok is True
        assert db.user(3)["quota_used"] == 15000

    def test_free_registra_evento_sin_tocar_quota_used(self, db, serp):
        ok, _ = _serp_como(1)
        assert ok is True
        assert db.user(1)["quota_used"] == 0
        assert [(e["user_id"], e["ru_consumed"], e["source"]) for e in db.events()] == [(1, 1, "serp_api")]

    def test_agotado_bloqueado_sin_ejecutar(self, db, serp):
        db.set_user(3, plan="basic", quota_limit=1225, quota_used=1225)
        ok, data = _serp_como(3)
        assert ok is False
        assert {k: data[k] for k in ("error", "message", "action_required", "blocked")} == {
            "error": "Quota exceeded",
            "message": "Cuota agotada (1225/1225 RU)",
            "action_required": "upgrade",
            "blocked": True,
        }
        assert data["quota_info"]["remaining"] == 0
        assert serp.llamadas == []
        assert db.events() == []

    def test_llamada_fallida_no_consume_ni_cachea(self, db, serp):
        serp.resultado = (False, {"error": "timeout"})
        assert _serp_como(3) == (False, {"error": "timeout"})
        assert db.user(3)["quota_used"] == 0
        assert db.events() == []
        assert quota_middleware.CALL_CACHE == {}

    def test_sin_gl_no_se_cobra(self, db, serp):
        # COMPORTAMIENTO ACTUAL (posible defecto): sin 'gl' se registra
        # country_code='unknown' (7 caracteres) en una columna VARCHAR(3); el
        # INSERT falla, track_quota_consumption devuelve False en silencio y la
        # llamada queda cacheada sin haber descontado RU.
        ok, _ = _serp_como(3, params={"q": "sin pais"})
        assert ok is True
        assert db.user(3)["quota_used"] == 0
        assert db.events() == []
        assert len(quota_middleware.CALL_CACHE) == 1

    def test_sin_usuario_en_request_local_no_consume(self, db, serp):
        ok, _ = _serp_como(None)
        assert ok is True
        assert len(serp.llamadas) == 1
        assert db.events() == []

    def test_sin_contexto_de_request_no_consume(self, db, serp):
        ok, _ = quota_middleware.quota_protected_serp_call(dict(PARAMS), "json")
        assert ok is True
        assert len(serp.llamadas) == 1
        assert db.events() == []

    def test_desplegado_bloquea_request_anonima(self, db, serp, monkeypatch):
        monkeypatch.setattr(quota_middleware, "_IS_DEPLOYED", True)
        assert _serp_como(None) == (False, {
            "error": "Authentication required",
            "message": "Debes iniciar sesión para realizar esta operación.",
            "blocked": True,
        })
        assert serp.llamadas == []

    def test_desplegado_permite_procesos_sin_request(self, db, serp, monkeypatch):
        monkeypatch.setattr(quota_middleware, "_IS_DEPLOYED", True)
        ok, _ = quota_middleware.quota_protected_serp_call(dict(PARAMS), "json")
        assert ok is True
        assert len(serp.llamadas) == 1

    @pytest.mark.parametrize("valor,controla", [
        ("true", True), ("TRUE", True), ("True", True),
        ("false", False), ("1", False), ("yes", False), (None, False),
    ])
    def test_enforce_quotas(self, db, serp, monkeypatch, valor, controla):
        if valor is None:
            monkeypatch.delenv("ENFORCE_QUOTAS", raising=False)
        else:
            monkeypatch.setenv("ENFORCE_QUOTAS", valor)
        db.set_user(3, plan="basic", quota_limit=1225, quota_used=1225)
        ok, _ = _serp_como(3)
        if controla:
            # Agotado: bloqueado y sin ejecutar.
            assert ok is False and serp.llamadas == []
        else:
            # Sin control: se ejecuta aunque esté agotado, sin registrar nada ni cachear.
            assert ok is True and len(serp.llamadas) == 1
            assert db.events() == [] and quota_middleware.CALL_CACHE == {}
        assert db.user(3)["quota_used"] == 1225


# ===========================================================================
# 3. Registro de consumo
# ===========================================================================

class TestTrackQuotaConsumption:
    # (ru, source, keyword, country, metadata, update_user_quota) -> (ok, quota_used, evento o None)
    @pytest.mark.parametrize("ru,source,keyword,country,metadata,update,esperado", [
        pytest.param(1, "manual_ai", "kw", "ES", {"project_id": 5}, True,
                     (True, 1, {"ru_consumed": 1, "source": "manual_ai", "keyword": "kw", "country_code": "ES",
                                "metadata": {"project_id": 5}}), id="manual_ai-actualiza"),
        pytest.param(1, "serp_api", "kw", "es", None, False,
                     (True, 0, {"ru_consumed": 1, "source": "serp_api", "keyword": "kw", "country_code": "es",
                                "metadata": None}), id="solo-evento"),
        # metadata {} se guarda como NULL (json.dumps solo si es truthy).
        pytest.param(2, "ai_mode", None, None, {}, True,
                     (True, 2, {"ru_consumed": 2, "source": "ai_mode", "keyword": None, "country_code": None,
                                "metadata": None}), id="ai_mode-metadata-vacia"),
        # El esquema de pruebas (volcado de staging) no tiene chk_source ni
        # chk_ru_consumed: cualquier source y ru 0 se aceptan.
        pytest.param(0, "cualquier_cosa", "kw", "US", None, True,
                     (True, 0, {"ru_consumed": 0, "source": "cualquier_cosa", "keyword": "kw", "country_code": "US",
                                "metadata": None}), id="ru-0-source-libre"),
        # COMPORTAMIENTO ACTUAL (posible defecto): sin validación, un ru negativo
        # descuenta del contador.
        pytest.param(-3, "manual_ai", "kw", "ES", None, True,
                     (True, -3, {"ru_consumed": -3, "source": "manual_ai", "keyword": "kw", "country_code": "ES",
                                 "metadata": None}), id="ru-negativo"),
        pytest.param(1, "serp_api", "kw", "unknown", None, True, (False, 0, None), id="country-demasiado-largo"),
        pytest.param(1, "serp_api", "k" * 300, "es", None, True, (False, 0, None), id="keyword-demasiado-larga"),
    ])
    def test_tabla(self, db, ru, source, keyword, country, metadata, update, esperado):
        ok = database.track_quota_consumption(3, ru, source, keyword=keyword, country_code=country,
                                              metadata=metadata, update_user_quota=update)
        ok_e, used_e, evento = esperado
        assert ok is ok_e
        assert db.user(3)["quota_used"] == used_e
        assert db.events() == ([{"user_id": 3, **evento}] if evento else [])

    @pytest.mark.parametrize("update", [True, False])
    def test_usuario_inexistente(self, db, update):
        # La FK de user_id hace fallar el INSERT antes de mirar el UPDATE.
        assert database.track_quota_consumption(999, 1, "manual_ai", update_user_quota=update) is False
        assert db.events() == []

    def test_acumula(self, db):
        for _ in range(3):
            assert database.track_quota_consumption(3, 2, "manual_ai", keyword="kw", country_code="ES")
        assert db.user(3)["quota_used"] == 6
        assert len(db.events(3)) == 3

    def test_sin_conexion(self, db, monkeypatch):
        monkeypatch.setattr(database, "get_db_connection", _sin_conexion)
        assert database.track_quota_consumption(3, 1, "manual_ai") is False
        monkeypatch.undo()
        assert db.user(3)["quota_used"] == 0
        assert db.events() == []


class _PgError(Exception):
    def __init__(self, pgcode):
        super().__init__(f"error pg {pgcode}")
        self.pgcode = pgcode


class _ConexionFalsa:
    """Conexión cuyo INSERT falla con el pgcode indicado (el to_regclass pasa)."""

    def __init__(self, pgcode):
        self.pgcode = pgcode
        self.rollbacks = 0
        self.cierres = 0

    def cursor(self):
        conn = self

        class _Cur:
            rowcount = 1

            def execute(self, sql, params=None):
                if "to_regclass" in sql:
                    return
                raise _PgError(conn.pgcode)

            def fetchone(self):
                return {"reg": "quota_usage_events"}

        return _Cur()

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        pass

    def close(self):
        self.cierres += 1


class TestTrackReintentos:
    @pytest.fixture
    def esperas(self, monkeypatch):
        registro = []
        monkeypatch.setattr(database.time, "sleep", registro.append)
        return registro

    @pytest.mark.parametrize("pgcode", [errorcodes.DEADLOCK_DETECTED, errorcodes.SERIALIZATION_FAILURE])
    def test_reintenta_3_veces_con_backoff(self, monkeypatch, esperas, pgcode):
        conexiones = []

        def nueva():
            conexiones.append(_ConexionFalsa(pgcode))
            return conexiones[-1]

        monkeypatch.setattr(database, "get_db_connection", nueva)
        assert database.track_quota_consumption(3, 1, "manual_ai") is False
        assert len(conexiones) == 3
        assert esperas == [0.5, 1.0]
        assert all(c.rollbacks == 1 and c.cierres == 1 for c in conexiones)

    def test_error_no_reintentable_un_solo_intento(self, monkeypatch, esperas):
        conexiones = []

        def nueva():
            conexiones.append(_ConexionFalsa(errorcodes.UNIQUE_VIOLATION))
            return conexiones[-1]

        monkeypatch.setattr(database, "get_db_connection", nueva)
        assert database.track_quota_consumption(3, 1, "manual_ai") is False
        assert len(conexiones) == 1 and esperas == []

    def test_reintento_tras_deadlock_registra_una_vez(self, db, monkeypatch, esperas):
        real = database.get_db_connection
        secuencia = iter([_ConexionFalsa(errorcodes.DEADLOCK_DETECTED)])
        monkeypatch.setattr(database, "get_db_connection", lambda: next(secuencia, None) or real())
        assert database.track_quota_consumption(3, 1, "manual_ai", keyword="kw", country_code="ES") is True
        assert esperas == [0.5]
        assert db.user(3)["quota_used"] == 1
        assert len(db.events()) == 1


class TestQuotaManagerConsumo:
    def test_record_quota_usage(self, db):
        assert quota_manager.record_quota_usage(3, 4, "serp_json", {"project_id": 9}) is True
        assert db.user(3)["quota_used"] == 4
        # keyword y country_code se guardan como cadena vacía; source = operation_type.
        assert db.events() == [{"user_id": 3, "ru_consumed": 4, "source": "serp_json", "keyword": "",
                                "country_code": "", "metadata": {"project_id": 9}}]

    def test_record_quota_usage_insert_fallido_devuelve_true_sin_guardar(self, db):
        # COMPORTAMIENTO ACTUAL (posible defecto): si el INSERT del evento falla
        # (aquí source de más de 50 caracteres) la transacción queda abortada,
        # el commit la deshace en silencio y la función devuelve True sin haber
        # sumado el consumo.
        assert quota_manager.record_quota_usage(3, 4, "x" * 60) is True
        assert db.user(3)["quota_used"] == 0
        assert db.events() == []

    def test_record_quota_usage_usuario_inexistente_devuelve_true(self, db):
        # COMPORTAMIENTO ACTUAL (posible defecto): True aunque no exista el usuario.
        assert quota_manager.record_quota_usage(999, 1, "serp_json") is True
        assert db.events() == []

    def test_consume_user_quota_con_cuota(self, db):
        db.set_user(3, plan="basic", quota_limit=1225, quota_used=1200)
        res = quota_manager.consume_user_quota(3, 5, "api_call", {"x": 1})
        assert res == {"success": True, "message": "Consumed 5 RU successfully",
                       "remaining": 20, "used": 1205, "limit": 1225}
        assert db.user(3)["quota_used"] == 1205
        # COMPORTAMIENTO ACTUAL: no registra evento (TODO en el código).
        assert db.events() == []

    def test_consume_user_quota_justo_hasta_el_limite(self, db):
        db.set_user(3, plan="basic", quota_limit=1225, quota_used=1220)
        assert quota_manager.consume_user_quota(3, 5)["remaining"] == 0
        assert db.user(3)["quota_used"] == 1225

    @pytest.mark.parametrize("user_id,used", [(3, 1225), (999, 0)])
    def test_consume_user_quota_sin_cuota_lanza(self, db, user_id, used):
        # COMPORTAMIENTO ACTUAL (posible defecto): la rama QUOTA_EXCEEDED hace
        # return antes de asignar `conn` y el finally lanza UnboundLocalError.
        db.set_user(3, plan="basic", quota_limit=1225, quota_used=1225)
        with pytest.raises(UnboundLocalError):
            quota_manager.consume_user_quota(user_id, 1)
        assert db.user(3)["quota_used"] == 1225

    def test_consume_user_quota_con_bd_caida(self, monkeypatch):
        monkeypatch.setattr(quota_manager, "get_db_connection", _sin_conexion)
        assert quota_manager.consume_user_quota(3, 1) == {
            "success": False, "message": "Database connection failed",
            "remaining": 0, "error_code": "DB_ERROR",
        }
        # Con 2 RU el fail-open ya no alcanza y se cae en la rama que lanza.
        with pytest.raises(UnboundLocalError):
            quota_manager.consume_user_quota(3, 2)


class TestPausasYReanudacion:
    @pytest.mark.parametrize("module,funcion", [
        ("manual_ai", database.pause_manual_ai_projects_for_quota),
        ("ai_mode", database.pause_ai_mode_projects_for_quota),
        ("llm_monitoring", database.pause_llm_projects_for_quota),
    ])
    def test_pausa_de_usuario_solo_proyectos_activos(self, db, module, funcion):
        activo = db.add_project(module, 3, name="Activo")
        inactivo = db.add_project(module, 3, name="Inactivo", is_active=False)
        ajeno = db.add_project(module, 1, name="Ajeno")
        assert funcion(3, RESET_FIJO) is True
        p = db.project(module, activo)
        assert (p["is_paused_by_quota"], p["paused_until"], p["paused_reason"]) == (True, RESET_FIJO, "quota_exceeded")
        assert p["paused_at"] is not None
        assert db.project(module, inactivo)["is_paused_by_quota"] is False
        assert db.project(module, ajeno)["is_paused_by_quota"] is False

    @pytest.mark.parametrize("module,funcion", [
        ("manual_ai", database.pause_manual_ai_projects_for_quota),
        ("ai_mode", database.pause_ai_mode_projects_for_quota),
        ("llm_monitoring", database.pause_llm_projects_for_quota),
    ])
    def test_pausa_con_paused_until_none_guarda_null(self, db, module, funcion):
        # COMPORTAMIENTO ACTUAL: la función guarda NULL tal cual; el fallback de
        # +30 días lo aplica cada llamador, no la función.
        pid = db.add_project(module, 3)
        assert funcion(3) is True
        p = db.project(module, pid)
        assert (p["is_paused_by_quota"], p["paused_until"]) == (True, None)

    def test_pausa_ai_overview_a_nivel_usuario(self, db):
        assert database.pause_ai_overview_for_quota(3, RESET_FIJO, reason="quota_exceeded") is True
        u = db.user(3)
        assert (u["ai_overview_paused_until"], u["ai_overview_paused_reason"]) == (RESET_FIJO, "quota_exceeded")
        assert u["ai_overview_paused_at"] is not None

    def test_reanudar_limpia_todo_del_usuario(self, db):
        ahora = datetime.now(UTC)
        db.set_user(3, ai_overview_paused_until=ahora + timedelta(days=5), ai_overview_paused_reason="quota_exceeded",
                    ai_overview_paused_at=ahora)
        pausa = dict(is_paused_by_quota=True, paused_until=ahora + timedelta(days=5), paused_at=ahora)
        ids = {
            "manual_ai": db.add_project("manual_ai", 3, paused_reason="project_quota_exceeded", **pausa),
            "ai_mode": db.add_project("ai_mode", 3, paused_reason="quota_exceeded", is_active=False, **pausa),
            "llm_monitoring": db.add_project("llm_monitoring", 3, paused_reason="quota_exceeded",
                                             **{**pausa, "paused_until": ahora - timedelta(days=1)}),
        }
        ajeno = db.add_project("manual_ai", 1, paused_reason="quota_exceeded", **pausa)

        assert database.resume_quota_pauses_for_user(3) is True

        u = db.user(3)
        assert (u["ai_overview_paused_until"], u["ai_overview_paused_at"], u["ai_overview_paused_reason"]) == (None, None, None)
        # Despausa también la pausa por tope de proyecto y los proyectos
        # inactivos, sin tocar is_active.
        for module, pid in ids.items():
            p = db.project(module, pid)
            assert (p["is_paused_by_quota"], p["paused_until"], p["paused_at"], p["paused_reason"]) == (False, None, None, None)
        assert db.project("ai_mode", ids["ai_mode"])["is_active"] is False
        assert db.project("manual_ai", ajeno)["is_paused_by_quota"] is True


# ===========================================================================
# 4. Fechas de reset y ventana de cuota
# ===========================================================================

D = datetime


class TestProximoReset:
    # (period_start, period_end, last_reset, now) -> próximo reset
    @pytest.mark.parametrize("period_start,period_end,last_reset,now,esperado", [
        # Periodo NULL: base = now + 30 días fijos (no "mismo día del mes siguiente").
        pytest.param(None, None, None, D(2026, 1, 31), D(2026, 3, 2), id="null-31ene-no-bisiesto"),
        pytest.param(None, None, None, D(2028, 1, 31), D(2028, 3, 1), id="null-31ene-bisiesto"),
        pytest.param(None, None, None, D(2026, 2, 28, 10, 30), D(2026, 3, 30, 10, 30), id="null-28feb-conserva-hora"),
        pytest.param(None, None, None, D(2028, 2, 29), D(2028, 3, 30), id="null-29feb-bisiesto"),
        # Día 29/30/31 como último reset.
        pytest.param(None, None, D(2026, 1, 29), D(2026, 1, 30), D(2026, 2, 28), id="29ene-no-bisiesto"),
        pytest.param(None, None, D(2026, 1, 30), D(2026, 1, 31), D(2026, 3, 1), id="30ene-no-bisiesto"),
        pytest.param(None, None, D(2026, 1, 31), D(2026, 2, 1), D(2026, 3, 2), id="31ene-no-bisiesto"),
        pytest.param(None, None, D(2028, 1, 30), D(2028, 1, 31), D(2028, 2, 29), id="30ene-bisiesto"),
        pytest.param(None, None, D(2028, 1, 31), D(2028, 2, 1), D(2028, 3, 1), id="31ene-bisiesto"),
        pytest.param(None, None, D(2026, 3, 31), D(2026, 4, 1), D(2026, 4, 30), id="31mar"),
        pytest.param(None, None, D(2026, 4, 30), D(2026, 5, 1), D(2026, 5, 30), id="30abr"),
        pytest.param(None, None, D(2026, 12, 31), D(2027, 1, 1), D(2027, 1, 30), id="31dic-cambio-de-anio"),
        # Mensual con periodo Stripe vigente: cap en period_end.
        pytest.param(D(2026, 1, 31), D(2026, 2, 28), None, D(2026, 2, 1), D(2026, 2, 28), id="mensual-cap-28feb"),
        pytest.param(D(2028, 1, 31), D(2028, 2, 29), None, D(2028, 2, 1), D(2028, 2, 29), id="mensual-cap-29feb-bisiesto"),
        pytest.param(D(2026, 3, 1), D(2026, 4, 1), None, D(2026, 3, 2), D(2026, 3, 31), id="mensual-31-dias-sin-cap"),
        pytest.param(None, D(2026, 8, 20), D(2026, 8, 1), D(2026, 8, 2), D(2026, 8, 20), id="mensual-cap-last_reset"),
        # period_end == now no se considera vigente (> estricto).
        pytest.param(None, D(2026, 2, 10), D(2026, 1, 20), D(2026, 2, 10), D(2026, 2, 19), id="period_end-igual-a-now"),
        # Anual: ventanas de 30 días, nunca salta al period_end lejano.
        pytest.param(D(2026, 1, 15), D(2027, 1, 15), None, D(2026, 1, 16), D(2026, 2, 14), id="anual-inicio"),
        pytest.param(None, D(2027, 1, 1), D(2026, 1, 1), D(2026, 4, 15), D(2026, 5, 1), id="anual-varios-ciclos-vencidos"),
        pytest.param(None, D(2027, 1, 1), D(2026, 12, 10), D(2026, 12, 11), D(2027, 1, 1), id="anual-cap-al-final"),
        # Legacy con period_end pasado: se ignora el cap y se avanza de 30 en 30.
        pytest.param(None, D(2026, 2, 1), D(2026, 1, 1), D(2026, 6, 15), D(2026, 6, 30), id="period_end-pasado"),
        pytest.param(D(2025, 1, 1), D(2025, 2, 1), None, D(2026, 6, 15), D(2026, 6, 25), id="periodo-entero-pasado"),
        # Justo en el límite: base + 30 == now se considera pasado y avanza.
        pytest.param(None, None, D(2026, 5, 1), D(2026, 5, 31), D(2026, 6, 30), id="base+30-igual-a-now"),
        # COMPORTAMIENTO ACTUAL (posible defecto): un last_reset futuro no se
        # acota; el reset queda a más de 30 días (aquí 89) de now.
        pytest.param(None, None, D(2026, 3, 1), D(2026, 1, 1), D(2026, 3, 31), id="last_reset-futuro"),
        # last_reset en texto ISO se interpreta; texto inválido cae a now.
        pytest.param(None, None, "2026-01-10T00:00:00", D(2026, 1, 11), D(2026, 2, 9), id="last_reset-iso"),
        pytest.param(None, None, "no-es-fecha", D(2026, 1, 11), D(2026, 2, 10), id="last_reset-invalido"),
    ])
    def test_tabla(self, period_start, period_end, last_reset, now, esperado):
        assert quota_manager.compute_next_quota_reset_date(
            period_start=period_start, period_end=period_end, last_reset=last_reset, now=now
        ) == esperado

    def test_intervalo_configurable(self, monkeypatch):
        monkeypatch.setenv("QUOTA_RESET_INTERVAL_DAYS", "7")
        assert quota_manager.compute_next_quota_reset_date(last_reset=D(2026, 2, 25), now=D(2026, 2, 26)) == D(2026, 3, 4)

    def test_todo_aware_funciona(self):
        now = datetime(2026, 9, 27, 12, tzinfo=UTC)
        assert quota_manager.compute_next_quota_reset_date(
            period_end=datetime(2026, 10, 10, tzinfo=UTC), last_reset=datetime(2026, 9, 20, tzinfo=UTC), now=now
        ) == datetime(2026, 10, 10, tzinfo=UTC)

    def test_sin_now_devuelve_utcnow_mas_30_naive(self):
        antes = datetime.utcnow()
        r = quota_manager.compute_next_quota_reset_date()
        despues = datetime.utcnow()
        assert r.tzinfo is None
        assert antes + timedelta(days=30) <= r <= despues + timedelta(days=30)

    @pytest.mark.parametrize("kwargs_de, dias_esperados", [
        # last_reset hace 5 días -> +30 desde él = dentro de 25 días
        pytest.param(lambda ahora: {"last_reset": ahora - timedelta(days=5)}, 25, id="last_reset-aware"),
        # sin base: ahora + 30 (el period_end a 60 días no recorta)
        pytest.param(lambda ahora: {"period_end": ahora + timedelta(days=60)}, 30, id="period_end-aware"),
        # base = inicio de periodo (hace 10 días) + 30 = dentro de 20 = period_end
        pytest.param(lambda ahora: {"period_start": ahora - timedelta(days=10),
                                    "period_end": ahora + timedelta(days=20)}, 20, id="periodo-aware"),
    ])
    def test_fechas_aware_sin_now_devuelven_fecha_aware(self, kwargs_de, dias_esperados):
        # ARREGLADO (2026-09-28): antes, con now=None se comparaba utcnow() (sin
        # zona) con fechas de BD (timestamptz, con zona) y saltaba TypeError: es el
        # caso de reset_user_quota y del reset manual del panel admin.
        ahora = datetime.now(UTC)
        r = quota_manager.compute_next_quota_reset_date(**kwargs_de(ahora))
        assert r.tzinfo is not None
        esperado = ahora + timedelta(days=dias_esperados)
        assert abs(r - esperado) <= timedelta(minutes=2)

    def test_fechas_mezcladas_con_y_sin_zona(self):
        # Una fecha sin zona se interpreta como UTC si alguna otra la trae.
        ahora = datetime.now(UTC)
        r = quota_manager.compute_next_quota_reset_date(
            last_reset=(ahora - timedelta(days=5)).replace(tzinfo=None),
            period_end=ahora + timedelta(days=60),
        )
        assert r.tzinfo is not None
        assert abs(r - (ahora + timedelta(days=25))) <= timedelta(minutes=2)


class TestVentanaDeCuota:
    @pytest.mark.parametrize("fila,today,esperado", [
        # quota_reset_date manda: [reset - 30 días, reset).
        pytest.param({"quota_reset_date": D(2026, 3, 1)}, None, (date(2026, 1, 30), date(2026, 3, 1)), id="reset-1mar-no-bisiesto"),
        pytest.param({"quota_reset_date": D(2028, 3, 1)}, None, (date(2028, 1, 31), date(2028, 3, 1)), id="reset-1mar-bisiesto"),
        pytest.param({"quota_reset_date": D(2026, 3, 31)}, None, (date(2026, 3, 1), date(2026, 3, 31)), id="reset-31mar"),
        pytest.param({"quota_reset_date": D(2026, 5, 31)}, None, (date(2026, 5, 1), date(2026, 5, 31)), id="reset-31may"),
        pytest.param({"quota_reset_date": date(2026, 1, 29)}, None, (date(2025, 12, 30), date(2026, 1, 29)), id="reset-date-29ene"),
        # La fecha se toma en la zona del propio datetime, sin pasar a UTC.
        pytest.param({"quota_reset_date": datetime(2026, 10, 1, 0, 30, tzinfo=timezone(timedelta(hours=2)))}, None,
                     (date(2026, 9, 1), date(2026, 10, 1)), id="reset-aware-+02"),
        # quota_reset_date gana aunque el today pedido esté en otro mes.
        pytest.param({"quota_reset_date": D(2026, 3, 1)}, date(2026, 9, 15), (date(2026, 1, 30), date(2026, 3, 1)), id="reset-ignora-today"),
        # Sin reset: periodo Stripe completo.
        pytest.param({"current_period_start": D(2026, 9, 5), "current_period_end": D(2026, 10, 5)}, None,
                     (date(2026, 9, 5), date(2026, 10, 5)), id="periodo-mensual"),
        # COMPORTAMIENTO ACTUAL (posible defecto): anual sin quota_reset_date ->
        # la ventana es el año entero y el tope "mensual" pasa a ser anual.
        pytest.param({"current_period_start": D(2026, 1, 15), "current_period_end": D(2027, 1, 15)}, None,
                     (date(2026, 1, 15), date(2027, 1, 15)), id="periodo-anual"),
        # Solo uno de los dos extremos del periodo: mes natural.
        pytest.param({"current_period_start": D(2026, 9, 5)}, date(2026, 9, 20), (date(2026, 9, 1), date(2026, 10, 1)), id="periodo-incompleto"),
        # Mes natural de today.
        pytest.param({}, date(2026, 1, 31), (date(2026, 1, 1), date(2026, 2, 1)), id="natural-31ene"),
        pytest.param({}, date(2026, 2, 28), (date(2026, 2, 1), date(2026, 3, 1)), id="natural-28feb"),
        pytest.param({}, date(2028, 2, 29), (date(2028, 2, 1), date(2028, 3, 1)), id="natural-29feb-bisiesto"),
        pytest.param({}, date(2026, 4, 30), (date(2026, 4, 1), date(2026, 5, 1)), id="natural-30abr"),
        pytest.param({}, date(2026, 12, 31), (date(2026, 12, 1), date(2027, 1, 1)), id="natural-31dic"),
        pytest.param(None, date(2026, 7, 29), (date(2026, 7, 1), date(2026, 8, 1)), id="fila-none"),
    ])
    def test_tabla(self, fila, today, esperado):
        assert project_quota.compute_quota_window(fila, today=today) == esperado


class TestResets:
    def test_reset_user_quota_sin_fechas(self, db):
        db.set_user(1, quota_used=40)
        db.add_project("manual_ai", 1, is_paused_by_quota=True, paused_reason="quota_exceeded",
                       paused_until=RESET_FIJO)
        assert quota_manager.reset_user_quota(1, admin_id=2) is True
        u = db.user(1)
        assert u["quota_used"] == 0
        faltan = db.one("SELECT quota_reset_date - NOW() AS d FROM users WHERE id = 1")["d"]
        assert timedelta(days=30) - timedelta(minutes=2) <= faltan <= timedelta(days=30) + timedelta(minutes=2)
        assert db.events(1) == [{
            "user_id": 1, "ru_consumed": 0, "source": "quota_reset", "keyword": "quota_reset", "country_code": "",
            "metadata": {"previous_usage": 40, "reset_by_admin": 2, "reason": "Manual quota reset"},
        }]
        assert db.all("SELECT is_paused_by_quota FROM manual_ai_projects") == [{"is_paused_by_quota": False}]

    def test_reset_user_quota_con_fechas_resetea(self, db):
        # ARREGLADO (2026-09-28): con quota_reset_date o periodo en BD (con zona)
        # antes saltaba TypeError y la función devolvía False sin resetear.
        db.set_user(3, quota_used=500)
        periodo_fin = db.user(3)["current_period_end"]
        assert quota_manager.reset_user_quota(3) is True
        u = db.user(3)
        assert u["quota_used"] == 0
        # +30 días desde el último reset, recortado al fin del periodo Stripe
        assert u["quota_reset_date"] == periodo_fin
        [evento] = db.events(3)
        assert (evento["ru_consumed"], evento["source"]) == (0, "quota_reset")
        assert evento["metadata"]["previous_usage"] == 500

    def test_reset_manual_admin_sin_fechas(self, db):
        db.set_user(1, quota_used=40)
        res = admin_billing_panel.reset_user_quota_manual(1, 2)
        assert (res["success"], res["previous_usage"], res["new_usage"]) == (True, 40, 0)
        assert res["message"] == "Quota reset successfully. Previous usage: 40 RU"
        assert db.user(1)["quota_used"] == 0
        [evento] = db.events(1)
        assert (evento["ru_consumed"], evento["source"], evento["keyword"]) == (0, "manual_ai", "admin_quota_reset")

    def test_reset_manual_admin_con_fechas_resetea(self, db):
        # ARREGLADO (2026-09-28): mismo fallo que arriba en el reset manual del
        # panel admin (admin_billing_panel.py); con usuarios de pago no funcionaba.
        db.set_user(3, quota_used=500)
        periodo_fin = db.user(3)["current_period_end"]
        res = admin_billing_panel.reset_user_quota_manual(3, 2)
        assert (res["success"], res["previous_usage"], res["new_usage"]) == (True, 500, 0)
        u = db.user(3)
        assert u["quota_used"] == 0
        assert u["quota_reset_date"] == periodo_fin

    @pytest.mark.parametrize("resetear", [
        pytest.param(lambda: quota_manager.reset_user_quota(3), id="reset_user_quota"),
        pytest.param(lambda: admin_billing_panel.reset_user_quota_manual(3, 2)["success"], id="panel_admin"),
    ])
    def test_reset_manual_conserva_el_proximo_reset_automatico(self, db, resetear):
        # ARREGLADO (2026-09-28): el reset manual recalculaba la fecha desde el
        # próximo reset previsto (+30 días); en un plan anual el ciclo se movía
        # un mes y el usuario perdía el reset que le tocaba.
        ahora = datetime.now(timezone.utc)
        previsto = (ahora + timedelta(days=10)).replace(microsecond=0)
        db.set_user(3, quota_used=500, current_period_start=ahora - timedelta(days=50),
                    current_period_end=ahora + timedelta(days=315), quota_reset_date=previsto)
        assert resetear() is True
        u = db.user(3)
        assert (u["quota_used"], u["quota_reset_date"]) == (0, previsto)

    @pytest.mark.parametrize("resetear", [
        pytest.param(lambda: quota_manager.reset_user_quota(3), id="reset_user_quota"),
        pytest.param(lambda: admin_billing_panel.reset_user_quota_manual(3, 2)["success"], id="panel_admin"),
    ])
    def test_reset_manual_con_reset_vencido_calcula_el_siguiente(self, db, resetear):
        ahora = datetime.now(timezone.utc)
        vencido = (ahora - timedelta(days=2)).replace(microsecond=0)
        db.set_user(3, quota_used=500, current_period_start=ahora - timedelta(days=50),
                    current_period_end=ahora + timedelta(days=315), quota_reset_date=vencido)
        assert resetear() is True
        u = db.user(3)
        assert (u["quota_used"], u["quota_reset_date"]) == (0, vencido + timedelta(days=30))

    def test_reset_manual_exige_admin(self, db):
        assert admin_billing_panel.reset_user_quota_manual(1, 3) == {
            "success": False, "error": "Admin not found or insufficient permissions"}


# ===========================================================================
# 5. Unidades LLM y límites LLM por plan
# ===========================================================================

class TestUnidadesLLM:
    def test_pesos_cargados(self):
        assert llm_monitoring_limits.SEARCH_UNIT_WEIGHTS == {"openai": 7, "anthropic": 10, "google": 3, "perplexity": 3}

    @pytest.mark.parametrize("proveedor,con_busqueda,sin_busqueda", [
        ("openai", 7, 1),
        ("anthropic", 10, 1),
        ("google", 3, 1),
        ("perplexity", 3, 1),
        # Las claves son los nombres internos: 'claude' y 'gemini' no tienen peso.
        ("claude", 1, 1),
        ("gemini", 1, 1),
        ("OpenAI", 1, 1),
        ("desconocido", 1, 1),
    ])
    def test_por_proveedor(self, proveedor, con_busqueda, sin_busqueda):
        assert llm_monitoring_limits.units_per_task(proveedor, "auto") == con_busqueda
        for modo in ("off", None, "", "AUTO", "Auto", " auto", "on", "true"):
            assert llm_monitoring_limits.units_per_task(proveedor, modo) == sin_busqueda

    @pytest.mark.parametrize("modo,esperado", [
        ("auto", {"openai": 7, "anthropic": 10, "google": 3, "perplexity": 3}),
        ("off", {"openai": 1, "anthropic": 1, "google": 1, "perplexity": 1}),
        (None, {"openai": 1, "anthropic": 1, "google": 1, "perplexity": 1}),
    ])
    def test_por_proyecto(self, modo, esperado):
        assert llm_monitoring_limits.units_by_provider(llm_monitoring_limits.LLM_PROVIDERS, modo) == esperado
        # Una pasada de 10 prompts por los 4 LLM: 230 unidades con búsqueda, 40 sin ella.
        assert 10 * sum(esperado.values()) == (230 if modo == "auto" else 40)

    def test_por_proyecto_sin_proveedores_y_repetidos(self):
        assert llm_monitoring_limits.units_by_provider([], "auto") == {}
        assert llm_monitoring_limits.units_by_provider(["google", "google"], "auto") == {"google": 3}

    def test_units_sql_con_columna_migrada(self, db):
        assert llm_monitoring_limits.llm_units_sql() == "SUM(units_consumed)"
        assert llm_monitoring_limits.llm_units_sql("r") == "SUM(r.units_consumed)"

    def test_units_sql_sin_conexion_cuenta_filas(self, monkeypatch):
        monkeypatch.setattr(llm_monitoring_limits, "get_db_connection", _sin_conexion)
        assert llm_monitoring_limits.llm_units_sql("r") == "COUNT(*)"


class TestAccesoYLimitesLLM:
    @pytest.mark.parametrize("plan,esperado", [
        ("basic", {"max_projects": 1, "max_prompts_per_project": 20, "max_monthly_units": 640}),
        ("premium", {"max_projects": 3, "max_prompts_per_project": 30, "max_monthly_units": 2880}),
        ("business", {"max_projects": 5, "max_prompts_per_project": 60, "max_monthly_units": 9600}),
        ("enterprise", {"max_projects": None, "max_prompts_per_project": None, "max_monthly_units": None}),
        ("free", {"max_projects": 0, "max_prompts_per_project": 0, "max_monthly_units": 0}),
        ("inventado", {"max_projects": 0, "max_prompts_per_project": 0, "max_monthly_units": 0}),
    ])
    def test_limites_por_plan(self, plan, esperado):
        assert llm_monitoring_limits.get_llm_plan_limits(plan) == esperado

    @pytest.mark.parametrize("user,esperado", [
        (None, False),
        ({}, False),
        ({"role": "admin"}, True),
        ({"role": "admin", "plan": "free", "billing_status": "canceled"}, True),
        ({"plan": "free", "billing_status": "active"}, False),
        ({"plan": "basic", "billing_status": "active"}, True),
        ({"plan": "premium", "billing_status": "trialing"}, True),
        ({"plan": "business", "billing_status": "beta"}, True),
        ({"plan": "enterprise", "billing_status": "active"}, True),
        ({"plan": "business", "billing_status": "past_due"}, False),
        ({"plan": "business", "billing_status": "canceled"}, False),
        ({"plan": "business", "billing_status": "ACTIVE"}, False),
        ({"plan": "business"}, False),
        ({"plan": "business", "billing_status": None}, False),
    ])
    def test_acceso(self, user, esperado):
        assert llm_monitoring_limits.can_access_llm_monitoring(user) is esperado

    @pytest.mark.parametrize("plan,esperado", [
        ("free", ["basic", "premium", "business"]),
        (None, ["basic", "premium", "business"]),
        ("basic", ["premium", "business", "enterprise"]),
        ("premium", ["business", "enterprise"]),
        ("business", ["enterprise"]),
        ("enterprise", ["enterprise"]),
    ])
    def test_opciones_de_upgrade(self, plan, esperado):
        assert llm_monitoring_limits.get_upgrade_options(plan) == esperado


@pytest.fixture
def llm_db(db):
    """User 3 con ventana [2026-09-01, 2026-10-01): dos proyectos activos y uno
    inactivo con resultados dentro y fuera de la ventana; y un proyecto de otro
    usuario con resultados dentro."""
    db.set_user(3, quota_reset_date=RESET_FIJO)
    a = db.add_project("llm_monitoring", 3, name="A")
    b = db.add_project("llm_monitoring", 3, name="B")
    inactivo = db.add_project("llm_monitoring", 3, name="Inactivo", is_active=False)
    ajeno = db.add_project("llm_monitoring", 1, name="Ajeno")
    db.add_llm_result(a, date(2026, 8, 31), "openai", 3)      # fuera
    db.add_llm_result(a, date(2026, 9, 1), "openai", 7)       # dentro
    db.add_llm_result(a, date(2026, 9, 30), "anthropic", 10)  # dentro
    db.add_llm_result(a, date(2026, 10, 1), "google", 3)      # fuera
    db.add_llm_result(b, date(2026, 9, 15), "perplexity", 1)  # dentro
    db.add_llm_result(inactivo, date(2026, 9, 10), "google", 3)  # dentro (inactivo cuenta)
    db.add_llm_result(ajeno, date(2026, 9, 10), "openai", 100)   # otro usuario
    return SimpleNamespace(db=db, a=a, b=b, inactivo=inactivo, ajeno=ajeno)


class TestConsumoLLM:
    def test_suma_pesos_en_la_ventana(self, llm_db):
        # 7 + 10 + 1 + 3 (el proyecto inactivo también cuenta).
        assert llm_monitoring_limits.get_user_monthly_llm_usage(3) == 21

    def test_sin_columna_migrada_cuenta_filas(self, llm_db, monkeypatch):
        monkeypatch.setattr(llm_monitoring_limits.UNITS_SCHEMA, "available", lambda _get: False)
        assert llm_monitoring_limits.get_user_monthly_llm_usage(3) == 4

    def test_periodo_stripe_sin_reset(self, llm_db):
        llm_db.db.set_user(3, quota_reset_date=None, current_period_start=datetime(2026, 9, 10, tzinfo=UTC),
                           current_period_end=datetime(2026, 10, 10, tzinfo=UTC))
        # [09-10, 10-10): 10 (30-sep) + 1 (15-sep) + 3 (10-sep) + 3 (1-oct).
        assert llm_monitoring_limits.get_user_monthly_llm_usage(3) == 17

    def test_mes_natural_de_month_date(self, llm_db):
        llm_db.db.set_user(3, quota_reset_date=None, current_period_start=None, current_period_end=None)
        assert llm_monitoring_limits.get_user_monthly_llm_usage(3, date(2026, 8, 20)) == 3
        assert llm_monitoring_limits.get_user_monthly_llm_usage(3, date(2026, 10, 2)) == 3

    def test_reset_obsoleto_ignora_month_date(self, llm_db):
        # COMPORTAMIENTO ACTUAL (posible defecto): con un quota_reset_date viejo
        # (cron de reset sin pasar) la ventana queda en el pasado y el consumo
        # LLM sale 0 aunque month_date caiga en septiembre.
        llm_db.db.set_user(3, quota_reset_date=datetime(2026, 3, 1, tzinfo=UTC))
        assert llm_monitoring_limits.get_user_monthly_llm_usage(3, date(2026, 9, 15)) == 0

    def test_sin_conexion(self, monkeypatch):
        monkeypatch.setattr(llm_monitoring_limits, "get_db_connection", _sin_conexion)
        assert llm_monitoring_limits.get_user_monthly_llm_usage(3) == 0
        assert llm_monitoring_limits.count_user_active_projects(3) == 0
        assert llm_monitoring_limits.count_project_active_queries(1) == 0

    def test_contadores(self, llm_db):
        db = llm_db.db
        # Un proyecto pausado por cuota sigue contando como activo.
        db.exec("UPDATE llm_monitoring_projects SET is_paused_by_quota = TRUE WHERE id = %s", (llm_db.b,))
        assert llm_monitoring_limits.count_user_active_projects(3) == 2
        for i, activa in enumerate([True, True, False]):
            db.exec("INSERT INTO llm_monitoring_queries (project_id, query_text, is_active) VALUES (%s, %s, %s)",
                    (llm_db.a, f"consulta numero {i}", activa))
        assert llm_monitoring_limits.count_project_active_queries(llm_db.a) == 2


class TestResumenLimitesLLM:
    # Consumo 21 unidades y 2 proyectos activos (fixture llm_db).
    @pytest.mark.parametrize("extra,esperado", [
        ({"plan": "basic"}, (1, 20, 640, 619)),
        ({"plan": "premium"}, (3, 30, 2880, 2859)),
        ({"plan": "business"}, (5, 60, 9600, 9579)),
        ({"plan": "free"}, (0, 0, 0, 0)),
        ({}, (0, 0, 0, 0)),
        ({"plan": "enterprise"}, (None, None, None, None)),
        ({"plan": "enterprise", "custom_llm_prompts_limit": 10, "custom_llm_monthly_units_limit": 2400,
          "custom_llm_max_projects": 5}, (5, 10, 2400, 2379)),
        ({"plan": "enterprise", "custom_llm_monthly_units_limit": 10}, (None, None, 10, 0)),
        ({"plan": "enterprise", "custom_llm_prompts_limit": "15"}, (None, 15, None, None)),
        # COMPORTAMIENTO ACTUAL (posible defecto): aquí 0 es un tope real
        # (0 proyectos, 0 unidades), mientras que enterprise_limits trata 0
        # como "sin override" para los topes de proyectos.
        ({"plan": "enterprise", "custom_llm_max_projects": 0, "custom_llm_monthly_units_limit": 0}, (0, None, 0, 0)),
        # Los custom solo aplican a enterprise.
        ({"plan": "basic", "custom_llm_prompts_limit": 99, "custom_llm_monthly_units_limit": 9999,
          "custom_llm_max_projects": 9}, (1, 20, 640, 619)),
    ])
    def test_tabla(self, llm_db, extra, esperado):
        resumen = llm_monitoring_limits.get_llm_limits_summary({"id": 3, "role": "user", **extra})
        max_projects, max_prompts, max_units, remaining = esperado
        assert resumen == {
            "plan": extra.get("plan", "free"),
            "is_admin": False,
            "max_projects": max_projects,
            "max_prompts_per_project": max_prompts,
            "max_monthly_units": max_units,
            "monthly_units_used": 21,
            "monthly_units_remaining": remaining,
            "active_projects": 2,
            "allowed_llms": ["openai", "anthropic", "google", "perplexity"],
        }

    def test_admin_sin_limites(self, llm_db):
        resumen = llm_monitoring_limits.get_llm_limits_summary({"id": 3, "role": "admin", "plan": "free"})
        assert (resumen["is_admin"], resumen["max_projects"], resumen["max_prompts_per_project"],
                resumen["max_monthly_units"], resumen["monthly_units_remaining"]) == (True, None, None, None, None)
        assert (resumen["monthly_units_used"], resumen["active_projects"]) == (21, 2)

    def test_sin_usuario(self):
        assert llm_monitoring_limits.get_llm_limits_summary(None) == {
            "plan": "free", "is_admin": False, "max_projects": 0, "max_prompts_per_project": 0,
            "max_monthly_units": 0, "monthly_units_used": 0, "monthly_units_remaining": 0,
            "active_projects": 0, "allowed_llms": ["openai", "anthropic", "google", "perplexity"],
        }


# ===========================================================================
# 6. Límites por proyecto (project_quota) y topes Enterprise
# ===========================================================================

def _preparar_consumo_proyecto(db, module):
    """Proyecto de user 3 con 9 RU en la ventana [2026-09-01, 2026-10-01) y
    ruido que no debe contar. Devuelve el id del proyecto."""
    db.set_user(3, quota_reset_date=RESET_FIJO)
    source = project_quota.MODULES[module]["source"]
    pid = db.add_project(module, 3, name="Objetivo")
    otro = db.add_project(module, 3, name="Otro")
    db.add_event(3, 100, source, datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC), {"project_id": pid})  # fuera
    db.add_event(3, 4, source, datetime(2026, 9, 1, tzinfo=UTC), {"project_id": pid})                  # dentro
    db.add_event(3, 5, source, datetime(2026, 9, 30, 23, 59, 59, tzinfo=UTC), {"project_id": str(pid)})  # dentro (id en texto)
    db.add_event(3, 100, source, datetime(2026, 10, 1, tzinfo=UTC), {"project_id": pid})               # fuera
    db.add_event(3, 50, "serp_api", datetime(2026, 9, 10, tzinfo=UTC), {"project_id": pid})           # otra fuente
    db.add_event(3, 70, source, datetime(2026, 9, 10, tzinfo=UTC), {"project_id": otro})              # otro proyecto
    db.add_event(1, 30, source, datetime(2026, 9, 10, tzinfo=UTC), {"project_id": pid})               # otro usuario
    db.add_event(3, 20, source, datetime(2026, 9, 10, tzinfo=UTC), None)                              # sin proyecto
    return pid


def _preparar_consumo_llm(db):
    """Proyecto LLM de user 3 con 17 unidades en la ventana (7 + 10)."""
    db.set_user(3, quota_reset_date=RESET_FIJO)
    pid = db.add_project("llm_monitoring", 3, name="Objetivo")
    otro = db.add_project("llm_monitoring", 3, name="Otro")
    db.add_llm_result(pid, date(2026, 8, 31), "openai", 3)
    db.add_llm_result(pid, date(2026, 9, 1), "openai", 7)
    db.add_llm_result(pid, date(2026, 9, 30), "anthropic", 10)
    db.add_llm_result(pid, date(2026, 10, 1), "google", 3)
    db.add_llm_result(otro, date(2026, 9, 10), "openai", 100)
    return pid


class TestCuotaPorProyecto:
    # (limite, planned) -> (allowed, remaining); consumo en ventana = 9
    CASOS_RU = [
        (None, 1, (True, None)),
        (None, 10_000, (True, None)),
        (10, 0, (True, 1)),
        (10, 1, (True, 1)),
        (10, 2, (False, 1)),
        (9, 0, (True, 0)),
        (9, 1, (False, 0)),
        # Un 0 guardado a mano en BD es un tope real (el admin no deja ponerlo).
        (0, 0, (False, 0)),
    ]

    @pytest.mark.parametrize("module", ["manual_ai", "ai_mode"])
    @pytest.mark.parametrize("limite,planned,esperado", CASOS_RU)
    def test_ru(self, db, module, limite, planned, esperado):
        pid = _preparar_consumo_proyecto(db, module)
        db.exec(f"UPDATE {project_quota.MODULES[module]['table']} SET monthly_ru_limit = %s WHERE id = %s", (limite, pid))
        estado = project_quota.check_project_quota(module, pid, 3, planned=planned)
        assert estado == {
            "module": module, "project_id": pid, "limit": limite, "used": 9,
            "remaining": esperado[1], "window_start": "2026-09-01", "window_end": "2026-10-01",
            "planned": planned, "allowed": esperado[0],
        }
        assert project_quota.get_project_usage(module, pid, 3) == 9

    @pytest.mark.parametrize("limite,planned,esperado", [
        (None, 100, (True, None)),
        (20, 3, (True, 3)),
        (20, 4, (False, 3)),
        (17, 0, (True, 0)),
    ])
    def test_llm(self, db, limite, planned, esperado):
        pid = _preparar_consumo_llm(db)
        db.exec("UPDATE llm_monitoring_projects SET monthly_units_limit = %s WHERE id = %s", (limite, pid))
        estado = project_quota.check_project_quota("llm_monitoring", pid, 3, planned=planned)
        assert (estado["used"], estado["allowed"], estado["remaining"]) == (17, *esperado)

    def test_llm_sin_columna_migrada_cuenta_filas(self, db, monkeypatch):
        pid = _preparar_consumo_llm(db)
        monkeypatch.setattr(llm_monitoring_limits.UNITS_SCHEMA, "available", lambda _get: False)
        assert project_quota.get_project_usage("llm_monitoring", pid, 3) == 2

    def test_llm_no_filtra_por_usuario(self, db):
        # El consumo LLM del proyecto solo filtra por project_id; la ventana sale
        # del user_id pasado aunque no sea el dueño.
        pid = _preparar_consumo_llm(db)
        db.set_user(1, quota_reset_date=RESET_FIJO)
        assert project_quota.get_project_usage("llm_monitoring", pid, 1) == 17

    def test_proyecto_inexistente_sin_tope(self, db):
        db.set_user(3, quota_reset_date=RESET_FIJO)
        estado = project_quota.check_project_quota("manual_ai", 999, 3, planned=5)
        assert (estado["limit"], estado["used"], estado["remaining"], estado["allowed"]) == (None, 0, None, True)

    def test_sin_conexion_fail_open(self, monkeypatch):
        monkeypatch.setattr(project_quota, "get_db_connection", _sin_conexion)
        assert project_quota.check_project_quota("ai_mode", 1, 3, planned=50) == {
            "module": "ai_mode", "project_id": 1, "limit": None, "used": 0, "remaining": None,
            "window_start": None, "window_end": None, "planned": 50, "allowed": True,
        }
        assert project_quota.get_project_usage("ai_mode", 1, 3) == 0

    def test_error_de_bd_fail_open_con_rollback(self, monkeypatch):
        conn = _conexion_que_falla(psycopg2.OperationalError("caída"))
        monkeypatch.setattr(project_quota, "get_db_connection", lambda: conn)
        estado = project_quota.check_project_quota("manual_ai", 1, 3, planned=1)
        assert (estado["limit"], estado["allowed"]) == (None, True)
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    @pytest.mark.parametrize("funcion", [
        lambda: project_quota.check_project_quota("aio", 1, 3),
        lambda: project_quota.pause_project_for_quota("aio", 1, None),
        lambda: project_quota.set_project_limits("aio", 1, monthly_limit=5),
    ])
    def test_modulo_desconocido(self, funcion):
        with pytest.raises(ValueError, match="Módulo desconocido: aio"):
            funcion()


class TestPausaDeProyecto:
    @pytest.mark.parametrize("module", ["manual_ai", "ai_mode", "llm_monitoring"])
    def test_pausa_solo_ese_proyecto(self, db, module):
        pid = db.add_project(module, 3, name="Objetivo")
        otro = db.add_project(module, 3, name="Otro")
        assert project_quota.pause_project_for_quota(module, pid, RESET_FIJO) is True
        p = db.project(module, pid)
        assert (p["is_paused_by_quota"], p["paused_until"], p["paused_reason"]) == (True, RESET_FIJO, "project_quota_exceeded")
        assert db.project(module, otro)["is_paused_by_quota"] is False

    def test_paused_until_none_usa_30_dias(self, db):
        pid = db.add_project("manual_ai", 3)
        assert project_quota.pause_project_for_quota("manual_ai", pid, None) is True
        faltan = db.one("SELECT paused_until - NOW() AS d FROM manual_ai_projects WHERE id = %s", (pid,))["d"]
        assert timedelta(days=30) - timedelta(minutes=2) <= faltan <= timedelta(days=30) + timedelta(minutes=2)

    def test_pausa_proyecto_inactivo_e_inexistente(self, db):
        # A diferencia de la pausa por usuario, no filtra is_active; y devuelve
        # True aunque el proyecto no exista.
        pid = db.add_project("ai_mode", 3, is_active=False)
        assert project_quota.pause_project_for_quota("ai_mode", pid, RESET_FIJO, reason="otra") is True
        assert db.project("ai_mode", pid)["paused_reason"] == "otra"
        assert project_quota.pause_project_for_quota("ai_mode", 999, RESET_FIJO) is True


class TestAjusteDeLimitesDeProyecto:
    @pytest.mark.parametrize("kwargs,limite,frecuencia", [
        ({"monthly_limit": 5}, 5, 1),
        ({"monthly_limit": "7"}, 7, 1),
        ({"monthly_limit": 2.9}, 2, 1),  # int() trunca
        ({"monthly_limit": None}, None, 1),
        ({"monthly_limit": ""}, None, 1),
        ({"analysis_frequency_days": 3}, None, 3),
        ({"analysis_frequency_days": None}, None, 1),
        ({"monthly_limit": 50, "analysis_frequency_days": "2"}, 50, 2),
    ])
    @pytest.mark.parametrize("module", ["manual_ai", "llm_monitoring"])
    def test_valores_validos(self, db, module, kwargs, limite, frecuencia):
        pid = db.add_project(module, 3, name="P")
        res = project_quota.set_project_limits(module, pid, **kwargs)
        assert res == {
            "success": True, "module": module, "project_id": pid, "user_id": 3, "name": "P",
            "monthly_limit": limite, "analysis_frequency_days": frecuencia, "resumed": False,
        }
        col = project_quota.MODULES[module]["limit_col"]
        p = db.project(module, pid)
        assert (p[col], p["analysis_frequency_days"]) == (limite, frecuencia)

    @pytest.mark.parametrize("kwargs,mensaje", [
        ({"monthly_limit": 0}, "Monthly limit must be >= 1"),
        ({"monthly_limit": -3}, "Monthly limit must be >= 1"),
        ({"monthly_limit": "abc"}, "Monthly limit must be a valid number"),
        ({"monthly_limit": "2.5"}, "Monthly limit must be a valid number"),
        ({"analysis_frequency_days": 0}, "Analysis frequency must be >= 1"),
    ])
    def test_valores_invalidos_lanzan(self, db, kwargs, mensaje):
        # Lanza ValueError (no devuelve un dict de error).
        pid = db.add_project("ai_mode", 3)
        with pytest.raises(ValueError, match=mensaje):
            project_quota.set_project_limits("ai_mode", pid, **kwargs)

    def test_nada_que_actualizar_y_proyecto_inexistente(self, db):
        assert project_quota.set_project_limits("ai_mode", 1) == {"success": False, "error": "Nothing to update"}
        assert project_quota.set_project_limits("ai_mode", 999, monthly_limit=5) == {
            "success": False, "error": "Project not found"}

    # Proyecto con 9 RU consumidos en la ventana y pausado.
    @pytest.mark.parametrize("motivo,kwargs,limite_previo,reanuda", [
        ("project_quota_exceeded", {"monthly_limit": 10}, 5, True),
        ("project_quota_exceeded", {"monthly_limit": 9}, 5, False),   # 9 < 9 es False
        ("project_quota_exceeded", {"monthly_limit": None}, 5, True),
        ("project_quota_exceeded", {"analysis_frequency_days": 2}, 5, False),
        # Cambiar solo la frecuencia de un proyecto sin tope también lo reanuda.
        ("project_quota_exceeded", {"analysis_frequency_days": 2}, None, True),
        # La pausa por cuota de usuario no se toca desde aquí.
        ("quota_exceeded", {"monthly_limit": None}, 5, False),
    ])
    def test_reanudacion(self, db, motivo, kwargs, limite_previo, reanuda):
        pid = _preparar_consumo_proyecto(db, "manual_ai")
        db.exec("""UPDATE manual_ai_projects SET monthly_ru_limit = %s, is_paused_by_quota = TRUE,
                   paused_until = %s, paused_at = NOW(), paused_reason = %s WHERE id = %s""",
                (limite_previo, RESET_FIJO, motivo, pid))
        res = project_quota.set_project_limits("manual_ai", pid, **kwargs)
        assert res["resumed"] is reanuda
        p = db.project("manual_ai", pid)
        if reanuda:
            assert (p["is_paused_by_quota"], p["paused_until"], p["paused_at"], p["paused_reason"]) == (False, None, None, None)
        else:
            assert (p["is_paused_by_quota"], p["paused_reason"]) == (True, motivo)

    def test_reanudacion_llm(self, db):
        pid = _preparar_consumo_llm(db)
        db.exec("""UPDATE llm_monitoring_projects SET monthly_units_limit = 10, is_paused_by_quota = TRUE,
                   paused_reason = 'project_quota_exceeded' WHERE id = %s""", (pid,))
        assert project_quota.set_project_limits("llm_monitoring", pid, monthly_limit=17)["resumed"] is False
        assert project_quota.set_project_limits("llm_monitoring", pid, monthly_limit=18)["resumed"] is True


class TestListadoDeProyectosConLimites:
    def test_listado(self, db):
        pid = _preparar_consumo_proyecto(db, "manual_ai")
        db.exec("UPDATE manual_ai_projects SET monthly_ru_limit = 10, analysis_frequency_days = NULL, "
                "is_paused_by_quota = TRUE, paused_until = %s, paused_reason = 'project_quota_exceeded' "
                "WHERE id = %s", (RESET_FIJO, pid))
        for i, activa in enumerate([True, True, None, False]):
            db.exec("INSERT INTO manual_ai_keywords (project_id, keyword, is_active) VALUES (%s, %s, %s)",
                    (pid, f"kw {i}", activa))
        llm = db.add_project("llm_monitoring", 3, name="LLM", monthly_units_limit=5)
        db.add_project("ai_mode", 1, name="Ajeno")

        out = project_quota.list_user_projects_with_limits(3)
        assert out["user_id"] == 3
        assert out["window"] == {"start": "2026-09-01", "end": "2026-10-01"}
        assert list(out["modules"]) == ["manual_ai", "ai_mode", "llm_monitoring"]
        assert {m: len(v["projects"]) for m, v in out["modules"].items()} == {"manual_ai": 2, "ai_mode": 0, "llm_monitoring": 1}

        objetivo = out["modules"]["manual_ai"]["projects"][0]
        assert objetivo == {
            "id": pid, "name": "Objetivo", "is_active": True, "is_paused_by_quota": True,
            "paused_until": RESET_FIJO.isoformat(), "paused_reason": "project_quota_exceeded",
            "analysis_frequency_days": 1, "monthly_limit": 10,
            "keyword_count": 3,  # is_active NULL cuenta como activa
            "used": 9, "remaining": 1, "unit": "RU",
        }
        fila_llm = out["modules"]["llm_monitoring"]["projects"][0]
        assert (fila_llm["id"], fila_llm["search_mode"], fila_llm["search_enabled_at"], fila_llm["unit"],
                fila_llm["used"], fila_llm["remaining"]) == (llm, "off", None, "units", 0, 5)

    def test_sin_conexion(self, monkeypatch):
        monkeypatch.setattr(project_quota, "get_db_connection", _sin_conexion)
        assert project_quota.list_user_projects_with_limits(3) == {"user_id": 3, "window": None, "modules": {}}


# ---------------------------------------------------------------------------
# Topes Enterprise por módulo (resolución pura)
# ---------------------------------------------------------------------------

MODULOS = [enterprise_limits.MODULE_MANUAL_AI, enterprise_limits.MODULE_AI_MODE, enterprise_limits.MODULE_LLM]
COL_PROYECTOS = {
    "manual_ai": "custom_manual_ai_max_projects",
    "ai_mode": "custom_ai_mode_max_projects",
    "llm_monitoring": "custom_llm_max_projects",
}
COL_KEYWORDS = {
    "manual_ai": "custom_manual_ai_keywords_limit",
    "ai_mode": "custom_ai_mode_keywords_limit",
    "llm_monitoring": "custom_llm_prompts_limit",
}


class TestTopesEnterprise:
    def test_columnas(self):
        assert enterprise_limits.ENTERPRISE_LIMIT_COLUMNS == sorted(
            set(COL_PROYECTOS.values()) | set(COL_KEYWORDS.values()))

    @pytest.mark.parametrize("module", MODULOS)
    @pytest.mark.parametrize("plan,role,valor,esperado", [
        ("enterprise", "user", None, None),
        ("enterprise", "user", 5, 5),
        ("enterprise", "user", "4", 4),
        ("enterprise", "user", 3.7, 3),    # int() trunca
        ("enterprise", "user", 1, 1),
        ("enterprise", "user", 0, None),   # 0 = sin override
        ("enterprise", "user", -2, None),
        ("enterprise", "user", "x", None),
        ("enterprise", "user", "2.5", None),
        ("enterprise", "admin", 5, None),  # admin nunca limitado
        ("enterprise", None, 5, 5),
        ("business", "user", 5, None),     # solo enterprise
        ("basic", "user", 5, None),
        ("free", "user", 5, None),
        (None, "user", 5, None),
    ])
    def test_max_proyectos(self, module, plan, role, valor, esperado):
        user = {"id": 1, "plan": plan, "role": role, COL_PROYECTOS[module]: valor}
        assert enterprise_limits.get_custom_max_projects(user, module) == esperado

    def test_max_proyectos_modulo_desconocido_y_sin_usuario(self):
        user = {"plan": "enterprise", "custom_manual_ai_max_projects": 5}
        assert enterprise_limits.get_custom_max_projects(user, "aio") is None
        assert enterprise_limits.get_custom_max_projects(None, "manual_ai") is None
        assert enterprise_limits.get_custom_max_projects({}, "manual_ai") is None

    @pytest.mark.parametrize("module,global_limit", [("manual_ai", 200), ("ai_mode", 300), ("llm_monitoring", 60)])
    @pytest.mark.parametrize("plan,role,valor,esperado", [
        ("enterprise", "user", None, "global"),
        ("enterprise", "user", 30, 30),
        ("enterprise", "user", 10_000, "global"),  # nunca supera el global
        ("enterprise", "user", 0, "global"),
        ("enterprise", "user", "x", "global"),
        ("enterprise", "admin", 30, "global"),
        ("premium", "user", 30, "global"),
    ])
    def test_keywords(self, module, global_limit, plan, role, valor, esperado):
        user = {"plan": plan, "role": role, COL_KEYWORDS[module]: valor}
        resultado = enterprise_limits.get_effective_keywords_limit(user, module, global_limit)
        assert resultado == (global_limit if esperado == "global" else esperado)

    def test_keywords_global_en_texto_y_modulo_desconocido(self):
        user = {"plan": "enterprise", "custom_manual_ai_keywords_limit": 30}
        assert enterprise_limits.get_effective_keywords_limit(user, "manual_ai", "200") == 30
        assert enterprise_limits.get_effective_keywords_limit(user, "aio", "200") == 200
        assert enterprise_limits.get_effective_keywords_limit(None, "manual_ai", 200) == 200

    @pytest.mark.parametrize("module", MODULOS)
    @pytest.mark.parametrize("tope,activos,bloquea", [
        (None, 10_000, False),
        (5, 0, False),
        (5, 4, False),
        (5, 5, True),
        (5, 6, True),
        (1, 1, True),
        (5, "5", True),
    ])
    def test_tope_de_proyectos(self, module, tope, activos, bloquea):
        user = {"plan": "enterprise", "role": "user", COL_PROYECTOS[module]: tope}
        err = enterprise_limits.check_project_cap(user, module, activos)
        if not bloquea:
            assert err is None
        else:
            assert err == {
                "success": False,
                "error": "project_limit_reached",
                "message": (
                    f"You have reached the maximum number of active projects for your plan "
                    f"({activos}/{tope}). Pause or delete a project to add another, "
                    f"or contact support to extend your limit."
                ),
                "current_plan": "enterprise",
                "limit": tope,
                "current": int(activos),
                "action_required": "contact_support",
            }

    def test_tope_no_aplica_a_admin_ni_a_otros_planes(self):
        for user in ({"plan": "enterprise", "role": "admin", "custom_ai_mode_max_projects": 1},
                     {"plan": "business", "custom_ai_mode_max_projects": 1},
                     None):
            assert enterprise_limits.check_project_cap(user, "ai_mode", 50) is None

    @pytest.mark.parametrize("user,esperado", [
        ({"plan": "enterprise", "custom_manual_ai_max_projects": 5, "custom_manual_ai_keywords_limit": 30},
         {"max_projects": 5, "active_projects": 3, "max_keywords_per_project": 30, "is_enterprise": True}),
        ({"plan": "enterprise"},
         {"max_projects": None, "active_projects": 3, "max_keywords_per_project": 200, "is_enterprise": True}),
        ({"plan": "enterprise", "role": "admin", "custom_manual_ai_max_projects": 5},
         {"max_projects": None, "active_projects": 3, "max_keywords_per_project": 200, "is_enterprise": True}),
        ({"plan": "premium", "custom_manual_ai_max_projects": 5},
         {"max_projects": None, "active_projects": 3, "max_keywords_per_project": 200, "is_enterprise": False}),
        (None, {"max_projects": None, "active_projects": 3, "max_keywords_per_project": 200, "is_enterprise": False}),
    ])
    def test_resumen(self, user, esperado):
        assert enterprise_limits.get_module_limits_summary(user, "manual_ai", "3", 200) == esperado
