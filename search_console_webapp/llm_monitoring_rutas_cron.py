"""Rutas de cron y salud de LLM Monitoring: análisis diario (/cron/daily-analysis),
watchdog (/cron/watchdog), alerta genérica de los servicios Bun (/cron/alert) y
comprobación de salud (/health).

Sacadas tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros gigantes).
Registran sus rutas en el blueprint de llm_monitoring_base al importarse;
llm_monitoring_routes importa este módulo y vuelve a exponer sus nombres. Para
parchear algo que usen estas rutas en un test (threading, analyze_all_active_projects,
cron_service...), hazlo en este módulo.
"""

import logging
from auth import cron_or_auth_required
from database import acquire_analysis_lock, get_db_connection, get_latest_analysis_run, release_analysis_lock
from datetime import datetime
from flask import jsonify, request
from services.llm_monitoring_service import MultiLLMMonitoringService, analyze_all_active_projects, cron_service_tier
import config
import html
import os
import threading
from llm_monitoring_base import (
    _ensure_cron_token_or_admin,
    _safe_notify_email,
    llm_monitoring_bp,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CRON JOBS
# ============================================================================

@llm_monitoring_bp.route('/cron/daily-analysis', methods=['POST'])
@cron_or_auth_required
def trigger_daily_analysis():
    """
    Trigger para análisis diario automático (cron job)

    Query params:
        async (int): Si es 1, ejecuta en background y responde inmediatamente con 202
        project_id (int): Si se proporciona, analiza SOLO ese proyecto (útil para re-runs)

    Returns:
        JSON con resultado de la ejecución del cron
    """
    auth_error = _ensure_cron_token_or_admin()
    if auth_error:
        return auth_error

    try:
        # Verificar si se solicita ejecución asíncrona
        is_async = request.args.get('async', '0') == '1'
        triggered_by = request.args.get('triggered_by', 'cron')
        single_project_id = request.args.get('project_id', type=int)

        # --- Modo proyecto individual (sin lock global) ---
        if single_project_id:
            def run_single_project(pid):
                # Re-run por cron/admin: misma cola barata que el batch diario
                service = MultiLLMMonitoringService(api_keys=None, service_tier=cron_service_tier())
                result = service.analyze_project(project_id=pid, max_workers=8)
                # 🩹 Fase B también en re-runs de proyecto único: si quedaron
                # huecos, reintentar solo los pares faltantes y reconstruir
                # snapshots. Nunca debe tumbar el run principal.
                try:
                    if isinstance(result, dict) and result.get('incomplete_llms'):
                        from services.llm_monitoring_service import _run_completion_pass
                        _run_completion_pass(service, [result], max_workers=8)
                except Exception as completion_err:
                    logger.error(f"Error en pasada de completitud (single project {pid}): {completion_err}", exc_info=True)
                return result

            if is_async:
                def run_single_bg():
                    try:
                        logger.info(f"🚀 LLM Monitoring: Single project analysis started (project_id={single_project_id})")
                        result = run_single_project(single_project_id)
                        logger.info(f"✅ LLM Monitoring: Single project analysis done: {result.get('total_queries_executed', 0)} queries")
                    except Exception as e:
                        logger.error(f"💥 LLM Monitoring: Single project analysis error: {e}")

                thread = threading.Thread(target=run_single_bg, daemon=True)
                thread.start()
                return jsonify({
                    'success': True,
                    'message': f'Analysis for project {single_project_id} triggered in background',
                    'async': True,
                    'project_id': single_project_id
                }), 202

            result = run_single_project(single_project_id)
            return jsonify({
                'success': result.get('success', result.get('total_queries_executed', 0) > 0),
                'project_id': single_project_id,
                'result': result
            }), 200

        # --- Modo todos los proyectos (comportamiento original) ---
        if is_async:
            # ✅ NUEVO: Intentar adquirir lock ANTES de lanzar thread
            run_id = acquire_analysis_lock(triggered_by=triggered_by)
            if run_id is None:
                # Ya hay un análisis en curso
                latest_run = get_latest_analysis_run()
                return jsonify({
                    'success': False,
                    'error': 'Analysis already running',
                    'message': 'An analysis is already in progress. Please wait for it to finish before starting another.',
                    'latest_run': latest_run
                }), 409  # Conflict

            # Ejecutar en background con lock y state tracking
            def run_analysis_in_background(run_id):
                try:
                    logger.info(f"🚀 LLM Monitoring: Starting daily analysis in background (run_id={run_id})")
                    results = analyze_all_active_projects(
                        api_keys=None,  # Usar variables de entorno
                        max_workers=10
                    )

                    # Procesar resultados
                    successful = sum(1 for r in results if 'error' not in r)
                    failed = sum(1 for r in results if 'error' in r)
                    total_queries = sum(r.get('total_queries_executed', 0) for r in results if 'error' not in r)

                    logger.info(f"✅ LLM Monitoring: Daily analysis completed - {len(results)} projects processed")
                    logger.info(f"   Successful: {successful}, Failed: {failed}, Total queries: {total_queries}")

                    # ✅ Liberar lock y registrar resultados (con detalle por proyecto)
                    release_analysis_lock(
                        run_id=run_id,
                        total_projects=len(results),
                        successful=successful,
                        failed=failed,
                        total_queries=total_queries,
                        project_results=results
                    )
                except Exception as e:
                    logger.error(f"💥 LLM Monitoring: Background analysis error: {e}")
                    # ✅ Liberar lock incluso en caso de error
                    release_analysis_lock(run_id=run_id, error_message=str(e))

            # Iniciar thread en background
            thread = threading.Thread(target=run_analysis_in_background, args=(run_id,), daemon=True)
            thread.start()

            logger.info(f"📤 LLM Monitoring: Daily analysis triggered (async mode, run_id={run_id})")
            return jsonify({
                'success': True,
                'message': 'Daily analysis triggered in background',
                'async': True,
                'run_id': run_id
            }), 202

        # Modo síncrono (comportamiento original) — también con lock
        run_id = acquire_analysis_lock(triggered_by=triggered_by)
        if run_id is None:
            latest_run = get_latest_analysis_run()
            return jsonify({
                'success': False,
                'error': 'Analysis already running',
                'message': 'An analysis is already in progress. Please wait for it to finish before starting another.',
                'latest_run': latest_run
            }), 409

        try:
            results = analyze_all_active_projects(
                api_keys=None,
                max_workers=10
            )

            successful = sum(1 for r in results if 'error' not in r)
            failed = sum(1 for r in results if 'error' in r)
            total_queries = sum(r.get('total_queries_executed', 0) for r in results if 'error' not in r)

            release_analysis_lock(
                run_id=run_id,
                total_projects=len(results),
                successful=successful,
                failed=failed,
                total_queries=total_queries,
                project_results=results
            )

            return jsonify({
                'success': True,
                'total_projects': len(results),
                'successful': successful,
                'failed': failed,
                'total_queries': total_queries,
                'run_id': run_id,
                'results': results
            }), 200
        except Exception as e:
            release_analysis_lock(run_id=run_id, error_message=str(e))
            raise

    except Exception as e:
        logger.error(f"Error in daily analysis cron trigger: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@llm_monitoring_bp.route('/cron/watchdog', methods=['POST', 'GET'])
@cron_or_auth_required
def cron_watchdog():
    """
    Watchdog para detectar que el cron LLM Monitoring NO se está ejecutando.

    Diseñado para ser llamado por otro function-bun Railway en un cron diario.
    Mira el último run con status='completed' y, si pasa más de
    LLM_WATCHDOG_MAX_HOURS desde entonces (default 36h), envía email crítico.

    Query/body params:
        max_hours (int, opcional): umbral en horas (default env LLM_WATCHDOG_MAX_HOURS / 36)
        notify_email (str, opcional): destinatario (default CRON_ALERTS_EMAIL)

    Returns:
        JSON con state: 'ok' | 'stale' | 'never_run' y detalles.
    """
    auth_error = _ensure_cron_token_or_admin()
    if auth_error:
        return auth_error

    try:
        max_hours = request.args.get('max_hours', type=int)
        if max_hours is None:
            payload = request.get_json(silent=True) or {}
            max_hours = payload.get('max_hours')
        if max_hours is None:
            try:
                max_hours = int(os.getenv('LLM_WATCHDOG_MAX_HOURS', '36'))
            except Exception:
                max_hours = 36

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'no_db_connection'}), 503
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, started_at, completed_at, status,
                       total_projects, successful_projects, failed_projects,
                       total_queries, triggered_by
                FROM llm_monitoring_analysis_runs
                WHERE status = 'completed'
                ORDER BY completed_at DESC NULLS LAST
                LIMIT 1
            """)
            last = cur.fetchone()
        finally:
            try: cur.close()
            except Exception: pass
            conn.close()

        now = datetime.utcnow()

        if not last:
            state = 'never_run'
            hours_since = None
            last_dict = None
            severity_msg = (
                f'No existe ningún run con status=completed en llm_monitoring_analysis_runs. '
                f'El watchdog se acaba de instalar, o el cron LLM Monitoring nunca ha completado.'
            )
        else:
            last_dict = dict(last) if not isinstance(last, dict) else last
            completed_at = last_dict.get('completed_at')
            if completed_at is None:
                hours_since = None
                state = 'stale'
                severity_msg = 'El último run en BD no tiene completed_at — estado incoherente.'
            else:
                # Normalize tz
                ref = completed_at
                if hasattr(ref, 'tzinfo') and ref.tzinfo is not None:
                    from datetime import timezone
                    now_cmp = datetime.now(timezone.utc)
                else:
                    now_cmp = now
                hours_since = (now_cmp - ref).total_seconds() / 3600.0
                if hours_since > max_hours:
                    state = 'stale'
                    severity_msg = (
                        f'Último análisis completado hace {hours_since:.1f}h '
                        f'(umbral: {max_hours}h). El cron LLM Monitoring podría no estar disparándose. '
                        f'Revisa Railway → function-bun-LLMs.'
                    )
                else:
                    state = 'ok'
                    severity_msg = None

        response = {
            'success': True,
            'state': state,
            'hours_since_last_run': hours_since,
            'max_hours': max_hours,
            'last_run': {
                'id': last_dict.get('id') if last_dict else None,
                'completed_at': str(last_dict.get('completed_at')) if last_dict else None,
                'status': last_dict.get('status') if last_dict else None,
                'total_projects': last_dict.get('total_projects') if last_dict else None,
                'successful_projects': last_dict.get('successful_projects') if last_dict else None,
                'failed_projects': last_dict.get('failed_projects') if last_dict else None,
            } if last_dict else None,
        }

        if state == 'ok':
            return jsonify(response), 200

        # state in ('stale', 'never_run') → send critical email
        try:
            payload = request.get_json(silent=True) or {}
            notify_email = _safe_notify_email(payload.get('notify_email'))
            from email_service import send_email
            env_name = config.etiqueta_entorno()
            last_info = ''
            if last_dict:
                last_info = (
                    f"<li>Run #{last_dict.get('id')}</li>"
                    f"<li>Completed at: <code>{last_dict.get('completed_at')}</code></li>"
                    f"<li>Status: <code>{last_dict.get('status')}</code></li>"
                    f"<li>Projects: {last_dict.get('successful_projects')}/{last_dict.get('total_projects')} OK · {last_dict.get('failed_projects')} fallidos</li>"
                )
            else:
                last_info = '<li>No previous run found.</li>'
            html = f"""
            <!DOCTYPE html>
            <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                               max-width:700px;margin:0 auto;padding:24px;color:#111827;">
                <h2 style="color:#dc2626;margin-top:0;">🚨 Watchdog LLM Monitoring — Cron no se ha ejecutado</h2>
                <p>Entorno: <strong>{env_name}</strong></p>
                <p>{severity_msg}</p>
                <h3>Último run conocido</h3>
                <ul>{last_info}</ul>
                <p style="color:#6b7280;font-size:12px;margin-top:24px;">
                    Watchdog automático. Umbral: {max_hours}h. Para ajustar: <code>LLM_WATCHDOG_MAX_HOURS</code>.
                </p>
            </body></html>
            """
            subject = f"🚨 [{env_name.upper()}] LLM Monitoring watchdog · {state.upper()}"
            sent = send_email(notify_email, subject, html)
            response['email_sent'] = bool(sent)
        except Exception as mail_err:
            logger.warning(f"Watchdog email send failed: {mail_err}")
            response['email_sent'] = False
            response['email_error'] = str(mail_err)

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in cron watchdog: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================

@llm_monitoring_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check del sistema LLM Monitoring
    
    Returns:
        JSON con estado del sistema
    """
    # Verificar conexión a BD
    conn = get_db_connection()
    if not conn:
        return jsonify({
            'status': 'error',
            'database': 'disconnected'
        }), 503
    cur = None
    try:
        cur = conn.cursor()

        # Contar proyectos activos
        cur.execute("SELECT COUNT(*) as count FROM llm_monitoring_projects WHERE is_active = TRUE")
        active_projects = cur.fetchone()['count']
        
        # Verificar API keys disponibles
        api_keys_available = {
            'openai': bool(os.getenv('OPENAI_API_KEY')),
            'anthropic': bool(os.getenv('ANTHROPIC_API_KEY')),
            'google': bool(os.getenv('GOOGLE_API_KEY')),
            'perplexity': bool(os.getenv('PERPLEXITY_API_KEY'))
        }
        
        return jsonify({
            'status': 'ok',
            'database': 'connected',
            'active_projects': active_projects,
            'api_keys_configured': sum(api_keys_available.values()),
            'api_keys': api_keys_available
        }), 200

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': 'Internal server error'
        }), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


