"""
Barreras comunes de la suite de tests.

1. Base de datos: la suite se detiene si DATABASE_URL apunta a un host que no
   sea local o el Postgres desechable de Docker (tests/docker). Varios tests
   escriben y borran filas; con la URL de staging o producción exportada en la
   shell lo harían contra datos reales. Los tests de integración pensados para
   staging se pueden seguir lanzando a propósito con ALLOW_REMOTE_DB_TESTS=1.

2. Red: se bloquean las conexiones salientes de Python salvo loopback, para que
   ningún test llame a APIs reales o de pago (OpenAI, Anthropic, Gemini,
   Perplexity, SerpAPI, Stripe, Brevo...). psycopg2 usa libpq y no pasa por
   aquí: la base de datos la protege la barrera 1. ALLOW_NETWORK_TESTS=1 la
   desactiva.

3. Fallos conocidos: los tests listados en tests/known_failures.txt ya
   fallaban antes de la limpieza de septiembre de 2026 (tests desfasados, no
   fallos de la app). Se marcan xfail no estricto para que cualquier fallo
   NUEVO destaque. Si uno se arregla, sale como XPASS y se quita de la lista.
"""

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

TESTS_DIR = Path(__file__).resolve().parent

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1", "clicandseo-test-db"}
LOCAL_NAMES = {"localhost", "localhost.localdomain", "clicandseo-test-db"}


# ---------------------------------------------------------------------------
# 1. Base de datos
# ---------------------------------------------------------------------------

def _allowed_db_hosts():
    extra = os.environ.get("TEST_DB_ALLOWED_HOSTS", "")
    return LOCAL_DB_HOSTS | {h.strip().lower() for h in extra.split(",") if h.strip()}


def _check_database_url():
    url = os.environ.get("DATABASE_URL")
    if not url or os.environ.get("ALLOW_REMOTE_DB_TESTS") == "1":
        return
    host = (urlparse(url).hostname or "").lower()
    if host not in _allowed_db_hosts():
        pytest.exit(
            f"DATABASE_URL apunta a '{host}', que no es una base local de pruebas. "
            "La suite se detiene para no escribir ni borrar datos reales. "
            "Usa scripts/run_tests_docker.sh o, solo para los tests de integración "
            "de staging, exporta ALLOW_REMOTE_DB_TESTS=1 a propósito.",
            returncode=2,
        )


# ---------------------------------------------------------------------------
# 2. Red
# ---------------------------------------------------------------------------

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _is_local_address(address):
    if not isinstance(address, tuple):  # AF_UNIX
        return True
    host = str(address[0]).split("%")[0]
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() in LOCAL_NAMES


def _guarded_connect(self, address):
    if not _is_local_address(address):
        raise ConnectionRefusedError(f"Red bloqueada en tests: {address!r}")
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if not _is_local_address(address):
        raise ConnectionRefusedError(f"Red bloqueada en tests: {address!r}")
    return _real_connect_ex(self, address)


def _guarded_getaddrinfo(host, *args, **kwargs):
    name = host.decode() if isinstance(host, bytes) else host
    if name is not None and not _is_local_address((name, 0)):
        raise socket.gaierror(socket.EAI_NONAME, f"Red bloqueada en tests: {name}")
    return _real_getaddrinfo(host, *args, **kwargs)


def _block_network():
    if os.environ.get("ALLOW_NETWORK_TESTS") == "1":
        return
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.getaddrinfo = _guarded_getaddrinfo


# ---------------------------------------------------------------------------
# 3. Fallos conocidos
# ---------------------------------------------------------------------------

def _known_failures():
    path = TESTS_DIR / "known_failures.txt"
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def pytest_configure(config):
    _check_database_url()
    _block_network()


# ---------------------------------------------------------------------------
# 4. Fixtures para tests que arrancan la app contra la base desechable
#    (solo se activan en los tests que los piden)
# ---------------------------------------------------------------------------

