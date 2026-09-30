"""
Tests de CARACTERIZACIÓN del reset diario de cuotas y de los endpoints de cron.

Fijan el comportamiento ACTUAL (con sus defectos) para que una refactorización
posterior no lo cambie sin que nadie se entere. No arreglan nada: donde el
comportamiento parece un defecto se marca con
"# COMPORTAMIENTO ACTUAL (posible defecto): ...".

Qué cubren:
1. daily_quota_reset_cron.main(): qué usuarios se resetean, qué campos cambian
   (quota_used, quota_reset_date, periodo, pausas) y qué no se toca, con
   stripe.Subscription.retrieve simulado. Se ejecuta directamente y vía
   POST /api/cron/quota-reset (síncrono y asíncrono).
2. Endpoints que llaman las funciones Bun de Railway:
     POST /api/cron/quota-reset
     POST /api/llm-monitoring/cron/daily-analysis
     POST /api/llm-monitoring/cron/watchdog
     POST /api/llm-monitoring/cron/model-discovery
     POST /manual-ai/api/cron/daily-analysis
     POST /ai-mode-projects/api/cron/daily-analysis
   Sin token, token incorrecto, token correcto, usuario sin permisos y admin
   con sesión. Lock de análisis LLM (409), advisory lock de Manual AI / AI Mode
   y watchdog con un run colgado.
3. Comparación del token: prefijos, largos distintos, mayúsculas, espacios,
   otras cabeceras y query string.

Aislamiento:
- Solo la base desechable de Docker (fixtures clean_db / flask_app).
- Ningún análisis real: threading se sustituye en cada módulo de rutas por un
  hilo falso que registra el objetivo y sus argumentos sin arrancarlo. Al final
  de cada test se comprueba que no queda ningún hilo nuevo vivo.
- Correo: email_service.send_email y los avisos de cron_alerts se capturan.
- Stripe: stripe.Subscription.retrieve se sustituye por un doble.
- El reloj del cron de cuotas se congela (datetime del módulo) en un instante
  T0 real, así que las fechas esperadas son exactas y relativas a T0.

Ejecutar:
    TEST_RUN_ID=crons scripts/run_tests_docker.sh -q tests/test_char_quota_reset_and_crons.py
"""

import importlib
import threading
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from tests.conftest import seed_users

TOKEN = "test-cron-token"  # CRON_TOKEN de tests/docker/test.env
DESTINO_POR_DEFECTO = "info@soycarlosgonzalez.com"

# Cabeceras que mandan las funciones Bun (*_function.js de la raíz).
CABECERAS_BUN = {"Content-Type": "application/json", "Accept": "application/json"}

URL_QUOTA_RESET = "/api/cron/quota-reset"
URL_HEALTH = "/api/cron/quota-health-check"
URL_LLM_DAILY = "/api/llm-monitoring/cron/daily-analysis"
URL_WATCHDOG = "/api/llm-monitoring/cron/watchdog"
URL_DISCOVERY = "/api/llm-monitoring/cron/model-discovery"
URL_MANUAL_AI = "/manual-ai/api/cron/daily-analysis"
URL_AI_MODE = "/ai-mode-projects/api/cron/daily-analysis"

# Cómo llama cada función Bun (URL con query incluida).
LLAMADAS_BUN = {
    "quota-reset": URL_QUOTA_RESET + "?async=1&triggered_by=bun_cron",
    "llm-daily": URL_LLM_DAILY + "?async=1",
    "llm-watchdog": URL_WATCHDOG,
    "llm-model-discovery": URL_DISCOVERY + "?notify_email=info%40soycarlosgonzalez.com&auto_update=false",
    "manual-ai": URL_MANUAL_AI + "?async=1",
    "ai-mode": URL_AI_MODE + "?async=1",
}

# Código con el que acepta cada endpoint un token válido (con los análisis parcheados).
CODIGO_ACEPTADO = {
    "quota-reset": 202,
    "llm-daily": 202,
    "llm-watchdog": 200,
    "llm-model-discovery": 200,
    "manual-ai": 202,
    "ai-mode": 202,
}

# Respuesta a un visitante sin credencial válida (con las cabeceras de Bun).
RECHAZO_ANONIMO = {
    "quota-reset": (403, {"success": False, "error": "forbidden",
                          "message": "Valid CRON_TOKEN bearer token required"}),
    "llm-daily": (401, {"error": "Authentication required", "auth_required": True}),
    "llm-watchdog": (401, {"error": "Authentication required", "auth_required": True}),
    "llm-model-discovery": (401, {"error": "Authentication required", "auth_required": True}),
    "manual-ai": (401, {"error": "Authentication required", "auth_required": True}),
    "ai-mode": (401, {"error": "Authentication required", "auth_required": True}),
}

# Respuesta a un usuario autenticado que no es admin (gratuito o de pago).
RECHAZO_NO_ADMIN = {
    "quota-reset": (403, {"success": False, "error": "forbidden",
                          "message": "Valid CRON_TOKEN bearer token required"}),
    "llm-daily": (403, {"success": False, "error": "forbidden",
                        "message": "Se requiere token de cron o rol admin"}),
    "llm-watchdog": (403, {"success": False, "error": "forbidden",
                           "message": "Se requiere token de cron o rol admin"}),
    "llm-model-discovery": (403, {"success": False, "error": "forbidden",
                                  "message": "Se requiere token de cron o rol admin"}),
    "manual-ai": (403, {"error": "Admin privileges required", "admin_required": True}),
    "ai-mode": (403, {"error": "Admin privileges required", "admin_required": True}),
}


# ---------------------------------------------------------------------------
# Utilidades de base de datos (conexión directa a la base desechable)
# ---------------------------------------------------------------------------

def _conectar(db_url):
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(db_url, connect_timeout=5, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    return conn


def _sql(db_url, sql, params=()):
    conn = _conectar(db_url)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()] if cur.description else []
    finally:
        conn.close()


def _insertar_usuario(db_url, email, **campos):
    campos.setdefault("name", email.split("@")[0])
    campos.setdefault("role", "user")
    campos.setdefault("is_active", True)
    columnas = ["email"] + list(campos)
    valores = [email] + list(campos.values())
    fila = _sql(
        db_url,
        f"INSERT INTO users ({', '.join(columnas)}) VALUES ({', '.join(['%s'] * len(columnas))}) RETURNING id",
        valores,
    )
    return fila[0]["id"]


COLUMNAS_USUARIO = (
    "plan", "billing_status", "quota_limit", "quota_used", "quota_reset_date",
    "subscription_id", "stripe_customer_id", "current_period_start", "current_period_end",
    "custom_quota_limit", "custom_quota_notes",
    "ai_overview_paused_until", "ai_overview_paused_at", "ai_overview_paused_reason",
)


def _estado_usuarios(db_url):
    filas = _sql(db_url, f"SELECT id, {', '.join(COLUMNAS_USUARIO)} FROM users ORDER BY id")
    return {f["id"]: {c: f[c] for c in COLUMNAS_USUARIO} for f in filas}


TABLAS_PROYECTO = ("manual_ai_projects", "ai_mode_projects", "llm_monitoring_projects")


def _crear_proyectos_pausados(db_url, user_id, T0):
    """Un proyecto por módulo, pausado por cuota hasta T0 + 10 días."""
    pausa = (True, T0 + timedelta(days=10), T0 - timedelta(days=1), "quota_exceeded")
    _sql(db_url, """
        INSERT INTO manual_ai_projects (user_id, name, domain, is_paused_by_quota, paused_until, paused_at, paused_reason)
        VALUES (%s, 'Proyecto AIO', 'ejemplo.invalid', %s, %s, %s, %s)
    """, (user_id,) + pausa)
    _sql(db_url, """
        INSERT INTO ai_mode_projects (user_id, name, brand_name, is_paused_by_quota, paused_until, paused_at, paused_reason)
        VALUES (%s, 'Proyecto AI Mode', 'Marca', %s, %s, %s, %s)
    """, (user_id,) + pausa)
    _sql(db_url, """
        INSERT INTO llm_monitoring_projects (user_id, name, brand_name, industry, is_paused_by_quota, paused_until, paused_at, paused_reason)
        VALUES (%s, 'Proyecto LLM', 'Marca', 'Pruebas', %s, %s, %s, %s)
    """, (user_id,) + pausa)
    return pausa


