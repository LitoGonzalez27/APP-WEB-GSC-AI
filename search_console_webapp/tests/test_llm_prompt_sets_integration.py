"""
Tests de INTEGRACIÓN de prompt sets + filtro global — Flask test client + BD real.

Ejercitan la feature completa contra la BD de STAGING: CRUD de sets, ventanas,
asignaciones, filtro exclusivo en los endpoints de datos, pseudo-snapshots,
exports y comportamiento del cron (selección de queries por ventana).

REQUISITOS (si faltan, los tests se SALTAN, no fallan):
- DATABASE_URL apuntando a la BD de staging (nunca prod).
- LLM_SETS_IT_PROJECT_ID: id de un proyecto de staging con >= 2 prompts
  y resultados históricos (p.ej. 12) cuyo dueño es LLM_SETS_IT_USER_ID (5).

Ejecutar (con el env de Railway para SECRET_KEY/API keys):
  railway run --service Clicandseo env DATABASE_URL=<staging> \
    LLM_SETS_IT_PROJECT_ID=12 LLM_SETS_IT_USER_ID=5 \
    python3 -m pytest tests/test_llm_prompt_sets_integration.py -q

Los tests restauran el estado del proyecto al terminar (sets a vacío y
prompts de vuelta al núcleo); los prompts creados aquí se borran en duro.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest  # noqa: E402

PROJECT_ID = os.getenv('LLM_SETS_IT_PROJECT_ID')
USER_ID = os.getenv('LLM_SETS_IT_USER_ID', '5')
TEST_PREFIX = '[IT prompt-sets]'

pytestmark = pytest.mark.skipif(
    not PROJECT_ID,
    reason='Integración: exportar LLM_SETS_IT_PROJECT_ID (BD staging) para ejecutar'
)

if PROJECT_ID:
    PROJECT_ID = int(PROJECT_ID)
    USER_ID = int(USER_ID)


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
    return f'/api/llm-monitoring/projects/{PROJECT_ID}'


@pytest.fixture(scope='module', autouse=True)
def clean_state(client, base):
    """Estado limpio antes y después: sin sets, sin prompts de test."""
    if not PROJECT_ID:
        yield
        return

    def _hard_clean():
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM llm_monitoring_queries WHERE project_id = %s AND query_text LIKE %s",
            (PROJECT_ID, f'{TEST_PREFIX}%')
        )
        conn.commit()
        conn.close()

    _hard_clean()
    client.put(f'{base}/sets', json={'sets_config': {'enabled': False, 'sets': []}})
    yield
    client.put(f'{base}/sets', json={'sets_config': {'enabled': False, 'sets': []}})
    _hard_clean()


@pytest.fixture(scope='module')
def with_sets(client, base):
    """Config de referencia: Black Friday (fuera de temporada en agosto) + Tendencias."""
    r = client.put(f'{base}/sets', json={'sets_config': {'enabled': True, 'sets': [
        {'name': 'Black Friday', 'window': {'start': '11-15', 'end': '12-02'}},
        {'name': 'Tendencias'},
    ]}})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()['sets_config']


class TestSetsCrud:

    def test_config_persistida_y_active_today(self, client, base, with_sets):
        r = client.get(f'{base}/sets')
        d = r.get_json()
        assert r.status_code == 200
        names = [s['name'] for s in d['sets_config']['sets']]
        assert names == ['Black Friday', 'Tendencias']
        # En cualquier fecha, un set sin ventana y el core están activos
        assert d['active_today']['core'] is True
        assert d['active_today']['Tendencias'] is True

    def test_nombre_reservado_rechazado(self, client, base, with_sets):
        r = client.put(f'{base}/sets', json={'sets_config': {
            'enabled': True, 'sets': [{'name': 'Núcleo'}]}})
        assert r.status_code == 400

    def test_ventana_malformada_rechazada(self, client, base, with_sets):
        r = client.put(f'{base}/sets', json={'sets_config': {
            'enabled': True,
            'sets': [{'name': 'X', 'window': {'start': '13-01', 'end': '11-30'}}]}})
        assert r.status_code == 400

    def test_rename_propaga_a_prompts(self, client, base, with_sets):
        # Crear prompt en Tendencias, renombrar el set, verificar el arrastre
        r = client.post(f'{base}/queries', json={
            'queries': [f'{TEST_PREFIX} rename check'], 'set': 'Tendencias'})
        assert r.status_code == 200
        r = client.post(f'{base}/sets/rename', json={
            'old_name': 'Tendencias', 'new_name': 'Tendencias 2027'})
        assert r.status_code == 200
        assert r.get_json()['updated_prompts'] >= 1

        r = client.get(f'{base}/queries?prompt_set=Tendencias 2027')
        found = [q for q in r.get_json()['queries'] if TEST_PREFIX in q['prompt']]
        assert len(found) == 1

        # Deshacer para el resto de tests
        client.post(f'{base}/sets/rename', json={
            'old_name': 'Tendencias 2027', 'new_name': 'Tendencias'})


class TestAssignments:

    def test_lote_con_set_y_asignacion_individual(self, client, base, with_sets):
        r = client.post(f'{base}/queries', json={
            'queries': [f'{TEST_PREFIX} lote BF'], 'set': 'Black Friday'})
        assert r.get_json()['added_count'] + r.get_json()['duplicate_count'] >= 1

        r = client.get(f'{base}/queries?prompt_set=Black Friday')
        bf = [q for q in r.get_json()['queries'] if TEST_PREFIX in q['prompt']]
        assert len(bf) >= 1
        qid = bf[0]['id']

        # 'core' y null vuelven a núcleo (prompt_set NULL)
        r = client.put(f'{base}/queries/{qid}/set', json={'set': 'core'})
        assert r.status_code == 200 and r.get_json()['prompt_set'] is None

        r = client.post(f'{base}/queries/bulk-set', json={
            'query_ids': [qid], 'set': 'Black Friday'})
        assert r.status_code == 200 and r.get_json()['updated'] == 1

    def test_set_desconocido_rechazado(self, client, base, with_sets):
        r = client.get(f'{base}/queries')
        qid = r.get_json()['queries'][0]['id']
        r = client.put(f'{base}/queries/{qid}/set', json={'set': 'No Existe'})
        assert r.status_code == 400


class TestExclusiveReportFilter:

    def test_core_excluye_sets_y_viceversa(self, client, base, with_sets):
        r = client.get(f'{base}/queries?prompt_set=core')
        assert all(not q.get('prompt_set') for q in r.get_json()['queries'])

        r = client.get(f'{base}/queries?prompt_set=Black Friday')
        rows = r.get_json()['queries']
        assert rows and all(q['prompt_set'] == 'Black Friday' for q in rows)

    @pytest.mark.parametrize('path', [
        'metrics?days=30&prompt_set=core',
        'share-of-voice-history?days=30&prompt_set=core',
        'comparison?days=30&prompt_set=core',
        'urls-ranking?days=30&prompt_set=core',
        'responses?days=30&prompt_set=core',
        'clusters/metrics?days=30&prompt_set=core',
        '?days=30&prompt_set=core',  # detalle del proyecto (KPIs)
    ])
    def test_endpoints_de_datos_aceptan_el_filtro(self, client, base, with_sets, path):
        url = f'{base}/{path}' if not path.startswith('?') else f'{base}{path}'
        r = client.get(url)
        assert r.status_code == 200, f'{path} → {r.status_code}'

    def test_filtro_activa_pseudo_snapshots(self, client, base, with_sets):
        """Con filtro los snapshots se recalculan desde results: el subconjunto
        filtrado nunca puede agregar más queries por fila que el total real."""
        legacy = client.get(f'{base}/metrics?days=30').get_json()['snapshots']
        filtered = client.get(f'{base}/metrics?days=30&prompt_set=core').get_json()['snapshots']
        assert filtered, 'la vista core debe tener datos históricos'
        legacy_by_key = {
            (s['snapshot_date'], s['llm_provider']): s['total_queries'] for s in legacy
        }
        for s in filtered:
            key = (s['snapshot_date'], s['llm_provider'])
            if key in legacy_by_key:
                assert s['total_queries'] <= legacy_by_key[key]

    def test_sin_filtro_camino_legacy_intacto(self, client, base, with_sets):
        r = client.get(f'{base}/metrics?days=30')
        assert r.status_code == 200
        assert isinstance(r.get_json()['snapshots'], list)


class TestExports:

    def test_excel_filtrado(self, client, base, with_sets):
        r = client.get(f'{base}/export/excel?days=30&prompt_set=core')
        assert r.status_code == 200
        assert 'spreadsheet' in r.headers.get('Content-Type', '')

    def test_pdf_filtrado(self, client, base, with_sets):
        r = client.get(f'{base}/export/pdf?days=30&metric=weighted&prompt_set=core')
        assert r.status_code == 200
        assert 'pdf' in r.headers.get('Content-Type', '')
        assert r.data[:5] == b'%PDF-'


class TestCronWindowSelection:

    def test_fuera_de_ventana_se_excluye_del_analisis(self, client, base, with_sets):
        """La query del engine (is_active + set en ventana) debe excluir los
        prompts de Black Friday fuera de temporada, sin tocar is_active."""
        from datetime import timezone
        from database import get_db_connection
        from services.llm_monitoring.prompt_sets import get_inactive_set_names, is_window_active

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT prompt_sets FROM llm_monitoring_projects WHERE id = %s",
                    (PROJECT_ID,))
        cfg = cur.fetchone()['prompt_sets']

        inactive = get_inactive_set_names(cfg)
        bf_in_window = is_window_active({'start': '11-15', 'end': '12-02'})
        if bf_in_window:
            assert 'Black Friday' not in inactive  # test corriendo en temporada BF
        else:
            assert inactive == ['Black Friday']

        cur.execute("""
            SELECT COUNT(*) AS c FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
              AND (prompt_set IS NULL OR NOT (prompt_set = ANY(%s)))
        """, (PROJECT_ID, inactive or ['']))
        analyzable = cur.fetchone()['c']
        cur.execute("""
            SELECT COUNT(*) AS c FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE AND prompt_set = ANY(%s)
        """, (PROJECT_ID, inactive or ['']))
        excluded = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM llm_monitoring_queries WHERE project_id = %s AND is_active = TRUE",
                    (PROJECT_ID,))
        total = cur.fetchone()['c']
        conn.close()
        assert analyzable + excluded == total


class TestGlobalFilterBarDimensions:
    """Filtros branded y llms de la barra global (encima de set/clusters)."""

    def test_llms_subset_estrecha_los_providers(self, client, base, with_sets):
        r = client.get(f'{base}/metrics?days=30&llms=google')
        assert r.status_code == 200
        providers = {s['llm_provider'] for s in r.get_json()['snapshots']}
        assert providers and providers <= {'google'}

    def test_llms_desconocido_se_ignora(self, client, base, with_sets):
        r = client.get(f'{base}/metrics?days=30&llms=inventado')
        assert r.status_code == 200
        # Con el filtro roto se enseña lo habilitado, no un dashboard vacío
        assert len(r.get_json()['snapshots']) > 0

    def test_llms_compone_con_set(self, client, base, with_sets):
        r = client.get(f'{base}/metrics?days=30&prompt_set=core&llms=google')
        assert r.status_code == 200
        providers = {s['llm_provider'] for s in r.get_json()['snapshots']}
        assert providers <= {'google'}
        # camino pseudo: cada fila agrega solo prompts del subconjunto
        assert all(s['total_queries'] >= 1 for s in r.get_json()['snapshots'])

    def test_branded_particiona_los_prompts(self, client, base, with_sets):
        total = len(client.get(f'{base}/queries').get_json()['queries'])
        branded = len(client.get(f'{base}/queries?branded=branded').get_json()['queries'])
        non_branded = len(client.get(f'{base}/queries?branded=non_branded').get_json()['queries'])
        assert branded + non_branded == total

    @pytest.mark.parametrize('path', [
        'metrics?days=30&branded=non_branded',
        'share-of-voice-history?days=30&branded=non_branded',
        'comparison?days=30&branded=non_branded',
        'urls-ranking?days=30&branded=non_branded',
        'responses?days=30&branded=non_branded',
        'clusters/metrics?days=30&branded=non_branded',
    ])
    def test_endpoints_aceptan_branded(self, client, base, with_sets, path):
        r = client.get(f'{base}/{path}')
        assert r.status_code == 200, f'{path} → {r.status_code}'

    def test_export_excel_con_todas_las_dimensiones(self, client, base, with_sets):
        r = client.get(f'{base}/export/excel?days=30&prompt_set=core&branded=non_branded&llms=google,openai')
        assert r.status_code == 200
        assert 'spreadsheet' in r.headers.get('Content-Type', '')

    def test_export_pdf_con_todas_las_dimensiones(self, client, base, with_sets):
        r = client.get(f'{base}/export/pdf?days=30&metric=weighted&branded=non_branded&llms=google')
        assert r.status_code == 200
        assert r.data[:5] == b'%PDF-'

    def test_prompts_concretos_filtran_todo(self, client, base, with_sets):
        rows = client.get(f'{base}/queries').get_json()['queries']
        assert len(rows) >= 2
        chosen = rows[0]['id']
        r = client.get(f'{base}/queries?prompts={chosen}')
        filtered = r.get_json()['queries']
        assert [q['id'] for q in filtered] == [chosen]
        # métricas con el subconjunto: cada fila pseudo agrega 1 solo prompt
        m = client.get(f'{base}/metrics?days=30&prompts={chosen}').get_json()
        assert all(s['total_queries'] == 1 for s in m['snapshots'])
        # ids inexistentes → dashboard vacío pero sin error
        r = client.get(f'{base}/metrics?days=30&prompts=99999998')
        assert r.status_code == 200 and r.get_json()['snapshots'] == []

    def test_sentiment_filtra_como_subconjunto_de_prompts(self, client, base, with_sets):
        """Semántica: prompts con ≥1 respuesta de ese sentimiento en el rango.
        La unión de los tres sentimientos no puede superar el total, y las
        métricas del subconjunto deben responder 200 con datos coherentes."""
        total = len(client.get(f'{base}/queries?days=90').get_json()['queries'])
        counts = {}
        for s in ('positive', 'neutral', 'negative'):
            rows = client.get(f'{base}/queries?days=90&sentiment={s}').get_json()['queries']
            counts[s] = len(rows)
            assert counts[s] <= total
        assert any(c > 0 for c in counts.values()), f'sin datos de sentimiento: {counts}'
        r = client.get(f'{base}/metrics?days=90&sentiment=neutral')
        assert r.status_code == 200

    def test_sentiment_en_responses_baja_a_nivel_respuesta(self, client, base, with_sets):
        r = client.get(f'{base}/responses?days=90&sentiment=neutral')
        assert r.status_code == 200
        rows = r.get_json()['responses']
        assert all(resp['sentiment'] == 'neutral' for resp in rows)

    def test_metrics_expone_sentiment_counts(self, client, base, with_sets):
        d = client.get(f'{base}/metrics?days=30').get_json()
        assert d['snapshots'], 'sin snapshots'
        for s in d['snapshots']:
            sc = s.get('sentiment_counts')
            assert sc is not None and set(sc) == {'positive', 'neutral', 'negative'}
        # También en el camino filtrado (pseudo-snapshots)
        d = client.get(f'{base}/metrics?days=30&prompt_set=core').get_json()
        for s in d['snapshots']:
            assert 'sentiment_counts' in s

    def test_prompts_compone_con_llms(self, client, base, with_sets):
        rows = client.get(f'{base}/queries').get_json()['queries']
        chosen = rows[0]['id']
        m = client.get(f'{base}/metrics?days=30&prompts={chosen}&llms=google').get_json()
        providers = {s['llm_provider'] for s in m['snapshots']}
        assert providers <= {'google'}


class TestDeletionSafety:

    def test_borrar_sets_devuelve_prompts_a_core_sin_perderlos(self, client, base, with_sets):
        before = len(client.get(f'{base}/queries').get_json()['queries'])
        r = client.put(f'{base}/sets', json={'sets_config': {'enabled': False, 'sets': []}})
        assert r.status_code == 200
        assert r.get_json()['reassigned_to_core'] >= 1
        after_rows = client.get(f'{base}/queries').get_json()['queries']
        assert len(after_rows) == before  # ningún prompt borrado
        assert all(not q.get('prompt_set') for q in after_rows)
