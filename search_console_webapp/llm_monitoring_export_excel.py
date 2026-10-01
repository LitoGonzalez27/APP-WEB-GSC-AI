"""Exportación a Excel de un proyecto de LLM Monitoring (ruta en llm_monitoring_routes.py).

Sacado tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros gigantes):
la ruta, sus decoradores y la URL siguen allí y llaman a esta función. Los helpers
de informes vienen de llm_monitoring_informes.py; este módulo no importa el de rutas.

Los helpers quedan enlazados aquí al importar: un monkeypatch sobre
llm_monitoring_routes.<helper> no afecta a la exportación (hay que parchear
este módulo). El logger es el de este módulo, no el de las rutas.
"""

import logging
from datetime import datetime, timedelta
from flask import request, jsonify
import json

from database import get_db_connection
from services.llm_monitoring import pseudo_snapshots as pseudo_snapshots_lib
from services.llm_monitoring.fanout_stats import fanout_export_tables
from services.llm_monitoring_stats import LLMMonitoringStatsService

from llm_monitoring_informes import (
    _OPPORTUNITY_LABELS,
    _compute_branded_metrics,
    _narrow_llms,
    _normalize_days_param,
    _parse_report_filters,
    _report_view_label,
    _resolve_filtered_query_ids,
    _safe_content_overview,
    _safe_fanout_metrics,
    classify_query_branded,
    collect_prompt_metrics,
    empty_prompt_metrics,
    round_half_up,
)

logger = logging.getLogger(__name__)


