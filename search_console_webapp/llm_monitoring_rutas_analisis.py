"""Rutas de análisis de LLM Monitoring: primer análisis (/run-initial-analysis), métricas,
ranking de URLs, fan-out, análisis de contenido de URLs, comparación entre LLMs, listado de
queries con su rendimiento, share of voice histórico y respuestas para inspección manual.

Sacadas tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros gigantes).
Registran sus rutas en el blueprint de llm_monitoring_base al importarse;
llm_monitoring_routes importa este módulo y vuelve a exponer sus nombres. Para
parchear algo que usen estas rutas en un test (threading, servicios...), hazlo en este
módulo.
"""

import logging
from auth import get_current_user, login_required
from database import get_db_connection
from datetime import datetime, timedelta
from flask import jsonify, request
from services.llm_monitoring import pseudo_snapshots as pseudo_snapshots_lib, url_content_analyzer
from services.llm_monitoring.fanout_stats import collect_fanout_metrics, response_search_detail
from services.llm_monitoring_service import MultiLLMMonitoringService
from services.llm_monitoring_stats import LLMMonitoringStatsService
from services.llm_providers.web_search import is_search_enabled
from urllib.parse import urlparse
import brand_palette
import json
import threading
from llm_monitoring_base import (
    _clear_initial_analysis_running,
    _mark_initial_analysis_running,
    llm_monitoring_bp,
    validate_project_ownership,
)
from llm_monitoring_informes import (
    _calculate_trend,
    _compute_branded_metrics,
    _extract_source_host,
    _narrow_llms,
    _normalize_days_param,
    _parse_report_filters,
    _resolve_filtered_query_ids,
    classify_query_branded,
    collect_prompt_metrics,
    empty_prompt_metrics,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENDPOINTS: ANÁLISIS
# ============================================================================

# REMOVED: Manual analysis endpoint
#
# Razón: El sistema ahora funciona EXCLUSIVAMENTE con cron diario (4:00 AM).
# 
# El análisis manual fue eliminado porque:
# - Toma 15-30 minutos (timeout en navegador)
# - Prioriza completitud sobre velocidad
# - Requiere sistema robusto de reintentos
# - El cron diario garantiza 100% de completitud
#
# El endpoint /projects/<int:project_id>/analyze ya NO está disponible.
# Solo se permite /projects/<id>/run-initial-analysis (una vez) para evitar
# que un proyecto nuevo quede vacío hasta el siguiente cron diario.
#
# Para ejecutar análisis manual (admin/debugging):
# - Usar: python3 fix_openai_incomplete_analysis.py
# - O ejecutar manualmente: python3 daily_llm_monitoring_cron.py


@llm_monitoring_bp.route('/projects/<int:project_id>/run-initial-analysis', methods=['POST'])
@login_required
@validate_project_ownership
def run_initial_analysis(project_id):
    """
    Ejecuta el PRIMER análisis de un proyecto en background.
    Solo disponible para proyectos sin análisis previo.
    """
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required. Please sign in.'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                p.id,
                p.name,
                p.is_active,
                p.last_analysis_date,
                p.enabled_llms,
                p.queries_per_llm,
                (
                    SELECT COUNT(*)
                    FROM llm_monitoring_queries q
                    WHERE q.project_id = p.id AND q.is_active = TRUE
                ) as total_queries
            FROM llm_monitoring_projects p
            WHERE p.id = %s
        """, (project_id,))
        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        if not project.get('is_active'):
            return jsonify({
                'error': 'project_inactive',
                'message': 'Activate the project before running the first analysis'
            }), 400

        # "Solo primera vez": si ya hay snapshot o fecha de análisis, no permitir.
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM llm_monitoring_snapshots
            WHERE project_id = %s
        """, (project_id,))
        row = cur.fetchone()
        has_snapshots = int(row['count']) > 0 if row else False

        if project.get('last_analysis_date') or has_snapshots:
            return jsonify({
                'error': 'initial_analysis_already_completed',
                'message': 'This project has already completed its first analysis'
            }), 409

        configured_queries = int(project.get('total_queries') or 0)
        if configured_queries <= 0:
            return jsonify({
                'error': 'no_active_queries',
                'message': 'Add at least one active prompt before running the first analysis'
            }), 400

        # Evitar doble click / doble thread del mismo proyecto.
        if not _mark_initial_analysis_running(project_id):
            return jsonify({
                'error': 'initial_analysis_in_progress',
                'message': 'The first analysis is already in progress for this project'
            }), 409

        enabled_llms = project.get('enabled_llms') or []
        llm_count = max(1, len(enabled_llms))
        estimated_units = llm_count * configured_queries
        estimated_min_minutes = max(2, min(12, int(round(estimated_units / 24.0))))
        estimated_max_minutes = max(5, min(35, int(round(estimated_units / 8.0))))

        project_name = project.get('name') or f'Project #{project_id}'

        def run_first_analysis_in_background():
            try:
                logger.info(
                    f"🚀 Initial analysis started for project {project_id} ({project_name}) by user {user.get('id')}"
                )
                service = MultiLLMMonitoringService(api_keys=None)
                result = service.analyze_project(project_id=project_id, max_workers=8)

                if result.get('success'):
                    logger.info(
                        f"✅ Initial analysis finished for project {project_id}: "
                        f"{result.get('total_queries_executed', 0)} queries"
                    )
                else:
                    logger.warning(
                        f"⚠️ Initial analysis ended with warning for project {project_id}: "
                        f"{result.get('error', 'unknown_error')}"
                    )
            except Exception as e:
                logger.error(f"❌ Error running initial analysis for project {project_id}: {e}", exc_info=True)
            finally:
                _clear_initial_analysis_running(project_id)

        thread = threading.Thread(target=run_first_analysis_in_background, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'project_id': project_id,
            'message': 'Initial analysis started in background',
            'estimated_minutes_min': estimated_min_minutes,
            'estimated_minutes_max': estimated_max_minutes
        }), 202

    except Exception as e:
        # Limpieza defensiva si algo falló antes de lanzar correctamente.
        _clear_initial_analysis_running(project_id)
        logger.error(f"Error triggering initial analysis for project {project_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to start initial analysis. Please try again.'}), 500
    finally:
        if cur:
            cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/metrics', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_metrics(project_id):
    """
    Obtiene métricas detalladas de un proyecto
    
    Query params opcionales:
        start_date: Fecha inicio (YYYY-MM-DD, default: último mes)
        end_date: Fecha fin (YYYY-MM-DD, default: hoy)
        llm_provider: Filtrar por LLM (openai, anthropic, google, perplexity)
    
    Returns:
        JSON con snapshots y métricas agregadas
    """
    # Parámetros de fecha
    raw_days = request.args.get('days')
    days = _normalize_days_param(raw_days, default=30)
    
    if raw_days is not None and raw_days != '':
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    else:
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        
    llm_provider = request.args.get('llm_provider')
    report_filters = _parse_report_filters(request.args)

    # ── Previous period dates (for period-over-period comparison) ──
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
    prev_end = start_date  # previous period ends where current starts
    prev_start = (start_date_obj - timedelta(days=days)).strftime('%Y-%m-%d')

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT enabled_llms, brand_keywords
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Project not found'}), 404
        enabled_llms_filter = _narrow_llms(project_row.get('enabled_llms') or [], report_filters)
        brand_keywords = project_row.get('brand_keywords') or []

        # Filtro global: con subconjunto de prompts activo (set/clusters/
        # branded) los snapshots preagregados no sirven → pseudo-snapshots.
        filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=start_date, end_date=end_date)

        if filtered_query_ids is not None:
            snapshots = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, filtered_query_ids,
                start_date, end_date,
                enabled_llms=enabled_llms_filter,
                llm_provider=llm_provider,
            )
            # Orden idéntico al camino legacy (fecha DESC, provider ASC)
            snapshots.sort(key=lambda s: s['llm_provider'])
            snapshots.sort(key=lambda s: s['snapshot_date'], reverse=True)
        else:
            # Query base
            query = """
                SELECT
                    s.*,
                    p.brand_name,
                    p.competitors
                FROM llm_monitoring_snapshots s
                JOIN llm_monitoring_projects p ON s.project_id = p.id
                WHERE s.project_id = %s
                AND s.snapshot_date >= %s
                AND s.snapshot_date <= %s
            """

            params = [project_id, start_date, end_date]

            # Filtro opcional por LLM
            if llm_provider:
                query += " AND s.llm_provider = %s"
                params.append(llm_provider)
            elif enabled_llms_filter:
                query += " AND s.llm_provider = ANY(%s)"
                params.append(enabled_llms_filter)

            query += " ORDER BY s.snapshot_date DESC, s.llm_provider"

            cur.execute(query, params)
            snapshots = cur.fetchall()
        
        # Formatear snapshots
        snapshots_list = []
        for s in snapshots:
            total_mentions = (s.get('total_mentions') or 0)
            pos_mentions = (s.get('positive_mentions') or 0)
            neu_mentions = (s.get('neutral_mentions') or 0)
            neg_mentions = (s.get('negative_mentions') or 0)

            positive_pct = (pos_mentions / total_mentions * 100) if total_mentions else 0
            neutral_pct = (neu_mentions / total_mentions * 100) if total_mentions else 0
            negative_pct = (neg_mentions / total_mentions * 100) if total_mentions else 0

            snapshots_list.append({
                'id': s['id'],
                'llm_provider': s['llm_provider'],
                'snapshot_date': s['snapshot_date'].isoformat() if s['snapshot_date'] else None,
                'mention_rate': float(s['mention_rate']) if s['mention_rate'] is not None else 0,
                'avg_position': float(s['avg_position']) if s['avg_position'] is not None else None,
                'top3_count': s.get('appeared_in_top3'),
                'top5_count': s.get('appeared_in_top5'),
                'top10_count': s.get('appeared_in_top10'),
                'share_of_voice': float(s['share_of_voice']) if s['share_of_voice'] is not None else 0,
                # ✨ NUEVO: Share of Voice ponderado por posición
                'weighted_share_of_voice': float(s.get('weighted_share_of_voice') or s.get('share_of_voice') or 0),
                # ➕ Exponer datos de competidores para el frontend (gráfico SOV)
                'total_competitor_mentions': int(s.get('total_competitor_mentions') or 0),
                'competitor_breakdown': s.get('competitor_breakdown') or {},
                'weighted_competitor_breakdown': s.get('weighted_competitor_breakdown') or {},
                'sentiment': {
                    'positive': float(positive_pct),
                    'neutral': float(neutral_pct),
                    'negative': float(negative_pct)
                },
                # Contadores crudos para la gráfica "Sentiment Over Time"
                # (barras apiladas por día: hay que sumar entre LLMs, y eso
                # con porcentajes no se puede)
                'sentiment_counts': {
                    'positive': int(pos_mentions),
                    'neutral': int(neu_mentions),
                    'negative': int(neg_mentions)
                },
                'total_queries': s.get('total_queries') or 0,
                'total_cost': float(s['total_cost_usd']) if s['total_cost_usd'] is not None else 0
            })
        
        # Calcular métricas agregadas
        total_cost = sum(s['total_cost'] for s in snapshots_list)
        total_queries = sum(s['total_queries'] for s in snapshots_list)
        
        # Promedio de mention_rate por LLM
        metrics_by_llm = {}
        for llm in ['openai', 'anthropic', 'google', 'perplexity']:
            llm_snapshots = [s for s in snapshots_list if s['llm_provider'] == llm]
            if llm_snapshots:
                metrics_by_llm[llm] = {
                    'avg_mention_rate': sum(s['mention_rate'] for s in llm_snapshots) / len(llm_snapshots),
                    'avg_position': sum(s['avg_position'] for s in llm_snapshots if s['avg_position']) / len([s for s in llm_snapshots if s['avg_position']]) if any(s['avg_position'] for s in llm_snapshots) else None,
                    'avg_share_of_voice': sum(s['share_of_voice'] for s in llm_snapshots) / len(llm_snapshots),
                    'total_snapshots': len(llm_snapshots)
                }
        
        # ── Branded vs Non-Branded breakdown ──
        branded_data = {'branded_metrics': None, 'non_branded_metrics': None}
        try:
            if brand_keywords:
                bq = """
                    SELECT r.llm_provider, q.query_text, r.brand_mentioned,
                           r.position_in_list, r.competitors_mentioned
                    FROM llm_monitoring_results r
                    JOIN llm_monitoring_queries q ON r.query_id = q.id
                    WHERE r.project_id = %s
                      AND r.analysis_date >= %s AND r.analysis_date <= %s
                """
                bparams = [project_id, start_date, end_date]
                if filtered_query_ids is not None:
                    bq += " AND r.query_id = ANY(%s)"
                    bparams.append(filtered_query_ids)
                if llm_provider:
                    bq += " AND r.llm_provider = %s"
                    bparams.append(llm_provider)
                elif enabled_llms_filter:
                    bq += " AND r.llm_provider = ANY(%s)"
                    bparams.append(enabled_llms_filter)
                cur.execute(bq, bparams)
                branded_data = _compute_branded_metrics(cur.fetchall(), brand_keywords)
        except Exception as be:
            logger.warning(f"Could not compute branded/non-branded metrics: {be}")

        # ── Previous period: metrics_by_llm ──
        previous_metrics_by_llm = {}
        try:
            if filtered_query_ids is not None:
                # Mismo cálculo pero desde pseudo-snapshots del período anterior.
                # build_pseudo_snapshots es inclusivo en end_date y el legacy usa
                # "< prev_end": se resta un día para no solapar el día frontera.
                prev_end_inclusive = (
                    start_date_obj - timedelta(days=1)
                ).strftime('%Y-%m-%d')
                prev_pseudo = pseudo_snapshots_lib.build_pseudo_snapshots(
                    cur, project_id, filtered_query_ids,
                    prev_start, prev_end_inclusive,
                    enabled_llms=enabled_llms_filter,
                    llm_provider=llm_provider,
                )
                prev_rates = {}
                for s in prev_pseudo:
                    prev_rates.setdefault(s['llm_provider'], []).append(s['mention_rate'])
                for prov, rates in prev_rates.items():
                    previous_metrics_by_llm[prov] = {
                        'avg_mention_rate': sum(rates) / len(rates)
                    }
            else:
                prev_snap_query = """
                    SELECT llm_provider, AVG(mention_rate) as avg_mention_rate
                    FROM llm_monitoring_snapshots
                    WHERE project_id = %s
                      AND snapshot_date >= %s AND snapshot_date < %s
                """
                prev_snap_params = [project_id, prev_start, prev_end]
                if llm_provider:
                    prev_snap_query += " AND llm_provider = %s"
                    prev_snap_params.append(llm_provider)
                elif enabled_llms_filter:
                    prev_snap_query += " AND llm_provider = ANY(%s)"
                    prev_snap_params.append(enabled_llms_filter)
                prev_snap_query += " GROUP BY llm_provider"
                cur.execute(prev_snap_query, prev_snap_params)
                for row in cur.fetchall():
                    previous_metrics_by_llm[row['llm_provider']] = {
                        'avg_mention_rate': float(row['avg_mention_rate']) if row['avg_mention_rate'] is not None else 0
                    }
        except Exception as prev_err:
            logger.warning(f"Could not compute previous metrics_by_llm: {prev_err}")

        # ── Previous period: branded / non-branded trends ──
        branded_trends = {}
        non_branded_trends = {}
        try:
            if brand_keywords:
                prev_bq = """
                    SELECT r.llm_provider, q.query_text, r.brand_mentioned,
                           r.position_in_list, r.competitors_mentioned
                    FROM llm_monitoring_results r
                    JOIN llm_monitoring_queries q ON r.query_id = q.id
                    WHERE r.project_id = %s
                      AND r.analysis_date >= %s AND r.analysis_date < %s
                """
                prev_bparams = [project_id, prev_start, prev_end]
                if filtered_query_ids is not None:
                    prev_bq += " AND r.query_id = ANY(%s)"
                    prev_bparams.append(filtered_query_ids)
                if llm_provider:
                    prev_bq += " AND r.llm_provider = %s"
                    prev_bparams.append(llm_provider)
                elif enabled_llms_filter:
                    prev_bq += " AND r.llm_provider = ANY(%s)"
                    prev_bparams.append(enabled_llms_filter)
                cur.execute(prev_bq, prev_bparams)
                prev_branded_data = _compute_branded_metrics(cur.fetchall(), brand_keywords)

                current_branded = branded_data.get('branded_metrics') or {}
                current_non_branded = branded_data.get('non_branded_metrics') or {}
                prev_branded = prev_branded_data.get('branded_metrics') or {}
                prev_non_branded = prev_branded_data.get('non_branded_metrics') or {}

                has_prev_branded = (prev_branded.get('total_results', 0) > 0)
                has_prev_non_branded = (prev_non_branded.get('total_results', 0) > 0)

                branded_trends = {
                    'mention_rate': _calculate_trend(
                        current_branded.get('mention_rate', 0),
                        prev_branded.get('mention_rate', 0),
                        has_prev_branded
                    ),
                    'share_of_voice': _calculate_trend(
                        current_branded.get('share_of_voice', 0),
                        prev_branded.get('share_of_voice', 0),
                        has_prev_branded
                    )
                }
                non_branded_trends = {
                    'mention_rate': _calculate_trend(
                        current_non_branded.get('mention_rate', 0),
                        prev_non_branded.get('mention_rate', 0),
                        has_prev_non_branded
                    ),
                    'share_of_voice': _calculate_trend(
                        current_non_branded.get('share_of_voice', 0),
                        prev_non_branded.get('share_of_voice', 0),
                        has_prev_non_branded
                    )
                }
        except Exception as bt_err:
            logger.warning(f"Could not compute branded trends: {bt_err}")

        return jsonify({
            'success': True,
            'project_id': project_id,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'snapshots': snapshots_list,
            'aggregated': {
                'total_snapshots': len(snapshots_list),
                'total_cost_usd': total_cost,
                'total_queries_analyzed': total_queries,
                'metrics_by_llm': metrics_by_llm
            },
            'branded_metrics': branded_data.get('branded_metrics'),
            'non_branded_metrics': branded_data.get('non_branded_metrics'),
            'branded_by_llm': branded_data.get('branded_by_llm', {}),
            'non_branded_by_llm': branded_data.get('non_branded_by_llm', {}),
            'branded_trends': branded_trends,
            'non_branded_trends': non_branded_trends,
            'previous_metrics_by_llm': previous_metrics_by_llm
        }), 200

    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/urls-ranking', methods=['GET'])
