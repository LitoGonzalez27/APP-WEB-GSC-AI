"""
Servicio de análisis de keywords con AI Overview
Motor principal del sistema Manual AI
"""

import logging
import json
import time
import os
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from database import get_db_connection, pause_manual_ai_projects_for_quota
from auth import get_user_by_id, get_current_user
from quota_manager import get_user_quota_status
from manual_ai.config import MANUAL_AI_KEYWORD_ANALYSIS_COST
from manual_ai.models.project_repository import ProjectRepository
from manual_ai.models.keyword_repository import KeywordRepository
from manual_ai.models.result_repository import ResultRepository
from manual_ai.utils.country_utils import convert_iso_to_internal_country
from manual_ai.utils.decorators import with_backoff
from manual_ai.services.domains_service import DomainsService

logger = logging.getLogger(__name__)

# Frescura de datos: forzar a SerpAPI a ignorar su caché de servidor para
# obtener un SERP/AI Overview actual en cada análisis (objetividad por
# mercado). Configurable por env para poder revertir sin redeploy si el
# coste en RU lo requiere. Por defecto: activado.
SERP_NO_CACHE = os.getenv('SERP_NO_CACHE', 'true').strip().lower() in ('1', 'true', 'yes', 'on')

# Lazy imports para evitar problemas de orden
try:
    from services.ai_cache import ai_cache
except Exception as e:
    ai_cache = None
    logger.warning(f"[Analysis Service] AI cache import failed: {e}")


