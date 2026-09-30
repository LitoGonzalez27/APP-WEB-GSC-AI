"""
admin_cost_panel.py — Agregación de costes reales de plataforma para el panel admin.

Fuentes de verdad:
  - LLM: llm_monitoring_results (tokens reales del proveedor + cost_usd congelado al
    precio de llm_model_registry en el momento de la llamada). 1 unidad = 1 prompt × 1 LLM.
  - SerpAPI: quota_usage_events + expansiones de Manual AI. Desde sep-2026 (ver
    SERP_BILLABLE_SOURCES) cuentan 'manual_ai' y 'ai_overview' (1 RU = 1 búsqueda por
    keyword; el middleware ya no registra esas búsquedas como 'serp_api'), 'ai_mode' y
    'serp_api' (vista de SERP). Además, cada expansión de un AIO plegado de Manual AI
    es otra búsqueda (manual_ai_results.ai_analysis_data->'aio_expansion').
  - SerpAPI /account: dato oficial del proveedor (plan, precio mensual, búsquedas
    usadas desde la última renovación, de toda la cuenta). Se usa para contrastar el
    conteo interno en el mismo ciclo y para derivar el coste real por búsqueda
    (plan_monthly_price / searches_per_month).

Config por entorno:
  SERPAPI_COST_PER_SEARCH_USD  — override del coste por búsqueda (si no, se deriva del plan)
  ADMIN_USD_EUR_RATE           — tipo de cambio para comparar costes USD con ingresos EUR (default 0.86)
"""

import os
import time
import logging
from datetime import date, timedelta

import requests
from flask import Blueprint, jsonify

from database import get_db_connection
from auth import admin_required

logger = logging.getLogger(__name__)

admin_costs_bp = Blueprint('admin_costs', __name__)

# Fuentes de quota_usage_events que representan búsquedas SerpAPI reales y facturables.
# Hasta sep-2026 solo contaban 'serp_api' y 'ai_mode', suponiendo que el middleware
# registraba como 'serp_api' las búsquedas de Manual AI y AI Overview; en producción
# nunca lo hizo (ENFORCE_QUOTAS=false) y el panel mostraba una fracción del gasto.
# Ahora 'serp_api' es solo la vista de SERP y cada módulo registra lo suyo (1 RU por
# keyword = 1 búsqueda). En staging hay eventos 'serp_api' antiguos que duplican
# análisis (ENFORCE_QUOTAS=true hasta sep-2026).
SERP_BILLABLE_SOURCES = ('serp_api', 'ai_mode', 'manual_ai', 'ai_overview')
# Fila extra de la tabla de atribución: las expansiones no son eventos de cuota.
FUENTE_EXPANSIONES = 'manual_ai · expansiones AIO'

# Búsquedas extra por expansión de un AI Overview plegado en Manual AI: cada intento
# es una búsqueda (engine google_ai_overview) y cada refetch, otra búsqueda completa.
# Se leen de manual_ai_results (1,7 GB en producción, sep-2026): siempre con filtro por
# analysis_date (tiene índice), nunca sobre todo el histórico. Límites conocidos: si se
# reanaliza una keyword el mismo día, la fila se sobrescribe y se pierden las expansiones
# del primer análisis; las expansiones de AI Overview (una por keyword plegada, unas
# pocas cientos al mes) no se guardan en ningún sitio y caen en "otros servicios".
_EXPANSIONES = ("COALESCE((r.ai_analysis_data->'aio_expansion'->>'attempts')::int, 0)"
                " + COALESCE((r.ai_analysis_data->'aio_expansion'->>'refetches')::int, 0)")

# Fallback si no hay override ni datos del plan (Developer: $75 / 5000 búsquedas).
DEFAULT_SERP_COST_PER_SEARCH = 0.015

# ---------------------------------------------------------------------------
# SerpAPI /account — dato oficial del proveedor, cacheado en memoria 10 min
# ---------------------------------------------------------------------------