def _pausas_proyectos(db_url, user_id):
    resultado = {}
    for tabla in TABLAS_PROYECTO:
        fila = _sql(db_url, f"""
            SELECT is_paused_by_quota, paused_until, paused_at, paused_reason
            FROM {tabla} WHERE user_id = %s
        """, (user_id,))[0]
        resultado[tabla] = (fila["is_paused_by_quota"], fila["paused_until"], fila["paused_at"], fila["paused_reason"])
    return resultado


def _runs(db_url):
    return _sql(db_url, """
        SELECT id, status, triggered_by, started_at, completed_at, total_projects,
               successful_projects, failed_projects, total_queries, error_message, project_results
        FROM llm_monitoring_analysis_runs ORDER BY id
    """)


def _lock(db_url):
    filas = _sql(db_url, "SELECT is_running, started_at, started_by FROM llm_monitoring_analysis_lock WHERE id = 1")
    return filas[0] if filas else None


def _sembrar_lock_llm(db_url, minutos_atras, started_by="cron", con_started_at=True):
    """Deja el lock de LLM Monitoring tomado y un run 'running' como lo dejaría un cron en curso.
    Usa datetime.now() naive, el mismo reloj con el que acquire_analysis_lock mide la antigüedad."""
    inicio = datetime.now() - timedelta(minutes=minutos_atras)
    _sql(db_url, """
        INSERT INTO llm_monitoring_analysis_lock (id, is_running, started_at, started_by)
        VALUES (1, TRUE, %s, %s)
        ON CONFLICT (id) DO UPDATE SET is_running = TRUE, started_at = EXCLUDED.started_at,
                                       started_by = EXCLUDED.started_by
    """, (inicio if con_started_at else None, started_by))
    return _sql(db_url, """
        INSERT INTO llm_monitoring_analysis_runs (status, triggered_by, started_at)
        VALUES ('running', %s, %s) RETURNING id
    """, (started_by, inicio))[0]["id"]


def _sembrar_run(db_url, status, horas_inicio, horas_fin=None, **extra):
    """Run con fechas naive en UTC (el watchdog compara con datetime.utcnow())."""
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    inicio = ahora - timedelta(hours=horas_inicio)
    fin = ahora - timedelta(hours=horas_fin) if horas_fin is not None else None
    return _sql(db_url, """
        INSERT INTO llm_monitoring_analysis_runs
            (status, triggered_by, started_at, completed_at, total_projects, successful_projects, failed_projects)
        VALUES (%s, 'cron', %s, %s, %s, %s, %s) RETURNING id
    """, (status, inicio, fin, extra.get("total", 3), extra.get("ok", 3), extra.get("ko", 0)))[0]["id"]


# ---------------------------------------------------------------------------
# Dobles: hilos, correo, avisos
# ---------------------------------------------------------------------------

class _RegistroHilos:
    """Sustituye al módulo threading dentro de cada módulo de rutas.
    Registra cada Thread creado (objetivo, argumentos, daemon, nombre) y start()
    no arranca nada."""

    def __init__(self):
        self.creados = []

    def modulo_falso(self):
        registro = self.creados

        class HiloFalso:
            def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
                self.target = target
                self.name = name
                self.args = tuple(args)
                self.kwargs = dict(kwargs or {})
                self.daemon = daemon
                self.arrancado = False
                registro.append(self)

            def start(self):
                self.arrancado = True

        return SimpleNamespace(Thread=HiloFalso)


