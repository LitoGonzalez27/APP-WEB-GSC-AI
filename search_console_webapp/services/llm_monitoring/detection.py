"""
Servicio Principal Multi-LLM Brand Monitoring

IMPORTANTE:
- Usa ThreadPoolExecutor para paralelización (10x más rápido)
- Sentimiento analizado con provider activo del proyecto (fallback a keywords)
- Reutiliza funciones de ai_analysis.py para detección de marca
"""

import logging
import re
import json
import time
from datetime import date, datetime
import os
from urllib.parse import urlparse
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

from database import get_db_connection
from llm_monitoring_limits import (
    can_access_llm_monitoring,
    get_llm_plan_limits,
    get_user_monthly_llm_usage,
)
from services.llm_providers import LLMProviderFactory, BaseLLMProvider
from services.llm_providers.locale_helpers import (
    LocaleContext,
    create_locale_context,
    build_system_instruction,
    # Re-exported for backward compatibility with any external module
    # that used to import these names from llm_monitoring_service.
    # They now live in locale_helpers.py as single source of truth.
    LANGUAGE_NAMES,
    COUNTRY_NAMES,
)
from services.ai_analysis import extract_brand_variations, remove_accents

logger = logging.getLogger(__name__)


class _DetectionMixin:

    def analyze_brand_mention(
        self,
        response_text: str,
        brand_name: str = None,
        brand_domain: str = None,
        brand_keywords: List[str] = None,
        sources: List[Dict] = None,
        competitors: List[str] = None,
        competitor_domains: List[str] = None,
        competitor_keywords: List[str] = None,
        competitor_term_to_name: Dict[str, str] = None
    ) -> Dict:
        """
        Analiza si una respuesta menciona la marca y extrae contexto
        
        MEJORADO: 
        - Soporta dominios y palabras clave múltiples
        - ✨ NUEVO: Busca marca en sources/URLs (crítico para Perplexity, Claude, etc.)
        - ✨ NUEVO: Agrupa competidores por nombre (orange.es + orange = "Orange")
        
        Args:
            response_text: Respuesta del LLM
            brand_name: Nombre de la marca (legacy, opcional)
            brand_domain: Dominio de la marca (ej: getquipu.com)
            brand_keywords: Lista de palabras clave de marca (ej: ["quipu", "getquipu"])
            sources: Lista de fuentes/URLs citadas [{'url': '...', 'provider': '...'}]
            competitors: Lista de competidores (legacy, opcional)
            competitor_domains: Lista de dominios de competidores
            competitor_keywords: Lista de palabras clave de competidores
            competitor_term_to_name: Mapeo de términos a nombre de competidor para agrupación
            
        Returns:
            Dict con:
                brand_mentioned: bool
                mention_count: int
                mention_contexts: List[str]
                appears_in_numbered_list: bool
                position_in_list: Optional[int]
                total_items_in_list: Optional[int]
                competitors_mentioned: Dict[str, int]
        """
        # Construir lista de todas las variaciones de marca a buscar
        brand_variations = []
        
        # 1. Añadir dominio si existe
        if brand_domain:
            brand_variations.extend(extract_brand_variations(brand_domain.lower()))
        
        # 2. Añadir palabras clave si existen
        if brand_keywords:
            for keyword in brand_keywords:
                brand_variations.append(keyword.lower())
        
        # 3. Fallback: usar brand_name legacy si no hay nada más
        if not brand_variations and brand_name:
            brand_variations = extract_brand_variations(brand_name.lower())
        
        # Si no hay nada que buscar, retornar sin menciones
        if not brand_variations:
            return {
                'brand_mentioned': False,
                'mention_count': 0,
                'mention_contexts': [],
                'appears_in_numbered_list': False,
                'position_in_list': None,
                'total_items_in_list': None,
                'competitors_mentioned': {}
            }
        
        # Eliminar duplicados manteniendo orden
        seen = set()
        brand_variations = [x for x in brand_variations if not (x in seen or seen.add(x))]
        
        # Buscar menciones con tolerancia a acentos y coincidencias parciales
        mentions_found = []
        mention_contexts = []
        
        text_lower = response_text.lower()
        text_lower_no_accents = remove_accents(text_lower)
        
        for variation in brand_variations:
            var_lower = variation.lower()
            var_no_accents = remove_accents(var_lower)
            
            # Coincidencias exactas como palabra completa (con y sin acentos)
            patterns = [
                r'\b' + re.escape(var_lower) + r'\b',
                r'\b' + re.escape(var_no_accents) + r'\b'
            ]
            
            # Buscar en texto normal y sin acentos
            for idx, pattern in enumerate(patterns):
                hay_accents = (idx == 0)
                search_text = text_lower if hay_accents else text_lower_no_accents
                for match in re.finditer(pattern, search_text, re.IGNORECASE):
                    start = match.start()
                    end = match.end()
                    # Contexto basado en texto original cuando es posible
                    if hay_accents:
                        context_start = max(0, start - 150)
                        context_end = min(len(response_text), end + 150)
                        context = response_text[context_start:context_end].strip()
                        if context not in mention_contexts:
                            mention_contexts.append(context)
                    mentions_found.append((start, end))
            
            # ✅ ELIMINADO: Fallback substring que causaba falsos positivos
            # ("quipus", "antiquipu" detectaban incorrectamente)
            # Word boundaries (\b regex) son suficientemente robustos
        
        brand_mentioned = len(mentions_found) > 0
        mention_count = len(mentions_found)
        
        # ✨ MEJORADO: Buscar marca en sources/URLs (CRÍTICO para Perplexity, etc.)
        # Si no encontramos la marca en el texto, verificar si está en las fuentes citadas
        brand_found_in_sources = False
        normalized_brand_domain = self._normalize_domain(brand_domain)
        if sources and len(sources) > 0:
            for source in sources:
                source_url = source.get('url', '')
                source_host = self._extract_source_host(source_url)
                
                # Match estricto: SOLO dominio/subdominio de marca
                if normalized_brand_domain and self._domain_matches_host(normalized_brand_domain, source_host):
                    brand_found_in_sources = True
                    source_context = f"🔗 Brand domain {brand_domain} found in cited source: {source.get('url', 'N/A')}"
                    if source_context not in mention_contexts:
                        mention_contexts.append(source_context)
                    logger.debug(f"[BRAND DETECTION] ✅ Domain match in source host: {source_host}")
                    break
        
        # Si se encontró en sources, marcar como mencionado incluso si no está en el texto
        if brand_found_in_sources:
            brand_mentioned = True
            # Si no había menciones en texto, contar al menos 1 por la source
            if mention_count == 0:
                mention_count = 1
        
        # Detectar posición en listas numeradas
        list_info = self._detect_position_in_list(response_text, brand_variations)
        
        # ✨ NUEVO: Determinar position_source (text/link/both)
        brand_in_text = len(mentions_found) > 0
        brand_in_link = brand_found_in_sources
        
        position_source = None
        final_position = None  # ✨ CORREGIDO: Inicializar como None, solo asignar si brand_mentioned
        
        if brand_mentioned:
            # Solo asignar posición si la marca fue mencionada
            final_position = list_info['position']
            
            if brand_in_text and brand_in_link:
                position_source = 'both'
                # Mantener la posición detectada en texto (más fiable)
            elif brand_in_text:
                position_source = 'text'
                # Mantener la posición detectada
            elif brand_in_link:
                position_source = 'link'
                # Si solo está en link y no tiene posición, asignar 15 (baja visibilidad)
                if final_position is None:
                    final_position = 15
                    logger.info(f"[POSITION] 🔗 Brand only in link → Assigned position 15 (low visibility)")
        
        # Detectar competidores mencionados (tolerante a acentos)
        # Ahora soporta dominios y palabras clave, y TAMBIÉN busca en sources/enlaces
        # ✨ NUEVO: Agrupa por NOMBRE de competidor (orange.es + orange = "Orange")
        competitors_mentioned = {}
        
        # Construir lista de todos los competidores a buscar
        all_competitors = []
        
        # 1. Añadir dominios de competidores
        if competitor_domains:
            all_competitors.extend(competitor_domains)
        
        # 2. Añadir palabras clave de competidores
        if competitor_keywords:
            all_competitors.extend(competitor_keywords)
        
        # 3. Fallback: usar competitors legacy
        if not all_competitors and competitors:
            all_competitors.extend(competitors)
        
        # ✨ NUEVO: Crear mapeo inverso si no se proporcionó
        if not competitor_term_to_name:
            competitor_term_to_name = {}
            for term in all_competitors:
                # En modo legacy, usar nombre legible derivado del dominio o keyword
                term_name = self._competitor_display_name(term)
                competitor_term_to_name[term.lower()] = term_name
        
        # Buscar cada competidor y agrupar por nombre
        for competitor in all_competitors:
            comp_variations = extract_brand_variations(competitor.lower())
            found_in_this_response = False
            
            # A) Buscar en response_text
            for variation in comp_variations:
                if found_in_this_response:
                    break  # Ya encontramos este término, no seguir contando
                v_lower = variation.lower()
                v_no_accents = remove_accents(v_lower)
                # Solo verificar si EXISTE (no contar apariciones)
                pattern_normal = r'\b' + re.escape(v_lower) + r'\b'
                pattern_no_acc = r'\b' + re.escape(v_no_accents) + r'\b'
                if re.search(pattern_normal, text_lower, re.IGNORECASE) or \
                   re.search(pattern_no_acc, text_lower_no_accents, re.IGNORECASE):
                    found_in_this_response = True
            
            # B) ✨ NUEVO: Buscar también en sources/enlaces (importante para Perplexity)
            if not found_in_this_response and sources:
                competitor_domain = self._normalize_domain(competitor)
                for source in sources:
                    source_url = source.get('url', '').lower()
                    source_host = self._extract_source_host(source.get('url', ''))
                    # Verificar si alguna variación del competidor está en la URL
                    if competitor_domain and self._domain_matches_host(competitor_domain, source_host):
                        found_in_this_response = True
                        logger.debug(f"[COMPETITOR] Found domain '{competitor}' in source URL host: {source_host}")
                        break

                    for variation in comp_variations:
                        variation_lower = variation.lower()
                        if variation_lower in source_url:
                            variation_pattern = r'(?<![a-z0-9]){}(?![a-z0-9])'.format(re.escape(variation_lower))
                            if re.search(variation_pattern, source_url):
                                found_in_this_response = True
                                logger.debug(f"[COMPETITOR] Found '{competitor}' in source URL: {source_url}")
                                break
                    if found_in_this_response:
                        break
            
            # ✨ NUEVO: Agrupar bajo el NOMBRE del competidor
            if found_in_this_response:
                # Obtener nombre agrupado (ej: "orange.es" → "Orange")
                comp_name = competitor_term_to_name.get(competitor.lower(), competitor)
                # Marcar como mencionado (1 = mencionado en esta respuesta)
                # Usamos max() para evitar sobrescribir si ya se encontró otro término del mismo competidor
                competitors_mentioned[comp_name] = max(competitors_mentioned.get(comp_name, 0), 1)
        
        return {
            'brand_mentioned': brand_mentioned,
            'mention_count': mention_count,
            'mention_contexts': mention_contexts[:5],  # Máximo 5 contextos
            'appears_in_numbered_list': list_info['appears_in_list'],
            'position_in_list': final_position,  # ✨ MODIFICADO: usar final_position (puede ser 15 si solo link)
            'total_items_in_list': list_info['total_items'],
            'position_source': position_source,  # ✨ NUEVO: 'text', 'link', 'both'
            'competitors_mentioned': competitors_mentioned
        }
    

    def _detect_position_in_list(
        self,
        text: str,
        brand_variations: List[str]
    ) -> Dict:
        """
        ✨ MEJORADO: Detecta posición en múltiples formatos de listas y contexto textual
        
        PATRONES SOPORTADOS:
        - Listas numeradas: "1. Brand", "1) Brand", "**1.** Brand"
        - Listas con bullets: "• Brand", "- Brand", "● Brand"
        - Referencias: "[1] Brand", "(1) Brand"
        - Ordinales: "First, Brand...", "Second, Brand..."
        - Inferencia contextual: Posición del texto cuando no hay lista
        
        Returns:
            Dict con appears_in_list, position, total_items, detection_method
        """
        # ============================================
        # FASE 1: PATRONES EXPLÍCITOS DE POSICIÓN
        # ============================================
        
        # ✨ LÍMITE MÁXIMO DE POSICIÓN RAZONABLE
        # Las listas típicas en respuestas de LLM no superan 20-30 elementos
        # Posiciones > 30 son casi seguro falsos positivos (ej: años como 2025)
        MAX_VALID_POSITION = 30
        
        # Patrón 1: Listas numeradas (alta confianza)
        # ✨ CORREGIDO: Los patrones ahora requieren que el número esté al inicio de línea
        # para evitar falsos positivos como "(2025)" o "(25 €/mes)" que se confundían con posiciones
        numbered_patterns = [
            r'(?:^|\n)\s*(\d+)\.\s*[*_]*(.+?)(?:\n|$)',       # "1. Item\n" al inicio de línea
            r'(?:^|\n)\s*(\d+)\)\s*[*_]*(.+?)(?:\n|$)',       # "1) Item\n" al inicio de línea
            r'(?:^|\n)\s*\*\*(\d+)\.\*\*\s*(.+?)(?:\n|$)',    # "**1.** Item\n" al inicio de línea
            r'(?:^|\n)\s*\*\*(\d+)\)\*\*\s*(.+?)(?:\n|$)',    # "**1)** Item\n" al inicio de línea
            r'(?:^|\n)\s*#\s*(\d+)\s*[:\.\-]\s*(.+?)(?:\n|$)',# "# 1: Item\n" al inicio de línea
        ]
        
        for pattern in numbered_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            
            for match in matches:
                position = int(match.group(1))
                item_text = match.group(2).strip()
                
                # ✨ VALIDACIÓN: Ignorar posiciones > MAX_VALID_POSITION (falsos positivos como años)
                if position > MAX_VALID_POSITION:
                    logger.debug(f"[POSITION] ⚠️ Ignored position {position} (exceeds max {MAX_VALID_POSITION}, likely false positive)")
                    continue
                
                # Verificar si alguna variación de la marca está en el item
                for variation in brand_variations:
                    if variation.lower() in item_text.lower():
                        # Encontrar total de items en la lista (solo posiciones válidas)
                        all_matches = [m for m in re.finditer(pattern, text, re.MULTILINE) 
                                       if int(m.group(1)) <= MAX_VALID_POSITION]
                        total_items = len(all_matches)
                        
                        logger.info(f"[POSITION] ✅ Numbered list detected: Position {position}/{total_items}")
                        return {
                            'appears_in_list': True,
                            'position': position,
                            'total_items': total_items,
                            'detection_method': 'numbered_list'
                        }
        
            # ❌ ELIMINADO: Patrón 2 - Referencias numeradas [1], (1), etc.
            # Las referencias bibliográficas [7], [2], etc. NO indican posición en rankings
            # Solo indican la fuente citada. Confundirlas con posiciones genera datos incorrectos.
            # 
            # Ejemplo incorrecto:
            #   "...tratamientos de fertilidad[2][7]. HM Fertility[19] ofrece..."
            #   ❌ Esto NO significa que HM Fertility está en posición 19
            #   ✅ Solo significa que la referencia bibliográfica #19 es hmfertility.com
            #
            # Por esta razón, este patrón ha sido eliminado del algoritmo.
        
        # Patrón 3: Ordinales multiidioma (en, es, fr, de, it, pt)
        ordinal_map = {
            # English
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
            # Spanish
            'primero': 1, 'segundo': 2, 'tercero': 3, 'cuarto': 4, 'quinto': 5,
            'sexto': 6, 'séptimo': 7, 'octavo': 8, 'noveno': 9, 'décimo': 10,
            'primera': 1, 'segunda': 2, 'tercera': 3, 'cuarta': 4, 'quinta': 5,
            # French
            'premier': 1, 'première': 1, 'deuxième': 2, 'troisième': 3,
            'quatrième': 4, 'cinquième': 5, 'sixième': 6, 'septième': 7,
            'huitième': 8, 'neuvième': 9, 'dixième': 10,
            # German
            'erste': 1, 'erster': 1, 'zweite': 2, 'zweiter': 2, 'dritte': 3,
            'dritter': 3, 'vierte': 4, 'fünfte': 5, 'sechste': 6,
            'siebte': 7, 'achte': 8, 'neunte': 9, 'zehnte': 10,
            # Italian
            'primo': 1, 'prima': 1, 'secondo': 2, 'terzo': 3, 'quarto': 4,
            'quinto': 5, 'sesto': 6, 'settimo': 7, 'ottavo': 8,
            'nono': 9, 'decimo': 10,
            # Portuguese
            'primeiro': 1, 'primeira': 1, 'segundo': 2, 'terceiro': 3,
            'quarto': 4, 'quinto': 5, 'sexto': 6, 'sétimo': 7,
            'oitavo': 8, 'nono': 9, 'décimo': 10,
        }
        
        for ordinal, position in ordinal_map.items():
            # Pattern: "First, Brand..." or "En primer lugar, Brand..."
            ordinal_pattern = rf'\b{ordinal}\b[,:]?\s*(.{{0,100}}?)\b(' + '|'.join(re.escape(v) for v in brand_variations) + r')\b'
            match = re.search(ordinal_pattern, text, re.IGNORECASE)
            if match:
                logger.info(f"[POSITION] ✅ Ordinal detected: {ordinal} → Position {position}")
                return {
                    'appears_in_list': True,
                    'position': position,
                    'total_items': None,
                    'detection_method': 'ordinal'
                }
        
        # Patrón 4: Listas con bullets (inferir orden)
        bullet_patterns = [
            r'[•●○▪]\s*(.+?)(?:\n|$)',      # Bullets
            r'[-–—]\s+(.+?)(?:\n|$)',        # Guiones
            r'[►▸▹]\s*(.+?)(?:\n|$)',        # Flechas
        ]
        
        for bullet_pattern in bullet_patterns:
            matches = list(re.finditer(bullet_pattern, text, re.MULTILINE))
            if len(matches) >= 2:  # Al menos 2 items con bullets
                for idx, match in enumerate(matches, start=1):
                    item_text = match.group(1).strip()
                    
                    for variation in brand_variations:
                        if variation.lower() in item_text.lower():
                            logger.info(f"[POSITION] ✅ Bullet list detected: Position {idx}/{len(matches)}")
                            return {
                                'appears_in_list': True,
                                'position': idx,
                                'total_items': len(matches),
                                'detection_method': 'bullet_list'
                            }
        
        # ============================================
        # FASE 2: INFERENCIA POR CONTEXTO TEXTUAL
        # ============================================
        
        # Si llegamos aquí, no hay lista explícita
        # Inferir posición basada en dónde aparece la marca en el texto
        
        for variation in brand_variations:
            pattern = r'\b' + re.escape(variation.lower()) + r'\b'
            match = re.search(pattern, text.lower())
            
            if match:
                mention_position = match.start()
                text_length = len(text)
                
                # Calcular posición relativa (0-1)
                relative_position = mention_position / text_length if text_length > 0 else 0.5
                
                # Inferir posición basada en ubicación en el texto
                if relative_position < 0.15:  # Primeros 15% del texto
                    inferred_position = 1
                    logger.info(f"[POSITION] 🔍 Context inference: Early mention (char {mention_position}) → Position 1")
                elif relative_position < 0.30:  # 15-30%
                    inferred_position = 3
                    logger.info(f"[POSITION] 🔍 Context inference: Early-mid mention (char {mention_position}) → Position 3")
                elif relative_position < 0.50:  # 30-50%
                    inferred_position = 5
                    logger.info(f"[POSITION] 🔍 Context inference: Mid mention (char {mention_position}) → Position 5")
                elif relative_position < 0.70:  # 50-70%
                    inferred_position = 8
                    logger.info(f"[POSITION] 🔍 Context inference: Late-mid mention (char {mention_position}) → Position 8")
                else:  # 70%+
                    inferred_position = 12
                    logger.info(f"[POSITION] 🔍 Context inference: Late mention (char {mention_position}) → Position 12")
                
                return {
                    'appears_in_list': False,  # No es lista explícita
                    'position': inferred_position,
                    'total_items': None,
                    'detection_method': 'context_inference',
                    'relative_position': round(relative_position, 3),
                    'char_position': mention_position
                }
        
        # No se detectó la marca en absoluto
        return {
            'appears_in_list': False,
            'position': None,
            'total_items': None,
            'detection_method': None
        }
    
    # =====================================================
    # ANÁLISIS DE SENTIMIENTO
    # =====================================================
