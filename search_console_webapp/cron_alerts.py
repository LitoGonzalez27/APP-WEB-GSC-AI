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
