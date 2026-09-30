"""Helpers de informes de LLM Monitoring: filtros, métricas por prompt, branded,
modelos, fan-out y contenido.

Sacados tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros
gigantes). Los usan las rutas y las exportaciones (llm_monitoring_export_excel.py,
llm_monitoring_export_pdf.py). llm_monitoring_routes los vuelve a exponer con los
mismos nombres, así que `llm_monitoring_routes._parse_report_filters` sigue valiendo.
Este módulo no importa el de rutas.
"""

import json
import logging
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse

from services.llm_monitoring import prompt_sets as prompt_sets_lib
from services.llm_monitoring import url_content_analyzer
from services.llm_monitoring.fanout_stats import collect_fanout_metrics
from services.llm_providers.base_provider import DEFAULT_MODELS
from services.llm_providers.web_search import is_search_enabled

logger = logging.getLogger(__name__)

_VALID_HOST_RE = re.compile(r'[a-z0-9.-]+')


def _normalize_days_param(raw_days, default: int = 30, min_days: int = 1, max_days: int = 365) -> int:
    """
    Normaliza el parámetro days para evitar rangos no válidos o excesivos.
    """
    try:
        if raw_days is None or raw_days == '':
            return default
        days = int(raw_days)
    except (TypeError, ValueError):
        return default

    if days < min_days:
        return min_days
    if days > max_days:
        return max_days
    return days


def _remove_accents(text):
    """Remove accents for tolerant matching (e.g. 'café' matches 'cafe')."""
    nfkd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def classify_query_branded(query_text, brand_keywords):
    """
    Returns True if query_text contains any brand keyword.
    Uses case-insensitive, accent-insensitive, word-boundary matching.
    """
    if not brand_keywords or not query_text:
        return False
    text_lower = query_text.lower()
    text_no_accents = _remove_accents(text_lower)
    for kw in brand_keywords:
        kw_lower = kw.lower()
        kw_no_accents = _remove_accents(kw_lower)
        for pattern_text, text_to_search in [(kw_lower, text_lower), (kw_no_accents, text_no_accents)]:
            try:
                if re.search(r'\b' + re.escape(pattern_text) + r'\b', text_to_search, re.IGNORECASE):
                    return True
            except re.error:
                if pattern_text in text_to_search:
                    return True
    return False


def _compute_branded_metrics(results, brand_keywords):
    """
    Splits results into branded/non-branded and computes metrics for each.
    Each result must have: query_text, brand_mentioned, position_in_list, competitors_mentioned.
    Returns dict with 'branded' and 'non_branded' metric blocks.
    """
    branded = []
    non_branded = []
    for r in results:
        if classify_query_branded(r.get('query_text', ''), brand_keywords):
            branded.append(r)
        else:
            non_branded.append(r)

    def compute(subset, label):
        if not subset:
            return {
                'label': label,
                'total_queries': 0,
                'total_results': 0,
                'total_mentions': 0,
                'mention_rate': 0.0,
                'share_of_voice': 0.0,
                'avg_position': None
            }
        unique_queries = len(set(r.get('query_text', '') for r in subset))
        total = len(subset)
        mentions = sum(1 for r in subset if r.get('brand_mentioned'))
        mention_rate = round((mentions / total) * 100, 1) if total > 0 else 0.0

        # SOV: brand / (brand + competitors)
        total_comp = 0
        for r in subset:
            cm = r.get('competitors_mentioned')
            if cm and isinstance(cm, dict):
                total_comp += sum(cm.values())
            elif cm and isinstance(cm, str):
                try:
                    parsed = json.loads(cm)
                    total_comp += sum(parsed.values()) if isinstance(parsed, dict) else 0
                except (json.JSONDecodeError, TypeError):
                    pass
        total_all = mentions + total_comp
        sov = round((mentions / total_all) * 100, 1) if total_all > 0 else 0.0

        positions = [r['position_in_list'] for r in subset
                     if r.get('position_in_list') is not None]
        avg_pos = round(sum(positions) / len(positions), 1) if positions else None

        return {
            'label': label,
            'total_queries': unique_queries,
            'total_results': total,
            'total_mentions': mentions,
            'mention_rate': mention_rate,
            'share_of_voice': sov,
            'avg_position': avg_pos
        }

    # Per-LLM breakdown for chart rendering
    def per_llm_breakdown(subset):
        llm_groups = {}
        for r in subset:
            prov = r.get('llm_provider', 'unknown')
            if prov not in llm_groups:
                llm_groups[prov] = {'total': 0, 'mentions': 0}
            llm_groups[prov]['total'] += 1
            if r.get('brand_mentioned'):
                llm_groups[prov]['mentions'] += 1
        return {
            prov: round((d['mentions'] / d['total']) * 100, 1) if d['total'] > 0 else 0.0
            for prov, d in llm_groups.items()
        }

    return {
        'branded_metrics': compute(branded, 'Branded'),
        'non_branded_metrics': compute(non_branded, 'Non-Branded'),
        'branded_by_llm': per_llm_breakdown(branded),
        'non_branded_by_llm': per_llm_breakdown(non_branded)
    }