class AnalysisService:
    """Servicio para ejecutar análisis de keywords con AI Overview"""
    
    def __init__(self):
        self.project_repo = ProjectRepository()
        self.keyword_repo = KeywordRepository()
        self.result_repo = ResultRepository()
        self.domains_service = DomainsService()
    
    def run_project_analysis(self, project_id: int, force_overwrite: bool = False, 
                            user_id: Optional[int] = None) -> List[Dict]:
        """
        Ejecutar análisis completo de todas las keywords activas de un proyecto
        
        Args:
            project_id: ID del proyecto a analizar
            force_overwrite: Si True, sobreescribe resultados existentes del día (para análisis manual)
                           Si False, omite keywords ya analizadas hoy (para análisis automático)
            user_id: ID del usuario (opcional). Si no se proporciona, se obtiene de la sesión actual.
            
        Returns:
            Lista de resultados o dict con error si falla
        """
        # Obtener usuario actual para validación de cuota
        if user_id:
            current_user = get_user_by_id(user_id)
        else:
            current_user = get_current_user()
        
        if not current_user:
            logger.error(f"Intento de análisis sin usuario autenticado para proyecto {project_id}")
            return {'success': False, 'error': 'User not authenticated'}

        # Obtener proyecto y keywords
        project = self.project_repo.get_project_with_details(project_id)
        keywords = [k for k in self.keyword_repo.get_keywords_for_project(project_id) if k['is_active']]

        if not project or not keywords:
            return []

        # Si el proyecto está pausado por cuota y la ventana paused_until aún no expiró,
        # bloquear el análisis. Si paused_until ya pasó, lo limpiamos y seguimos.
        if project.get('is_paused_by_quota'):
            paused_until = project.get('paused_until')
            now_cmp = None
            if paused_until is not None:
                try:
                    now_cmp = datetime.now(paused_until.tzinfo) if paused_until.tzinfo else datetime.utcnow()
                except Exception:
                    now_cmp = datetime.utcnow()

            if paused_until is None or paused_until > now_cmp:
                return {
                    'success': False,
                    'error': 'project_paused_quota',
                    'message': 'Project paused due to quota exhaustion',
                    'paused_until': paused_until
                }

            # paused_until expiró → limpiar el flag para este proyecto y continuar
            try:
                resume_conn = get_db_connection()
                if resume_conn:
                    resume_cur = resume_conn.cursor()
                    try:
                        resume_cur.execute('''
                            UPDATE manual_ai_projects
                            SET is_paused_by_quota = FALSE,
                                paused_until = NULL,
                                paused_at = NULL,
                                paused_reason = NULL,
                                updated_at = NOW()
                            WHERE id = %s
                        ''', (project_id,))
                        resume_conn.commit()
                        project['is_paused_by_quota'] = False
                        project['paused_until'] = None
                        project['paused_reason'] = None
                    finally:
                        resume_cur.close()
                        resume_conn.close()
            except Exception as resume_error:
                logger.warning(
                    f"Error reanudando proyecto Manual AI {project_id} tras expiración de paused_until: {resume_error}"
                )

        # Validar cuota antes de empezar
        quota_info = get_user_quota_status(current_user['id'])
        if not quota_info.get('can_consume'):
            logger.warning(f"User {current_user['id']} sin cuota para iniciar análisis del proyecto {project_id}. "
                          f"Used: {quota_info.get('quota_used', 0)}/{quota_info.get('quota_limit', 0)} RU")
            paused_until = quota_info.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
            try:
                pause_manual_ai_projects_for_quota(current_user['id'], paused_until, reason='quota_exceeded')
            except Exception as pause_exc:
                logger.warning(f"Could not auto-pause Manual AI projects for user {current_user['id']}: {pause_exc}")
            return {
                'success': False,
                'error': 'Quota limit exceeded',
                'quota_info': quota_info,
                'paused_until': paused_until
            }

        # Cuota por PROYECTO (tope propio en la ventana del usuario, ver project_quota.py).
        # Sin tope (limit None) → no aplica. Si no cabe ni una keyword, se pausa SOLO este proyecto.
        from project_quota import check_project_quota, pause_project_for_quota
        project_quota = check_project_quota('manual_ai', project_id, current_user['id'],
                                            planned=MANUAL_AI_KEYWORD_ANALYSIS_COST)
        project_limit = project_quota.get('limit')
        project_used_before = int(project_quota.get('used') or 0)
        if not project_quota.get('allowed', True):
            paused_until = quota_info.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
            logger.warning(f"Proyecto {project_id} sin cuota propia: {project_used_before}/{project_limit} RU")
            pause_project_for_quota('manual_ai', project_id, paused_until)
            return {
                'success': False,
                'error': 'project_quota_exceeded',
                'message': 'This project has used its own monthly quota. It will resume automatically on the next cycle.',
                'project_quota': project_quota,
                'paused_until': paused_until
            }

        results = []
        failed_keywords = 0
        consumed_ru = 0
        today = date.today()

        # NOTA (2026-04-09): Antes aquí abríamos conn + cur para usarlos
        # exclusivamente en la rama quota_error (la única que escribe con el
        # outer cursor). Esto dejaba una conexión idle-in-transaction durante
        # todo el loop de keywords (minutos/horas para proyectos grandes),
        # vulnerable al idle_in_transaction_session_timeout (15 min). Ahora
        # la conn para quota_error se abre localmente en ese except, sólo
        # cuando hace falta.

        analysis_mode = "MANUAL (with overwrite)" if force_overwrite else "AUTOMATIC (skip existing)"
        logger.info(f"🚀 Starting {analysis_mode} analysis for project {project_id} with {len(keywords)} user-defined keywords")
        
        for keyword_data in keywords:
            # Re-validar cuota en cada iteración
            current_quota = get_user_quota_status(current_user['id'])
            if not current_quota.get('can_consume') or current_quota.get('remaining', 0) < MANUAL_AI_KEYWORD_ANALYSIS_COST:
                logger.warning(f"Análisis del proyecto {project_id} detenido por falta de cuota. "
                              f"Keywords procesadas: {len(results)}. Keywords pendientes: {len(keywords) - len(results)}")
                paused_until = current_quota.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
                try:
                    pause_manual_ai_projects_for_quota(current_user['id'], paused_until, reason='quota_exceeded')
                except Exception as pause_exc:
                    logger.warning(f"Could not auto-pause Manual AI projects for user {current_user['id']}: {pause_exc}")
                break

            # Tope propio del proyecto (contador local: consumo previo en la ventana + lo gastado en este run)
            if project_limit is not None and \
                    project_used_before + consumed_ru + MANUAL_AI_KEYWORD_ANALYSIS_COST > project_limit:
                logger.warning(f"Análisis del proyecto {project_id} detenido por su tope propio "
                               f"({project_used_before + consumed_ru}/{project_limit} RU). "
                               f"Keywords procesadas: {len(results)}. Pendientes: {len(keywords) - len(results)}")
                paused_until = current_quota.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
                pause_project_for_quota('manual_ai', project_id, paused_until)
                break

            keyword = keyword_data['keyword']
            keyword_id = keyword_data['id']
            
            try:
                # Verificar si ya existe análisis para hoy
                existing_analysis = self.result_repo.result_exists_for_date(project_id, keyword_id, today)
                
                if existing_analysis and not force_overwrite:
                    logger.debug(f"Analysis already exists for keyword '{keyword}' on {today}, skipping (auto mode)")
                    continue
                elif existing_analysis and force_overwrite:
                    self.result_repo.delete_result_for_date(project_id, keyword_id, today)
                    logger.info(f"🔄 Overwriting existing analysis for keyword '{keyword}' (manual mode)")
                
                # Ejecutar análisis
                try:
                    ai_result, serp_data = self._analyze_keyword(keyword, project, keyword_id)
                    
                    # Guardar resultado en base de datos
                    self.result_repo.create_result(
                        project_id=project_id,
                        keyword_id=keyword_id,
                        analysis_date=today,
                        keyword=keyword,
                        domain=project['domain'],
                        ai_result=ai_result,
                        serp_data=serp_data,
                        country_code=project['country_code']
                    )
                    
                    # Almacenar dominios globales detectados
                    if ai_result.get('has_ai_overview', False):
                        self.domains_service.store_global_domains_detected(
                            project_id=project_id,
                            keyword_id=keyword_id,
                            keyword=keyword,
                            project_domain=project['domain'],
                            ai_analysis_data=ai_result,
                            analysis_date=today,
                            country_code=project['country_code'],
                            selected_competitors=project.get('selected_competitors', [])
                        )
                    
                    results.append({
                        'keyword': keyword,
                        'has_ai_overview': ai_result.get('has_ai_overview', False),
                        'domain_mentioned': ai_result.get('domain_is_ai_source', False),
                        'position': ai_result.get('domain_ai_source_position'),
                        'impact_score': ai_result.get('impact_score', 0)
                    })
                    
                    # Registrar consumo de RU
                    try:
                        from database import track_quota_consumption
                        track_quota_consumption(
                            user_id=current_user['id'],
                            ru_consumed=MANUAL_AI_KEYWORD_ANALYSIS_COST,
                            source='manual_ai',
                            keyword=keyword,
                            country_code=project['country_code'],
                            metadata={
                                'project_id': project_id,
                                'force_overwrite': bool(force_overwrite),
                                'domain': project['domain']
                            }
                        )
                        consumed_ru += MANUAL_AI_KEYWORD_ANALYSIS_COST
                    except Exception as track_error:
                        logger.warning(f"Error registrando consumo de RU para '{keyword}': {track_error}")
                    
                    logger.debug(f"Analyzed keyword '{keyword}': AI={ai_result.get('has_ai_overview')}, "
                               f"Mentioned={ai_result.get('domain_is_ai_source')}")
                    
                except Exception as analysis_error:
                    # Manejar errores de quota específicamente
                    if hasattr(analysis_error, 'is_quota_error') and analysis_error.is_quota_error:
                        logger.warning(f"🚫 Keyword '{keyword}' bloqueada por quota: {analysis_error}")

                        # Guardar marcador de quota_exceeded para esta keyword
                        # en manual_ai_results. La tabla no tiene columna
                        # error_details (verificado en producción), así que el
                        # marcador se limita a has_ai_overview=False /
                        # domain_mentioned=False; el detalle del error se loggea
                        # arriba con logger.warning.
                        # Conn local: abierta sólo para esta operación puntual,
                        # cerrada inmediatamente. Evita mantener una conexión
                        # outer abierta durante todo el loop (vulnerable al
                        # idle_in_transaction_session_timeout de 15 min).
                        quota_conn = get_db_connection()
                        if quota_conn:
                            try:
                                quota_cur = quota_conn.cursor()
                                quota_cur.execute('''
                                    INSERT INTO manual_ai_results
                                    (project_id, keyword_id, keyword, analysis_date, has_ai_overview,
                                     domain_mentioned, country_code)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (project_id, keyword_id, analysis_date)
                                    DO NOTHING
                                ''', (
                                    project_id, keyword_id, keyword, today, False, False,
                                    project['country_code']
                                ))
                                quota_conn.commit()
                            finally:
                                try:
                                    quota_conn.close()
                                except Exception:
                                    pass

                        # Terminar análisis y retornar información de quota
                        quota_info = getattr(analysis_error, 'quota_info', {})
                        action_required = getattr(analysis_error, 'action_required', 'upgrade')

                        logger.error(f"🚫 Manual AI analysis stopped due to quota limit. "
                                   f"Plan: {quota_info.get('plan', 'unknown')}, "
                                   f"Used: {quota_info.get('quota_used', 0)}/{quota_info.get('quota_limit', 0)} RU")

                        # Auto-pausar el proyecto para que el cron y otros endpoints
                        # no sigan intentando consumir cuota hasta el reset.
                        live_quota = get_user_quota_status(current_user['id'])
                        paused_until = live_quota.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
                        try:
                            pause_manual_ai_projects_for_quota(
                                current_user['id'], paused_until, reason='quota_exceeded'
                            )
                        except Exception as pause_exc:
                            logger.warning(
                                f"Could not auto-pause Manual AI projects for user {current_user['id']}: {pause_exc}"
                            )

                        return {
                            'results': results,
                            'quota_exceeded': True,
                            'quota_info': quota_info,
                            'action_required': action_required,
                            'keywords_analyzed': len(results),
                            'keywords_remaining': len(keywords) - len(results),
                            'error': 'QUOTA_EXCEEDED',
                            'paused_until': paused_until
                        }
                    else:
                        logger.error(f"Error analyzing keyword '{keyword}': {analysis_error}")
                        failed_keywords += 1
                        continue
                
            except Exception as e:
                logger.error(f"Error analyzing keyword '{keyword}': {e}")
                failed_keywords += 1
                continue

        # Nota: no hay `conn.commit()/close()` aquí porque ya no abrimos una
        # conn outer al inicio del método. Todas las escrituras van por
        # `result_repo`, `domains_service` y `track_quota_consumption`, que
        # usan sus propias conexiones de vida corta con commit inmediato.

        overwrite_info = " (with overwrite)" if force_overwrite else " (skipping existing)"
        logger.info(f"✅ Completed {analysis_mode} analysis for project {project_id}: "
                   f"{len(results)}/{len(keywords)} keywords processed, {failed_keywords} failed{overwrite_info}, "
                   f"RU consumed: {consumed_ru}")
        
        if failed_keywords > 0:
            logger.warning(f"⚠️ {failed_keywords} keywords failed analysis (check SERPAPI_KEY configuration)")
        
        return results
    
    def _analyze_keyword(self, keyword: str, project: Dict, keyword_id: int) -> tuple:
        """
        Analizar una keyword individual
        
        Returns:
            Tuple (ai_result, serp_data)
        """
        internal_country = convert_iso_to_internal_country(project['country_code'])
        
        # 1. Verificar caché primero
        if ai_cache:
            cached_result = ai_cache.get_cached_analysis(keyword, project['domain'], internal_country)
            if cached_result and cached_result.get('analysis'):
                logger.info(f"💾 Using cached result for '{keyword}'")
                ai_result = cached_result['analysis'].get('ai_analysis', {})
                serp_data = cached_result.get('serp_data', {})
                return ai_result, serp_data
        
        # 2. Obtener SERP con reintentos
        serp_data = self._fetch_serp_data(keyword, internal_country)

        # 3. Analizar AI Overview
        ai_result = self._detect_ai_overview(serp_data, project['domain'])

        # 3b. AI Overview "collapsed" (escondido tras "Show more": ai_overview
        #     solo trae page_token, sin text_blocks/references). Se expande con
        #     el engine google_ai_overview; ver _expand_collapsed_aio.
        if ai_result.get('debug_info', {}).get('requires_additional_request'):
            serp_data, ai_result = self._expand_collapsed_aio(
                keyword, internal_country, serp_data, ai_result, project['domain']
            )

        # 4. Guardar en caché
        if ai_cache:
            ai_cache.cache_analysis(keyword, project['domain'], internal_country, {
                'keyword': keyword,
                'ai_analysis': ai_result,
                'timestamp': time.time(),
                'country_analyzed': internal_country,
                'serp_data': serp_data
            })
        
        return ai_result, serp_data
    
    def _expand_collapsed_aio(self, keyword: str, internal_country: str,
                              serp_data: Dict, ai_result: Dict, domain: str) -> tuple:
        """
        Expande un AI Overview collapsed y deja constancia del resultado en
        ai_result['aio_expansion'] (se guarda en ai_analysis_data).

        Hasta 2026-09 la expansión repetía la búsqueda con engine=google +
        page_token: SerpAPI ignora el token en ese engine y devuelve una SERP
        nueva, que casi siempre vuelve a traer el AIO collapsed (~30% de los
        AIO sin contenido). El token es del engine google_ai_overview y caduca
        ~1 minuto después de la búsqueda, así que se usa enseguida y, si aun
        así falla, se repite la búsqueda completa para obtener un token nuevo
        (MANUAL_AI_AIO_REFETCH_ATTEMPTS veces, por defecto 1).

        Si nada funciona se conserva el resultado collapsed (has_ai_overview
        sigue siendo True) marcado con aio_expansion.status='failed'.

        Returns:
            Tuple (serp_data, ai_result)
        """
        refetch_attempts = max(0, int(os.getenv('MANUAL_AI_AIO_REFETCH_ATTEMPTS', '1')))
        expansion = {'status': 'failed', 'attempts': 0, 'refetches': 0, 'error': None}

        for round_idx in range(refetch_attempts + 1):
            page_token = ai_result.get('debug_info', {}).get('page_token', '')
            if not page_token:
                expansion['error'] = 'collapsed AIO without page_token'
                break

            expansion['attempts'] += 1
            try:
                expanded_aio = self._fetch_expanded_aio(keyword, internal_country, page_token)
                serp_data['ai_overview'] = expanded_aio
                ai_result = self._detect_ai_overview(serp_data, domain)
                expansion['status'] = 'expanded'
                expansion['error'] = None
                logger.info(f"[Manual AI] ✅ AIO expanded for '{keyword}' (attempt {expansion['attempts']})")
                break
            except Exception as e_expand:
                if getattr(e_expand, 'is_quota_error', False):
                    raise
                expansion['error'] = str(e_expand)[:300]
                logger.warning(f"[Manual AI] AIO expansion failed for '{keyword}': {e_expand}")

            if round_idx >= refetch_attempts:
                break

            # Token probablemente caducado o sin contenido: SERP nueva → token nuevo.
            expansion['refetches'] += 1
            try:
                serp_data = self._fetch_serp_data(keyword, internal_country)
            except Exception as e_refetch:
                if getattr(e_refetch, 'is_quota_error', False):
                    raise
                expansion['error'] = f"refetch failed: {str(e_refetch)[:250]}"
                logger.warning(f"[Manual AI] SERP refetch for AIO expansion failed for '{keyword}': {e_refetch}")
                break
            ai_result = self._detect_ai_overview(serp_data, domain)
            if not ai_result.get('debug_info', {}).get('requires_additional_request'):
                # La SERP nueva ya trae el AIO completo (o ya no hay AIO).
                expansion['status'] = 'refetched'
                expansion['error'] = None
                break

        if expansion['status'] == 'failed':
            logger.warning(
                f"[Manual AI] Keeping collapsed AIO for '{keyword}' after "
                f"{expansion['attempts']} expansion attempt(s): {expansion['error']}"
            )
        ai_result['aio_expansion'] = expansion
        return serp_data, ai_result

    def _fetch_serp_data(self, keyword: str, internal_country: str) -> Dict:
        """Obtener datos SERP con reintentos"""
        try:
            from services.serp_service import get_serp_json
            from services.country_config import get_country_config
        except Exception as e:
            logger.error(f"❌ SERP service not available: {e}")
            raise
        
        api_key = os.getenv('SERPAPI_KEY')
        if not api_key:
            logger.error(f"❌ SERPAPI_KEY not configured")
            raise RuntimeError("SERPAPI_KEY not configured")
        
        serp_params_base = {
            'engine': 'google',
            'q': keyword,
            'api_key': api_key,
            'num': 20
        }
        if SERP_NO_CACHE:
            serp_params_base['no_cache'] = True

        country_config = get_country_config(internal_country)
        if country_config:
            serp_params_base.update({
                'location': country_config['serp_location'],
                'gl': country_config['serp_gl'],
                'hl': country_config['serp_hl'],
                'google_domain': country_config['google_domain']
            })
            logger.debug(f"Using {country_config['name']} config for '{keyword}'")
        
        @with_backoff(max_attempts=3, base_delay_sec=1.0)
        def fetch_serp():
            data = get_serp_json(dict(serp_params_base))
            
            if not data:
                raise RuntimeError('No SERP data returned')
            
            # Verificar errores de quota
            if data.get('quota_blocked'):
                logger.warning(f"🚫 Manual AI bloqueado por quota para '{keyword}': {data.get('error')}")
                quota_error = RuntimeError(f"QUOTA_EXCEEDED: {data.get('error', 'Quota limit reached')}")
                quota_error.quota_info = data.get('quota_info', {})
                quota_error.action_required = data.get('action_required', 'upgrade')
                quota_error.is_quota_error = True
                raise quota_error
            
            if data.get('error'):
                raise RuntimeError(data.get('error', 'SERP fetch error'))
            
            return data
        
        return fetch_serp()

    def _fetch_expanded_aio(self, keyword: str, internal_country: str, page_token: str) -> Dict:
        """
        Pide a SerpAPI el contenido de un AI Overview collapsed con el engine
        google_ai_overview (el page_token solo es válido en ese engine y
        caduca ~1 minuto después de la búsqueda original).

        Consume 1 RU vía quota_middleware, igual que cualquier llamada SERP.

        Returns:
            dict ai_overview con text_blocks y/o references.

        Raises:
            RuntimeError: error de SerpAPI, bloqueo de cuota (is_quota_error)
                          o respuesta sin contenido de AIO.
        """
        try:
            from services.serp_service import get_serp_json
            from services.country_config import get_country_config
        except Exception as e:
            logger.error(f"❌ SERP service not available for expansion: {e}")
            raise

        api_key = os.getenv('SERPAPI_KEY')
        if not api_key:
            logger.error("❌ SERPAPI_KEY not configured (expansion)")
            raise RuntimeError("SERPAPI_KEY not configured")

        expanded_params = {
            'engine': 'google_ai_overview',
            'page_token': page_token,
            'api_key': api_key,
            # q/gl solo sirven para el tracking de cuota (quota_middleware);
            # SerpAPI los ignora en este engine.
            'q': keyword,
        }
        country_config = get_country_config(internal_country)
        if country_config:
            expanded_params['gl'] = country_config['serp_gl']

        # Sin reintento propio: quota_middleware ya reintenta los errores
        # transitorios, y repetir un token caducado solo gasta RU. Si falla,
        # _expand_collapsed_aio repite la búsqueda para obtener otro token.
        data = get_serp_json(expanded_params)
        if not data:
            raise RuntimeError('No AIO expansion data returned')
        if data.get('quota_blocked'):
            quota_error = RuntimeError(f"QUOTA_EXCEEDED: {data.get('error', 'Quota limit reached')}")
            quota_error.quota_info = data.get('quota_info', {})
            quota_error.action_required = data.get('action_required', 'upgrade')
            quota_error.is_quota_error = True
            raise quota_error
        if data.get('error'):
            raise RuntimeError(data['error'])
        aio = data.get('ai_overview') or {}
        if aio.get('error'):
            raise RuntimeError(f"ai_overview error: {aio['error']}")
        if not aio.get('text_blocks') and not aio.get('references'):
            raise RuntimeError(f"AIO expansion without content (keys: {sorted(aio.keys())})")
        return aio

    def _detect_ai_overview(self, serp_data: Dict, domain: str) -> Dict:
        """Detectar elementos de AI Overview en SERP"""
        try:
            from services.ai_analysis import detect_ai_overview_elements
        except Exception as e:
            logger.error(f"❌ AI analysis service not available: {e}")
            raise
        
        return detect_ai_overview_elements(serp_data, domain)

