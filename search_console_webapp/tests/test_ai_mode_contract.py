"""
Test de caracterización del sistema AI Mode (Google AI Mode Monitoring).

Congela el "contrato" público del paquete `ai_mode_projects` para que la
limpieza/refactor NO altere el comportamiento observable:

  - El bridge `ai_mode_system_bridge` exporta los mismos símbolos.
  - El blueprint registra EXACTAMENTE el mismo conjunto de rutas (34).
  - El entrypoint del cron resuelve sus imports.

No conecta a BD real: basta con que `DATABASE_URL` exista (la conexión es perezosa).

Ejecutar:  python3 -m pytest tests/test_ai_mode_contract.py -q
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from flask import Flask  # noqa: E402


# Contrato congelado: 34 rutas bajo /ai-mode-projects.
EXPECTED_ROUTES = {
    (frozenset({"DELETE"}), "/ai-mode-projects/api/projects/<int:project_id>", "ai_mode.delete_project"),
    (frozenset({"DELETE"}), "/ai-mode-projects/api/projects/<int:project_id>/keywords/<int:keyword_id>", "ai_mode.delete_project_keyword"),
    (frozenset({"GET"}), "/ai-mode-projects/", "ai_mode.ai_mode_dashboard"),
    (frozenset({"GET"}), "/ai-mode-projects/api/health", "ai_mode.manual_ai_health"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects", "ai_mode.get_projects"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>", "ai_mode.get_project_details"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/ai-overview-table", "ai_mode.get_ai_overview_table_data"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/ai-overview-table-latest", "ai_mode.get_ai_overview_table_latest"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/clusters", "ai_mode.get_project_clusters"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/clusters/statistics", "ai_mode.get_clusters_statistics"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/comparative-charts", "ai_mode.get_comparative_charts_data"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/competitors", "ai_mode.get_project_competitors"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/competitors-charts", "ai_mode.get_competitors_charts_data"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/export", "ai_mode.export_project_data"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/global-domains-ranking", "ai_mode.get_global_domains_ranking"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/keywords", "ai_mode.get_project_keywords"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/results", "ai_mode.get_project_results"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/stats", "ai_mode.get_project_stats"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/stats-latest", "ai_mode.get_project_stats_latest"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/top-domains", "ai_mode.get_top_domains"),
    (frozenset({"GET"}), "/ai-mode-projects/api/projects/<int:project_id>/urls-ranking", "ai_mode.get_urls_ranking"),
    (frozenset({"POST"}), "/ai-mode-projects/api/cron/daily-analysis", "ai_mode.trigger_daily_analysis"),
    (frozenset({"POST"}), "/ai-mode-projects/api/projects", "ai_mode.create_project"),
    (frozenset({"POST"}), "/ai-mode-projects/api/projects/<int:project_id>/analyze", "ai_mode.analyze_project"),
    (frozenset({"POST"}), "/ai-mode-projects/api/projects/<int:project_id>/clusters/test", "ai_mode.test_cluster_classification"),
    (frozenset({"POST"}), "/ai-mode-projects/api/projects/<int:project_id>/clusters/validate", "ai_mode.validate_clusters_config"),
    (frozenset({"POST"}), "/ai-mode-projects/api/projects/<int:project_id>/download-excel", "ai_mode.download_manual_ai_excel"),
    (frozenset({"POST"}), "/ai-mode-projects/api/projects/<int:project_id>/keywords", "ai_mode.add_keywords_to_project"),
    (frozenset({"PUT"}), "/ai-mode-projects/api/projects/<int:project_id>", "ai_mode.update_project"),
    (frozenset({"PUT"}), "/ai-mode-projects/api/projects/<int:project_id>/clusters", "ai_mode.update_project_clusters"),
    (frozenset({"PUT"}), "/ai-mode-projects/api/projects/<int:project_id>/competitors", "ai_mode.update_project_competitors"),
    (frozenset({"PUT"}), "/ai-mode-projects/api/projects/<int:project_id>/keywords/<int:keyword_id>", "ai_mode.update_project_keyword"),
    (frozenset({"PUT"}), "/ai-mode-projects/api/projects/<int:project_id>/pause", "ai_mode.pause_project"),
    (frozenset({"PUT"}), "/ai-mode-projects/api/projects/<int:project_id>/resume", "ai_mode.resume_project"),
}


def _current_routes():
    from ai_mode_projects import ai_mode_bp

    app = Flask(__name__)
    app.register_blueprint(ai_mode_bp)
    routes = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/ai-mode-projects"):
            continue
        methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
        routes.add((methods, rule.rule, rule.endpoint))
    return routes


def test_blueprint_routes_contract_unchanged():
    current = _current_routes()
    missing = EXPECTED_ROUTES - current
    extra = current - EXPECTED_ROUTES
    assert not missing, f"Rutas que DESAPARECIERON: {sorted(missing)}"
    assert not extra, f"Rutas NUEVAS no esperadas: {sorted(extra)}"
    assert len(current) == len(EXPECTED_ROUTES) == 34


def test_bridge_exports_stable():
    import ai_mode_system_bridge as bridge

    assert hasattr(bridge, "ai_mode_bp")
    assert hasattr(bridge, "run_daily_analysis_for_all_ai_mode_projects")
    assert hasattr(bridge, "USING_AI_MODE_SYSTEM")
    assert callable(bridge.run_daily_analysis_for_all_ai_mode_projects)
    # Con el paquete disponible, el sistema está activo.
    assert bridge.USING_AI_MODE_SYSTEM is True
    assert bridge.ai_mode_bp is not None


def test_cron_entrypoint_imports_resolve():
    import importlib

    cron = importlib.import_module("daily_ai_mode_cron")
    assert cron is not None
    from ai_mode_system_bridge import (  # noqa: F401
        run_daily_analysis_for_all_ai_mode_projects,
        USING_AI_MODE_SYSTEM,
    )