@pytest.fixture
def entorno(flask_app, clean_db, monkeypatch):
    """Base vacía con los usuarios semilla (1 gratuito, 2 admin, 3 pago business),
    variables fijadas, hilos/correo/avisos capturados y el análisis LLM global parcheado."""
    import cron_alerts
    import cron_routes
    import email_service
    import llm_monitoring_routes
    import llm_monitoring_rutas_cron  # crons de LLM Monitoring desde sep-2026
    import llm_monitoring_rutas_analisis  # primer análisis y contenido de URLs desde sep-2026

    manual_ai_routes = importlib.import_module("manual_ai.routes.analysis")
    ai_mode_routes = importlib.import_module("ai_mode_projects.routes.analysis")

    monkeypatch.setenv("CRON_TOKEN", TOKEN)
    monkeypatch.setenv("CRON_ALERTS_ENABLED", "true")
    for var in (
        "CRON_SECRET", "CRON_ALERTS_EMAIL", "CRON_ALERT_EMAIL", "MODEL_DISCOVERY_EMAIL",
        "APP_ENV", "RAILWAY_ENVIRONMENT_NAME", "LLM_WATCHDOG_MAX_HOURS",
        "QUOTA_RESET_INTERVAL_DAYS", "CRON_STALENESS_MAX_DAYS",
        "OPENAI_API_KEY", "GOOGLE_AI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    hilos = _RegistroHilos()
    # Las rutas de LLM que lanzan hilos viven en rutas_cron y rutas_analisis desde sep-2026;
    # llm_monitoring_routes ya no importa threading.
    for modulo in (cron_routes, llm_monitoring_rutas_cron, llm_monitoring_rutas_analisis,
                   manual_ai_routes, ai_mode_routes):
        monkeypatch.setattr(modulo, "threading", hilos.modulo_falso())

    correos = []

    def enviar_correo(to_email, subject, html_body, text_body=None):
        correos.append({"to": to_email, "subject": subject})
        return True

    monkeypatch.setattr(email_service, "send_email", enviar_correo)

    avisos_run = []

    def aviso_run(run_id, get_db_connection_fn=None):
        avisos_run.append(run_id)
        return {"severity": "ok", "email_sent": False, "alerts": []}

    monkeypatch.setattr(cron_alerts, "send_run_completion_email", aviso_run)
    avisos_simples = []
    monkeypatch.setattr(
        cron_alerts, "send_simple_run_completion_email",
        lambda etiqueta, stats: avisos_simples.append((etiqueta, stats)) or {},
    )

    llamadas_analisis_llm = []
    resultados_llm = {"valor": []}

    def analizar_todo(api_keys=None, max_workers=10):
        llamadas_analisis_llm.append({"api_keys": api_keys, "max_workers": max_workers})
        valor = resultados_llm["valor"]
        if isinstance(valor, Exception):
            raise valor
        return valor

    monkeypatch.setattr(llm_monitoring_rutas_cron, "analyze_all_active_projects", analizar_todo)

    gratuito, admin, pago = seed_users()
    hilos_previos = set(threading.enumerate())

    yield SimpleNamespace(
        app=flask_app.app,
        db=clean_db,
        hilos=hilos.creados,
        correos=correos,
        avisos_run=avisos_run,
        avisos_simples=avisos_simples,
        llamadas_analisis_llm=llamadas_analisis_llm,
        resultados_llm=resultados_llm,
        gratuito=gratuito,
        admin=admin,
        pago=pago,
        manual_ai_routes=manual_ai_routes,
        ai_mode_routes=ai_mode_routes,
    )

    nuevos = [t for t in threading.enumerate() if t not in hilos_previos and t.is_alive()]
    assert not nuevos, f"Quedan hilos vivos tras el test: {nuevos}"


def _cliente(app, usuario=None):
    cliente = app.test_client()
    if usuario:
        with cliente.session_transaction() as sesion:
            sesion["user_id"] = usuario["id"]
            sesion["user_email"] = usuario["email"]
            sesion["user_name"] = usuario["name"]
            sesion["last_activity"] = datetime.now().isoformat()
    return cliente


def _post(ent, url, usuario=None, autorizacion=None, cabeceras_extra=None, json_body=None, metodo="POST"):
    cabeceras = dict(CABECERAS_BUN)
    if autorizacion is not None:
        cabeceras["Authorization"] = autorizacion
    if cabeceras_extra:
        cabeceras.update(cabeceras_extra)
    kwargs = {"headers": cabeceras}
    if json_body is not None:
        kwargs["json"] = json_body
    return _cliente(ent.app, usuario).open(url, method=metodo, **kwargs)


def _bearer(token=TOKEN):
    return f"Bearer {token}"


# ---------------------------------------------------------------------------
# 1. Reset diario de cuotas
# ---------------------------------------------------------------------------

def _escenarios_reset(T0):
    """Usuarios sembrados para el reset. Cada entrada:
    (clave, campos de users, respuesta simulada de Stripe o None, cambios esperados o None).
    None en cambios = el cron no toca la fila."""
    d = lambda dias: T0 + timedelta(days=dias)  # noqa: E731
    ts = lambda dias: int(d(dias).timestamp())  # noqa: E731

    pausa_vencida = {"ai_overview_paused_until": d(-1), "ai_overview_paused_at": d(-20),
                     "ai_overview_paused_reason": "quota_exceeded"}
    pausa_vigente = {"ai_overview_paused_until": d(5), "ai_overview_paused_at": d(-2),
                     "ai_overview_paused_reason": "quota_exceeded"}

    def reset(fecha, **otros):
        cambios = {"quota_used": 0, "quota_reset_date": fecha, "ai_overview_paused_until": None,
                   "ai_overview_paused_at": None, "ai_overview_paused_reason": None}
        cambios.update(otros)
        return cambios

    return [
        # Gratuitos: el cron solo mira plan != 'free', nunca los resetea.
        ("free_vencido", dict(plan="free", billing_status="active", quota_limit=0, quota_used=7,
                              quota_reset_date=d(-2), **pausa_vencida), None, None),
        ("free_no_vencido", dict(plan="free", billing_status="active", quota_limit=0, quota_used=3,
                                 quota_reset_date=d(5)), None, None),
        # Pago mensual con periodo Stripe vigente cacheado en BD: se resetea y la
        # próxima fecha se recorta a current_period_end. Desde el 2026-09-28 se
        # consulta el estado en Stripe (active => sigue igual).
        ("mensual_periodo_vigente", dict(plan="basic", billing_status="active", quota_limit=1225,
                                         quota_used=1225, quota_reset_date=d(-1),
                                         current_period_start=d(-20), current_period_end=d(10),
                                         subscription_id="sub_mensual", stripe_customer_id="cus_mensual",
                                         **pausa_vigente),
         {"id": "sub_mensual", "status": "active", "current_period_end": ts(10)}, reset(d(10))),
        # Anual a mitad de periodo (caso user 665719): reset mensual, +30 días desde el último.
        ("anual_mitad_periodo", dict(plan="premium", billing_status="active", quota_limit=2950,
                                     quota_used=2950, quota_reset_date=d(-2),
                                     current_period_start=d(-100), current_period_end=d(265),
                                     subscription_id="sub_anual", **pausa_vencida),
         {"id": "sub_anual", "status": "active", "current_period_end": ts(265)}, reset(d(28))),
        # Periodo en BD ya vencido: se ignora el periodo (no hay recorte). Stripe se
        # consulta solo por el estado (active => reset como siempre).
        ("periodo_vencido_en_bd", dict(plan="business", billing_status="active", quota_limit=15000,
                                       quota_used=100, quota_reset_date=d(-3),
                                       current_period_start=d(-33), current_period_end=d(-3),
                                       subscription_id="sub_vencido"),
         {"id": "sub_vencido", "status": "active", "current_period_end": ts(27)}, reset(d(27))),
        # Muy atrasado (45 días): un solo reset, la fecha avanza de 30 en 30 hasta el futuro.
        ("muy_atrasado", dict(plan="basic", billing_status="active", quota_limit=1225, quota_used=50,
                              quota_reset_date=d(-45)),
         None, reset(d(15))),
        ("trialing", dict(plan="basic", billing_status="trialing", quota_limit=1225, quota_used=10,
                          quota_reset_date=d(-3)),
         None, reset(d(27))),
        # Sin Stripe y sin fecha: base = ahora, +30 días.
        ("beta_sin_stripe", dict(plan="premium", billing_status="beta", quota_limit=2950, quota_used=20),
         None, reset(d(30))),
        # Enterprise con cuota personalizada: se resetea igual; custom_quota_* no se toca.
        ("enterprise_custom", dict(plan="enterprise", billing_status="active", quota_limit=0,
                                   custom_quota_limit=50000, custom_quota_notes="acuerdo anual",
                                   quota_used=42000, quota_reset_date=d(-1), **pausa_vigente),
         None, reset(d(29))),
        # billing_status fuera de active/trialing/beta en BD: no se resetean.
        ("cancelado_en_bd", dict(plan="basic", billing_status="canceled", quota_limit=1225, quota_used=900,
                                 quota_reset_date=d(-5), subscription_id="sub_cancelado_bd",
                                 **pausa_vencida), None, None),
        ("past_due_en_bd", dict(plan="premium", billing_status="past_due", quota_limit=2950, quota_used=800,
                                quota_reset_date=d(-5), subscription_id="sub_past_due_bd"), None, None),
        # Reset no vencido: no se toca (la pausa vigente y los proyectos pausados siguen).
        ("no_vencido", dict(plan="business", billing_status="active", quota_limit=15000, quota_used=500,
                            quota_reset_date=d(10), current_period_start=d(-20), current_period_end=d(10),
                            subscription_id="sub_no_vencido_bd", **pausa_vigente), None, None),
        # Fecha absurda a un año vista (bug anual): el cron no la corrige, solo el health-check la señala.
        ("anual_congelado", dict(plan="premium", billing_status="active", quota_limit=2950, quota_used=2950,
                                 quota_reset_date=d(300), current_period_start=d(-65),
                                 current_period_end=d(300), subscription_id="sub_congelado"), None, None),
        # --- Con subscription_id y current_period_end NULL: el cron pregunta a Stripe ---
        # Sin quota_reset_date y periodo Stripe vigente: cachea el periodo e inicializa la
        # fecha SIN resetear (quota_used y pausas se quedan como estaban).
        ("stripe_vivo_sin_fecha", dict(plan="basic", billing_status="active", quota_limit=1225, quota_used=300,
                                       subscription_id="sub_vivo_sin_fecha", **pausa_vencida),
         {"id": "sub_vivo_sin_fecha", "status": "active", "current_period_end": ts(12)},
         {"current_period_end": d(12), "quota_reset_date": d(12)}),
        # Reset vencido y periodo vigente en el formato nuevo de la API (items.data[0]).
        ("stripe_vivo_vencido", dict(plan="premium", billing_status="active", quota_limit=2950, quota_used=800,
                                     quota_reset_date=d(-1), subscription_id="sub_vivo_vencido"),
         {"id": "sub_vivo_vencido", "status": "active", "items": {"data": [{"current_period_end": ts(20)}]}},
         reset(d(20), current_period_end=d(20))),
        # ARREGLADO (2026-09-28): cancelada o past_due en Stripe pero 'active' en BD
        # => NO se da cuota nueva ni se toca la fila (antes se reseteaba igualmente).
        ("stripe_cancelado", dict(plan="basic", billing_status="active", quota_limit=1225, quota_used=600,
                                  quota_reset_date=d(-1), subscription_id="sub_cancelado_stripe"),
         {"id": "sub_cancelado_stripe", "status": "canceled", "current_period_end": ts(-5)},
         None),
        ("stripe_past_due", dict(plan="basic", billing_status="active", quota_limit=1225, quota_used=400,
                                 quota_reset_date=d(-1), subscription_id="sub_past_due_stripe"),
         {"id": "sub_past_due_stripe", "status": "past_due", "current_period_end": ts(-2)},
         None),
        # Stripe falla: se sigue con el reset normal y el periodo sigue NULL.
        ("stripe_error", dict(plan="basic", billing_status="active", quota_limit=1225, quota_used=70,
                              quota_reset_date=d(-1), subscription_id="sub_error"),
         RuntimeError("Stripe no responde"), reset(d(29))),
        # Stripe responde sin periodo: tampoco se cachea nada; reset con base = ahora.
        ("stripe_sin_periodo", dict(plan="basic", billing_status="active", quota_limit=1225, quota_used=60,
                                    subscription_id="sub_sin_periodo"),
         {"id": "sub_sin_periodo", "status": "active"}, reset(d(30))),
        # Reset no vencido: el usuario no se selecciona y Stripe no se consulta.
        ("stripe_no_seleccionado", dict(plan="basic", billing_status="active", quota_limit=1225, quota_used=30,
                                        quota_reset_date=d(5), subscription_id="sub_no_seleccionado"),
         {"id": "sub_no_seleccionado", "status": "active", "current_period_end": ts(40)}, None),
    ]


# Suscripciones que el cron debe consultar en Stripe (una vez cada una): desde el
# 2026-09-28, todas las de usuarios con reset vencido y billing_status active/trialing.
SUBS_CONSULTADAS = {
    "sub_mensual", "sub_anual", "sub_vencido",
    "sub_vivo_sin_fecha", "sub_vivo_vencido", "sub_cancelado_stripe",
    "sub_past_due_stripe", "sub_error", "sub_sin_periodo",
}
# Usuarios con proyectos pausados en los tres módulos.
CON_PROYECTOS = ("mensual_periodo_vigente", "no_vencido", "stripe_vivo_sin_fecha")


@pytest.fixture
def escenario_reset(entorno, monkeypatch):
    import stripe

    import daily_quota_reset_cron

    T0 = datetime.now(timezone.utc).replace(microsecond=0)

    class RelojCongelado(datetime):
        @classmethod
        def now(cls, tz=None):
            return T0.astimezone(tz) if tz else T0.replace(tzinfo=None)

    monkeypatch.setattr(daily_quota_reset_cron, "datetime", RelojCongelado)

    respuestas_stripe = {}
    ids = {}
    cambios_esperados = {}
    for clave, campos, stripe_resp, cambios in _escenarios_reset(T0):
        ids[clave] = _insertar_usuario(entorno.db, f"{clave.replace('_', '.')}@example.invalid", **campos)
        cambios_esperados[clave] = cambios
        if campos.get("subscription_id") and stripe_resp is not None:
            respuestas_stripe[campos["subscription_id"]] = stripe_resp

    pausas_proyectos = {}
    for clave in CON_PROYECTOS:
        pausas_proyectos[clave] = _crear_proyectos_pausados(entorno.db, ids[clave], T0)

    llamadas_stripe = []

    def retrieve(sub_id, *args, **kwargs):
        llamadas_stripe.append(sub_id)
        respuesta = respuestas_stripe.get(sub_id)
        if isinstance(respuesta, Exception):
            raise respuesta
        if respuesta is None:
            raise AssertionError(f"Stripe consultado para {sub_id} sin respuesta preparada")
        return respuesta

    monkeypatch.setattr(stripe.Subscription, "retrieve", retrieve)
    monkeypatch.setattr(stripe, "api_key", None)

    antes = _estado_usuarios(entorno.db)
    esperado = {uid: dict(fila) for uid, fila in antes.items()}
    for clave, cambios in cambios_esperados.items():
        if cambios:
            esperado[ids[clave]].update(cambios)

    return SimpleNamespace(
        T0=T0, ids=ids, antes=antes, esperado=esperado, llamadas_stripe=llamadas_stripe,
        pausas_proyectos=pausas_proyectos, modulo=daily_quota_reset_cron, stripe=stripe,
    )


def _diferencias(actual, esperado, ids):
    nombre = {uid: clave for clave, uid in ids.items()}
    difs = []
    for uid in sorted(set(actual) | set(esperado)):
        for col in COLUMNAS_USUARIO:
            a = actual.get(uid, {}).get(col)
            e = esperado.get(uid, {}).get(col)
            if a != e:
                difs.append(f"user {uid} ({nombre.get(uid, 'semilla')}).{col}: actual={a!r} esperado={e!r}")
    return difs


def _comprobar_estado_tras_reset(ent, esc):
    difs = _diferencias(_estado_usuarios(ent.db), esc.esperado, esc.ids)
    assert not difs, "El reset cambió algo distinto de lo fijado:\n" + "\n".join(difs)

    # Proyectos: el usuario reseteado queda despausado en los tres módulos;
    # los demás conservan su pausa tal cual.
    libre = {t: (False, None, None, None) for t in TABLAS_PROYECTO}
    assert _pausas_proyectos(ent.db, esc.ids["mensual_periodo_vigente"]) == libre
    for clave in ("no_vencido", "stripe_vivo_sin_fecha"):
        pausa = esc.pausas_proyectos[clave]
        assert _pausas_proyectos(ent.db, esc.ids[clave]) == {t: pausa for t in TABLAS_PROYECTO}


def test_reset_directo_fija_quien_se_resetea_y_que_cambia(entorno, escenario_reset):
    escenario_reset.modulo.main()

    _comprobar_estado_tras_reset(entorno, escenario_reset)

    # Stripe se consulta una vez por cada usuario seleccionado con subscription_id y
    # billing_status active/trialing (estado real antes de resetear).
    assert sorted(escenario_reset.llamadas_stripe) == sorted(SUBS_CONSULTADAS)
    # Efecto lateral: fija la clave global del SDK de Stripe con STRIPE_SECRET_KEY.
    assert escenario_reset.stripe.api_key == "sk_test_notreal0000000000000000"

    # Los usuarios semilla (gratuito, admin y pago con reset a +29 días) no se tocan.
    for uid in (entorno.gratuito["id"], entorno.admin["id"], entorno.pago["id"]):
        assert _estado_usuarios(entorno.db)[uid] == escenario_reset.antes[uid]

    # El cron no manda correos ni lanza hilos.
    assert entorno.correos == []
    assert entorno.hilos == []


def test_reset_segunda_ejecucion_no_cambia_nada(entorno, escenario_reset):
    escenario_reset.modulo.main()
    tras_primera = _estado_usuarios(entorno.db)
    llamadas_primera = list(escenario_reset.llamadas_stripe)

    escenario_reset.modulo.main()

    assert _estado_usuarios(entorno.db) == tras_primera
    # La segunda pasada solo vuelve a preguntar por los que Stripe dejó sin reset
    # (siguen pendientes hasta que Stripe o el webhook lo resuelvan).
    assert sorted(escenario_reset.llamadas_stripe[len(llamadas_primera):]) == \
        ["sub_cancelado_stripe", "sub_past_due_stripe"]


def test_reset_si_stripe_no_tiene_clave_resetea_sin_consultar(entorno, escenario_reset, monkeypatch):
    """Sin STRIPE_SECRET_KEY la consulta viva lanza RuntimeError y el cron sigue
    con el reset normal: los usuarios con reset vencido se resetean sin cachear
    periodo, y el que no tenía fecha (stripe_vivo_sin_fecha) se RESETEA en vez
    de solo inicializar su fecha."""
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    T0 = escenario_reset.T0
    ids = escenario_reset.ids
    esperado = escenario_reset.esperado
    esperado[ids["stripe_vivo_vencido"]]["current_period_end"] = None
    esperado[ids["stripe_vivo_vencido"]]["quota_reset_date"] = T0 + timedelta(days=29)
    # Sin clave no se puede consultar el estado en Stripe: se resetea como antes.
    for clave in ("stripe_cancelado", "stripe_past_due"):
        esperado[ids[clave]].update({
            "quota_used": 0, "quota_reset_date": T0 + timedelta(days=29), "current_period_end": None,
            "ai_overview_paused_until": None, "ai_overview_paused_at": None, "ai_overview_paused_reason": None,
        })
    # COMPORTAMIENTO ACTUAL (posible defecto): sin clave de Stripe, un usuario de pago a
    # mitad de periodo sin quota_reset_date recibe un reset completo de cuota.
    esperado[ids["stripe_vivo_sin_fecha"]].update({
        "quota_used": 0, "quota_reset_date": T0 + timedelta(days=30), "current_period_end": None,
        "ai_overview_paused_until": None, "ai_overview_paused_at": None, "ai_overview_paused_reason": None,
    })

    escenario_reset.modulo.main()

    difs = _diferencias(_estado_usuarios(entorno.db), esperado, ids)
    assert not difs, "\n".join(difs)
    assert escenario_reset.llamadas_stripe == []
    libre = {t: (False, None, None, None) for t in TABLAS_PROYECTO}
    assert _pausas_proyectos(entorno.db, ids["stripe_vivo_sin_fecha"]) == libre


def _comprobar_health_check(ent, esc, health):
    congelado = esc.ids["anual_congelado"]
    assert health["ok"] is False
    # Desde el 2026-09-28 los usuarios que Stripe da por cancelados/impagados no se
    # resetean y quedan con la fecha vencida: el health-check los señala junto al
    # congelado a +300 días (aviso de desajuste entre BD y Stripe).
    assert health["stuck_count"] == 3
    assert {u["id"] for u in health["stuck_users"]} == {
        congelado, esc.ids["stripe_cancelado"], esc.ids["stripe_past_due"]}
    atascado = next(u for u in health["stuck_users"] if u["id"] == congelado)
    assert atascado["id"] == congelado
    assert atascado["email"] == "anual.congelado@example.invalid"
    assert atascado["plan"] == "premium"
    assert (atascado["quota_used"], atascado["quota_limit"]) == (2950, 2950)
    assert atascado["reset"] == (esc.T0 + timedelta(days=300)).date().isoformat()
    # Un correo de alerta al destinatario por defecto (sin APP_ENV => UNKNOWN).
    assert ent.correos == [{"to": DESTINO_POR_DEFECTO, "subject": "[UNKNOWN] Quota reset stuck — 3 user(s)"}]


def test_reset_via_endpoint_sincrono(entorno, escenario_reset):
    resp = _post(entorno, URL_QUOTA_RESET, autorizacion=_bearer())

    assert resp.status_code == 200
    cuerpo = resp.get_json()
    assert cuerpo["success"] is True
    assert cuerpo["message"] == "Quota reset completed"
    assert cuerpo["triggered_by"] == "cron"
    # Mismo resultado en BD que la llamada directa.
    _comprobar_estado_tras_reset(entorno, escenario_reset)
    assert sorted(escenario_reset.llamadas_stripe) == sorted(SUBS_CONSULTADAS)
    # Health-check posterior: solo el usuario con fecha a +300 días queda marcado.
    _comprobar_health_check(entorno, escenario_reset, cuerpo["health_check"])
    # Ningún proyecto elegible (sin keywords activas) => staleness OK.
    assert cuerpo["cron_staleness"] == {"ok": True, "stale_modules": []}
    assert entorno.hilos == []


def test_reset_via_endpoint_asincrono_lanza_hilo_que_hace_lo_mismo(entorno, escenario_reset):
    resp = _post(entorno, LLAMADAS_BUN["quota-reset"], autorizacion=_bearer())

    assert resp.status_code == 202
    assert resp.get_json() == {
        "success": True, "message": "Quota reset triggered in background",
        "async": True, "triggered_by": "bun_cron",
    }
    assert len(entorno.hilos) == 1
    hilo = entorno.hilos[0]
    assert (hilo.name, hilo.daemon, hilo.arrancado, hilo.args) == ("quota-reset-bg", True, True, ())
    # El hilo no ha corrido: la BD sigue igual.
    assert _estado_usuarios(entorno.db) == escenario_reset.antes
    assert escenario_reset.llamadas_stripe == []

    # Ejecutado aquí mismo (sin hilo real) hace el reset, el health-check y el staleness.
    hilo.target()

    _comprobar_estado_tras_reset(entorno, escenario_reset)
    assert entorno.correos == [{"to": DESTINO_POR_DEFECTO, "subject": "[UNKNOWN] Quota reset stuck — 3 user(s)"}]


def test_health_check_endpoint_no_modifica_usuarios(entorno, escenario_reset):
    for metodo in ("GET", "POST"):
        entorno.correos.clear()
        resp = _post(entorno, URL_HEALTH, autorizacion=_bearer(), metodo=metodo)
        assert resp.status_code == 200
        cuerpo = resp.get_json()
        assert cuerpo["success"] is True
        assert cuerpo["cron_staleness"] == {"ok": True, "stale_modules": []}
        # Antes del reset: pago en active/trialing/beta con fecha de hace 24 h o más
        # (los de T0 - 1 día entran porque NOW() en la base es posterior a T0) o a
        # más de 35 días vista. Los NULL, los gratuitos y los canceled/past_due no.
        atascados = {u["id"] for u in cuerpo["health"]["stuck_users"]}
        ids = escenario_reset.ids
        assert atascados == {ids[c] for c in (
            "mensual_periodo_vigente", "anual_mitad_periodo", "periodo_vencido_en_bd", "muy_atrasado",
            "trialing", "enterprise_custom", "stripe_vivo_vencido", "stripe_cancelado", "stripe_past_due",
            "stripe_error", "anual_congelado",
        )}
        assert cuerpo["health"]["stuck_count"] == 11
        assert len(entorno.correos) == 1
    assert _estado_usuarios(entorno.db) == escenario_reset.antes
    assert escenario_reset.llamadas_stripe == []

    sin_token = _post(entorno, URL_HEALTH)
    assert sin_token.status_code == 403


# ---------------------------------------------------------------------------
# 2. Autorización de los endpoints de cron (tal y como llaman las funciones Bun)
# ---------------------------------------------------------------------------

def _sin_efectos(ent):
    assert ent.hilos == [], "Una petición rechazada no debe lanzar hilos"
    assert ent.correos == [], "Una petición rechazada no debe mandar correos"
    assert _runs(ent.db) == [], "Una petición rechazada no debe crear runs"
    assert ent.llamadas_analisis_llm == []


@pytest.mark.parametrize("endpoint", sorted(LLAMADAS_BUN))
def test_sin_token_rechaza(entorno, endpoint):
    resp = _post(entorno, LLAMADAS_BUN[endpoint])
    codigo, cuerpo = RECHAZO_ANONIMO[endpoint]
    assert resp.status_code == codigo
    assert resp.get_json() == cuerpo
    _sin_efectos(entorno)


@pytest.mark.parametrize("endpoint", sorted(LLAMADAS_BUN))
def test_token_incorrecto_rechaza(entorno, endpoint):
    resp = _post(entorno, LLAMADAS_BUN[endpoint], autorizacion=_bearer("token-que-no-es"))
    codigo, cuerpo = RECHAZO_ANONIMO[endpoint]
    assert resp.status_code == codigo
    assert resp.get_json() == cuerpo
    _sin_efectos(entorno)


@pytest.mark.parametrize("rol", ["gratuito", "pago"])
@pytest.mark.parametrize("endpoint", sorted(LLAMADAS_BUN))
def test_usuario_no_admin_con_sesion_rechaza(entorno, endpoint, rol):
    resp = _post(entorno, LLAMADAS_BUN[endpoint], usuario=getattr(entorno, rol))
    codigo, cuerpo = RECHAZO_NO_ADMIN[endpoint]
    assert resp.status_code == codigo
    assert resp.get_json() == cuerpo
    _sin_efectos(entorno)


@pytest.mark.parametrize("endpoint", sorted(LLAMADAS_BUN))
def test_admin_con_sesion(entorno, endpoint):
    resp = _post(entorno, LLAMADAS_BUN[endpoint], usuario=entorno.admin)
    if endpoint == "quota-reset":
        # COMPORTAMIENTO ACTUAL: quota-reset solo admite el token, un admin con sesión recibe 403.
        assert resp.status_code == 403
        assert resp.get_json() == RECHAZO_ANONIMO["quota-reset"][1]
        _sin_efectos(entorno)
    else:
        assert resp.status_code == CODIGO_ACEPTADO[endpoint]
        assert resp.get_json()["success"] is True


@pytest.mark.parametrize("endpoint", sorted(LLAMADAS_BUN))
def test_token_correcto_acepta(entorno, endpoint):
    resp = _post(entorno, LLAMADAS_BUN[endpoint], autorizacion=_bearer())
    assert resp.status_code == CODIGO_ACEPTADO[endpoint]
    assert resp.get_json()["success"] is True


@pytest.mark.parametrize("url", [URL_MANUAL_AI + "?async=1", URL_AI_MODE + "?async=1"])
def test_cron_or_admin_sin_cabeceras_json_responde_json(entorno, url):
    """cron_or_admin_required (Manual AI / AI Mode) cae en admin_required.
    CAMBIADO (29-sep-2026, fase de fiabilidad): admin_required detecta JSON como
    auth_required (Accept, XHR o ruta /api/); antes, sin Content-Type redirigía
    al login o al dashboard con HTML que el JS no podía leer."""
    anonimo = _cliente(entorno.app).post(url)
    assert anonimo.status_code == 401
    assert anonimo.get_json()["auth_required"] is True

    usuario = _cliente(entorno.app, entorno.gratuito).post(url)
    assert usuario.status_code == 403
    assert usuario.get_json()["admin_required"] is True
    _sin_efectos(entorno)


def test_endpoints_llm_sin_cabeceras_json_siguen_respondiendo_json(entorno):
    # auth_required trata cualquier ruta con /api/ como JSON: 401 sin redirección.
    for url in (URL_LLM_DAILY + "?async=1", URL_WATCHDOG, URL_DISCOVERY):
        resp = _cliente(entorno.app).post(url)
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Authentication required", "auth_required": True}
    assert _cliente(entorno.app).post(URL_QUOTA_RESET).status_code == 403
    _sin_efectos(entorno)


# ---------------------------------------------------------------------------
# 3. Comparación del token
# ---------------------------------------------------------------------------

AUTORIZACIONES_RECHAZADAS = {
    "prefijo_del_token": "Bearer test-cron-toke",
    "token_mas_largo": "Bearer test-cron-token0",
    "token_con_sufijo": "Bearer test-cron-token-extra",
    "mayusculas": "Bearer TEST-CRON-TOKEN",
    "sin_esquema": TOKEN,
    "sin_espacio_tras_bearer": "Bearertest-cron-token",
    "esquema_token": "Token test-cron-token",
    "esquema_basic": "Basic dGVzdC1jcm9uLXRva2Vu",
    "bearer_vacio": "Bearer ",
    "solo_bearer": "Bearer",
}


@pytest.mark.parametrize("variante", sorted(AUTORIZACIONES_RECHAZADAS))
def test_variantes_de_token_rechazadas(entorno, variante):
    for endpoint, url in sorted(LLAMADAS_BUN.items()):
        resp = _post(entorno, url, autorizacion=AUTORIZACIONES_RECHAZADAS[variante])
        codigo, cuerpo = RECHAZO_ANONIMO[endpoint]
        assert (endpoint, resp.status_code) == (endpoint, codigo)
        assert resp.get_json() == cuerpo
    _sin_efectos(entorno)


def test_token_fuera_de_authorization_no_vale(entorno):
    for endpoint, url in sorted(LLAMADAS_BUN.items()):
        separador = "&" if "?" in url else "?"
        intentos = [
            _post(entorno, url, cabeceras_extra={"X-Cron-Token": TOKEN}),
            _post(entorno, url, cabeceras_extra={"X-Cron-Secret": TOKEN}),
            _post(entorno, f"{url}{separador}token={TOKEN}"),
            _post(entorno, f"{url}{separador}cron_token={TOKEN}"),
            _post(entorno, url, json_body={"token": TOKEN, "cron_token": TOKEN}),
        ]
        codigo, cuerpo = RECHAZO_ANONIMO[endpoint]
        for resp in intentos:
            assert (endpoint, resp.status_code) == (endpoint, codigo)
            assert resp.get_json() == cuerpo
    _sin_efectos(entorno)


AUTORIZACIONES_ACEPTADAS = {
    "normal": "Bearer test-cron-token",
    "esquema_en_minusculas": "bearer test-cron-token",
    "esquema_en_mayusculas": "BEARER test-cron-token",
    # El token se recorta con strip(): los espacios alrededor no importan.
    "espacios_alrededor": "Bearer   test-cron-token   ",
}


@pytest.mark.parametrize("variante", sorted(AUTORIZACIONES_ACEPTADAS))
@pytest.mark.parametrize("endpoint", sorted(LLAMADAS_BUN))
def test_variantes_de_token_aceptadas(entorno, endpoint, variante):
    resp = _post(entorno, LLAMADAS_BUN[endpoint], autorizacion=AUTORIZACIONES_ACEPTADAS[variante])
    assert resp.status_code == CODIGO_ACEPTADO[endpoint]


def test_token_con_caracteres_no_ascii(entorno):
    """secrets.compare_digest lanza TypeError con cadenas str no ASCII;
    config.cabecera_cron_valida() lo trata como token inválido."""
    autorizacion = "Bearer test-cron-tokeñ"

    # CAMBIADO (config único, sep-2026): antes quota-reset no capturaba la
    # excepción y respondía 500; ahora es un token inválido más (403).
    assert _post(entorno, LLAMADAS_BUN["quota-reset"], autorizacion=autorizacion).status_code == 403

    # Los decoradores de auth.py capturan la excepción y caen a la autenticación normal.
    for endpoint in ("llm-daily", "llm-watchdog", "llm-model-discovery", "manual-ai", "ai-mode"):
        resp = _post(entorno, LLAMADAS_BUN[endpoint], autorizacion=autorizacion)
        assert (endpoint, resp.status_code) == (endpoint, 401)
    _sin_efectos(entorno)

    # CAMBIADO (config único, sep-2026): antes, con sesión de admin, el endpoint LLM
    # volvía a comparar en _ensure_cron_token_or_admin y el TypeError daba 500; ahora
    # el token no vale y pasa por ser admin, como en Manual AI.
    resp = _post(entorno, LLAMADAS_BUN["llm-watchdog"], usuario=entorno.admin, autorizacion=autorizacion)
    assert resp.status_code == CODIGO_ACEPTADO["llm-watchdog"]
    # En Manual AI el mismo admin pasa (cron_or_admin_required no vuelve a comparar).
    resp = _post(entorno, LLAMADAS_BUN["manual-ai"], usuario=entorno.admin, autorizacion=autorizacion)
    assert resp.status_code == 202


def test_cron_secret_como_alternativa_y_token_vacio(entorno, monkeypatch):
    # Sin CRON_TOKEN se usa CRON_SECRET.
    monkeypatch.delenv("CRON_TOKEN", raising=False)
    monkeypatch.setenv("CRON_SECRET", "secreto-alternativo")
    for endpoint, url in sorted(LLAMADAS_BUN.items()):
        rechazo = _post(entorno, url, autorizacion=_bearer())
        assert (endpoint, rechazo.status_code) == (endpoint, RECHAZO_ANONIMO[endpoint][0])
    assert _post(entorno, LLAMADAS_BUN["quota-reset"], autorizacion="Bearer secreto-alternativo").status_code == 202
    assert _post(entorno, LLAMADAS_BUN["llm-watchdog"], autorizacion="Bearer secreto-alternativo").status_code == 200
    assert _post(entorno, LLAMADAS_BUN["manual-ai"], autorizacion="Bearer secreto-alternativo").status_code == 202

    # CRON_TOKEN definido pero vacío cuenta como ausente ('' es falsy) => vuelve a CRON_SECRET.
    monkeypatch.setenv("CRON_TOKEN", "")
    assert _post(entorno, LLAMADAS_BUN["quota-reset"], autorizacion="Bearer secreto-alternativo").status_code == 202

    # Sin ninguno de los dos, nada pasa, tampoco un Bearer vacío.
    monkeypatch.delenv("CRON_SECRET", raising=False)
    for autorizacion in ("Bearer ", "Bearer x", _bearer()):
        for endpoint, url in sorted(LLAMADAS_BUN.items()):
            resp = _post(entorno, url, autorizacion=autorizacion)
            assert (endpoint, resp.status_code) == (endpoint, RECHAZO_ANONIMO[endpoint][0])


# ---------------------------------------------------------------------------
# 4. LLM Monitoring: daily-analysis y su lock
# ---------------------------------------------------------------------------

def test_llm_daily_token_toma_lock_crea_run_y_lanza_hilo(entorno):
    resp = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())

    assert resp.status_code == 202
    cuerpo = resp.get_json()
    run_id = cuerpo["run_id"]
    assert cuerpo == {"success": True, "message": "Daily analysis triggered in background",
                      "async": True, "run_id": run_id}
    lock = _lock(entorno.db)
    assert (lock["is_running"], lock["started_by"]) == (True, "cron")
    assert lock["started_at"] is not None
    runs = _runs(entorno.db)
    assert [(r["id"], r["status"], r["triggered_by"], r["completed_at"]) for r in runs] == [
        (run_id, "running", "cron", None)]
    assert len(entorno.hilos) == 1
    hilo = entorno.hilos[0]
    assert (hilo.target.__name__, hilo.args, hilo.daemon, hilo.arrancado) == (
        "run_analysis_in_background", (run_id,), True, True)
    # El análisis no ha corrido.
    assert entorno.llamadas_analisis_llm == []


