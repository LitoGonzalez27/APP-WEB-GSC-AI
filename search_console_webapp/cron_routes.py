"""
HTTP endpoints invoked by Railway Bun cron functions for non-LLM-monitoring crons.

Currently exposes:
  POST /api/cron/quota-reset   — runs the daily quota reset (with health check).

Auth: Bearer CRON_TOKEN (env). Same pattern as the existing LLM monitoring
cron endpoint at /api/llm-monitoring/cron/daily-analysis.

This file exists because the previous mechanism — a Python script defined under
the `crons` key of railway.json — was silently NOT executed by Railway in this
project. The crons that actually fire on Railway are dedicated Bun function
services that POST to HTTP endpoints with a CRON_TOKEN bearer. This file gives
quota reset the same shape, so a new function-bun-Quota-Reset service can
trigger it on a `30 1 * * *` schedule.
"""

import os
import logging
import secrets
import threading

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

cron_bp = Blueprint('cron', __name__, url_prefix='/api/cron')


def _ensure_cron_token():
    """Verify Authorization: Bearer <CRON_TOKEN>. Returns Flask response on failure, None on success."""
    auth_header = request.headers.get('Authorization', '') or ''
    token = auth_header[7:].strip() if auth_header.lower().startswith('bearer ') else ''
    cron_secret = os.environ.get('CRON_TOKEN') or os.environ.get('CRON_SECRET')
    if not cron_secret or not token or not secrets.compare_digest(token, cron_secret):
        return jsonify({
            'success': False,
            'error': 'forbidden',
            'message': 'Valid CRON_TOKEN bearer token required'
        }), 403
    return None


# ---------------------------------------------------------------------------
# Quota reset endpoint
# ---------------------------------------------------------------------------