def _calculate_trend(current, previous, has_previous_data):
    """
    Calcula tendencia: direction (up/down/stable) y change (%).
    Si no hay histórico suficiente en el período anterior, devuelve None.
    Reutilizable desde múltiples endpoints (/detail, /metrics, /comparison, exports).
    """
    if not has_previous_data:
        return None

    if previous == 0:
        if current > 0:
            return {'direction': 'up', 'change': 100, 'previous': 0}
        return {'direction': 'stable', 'change': 0, 'previous': 0}

    change = ((current - previous) / previous) * 100

    # Considerar "stable" si el cambio es menor al 2%
    if abs(change) < 2:
        direction = 'stable'
    else:
        direction = 'up' if change > 0 else 'down'

    return {
        'direction': direction,
        'change': round(abs(change), 1),
        'previous': round(previous, 1)
    }


def _weight_for_position(pos):
    """
    Pondera una mención según su posición en la lista de respuesta del LLM.
    Las primeras posiciones pesan más en el cálculo de Share of Voice.
    Reutilizable desde /clusters/metrics y /queries (SOV por cluster y por prompt).
    """
    if pos is None:
        return 1.0
    if pos <= 3:
        return 2.0
    if pos <= 5:
        return 1.5
    if pos <= 10:
        return 1.2
    return 0.8


def _extract_source_host(raw_url):
    """
    Host normalizado de una URL citada por un LLM: sin esquema, sin www, sin
    puerto y en minúsculas. Devuelve '' si no se puede extraer.

    No basta con urlparse(url).netloc: las sources llegan de la respuesta de un
    LLM y muchas vienen sin protocolo ("example.com/guia"), en cuyo caso netloc
    es vacío y el dominio se perdería en silencio.

    Además filtra el host a los caracteres que un hostname admite. Es la
    frontera de confianza: este valor acaba interpolado en HTML y en URLs del
    cliente, y urlparse NO sanea (acepta comillas en el host sin rechistar).
    """
    raw_value = str(raw_url or '').strip()
    if not raw_value:
        return ''
    if not raw_value.startswith(('http://', 'https://')):
        raw_value = f"https://{raw_value}"
    try:
        parsed = urlparse(raw_value)
    except Exception:
        return ''
    host = (parsed.netloc or parsed.path or '').split('/')[0].split(':')[0].strip().lower()
    if host.startswith('www.'):
        host = host[4:]
    # Un hostname legítimo solo lleva letras, dígitos, punto y guion.
    if host and not _VALID_HOST_RE.fullmatch(host):
        return ''
    return host


_PROMPT_METRICS_SQL = """
    SELECT
        r.query_id,
        r.brand_mentioned,
        r.position_in_list,
        r.competitors_mentioned,
        r.sentiment,
        r.sentiment_score,
        r.sources
    FROM llm_monitoring_results r
    WHERE r.project_id = %s
        AND r.query_id = ANY(%s)
        AND r.analysis_date >= %s
        AND r.analysis_date <= %s
        {llm_filter}
"""


