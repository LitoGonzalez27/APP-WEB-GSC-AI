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
        return jsonify({
            'success': True,
            'message': 'Quota reset completed',
            'triggered_by': triggered_by,
            'health_check': health,
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
    return jsonify({'success': True, 'health': health}), 200


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
