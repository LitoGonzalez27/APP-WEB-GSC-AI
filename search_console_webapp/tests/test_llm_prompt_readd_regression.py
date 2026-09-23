"""
Regresión: volver a añadir un prompt borrado en LLM Monitoring.

Caso real (Ceramic Connection - ES, 2026-09-23): la colaboradora borró un
prompt para modificarlo y al volver a añadirlo el panel respondía
"All prompts already exist in this project". El borrado es "soft"
(is_active = FALSE) y la fila seguía ocupando el UNIQUE (project_id,
query_text), así que el INSERT ... ON CONFLICT DO NOTHING lo contaba como
duplicado para siempre.

Comportamiento esperado: el alta REACTIVA la fila inactiva (mismo id, luego
mismo histórico) con los valores del lote; solo es duplicado si ya está activo.

Dos bloques:
1. Unitario (sin BD): blindaje en el texto de la ruta y del JS.
2. Integración (BD de STAGING, se SALTA sin env): alta → borrado → alta.

Ejecutar la integración (nunca contra prod):
  railway run --service Clicandseo --environment staging \
    env DATABASE_URL=<staging public> LLM_SETS_IT_PROJECT_ID=12 LLM_SETS_IT_USER_ID=5 \
    python3 -m pytest tests/test_llm_prompt_readd_regression.py -q
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest  # noqa: E402

ROOT = Path(__file__).parent.parent
TEST_PREFIX = '[IT readd]'
PROJECT_ID = os.getenv('LLM_SETS_IT_PROJECT_ID')
USER_ID = int(os.getenv('LLM_SETS_IT_USER_ID', '5'))


# ══════════════════════════════════════════════════════════════════
# 1. Blindaje en el código (sin BD)
# ══════════════════════════════════════════════════════════════════

class TestReaddCodeGuards:
    routes = (ROOT / 'llm_monitoring_routes.py').read_text()

    def _route_body(self, name):
        body = self.routes[self.routes.index(f'def {name}('):]
        return body[:body.index('\n@llm_monitoring_bp.route')]

    def test_add_queries_reactivates_soft_deleted_rows(self):
        body = self._route_body('add_queries_to_project')
        assert 'ON CONFLICT (project_id, query_text) DO UPDATE SET' in body
        assert 'is_active = TRUE,' in body
        # La guarda es lo que convierte el duplicado activo en rowcount 0
        assert 'WHERE llm_monitoring_queries.is_active = FALSE' in body
        assert 'DO NOTHING' not in body
        # Reactivación = alta a efectos de contadores + señal aparte
        assert "'reactivated_count': reactivated_count" in body

    def test_delete_query_is_still_a_soft_delete(self):
        # Si algún día el borrado pasa a ser físico, este test recuerda revisar
        # la reactivación (que dejaría de tener sentido) y el histórico.
        body = self._route_body('delete_query')
        assert 'SET is_active = FALSE' in body
        assert 'DELETE FROM llm_monitoring_queries' not in body

    def test_js_tells_the_user_when_a_prompt_was_restored(self):
        js = (ROOT / 'static/js/llm_monitoring/llm-monitoring-prompts.js').read_text()
        assert 'data.reactivated_count > 0' in js


# ══════════════════════════════════════════════════════════════════
# 2. Integración contra BD de staging (se salta sin env)
# ══════════════════════════════════════════════════════════════════

pytestmark_it = pytest.mark.skipif(
    not PROJECT_ID,
    reason='Integración: exportar LLM_SETS_IT_PROJECT_ID (BD staging) para ejecutar'
)


@pytest.fixture(scope='module')
def client():
    from app import app
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = USER_ID
        s['last_activity'] = datetime.now().isoformat()
    return c


@pytest.fixture(scope='module')
def base():
    return f'/api/llm-monitoring/projects/{int(PROJECT_ID)}'


@pytest.fixture(scope='module', autouse=True)
def hard_clean_test_prompts():
    """Borra en duro los prompts de test antes y después (por prefijo)."""
    if not PROJECT_ID:
        yield
        return

    def _clean():
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM llm_monitoring_queries WHERE project_id = %s AND query_text LIKE %s",
            (int(PROJECT_ID), f'{TEST_PREFIX}%')
        )
        conn.commit()
        conn.close()

    _clean()
    yield
    _clean()


def _listed(client, base, text):
    r = client.get(f'{base}/queries')
    assert r.status_code == 200, r.get_data(as_text=True)
    return [q for q in r.get_json()['queries'] if q['prompt'] == text]


@pytestmark_it
class TestReaddAfterDelete:

    def test_alta_borrado_y_alta_de_nuevo_conserva_el_id(self, client, base):
        text = f'{TEST_PREFIX} ¿Cuáles son las mejores tiendas online de azulejos?'

        # 1) Alta normal
        r = client.post(f'{base}/queries', json={'queries': [text]})
        assert r.status_code == 200, r.get_data(as_text=True)
        d = r.get_json()
        assert (d['added_count'], d['reactivated_count'], d['duplicate_count']) == (1, 0, 0)
        rows = _listed(client, base, text)
        assert len(rows) == 1
        qid = rows[0]['id']

        # 2) Borrado (soft): desaparece del listado
        r = client.delete(f'{base}/queries/{qid}')
        assert r.status_code == 200, r.get_data(as_text=True)
        assert _listed(client, base, text) == []

        # 3) Volver a añadir el MISMO texto: se reactiva, mismo id, no es duplicado
        r = client.post(f'{base}/queries', json={'queries': [text]})
        assert r.status_code == 200, r.get_data(as_text=True)
        d = r.get_json()
        assert (d['added_count'], d['reactivated_count'], d['duplicate_count']) == (1, 1, 0)
        rows = _listed(client, base, text)
        assert len(rows) == 1
        assert rows[0]['id'] == qid

        # 4) Añadirlo estando activo sí es duplicado
        r = client.post(f'{base}/queries', json={'queries': [text]})
        d = r.get_json()
        assert (d['added_count'], d['reactivated_count'], d['duplicate_count']) == (0, 0, 1)

    def test_lote_mixto_cuenta_cada_caso(self, client, base):
        activo = f'{TEST_PREFIX} activo'
        borrado = f'{TEST_PREFIX} borrado'
        nuevo = f'{TEST_PREFIX} nuevo'

        r = client.post(f'{base}/queries', json={'queries': [activo, borrado]})
        assert r.get_json()['added_count'] == 2
        qid_borrado = _listed(client, base, borrado)[0]['id']
        assert client.delete(f'{base}/queries/{qid_borrado}').status_code == 200

        r = client.post(f'{base}/queries', json={'queries': [activo, borrado, nuevo, '  ']})
        d = r.get_json()
        assert d['added_count'] == 2          # borrado (reactivado) + nuevo
        assert d['reactivated_count'] == 1
        assert d['duplicate_count'] == 1      # activo
        assert d['error_count'] == 1          # cadena vacía
        assert _listed(client, base, borrado)[0]['id'] == qid_borrado