def collect_prompt_metrics(cur, project_id, query_ids, start_date, end_date, enabled_llms=None):
    """
    Share of Voice, sentimiento y top-3 de dominios POR PROMPT en el período.

    Fuente única para la tabla de prompts del panel y para la hoja equivalente
    del Excel: si cada uno lo calculase por su cuenta, el informe descargado
    acabaría diciendo cifras distintas de las que el usuario tiene en pantalla.

    A diferencia de `mentions_by_query` (solo el resultado más reciente por LLM),
    aquí entran TODOS los resultados del período, para que los agregados
    reflejen la ventana completa que muestra el panel.

    El SoV es siempre el PONDERADO por posición: es el que la tabla del panel
    enseña en su columna "SOV %".

    Devuelve {query_id: {'share_of_voice', 'sentiment': {...}, 'top_domains': [...]}}
    para los prompts con datos; los que no tienen resultados no aparecen (usar
    `empty_prompt_metrics()` para ellos).
    """
    if not query_ids:
        return {}

    sql = _PROMPT_METRICS_SQL.format(
        llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms else ""
    )
    # project_id primero por el índice: el UNIQUE de la tabla es
    # (project_id, query_id, llm_provider, analysis_date), así que sin este
    # filtro la consulta no puede usarlo y degenera en un scan completo.
    params = [project_id, list(query_ids), start_date, end_date]
    if enabled_llms:
        params.append(enabled_llms)
    cur.execute(sql, params)

    buckets = {}
    for row in cur.fetchall():
        bucket = buckets.setdefault(row['query_id'], {
            'weighted_brand': 0.0,
            'weighted_competitors': 0.0,
            'positive': 0,
            'neutral': 0,
            'negative': 0,
            'sentiment_scores': [],
            'domain_mentions': {}
        })
        weight = _weight_for_position(row['position_in_list'])

        if row['brand_mentioned']:
            bucket['weighted_brand'] += weight

        competitors = _as_json(row['competitors_mentioned'], {})
        if isinstance(competitors, dict):
            for _comp, count in competitors.items():
                try:
                    count_int = int(count)
                except (TypeError, ValueError):
                    continue
                if count_int > 0:
                    bucket['weighted_competitors'] += weight

        sentiment = row['sentiment']
        if sentiment in ('positive', 'neutral', 'negative'):
            bucket[sentiment] += 1
        if row['sentiment_score'] is not None:
            bucket['sentiment_scores'].append(float(row['sentiment_score']))

        for source in _as_json(row['sources'], []) or []:
            if not isinstance(source, dict):
                continue
            host = _extract_source_host(source.get('url'))
            if not host:
                continue
            bucket['domain_mentions'][host] = bucket['domain_mentions'].get(host, 0) + 1

    return {qid: _summarize_prompt_bucket(b) for qid, b in buckets.items()}


def empty_prompt_metrics():
    """Métricas de un prompt sin ningún resultado en el período."""
    return {
        'share_of_voice': None,
        'sentiment': {'label': None, 'score': None,
                      'counts': {'positive': 0, 'neutral': 0, 'negative': 0}},
        'top_domains': []
    }


def _summarize_prompt_bucket(bucket):
    weighted_total = bucket['weighted_brand'] + bucket['weighted_competitors']
    sov = round((bucket['weighted_brand'] / weighted_total) * 100, 1) if weighted_total > 0 else None

    counts = {k: bucket[k] for k in ('positive', 'neutral', 'negative')}
    if sum(counts.values()) == 0:
        label = None
        score = None
    else:
        label = max(counts, key=counts.get)
        scores = bucket['sentiment_scores']
        score = round(sum(scores) / len(scores), 2) if scores else None

    top_domains = sorted(bucket['domain_mentions'].items(),
                         key=lambda item: item[1], reverse=True)[:3]

    return {
        'share_of_voice': sov,
        'sentiment': {'label': label, 'score': score, 'counts': counts},
        'top_domains': [{'domain': d, 'mentions': c} for d, c in top_domains]
    }


# Etiquetas de oportunidad del análisis de contenido. Copian literalmente los
# badges del panel (llm-monitoring-url-content.js) para que el informe use el
# mismo vocabulario que el usuario ve en pantalla.
_OPPORTUNITY_LABELS = {
    'mentioned': "You're mentioned",
    'quick_win': 'Quick Win',
    'competitor_page': 'Competitor site',
    'no_mentions': 'No brands',
    None: 'No brands',
}


# Una sola fuente para los modelos por defecto (la usan también los providers)
MODEL_FALLBACKS = DEFAULT_MODELS