def test_llm_daily_triggered_by_se_guarda_en_lock_y_run(entorno):
    resp = _post(entorno, URL_LLM_DAILY + "?async=1&triggered_by=manual_admin", autorizacion=_bearer())
    assert resp.status_code == 202
    assert _lock(entorno.db)["started_by"] == "manual_admin"
    assert _runs(entorno.db)[0]["triggered_by"] == "manual_admin"


def test_llm_daily_segundo_disparo_con_lock_tomado_da_409(entorno):
    primero = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())
    run_id = primero.get_json()["run_id"]
    lock_antes = _lock(entorno.db)

    segundo = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())

    assert segundo.status_code == 409
    cuerpo = segundo.get_json()
    assert cuerpo["success"] is False
    assert cuerpo["error"] == "Analysis already running"
    assert cuerpo["message"] == ("An analysis is already in progress. Please wait for it to finish "
                                 "before starting another.")
    assert (cuerpo["latest_run"]["id"], cuerpo["latest_run"]["status"]) == (run_id, "running")
    assert _lock(entorno.db) == lock_antes
    assert len(_runs(entorno.db)) == 1
    assert len(entorno.hilos) == 1

    # El modo síncrono también respeta el lock.
    sincrono = _post(entorno, URL_LLM_DAILY, autorizacion=_bearer())
    assert sincrono.status_code == 409
    assert entorno.llamadas_analisis_llm == []


