"""Exportación a PDF de un proyecto de LLM Monitoring (ruta en llm_monitoring_routes.py).

Sacado tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros gigantes):
la ruta, sus decoradores y la URL siguen allí y llaman a esta función. Los helpers
de informes compartidos con las demás rutas se importan del módulo de rutas; por
eso este módulo se importa al atender la petición y no al cargar las rutas.
"""

import logging
from datetime import datetime, timedelta
from flask import request, jsonify
import brand_palette
import json
import re

from llm_monitoring_routes import (
    LLMMonitoringStatsService,
    _OPPORTUNITY_LABELS,
    _narrow_llms,
    _normalize_days_param,
    _parse_report_filters,
    _report_view_label,
    _resolve_filtered_query_ids,
    _safe_content_overview,
    _safe_fanout_metrics,
    classify_query_branded,
    fanout_export_tables,
    fetch_current_models,
    get_db_connection,
    pseudo_snapshots_lib,
)

logger = logging.getLogger(__name__)


def exportar_pdf(project_id):
    """
    Exportar datos del proyecto a PDF - Multi-page professional report

    Query params:
        days: int - Periodo de dias (default: 30)
    """
    from io import BytesIO
    from flask import send_file

    logger.info(f"Starting PDF export for project {project_id}")

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        logger.info("reportlab imported successfully for PDF export")
    except ImportError as e:
        logger.error(f"reportlab no esta instalado: {e}")
        return jsonify({'error': 'PDF export not available. Missing reportlab library.'}), 500

    days = _normalize_days_param(request.args.get('days'), default=30)
    # Misma métrica de SoV que el toggle del panel (que por defecto es weighted).
    # Sin esto el PDF imprimía siempre la estándar y su cifra de Share of Voice
    # no coincidía con la que el usuario tenía delante al pulsar "descargar".
    sov_metric = 'weighted' if request.args.get('metric', 'weighted') != 'normal' else 'normal'
    sov_column = 'weighted_share_of_voice' if sov_metric == 'weighted' else 'share_of_voice'
    sov_metric_label = 'weighted by position' if sov_metric == 'weighted' else 'standard'
    report_filters = _parse_report_filters(request.args)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexion a BD'}), 500
    cur = None
    try:
        cur = conn.cursor()

        # ── 1. Project data ──
        cur.execute("""
            SELECT id, name, industry, brand_domain, brand_keywords, language,
                   country_code, enabled_llms, selected_competitors,
                   search_mode, search_enabled_at
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        prev_start = start_date - timedelta(days=days)
        enabled_llms_filter = _narrow_llms(project.get('enabled_llms') or [], report_filters)
        brand_keywords_pdf = project.get('brand_keywords') or []

        # Modelos vigentes. Mismo helper que el modal "Models" del panel, para
        # que la portada del informe no pueda listar otros modelos.
        current_models_pdf, _models_from_db = fetch_current_models(cur)

        # Helper to append LLM filter
        def _llm_filter(query, params):
            if enabled_llms_filter:
                query += " AND llm_provider = ANY(%s)"
                params.append(enabled_llms_filter)
            return query, params

        # Filtro global del informe: el PDF refleja la vista con la que se
        # descargó, como el panel y el Excel.
        pdf_filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=start_date, end_date=end_date)

        def _pdf_query_filter(query, params, column='query_id'):
            if pdf_filtered_query_ids is not None:
                query += f" AND {column} = ANY(%s)"
                params.append(pdf_filtered_query_ids)
            return query, params

        _pdf_label = _report_view_label(report_filters)
        pdf_report_view_label = '' if _pdf_label == 'All prompts' else _pdf_label

        # ── 2. LLM results metrics (per provider) ──
        pdf_q = """
            SELECT llm_provider,
                   COUNT(DISTINCT query_id) as total_queries,
                   SUM(CASE WHEN brand_mentioned THEN 1 ELSE 0 END) as total_mentions,
                   ROUND(AVG(CASE WHEN brand_mentioned THEN 100.0 ELSE 0 END), 1) as mention_rate_pct
            FROM llm_monitoring_results
            WHERE project_id = %s AND analysis_date >= %s AND analysis_date <= %s
        """
        pdf_p = [project_id, start_date, end_date]
        pdf_q, pdf_p = _pdf_query_filter(pdf_q, pdf_p)
        pdf_q, pdf_p = _llm_filter(pdf_q, pdf_p)
        pdf_q += " GROUP BY llm_provider ORDER BY mention_rate_pct DESC"
        cur.execute(pdf_q, pdf_p)
        metrics = cur.fetchall()

        # ── 3. Snapshot aggregates (SOV, sentiment, position) ──
        if pdf_filtered_query_ids is not None:
            # Con filtro activo: agregados desde pseudo-snapshots (los snapshots
            # reales agregan todos los prompts y no pueden filtrarse)
            _pdf_pseudo = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, pdf_filtered_query_ids,
                start_date.date(), end_date.date(),
                enabled_llms=enabled_llms_filter,
            )
            _by_prov = {}
            for s in _pdf_pseudo:
                _by_prov.setdefault(s['llm_provider'], []).append(s)
            snapshot_metrics = {}
            for prov, rows_p in _by_prov.items():
                _pos_vals = [r['avg_position'] for r in rows_p if r['avg_position'] is not None]
                snapshot_metrics[prov] = {
                    'llm_provider': prov,
                    'avg_mr': sum(r['mention_rate'] for r in rows_p) / len(rows_p),
                    'avg_sov': sum(r[sov_column] for r in rows_p) / len(rows_p),
                    'avg_pos': (sum(_pos_vals) / len(_pos_vals)) if _pos_vals else None,
                    'avg_sentiment': sum(r['avg_sentiment_score'] for r in rows_p) / len(rows_p),
                    'total_positive': sum(r['positive_mentions'] for r in rows_p),
                    'total_neutral': sum(r['neutral_mentions'] for r in rows_p),
                    'total_negative': sum(r['negative_mentions'] for r in rows_p),
                    'total_queries': sum(r['total_queries'] for r in rows_p),
                }

            _prev_pseudo_pdf = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, pdf_filtered_query_ids,
                prev_start.date(), (start_date - timedelta(days=1)).date(),
                enabled_llms=enabled_llms_filter,
            )
            if _prev_pseudo_pdf:
                prev_snap_agg = {
                    'avg_mr': sum(r['mention_rate'] for r in _prev_pseudo_pdf) / len(_prev_pseudo_pdf),
                    'avg_sov': sum(r[sov_column] for r in _prev_pseudo_pdf) / len(_prev_pseudo_pdf),
                }
            else:
                prev_snap_agg = {}
        else:
            snap_q = """
                SELECT llm_provider,
                    AVG(mention_rate) as avg_mr,
                    AVG({sov_column}) as avg_sov,
                    AVG(avg_position) as avg_pos,
                    AVG(avg_sentiment_score) as avg_sentiment,
                    SUM(positive_mentions) as total_positive,
                    SUM(neutral_mentions) as total_neutral,
                    SUM(negative_mentions) as total_negative,
                    SUM(total_queries) as total_queries
                FROM llm_monitoring_snapshots
                WHERE project_id = %s AND snapshot_date >= %s AND snapshot_date <= %s
            """.format(sov_column=sov_column)
            snap_p = [project_id, start_date.date(), end_date.date()]
            snap_q, snap_p = _llm_filter(snap_q, snap_p)
            snap_q += " GROUP BY llm_provider ORDER BY avg_mr DESC"
            cur.execute(snap_q, snap_p)
            snapshot_metrics = {row['llm_provider']: row for row in cur.fetchall()}

            # Previous period snapshot aggregates for comparison
            prev_snap_q = """
                SELECT AVG(mention_rate) as avg_mr,
                       AVG({sov_column}) as avg_sov
                FROM llm_monitoring_snapshots
                WHERE project_id = %s AND snapshot_date >= %s AND snapshot_date < %s
            """.format(sov_column=sov_column)
            prev_snap_p = [project_id, prev_start.date(), start_date.date()]
            prev_snap_q, prev_snap_p = _llm_filter(prev_snap_q, prev_snap_p)
            cur.execute(prev_snap_q, prev_snap_p)
            prev_snap_agg = cur.fetchone() or {}

        # ── 4. Branded vs Non-Branded results ──
        bvnb_q = """
            SELECT q.query_text, r.brand_mentioned, r.sentiment
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON r.query_id = q.id
            WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
        """
        bvnb_p = [project_id, start_date, end_date]
        bvnb_q, bvnb_p = _pdf_query_filter(bvnb_q, bvnb_p, 'r.query_id')
        bvnb_q, bvnb_p = _llm_filter(bvnb_q, bvnb_p)
        cur.execute(bvnb_q, bvnb_p)
        bvnb_results = cur.fetchall()

        # Previous period branded/non-branded
        prev_bvnb_q = """
            SELECT q.query_text, r.brand_mentioned, r.sentiment
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON r.query_id = q.id
            WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date < %s
        """
        prev_bvnb_p = [project_id, prev_start, start_date]
        prev_bvnb_q, prev_bvnb_p = _pdf_query_filter(prev_bvnb_q, prev_bvnb_p, 'r.query_id')
        prev_bvnb_q, prev_bvnb_p = _llm_filter(prev_bvnb_q, prev_bvnb_p)
        prev_branded_pdf = []
        prev_non_branded_pdf = []
        try:
            cur.execute(prev_bvnb_q, prev_bvnb_p)
            for r in cur.fetchall():
                qt = r.get('query_text', '') or ''
                if classify_query_branded(qt, brand_keywords_pdf):
                    prev_branded_pdf.append(r)
                else:
                    prev_non_branded_pdf.append(r)
        except Exception:
            logger.warning("Could not compute prev branded for PDF")

        # Previous period LLM MR
        prev_llm_mr = {}
        try:
            plmr_q = """
                SELECT llm_provider,
                       ROUND(AVG(CASE WHEN brand_mentioned THEN 100.0 ELSE 0 END), 1) as mention_rate_pct
                FROM llm_monitoring_results
                WHERE project_id = %s AND analysis_date >= %s AND analysis_date < %s
            """
            plmr_p = [project_id, prev_start, start_date]
            plmr_q, plmr_p = _pdf_query_filter(plmr_q, plmr_p)
            plmr_q, plmr_p = _llm_filter(plmr_q, plmr_p)
            plmr_q += " GROUP BY llm_provider"
            cur.execute(plmr_q, plmr_p)
            for row in cur.fetchall():
                prev_llm_mr[row['llm_provider']] = float(row['mention_rate_pct'] or 0)
        except Exception:
            logger.warning("Could not compute prev LLM MR for PDF")

        # ── 5. Prompt / query performance ──
        prompt_q = """
            SELECT q.query_text,
                q.topic_cluster,
                COUNT(r.id) as total_results,
                SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) as mentions,
                AVG(CASE WHEN r.brand_mentioned THEN r.position_in_list ELSE NULL END) as avg_position
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON r.query_id = q.id
            WHERE r.project_id = %s AND r.analysis_date >= %s AND r.analysis_date <= %s
        """
        prompt_p = [project_id, start_date, end_date]
        prompt_q, prompt_p = _pdf_query_filter(prompt_q, prompt_p, 'r.query_id')
        prompt_q, prompt_p = _llm_filter(prompt_q, prompt_p)
        prompt_q += " GROUP BY q.query_text, q.topic_cluster ORDER BY mentions DESC, total_results DESC LIMIT 20"
        cur.execute(prompt_q, prompt_p)
        prompt_data = cur.fetchall()

        # ── 5b. ✨ NEW: Cluster performance data ──
        cur.execute("SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s", (project_id,))
        _pc_pdf_row = cur.fetchone() or {}
        _pc_pdf_raw = _pc_pdf_row.get('prompt_clusters') or {}
        if isinstance(_pc_pdf_raw, str):
            try:
                _pc_pdf_raw = json.loads(_pc_pdf_raw)
            except (json.JSONDecodeError, TypeError):
                _pc_pdf_raw = {}
        pdf_clusters_enabled = bool(_pc_pdf_raw.get('enabled'))
        pdf_defined_clusters = [
            c.get('name') for c in (_pc_pdf_raw.get('clusters') or [])
            if isinstance(c, dict) and c.get('name')
        ]
        pdf_cluster_metrics = []
        if pdf_defined_clusters:
            cluster_pdf_sql = """
                SELECT q.topic_cluster AS cluster,
                       COUNT(DISTINCT q.id) AS prompts,
                       COUNT(r.id) AS total_results,
                       SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) AS brand_mentions,
                       AVG(r.position_in_list) FILTER (WHERE r.position_in_list IS NOT NULL AND r.position_in_list <= 30) AS avg_position
                FROM llm_monitoring_queries q
                LEFT JOIN llm_monitoring_results r ON q.id = r.query_id
                    AND r.analysis_date >= %s AND r.analysis_date <= %s
            """
            cluster_pdf_params = [start_date, end_date]
            if enabled_llms_filter:
                cluster_pdf_sql += " AND r.llm_provider = ANY(%s) "
                cluster_pdf_params.append(enabled_llms_filter)
            _pdf_cluster_ids = _resolve_filtered_query_ids(
                cur, project_id, report_filters, include_clusters=False,
            start_date=start_date, end_date=end_date
            )
            _pdf_set_sql = 'AND q.id = ANY(%s)' if _pdf_cluster_ids is not None else ''
            _pdf_set_params = [_pdf_cluster_ids] if _pdf_cluster_ids is not None else []
            cluster_pdf_sql += f"""
                WHERE q.project_id = %s
                  AND q.is_active = TRUE
                  AND q.topic_cluster IS NOT NULL
                  AND q.topic_cluster = ANY(%s)
                  {_pdf_set_sql}
                GROUP BY q.topic_cluster
            """
            cluster_pdf_params.extend([project_id, pdf_defined_clusters])
            cluster_pdf_params.extend(_pdf_set_params)
            cur.execute(cluster_pdf_sql, cluster_pdf_params)
            cluster_rows_pdf = cur.fetchall()

            # Competitor mentions per cluster (for SoV)
            comp_cluster_sql = """
                SELECT q.topic_cluster AS cluster, r.competitors_mentioned
                FROM llm_monitoring_queries q
                JOIN llm_monitoring_results r ON q.id = r.query_id
                WHERE q.project_id = %s
                  AND r.analysis_date >= %s AND r.analysis_date <= %s
                  AND q.topic_cluster IS NOT NULL
                  AND q.topic_cluster = ANY(%s)
            """
            comp_cluster_params = [project_id, start_date, end_date, pdf_defined_clusters]
            if _pdf_set_sql:
                comp_cluster_sql += f" {_pdf_set_sql}"
                comp_cluster_params.extend(_pdf_set_params)
            if enabled_llms_filter:
                comp_cluster_sql += " AND r.llm_provider = ANY(%s)"
                comp_cluster_params.append(enabled_llms_filter)
            cur.execute(comp_cluster_sql, comp_cluster_params)
            _comp_cluster_rows = cur.fetchall()
            comp_cnt_by_cluster = {name: 0 for name in pdf_defined_clusters}
            for _ccr in _comp_cluster_rows:
                _cname = _ccr['cluster']
                _cm = _ccr.get('competitors_mentioned') or {}
                if isinstance(_cm, str):
                    try:
                        _cm = json.loads(_cm)
                    except (json.JSONDecodeError, TypeError):
                        _cm = {}
                if isinstance(_cm, dict):
                    for _v in _cm.values():
                        try:
                            if int(_v) > 0:
                                comp_cnt_by_cluster[_cname] = comp_cnt_by_cluster.get(_cname, 0) + 1
                        except (TypeError, ValueError):
                            continue

            by_name = {r['cluster']: r for r in cluster_rows_pdf}
            for name in pdf_defined_clusters:
                row = by_name.get(name, {})
                tr = int(row.get('total_results') or 0)
                bm = int(row.get('brand_mentions') or 0)
                cm_total = comp_cnt_by_cluster.get(name, 0)
                mention_rate = round((bm / tr) * 100, 1) if tr > 0 else 0.0
                sov_denom = bm + cm_total
                sov = round((bm / sov_denom) * 100, 1) if sov_denom > 0 else 0.0
                ap = row.get('avg_position')
                pdf_cluster_metrics.append({
                    'cluster': name,
                    'prompts': int(row.get('prompts') or 0),
                    'total_results': tr,
                    'brand_mentions': bm,
                    'mention_rate': mention_rate,
                    'share_of_voice': sov,
                    'avg_position': round(float(ap), 1) if ap is not None else None,
                })

        # ── 6. Top URLs (via service) ──
        urls_data = []
        try:
            urls_data = LLMMonitoringStatsService.get_project_urls_ranking(
                project_id=project_id,
                days=days,
                enabled_llms=enabled_llms_filter if enabled_llms_filter else None,
                limit=15,
                query_ids=pdf_filtered_query_ids
            )
        except Exception as url_err:
            logger.warning(f"Could not fetch URL rankings for PDF: {url_err}")

        # ── 7. Competitor snapshot breakdown ──
        if pdf_filtered_query_ids is not None:
            comp_snapshots = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, pdf_filtered_query_ids,
                start_date.date(), end_date.date(),
                enabled_llms=enabled_llms_filter,
            )
            comp_snapshots.sort(key=lambda s: s['snapshot_date'])
        else:
            comp_snapshot_q = """
                SELECT snapshot_date, llm_provider,
                       total_mentions, total_competitor_mentions,
                       competitor_breakdown
                FROM llm_monitoring_snapshots
                WHERE project_id = %s AND snapshot_date >= %s AND snapshot_date <= %s
            """
            comp_snap_p = [project_id, start_date.date(), end_date.date()]
            comp_snapshot_q, comp_snap_p = _llm_filter(comp_snapshot_q, comp_snap_p)
            comp_snapshot_q += " ORDER BY snapshot_date"
            cur.execute(comp_snapshot_q, comp_snap_p)
            comp_snapshots = cur.fetchall()

        # ── Aggregate competitor mentions ──
        brand_total_mentions = 0
        competitor_mention_totals = {}
        num_days_with_data = set()
        for snap in comp_snapshots:
            brand_total_mentions += int(snap.get('total_mentions') or 0)
            num_days_with_data.add(str(snap.get('snapshot_date', '')))
            breakdown = snap.get('competitor_breakdown') or {}
            if isinstance(breakdown, str):
                import json as json_mod
                try:
                    breakdown = json_mod.loads(breakdown)
                except Exception:
                    breakdown = {}
            for comp_key, count in breakdown.items():
                comp_key_lower = comp_key.lower().strip()
                competitor_mention_totals[comp_key_lower] = competitor_mention_totals.get(comp_key_lower, 0) + int(count or 0)

        days_count = max(len(num_days_with_data), 1)

        # Map competitor_breakdown keys to selected_competitors domains
        comp_display_map = {}  # normalized_key -> display_name
        for comp in (project.get('selected_competitors') or []):
            domain = (comp.get('domain') or '').lower().strip()
            keywords = comp.get('keywords') or []
            display = domain or (keywords[0] if keywords else 'Unknown')
            # Map domain and keywords to this display name
            for variant in [domain] + [k.lower().strip() for k in keywords]:
                if variant:
                    comp_display_map[variant] = display
                    # Also strip TLD
                    for tld in ['.com', '.es', '.mx', '.org', '.net', '.io', '.co']:
                        if variant.endswith(tld):
                            comp_display_map[variant.replace(tld, '')] = display

        # Consolidate competitor mentions by display name
        comp_consolidated = {}
        for key, count in competitor_mention_totals.items():
            display = comp_display_map.get(key, key)
            comp_consolidated[display] = comp_consolidated.get(display, 0) + count

        # ── Compute aggregate KPIs ──
        total_positive = sum(float(s.get('total_positive') or 0) for s in snapshot_metrics.values())
        total_neutral = sum(float(s.get('total_neutral') or 0) for s in snapshot_metrics.values())
        total_negative = sum(float(s.get('total_negative') or 0) for s in snapshot_metrics.values())
        sentiment_total = total_positive + total_neutral + total_negative

        if sentiment_total > 0:
            best_sent = max(
                [('Positive', total_positive), ('Neutral', total_neutral), ('Negative', total_negative)],
                key=lambda x: x[1]
            )
            dominant_sentiment = best_sent[0]
        else:
            dominant_sentiment = 'N/A'

        # Weighted averages across providers
        agg_mr_values = [float(s.get('avg_mr') or 0) for s in snapshot_metrics.values() if s.get('avg_mr') is not None]
        agg_sov_values = [float(s.get('avg_sov') or 0) for s in snapshot_metrics.values() if s.get('avg_sov') is not None]
        agg_pos_values = [float(s.get('avg_pos') or 0) for s in snapshot_metrics.values() if s.get('avg_pos') is not None and float(s.get('avg_pos') or 0) > 0]

        overall_mr = round(sum(agg_mr_values) / len(agg_mr_values), 1) if agg_mr_values else 0
        overall_sov = round(sum(agg_sov_values) / len(agg_sov_values), 1) if agg_sov_values else 0
        overall_pos = round(sum(agg_pos_values) / len(agg_pos_values), 1) if agg_pos_values else 0

        prev_mr_agg = round(float(prev_snap_agg.get('avg_mr') or 0), 1)
        prev_sov_agg = round(float(prev_snap_agg.get('avg_sov') or 0), 1)

        # ── Classify branded / non-branded ──
        branded_pdf = []
        non_branded_pdf = []
        for r in bvnb_results:
            qt = r.get('query_text', '') or ''
            if classify_query_branded(qt, brand_keywords_pdf):
                branded_pdf.append(r)
            else:
                non_branded_pdf.append(r)

        # ── Competitors list ──
        selected_competitors = project.get('selected_competitors') or []
        competitor_names = []
        for comp in selected_competitors:
            domain = comp.get('domain', '')
            if domain:
                competitor_names.append(domain)

        # =====================================================================
        # BUILD PDF
        # =====================================================================
        output = BytesIO()

        # Color palette — espejo de static/brand-dashboard-tokens.css (--cs-*).
        # Si cambian los tokens del panel, cambiar aquí también o el PDF deriva.
        CLR_DARK = colors.HexColor('#0F172A')       # --cs-text-primary
        CLR_WHITE = colors.white
        CLR_ACCENT = colors.HexColor('#d9f9b8')     # --cs-accent
        CLR_SUBHEADER = colors.HexColor('#F1F5F9')  # --cs-bg-subtle
        CLR_GREEN_CELL = colors.HexColor('#E4F4EA')  # tinte de --cs-success
        CLR_YELLOW_CELL = colors.HexColor('#FEF3C7')
        CLR_RED_CELL = colors.HexColor('#FBE9E9')    # tinte de --cs-error
        CLR_BODY = colors.HexColor('#334155')       # --cs-surface-dark
        CLR_BORDER = colors.HexColor('#E2E8F0')     # --cs-border
        CLR_LIGHT_GRAY = colors.HexColor('#94A3B8')  # --cs-text-tertiary
        CLR_ROW_ALT = colors.HexColor('#F8FAFC')

        page_width, page_height = A4
        usable_width = page_width - 4 * cm  # 2cm margins each side

        # Page header / footer callbacks
        total_pages_holder = [0]

        # Logo watermark: render brand text "Clicandseo." matching SVG identity
        def _draw_logo_watermark(canvas_obj, x, y, font_size=12, dark_bg=False):
            """Draw the Clicandseo. logo as styled text (matching brand SVG)."""
            text_color = colors.white if dark_bg else colors.HexColor('#0F172A')
            faded_color = colors.Color(1, 1, 1, 0.5) if dark_bg else colors.Color(0.06, 0.09, 0.16, 0.5)
            accent_color = CLR_ACCENT

            canvas_obj.setFont('Helvetica-Bold', font_size)
            canvas_obj.setFillColor(text_color)
            # "Clic"
            canvas_obj.drawString(x, y, "Clic")
            w_clic = canvas_obj.stringWidth("Clic", 'Helvetica-Bold', font_size)
            # "and" (faded)
            canvas_obj.setFont('Helvetica', font_size)
            canvas_obj.setFillColor(faded_color)
            canvas_obj.drawString(x + w_clic, y, "and")
            w_and = canvas_obj.stringWidth("and", 'Helvetica', font_size)
            # "seo"
            canvas_obj.setFont('Helvetica-Bold', font_size)
            canvas_obj.setFillColor(text_color)
            canvas_obj.drawString(x + w_clic + w_and, y, "seo")
            w_seo = canvas_obj.stringWidth("seo", 'Helvetica-Bold', font_size)
            # "." (accent green)
            canvas_obj.setFillColor(accent_color)
            canvas_obj.drawString(x + w_clic + w_and + w_seo, y, ".")

        def _draw_page_chrome(canvas_obj, doc_obj):
            """Shared header + footer + watermark for all pages."""
            canvas_obj.saveState()
            # Dark header bar
            canvas_obj.setFillColor(CLR_DARK)
            canvas_obj.rect(0, page_height - 1.2 * cm, page_width, 1.2 * cm, fill=1, stroke=0)
            canvas_obj.setFillColor(CLR_WHITE)
            canvas_obj.setFont('Helvetica-Bold', 10)
            canvas_obj.drawString(2 * cm, page_height - 0.85 * cm, "LLM Visibility Monitor Report")
            # Header logo (dark bg → white text)
            _draw_logo_watermark(canvas_obj, page_width - 4.5 * cm, page_height - 0.85 * cm, font_size=10, dark_bg=True)
            # Footer text
            canvas_obj.setFillColor(CLR_LIGHT_GRAY)
            canvas_obj.setFont('Helvetica', 8)
            footer_text = f"Generated by ClicAndSEO LLM Visibility Monitor | Page {doc_obj.page}"
            canvas_obj.drawCentredString(page_width / 2, 1 * cm, footer_text)
            # Watermark logo bottom-right (light bg → dark text)
            _draw_logo_watermark(canvas_obj, page_width - 4 * cm, 0.5 * cm, font_size=11, dark_bg=False)
            canvas_obj.restoreState()

        def _on_first_page(canvas_obj, doc_obj):
            _draw_page_chrome(canvas_obj, doc_obj)

        def _on_later_pages(canvas_obj, doc_obj):
            _draw_page_chrome(canvas_obj, doc_obj)

        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2.2 * cm,
            bottomMargin=1.8 * cm
        )

        styles = getSampleStyleSheet()

        # ── Custom styles ──
        st_title = ParagraphStyle('PDFTitle', parent=styles['Heading1'],
                                  fontSize=22, fontName='Helvetica-Bold',
                                  textColor=CLR_DARK, spaceAfter=6, spaceBefore=0)
        st_project = ParagraphStyle('PDFProject', parent=styles['Heading1'],
                                    fontSize=18, fontName='Helvetica-Bold',
                                    textColor=CLR_DARK, spaceAfter=4)
        st_period = ParagraphStyle('PDFPeriod', parent=styles['Normal'],
                                   fontSize=10, fontName='Helvetica',
                                   textColor=CLR_LIGHT_GRAY, spaceAfter=14)
        st_section = ParagraphStyle('PDFSection', parent=styles['Heading2'],
                                    fontSize=14, fontName='Helvetica-Bold',
                                    textColor=CLR_DARK, spaceAfter=8, spaceBefore=12)
        st_subsection = ParagraphStyle('PDFSubsection', parent=styles['Heading3'],
                                       fontSize=11, fontName='Helvetica-Bold',
                                       textColor=CLR_BODY, spaceAfter=6, spaceBefore=8)
        st_body = ParagraphStyle('PDFBody', parent=styles['Normal'],
                                 fontSize=9, fontName='Helvetica',
                                 textColor=CLR_BODY, spaceAfter=4)
        st_kpi_label = ParagraphStyle('KPILabel', parent=styles['Normal'],
                                      fontSize=8, fontName='Helvetica',
                                      textColor=CLR_LIGHT_GRAY, spaceAfter=0, alignment=TA_CENTER)
        st_kpi_value = ParagraphStyle('KPIValue', parent=styles['Normal'],
                                      fontSize=16, fontName='Helvetica-Bold',
                                      textColor=CLR_DARK, spaceAfter=0, alignment=TA_CENTER)
        st_kpi_delta = ParagraphStyle('KPIDelta', parent=styles['Normal'],
                                      fontSize=8, fontName='Helvetica',
                                      textColor=CLR_LIGHT_GRAY, spaceAfter=0, alignment=TA_CENTER)
        st_no_data = ParagraphStyle('NoData', parent=styles['Normal'],
                                    fontSize=10, fontName='Helvetica',
                                    textColor=CLR_LIGHT_GRAY, spaceAfter=8,
                                    alignment=TA_CENTER)

        # Reusable table style builder
        def _base_table_style(num_rows):
            """Returns a standard TableStyle list for dark-header tables."""
            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), CLR_DARK),
                ('TEXTCOLOR', (0, 0), (-1, 0), CLR_WHITE),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('TEXTCOLOR', (0, 1), (-1, -1), CLR_BODY),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, CLR_BORDER),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            # Alternating row colors
            for i in range(1, num_rows):
                if i % 2 == 0:
                    style_cmds.append(('BACKGROUND', (0, i), (-1, i), CLR_ROW_ALT))
            return style_cmds

        def _truncate(text, max_len):
            """Truncate text with ellipsis."""
            if not text:
                return 'N/A'
            text = str(text)
            if len(text) <= max_len:
                return text
            return text[:max_len - 3] + '...'

        def _delta_str(current, previous):
            """Format delta string for percentage point change."""
            d = round(current - previous, 1)
            if previous == 0 and current == 0:
                return 'N/A'
            sign = '+' if d > 0 else ''
            return f"{sign}{d} pp"

        def _sentiment_label(score):
            """Convert numeric sentiment score to label."""
            if score is None:
                return 'N/A'
            s = float(score)
            if s >= 0.3:
                return 'Positive'
            elif s <= -0.3:
                return 'Negative'
            return 'Neutral'

        # Delta color helper for KPI paragraphs
        # Pasos -text de los estados (--cs-success-text / --cs-error-text): los
        # tonos base de marca no llegan a contraste de texto.
        CLR_DELTA_UP = colors.HexColor('#287A4C')
        CLR_DELTA_DOWN = colors.HexColor('#D13B3B')
        st_kpi_delta_up = ParagraphStyle('KPIDeltaUp', parent=st_kpi_delta, textColor=CLR_DELTA_UP)
        st_kpi_delta_down = ParagraphStyle('KPIDeltaDown', parent=st_kpi_delta, textColor=CLR_DELTA_DOWN)

        def _delta_style(current, previous):
            """Return (text, style) for delta display with color."""
            d = round(current - previous, 1)
            if previous == 0 and current == 0:
                return 'N/A', st_kpi_delta
            if previous == 0 and current > 0:
                return f'+{current} pp', st_kpi_delta_up
            sign = '+' if d > 0 else ''
            style = st_kpi_delta_up if d > 0 else (st_kpi_delta_down if d < 0 else st_kpi_delta)
            return f"vs prev: {sign}{d} pp", style

        elements = []

        # =================================================================
        # PAGE 1: PROJECT DETAILS
        # =================================================================
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph("LLM Visibility Monitor Report", st_title))
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph(project['name'], st_project))
        elements.append(Paragraph(
            f"Period: Last {days} days  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            st_period
        ))
        # Vista con la que se generó el informe (set/clusters): sin esta línea,
        # un PDF filtrado circulando fuera de contexto diría cifras parciales
        # sin explicación.
        if pdf_report_view_label:
            elements.append(Paragraph(
                f"<b>Report view:</b> {pdf_report_view_label} — trend/seasonal sets are always reported separately from Core.",
                st_period
            ))
        elements.append(Spacer(1, 0.8 * cm))

        # ── Project Details ──
        elements.append(Paragraph("Project Details", st_section))
        details_info = [
            f"<b>Industry:</b> {project.get('industry') or 'N/A'}",
            f"<b>Domain:</b> {project.get('brand_domain') or 'N/A'}",
            f"<b>Keywords:</b> {', '.join(brand_keywords_pdf) if brand_keywords_pdf else 'N/A'}",
            f"<b>Language:</b> {project.get('language') or 'N/A'}  |  <b>Country:</b> {project.get('country_code') or 'N/A'}",
        ]
        for info in details_info:
            elements.append(Paragraph(info, st_body))
        elements.append(Spacer(1, 0.4 * cm))

        # ── Competitors list ──
        if competitor_names:
            elements.append(Paragraph("Competitors", st_subsection))
            elements.append(Paragraph(', '.join(competitor_names), st_body))
            elements.append(Spacer(1, 0.5 * cm))

        # ── Competitor Details table ──
        if selected_competitors:
            elements.append(Paragraph("Competitor Details", st_subsection))
            elements.append(Spacer(1, 0.2 * cm))
            comp_detail_header = ['Competitor', 'Domain', 'Keywords']
            comp_detail_rows = [comp_detail_header]
            for i, comp in enumerate(selected_competitors):
                domain = comp.get('domain', 'N/A')
                keywords = ', '.join(comp.get('keywords', [])) or 'N/A'
                comp_detail_rows.append([
                    f"Competitor {i + 1}",
                    domain,
                    Paragraph(_truncate(keywords, 45), st_body),
                ])

            cd_widths = [3 * cm, 4.5 * cm, 7.5 * cm]
            cd_table = Table(comp_detail_rows, colWidths=cd_widths)
            cd_style = _base_table_style(len(comp_detail_rows))
            cd_style.append(('ALIGN', (0, 1), (0, -1), 'LEFT'))
            cd_style.append(('ALIGN', (1, 1), (1, -1), 'LEFT'))
            cd_style.append(('ALIGN', (2, 1), (2, -1), 'LEFT'))
            cd_table.setStyle(TableStyle(cd_style))
            elements.append(cd_table)

        # ── LLM Models Used ──
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph("LLM Models Used", st_subsection))
        elements.append(Spacer(1, 0.2 * cm))

        if current_models_pdf:
            provider_labels = {
                'openai': 'ChatGPT', 'anthropic': 'Claude',
                'google': 'Gemini', 'perplexity': 'Perplexity'
            }
            model_rows = [['Provider', 'Model', 'Knowledge Cutoff']]
            for prov, m in sorted(current_models_pdf.items()):
                if enabled_llms_filter and prov not in enabled_llms_filter:
                    continue
                label = provider_labels.get(prov, prov.title())
                model_name = m.get('display_name') or m.get('model_id', 'N/A')
                cutoff = m.get('knowledge_cutoff') or 'Unknown'
                model_rows.append([label, model_name, cutoff])

            if len(model_rows) > 1:
                m_widths = [3.5 * cm, 5 * cm, 6.5 * cm]
                m_table = Table(model_rows, colWidths=m_widths)
                m_style = _base_table_style(len(model_rows))
                m_style.append(('ALIGN', (0, 1), (-1, -1), 'LEFT'))
                m_table.setStyle(TableStyle(m_style))
                elements.append(m_table)
            else:
                elements.append(Paragraph("No model data available.", st_no_data))
        else:
            elements.append(Paragraph("No model data available.", st_no_data))

        # =================================================================
        # PAGE 2: EXECUTIVE SUMMARY + LLM PERFORMANCE
        # =================================================================
        elements.append(PageBreak())
        elements.append(Spacer(1, 0.3 * cm))

        # ── Executive Summary KPIs (2x2 grid with colored deltas) ──
        elements.append(Paragraph("Executive Summary", st_section))

        mr_delta_text, mr_delta_st = _delta_style(overall_mr, prev_mr_agg)
        sov_delta_text, sov_delta_st = _delta_style(overall_sov, prev_sov_agg)

        kpi_data = [
            [
                Paragraph(f"<b>{overall_mr}%</b>", st_kpi_value),
                Paragraph(f"<b>{overall_sov}%</b>", st_kpi_value),
            ],
            [
                Paragraph("Mention Rate", st_kpi_label),
                Paragraph(f"Share of Voice ({sov_metric_label})", st_kpi_label),
            ],
            [
                Paragraph(mr_delta_text, mr_delta_st),
                Paragraph(sov_delta_text, sov_delta_st),
            ],
            [Spacer(1, 0.2 * cm), Spacer(1, 0.2 * cm)],
            [
                Paragraph(f"<b>#{overall_pos}</b>" if overall_pos > 0 else "<b>N/A</b>", st_kpi_value),
                Paragraph(f"<b>{dominant_sentiment}</b>", st_kpi_value),
            ],
            [
                Paragraph("Avg Position (when mentioned)", st_kpi_label),
                Paragraph("Dominant Sentiment", st_kpi_label),
            ],
        ]

        kpi_col_w = usable_width / 2
        kpi_table = Table(kpi_data, colWidths=[kpi_col_w, kpi_col_w])
        kpi_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (0, 2), 1, CLR_BORDER),
            ('BOX', (1, 0), (1, 2), 1, CLR_BORDER),
            ('BOX', (0, 4), (0, 5), 1, CLR_BORDER),
            ('BOX', (1, 4), (1, 5), 1, CLR_BORDER),
            ('BACKGROUND', (0, 0), (0, 2), CLR_SUBHEADER),
            ('BACKGROUND', (1, 0), (1, 2), CLR_SUBHEADER),
            ('BACKGROUND', (0, 4), (0, 5), CLR_SUBHEADER),
            ('BACKGROUND', (1, 4), (1, 5), CLR_SUBHEADER),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 0.5 * cm))

        # ── LLM Performance Comparison ──
        elements.append(Paragraph("LLM Performance Comparison", st_section))

        if metrics:
            perf_header = ["LLM", "Prompts", "Mentions", "MR (%)", "SOV (%)", "Avg Pos", "Sentiment", "vs Prev MR"]
            perf_rows = [perf_header]
            row_meta = []  # (sentiment_label, delta_value) per data row

            for idx, m in enumerate(metrics):
                provider = m['llm_provider']
                cur_mr = round(float(m['mention_rate_pct'] or 0), 1)
                prev_mr_val = round(prev_llm_mr.get(provider, 0), 1)
                snap = snapshot_metrics.get(provider, {})
                sov_val = round(float(snap.get('avg_sov') or 0), 1)
                pos_val = round(float(snap.get('avg_pos') or 0), 1)
                sent_score = snap.get('avg_sentiment')
                sent_label = _sentiment_label(sent_score)

                delta_val = round(cur_mr - prev_mr_val, 1)
                delta_sign = '+' if delta_val > 0 else ''
                delta_text = f"{delta_sign}{delta_val} pp" if (prev_mr_val > 0 or cur_mr > 0) else 'new'

                row_meta.append((sent_label, delta_val))

                perf_rows.append([
                    provider.upper(),
                    str(m['total_queries'] or 0),
                    str(m['total_mentions'] or 0),
                    f"{cur_mr}%",
                    f"{sov_val}%",
                    f"#{pos_val}" if pos_val > 0 else 'N/A',
                    sent_label,
                    delta_text,
                ])

            perf_widths = [2 * cm, 1.6 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 2 * cm, 2 * cm]
            perf_table = Table(perf_rows, colWidths=perf_widths)
            style_cmds = _base_table_style(len(perf_rows))
            # Color sentiment and delta columns
            for row_idx, (sent, dv) in enumerate(row_meta):
                r = row_idx + 1
                if sent == 'Positive':
                    style_cmds.append(('BACKGROUND', (6, r), (6, r), CLR_GREEN_CELL))
                elif sent == 'Negative':
                    style_cmds.append(('BACKGROUND', (6, r), (6, r), CLR_RED_CELL))
                # Color delta column (col 7) green/red
                if dv > 0:
                    style_cmds.append(('TEXTCOLOR', (7, r), (7, r), CLR_DELTA_UP))
                elif dv < 0:
                    style_cmds.append(('TEXTCOLOR', (7, r), (7, r), CLR_DELTA_DOWN))
            perf_table.setStyle(TableStyle(style_cmds))
            elements.append(perf_table)
        else:
            elements.append(Paragraph("No LLM performance data available for this period.", st_no_data))

        elements.append(Spacer(1, 0.8 * cm))

        # ── Branded vs Non-Branded Analysis ──
        elements.append(Paragraph("Branded vs Non-Branded Analysis", st_section))

        bvnb_header = ['Prompt Type', 'Responses', 'Mentions', 'MR (%)', 'vs Prev']
        bvnb_rows = [bvnb_header]
        bvnb_deltas = []

        prev_subsets = {'Non-Branded': prev_non_branded_pdf, 'Branded': prev_branded_pdf}
        for label, subset in [('Non-Branded', non_branded_pdf), ('Branded', branded_pdf)]:
            total = len(subset)
            mentions = sum(1 for r in subset if r.get('brand_mentioned'))
            rate = round((mentions / total) * 100, 1) if total > 0 else 0
            prev_sub = prev_subsets.get(label, [])
            prev_total = len(prev_sub)
            prev_mentions = sum(1 for r in prev_sub if r.get('brand_mentioned'))
            prev_rate = round((prev_mentions / prev_total) * 100, 1) if prev_total > 0 else 0
            dv = round(rate - prev_rate, 1)
            bvnb_deltas.append(dv)
            bvnb_rows.append([label, str(total), str(mentions), f"{rate}%", _delta_str(rate, prev_rate)])

        bvnb_widths = [3.2 * cm, 2.2 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm]
        bvnb_table = Table(bvnb_rows, colWidths=bvnb_widths)
        bvnb_style = _base_table_style(len(bvnb_rows))
        # Non-branded row green, branded row yellow
        bvnb_style.append(('BACKGROUND', (0, 1), (-1, 1), CLR_GREEN_CELL))
        bvnb_style.append(('BACKGROUND', (0, 2), (-1, 2), CLR_YELLOW_CELL))
        # Color delta column
        for i, dv in enumerate(bvnb_deltas):
            r = i + 1
            if dv > 0:
                bvnb_style.append(('TEXTCOLOR', (4, r), (4, r), CLR_DELTA_UP))
            elif dv < 0:
                bvnb_style.append(('TEXTCOLOR', (4, r), (4, r), CLR_DELTA_DOWN))
        bvnb_table.setStyle(TableStyle(bvnb_style))
        elements.append(bvnb_table)

        # =================================================================
        # PAGE 3: COMPETITOR ANALYSIS
        # =================================================================
        elements.append(PageBreak())
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph("Competitor Analysis", st_section))
        elements.append(Paragraph("Brand vs competitors — Share of Voice comparison", st_body))
        elements.append(Spacer(1, 0.3 * cm))

        # Build brand vs competitors SOV table
        all_entity_mentions = brand_total_mentions + sum(comp_consolidated.values())
        sorted_comps = sorted(comp_consolidated.items(), key=lambda x: x[1], reverse=True) if comp_consolidated else []

        if all_entity_mentions > 0:
            sov_header = ['Brand / Competitor', 'Total Mentions', 'Mention Share (%)', 'Avg Mentions/Day']
            sov_rows = [sov_header]

            brand_share = round((brand_total_mentions / all_entity_mentions) * 100, 1)
            brand_avg_day = round(brand_total_mentions / days_count, 1)
            sov_rows.append([
                Paragraph(f"<b>{(project.get('brand_domain') or project['name']).upper()}</b>  (Your Brand)", st_body),
                str(brand_total_mentions),
                f"{brand_share}%",
                str(brand_avg_day),
            ])

            for comp_name, comp_mentions in sorted_comps:
                comp_share = round((comp_mentions / all_entity_mentions) * 100, 1)
                comp_avg_day = round(comp_mentions / days_count, 1)
                sov_rows.append([
                    comp_name.upper(),
                    str(comp_mentions),
                    f"{comp_share}%",
                    str(comp_avg_day),
                ])

            sov_widths = [5.5 * cm, 3 * cm, 3.5 * cm, 3 * cm]
            sov_table = Table(sov_rows, colWidths=sov_widths)
            sov_style = _base_table_style(len(sov_rows))
            sov_style.append(('BACKGROUND', (0, 1), (-1, 1), CLR_GREEN_CELL))
            sov_style.append(('ALIGN', (0, 1), (0, -1), 'LEFT'))
            sov_table.setStyle(TableStyle(sov_style))
            elements.append(sov_table)
        else:
            elements.append(Paragraph("No competitor mention data available for this period.", st_no_data))

        elements.append(Spacer(1, 0.5 * cm))

        # SOV Over Time line chart (like the UI)
        if comp_snapshots and all_entity_mentions > 0:
            from reportlab.graphics.shapes import Drawing, Line, String, Rect
            from reportlab.graphics.charts.lineplots import LinePlot
            from reportlab.graphics.widgets.markers import makeMarker
            from reportlab.graphics import renderPDF

            elements.append(Paragraph("Share of Voice Over Time", st_subsection))
            elements.append(Spacer(1, 0.2 * cm))

            # Aggregate snapshots by date: brand mentions + competitor mentions
            date_brand = {}  # date_str -> total brand mentions
            date_comp = {}   # date_str -> {comp_name: mentions}
            date_total = {}  # date_str -> total all mentions

            for snap in comp_snapshots:
                ds = str(snap.get('snapshot_date', ''))
                bm = int(snap.get('total_mentions') or 0)
                date_brand[ds] = date_brand.get(ds, 0) + bm

                breakdown = snap.get('competitor_breakdown') or {}
                if isinstance(breakdown, str):
                    import json as json_mod2
                    try:
                        breakdown = json_mod2.loads(breakdown)
                    except Exception:
                        breakdown = {}
                for ck, cv in breakdown.items():
                    ck_display = comp_display_map.get(ck.lower().strip(), ck.lower().strip())
                    if ds not in date_comp:
                        date_comp[ds] = {}
                    date_comp[ds][ck_display] = date_comp[ds].get(ck_display, 0) + int(cv or 0)

            sorted_dates = sorted(date_brand.keys())
            if len(sorted_dates) >= 2:
                # Calculate SOV % per date
                # Paleta de datos oficial (--cs-series-*): marca en el slot 1
                # y competidores en los siguientes, igual que el panel.
                chart_colors = [
                    colors.HexColor(c) for c in brand_palette.SERIES_EXTENDED[:5]
                ]

                # Build SOV series for each entity
                comp_names_ordered = [cn for cn, _ in sorted_comps[:4]]
                all_series_names = [(project.get('brand_domain') or project['name'])] + comp_names_ordered

                # Create data tuples for LinePlot: list of [(x, y), ...]
                plot_data = []
                for si, series_name in enumerate(all_series_names):
                    series_points = []
                    for di, ds in enumerate(sorted_dates):
                        if si == 0:  # brand
                            mentions = date_brand.get(ds, 0)
                        else:
                            mentions = date_comp.get(ds, {}).get(series_name, 0)
                        # SOV for this date
                        total_day = date_brand.get(ds, 0) + sum(date_comp.get(ds, {}).values())
                        sov_pct = round((mentions / total_day) * 100, 1) if total_day > 0 else 0
                        series_points.append((di, sov_pct))
                    plot_data.append(series_points)

                # Create Drawing
                chart_w = usable_width
                chart_h = 6.5 * cm
                drawing = Drawing(float(chart_w), float(chart_h))

                # Background
                drawing.add(Rect(0, 0, float(chart_w), float(chart_h),
                                 fillColor=colors.HexColor('#FAFAFA'), strokeColor=None))

                lp = LinePlot()
                lp.x = 40
                lp.y = 30
                lp.width = float(chart_w) - 60
                lp.height = float(chart_h) - 55
                lp.data = plot_data

                # Style each line
                for si in range(len(all_series_names)):
                    lp.lines[si].strokeColor = chart_colors[si % len(chart_colors)]
                    lp.lines[si].strokeWidth = 2.5 if si == 0 else 1.5
                    lp.lines[si].symbol = makeMarker('Circle')
                    lp.lines[si].symbol.size = 4 if si == 0 else 3

                # Axes
                lp.xValueAxis.valueMin = 0
                lp.xValueAxis.valueMax = len(sorted_dates) - 1
                lp.xValueAxis.valueSteps = list(range(len(sorted_dates)))
                lp.xValueAxis.labelTextFormat = lambda v: sorted_dates[int(v)][-5:] if 0 <= int(v) < len(sorted_dates) else ''
                lp.xValueAxis.labels.fontSize = 7
                lp.xValueAxis.labels.angle = 0
                lp.xValueAxis.strokeColor = colors.HexColor('#E5E7EB')

                lp.yValueAxis.valueMin = 0
                lp.yValueAxis.valueMax = 100
                lp.yValueAxis.valueStep = 20
                lp.yValueAxis.labelTextFormat = '%d%%'
                lp.yValueAxis.labels.fontSize = 7
                lp.yValueAxis.strokeColor = colors.HexColor('#E5E7EB')
                lp.yValueAxis.gridStrokeColor = colors.HexColor('#F3F4F6')
                lp.yValueAxis.visibleGrid = 1

                drawing.add(lp)

                # Legend text at bottom
                legend_x = 40
                for si, sn in enumerate(all_series_names):
                    color = chart_colors[si % len(chart_colors)]
                    drawing.add(Rect(legend_x, 5, 8, 8, fillColor=color, strokeColor=None))
                    label = sn[:15].upper()
                    drawing.add(String(legend_x + 11, 6, label, fontSize=6,
                                       fillColor=colors.HexColor('#6B7280')))
                    legend_x += len(label) * 4 + 22

                elements.append(drawing)
            else:
                elements.append(Paragraph("Not enough data points for SOV trend chart.", st_no_data))

        elements.append(Spacer(1, 0.5 * cm))

        # Key insight
        if all_entity_mentions > 0 and sorted_comps:
            top_comp_name, top_comp_mentions = sorted_comps[0]
            insight_text = (
                f"In the analyzed {days}-day period, <b>{project.get('brand_domain') or project['name']}</b> "
                f"received <b>{brand_total_mentions}</b> total mentions across all LLMs, "
                f"representing <b>{brand_share}%</b> of all entity mentions. "
                f"The top competitor by mentions was <b>{top_comp_name}</b> "
                f"with <b>{top_comp_mentions}</b> mentions."
            )
            elements.append(Paragraph(insight_text, st_body))

        # =================================================================
        # ✨ PAGE 3b: PERFORMANCE BY CLUSTER (if clusters are configured)
        # =================================================================
        if pdf_defined_clusters:
            elements.append(PageBreak())
            elements.append(Spacer(1, 0.3 * cm))
            elements.append(Paragraph("Performance by Cluster", st_section))
            elements.append(Paragraph(
                f"Topic clusters: {len(pdf_defined_clusters)} configured · "
                f"{'enabled' if pdf_clusters_enabled else 'disabled'}. "
                "Prompts without a cluster are excluded from these metrics.",
                st_body
            ))
            elements.append(Spacer(1, 0.3 * cm))

            cl_header = [
                'Cluster', 'Prompts',
                'Mentions', 'Mention Rate', 'Share of Voice', 'Avg Position'
            ]
            cl_rows = [cl_header]
            # Sort by SoV desc
            for m in sorted(pdf_cluster_metrics, key=lambda x: (-(x['share_of_voice'] or 0), x['cluster'])):
                ap = m['avg_position']
                cl_rows.append([
                    Paragraph(_truncate(m['cluster'], 32), st_body),
                    str(m['prompts']),
                    str(m['brand_mentions']),
                    f"{m['mention_rate']:.1f}%",
                    f"{m['share_of_voice']:.1f}%",
                    f"#{ap:.1f}" if ap is not None else 'N/A',
                ])
            cl_widths = [5.5 * cm, 1.8 * cm, 2 * cm, 2.2 * cm, 2.4 * cm, 2 * cm]
            cl_table = Table(cl_rows, colWidths=cl_widths)
            cl_style = _base_table_style(len(cl_rows))
            cl_style.append(('ALIGN', (0, 1), (0, -1), 'LEFT'))
            # Highlight best-performing cluster (index 1, since it's sorted)
            if len(cl_rows) > 1:
                cl_style.append(('BACKGROUND', (0, 1), (-1, 1), CLR_GREEN_CELL))
            cl_table.setStyle(TableStyle(cl_style))
            elements.append(cl_table)
            elements.append(Spacer(1, 0.3 * cm))

            # Quick insights
            any_with_data = [m for m in pdf_cluster_metrics if m['total_results'] > 0]
            if any_with_data:
                best = max(any_with_data, key=lambda x: (x['share_of_voice'] or 0))
                worst = min(any_with_data, key=lambda x: (x['share_of_voice'] or 0))
                elements.append(Paragraph(
                    f"<b>Best cluster:</b> {best['cluster']} "
                    f"(SoV {best['share_of_voice']:.1f}%, "
                    f"avg position {('#' + format(best['avg_position'], '.1f')) if best['avg_position'] is not None else 'N/A'}). "
                    f"<b>Weakest cluster:</b> {worst['cluster']} "
                    f"(SoV {worst['share_of_voice']:.1f}%).",
                    st_body
                ))
            else:
                elements.append(Paragraph(
                    "No cluster has responses in this period yet. Run an analysis to populate cluster metrics.",
                    st_no_data
                ))

        # =================================================================
        # PAGE 4: PROMPT PERFORMANCE
        # =================================================================
        elements.append(PageBreak())
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph("Prompt Performance", st_section))
        elements.append(Paragraph("Top 20 prompts by visibility", st_body))
        elements.append(Spacer(1, 0.3 * cm))

        if prompt_data:
            # ✨ Add Cluster column only if at least one cluster is configured
            include_cluster_col = bool(pdf_defined_clusters)
            if include_cluster_col:
                pr_header = ["Prompt", "Cluster", "Type", "Brand Mentions", "Visibility %", "Avg Pos"]
            else:
                pr_header = ["Prompt", "Type", "Brand Mentions", "Visibility %", "Avg Pos"]
            pr_rows = [pr_header]
            pr_row_types = []  # 'branded', 'non-branded' for coloring
            for p in prompt_data:
                qt = p.get('query_text', '') or ''
                is_branded = classify_query_branded(qt, brand_keywords_pdf)
                type_label = '🏷️ Branded' if is_branded else '🌿 Generic'
                total_r = int(p.get('total_results') or 0)
                ment = int(p.get('mentions') or 0)
                vis_pct = round((ment / total_r) * 100, 1) if total_r > 0 else 0
                avg_p = round(float(p.get('avg_position') or 0), 1)
                pr_row_types.append('branded' if is_branded else 'generic')
                if include_cluster_col:
                    cluster_val = p.get('topic_cluster') or '—'
                    pr_rows.append([
                        Paragraph(_truncate(qt, 50), st_body),
                        Paragraph(_truncate(cluster_val, 20), st_body),
                        type_label,
                        str(ment),
                        f"{vis_pct}%",
                        f"#{avg_p}" if avg_p > 0 else 'N/A',
                    ])
                else:
                    pr_rows.append([
                        Paragraph(_truncate(qt, 55), st_body),
                        type_label,
                        str(ment),
                        f"{vis_pct}%",
                        f"#{avg_p}" if avg_p > 0 else 'N/A',
                    ])

            if include_cluster_col:
                pr_widths = [4.6 * cm, 2.4 * cm, 2 * cm, 2 * cm, 1.8 * cm, 1.6 * cm]
            else:
                pr_widths = [6 * cm, 2.2 * cm, 2.2 * cm, 2 * cm, 1.6 * cm]
            pr_table = Table(pr_rows, colWidths=pr_widths)
            pr_style = _base_table_style(len(pr_rows))
            pr_style.append(('ALIGN', (0, 1), (0, -1), 'LEFT'))
            # Indices for "Brand Mentions" and "Visibility %" depend on whether
            # the Cluster column is present.
            mentions_col = 3 if include_cluster_col else 2
            visibility_col = 4 if include_cluster_col else 3
            # Color rows: green for mentioned, red for 0 mentions
            for ri, rtype in enumerate(pr_row_types):
                r = ri + 1
                try:
                    ment_val = int(pr_rows[r][mentions_col])
                except (ValueError, TypeError):
                    ment_val = 0
                if ment_val > 0:
                    pr_style.append(('TEXTCOLOR', (mentions_col, r), (mentions_col, r), CLR_DELTA_UP))
                else:
                    pr_style.append(('TEXTCOLOR', (mentions_col, r), (mentions_col, r), CLR_DELTA_DOWN))
                # Visibility color
                vis_str = pr_rows[r][visibility_col]
                try:
                    vis_val = float(str(vis_str).replace('%', '')) if '%' in str(vis_str) else 0
                except (ValueError, TypeError):
                    vis_val = 0
                if vis_val >= 50:
                    pr_style.append(('TEXTCOLOR', (visibility_col, r), (visibility_col, r), CLR_DELTA_UP))
                elif vis_val == 0:
                    pr_style.append(('TEXTCOLOR', (visibility_col, r), (visibility_col, r), CLR_DELTA_DOWN))
            pr_table.setStyle(TableStyle(pr_style))
            elements.append(pr_table)
        else:
            elements.append(Paragraph("No prompt data available for this period.", st_no_data))

        # =================================================================
        # PAGE 5: TOP CITED URLs
        # =================================================================
        elements.append(PageBreak())
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph("Most Cited URLs by LLMs", st_section))
        elements.append(Paragraph("Top 15 URLs by total mentions", st_body))
        elements.append(Spacer(1, 0.3 * cm))

        # Style for clickable URL links
        st_url_link = ParagraphStyle('URLLink', parent=st_body,
                                      textColor=colors.HexColor('#2563EB'), fontSize=8)
        brand_domain = (project.get('brand_domain') or '').lower().strip()

        if urls_data:
            url_header = ["Rank", "URL", "Mentions", "% of Total"]
            url_rows = [url_header]
            url_is_brand = []
            for u in urls_data[:15]:
                raw_url = u.get('url', '') or ''
                display_url = _truncate(raw_url, 55)
                # Make clickable link
                if raw_url.startswith('http'):
                    url_para = Paragraph(f'<a href="{raw_url}" color="#2563EB">{display_url}</a>', st_url_link)
                else:
                    url_para = Paragraph(display_url, st_body)
                is_brand_url = brand_domain and brand_domain in raw_url.lower()
                url_is_brand.append(is_brand_url)
                url_rows.append([
                    str(u.get('rank', '')),
                    url_para,
                    str(u.get('mentions', 0)),
                    f"{round(float(u.get('percentage', 0)), 1)}%",
                ])

            url_widths = [1.2 * cm, 8.5 * cm, 2 * cm, 2.3 * cm]
            url_table = Table(url_rows, colWidths=url_widths)
            url_style = _base_table_style(len(url_rows))
            url_style.append(('ALIGN', (1, 1), (1, -1), 'LEFT'))
            # Highlight brand URLs in green
            for ri, is_brand in enumerate(url_is_brand):
                if is_brand:
                    url_style.append(('BACKGROUND', (0, ri + 1), (-1, ri + 1), CLR_GREEN_CELL))
            url_table.setStyle(TableStyle(url_style))
            elements.append(url_table)
        else:
            elements.append(Paragraph("No cited URL data available for this period.", st_no_data))

        # ── Query Fan-out (solo proyectos con búsqueda web; con 'off' el PDF no cambia) ──
        pdf_fanout = _safe_fanout_metrics(cur, project, start_date.date(), end_date.date(),
                                          enabled_llms_filter or None, pdf_filtered_query_ids)
        if pdf_fanout:
            fanout_tables = fanout_export_tables(pdf_fanout)
            elements.append(Spacer(1, 0.6 * cm))
            elements.append(Paragraph("Query Fan-out", st_section))
            elements.append(Paragraph(
                f"What the models searched on the web to answer your prompts: "
                f"{pdf_fanout['responses_with_search']} of {pdf_fanout['responses']} answers used web search "
                f"since {pdf_fanout['period']['start_date']}.", st_body))
            elements.append(Spacer(1, 0.3 * cm))
            if pdf_fanout['responses']:
                # (tabla, anchos de columna, filas máximas, columna de texto largo que se ajusta)
                fanout_specs = (
                    ('by_llm', [3 * cm, 1.8 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, 2.6 * cm], None, None),
                    ('queries', [0.8 * cm, 7 * cm, 1.6 * cm, 1.8 * cm, 3.4 * cm, 2.2 * cm], 15, 1),
                    ('pages', [3.2 * cm, 8.8 * cm, 1.8 * cm, 3 * cm], 15, 1),
                )
                for key, widths, limit, wrap_col in fanout_specs:
                    header, *body = fanout_tables[key]
                    if not body:
                        continue
                    columns = len(widths)
                    data = [header[:columns]] + [
                        [Paragraph(_truncate(str(v), 90), st_body) if i == wrap_col else str(v)
                         for i, v in enumerate(row[:columns])]
                        for row in body[:limit]
                    ]
                    table = Table(data, colWidths=widths, repeatRows=1)
                    style = _base_table_style(len(data))
                    style.append(('ALIGN', (1, 1), (1, -1), 'LEFT'))
                    table.setStyle(TableStyle(style))
                    elements.append(table)
                    elements.append(Spacer(1, 0.3 * cm))
            else:
                elements.append(Paragraph("No web search data for this period yet.", st_no_data))

        # ── Content Analysis (Top cited pages) ──
        # Solo si el usuario ha lanzado el análisis: es una acción manual que
        # descarga hasta 30 páginas, y si nunca se ha ejecutado no hay nada que
        # contar. Se prioriza a los Quick Wins, que son la parte accionable:
        # páginas que ya citan a competidores pero todavía no a la marca.
        pdf_content = _safe_content_overview(project_id, days)
        pdf_content_results = [
            r for r in (pdf_content.get('results') or []) if r.get('analysis')
        ]

        if pdf_content_results:
            elements.append(Spacer(1, 0.6 * cm))
            elements.append(Paragraph("Content Analysis", st_section))
            csum = pdf_content.get('summary') or {}
            elements.append(Paragraph(
                f"Brand presence inside the content of the top "
                f"{pdf_content.get('top_limit', 30)} most cited pages "
                f"({csum.get('analyzed', 0)} analyzed).",
                st_body
            ))

            presence_rows = [["Brand presence", "Pages"]]
            for key in ('mentioned', 'quick_win', 'no_mentions', 'competitor_page'):
                presence_rows.append([
                    _OPPORTUNITY_LABELS[key],
                    str(csum.get({'mentioned': 'mentioned', 'quick_win': 'quick_wins',
                                  'no_mentions': 'no_mentions',
                                  'competitor_page': 'competitor_pages'}[key], 0))
                ])
            presence_table = Table(presence_rows, colWidths=[usable_width * 0.7, usable_width * 0.3])
            presence_table.setStyle(TableStyle(_base_table_style(len(presence_rows))))
            elements.append(presence_table)

            quick_wins = [r for r in pdf_content_results
                          if r['analysis'].get('opportunity') == 'quick_win']
            if quick_wins:
                elements.append(Spacer(1, 0.4 * cm))
                elements.append(Paragraph(
                    "Quick Wins — pages that already cite competitors but not your brand",
                    st_subsection
                ))
                qw_rows = [["#", "URL", "Competitors cited"]]
                for r in quick_wins[:15]:
                    comps = [c for c in (r['analysis'].get('competitors_found') or [])
                             if isinstance(c, dict) and c.get('mentioned')]
                    qw_rows.append([
                        str(r.get('rank') or len(qw_rows)),
                        _truncate(r.get('url') or '', 78),
                        _truncate(', '.join(
                            (c.get('name') or c.get('domain') or '') for c in comps
                        ) or '—', 34),
                    ])
                qw_table = Table(qw_rows, colWidths=[1.2 * cm, 9.3 * cm, 3.5 * cm])
                qw_style = _base_table_style(len(qw_rows))
                qw_style.append(('ALIGN', (1, 1), (1, -1), 'LEFT'))
                qw_style.append(('ALIGN', (2, 1), (2, -1), 'LEFT'))
                qw_table.setStyle(TableStyle(qw_style))
                elements.append(qw_table)

            mentioned_pages = [r for r in pdf_content_results
                               if r['analysis'].get('opportunity') == 'mentioned']
            if mentioned_pages:
                elements.append(Spacer(1, 0.4 * cm))
                elements.append(Paragraph(
                    "Pages that already mention your brand", st_subsection
                ))
                mp_rows = [["#", "URL", "Mentions", "Linked"]]
                for r in mentioned_pages[:15]:
                    a = r['analysis']
                    mp_rows.append([
                        str(r.get('rank') or len(mp_rows)),
                        _truncate(r.get('url') or '', 74),
                        str(a.get('brand_mention_count') or 0),
                        "Yes" if a.get('brand_linked') else "No",
                    ])
                mp_table = Table(mp_rows, colWidths=[1.2 * cm, 8.6 * cm, 2 * cm, 2.2 * cm])
                mp_style = _base_table_style(len(mp_rows))
                mp_style.append(('ALIGN', (1, 1), (1, -1), 'LEFT'))
                mp_table.setStyle(TableStyle(mp_style))
                elements.append(mp_table)

        # ── Build PDF ──
        doc.build(elements, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)
        output.seek(0)

        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', project['name'])
        filename = f"llm-monitoring-{safe_name}-{datetime.now().strftime('%Y%m%d')}.pdf"

        logger.info(f"PDF exported successfully for project {project_id}")

        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Error exporting PDF for project {project_id}: {e}", exc_info=True)
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
