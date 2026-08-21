"""
Tests UNITARIOS de prompt sets (núcleo/tendencia/estacionales) — sin BD.

Cubren las tres piezas puras de la feature:
1. services/llm_monitoring/prompt_sets.py — ventanas estacionales UTC
   (con wrap-around dic→ene), saneado de config y nombres reservados.
2. services/llm_monitoring/pseudo_snapshots.py — paridad matemática con
   snapshot.py::_create_snapshot (mention rate, SOV normal y ponderado,
   breakdowns, sentimiento). Si la matemática de una cambia, este test
   obliga a mirar la otra.
3. Helpers de filtro global de llm_monitoring_routes.py — parseo de
   query params y condiciones SQL.

Ejecutar:  python3 -m pytest tests/test_llm_prompt_sets.py -q
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

import pytest  # noqa: E402

from services.llm_monitoring.prompt_sets import (  # noqa: E402
    is_window_active,
    get_inactive_set_names,
    get_defined_set_names,
    sanitize_prompt_sets_config,
    parse_window,
    normalize_set_name,
    RESERVED_CORE_NAMES,
)
from services.llm_monitoring.pseudo_snapshots import (  # noqa: E402
    compute_snapshot_row,
    _weight_for_position,
)


def _utc(month, day):
    return datetime(2026, month, day, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════════
# 1. Ventanas estacionales
# ══════════════════════════════════════════════════════════════════

class TestSeasonalWindows:

    def test_ventana_normal_incluye_ambos_extremos(self):
        w = {'start': '11-15', 'end': '12-02'}
        assert is_window_active(w, _utc(11, 15))
        assert is_window_active(w, _utc(11, 20))
        assert is_window_active(w, _utc(12, 2))

    def test_ventana_normal_excluye_fuera(self):
        w = {'start': '11-15', 'end': '12-02'}
        assert not is_window_active(w, _utc(11, 14))
        assert not is_window_active(w, _utc(12, 3))
        assert not is_window_active(w, _utc(8, 20))

    def test_wrap_around_cruza_fin_de_ano(self):
        w = {'start': '12-20', 'end': '01-06'}
        assert is_window_active(w, _utc(12, 20))
        assert is_window_active(w, _utc(12, 25))
        assert is_window_active(w, _utc(1, 3))
        assert is_window_active(w, _utc(1, 6))
        assert not is_window_active(w, _utc(1, 7))
        assert not is_window_active(w, _utc(12, 19))
        assert not is_window_active(w, _utc(6, 15))

    def test_sin_ventana_siempre_activa(self):
        assert is_window_active(None)
        assert is_window_active({})

    def test_ventana_corrupta_no_silencia_el_set(self):
        # Mejor analizar de más que dejar de analizar por datos corruptos
        assert is_window_active({'start': 'xx', 'end': 'yy'})

    def test_inactive_sets_solo_los_fuera_de_ventana(self):
        cfg = {'enabled': True, 'sets': [
            {'name': 'Black Friday', 'window': {'start': '11-15', 'end': '12-02'}},
            {'name': 'Tendencias'},  # sin ventana: nunca inactivo
        ]}
        assert get_inactive_set_names(cfg, _utc(8, 20)) == ['Black Friday']
        assert get_inactive_set_names(cfg, _utc(11, 20)) == []

    def test_feature_deshabilitada_no_desactiva_nada(self):
        cfg = {'enabled': False, 'sets': [
            {'name': 'BF', 'window': {'start': '11-15', 'end': '12-02'}},
        ]}
        assert get_inactive_set_names(cfg, _utc(8, 20)) == []


# ══════════════════════════════════════════════════════════════════
# 2. Saneado de configuración
# ══════════════════════════════════════════════════════════════════

class TestConfigSanitize:

    def test_nombres_reservados_del_core_rechazados(self):
        for reserved in ('core', 'Núcleo', 'NUCLEO'):
            with pytest.raises(ValueError):
                sanitize_prompt_sets_config({'enabled': True, 'sets': [{'name': reserved}]})

    def test_ventana_malformada_rechazada(self):
        for bad in ({'start': '13-01', 'end': '11-30'},   # mes 13
                    {'start': '11-32', 'end': '12-01'},   # día 32
                    {'start': '11-15', 'end': ''},        # incompleta
                    {'start': 'foo', 'end': 'bar'}):
            with pytest.raises(ValueError):
                sanitize_prompt_sets_config(
                    {'enabled': True, 'sets': [{'name': 'BF', 'window': bad}]}
                )

    def test_config_valida_conserva_orden_y_ventanas(self):
        cfg, names = sanitize_prompt_sets_config({'enabled': True, 'sets': [
            {'name': 'Black Friday', 'window': {'start': '11-15', 'end': '12-02'}},
            {'name': 'Tendencias'},
        ]})
        assert names == ['Black Friday', 'Tendencias']
        assert cfg['enabled'] is True
        assert cfg['sets'][0]['window'] == {'start': '11-15', 'end': '12-02'}
        assert 'window' not in cfg['sets'][1]

    def test_duplicados_case_insensitive_colapsan(self):
        _, names = sanitize_prompt_sets_config({'enabled': True, 'sets': [
            {'name': 'Black Friday'}, {'name': 'black friday'}, {'name': 'Navidad'},
        ]})
        assert names == ['Black Friday', 'Navidad']

    def test_enabled_sin_sets_queda_deshabilitado(self):
        cfg, names = sanitize_prompt_sets_config({'enabled': True, 'sets': []})
        assert cfg['enabled'] is False and names == []

    def test_parse_window_vacia_es_none(self):
        assert parse_window(None) is None
        assert parse_window({}) is None
        assert parse_window({'start': '', 'end': ''}) is None

    def test_normalize_name_compacta_y_capa(self):
        assert normalize_set_name('  Black   Friday  ') == 'Black Friday'
        assert len(normalize_set_name('x' * 200)) == 80
        assert normalize_set_name(None) == ''

    def test_defined_names_ignora_basura(self):
        assert get_defined_set_names({'enabled': True, 'sets': [
            {'name': 'BF'}, {'sin_nombre': 1}, 'no-dict-valido'
        ]}) == ['BF']
        assert get_defined_set_names('{"enabled": true, "sets": [{"name": "X"}]}') == ['X']
        assert get_defined_set_names(None) == []


# ══════════════════════════════════════════════════════════════════
# 3. Pseudo-snapshots: paridad con snapshot.py::_create_snapshot
# ══════════════════════════════════════════════════════════════════

def _result(brand=False, pos=None, comps=None, sentiment='neutral',
            score=0.5, cost=0.001, tokens=100, rt=500):
    return {
        'brand_mentioned': brand,
        'position_in_list': pos,
        'competitors_mentioned': comps or {},
        'sentiment': sentiment,
        'sentiment_score': score,
        'cost_usd': cost,
        'tokens_used': tokens,
        'response_time_ms': rt,
    }


class TestPseudoSnapshotMath:

    def test_pesos_por_posicion_identicos_a_snapshot_real(self):
        # Tabla de snapshot.py::_calculate_weighted_mentions
        assert _weight_for_position(None) == 1.0
        assert _weight_for_position(1) == 2.0
        assert _weight_for_position(3) == 2.0
        assert _weight_for_position(4) == 1.5
        assert _weight_for_position(5) == 1.5
        assert _weight_for_position(6) == 1.2
        assert _weight_for_position(10) == 1.2
        assert _weight_for_position(11) == 0.8

    def test_mention_rate_y_sov_normal(self):
        rows = [
            _result(brand=True, pos=1, comps={'haribo': 2}),
            _result(brand=True, pos=4),
            _result(brand=False, comps={'haribo': 1, 'vidal': 3}),
            _result(brand=False),
        ]
        snap = compute_snapshot_row('2026-08-20', 'openai', rows)
        assert snap['total_queries'] == 4
        assert snap['total_mentions'] == 2
        assert snap['mention_rate'] == 50.0
        # SOV normal: 1 mención por query — marca 2, haribo 2, vidal 1
        assert snap['competitor_breakdown'] == {'haribo': 2, 'vidal': 1}
        assert snap['total_competitor_mentions'] == 3
        assert snap['share_of_voice'] == round(2 / 5 * 100, 2)

    def test_sov_ponderado_por_posicion(self):
        rows = [
            _result(brand=True, pos=1),                 # marca peso 2.0
            _result(brand=False, pos=2, comps={'haribo': 1}),  # haribo peso 2.0
            _result(brand=False, pos=12, comps={'haribo': 1}),  # haribo peso 0.8
        ]
        snap = compute_snapshot_row('2026-08-20', 'google', rows)
        assert snap['weighted_competitor_breakdown'] == {'haribo': 2.8}
        assert snap['weighted_share_of_voice'] == round(2.0 / 4.8 * 100, 2)

    def test_posiciones_mayores_de_30_son_falsos_positivos(self):
        rows = [
            _result(brand=True, pos=2),
            _result(brand=True, pos=45),  # excluida (año/canal detectado como posición)
        ]
        snap = compute_snapshot_row('2026-08-20', 'openai', rows)
        assert snap['avg_position'] == 2.0
        assert snap['appeared_in_top3'] == 1

    def test_sentimiento_y_costes(self):
        rows = [
            _result(sentiment='positive', score=0.9, cost=0.002, tokens=200, rt=400),
            _result(sentiment='negative', score=0.1, cost=0.001, tokens=100, rt=600),
        ]
        snap = compute_snapshot_row('2026-08-20', 'anthropic', rows)
        assert snap['positive_mentions'] == 1
        assert snap['negative_mentions'] == 1
        assert snap['avg_sentiment_score'] == 0.5
        assert snap['total_cost_usd'] == 0.003
        assert snap['total_tokens'] == 300
        assert snap['avg_response_time_ms'] == 500

    def test_competitors_mentioned_como_string_json(self):
        rows = [_result(comps='{"haribo": 2}')]
        snap = compute_snapshot_row('2026-08-20', 'openai', rows)
        assert snap['competitor_breakdown'] == {'haribo': 1}

    def test_sin_resultados_devuelve_none(self):
        assert compute_snapshot_row('2026-08-20', 'openai', []) is None


# ══════════════════════════════════════════════════════════════════
# 4. Helpers del filtro global (routes)
# ══════════════════════════════════════════════════════════════════

class TestReportFilterHelpers:

    @pytest.fixture(scope='class')
    def routes(self):
        import llm_monitoring_routes as m
        return m

    def test_parse_sin_params(self, routes):
        rf = routes._parse_report_filters({})
        assert rf.set_filter is None and rf.clusters is None
        assert rf.branded is None and rf.llms is None
        assert rf.prompt_subset_active is False

    def test_parse_core_y_alias_nucleo(self, routes):
        for alias in ('core', 'Core', 'núcleo', 'nucleo'):
            rf = routes._parse_report_filters({'prompt_set': alias})
            assert rf.set_filter == 'core'
            assert rf.prompt_subset_active is True

    def test_parse_set_con_nombre_y_clusters(self, routes):
        rf = routes._parse_report_filters({
            'prompt_set': ' Black  Friday ',
            'clusters': 'T1 · Cat, T2 · Otro ,,',
        })
        assert rf.set_filter == 'Black Friday'
        assert rf.clusters == ['T1 · Cat', 'T2 · Otro']

    def test_parse_branded(self, routes):
        assert routes._parse_report_filters({'branded': 'branded'}).branded == 'branded'
        assert routes._parse_report_filters({'branded': 'non_branded'}).branded == 'non_branded'
        # Valores inválidos se ignoran (no rompen el endpoint)
        assert routes._parse_report_filters({'branded': 'todo'}).branded is None
        assert routes._parse_report_filters({'branded': 'branded'}).prompt_subset_active is True

    def test_parse_llms_valida_contra_conocidos(self, routes):
        rf = routes._parse_report_filters({'llms': 'openai, google ,inventado'})
        assert rf.llms == ['openai', 'google']
        # Solo desconocidos → sin filtro (no un filtro vacío que apague todo)
        assert routes._parse_report_filters({'llms': 'inventado'}).llms is None
        # llms NO exige resolver query_ids
        assert routes._parse_report_filters({'llms': 'openai'}).prompt_subset_active is False

    def test_parse_prompts_ids(self, routes):
        rf = routes._parse_report_filters({'prompts': '12, 34,x,56'})
        assert rf.prompt_ids == [12, 34, 56]
        assert rf.prompt_subset_active is True
        # Vacío o basura → sin filtro
        assert routes._parse_report_filters({'prompts': 'a,b'}).prompt_ids is None
        assert routes._parse_report_filters({'prompts': ''}).prompt_ids is None

    def test_report_view_label_incluye_prompts(self, routes):
        RF = routes.ReportFilters
        label = routes._report_view_label(RF(branded='non_branded', prompt_ids=[1, 2, 3]))
        assert 'Non-branded prompts only' in label
        assert 'Prompts: 3 selected' in label
        assert routes._report_view_label(RF()) == 'All prompts'

    def test_narrow_llms(self, routes):
        RF = routes.ReportFilters
        enabled = ['openai', 'google', 'perplexity']
        # Sin filtro → intactos
        assert routes._narrow_llms(enabled, RF()) == enabled
        # Subconjunto válido
        assert routes._narrow_llms(enabled, RF(llms=['google'])) == ['google']
        # Un LLM no habilitado no se resucita
        assert routes._narrow_llms(enabled, RF(llms=['anthropic', 'google'])) == ['google']
        # Intersección vacía → se ignora el filtro (mejor todo que nada)
        assert routes._narrow_llms(enabled, RF(llms=['anthropic'])) == enabled

    def test_condiciones_sql_core(self, routes):
        conds, params = routes._report_filter_conditions('core', None)
        assert conds == ['q.prompt_set IS NULL'] and params == []

    def test_condiciones_sql_set_y_clusters(self, routes):
        conds, params = routes._report_filter_conditions('BF', ['C1', 'C2'], alias='x')
        assert conds[0] == 'LOWER(x.prompt_set) = LOWER(%s)'
        assert conds[1] == 'LOWER(x.topic_cluster) = ANY(%s)'
        assert params == ['BF', ['c1', 'c2']]

    def test_resolver_asignacion_core_y_desconocido(self, routes):
        cfg = {'enabled': True, 'sets': [{'name': 'Black Friday'}]}
        ok, val = routes._resolve_set_assignment(None, cfg)
        assert ok and val is None
        ok, val = routes._resolve_set_assignment('core', cfg)
        assert ok and val is None
        # Nombre canónico aunque llegue en otra caja
        ok, val = routes._resolve_set_assignment('black friday', cfg)
        assert ok and val == 'Black Friday'
        ok, err = routes._resolve_set_assignment('Inexistente', cfg)
        assert not ok and 'not defined' in err