_serpapi_account_cache = {'data': None, 'fetched_at': 0.0}
_SERPAPI_ACCOUNT_TTL = 600  # segundos


def inicio_ciclo_serpapi(account, hoy=None):
    """Primer día del ciclo de facturación de SerpAPI (renovación − 1 mes) o None.

    this_month_usage de SerpAPI cuenta desde la última renovación, no desde el día 1:
    para restarle lo de Clicandseo hay que contar lo nuestro en el mismo periodo.
    Aproximado: SerpAPI no da la hora de renovación y el día ancla se pierde en los
    meses cortos (renovar el 28-feb con ancla 30 da un ciclo desde el 28-ene).
    None si la fecha no encaja con un ciclo en curso (dato de cuenta viejo o raro)."""
    try:
        renovacion = date.fromisoformat(str((account or {}).get('plan_renewal_date'))[:10])
    except ValueError:
        return None
    anio, mes = (renovacion.year, renovacion.month - 1) if renovacion.month > 1 else (renovacion.year - 1, 12)
    inicio = None
    for dia in range(renovacion.day, 27, -1):  # 31-mar -> 28/29-feb
        try:
            inicio = date(anio, mes, dia)
            break
        except ValueError:
            continue
    inicio = inicio or date(anio, mes, renovacion.day)
    hoy = hoy or date.today()
    if renovacion < hoy or not (hoy - timedelta(days=32) <= inicio <= hoy):
        return None  # renovación ya pasada (dato de cuenta viejo) o ciclo que no ha empezado
    return inicio


