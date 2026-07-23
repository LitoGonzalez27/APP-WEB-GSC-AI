# -*- coding: utf-8 -*-
"""Blueprint del Agent-Ready Scanner integrado en clicandseo.

Rutas (bajo /agent, solo admin):
  GET  /agent                 -> UI del scanner (single-page)
  POST /agent/api/scan        -> lanza un análisis en background, devuelve job id
  GET  /agent/api/status/<id> -> estado + log en vivo (polling)
  GET  /agent/api/result/<id> -> resultado completo (data JSON)

Los análisis corren en un hilo (uno a la vez por proceso). Para escalado a
clientes, mover a cola + worker + tabla en Postgres (Fase 2).
"""
import logging
import os
import threading
import time
import uuid
from functools import wraps
from urllib.parse import urlparse

from flask import (Blueprint, jsonify, redirect, request, send_from_directory,
                   session, url_for)

from auth import admin_required, get_current_user, is_user_authenticated

logger = logging.getLogger(__name__)

agent_bp = Blueprint("agent_scanner", __name__, url_prefix="/agent")


def agent_access_required(f):
    """Acceso al panel: admins SIEMPRE + emails de la allowlist (tabla aislada)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        wants_json = request.is_json or request.path.startswith("/agent/api/")
        if not is_user_authenticated():
            if wants_json:
                return jsonify({"error": "Authentication required", "auth_required": True}), 401
            return redirect(url_for("login_page") + "?auth_required=true")
        user = get_current_user()
        if not user or not user.get("is_active"):
            session.clear()
            if wants_json:
                return jsonify({"error": "Unauthorized", "auth_required": True}), 401
            return redirect(url_for("login_page") + "?auth_required=true")
        try:
            from agent_scanner.access import user_has_access
            allowed = user_has_access(user)
        except Exception as exc:
            logger.warning(f"agent access check falló, fallback a admin: {exc}")
            allowed = user.get("role") == "admin"
        if not allowed:
            if wants_json:
                return jsonify({"error": "No tienes acceso a esta herramienta"}), 403
            return redirect(url_for("login_page") + "?account_suspended=true")
        return f(*args, **kwargs)
    return wrapper

_WEB_DIR = os.path.join(os.path.dirname(__file__), "agent_scanner", "web")
_JOBS = {}
_JOBS_LOCK = threading.Lock()
_MAX_JOBS = 50
# El panel sondea /status cada pocos segundos. Si dejan de llegar polls, quien
# pidió el análisis se ha ido (cerró la pestaña, volvió atrás): pasado este
# margen el job se considera ABANDONADO y se cancela. 12s cubre el sondeo más
# lento (6s) con holgura para un poll perdido.
_ABANDONO_SEG = 12
# Tope absoluto: un análisis nunca debería pasar de esto; si lo hace, algo se
# colgó y no puede bloquear a los siguientes para siempre.
_JOB_MAX_SEG = 600


def _abandonado(job):
    """¿Nadie está mirando este análisis (o pidió cancelarlo, o se colgó)?"""
    if job.get("cancel"):
        return True
    ahora = time.time()
    if ahora - job.get("started", ahora) > _JOB_MAX_SEG:
        return True
    # last_seen se pone en el primer poll; hasta entonces, cuenta desde started
    return ahora - job.get("last_seen", job.get("started", ahora)) > _ABANDONO_SEG


def _hay_analisis_vivo():
    """Un análisis 'running' solo bloquea si de verdad sigue vivo: uno
    abandonado (pestaña cerrada) no puede impedir lanzar otro."""
    return any(j["status"] == "running" and not _abandonado(j)
               for j in _JOBS.values())


def _run_job(job_id, urls, opts):
    from agent_scanner import engine
    job = _JOBS[job_id]
    # el motor consulta esto en cada punto de progreso y aborta si el usuario se
    # fue (pestaña cerrada -> sin polls -> abandonado) o pidió cancelar.
    engine.CANCEL_CHECK = lambda: _abandonado(job)
    try:
        cats = set(opts.get("cats") or [])
        audits = []
        for i, u in enumerate(urls):
            if _abandonado(job):
                raise engine.AnalisisCancelado()
            job["domains"][i]["state"] = "running"
            job["phase"] = f"Auditando {job['domains'][i]['host']}"
            try:
                engine.LOG_SINK = job["log"]
                a = engine.audit_domain(
                    u, typology_override=opts.get("type") or None,
                    skip_render=not opts.get("render", True),
                    with_psi=opts.get("psi", False),
                    categories=cats or None,
                    check_ids=set(opts.get("checks") or []) or None,
                    # Las pruebas agénticas NO corren aquí: son con diferencia lo
                    # más lento (10-15 min) y bloqueaban la lectura del panel.
                    # Se lanzan aparte desde el informe con "Simular agentes".
                    with_agents=False,
                    # identidad de Googlebot: solo si quien audita lo activa
                    # a conciencia (dominio propio o con permiso del cliente)
                    ua_googlebot=bool(opts.get("ua_googlebot")),
                    agentes_pendientes=bool(opts.get("agents")))
                audits.append(a)
                job["domains"][i].update(state="done", score=a["score"],
                                         emoji=a["level"]["emoji"], level=a["level"]["name"])
            except engine.AnalisisCancelado:
                raise          # la cancelación no es un error del dominio: sube
            except Exception as exc:
                audits.append({"domain": u, "error": str(exc)[:200]})
                job["domains"][i].update(state="error", error=str(exc)[:200])
                job["log"].append(f"error en {job['domains'][i]['host']}: {exc}")
        data = {
            "client": audits[0],
            "competitors": audits[1:],
            "framework_version": "2.0 (agent_scanner en clicandseo)",
            # el informe usa esto para ofrecer el botón "Simular agentes"
            "agentes": {
                "solicitados": bool(opts.get("agents")),
                "estado": "pendiente" if opts.get("agents") else "desactivadas",
                "allow_submit": bool(opts.get("allow_submit")),
                "repeticiones": int(opts.get("agent_reps") or 3),
            },
        }
        if "error" in audits[0]:
            job["status"] = "error"
            job["error"] = audits[0]["error"]
        else:
            job["result"] = data
            job["status"] = "done"
            job["phase"] = "Análisis completado"
            _guardar_informe(job_id, data, job.get("user_email"))
    except engine.AnalisisCancelado:
        # el usuario se fue: no es un fallo, es que el trabajo ya no interesa.
        # Se marca cancelado y se libera el hueco para el siguiente análisis.
        job["status"] = "cancelled"
        job["phase"] = "Análisis cancelado (abandonado)"
        job["log"].append("análisis cancelado: nadie estaba mirando")
    except Exception as exc:
        logger.exception("Fallo en job de agent_scanner")
        job["status"] = "error"
        job["error"] = str(exc)[:300]
    finally:
        from agent_scanner import engine
        engine.LOG_SINK = None
        engine.CANCEL_CHECK = None


def _aplicar_agentes(audit, agent_tests):
    """Integra el resultado agéntico en una auditoría YA calculada.

    Como el análisis base no guarda el contexto (sería muy pesado en memoria),
    se reconstruye solo lo que el check 6.3 necesita, se sustituye ese check y
    se recalcula la puntuación con el mismo scoring del motor. Así el panel
    refleja los agentes sin repetir las tres horas de sondas.
    """
    from agent_scanner import checks as checks_mod, scoring
    from agent_scanner.knowledge import advice_for

    ctx = {"agent_tests": agent_tests, "wellknown": {}, "home": {"body": ""},
           "pages": [], "login_probe": {"found": False}}
    nuevo = next(c for c in checks_mod.run_c6(ctx) if c["id"] == "6.3")
    if nuevo["score"] is not None and nuevo["score"] < 1:
        nuevo["advice"] = advice_for("6.3")

    audit["checks"] = [nuevo if c["id"] == "6.3" else c for c in audit["checks"]]
    total, cat_scores, weights, cobertura = scoring.total_score(
        audit["checks"], audit["typology"])
    adjusted, penalties = scoring.apply_governance_gate(
        total, audit["checks"], audit["typology"])
    # si el sitio nos cerró la puerta, correr agentes no cambia el veredicto:
    # sigue sin haber nota. Recalcularlo sin esto devolvía a "Agent-aware" al
    # dominio bloqueado en cuanto se lanzaba la segunda fase.
    bloqueado = (audit.get("acceso_degradado") or {}).get("nivel") == "total"
    audit.update({
        "score": adjusted, "score_pre_gate": total, "penalties": penalties,
        "cobertura_score": cobertura,
        "level": scoring.level_for(adjusted, bloqueado=bloqueado),
        "category_scores": cat_scores,
        "category_weights": {k: round(v, 1) for k, v in weights.items()},
        "agent_tests": agent_tests,
    })
    return audit


def _run_agents_job(job_id, opts):
    """Segunda fase: solo las pruebas agénticas, sobre un análisis ya hecho."""
    job = _JOBS[job_id]
    data = job["result"]
    try:
        from agent_scanner import engine
        from agent_scanner.agents import run_agent_tests
        engine.LOG_SINK = job["log"]
        dominios = [data["client"]] + [c for c in data["competitors"] if "error" not in c]
        logrados, fallidos = 0, []
        for i, audit in enumerate(dominios):
            host = audit.get("host", "?")
            job["agents_phase"] = f"Simulando agentes en {host}"
            job["log"].append(f"agentes en {host}…")
            try:
                at = run_agent_tests(
                    audit["domain"], audit["typology"],
                    # el envío real solo en el dominio del cliente (i == 0)
                    allow_submit=bool(opts.get("allow_submit")) and i == 0,
                    log=job["log"],
                    # rigor completo en el cliente, una pasada en competidores
                    repeticiones=(int(opts.get("agent_reps") or 3) if i == 0 else 1))
                _aplicar_agentes(audit, at)
                logrados += 1
                job["log"].append(f"  {host}: agentes completados")
            except Exception as exc:
                fallidos.append(host)
                logger.warning(f"agentes fallaron en {host}: {exc}")
                job["log"].append(f"  {host}: fallo en agentes ({str(exc)[:80]})")
        # Antes se marcaba "completado" pasara lo que pasara: si la simulación
        # reventaba en TODOS los dominios, el panel pintaba igualmente el botón
        # verde "✓ Agentes simulados". Decir que algo se comprobó sin haberlo
        # comprobado es el falso positivo que peor acaba: en un informe que un
        # CMO reenvía a su equipo técnico.
        if logrados == 0:
            data["agentes"]["estado"] = "error"
            data["agentes"]["detalle"] = (
                f"La simulación no pudo completarse en ningún dominio "
                f"({', '.join(fallidos) or 'sin dominios'}). El check 6.3 sigue "
                f"sin evidencia agéntica: no se ha comprobado.")
        else:
            data["agentes"]["estado"] = "completado"
            if fallidos:
                data["agentes"]["detalle"] = (
                    f"Simulación completada en {logrados}/{len(dominios)} dominios. "
                    f"Sin evidencia agéntica en: {', '.join(fallidos)}.")
        _guardar_informe(job_id, data, job.get("user_email"))
        job["agents_status"] = "done" if logrados else "error"
        if not logrados:
            job["agents_error"] = data["agentes"].get("detalle", "sin resultados")
        job["agents_phase"] = (
            f"Simulación agéntica completada ({logrados}/{len(dominios)} dominios)"
            if logrados else "La simulación agéntica no pudo completarse")
    except Exception as exc:
        logger.exception("Fallo en la simulación agéntica")
        job["agents_status"] = "error"
        job["agents_error"] = str(exc)[:300]
        if data.get("agentes"):
            data["agentes"]["estado"] = "error"
    finally:
        from agent_scanner import engine
        engine.LOG_SINK = None


@agent_bp.route("/api/agents/<job_id>", methods=["POST"])
@agent_access_required
def run_agents(job_id):
    """Lanza la simulación agéntica sobre un análisis ya terminado."""
    job = _JOBS.get(job_id)
    if not job or not job.get("result"):
        return jsonify({"error": "análisis desconocido o sin resultado"}), 404
    if job.get("agents_status") == "running":
        return jsonify({"error": "la simulación ya está en curso"}), 409
    with _JOBS_LOCK:
        if any(j.get("agents_status") == "running" for j in _JOBS.values()):
            return jsonify({"error": "Ya hay una simulación agéntica en curso"}), 409
    payload = request.get_json(silent=True) or {}
    solicitado = job["result"].get("agentes") or {}
    opts = {"allow_submit": payload.get("allow_submit", solicitado.get("allow_submit")),
            "agent_reps": payload.get("agent_reps", solicitado.get("repeticiones", 3))}
    job.update(agents_status="running", agents_phase="Preparando agentes…",
               agents_error=None, agents_started=time.time())
    job["result"]["agentes"]["estado"] = "corriendo"
    threading.Thread(target=_run_agents_job, args=(job_id, opts), daemon=True).start()
    return jsonify({"ok": True})


@agent_bp.route("/api/agents/<job_id>/status")
@agent_access_required
def agents_status(job_id):
    job = _JOBS.get(job_id)
    if not job:
        return jsonify({"error": "análisis desconocido"}), 404
    return jsonify({
        "status": job.get("agents_status", "idle"),
        "phase": job.get("agents_phase", ""),
        "error": job.get("agents_error"),
        "log": job["log"][-25:],
        "elapsed": round(time.time() - job["agents_started"]) if job.get("agents_started") else 0,
    })


@agent_bp.route("/")
@agent_access_required
def index():
    return send_from_directory(_WEB_DIR, "index.html")


@agent_bp.route("/api/scan", methods=["POST"])
@agent_access_required
def scan():
    with _JOBS_LOCK:
        # un análisis abandonado (pestaña cerrada) ya no bloquea: se marca para
        # que su hilo aborte en el siguiente punto de control, y se deja pasar.
        for j in _JOBS.values():
            if j["status"] == "running" and _abandonado(j):
                j["cancel"] = True
        if _hay_analisis_vivo():
            return jsonify({"error": "Ya hay un análisis en curso. Espera a que termine."}), 409
    payload = request.get_json(silent=True) or {}
    from agent_scanner.discovery import normalize
    from agent_scanner.httpfetch import assert_public_url, BlockedURLError
    raw = [u for u in payload.get("urls", []) if u and u.strip()][:3]
    urls = []
    for u in raw:
        n = normalize(u)
        try:
            assert_public_url(n)
        except BlockedURLError as exc:
            return jsonify({"error": f"URL no permitida ({u}): {exc}"}), 400
        urls.append(n)
    if not urls:
        return jsonify({"error": "Falta la URL de tu proyecto"}), 400

    jid = uuid.uuid4().hex[:10]
    with _JOBS_LOCK:
        if len(_JOBS) >= _MAX_JOBS:  # poda simple de jobs viejos
            for k in sorted(_JOBS, key=lambda k: _JOBS[k]["started"])[:10]:
                _JOBS.pop(k, None)
        _JOBS[jid] = {
            "status": "running", "phase": "Preparando análisis…", "log": [],
            "user_email": (get_current_user() or {}).get("email"),
            "started": time.time(), "last_seen": time.time(),
            "cancel": False, "error": None, "result": None,
            "domains": [{"url": u, "host": urlparse(u).netloc.replace("www.", ""),
                         "state": "pending", "score": None} for u in urls],
        }
    threading.Thread(target=_run_job, args=(jid, urls, payload), daemon=True).start()
    return jsonify({"id": jid})


@agent_bp.route("/api/status/<job_id>")
@agent_access_required
def status(job_id):
    job = _JOBS.get(job_id)
    if not job:
        return jsonify({"error": "análisis desconocido"}), 404
    # cada poll es la señal de que el usuario sigue mirando: renueva el latido.
    job["last_seen"] = time.time()
    slim = {k: v for k, v in job.items() if k != "result"}
    slim["log"] = job["log"][-40:]
    slim["elapsed"] = round(time.time() - job["started"])
    return jsonify(slim)


@agent_bp.route("/api/cancel/<job_id>", methods=["POST"])
@agent_access_required
def cancel(job_id):
    """El panel llama a esto al salir (cerrar pestaña, volver atrás). Marca el
    análisis para que su hilo aborte en el siguiente punto de control. Se acepta
    también por sendBeacon, que no espera respuesta."""
    job = _JOBS.get(job_id)
    if job and job["status"] == "running":
        job["cancel"] = True
    return jsonify({"cancelado": bool(job)})


def _resultado(job_id):
    """Resultado de un análisis: primero memoria, si no la base de datos.

    Los jobs viven en el proceso, así que un deploy o un reinicio los borra. La
    persistencia hace que un informe (y sus descargas de PDF/JSON) siga
    existiendo mañana, que es lo mínimo para entregarlo a un cliente.
    """
    job = _JOBS.get(job_id)
    if job and job.get("result") is not None:
        return job["result"]
    try:
        from agent_scanner.storage import cargar
        return cargar(job_id)
    except Exception:
        return None


def _guardar_informe(job_id, data, user_email=None):
    """Persiste el informe. Nunca puede tumbar un análisis que ya salió bien.

    OJO: se llama desde hilos de fondo, donde NO hay contexto de petición de
    Flask. Por eso el email se captura al crear el job y viaja en él, en vez de
    resolverse aquí con get_current_user().
    """
    try:
        from agent_scanner.storage import guardar
        if guardar(job_id, data, user_email):
            logger.info(f"agent_scanner: informe {job_id} persistido")
    except Exception as exc:
        logger.warning(f"agent_scanner: no se pudo persistir {job_id}: {exc}")


@agent_bp.route("/api/result/<job_id>")
@agent_access_required
def result(job_id):
    data = _resultado(job_id)
    if data is None:
        return jsonify({"error": "resultado no disponible"}), 404
    return jsonify(data)


# ---------------------------------------------------------------- gestión de acceso (solo admin)

@agent_bp.route("/api/report/<job_id>.pdf")
@agent_access_required
def report_pdf(job_id):
    """Informe PDF estructurado (CMO → equipo técnico)."""
    from flask import send_file
    data = _resultado(job_id)
    if data is None:
        return jsonify({"error": "resultado no disponible"}), 404
    try:
        from agent_scanner.report_pdf import build_pdf
        buf = build_pdf(data)
    except ImportError:
        return jsonify({"error": "generación de PDF no disponible (falta reportlab)"}), 500
    except Exception as exc:
        logger.exception("Fallo generando PDF del agent scanner")
        return jsonify({"error": f"no se pudo generar el PDF: {exc}"}), 500
    host = (data.get("client") or {}).get("host", "informe")
    fecha = (data.get("generated") or "")[:10]
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                     download_name=f"agent-readiness_{host}_{fecha}.pdf")


@agent_bp.route("/api/report/<job_id>.json")
@agent_access_required
def report_json(job_id):
    """JSON completo y estructurado, pensado para iterar con IA."""
    import json as _json
    from flask import Response
    data = _resultado(job_id)
    if data is None:
        return jsonify({"error": "resultado no disponible"}), 404
    try:
        from agent_scanner.report_json import build_json
        payload = build_json(data)
    except Exception as exc:
        logger.warning(f"build_json falló, se sirve el crudo: {exc}")
        payload = data
    host = (data.get("client") or {}).get("host", "informe")
    fecha = (data.get("generated") or "")[:10]
    body = _json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": f'attachment; filename="agent-readiness_{host}_{fecha}.json"'})


@agent_bp.route("/api/historial")
@agent_access_required
def historial():
    """Informes anteriores del usuario. Vacío si la BD no está disponible."""
    try:
        from agent_scanner.storage import historial as _hist, DISPONIBLE
        user = get_current_user() or {}
        # los admin ven todo el historial; el resto, solo el suyo
        es_admin = user.get("role") == "admin"
        items = _hist(None if es_admin else user.get("email"), limite=30)
        return jsonify({"informes": items, "persistencia": DISPONIBLE is not False})
    except Exception as exc:
        logger.warning(f"historial no disponible: {exc}")
        return jsonify({"informes": [], "persistencia": False})


@agent_bp.route("/api/historial/<job_id>", methods=["DELETE"])
@agent_access_required
def borrar_informe(job_id):
    try:
        from agent_scanner.storage import borrar
        user = get_current_user() or {}
        # un no-admin solo puede borrar lo suyo (el filtro va en el WHERE)
        dueno = None if user.get("role") == "admin" else user.get("email")
        return jsonify({"borrado": borrar(job_id, dueno)})
    except Exception as exc:
        logger.warning(f"no se pudo borrar {job_id}: {exc}")
        return jsonify({"borrado": False}), 500


@agent_bp.route("/api/catalog")
@agent_access_required
def catalog():
    """Catálogo de factores analizados (para el selector del formulario)."""
    from agent_scanner.catalog import as_dict
    return jsonify({"categorias": as_dict()})


@agent_bp.route("/api/me")
@agent_access_required
def whoami():
    user = get_current_user() or {}
    return jsonify({"email": user.get("email"), "is_admin": user.get("role") == "admin"})


@agent_bp.route("/acceso")
@admin_required
def access_page():
    return send_from_directory(_WEB_DIR, "access.html")


@agent_bp.route("/api/access/list")
@admin_required
def access_list():
    from agent_scanner.access import list_emails
    return jsonify({"emails": list_emails()})


@agent_bp.route("/api/access/add", methods=["POST"])
@admin_required
def access_add():
    from agent_scanner.access import add_email, send_invitation_email
    payload = request.get_json(silent=True) or {}
    user = get_current_user() or {}
    ok, res = add_email(payload.get("email"), added_by=user.get("email"))
    if not ok:
        return jsonify({"error": res}), 400
    email_sent = send_invitation_email(res, invited_by_name=user.get("name") or user.get("email"))
    return jsonify({"ok": True, "email": res, "email_sent": email_sent})


@agent_bp.route("/api/access/resend", methods=["POST"])
@admin_required
def access_resend():
    from agent_scanner.access import send_invitation_email
    payload = request.get_json(silent=True) or {}
    user = get_current_user() or {}
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "falta email"}), 400
    sent = send_invitation_email(email, invited_by_name=user.get("name") or user.get("email"))
    return jsonify({"ok": sent, "email_sent": sent})


@agent_bp.route("/api/access/remove", methods=["POST"])
@admin_required
def access_remove():
    from agent_scanner.access import remove_email
    payload = request.get_json(silent=True) or {}
    if remove_email(payload.get("email")):
        return jsonify({"ok": True})
    return jsonify({"error": "no se pudo eliminar"}), 400
