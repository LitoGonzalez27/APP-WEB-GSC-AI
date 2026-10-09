"""
Cifra principal de las tarjetas de proyecto (AI Overview, AI Mode, LLM).

Las tres listas de proyectos usan el mismo componente de tarjeta
(static/js/project-cards.js). La cifra grande y su variación salen de los
MISMOS adapters que AI Visibility Summary, para que un proyecto muestre el
mismo número en su tarjeta y en el resumen de su marca:

- AI Overview / AI Mode: visibilidad media de los últimos 30 días.
- LLM Visibility: mention rate de los últimos 30 días (solo el set núcleo si
  el proyecto tiene sets, igual que en Summary).

La lista se pinta primero y las cifras llegan después con esta llamada, así
que una consulta lenta nunca retrasa el listado.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, jsonify, request

from auth import auth_required, get_current_user

logger = logging.getLogger(__name__)

project_cards_bp = Blueprint("project_cards", __name__, url_prefix="/api/project-cards")

PERIOD = "30"
MAX_IDS = 60
WORKERS = 4

# módulo de la URL -> (nombre en project_access_service, adapter de Summary)
MODULES = {
    "manual_ai": "manual_ai",
    "ai_mode": "ai_mode",
    "llm": "llm_monitoring",
}


def _adapter(module: str):
    if module == "manual_ai":
        from ai_summary.services.adapters import manual_ai_adapter as m
    elif module == "ai_mode":
        from ai_summary.services.adapters import ai_mode_adapter as m
    else:
        from ai_summary.services.adapters import llm_monitoring_adapter as m
    return m


def _parse_ids(raw: str) -> list[int]:
    ids = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return list(dict.fromkeys(ids))[:MAX_IDS]


@project_cards_bp.route("/kpis", methods=["GET"])
@auth_required
def get_kpis():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    module = request.args.get("module", "")
    if module not in MODULES:
        return jsonify({"success": False, "error": "Unknown module"}), 400
    ids = _parse_ids(request.args.get("ids", ""))
    if not ids:
        return jsonify({"success": True, "kpis": {}})

    # Solo proyectos que el usuario puede ver (dueño o colaborador): los
    # adapters consultan por id sin comprobar nada.
    from services.project_access_service import user_can_view_project
    access_module = MODULES[module]
    visible = [pid for pid in ids if user_can_view_project(user["id"], access_module, pid)]

    adapter = _adapter(module)

    def kpi(pid: int):
        try:
            s = adapter.get_channel_summary(pid, PERIOD, include_competitors=False)
        except Exception as exc:  # una tarjeta sin cifra no rompe la lista
            logger.warning("project card kpi failed module=%s project=%s: %s", module, pid, exc)
            return pid, {"available": False, "reason": "error"}
        return pid, {
            "available": bool(s.get("available")),
            "reason": s.get("reason"),
            "value": s.get("visibility_pct"),
            "delta": s.get("visibility_delta"),
            "last_date": s.get("last_date"),
        }

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        result = dict(pool.map(kpi, visible))

    return jsonify({"success": True, "period_days": int(PERIOD), "kpis": {str(k): v for k, v in result.items()}})
