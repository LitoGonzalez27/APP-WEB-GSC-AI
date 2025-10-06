"""
Servicio para gestión de Topic Clusters en el sistema Manual AI
"""

import logging
import re
from typing import List, Dict, Optional
from database import get_db_connection

logger = logging.getLogger(__name__)


class ClusterService:
    """Servicio para gestionar clusters temáticos de keywords"""
    
    @staticmethod
    def get_project_clusters(project_id: int) -> Dict:
        """
        Obtener configuración de clusters de un proyecto
        
        Args:
            project_id: ID del proyecto
            
        Returns:
            Dict con configuración de clusters
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT topic_clusters
                FROM manual_ai_projects
                WHERE id = %s
            """, (project_id,))
            
            result = cur.fetchone()
            if result and result['topic_clusters']:
                return result['topic_clusters']
            
            # Valor por defecto si no existe
            return {'enabled': False, 'clusters': []}
            
        except Exception as e:
            logger.error(f"Error getting clusters for project {project_id}: {e}")
            return {'enabled': False, 'clusters': []}
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def update_project_clusters(project_id: int, clusters_config: Dict) -> bool:
        """
        Actualizar configuración de clusters de un proyecto
        
        Args:
            project_id: ID del proyecto
            clusters_config: Configuración de clusters
            
        Returns:
            bool: True si se actualizó correctamente
        """
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            import json
            
            # Validar formato de clusters_config
            if not isinstance(clusters_config, dict):
                logger.error("clusters_config debe ser un diccionario")
                return False
            
            # Asegurar estructura correcta
            if 'enabled' not in clusters_config:
                clusters_config['enabled'] = False
            
            if 'clusters' not in clusters_config:
                clusters_config['clusters'] = []
            
            # Validar cada cluster
            validated_clusters = []
            for cluster in clusters_config.get('clusters', []):
                if not isinstance(cluster, dict):
                    continue
                
                if 'name' not in cluster or 'terms' not in cluster:
                    continue
                
                validated_cluster = {
                    'name': cluster['name'],
                    'terms': cluster['terms'] if isinstance(cluster['terms'], list) else [],
                    'match_method': cluster.get('match_method', 'contains')
                }
                validated_clusters.append(validated_cluster)
            
            clusters_config['clusters'] = validated_clusters
            
            # Actualizar en base de datos
            cur.execute("""
                UPDATE manual_ai_projects
                SET topic_clusters = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(clusters_config), project_id))
            
            conn.commit()
            
            logger.info(f"✅ Clusters updated for project {project_id}: {len(validated_clusters)} clusters, enabled={clusters_config['enabled']}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating clusters for project {project_id}: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def classify_keyword(keyword: str, clusters_config: Dict) -> List[str]:
        """
        Clasificar una keyword en clusters según las reglas definidas
        
        Args:
            keyword: Texto de la keyword
            clusters_config: Configuración de clusters
            
        Returns:
            Lista de nombres de clusters donde clasifica la keyword
        """
        if not clusters_config.get('enabled', False):
            return []
        
        if not keyword:
            return []
        
        keyword_lower = keyword.lower().strip()
        matching_clusters = []
        
        for cluster in clusters_config.get('clusters', []):
            cluster_name = cluster.get('name', '')
            terms = cluster.get('terms', [])
            match_method = cluster.get('match_method', 'contains')
            
            if not cluster_name or not terms:
                continue
            
            # Verificar si la keyword coincide con algún término del cluster
            for term in terms:
                if not term:
                    continue
                
                term_lower = term.lower().strip()
                
                if match_method == 'contains':
                    # Coincidencia si la keyword contiene el término
                    if term_lower in keyword_lower:
                        if cluster_name not in matching_clusters:
                            matching_clusters.append(cluster_name)
                        break
                
                elif match_method == 'exact':
                    # Coincidencia exacta
                    if keyword_lower == term_lower:
                        if cluster_name not in matching_clusters:
                            matching_clusters.append(cluster_name)
                        break
                
                elif match_method == 'starts_with':
                    # Coincidencia si la keyword empieza con el término
                    if keyword_lower.startswith(term_lower):
                        if cluster_name not in matching_clusters:
                            matching_clusters.append(cluster_name)
                        break
                
                elif match_method == 'regex':
                    # Coincidencia por expresión regular
                    try:
                        if re.search(term_lower, keyword_lower, re.IGNORECASE):
                            if cluster_name not in matching_clusters:
                                matching_clusters.append(cluster_name)
                            break
                    except re.error:
                        logger.warning(f"Invalid regex pattern: {term}")
                        continue
        
        return matching_clusters
    
    @staticmethod
    def get_cluster_statistics(project_id: int, days: int = 30) -> Dict:
        """
        Obtener estadísticas de clusters para un proyecto
        
        Args:
            project_id: ID del proyecto
            days: Número de días hacia atrás
            
        Returns:
            Dict con estadísticas de clusters para gráficas y tablas
        """
        from datetime import date, timedelta
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Obtener configuración de clusters
            clusters_config = ClusterService.get_project_clusters(project_id)
            
            if not clusters_config.get('enabled', False):
                return {
                    'enabled': False,
                    'clusters': [],
                    'chart_data': {'labels': [], 'ai_overview': [], 'mentions': []},
                    'table_data': []
                }
            
            # Obtener todas las keywords activas del proyecto con sus últimos resultados
            cur.execute("""
                WITH latest_results AS (
                    SELECT DISTINCT ON (k.id)
                        k.id as keyword_id,
                        k.keyword,
                        r.has_ai_overview,
                        r.domain_mentioned,
                        r.analysis_date
                    FROM manual_ai_keywords k
                    LEFT JOIN manual_ai_results r ON k.id = r.keyword_id
                        AND r.analysis_date >= %s AND r.analysis_date <= %s
                    WHERE k.project_id = %s AND k.is_active = true
                    ORDER BY k.id, r.analysis_date DESC
                )
                SELECT 
                    keyword_id,
                    keyword,
                    has_ai_overview,
                    domain_mentioned
                FROM latest_results
            """, (start_date, end_date, project_id))
            
            keywords_data = cur.fetchall()
            
            # Clasificar cada keyword en clusters
            clusters_stats = {}
            unclassified_keywords = []
            
            # Inicializar estadísticas para cada cluster
            for cluster in clusters_config.get('clusters', []):
                cluster_name = cluster.get('name', '')
                if cluster_name:
                    clusters_stats[cluster_name] = {
                        'name': cluster_name,
                        'total_keywords': 0,
                        'ai_overview_count': 0,
                        'mentions_count': 0,
                        'keywords': []
                    }
            
            # Clasificar keywords y calcular estadísticas
            for kw_data in keywords_data:
                keyword = kw_data['keyword']
                has_ai_overview = kw_data['has_ai_overview'] or False
                domain_mentioned = kw_data['domain_mentioned'] or False
                
                # Clasificar keyword
                matching_clusters = ClusterService.classify_keyword(keyword, clusters_config)
                
                if matching_clusters:
                    # Añadir a todos los clusters que coinciden
                    for cluster_name in matching_clusters:
                        if cluster_name in clusters_stats:
                            clusters_stats[cluster_name]['total_keywords'] += 1
                            clusters_stats[cluster_name]['keywords'].append(keyword)
                            if has_ai_overview:
                                clusters_stats[cluster_name]['ai_overview_count'] += 1
                            if domain_mentioned:
                                clusters_stats[cluster_name]['mentions_count'] += 1
                else:
                    # Keyword no clasificada
                    unclassified_keywords.append({
                        'keyword': keyword,
                        'has_ai_overview': has_ai_overview,
                        'domain_mentioned': domain_mentioned
                    })
            
            # Añadir cluster "Unclassified" si hay keywords sin clasificar
            if unclassified_keywords:
                clusters_stats['Unclassified'] = {
                    'name': 'Unclassified',
                    'total_keywords': len(unclassified_keywords),
                    'ai_overview_count': sum(1 for kw in unclassified_keywords if kw['has_ai_overview']),
                    'mentions_count': sum(1 for kw in unclassified_keywords if kw['domain_mentioned']),
                    'keywords': [kw['keyword'] for kw in unclassified_keywords]
                }
            
            # Preparar datos para la gráfica (barras + línea)
            chart_data = {
                'labels': [],
                'ai_overview': [],
                'mentions': []
            }
            
            # Preparar datos para la tabla
            table_data = []
            
            # Ordenar clusters por nombre (excepto Unclassified al final)
            sorted_clusters = sorted(
                [(name, stats) for name, stats in clusters_stats.items() if name != 'Unclassified'],
                key=lambda x: x[0]
            )
            
            # Añadir Unclassified al final si existe
            if 'Unclassified' in clusters_stats:
                sorted_clusters.append(('Unclassified', clusters_stats['Unclassified']))
            
            for cluster_name, stats in sorted_clusters:
                if stats['total_keywords'] == 0:
                    continue
                
                # Datos para gráfica
                chart_data['labels'].append(cluster_name)
                chart_data['ai_overview'].append(stats['ai_overview_count'])
                chart_data['mentions'].append(stats['mentions_count'])
                
                # Datos para tabla
                ai_overview_pct = (stats['ai_overview_count'] / stats['total_keywords'] * 100) if stats['total_keywords'] > 0 else 0
                mentions_pct = (stats['mentions_count'] / stats['total_keywords'] * 100) if stats['total_keywords'] > 0 else 0
                
                table_data.append({
                    'cluster_name': cluster_name,
                    'total_keywords': stats['total_keywords'],
                    'ai_overview_count': stats['ai_overview_count'],
                    'mentions_count': stats['mentions_count'],
                    'ai_overview_percentage': round(ai_overview_pct, 1),
                    'mentions_percentage': round(mentions_pct, 1)
                })
            
            return {
                'enabled': True,
                'clusters': list(clusters_stats.keys()),
                'chart_data': chart_data,
                'table_data': table_data,
                'total_clusters': len([c for c in clusters_stats.values() if c['total_keywords'] > 0]),
                'date_range': {
                    'start': str(start_date),
                    'end': str(end_date)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting cluster statistics for project {project_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'enabled': False,
                'clusters': [],
                'chart_data': {'labels': [], 'ai_overview': [], 'mentions': []},
                'table_data': [],
                'error': str(e)
            }
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def validate_clusters_config(clusters_config: Dict) -> Dict:
        """
        Validar y sanitizar configuración de clusters
        
        Args:
            clusters_config: Configuración de clusters a validar
            
        Returns:
            Dict con resultado de validación
        """
        errors = []
        warnings = []
        
        if not isinstance(clusters_config, dict):
            return {
                'valid': False,
                'errors': ['clusters_config must be a dictionary'],
                'warnings': []
            }
        
        # Validar campo enabled
        enabled = clusters_config.get('enabled', False)
        if not isinstance(enabled, bool):
            errors.append('enabled must be a boolean')
        
        # Validar clusters
        clusters = clusters_config.get('clusters', [])
        if not isinstance(clusters, list):
            errors.append('clusters must be a list')
        else:
            seen_names = set()
            for i, cluster in enumerate(clusters):
                if not isinstance(cluster, dict):
                    errors.append(f'Cluster at index {i} must be a dictionary')
                    continue
                
                # Validar nombre
                name = cluster.get('name', '')
                if not name or not isinstance(name, str):
                    errors.append(f'Cluster at index {i} must have a valid name')
                elif name in seen_names:
                    errors.append(f'Duplicate cluster name: {name}')
                else:
                    seen_names.add(name)
                
                # Validar términos
                terms = cluster.get('terms', [])
                if not isinstance(terms, list):
                    errors.append(f'Cluster "{name}" terms must be a list')
                elif len(terms) == 0:
                    warnings.append(f'Cluster "{name}" has no terms defined')
                else:
                    for term in terms:
                        if not isinstance(term, str) or not term.strip():
                            errors.append(f'Cluster "{name}" contains invalid terms')
                            break
                
                # Validar método de coincidencia
                match_method = cluster.get('match_method', 'contains')
                valid_methods = ['contains', 'exact', 'starts_with', 'regex']
                if match_method not in valid_methods:
                    errors.append(f'Cluster "{name}" has invalid match_method. Must be one of: {", ".join(valid_methods)}')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

