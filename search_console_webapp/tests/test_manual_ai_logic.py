"""
Tests de caracterización de la LÓGICA DE NEGOCIO de Manual AI.

A diferencia de `test_manual_ai_contract.py` (que congela el cableado/rutas),
aquí se congela el COMPORTAMIENTO OBSERVABLE de las funciones puras críticas:

  - `services.ai_analysis.detect_ai_overview_elements`: corazón del sistema.
    Detección de AI Overview, estado "collapsed", impact_score y detección del
    dominio como fuente.
  - `manual_ai.utils.helpers.extract_domain_from_url`: normalización de dominios.
  - `manual_ai.utils.country_utils.convert_iso_to_internal_country`: mapeo de país.

Son funciones puras → no tocan BD. `DATABASE_URL` se fija solo para que los
imports de módulos que la exigen en import-time no fallen.

Ejecutar:  python3 -m pytest tests/test_manual_ai_logic.py -q
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from services.ai_analysis import detect_ai_overview_elements  # noqa: E402
from manual_ai.utils.helpers import extract_domain_from_url  # noqa: E402
from manual_ai.utils.country_utils import convert_iso_to_internal_country  # noqa: E402


# ---------------------------------------------------------------------------
# detect_ai_overview_elements — ramas de detección
# ---------------------------------------------------------------------------

def test_aio_sin_datos_serp():
    """SERP vacío/None → no hay AIO y se reporta el error."""
    r = detect_ai_overview_elements(None)
    assert r['has_ai_overview'] is False
    assert r['debug_info'].get('error') == 'No SERP data'


def test_aio_sin_clave_ai_overview():
    """SERP sin la clave 'ai_overview' → no hay AIO."""
    r = detect_ai_overview_elements({'organic_results': []}, site_url='example.com')
    assert r['has_ai_overview'] is False
    assert r['debug_info'].get('ai_overview_found') is False
    assert 'available_keys' in r['debug_info']


def test_aio_con_error_en_payload():
    """ai_overview con 'error' → no se considera AIO válido."""
    r = detect_ai_overview_elements({'ai_overview': {'error': 'boom'}})
    assert r['has_ai_overview'] is False
    assert r['debug_info'].get('ai_overview_error') == 'boom'


def test_aio_collapsed_requiere_segunda_peticion():
    """AIO collapsed (page_token sin text_blocks/references) → existe pero pendiente."""
    serp = {'ai_overview': {'page_token': 'TOKEN123', 'serpapi_link': 'http://x'}}
    r = detect_ai_overview_elements(serp, site_url='example.com')
    assert r['has_ai_overview'] is True
    assert r['debug_info'].get('requires_additional_request') is True
    assert r['debug_info'].get('page_token') == 'TOKEN123'
    assert r['debug_info'].get('ai_overview_collapsed') is True


def test_aio_presente_impact_score_y_total_elements():
    """AIO con text_blocks: total_elements = nº bloques, impact_score = min(40*n,100)."""
    serp = {
        'ai_overview': {
            'text_blocks': [
                {'type': 'paragraph', 'snippet': 'foo'},
                {'type': 'paragraph', 'snippet': 'bar'},
            ],
            'references': [],
        }
    }
    r = detect_ai_overview_elements(serp)  # sin site_url → no se busca dominio
    assert r['has_ai_overview'] is True
    assert r['total_elements'] == 2
    assert r['elements_before_organic'] == 2
    # 40*2 = 80, sin dominio encontrado (no site_url) → sin bonus
    assert r['impact_score'] == 80
    assert r['domain_is_ai_source'] is False


def test_aio_impact_score_clamp_a_100():
    """Con muchos bloques el impact_score base se satura en 100 (sin site_url)."""
    serp = {'ai_overview': {'text_blocks': [{'snippet': 's'} for _ in range(5)], 'references': []}}
    r = detect_ai_overview_elements(serp)
    assert r['total_elements'] == 5
    assert r['impact_score'] == 100  # min(40*5, 100)


def test_aio_dominio_detectado_en_referencias_oficiales():
    """Dominio del proyecto citado como referencia oficial → fuente detectada en posición index+1."""
    serp = {
        'ai_overview': {
            'text_blocks': [{'type': 'paragraph', 'snippet': 'algo'}],
            'references': [
                {'index': 0, 'title': 'Otro', 'link': 'https://www.otrodominio.com/x'},
                {'index': 1, 'title': 'Mi marca', 'link': 'https://www.example.com/page'},
            ],
        }
    }
    r = detect_ai_overview_elements(serp, site_url='example.com')
    assert r['has_ai_overview'] is True
    assert r['domain_is_ai_source'] is True
    # Posición 1-based del índice de la referencia (index 1 → posición 2)
    assert r['domain_ai_source_position'] == 2
    assert r['debug_info'].get('detection_method') == 'official_references'
    # impact_score: 40*1 (1 bloque) + 20 (bonus dominio) = 60
    assert r['impact_score'] == 60


def test_aio_dominio_no_citado():
    """Si el dominio del proyecto no aparece, no es fuente del AIO."""
    serp = {
        'ai_overview': {
            'text_blocks': [{'type': 'paragraph', 'snippet': 'algo'}],
            'references': [{'index': 0, 'title': 'Otro', 'link': 'https://www.competidor.com/x'}],
        }
    }
    r = detect_ai_overview_elements(serp, site_url='example.com')
    assert r['has_ai_overview'] is True
    assert r['domain_is_ai_source'] is False
    assert r['domain_ai_source_position'] is None


# ---------------------------------------------------------------------------
# extract_domain_from_url — normalización de dominios
# ---------------------------------------------------------------------------

def test_extract_domain_casos():
    assert extract_domain_from_url('https://www.example.com/page') == 'example.com'
    assert extract_domain_from_url('http://subdomain.example.com') == 'subdomain.example.com'
    assert extract_domain_from_url('example.com') == 'example.com'
    assert extract_domain_from_url('WWW.EXAMPLE.COM') == 'example.com'
    assert extract_domain_from_url('https://example.com:8080/x') == 'example.com'
    assert extract_domain_from_url('') == ''
    assert extract_domain_from_url(None) == ''


# ---------------------------------------------------------------------------
# convert_iso_to_internal_country — mapeo de país
# ---------------------------------------------------------------------------

def test_country_iso2_a_interno():
    assert convert_iso_to_internal_country('ES') == 'esp'
    assert convert_iso_to_internal_country('US') == 'usa'
    assert convert_iso_to_internal_country('GB') == 'gbr'


def test_country_fallback_seguro():
    """Vacío, None o código desconocido → fallback 'esp' (nunca rompe)."""
    assert convert_iso_to_internal_country('') == 'esp'
    assert convert_iso_to_internal_country(None) == 'esp'
    assert convert_iso_to_internal_country('ZZ') == 'esp'