@login_required
@validate_project_ownership
def get_urls_ranking(project_id):
    """
    Obtiene el ranking de URLs más mencionadas por los LLMs
    
    Query params opcionales:
        days: Número de días (default: 30)
        llm_provider: Filtrar por LLM específico ('openai', 'anthropic', 'google', 'perplexity')
        limit: Número máximo de URLs (default: 50). Usa 0 para "sin límite"
    
    Returns:
        JSON con ranking de URLs citadas por los LLMs
    """
    days = _normalize_days_param(request.args.get('days'), default=30)
    llm_provider = request.args.get('llm_provider')
    report_filters = _parse_report_filters(request.args)
    raw_limit = request.args.get('limit')
    limit = 50
    if raw_limit is not None and str(raw_limit).strip() != '':
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return jsonify({'error': 'Limit must be an integer'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()

        enabled_llms_filter = (project or {}).get('enabled_llms') or []
        if llm_provider and enabled_llms_filter and llm_provider not in enabled_llms_filter:
            return jsonify({
                'error': 'llm_provider no habilitado para este proyecto'
            }), 400

        enabled_llms_filter = _narrow_llms(enabled_llms_filter, report_filters)
        if not llm_provider and not enabled_llms_filter:
            enabled_llms_filter = None

        filtered_query_ids = _resolve_filtered_query_ids(
            cur, project_id, report_filters,
            start_date=datetime.now().date() - timedelta(days=days),
            end_date=datetime.now().date()
        )

        urls_ranking = LLMMonitoringStatsService.get_project_urls_ranking(
            project_id=project_id,
            days=days,
            llm_provider=llm_provider,
            enabled_llms=enabled_llms_filter,
            limit=limit,
            query_ids=filtered_query_ids
        )
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'filters': {
                'days': days,
                'llm_provider': llm_provider or 'all',
                'limit': limit
            },
            'urls': urls_ranking,
            'total_urls': len(urls_ranking)
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo ranking de URLs: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


@llm_monitoring_bp.route('/projects/<int:project_id>/fanout', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_fanout(project_id):
    """
    Query fan-out del proyecto (P7): sub-consultas que lanzan los modelos al buscar en la
    web, páginas que leen y presencia de la marca. Solo para proyectos con
    search_mode='auto'; con 'off' devuelve {"enabled": false} y el panel no pinta nada.

    Query params: days (default 30) + filtros globales del informe.
    """
    days = _normalize_days_param(request.args.get('days'), default=30)
    report_filters = _parse_report_filters(request.args)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, enabled_llms, brand_domain, competitor_domains, selected_competitors,
                   search_mode, search_enabled_at
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        if not is_search_enabled(project.get('search_mode')):
            return jsonify({'success': True, 'enabled': False}), 200

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        metrics = collect_fanout_metrics(
            cur, project,
            start_date=start_date, end_date=end_date,
            enabled_llms=_narrow_llms(project.get('enabled_llms') or [], report_filters),
            query_ids=_resolve_filtered_query_ids(cur, project_id, report_filters,
                                                  start_date=start_date, end_date=end_date),
        )
        return jsonify({'success': True, 'days': days, **metrics}), 200
    except Exception as e:
        logger.error(f"Error obteniendo fan-out del proyecto {project_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


@llm_monitoring_bp.route('/projects/<int:project_id>/url-content-analysis', methods=['POST'])
@login_required
@validate_project_ownership
def start_url_content_analysis(project_id):
    """
    Lanza en background el análisis de contenido del Top 30 de URLs citadas
    (Fase 1 determinista: menciones/enlaces de marca y competidores, sin LLM).

    Body JSON opcional:
        days: rango del ranking (default: 30)
        force: re-analizar aunque haya caché vigente (default: false)

    Returns:
        202 si el análisis arrancó, 409 si ya hay uno en curso
    """
    data = request.get_json(silent=True) or {}
    days = _normalize_days_param(data.get('days'), default=30)
    force = bool(data.get('force', False))

    if not url_content_analyzer.try_begin_analysis(project_id):
        return jsonify({
            'error': 'url_analysis_in_progress',
            'message': 'A content analysis is already running for this project'
        }), 409

    def run_url_analysis_in_background():
        try:
            result = url_content_analyzer.run_analysis_for_project(
                project_id=project_id, days=days, force=force
            )
            if result.get('success'):
                logger.info(
                    f"✅ URL content analysis finished for project {project_id}: "
                    f"{result.get('processed', 0)} processed, {result.get('skipped', 0)} cached"
                )
            else:
                logger.warning(
                    f"⚠️ URL content analysis failed for project {project_id}: "
                    f"{result.get('error', 'unknown_error')}"
                )
        except Exception as e:
            logger.error(f"❌ Error in URL content analysis for project {project_id}: {e}", exc_info=True)

    try:
        thread = threading.Thread(target=run_url_analysis_in_background, daemon=True)
        thread.start()
    except Exception as e:
        # Si el thread no llegó a arrancar, liberar el guard para no bloquear reintentos
        url_content_analyzer.release_analysis_guard(project_id)
        logger.error(f"Error starting URL content analysis for project {project_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to start analysis. Please try again.'}), 500

    return jsonify({
        'success': True,
        'project_id': project_id,
        'message': 'URL content analysis started in background',
        'days': days,
        'force': force
    }), 202


@llm_monitoring_bp.route('/projects/<int:project_id>/url-content-analysis', methods=['GET'])
@login_required
@validate_project_ownership
def get_url_content_analysis(project_id):
    """
    Estado y resultados del análisis de contenido para el Top 30 actual.

    Query params opcionales:
        days: rango del ranking (default: 30, debe coincidir con la tabla)

    Returns:
        JSON con progress (running/done/total), summary y results por URL
    """
    days = _normalize_days_param(request.args.get('days'), default=30)

    try:
        overview = url_content_analyzer.get_analysis_overview(project_id, days=days)
        if not overview.get('success'):
            return jsonify({'error': 'Project not found'}), 404
        return jsonify(overview), 200
    except Exception as e:
        logger.error(f"Error obteniendo análisis de contenido de URLs: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500


@llm_monitoring_bp.route('/projects/<int:project_id>/comparison', methods=['GET'])
@login_required
@validate_project_ownership
def get_llm_comparison(project_id):
    """
    Comparativa entre LLMs para un proyecto (usa vista llm_visibility_comparison)
    
    Query params opcionales:
        metric: 'weighted' o 'normal' (default: 'weighted')
    
    Returns:
        JSON con comparativa de métricas entre LLMs
    """
    # ✨ NUEVO: Parámetro de métrica para Share of Voice
    metric_type = request.args.get('metric', 'weighted')

    # ✨ NUEVO: Parámetro de días
    days = _normalize_days_param(request.args.get('days'), default=30)
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    report_filters = _parse_report_filters(request.args)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT enabled_llms, brand_domain
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Project not found'}), 404
        enabled_llms_filter = _narrow_llms(project_row.get('enabled_llms') or [], report_filters)
        brand_domain_raw = project_row.get('brand_domain') or ''

        def _normalize_domain(value):
            raw_value = str(value or '').strip().lower()
            if not raw_value:
                return ''
            if not raw_value.startswith(('http://', 'https://')):
                raw_value = f"https://{raw_value}"
            try:
                parsed = urlparse(raw_value)
            except Exception:
                return ''
            host = (parsed.netloc or parsed.path or '').split('/')[0].split(':')[0].strip().lower()
            if host.startswith('www.'):
                host = host[4:]
            return host

        normalized_brand_domain = _normalize_domain(brand_domain_raw)

        def _to_date_key(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.date().isoformat()
            if hasattr(value, 'isoformat'):
                return value.isoformat()
            return str(value)
        
        # Filtro global: con subconjunto de prompts activo se calculan
        # pseudo-snapshots desde results (los snapshots agregan todos los prompts)
        filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=datetime.now().date() - timedelta(days=days), end_date=datetime.now().date())

        if filtered_query_ids is not None:
            rows = pseudo_snapshots_lib.build_pseudo_snapshots(
                cur, project_id, filtered_query_ids,
                start_date, None,
                enabled_llms=enabled_llms_filter,
            )
            rows.sort(key=lambda s: s['llm_provider'])
            rows.sort(key=lambda s: s['snapshot_date'], reverse=True)
        else:
            # Traer filas por LLM directamente desde snapshots
            # ✨ NUEVO: Incluir weighted_share_of_voice
            comparison_query = """
                SELECT
                    llm_provider,
                    snapshot_date,
                    mention_rate,
                    total_mentions,
                    avg_position,
                    share_of_voice,
                    weighted_share_of_voice,
                    avg_sentiment_score,
                    positive_mentions,
                    neutral_mentions,
                    negative_mentions,
                    total_queries
                FROM llm_monitoring_snapshots
                WHERE project_id = %s
                AND snapshot_date >= %s
            """
            comparison_params = [project_id, start_date]
            if enabled_llms_filter:
                comparison_query += " AND llm_provider = ANY(%s)"
                comparison_params.append(enabled_llms_filter)
            comparison_query += " ORDER BY snapshot_date DESC, llm_provider"
            cur.execute(comparison_query, comparison_params)

            rows = cur.fetchall()

        # Recalcular position_source con criterio estricto de dominio/subdominio para enlaces.
        position_source_rows_query = """
            SELECT
                llm_provider,
                analysis_date,
                brand_mentioned,
                mention_contexts,
                sources
            FROM llm_monitoring_results
            WHERE project_id = %s
            AND analysis_date >= %s
        """
        position_source_rows_params = [project_id, start_date]
        if filtered_query_ids is not None:
            position_source_rows_query += " AND query_id = ANY(%s)"
            position_source_rows_params.append(filtered_query_ids)
        if enabled_llms_filter:
            position_source_rows_query += " AND llm_provider = ANY(%s)"
            position_source_rows_params.append(enabled_llms_filter)
        cur.execute(position_source_rows_query, position_source_rows_params)

        position_rows = cur.fetchall()

        # Crear lookup dict para position_source por (llm_provider, date)
        position_source_map = {}
        for row in position_rows:
            key = (row['llm_provider'], _to_date_key(row.get('analysis_date')))
            bucket = position_source_map.setdefault(key, {'text_count': 0, 'link_count': 0, 'both_count': 0})

            raw_contexts = row.get('mention_contexts') or []
            if isinstance(raw_contexts, str):
                try:
                    raw_contexts = json.loads(raw_contexts)
                except Exception:
                    raw_contexts = []
            if not isinstance(raw_contexts, list):
                raw_contexts = []

            raw_sources = row.get('sources') or []
            if isinstance(raw_sources, str):
                try:
                    raw_sources = json.loads(raw_sources)
                except Exception:
                    raw_sources = []
            if not isinstance(raw_sources, list):
                raw_sources = []

            has_text_context = False
            has_link_context = False
            for context in raw_contexts:
                ctx = str(context or '').strip()
                if not ctx:
                    continue
                if ctx.startswith('🔗'):
                    has_link_context = True
                else:
                    has_text_context = True

            brand_in_link = False
            if normalized_brand_domain:
                for source in raw_sources:
                    if not isinstance(source, dict):
                        continue
                    source_host = _extract_source_host(source.get('url'))
                    if source_host and (
                        source_host == normalized_brand_domain or
                        source_host.endswith(f".{normalized_brand_domain}")
                    ):
                        brand_in_link = True
                        break

            # Fallback defensivo para registros antiguos sin contextos.
            brand_mentioned = bool(row.get('brand_mentioned'))
            if has_text_context:
                brand_in_text = True
            elif brand_in_link:
                brand_in_text = False
            elif brand_mentioned and not has_link_context:
                brand_in_text = True
            else:
                brand_in_text = False

            if not brand_in_text and not brand_in_link:
                continue

            if brand_in_text and brand_in_link:
                bucket['both_count'] += 1
            elif brand_in_text:
                bucket['text_count'] += 1
            else:
                bucket['link_count'] += 1

        for key, counts in position_source_map.items():
            text_count = counts['text_count']
            link_count = counts['link_count']
            both_count = counts['both_count']
            
            # Determinar badge predominante
            if both_count > 0 or (text_count > 0 and link_count > 0):
                dominant_source = 'both'
            elif text_count >= link_count:
                dominant_source = 'text'
            else:
                dominant_source = 'link'
            
            position_source_map[key] = {
                'dominant': dominant_source,
                'text_count': text_count,
                'link_count': link_count,
                'both_count': both_count
            }
        
        # Formatear datos
        comparison_list = []
        for c in rows:
            # 🔧 FIX: Calcular sentiment basándose en los contadores, igual que en el KPI
            positive_mentions = c.get('positive_mentions') or 0
            neutral_mentions = c.get('neutral_mentions') or 0
            negative_mentions = c.get('negative_mentions') or 0
            total_queries_row = c.get('total_queries') or 0
            
            positive_pct = (positive_mentions / total_queries_row * 100) if total_queries_row else 0
            neutral_pct = (neutral_mentions / total_queries_row * 100) if total_queries_row else 0
            negative_pct = (negative_mentions / total_queries_row * 100) if total_queries_row else 0
            
            # ✨ NUEVO: Seleccionar Share of Voice según métrica
            if metric_type == 'weighted':
                sov = c.get('weighted_share_of_voice') or c.get('share_of_voice') or 0
            else:
                sov = c.get('share_of_voice') or 0
            
            # ✨ NUEVO: Obtener position_source info para este snapshot
            snapshot_key = (c['llm_provider'], _to_date_key(c.get('snapshot_date')))
            position_source_info = position_source_map.get(snapshot_key, {
                'dominant': None,
                'text_count': 0,
                'link_count': 0,
                'both_count': 0
            })
            
            comparison_list.append({
                'llm_provider': c['llm_provider'],
                'snapshot_date': c['snapshot_date'].isoformat() if c['snapshot_date'] else None,
                'mention_rate': float(c['mention_rate']) if c['mention_rate'] is not None else 0,
                'total_mentions': c.get('total_mentions') or 0,  # 🔧 FIX: Campo faltante para Grid.js
                'avg_position': float(c['avg_position']) if c['avg_position'] is not None else None,
                'position_source': position_source_info['dominant'],  # ✨ NUEVO: 'text', 'link', 'both'
                'position_source_details': position_source_info,  # ✨ NUEVO: Detalles para tooltip
                'share_of_voice': float(sov) if sov is not None else 0,  # ✨ MODIFICADO: Usar métrica seleccionada
                'sentiment_score': float(c['avg_sentiment_score']) if c['avg_sentiment_score'] is not None else 0,
                'sentiment': {
                    'positive': float(positive_pct),
                    'neutral': float(neutral_pct),
                    'negative': float(negative_pct)
                },
                'total_queries': total_queries_row
            })
        
        # Agrupar por fecha para comparación lado a lado
        by_date = {}
        for c in comparison_list:
            date = c['snapshot_date']
            if date not in by_date:
                by_date[date] = {}
            by_date[date][c['llm_provider']] = c

        # ── Previous period aggregated metrics (period-over-period) ──
        previous_period = {}
        try:
            prev_end_comp = start_date  # previous period ends where current starts
            prev_start_comp = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            prev_comp_query = """
                SELECT llm_provider,
                       AVG(mention_rate) as avg_mention_rate,
                       AVG(share_of_voice) as avg_sov,
                       AVG(weighted_share_of_voice) as avg_weighted_sov,
                       AVG(avg_sentiment_score) as avg_sentiment
                FROM llm_monitoring_snapshots
                WHERE project_id = %s
                  AND snapshot_date >= %s AND snapshot_date < %s
            """
            prev_comp_params = [project_id, prev_start_comp, prev_end_comp]
            if enabled_llms_filter:
                prev_comp_query += " AND llm_provider = ANY(%s)"
                prev_comp_params.append(enabled_llms_filter)
            prev_comp_query += " GROUP BY llm_provider"
            cur.execute(prev_comp_query, prev_comp_params)

            for row in cur.fetchall():
                previous_period[row['llm_provider']] = {
                    'avg_mention_rate': float(row['avg_mention_rate']) if row['avg_mention_rate'] is not None else 0,
                    'avg_sov': float(row['avg_sov']) if row['avg_sov'] is not None else 0,
                    'avg_weighted_sov': float(row['avg_weighted_sov']) if row['avg_weighted_sov'] is not None else 0,
                    'avg_sentiment': float(row['avg_sentiment']) if row['avg_sentiment'] is not None else 0
                }
        except Exception as prev_comp_err:
            logger.warning(f"Could not compute previous period comparison: {prev_comp_err}")

        return jsonify({
            'success': True,
            'project_id': project_id,
            'comparison': comparison_list,
            'by_date': by_date,
            'previous_period': previous_period
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo comparativa: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# ENDPOINTS: CONFIGURACIÓN
# ============================================================================
# 
# NOTA: Los endpoints de configuración de API keys y presupuesto por usuario
# han sido ELIMINADOS porque en este modelo de negocio, los usuarios NO 
# configuran sus propias API keys. El servicio usa API keys globales
# gestionadas por el dueño del servicio en variables de entorno.
#
# Si en el futuro se necesita un modelo "Enterprise" donde clientes grandes
# usen sus propias APIs, se pueden restaurar estos endpoints.
# ============================================================================


# ============================================================================
# ENDPOINTS: QUERIES DETALLADAS
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/queries', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_queries(project_id):
    """
    Obtener tabla detallada de queries/prompts con métricas agregadas
    
    Devuelve información similar a la tabla de LLM Pulse:
    - Query text
    - Country & Language
    - Total responses (cuántos LLMs respondieron)
    - Total mentions
    - Visibility % (promedio)
    - Average position
    - Last update
    - Creation date
    
    Query params:
        days: Días hacia atrás para filtrar resultados (default: 30)
    
    Returns:
        JSON con lista de queries y sus métricas
    """
    user = get_current_user()
    days = _normalize_days_param(request.args.get('days'), default=30)
    report_filters = _parse_report_filters(request.args)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()

        # Obtener información del proyecto (para country)
        cur.execute("""
            SELECT name, language, country_code, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))

        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        enabled_llms_filter = _narrow_llms(project.get('enabled_llms') or [], report_filters)
        
        # Calcular rango de fechas
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Obtener información del proyecto para filtrar URLs de marca
        cur.execute("""
            SELECT brand_domain FROM llm_monitoring_projects WHERE id = %s
        """, (project_id,))
        
        project_info = cur.fetchone()
        brand_domain = project_info['brand_domain'] if project_info else None
        
        # Obtener queries con métricas agregadas
        # ✨ MEJORADO: Contar menciones en texto + menciones en URLs
        query_metrics_sql = """
            WITH query_metrics AS (
                SELECT
                    q.id,
                    q.query_text,
                    q.language,
                    q.query_type,
                    q.topic_cluster,
                    q.prompt_set,
                    q.added_at as created_at,
                    COUNT(DISTINCT r.llm_provider) as total_responses,
                    COUNT(DISTINCT r.id) as total_results,
                    -- ✨ NUEVO: Contar menciones en texto (brand_mentioned)
                    SUM(CASE WHEN r.brand_mentioned THEN 1 ELSE 0 END) as text_mentions,
                    -- ✨ NUEVO: Contar URLs de marca en sources (requiere jsonb_array_elements)
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
                    AVG(CASE WHEN r.brand_mentioned THEN 100 ELSE 0 END) as visibility_pct,
                    AVG(r.position_in_list) FILTER (WHERE r.position_in_list IS NOT NULL) as avg_position,
                    MAX(r.analysis_date) as last_analysis_date,
                    MAX(r.created_at) as last_update
                FROM llm_monitoring_queries q
                LEFT JOIN llm_monitoring_results r ON q.id = r.query_id
                    AND r.analysis_date >= %s
                    AND r.analysis_date <= %s
                    {llm_filter}
                WHERE q.project_id = %s AND q.is_active = TRUE
                {report_filter}
                GROUP BY q.id, q.query_text, q.language, q.query_type, q.topic_cluster, q.prompt_set, q.added_at
            )
            SELECT
                id,
                query_text,
                language,
                query_type,
                topic_cluster,
                prompt_set,
                created_at,
                total_responses,
                total_results,
                -- ✨ NUEVO: Total de menciones = menciones en texto + citaciones en URLs
                (COALESCE(text_mentions, 0) + COALESCE(url_citations, 0)) as total_mentions,
                text_mentions,
                url_citations,
                ROUND(visibility_pct::numeric, 1) as visibility_pct,
                ROUND(avg_position::numeric, 1) as avg_position,
                last_analysis_date,
                last_update
            FROM query_metrics
            ORDER BY last_update DESC NULLS LAST, created_at DESC
        """
        filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=start_date, end_date=end_date)
        query_metrics_sql = query_metrics_sql.format(
            llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms_filter else "",
            report_filter="AND q.id = ANY(%s)" if filtered_query_ids is not None else ""
        )
        query_metrics_params = [f'%{brand_domain}%' if brand_domain else '%', start_date, end_date]
        if enabled_llms_filter:
            query_metrics_params.append(enabled_llms_filter)
        query_metrics_params.append(project_id)
        if filtered_query_ids is not None:
            query_metrics_params.append(filtered_query_ids)
        cur.execute(query_metrics_sql, query_metrics_params)
        
        queries_raw = cur.fetchall()
        
        # ✨ NUEVO: Obtener menciones detalladas por LLM para cada query (para acordeón expandible)
        # Esto nos permite mostrar qué LLMs mencionaron la marca y los competidores
        # Usamos DISTINCT ON para obtener solo el resultado más reciente por (query_id, llm_provider)
        # 🔧 FIX: Incluir información sobre menciones en URLs también
        mentions_query_sql = """
            SELECT DISTINCT ON (r.query_id, r.llm_provider)
                r.query_id,
                r.llm_provider,
                r.brand_mentioned,
                r.position_in_list,
                r.competitors_mentioned,
                r.sources,
                r.analysis_date
            FROM llm_monitoring_results r
            WHERE r.query_id = ANY(%s)
                AND r.analysis_date >= %s
                AND r.analysis_date <= %s
                {llm_filter}
            ORDER BY r.query_id, r.llm_provider, r.analysis_date DESC
        """.format(
            llm_filter="AND r.llm_provider = ANY(%s)" if enabled_llms_filter else ""
        )
        mentions_query_params = [[q['id'] for q in queries_raw], start_date, end_date]
        if enabled_llms_filter:
            mentions_query_params.append(enabled_llms_filter)
        cur.execute(mentions_query_sql, mentions_query_params)
        
        mentions_by_query = {}
        for row in cur.fetchall():
            query_id = row['query_id']
            llm = row['llm_provider']
            
            if query_id not in mentions_by_query:
                mentions_by_query[query_id] = {}
            
            # 🔧 FIX: Detectar menciones en URLs también
            brand_in_text = row['brand_mentioned'] or False
            brand_in_urls = False
            
            # Verificar si la marca aparece en las URLs citadas
            if brand_domain and row['sources']:
                sources = row['sources']
                # sources puede ser una string JSON o ya un dict/list
                if isinstance(sources, str):
                    import json
                    try:
                        sources = json.loads(sources)
                    except:
                        sources = []
                
                if isinstance(sources, list):
                    for source in sources:
                        if isinstance(source, dict):
                            url = source.get('url', '').lower()
                            if brand_domain.lower() in url:
                                brand_in_urls = True
                                break
            
            # La marca fue mencionada si apareció en texto O en URLs
            brand_mentioned_total = brand_in_text or brand_in_urls
            
            # Ahora cada fila es única por (query_id, llm_provider) - el más reciente
            mentions_by_query[query_id][llm] = {
                'brand_mentioned': brand_mentioned_total,  # 🔧 FIX: Total incluyendo URLs
                'brand_mentioned_in_text': brand_in_text,  # ✨ NUEVO: Desglose
                'brand_mentioned_in_urls': brand_in_urls,  # ✨ NUEVO: Desglose
                'position': row['position_in_list'],
                'competitors': row['competitors_mentioned'] or {}
            }

        # Share of Voice, sentimiento y top dominios por prompt. Mismo helper que
        # usa la hoja "Prompts & Queries" del Excel, para que el informe
        # descargado no pueda decir cifras distintas de las de la pantalla.
        # OJO con el nombre: el bucle de abajo usa `prompt_metrics` para el dict
        # de UN prompt, y si el closure leyera esa misma variable devolvería
        # vacío a partir del segundo.
        prompt_metrics_by_id = collect_prompt_metrics(
            cur, project_id, [q['id'] for q in queries_raw],
            start_date, end_date, enabled_llms_filter
        )

        def _build_prompt_metrics(qid):
            return prompt_metrics_by_id.get(qid) or empty_prompt_metrics()

        # Formatear datos para el frontend
        queries_list = []
        for q in queries_raw:
            query_id = q['id']

            # ✨ NUEVO: Añadir información de menciones por LLM
            mentions_detail = mentions_by_query.get(query_id, {})
            prompt_metrics = _build_prompt_metrics(query_id)

            queries_list.append({
                'id': query_id,
                'prompt': q['query_text'],
                'country': 'Global',  # Por ahora global, se puede añadir por query
                'language': q['language'] or project['language'] or 'en',
                'query_type': q['query_type'],
                'topic_cluster': q.get('topic_cluster'),  # ✨ NUEVO: Cluster asignado (o None)
                'prompt_set': q.get('prompt_set'),  # Set asignado (None = núcleo)
                'total_responses': q['total_responses'] or 0,
                # int() explícito: el SUM de PostgreSQL llega como Decimal y Flask
                # serializa Decimal como string, rompiendo el orden numérico en Grid.js
                'total_mentions': int(q['total_mentions'] or 0),
                'visibility_pct': float(q['visibility_pct']) if q['visibility_pct'] else 0,
                'avg_position': float(q['avg_position']) if q['avg_position'] else None,
                'last_update': q['last_update'].isoformat() if q['last_update'] else None,
                'last_analysis_date': q['last_analysis_date'].isoformat() if q['last_analysis_date'] else None,
                'created_at': q['created_at'].isoformat() if q['created_at'] else None,
                'mentions_by_llm': mentions_detail,  # ✨ NUEVO: Detalles para acordeón
                'share_of_voice': prompt_metrics['share_of_voice'],  # ✨ NUEVO
                'sentiment': prompt_metrics['sentiment'],  # ✨ NUEVO
                'top_domains': prompt_metrics['top_domains']  # ✨ NUEVO
            })
        
        return jsonify({
            'success': True,
            'queries': queries_list,
            'total': len(queries_list),
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo queries: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ============================================================================
# ENDPOINTS: SHARE OF VOICE HISTÓRICO
# ============================================================================

@llm_monitoring_bp.route('/projects/<int:project_id>/share-of-voice-history', methods=['GET'])
@login_required
@validate_project_ownership
def get_share_of_voice_history(project_id):
    """
    Obtener datos históricos de Share of Voice para gráfico de líneas temporal
    
    Similar a los gráficos comparativos de Manual AI, muestra la evolución
    del Share of Voice de la marca vs competidores a lo largo del tiempo.
    
    Query params:
        days: Número de días hacia atrás (default: 30)
        metric: 'normal' o 'weighted' (default: 'weighted') - tipo de Share of Voice
    
    Returns:
        JSON con datos para gráfico de líneas:
        {
            'dates': ['2025-01-01', '2025-01-02', ...],
            'datasets': [
                {
                    'label': 'Tu Marca',
                    'data': [45.2, 48.1, ...],
                    'borderColor': brand_palette.BRAND,
                    ...
                },
                {
                    'label': 'Competidor 1',
                    'data': [30.5, 28.3, ...],
                    'borderColor': '#ef4444',
                    ...
                }
            ]
        }
    """
    user = get_current_user()
    days = _normalize_days_param(request.args.get('days'), default=30)
    metric_type = request.args.get('metric', 'weighted')  # 'normal' o 'weighted'
    # query_scope es el legacy de los toggles por-gráfica (retirados de la UI);
    # se mantiene por compatibilidad. El filtro global usa `branded=` y viaja
    # dentro de report_filters.
    query_scope = request.args.get('query_scope', 'all')  # 'all', 'branded', 'non_branded'
    report_filters = _parse_report_filters(request.args)

    # Validar metric_type
    if metric_type not in ['normal', 'weighted']:
        metric_type = 'weighted'
    if query_scope not in ['all', 'branded', 'non_branded']:
        query_scope = 'all'

    logger.info(f"📊 Share of Voice history requested - Type: {metric_type}, Days: {days}, Scope: {query_scope}")

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()

        # Obtener proyecto
        cur.execute("""
            SELECT
                id, user_id, name, brand_name, industry,
                brand_domain, brand_keywords,
                competitors, selected_competitors,
                language, country_code,
                queries_per_llm, enabled_llms,
                is_active, created_at, last_analysis_date
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))

        project = cur.fetchone()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Calcular fechas de inicio y fin
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        enabled_llms_filter = _narrow_llms(project.get('enabled_llms') or [], report_filters)
        brand_keywords_sov = project.get('brand_keywords') or []

        # ── Rama basada en results individuales ──
        # Se usa cuando el scope branded/non-branded legacy está activo Y/O
        # cuando hay filtro global de subconjunto de prompts (los snapshots
        # agregan todos los prompts y no pueden filtrarse a posteriori).
        filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=start_date)
        if (query_scope != 'all' and brand_keywords_sov) or filtered_query_ids is not None:
            sov_result_query = """
                SELECT r.analysis_date, r.llm_provider, q.query_text,
                       r.brand_mentioned, r.competitors_mentioned
                FROM llm_monitoring_results r
                JOIN llm_monitoring_queries q ON r.query_id = q.id
                WHERE r.project_id = %s AND r.analysis_date >= %s
            """
            sov_result_params = [project_id, start_date]
            if filtered_query_ids is not None:
                sov_result_query += " AND r.query_id = ANY(%s)"
                sov_result_params.append(filtered_query_ids)
            if enabled_llms_filter:
                sov_result_query += " AND r.llm_provider = ANY(%s)"
                sov_result_params.append(enabled_llms_filter)
            sov_result_query += " ORDER BY r.analysis_date"
            cur.execute(sov_result_query, sov_result_params)
            all_results = cur.fetchall()

            # Filter by branded/non-branded (solo si el scope lo pide)
            if query_scope != 'all' and brand_keywords_sov:
                filtered = []
                for r in all_results:
                    is_branded = classify_query_branded(r.get('query_text', ''), brand_keywords_sov)
                    if (query_scope == 'branded' and is_branded) or \
                       (query_scope == 'non_branded' and not is_branded):
                        filtered.append(r)
            else:
                filtered = all_results

            # Group by date: brand mentions + per-competitor mentions
            from collections import defaultdict
            scope_by_date = defaultdict(lambda: {'brand': 0, 'competitors': defaultdict(int)})
            all_comp_names = set()
            for r in filtered:
                d = r['analysis_date'].isoformat() if hasattr(r['analysis_date'], 'isoformat') else str(r['analysis_date'])
                if r.get('brand_mentioned'):
                    scope_by_date[d]['brand'] += 1
                cm = r.get('competitors_mentioned')
                if cm:
                    if isinstance(cm, str):
                        try:
                            cm = json.loads(cm)
                        except Exception:
                            cm = {}
                    if isinstance(cm, dict):
                        for ck, cv in cm.items():
                            ck_lower = ck.lower().strip()
                            scope_by_date[d]['competitors'][ck_lower] += int(cv or 0)
                            all_comp_names.add(ck_lower)

            dates_sorted = sorted(scope_by_date.keys())

            # Build brand SOV dataset
            brand_data = []
            for d in dates_sorted:
                b = scope_by_date[d]['brand']
                total_comp = sum(scope_by_date[d]['competitors'].values())
                total = b + total_comp
                brand_data.append(round((b / total) * 100, 1) if total > 0 else 0)

            # Build competitor datasets
            # Slots 2..5 de la paleta de datos (--cs-series-* en
            # static/brand-dashboard-tokens.css). Antes esta rama usaba una
            # paleta propia (rojo/naranja/verde/morado) distinta de la que la
            # rama "all" y el resto de gráficas ya sirven: la misma entidad
            # cambiaba de color al cambiar de pestaña.
            comp_colors = [
                (c, brand_palette.hex_to_rgba(c, 0.1))
                for c in brand_palette.COMPETITORS[:4]
            ]
            sorted_comp_names = sorted(all_comp_names)[:4]
            datasets = [{
                'label': f'Your Brand',
                'data': brand_data,
                'borderColor': brand_palette.BRAND,
                'backgroundColor': brand_palette.hex_to_rgba(brand_palette.BRAND, 0.1),
                'fill': True,
                'tension': 0.3,
                'borderWidth': 2.5
            }]
            for ci, cname in enumerate(sorted_comp_names):
                comp_data = []
                for d in dates_sorted:
                    b = scope_by_date[d]['brand']
                    total_comp = sum(scope_by_date[d]['competitors'].values())
                    total = b + total_comp
                    c_mentions = scope_by_date[d]['competitors'].get(cname, 0)
                    comp_data.append(round((c_mentions / total) * 100, 1) if total > 0 else 0)
                border_color, bg_color = comp_colors[ci % len(comp_colors)]
                datasets.append({
                    'label': cname,
                    'data': comp_data,
                    'borderColor': border_color,
                    'backgroundColor': bg_color,
                    'fill': False,
                    'tension': 0.3,
                    'borderWidth': 1.5
                })

            # Menciones absolutas con el mismo scope (para "Total Mentions Over Time")
            mentions_datasets = [{
                'label': project.get('brand_name') or 'Your Brand',
                'data': [scope_by_date[d]['brand'] for d in dates_sorted],
                'borderColor': brand_palette.BRAND,
                'backgroundColor': brand_palette.hex_to_rgba(brand_palette.BRAND, 0.1),
                'borderWidth': 3,
                'tension': 0.4,
                'fill': True,
                'pointRadius': 4,
                'pointHoverRadius': 6
            }]
            for ci, cname in enumerate(sorted_comp_names):
                border_color, bg_color = comp_colors[ci % len(comp_colors)]
                mentions_datasets.append({
                    'label': cname,
                    'data': [scope_by_date[d]['competitors'].get(cname, 0) for d in dates_sorted],
                    'borderColor': border_color,
                    'backgroundColor': bg_color,
                    'borderWidth': 2,
                    'tension': 0.4,
                    'fill': False,
                    'pointRadius': 3,
                    'pointHoverRadius': 5
                })

            if query_scope == 'non_branded':
                scope_label = 'Non-Branded'
            elif query_scope == 'branded':
                scope_label = 'Branded'
            else:
                scope_label = 'All'
            return jsonify({
                'success': True,
                'query_scope': query_scope,
                'scope_label': scope_label,
                'dates': dates_sorted,
                'datasets': datasets,
                'mentions_datasets': mentions_datasets
            }), 200

        # Obtener todos los snapshots del período agrupados por fecha (incluir métricas ponderadas)
        sov_history_query = """
            SELECT 
                snapshot_date,
                llm_provider,
                share_of_voice,
                weighted_share_of_voice,
                total_mentions,
                total_competitor_mentions,
                competitor_breakdown,
                weighted_competitor_breakdown
            FROM llm_monitoring_snapshots
            WHERE project_id = %s 
                AND snapshot_date >= %s 
        """
        sov_history_params = [project_id, start_date]
        if enabled_llms_filter:
            sov_history_query += " AND llm_provider = ANY(%s)"
            sov_history_params.append(enabled_llms_filter)
        sov_history_query += " ORDER BY snapshot_date, llm_provider"
        cur.execute(sov_history_query, sov_history_params)
        
        snapshots = cur.fetchall()

        # Si no hay datos, devolver estructura vacía
        if not snapshots:
            return jsonify({
                'success': True,
                'dates': [],
                'datasets': []
            }), 200
        
        # ✨ NEW: Use selected_competitors structure for clear attribution
        # =======================================================================
        # MAPEO DIRECTO: Cada dominio tiene sus keywords asociadas
        # =======================================================================
        
        selected_competitors = project.get('selected_competitors') or []
        
        # Crear mapeo: variante_detectada -> dominio_competidor
        competitor_mapping = {}
        competitor_display_names = {}  # dominio -> nombre_display
        
        def normalize_variant(variant):
            """Normaliza una variante para matching"""
            v = variant.lower().strip()
            # Quitar extensiones de dominio comunes
            v = v.replace('.com', '').replace('.es', '').replace('.net', '').replace('.org', '')
            v = v.replace('.mx', '').replace('.ar', '').replace('.cl', '').replace('.pe', '')
            v = v.replace('www.', '')
            return v
        
        def get_display_name(domain):
            """Obtiene nombre display limpio del dominio"""
            if not domain:
                return 'Unknown Competitor'
            # Quitar www. y extensión
            name = domain.replace('www.', '')
            # Tomar solo el nombre antes del TLD
            name_parts = name.split('.')
            if len(name_parts) > 0:
                return name_parts[0].upper()
            return domain.upper()
        
        # ✨ NEW: Mapear directamente desde selected_competitors
        for comp in selected_competitors:
            domain = comp.get('domain', '').strip()
            keywords = comp.get('keywords', [])
            
            if not domain:
                continue
            
            # Usar el dominio como identificador único
            domain_lower = domain.lower()
            display_name = get_display_name(domain)
            competitor_display_names[domain_lower] = display_name
            
            # Mapear el dominio a sí mismo
            competitor_mapping[domain_lower] = domain_lower
            
            # Mapear todas las keywords asociadas a este dominio
            for keyword in keywords:
                keyword_lower = keyword.lower().strip()
                competitor_mapping[keyword_lower] = domain_lower
                
                # También mapear variante normalizada
                keyword_normalized = normalize_variant(keyword)
                if keyword_normalized != keyword_lower:
                    competitor_mapping[keyword_normalized] = domain_lower
        
        # Agrupar datos por fecha Y agrupar menciones por dominio de competidor
        from collections import defaultdict
        data_by_date = defaultdict(lambda: {
            'brand_mentions': 0,
            'competitor_mentions': defaultdict(int),  # Agrupado por dominio
            'llm_count': 0
        })
        
        # ✨ NUEVO: Elegir la métrica correcta según el parámetro
        for snapshot in snapshots:
            date_str = snapshot['snapshot_date'].isoformat()
            
            # ✨ MEJORADO: Usar menciones ponderadas o normales según el parámetro
            if metric_type == 'weighted':
                # Si hay weighted_share_of_voice, usarlo para inferir menciones ponderadas
                try:
                    weighted_sov_raw = snapshot.get('weighted_share_of_voice')
                    # Convertir a float de forma segura
                    try:
                        weighted_sov = float(weighted_sov_raw) if weighted_sov_raw is not None else None
                    except Exception:
                        weighted_sov = None
                    
                    weighted_breakdown_raw = snapshot.get('weighted_competitor_breakdown')
                    # Asegurar que sea un dict; si viene en string JSON, parsear
                    if isinstance(weighted_breakdown_raw, dict):
                        weighted_breakdown = weighted_breakdown_raw
                    elif isinstance(weighted_breakdown_raw, str):
                        try:
                            parsed = json.loads(weighted_breakdown_raw)
                            weighted_breakdown = parsed if isinstance(parsed, dict) else {}
                        except Exception:
                            weighted_breakdown = {}
                    else:
                        weighted_breakdown = {}
                    
                    # Si tenemos datos ponderados, usarlos
                    if weighted_sov is not None and weighted_breakdown:
                        # Calcular menciones ponderadas de competidores
                        try:
                            total_weighted_comp = sum(float(v) for v in weighted_breakdown.values() if v is not None)
                        except Exception:
                            total_weighted_comp = 0.0
                        
                        if weighted_sov and weighted_sov > 0:
                            # SoV = brand / (brand + comp) * 100
                            # brand = (SoV / (100 - SoV)) * comp
                            if weighted_sov >= 100:
                                # Si SoV es 100%, la marca tiene todas las menciones
                                weighted_brand = total_weighted_comp if total_weighted_comp > 0 else 1.0
                            else:
                                weighted_brand = (weighted_sov / (100 - weighted_sov)) * total_weighted_comp
                        else:
                            weighted_brand = 0.0
                        
                        data_by_date[date_str]['brand_mentions'] += weighted_brand
                        breakdown = weighted_breakdown
                    else:
                        # Fallback a métricas normales si no hay datos ponderados
                        logger.warning(f"⚠️ No weighted data for {date_str}, falling back to normal metrics")
                        data_by_date[date_str]['brand_mentions'] += (snapshot['total_mentions'] or 0)
                        breakdown = snapshot.get('competitor_breakdown') or {}
                except Exception as e_weighted:
                    # Cualquier error en la ruta ponderada no debe romper el endpoint
                    logger.warning(f"⚠️ Weighted calc error on {date_str}: {e_weighted}. Using normal metrics as fallback.")
                    data_by_date[date_str]['brand_mentions'] += (snapshot['total_mentions'] or 0)
                    breakdown = snapshot.get('competitor_breakdown') or {}
            else:
                # Modo normal: usar métricas estándar
                data_by_date[date_str]['brand_mentions'] += (snapshot['total_mentions'] or 0)
                breakdown = snapshot.get('competitor_breakdown') or {}
            
            data_by_date[date_str]['llm_count'] += 1
            
            # 🔧 FIX: Asegurar que breakdown es un dict antes de iterar
            if isinstance(breakdown, str):
                try:
                    breakdown = json.loads(breakdown)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"⚠️ Could not parse breakdown JSON for {date_str}, skipping")
                    breakdown = {}
            
            if not isinstance(breakdown, dict):
                logger.warning(f"⚠️ Breakdown is not a dict for {date_str}, skipping")
                breakdown = {}
            
            for detected_variant, mentions in breakdown.items():
                variant_lower = detected_variant.lower().strip()
                variant_normalized = normalize_variant(detected_variant)
                
                # Buscar en el mapeo directo
                competitor_domain = None
                if variant_lower in competitor_mapping:
                    competitor_domain = competitor_mapping[variant_lower]
                elif variant_normalized in competitor_mapping:
                    competitor_domain = competitor_mapping[variant_normalized]
                else:
                    # Buscar por coincidencia parcial (más robustez)
                    for mapped_variant, domain in competitor_mapping.items():
                        if (mapped_variant in variant_lower or 
                            variant_lower in mapped_variant or
                            normalize_variant(mapped_variant) == variant_normalized):
                            competitor_domain = domain
                            break
                
                # Si encontramos el dominio, acumular menciones
                if competitor_domain:
                    data_by_date[date_str]['competitor_mentions'][competitor_domain] += mentions
                elif not competitor_mapping:
                    # Sin competidores configurados en el proyecto, usar el nombre
                    # detectado por el análisis tal cual — igual que hace la rama
                    # branded/non-branded. Antes esta rama descartaba TODO lo no
                    # configurado, y por eso en "All" no aparecía ningún competidor
                    # mientras que en Non-Branded sí (dos caminos de código con
                    # criterios distintos para el mismo dato).
                    data_by_date[date_str]['competitor_mentions'][variant_lower] += mentions
                # Con competidores configurados, lo no mapeado se sigue ignorando:
                # es la forma de excluir marcas que no interesan.
        
        # Ordenar fechas
        dates = sorted(data_by_date.keys())
        
        # Preparar datasets
        datasets = []
        
        # Dataset para la marca principal (TODAS las variantes ya están sumadas en total_mentions)
        brand_name = project['brand_name'] or 'Your Brand'
        brand_data = []
        
        for date_str in dates:
            day_data = data_by_date[date_str]
            brand_mentions = day_data['brand_mentions']
            total_comp_mentions = sum(day_data['competitor_mentions'].values())
            total_mentions = brand_mentions + total_comp_mentions
            
            # Calcular Share of Voice de la marca
            sov = (brand_mentions / total_mentions * 100) if total_mentions > 0 else 0
            brand_data.append(round(sov, 2))
        
        datasets.append({
            'label': brand_name,
            'data': brand_data,
            'borderColor': brand_palette.BRAND,
            'backgroundColor': brand_palette.hex_to_rgba(brand_palette.BRAND, 0.1),
            'borderWidth': 3,
            'tension': 0.4,
            'fill': True,
            'pointRadius': 4,
            'pointHoverRadius': 6
        })
        
        # Datasets para competidores (ahora agrupados).
        # Slots 2..6 de la paleta de datos (--cs-series-* en
        # static/brand-dashboard-tokens.css); el slot 1 queda para la marca
        # propia. Mantener sincronizado con CSChartTheme.seriesExtended o el
        # donut dirá un color y el resto de gráficas otro.
        competitor_colors = brand_palette.COMPETITORS
        
        # ✨ NEW: Obtener lista única de dominios de competidores
        all_competitor_domains = set()
        for day_data in data_by_date.values():
            all_competitor_domains.update(day_data['competitor_mentions'].keys())
        
        for idx, competitor_domain in enumerate(sorted(all_competitor_domains)):
            comp_data = []
            
            # ✨ NEW: Obtener nombre display del dominio
            display_name = competitor_display_names.get(competitor_domain, get_display_name(competitor_domain))
            
            for date_str in dates:
                day_data = data_by_date[date_str]
                brand_mentions = day_data['brand_mentions']
                comp_mentions = day_data['competitor_mentions'].get(competitor_domain, 0)
                total_comp_mentions = sum(day_data['competitor_mentions'].values())
                total_mentions = brand_mentions + total_comp_mentions
                
                # Calcular Share of Voice del competidor
                sov = (comp_mentions / total_mentions * 100) if total_mentions > 0 else 0
                comp_data.append(round(sov, 2))
            
            color = competitor_colors[idx % len(competitor_colors)]
            datasets.append({
                'label': display_name,
                'data': comp_data,
                'borderColor': color,
                'backgroundColor': color.replace('rgb', 'rgba').replace(')', ', 0.1)') if 'rgb' in color else f'{color}20',
                'borderWidth': 2,
                'tension': 0.4,
                'fill': False,
                'pointRadius': 3,
                'pointHoverRadius': 5
            })
        
        # =======================================================================
        # DATOS ADICIONALES: Menciones absolutas + Donut data
        # =======================================================================
        
        # 1. Datasets para gráfico de menciones (números absolutos)
        mentions_datasets = []
        
        # Dataset de menciones de marca
        brand_mentions_data = []
        for date_str in dates:
            day_data = data_by_date[date_str]
            brand_mentions_data.append(day_data['brand_mentions'])
        
        mentions_datasets.append({
            'label': brand_name,
            'data': brand_mentions_data,
            'borderColor': brand_palette.BRAND,
            'backgroundColor': brand_palette.hex_to_rgba(brand_palette.BRAND, 0.1),
            'borderWidth': 3,
            'tension': 0.4,
            'fill': True,
            'pointRadius': 4,
            'pointHoverRadius': 6
        })
        
        # Datasets de menciones de competidores
        for idx, competitor_domain in enumerate(sorted(all_competitor_domains)):
            comp_mentions_data = []
            display_name = competitor_display_names.get(competitor_domain, get_display_name(competitor_domain))
            
            for date_str in dates:
                day_data = data_by_date[date_str]
                comp_mentions_data.append(day_data['competitor_mentions'].get(competitor_domain, 0))
            
            color = competitor_colors[idx % len(competitor_colors)]
            mentions_datasets.append({
                'label': display_name,
                'data': comp_mentions_data,
                'borderColor': color,
                'backgroundColor': color.replace('rgb', 'rgba').replace(')', ', 0.1)') if 'rgb' in color else f'{color}20',
                'borderWidth': 2,
                'tension': 0.4,
                'fill': False,
                'pointRadius': 3,
                'pointHoverRadius': 5
            })
        
        # 2. Datos para gráfico de rosco (promedio del período)
        total_brand_mentions_period = sum(data_by_date[date_str]['brand_mentions'] for date_str in dates)
        total_competitor_mentions_period = defaultdict(int)
        
        for date_str in dates:
            for comp_domain, mentions in data_by_date[date_str]['competitor_mentions'].items():
                total_competitor_mentions_period[comp_domain] += mentions
        
        # Calcular totales
        grand_total = total_brand_mentions_period + sum(total_competitor_mentions_period.values())
        
        # Preparar datos del donut
        donut_labels = [brand_name]
        donut_values = [round(total_brand_mentions_period / grand_total * 100, 2) if grand_total > 0 else 0]
        # Slot 1 de la paleta de datos: la marca propia siempre en el mismo color
        # y el más contrastado. Debe coincidir con CSChartTheme.series[0].
        donut_colors = [brand_palette.BRAND]
        
        for idx, competitor_domain in enumerate(sorted(all_competitor_domains)):
            display_name = competitor_display_names.get(competitor_domain, get_display_name(competitor_domain))
            comp_total = total_competitor_mentions_period.get(competitor_domain, 0)
            comp_percentage = round(comp_total / grand_total * 100, 2) if grand_total > 0 else 0
            
            if comp_percentage > 0:  # Solo incluir si tiene menciones
                donut_labels.append(display_name)
                donut_values.append(comp_percentage)
                donut_colors.append(competitor_colors[idx % len(competitor_colors)])
        
        # ── Previous period averages for tooltip comparison ──
        prev_period_avg = {}
        try:
            prev_end = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            prev_start = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            prev_conn = get_db_connection()
            if prev_conn:
                prev_cur = None
                try:
                    prev_cur = prev_conn.cursor()
                    prev_sov_query = """
                        SELECT snapshot_date, llm_provider,
                               total_mentions, total_competitor_mentions, competitor_breakdown,
                               share_of_voice, weighted_share_of_voice,
                               weighted_competitor_breakdown
                        FROM llm_monitoring_snapshots
                        WHERE project_id = %s AND snapshot_date >= %s AND snapshot_date < %s
                    """
                    prev_params = [project_id, prev_start, prev_end]
                    if enabled_llms_filter:
                        prev_sov_query += " AND llm_provider = ANY(%s)"
                        prev_params.append(enabled_llms_filter)
                    prev_sov_query += " ORDER BY snapshot_date"
                    prev_cur.execute(prev_sov_query, prev_params)
                    prev_snaps = prev_cur.fetchall()
                finally:
                    try:
                        prev_cur.close()
                    except Exception:
                        pass
                    try:
                        prev_conn.close()
                    except Exception:
                        pass

                if prev_snaps:
                    # Aggregate previous period brand + competitor mentions
                    prev_brand_total = 0
                    prev_comp_totals = defaultdict(int)
                    for ps in prev_snaps:
                        prev_brand_total += int(ps.get('total_mentions') or 0)
                        breakdown_key = 'weighted_competitor_breakdown' if metric_type == 'weighted' else 'competitor_breakdown'
                        bd = ps.get(breakdown_key) or ps.get('competitor_breakdown') or {}
                        if isinstance(bd, str):
                            try:
                                bd = json.loads(bd)
                            except Exception:
                                bd = {}
                        if isinstance(bd, dict):
                            for ck, cv in bd.items():
                                ck_lower = ck.lower().strip()
                                mapped = competitor_mapping.get(ck_lower) or competitor_mapping.get(normalize_variant(ck_lower))
                                if mapped:
                                    prev_comp_totals[mapped] += int(cv or 0)

                    prev_grand = prev_brand_total + sum(prev_comp_totals.values())
                    if prev_grand > 0:
                        prev_period_avg[brand_name] = round((prev_brand_total / prev_grand) * 100, 1)
                        for comp_dom, comp_ment in prev_comp_totals.items():
                            disp = competitor_display_names.get(comp_dom, get_display_name(comp_dom))
                            prev_period_avg[disp] = round((comp_ment / prev_grand) * 100, 1)
        except Exception as prev_err:
            logger.warning(f"Could not compute previous period SOV: {prev_err}")

        return jsonify({
            'success': True,
            'metric_type': metric_type,
            'dates': dates,
            'datasets': datasets,
            'mentions_datasets': mentions_datasets,
            'donut_data': {
                'labels': donut_labels,
                'values': donut_values,
                'colors': donut_colors
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'previous_period_avg': prev_period_avg
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo histórico de Share of Voice: {e}", exc_info=True)
        logger.error(f"   Project ID: {project_id}, Days: {days}, Metric: {metric_type}")
        return jsonify({
            'error': 'Failed to load data. Please try again.',
            'details': 'Check server logs for more information'
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


@llm_monitoring_bp.route('/projects/<int:project_id>/responses', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_responses(project_id):
    """
    Obtener respuestas detalladas de LLMs para inspección manual
    
    Query params:
        query_id: ID de query específica (opcional)
        llm_provider: Filtrar por proveedor (opcional)
        days: Días hacia atrás (default: 7)
    
    Returns:
        JSON con respuestas completas de cada LLM
    """
    query_id = request.args.get('query_id', type=int)
    llm_provider = request.args.get('llm_provider')
    # ✨ NEW: optional cluster filter. Use the literal value "__unassigned__" to
    # request only prompts without a cluster assigned.
    cluster_filter_raw = request.args.get('cluster')
    report_filters = _parse_report_filters(request.args)
    days = _normalize_days_param(request.args.get('days'), default=7)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT enabled_llms, brand_keywords, search_mode
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Project not found'}), 404
        # Con la búsqueda desactivada la consulta y el JSON son exactamente los de siempre
        include_search = is_search_enabled(project_row.get('search_mode'))
        enabled_llms_filter = project_row.get('enabled_llms') or []
        resp_brand_keywords = project_row.get('brand_keywords') or []
        if llm_provider and enabled_llms_filter and llm_provider not in enabled_llms_filter:
            return jsonify({
                'error': 'llm_provider no habilitado para este proyecto'
            }), 400
        enabled_llms_filter = _narrow_llms(enabled_llms_filter, report_filters)

        # Calcular rango de fechas
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # Query base
        query = """
            SELECT
                r.id,
                r.query_id,
                q.query_text,
                q.topic_cluster,
                q.prompt_set,
                r.llm_provider,
                r.model_used,
                r.brand_mentioned,
                r.position_in_list,
                r.sentiment,
                r.mention_contexts,
                r.competitors_mentioned,
                r.full_response,
                r.response_length,
                r.sources,
                r.analysis_date,
                r.created_at""" + (""",
                r.execution_metadata,
                r.search_queries""" if include_search else "") + """
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON r.query_id = q.id
            WHERE r.project_id = %s
                AND r.analysis_date >= %s
                AND r.analysis_date <= %s
        """

        params = [project_id, start_date, end_date]

        # Filtros opcionales
        if query_id:
            query += " AND r.query_id = %s"
            params.append(query_id)

        if llm_provider:
            query += " AND r.llm_provider = %s"
            params.append(llm_provider)
        elif enabled_llms_filter:
            query += " AND r.llm_provider = ANY(%s)"
            params.append(enabled_llms_filter)

        # ✨ NEW: Cluster filter (server-side)
        if cluster_filter_raw:
            if cluster_filter_raw == '__unassigned__':
                query += " AND q.topic_cluster IS NULL"
            else:
                query += " AND q.topic_cluster = %s"
                params.append(cluster_filter_raw)

        # Filtro global del informe (set + clusters + branded → query_ids)
        filtered_query_ids = _resolve_filtered_query_ids(cur, project_id, report_filters, start_date=start_date, end_date=end_date)
        if filtered_query_ids is not None:
            query += " AND r.query_id = ANY(%s)"
            params.append(filtered_query_ids)

        # Sentiment: el Inspector es la vista de nivel RESPUESTA, así que aquí
        # el filtro global de sentimiento sí baja al detalle (además del
        # subconjunto de prompts que ya aplican las métricas)
        if report_filters.sentiment:
            query += " AND r.sentiment = %s"
            params.append(report_filters.sentiment)

        query += " ORDER BY r.analysis_date DESC, q.query_text, r.llm_provider"

        cur.execute(query, params)
        results = cur.fetchall()

        # Formatear resultados
        responses = []
        for r in results:
            item = {
                'id': r['id'],
                'query_id': r['query_id'],
                'query_text': r['query_text'],
                'topic_cluster': r.get('topic_cluster'),  # ✨ NUEVO
                'prompt_set': r.get('prompt_set'),  # Set del prompt (None = núcleo)
                'llm_provider': r['llm_provider'],
                'model_used': r['model_used'],
                'brand_mentioned': r['brand_mentioned'],
                'position_in_list': r['position_in_list'],
                'sentiment': r['sentiment'],
                'mention_contexts': r['mention_contexts'] or [],
                'competitors_mentioned': r['competitors_mentioned'] or {},
                'full_response': r['full_response'],
                'response_length': r['response_length'],
                'sources': r['sources'] or [],
                'is_branded_query': classify_query_branded(r['query_text'], resp_brand_keywords),
                'analysis_date': r['analysis_date'].isoformat() if r['analysis_date'] else None,
                'created_at': r['created_at'].isoformat() if r['created_at'] else None
            }
            if include_search:
                item['search'] = response_search_detail(r.get('execution_metadata'), r.get('search_queries'))
            responses.append(item)
        
        return jsonify({
            'success': True,
            'responses': responses,
            'total': len(responses),
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            }
        }), 200

    except Exception as e:
        logger.error(f"Error obteniendo respuestas: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.'}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