def test_llm_daily_lock_reciente_sembrado_da_409(entorno):
    run_id = _sembrar_lock_llm(entorno.db, minutos_atras=10)
    resp = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())
    assert resp.status_code == 409
    assert resp.get_json()["latest_run"]["id"] == run_id
    assert entorno.hilos == []


def test_llm_daily_lock_de_mas_de_15_minutos_se_fuerza(entorno):
    # El timeout de lock obsoleto es 15 minutos (el doc de LLM Monitoring habla de 30).
    run_viejo = _sembrar_lock_llm(entorno.db, minutos_atras=20, started_by="cron_anterior")

    resp = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())

    assert resp.status_code == 202
    run_nuevo = resp.get_json()["run_id"]
    assert run_nuevo != run_viejo
    lock = _lock(entorno.db)
    assert (lock["is_running"], lock["started_by"]) == (True, "cron")
    assert datetime.now() - lock["started_at"] < timedelta(minutes=1)
    estados = {r["id"]: (r["status"], r["completed_at"]) for r in _runs(entorno.db)}
    # COMPORTAMIENTO ACTUAL (posible defecto): al forzar el lock, el run anterior se
    # queda en 'running' sin completed_at (huérfano) hasta el próximo arranque de la app.
    assert estados == {run_viejo: ("running", None), run_nuevo: ("running", None)}
    assert len(entorno.hilos) == 1