def fetch_current_models(cur):
    """
    Modelos vigentes por proveedor, con recurso a los valores por defecto.

    Fuente única para el modal "Models" del panel y para la portada del PDF: si
    cada uno consultase por su cuenta acabarían enseñando modelos distintos.

    Tolera que falten `knowledge_cutoff`/`knowledge_cutoff_date`: son columnas
    que añade scripts/migrations/migrate_llm_model_discovery_v2.py y que en entornos sin migrar no
    existen. El endpoint del panel ya sobrevivía a eso por su try/except global,
    pero el PDF no, y la descarga entera fallaba con un 500.
    """
    models = {}
    for columns in ("llm_provider, model_id, model_display_name, "
                    "knowledge_cutoff, knowledge_cutoff_date",
                    "llm_provider, model_id, model_display_name"):
        try:
            cur.execute(f"""
                SELECT {columns}
                FROM llm_model_registry
                WHERE is_current = TRUE AND is_available = TRUE
                ORDER BY llm_provider
            """)
            rows = cur.fetchall()
            break
        except Exception:
            # La transacción queda abortada tras un error de SQL: hay que
            # revertirla antes de poder lanzar la consulta de repuesto.
            try:
                cur.connection.rollback()
            except Exception:
                pass
            rows = None
    if rows is None:
        logger.warning("No se pudo leer llm_model_registry; se usan los modelos por defecto.")
        rows = []

    for m in rows:
        cutoff_date = m.get('knowledge_cutoff_date')
        models[m['llm_provider']] = {
            'model_id': m['model_id'],
            'display_name': m['model_display_name'] or m['model_id'],
            'knowledge_cutoff': m.get('knowledge_cutoff'),
            'knowledge_cutoff_date': cutoff_date.isoformat() if cutoff_date else None,
        }

    for provider, fallback in MODEL_FALLBACKS.items():
        models.setdefault(provider, dict(fallback))

    return models, bool(rows)


def _safe_fanout_metrics(cur, project, start_date, end_date, enabled_llms, query_ids):
    """
    Métricas de fan-out para las exportaciones. None si el proyecto no tiene la búsqueda
    web activada (el Excel y el PDF quedan igual que siempre) o si falla la consulta
    (una exportación nunca debe romperse por esta sección).
    """
    if not is_search_enabled(project.get('search_mode')):
        return None
    try:
        metrics = collect_fanout_metrics(cur, project, start_date=start_date, end_date=end_date,
                                         enabled_llms=enabled_llms, query_ids=query_ids)
        return metrics if metrics.get('enabled') else None
    except Exception as exc:
        logger.warning(f"⚠️ Could not compute fan-out for export of project {project.get('id')}: {exc}")
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return None


def _safe_content_overview(project_id, days):
    """
    Análisis de contenido del Top de URLs, o un vacío si no se puede leer.

    Los exports no deben caerse porque este módulo falle: es una función
    opcional del panel y el resto del informe sigue siendo válido sin ella.
    """
    try:
        overview = url_content_analyzer.get_analysis_overview(project_id, days=days)
        return overview if overview.get('success') else {}
    except Exception as e:
        logger.warning(f"No se pudo incluir el análisis de contenido en el export: {e}")
        return {}


def round_half_up(value, decimals=1):
    """
    Redondea como lo hace Postgres (mitad hacia ARRIBA), no como Python.

    `round()` de Python usa banker's rounding (mitad al par): round(3.25, 1)
    devuelve 3.2, mientras ROUND(3.25, 1) en Postgres devuelve 3.3. El panel
    redondea en SQL y el Excel en Python, así que la misma posición media salía
    3.3 en pantalla y 3.2 en la descarga.
    """
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(float(value))).quantize(quantum, rounding=ROUND_HALF_UP))


