"""
Servicio de análisis de keywords con AI Overview
Motor principal del sistema Manual AI
"""

import logging
import json
import time
import os
from datetime import date
from typing import List, Dict, Optional
from database import get_db_connection
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

        # Validar cuota antes de empezar
        quota_info = get_user_quota_status(current_user['id'])
        if not quota_info.get('can_consume'):
            logger.warning(f"User {current_user['id']} sin cuota para iniciar análisis del proyecto {project_id}. "
                          f"Used: {quota_info.get('quota_used', 0)}/{quota_info.get('quota_limit', 0)} RU")
            return {'success': False, 'error': 'Quota limit exceeded', 'quota_info': quota_info}

        results = []
        failed_keywords = 0
        consumed_ru = 0
        today = date.today()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        analysis_mode = "MANUAL (with overwrite)" if force_overwrite else "AUTOMATIC (skip existing)"
        logger.info(f"🚀 Starting {analysis_mode} analysis for project {project_id} with {len(keywords)} user-defined keywords")
        
        for keyword_data in keywords:
            # Re-validar cuota en cada iteración
            current_quota = get_user_quota_status(current_user['id'])
            if not current_quota.get('can_consume') or current_quota.get('remaining', 0) < MANUAL_AI_KEYWORD_ANALYSIS_COST:
                logger.warning(f"Análisis del proyecto {project_id} detenido por falta de cuota. "
                              f"Keywords procesadas: {len(results)}. Keywords pendientes: {len(keywords) - len(results)}")
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
                        
                        # Guardar resultado de error de quota
                        cur.execute('''
                            INSERT INTO manual_ai_results 
                            (project_id, keyword_id, keyword, analysis_date, has_ai_overview, 
                             domain_mentioned, error_details, country_code)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (project_id, keyword_id, analysis_date) 
                            DO UPDATE SET 
                                has_ai_overview = EXCLUDED.has_ai_overview,
                                domain_mentioned = EXCLUDED.domain_mentioned,
                                error_details = EXCLUDED.error_details,
                                updated_at = NOW()
                        ''', (
                            project_id, keyword_id, keyword, today, False, False,
                            f"QUOTA_EXCEEDED: {getattr(analysis_error, 'quota_info', {}).get('message', 'Quota limit reached')}",
                            project['country_code']
                        ))
                        
                        # Terminar análisis y retornar información de quota
                        quota_info = getattr(analysis_error, 'quota_info', {})
                        action_required = getattr(analysis_error, 'action_required', 'upgrade')
                        
                        logger.error(f"🚫 Manual AI analysis stopped due to quota limit. "
                                   f"Plan: {quota_info.get('plan', 'unknown')}, "
                                   f"Used: {quota_info.get('quota_used', 0)}/{quota_info.get('quota_limit', 0)} RU")
                        
                        conn.commit()
                        cur.close()
                        conn.close()
                        
                        return {
                            'results': results,
                            'quota_exceeded': True,
                            'quota_info': quota_info,
                            'action_required': action_required,
                            'keywords_analyzed': len(results),
                            'keywords_remaining': len(keywords) - len(results),
                            'error': 'QUOTA_EXCEEDED'
                        }
                    else:
                        logger.error(f"Error analyzing keyword '{keyword}': {analysis_error}")
                        failed_keywords += 1
                        continue
                
            except Exception as e:
                logger.error(f"Error analyzing keyword '{keyword}': {e}")
                failed_keywords += 1
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
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
    
    def _detect_ai_overview(self, serp_data: Dict, domain: str) -> Dict:
        """Detectar elementos de AI Overview en SERP"""
        try:
            from services.ai_analysis import detect_ai_overview_elements
        except Exception as e:
            logger.error(f"❌ AI analysis service not available: {e}")
            raise
        
        return detect_ai_overview_elements(serp_data, domain)

