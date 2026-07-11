"""
Servicio para análisis diario automático (Cron Jobs)
"""

import logging
import json
import time
from datetime import date
from database import get_db_connection
from manual_ai.config import CRON_LOCK_CLASS_ID
from manual_ai.utils.helpers import now_utc_iso
from manual_ai.services.analysis_service import AnalysisService
from manual_ai.models.result_repository import ResultRepository
from manual_ai.models.event_repository import EventRepository

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

            # ✨ NUEVO (2026-04-09): Las advisory locks de Postgres son session-level,
            # no transaction-level. Activando autocommit evitamos que lock_conn quede
            # idle-in-transaction durante el procesamiento, lo que eliminaría el riesgo
            # de que idle_in_transaction_session_timeout (15 min, hardening del 2026-04-08)
            # mate la conn a mitad de tanda y libere la advisory lock, permitiendo que
            # otro cron arranque en paralelo. Tandas con 40-60 proyectos pueden durar
            # >15 min, así que sin este cambio el riesgo es real.
            lock_conn.autocommit = True

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
                # Liberar el advisory lock y devolver la conexión al pool también en
                # este early-return: la conexión es pooled (close() no cierra la sesión),
                # así que sin unlock explícito el lock quedaría retenido indefinidamente.
                lock_cur.execute("SELECT pg_advisory_unlock(%s, %s)", (lock_class_id, lock_object_id))
                lock_acquired = False
                lock_cur.close()
                lock_conn.close()
                result = {"success": True, "message": "No active projects", "processed": 0,
                          "job_id": job_id}
                self._send_completion_email(result)
                return result
            
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
            
            result = {
                "success": True,
                "job_id": job_id,
                "successful": stats['successful'],
                "failed": stats['failed'],
                "skipped": stats['skipped'],
                "total_keywords": stats['total_keywords'],
                "elapsed_seconds": round(elapsed_time, 2)
            }
            self._send_completion_email(result)
            return result

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

            result = {"success": False, "error": str(e), "job_id": job_id}
            self._send_completion_email(result)
            return result

    @staticmethod
    def _send_completion_email(stats):
        """Email de resumen del run (OK/WARNING/CRITICAL). Nunca afecta al run."""
        try:
            from cron_alerts import send_simple_run_completion_email
            send_simple_run_completion_email('Manual AI (AI Overview)', stats)
        except Exception as e:
            logger.warning(f"Completion email failed (non-fatal): {e}")
    
    def _get_active_projects(self):
        """Obtener proyectos activos para análisis diario.

        Excluye los pausados manualmente (is_active=false) y los pausados
        por cuota cuya ventana paused_until aún no ha expirado.
        """
        conn = get_db_connection()
        if not conn:
            logger.error("❌ No se pudo conectar a la base de datos")
            return []

        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT p.id, p.name, p.domain, p.country_code, p.user_id,
                       COUNT(k.id) as keyword_count
                FROM manual_ai_projects p
                JOIN users u ON u.id = p.user_id
                LEFT JOIN manual_ai_keywords k ON p.id = k.project_id AND k.is_active = true
                WHERE p.is_active = true
                  AND (
                      COALESCE(p.is_paused_by_quota, FALSE) = FALSE
                      OR (p.paused_until IS NOT NULL AND p.paused_until <= NOW())
                  )
                  AND COALESCE(u.plan, 'free') <> 'free'
                  AND COALESCE(u.billing_status, '') NOT IN ('canceled')
                GROUP BY p.id, p.name, p.domain, p.country_code, p.user_id
                HAVING COUNT(k.id) > 0
                ORDER BY p.id
            """)
        except Exception as exc:
            # Fallback for deployments where the quota-pause migration hasn't
            # run yet — the columns simply don't exist, so just filter on is_active.
            logger.warning(
                f"Manual AI cron quota-pause filter unavailable, falling back: {exc}"
            )
            conn.rollback()
            cur.execute("""
                SELECT p.id, p.name, p.domain, p.country_code, p.user_id,
                       COUNT(k.id) as keyword_count
                FROM manual_ai_projects p
                JOIN users u ON u.id = p.user_id
                LEFT JOIN manual_ai_keywords k ON p.id = k.project_id AND k.is_active = true
                WHERE p.is_active = true
                  AND COALESCE(u.plan, 'free') <> 'free'
                  AND COALESCE(u.billing_status, '') NOT IN ('canceled')
                GROUP BY p.id, p.name, p.domain, p.country_code, p.user_id
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
                if not conn:
                    raise Exception("No se pudo conectar a BD")

                cur = None
                existing_results = 0
                user_plan = 'free'
                user_billing = ''
                try:
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
                        continue  # inner finally closes conn before continuing the outer for

                    # Frecuencia de análisis del proyecto (1 = cada tick del cron,
                    # 7 = semanal). Fallback a 1 si la migración no ha corrido.
                    frequency_days = 1
                    try:
                        cur.execute("""
                            SELECT COALESCE(analysis_frequency_days, 1) AS freq
                            FROM manual_ai_projects
                            WHERE id = %s
                        """, (project_dict['id'],))
                        freq_row = cur.fetchone()
                        if freq_row:
                            freq_value = freq_row['freq'] if isinstance(freq_row, dict) else freq_row[0]
                            frequency_days = max(int(freq_value or 1), 1)
                    except Exception:
                        conn.rollback()
                        frequency_days = 1

                    # Verificar si ya hay resultados dentro de la ventana de frecuencia
                    cur.execute("""
                        SELECT COUNT(*) as count
                        FROM manual_ai_results
                        WHERE project_id = %s AND analysis_date > %s - %s::integer
                    """, (project_dict['id'], today, frequency_days))

                    result_row = cur.fetchone()
                    existing_results = result_row['count'] if result_row else 0
                finally:
                    # Always return the pooled connection — previously the
                    # outer except (failed_analyses += 1; continue) leaked
                    # conn whenever cur.execute or fetch raised, contributing
                    # to the 2026-05-14 pool exhaustion incident.
                    if cur is not None:
                        try:
                            cur.close()
                        except Exception:
                            pass
                    try:
                        conn.close()
                    except Exception:
                        pass

                if existing_results > 0:
                    logger.info(f"⏭️ Project {project_dict['id']} ({project_dict['name']}) "
                              f"already analyzed within last {frequency_days} day(s) "
                              f"with {existing_results} results, skipping")
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
        if not conn:
            logger.error(f"_calculate_snapshot_metrics({project_id}): no DB connection")
            return {}
        try:
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
            try:
                conn.close()
            except Exception:
                pass


# Función de compatibilidad para importación directa
def run_daily_analysis_for_all_projects():
    """Wrapper para compatibilidad con código legacy"""
    service = CronService()
    return service.run_daily_analysis_for_all_projects()

