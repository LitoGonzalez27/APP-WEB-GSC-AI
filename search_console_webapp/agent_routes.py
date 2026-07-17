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
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request, send_from_directory

from auth import admin_required

logger = logging.getLogger(__name__)

agent_bp = Blueprint("agent_scanner", __name__, url_prefix="/agent")

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
                    categories=cats or None)
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
@admin_required
def index():
    return send_from_directory(_WEB_DIR, "index.html")


@agent_bp.route("/api/scan", methods=["POST"])
@admin_required
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
@admin_required
def status(job_id):
    job = _JOBS.get(job_id)
    if not job:
        return jsonify({"error": "análisis desconocido"}), 404
    slim = {k: v for k, v in job.items() if k != "result"}
    slim["log"] = job["log"][-40:]
    slim["elapsed"] = round(time.time() - job["started"])
    return jsonify(slim)


@agent_bp.route("/api/result/<job_id>")
@admin_required
def result(job_id):
    job = _JOBS.get(job_id)
    if not job or job.get("result") is None:
        return jsonify({"error": "resultado no disponible"}), 404
    return jsonify(job["result"])