def _is_disposable_db(url):
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    dbname = (parsed.path or "").lstrip("/")
    return host in LOCAL_DB_HOSTS and dbname.startswith("clicandseo_test")


def _load_test_env():
    """Carga las variables FICTICIAS de tests/docker/test.env en el proceso."""
    for raw in (TESTS_DIR / "docker" / "test.env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


@pytest.fixture(scope="session")
def test_db_url():
    url = os.environ.get("DATABASE_URL", "")
    if not _is_disposable_db(url):
        pytest.skip("Necesita la base desechable de Docker (scripts/run_tests_docker.sh)")
    try:
        import psycopg2
        psycopg2.connect(url, connect_timeout=3).close()
    except Exception as exc:  # pragma: no cover - solo informativo
        pytest.skip(f"Base de pruebas no disponible: {exc}")
    return url


def truncate_all_tables(url):
    """Vacía todas las tablas de la base desechable. Se niega a tocar otra."""
    if not _is_disposable_db(url):
        raise RuntimeError("truncate_all_tables solo trabaja sobre la base desechable clicandseo_test*")
    import psycopg2
    conn = psycopg2.connect(url, connect_timeout=5)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET lock_timeout = '10s'")
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = [row[0] for row in cur.fetchall()]
        if tables:
            cur.execute(
                "TRUNCATE " + ", ".join(f'public."{t}"' for t in tables) + " RESTART IDENTITY CASCADE"
            )
    finally:
        conn.close()


@pytest.fixture(scope="session")
def flask_app(test_db_url):
    """Importa app.py una vez, con variables ficticias y como en producción:
    las excepciones de las vistas se convierten en 500 y el limitador global
    se desactiva para que cientos de peticiones seguidas no den 429."""
    _load_test_env()
    import app as app_module

    app_module.app.config["PROPAGATE_EXCEPTIONS"] = False
    app_module.limiter.enabled = False
    return app_module


@pytest.fixture
def clean_db(test_db_url):
    truncate_all_tables(test_db_url)
    yield test_db_url


SEED_USER_EMAIL = "usuario.test@example.invalid"
SEED_ADMIN_EMAIL = "admin.test@example.invalid"
SEED_PAID_EMAIL = "pago.test@example.invalid"


def seed_users():
    """Crea, con la propia lógica de la app, un usuario gratuito, un admin y un
    usuario de pago (plan business activo con cuota). Tras truncate_all_tables
    los ids son siempre 1 (gratuito), 2 (admin) y 3 (pago)."""
    import database

    user = database.create_user(SEED_USER_EMAIL, "Usuario Test", password="clave-test-123", auto_activate=True)
    admin = database.create_user(SEED_ADMIN_EMAIL, "Admin Test", password="clave-test-123", auto_activate=True)
    paid = database.create_user(SEED_PAID_EMAIL, "Pago Test", password="clave-test-123", auto_activate=True)
    assert user and admin and paid, "No se pudieron crear los usuarios semilla"
    assert database.update_user_role(admin["id"], "admin")

    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE users
               SET plan = 'business', current_plan = 'business', billing_status = 'active',
                   quota_limit = 15000, quota_used = 0,
                   subscription_id = 'sub_test_seed', stripe_customer_id = 'cus_test_seed',
                   current_period_start = NOW() - INTERVAL '1 day',
                   current_period_end = NOW() + INTERVAL '29 days',
                   quota_reset_date = NOW() + INTERVAL '29 days'
             WHERE id = %s
            """,
            (paid["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    return user, admin, paid


def pytest_collection_modifyitems(config, items):
    known = _known_failures()
    if not known:
        return
    marker = pytest.mark.xfail(
        reason="Fallo previo a la limpieza de sep-2026 (tests/known_failures.txt)",
        strict=False,
    )
    for item in items:
        if item.nodeid in known:
            item.add_marker(marker)
