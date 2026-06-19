"""
Test de caracterización del sistema Manual AI.

Congela el "contrato" público del módulo `manual_ai` para garantizar que las
tareas de limpieza/refactor NO alteran el comportamiento observable:

  - El bridge `manual_ai_system_bridge` sigue exportando los mismos símbolos.
  - El blueprint registra EXACTAMENTE el mismo conjunto de rutas (método + URL +
    endpoint).
  - El entrypoint del cron (`daily_analysis_cron`) puede resolver sus imports.

No conecta a la base de datos real: basta con que `DATABASE_URL` exista para
pasar el chequeo de import de `database.py` (la conexión es perezosa).

Ejecutar:  python3 -m pytest tests/test_manual_ai_contract.py -q
"""

import os

# database.py exige DATABASE_URL en import-time (la conexión es perezosa).
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from flask import Flask  # noqa: E402


# Contrato congelado: 36 rutas registradas bajo /manual-ai.
# Formato: (frozenset(methods sin HEAD/OPTIONS), rule, endpoint)
EXPECTED_ROUTES = {
    (frozenset({"DELETE"}), "/manual-ai/api/projects/<int:project_id>", "manual_ai.delete_project"),
    (frozenset({"DELETE"}), "/manual-ai/api/projects/<int:project_id>/keywords/<int:keyword_id>", "manual_ai.delete_project_keyword"),
    (frozenset({"GET"}), "/manual-ai/", "manual_ai.manual_ai_dashboard"),
    (frozenset({"GET"}), "/manual-ai/api/health", "manual_ai.manual_ai_health"),
    (frozenset({"GET"}), "/manual-ai/api/projects", "manual_ai.get_projects"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>", "manual_ai.get_project_details"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/ai-overview-table", "manual_ai.get_ai_overview_table_data"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/ai-overview-table-latest", "manual_ai.get_ai_overview_table_latest"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/aio-vs-organic", "manual_ai.get_aio_vs_organic_comparison"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/clusters", "manual_ai.get_project_clusters"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/clusters/statistics", "manual_ai.get_clusters_statistics"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/comparative-charts", "manual_ai.get_comparative_charts_data"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/competitors", "manual_ai.get_project_competitors"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/competitors-charts", "manual_ai.get_competitors_charts_data"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/export", "manual_ai.export_project_data"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/export/pdf", "manual_ai.download_manual_ai_pdf"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/global-domains-ranking", "manual_ai.get_global_domains_ranking"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/keywords", "manual_ai.get_project_keywords"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/results", "manual_ai.get_project_results"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/stats", "manual_ai.get_project_stats"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/stats-latest", "manual_ai.get_project_stats_latest"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/top-domains", "manual_ai.get_top_domains"),
    (frozenset({"GET"}), "/manual-ai/api/projects/<int:project_id>/urls-ranking", "manual_ai.get_urls_ranking"),
    (frozenset({"POST"}), "/manual-ai/api/cron/daily-analysis", "manual_ai.trigger_daily_analysis"),
    (frozenset({"POST"}), "/manual-ai/api/projects", "manual_ai.create_project"),
    (frozenset({"POST"}), "/manual-ai/api/projects/<int:project_id>/analyze", "manual_ai.analyze_project"),
    (frozenset({"POST"}), "/manual-ai/api/projects/<int:project_id>/clusters/test", "manual_ai.test_cluster_classification"),
    (frozenset({"POST"}), "/manual-ai/api/projects/<int:project_id>/clusters/validate", "manual_ai.validate_clusters_config"),
    (frozenset({"POST"}), "/manual-ai/api/projects/<int:project_id>/download-excel", "manual_ai.download_manual_ai_excel"),
    (frozenset({"POST"}), "/manual-ai/api/projects/<int:project_id>/keywords", "manual_ai.add_keywords_to_project"),
    (frozenset({"PUT"}), "/manual-ai/api/projects/<int:project_id>", "manual_ai.update_project"),
    (frozenset({"PUT"}), "/manual-ai/api/projects/<int:project_id>/clusters", "manual_ai.update_project_clusters"),
    (frozenset({"PUT"}), "/manual-ai/api/projects/<int:project_id>/competitors", "manual_ai.update_project_competitors"),
    (frozenset({"PUT"}), "/manual-ai/api/projects/<int:project_id>/keywords/<int:keyword_id>", "manual_ai.update_project_keyword"),
    (frozenset({"PUT"}), "/manual-ai/api/projects/<int:project_id>/pause", "manual_ai.pause_project"),
    (frozenset({"PUT"}), "/manual-ai/api/projects/<int:project_id>/resume", "manual_ai.resume_project"),
}


def _current_routes():
    from manual_ai import manual_ai_bp

    app = Flask(__name__)
    app.register_blueprint(manual_ai_bp)
    routes = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/manual-ai"):
            continue
        methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
        routes.add((methods, rule.rule, rule.endpoint))
    return routes


def test_blueprint_routes_contract_unchanged():
    """El conjunto de rutas registradas debe ser idéntico al congelado."""
    current = _current_routes()
    missing = EXPECTED_ROUTES - current
    extra = current - EXPECTED_ROUTES
    assert not missing, f"Rutas que DESAPARECIERON tras el refactor: {sorted(missing)}"
    assert not extra, f"Rutas NUEVAS no esperadas tras el refactor: {sorted(extra)}"
    assert len(current) == len(EXPECTED_ROUTES) == 36


def test_bridge_exports_stable():
    """El bridge debe seguir exportando los símbolos que consume el resto del sistema."""
    import manual_ai_system_bridge as bridge

    assert hasattr(bridge, "manual_ai_bp")
    assert hasattr(bridge, "run_daily_analysis_for_all_projects")
    assert hasattr(bridge, "USING_NEW_SYSTEM")
    assert callable(bridge.run_daily_analysis_for_all_projects)
    # Tras la limpieza, el sistema modular es el único: USING_NEW_SYSTEM siempre True.
    assert bridge.USING_NEW_SYSTEM is True


def test_cron_entrypoint_imports_resolve():
    """El script del cron debe poder importar lo que usa, vía el bridge."""
    import importlib

    cron = importlib.import_module("daily_analysis_cron")
    assert hasattr(cron, "main")
    # Los símbolos que el cron importa dentro de main() deben existir en el bridge.
    from manual_ai_system_bridge import (  # noqa: F401
        run_daily_analysis_for_all_projects,
        USING_NEW_SYSTEM,
    )