@cron_bp.route('/quota-reset', methods=['POST'])
def trigger_quota_reset():
    """
    Trigger the monthly quota reset cron.

    Query params:
        async=1        → run in background, respond 202 immediately
        triggered_by=  → label stored in logs (defaults to "cron")

    Returns:
        202 in async mode, 200 in sync mode with the health-check summary.
    """
    auth_error = _ensure_cron_token()
    if auth_error:
        return auth_error

    is_async = request.args.get('async', '0') == '1'
    triggered_by = request.args.get('triggered_by', 'cron')

    if is_async:
        def run_bg():
            try:
                logger.info(f"🚀 quota-reset cron triggered (by={triggered_by}, async)")
                from daily_quota_reset_cron import main as run_reset
                run_reset()
                _run_health_check_and_alert()
                _run_module_staleness_check()
                logger.info("✅ quota-reset cron finished (async)")
            except Exception as e:
                logger.error(f"💥 quota-reset bg error: {e}", exc_info=True)

        thread = threading.Thread(target=run_bg, daemon=True, name='quota-reset-bg')
        thread.start()
        return jsonify({
            'success': True,
            'message': 'Quota reset triggered in background',
            'async': True,
            'triggered_by': triggered_by,
        }), 202

    # Sync mode
    try:
        logger.info(f"🚀 quota-reset cron triggered (by={triggered_by}, sync)")
        from daily_quota_reset_cron import main as run_reset
        run_reset()
        health = _run_health_check_and_alert()
        staleness = _run_module_staleness_check()
        return jsonify({
            'success': True,
            'message': 'Quota reset completed',
            'triggered_by': triggered_by,
            'health_check': health,
            'cron_staleness': staleness,
        }), 200
    except Exception as e:
        logger.error(f"❌ quota-reset sync error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Quota health check (defensive monitoring)
# ---------------------------------------------------------------------------

@cron_bp.route('/quota-health-check', methods=['POST', 'GET'])
def quota_health_check_endpoint():
    """
    Standalone health check — useful for ad-hoc verification or as a separate
    cron that runs OUTSIDE the reset window (e.g. once during business hours)
    so that, even if the reset cron itself fails to fire, we still detect
    stuck users within 24h.
    """
    auth_error = _ensure_cron_token()
    if auth_error:
        return auth_error
    health = _run_health_check_and_alert()
    staleness = _run_module_staleness_check()
    return jsonify({'success': True, 'health': health, 'cron_staleness': staleness}), 200


def _run_health_check_and_alert():
    """
    Detect users whose quota_reset_date is more than 24h in the past — these
    are paying users that should have already been reset by the cron. If any
    are found, send an alert email (gated by CRON_ALERTS_ENABLED) so we
    detect a regression in <24h instead of in 49 days like last time.

    Returns a dict suitable for embedding in the API response.
    """
    from database import get_db_connection

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return {'ok': False, 'reason': 'no_db_conn'}

        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, plan,
                   quota_reset_date::date AS reset_date,
                   quota_used, quota_limit
            FROM users
            WHERE plan != 'free'
              AND billing_status IN ('active', 'trialing', 'beta')
              AND quota_reset_date IS NOT NULL
              AND quota_reset_date < NOW() - INTERVAL '1 day'
            ORDER BY quota_reset_date
        """)
        rows = cur.fetchall() or []

        stuck = []
        for r in rows:
            if isinstance(r, dict):
                stuck.append({
                    'id': r['id'], 'email': r['email'], 'plan': r['plan'],
                    'reset': str(r['reset_date']),
                    'quota_used': r['quota_used'], 'quota_limit': r['quota_limit'],
                })
            else:
                stuck.append({
                    'id': r[0], 'email': r[1], 'plan': r[2], 'reset': str(r[3]),
                    'quota_used': r[4], 'quota_limit': r[5],
                })

        if stuck:
            logger.warning(f"⚠️ Quota health check: {len(stuck)} stuck users")
            try:
                _send_stuck_quota_alert(stuck)
            except Exception as e:
                logger.error(f"Failed to send stuck quota alert (non-fatal): {e}")
            return {'ok': False, 'stuck_count': len(stuck), 'stuck_users': stuck}

        logger.info("✅ Quota health check: all paying users healthy")
        return {'ok': True, 'stuck_count': 0}

    except Exception as e:
        logger.error(f"Quota health check failed: {e}", exc_info=True)
        return {'ok': False, 'reason': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _run_module_staleness_check():
    """
    Detecta crons de análisis (Manual AI / AI Mode) que llevan demasiados días
    sin producir resultados pese a tener proyectos elegibles.

    Los crons corren lunes/jueves/sábado, así que el hueco normal máximo es de
    3 días. Si hay proyectos elegibles con frecuencia estándar (1 día) y el
    último analysis_date es más antiguo que CRON_STALENESS_MAX_DAYS (default 4),
    se envía un email de alerta. Se ignoran los proyectos con frecuencia
    personalizada (analysis_frequency_days > 1) porque sus huecos largos son
    intencionados.

    Corre a diario tras el quota-reset, igual que el health-check de cuotas.
    Nunca lanza excepción.
    """
    from database import get_db_connection

    max_days = int(os.getenv('CRON_STALENESS_MAX_DAYS', '4'))
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return {'ok': None, 'reason': 'no_db_conn'}

        cur = conn.cursor()
        stale = []
        modules = [
            ('Manual AI (AI Overview)', 'manual_ai_projects', 'manual_ai_results', 'manual_ai_keywords'),
            ('AI Mode', 'ai_mode_projects', 'ai_mode_results', 'ai_mode_keywords'),
        ]
        for label, ptable, rtable, ktable in modules:
            cur.execute(f"""
                SELECT COUNT(DISTINCT p.id) AS eligible,
                       MAX(r.analysis_date) AS last_date
                FROM {ptable} p
                JOIN users u ON u.id = p.user_id
                LEFT JOIN {rtable} r ON r.project_id = p.id
                WHERE p.is_active = TRUE
                  AND COALESCE(p.is_paused_by_quota, FALSE) = FALSE
                  AND COALESCE(p.analysis_frequency_days, 1) = 1
                  AND COALESCE(u.plan, 'free') <> 'free'
                  AND COALESCE(u.billing_status, '') NOT IN ('canceled')
                  AND EXISTS (SELECT 1 FROM {ktable} k
                              WHERE k.project_id = p.id AND k.is_active = TRUE)
            """)
            row = cur.fetchone()
            if isinstance(row, dict):
                eligible, last_date = row.get('eligible') or 0, row.get('last_date')
            else:
                eligible, last_date = (row[0] or 0) if row else 0, row[1] if row else None

            if eligible > 0:
                from datetime import date as _date
                days_since = (_date.today() - last_date).days if last_date else None
                if last_date is None or days_since > max_days:
                    stale.append({
                        'module': label,
                        'eligible_projects': eligible,
                        'last_analysis': str(last_date) if last_date else 'nunca',
                        'days_since': days_since if days_since is not None else '∞',
                    })

        if stale:
            logger.warning(f"⚠️ Cron staleness check: {len(stale)} module(s) stale: "
                           f"{[s['module'] for s in stale]}")
            try:
                _send_stale_cron_alert(stale, max_days)
            except Exception as e:
                logger.error(f"Failed to send stale-cron alert (non-fatal): {e}")
            return {'ok': False, 'stale_modules': stale}

        logger.info("✅ Cron staleness check: all analysis crons producing results")
        return {'ok': True, 'stale_modules': []}

    except Exception as e:
        logger.error(f"Cron staleness check failed: {e}", exc_info=True)
        return {'ok': None, 'reason': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _send_stale_cron_alert(stale_modules, max_days):
    """Email de alerta cuando un cron de análisis lleva días sin producir datos."""
    if os.getenv('CRON_ALERTS_ENABLED', 'true').lower() != 'true':
        logger.info("Stale-cron alert suppressed: CRON_ALERTS_ENABLED=false")
        return

    try:
        from email_service import send_email
    except Exception as e:
        logger.error(f"Cannot import email_service: {e}")
        return

    to = os.getenv('CRON_ALERTS_EMAIL', 'info@soycarlosgonzalez.com')
    env_name = os.getenv('APP_ENV', os.getenv('RAILWAY_ENVIRONMENT_NAME', 'unknown'))

    rows_html = ''.join(
        f"""<tr>
            <td style="padding:6px;border:1px solid #e5e7eb">{m['module']}</td>
            <td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{m['eligible_projects']}</td>
            <td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{m['last_analysis']}</td>
            <td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{m['days_since']}</td>
        </tr>"""
        for m in stale_modules
    )

    html = f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
        <h2 style="color:#dc2626;margin-top:0">🚨 Cron de análisis parado — {len(stale_modules)} módulo(s)</h2>
        <p><strong>Entorno:</strong> {env_name}</p>
        <p>Hay módulos con proyectos elegibles cuyo último análisis tiene más de {max_days} días.
           Los crons corren lunes/jueves/sábado (04:00 UTC), así que esto indica que el cron
           no se está disparando o está fallando antes de procesar nada.</p>
        <p>Acción recomendada: revisar los logs del servicio Bun correspondiente en Railway
           (<code>function-bun-AI-Overview</code> / <code>function-bun-AI-Mode</code>) y, si hace falta,
           disparar el cron manualmente con bearer CRON_TOKEN.</p>
        <table style="border-collapse:collapse;font-size:14px;margin-top:12px">
            <thead><tr style="background:#f9fafb">
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Módulo</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Proyectos elegibles</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Último análisis</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Días</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <p style="color:#6b7280;font-size:12px;margin-top:24px">
            Disparado automáticamente por <code>cron_routes._run_module_staleness_check</code>
            tras el quota-reset diario. Para silenciar: <code>CRON_ALERTS_ENABLED=false</code>.
        </p>
    </body></html>
    """

    subject = f"🚨 [{env_name.upper()}] Cron de análisis parado — {', '.join(m['module'] for m in stale_modules)}"
    send_email(to, subject, html)
    logger.info(f"📧 Stale-cron alert sent to {to} ({len(stale_modules)} modules)")


def _send_stuck_quota_alert(stuck_users):
    """Send the alert email. Silenced by CRON_ALERTS_ENABLED=false."""
    if os.getenv('CRON_ALERTS_ENABLED', 'true').lower() != 'true':
        logger.info("Stuck-quota alert suppressed: CRON_ALERTS_ENABLED=false")
        return

    try:
        from email_service import send_email
    except Exception as e:
        logger.error(f"Cannot import email_service: {e}")
        return

    to = os.getenv('CRON_ALERTS_EMAIL', 'info@soycarlosgonzalez.com')
    env_name = os.getenv('APP_ENV', os.getenv('RAILWAY_ENVIRONMENT_NAME', 'unknown'))

    rows_html = ''.join(
        f"""<tr>
            <td style="padding:6px;border:1px solid #e5e7eb">{u['id']}</td>
            <td style="padding:6px;border:1px solid #e5e7eb">{u['email']}</td>
            <td style="padding:6px;border:1px solid #e5e7eb">{u['plan']}</td>
            <td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{u['reset']}</td>
            <td style="padding:6px;border:1px solid #e5e7eb;font-family:monospace">{u['quota_used']}/{u['quota_limit']}</td>
        </tr>"""
        for u in stuck_users
    )

    html = f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
        <h2 style="color:#dc2626;margin-top:0">🚨 Quota Reset Stuck — {len(stuck_users)} usuario(s) afectado(s)</h2>
        <p><strong>Entorno:</strong> {env_name}</p>
        <p>El health-check ha detectado usuarios con <code>quota_reset_date</code> >24 h en el pasado.
           Esto indica que el cron de reset NO los ha procesado — probablemente porque el cron
           no se ha ejecutado, o ha fallado silenciosamente para estos usuarios concretos.</p>
        <p>Acción recomendada: ejecutar manualmente
           <code>POST /api/cron/quota-reset?async=1</code> con bearer CRON_TOKEN, o disparar
           el script <code>daily_quota_reset_cron.py</code> contra la BD afectada.</p>
        <table style="border-collapse:collapse;font-size:14px;margin-top:12px">
            <thead><tr style="background:#f9fafb">
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">user_id</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">email</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">plan</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">reset_date</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">quota</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <p style="color:#6b7280;font-size:12px;margin-top:24px">
            Disparado automáticamente por <code>cron_routes._run_health_check_and_alert</code>
            tras un run del cron. Para silenciar: <code>CRON_ALERTS_ENABLED=false</code>.
        </p>
    </body></html>
    """

    subject = f"[{env_name.upper()}] Quota reset stuck — {len(stuck_users)} user(s)"
    send_email(to, subject, html)
    logger.info(f"📧 Stuck-quota alert sent to {to} ({len(stuck_users)} users)")


# ---------------------------------------------------------------------------
# Blueprint registration helper
# ---------------------------------------------------------------------------

def register_cron_routes(app):
    """Wire the cron blueprint into the Flask app. Call once during app init."""
    app.register_blueprint(cron_bp)
    logger.info("🔧 cron_routes registered (POST /api/cron/quota-reset, /api/cron/quota-health-check)")