@llm_monitoring_bp.route('/cron/alert', methods=['POST'])
@cron_or_auth_required
def cron_alert():
    """
    Endpoint para alertas de cron (fallos o warnings).
    Reutiliza el sistema de email existente.
    
    Payload JSON opcional:
        - notify_email
        - job_name
        - status (failed|warning|ok)
        - message
        - endpoint
        - response_status
        - response_body
        - run_at
    """
    auth_error = _ensure_cron_token_or_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    
    notify_email = _safe_notify_email(data.get('notify_email') or request.args.get('notify_email'))

    job_name = data.get('job_name') or 'Cron'
    status = (data.get('status') or 'failed').lower()
    message = data.get('message') or 'Fallo no especificado'
    endpoint = data.get('endpoint') or ''
    response_status = data.get('response_status')
    response_body = data.get('response_body') or ''
    run_at = data.get('run_at') or datetime.utcnow().isoformat()
    
    def _truncate(value: str, max_len: int = 2000) -> str:
        # Escapa HTML: estos valores vienen del cuerpo de la petición y se
        # interpolan en un email HTML → evitar inyección de HTML/enlaces.
        if value is None:
            return ''
        text = str(value)
        if len(text) > max_len:
            text = text[:max_len] + "…"
        return html.escape(text)
    
    status_icon = "🚨" if status == "failed" else "⚠️" if status == "warning" else "✅"
    subject = f"{status_icon} Cron {status.upper()}: {job_name}"
    
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <h1 style="color: #161616; border-bottom: 3px solid #D8F9B8; padding-bottom: 10px;">
            {status_icon} Alerta de Cron
        </h1>
        <p style="color: #666;">Fecha: {html.escape(str(run_at))} UTC</p>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
            <tr style="background: #161616; color: #D8F9B8;">
                <th style="padding: 10px; text-align: left;">Campo</th>
                <th style="padding: 10px; text-align: left;">Valor</th>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">Job</td>
                <td style="padding: 10px;">{html.escape(str(job_name))}</td>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">Estado</td>
                <td style="padding: 10px;">{html.escape(str(status).upper())}</td>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">Endpoint</td>
                <td style="padding: 10px;">{_truncate(endpoint, 300)}</td>
            </tr>
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">HTTP Status</td>
                <td style="padding: 10px;">{response_status}</td>
            </tr>
        </table>
        <h3 style="color: #161616;">Mensaje</h3>
        <pre style="background: #f9fafb; padding: 12px; border-radius: 8px; white-space: pre-wrap; word-break: break-word;">{_truncate(message)}</pre>
        <h3 style="color: #161616;">Respuesta</h3>
        <pre style="background: #f9fafb; padding: 12px; border-radius: 8px; white-space: pre-wrap; word-break: break-word;">{_truncate(response_body)}</pre>
        <hr style="margin: 24px 0; border: none; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px; text-align: center;">
            ClicAndSEO - Alerta automática de cron
        </p>
    </div>
    """
    
    email_sent = False
    if notify_email:
        try:
            from email_service import send_email
            email_sent = send_email(notify_email, subject, html_body)
            logger.info(f"📧 Alerta de cron enviada a {notify_email}")
        except Exception as e:
            logger.error(f"❌ Error enviando alerta de cron: {e}")
    
    return jsonify({
        'success': True,
        'email_sent': email_sent,
        'notify_email': notify_email,
        'job_name': job_name,
        'status': status
    }), 200