def test_llm_daily_lock_sin_started_at_se_fuerza(entorno):
    _sembrar_lock_llm(entorno.db, minutos_atras=0, con_started_at=False)
    resp = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())
    assert resp.status_code == 202
    assert _lock(entorno.db)["started_at"] is not None


def test_llm_daily_fila_del_lock_bloqueada_por_otra_transaccion_da_409(entorno):
    import psycopg2

    _sql(entorno.db, "INSERT INTO llm_monitoring_analysis_lock (id, is_running) VALUES (1, FALSE)")
    retenedor = psycopg2.connect(entorno.db, connect_timeout=5)
    try:
        cur = retenedor.cursor()
        cur.execute("SELECT 1 FROM llm_monitoring_analysis_lock WHERE id = 1 FOR UPDATE")
        resp = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())
    finally:
        retenedor.rollback()
        retenedor.close()

    # SKIP LOCKED: no espera, responde 409 aunque is_running sea FALSE y no haya runs.
    assert resp.status_code == 409
    assert resp.get_json()["latest_run"] is None
    assert _lock(entorno.db)["is_running"] is False
    assert entorno.hilos == []


def test_llm_daily_hilo_capturado_libera_lock_y_cierra_run(entorno):
    entorno.resultados_llm["valor"] = [
        {"project_id": 1, "project_name": "Uno", "total_queries_executed": 10},
        {"project_id": 2, "project_name": "Dos", "error": "quota_exceeded", "message": "sin cuota"},
    ]
    resp = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())
    run_id = resp.get_json()["run_id"]

    entorno.hilos[0].target(*entorno.hilos[0].args)

    assert entorno.llamadas_analisis_llm == [{"api_keys": None, "max_workers": 10}]
    assert _lock(entorno.db) == {"is_running": False, "started_at": None, "started_by": None}
    run = _runs(entorno.db)[0]
    assert run["id"] == run_id
    assert (run["status"], run["total_projects"], run["successful_projects"], run["failed_projects"],
            run["total_queries"], run["error_message"]) == ("completed", 2, 1, 1, 10, None)
    assert run["completed_at"] is not None
    assert run["project_results"] == [
        {"project_id": 1, "project_name": "Uno", "success": True, "queries": 10},
        {"project_id": 2, "project_name": "Dos", "success": False, "error": "quota_exceeded",
         "message": "sin cuota"},
    ]
    assert entorno.avisos_run == [run_id]


