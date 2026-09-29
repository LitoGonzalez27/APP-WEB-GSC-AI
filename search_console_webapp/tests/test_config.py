"""
config.py: configuración del entorno en un solo sitio (sep-2026).

Unitarios de cada función (sin base de datos) y una guardia: las variables que
deciden el entorno y los secretos de cron solo se leen en config.py. Antes,
stripe_config y billing_routes tomaban APP_ENV con 'staging' por defecto y,
sin APP_ENV en producción, la app se creía staging.
"""

import ast
import pathlib

import pytest

import config

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VARIABLES = ("APP_ENV", "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "CRON_TOKEN", "CRON_SECRET",
             "CRON_ALERTS_ENABLED", "ENFORCE_QUOTAS")
LECTURAS_PERMITIDAS = {  # (fichero, variable) -> motivo
    ("diagnostic_endpoint.py", "ENFORCE_QUOTAS"): "muestra el valor tal cual ('not set' si falta)",
}


@pytest.fixture
def entorno(monkeypatch):
    for v in VARIABLES + ("CRON_ALERTS_EMAIL", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    return monkeypatch


# --- entorno -------------------------------------------------------------------

@pytest.mark.parametrize("app_env, railway_name, railway, esperado", [
    (None, None, None, "development"),
    ("production", "production", "production", "production"),   # producción hoy
    (None, "staging", "staging", "staging"),                    # staging hoy (sin APP_ENV)
    (None, "production", "production", "production"),           # CAMBIADO: antes 'staging' en stripe_config
    ("staging", None, None, "staging"),
    (None, None, "production", "production"),
])
def test_entorno_app(entorno, app_env, railway_name, railway, esperado):
    for nombre, valor in (("APP_ENV", app_env), ("RAILWAY_ENVIRONMENT_NAME", railway_name), ("RAILWAY_ENVIRONMENT", railway)):
        if valor is not None:
            entorno.setenv(nombre, valor)
    assert config.entorno_app() == esperado
    assert config.es_produccion() is (esperado == "production")


@pytest.mark.parametrize("railway, desplegado", [
    (None, False), ("production", True), ("staging", True), ("development", False), ("", False)])
def test_desplegado_solo_depende_de_railway(entorno, railway, desplegado):
    entorno.setenv("APP_ENV", "production")  # APP_ENV no abre ni cierra barreras de seguridad
    if railway is not None:
        entorno.setenv("RAILWAY_ENVIRONMENT", railway)
    assert config.desplegado() is desplegado
    assert config.entorno_railway() == (railway or "")


def test_etiqueta_de_alertas_igual_que_antes(entorno):
    assert config.etiqueta_entorno() == "unknown"
    entorno.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    assert config.etiqueta_entorno() == "staging"
    entorno.setenv("APP_ENV", "production")
    assert config.etiqueta_entorno() == "production"


def test_aviso_si_app_env_contradice_a_railway(entorno):
    assert config.aviso_de_entorno() is None
    entorno.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    entorno.setenv("RAILWAY_ENVIRONMENT", "staging")
    assert config.aviso_de_entorno() is None
    entorno.setenv("APP_ENV", "staging")
    assert config.aviso_de_entorno() is None
    entorno.setenv("APP_ENV", "production")
    assert "no coincide" in config.aviso_de_entorno()


# --- crons -----------------------------------------------------------------------

@pytest.mark.parametrize("cabecera, valida", [
    ("Bearer secreto-cron", True),
    ("bearer secreto-cron", True),
    ("Bearer   secreto-cron  ", True),
    ("Bearer otro", False),
    ("Bearer ", False),
    ("secreto-cron", False),
    ("", False),
    (None, False),
    ("Bearer secreto-croñ", False),   # no ASCII: antes TypeError (500 en cron_routes)
])
def test_cabecera_cron(entorno, cabecera, valida):
    entorno.setenv("CRON_TOKEN", "secreto-cron")
    assert config.cabecera_cron_valida(cabecera) is valida


def test_cron_secret_como_nombre_antiguo_y_sin_secreto(entorno):
    assert config.token_cron() is None
    assert config.cabecera_cron_valida("Bearer ") is False
    assert config.cabecera_cron_valida("Bearer cualquiera") is False
    entorno.setenv("CRON_SECRET", "antiguo")
    assert config.cabecera_cron_valida("Bearer antiguo") is True
    entorno.setenv("CRON_TOKEN", "nuevo")
    assert config.cabecera_cron_valida("Bearer antiguo") is False
    assert config.cabecera_cron_valida("Bearer nuevo") is True


def test_alertas_email_url_y_cuotas(entorno):
    assert config.alertas_cron_activas() is True
    entorno.setenv("CRON_ALERTS_ENABLED", "FALSE")
    assert config.alertas_cron_activas() is False
    assert config.email_alertas() == config.EMAIL_ALERTAS_POR_DEFECTO
    entorno.setenv("CRON_ALERTS_EMAIL", "alertas@example.invalid")
    assert config.email_alertas() == "alertas@example.invalid"
    assert config.url_publica() == "https://app.clicandseo.com"
    entorno.setenv("PUBLIC_BASE_URL", "https://staging.example.invalid/")
    assert config.url_publica() == "https://staging.example.invalid"
    assert config.cuotas_forzadas() is False
    entorno.setenv("ENFORCE_QUOTAS", "true")
    assert config.cuotas_forzadas() is True


# --- guardia -----------------------------------------------------------------------

def _lecturas_de_entorno():
    excluir = {"tests", "scripts", ".venv", "venv", "node_modules", "__pycache__", ".claude"}
    for p in sorted(RAIZ.rglob("*.py")):
        rel = p.relative_to(RAIZ)
        if excluir.intersection(rel.parts) or rel.as_posix() == "config.py":
            continue
        try:
            arbol = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            nombre = None
            if isinstance(nodo, ast.Call) and ast.unparse(nodo.func) in ("os.getenv", "os.environ.get", "getenv", "environ.get"):
                if nodo.args and isinstance(nodo.args[0], ast.Constant):
                    nombre = nodo.args[0].value
            elif isinstance(nodo, ast.Subscript) and ast.unparse(nodo.value) in ("os.environ", "environ"):
                if isinstance(nodo.slice, ast.Constant):
                    nombre = nodo.slice.value
            if nombre in VARIABLES:
                yield rel.as_posix(), nombre, nodo.lineno


def test_las_variables_de_entorno_solo_se_leen_en_config():
    fuera = [f"{f}:{l} {v}" for f, v, l in _lecturas_de_entorno() if (f, v) not in LECTURAS_PERMITIDAS]
    assert not fuera, f"Lee estas variables con config.py (entorno_app, desplegado, cabecera_cron_valida...): {fuera}"