def exportar_excel(project_id):
    """
    Exportar datos COMPLETOS del proyecto a Excel (todas las métricas visibles en UI)

    Query params:
        days: int - Período de días (default: 30)

    Sheets generadas:
        1. Project Summary - Resumen del proyecto y métricas globales
        2. Share of Voice - SOV de marca y competidores por día
        3. LLM Comparison - Métricas comparativas por proveedor LLM
        4. Daily Metrics - Snapshots diarios detallados por LLM
        5. Prompts & Queries - Performance por prompt/query
        6. URL Rankings - URLs más citadas por los LLMs
        7. Sentiment Analysis - Distribución de sentimiento por LLM
        8. Detailed Results - Datos individuales por query × LLM × día
    """
    from io import BytesIO
    from flask import send_file
    json_module = json  # alias to avoid shadowing in nested scope

    logger.info(f"📥 Starting comprehensive Excel export for project {project_id}")

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        logger.error(f"openpyxl no está instalado: {e}")
        return jsonify({'error': 'Excel export not available. Missing openpyxl library.'}), 500

    days = _normalize_days_param(request.args.get('days'), default=30)
    report_filters = _parse_report_filters(request.args)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()

        # ──────────────────────────────────────────────────
        # FETCH ALL DATA
        # ──────────────────────────────────────────────────

        # .date() y no datetime: `analysis_date` es un DATE, así que compararlo
        # con un timestamp lo convierte a medianoche y `>= hoy-90d 11:20` deja
        # fuera el primer día entero del rango. El panel usa fechas, y sin esto
        # el Excel exportaba un día menos y sus cifras no cuadraban con la
        # pantalla.
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # 1. Project info
        cur.execute("""
            SELECT id, name, brand_name, industry, brand_domain, brand_keywords,
                   competitor_domains, selected_competitors,
                   language, country_code, enabled_llms, queries_per_llm,
                   is_active, created_at, last_analysis_date,
                   search_mode, search_enabled_at
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        enabled_llms_filter = _narrow_llms(project.get('enabled_llms') or [], report_filters)
        brand_keywords = project.get('brand_keywords') or []

        # Helper for LLM filter in queries
        def _add_llm_filter(query_str, params_list, column='llm_provider'):
            if enabled_llms_filter:
                query_str += f" AND {column} = ANY(%s)"
                params_list.append(enabled_llms_filter)
            return query_str, params_list

        # Filtro global del informe: el Excel debe decir lo mismo que la
        # pantalla desde la que se descargó.
        filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=start_date, end_date=end_date)

        def _add_query_filter(query_str, params_list, column='r.query_id'):
            if filtered_query_ids is not None:
                query_str += f" AND {column} = ANY(%s)"
                params_list.append(filtered_query_ids)
            return query_str, params_list

        # Etiqueta legible del filtro para las cabeceras de las hojas
        report_view_label = _report_view_label(report_filters)

        # 2. Snapshots (daily metrics per LLM) — source for multiple sheets.
        # Con filtro activo, los snapshots preagregados no sirven → pseudo.
        if filtered_query_ids is not None:
            snapshots = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, filtered_query_ids,
                start_date_str, end_date_str,
                enabled_llms=enabled_llms_filter,
            )
            snapshots.sort(key=lambda s: s['llm_provider'])
            snapshots.sort(key=lambda s: s['snapshot_date'], reverse=True)
        else:
            snap_query = """
                SELECT
                    snapshot_date, llm_provider,
                    total_queries, total_mentions, mention_rate,
                    avg_position,
                    appeared_in_top3, appeared_in_top5, appeared_in_top10,
                    share_of_voice, weighted_share_of_voice,
                    total_competitor_mentions, competitor_breakdown, weighted_competitor_breakdown,
                    positive_mentions, neutral_mentions, negative_mentions, avg_sentiment_score,
                    avg_response_time_ms, total_cost_usd, total_tokens
                FROM llm_monitoring_snapshots
                WHERE project_id = %s AND snapshot_date >= %s
            """
            snap_params = [project_id, start_date_str]
            snap_query, snap_params = _add_llm_filter(snap_query, snap_params)
            snap_query += " ORDER BY snapshot_date DESC, llm_provider"
            cur.execute(snap_query, snap_params)
            snapshots = cur.fetchall()

        # 3. Aggregated LLM metrics (from results table)
        metrics_query = """
            SELECT
                llm_provider,
                COUNT(DISTINCT query_id) as total_queries,
                COUNT(*) as total_results,
                SUM(CASE WHEN brand_mentioned THEN 1 ELSE 0 END) as total_mentions,
                ROUND(AVG(CASE WHEN brand_mentioned THEN 100.0 ELSE 0 END), 1) as mention_rate_pct,
                AVG(position_in_list) FILTER (WHERE position_in_list IS NOT NULL) as avg_position,
                SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
                SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count,
                AVG(sentiment_score) as avg_sentiment_score,
                SUM(cost_usd) as total_cost,
                SUM(tokens_used) as total_tokens,
                AVG(response_time_ms) as avg_response_time
            FROM llm_monitoring_results
            WHERE project_id = %s AND analysis_date >= %s AND analysis_date <= %s
        """
        metrics_params = [project_id, start_date, end_date]
        metrics_query, metrics_params = _add_query_filter(metrics_query, metrics_params, 'query_id')
        metrics_query, metrics_params = _add_llm_filter(metrics_query, metrics_params)
        metrics_query += " GROUP BY llm_provider ORDER BY llm_provider"
        cur.execute(metrics_query, metrics_params)
        llm_metrics = cur.fetchall()

        # 4. Query/Prompt level data
        #
        # Las tres cifras de menciones usan LA MISMA definición que la tabla de
        # prompts del panel (get_project_queries): "Text Mentions" son los
        # resultados con la marca mencionada, "URL Citations" son las URLs de la
        # marca dentro de `sources`, y el total es la suma de ambas. Antes esta
        # hoja contaba otra cosa bajo los mismos nombres — total_mentions era
        # solo brand_mentioned, y text/url salían de `position_source` — así que
        # el Excel y la pantalla daban números distintos para el mismo prompt.
        queries_query = """
            SELECT
                q.id AS query_id,
                q.query_text AS prompt,
                q.language,
                q.query_type,
                q.topic_cluster,
                q.prompt_set,
                COUNT(DISTINCT r.llm_provider) as llms_analyzed,
                COUNT(DISTINCT r.id) as total_results,
                SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) as text_mentions,
                SUM(
                    CASE
                        WHEN r.sources IS NOT NULL AND r.sources::text != '[]'
                        THEN (
                            SELECT COUNT(*)
                            FROM jsonb_array_elements(r.sources::jsonb) AS source
                            WHERE source->>'url' ILIKE %s
                        )
                        ELSE 0
                    END
                ) as url_citations,
                ROUND(AVG(CASE WHEN r.brand_mentioned THEN 100.0 ELSE 0 END), 1) as visibility_pct,
                AVG(r.position_in_list) FILTER (WHERE r.position_in_list IS NOT NULL) as avg_position,
                MAX(r.analysis_date) as last_analysis
            FROM llm_monitoring_queries q
            LEFT JOIN llm_monitoring_results r ON q.id = r.query_id
                AND r.analysis_date >= %s AND r.analysis_date <= %s
                {llm_filter}
            WHERE q.project_id = %s AND q.is_active = TRUE
            {report_filter}
            GROUP BY q.id, q.query_text, q.language, q.query_type, q.topic_cluster, q.prompt_set
            ORDER BY text_mentions DESC, visibility_pct DESC
        """
        has_prompt_subset = filtered_query_ids is not None
        queries_query = queries_query.format(
            llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms_filter else "",
            report_filter="AND q.id = ANY(%s)" if has_prompt_subset else ""
        )
        brand_domain_like = f"%{project['brand_domain']}%" if project.get('brand_domain') else '%'
        queries_params = [brand_domain_like, start_date, end_date]
        if enabled_llms_filter:
            queries_params.append(enabled_llms_filter)
        queries_params.append(project_id)
        if has_prompt_subset:
            queries_params.append(filtered_query_ids)
        cur.execute(queries_query, queries_params)
        queries = cur.fetchall()

        # Prompts de sets de tendencia (no-core) para su hoja separada:
        # SIEMPRE se listan aparte, con su set, para que el documento sea
        # completo sin mezclar sus cifras con las del set en vista.
        trend_queries = []
        try:
            trend_sql = queries_query.replace(
                "AND q.id = ANY(%s)",
                "AND q.prompt_set IS NOT NULL"
            ) if has_prompt_subset else queries_query.replace(
                "WHERE q.project_id = %s AND q.is_active = TRUE",
                "WHERE q.project_id = %s AND q.is_active = TRUE AND q.prompt_set IS NOT NULL"
            )
            trend_params = [brand_domain_like, start_date, end_date]
            if enabled_llms_filter:
                trend_params.append(enabled_llms_filter)
            trend_params.append(project_id)
            cur.execute(trend_sql, trend_params)
            trend_queries = cur.fetchall()
        except Exception as trend_err:
            logger.warning(f"Could not fetch trend prompts for export: {trend_err}")

        # SoV, sentimiento y top dominios por prompt: mismo helper que alimenta
        # la tabla del panel, para que las columnas coincidan por construcción.
        prompt_metrics_by_id = collect_prompt_metrics(
            cur, project_id, [q['query_id'] for q in queries],
            start_date, end_date, enabled_llms_filter
        )

        # ✨ NEW: Cluster-level aggregated metrics (for "Clusters Overview" sheet)
        # Load prompt_clusters config to know which clusters are defined
        cur.execute("""
            SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s
        """, (project_id,))
        _pc_row = cur.fetchone() or {}
        _pc_raw = _pc_row.get('prompt_clusters') or {}
        if isinstance(_pc_raw, str):
            try:
                _pc_raw = json.loads(_pc_raw)
            except (json.JSONDecodeError, TypeError):
                _pc_raw = {}
        prompt_clusters_enabled = bool(_pc_raw.get('enabled'))
        defined_cluster_names = [
            c.get('name') for c in (_pc_raw.get('clusters') or [])
            if isinstance(c, dict) and c.get('name')
        ]

        clusters_aggregates = []
        clusters_by_llm_rows = []
        # A las hojas de clusters les aplica set/branded (el filtro de clusters
        # no: ya desglosan por cluster) → ids resueltos sin clusters
        _cluster_sheet_ids = _resolve_filtered_query_ids(
            cur, project_id, report_filters, include_clusters=False,
            start_date=start_date, end_date=end_date
        )
        _set_filter_sql = 'AND q.id = ANY(%s)' if _cluster_sheet_ids is not None else ''
        _set_params = [_cluster_sheet_ids] if _cluster_sheet_ids is not None else []
        if defined_cluster_names:
            cluster_agg_sql = """
                SELECT
                    q.topic_cluster AS cluster,
                    COUNT(DISTINCT q.id) AS prompts,
                    COUNT(r.id) AS total_results,
                    SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) AS brand_mentions,
                    AVG(r.position_in_list) FILTER (WHERE r.position_in_list IS NOT NULL AND r.position_in_list <= 30) AS avg_position,
                    ROUND(AVG(CASE WHEN r.brand_mentioned THEN 100.0 ELSE 0 END)::numeric, 1) AS mention_rate,
                    r.competitors_mentioned
                FROM llm_monitoring_queries q
                LEFT JOIN llm_monitoring_results r ON q.id = r.query_id
                    AND r.analysis_date >= %s AND r.analysis_date <= %s
                    {llm_filter}
                WHERE q.project_id = %s
                  AND q.is_active = TRUE
                  AND q.topic_cluster IS NOT NULL
                  AND q.topic_cluster = ANY(%s)
                  {set_filter}
                GROUP BY q.topic_cluster, r.competitors_mentioned
            """.format(
                llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms_filter else "",
                set_filter=_set_filter_sql
            )
            cluster_agg_params = [start_date, end_date]
            if enabled_llms_filter:
                cluster_agg_params.append(enabled_llms_filter)
            cluster_agg_params.append(project_id)
            cluster_agg_params.append(defined_cluster_names)
            cluster_agg_params.extend(_set_params)
            cur.execute(cluster_agg_sql, cluster_agg_params)
            _cluster_raw_rows = cur.fetchall()

            # Aggregate by cluster name (collapsing competitor_mentioned rows)
            _cluster_buckets = {}
            for _row in _cluster_raw_rows:
                _name = _row['cluster']
                b = _cluster_buckets.setdefault(_name, {
                    'prompts': set(),
                    'total_results': 0,
                    'brand_mentions': 0,
                    'positions_sum': 0.0,
                    'positions_cnt': 0,
                    'competitor_mentions': 0,
                })
                b['total_results'] += int(_row.get('total_results') or 0)
                b['brand_mentions'] += int(_row.get('brand_mentions') or 0)
                # We cannot recover per-prompt here reliably via this query alone, so get it separately
                cm = _row.get('competitors_mentioned') or {}
                if isinstance(cm, str):
                    try:
                        cm = json.loads(cm)
                    except (json.JSONDecodeError, TypeError):
                        cm = {}
                if isinstance(cm, dict):
                    for _c, _cnt in cm.items():
                        try:
                            cnt_int = int(_cnt)
                        except (TypeError, ValueError):
                            continue
                        if cnt_int > 0:
                            b['competitor_mentions'] += 1

            # Per-cluster prompt counts
            cur.execute(f"""
                SELECT q.topic_cluster AS cluster, COUNT(*) AS prompts
                FROM llm_monitoring_queries q
                WHERE q.project_id = %s AND q.is_active = TRUE AND q.topic_cluster = ANY(%s)
                {_set_filter_sql}
                GROUP BY q.topic_cluster
            """, tuple([project_id, defined_cluster_names] + _set_params))
            _prompt_counts = {r['cluster']: int(r['prompts']) for r in cur.fetchall()}

            # Aggregated positions (avg over valid positions <=30)
            cur.execute(f"""
                SELECT q.topic_cluster AS cluster,
                       AVG(r.position_in_list) FILTER (WHERE r.position_in_list IS NOT NULL AND r.position_in_list <= 30) AS avg_position
                FROM llm_monitoring_queries q
                JOIN llm_monitoring_results r ON q.id = r.query_id
                WHERE q.project_id = %s
                  AND r.analysis_date >= %s AND r.analysis_date <= %s
                  AND q.topic_cluster IS NOT NULL
                  AND q.topic_cluster = ANY(%s)
                  {_set_filter_sql}
                  {('AND r.llm_provider = ANY(%s)' if enabled_llms_filter else '')}
                GROUP BY q.topic_cluster
            """, tuple(
                [project_id, start_date, end_date, defined_cluster_names]
                + _set_params
                + ([enabled_llms_filter] if enabled_llms_filter else [])
            ))
            _position_rows = {r['cluster']: r['avg_position'] for r in cur.fetchall()}

            for _name in defined_cluster_names:
                b = _cluster_buckets.get(_name, {
                    'total_results': 0, 'brand_mentions': 0, 'competitor_mentions': 0
                })
                tr = b.get('total_results', 0)
                bm = b.get('brand_mentions', 0)
                cm_total = b.get('competitor_mentions', 0)
                sov_denom = bm + cm_total
                sov = round((bm / sov_denom) * 100, 1) if sov_denom > 0 else 0.0
                mention_rate = round((bm / tr) * 100, 1) if tr > 0 else 0.0
                ap_val = _position_rows.get(_name)
                clusters_aggregates.append({
                    'cluster': _name,
                    'prompts': _prompt_counts.get(_name, 0),
                    'total_results': tr,
                    'brand_mentions': bm,
                    'mention_rate': mention_rate,
                    'share_of_voice': sov,
                    'avg_position': round(float(ap_val), 2) if ap_val is not None else None,
                })

            # Per-cluster × LLM breakdown
            cur.execute(f"""
                SELECT q.topic_cluster AS cluster,
                       r.llm_provider,
                       COUNT(r.id) AS total_results,
                       SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) AS brand_mentions,
                       AVG(r.position_in_list) FILTER (WHERE r.position_in_list IS NOT NULL AND r.position_in_list <= 30) AS avg_position
                FROM llm_monitoring_queries q
                JOIN llm_monitoring_results r ON q.id = r.query_id
                WHERE q.project_id = %s
                  AND r.analysis_date >= %s AND r.analysis_date <= %s
                  AND q.topic_cluster IS NOT NULL
                  AND q.topic_cluster = ANY(%s)
                  {_set_filter_sql}
                  {('AND r.llm_provider = ANY(%s)' if enabled_llms_filter else '')}
                GROUP BY q.topic_cluster, r.llm_provider
                ORDER BY q.topic_cluster, r.llm_provider
            """, tuple(
                [project_id, start_date, end_date, defined_cluster_names]
                + _set_params
                + ([enabled_llms_filter] if enabled_llms_filter else [])
            ))
            for r in cur.fetchall():
                tr = int(r.get('total_results') or 0)
                bm = int(r.get('brand_mentions') or 0)
                mr = round((bm / tr) * 100, 1) if tr > 0 else 0.0
                ap = r.get('avg_position')
                clusters_by_llm_rows.append({
                    'cluster': r['cluster'],
                    'llm_provider': r['llm_provider'],
                    'total_results': tr,
                    'brand_mentions': bm,
                    'mention_rate': mr,
                    'avg_position': round(float(ap), 2) if ap is not None else None,
                })

        # 5. Detailed results (per query × LLM × date)
        detail_query = """
            SELECT
                r.analysis_date,
                r.llm_provider,
                r.model_used,
                q.query_text,
                q.topic_cluster,
                r.brand_mentioned,
                r.mention_count,
                r.position_in_list,
                r.total_items_in_list,
                r.position_source,
                r.sentiment,
                r.sentiment_score,
                r.competitors_mentioned,
                r.sources,
                r.tokens_used,
                r.cost_usd,
                r.response_time_ms,
                r.response_length
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON r.query_id = q.id
            WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
        """
        detail_params = [project_id, start_date, end_date]
        detail_query, detail_params = _add_query_filter(detail_query, detail_params, 'r.query_id')
        detail_query, detail_params = _add_llm_filter(detail_query, detail_params, 'r.llm_provider')
        detail_query += " ORDER BY r.analysis_date DESC, q.query_text, r.llm_provider"
        cur.execute(detail_query, detail_params)
        detailed_results = cur.fetchall()

        # 6b. Previous period data (for period-over-period comparison in export)
        prev_start_date = start_date - timedelta(days=days)
        prev_start_date_str = prev_start_date.strftime('%Y-%m-%d')

        # Previous branded/non-branded metrics
        prev_branded_export = {'branded_metrics': None, 'non_branded_metrics': None}
        try:
            if brand_keywords:
                prev_bq_export = """
                    SELECT r.llm_provider, q.query_text, r.brand_mentioned,
                           r.position_in_list, r.competitors_mentioned
                    FROM llm_monitoring_results r
                    JOIN llm_monitoring_queries q ON r.query_id = q.id
                    WHERE r.project_id = %s
                      AND r.analysis_date >= %s AND r.analysis_date < %s
                """
                prev_bparams_export = [project_id, prev_start_date_str, start_date_str]
                prev_bq_export, prev_bparams_export = _add_query_filter(prev_bq_export, prev_bparams_export, 'r.query_id')
                prev_bq_export, prev_bparams_export = _add_llm_filter(prev_bq_export, prev_bparams_export, 'r.llm_provider')
                cur.execute(prev_bq_export, prev_bparams_export)
                prev_branded_export = _compute_branded_metrics(cur.fetchall(), brand_keywords)
        except Exception as prev_b_err:
            logger.warning(f"Could not compute prev branded for export: {prev_b_err}")

        # Previous LLM metrics (avg mention_rate per provider)
        prev_llm_mr_export = {}
        try:
            if filtered_query_ids is not None:
                _prev_end_incl = (start_date - timedelta(days=1)).strftime('%Y-%m-%d')
                _prev_pseudo = pseudo_snapshots_lib.build_pseudo_snapshots(
                    cur, project_id, filtered_query_ids,
                    prev_start_date_str, _prev_end_incl,
                    enabled_llms=enabled_llms_filter,
                )
                _prev_rates = {}
                for s in _prev_pseudo:
                    _prev_rates.setdefault(s['llm_provider'], []).append(s['mention_rate'])
                prev_llm_mr_export = {
                    prov: sum(rates) / len(rates) for prov, rates in _prev_rates.items()
                }
            else:
                prev_mr_query = """
                    SELECT llm_provider, AVG(mention_rate) as avg_mention_rate
                    FROM llm_monitoring_snapshots
                    WHERE project_id = %s
                      AND snapshot_date >= %s AND snapshot_date < %s
                """
                prev_mr_params = [project_id, prev_start_date_str, start_date_str]
                prev_mr_query, prev_mr_params = _add_llm_filter(prev_mr_query, prev_mr_params)
                prev_mr_query += " GROUP BY llm_provider"
                cur.execute(prev_mr_query, prev_mr_params)
                for row in cur.fetchall():
                    prev_llm_mr_export[row['llm_provider']] = float(row['avg_mention_rate']) if row['avg_mention_rate'] is not None else 0
        except Exception as prev_mr_err:
            logger.warning(f"Could not compute prev LLM MR for export: {prev_mr_err}")

        # 6. URL Rankings (via service)
        try:
            urls_ranking = LLMMonitoringStatsService.get_project_urls_ranking(
                project_id=project_id,
                days=days,
                enabled_llms=enabled_llms_filter if enabled_llms_filter else None,
                limit=100,
                query_ids=filtered_query_ids
            )
        except Exception as url_err:
            logger.warning(f"⚠️ Could not fetch URL rankings: {url_err}")
            urls_ranking = []

        # 6b. Query fan-out: solo proyectos con búsqueda web (con 'off' el Excel no cambia)
        excel_fanout = _safe_fanout_metrics(cur, project, start_date, end_date,
                                            enabled_llms_filter or None, filtered_query_ids)

        # ──────────────────────────────────────────────────
        # BUILD EXCEL WORKBOOK
        # ──────────────────────────────────────────────────

        wb = openpyxl.Workbook()

        # — Shared styles —
        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_fill = PatternFill(start_color="161616", end_color="161616", fill_type="solid")
        subheader_font = Font(bold=True, size=10)
        subheader_fill = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
        title_font = Font(bold=True, size=14, color="161616")
        section_font = Font(bold=True, size=12, color="161616")
        brand_fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
        positive_fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
        negative_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        border = Border(
            left=Side(style='thin', color='E5E7EB'),
            right=Side(style='thin', color='E5E7EB'),
            top=Side(style='thin', color='E5E7EB'),
            bottom=Side(style='thin', color='E5E7EB')
        )
        center_align = Alignment(horizontal='center', vertical='center')
        wrap_align = Alignment(wrap_text=True, vertical='top')

        def write_header_row(ws, row, headers_list, col_start=1):
            """Write styled header row"""
            for col_idx, h in enumerate(headers_list, col_start):
                cell = ws.cell(row=row, column=col_idx, value=h)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = border

        def write_data_cell(ws, row, col, value, fmt=None):
            """Write data cell with border"""
            cell = ws.cell(row=row, column=col, value=value)
            cell.border = border
            if fmt:
                cell.number_format = fmt
            return cell

        def auto_width(ws, min_width=10, max_width=60):
            """Auto-adjust column widths"""
            for col_cells in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col_cells[0].column)
                for cell in col_cells:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                adjusted = min(max(max_len + 2, min_width), max_width)
                ws.column_dimensions[col_letter].width = adjusted

        # ════════════════════════════════════════════════
        # SHEET 1: PROJECT SUMMARY
        # ════════════════════════════════════════════════
        ws1 = wb.active
        ws1.title = "Project Summary"

        ws1['A1'] = "LLM Monitoring Report"
        ws1['A1'].font = title_font
        ws1['A2'] = f"Project: {project['name']}"
        ws1['A2'].font = Font(bold=True, size=12)
        ws1['A3'] = f"Period: Last {days} days ({start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')})"
        ws1['A4'] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        # Vista con la que se generó el informe: sin esto, un Excel filtrado
        # circulando por email diría cifras "incompletas" sin explicación.
        ws1['A5'] = f"Report view: {report_view_label}"
        ws1['A5'].font = Font(bold=True, color="7C3AED", size=10)

        # Project details
        ws1['A6'] = "Project Configuration"
        ws1['A6'].font = section_font
        details = [
            ("Brand Name", project.get('brand_name') or project['name']),
            ("Industry", project['industry'] or 'N/A'),
            ("Brand Domain", project.get('brand_domain') or 'N/A'),
            ("Brand Keywords", ', '.join(project.get('brand_keywords') or []) or 'N/A'),
            ("Language", project['language'] or 'N/A'),
            ("Country", project['country_code'] or 'N/A'),
            ("Enabled LLMs", ', '.join([llm.upper() for llm in (project.get('enabled_llms') or [])]) or 'All'),
            ("Queries per LLM", project.get('queries_per_llm') or 'N/A'),
            ("Status", "Active" if project.get('is_active') else "Paused"),
            ("Last Analysis", str(project.get('last_analysis_date') or 'Never')),
        ]
        for i, (label, value) in enumerate(details, 7):
            ws1[f'A{i}'] = label
            ws1[f'A{i}'].font = Font(bold=True)
            ws1[f'B{i}'] = str(value)

        # Competitors
        selected_competitors = project.get('selected_competitors') or []
        row_offset = 7 + len(details) + 1
        ws1[f'A{row_offset}'] = "Competitors"
        ws1[f'A{row_offset}'].font = section_font
        row_offset += 1
        if selected_competitors:
            ws1[f'A{row_offset}'] = "Domain"
            ws1[f'A{row_offset}'].font = Font(bold=True)
            ws1[f'B{row_offset}'] = "Keywords"
            ws1[f'B{row_offset}'].font = Font(bold=True)
            row_offset += 1
            for comp in selected_competitors:
                ws1[f'A{row_offset}'] = comp.get('domain', 'N/A')
                ws1[f'B{row_offset}'] = ', '.join(comp.get('keywords', []))
                row_offset += 1
        else:
            ws1[f'A{row_offset}'] = "No competitors configured"
            row_offset += 1

        # Global aggregated metrics summary
        row_offset += 1
        ws1[f'A{row_offset}'] = "Global Metrics Summary"
        ws1[f'A{row_offset}'].font = section_font
        row_offset += 1

        total_mentions_all = sum(m.get('total_mentions') or 0 for m in llm_metrics)
        total_results_all = sum(m.get('total_results') or 0 for m in llm_metrics)
        total_cost_all = sum(float(m.get('total_cost') or 0) for m in llm_metrics)
        total_tokens_all = sum(m.get('total_tokens') or 0 for m in llm_metrics)

        global_summary = [
            ("Total LLM Responses", total_results_all),
            ("Total Brand Mentions", total_mentions_all),
            ("Overall Mention Rate", f"{round(total_mentions_all / total_results_all * 100, 1)}%" if total_results_all > 0 else "N/A"),
            ("Total Cost (USD)", f"${round(total_cost_all, 4)}"),
            ("Total Tokens Used", total_tokens_all),
            ("Active Queries", len(queries)),
            ("URLs Cited", len(urls_ranking)),
        ]
        for label, value in global_summary:
            ws1[f'A{row_offset}'] = label
            ws1[f'A{row_offset}'].font = Font(bold=True)
            ws1[f'B{row_offset}'] = str(value)
            row_offset += 1

        # Period Comparison section (branded MR / SOV deltas)
        row_offset += 1
        ws1[f'A{row_offset}'] = "Period Comparison (vs Previous Period)"
        ws1[f'A{row_offset}'].font = section_font
        row_offset += 1

        if brand_keywords and detailed_results:
            branded_res_exp = []
            non_branded_res_exp = []
            for r in detailed_results:
                qt = r.get('query_text', '') or ''
                if classify_query_branded(qt, brand_keywords):
                    branded_res_exp.append(r)
                else:
                    non_branded_res_exp.append(r)
            def _quick_mr(subset):
                if not subset:
                    return 0.0
                mentions = sum(1 for r in subset if r.get('brand_mentioned'))
                return round((mentions / len(subset)) * 100, 1) if len(subset) > 0 else 0.0
            cur_br_mr = _quick_mr(branded_res_exp)
            cur_nb_mr = _quick_mr(non_branded_res_exp)
        else:
            cur_br_mr = 0.0
            cur_nb_mr = 0.0

        prev_br_metrics = prev_branded_export.get('branded_metrics') or {}
        prev_nb_metrics = prev_branded_export.get('non_branded_metrics') or {}
        prev_br_mr = prev_br_metrics.get('mention_rate', 0)
        prev_nb_mr = prev_nb_metrics.get('mention_rate', 0)

        comparison_rows = [
            ("Branded MR (Current)", f"{cur_br_mr}%"),
            ("Branded MR (Previous)", f"{prev_br_mr}%"),
            ("Branded MR Change", f"{round(cur_br_mr - prev_br_mr, 1)} pp"),
            ("Non-Branded MR (Current)", f"{cur_nb_mr}%"),
            ("Non-Branded MR (Previous)", f"{prev_nb_mr}%"),
            ("Non-Branded MR Change", f"{round(cur_nb_mr - prev_nb_mr, 1)} pp"),
        ]
        for label, value in comparison_rows:
            ws1[f'A{row_offset}'] = label
            ws1[f'A{row_offset}'].font = Font(bold=True)
            ws1[f'B{row_offset}'] = str(value)
            row_offset += 1

        ws1.column_dimensions['A'].width = 35
        ws1.column_dimensions['B'].width = 50

        # ════════════════════════════════════════════════
        # SHEET 2: SHARE OF VOICE (brand vs competitors over time)
        # ════════════════════════════════════════════════
        ws2 = wb.create_sheet("Share of Voice")

        # Build SOV data from snapshots
        # Aggregate across LLMs per date for brand SOV
        sov_by_date = {}
        all_competitor_domains = set()

        for snap in snapshots:
            d = str(snap['snapshot_date'])
            if d not in sov_by_date:
                sov_by_date[d] = {
                    'brand_sov': [], 'brand_weighted_sov': [],
                    'brand_mentions': 0, 'total_competitor_mentions': 0,
                    'competitor_breakdown': {}, 'weighted_competitor_breakdown': {}
                }

            sov_by_date[d]['brand_sov'].append(float(snap['share_of_voice'] or 0))
            sov_by_date[d]['brand_weighted_sov'].append(float(snap['weighted_share_of_voice'] or 0))
            sov_by_date[d]['brand_mentions'] += (snap['total_mentions'] or 0)
            sov_by_date[d]['total_competitor_mentions'] += (snap['total_competitor_mentions'] or 0)

            # Merge competitor breakdowns
            for field, target in [
                ('competitor_breakdown', 'competitor_breakdown'),
                ('weighted_competitor_breakdown', 'weighted_competitor_breakdown')
            ]:
                breakdown = snap.get(field) or {}
                if isinstance(breakdown, str):
                    try:
                        breakdown = json_module.loads(breakdown)
                    except:
                        breakdown = {}
                for comp_key, val in breakdown.items():
                    all_competitor_domains.add(comp_key)
                    if comp_key not in sov_by_date[d][target]:
                        sov_by_date[d][target][comp_key] = 0
                    sov_by_date[d][target][comp_key] += (val if isinstance(val, (int, float)) else 0)

        sorted_competitor_domains = sorted(all_competitor_domains)

        # Build header: Date, Brand SoV (Weighted), Brand SoV (Standard), Brand Mentions,
        #               Competitor1 SoV, Competitor1 Mentions, Competitor2 SoV, ...
        sov_headers = [
            "Date",
            "Brand SoV Weighted (%)", "Brand SoV Standard (%)",
            "Brand Mentions", "Total Competitor Mentions"
        ]
        for comp_d in sorted_competitor_domains:
            sov_headers.append(f"{comp_d} - Mentions")
            sov_headers.append(f"{comp_d} - Weighted SoV")

        write_header_row(ws2, 1, sov_headers)

        row_idx = 2
        for d in sorted(sov_by_date.keys()):
            data = sov_by_date[d]
            avg_wsov = round(sum(data['brand_weighted_sov']) / len(data['brand_weighted_sov']), 2) if data['brand_weighted_sov'] else 0
            avg_sov = round(sum(data['brand_sov']) / len(data['brand_sov']), 2) if data['brand_sov'] else 0

            col = 1
            write_data_cell(ws2, row_idx, col, d); col += 1
            write_data_cell(ws2, row_idx, col, avg_wsov, '0.00'); col += 1
            write_data_cell(ws2, row_idx, col, avg_sov, '0.00'); col += 1
            write_data_cell(ws2, row_idx, col, data['brand_mentions']); col += 1
            write_data_cell(ws2, row_idx, col, data['total_competitor_mentions']); col += 1

            # Competitor columns
            total_all = data['brand_mentions'] + data['total_competitor_mentions']
            for comp_d in sorted_competitor_domains:
                mentions = data['competitor_breakdown'].get(comp_d, 0)
                weighted = data['weighted_competitor_breakdown'].get(comp_d, 0)
                write_data_cell(ws2, row_idx, col, mentions); col += 1
                write_data_cell(ws2, row_idx, col, round(float(weighted), 2) if weighted else 0, '0.00'); col += 1

            row_idx += 1

        auto_width(ws2)

        # ════════════════════════════════════════════════
        # SHEET 3: LLM COMPARISON (aggregated per provider)
        # ════════════════════════════════════════════════
        ws3 = wb.create_sheet("LLM Comparison")

        comp_headers = [
            "LLM Provider", "Total Queries", "Total Results", "Total Mentions",
            "Mention Rate (%)", "Prev. MR (%)", "\u0394 MR (%)",
            "Avg Position",
            "Positive", "Neutral", "Negative", "Avg Sentiment Score",
            "SoV Weighted (%)", "SoV Standard (%)",
            "Total Cost (USD)", "Total Tokens", "Avg Response Time (ms)"
        ]
        write_header_row(ws3, 1, comp_headers)

        # Also compute avg SOV from snapshots per provider
        sov_per_provider = {}
        for snap in snapshots:
            prov = snap['llm_provider']
            if prov not in sov_per_provider:
                sov_per_provider[prov] = {'sov': [], 'wsov': []}
            sov_per_provider[prov]['sov'].append(float(snap['share_of_voice'] or 0))
            sov_per_provider[prov]['wsov'].append(float(snap['weighted_share_of_voice'] or 0))

        for row_idx, m in enumerate(llm_metrics, 2):
            prov = m['llm_provider']
            prov_sov = sov_per_provider.get(prov, {'sov': [0], 'wsov': [0]})
            avg_wsov = round(sum(prov_sov['wsov']) / len(prov_sov['wsov']), 2) if prov_sov['wsov'] else 0
            avg_sov = round(sum(prov_sov['sov']) / len(prov_sov['sov']), 2) if prov_sov['sov'] else 0

            cur_mr = round(float(m['mention_rate_pct'] or 0), 1)
            prev_mr = round(prev_llm_mr_export.get(prov, 0), 1)
            delta_mr = round(cur_mr - prev_mr, 1)

            col = 1
            write_data_cell(ws3, row_idx, col, prov.upper()); col += 1
            write_data_cell(ws3, row_idx, col, m['total_queries'] or 0); col += 1
            write_data_cell(ws3, row_idx, col, m['total_results'] or 0); col += 1
            write_data_cell(ws3, row_idx, col, m['total_mentions'] or 0); col += 1
            write_data_cell(ws3, row_idx, col, cur_mr, '0.0'); col += 1
            write_data_cell(ws3, row_idx, col, prev_mr, '0.0'); col += 1
            write_data_cell(ws3, row_idx, col, delta_mr, '0.0'); col += 1
            write_data_cell(ws3, row_idx, col, round(float(m['avg_position'] or 0), 1) if m['avg_position'] else 'N/A', '0.0'); col += 1
            write_data_cell(ws3, row_idx, col, m['positive_count'] or 0); col += 1
            write_data_cell(ws3, row_idx, col, m['neutral_count'] or 0); col += 1
            write_data_cell(ws3, row_idx, col, m['negative_count'] or 0); col += 1
            write_data_cell(ws3, row_idx, col, round(float(m['avg_sentiment_score'] or 0), 3) if m['avg_sentiment_score'] else 'N/A', '0.000'); col += 1
            write_data_cell(ws3, row_idx, col, avg_wsov, '0.00'); col += 1
            write_data_cell(ws3, row_idx, col, avg_sov, '0.00'); col += 1
            write_data_cell(ws3, row_idx, col, round(float(m['total_cost'] or 0), 4) if m['total_cost'] else 0, '0.0000'); col += 1
            write_data_cell(ws3, row_idx, col, m['total_tokens'] or 0); col += 1
            write_data_cell(ws3, row_idx, col, round(float(m['avg_response_time'] or 0), 0) if m['avg_response_time'] else 'N/A'); col += 1

        auto_width(ws3)

        # ════════════════════════════════════════════════
        # SHEET 4: DAILY METRICS (snapshots per date × LLM)
        # ════════════════════════════════════════════════
        ws4 = wb.create_sheet("Daily Metrics")

        daily_headers = [
            "Date", "LLM Provider",
            "Total Queries", "Total Mentions", "Mention Rate (%)",
            "Avg Position", "Top 3", "Top 5", "Top 10",
            "SoV Weighted (%)", "SoV Standard (%)",
            "Competitor Mentions",
            "Positive", "Neutral", "Negative", "Sentiment Score",
            "Cost (USD)", "Tokens", "Avg Response (ms)"
        ]
        write_header_row(ws4, 1, daily_headers)

        for row_idx, snap in enumerate(snapshots, 2):
            col = 1
            write_data_cell(ws4, row_idx, col, str(snap['snapshot_date'])); col += 1
            write_data_cell(ws4, row_idx, col, snap['llm_provider'].upper()); col += 1
            write_data_cell(ws4, row_idx, col, snap['total_queries'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, snap['total_mentions'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, round(float(snap['mention_rate'] or 0), 1), '0.0'); col += 1
            write_data_cell(ws4, row_idx, col, round(float(snap['avg_position'] or 0), 1) if snap['avg_position'] else 'N/A', '0.0'); col += 1
            write_data_cell(ws4, row_idx, col, snap['appeared_in_top3'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, snap['appeared_in_top5'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, snap['appeared_in_top10'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, round(float(snap['weighted_share_of_voice'] or 0), 2), '0.00'); col += 1
            write_data_cell(ws4, row_idx, col, round(float(snap['share_of_voice'] or 0), 2), '0.00'); col += 1
            write_data_cell(ws4, row_idx, col, snap['total_competitor_mentions'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, snap['positive_mentions'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, snap['neutral_mentions'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, snap['negative_mentions'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, round(float(snap['avg_sentiment_score'] or 0), 3) if snap['avg_sentiment_score'] else 'N/A', '0.000'); col += 1
            write_data_cell(ws4, row_idx, col, round(float(snap['total_cost_usd'] or 0), 4) if snap['total_cost_usd'] else 0, '0.0000'); col += 1
            write_data_cell(ws4, row_idx, col, snap['total_tokens'] or 0); col += 1
            write_data_cell(ws4, row_idx, col, snap['avg_response_time_ms'] or 0); col += 1

        auto_width(ws4)

        # ════════════════════════════════════════════════
        # SHEET 5: PROMPTS & QUERIES (enhanced)
        # ════════════════════════════════════════════════
        ws5 = wb.create_sheet("Prompts & Queries")

        export_country = project['country_code'] or 'Global'
        # Mismo orden de columnas que la tabla del panel (SOV, Avg. Pos.,
        # Mentions, Top Domains, Cluster, Sentiment), más el detalle que solo
        # tiene sentido en una hoja de cálculo.
        query_headers = [
            "Prompt", "Share of Voice (%)", "Avg Position", "Total Mentions",
            "Top Domains", "Cluster", "Set", "Sentiment", "Sentiment Score",
            "Text Mentions", "URL Citations",
            "Country", "Language", "Type", "LLMs Analyzed", "Total Results",
            "Visibility (%)", "Last Analysis", "Branded Query"
        ]

        def _write_prompt_sheet_rows(ws, rows_source, metrics_by_id):
            """Filas de prompts con formato compartido (hoja principal y Trend Prompts)."""
            for row_idx, q in enumerate(rows_source, 2):
                pm = metrics_by_id.get(q['query_id']) or empty_prompt_metrics()
                text_mentions = int(q['text_mentions'] or 0)
                url_citations = int(q['url_citations'] or 0)
                top_domains = ', '.join(
                    f"{d['domain']} ({d['mentions']})" for d in pm['top_domains']
                ) or 'N/A'
                sentiment_label = pm['sentiment']['label']
                sentiment_score = pm['sentiment']['score']

                col = 1
                write_data_cell(ws, row_idx, col, q['prompt']); col += 1
                write_data_cell(ws, row_idx, col,
                                pm['share_of_voice'] if pm['share_of_voice'] is not None else 'N/A', '0.0'); col += 1
                write_data_cell(ws, row_idx, col,
                                round_half_up(q['avg_position']) if q['avg_position'] else 'N/A', '0.0'); col += 1
                write_data_cell(ws, row_idx, col, text_mentions + url_citations); col += 1
                write_data_cell(ws, row_idx, col, top_domains); col += 1
                write_data_cell(ws, row_idx, col, q.get('topic_cluster') or 'Unassigned'); col += 1
                write_data_cell(ws, row_idx, col, q.get('prompt_set') or 'Core'); col += 1
                write_data_cell(ws, row_idx, col, sentiment_label.capitalize() if sentiment_label else 'N/A'); col += 1
                write_data_cell(ws, row_idx, col,
                                sentiment_score if sentiment_score is not None else 'N/A', '0.00'); col += 1
                write_data_cell(ws, row_idx, col, text_mentions); col += 1
                write_data_cell(ws, row_idx, col, url_citations); col += 1
                write_data_cell(ws, row_idx, col, export_country); col += 1
                write_data_cell(ws, row_idx, col, q['language'] or 'N/A'); col += 1
                write_data_cell(ws, row_idx, col, q['query_type'] or 'general'); col += 1
                write_data_cell(ws, row_idx, col, q['llms_analyzed'] or 0); col += 1
                write_data_cell(ws, row_idx, col, q['total_results'] or 0); col += 1
                write_data_cell(ws, row_idx, col, round_half_up(q['visibility_pct'] or 0), '0.0'); col += 1
                write_data_cell(ws, row_idx, col, str(q['last_analysis']) if q['last_analysis'] else 'N/A'); col += 1
                is_branded = classify_query_branded(q.get('prompt', '') or q.get('query_text', ''), brand_keywords)
                write_data_cell(ws, row_idx, col, "Yes" if is_branded else "No"); col += 1

        write_header_row(ws5, 1, query_headers)
        _write_prompt_sheet_rows(ws5, queries, prompt_metrics_by_id)

        ws5.column_dimensions['A'].width = 60
        auto_width(ws5, min_width=12)
        ws5.column_dimensions['A'].width = 60  # Override for prompt column

        # ════════════════════════════════════════════════
        # SHEET: TREND PROMPTS (sets no-core, SIEMPRE separados)
        # Decisión de producto: las tendencias/estacionales nunca se mezclan
        # con el núcleo — ni en pantalla ni en el documento descargado.
        # ════════════════════════════════════════════════
        if trend_queries:
            ws_trend = wb.create_sheet("Trend Prompts")
            ws_trend['A1'] = "Trend / Seasonal Prompts"
            ws_trend['A1'].font = title_font
            ws_trend['A2'] = (
                "Prompts from non-core sets, reported SEPARATELY from the core panel. "
                "Seasonal sets only run inside their window (UTC), so out-of-season "
                "prompts may show no recent data. See the 'Set' column for the set of each prompt."
            )
            ws_trend['A2'].font = Font(italic=True, color="6B7280", size=9)

            # Cabecera en fila 3 → las filas de datos empiezan en 4
            write_header_row(ws_trend, 3, query_headers)
            trend_metrics_by_id = collect_prompt_metrics(
                cur, project_id, [q['query_id'] for q in trend_queries],
                start_date, end_date, enabled_llms_filter
            )
            # Mismas columnas que la hoja principal, con los datos empezando
            # en la fila 4 (título + nota + cabecera ocupan las tres primeras)
            for row_idx, q in enumerate(trend_queries, 4):
                pm = trend_metrics_by_id.get(q['query_id']) or empty_prompt_metrics()
                text_mentions = int(q['text_mentions'] or 0)
                url_citations = int(q['url_citations'] or 0)
                top_domains = ', '.join(
                    f"{d['domain']} ({d['mentions']})" for d in pm['top_domains']
                ) or 'N/A'
                sentiment_label = pm['sentiment']['label']
                sentiment_score = pm['sentiment']['score']

                col = 1
                write_data_cell(ws_trend, row_idx, col, q['prompt']); col += 1
                write_data_cell(ws_trend, row_idx, col,
                                pm['share_of_voice'] if pm['share_of_voice'] is not None else 'N/A', '0.0'); col += 1
                write_data_cell(ws_trend, row_idx, col,
                                round_half_up(q['avg_position']) if q['avg_position'] else 'N/A', '0.0'); col += 1
                write_data_cell(ws_trend, row_idx, col, text_mentions + url_citations); col += 1
                write_data_cell(ws_trend, row_idx, col, top_domains); col += 1
                write_data_cell(ws_trend, row_idx, col, q.get('topic_cluster') or 'Unassigned'); col += 1
                write_data_cell(ws_trend, row_idx, col, q.get('prompt_set') or 'Core'); col += 1
                write_data_cell(ws_trend, row_idx, col, sentiment_label.capitalize() if sentiment_label else 'N/A'); col += 1
                write_data_cell(ws_trend, row_idx, col,
                                sentiment_score if sentiment_score is not None else 'N/A', '0.00'); col += 1
                write_data_cell(ws_trend, row_idx, col, text_mentions); col += 1
                write_data_cell(ws_trend, row_idx, col, url_citations); col += 1
                write_data_cell(ws_trend, row_idx, col, export_country); col += 1
                write_data_cell(ws_trend, row_idx, col, q['language'] or 'N/A'); col += 1
                write_data_cell(ws_trend, row_idx, col, q['query_type'] or 'general'); col += 1
                write_data_cell(ws_trend, row_idx, col, q['llms_analyzed'] or 0); col += 1
                write_data_cell(ws_trend, row_idx, col, q['total_results'] or 0); col += 1
                write_data_cell(ws_trend, row_idx, col, round_half_up(q['visibility_pct'] or 0), '0.0'); col += 1
                write_data_cell(ws_trend, row_idx, col, str(q['last_analysis']) if q['last_analysis'] else 'N/A'); col += 1
                is_branded = classify_query_branded(q.get('prompt', '') or q.get('query_text', ''), brand_keywords)
                write_data_cell(ws_trend, row_idx, col, "Yes" if is_branded else "No"); col += 1

            ws_trend.column_dimensions['A'].width = 60
            auto_width(ws_trend, min_width=12)
            ws_trend.column_dimensions['A'].width = 60

        # ════════════════════════════════════════════════
        # SHEET 5b/5c: CLUSTERS OVERVIEW & BY LLM  (✨ NEW)
        # ════════════════════════════════════════════════
        if defined_cluster_names:
            # 5b. Clusters Overview
            ws_clusters = wb.create_sheet("Clusters Overview")
            ws_clusters['A1'] = "Clusters Overview"
            ws_clusters['A1'].font = title_font
            ws_clusters['A2'] = (
                f"Manual topic clustering — {len(defined_cluster_names)} clusters configured. "
                f"{'Enabled' if prompt_clusters_enabled else 'Disabled'} at export time. "
                "Prompts without a cluster are excluded from these aggregates."
            )
            ws_clusters['A2'].font = Font(italic=True, color="6B7280", size=9)

            cluster_headers = [
                "Cluster", "Prompts", "Total Results",
                "Brand Mentions", "Mention Rate (%)",
                "Share of Voice (%)", "Avg Position"
            ]
            write_header_row(ws_clusters, 4, cluster_headers)

            for r_idx, c in enumerate(clusters_aggregates, 5):
                col = 1
                write_data_cell(ws_clusters, r_idx, col, c['cluster']); col += 1
                write_data_cell(ws_clusters, r_idx, col, c['prompts']); col += 1
                write_data_cell(ws_clusters, r_idx, col, c['total_results']); col += 1
                write_data_cell(ws_clusters, r_idx, col, c['brand_mentions']); col += 1
                write_data_cell(ws_clusters, r_idx, col, c['mention_rate'], '0.0'); col += 1
                write_data_cell(ws_clusters, r_idx, col, c['share_of_voice'], '0.0'); col += 1
                ap = c['avg_position']
                write_data_cell(
                    ws_clusters, r_idx, col,
                    round(float(ap), 1) if ap is not None else 'N/A',
                    '0.0'
                ); col += 1

            auto_width(ws_clusters, min_width=12)
            ws_clusters.column_dimensions['A'].width = 32

            # 5c. Clusters by LLM
            ws_clusters_llm = wb.create_sheet("Clusters by LLM")
            ws_clusters_llm['A1'] = "Clusters × LLM breakdown"
            ws_clusters_llm['A1'].font = title_font

            cllm_headers = [
                "Cluster", "LLM",
                "Total Results", "Brand Mentions",
                "Mention Rate (%)", "Avg Position"
            ]
            write_header_row(ws_clusters_llm, 3, cllm_headers)

            for r_idx, row in enumerate(clusters_by_llm_rows, 4):
                col = 1
                write_data_cell(ws_clusters_llm, r_idx, col, row['cluster']); col += 1
                write_data_cell(ws_clusters_llm, r_idx, col, row['llm_provider'].upper()); col += 1
                write_data_cell(ws_clusters_llm, r_idx, col, row['total_results']); col += 1
                write_data_cell(ws_clusters_llm, r_idx, col, row['brand_mentions']); col += 1
                write_data_cell(ws_clusters_llm, r_idx, col, row['mention_rate'], '0.0'); col += 1
                ap = row['avg_position']
                write_data_cell(
                    ws_clusters_llm, r_idx, col,
                    round(float(ap), 1) if ap is not None else 'N/A',
                    '0.0'
                ); col += 1

            auto_width(ws_clusters_llm, min_width=12)
            ws_clusters_llm.column_dimensions['A'].width = 28

        # ════════════════════════════════════════════════
        # SHEET 6: URL RANKINGS
        # ════════════════════════════════════════════════
        ws6 = wb.create_sheet("URL Rankings")

        url_headers = ["Rank", "URL", "Total Mentions", "Percentage (%)", "Providers"]
        # Add per-LLM breakdown columns
        llm_provider_names = ['openai', 'anthropic', 'google', 'perplexity']
        for llm_name in llm_provider_names:
            url_headers.append(f"{llm_name.upper()} Mentions")

        write_header_row(ws6, 1, url_headers)

        for row_idx, url_data in enumerate(urls_ranking, 2):
            col = 1
            write_data_cell(ws6, row_idx, col, url_data.get('rank', row_idx - 1)); col += 1
            write_data_cell(ws6, row_idx, col, url_data.get('url', 'N/A')); col += 1
            write_data_cell(ws6, row_idx, col, url_data.get('mentions', 0)); col += 1
            write_data_cell(ws6, row_idx, col, round(float(url_data.get('percentage', 0)), 1), '0.0'); col += 1
            write_data_cell(ws6, row_idx, col, ', '.join(url_data.get('providers', []))); col += 1

            llm_breakdown = url_data.get('llm_breakdown', {})
            for llm_name in llm_provider_names:
                write_data_cell(ws6, row_idx, col, llm_breakdown.get(llm_name, 0)); col += 1

        ws6.column_dimensions['B'].width = 70
        auto_width(ws6, min_width=12)
        ws6.column_dimensions['B'].width = 70  # Override for URL column

        # ════════════════════════════════════════════════
        # SHEET 6a: QUERY FAN-OUT (solo proyectos con búsqueda web)
        # ════════════════════════════════════════════════
        if excel_fanout:
            ws_fanout = wb.create_sheet("Query Fan-out")
            ws_fanout['A1'] = "Query Fan-out — what the models searched on the web"
            ws_fanout['A1'].font = title_font
            ws_fanout['A2'] = (f"{excel_fanout['responses_with_search']} of {excel_fanout['responses']} answers used web search "
                               f"since {excel_fanout['period']['start_date']}.")
            row_cursor = 4
            for title, table in (("By model", 'by_llm'), ("Top sub-queries", 'queries'), ("Pages the models read", 'pages')):
                rows = fanout_export_tables(excel_fanout)[table]
                ws_fanout.cell(row=row_cursor, column=1, value=title).font = Font(bold=True)
                write_header_row(ws_fanout, row_cursor + 1, rows[0])
                for offset, values in enumerate(rows[1:], row_cursor + 2):
                    for col, value in enumerate(values, 1):
                        write_data_cell(ws_fanout, offset, col, value)
                row_cursor += len(rows) + 3
            auto_width(ws_fanout, min_width=12, max_width=70)

        # ════════════════════════════════════════════════
        # SHEET 6b: CONTENT ANALYSIS  (Top 30 cited pages)
        # ════════════════════════════════════════════════
        # Solo aparece si el usuario ha lanzado el análisis de contenido: es una
        # acción manual y de pago (hace fetch de hasta 30 páginas), así que si
        # nunca se ha ejecutado no hay nada que volcar.
        content_overview = _safe_content_overview(project_id, days)
        content_results = [
            r for r in (content_overview.get('results') or []) if r.get('analysis')
        ]

        if content_results:
            ws_content = wb.create_sheet("Content Analysis")
            ws_content['A1'] = "Content Analysis — Top cited pages"
            ws_content['A1'].font = title_font
            csum = content_overview.get('summary') or {}
            ws_content['A2'] = (
                f"Brand presence detected in the content of the top "
                f"{content_overview.get('top_limit', 30)} most cited pages. "
                f"Analyzed: {csum.get('analyzed', 0)} · "
                f"You're mentioned: {csum.get('mentioned', 0)} · "
                f"Quick Wins: {csum.get('quick_wins', 0)} · "
                f"No brands: {csum.get('no_mentions', 0)} · "
                f"Competitor sites: {csum.get('competitor_pages', 0)} · "
                f"Pending: {csum.get('pending', 0)} · Errors: {csum.get('errors', 0)}"
            )
            ws_content['A2'].font = Font(italic=True, color="6B7280", size=9)

            content_headers = [
                "Rank", "URL", "Page Title", "Brand Presence", "Brand Mentioned",
                "Brand Mentions", "Brand Linked", "Brand Anchor Texts",
                "Competitors Found", "Competitors Linked",
                "Fetch Method", "HTTP Status", "Analyzed At", "Error"
            ]
            write_header_row(ws_content, 4, content_headers)

            for row_idx, item in enumerate(content_results, 5):
                a = item['analysis']
                competitors = [c for c in (a.get('competitors_found') or [])
                               if isinstance(c, dict) and c.get('mentioned')]
                comp_text = ', '.join(
                    f"{c.get('name') or c.get('domain')} ({c.get('mention_count', 0)})"
                    for c in competitors
                ) or 'None'
                comp_linked = ', '.join(
                    (c.get('name') or c.get('domain') or '') for c in competitors if c.get('linked')
                ) or 'None'
                anchors = ', '.join(a.get('brand_anchor_texts') or []) or 'None'

                col = 1
                write_data_cell(ws_content, row_idx, col, item.get('rank') or row_idx - 4); col += 1
                write_data_cell(ws_content, row_idx, col, item.get('url') or 'N/A'); col += 1
                write_data_cell(ws_content, row_idx, col, a.get('page_title') or 'N/A'); col += 1
                write_data_cell(ws_content, row_idx, col, _OPPORTUNITY_LABELS.get(
                    a.get('opportunity'), _OPPORTUNITY_LABELS[None])); col += 1
                write_data_cell(ws_content, row_idx, col, "Yes" if a.get('brand_mentioned') else "No"); col += 1
                write_data_cell(ws_content, row_idx, col, int(a.get('brand_mention_count') or 0)); col += 1
                write_data_cell(ws_content, row_idx, col, "Yes" if a.get('brand_linked') else "No"); col += 1
                write_data_cell(ws_content, row_idx, col, anchors); col += 1
                write_data_cell(ws_content, row_idx, col, comp_text); col += 1
                write_data_cell(ws_content, row_idx, col, comp_linked); col += 1
                write_data_cell(ws_content, row_idx, col, a.get('fetch_method') or 'direct'); col += 1
                write_data_cell(ws_content, row_idx, col, a.get('http_status') or 'N/A'); col += 1
                write_data_cell(ws_content, row_idx, col, (a.get('fetched_at') or 'N/A')[:19]); col += 1
                write_data_cell(ws_content, row_idx, col, a.get('error_reason') or ''); col += 1

            auto_width(ws_content, min_width=12)
            ws_content.column_dimensions['B'].width = 70
            ws_content.column_dimensions['C'].width = 45
            ws_content.column_dimensions['H'].width = 40
            ws_content.column_dimensions['I'].width = 40

        # ════════════════════════════════════════════════
        # SHEET 7: SENTIMENT ANALYSIS
        # ════════════════════════════════════════════════
        ws7 = wb.create_sheet("Sentiment Analysis")

        # Section A: Sentiment by LLM Provider (aggregated)
        ws7['A1'] = "Sentiment Distribution by LLM Provider"
        ws7['A1'].font = section_font

        sent_headers = [
            "LLM Provider", "Positive", "Neutral", "Negative", "Total",
            "Positive %", "Neutral %", "Negative %", "Avg Sentiment Score"
        ]
        write_header_row(ws7, 3, sent_headers)

        row_idx = 4
        for m in llm_metrics:
            pos = m['positive_count'] or 0
            neu = m['neutral_count'] or 0
            neg = m['negative_count'] or 0
            total = pos + neu + neg

            col = 1
            write_data_cell(ws7, row_idx, col, m['llm_provider'].upper()); col += 1
            c = write_data_cell(ws7, row_idx, col, pos); c.fill = positive_fill; col += 1
            write_data_cell(ws7, row_idx, col, neu); col += 1
            c = write_data_cell(ws7, row_idx, col, neg); c.fill = negative_fill; col += 1
            write_data_cell(ws7, row_idx, col, total); col += 1
            write_data_cell(ws7, row_idx, col, round(pos / total * 100, 1) if total > 0 else 0, '0.0'); col += 1
            write_data_cell(ws7, row_idx, col, round(neu / total * 100, 1) if total > 0 else 0, '0.0'); col += 1
            write_data_cell(ws7, row_idx, col, round(neg / total * 100, 1) if total > 0 else 0, '0.0'); col += 1
            write_data_cell(ws7, row_idx, col, round(float(m['avg_sentiment_score'] or 0), 3), '0.000'); col += 1
            row_idx += 1

        # Section B: Sentiment over time (from snapshots)
        row_idx += 2
        ws7.cell(row=row_idx, column=1, value="Sentiment Over Time (Daily)").font = section_font
        row_idx += 1

        sent_time_headers = ["Date", "LLM Provider", "Positive", "Neutral", "Negative", "Sentiment Score"]
        write_header_row(ws7, row_idx, sent_time_headers)
        row_idx += 1

        for snap in snapshots:
            col = 1
            write_data_cell(ws7, row_idx, col, str(snap['snapshot_date'])); col += 1
            write_data_cell(ws7, row_idx, col, snap['llm_provider'].upper()); col += 1
            write_data_cell(ws7, row_idx, col, snap['positive_mentions'] or 0); col += 1
            write_data_cell(ws7, row_idx, col, snap['neutral_mentions'] or 0); col += 1
            write_data_cell(ws7, row_idx, col, snap['negative_mentions'] or 0); col += 1
            write_data_cell(ws7, row_idx, col, round(float(snap['avg_sentiment_score'] or 0), 3) if snap['avg_sentiment_score'] else 'N/A', '0.000'); col += 1
            row_idx += 1

        auto_width(ws7)

        # ════════════════════════════════════════════════
        # SHEET 8: DETAILED RESULTS (per query × LLM × date)
        # ════════════════════════════════════════════════
        ws8 = wb.create_sheet("Detailed Results")

        detail_headers = [
            "Date", "LLM Provider", "Model", "Query/Prompt", "Cluster", "Branded Query",
            "Brand Mentioned", "Mention Count", "Position", "Total in List",
            "Position Source", "Sentiment", "Sentiment Score",
            "Competitors Mentioned", "URLs Cited",
            "Tokens", "Cost (USD)", "Response Time (ms)", "Response Length"
        ]
        write_header_row(ws8, 1, detail_headers)

        # Limit to 5000 rows to avoid memory issues
        max_detail_rows = min(len(detailed_results), 5000)

        for row_idx, r in enumerate(detailed_results[:max_detail_rows], 2):
            col = 1
            write_data_cell(ws8, row_idx, col, str(r['analysis_date'])); col += 1
            write_data_cell(ws8, row_idx, col, r['llm_provider'].upper()); col += 1
            write_data_cell(ws8, row_idx, col, r['model_used'] or 'N/A'); col += 1
            write_data_cell(ws8, row_idx, col, r['query_text'] or 'N/A'); col += 1
            # ✨ NEW: Cluster column (after Query/Prompt)
            write_data_cell(ws8, row_idx, col, r.get('topic_cluster') or 'Unassigned'); col += 1
            is_branded_detail = classify_query_branded(r.get('query_text', '') or '', brand_keywords)
            write_data_cell(ws8, row_idx, col, "Yes" if is_branded_detail else "No"); col += 1
            write_data_cell(ws8, row_idx, col, "Yes" if r['brand_mentioned'] else "No"); col += 1
            write_data_cell(ws8, row_idx, col, r['mention_count'] or 0); col += 1
            write_data_cell(ws8, row_idx, col, r['position_in_list'] if r['position_in_list'] else 'N/A'); col += 1
            write_data_cell(ws8, row_idx, col, r['total_items_in_list'] if r['total_items_in_list'] else 'N/A'); col += 1
            write_data_cell(ws8, row_idx, col, r['position_source'] or 'N/A'); col += 1
            write_data_cell(ws8, row_idx, col, r['sentiment'] or 'N/A'); col += 1
            write_data_cell(ws8, row_idx, col, round(float(r['sentiment_score'] or 0), 3) if r['sentiment_score'] else 'N/A', '0.000'); col += 1

            # Competitors mentioned (JSON → readable string)
            comps = r.get('competitors_mentioned') or {}
            if isinstance(comps, str):
                try:
                    comps = json_module.loads(comps)
                except:
                    comps = {}
            if isinstance(comps, dict) and comps:
                comps_str = ', '.join([f"{k}: {v}" for k, v in comps.items()])
            else:
                comps_str = 'None'
            write_data_cell(ws8, row_idx, col, comps_str); col += 1

            # Sources/URLs (JSON → readable string)
            sources = r.get('sources') or []
            if isinstance(sources, str):
                try:
                    sources = json_module.loads(sources)
                except:
                    sources = []
            if isinstance(sources, list) and sources:
                urls_str = ', '.join([s.get('url', '') for s in sources if isinstance(s, dict) and s.get('url')])
            else:
                urls_str = 'None'
            write_data_cell(ws8, row_idx, col, urls_str); col += 1

            write_data_cell(ws8, row_idx, col, r['tokens_used'] or 0); col += 1
            write_data_cell(ws8, row_idx, col, round(float(r['cost_usd'] or 0), 6) if r['cost_usd'] else 0, '0.000000'); col += 1
            write_data_cell(ws8, row_idx, col, r['response_time_ms'] or 0); col += 1
            write_data_cell(ws8, row_idx, col, r['response_length'] or 0); col += 1

        # Add note if truncated
        if len(detailed_results) > max_detail_rows:
            note_row = max_detail_rows + 2
            ws8.cell(row=note_row, column=1,
                     value=f"⚠ Showing {max_detail_rows} of {len(detailed_results)} results. Full data available in the application.").font = Font(italic=True, color="666666")

        ws8.column_dimensions['D'].width = 60  # Query column
        ws8.column_dimensions['E'].width = 22  # Cluster column (NEW)
        ws8.column_dimensions['N'].width = 30  # Competitors (shifted)
        ws8.column_dimensions['O'].width = 50  # URLs (shifted)
        auto_width(ws8, min_width=12)
        ws8.column_dimensions['D'].width = 60
        ws8.column_dimensions['E'].width = 22
        ws8.column_dimensions['N'].width = 30
        ws8.column_dimensions['O'].width = 50

        # ════════════════════════════════════════════════
        # SHEET 9: BRANDED vs NON-BRANDED ANALYSIS
        # ════════════════════════════════════════════════
        ws9 = wb.create_sheet("Branded vs Non-Branded")

        # Title
        ws9.merge_cells('A1:J1')
        ws9['A1'] = 'Branded vs Non-Branded Analysis'
        ws9['A1'].font = Font(name='Calibri', size=14, bold=True, color='FFFFFF')
        ws9['A1'].fill = PatternFill(start_color='161616', end_color='161616', fill_type='solid')
        ws9['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws9.row_dimensions[1].height = 35

        # Classify all detailed results
        branded_results = []
        non_branded_results = []
        for r in detailed_results:
            qt = r.get('query_text', '') or ''
            if classify_query_branded(qt, brand_keywords):
                branded_results.append(r)
            else:
                non_branded_results.append(r)

        # Helper to compute metrics for a subset
        def compute_subset_metrics(subset, label, prev_mr=0.0):
            total = len(subset)
            mentions = sum(1 for r in subset if r.get('brand_mentioned'))
            mention_rate = round((mentions / total) * 100, 1) if total > 0 else 0.0
            delta_mr = round(mention_rate - prev_mr, 1)
            positions = [r['position_in_list'] for r in subset if r.get('position_in_list') is not None]
            avg_pos = round(sum(positions) / len(positions), 1) if positions else None
            pos_count = sum(1 for r in subset if r.get('sentiment') == 'positive')
            neu_count = sum(1 for r in subset if r.get('sentiment') == 'neutral')
            neg_count = sum(1 for r in subset if r.get('sentiment') == 'negative')
            return [label, total, mentions, mention_rate, round(prev_mr, 1), delta_mr,
                    avg_pos or 'N/A',
                    round(pos_count / total * 100, 1) if total else 0,
                    round(neu_count / total * 100, 1) if total else 0,
                    round(neg_count / total * 100, 1) if total else 0]

        # Headers
        bvnb_headers = ['Query Type', 'Total Results', 'Total Mentions', 'Mention Rate (%)',
                        'Prev. MR (%)', '\u0394 MR',
                        'Avg Position', 'Positive %', 'Neutral %', 'Negative %']
        for col_idx, h in enumerate(bvnb_headers, 1):
            cell = ws9.cell(row=3, column=col_idx, value=h)
            cell.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='374151', end_color='374151', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border

        # Previous period MRs for branded / non-branded
        prev_all_mr = 0.0
        prev_b_mr_exp = (prev_branded_export.get('branded_metrics') or {}).get('mention_rate', 0)
        prev_nb_mr_exp = (prev_branded_export.get('non_branded_metrics') or {}).get('mention_rate', 0)
        if prev_b_mr_exp or prev_nb_mr_exp:
            # Weighted average for "all" based on result counts
            prev_b_total = (prev_branded_export.get('branded_metrics') or {}).get('total_results', 0)
            prev_nb_total = (prev_branded_export.get('non_branded_metrics') or {}).get('total_results', 0)
            prev_all_total = prev_b_total + prev_nb_total
            if prev_all_total > 0:
                prev_all_mr = (prev_b_mr_exp * prev_b_total + prev_nb_mr_exp * prev_nb_total) / prev_all_total

        # Data rows
        all_metrics = compute_subset_metrics(detailed_results, 'All Queries', prev_all_mr)
        branded_m = compute_subset_metrics(branded_results, 'Branded', prev_b_mr_exp)
        non_branded_m = compute_subset_metrics(non_branded_results, 'Non-Branded', prev_nb_mr_exp)

        for row_idx, row_data in enumerate([all_metrics, non_branded_m, branded_m], 4):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws9.cell(row=row_idx, column=col_idx, value=value)
                cell.font = Font(name='Calibri', size=11)
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = border
                if row_idx == 5:  # Non-branded row highlight
                    cell.fill = PatternFill(start_color='D1FAE5', end_color='D1FAE5', fill_type='solid')
                elif row_idx == 6:  # Branded row highlight
                    cell.fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid')

        # Auto-width — use the shared helper that reads col via get_column_letter,
        # safe with MergedCell objects (A1:J1 is merged for the title).
        auto_width(ws9, min_width=12, max_width=30)

        # ──────────────────────────────────────────────────
        # SAVE & RETURN
        # ──────────────────────────────────────────────────

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        safe_name = project['name'].replace(' ', '-').replace('/', '-')[:50]
        filename = f"llm-monitoring-{safe_name}-{days}d-{datetime.now().strftime('%Y%m%d')}.xlsx"

        logger.info(f"✅ Comprehensive Excel exported for project {project_id} ({len(snapshots)} snapshots, {len(queries)} queries, {len(detailed_results)} results, {len(urls_ranking)} URLs)")

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"❌ Error exportando Excel para proyecto {project_id}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
