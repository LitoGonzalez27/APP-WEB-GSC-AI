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


def _run_job(job_id, urls, opts):
    from agent_scanner import engine
    job = _JOBS[job_id]
    try:
        cats = set(opts.get("cats") or [])
        audits = []
        for i, u in enumerate(urls):
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
                    with_agents=bool(opts.get("agents")) and i == 0,
                    allow_submit=bool(opts.get("allow_submit")) and i == 0,
                    agent_repeticiones=int(opts.get("agent_reps") or 3))
                audits.append(a)
                job["domains"][i].update(state="done", score=a["score"],
                                         emoji=a["level"]["emoji"], level=a["level"]["name"])
            except Exception as exc:
                audits.append({"domain": u, "error": str(exc)[:200]})
                job["domains"][i].update(state="error", error=str(exc)[:200])
                job["log"].append(f"error en {job['domains'][i]['host']}: {exc}")
        data = {
            "client": audits[0],
            "competitors": audits[1:],
            "framework_version": "2.0 (agent_scanner en clicandseo)",
        }
        if "error" in audits[0]:
            job["status"] = "error"
            job["error"] = audits[0]["error"]
        else:
            job["result"] = data
            job["status"] = "done"
            job["phase"] = "Análisis completado"
    except Exception as exc:
        logger.exception("Fallo en job de agent_scanner")
        job["status"] = "error"
        job["error"] = str(exc)[:300]
    finally:
        from agent_scanner import engine
        engine.LOG_SINK = None


@agent_bp.route("/")
@agent_access_required
def index():
    return send_from_directory(_WEB_DIR, "index.html")


@agent_bp.route("/api/scan", methods=["POST"])
@agent_access_required
def scan():
    with _JOBS_LOCK:
        if any(j["status"] == "running" for j in _JOBS.values()):
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
            "started": time.time(), "error": None, "result": None,
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
    slim = {k: v for k, v in job.items() if k != "result"}
    slim["log"] = job["log"][-40:]
    slim["elapsed"] = round(time.time() - job["started"])
    return jsonify(slim)


@agent_bp.route("/api/result/<job_id>")
@agent_access_required
def result(job_id):
    job = _JOBS.get(job_id)
    if not job or job.get("result") is None:
        return jsonify({"error": "resultado no disponible"}), 404
    return jsonify(job["result"])


# ---------------------------------------------------------------- gestión de acceso (solo admin)

@agent_bp.route("/api/report/<job_id>.pdf")
@agent_access_required
def report_pdf(job_id):
    """Informe PDF estructurado (CMO → equipo técnico)."""
    from flask import send_file
    job = _JOBS.get(job_id)
    if not job or job.get("result") is None:
        return jsonify({"error": "resultado no disponible"}), 404
    try:
        from agent_scanner.report_pdf import build_pdf
        buf = build_pdf(job["result"])
    except ImportError:
        return jsonify({"error": "generación de PDF no disponible (falta reportlab)"}), 500
    except Exception as exc:
        logger.exception("Fallo generando PDF del agent scanner")
        return jsonify({"error": f"no se pudo generar el PDF: {exc}"}), 500
    host = (job["result"].get("client") or {}).get("host", "informe")
    fecha = (job["result"].get("generated") or "")[:10]
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                     download_name=f"agent-readiness_{host}_{fecha}.pdf")


@agent_bp.route("/api/report/<job_id>.json")
@agent_access_required
def report_json(job_id):
    """JSON completo y estructurado, pensado para iterar con IA."""
    import json as _json
    from flask import Response
    job = _JOBS.get(job_id)
    if not job or job.get("result") is None:
        return jsonify({"error": "resultado no disponible"}), 404
    try:
        from agent_scanner.report_json import build_json
        payload = build_json(job["result"])
    except Exception as exc:
        logger.warning(f"build_json falló, se sirve el crudo: {exc}")
        payload = job["result"]
    host = (job["result"].get("client") or {}).get("host", "informe")
    fecha = (job["result"].get("generated") or "")[:10]
    body = _json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": f'attachment; filename="agent-readiness_{host}_{fecha}.json"'})


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
