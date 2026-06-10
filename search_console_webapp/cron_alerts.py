"""
Cron Alert System for LLM Monitoring runs.

Fires email alerts when an analysis run breaches one of three thresholds:

  1. DURATION    — completed_at - started_at exceeds CRON_ALERT_DURATION_MIN minutes
  2. ERROR RATE  — failed_projects / total_projects exceeds CRON_ALERT_ERROR_RATE
  3. COST SPIKE  — today's LLM cost exceeds CRON_ALERT_COST_MULTIPLIER × 7-day moving avg

A single email is sent per run, batching all triggered alerts.

Design notes:
  * The hot path (release_analysis_lock) calls check_and_send_cron_alerts() inside
    a try/except so any failure here is silent and does NOT affect lock release
    or run state.
  * All thresholds and the destination email are env-var driven so they can be
    tuned per-environment without redeploys.
  * CRON_ALERTS_ENABLED=false acts as a kill switch.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration (env-driven, with safe defaults)
# ---------------------------------------------------------------------------

def _get_config() -> Dict:
    """Read alert configuration from environment variables on every call."""
    return {
        'enabled': os.getenv('CRON_ALERTS_ENABLED', 'true').lower() == 'true',
        'email': os.getenv('CRON_ALERTS_EMAIL', 'info@soycarlosgonzalez.com'),
        'duration_min_threshold': float(os.getenv('CRON_ALERT_DURATION_MIN', '90')),
        'error_rate_threshold': float(os.getenv('CRON_ALERT_ERROR_RATE', '0.20')),
        'cost_multiplier_threshold': float(os.getenv('CRON_ALERT_COST_MULTIPLIER', '2.0')),
        'environment': os.getenv('APP_ENV', os.getenv('RAILWAY_ENVIRONMENT_NAME', 'unknown')),
    }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_duration(run: Dict, threshold_min: float) -> Optional[Dict]:
    """Return alert dict if run took longer than threshold, else None."""
    started = run.get('started_at')
    completed = run.get('completed_at')
    if not started or not completed:
        return None

    duration_min = (completed - started).total_seconds() / 60.0

    if duration_min > threshold_min:
        return {
            'type': 'duration',
            'severity': 'high' if duration_min > threshold_min * 1.5 else 'medium',
            'metric': f'{duration_min:.1f} min',
            'threshold': f'{threshold_min:.0f} min',
            'message': (
                f'El cron LLM tardó {duration_min:.1f} minutos en completar '
                f'(umbral: {threshold_min:.0f} min). Esto puede indicar un proyecto '
                f'colgado o saturación de algún proveedor de LLM.'
            ),
        }
    return None


def _check_error_rate(run: Dict, threshold: float) -> Optional[Dict]:
    """Return alert dict if failed/total ratio exceeds threshold."""
    total = run.get('total_projects') or 0
    failed = run.get('failed_projects') or 0
    if total <= 0:
        return None

    rate = failed / total

    if rate > threshold:
        return {
            'type': 'error_rate',
            'severity': 'high' if rate > threshold * 2 else 'medium',
            'metric': f'{rate * 100:.1f}% ({failed}/{total} fallos)',
            'threshold': f'{threshold * 100:.0f}%',
            'message': (
                f'{failed} de {total} proyectos fallaron en la última ejecución '
                f'(ratio {rate * 100:.1f}%, umbral {threshold * 100:.0f}%). '
                f'Revisa logs y disponibilidad de APIs de LLMs.'
            ),
        }
    return None


def _check_cost_spike(get_db_connection_fn, multiplier: float) -> Optional[Dict]:
    """Compare today's LLM cost vs 7-day moving avg. Alert if today > multiplier × avg."""
    conn = None
    try:
        conn = get_db_connection_fn()
        if not conn:
            return None
        cur = conn.cursor()

        # Today's cost
        cur.execute("""
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM llm_monitoring_results
            WHERE created_at::date = CURRENT_DATE
        """)
        row = cur.fetchone()
        today_cost = float(row[0] if not isinstance(row, dict) else row.get('coalesce') or 0)

        # 7-day moving avg (excluding today to avoid self-reference)
        cur.execute("""
            SELECT COALESCE(AVG(daily_cost), 0) AS avg_cost
            FROM (
                SELECT DATE(created_at) AS d, SUM(cost_usd) AS daily_cost
                FROM llm_monitoring_results
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                  AND created_at < CURRENT_DATE
                GROUP BY DATE(created_at)
            ) sub
        """)
        row = cur.fetchone()
        avg_cost = float(row[0] if not isinstance(row, dict) else row.get('avg_cost') or 0)

        if avg_cost <= 0:
            return None  # No baseline yet, can't compute spike

        ratio = today_cost / avg_cost if avg_cost > 0 else 0

        if today_cost > avg_cost * multiplier:
            return {
                'type': 'cost_spike',
                'severity': 'high' if ratio > multiplier * 1.5 else 'medium',
                'metric': f'${today_cost:.2f} hoy vs ${avg_cost:.2f} media 7d ({ratio:.1f}×)',
                'threshold': f'{multiplier}× media',
                'message': (
                    f'Coste de hoy (${today_cost:.2f}) supera {ratio:.1f}× la media '
                    f'móvil de 7 días (${avg_cost:.2f}). Revisa si hay ejecuciones '
                    f'duplicadas, queries fuera de control, o proyectos nuevos consumiendo más.'
                ),
            }
        return None

    except Exception as e:
        logger.warning(f"[cron_alerts] cost-spike check skipped: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _check_provider_coverage(run: Dict, get_db_connection_fn) -> Optional[Dict]:
    """
    Alert si algún LLM HABILITADO no devolvió NINGÚN resultado durante el run.

    Cubre el fallo silencioso en el que un provider se excluye en el health-check
    (o cae/agota cuota por completo) y desaparece del análisis sin contar como
    'fallo de proyecto' — exactamente el caso del outage de Gemini de may-2026,
    en el que Google estuvo a 0 resultados durante varios runs sin que ninguna
    alerta se disparara.

    Por cada proyecto que produjo filas en la ventana del run, compara los
    providers habilitados (enabled_llms) contra los que realmente devolvieron
    filas. Funciona para CUALQUIER provider (OpenAI / Anthropic / Google /
    Perplexity).
    """
    started = run.get('started_at')
    completed = run.get('completed_at')
    if not started or not completed:
        return None
    conn = None
    try:
        conn = get_db_connection_fn()
        if conn is None:
            return None
        cur = conn.cursor()
        cur.execute("""
            WITH ran AS (
                SELECT DISTINCT project_id
                FROM llm_monitoring_results
                WHERE created_at >= %s AND created_at <= %s
            ),
            expected AS (
                SELECT p.id AS project_id, p.name AS project_name,
                       UNNEST(p.enabled_llms) AS provider
                FROM llm_monitoring_projects p
                JOIN ran r ON r.project_id = p.id
            ),
            got AS (
                SELECT project_id, llm_provider, COUNT(*) AS n
                FROM llm_monitoring_results
                WHERE created_at >= %s AND created_at <= %s
                GROUP BY project_id, llm_provider
            )
            SELECT e.provider, e.project_id, e.project_name
            FROM expected e
            LEFT JOIN got g
              ON g.project_id = e.project_id AND g.llm_provider = e.provider
            WHERE COALESCE(g.n, 0) = 0
            ORDER BY e.provider, e.project_id
        """, (started, completed, started, completed))
        rows = cur.fetchall() or []
        if not rows:
            return None

        from collections import defaultdict
        missing = defaultdict(list)
        for r in rows:
            if isinstance(r, dict):
                prov, pid, pname = r.get('provider'), r.get('project_id'), r.get('project_name')
            else:
                prov, pid, pname = r[0], r[1], r[2]
            missing[prov].append(pname or f'#{pid}')

        # Total de proyectos que corrieron (para calcular severidad)
        cur.execute("""
            SELECT COUNT(DISTINCT project_id)
            FROM llm_monitoring_results
            WHERE created_at >= %s AND created_at <= %s
        """, (started, completed))
        rr = cur.fetchone()
        if isinstance(rr, dict):
            total_ran = (list(rr.values())[0] if rr else 0) or 0
        else:
            total_ran = (rr[0] if rr else 0) or 0

        parts = []
        global_outage = False
        for prov, projects in sorted(missing.items()):
            parts.append(f"{prov} (faltó en {len(projects)}/{total_ran} proyectos)")
            if total_ran and len(projects) >= total_ran:
                global_outage = True

        return {
            'type': 'provider_missing',
            'severity': 'high' if global_outage else 'medium',
            'metric': '; '.join(parts),
            'threshold': '0 resultados',
            'message': (
                'Uno o más LLMs habilitados no devolvieron ningún resultado en este run: '
                + '; '.join(parts) + '. '
                'Posible health-check fallido, API caída, cuota agotada o modelo retirado. '
                'Revisa los logs del provider y el modelo is_current en llm_model_registry.'
            ),
        }
    except Exception as e:
        logger.warning(f"[cron_alerts] provider-coverage check skipped: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Email rendering and sending
# ---------------------------------------------------------------------------

def _build_html_email(alerts: List[Dict], run: Dict, env_name: str) -> str:
    """Return HTML body. Keep simple — this goes to ops, not customers."""
    severity_color = {'high': '#dc2626', 'medium': '#f59e0b', 'low': '#6b7280'}
    rows = []
    for a in alerts:
        color = severity_color.get(a.get('severity', 'medium'), '#6b7280')
        rows.append(f"""
        <tr>
            <td style="padding:12px; border-bottom:1px solid #e5e7eb; vertical-align:top;">
                <span style="display:inline-block; padding:3px 10px; background:{color};
                             color:#fff; border-radius:4px; font-size:12px; font-weight:600;
                             text-transform:uppercase;">{a.get('type', 'alert')}</span>
            </td>
            <td style="padding:12px; border-bottom:1px solid #e5e7eb; font-family:monospace;">
                {a.get('metric', '-')}
            </td>
            <td style="padding:12px; border-bottom:1px solid #e5e7eb; font-family:monospace; color:#6b7280;">
                {a.get('threshold', '-')}
            </td>
            <td style="padding:12px; border-bottom:1px solid #e5e7eb;">
                {a.get('message', '-')}
            </td>
        </tr>
        """)

    run_id = run.get('id', '?')
    started = run.get('started_at', '?')
    total = run.get('total_projects', 0)
    successful = run.get('successful_projects', 0)
    failed = run.get('failed_projects', 0)

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                 max-width:800px; margin:0 auto; padding:24px; color:#111827;">
        <h2 style="color:#dc2626; margin-top:0;">🚨 Cron LLM Monitoring — Alertas activadas</h2>
        <p>Entorno: <strong>{env_name}</strong> · Run ID: <strong>{run_id}</strong> ·
           Iniciado: {started}</p>
        <p style="background:#f3f4f6; padding:12px; border-radius:6px;">
            <strong>Resumen del run:</strong> {successful}/{total} OK · {failed} fallidos
        </p>
        <h3 style="margin-top:28px;">Alertas disparadas ({len(alerts)})</h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <thead>
                <tr style="background:#f9fafb;">
                    <th style="text-align:left; padding:12px; border-bottom:2px solid #e5e7eb;">Tipo</th>
                    <th style="text-align:left; padding:12px; border-bottom:2px solid #e5e7eb;">Métrica</th>
                    <th style="text-align:left; padding:12px; border-bottom:2px solid #e5e7eb;">Umbral</th>
                    <th style="text-align:left; padding:12px; border-bottom:2px solid #e5e7eb;">Detalle</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        <p style="color:#6b7280; font-size:12px; margin-top:32px;">
            Mensaje automático del sistema de alertas de cron LLM Monitoring.
            Para silenciar puntualmente: <code>CRON_ALERTS_ENABLED=false</code>.
        </p>
    </body>
    </html>
    """


def _build_subject(alerts: List[Dict], env_name: str) -> str:
    types = sorted({a['type'] for a in alerts})
    return f"[{env_name.upper()}] LLM Cron alerts: {', '.join(types)}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def check_and_send_cron_alerts(run_id: int, get_db_connection_fn=None) -> Dict:
    """
    Evaluate the three alert thresholds for a completed run and send a single
    email if any of them are breached.

    Args:
        run_id: id of the row in llm_monitoring_analysis_runs to evaluate.
        get_db_connection_fn: optional injected DB connection getter
            (used by tests to mock). Defaults to database.get_db_connection.

    Returns:
        Dict with: alerts_triggered (int), email_sent (bool), reason (str).
        Never raises — all errors are caught and logged.
    """
    cfg = _get_config()
    if not cfg['enabled']:
        return {'alerts_triggered': 0, 'email_sent': False, 'reason': 'disabled'}

    if get_db_connection_fn is None:
        try:
            from database import get_db_connection as _gdc
            get_db_connection_fn = _gdc
        except Exception as e:
            logger.warning(f"[cron_alerts] cannot import get_db_connection: {e}")
            return {'alerts_triggered': 0, 'email_sent': False, 'reason': 'no_db'}

    # Load the run
    run = None
    conn = None
    try:
        conn = get_db_connection_fn()
        if conn is None:
            return {'alerts_triggered': 0, 'email_sent': False, 'reason': 'no_db_conn'}
        cur = conn.cursor()
        cur.execute("""
            SELECT id, started_at, completed_at, status,
                   total_projects, successful_projects, failed_projects,
                   total_queries, error_message, triggered_by
            FROM llm_monitoring_analysis_runs
            WHERE id = %s
        """, (run_id,))
        row = cur.fetchone()
        if not row:
            return {'alerts_triggered': 0, 'email_sent': False, 'reason': 'run_not_found'}

        # Normalize to dict (works whether the cursor returns dict or tuple)
        if isinstance(row, dict):
            run = row
        else:
            run = {
                'id': row[0], 'started_at': row[1], 'completed_at': row[2],
                'status': row[3], 'total_projects': row[4],
                'successful_projects': row[5], 'failed_projects': row[6],
                'total_queries': row[7], 'error_message': row[8],
                'triggered_by': row[9],
            }
    except Exception as e:
        logger.warning(f"[cron_alerts] failed to load run {run_id}: {e}")
        return {'alerts_triggered': 0, 'email_sent': False, 'reason': f'load_error: {e}'}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    # Run the three checks
    alerts = []
    try:
        a = _check_duration(run, cfg['duration_min_threshold'])
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] duration check failed: {e}")

    try:
        a = _check_error_rate(run, cfg['error_rate_threshold'])
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] error-rate check failed: {e}")

    try:
        a = _check_cost_spike(get_db_connection_fn, cfg['cost_multiplier_threshold'])
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] cost-spike check failed: {e}")

    try:
        a = _check_provider_coverage(run, get_db_connection_fn)
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] provider-coverage check failed: {e}")

    if not alerts:
        logger.info(f"[cron_alerts] run {run_id}: no thresholds breached")
        return {'alerts_triggered': 0, 'email_sent': False, 'reason': 'no_breach'}

    # Send email
    try:
        from email_service import send_email
        html = _build_html_email(alerts, run, cfg['environment'])
        subject = _build_subject(alerts, cfg['environment'])
        sent = send_email(cfg['email'], subject, html)
        if sent:
            logger.info(
                f"[cron_alerts] run {run_id}: sent {len(alerts)} alert(s) to {cfg['email']}"
            )
        else:
            logger.warning(f"[cron_alerts] run {run_id}: email send returned False")
        return {
            'alerts_triggered': len(alerts),
            'email_sent': bool(sent),
            'alerts': [a['type'] for a in alerts],
            'reason': 'sent' if sent else 'send_failed',
        }
    except Exception as e:
        logger.warning(f"[cron_alerts] failed to send email for run {run_id}: {e}")
        return {
            'alerts_triggered': len(alerts),
            'email_sent': False,
            'alerts': [a['type'] for a in alerts],
            'reason': f'send_exception: {e}',
        }


# ---------------------------------------------------------------------------
# Always-on completion email (per-run summary)
# ---------------------------------------------------------------------------

def _load_run(run_id: int, get_db_connection_fn) -> Optional[Dict]:
    """Load a single run row as dict, or None on error."""
    conn = None
    try:
        conn = get_db_connection_fn()
        if conn is None:
            return None
        cur = conn.cursor()
        cur.execute("""
            SELECT id, started_at, completed_at, status,
                   total_projects, successful_projects, failed_projects,
                   total_queries, error_message, triggered_by
            FROM llm_monitoring_analysis_runs
            WHERE id = %s
        """, (run_id,))
        row = cur.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return dict(row)
        return {
            'id': row[0], 'started_at': row[1], 'completed_at': row[2],
            'status': row[3], 'total_projects': row[4],
            'successful_projects': row[5], 'failed_projects': row[6],
            'total_queries': row[7], 'error_message': row[8],
            'triggered_by': row[9],
        }
    except Exception as e:
        logger.warning(f"[cron_alerts] _load_run({run_id}) failed: {e}")
        return None
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


def _load_run_cost(run: Dict, get_db_connection_fn) -> Optional[float]:
    """Return total cost_usd of llm_monitoring_results created during this run."""
    started = run.get('started_at')
    completed = run.get('completed_at')
    if not started or not completed:
        return None
    conn = None
    try:
        conn = get_db_connection_fn()
        if conn is None:
            return None
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(cost_usd), 0) AS total
            FROM llm_monitoring_results
            WHERE created_at >= %s AND created_at <= %s
        """, (started, completed))
        row = cur.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return float(row.get('total') or 0)
        return float(row[0] or 0)
    except Exception as e:
        logger.warning(f"[cron_alerts] _load_run_cost failed: {e}")
        return None
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


def _load_top_errors(run: Dict, get_db_connection_fn, limit: int = 10) -> List[Dict]:
    """Return up to `limit` error rows from llm_monitoring_results during this run."""
    started = run.get('started_at')
    completed = run.get('completed_at')
    if not started or not completed:
        return []
    conn = None
    try:
        conn = get_db_connection_fn()
        if conn is None:
            return []
        cur = conn.cursor()
        cur.execute("""
            SELECT project_id, llm_provider, error_message
            FROM llm_monitoring_results
            WHERE created_at >= %s AND created_at <= %s
              AND (error_message IS NOT NULL AND error_message <> '')
            ORDER BY created_at DESC
            LIMIT %s
        """, (started, completed, limit))
        rows = cur.fetchall() or []
        out = []
        for r in rows:
            if isinstance(r, dict):
                out.append({
                    'project_id': r.get('project_id'),
                    'llm_provider': r.get('llm_provider'),
                    'error_message': (r.get('error_message') or '')[:240],
                })
            else:
                out.append({
                    'project_id': r[0],
                    'llm_provider': r[1],
                    'error_message': (r[2] or '')[:240],
                })
        return out
    except Exception as e:
        logger.warning(f"[cron_alerts] _load_top_errors failed: {e}")
        return []
    finally:
        if conn:
            try: conn.close()
            except Exception: pass


def _derive_severity(run: Dict, alerts: List[Dict]) -> str:
    """Pick a single severity for the email subject."""
    if run.get('status') == 'failed' or run.get('error_message'):
        return 'critical'
    if any(a.get('severity') == 'high' for a in alerts):
        return 'critical'
    if alerts:
        return 'warning'
    failed = run.get('failed_projects') or 0
    if failed > 0:
        return 'warning'
    return 'ok'


def _build_completion_email_html(run: Dict, alerts: List[Dict], run_cost: Optional[float],
                                 errors: List[Dict], env_name: str, severity: str) -> str:
    icon = {'ok': '✅', 'warning': '⚠️', 'critical': '🚨'}.get(severity, 'ℹ️')
    color = {'ok': '#16a34a', 'warning': '#f59e0b', 'critical': '#dc2626'}.get(severity, '#6b7280')

    started = run.get('started_at')
    completed = run.get('completed_at')
    duration_min = None
    if started and completed:
        try:
            duration_min = (completed - started).total_seconds() / 60.0
        except Exception:
            duration_min = None

    total = run.get('total_projects') or 0
    ok = run.get('successful_projects') or 0
    failed = run.get('failed_projects') or 0
    queries = run.get('total_queries') or 0
    status = (run.get('status') or 'unknown').upper()
    triggered_by = run.get('triggered_by') or '-'
    err_msg = run.get('error_message') or ''

    cost_row = ''
    if run_cost is not None:
        cost_row = f'<tr><td style="padding:8px 12px;color:#6b7280;">Coste de la run</td><td style="padding:8px 12px;font-family:monospace;">${run_cost:.4f}</td></tr>'

    alert_rows = ''
    if alerts:
        sev_color = {'high': '#dc2626', 'medium': '#f59e0b', 'low': '#6b7280'}
        for a in alerts:
            c = sev_color.get(a.get('severity', 'medium'), '#6b7280')
            alert_rows += f"""
            <tr>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;">
                    <span style="display:inline-block;padding:3px 8px;background:{c};color:#fff;
                                 border-radius:4px;font-size:11px;font-weight:600;text-transform:uppercase;">
                        {a.get('type','alert')}
                    </span>
                </td>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;font-family:monospace;">{a.get('metric','-')}</td>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;font-family:monospace;color:#6b7280;">{a.get('threshold','-')}</td>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;">{a.get('message','-')}</td>
            </tr>
            """
        alerts_block = f"""
        <h3 style="margin-top:24px;">Alertas activadas ({len(alerts)})</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead><tr style="background:#f9fafb;">
                <th style="text-align:left;padding:10px;border-bottom:2px solid #e5e7eb;">Tipo</th>
                <th style="text-align:left;padding:10px;border-bottom:2px solid #e5e7eb;">Métrica</th>
                <th style="text-align:left;padding:10px;border-bottom:2px solid #e5e7eb;">Umbral</th>
                <th style="text-align:left;padding:10px;border-bottom:2px solid #e5e7eb;">Detalle</th>
            </tr></thead>
            <tbody>{alert_rows}</tbody>
        </table>
        """
    else:
        alerts_block = ''

    err_rows = ''
    if errors:
        for e in errors:
            err_rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{e.get('project_id','-')}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f4f6;">{e.get('llm_provider','-')}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f4f6;font-family:monospace;font-size:12px;color:#7f1d1d;">{e.get('error_message','-')}</td>
            </tr>
            """
        errors_block = f"""
        <h3 style="margin-top:24px;">Últimos errores ({len(errors)})</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead><tr style="background:#f9fafb;">
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e5e7eb;">Proyecto</th>
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e5e7eb;">Provider</th>
                <th style="text-align:left;padding:8px;border-bottom:2px solid #e5e7eb;">Error</th>
            </tr></thead>
            <tbody>{err_rows}</tbody>
        </table>
        """
    else:
        errors_block = ''

    err_block = ''
    if err_msg:
        err_block = f"""
        <p style="background:#fef2f2;border-left:4px solid #dc2626;padding:12px;margin:16px 0;">
            <strong>Error global de la run:</strong><br>
            <code style="font-size:12px;color:#7f1d1d;">{err_msg[:1000]}</code>
        </p>
        """

    duration_str = f'{duration_min:.1f} min' if duration_min is not None else '-'

    return f"""
    <!DOCTYPE html>
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                       max-width:800px;margin:0 auto;padding:24px;color:#111827;">
        <h2 style="color:{color};margin-top:0;">{icon} LLM Monitoring — Run #{run.get('id','?')} {status}</h2>
        <p>Entorno: <strong>{env_name}</strong> · Disparado por: <strong>{triggered_by}</strong></p>
        {err_block}
        <table style="width:100%;border-collapse:collapse;font-size:14px;background:#f9fafb;border-radius:8px;">
            <tr><td style="padding:8px 12px;color:#6b7280;">Inicio</td><td style="padding:8px 12px;font-family:monospace;">{started}</td></tr>
            <tr><td style="padding:8px 12px;color:#6b7280;">Fin</td><td style="padding:8px 12px;font-family:monospace;">{completed}</td></tr>
            <tr><td style="padding:8px 12px;color:#6b7280;">Duración</td><td style="padding:8px 12px;font-family:monospace;">{duration_str}</td></tr>
            <tr><td style="padding:8px 12px;color:#6b7280;">Proyectos</td><td style="padding:8px 12px;font-family:monospace;">{ok}/{total} OK · {failed} fallidos</td></tr>
            <tr><td style="padding:8px 12px;color:#6b7280;">Queries totales</td><td style="padding:8px 12px;font-family:monospace;">{queries}</td></tr>
            {cost_row}
        </table>
        {alerts_block}
        {errors_block}
        <p style="color:#6b7280;font-size:12px;margin-top:32px;">
            Email automático del sistema de monitorización de cron.
            Kill switch: <code>CRON_ALERTS_ENABLED=false</code>.
        </p>
    </body></html>
    """


def send_simple_run_completion_email(module_label: str, stats: Dict) -> Dict:
    """
    Email de resumen para crons SIN tabla de runs (Manual AI, AI Mode).

    A diferencia de send_run_completion_email (que lee llm_monitoring_analysis_runs),
    esta función trabaja directamente con el dict de stats que devuelven los
    CronService de Manual AI / AI Mode:

        {success, successful, failed, skipped, total_keywords, elapsed_seconds,
         error (opcional), job_id (opcional)}

    Severidad del asunto:
      - 🚨 CRITICAL → success=False o error presente (el run reventó entero)
      - ⚠️ WARNING  → algún proyecto falló, o duración > CRON_ALERT_DURATION_MIN
      - ✅ OK       → todo bien

    Respeta el kill switch CRON_ALERTS_ENABLED. Nunca lanza excepción — está
    pensada para llamarse desde el final del cron sin riesgo para el run.
    """
    try:
        cfg = _get_config()
        if not cfg['enabled']:
            return {'email_sent': False, 'reason': 'disabled'}

        successful = int(stats.get('successful') or 0)
        failed = int(stats.get('failed') or 0)
        skipped = int(stats.get('skipped') or 0)
        total = successful + failed + skipped
        keywords = int(stats.get('total_keywords') or 0)
        elapsed_min = float(stats.get('elapsed_seconds') or 0) / 60.0
        run_ok = bool(stats.get('success', True))
        error_msg = str(stats.get('error') or '')
        job_id = stats.get('job_id') or '-'

        if not run_ok or error_msg:
            severity = 'critical'
        elif failed > 0 or elapsed_min > cfg['duration_min_threshold']:
            severity = 'warning'
        else:
            severity = 'ok'

        icon = {'ok': '✅', 'warning': '⚠️', 'critical': '🚨'}[severity]
        color = {'ok': '#16a34a', 'warning': '#f59e0b', 'critical': '#dc2626'}[severity]
        env_name = cfg['environment']

        err_block = ''
        if error_msg:
            err_block = f"""
            <p style="background:#fef2f2;border-left:4px solid #dc2626;padding:12px;margin:16px 0;">
                <strong>Error global del run:</strong><br>
                <code style="font-size:12px;color:#7f1d1d;">{error_msg[:1000]}</code>
            </p>
            """

        html = f"""
        <!DOCTYPE html>
        <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                           max-width:700px;margin:0 auto;padding:24px;color:#111827;">
            <h2 style="color:{color};margin-top:0;">{icon} {module_label} — Cron {severity.upper()}</h2>
            <p>Entorno: <strong>{env_name}</strong> · Job: <strong>{job_id}</strong></p>
            {err_block}
            <table style="width:100%;border-collapse:collapse;font-size:14px;background:#f9fafb;border-radius:8px;">
                <tr><td style="padding:8px 12px;color:#6b7280;">Proyectos OK</td><td style="padding:8px 12px;font-family:monospace;">{successful}/{total}</td></tr>
                <tr><td style="padding:8px 12px;color:#6b7280;">Fallidos</td><td style="padding:8px 12px;font-family:monospace;">{failed}</td></tr>
                <tr><td style="padding:8px 12px;color:#6b7280;">Saltados (ya analizados / sin cuota)</td><td style="padding:8px 12px;font-family:monospace;">{skipped}</td></tr>
                <tr><td style="padding:8px 12px;color:#6b7280;">Keywords procesadas</td><td style="padding:8px 12px;font-family:monospace;">{keywords}</td></tr>
                <tr><td style="padding:8px 12px;color:#6b7280;">Duración</td><td style="padding:8px 12px;font-family:monospace;">{elapsed_min:.1f} min</td></tr>
            </table>
            <p style="color:#6b7280;font-size:12px;margin-top:32px;">
                Email automático del sistema de monitorización de crons ({module_label}).
                Kill switch: <code>CRON_ALERTS_ENABLED=false</code>.
            </p>
        </body></html>
        """

        subject = (
            f"{icon} [{env_name.upper()}] {module_label} Cron {severity.upper()} · "
            f"{successful}/{total} OK · {keywords} keywords"
        )

        from email_service import send_email
        sent = send_email(cfg['email'], subject, html)
        logger.info(f"[cron_alerts] {module_label} completion email severity={severity} sent={bool(sent)}")
        return {'email_sent': bool(sent), 'severity': severity}

    except Exception as e:
        logger.warning(f"[cron_alerts] {module_label} completion email failed: {e}")
        return {'email_sent': False, 'reason': f'send_exception: {e}'}


def send_run_completion_email(run_id: int, get_db_connection_fn=None) -> Dict:
    """
    SIEMPRE envía un email al terminar un run (a menos que el kill switch
    CRON_ALERTS_ENABLED=false esté activo). El asunto refleja la severidad:

      - ✅ OK         → run completado sin fallos ni umbrales superados
      - ⚠️ WARNING    → algún proyecto falló o algún umbral medio superado
      - 🚨 CRITICAL   → run con status='failed' o umbral alto superado

    Internamente reutiliza los tres checks (duration / error rate / cost spike)
    y los anexa al cuerpo cuando aplican. Nunca lanza excepción.
    """
    cfg = _get_config()
    if not cfg['enabled']:
        return {'email_sent': False, 'reason': 'disabled'}

    if get_db_connection_fn is None:
        try:
            from database import get_db_connection as _gdc
            get_db_connection_fn = _gdc
        except Exception as e:
            logger.warning(f"[cron_alerts] cannot import get_db_connection: {e}")
            return {'email_sent': False, 'reason': 'no_db_import'}

    run = _load_run(run_id, get_db_connection_fn)
    if not run:
        return {'email_sent': False, 'reason': 'run_not_found'}

    alerts: List[Dict] = []
    try:
        a = _check_duration(run, cfg['duration_min_threshold'])
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] duration check failed: {e}")
    try:
        a = _check_error_rate(run, cfg['error_rate_threshold'])
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] error-rate check failed: {e}")
    try:
        a = _check_cost_spike(get_db_connection_fn, cfg['cost_multiplier_threshold'])
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] cost-spike check failed: {e}")
    try:
        a = _check_provider_coverage(run, get_db_connection_fn)
        if a: alerts.append(a)
    except Exception as e:
        logger.warning(f"[cron_alerts] provider-coverage check failed: {e}")

    run_cost = _load_run_cost(run, get_db_connection_fn)
    errors = _load_top_errors(run, get_db_connection_fn, limit=10)
    severity = _derive_severity(run, alerts)

    subject_icon = {'ok': '✅', 'warning': '⚠️', 'critical': '🚨'}[severity]
    subject = (
        f"{subject_icon} [{cfg['environment'].upper()}] LLM Cron {severity.upper()} · "
        f"run #{run['id']} · {run.get('successful_projects',0)}/{run.get('total_projects',0)} OK"
    )

    try:
        from email_service import send_email
        html = _build_completion_email_html(run, alerts, run_cost, errors,
                                            cfg['environment'], severity)
        sent = send_email(cfg['email'], subject, html)
        logger.info(f"[cron_alerts] completion email run {run_id} severity={severity} sent={bool(sent)}")
        return {
            'email_sent': bool(sent),
            'severity': severity,
            'alerts_triggered': len(alerts),
            'alerts': [a['type'] for a in alerts],
        }
    except Exception as e:
        logger.warning(f"[cron_alerts] completion email failed for run {run_id}: {e}")
        return {'email_sent': False, 'reason': f'send_exception: {e}'}
