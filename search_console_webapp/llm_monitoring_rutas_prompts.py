"""Rutas de gestión de prompts de LLM Monitoring: alta y baja de prompts (/queries),
clusters temáticos, prompt sets, historial de un prompt, métricas por cluster y
sugerencias de prompts con IA.

Sacadas tal cual de llm_monitoring_routes.py (sep-2026, limpieza de ficheros gigantes).
Registran sus rutas en el blueprint de llm_monitoring_base al importarse;
llm_monitoring_routes importa este módulo y vuelve a exponer sus nombres. Para
parchear algo que usen estas rutas en un test, hazlo en este módulo.
"""

import logging
from auth import get_current_user, login_required
from database import get_db_connection
from datetime import datetime, timedelta
from flask import jsonify, request
from services.llm_monitoring import prompt_sets as prompt_sets_lib
import json
from llm_monitoring_limits import _get_effective_plan_limits, get_upgrade_options
from llm_monitoring_base import (
    llm_monitoring_bp,
    validate_project_ownership,
)
from llm_monitoring_informes import (
    _narrow_llms,
    _normalize_cluster_name,
    _normalize_days_param,
    _parse_report_filters,
    _resolve_filtered_query_ids,
    _weight_for_position,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENDPOINTS: PROMPTS/QUERIES (Manual Management)
# ============================================================================
@llm_monitoring_bp.route('/projects/<int:project_id>/queries', methods=['POST'])
@login_required
@validate_project_ownership
def add_queries_to_project(project_id):
    """
    Añade queries/prompts manualmente a un proyecto
    
    Body esperado:
    {
        "queries": ["¿Qué es X?", "¿Cómo funciona Y?", ...],
        "language": "es" (opcional, default del proyecto),
        "query_type": "manual" (opcional, default: "manual")
    }
    
    Returns:
        JSON con resultado de la operación
    """
    user = get_current_user()
    
    data = request.get_json()
    queries_list = data.get('queries', [])
    language = data.get('language')
    query_type = data.get('query_type', 'manual')
    # ✨ NEW: optional cluster to assign to all prompts in this batch
    cluster_assignment_raw = data.get('cluster', None)
    target_cluster = None
    if cluster_assignment_raw is not None and cluster_assignment_raw != '':
        target_cluster = _normalize_cluster_name(cluster_assignment_raw)
        if not target_cluster:
            target_cluster = None
    # Prompt set opcional para todo el lote ('core'/null → núcleo)
    set_assignment_raw = data.get('set', None)

    if not queries_list:
        return jsonify({'error': 'No se proporcionaron queries'}), 400

    if not isinstance(queries_list, list):
        return jsonify({'error': 'queries debe ser una lista'}), 400
    
    # Validar límites por plan (prompts por proyecto)
    plan_limits = _get_effective_plan_limits(user)
    max_prompts = plan_limits.get('max_prompts_per_project')

    # Obtener configuración del proyecto si no se especificó idioma
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()

        # Lock del proyecto para evitar carreras al añadir prompts
        cur.execute("SELECT id FROM llm_monitoring_projects WHERE id = %s FOR UPDATE", (project_id,))

        if max_prompts is not None:
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM llm_monitoring_queries
                WHERE project_id = %s AND is_active = TRUE
            """, (project_id,))
            row = cur.fetchone()
            current_count = int(row['count']) if row else 0
            incoming_count = len([q for q in queries_list if isinstance(q, str) and q.strip()])
            if current_count + incoming_count > max_prompts:
                return jsonify({
                    'error': 'prompt_limit_exceeded',
                    'message': 'You have reached the maximum number of prompts allowed for this project',
                    'current_plan': user.get('plan', 'free'),
                    'upgrade_options': get_upgrade_options(user.get('plan', 'free')),
                    'limit': max_prompts,
                    'current': current_count,
                    'requested': incoming_count
                }), 402
        
        # Si no se especificó idioma, usar el del proyecto
        if not language:
            cur.execute("SELECT language FROM llm_monitoring_projects WHERE id = %s", (project_id,))
            project = cur.fetchone()
            if project:
                language = project['language']
            else:
                language = 'es'

        # ✨ NEW: Validate that target_cluster (if any) is defined in the project config
        if target_cluster:
            cur.execute(
                "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s",
                (project_id,)
            )
            project_cfg = cur.fetchone() or {}
            raw_clusters_cfg = project_cfg.get('prompt_clusters') or {}
            if isinstance(raw_clusters_cfg, str):
                try:
                    raw_clusters_cfg = json.loads(raw_clusters_cfg)
                except (json.JSONDecodeError, TypeError):
                    raw_clusters_cfg = {}
            defined_clusters = {
                (c.get('name') or '').lower()
                for c in (raw_clusters_cfg.get('clusters') or [])
                if isinstance(c, dict)
            }
            if target_cluster.lower() not in defined_clusters:
                # Silently ignore unknown cluster rather than failing the whole batch
                logger.warning(
                    f"Cluster '{target_cluster}' not defined for project {project_id} — ignoring"
                )
                target_cluster = None

        # Resolver set del lote (mismo criterio tolerante que el cluster:
        # un set desconocido se ignora, no rompe el lote entero)
        target_set = None
        if set_assignment_raw is not None and set_assignment_raw != '':
            sets_cfg = _load_sets_config(cur, project_id)
            ok, resolved = _resolve_set_assignment(set_assignment_raw, sets_cfg or {})
            if ok:
                target_set = resolved
            else:
                logger.warning(
                    f"Set '{set_assignment_raw}' not defined for project {project_id} — ignoring"
                )

        added_count = 0
        reactivated_count = 0
        duplicate_count = 0
        error_count = 0

        for query_text in queries_list:
            query_text = query_text.strip()
            if not query_text:
                error_count += 1
                continue

            try:
                # El borrado de prompts es "soft" (is_active = FALSE) y la fila
                # sigue ocupando el UNIQUE (project_id, query_text). Un prompt
                # borrado y vuelto a añadir se REACTIVA con los valores del lote
                # (idioma, tipo, cluster, set) conservando su id y, por tanto, su
                # histórico. Solo cuenta como duplicado si ya está activo:
                # con DO UPDATE ... WHERE, rowcount es 0 cuando la guarda falla.
                cur.execute("""
                    INSERT INTO llm_monitoring_queries (
                        project_id, query_text, language, query_type, topic_cluster, prompt_set, is_active, added_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
                    ON CONFLICT (project_id, query_text) DO UPDATE SET
                        is_active = TRUE,
                        language = EXCLUDED.language,
                        query_type = EXCLUDED.query_type,
                        topic_cluster = EXCLUDED.topic_cluster,
                        prompt_set = EXCLUDED.prompt_set,
                        added_at = NOW()
                    WHERE llm_monitoring_queries.is_active = FALSE
                    RETURNING (xmax = 0) AS inserted
                """, (project_id, query_text, language, query_type, target_cluster, target_set))

                if cur.rowcount > 0:
                    added_count += 1
                    row = cur.fetchone()
                    if row is not None and not row['inserted']:
                        reactivated_count += 1
                else:
                    duplicate_count += 1

            except Exception as e:
                logger.warning(f"Error añadiendo query '{query_text}': {e}")
                error_count += 1
                continue
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'added_count': added_count,
            'reactivated_count': reactivated_count,
            'duplicate_count': duplicate_count,
            'error_count': error_count,
            'message': f'{added_count} prompts added successfully'
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error añadiendo queries: {e}", exc_info=True)
        return jsonify({'error': 'Failed to add prompts. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>', methods=['DELETE'])
@login_required
@validate_project_ownership
def delete_query(project_id, query_id):
    """
    Elimina una query de un proyecto (soft delete: marca is_active = false)
    
    Returns:
        JSON con confirmación
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verificar que la query pertenece al proyecto
        cur.execute("""
            SELECT id, query_text
            FROM llm_monitoring_queries
            WHERE id = %s AND project_id = %s
        """, (query_id, project_id))
        
        query = cur.fetchone()
        
        if not query:
            return jsonify({'error': 'Prompt not found'}), 404
        
        # Soft delete
        cur.execute("""
            UPDATE llm_monitoring_queries
            SET is_active = FALSE
            WHERE id = %s AND project_id = %s
            RETURNING id
        """, (query_id, project_id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Query eliminada exitosamente',
            'query_id': query_id
        }), 200
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error eliminando query: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()


# ============================================================================
# PROMPT CLUSTERS (topic clustering manual)
# ============================================================================


def _sanitize_prompt_clusters_config(raw):
    """
    Sanitize incoming clusters config. Expected shape:
        {"enabled": bool, "clusters": [{"name": "..."}]}
    Returns (config_dict, list_of_names_in_order).
    Raises ValueError on invalid input.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError('clusters_config must be an object')

    enabled = bool(raw.get('enabled'))
    clusters_in = raw.get('clusters') or []
    if not isinstance(clusters_in, list):
        raise ValueError('clusters must be a list')

    seen = set()
    cleaned = []
    names_in_order = []
    for entry in clusters_in:
        if isinstance(entry, str):
            name = _normalize_cluster_name(entry)
        elif isinstance(entry, dict):
            name = _normalize_cluster_name(entry.get('name'))
        else:
            continue
        if not name:
            continue
        # case-insensitive uniqueness
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({'name': name})
        names_in_order.append(name)

    return (
        {'enabled': enabled and len(cleaned) > 0, 'clusters': cleaned},
        names_in_order,
    )


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_clusters(project_id):
    """
    Devuelve la configuración de clusters del proyecto + conteo de prompts por cluster.

    Returns:
        {
            "success": true,
            "clusters_config": {"enabled": bool, "clusters": [{"name": "..."}]},
            "counts": {"ClusterA": 5, "Unassigned": 2, ...}
        }
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT prompt_clusters
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Project not found'}), 404

        raw_config = row.get('prompt_clusters') or {'enabled': False, 'clusters': []}
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except (json.JSONDecodeError, TypeError):
                raw_config = {'enabled': False, 'clusters': []}

        # Conteo de prompts activos por cluster
        cur.execute("""
            SELECT COALESCE(topic_cluster, '') AS cluster, COUNT(*) AS cnt
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
            GROUP BY COALESCE(topic_cluster, '')
        """, (project_id,))
        counts = {}
        for r in cur.fetchall():
            key = r['cluster'] if r['cluster'] else 'Unassigned'
            counts[key] = int(r['cnt'])

        return jsonify({
            'success': True,
            'clusters_config': raw_config,
            'counts': counts
        }), 200

    except Exception as e:
        logger.error(f"Error obteniendo clusters: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load clusters. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters', methods=['PUT'])
@login_required
@validate_project_ownership
def update_project_clusters(project_id):
    """
    Actualiza la configuración de clusters del proyecto.

    Body:
        {"clusters_config": {"enabled": bool, "clusters": [{"name": "..."}]}}

    Comportamiento:
    - Guarda el nuevo array canónico en llm_monitoring_projects.prompt_clusters.
    - Si un cluster ha sido ELIMINADO (o si se deshabilita la feature),
      todos los queries con ese topic_cluster se ponen a NULL (desasignados).
    - No renombra clusters automáticamente: usa el endpoint /clusters/rename para eso.
    """
    data = request.get_json() or {}
    raw_config = data.get('clusters_config')
    if raw_config is None:
        return jsonify({'error': 'clusters_config is required'}), 400

    try:
        sanitized, names_in_order = _sanitize_prompt_clusters_config(raw_config)
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        # Lock del proyecto para evitar carreras
        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s FOR UPDATE",
            (project_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Project not found'}), 404

        # Guardar nueva config
        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_clusters = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(sanitized), project_id))

        # Desasignar cluster de queries cuyo cluster ya no exista (o si se desactiva)
        if not sanitized['enabled'] or not names_in_order:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET topic_cluster = NULL
                WHERE project_id = %s AND topic_cluster IS NOT NULL
            """, (project_id,))
            orphaned = cur.rowcount
        else:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET topic_cluster = NULL
                WHERE project_id = %s
                  AND topic_cluster IS NOT NULL
                  AND NOT (topic_cluster = ANY(%s))
            """, (project_id, names_in_order))
            orphaned = cur.rowcount

        conn.commit()

        return jsonify({
            'success': True,
            'clusters_config': sanitized,
            'orphaned_prompts': orphaned
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando clusters: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save clusters. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters/rename', methods=['POST'])
@login_required
@validate_project_ownership
def rename_project_cluster(project_id):
    """
    Renombra un cluster: actualiza la config del proyecto y todos los prompts asignados.

    Body: {"old_name": "...", "new_name": "..."}
    """
    data = request.get_json() or {}
    old_name = _normalize_cluster_name(data.get('old_name'))
    new_name = _normalize_cluster_name(data.get('new_name'))

    if not old_name or not new_name:
        return jsonify({'error': 'old_name and new_name are required'}), 400
    if old_name == new_name:
        return jsonify({'success': True, 'updated_prompts': 0}), 200

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s FOR UPDATE",
            (project_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Project not found'}), 404

        raw_config = row.get('prompt_clusters') or {'enabled': False, 'clusters': []}
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except (json.JSONDecodeError, TypeError):
                raw_config = {'enabled': False, 'clusters': []}

        clusters_list = raw_config.get('clusters') or []
        existing_names_lower = {c.get('name', '').lower() for c in clusters_list if isinstance(c, dict)}

        if old_name.lower() not in existing_names_lower:
            return jsonify({'error': f"Cluster '{old_name}' not found"}), 404
        if new_name.lower() in existing_names_lower and new_name.lower() != old_name.lower():
            return jsonify({'error': f"A cluster named '{new_name}' already exists"}), 409

        # Actualizar config
        renamed_list = []
        for c in clusters_list:
            if not isinstance(c, dict):
                continue
            if c.get('name', '').lower() == old_name.lower():
                renamed_list.append({'name': new_name})
            else:
                renamed_list.append({'name': c.get('name')})
        raw_config['clusters'] = renamed_list
        raw_config['enabled'] = bool(raw_config.get('enabled')) and len(renamed_list) > 0

        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_clusters = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(raw_config), project_id))

        # Actualizar queries asignados
        cur.execute("""
            UPDATE llm_monitoring_queries
            SET topic_cluster = %s
            WHERE project_id = %s AND topic_cluster = %s
        """, (new_name, project_id, old_name))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'clusters_config': raw_config,
            'updated_prompts': updated
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error renombrando cluster: {e}", exc_info=True)
        return jsonify({'error': 'Failed to rename cluster. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>/cluster', methods=['PUT'])
@login_required
@validate_project_ownership
def assign_query_cluster(project_id, query_id):
    """
    Asigna (o desasigna) un cluster a un prompt concreto.

    Body: {"cluster": "NombreCluster"}  o  {"cluster": null}  para desasignar.

    Validaciones:
    - El cluster debe existir en prompt_clusters del proyecto (o ser null).
    """
    data = request.get_json() or {}
    requested = data.get('cluster', None)
    # Permitir null/"" para desasignar
    if requested is None or requested == '':
        target_cluster = None
    else:
        target_cluster = _normalize_cluster_name(requested)
        if not target_cluster:
            return jsonify({'error': 'Invalid cluster name'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s",
            (project_id,)
        )
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Project not found'}), 404

        # Validar que el cluster exista en la config (si se está asignando)
        if target_cluster is not None:
            raw_config = project_row.get('prompt_clusters') or {}
            if isinstance(raw_config, str):
                try:
                    raw_config = json.loads(raw_config)
                except (json.JSONDecodeError, TypeError):
                    raw_config = {}
            cluster_names = {
                (c.get('name') or '').lower()
                for c in (raw_config.get('clusters') or [])
                if isinstance(c, dict)
            }
            if target_cluster.lower() not in cluster_names:
                return jsonify({
                    'error': f"Cluster '{target_cluster}' is not defined for this project"
                }), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET topic_cluster = %s
            WHERE id = %s AND project_id = %s
            RETURNING id, topic_cluster
        """, (target_cluster, query_id, project_id))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Prompt not found'}), 404

        conn.commit()
        return jsonify({
            'success': True,
            'query_id': row['id'],
            'topic_cluster': row['topic_cluster']
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error asignando cluster a query: {e}", exc_info=True)
        return jsonify({'error': 'Failed to assign cluster. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/bulk-cluster', methods=['POST'])
@login_required
@validate_project_ownership
def bulk_assign_cluster(project_id):
    """
    Asigna (o desasigna) un mismo cluster a varios prompts en una sola llamada.

    Body: {"query_ids": [1,2,3], "cluster": "NombreCluster" | null}
    """
    data = request.get_json() or {}
    query_ids = data.get('query_ids') or []
    if not isinstance(query_ids, list) or not query_ids:
        return jsonify({'error': 'query_ids must be a non-empty list'}), 400
    # Sanity cap
    query_ids = [int(q) for q in query_ids if isinstance(q, (int, str)) and str(q).isdigit()][:500]
    if not query_ids:
        return jsonify({'error': 'query_ids must contain integer IDs'}), 400

    requested = data.get('cluster', None)
    if requested is None or requested == '':
        target_cluster = None
    else:
        target_cluster = _normalize_cluster_name(requested)
        if not target_cluster:
            return jsonify({'error': 'Invalid cluster name'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT prompt_clusters FROM llm_monitoring_projects WHERE id = %s",
            (project_id,)
        )
        project_row = cur.fetchone()
        if not project_row:
            return jsonify({'error': 'Project not found'}), 404

        if target_cluster is not None:
            raw_config = project_row.get('prompt_clusters') or {}
            if isinstance(raw_config, str):
                try:
                    raw_config = json.loads(raw_config)
                except (json.JSONDecodeError, TypeError):
                    raw_config = {}
            cluster_names = {
                (c.get('name') or '').lower()
                for c in (raw_config.get('clusters') or [])
                if isinstance(c, dict)
            }
            if target_cluster.lower() not in cluster_names:
                return jsonify({
                    'error': f"Cluster '{target_cluster}' is not defined for this project"
                }), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET topic_cluster = %s
            WHERE project_id = %s AND id = ANY(%s)
        """, (target_cluster, project_id, query_ids))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'updated': updated,
            'topic_cluster': target_cluster
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error en bulk-cluster: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update clusters. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# PROMPT SETS (núcleo / tendencia / estacionales)
# El set "núcleo" es implícito (prompt_set = NULL): siempre existe,
# siempre activo. Los sets adicionales viven en projects.prompt_sets
# y pueden llevar ventana estacional UTC (ver services/llm_monitoring/
# prompt_sets.py). Espejo del patrón de clusters de arriba.
# ═══════════════════════════════════════════════════════════════════

CORE_SET_KEY = 'core'


def _load_sets_config(cur, project_id, for_update=False):
    """Lee y parsea prompt_sets del proyecto. Devuelve None si el proyecto no existe."""
    lock = ' FOR UPDATE' if for_update else ''
    cur.execute(
        f"SELECT prompt_sets FROM llm_monitoring_projects WHERE id = %s{lock}",
        (project_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    return prompt_sets_lib.parse_sets_config(row.get('prompt_sets'))


def _resolve_set_assignment(requested, sets_config):
    """
    Resuelve el valor entrante de un assignment de set a valor de columna.

    'core'/None/'' → None (núcleo). Otro nombre → debe existir en la config.
    Returns (ok, value_or_error): si ok, value es None o el nombre canónico.
    """
    if requested is None or requested == '' or \
            str(requested).strip().lower() in prompt_sets_lib.RESERVED_CORE_NAMES:
        return True, None
    name = prompt_sets_lib.normalize_set_name(requested)
    if not name:
        return False, 'Invalid set name'
    defined = {n.lower(): n for n in prompt_sets_lib.get_defined_set_names(sets_config)}
    canonical = defined.get(name.lower())
    if not canonical:
        return False, f"Set '{name}' is not defined for this project"
    return True, canonical


@llm_monitoring_bp.route('/projects/<int:project_id>/sets', methods=['GET'])
@login_required
@validate_project_ownership
def get_project_sets(project_id):
    """
    Devuelve la configuración de sets del proyecto + conteo de prompts por set
    + si cada ventana está activa hoy (día UTC).

    Returns:
        {
            "success": true,
            "sets_config": {"enabled": bool, "sets": [{"name", "window"?}]},
            "counts": {"core": 59, "Black Friday": 12},
            "active_today": {"core": true, "Black Friday": false}
        }
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        cur.execute("""
            SELECT COALESCE(prompt_set, %s) AS set_name, COUNT(*) AS cnt
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
            GROUP BY COALESCE(prompt_set, %s)
        """, (CORE_SET_KEY, project_id, CORE_SET_KEY))
        counts = {r['set_name']: int(r['cnt']) for r in cur.fetchall()}

        active_today = {CORE_SET_KEY: True}
        for entry in (cfg.get('sets') or []):
            if isinstance(entry, dict) and entry.get('name'):
                active_today[entry['name']] = prompt_sets_lib.is_window_active(
                    entry.get('window')
                )

        # enabled_llms viaja aquí porque la barra de filtros global se pinta
        # ANTES de que el detalle del proyecto esté cargado.
        cur.execute(
            "SELECT enabled_llms FROM llm_monitoring_projects WHERE id = %s",
            (project_id,)
        )
        llms_row = cur.fetchone() or {}

        return jsonify({
            'success': True,
            'sets_config': cfg,
            'counts': counts,
            'active_today': active_today,
            'enabled_llms': llms_row.get('enabled_llms') or []
        }), 200

    except Exception as e:
        logger.error(f"Error obteniendo sets: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load sets. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/sets', methods=['PUT'])
@login_required
@validate_project_ownership
def update_project_sets(project_id):
    """
    Actualiza la configuración de sets del proyecto.

    Body:
        {"sets_config": {"enabled": bool,
                         "sets": [{"name": "...", "window": {"start": "MM-DD", "end": "MM-DD"}|null}]}}

    Comportamiento (espejo de clusters):
    - Guarda el array canónico en llm_monitoring_projects.prompt_sets.
    - Si un set ha sido ELIMINADO (o se deshabilita la feature), los prompts
      con ese prompt_set vuelven a NULL (núcleo) — nunca se borran prompts.
    """
    data = request.get_json() or {}
    raw_config = data.get('sets_config')
    if raw_config is None:
        return jsonify({'error': 'sets_config is required'}), 400

    try:
        sanitized, names_in_order = prompt_sets_lib.sanitize_prompt_sets_config(raw_config)
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        if _load_sets_config(cur, project_id, for_update=True) is None:
            return jsonify({'error': 'Project not found'}), 404

        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_sets = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(sanitized), project_id))

        # Prompts de sets eliminados (o feature deshabilitada) → núcleo
        if not sanitized['enabled'] or not names_in_order:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET prompt_set = NULL
                WHERE project_id = %s AND prompt_set IS NOT NULL
            """, (project_id,))
            reassigned = cur.rowcount
        else:
            cur.execute("""
                UPDATE llm_monitoring_queries
                SET prompt_set = NULL
                WHERE project_id = %s
                  AND prompt_set IS NOT NULL
                  AND NOT (prompt_set = ANY(%s))
            """, (project_id, names_in_order))
            reassigned = cur.rowcount

        conn.commit()

        return jsonify({
            'success': True,
            'sets_config': sanitized,
            'reassigned_to_core': reassigned
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando sets: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save sets. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/sets/rename', methods=['POST'])
@login_required
@validate_project_ownership
def rename_project_set(project_id):
    """
    Renombra un set: actualiza la config del proyecto y todos los prompts asignados.

    Body: {"old_name": "...", "new_name": "..."}
    """
    data = request.get_json() or {}
    old_name = prompt_sets_lib.normalize_set_name(data.get('old_name'))
    new_name = prompt_sets_lib.normalize_set_name(data.get('new_name'))

    if not old_name or not new_name:
        return jsonify({'error': 'old_name and new_name are required'}), 400
    if new_name.lower() in prompt_sets_lib.RESERVED_CORE_NAMES:
        return jsonify({'error': f'"{new_name}" is reserved for the core set'}), 400
    if old_name == new_name:
        return jsonify({'success': True, 'updated_prompts': 0}), 200

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id, for_update=True)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        sets_list = [s for s in (cfg.get('sets') or []) if isinstance(s, dict)]
        existing_lower = {s.get('name', '').lower() for s in sets_list}

        if old_name.lower() not in existing_lower:
            return jsonify({'error': f"Set '{old_name}' not found"}), 404
        if new_name.lower() in existing_lower and new_name.lower() != old_name.lower():
            return jsonify({'error': f"A set named '{new_name}' already exists"}), 409

        for s in sets_list:
            if s.get('name', '').lower() == old_name.lower():
                s['name'] = new_name
        cfg['sets'] = sets_list

        cur.execute("""
            UPDATE llm_monitoring_projects
            SET prompt_sets = %s::jsonb, updated_at = NOW()
            WHERE id = %s
        """, (json.dumps(cfg), project_id))

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET prompt_set = %s
            WHERE project_id = %s AND prompt_set = %s
        """, (new_name, project_id, old_name))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'sets_config': cfg,
            'updated_prompts': updated
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error renombrando set: {e}", exc_info=True)
        return jsonify({'error': 'Failed to rename set. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>/set', methods=['PUT'])
@login_required
@validate_project_ownership
def assign_query_set(project_id, query_id):
    """
    Asigna un set a un prompt concreto.

    Body: {"set": "Black Friday"}  o  {"set": null|"core"}  para volver a núcleo.
    """
    data = request.get_json() or {}

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        ok, target = _resolve_set_assignment(data.get('set', None), cfg)
        if not ok:
            return jsonify({'error': target}), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET prompt_set = %s
            WHERE id = %s AND project_id = %s
            RETURNING id, prompt_set
        """, (target, query_id, project_id))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Prompt not found'}), 404

        conn.commit()
        return jsonify({
            'success': True,
            'query_id': row['id'],
            'prompt_set': row['prompt_set']
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error asignando set a query: {e}", exc_info=True)
        return jsonify({'error': 'Failed to assign set. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/bulk-set', methods=['POST'])
@login_required
@validate_project_ownership
def bulk_assign_set(project_id):
    """
    Asigna un mismo set a varios prompts en una sola llamada.

    Body: {"query_ids": [1,2,3], "set": "Black Friday" | null | "core"}
    """
    data = request.get_json() or {}
    query_ids = data.get('query_ids') or []
    if not isinstance(query_ids, list) or not query_ids:
        return jsonify({'error': 'query_ids must be a non-empty list'}), 400
    query_ids = [int(q) for q in query_ids if isinstance(q, (int, str)) and str(q).isdigit()][:500]
    if not query_ids:
        return jsonify({'error': 'query_ids must contain integer IDs'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()
        cfg = _load_sets_config(cur, project_id)
        if cfg is None:
            return jsonify({'error': 'Project not found'}), 404

        ok, target = _resolve_set_assignment(data.get('set', None), cfg)
        if not ok:
            return jsonify({'error': target}), 400

        cur.execute("""
            UPDATE llm_monitoring_queries
            SET prompt_set = %s
            WHERE project_id = %s AND id = ANY(%s)
        """, (target, project_id, query_ids))
        updated = cur.rowcount

        conn.commit()
        return jsonify({
            'success': True,
            'updated': updated,
            'prompt_set': target
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Error en bulk-set: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update sets. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/clusters/metrics', methods=['GET'])
@login_required
@validate_project_ownership
def get_clusters_metrics(project_id):
    """
    Devuelve métricas agregadas por cluster (Share of Voice + Avg Position)
    para el gráfico de barras que sustituye a "LLM Comparison".

    Query params:
        - days: ventana temporal (default 30)
        - metric: "weighted" | "classic"  (default "weighted")

    Excluye prompts sin cluster (topic_cluster IS NULL).
    Los cálculos se hacen on-the-fly a partir de llm_monitoring_results.
    """
    days = _normalize_days_param(request.args.get('days'), default=30)
    metric = (request.args.get('metric') or 'weighted').lower()
    if metric not in ('weighted', 'classic'):
        metric = 'weighted'
    # Aplica set/branded/llms; el filtro de clusters se ignora aquí a propósito
    # (este endpoint ya desglosa por cluster)
    report_filters = _parse_report_filters(request.args)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT prompt_clusters, enabled_llms
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        project = cur.fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        raw_config = project.get('prompt_clusters') or {}
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except (json.JSONDecodeError, TypeError):
                raw_config = {}
        enabled = bool(raw_config.get('enabled'))
        defined_clusters = [
            c.get('name') for c in (raw_config.get('clusters') or [])
            if isinstance(c, dict) and c.get('name')
        ]
        enabled_llms = _narrow_llms(project.get('enabled_llms') or [], report_filters)

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # Pull per-result rows (only for prompts with cluster assigned)
        filtered_query_ids = _resolve_filtered_query_ids(
            cur, project_id, report_filters, include_clusters=False,
            start_date=start_date, end_date=end_date
        )
        params = [project_id, start_date, end_date]
        ids_filter = ''
        if filtered_query_ids is not None:
            ids_filter = 'AND r.query_id = ANY(%s)'
            params.append(filtered_query_ids)
        llm_filter = ''
        if enabled_llms:
            llm_filter = 'AND r.llm_provider = ANY(%s)'
            params.append(enabled_llms)

        cur.execute(f"""
            SELECT
                q.topic_cluster AS cluster,
                r.brand_mentioned,
                r.position_in_list,
                r.competitors_mentioned
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON q.id = r.query_id
            WHERE r.project_id = %s
              AND r.analysis_date >= %s
              AND r.analysis_date <= %s
              AND q.topic_cluster IS NOT NULL
              {ids_filter}
              {llm_filter}
        """, params)
        rows = cur.fetchall() or []

        MAX_POSITION = 30

        # Init buckets for every defined cluster so the chart still shows them
        # as empty bars (0) instead of being missing.
        buckets = {
            name: {
                'total_results': 0,
                'brand_mentions': 0,
                'competitor_mentions': 0,
                'weighted_brand': 0.0,
                'weighted_competitors': 0.0,
                'positions': []
            }
            for name in defined_clusters
        }

        for r in rows:
            cluster = r.get('cluster')
            if not cluster or cluster not in buckets:
                continue
            b = buckets[cluster]
            b['total_results'] += 1
            position = r.get('position_in_list')

            # Brand contribution
            if r.get('brand_mentioned'):
                b['brand_mentions'] += 1
                b['weighted_brand'] += _weight_for_position(position)

            # Competitor contribution
            cm = r.get('competitors_mentioned') or {}
            if isinstance(cm, str):
                try:
                    cm = json.loads(cm)
                except (json.JSONDecodeError, TypeError):
                    cm = {}
            if isinstance(cm, dict):
                for _comp, count in cm.items():
                    try:
                        count_int = int(count)
                    except (TypeError, ValueError):
                        continue
                    if count_int > 0:
                        b['competitor_mentions'] += 1
                        b['weighted_competitors'] += _weight_for_position(position)

            # Positions (filtered)
            if position is not None and position <= MAX_POSITION:
                b['positions'].append(position)

        clusters_out = []
        for name in defined_clusters:
            b = buckets[name]
            if metric == 'weighted':
                denom = b['weighted_brand'] + b['weighted_competitors']
                sov = round((b['weighted_brand'] / denom) * 100, 1) if denom > 0 else 0.0
            else:
                denom = b['brand_mentions'] + b['competitor_mentions']
                sov = round((b['brand_mentions'] / denom) * 100, 1) if denom > 0 else 0.0

            avg_pos = None
            if b['positions']:
                avg_pos = round(sum(b['positions']) / len(b['positions']), 1)

            clusters_out.append({
                'cluster': name,
                'total_results': b['total_results'],
                'brand_mentions': b['brand_mentions'],
                'competitor_mentions': b['competitor_mentions'],
                'share_of_voice': sov,
                'avg_position': avg_pos,
                'has_data': b['total_results'] > 0
            })

        # Sort: clusters with data first (by SoV desc), then empty clusters
        clusters_out.sort(
            key=lambda c: (
                -1 if c['has_data'] else 1,
                -(c['share_of_voice'] or 0),
                c['cluster']
            )
        )

        return jsonify({
            'success': True,
            'enabled': enabled,
            'metric': metric,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'clusters': clusters_out,
            'total_clusters_defined': len(defined_clusters)
        }), 200

    except Exception as e:
        logger.error(f"Error calculando métricas de clusters: {e}", exc_info=True)
        return jsonify({'error': 'Failed to compute cluster metrics. Please try again.'}), 500
    finally:
        cur.close()
        conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/<int:query_id>/history', methods=['GET'])
@login_required
@validate_project_ownership
def get_query_history(project_id, query_id):
    """
    ✨ NUEVO: Obtiene el historial de visibilidad de un prompt/query específico
    para mostrar la evolución temporal en una gráfica.
    
    Query params:
        - days: Número de días de historial (default: 30, usa el time range global)
    
    Returns:
        JSON con historial de menciones por fecha y LLM
    """
    # ✨ Obtener parámetro days del time range global (normalizado como el resto)
    days = _normalize_days_param(request.args.get('days'), default=30)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    cur = None
    try:
        cur = conn.cursor()
        
        # Verificar que la query pertenece al proyecto
        cur.execute("""
            SELECT q.id, q.query_text, p.enabled_llms
            FROM llm_monitoring_queries q
            JOIN llm_monitoring_projects p ON q.project_id = p.id
            WHERE q.id = %s AND q.project_id = %s
        """, (query_id, project_id))
        
        query = cur.fetchone()
        
        if not query:
            return jsonify({'error': 'Prompt not found', 'success': False}), 404
        
        logger.info(f"📊 Fetching history for query {query_id} ('{query['query_text'][:30]}...') - last {days} days")
        
        # Obtener historial de resultados para esta query
        enabled_llms_filter = query.get('enabled_llms') or []
        history_query = """
            SELECT
                analysis_date,
                llm_provider,
                brand_mentioned,
                position_in_list,
                sentiment
            FROM llm_monitoring_results
            WHERE query_id = %s AND project_id = %s
                AND analysis_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        """
        history_params = [query_id, project_id, days]
        if enabled_llms_filter:
            history_query += " AND llm_provider = ANY(%s)"
            history_params.append(enabled_llms_filter)
        history_query += " ORDER BY analysis_date ASC, llm_provider"
        cur.execute(history_query, history_params)
        
        results = cur.fetchall()
        
        logger.info(f"   → Found {len(results)} result records")
        
        # Si no hay resultados, retornar lista vacía con éxito
        if not results:
            return jsonify({
                'success': True,
                'query_id': query_id,
                'query_text': query['query_text'],
                'history': [],
                'llm_providers': [],
                'total_data_points': 0,
                'days': days,
                'message': 'No historical data found for this query in the selected period'
            }), 200
        
        # Agrupar resultados por fecha
        history_by_date = {}
        llm_providers_set = set()
        
        for row in results:
            date_str = row['analysis_date'].isoformat() if row['analysis_date'] else None
            if not date_str:
                continue
                
            llm = row['llm_provider']
            llm_providers_set.add(llm)
            
            if date_str not in history_by_date:
                history_by_date[date_str] = {
                    'date': date_str,
                    'total_llms': 0,
                    'llms_mentioned': 0,
                    'visibility_rate': 0,
                    'by_llm': {}
                }
            
            history_by_date[date_str]['total_llms'] += 1
            if row['brand_mentioned']:
                history_by_date[date_str]['llms_mentioned'] += 1
            
            history_by_date[date_str]['by_llm'][llm] = {
                'mentioned': row['brand_mentioned'] or False,
                'position': row['position_in_list'],
                'sentiment': row['sentiment']
            }
        
        # Calcular visibility_rate por fecha
        for date_str, data in history_by_date.items():
            if data['total_llms'] > 0:
                data['visibility_rate'] = round(
                    (data['llms_mentioned'] / data['total_llms']) * 100, 1
                )
        
        # Convertir a lista ordenada por fecha
        history_list = sorted(
            list(history_by_date.values()),
            key=lambda x: x['date']
        )
        
        # Obtener lista de LLMs únicos para la leyenda del gráfico
        llm_providers = sorted(list(llm_providers_set))
        
        logger.info(f"   ✅ Returning {len(history_list)} data points for {len(llm_providers)} LLMs")
        
        return jsonify({
            'success': True,
            'query_id': query_id,
            'query_text': query['query_text'],
            'history': history_list,
            'llm_providers': llm_providers,
            'total_data_points': len(history_list),
            'days': days
        }), 200
        
    except Exception as e:
        logger.error(f"Error obteniendo historial de query: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load data. Please try again.', 'success': False}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/suggest', methods=['POST'])
@login_required
@validate_project_ownership
def suggest_queries(project_id):
    """
    Genera sugerencias de queries usando IA (Gemini Flash)
    
    Analiza los prompts existentes del proyecto y el contexto (marca, industria)
    para sugerir prompts adicionales relevantes usando Gemini Flash.
    
    Body opcional:
    {
        "count": 10  (número de sugerencias, default: 10, max: 20)
    }
    
    Returns:
        JSON con lista de sugerencias generadas por IA
    """
    user = get_current_user()
    
    data = request.get_json() or {}
    count = min(data.get('count', 10), 20)  # Máximo 20 sugerencias
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    cur = None
    try:
        cur = conn.cursor()

        # Obtener datos del proyecto
        cur.execute("""
            SELECT name, brand_name, industry, language, competitors
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Obtener queries existentes
        cur.execute("""
            SELECT query_text
            FROM llm_monitoring_queries
            WHERE project_id = %s AND is_active = TRUE
            ORDER BY added_at DESC
            LIMIT 20
        """, (project_id,))
        
        existing_queries = cur.fetchall()
        existing_queries_list = [q['query_text'] for q in existing_queries]

        # Generar sugerencias usando IA
        from services.llm_monitoring_service import generate_query_suggestions_with_ai
        
        logger.info(f"🤖 Generando sugerencias para proyecto {project_id}: {project['brand_name']}")
        logger.info(f"   - Industria: {project['industry']}")
        logger.info(f"   - Queries existentes: {len(existing_queries_list)}")
        logger.info(f"   - Competidores: {project['competitors']}")
        
        suggestions = generate_query_suggestions_with_ai(
            brand_name=project['brand_name'],
            industry=project['industry'],
            language=project['language'],
            existing_queries=existing_queries_list,
            competitors=project['competitors'] or [],
            count=count
        )
        
        if not suggestions:
            logger.warning(f"⚠️ No se generaron sugerencias para proyecto {project_id}")
            # Verificar si es por falta de API key
            import os
            if not os.getenv('GOOGLE_API_KEY'):
                return jsonify({
                    'success': False,
                    'error': 'GOOGLE_API_KEY is not configured on the server',
                    'hint': 'Contacta al administrador para configurar las API keys'
                }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate suggestions. The Gemini API may be experiencing issues.',
                    'hint': 'Intenta de nuevo en unos momentos'
                }), 500
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'count': len(suggestions),
            'message': f'{len(suggestions)} sugerencias generadas por IA'
        }), 200
        
    except Exception as e:
        logger.error(f"Error generando sugerencias: {e}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'hint': 'Verifica que GOOGLE_API_KEY esté configurada'
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


@llm_monitoring_bp.route('/projects/<int:project_id>/queries/suggest-variations', methods=['POST'])
@login_required
@validate_project_ownership
def suggest_query_variations(project_id):
    """
    ✨ NUEVO: Genera variaciones rápidas de prompts existentes usando IA
    
    Body:
    {
        "existing_prompts": ["prompt1", "prompt2"],
        "count": 6
    }
    
    Returns:
        JSON con lista de variaciones sugeridas
    """
    data = request.get_json() or {}
    existing_prompts = data.get('existing_prompts', [])
    count = min(data.get('count', 6), 10)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Service temporarily unavailable. Please try again.'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener datos del proyecto
        cur.execute("""
            SELECT brand_name, industry, language, competitors
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        cur.close()
        conn.close()
        
        brand_name = project['brand_name']
        industry = project['industry'] or 'general'
        competitors = project['competitors'] or []
        
        language = (project['language'] or 'en').lower()

        # Intentar generar con IA usando el provider configurado en BD (sin modelo hardcodeado)
        try:
            from services.llm_monitoring_service import generate_query_suggestions_with_ai

            suggestions = generate_query_suggestions_with_ai(
                brand_name=brand_name,
                industry=industry,
                language=language,
                existing_queries=existing_prompts,
                competitors=competitors,
                count=count
            )
            if suggestions:
                return jsonify({
                    'success': True,
                    'suggestions': suggestions,
                    'source': 'ai'
                }), 200

        except Exception as ai_error:
            logger.warning(f"AI generation failed, using fallback: {ai_error}")
        
        # Fallback: Generate simple variations locally with randomization
        import random
        
        competitor_fallback = {
            'es': 'competidores',
            'it': 'concorrenti',
            'fr': 'concurrents',
            'de': 'Wettbewerber',
            'pt': 'concorrentes',
        }
        comp_name = competitors[0] if competitors else competitor_fallback.get(language, 'competitors')
        
        if language == 'es':
            all_variations = [
                f"¿Qué es {brand_name} y cómo funciona?",
                f"Mejores herramientas de {industry}",
                f"{brand_name} vs {comp_name} comparativa",
                f"¿Vale la pena {brand_name}? Opiniones",
                f"Alternativas a {brand_name}",
                f"Cómo empezar con {brand_name}",
                f"Precios y planes de {brand_name}",
                f"Las mejores soluciones de {industry}",
                f"Opiniones sobre {brand_name}",
                f"¿Qué opinan de {brand_name}?",
                f"Ventajas y desventajas de {brand_name}",
                f"¿Recomiendan {brand_name}?",
                f"Tutorial de {brand_name}",
                f"Características de {brand_name}",
                f"¿Es bueno {brand_name}?",
                f"Empresas que usan {brand_name}",
                f"Comparativa de {industry}",
                f"Top {industry} en 2024",
                f"¿Cuál es mejor {brand_name} o {comp_name}?",
                f"Experiencias con {brand_name}"
            ]
        elif language == 'it':
            all_variations = [
                f"Cos'è {brand_name} e come funziona?",
                f"Migliori strumenti di {industry}",
                f"Confronto {brand_name} vs {comp_name}",
                f"{brand_name} vale la pena? Recensioni",
                f"Alternative a {brand_name}",
                f"Come iniziare con {brand_name}",
                f"Prezzi e piani di {brand_name}",
                f"Opinioni su {brand_name}",
                f"Pro e contro di {brand_name}",
                f"{brand_name} per principianti"
            ]
        elif language == 'fr':
            all_variations = [
                f"Qu'est-ce que {brand_name} et comment ça marche ?",
                f"Meilleurs outils de {industry}",
                f"Comparatif {brand_name} vs {comp_name}",
                f"{brand_name} vaut-il le coup ? Avis",
                f"Alternatives à {brand_name}",
                f"Comment démarrer avec {brand_name}",
                f"Tarifs et offres de {brand_name}",
                f"Avis sur {brand_name}",
                f"Avantages et inconvénients de {brand_name}",
                f"{brand_name} pour débutants"
            ]
        elif language == 'de':
            all_variations = [
                f"Was ist {brand_name} und wie funktioniert es?",
                f"Beste {industry}-Tools",
                f"{brand_name} vs {comp_name} Vergleich",
                f"Lohnt sich {brand_name}? Erfahrungen",
                f"Alternativen zu {brand_name}",
                f"Wie startet man mit {brand_name}?",
                f"Preise und Pakete von {brand_name}",
                f"Bewertungen zu {brand_name}",
                f"Vor- und Nachteile von {brand_name}",
                f"{brand_name} für Einsteiger"
            ]
        elif language == 'pt':
            all_variations = [
                f"O que é {brand_name} e como funciona?",
                f"Melhores ferramentas de {industry}",
                f"Comparativo {brand_name} vs {comp_name}",
                f"{brand_name} vale a pena? Avaliações",
                f"Alternativas ao {brand_name}",
                f"Como começar com {brand_name}",
                f"Preços e planos do {brand_name}",
                f"Opiniões sobre {brand_name}",
                f"Prós e contras do {brand_name}",
                f"{brand_name} para iniciantes"
            ]
        else:
            all_variations = [
                f"What is {brand_name} and how does it work?",
                f"Best {industry} tools and platforms",
                f"{brand_name} vs {comp_name} comparison",
                f"Is {brand_name} worth it? Reviews",
                f"Alternatives to {brand_name}",
                f"How to get started with {brand_name}",
                f"{brand_name} pricing and plans",
                f"Top rated {industry} solutions",
                f"{brand_name} reviews and opinions",
                f"Pros and cons of {brand_name}",
                f"Would you recommend {brand_name}?",
                f"{brand_name} tutorial",
                f"{brand_name} features",
                f"Is {brand_name} good?",
                f"Companies using {brand_name}",
                f"Best {industry} comparison",
                f"Top {industry} in 2024",
                f"Which is better {brand_name} or {comp_name}?",
                f"User experiences with {brand_name}",
                f"{brand_name} for beginners"
            ]
        
        # Shuffle and pick random variations
        random.shuffle(all_variations)
        variations = all_variations
        
        # Filter out existing prompts
        existing_lower = [p.lower() for p in existing_prompts]
        suggestions = [v for v in variations if v.lower() not in existing_lower][:count]
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'source': 'fallback'
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating variations: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'success': False}), 500
    finally:
        pass  # Connection already closed
