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
from ai_mode_projects.services.domains_service import DomainsService

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
                    
                    # Almacenar dominios globales detectados para ranking/competidores
                    try:
                        references = serp_data.get('references', []) or []
                        # Adaptar formato a DomainsService (debug_info.references_found)
                        ai_analysis_data = {
                            'debug_info': {
                                'references_found': [
                                    {
                                        'link': ref.get('link'),
                                        'index': ref.get('position', i + 1) if (ref.get('position') and isinstance(ref.get('position'), int)) else i + 1,
                                        'title': ref.get('title', ''),
                                        'source': ref.get('source', '')
                                    } for i, ref in enumerate(references)
                                ]
                            }
                        }
                        DomainsService.store_global_domains_detected(
                            project_id=project_id,
                            keyword_id=keyword_id,
                            keyword=keyword,
                            project_domain=project.get('brand_name', ''),
                            ai_analysis_data=ai_analysis_data,
                            analysis_date=today,
                            country_code=project.get('country_code', 'ES'),
                            selected_competitors=project.get('selected_competitors', []) if isinstance(project, dict) else []
                        )
                    except Exception as domains_error:
                        logger.warning(f"[AI MODE] Error storing global domains for '{keyword}': {domains_error}")
                    
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
                        
                        # Terminar análisis y retornar información de quota (sin escribir en tablas ajenas)
                        quota_info = getattr(analysis_error, 'quota_info', {})
                        action_required = getattr(analysis_error, 'action_required', 'upgrade')
                        
                        logger.error(f"🚫 AI Mode analysis stopped due to quota limit. "
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
        
        # Mapeo de códigos ISO-2 a nombres de ubicación para Google AI Mode
        # SerpApi requiere nombres de países/ciudades, no códigos
        location_map = {
            'ES': 'Spain',
            'US': 'United States',
            'GB': 'United Kingdom',
            'FR': 'France',
            'DE': 'Germany',
            'IT': 'Italy',
            'PT': 'Portugal',
            'MX': 'Mexico',
            'AR': 'Argentina',
            'CO': 'Colombia',
            'CL': 'Chile',
            'PE': 'Peru',
            'BR': 'Brazil',
            'CA': 'Canada',
            'AU': 'Australia',
            'NZ': 'New Zealand',
            'IN': 'India',
            'JP': 'Japan',
            'CN': 'China',
            'KR': 'South Korea',
            'NL': 'Netherlands',
            'BE': 'Belgium',
            'CH': 'Switzerland',
            'AT': 'Austria',
            'SE': 'Sweden',
            'NO': 'Norway',
            'DK': 'Denmark',
            'FI': 'Finland',
            'PL': 'Poland',
            'CZ': 'Czech Republic',
            'IE': 'Ireland',
            'GR': 'Greece',
            'RO': 'Romania',
            'HU': 'Hungary'
        }
        
        location = location_map.get(country_code, 'Spain')  # Default a Spain
        
        try:
            # Parámetros para Google AI Mode (google.com/ai)
            params = {
                "q": keyword,
                "engine": "google_ai_mode",
                "location": location,  # Nombre de país/ciudad que SerpApi acepta
                "api_key": api_key
            }
            
            logger.info(f"🔍 Calling SerpApi Google AI Mode for keyword: '{keyword}' (location: {location})")
            
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
        Parsear respuesta de Google AI Mode (google.com/ai) para detectar menciones de marca
        
        Estructura de SerpApi Google AI Mode:
        - text_blocks: Array de bloques de texto generados por IA
        - references: Array de fuentes citadas (con link, title, source)
        - inline_images: Imágenes inline (opcional)
        - related_questions: Preguntas relacionadas (opcional)
        
        Args:
            serp_data: Datos raw de SerpApi Google AI Mode
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
        
        # Google AI Mode (SerpAPI engine=google_ai_mode) proporciona:
        # - text_blocks: bloques de texto generados por AI Mode
        # - references: fuentes citadas por AI Mode con campo position
        # No usar campos propios de AI Overview (otro sistema)
        text_blocks = serp_data.get('text_blocks', []) or []
        references = serp_data.get('references', []) or []
        
        result['total_sources'] = len(references)
        
        # Buscar menciones de la marca (case-insensitive) con pequeñas variaciones
        brand_lower = (brand_name or '').strip().lower()
        # Variaciones simples
        variations = {brand_lower}
        if ' ' in brand_lower:
            variations.add(brand_lower.replace(' ', ''))
        if '-' in brand_lower:
            variations.add(brand_lower.replace('-', ''))
        if brand_lower.startswith('get') and len(brand_lower) > 3:
            variations.add(brand_lower[3:])
        
        # 1. Buscar en los text_blocks (respuesta generada por IA)
        for block in text_blocks:
            # Algunas variantes usan 'text', otras 'snippet' o 'content'
            raw_text = block.get('text') or block.get('snippet') or block.get('content') or ''
            text = str(raw_text).lower()
            
            if any(v in text for v in variations if v):
                result['brand_mentioned'] = True
                result['mention_context'] = str(raw_text)[:500]
                result['mention_position'] = 0  # Posición 0 para menciones en texto de IA
                
                # Analizar sentimiento básico
                if any(word in text for word in ['best', 'excellent', 'great', 'top', 'leading', 'recommended']):
                    result['sentiment'] = 'positive'
                elif any(word in text for word in ['worst', 'bad', 'poor', 'avoid', 'problem', 'issue']):
                    result['sentiment'] = 'negative'
                
                logger.info(f"✨ Brand '{brand_name}' found in AI text_blocks at position 0")
                return result

        # No buscar summaries de AI Overview: fuera de alcance AI Mode
        
        # 2. Si no está en text_blocks, buscar en references (fuentes citadas)
        for idx, ref in enumerate(references):
            title = str(ref.get('title', '')).lower()
            link = str(ref.get('link', '')).lower()
            source = str(ref.get('source', '')).lower()
            position = ref.get('position')
            
            def _matches_brand():
                if any(v and (v in title or v in link or v in source) for v in variations):
                    return True
                # Comprobar dominio del link
                try:
                    from urllib.parse import urlparse
                    netloc = urlparse(link).netloc.lower()
                    if netloc.startswith('www.'):
                        netloc = netloc[4:]
                    return any(v and v in netloc for v in variations)
                except Exception:
                    return False
            
            if _matches_brand():
                result['brand_mentioned'] = True
                # Fallback a índice+1 si no hay position
                result['mention_position'] = position if isinstance(position, int) and position > 0 else (idx + 1)
                result['mention_context'] = ref.get('title', '')[:500]
                
                # Análisis de sentimiento básico
                text = f"{title} {source}"
                if any(word in text for word in ['best', 'excellent', 'great', 'top', 'leading', 'recommended']):
                    result['sentiment'] = 'positive'
                elif any(word in text for word in ['worst', 'bad', 'poor', 'avoid', 'problem', 'issue']):
                    result['sentiment'] = 'negative'
                
                logger.info(f"✨ Brand '{brand_name}' found in reference at position {position}")
                break
        
        if not result['brand_mentioned']:
            logger.info(f"❌ Brand '{brand_name}' not found in AI Mode results")
        
        return result