def test_llm_daily_hilo_capturado_con_excepcion_marca_run_fallido(entorno):
    entorno.resultados_llm["valor"] = RuntimeError("proveedor caído")
    resp = _post(entorno, LLAMADAS_BUN["llm-daily"], autorizacion=_bearer())
    run_id = resp.get_json()["run_id"]

    entorno.hilos[0].target(*entorno.hilos[0].args)

    assert _lock(entorno.db)["is_running"] is False
    run = _runs(entorno.db)[0]
    assert (run["id"], run["status"], run["error_message"], run["total_projects"]) == (
        run_id, "failed", "proveedor caído", 0)
    assert entorno.avisos_run == [run_id]


def test_llm_daily_modo_sincrono(entorno):
    entorno.resultados_llm["valor"] = [
        {"project_id": 7, "project_name": "Siete", "total_queries_executed": 4},
    ]
    resp = _post(entorno, URL_LLM_DAILY, autorizacion=_bearer())

    assert resp.status_code == 200
    cuerpo = resp.get_json()
    run_id = cuerpo["run_id"]
    assert cuerpo == {
        "success": True, "total_projects": 1, "successful": 1, "failed": 0, "total_queries": 4,
        "run_id": run_id, "results": [{"project_id": 7, "project_name": "Siete", "total_queries_executed": 4}],
    }
    assert _lock(entorno.db)["is_running"] is False
    assert _runs(entorno.db)[0]["status"] == "completed"
    assert entorno.hilos == []


def test_llm_daily_modo_sincrono_con_excepcion(entorno):
    entorno.resultados_llm["valor"] = RuntimeError("fallo")
    resp = _post(entorno, URL_LLM_DAILY, autorizacion=_bearer())
    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "error": "Internal server error"}
    assert _lock(entorno.db)["is_running"] is False
    assert _runs(entorno.db)[0]["status"] == "failed"


def test_llm_daily_por_proyecto_ignora_el_lock_global(entorno):
    run_viejo = _sembrar_lock_llm(entorno.db, minutos_atras=5)
    lock_antes = _lock(entorno.db)

    resp = _post(entorno, URL_LLM_DAILY + "?async=1&project_id=77", autorizacion=_bearer())

    # COMPORTAMIENTO ACTUAL: el re-run por proyecto no mira el lock global ni comprueba
    # que el proyecto exista; responde 202 y lanza el hilo.
    assert resp.status_code == 202
    assert resp.get_json() == {"success": True, "message": "Analysis for project 77 triggered in background",
                               "async": True, "project_id": 77}
    assert _lock(entorno.db) == lock_antes
    assert [r["id"] for r in _runs(entorno.db)] == [run_viejo]
    assert len(entorno.hilos) == 1
    assert (entorno.hilos[0].target.__name__, entorno.hilos[0].args) == ("run_single_bg", ())


# ---------------------------------------------------------------------------
# 5. LLM Monitoring: watchdog
# ---------------------------------------------------------------------------

def _watchdog(ent, url=URL_WATCHDOG, json_body=None, metodo="POST"):
    resp = _post(ent, url, autorizacion=_bearer(), json_body=json_body, metodo=metodo)
    assert resp.status_code == 200
    return resp.get_json()


def test_watchdog_sin_runs_completados_avisa_never_run(entorno):
    cuerpo = _watchdog(entorno)
    assert cuerpo == {"success": True, "state": "never_run", "hours_since_last_run": None,
                      "max_hours": 36, "last_run": None, "email_sent": True}
    assert len(entorno.correos) == 1
    assert entorno.correos[0]["to"] == DESTINO_POR_DEFECTO
    assert entorno.correos[0]["subject"].endswith("[UNKNOWN] LLM Monitoring watchdog · NEVER_RUN")


def test_watchdog_run_reciente_ok_sin_correo(entorno):
    run_id = _sembrar_run(entorno.db, "completed", horas_inicio=3, horas_fin=2)
    for metodo in ("POST", "GET"):
        cuerpo = _watchdog(entorno, metodo=metodo)
        assert cuerpo["state"] == "ok"
        assert 1.9 < cuerpo["hours_since_last_run"] < 2.1
        assert (cuerpo["last_run"]["id"], cuerpo["last_run"]["status"]) == (run_id, "completed")
        assert "email_sent" not in cuerpo
    assert entorno.correos == []


def test_watchdog_run_antiguo_stale_con_correo(entorno):
    run_id = _sembrar_run(entorno.db, "completed", horas_inicio=49, horas_fin=48)
    cuerpo = _watchdog(entorno)
    assert cuerpo["state"] == "stale"
    assert 47.9 < cuerpo["hours_since_last_run"] < 48.1
    assert cuerpo["last_run"]["id"] == run_id
    assert cuerpo["email_sent"] is True
    assert entorno.correos[0]["subject"].endswith("[UNKNOWN] LLM Monitoring watchdog · STALE")


