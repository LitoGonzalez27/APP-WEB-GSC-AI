"""
Servicio de análisis de keywords con AI Mode
Motor principal del sistema AI Mode Monitoring
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
from ai_mode_projects.config import AI_MODE_KEYWORD_ANALYSIS_COST
from ai_mode_projects.models.project_repository import ProjectRepository
from ai_mode_projects.models.keyword_repository import KeywordRepository
from ai_mode_projects.models.result_repository import ResultRepository
from ai_mode_projects.utils.country_utils import convert_iso_to_internal_country
from ai_mode_projects.utils.decorators import with_backoff

logger = logging.getLogger(__name__)

# Lazy imports para evitar problemas de orden
try:
    from services.ai_cache import ai_cache
except Exception as e:
    ai_cache = None
    logger.warning(f"[AI Mode Analysis Service] AI cache import failed: {e}")


class AnalysisService:
    """Servicio para ejecutar análisis de keywords con AI Mode"""
    
    def __init__(self):
        self.project_repo = ProjectRepository()
        self.keyword_repo = KeywordRepository()
        self.result_repo = ResultRepository()
    
    def run_project_analysis(self, project_id: int, force_overwrite: bool = False, 
                            user_id: Optional[int] = None) -> List[Dict]:
        """
        Ejecutar análisis completo de todas las keywords activas de un proyecto AI Mode
        
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
            logger.error(f"Intento de análisis AI Mode sin usuario autenticado para proyecto {project_id}")
            return {'success': False, 'error': 'User not authenticated'}

        # Obtener proyecto y keywords
        project = self.project_repo.get_project_with_details(project_id)
        keywords = [k for k in self.keyword_repo.get_keywords_for_project(project_id) if k['is_active']]
        
        if not project or not keywords:
            return []

        # Validar cuota antes de empezar
        quota_info = get_user_quota_status(current_user['id'])
        if not quota_info.get('can_consume'):
            logger.warning(f"User {current_user['id']} sin cuota para iniciar análisis AI Mode del proyecto {project_id}. "
                          f"Used: {quota_info.get('quota_used', 0)}/{quota_info.get('quota_limit', 0)} RU")
            return {'success': False, 'error': 'Quota limit exceeded', 'quota_info': quota_info}

        results = []
        failed_keywords = 0
        consumed_ru = 0
        today = date.today()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        analysis_mode = "MANUAL (with overwrite)" if force_overwrite else "AUTOMATIC (skip existing)"
        logger.info(f"🚀 Starting AI Mode {analysis_mode} analysis for project {project_id} with {len(keywords)} keywords")
        
        for keyword_data in keywords:
            # Re-validar cuota en cada iteración
            current_quota = get_user_quota_status(current_user['id'])
            if not current_quota.get('can_consume') or current_quota.get('remaining', 0) < AI_MODE_KEYWORD_ANALYSIS_COST:
                logger.warning(f"Análisis AI Mode del proyecto {project_id} detenido por falta de cuota. "
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
                
                # Ejecutar análisis AI Mode
                try:
                    ai_result, serp_data = self._analyze_keyword(keyword, project, keyword_id)
                    
                    # Guardar resultado en base de datos
                    self.result_repo.create_result(
                        project_id=project_id,
                        keyword_id=keyword_id,
                        analysis_date=today,
                        keyword=keyword,
                        brand_name=project['brand_name'],
                        ai_result=ai_result,
                        serp_data=serp_data,
                        country_code=project['country_code']
                    )
                    
                    results.append({
                        'keyword': keyword,
                        'brand_mentioned': ai_result.get('brand_mentioned', False),
                        'mention_position': ai_result.get('mention_position'),
                        'total_sources': ai_result.get('total_sources', 0),
                        'sentiment': ai_result.get('sentiment', 'neutral')
                    })
                    
                    # Registrar consumo de RU
                    try:
                        from database import track_quota_consumption
                        track_quota_consumption(
                            user_id=current_user['id'],
                            ru_consumed=AI_MODE_KEYWORD_ANALYSIS_COST,
                            source='ai_mode',
                            keyword=keyword,
                            country_code=project['country_code'],
                            metadata={
                                'project_id': project_id,
                                'force_overwrite': bool(force_overwrite),
                                'brand_name': project['brand_name']
                            }
                        )
                        consumed_ru += AI_MODE_KEYWORD_ANALYSIS_COST
                    except Exception as track_error:
                        logger.warning(f"Error registrando consumo de RU para '{keyword}': {track_error}")
                    
                    logger.debug(f"Analyzed AI Mode keyword '{keyword}': Mentioned={ai_result.get('brand_mentioned')}, "
                               f"Position={ai_result.get('mention_position')}")
                    
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
    
    @with_backoff(max_attempts=3, base_delay_sec=1.0)
    def _analyze_keyword(self, keyword: str, project: Dict, keyword_id: int) -> tuple:
        """
        Analizar una keyword usando Google Search de SerpApi para detectar menciones de marca
        
        Args:
            keyword: Keyword a analizar
            project: Datos del proyecto (con brand_name)
            keyword_id: ID de la keyword
            
        Returns:
            Tupla (ai_result, serp_data)
        """
        from serpapi import GoogleSearch
        
        api_key = os.getenv('SERPAPI_API_KEY')
        if not api_key:
            # Intentar con SERPAPI_KEY si SERPAPI_API_KEY no existe
            api_key = os.getenv('SERPAPI_KEY')
        
        if not api_key:
            logger.error(f"❌ SERPAPI_API_KEY not configured")
            raise RuntimeError("SERPAPI_API_KEY not configured")
        
        brand_name = project.get('brand_name', '')
        country_code = project.get('country_code', 'US')
        
        # Convertir código de país para country_param (interno de 3 letras)
        country_param = convert_iso_to_internal_country(country_code)
        
        # Para Google domain, usar el código ISO-2 directamente (2 letras)
        google_domain_code = country_code.lower() if country_code else 'us'
        
        try:
            # Parámetros para Google Search
            params = {
                "q": keyword,
                "engine": "google",
                "google_domain": f"google.{google_domain_code}",
                "gl": country_code,
                "hl": "en",
                "api_key": api_key,
                "num": 10
            }
            
            logger.info(f"🔍 Calling SerpApi for AI Mode keyword: {keyword}")
            
            # Hacer la llamada a SerpApi
            search = GoogleSearch(params)
            serp_data = search.get_dict()
            
            # Analizar resultados para detectar menciones de la marca
            ai_result = self._parse_ai_mode_response(serp_data, brand_name)
            
            logger.info(f"✅ AI Mode analysis completed for '{keyword}': Brand mentioned={ai_result.get('brand_mentioned')}")
            
            # Pequeña pausa para rate limiting
            time.sleep(0.3)
            
            return ai_result, serp_data
            
        except Exception as e:
            logger.error(f"Error analyzing AI Mode keyword '{keyword}': {e}")
            # Devolver resultado vacío en caso de error
            return {
                'brand_mentioned': False,
                'mention_position': None,
                'mention_context': None,
                'total_sources': 0,
                'sentiment': 'unknown'
            }, {}
    
    def _parse_ai_mode_response(self, serp_data: dict, brand_name: str) -> dict:
        """
        Parsear respuesta de SerpApi para detectar menciones de marca
        
        Args:
            serp_data: Datos raw de SerpApi
            brand_name: Nombre de la marca a buscar
            
        Returns:
            Dict con resultados del análisis
        """
        result = {
            'brand_mentioned': False,
            'mention_position': None,
            'mention_context': None,
            'total_sources': 0,
            'sentiment': 'neutral'
        }
        
        # Buscar en resultados orgánicos
        organic_results = serp_data.get('organic_results', [])
        ai_overview = serp_data.get('ai_overview', {})
        
        result['total_sources'] = len(organic_results)
        
        # Buscar menciones de la marca (case-insensitive)
        brand_lower = brand_name.lower()
        
        # Buscar primero en AI Overview (si existe)
        if ai_overview:
            ai_text = str(ai_overview.get('text', '')).lower()
            ai_sources = ai_overview.get('sources', [])
            
            if brand_lower in ai_text:
                result['brand_mentioned'] = True
                result['mention_context'] = ai_overview.get('text', '')[:500]
                result['mention_position'] = 0  # Posición especial para AI Overview
                
                # Analizar sentimiento básico
                if any(word in ai_text for word in ['best', 'excellent', 'great', 'top', 'leading', 'recommended']):
                    result['sentiment'] = 'positive'
                elif any(word in ai_text for word in ['worst', 'bad', 'poor', 'avoid', 'problem', 'issue']):
                    result['sentiment'] = 'negative'
                
                logger.info(f"✨ Brand '{brand_name}' found in AI Overview at position 0")
                return result
        
        # Si no está en AI Overview, buscar en resultados orgánicos
        for idx, organic in enumerate(organic_results, 1):
            title = str(organic.get('title', '')).lower()
            snippet = str(organic.get('snippet', '')).lower()
            
            if brand_lower in title or brand_lower in snippet:
                result['brand_mentioned'] = True
                result['mention_position'] = idx
                result['mention_context'] = organic.get('snippet', '')[:500]
                
                # Análisis de sentimiento básico
                text = f"{title} {snippet}"
                if any(word in text for word in ['best', 'excellent', 'great', 'top', 'leading', 'recommended']):
                    result['sentiment'] = 'positive'
                elif any(word in text for word in ['worst', 'bad', 'poor', 'avoid', 'problem', 'issue']):
                    result['sentiment'] = 'negative'
                
                logger.info(f"✨ Brand '{brand_name}' found in organic result at position {idx}")
                break
        
        if not result['brand_mentioned']:
            logger.info(f"❌ Brand '{brand_name}' not found in search results")
        
        return result

