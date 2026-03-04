"""
Servicio de análisis de keywords con AI Mode
Motor principal del sistema AI Mode Monitoring
"""

import logging
import json
import time
import os
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from database import get_db_connection, pause_ai_mode_projects_for_quota
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

        if project.get('is_paused_by_quota'):
            paused_until = project.get('paused_until')
            if paused_until:
                try:
                    now_cmp = datetime.now(paused_until.tzinfo) if paused_until.tzinfo else datetime.utcnow()
                except Exception:
                    now_cmp = datetime.utcnow()
                if paused_until <= now_cmp:
                    try:
                        resume_conn = get_db_connection()
                        if not resume_conn:
                            raise Exception("No DB connection available for resume")
                        resume_cur = resume_conn.cursor()
                        resume_cur.execute('''
                            UPDATE ai_mode_projects
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
                    except Exception as resume_error:
                        logger.warning(f"Error reanudando proyecto AI Mode {project_id}: {resume_error}")
                    finally:
                        try:
                            resume_cur.close()
                        except Exception:
                            pass
                        try:
                            resume_conn.close()
                        except Exception:
                            pass
                else:
                    return {
                        'success': False,
                        'error': 'project_paused_quota',
                        'message': 'Proyecto en pausa por agotamiento de cuota',
                        'paused_until': paused_until
                    }
            else:
                return {
                    'success': False,
                    'error': 'project_paused_quota',
                    'message': 'Proyecto en pausa por agotamiento de cuota',
                    'paused_until': paused_until
                }

        # Validar cuota antes de empezar
        quota_info = get_user_quota_status(current_user['id'])
        if not quota_info.get('can_consume'):
            logger.warning(f"User {current_user['id']} sin cuota para iniciar análisis AI Mode del proyecto {project_id}. "
                          f"Used: {quota_info.get('quota_used', 0)}/{quota_info.get('quota_limit', 0)} RU")
            paused_until = quota_info.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
            pause_ai_mode_projects_for_quota(current_user['id'], paused_until, reason='quota_exceeded')
            return {
                'success': False,
                'error': 'Quota limit exceeded',
                'quota_info': quota_info,
                'paused_until': paused_until
            }

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
                paused_until = current_quota.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
                pause_ai_mode_projects_for_quota(current_user['id'], paused_until, reason='quota_exceeded')
                conn.commit()
                cur.close()
                conn.close()
                return {
                    'results': results,
                    'quota_exceeded': True,
                    'quota_info': current_quota,
                    'action_required': 'upgrade',
                    'keywords_analyzed': len(results),
                    'keywords_remaining': len(keywords) - len(results),
                    'error': 'QUOTA_EXCEEDED',
                    'paused_until': paused_until
                }

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
                        # Orden estable: primero por index asc (AI Mode usa 'index' 0-based, no 'position')
                        enriched = []
                        for i, ref in enumerate(references):
                            idx = ref.get('index')
                            # index es 0-based: 0, 1, 2, ...
                            idx_num = idx if isinstance(idx, int) and idx >= 0 else None
                            enriched.append((idx_num, i, ref))
                        enriched.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 10**9, t[1]))
                        # Adaptar formato a DomainsService (debug_info.references_found) con índice visual consistente 0-based
                        ordered_refs = []
                        for display_idx, (_, _, ref) in enumerate(enriched):
                            ordered_refs.append({
                                'link': ref.get('link'),
                                'index': display_idx,  # índice visual 0-based
                                'title': ref.get('title', ''),
                                'source': ref.get('source', '')
                            })
                        ai_analysis_data = { 'debug_info': { 'references_found': ordered_refs } }
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
                        paused_until = quota_info.get('reset_date') or (datetime.utcnow() + timedelta(days=30))
                        pause_ai_mode_projects_for_quota(current_user['id'], paused_until, reason='quota_exceeded')
                        
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
        
        # Fix #7: Unified location map — use country_config.py (70+ countries) via ISO-2 conversion
        # instead of hardcoded 32-country map
        internal_code = convert_iso_to_internal_country(country_code)
        try:
            from services.country_config import get_country_config
            country_cfg = get_country_config(internal_code)
            if country_cfg:
                location = country_cfg['serp_location']
            else:
                location = 'Madrid, Spain'  # Fallback seguro
        except Exception:
            location = 'Madrid, Spain'
        
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
        - text_blocks: [{"type": "paragraph", "snippet": "...", "reference_indexes": [0,1]}]
        - references: [{"link": "...", "index": 0, "title": "...", "source": "...", "snippet": "..."}]
        - inline_images: Imágenes inline (opcional)
        - related_questions: Preguntas relacionadas (opcional)
        
        Args:
            serp_data: Datos raw de SerpApi Google AI Mode
            brand_name: Nombre de la marca a buscar
            
        Returns:
            Dict con resultados del análisis
        """
        # VALIDACIÓN CRÍTICA 1: Verificar que serp_data es válido
        if not serp_data or not isinstance(serp_data, dict):
            logger.error("❌ CRITICAL: Invalid serp_data structure (not a dict)")
            return {
                'brand_mentioned': False,
                'mention_position': None,
                'mention_context': None,
                'total_sources': 0,
                'sentiment': 'neutral',
                'error': 'Invalid serp_data'
            }
        
        # VALIDACIÓN CRÍTICA 2: Verificar que brand_name existe
        if not brand_name or not brand_name.strip():
            logger.error("❌ CRITICAL: brand_name is empty or None!")
            return {
                'brand_mentioned': False,
                'mention_position': None,
                'mention_context': None,
                'total_sources': 0,
                'sentiment': 'neutral',
                'error': 'No brand name configured'
            }
        
        result = {
            'brand_mentioned': False,
            'mention_position': None,
            'mention_context': None,
            'total_sources': 0,
            'sentiment': 'neutral'
        }
        
        # Extraer y validar estructura de datos
        text_blocks = serp_data.get('text_blocks') or []
        references = serp_data.get('references') or []
        
        # VALIDACIÓN: Asegurar que son listas
        if not isinstance(text_blocks, list):
            logger.warning(f"⚠️ text_blocks is not a list: {type(text_blocks)}")
            text_blocks = []
        
        if not isinstance(references, list):
            logger.warning(f"⚠️ references is not a list: {type(references)}")
            references = []
        
        result['total_sources'] = len(references)
        
        # Preparar variaciones de la marca con protección inteligente
        import re
        
        brand_lower = brand_name.strip().lower()
        
        # Variaciones para dominios/links (búsqueda simple de substring)
        domain_variations = {brand_lower}
        
        # Variaciones para texto (búsqueda con word boundaries)
        # Incluir TODAS las variaciones, pero buscar como palabras completas
        text_variations = {brand_lower}
        
        # Variación sin espacios: "HM Fertility" → "hmfertility"
        if ' ' in brand_lower:
            no_space = brand_lower.replace(' ', '')
            domain_variations.add(no_space)
            text_variations.add(no_space)
        
        # Variación sin guiones: "click-and-seo" → "clickandseo"
        if '-' in brand_lower:
            no_dash = brand_lower.replace('-', '')
            domain_variations.add(no_dash)
            text_variations.add(no_dash)
        
        # Variación sin prefijo 'get': "getquipu" → "quipu"
        # Incluir en ambas, pero en texto buscar con word boundaries
        if brand_lower.startswith('get') and len(brand_lower) > 3:
            short_variation = brand_lower[3:]
            domain_variations.add(short_variation)
            text_variations.add(short_variation)
        
        # Añadir variaciones con dominios
        for var in list(domain_variations):
            domain_variations.add(f"{var}.com")
            domain_variations.add(f"{var}.es")
            domain_variations.add(f"www.{var}")
        
        logger.debug(f"🔍 Brand variations:")
        logger.debug(f"   Domain (substring): {domain_variations}")
        logger.debug(f"   Text (word boundary): {text_variations}")
        
        # PRIORIDAD: Buscar primero en references (fuentes citadas) - tienen posiciones específicas
        # Usar el mismo criterio de orden que para global domains: index asc (0-based), luego orden natural
        enriched_refs = []
        for i, ref in enumerate(references):
            if not isinstance(ref, dict):
                continue
            
            idx = ref.get('index')
            # index es 0-based: 0, 1, 2, ...
            idx_num = idx if isinstance(idx, int) and idx >= 0 else None
            enriched_refs.append((idx_num, i, ref))
        enriched_refs.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 10**9, t[1]))

        for loop_idx, (index_value, original_idx, ref) in enumerate(enriched_refs):
            title = str(ref.get('title', '')).lower()
            link = str(ref.get('link', '')).lower()
            source = str(ref.get('source', '')).lower()
            snippet = str(ref.get('snippet', '')).lower()  # FIX CRÍTICO: Añadir snippet
            
            # Usar index del campo para position (1-based)
            actual_index = ref.get('index')
            position = (actual_index + 1) if isinstance(actual_index, int) and actual_index >= 0 else (loop_idx + 1)
            
            # Buscar marca con variaciones apropiadas por campo
            matched_variation = None
            matched_field = None
            
            # PRIORIDAD 1: Buscar en dominio del link (substring simple - MÁS CONFIABLE)
            try:
                from urllib.parse import urlparse
                netloc = urlparse(link).netloc.lower()
                if netloc.startswith('www.'):
                    netloc = netloc[4:]
                
                for v in domain_variations:
                    if v and v in netloc:
                        matched_variation = v
                        matched_field = 'domain'
                        break
            except Exception:
                pass
            
            # PRIORIDAD 2: Buscar en link completo (substring simple)
            if not matched_variation:
                for v in domain_variations:
                    if v and v in link:
                        matched_variation = v
                        matched_field = 'link'
                        break
            
            # PRIORIDAD 3: Buscar en texto con WORD BOUNDARIES (evita falsos positivos)
            # Ejemplo: "quipu" como palabra completa, NO dentro de "quipus" o "quipuxyz"
            if not matched_variation:
                for v in text_variations:
                    if not v:
                        continue
                    
                    # Crear patrón con word boundaries: \bquipu\b
                    # Esto matchea "quipu" pero NO "quipus" ni "antiquipu"
                    pattern = r'\b' + re.escape(v) + r'\b'
                    
                    if re.search(pattern, title):
                        matched_variation = v
                        matched_field = 'title'
                        break
                    elif re.search(pattern, snippet):
                        matched_variation = v
                        matched_field = 'snippet'
                        break
                    elif re.search(pattern, source):
                        matched_variation = v
                        matched_field = 'source'
                        break
            
            if matched_variation:
                result['brand_mentioned'] = True
                result['mention_position'] = position
                result['mention_context'] = ref.get('title', '')[:500]
                
                # Análisis de sentimiento mejorado (incluir snippet)
                text = f"{title} {source} {snippet}"
                positive_words = ['best', 'excellent', 'great', 'top', 'leading', 'recommended',
                                  'outstanding', 'superior', 'perfect', 'amazing', 'fantastic']
                negative_words = ['worst', 'bad', 'poor', 'avoid', 'problem', 'issue',
                                  'terrible', 'horrible', 'disappointing', 'unreliable']
                
                if any(word in text for word in positive_words):
                    result['sentiment'] = 'positive'
                elif any(word in text for word in negative_words):
                    result['sentiment'] = 'negative'
                
                # MEJORA: Logging detallado
                logger.info(f"✨ Brand '{brand_name}' found in reference at position {position}")
                logger.info(f"   → Matched variation: '{matched_variation}'")
                logger.info(f"   → Matched field: '{matched_field}'")
                logger.info(f"   → Reference index (0-based): {actual_index}")
                logger.info(f"   → Title: {ref.get('title', '')[:80]}...")
                logger.info(f"   → Sentiment: {result['sentiment']}")
                
                break
        
        # 2. Si NO se encontró en references, buscar en text_blocks (texto generado por IA)
        if not result['brand_mentioned']:
            text_blocks = text_blocks if isinstance(text_blocks, list) else []
            for block_idx, block in enumerate(text_blocks):
                if not isinstance(block, dict):
                    continue
                
                raw_text = block.get('text', '')
                text = str(raw_text).lower()
                reference_indexes = block.get('reference_indexes', [])
                
                # Buscar marca con word boundaries para evitar falsos positivos
                matched_variation = None
                for v in text_variations:
                    if not v:
                        continue
                    # Word boundary: "quipu" como palabra completa, NO dentro de "quipus"
                    pattern = r'\b' + re.escape(v) + r'\b'
                    if re.search(pattern, text):
                        matched_variation = v
                        break
                
                if matched_variation:
                    result['brand_mentioned'] = True
                    result['mention_context'] = str(raw_text)[:500]
                    result['mention_position'] = 0  # Posición 0 para menciones en texto de IA
                    
                    # Analizar sentimiento mejorado (con más palabras)
                    positive_words = ['best', 'excellent', 'great', 'top', 'leading', 'recommended', 
                                      'outstanding', 'superior', 'perfect', 'amazing', 'fantastic']
                    negative_words = ['worst', 'bad', 'poor', 'avoid', 'problem', 'issue', 
                                      'terrible', 'horrible', 'disappointing', 'unreliable']
                    
                    if any(word in text for word in positive_words):
                        result['sentiment'] = 'positive'
                    elif any(word in text for word in negative_words):
                        result['sentiment'] = 'negative'
                    
                    # MEJORA: Logging detallado
                    logger.info(f"✨ Brand '{brand_name}' found in AI text_blocks at position 0")
                    logger.info(f"   → Matched variation: '{matched_variation}'")
                    logger.info(f"   → Block index: {block_idx}")
                    logger.info(f"   → Referenced sources: {reference_indexes}")
                    logger.info(f"   → Sentiment: {result['sentiment']}")
                    
                    break
        
        if not result['brand_mentioned']:
            logger.info(f"❌ Brand '{brand_name}' not found in AI Mode results")
            logger.info(f"   → Analyzed {len(text_blocks)} text_blocks and {len(references)} references")
            logger.debug(f"   → Variations searched: domain={domain_variations}, text={text_variations}")
        
        return result

