"""
Test de caracterización del sistema LLM Monitoring.

Congela el contrato público del blueprint `llm_monitoring_bp` (39 rutas) para que
el refactor (limpieza + split del monolito) NO altere el comportamiento observable.

LLM Monitoring es el sistema más grande (routes 9k líneas, JS 8.8k) y NO se puede
verificar lanzando análisis reales (consumen tokens facturables), así que este
contrato + los tests de lógica son la red de seguridad principal.

No conecta a BD real: basta con que DATABASE_URL exista (conexión perezosa).

Ejecutar:  python3 -m pytest tests/test_llm_monitoring_contract.py -q
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

from flask import Flask  # noqa: E402


# Contrato congelado: 39 rutas bajo /api/llm-monitoring.
EXPECTED_ROUTES = {
    (frozenset({'POST'}), '/api/llm-monitoring/cron/alert', 'llm_monitoring.cron_alert'),
    (frozenset({'POST'}), '/api/llm-monitoring/cron/daily-analysis', 'llm_monitoring.trigger_daily_analysis'),
    (frozenset({'POST'}), '/api/llm-monitoring/cron/model-discovery', 'llm_monitoring.cron_model_discovery'),
    (frozenset({'GET', 'POST'}), '/api/llm-monitoring/cron/watchdog', 'llm_monitoring.cron_watchdog'),
    (frozenset({'GET'}), '/api/llm-monitoring/health', 'llm_monitoring.health_check'),
    (frozenset({'GET'}), '/api/llm-monitoring/models', 'llm_monitoring.get_models'),
    (frozenset({'PUT'}), '/api/llm-monitoring/models/<int:model_id>', 'llm_monitoring.update_model'),
    (frozenset({'GET'}), '/api/llm-monitoring/models/approve', 'llm_monitoring.approve_model_by_token'),
    (frozenset({'GET'}), '/api/llm-monitoring/models/changelog', 'llm_monitoring.get_model_changelog'),
    (frozenset({'GET'}), '/api/llm-monitoring/models/current', 'llm_monitoring.get_current_models'),
    (frozenset({'GET'}), '/api/llm-monitoring/models/reject', 'llm_monitoring.reject_model_by_token'),
    (frozenset({'POST'}), '/api/llm-monitoring/projects', 'llm_monitoring.create_project'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects', 'llm_monitoring.get_projects'),
    (frozenset({'DELETE'}), '/api/llm-monitoring/projects/<int:project_id>', 'llm_monitoring.delete_project'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>', 'llm_monitoring.get_project'),
    (frozenset({'PUT'}), '/api/llm-monitoring/projects/<int:project_id>', 'llm_monitoring.update_project'),
    (frozenset({'PUT'}), '/api/llm-monitoring/projects/<int:project_id>/activate', 'llm_monitoring.activate_project'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/clusters', 'llm_monitoring.get_project_clusters'),
    (frozenset({'PUT'}), '/api/llm-monitoring/projects/<int:project_id>/clusters', 'llm_monitoring.update_project_clusters'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/clusters/metrics', 'llm_monitoring.get_clusters_metrics'),
    (frozenset({'POST'}), '/api/llm-monitoring/projects/<int:project_id>/clusters/rename', 'llm_monitoring.rename_project_cluster'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/comparison', 'llm_monitoring.get_llm_comparison'),
    (frozenset({'PUT'}), '/api/llm-monitoring/projects/<int:project_id>/deactivate', 'llm_monitoring.deactivate_project'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/export/excel', 'llm_monitoring.export_project_excel'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/export/pdf', 'llm_monitoring.export_project_pdf'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/metrics', 'llm_monitoring.get_project_metrics'),
    (frozenset({'POST'}), '/api/llm-monitoring/projects/<int:project_id>/queries', 'llm_monitoring.add_queries_to_project'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/queries', 'llm_monitoring.get_project_queries'),
    (frozenset({'DELETE'}), '/api/llm-monitoring/projects/<int:project_id>/queries/<int:query_id>', 'llm_monitoring.delete_query'),
    (frozenset({'PUT'}), '/api/llm-monitoring/projects/<int:project_id>/queries/<int:query_id>/cluster', 'llm_monitoring.assign_query_cluster'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/queries/<int:query_id>/history', 'llm_monitoring.get_query_history'),
    (frozenset({'POST'}), '/api/llm-monitoring/projects/<int:project_id>/queries/bulk-cluster', 'llm_monitoring.bulk_assign_cluster'),
    (frozenset({'POST'}), '/api/llm-monitoring/projects/<int:project_id>/queries/suggest', 'llm_monitoring.suggest_queries'),
    (frozenset({'POST'}), '/api/llm-monitoring/projects/<int:project_id>/queries/suggest-variations', 'llm_monitoring.suggest_query_variations'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/responses', 'llm_monitoring.get_project_responses'),
    (frozenset({'POST'}), '/api/llm-monitoring/projects/<int:project_id>/run-initial-analysis', 'llm_monitoring.run_initial_analysis'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/share-of-voice-history', 'llm_monitoring.get_share_of_voice_history'),
    (frozenset({'GET'}), '/api/llm-monitoring/projects/<int:project_id>/urls-ranking', 'llm_monitoring.get_urls_ranking'),
    (frozenset({'GET'}), '/api/llm-monitoring/usage', 'llm_monitoring.get_usage'),
}


def _current_routes():
    from llm_monitoring_routes import llm_monitoring_bp

    app = Flask(__name__)
    app.register_blueprint(llm_monitoring_bp)
    routes = set()
    for rule in app.url_map.iter_rules():
        if "llm-monitoring" not in rule.rule:
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
    assert len(current) == len(EXPECTED_ROUTES) == 39


def test_blueprint_and_service_import():
    from llm_monitoring_routes import llm_monitoring_bp
    assert llm_monitoring_bp.name == "llm_monitoring"
    assert llm_monitoring_bp.url_prefix == "/api/llm-monitoring"
    # El servicio central debe importar.
    from services.llm_monitoring_service import MultiLLMMonitoringService
    assert MultiLLMMonitoringService is not None