def get_serpapi_account(force_refresh=False, dato_viejo_si_falla=True):
    """Info oficial de la cuenta SerpAPI (plan, precio, uso del ciclo). None si falla.

    Si la consulta falla devuelve el último dato bueno, salvo con
    dato_viejo_si_falla=False (el aviso de saldo necesita saber que falló)."""
    now = time.time()
    if (not force_refresh
            and _serpapi_account_cache['data'] is not None
            and now - _serpapi_account_cache['fetched_at'] < _SERPAPI_ACCOUNT_TTL):
        return _serpapi_account_cache['data']

    api_key = os.getenv('SERPAPI_KEY', '').strip()
    if not api_key:
        return None
    try:
        resp = requests.get('https://serpapi.com/account',
                            params={'api_key': api_key}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        account = {
            'plan_name': data.get('plan_name'),
            'plan_monthly_price': data.get('plan_monthly_price'),
            'searches_per_month': data.get('searches_per_month'),
            'this_month_usage': data.get('this_month_usage'),
            'plan_searches_left': data.get('plan_searches_left'),
            'extra_credits': data.get('extra_credits'),
            'total_searches_left': data.get('total_searches_left'),
            'plan_renewal_date': data.get('plan_renewal_date'),
            'account_status': data.get('account_status'),
        }
        _serpapi_account_cache['data'] = account
        _serpapi_account_cache['fetched_at'] = now
        return account
    except Exception as e:
        # Sin {e}: el mensaje de requests lleva la URL con la api_key.
        estado = getattr(getattr(e, 'response', None), 'status_code', None)
        logger.warning(f"No se pudo consultar SerpAPI /account: {type(e).__name__}"
                       + (f" (HTTP {estado})" if estado else ''))
        return _serpapi_account_cache['data'] if dato_viejo_si_falla else None


def get_serp_cost_per_search(account=None):
    """Coste real por búsqueda SerpAPI y de dónde sale ese número."""
    override = os.getenv('SERPAPI_COST_PER_SEARCH_USD', '').strip()
    if override:
        try:
            return float(override), 'env:SERPAPI_COST_PER_SEARCH_USD'
        except ValueError:
            pass
    if account and account.get('plan_monthly_price') and account.get('searches_per_month'):
        return (float(account['plan_monthly_price']) / float(account['searches_per_month']),
                f"plan {account.get('plan_name')} (${account['plan_monthly_price']}/mes ÷ {account['searches_per_month']} búsquedas)")
    return DEFAULT_SERP_COST_PER_SEARCH, 'fallback por defecto'


# ---------------------------------------------------------------------------
# Agregación principal
# ---------------------------------------------------------------------------

def _f(value):
    """Decimal/None → float redondeado (JSON-safe)."""
    return round(float(value or 0), 6)


def get_costs_dashboard():
    """Payload completo del dashboard de costes. Una sola conexión DB."""
    # Primero el dato oficial de SerpAPI: su "mes" es el ciclo de facturación y lo
    # nuestro se cuenta en el mismo periodo para poder restarlo.
    account = get_serpapi_account()
    ciclo = inicio_ciclo_serpapi(account)
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Sin conexión a base de datos")
    try:
        cur = conn.cursor()

        # ------------------------- LLM -------------------------
        cur.execute("""
            SELECT
                COUNT(*)                                                          AS units_total,
                COALESCE(SUM(cost_usd), 0)                                        AS cost_total,
                COUNT(*)              FILTER (WHERE analysis_date >= DATE_TRUNC('month', CURRENT_DATE)) AS units_month,
                COALESCE(SUM(cost_usd) FILTER (WHERE analysis_date >= DATE_TRUNC('month', CURRENT_DATE)), 0) AS cost_month,
                COUNT(*)              FILTER (WHERE analysis_date = CURRENT_DATE) AS units_today,
                COALESCE(SUM(cost_usd) FILTER (WHERE analysis_date = CURRENT_DATE), 0) AS cost_today,
                COUNT(*)              FILTER (WHERE analysis_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
                                                AND analysis_date < DATE_TRUNC('month', CURRENT_DATE)) AS units_prev_month,
                COALESCE(SUM(cost_usd) FILTER (WHERE analysis_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
                                                AND analysis_date < DATE_TRUNC('month', CURRENT_DATE)), 0) AS cost_prev_month,
                COUNT(*)              FILTER (WHERE cost_usd IS NULL OR cost_usd = 0) AS zero_cost_units
            FROM llm_monitoring_results
        """)
        llm_totals = dict(cur.fetchone())

        # Por proveedor y modelo (mes actual + histórico para promedios estables)
        cur.execute("""
            SELECT llm_provider, model_used,
                   COUNT(*) AS units,
                   COALESCE(SUM(cost_usd), 0) AS cost,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COUNT(*) FILTER (WHERE analysis_date >= DATE_TRUNC('month', CURRENT_DATE)) AS units_month,
                   COALESCE(SUM(cost_usd) FILTER (WHERE analysis_date >= DATE_TRUNC('month', CURRENT_DATE)), 0) AS cost_month
            FROM llm_monitoring_results
            GROUP BY llm_provider, model_used
            ORDER BY cost DESC
        """)
        llm_by_model = [dict(r) for r in cur.fetchall()]

        # Promedio por prompt por proveedor (solo filas con coste calculado)
        cur.execute("""
            SELECT llm_provider,
                   COUNT(*) AS units,
                   COALESCE(SUM(cost_usd), 0) AS cost,
                   COALESCE(AVG(cost_usd) FILTER (WHERE cost_usd > 0), 0) AS avg_cost_per_unit
            FROM llm_monitoring_results
            GROUP BY llm_provider
            ORDER BY cost DESC
        """)
        llm_by_provider = [dict(r) for r in cur.fetchall()]

        # Coste LLM por usuario (mes actual)
        cur.execute("""
            SELECT p.user_id, u.email, COALESCE(u.name, u.email) AS name,
                   COUNT(*) AS units_month,
                   COALESCE(SUM(r.cost_usd), 0) AS cost_month
            FROM llm_monitoring_results r
            JOIN llm_monitoring_projects p ON p.id = r.project_id
            JOIN users u ON u.id = p.user_id
            WHERE r.analysis_date >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY p.user_id, u.email, u.name
        """)
        llm_by_user = {row['user_id']: dict(row) for row in cur.fetchall()}

        # Serie diaria (últimos 30 días)
        cur.execute("""
            SELECT analysis_date AS day, COUNT(*) AS units, COALESCE(SUM(cost_usd), 0) AS cost
            FROM llm_monitoring_results
            WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY analysis_date ORDER BY analysis_date
        """)
        llm_daily = [{'day': r['day'].isoformat(), 'units': int(r['units']), 'cost': _f(r['cost'])}
                     for r in cur.fetchall()]

        # Modelos activos con su pricing (para el simulador)
        cur.execute("""
            SELECT llm_provider, model_id, model_display_name,
                   cost_per_1m_input_tokens, cost_per_1m_output_tokens, is_current
            FROM llm_model_registry
            WHERE is_current = TRUE
            ORDER BY llm_provider
        """)
        llm_current_models = [dict(r) for r in cur.fetchall()]

        # ------------------------- SerpAPI -------------------------
        # Búsquedas reales facturables (serp_api + ai_mode)
        cur.execute("""
            SELECT
                COALESCE(SUM(ru_consumed), 0)                                  AS searches_total,
                COALESCE(SUM(ru_consumed) FILTER (WHERE timestamp >= DATE_TRUNC('month', CURRENT_DATE)), 0) AS searches_month,
                COALESCE(SUM(ru_consumed) FILTER (WHERE timestamp >= CURRENT_DATE), 0) AS searches_today,
                COALESCE(SUM(ru_consumed) FILTER (WHERE timestamp >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
                                                    AND timestamp < DATE_TRUNC('month', CURRENT_DATE)), 0) AS searches_prev_month,
                COALESCE(SUM(ru_consumed) FILTER (WHERE %s::date IS NOT NULL AND timestamp >= %s::date), 0) AS searches_cycle
            FROM quota_usage_events
            WHERE source IN %s
        """, (ciclo, ciclo, SERP_BILLABLE_SOURCES))
        serp_totals = dict(cur.fetchone())

        # Expansiones de AIO de Manual AI (búsquedas extra, sin evento de cuota).
        # searches_total se queda solo con los eventos: sumar las expansiones de todo el
        # histórico obligaría a recorrer manual_ai_results entera en cada carga.
        cur.execute(f"""
            SELECT
                COALESCE(SUM(x.n) FILTER (WHERE x.analysis_date >= DATE_TRUNC('month', CURRENT_DATE)), 0) AS searches_month,
                COUNT(*) FILTER (WHERE x.analysis_date >= DATE_TRUNC('month', CURRENT_DATE) AND x.n > 0) AS rows_month,
                COALESCE(SUM(x.n) FILTER (WHERE x.analysis_date >= CURRENT_DATE), 0) AS searches_today,
                COALESCE(SUM(x.n) FILTER (WHERE x.analysis_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
                                            AND x.analysis_date < DATE_TRUNC('month', CURRENT_DATE)), 0) AS searches_prev_month,
                COALESCE(SUM(x.n) FILTER (WHERE %s::date IS NOT NULL AND x.analysis_date >= %s::date), 0) AS searches_cycle
            FROM (SELECT r.analysis_date, {_EXPANSIONES} AS n
                  FROM manual_ai_results r
                  WHERE r.analysis_date >= LEAST(DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month',
                                                 COALESCE(%s::date, CURRENT_DATE))
                    AND r.ai_analysis_data ? 'aio_expansion') x
        """, (ciclo, ciclo, ciclo))
        expansiones = dict(cur.fetchone())
        for clave in ('searches_month', 'searches_today', 'searches_prev_month', 'searches_cycle'):
            serp_totals[clave] = int(serp_totals[clave]) + int(expansiones[clave])
        serp_totals['expansions_month'] = int(expansiones['searches_month'])

        # Atribución por módulo (todas las fuentes, mes actual) — RU internas
        cur.execute("""
            SELECT COALESCE(source, 'desconocido') AS source,
                   COUNT(*) AS events,
                   COALESCE(SUM(ru_consumed), 0) AS ru
            FROM quota_usage_events
            WHERE timestamp >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY source ORDER BY ru DESC
        """)
        serp_by_source_month = [dict(r) for r in cur.fetchall()]
        if serp_totals['expansions_month']:
            serp_by_source_month.append({'source': FUENTE_EXPANSIONES, 'events': int(expansiones['rows_month']),
                                         'ru': serp_totals['expansions_month']})
            serp_by_source_month.sort(key=lambda r: -int(r['ru']))

        # Búsquedas facturables por usuario (mes actual)
        cur.execute("""
            SELECT q.user_id, u.email, COALESCE(u.name, u.email) AS name,
                   COALESCE(SUM(q.ru_consumed), 0) AS searches_month
            FROM quota_usage_events q
            JOIN users u ON u.id = q.user_id
            WHERE q.timestamp >= DATE_TRUNC('month', CURRENT_DATE)
              AND q.source IN %s
            GROUP BY q.user_id, u.email, u.name
        """, (SERP_BILLABLE_SOURCES,))
        serp_by_user = {row['user_id']: dict(row) for row in cur.fetchall()}

        cur.execute(f"""
            SELECT p.user_id, COALESCE(SUM({_EXPANSIONES}), 0) AS searches
            FROM manual_ai_results r
            JOIN manual_ai_projects p ON p.id = r.project_id
            WHERE r.analysis_date >= DATE_TRUNC('month', CURRENT_DATE)
              AND r.ai_analysis_data ? 'aio_expansion'
            GROUP BY p.user_id
        """)
        for row in cur.fetchall():
            extra = int(row['searches'] or 0)
            if extra:
                fila = serp_by_user.setdefault(row['user_id'], {'user_id': row['user_id'], 'searches_month': 0})
                fila['searches_month'] = int(fila['searches_month'] or 0) + extra

        # Serie diaria de búsquedas (últimos 30 días)
        cur.execute("""
            SELECT DATE(timestamp) AS day, COALESCE(SUM(ru_consumed), 0) AS searches
            FROM quota_usage_events
            WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
              AND source IN %s
            GROUP BY DATE(timestamp) ORDER BY day
        """, (SERP_BILLABLE_SOURCES,))
        serp_por_dia = {r['day']: int(r['searches']) for r in cur.fetchall()}
        cur.execute(f"""
            SELECT r.analysis_date AS day, COALESCE(SUM({_EXPANSIONES}), 0) AS searches
            FROM manual_ai_results r
            WHERE r.analysis_date >= CURRENT_DATE - INTERVAL '30 days'
              AND r.ai_analysis_data ? 'aio_expansion'
            GROUP BY r.analysis_date
        """)
        for r in cur.fetchall():
            serp_por_dia[r['day']] = serp_por_dia.get(r['day'], 0) + int(r['searches'] or 0)
        serp_daily = [{'day': d.isoformat(), 'searches': n} for d, n in sorted(serp_por_dia.items())]

        # ------------------------- Usuarios: plan/rol para margen -------------------------
        cur.execute("""
            SELECT id, email, COALESCE(name, email) AS name, role,
                   COALESCE(plan, 'free') AS plan
            FROM users
        """)
        users_index = {row['id']: dict(row) for row in cur.fetchall()}

    finally:
        conn.close()

    # ------------------------- Cálculo de costes -------------------------
    cost_per_search, cps_source = get_serp_cost_per_search(account)
    usd_eur = float(os.getenv('ADMIN_USD_EUR_RATE', '0.86'))

    serp_cost_month_internal = _f(int(serp_totals['searches_month']) * cost_per_search)
    serp_cost_month_official = None
    if account and account.get('this_month_usage') is not None:
        serp_cost_month_official = _f(int(account['this_month_usage']) * cost_per_search)

    llm_cost_month = _f(llm_totals['cost_month'])
    total_cost_month_usd = _f(llm_cost_month + serp_cost_month_internal)

    # Ingresos (EUR) desde el módulo de billing
    try:
        from admin_billing_panel import get_revenue_stats
        revenue = get_revenue_stats()
    except Exception as e:
        logger.warning(f"No se pudieron obtener ingresos: {e}")
        revenue = {'total_revenue': 0.0, 'by_plan': {}, 'paying_users': 0}

    total_cost_month_eur = _f(total_cost_month_usd * usd_eur)
    margin_month_eur = _f(float(revenue.get('total_revenue', 0)) - total_cost_month_eur)

    # Tabla combinada de coste por usuario (mes actual)
    plan_prices = {'basic': 29.99, 'premium': 79.99, 'business': 229.99}
    user_ids = set(llm_by_user) | set(serp_by_user)
    per_user = []
    for uid in user_ids:
        base = users_index.get(uid, {})
        llm_u = llm_by_user.get(uid, {})
        serp_u = serp_by_user.get(uid, {})
        llm_cost = _f(llm_u.get('cost_month'))
        searches = int(serp_u.get('searches_month') or 0)
        serp_cost = _f(searches * cost_per_search)
        total_usd = _f(llm_cost + serp_cost)
        plan = base.get('plan', 'free')
        revenue_eur = plan_prices.get(plan, 0.0) if base.get('role') != 'admin' else 0.0
        per_user.append({
            'user_id': uid,
            'name': llm_u.get('name') or serp_u.get('name') or base.get('name') or f'ID {uid}',
            'email': llm_u.get('email') or serp_u.get('email') or base.get('email') or '',
            'role': base.get('role', 'user'),
            'plan': plan,
            'llm_units': int(llm_u.get('units_month') or 0),
            'llm_cost_usd': llm_cost,
            'serp_searches': searches,
            'serp_cost_usd': serp_cost,
            'total_cost_usd': total_usd,
            'revenue_eur': revenue_eur,
            'margin_eur': _f(revenue_eur - total_usd * usd_eur),
        })
    per_user.sort(key=lambda x: x['total_cost_usd'], reverse=True)

    # Promedios por prompt (para el simulador de presupuestos)
    providers_avg = []
    for p in llm_by_provider:
        providers_avg.append({
            'provider': p['llm_provider'],
            'units': int(p['units']),
            'cost': _f(p['cost']),
            'avg_cost_per_prompt': _f(p['avg_cost_per_unit']),
        })
    units_with_cost = int(llm_totals['units_total']) - int(llm_totals['zero_cost_units'])
    avg_prompt_global = _f(float(llm_totals['cost_total']) / units_with_cost) if units_with_cost > 0 else 0.0

    return {
        'generated_at': time.time(),
        'month_label': date.today().strftime('%B %Y'),
        'exchange': {'usd_eur': usd_eur},
        'llm': {
            'totals': {k: (int(v) if 'units' in k else _f(v)) for k, v in llm_totals.items()},
            'by_provider': providers_avg,
            'by_model': [{
                'provider': m['llm_provider'],
                'model': m['model_used'],
                'units': int(m['units']),
                'cost': _f(m['cost']),
                'input_tokens': int(m['input_tokens']),
                'output_tokens': int(m['output_tokens']),
                'units_month': int(m['units_month']),
                'cost_month': _f(m['cost_month']),
                'avg_cost_per_unit': _f(float(m['cost']) / int(m['units'])) if int(m['units']) else 0.0,
            } for m in llm_by_model],
            'daily': llm_daily,
            'avg_cost_per_prompt_global': avg_prompt_global,
            'current_models': [{
                'provider': m['llm_provider'],
                'model_id': m['model_id'],
                'display_name': m['model_display_name'],
                'cost_per_1m_input': _f(m['cost_per_1m_input_tokens']),
                'cost_per_1m_output': _f(m['cost_per_1m_output_tokens']),
            } for m in llm_current_models],
            'data_quality': {
                'zero_cost_units': int(llm_totals['zero_cost_units']),
                'note': 'Filas con cost_usd=0: llamadas antiguas cuyo modelo no tenía pricing en llm_model_registry. Excluidas de los promedios por prompt.',
            },
        },
        'serp': {
            'totals': {k: int(v) for k, v in serp_totals.items()},
            'by_source_month': serp_by_source_month and [
                {'source': s['source'], 'events': int(s['events']), 'ru': int(s['ru'])}
                for s in serp_by_source_month
            ] or [],
            'daily': serp_daily,
            'cost_per_search': _f(cost_per_search),
            'cost_per_search_source': cps_source,
            'cost_month_internal_usd': serp_cost_month_internal,
            'cost_month_official_usd': serp_cost_month_official,
            'account': account,
            'billable_sources': list(SERP_BILLABLE_SOURCES) + [FUENTE_EXPANSIONES],
            'note': ("Búsquedas de Clicandseo = Manual AI y AI Overview (1 por keyword), expansiones de AIO de Manual AI, "
                     "AI Mode y la vista de SERP. El dato oficial (this_month_usage) es de toda la cuenta de SerpAPI y "
                     "cuenta desde la última renovación: la misma clave la usan staging y otros servicios (n8n, vigía "
                     "de competidores, tracker...), así que la diferencia con lo atribuido en el mismo ciclo es su "
                     "consumo (más las expansiones de AI Overview, que no se registran). Aproximado: SerpAPI no dice "
                     "a qué hora renueva y el día de la renovación se cuenta entero, así que la cifra puede "
                     "desviarse en lo que Clicandseo gastó ese día antes de renovar (como mucho, un día de consumo)."),
            'cycle_start': ciclo.isoformat() if ciclo else None,
            'clicandseo_cycle': int(serp_totals['searches_cycle']) if ciclo else None,
            # El día de la renovación contamos desde las 00:00 y SerpAPI desde la hora
            # de renovar, que no da: saldría negativo sin serlo. Ese día no hay cifra.
            'cycle_renewal_day': bool(ciclo and ciclo == date.today()),
            # Lo gastado el día de la renovación: si "otros" sale negativo por menos de
            # esto, es el desfase de la hora de renovar, no un doble conteo.
            'cycle_first_day_searches': int(serp_por_dia.get(ciclo, 0)) if ciclo else None,
            # Puede salir negativo si lo atribuido supera al dato oficial (doble conteo):
            # se muestra como aviso, no se recorta a 0.
            'other_consumers_cycle': (int(account['this_month_usage']) - int(serp_totals['searches_cycle'])
                                      if ciclo and ciclo != date.today()
                                      and account.get('this_month_usage') is not None else None),
        },
        'summary': {
            'llm_cost_month_usd': llm_cost_month,
            'serp_cost_month_usd': serp_cost_month_internal,
            'serp_cost_month_official_usd': serp_cost_month_official,
            'total_cost_month_usd': total_cost_month_usd,
            'total_cost_month_eur': total_cost_month_eur,
            'revenue_month_eur': _f(revenue.get('total_revenue', 0)),
            'paying_users': int(revenue.get('paying_users', 0)),
            'margin_month_eur': margin_month_eur,
        },
        'per_user': per_user,
    }


# ---------------------------------------------------------------------------
# Ruta
# ---------------------------------------------------------------------------

@admin_costs_bp.route('/admin/api/costs', methods=['GET'])
@admin_required
def admin_costs_api():
    try:
        return jsonify({'success': True, 'data': get_costs_dashboard()})
    except Exception as e:
        logger.error(f"Error generando dashboard de costes: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
