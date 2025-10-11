"""
Servicio para análisis diario automático (Cron Jobs)
"""

import logging
import json
import time
from datetime import date
from database import get_db_connection
from ai_mode_projects.config import CRON_LOCK_CLASS_ID
from ai_mode_projects.utils.helpers import now_utc_iso
from ai_mode_projects.services.analysis_service import AnalysisService
from ai_mode_projects.models.result_repository import ResultRepository
from ai_mode_projects.models.event_repository import EventRepository

logger = logging.getLogger(__name__)


class CronService:
    """Servicio para ejecutar análisis diario automático de todos los proyectos"""
    
    def __init__(self):
        self.analysis_service = AnalysisService()
        self.result_repo = ResultRepository()
        self.event_repo = EventRepository()
    
    def run_daily_analysis_for_all_projects(self):
        """
        Ejecutar análisis diario para todos los proyectos activos.
        Esta función está destinada a ser ejecutada por cron job diario.
        
        Returns:
            Dict con estadísticas de la ejecución
        """
        job_id = f"cron-{int(time.time())}"
        started_at = time.time()
        logger.info(json.dumps({
            "event": "cron_start",
            "job_id": job_id,
            "ts": now_utc_iso()
        }))

        # Lock de concurrencia por día (PostgreSQL advisory lock)
        lock_conn = None
        lock_cur = None
        lock_acquired = False
        lock_class_id = CRON_LOCK_CLASS_ID
        lock_object_id = int(date.today().strftime('%Y%m%d'))

        try:
            lock_conn = get_db_connection()
            if not lock_conn:
                logger.error("❌ No se pudo conectar a la base de datos para adquirir el lock")
                return {"success": False, "error": "DB connection failed for lock"}
            
            lock_cur = lock_conn.cursor()
            lock_cur.execute("SELECT pg_try_advisory_lock(%s, %s) as lock_acquired", 
                           (lock_class_id, lock_object_id))
            result = lock_cur.fetchone()
            lock_acquired = bool(result['lock_acquired']) if result else False
            
            logger.info(f"🔐 Advisory lock attempt: class_id={lock_class_id}, "
                       f"object_id={lock_object_id}, acquired={lock_acquired}")

            if not lock_acquired:
                logger.info(json.dumps({
                    "event": "cron_skipped_lock",
                    "job_id": job_id,
                    "ts": now_utc_iso()
                }))
                lock_cur.close()
                lock_conn.close()
                return {
                    "success": True,
                    "message": "Another daily run in progress (skipped)",
                    "skipped": 0,
                    "failed": 0,
                    "successful": 0,
                    "total_projects": 0
                }
            
            logger.info("✅ Advisory lock adquirido exitosamente. Continuando con análisis...")
            
            # Obtener todos los proyectos activos
            projects = self._get_active_projects()
            
            if not projects:
                logger.info("⏭️ No active projects found for daily analysis")
                return {"success": True, "message": "No active projects", "processed": 0}
            
            logger.info(json.dumps({
                "event": "cron_projects_found",
                "job_id": job_id,
                "count": len(projects)
            }))
            
            # Log de proyectos encontrados
            for i, project in enumerate(projects):
                project_data = project if isinstance(project, dict) else {
                    'id': project[0], 'name': project[1], 'domain': project[2],
                    'country_code': project[3], 'user_id': project[4], 'keyword_count': project[5]
                }
                logger.info(f"📋 Project {i+1}: ID={project_data['id']}, "
                          f"Name='{project_data['name']}', Domain='{project_data['domain']}', "
                          f"Keywords={project_data['keyword_count']}")
            
            # Procesar cada proyecto
            stats = self._process_projects(projects)
            
            # Liberar lock
            lock_cur.execute("SELECT pg_advisory_unlock(%s, %s)", (lock_class_id, lock_object_id))
            lock_cur.close()
            lock_conn.close()
            
            elapsed_time = time.time() - started_at
            
            logger.info(json.dumps({
                "event": "cron_end",
                "job_id": job_id,
                "ts": now_utc_iso(),
                "successful": stats['successful'],
                "failed": stats['failed'],
                "skipped": stats['skipped'],
                "total_keywords": stats['total_keywords'],
                "elapsed_sec": round(elapsed_time, 2)
            }))
            
            return {
                "success": True,
                "job_id": job_id,
                "successful": stats['successful'],
                "failed": stats['failed'],
                "skipped": stats['skipped'],
                "total_keywords": stats['total_keywords'],
                "elapsed_seconds": round(elapsed_time, 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in daily analysis cron: {e}")
            
            # Liberar lock si fue adquirido
            if lock_acquired and lock_cur:
                try:
                    lock_cur.execute("SELECT pg_advisory_unlock(%s, %s)", 
                                   (lock_class_id, lock_object_id))
                except:
                    pass
            
            if lock_cur:
                lock_cur.close()
            if lock_conn:
                lock_conn.close()
            
            return {"success": False, "error": str(e)}
    
    def _get_active_projects(self):
        """Obtener proyectos activos para análisis diario"""
        conn = get_db_connection()
        if not conn:
            logger.error("❌ No se pudo conectar a la base de datos")
            return []
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT p.id, p.name, p.brand_name as domain, p.country_code, p.user_id,
                   COUNT(k.id) as keyword_count
            FROM ai_mode_projects p
            JOIN users u ON u.id = p.user_id
            LEFT JOIN ai_mode_keywords k ON p.id = k.project_id AND k.is_active = true
            WHERE p.is_active = true
              AND COALESCE(u.plan, 'free') <> 'free'
              AND COALESCE(u.billing_status, '') NOT IN ('canceled')
            GROUP BY p.id, p.name, p.brand_name, p.country_code, p.user_id
            HAVING COUNT(k.id) > 0
            ORDER BY p.id
        """)
        
        projects = cur.fetchall()
        cur.close()
        conn.close()
        
        return projects
    
    def _process_projects(self, projects):
        """Procesar lista de proyectos"""
        successful_analyses = 0
        failed_analyses = 0
        skipped_analyses = 0
        total_keywords_processed = 0
        
        for project in projects:
            # Convertir a dict si es necesario
            if isinstance(project, (tuple, list)):
                project_dict = {
                    'id': project[0],
                    'name': project[1],
                    'domain': project[2],
                    'country_code': project[3],
                    'user_id': project[4],
                    'keyword_count': project[5]
                }
            else:
                project_dict = dict(project)
            
            try:
                # Verificar estado del usuario
                conn = get_db_connection()
                cur = conn.cursor()
                
                today = date.today()
                
                # Verificar plan y facturación
                cur.execute("""
                    SELECT COALESCE(plan, 'free') AS plan,
                           COALESCE(billing_status, '') AS billing_status
                    FROM users
                    WHERE id = %s
                """, (project_dict['user_id'],))
                
                user_state = cur.fetchone() or {}
                user_plan = user_state.get('plan', 'free') if isinstance(user_state, dict) else (
                    user_state[0] if user_state else 'free'
                )
                user_billing = user_state.get('billing_status', '') if isinstance(user_state, dict) else (
                    user_state[1] if user_state and len(user_state) > 1 else ''
                )
                
                if user_plan == 'free' or user_billing in ('canceled',):
                    logger.info(f"⏭️ Skipping project {project_dict['id']} due to user "
                              f"plan/billing status (plan={user_plan}, billing={user_billing})")
                    skipped_analyses += 1
                    cur.close()
                    conn.close()
                    continue
                
                # Verificar si ya hay resultados hoy
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM manual_ai_results 
                    WHERE project_id = %s AND analysis_date = %s
                """, (project_dict['id'], today))
                
                result_row = cur.fetchone()
                existing_results = result_row['count'] if result_row else 0
                cur.close()
                conn.close()
                
                if existing_results > 0:
                    logger.info(f"⏭️ Project {project_dict['id']} ({project_dict['name']}) "
                              f"already analyzed today with {existing_results} results, skipping")
                    skipped_analyses += 1
                    continue
                
                logger.info(f"🚀 Starting daily analysis for project {project_dict['id']} "
                          f"({project_dict['name']}) - {project_dict['keyword_count']} keywords")
                
                # Ejecutar análisis automático (sin sobreescritura)
                results = self.analysis_service.run_project_analysis(
                    project_dict['id'],
                    force_overwrite=False,
                    user_id=project_dict['user_id']
                )
                
                total_keywords_processed += len(results)
                
                # Crear snapshot diario
                self.result_repo.create_snapshot(
                    project_id=project_dict['id'],
                    snapshot_date=today,
                    metrics=self._calculate_snapshot_metrics(project_dict['id'])
                )
                
                # Crear evento
                self.event_repo.create_event(
                    project_id=project_dict['id'],
                    event_type='daily_analysis',
                    event_title='Daily automated analysis completed',
                    keywords_affected=len(results),
                    user_id=project_dict['user_id']
                )
                
                logger.info(f"✅ Completed daily analysis for project {project_dict['id']}: "
                          f"{len(results)} keywords processed")
                successful_analyses += 1
                
            except Exception as e:
                logger.error(f"❌ Error analyzing project {project_dict['id']}: {e}")
                failed_analyses += 1
                continue
        
        return {
            'successful': successful_analyses,
            'failed': failed_analyses,
            'skipped': skipped_analyses,
            'total_keywords': total_keywords_processed
        }
    
    def _calculate_snapshot_metrics(self, project_id: int) -> dict:
        """Calcular métricas para snapshot diario"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            today = date.today()
            
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT k.id) as total_keywords,
                    COUNT(DISTINCT CASE WHEN k.is_active = true THEN k.id END) as active_keywords,
                    COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN k.id END) as keywords_with_ai,
                    COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN k.id END) as domain_mentions,
                    AVG(CASE WHEN r.domain_mentioned = true THEN r.domain_position END) as avg_position,
                    (COUNT(DISTINCT CASE WHEN r.domain_mentioned = true THEN k.id END)::float /
                     NULLIF(COUNT(DISTINCT CASE WHEN r.has_ai_overview = true THEN k.id END), 0)::float * 100) as visibility_percentage
                FROM manual_ai_keywords k
                LEFT JOIN manual_ai_results r ON k.id = r.keyword_id AND r.analysis_date = %s
                WHERE k.project_id = %s
            """, (today, project_id))
            
            result = cur.fetchone()
            
            return dict(result) if result else {}
            
        except Exception as e:
            logger.error(f"Error calculating snapshot metrics: {e}")
            return {}
        finally:
            cur.close()
            conn.close()


# Función de compatibilidad para importación directa
def run_daily_analysis_for_all_projects():
    """Wrapper para compatibilidad con código legacy"""
    service = CronService()
    return service.run_daily_analysis_for_all_projects()