def test_watchdog_umbral_por_query_y_por_cuerpo(entorno):
    _sembrar_run(entorno.db, "completed", horas_inicio=3, horas_fin=2)
    assert _watchdog(entorno, url=URL_WATCHDOG + "?max_hours=1")["state"] == "stale"
    assert _watchdog(entorno, json_body={"max_hours": 72})["state"] == "ok"
    # El query string gana al cuerpo.
    assert _watchdog(entorno, url=URL_WATCHDOG + "?max_hours=1", json_body={"max_hours": 72})["state"] == "stale"


def test_watchdog_con_run_colgado_no_lo_toca(entorno):
    """Run 'running' desde hace 3 días con el lock tomado, y un run completado hace 2 h."""
    run_ok = _sembrar_run(entorno.db, "completed", horas_inicio=3, horas_fin=2)
    run_colgado = _sembrar_lock_llm(entorno.db, minutos_atras=3 * 24 * 60)
    lock_antes = _lock(entorno.db)

    cuerpo = _watchdog(entorno)

    # COMPORTAMIENTO ACTUAL (posible defecto): el watchdog solo mira el último run
    # 'completed'; un run colgado en 'running' pasa desapercibido (estado ok, sin correo)
    # y no se cierra ni se libera el lock.
    assert cuerpo["state"] == "ok"
    assert cuerpo["last_run"]["id"] == run_ok
    assert entorno.correos == []
    colgado = [r for r in _runs(entorno.db) if r["id"] == run_colgado][0]
    assert (colgado["status"], colgado["completed_at"]) == ("running", None)
    assert _lock(entorno.db) == lock_antes


def test_watchdog_con_solo_run_colgado_avisa_never_run_sin_tocarlo(entorno):
    run_colgado = _sembrar_lock_llm(entorno.db, minutos_atras=3 * 24 * 60)
    lock_antes = _lock(entorno.db)

    cuerpo = _watchdog(entorno)

    assert cuerpo["state"] == "never_run"
    assert cuerpo["last_run"] is None
    assert cuerpo["email_sent"] is True
    assert [(r["id"], r["status"]) for r in _runs(entorno.db)] == [(run_colgado, "running")]
    assert _lock(entorno.db) == lock_antes


def test_watchdog_notify_email_solo_dominios_internos(entorno):
    _watchdog(entorno, json_body={"notify_email": "atacante@example.com"})
    _watchdog(entorno, json_body={"notify_email": "ops@clicandseo.com"})
    _watchdog(entorno, json_body={"notify_email": "alertas@SoyCarlosGonzalez.com"})
    assert [c["to"] for c in entorno.correos] == [
        DESTINO_POR_DEFECTO, "ops@clicandseo.com", "alertas@SoyCarlosGonzalez.com"]


# ---------------------------------------------------------------------------
# 6. LLM Monitoring: model-discovery
# ---------------------------------------------------------------------------

def test_model_discovery_con_token_sin_claves_de_proveedor(entorno):
    """Sin claves de OpenAI/Google/Anthropic solo cuenta la lista estática de
    Perplexity; sin registro de modelos no hay nada 'más nuevo'. Es síncrono."""
    resp = _post(entorno, URL_DISCOVERY + "?notify_email=externo%40example.com&auto_update=false",
                 autorizacion=_bearer())

    assert resp.status_code == 200
    cuerpo = resp.get_json()
    assert cuerpo["success"] is True
    assert cuerpo["discovered_count"] == 2
    assert cuerpo["newer_chat_models"] == []
    assert cuerpo["models_added"] == []
    assert cuerpo["pending_approval"] == 0
    assert cuerpo["current_models"] == {}
    assert cuerpo["errors"] == []
    assert cuerpo["email_sent"] is True
    # El destinatario externo se sustituye por el de por defecto (anti-relay).
    assert [c["to"] for c in entorno.correos] == [DESTINO_POR_DEFECTO]
    assert "Todo actualizado" in entorno.correos[0]["subject"]
    assert entorno.hilos == []
    assert _sql(entorno.db, "SELECT COUNT(*) AS n FROM llm_model_registry")[0]["n"] == 0


# ---------------------------------------------------------------------------
# 7. Manual AI y AI Mode
# ---------------------------------------------------------------------------

MODULOS_SERP = {
    "manual-ai": ("manual_ai_routes", URL_MANUAL_AI, 4242),
    "ai-mode": ("ai_mode_routes", URL_AI_MODE, 4243),
}


def _registrar_run_diario(monkeypatch, modulo_rutas, resultado):
    llamadas = []

    def run_diario():
        llamadas.append(True)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    monkeypatch.setattr(modulo_rutas.cron_service, "run_daily_analysis_for_all_projects", run_diario)
    return llamadas


@pytest.mark.parametrize("modulo", sorted(MODULOS_SERP))
def test_serp_async_responde_202_y_lanza_hilo_sin_lock_de_ruta(entorno, monkeypatch, modulo):
    atributo, url, _ = MODULOS_SERP[modulo]
    llamadas = _registrar_run_diario(monkeypatch, getattr(entorno, atributo), {"success": True})

    primero = _post(entorno, url + "?async=1", autorizacion=_bearer())
    segundo = _post(entorno, url + "?async=1", autorizacion=_bearer())

    # COMPORTAMIENTO ACTUAL: la ruta no tiene lock; dos disparos seguidos dan 202 y dos
    # hilos. La exclusión la hace el advisory lock dentro del hilo.
    for resp in (primero, segundo):
        assert resp.status_code == 202
        assert resp.get_json() == {"success": True, "message": "Daily analysis triggered in background",
                                   "async": True}
    assert len(entorno.hilos) == 2
    assert [(h.target.__name__, h.args, h.daemon, h.arrancado) for h in entorno.hilos] == [
        ("run_analysis_in_background", (), True, True)] * 2
    assert llamadas == []

    # El objetivo del hilo llama al servicio de cron.
    entorno.hilos[0].target()
    assert llamadas == [True]


@pytest.mark.parametrize("modulo", sorted(MODULOS_SERP))
def test_serp_sincrono_devuelve_el_resultado_del_servicio(entorno, monkeypatch, modulo):
    atributo, url, _ = MODULOS_SERP[modulo]
    rutas = getattr(entorno, atributo)

    _registrar_run_diario(monkeypatch, rutas, {"success": True, "successful": 3, "failed": 0})
    ok = _post(entorno, url, autorizacion=_bearer())
    assert ok.status_code == 200
    assert ok.get_json() == {"success": True, "successful": 3, "failed": 0}

    _registrar_run_diario(monkeypatch, rutas, {"success": False, "error": "DB connection failed for lock"})
    fallo = _post(entorno, url, autorizacion=_bearer())
    assert fallo.status_code == 500
    assert fallo.get_json() == {"success": False, "error": "DB connection failed for lock"}

    _registrar_run_diario(monkeypatch, rutas, RuntimeError("explota"))
    excepcion = _post(entorno, url, autorizacion=_bearer())
    assert excepcion.status_code == 500
    assert excepcion.get_json() == {"success": False, "error": "Internal server error"}
    assert entorno.hilos == []


@pytest.mark.parametrize("modulo", sorted(MODULOS_SERP))
def test_serp_sincrono_con_advisory_lock_tomado_se_salta(entorno, monkeypatch, modulo):
    """Segundo disparo con el advisory lock del día retenido por otra sesión:
    el servicio real no procesa nada y la ruta responde 200 'skipped'."""
    atributo, url, clase_lock = MODULOS_SERP[modulo]
    servicio = getattr(entorno, atributo).cron_service

    def no_debe_llamarse(*args, **kwargs):
        raise AssertionError("Con el lock tomado no debe buscar proyectos")

    completados = []
    monkeypatch.setattr(servicio, "_get_active_projects", no_debe_llamarse)
    monkeypatch.setattr(servicio, "_send_completion_email", lambda stats: completados.append(stats))

    dia = int(date.today().strftime("%Y%m%d"))
    retenedor = _conectar(entorno.db)
    try:
        retenedor.cursor().execute("SELECT pg_advisory_lock(%s, %s)", (clase_lock, dia))
        resp = _post(entorno, url, autorizacion=_bearer())
    finally:
        retenedor.cursor().execute("SELECT pg_advisory_unlock(%s, %s)", (clase_lock, dia))
        retenedor.close()

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "Another daily run in progress (skipped)",
                               "skipped": 0, "failed": 0, "successful": 0, "total_projects": 0}
    # En el salto por lock no se manda el correo de fin de run.
    assert completados == []
    assert entorno.avisos_simples == []
    assert entorno.hilos == []