def _as_json(value, default):
    """Columna JSONB que psycopg puede entregar ya deserializada o como texto."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value


def _normalize_cluster_name(name):
    """Trim + compact whitespace. Returns empty string if invalid."""
    if not name:
        return ''
    trimmed = re.sub(r'\s+', ' ', str(name)).strip()
    # Hard cap to avoid absurd names
    return trimmed[:80]


# ─────────────────────────────────────────────────────────────────
# Filtro global del informe (barra de filtros del dashboard)
# Query params compartidos por todos los endpoints de datos:
#   prompt_set=core | <nombre de set>     (ausente = sin filtro, legacy)
#   clusters=Nombre1,Nombre2              (ausente = todos)
#   branded=branded | non_branded         (ausente = todos)
#   llms=openai,google                    (ausente = los habilitados)
# Los filtros que definen un SUBCONJUNTO DE PROMPTS (set, clusters,
# branded) se resuelven a una lista de query_ids; los endpoints que leen
# snapshots preagregados cambian entonces a pseudo-snapshots calculados
# desde results (los snapshots reales agregan TODOS los prompts y no
# pueden filtrarse a posteriori). El filtro de LLMs estrecha la lista de
# providers y funciona igual en ambos caminos.
# ─────────────────────────────────────────────────────────────────

_REPORT_VALID_LLMS = ('openai', 'anthropic', 'google', 'perplexity')


class ReportFilters:
    """Filtro global parseado. prompt_subset_active == True si algún filtro
    exige resolver query_ids (set/clusters/branded/prompts/sentiment)."""

    __slots__ = ('set_filter', 'clusters', 'branded', 'llms', 'prompt_ids', 'sentiment')

    def __init__(self, set_filter=None, clusters=None, branded=None, llms=None,
                 prompt_ids=None, sentiment=None):
        self.set_filter = set_filter
        self.clusters = clusters
        self.branded = branded
        self.llms = llms
        self.prompt_ids = prompt_ids
        self.sentiment = sentiment

    @property
    def prompt_subset_active(self):
        return bool(self.set_filter or self.clusters or self.branded
                    or self.prompt_ids or self.sentiment)


def _parse_report_filters(args):
    """Lee el filtro global del query string. Devuelve ReportFilters."""
    raw_set = (args.get('prompt_set') or '').strip()
    set_filter = None
    if raw_set:
        if raw_set.lower() in prompt_sets_lib.RESERVED_CORE_NAMES:
            set_filter = 'core'
        else:
            set_filter = prompt_sets_lib.normalize_set_name(raw_set) or None

    raw_clusters = (args.get('clusters') or '').strip()
    clusters = None
    if raw_clusters:
        clusters = [
            _normalize_cluster_name(c) for c in raw_clusters.split(',')
            if _normalize_cluster_name(c)
        ] or None

    raw_branded = (args.get('branded') or '').strip().lower()
    branded = raw_branded if raw_branded in ('branded', 'non_branded') else None

    raw_llms = (args.get('llms') or '').strip().lower()
    llms = None
    if raw_llms:
        llms = [l.strip() for l in raw_llms.split(',') if l.strip() in _REPORT_VALID_LLMS] or None

    # Prompts concretos (ids). Cap defensivo: nadie selecciona a mano miles.
    raw_prompts = (args.get('prompts') or '').strip()
    prompt_ids = None
    if raw_prompts:
        prompt_ids = [
            int(p) for p in raw_prompts.split(',')[:500] if p.strip().isdigit()
        ] or None

    raw_sentiment = (args.get('sentiment') or '').strip().lower()
    sentiment = raw_sentiment if raw_sentiment in ('positive', 'neutral', 'negative') else None

    return ReportFilters(set_filter, clusters, branded, llms, prompt_ids, sentiment)


def _report_filter_conditions(set_filter, clusters, alias='q'):
    """Condiciones SQL (lista) + params para set/clusters sobre llm_monitoring_queries."""
    conds, params = [], []
    if set_filter == 'core':
        conds.append(f"{alias}.prompt_set IS NULL")
    elif set_filter:
        conds.append(f"LOWER({alias}.prompt_set) = LOWER(%s)")
        params.append(set_filter)
    if clusters:
        conds.append(f"LOWER({alias}.topic_cluster) = ANY(%s)")
        params.append([c.lower() for c in clusters])
    return conds, params


def _narrow_llms(enabled_llms, report_filters):
    """
    Estrecha la lista de providers al subconjunto pedido por el filtro global.

    La intersección con los habilitados del proyecto es la autoridad: pedir un
    LLM no habilitado no lo resucita. Intersección vacía → se ignora el filtro
    (equivale a 'ninguno válido': mejor enseñar lo habilitado que un dashboard
    en blanco por un parámetro roto).
    """
    if not report_filters or not report_filters.llms:
        return enabled_llms
    base = enabled_llms or list(_REPORT_VALID_LLMS)
    narrowed = [l for l in base if l in report_filters.llms]
    return narrowed or enabled_llms


def _resolve_filtered_query_ids(cur, project_id, report_filters, include_clusters=True,
                                start_date=None, end_date=None):
    """
    IDs de queries del proyecto que pasan el filtro global (set + clusters +
    branded + prompts + sentiment). branded NO es una columna: se clasifica en
    Python con las brand_keywords del proyecto (classify_query_branded), así
    que el resolver trae los textos y filtra aquí.

    sentiment usa semántica de SUBCONJUNTO DE PROMPTS: "prompts con al menos
    una respuesta de ese sentimiento en el rango" (start/end_date del
    endpoint). Filtrar respuestas individuales rompería los denominadores
    (mention rate ~100% por construcción); así todas las métricas siguen
    siendo verdad sobre los prompts afectados. El Inspector aplica ADEMÁS el
    filtro a nivel de respuesta por su cuenta.

    include_clusters=False para endpoints que ya desglosan por cluster
    (/clusters/metrics y las hojas de clusters de los exports).

    Returns:
        None si no hay filtro de subconjunto activo (camino legacy),
        lista de IDs (posiblemente vacía) si lo hay.
    """
    clusters = report_filters.clusters if include_clusters else None
    if not report_filters.set_filter and not clusters \
            and not report_filters.branded and not report_filters.prompt_ids \
            and not report_filters.sentiment:
        return None

    conds, params = _report_filter_conditions(report_filters.set_filter, clusters, alias='q')
    if report_filters.prompt_ids:
        conds.append("q.id = ANY(%s)")
        params.append(report_filters.prompt_ids)
    if report_filters.sentiment:
        sentiment_sql = ("SELECT 1 FROM llm_monitoring_results r "
                         "WHERE r.query_id = q.id AND r.sentiment = %s")
        sentiment_params = [report_filters.sentiment]
        if start_date is not None:
            sentiment_sql += " AND r.analysis_date >= %s"
            sentiment_params.append(start_date)
        if end_date is not None:
            sentiment_sql += " AND r.analysis_date <= %s"
            sentiment_params.append(end_date)
        conds.append(f"EXISTS ({sentiment_sql})")
        params.extend(sentiment_params)
    sql = "SELECT q.id, q.query_text FROM llm_monitoring_queries q WHERE q.project_id = %s"
    if conds:
        sql += " AND " + " AND ".join(conds)
    cur.execute(sql, [project_id] + params)
    rows = cur.fetchall()

    if report_filters.branded:
        cur.execute(
            "SELECT brand_keywords FROM llm_monitoring_projects WHERE id = %s",
            (project_id,)
        )
        project_row = cur.fetchone() or {}
        brand_keywords = project_row.get('brand_keywords') or []
        want_branded = report_filters.branded == 'branded'
        rows = [
            r for r in rows
            if classify_query_branded(r.get('query_text', '') or '', brand_keywords) == want_branded
        ]

    return [r['id'] for r in rows]


def _report_view_label(report_filters):
    """
    Etiqueta legible del filtro activo para las cabeceras de Excel/PDF.
    Un documento filtrado que circule sin esta línea diría cifras parciales
    sin explicación.
    """
    parts = []
    if report_filters.set_filter:
        parts.append(
            'Set: Core' if report_filters.set_filter == 'core'
            else f'Set: {report_filters.set_filter}'
        )
    if report_filters.clusters:
        parts.append(f"Clusters: {', '.join(report_filters.clusters)}")
    if report_filters.branded:
        parts.append('Branded prompts only' if report_filters.branded == 'branded'
                     else 'Non-branded prompts only')
    if report_filters.llms:
        parts.append('LLMs: ' + ', '.join(l.capitalize() for l in report_filters.llms))
    if report_filters.prompt_ids:
        parts.append(f'Prompts: {len(report_filters.prompt_ids)} selected')
    if report_filters.sentiment:
        parts.append(f'Sentiment: prompts with {report_filters.sentiment} responses')
    return ' · '.join(parts) if parts else 'All prompts'
