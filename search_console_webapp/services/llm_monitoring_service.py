"""
Servicio Principal Multi-LLM Brand Monitoring

IMPORTANTE:
- Usa ThreadPoolExecutor para paralelización (10x más rápido)
- Sentimiento analizado con LLM (Gemini Flash), no keywords
- Reutiliza funciones de ai_analysis.py para detección de marca
"""

import logging
import re
import json
import time
from datetime import date, datetime
import os
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

from database import get_db_connection
from services.llm_providers import LLMProviderFactory, BaseLLMProvider
from services.ai_analysis import extract_brand_variations, remove_accents

logger = logging.getLogger(__name__)


class MultiLLMMonitoringService:
    """
    Servicio principal para monitorización de marca en múltiples LLMs
    
    Características:
    - Genera queries automáticamente
    - Ejecuta en paralelo (ThreadPoolExecutor)
    - Analiza menciones de marca
    - Calcula métricas (mention rate, share of voice, sentimiento)
    - Guarda resultados en BD
    
    Uso:
        service = MultiLLMMonitoringService(api_keys)
        result = service.analyze_project(project_id=1)
    """
    
    def __init__(self, api_keys: Dict[str, str] = None):
        """
        Inicializa el servicio
        
        Args:
            api_keys: Dict con API keys por proveedor (opcional)
                     Si es None, usa variables de entorno (recomendado)
                     Ejemplo: {'openai': 'sk-...', 'google': 'AIza...', ...}
        """
        logger.info("🚀 Inicializando MultiLLMMonitoringService...")
        
        # Crear todos los proveedores usando Factory
        # Si api_keys es None, el Factory usará variables de entorno
        self.providers = LLMProviderFactory.create_all_providers(
            api_keys,
            validate_connections=True
        )
        
        if len(self.providers) == 0:
            logger.error("❌ No se pudo crear ningún proveedor LLM")
            raise ValueError("No hay proveedores LLM disponibles")
        
        # Proveedor dedicado para análisis de sentimiento (Gemini Flash - más barato)
        self.sentiment_analyzer = self.providers.get('google')
        
        if not self.sentiment_analyzer:
            logger.warning("⚠️ Gemini no disponible, sentimiento será por keywords")
        
        # ✨ NUEVO: Límites de concurrencia por proveedor (para evitar rate limits)
        # Configurable vía variables de entorno. 
        # IMPORTANTE: Para cron diario, preferimos fiabilidad sobre velocidad
        # Valores MUY conservadores por defecto para asegurar 100% de completitud
        self.provider_concurrency = {
            'openai': int(os.getenv('OPENAI_CONCURRENCY', '2')),      # 2 (GPT-5 es lento, evitar rate limits)
            'google': int(os.getenv('GOOGLE_CONCURRENCY', '5')),      # 5 (Gemini tiene límites estrictos)
            'anthropic': int(os.getenv('ANTHROPIC_CONCURRENCY', '3')), # 3 (Claude es estable)
            'perplexity': int(os.getenv('PERPLEXITY_CONCURRENCY', '4')) # 4 (Perplexity es rápido)
        }
        # Crear semáforos por proveedor
        self.provider_semaphores = {
            name: Semaphore(max(1, limit)) for name, limit in self.provider_concurrency.items()
        }
        logger.info("🛡️ Límites de concurrencia por proveedor:")
        for pname, limit in self.provider_concurrency.items():
            if pname in self.providers:
                logger.info(f"   • {pname}: {limit} concurrente(s)")
        
        logger.info(f"✅ Servicio inicializado con {len(self.providers)} proveedores")
    
    # =====================================================
    # GENERACIÓN DE QUERIES
    # =====================================================
    
    def generate_queries_for_project(
        self,
        brand_name: str,
        industry: str,
        language: str = 'es',
        competitors: List[str] = None,
        count: int = 15
    ) -> List[Dict]:
        """
        Genera queries automáticamente para un proyecto
        
        Args:
            brand_name: Nombre de la marca
            industry: Industria/sector
            language: Idioma ('es' o 'en')
            competitors: Lista de competidores
            count: Número de queries a generar
            
        Returns:
            Lista de dicts con query_text, language, query_type
            
        Example:
            >>> queries = service.generate_queries_for_project(
            ...     brand_name="Quipu",
            ...     industry="software de facturación",
            ...     language="es",
            ...     competitors=["Holded", "Sage"]
            ... )
        """
        queries = []
        competitors = competitors or []
        
        # Templates por idioma
        templates = {
            'es': {
                'general': [
                    f"¿Cuáles son las mejores herramientas de {industry}?",
                    f"Top 10 empresas de {industry}",
                    f"¿Qué software de {industry} recomiendas?",
                    f"Comparativa de {industry}",
                    f"Mejores soluciones para {industry}",
                    f"¿Cómo elegir {industry}?",
                    f"Ventajas y desventajas de {industry}",
                    f"Opiniones sobre {industry}",
                    f"Alternativas de {industry}",
                    f"Precio de {industry}",
                ],
                'with_brand': [
                    f"¿Qué es {brand_name}?",
                    f"Opiniones sobre {brand_name}",
                    f"¿{brand_name} es bueno?",
                    f"Ventajas de {brand_name}",
                    f"Alternativas a {brand_name}",
                ],
                'with_competitors': [
                    f"{{competitor}} vs alternativas de {industry}",
                    f"¿{{competitor}} o hay mejores opciones?",
                    f"Comparar {{competitor}} con otros de {industry}",
                ]
            },
            'en': {
                'general': [
                    f"What are the best {industry} tools?",
                    f"Top 10 {industry} companies",
                    f"Which {industry} software do you recommend?",
                    f"{industry} comparison",
                    f"Best {industry} solutions",
                    f"How to choose {industry}?",
                    f"{industry} pros and cons",
                    f"{industry} reviews",
                    f"{industry} alternatives",
                    f"{industry} pricing",
                ],
                'with_brand': [
                    f"What is {brand_name}?",
                    f"{brand_name} reviews",
                    f"Is {brand_name} good?",
                    f"{brand_name} advantages",
                    f"Alternatives to {brand_name}",
                ],
                'with_competitors': [
                    f"{{competitor}} vs {industry} alternatives",
                    f"{{competitor}} or better options?",
                    f"Compare {{competitor}} with other {industry}",
                ]
            }
        }
        
        lang_templates = templates.get(language, templates['es'])
        
        # Queries generales (60%)
        general_count = int(count * 0.6)
        for template in lang_templates['general'][:general_count]:
            queries.append({
                'query_text': template,
                'language': language,
                'query_type': 'general'
            })
        
        # Queries con marca (20%)
        brand_count = int(count * 0.2)
        for template in lang_templates['with_brand'][:brand_count]:
            queries.append({
                'query_text': template,
                'language': language,
                'query_type': 'with_brand'
            })
        
        # Queries con competidores (20%)
        if competitors:
            comp_count = count - len(queries)
            comp_templates = lang_templates['with_competitors']
            
            for i in range(comp_count):
                competitor = competitors[i % len(competitors)]
                template = comp_templates[i % len(comp_templates)]
                
                queries.append({
                    'query_text': template.format(competitor=competitor),
                    'language': language,
                    'query_type': 'with_competitor'
                })
        
        logger.info(f"📝 Generadas {len(queries)} queries para {brand_name}")
        return queries[:count]
    
    # =====================================================
    # ANÁLISIS DE MENCIONES
    # =====================================================
    
    def analyze_brand_mention(
        self,
        response_text: str,
        brand_name: str = None,
        brand_domain: str = None,
        brand_keywords: List[str] = None,
        sources: List[Dict] = None,
        competitors: List[str] = None,
        competitor_domains: List[str] = None,
        competitor_keywords: List[str] = None
    ) -> Dict:
        """
        Analiza si una respuesta menciona la marca y extrae contexto
        
        MEJORADO: 
        - Soporta dominios y palabras clave múltiples
        - ✨ NUEVO: Busca marca en sources/URLs (crítico para Perplexity, Claude, etc.)
        
        Args:
            response_text: Respuesta del LLM
            brand_name: Nombre de la marca (legacy, opcional)
            brand_domain: Dominio de la marca (ej: getquipu.com)
            brand_keywords: Lista de palabras clave de marca (ej: ["quipu", "getquipu"])
            sources: Lista de fuentes/URLs citadas [{'url': '...', 'provider': '...'}]
            competitors: Lista de competidores (legacy, opcional)
            competitor_domains: Lista de dominios de competidores
            competitor_keywords: Lista de palabras clave de competidores
            
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
        if sources and len(sources) > 0:
            for source in sources:
                source_url = source.get('url', '').lower()
                
                # PRIORIDAD 1: Buscar dominio COMPLETO como dominio válido (más restrictivo y preciso)
                if brand_domain:
                    domain_clean = brand_domain.lower().replace('www.', '').replace('.com', '').replace('.es', '').replace('.net', '').replace('.org', '')
                    
                    # Patrón para buscar como dominio real (entre :// y / o final)
                    # Ejemplos que coinciden: "https://getkipu.com/", "http://www.getkipu.com", "getkipu.com/page"
                    # Ejemplos que NO coinciden: "https://wikipedia.org/wiki/Kipuka" (kipuka ≠ kipu)
                    domain_patterns = [
                        r'://(?:www\.)?{}\.(?:com|es|net|org|io|co)(?:/|$)'.format(re.escape(domain_clean)),  # Con protocolo
                        r'^(?:www\.)?{}\.(?:com|es|net|org|io|co)(?:/|$)'.format(re.escape(domain_clean)),  # Sin protocolo al inicio
                    ]
                    
                    for pattern in domain_patterns:
                        if re.search(pattern, source_url):
                            brand_found_in_sources = True
                            source_context = f"🔗 Brand domain {brand_domain} found in cited source: {source.get('url', 'N/A')}"
                            if source_context not in mention_contexts:
                                mention_contexts.append(source_context)
                            logger.debug(f"[BRAND DETECTION] ✅ Domain match in source URL via pattern: {pattern}")
                            break
                    
                    if brand_found_in_sources:
                        break
                
                # PRIORIDAD 2: Buscar variaciones de marca en la URL (solo si no encontramos dominio completo)
                # Esto es más permisivo pero puede tener falsos positivos
                # Solo buscar variaciones largas (>=5 chars) para minimizar falsos positivos
                for variation in brand_variations:
                    if len(variation) >= 5 and variation.lower() in source_url:
                        # Verificación adicional: asegurarse de que no es parte de otra palabra
                        # Por ejemplo, evitar detectar "kipu" en "kipuka"
                        var_pattern = r'\b{}\b'.format(re.escape(variation.lower()))
                        if re.search(var_pattern, source_url):
                            brand_found_in_sources = True
                            source_context = f"🔗 Brand '{variation}' found in cited source: {source.get('url', 'N/A')}"
                            if source_context not in mention_contexts:
                                mention_contexts.append(source_context)
                            logger.debug(f"[BRAND DETECTION] ✅ Variation match in source URL: {variation}")
                            break
                
                if brand_found_in_sources:
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
        final_position = list_info['position']
        
        if brand_mentioned:
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
        
        # Buscar cada competidor
        for competitor in all_competitors:
            comp_variations = extract_brand_variations(competitor.lower())
            comp_count = 0
            
            # A) Buscar en response_text
            for variation in comp_variations:
                v_lower = variation.lower()
                v_no_accents = remove_accents(v_lower)
                # Contar en texto normal y sin acentos usando límites de palabra
                pattern_normal = r'\b' + re.escape(v_lower) + r'\b'
                pattern_no_acc = r'\b' + re.escape(v_no_accents) + r'\b'
                comp_count += len(re.findall(pattern_normal, text_lower, re.IGNORECASE))
                comp_count += len(re.findall(pattern_no_acc, text_lower_no_accents, re.IGNORECASE))
            
            # B) ✨ NUEVO: Buscar también en sources/enlaces (importante para Perplexity)
            if sources:
                for source in sources:
                    source_url = source.get('url', '').lower()
                    # Verificar si alguna variación del competidor está en la URL
                    for variation in comp_variations:
                        if variation.lower() in source_url:
                            comp_count += 1
                            logger.debug(f"[COMPETITOR] Found '{competitor}' in source URL: {source_url}")
                            break  # Solo contar una vez por URL
            
            if comp_count > 0:
                competitors_mentioned[competitor] = comp_count
        
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
        
        # Patrón 1: Listas numeradas (alta confianza)
        numbered_patterns = [
            r'(\d+)\.\s*[*_]*(.+?)(?:\n|$)',           # "1. Item\n"
            r'(\d+)\)\s*[*_]*(.+?)(?:\n|$)',           # "1) Item\n"
            r'\*\*(\d+)\.\*\*\s*(.+?)(?:\n|$)',        # "**1.** Item\n"
            r'\*\*(\d+)\)\*\*\s*(.+?)(?:\n|$)',        # "**1)** Item\n"
            r'#\s*(\d+)\s*[:\.\-]\s*(.+?)(?:\n|$)',    # "# 1: Item\n"
        ]
        
        for pattern in numbered_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            
            for match in matches:
                position = int(match.group(1))
                item_text = match.group(2).strip()
                
                # Verificar si alguna variación de la marca está en el item
                for variation in brand_variations:
                    if variation.lower() in item_text.lower():
                        # Encontrar total de items en la lista
                        all_matches = list(re.finditer(pattern, text, re.MULTILINE))
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
        
        # Patrón 3: Ordinales en inglés (First, Second, etc.)
        ordinal_map = {
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
            'primero': 1, 'segundo': 2, 'tercero': 3, 'cuarto': 4, 'quinto': 5,
            'sexto': 6, 'séptimo': 7, 'octavo': 8, 'noveno': 9, 'décimo': 10
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
    
    def _analyze_sentiment_with_llm(
        self,
        contexts: List[str],
        brand_name: str
    ) -> Dict:
        """
        Analiza el sentimiento hacia la marca usando LLM (Gemini Flash)
        
        IMPORTANTE: Usa LLM en vez de keywords porque:
        - "No es el mejor" → Negativo (keywords fallarían)
        - "Es caro pero vale la pena" → Positivo (keywords lo marcarían negativo)
        
        Args:
            contexts: Lista de contextos donde se menciona la marca
            brand_name: Nombre de la marca
            
        Returns:
            Dict con:
                sentiment: 'positive', 'neutral', 'negative'
                score: float (0.0 a 1.0)
                method: 'llm' o 'keywords' (fallback)
        """
        if not contexts:
            return {
                'sentiment': 'neutral',
                'score': 0.5,
                'method': 'none'
            }
        
        # Si no hay Gemini disponible, usar fallback
        if not self.sentiment_analyzer:
            return self._analyze_sentiment_keywords(contexts)
        
        # Unir contextos (máximo 1000 chars para no gastar mucho)
        combined_contexts = ' ... '.join(contexts)[:1000]
        
        # Prompt estructurado para obtener JSON
        prompt = f"""Analiza el sentimiento hacia "{brand_name}" en el siguiente texto.

Responde SOLO con JSON en este formato exacto:
{{"sentiment": "positive/neutral/negative", "score": 0.XX}}

Donde:
- sentiment: "positive", "neutral" o "negative"
- score: 0.0 (muy negativo) a 1.0 (muy positivo)

Texto a analizar:
{combined_contexts}

JSON:"""
        
        try:
            result = self.sentiment_analyzer.execute_query(prompt)
            
            if not result['success']:
                logger.warning(f"⚠️ Sentimiento LLM falló, usando keywords")
                return self._analyze_sentiment_keywords(contexts)
            
            # Parsear JSON de la respuesta
            response_text = result['content'].strip()
            
            # Extraer JSON (puede venir con texto adicional)
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                sentiment_data = json.loads(json_match.group())
                
                return {
                    'sentiment': sentiment_data.get('sentiment', 'neutral'),
                    'score': float(sentiment_data.get('score', 0.5)),
                    'method': 'llm'
                }
            else:
                logger.warning(f"⚠️ No se pudo extraer JSON, usando keywords")
                return self._analyze_sentiment_keywords(contexts)
                
        except Exception as e:
            logger.error(f"❌ Error analizando sentimiento con LLM: {e}")
            return self._analyze_sentiment_keywords(contexts)
    
    def _analyze_sentiment_keywords(self, contexts: List[str]) -> Dict:
        """
        Fallback: análisis de sentimiento por keywords
        
        Método simple pero funciona en ~70% de casos
        """
        combined = ' '.join(contexts).lower()
        
        positive_words = ['excelente', 'bueno', 'mejor', 'recomiendo', 'fantástico',
                         'increíble', 'perfecto', 'great', 'excellent', 'best', 'amazing']
        negative_words = ['malo', 'peor', 'no recomiendo', 'terrible', 'horrible',
                         'decepcionante', 'bad', 'worst', 'terrible', 'disappointing']
        
        positive_count = sum(1 for word in positive_words if word in combined)
        negative_count = sum(1 for word in negative_words if word in combined)
        
        if positive_count > negative_count:
            sentiment = 'positive'
            score = min(0.7 + (positive_count * 0.05), 0.95)
        elif negative_count > positive_count:
            sentiment = 'negative'
            score = max(0.3 - (negative_count * 0.05), 0.05)
        else:
            sentiment = 'neutral'
            score = 0.5
        
        return {
            'sentiment': sentiment,
            'score': score,
            'method': 'keywords'
        }
    
    # =====================================================
    # ANÁLISIS DE PROYECTO (MÉTODO PRINCIPAL)
    # =====================================================
    
    def analyze_project(
        self,
        project_id: int,
        max_workers: int = 8,  # Reducido de 10 a 8 para más estabilidad
        analysis_date: date = None
    ) -> Dict:
        """
        Analiza un proyecto completo en todos los LLMs habilitados
        
        ⚡ OPTIMIZADO PARA CRON DIARIO:
        - Prioriza COMPLETITUD sobre velocidad
        - Sistema de reintentos robusto (4 intentos con delays incrementales)
        - Concurrencia conservadora por provider para evitar rate limits
        - Timeouts generosos para queries lentas (GPT-5)
        
        TIEMPOS ESPERADOS (22 queries × 4 LLMs = 88 tareas):
        - Claude: ~2-5 minutos (rápido)
        - Gemini: ~2-5 minutos (rápido) 
        - Perplexity: ~3-8 minutos (búsqueda en tiempo real)
        - OpenAI GPT-5: ~10-20 minutos (lento pero potente)
        - TOTAL: ~15-30 minutos (aceptable para cron diario)
        
        Args:
            project_id: ID del proyecto a analizar
            max_workers: Número de threads paralelos (default: 8, conservador)
            analysis_date: Fecha del análisis (default: hoy)
            
        Returns:
            Dict con métricas globales y completitud por LLM
        """
        if analysis_date is None:
            # Usar zona horaria configurada para que la fecha refleje el día local del negocio
            tz_name = os.getenv('APP_TZ', 'Europe/Madrid')
            if ZoneInfo is not None:
                analysis_date = datetime.now(ZoneInfo(tz_name)).date()
            else:
                analysis_date = date.today()
        start_time = time.time()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"🔍 ANALIZANDO PROYECTO #{project_id}")
        logger.info("=" * 70)
        
        # Obtener proyecto de BD
        conn = get_db_connection()
        if not conn:
            raise Exception("No se pudo conectar a BD")
        
        try:
            cur = conn.cursor()
            
            # Obtener datos del proyecto (incluyendo nuevos campos)
            cur.execute("""
                SELECT 
                    id, user_id, name, brand_name, industry,
                    brand_domain, brand_keywords,
                    enabled_llms, competitors, 
                    competitor_domains, competitor_keywords,
                    selected_competitors,
                    language, queries_per_llm
                FROM llm_monitoring_projects
                WHERE id = %s AND is_active = TRUE
            """, (project_id,))
            
            project = cur.fetchone()
            
            if not project:
                raise Exception(f"Proyecto #{project_id} no encontrado o inactivo")
            
            logger.info(f"📋 Proyecto: {project['name']}")
            logger.info(f"   Marca: {project['brand_name']}")
            logger.info(f"   Industria: {project['industry']}")
            logger.info(f"   LLMs habilitados: {project['enabled_llms']}")
            
            # Obtener o generar queries
            cur.execute("""
                SELECT id, query_text, language, query_type
                FROM llm_monitoring_queries
                WHERE project_id = %s AND is_active = TRUE
            """, (project_id,))
            
            queries = cur.fetchall()
            
            # Si no hay queries, generarlas
            if len(queries) == 0:
                logger.info("📝 No hay queries, generando automáticamente...")
                
                generated_queries = self.generate_queries_for_project(
                    brand_name=project['brand_name'],
                    industry=project['industry'],
                    language=project['language'],
                    competitors=project['competitors'] or [],
                    count=project['queries_per_llm']
                )
                
                # Insertar en BD
                for q in generated_queries:
                    cur.execute("""
                        INSERT INTO llm_monitoring_queries 
                        (project_id, query_text, language, query_type)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (project_id, query_text) DO NOTHING
                        RETURNING id
                    """, (project_id, q['query_text'], q['language'], q['query_type']))
                    
                conn.commit()
                
                # Recargar queries
                cur.execute("""
                    SELECT id, query_text, language, query_type
                    FROM llm_monitoring_queries
                    WHERE project_id = %s AND is_active = TRUE
                """, (project_id,))
                
                queries = cur.fetchall()
                logger.info(f"   ✅ {len(queries)} queries creadas")
            
            logger.info(f"   📊 {len(queries)} queries a ejecutar")
            
            # Filtrar LLMs activos
            enabled_llms = project['enabled_llms'] or []
            active_providers = {
                name: provider 
                for name, provider in self.providers.items()
                if name in enabled_llms
            }
            
            if len(active_providers) == 0:
                raise Exception("No hay proveedores LLM habilitados para este proyecto")
            
            logger.info(f"   🤖 {len(active_providers)} proveedores habilitados")
            logger.info("")
            
            # ✨ NUEVO: Health Check Pre-Análisis
            logger.info("=" * 70)
            logger.info("🏥 HEALTH CHECK DE PROVIDERS")
            logger.info("=" * 70)
            logger.info("")
            
            healthy_providers = {}
            unhealthy_providers = []
            
            for name, provider in active_providers.items():
                logger.info(f"🔍 Testeando {name}...")
                
                try:
                    # Test rápido con query simple
                    test_result = provider.execute_query("Hi")
                    
                    if test_result.get('success'):
                        healthy_providers[name] = provider
                        logger.info(f"   ✅ {name} respondió OK en {test_result.get('response_time_ms', 0)}ms")
                    else:
                        unhealthy_providers.append(name)
                        error = test_result.get('error', 'Unknown error')
                        logger.error(f"   ❌ {name} falló: {error}")
                        logger.error(f"   ⚠️  Este provider será EXCLUIDO del análisis")
                        
                except Exception as e:
                    unhealthy_providers.append(name)
                    logger.error(f"   ❌ {name} excepción: {e}")
                    logger.error(f"   ⚠️  Este provider será EXCLUIDO del análisis")
            
            # Usar solo providers saludables
            active_providers = healthy_providers
            
            logger.info("")
            logger.info("=" * 70)
            logger.info(f"✅ PROVIDERS SALUDABLES: {len(active_providers)}/{len(enabled_llms)}")
            logger.info("=" * 70)
            logger.info(f"Activos: {', '.join(active_providers.keys())}")
            if unhealthy_providers:
                logger.warning(f"⚠️  Excluidos: {', '.join(unhealthy_providers)}")
                logger.warning(f"   → El análisis continuará sin estos providers")
            logger.info("")
            
            if len(active_providers) == 0:
                logger.error("❌ NINGÚN PROVIDER ESTÁ DISPONIBLE")
                logger.error("   No se puede realizar el análisis")
                cur.close()
                conn.close()
                return {
                    'project_id': project_id,
                    'error': 'No providers available after health check',
                    'analysis_date': str(analysis_date),
                    'unhealthy_providers': unhealthy_providers
                }
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo proyecto: {e}")
            cur.close()
            conn.close()
            raise
        
        # ✨ Parsear selected_competitors para extraer dominios y keywords
        selected_competitors = project.get('selected_competitors', [])
        competitor_domains_flat = []
        competitor_keywords_flat = []
        
        if selected_competitors and len(selected_competitors) > 0:
            for comp in selected_competitors:
                domain = comp.get('domain', '').strip()
                keywords = comp.get('keywords', [])
                
                if domain:
                    competitor_domains_flat.append(domain)
                if keywords:
                    competitor_keywords_flat.extend(keywords)
            
            logger.info(f"   🏢 {len(selected_competitors)} competidores configurados:")
            for comp in selected_competitors:
                comp_name = comp.get('name', 'Unknown')
                comp_domain = comp.get('domain', 'N/A')
                comp_keywords = comp.get('keywords', [])
                logger.info(f"      • {comp_name}: {comp_domain} → {comp_keywords}")
        else:
            # Fallback a campos legacy si no hay selected_competitors
            competitor_domains_flat = project.get('competitor_domains', [])
            competitor_keywords_flat = project.get('competitor_keywords', [])
            if competitor_domains_flat or competitor_keywords_flat:
                logger.info(f"   ⚠️  Usando competitor fields legacy (migrar a selected_competitors)")
        
        # Crear todas las tareas (combinaciones de LLM + query)
        tasks = []
        for llm_name, provider in active_providers.items():
            for query in queries:
                tasks.append({
                    'project_id': project_id,
                    'query_id': query['id'],
                    'query_text': query['query_text'],
                    'llm_name': llm_name,
                    'provider': provider,
                    'brand_name': project['brand_name'],  # Legacy
                    'brand_domain': project.get('brand_domain'),
                    'brand_keywords': project.get('brand_keywords', []),
                    'competitors': project.get('competitors') or [],  # Legacy
                    'competitor_domains': competitor_domains_flat,  # ✨ NUEVO: Array plano
                    'competitor_keywords': competitor_keywords_flat,  # ✨ NUEVO: Array plano
                    'analysis_date': analysis_date
                })
        
        total_tasks = len(tasks)
        logger.info(f"⚡ Ejecutando {total_tasks} tareas en paralelo (max_workers={max_workers})...")
        logger.info(f"   Concurrencia por provider:")
        for pname in active_providers.keys():
            logger.info(f"      • {pname}: {self.provider_concurrency.get(pname, 1)} workers")
        logger.info(f"   🎯 Objetivo: 100% de completitud (velocidad no es crítica)")
        logger.info("")
        
        # Ejecutar en paralelo con ThreadPoolExecutor
        results_by_llm = {name: [] for name in active_providers.keys()}
        completed_tasks = 0
        failed_tasks = 0
        failed_task_list = []  # ✨ NUEVO: Registrar tareas fallidas para reintentos
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Enviar todas las tareas
            future_to_task = {
                executor.submit(self._execute_single_query_task, task): task
                for task in tasks
            }
            
            # Procesar resultados conforme se completan
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                
                try:
                    result = future.result()
                    
                    if result['success']:
                        results_by_llm[task['llm_name']].append(result)
                        completed_tasks += 1
                        
                        # Log cada 10 tareas
                        if completed_tasks % 10 == 0:
                            logger.info(f"   ✅ {completed_tasks}/{total_tasks} tareas completadas")
                    else:
                        failed_tasks += 1
                        failed_task_list.append({
                            'task': task,
                            'error': result.get('error', 'Unknown error')
                        })
                        logger.warning(f"   ⚠️ Tarea fallida: {task['llm_name']} - {task['query_text'][:50]}...")
                        
                except Exception as e:
                    failed_tasks += 1
                    failed_task_list.append({
                        'task': task,
                        'error': str(e)
                    })
                    logger.error(f"   ❌ Excepción en tarea: {e}")
        
        # ✨ NUEVO: Sistema de reintentos para tareas fallidas
        # OPTIMIZADO PARA CRON: Más reintentos y delays más largos para asegurar completitud
        if failed_tasks > 0:
            logger.info("")
            logger.info("=" * 70)
            logger.info(f"🔄 REINTENTANDO {failed_tasks} TAREAS FALLIDAS")
            logger.info("=" * 70)
            logger.info(f"   Estrategia para CRON: 4 reintentos con delays incrementales")
            logger.info(f"   Objetivo: 100% de completitud (velocidad no es crítica)")
            logger.info("")
            
            retry_count = 0
            max_retries = 4  # Aumentado de 2 a 4 para cron diario
            
            for attempt in range(1, max_retries + 1):
                if not failed_task_list:
                    break
                    
                # Delay incremental: 5s, 10s, 20s, 30s
                delay = min(5 * (2 ** (attempt - 1)), 30)
                
                logger.info(f"📍 Intento {attempt}/{max_retries} ({len(failed_task_list)} tareas)")
                logger.info(f"   Esperando {delay}s para evitar rate limits...")
                
                tasks_to_retry = failed_task_list.copy()
                failed_task_list = []
                
                time.sleep(delay)  # Delay incremental antes de reintentar
                
                for failed_item in tasks_to_retry:
                    task = failed_item['task']
                    logger.info(f"   🔄 Reintentando: {task['llm_name']} - {task['query_text'][:50]}...")
                    
                    try:
                        result = self._execute_single_query_task(task)
                        
                        if result['success']:
                            results_by_llm[task['llm_name']].append(result)
                            completed_tasks += 1
                            retry_count += 1
                            logger.info(f"   ✅ Exitoso en intento {attempt}")
                        else:
                            failed_task_list.append({
                                'task': task,
                                'error': result.get('error', 'Unknown error')
                            })
                            logger.warning(f"   ❌ Falló nuevamente: {result.get('error', 'Unknown')}")
                    except Exception as e:
                        failed_task_list.append({
                            'task': task,
                            'error': str(e)
                        })
                        logger.error(f"   ❌ Excepción en reintento: {e}")
            
            # Actualizar contador de tareas fallidas
            failed_tasks = len(failed_task_list)
            
            logger.info("")
            logger.info(f"   📊 Reintentos exitosos: {retry_count}")
            logger.info(f"   📊 Tareas aún fallidas: {failed_tasks}")
            
            # Log detallado de tareas que no pudieron completarse
            if failed_task_list:
                logger.warning("")
                logger.warning("=" * 70)
                logger.warning("⚠️  TAREAS QUE NO PUDIERON COMPLETARSE")
                logger.warning("=" * 70)
                for failed_item in failed_task_list:
                    task = failed_item['task']
                    error = failed_item['error']
                    logger.warning(f"❌ {task['llm_name']}: {task['query_text'][:60]}...")
                    logger.warning(f"   Error: {error}")
                logger.warning("=" * 70)
                logger.warning("")
        
        # Recalcular duración después de reintentos
        duration = time.time() - start_time
        
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"✅ ANÁLISIS COMPLETADO")
        logger.info("=" * 70)
        logger.info(f"   Duración: {duration:.1f}s")
        logger.info(f"   Tareas completadas: {completed_tasks}/{total_tasks}")
        logger.info(f"   Tareas fallidas: {failed_tasks}")
        logger.info(f"   Velocidad: {total_tasks/duration:.1f} tareas/segundo")
        logger.info("")
        
        # Crear snapshots por LLM
        conn = get_db_connection()
        cur = conn.cursor()
        
        # ✨ NUEVO: Crear lista unificada de todos los competidores para el snapshot
        all_competitors = []
        if competitor_domains_flat:
            all_competitors.extend(competitor_domains_flat)
        if competitor_keywords_flat:
            all_competitors.extend(competitor_keywords_flat)
        
        # Eliminar duplicados manteniendo orden
        seen = set()
        all_competitors = [x for x in all_competitors if not (x in seen or seen.add(x))]
        
        # ✨ NUEVO: Validar que todos los LLMs analicen todas las queries
        total_queries_expected = len(queries)
        
        try:
            for llm_name, llm_results in results_by_llm.items():
                queries_analyzed = len(llm_results)
                
                if queries_analyzed > 0:
                    # ⚠️ VALIDACIÓN: Advertir si faltan queries
                    if queries_analyzed < total_queries_expected:
                        missing = total_queries_expected - queries_analyzed
                        logger.warning("")
                        logger.warning("=" * 70)
                        logger.warning(f"⚠️  ANÁLISIS INCOMPLETO PARA {llm_name.upper()}")
                        logger.warning("=" * 70)
                        logger.warning(f"   Queries esperadas: {total_queries_expected}")
                        logger.warning(f"   Queries analizadas: {queries_analyzed}")
                        logger.warning(f"   Queries faltantes: {missing}")
                        logger.warning(f"   Completitud: {queries_analyzed/total_queries_expected*100:.1f}%")
                        logger.warning("")
                        logger.warning(f"   ⚠️  El snapshot se creará con DATOS PARCIALES")
                        logger.warning(f"   ⚠️  Los porcentajes pueden no ser representativos")
                        logger.warning(f"   ⚠️  Considera ejecutar un nuevo análisis")
                        logger.warning("=" * 70)
                        logger.warning("")
                    
                    self._create_snapshot(
                        cur=cur,
                        project_id=project_id,
                        date=analysis_date,
                        llm_provider=llm_name,
                        llm_results=llm_results,
                        competitors=all_competitors,  # ✨ NUEVO: Usar lista unificada
                        total_queries_expected=total_queries_expected  # ✨ NUEVO: Pasar total esperado
                    )
            
            # Actualizar fecha de último análisis
            cur.execute("""
                UPDATE llm_monitoring_projects
                SET last_analysis_date = %s, updated_at = NOW()
                WHERE id = %s
            """, (datetime.now(), project_id))
            
            conn.commit()
            
            logger.info("💾 Snapshots guardados en BD")
            logger.info("")
            
        except Exception as e:
            logger.error(f"❌ Error guardando snapshots: {e}")
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        
        # ✨ NUEVO: Calcular completitud por LLM
        completeness_by_llm = {}
        incomplete_llms = []
        
        for llm_name, llm_results in results_by_llm.items():
            queries_analyzed = len(llm_results)
            completeness_pct = (queries_analyzed / total_queries_expected * 100) if total_queries_expected > 0 else 0
            completeness_by_llm[llm_name] = {
                'queries_analyzed': queries_analyzed,
                'queries_expected': total_queries_expected,
                'completeness_pct': round(completeness_pct, 1)
            }
            
            if queries_analyzed < total_queries_expected:
                incomplete_llms.append(llm_name)
        
        # Retornar métricas globales
        return {
            'project_id': project_id,
            'analysis_date': str(analysis_date),
            'duration_seconds': round(duration, 1),
            'total_queries_executed': completed_tasks,
            'failed_queries': failed_tasks,
            'llms_analyzed': len(results_by_llm),
            'results_by_llm': {
                llm: len(results) for llm, results in results_by_llm.items()
            },
            'completeness_by_llm': completeness_by_llm,  # ✨ NUEVO
            'incomplete_llms': incomplete_llms,  # ✨ NUEVO
            'all_queries_analyzed': len(incomplete_llms) == 0  # ✨ NUEVO
        }
    
    def _execute_single_query_task(self, task: Dict) -> Dict:
        """
        Ejecuta una query en un LLM y analiza el resultado
        
        Esta función se ejecuta en un thread separado.
        Cada thread crea su propia conexión a BD (thread-safe).
        
        Args:
            task: Dict con toda la info de la tarea
            
        Returns:
            Dict con resultado analizado
        """
        try:
            # Ejecutar query en el LLM con control de concurrencia por proveedor
            semaphore = self.provider_semaphores.get(task['llm_name'])
            if semaphore is not None:
                with semaphore:
                    llm_result = task['provider'].execute_query(task['query_text'])
            else:
                llm_result = task['provider'].execute_query(task['query_text'])
            
            if not llm_result['success']:
                # ✨ NUEVO: Guardar el error en BD para que sea visible
                error_msg = llm_result.get('error', 'Unknown error')
                self._save_error_result(task, error_msg)
                
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Analizar menciones de marca con nuevos campos
            mention_analysis = self.analyze_brand_mention(
                response_text=llm_result['content'],
                brand_name=task.get('brand_name'),  # Legacy
                brand_domain=task.get('brand_domain'),
                brand_keywords=task.get('brand_keywords'),
                sources=llm_result.get('sources', []),  # ✨ NUEVO: Pasar sources para detección
                competitors=task.get('competitors'),  # Legacy
                competitor_domains=task.get('competitor_domains'),
                competitor_keywords=task.get('competitor_keywords')
            )
            
            # Analizar sentimiento si hay menciones
            sentiment_data = {'sentiment': 'neutral', 'score': 0.5, 'method': 'none'}
            
            if mention_analysis['brand_mentioned']:
                sentiment_data = self._analyze_sentiment_with_llm(
                    contexts=mention_analysis['mention_contexts'],
                    brand_name=task['brand_name']
                )
            
            # Guardar resultado en BD (conexión thread-local)
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                cur.execute("""
                    INSERT INTO llm_monitoring_results (
                        project_id, query_id, analysis_date,
                        llm_provider, model_used,
                        query_text, brand_name,
                        brand_mentioned, mention_count, mention_contexts,
                        appears_in_numbered_list, position_in_list, total_items_in_list, position_source,
                        sentiment, sentiment_score,
                        competitors_mentioned,
                        full_response, response_length,
                        sources,
                        tokens_used, input_tokens, output_tokens, cost_usd, response_time_ms
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s,
                        %s, %s,
                        %s,
                        %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (project_id, query_id, llm_provider, analysis_date) 
                    DO UPDATE SET
                        brand_mentioned = EXCLUDED.brand_mentioned,
                        mention_count = EXCLUDED.mention_count,
                        position_in_list = EXCLUDED.position_in_list,
                        position_source = EXCLUDED.position_source,
                        sentiment = EXCLUDED.sentiment,
                        sources = EXCLUDED.sources,
                        cost_usd = EXCLUDED.cost_usd
                """, (
                    task['project_id'], task['query_id'], task['analysis_date'],
                    task['llm_name'], llm_result.get('model_used'),
                    task['query_text'], task['brand_name'],
                    mention_analysis['brand_mentioned'],
                    mention_analysis['mention_count'],
                    mention_analysis['mention_contexts'],
                    mention_analysis['appears_in_numbered_list'],
                    mention_analysis['position_in_list'],
                    mention_analysis['total_items_in_list'],
                    mention_analysis.get('position_source'),  # ✨ NUEVO: 'text', 'link', 'both'
                    sentiment_data['sentiment'],
                    sentiment_data['score'],
                    json.dumps(mention_analysis['competitors_mentioned']),
                    llm_result['content'],
                    len(llm_result['content']),
                    json.dumps(llm_result.get('sources', [])),
                    llm_result['tokens'],
                    llm_result['input_tokens'],
                    llm_result['output_tokens'],
                    llm_result['cost_usd'],
                    llm_result['response_time_ms']
                ))
                
                conn.commit()
                
            finally:
                cur.close()
                conn.close()
            
            # Retornar resultado para agregación
            return {
                'success': True,
                'brand_mentioned': mention_analysis['brand_mentioned'],
                'mention_count': mention_analysis['mention_count'],
                'position_in_list': mention_analysis['position_in_list'],
                'sentiment': sentiment_data['sentiment'],
                'sentiment_score': sentiment_data['score'],
                'competitors_mentioned': mention_analysis['competitors_mentioned'],
                'cost_usd': llm_result['cost_usd'],
                'tokens_used': llm_result['tokens'],
                'response_time_ms': llm_result['response_time_ms']
            }
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando tarea: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _save_error_result(self, task: Dict, error_message: str):
        """
        Guarda un registro de error en BD cuando un LLM falla
        
        Esto permite:
        - Diferenciar entre 'no mencionado' y 'error al consultar'
        - Mostrar errores específicos en el frontend
        - Analizar patrones de fallos
        
        Args:
            task: Información de la tarea que falló
            error_message: Mensaje de error detallado
        """
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                cur.execute("""
                    INSERT INTO llm_monitoring_results (
                        project_id, query_id, analysis_date,
                        llm_provider, model_used,
                        query_text, brand_name,
                        brand_mentioned, mention_count,
                        has_error, error_message,
                        full_response, response_length,
                        tokens_used, cost_usd
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        FALSE, 0,
                        TRUE, %s,
                        %s, 0,
                        0, 0
                    )
                    ON CONFLICT (project_id, query_id, llm_provider, analysis_date) 
                    DO UPDATE SET
                        has_error = TRUE,
                        error_message = EXCLUDED.error_message,
                        updated_at = NOW()
                """, (
                    task['project_id'], task['query_id'], task['analysis_date'],
                    task['llm_name'], None,  # model_used es NULL en caso de error
                    task['query_text'], task['brand_name'],
                    error_message,
                    f"Error: {error_message}"  # full_response contiene el error
                ))
                
                conn.commit()
                logger.debug(f"✅ Error guardado en BD: {task['llm_name']} - {error_message[:50]}...")
                
            finally:
                cur.close()
                conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error guardando registro de error: {e}")
    
    # =====================================================
    # CREACIÓN DE SNAPSHOTS
    # =====================================================
    
    def _calculate_weighted_mentions(self, results: List[Dict], entity_key: str = None) -> float:
        """
        Calcula menciones ponderadas según la posición en listas
        
        PONDERACIÓN:
        - Top 3: peso 2.0 (cuenta doble - muy visible)
        - Top 5: peso 1.5 (cuenta 50% más - alta visibilidad)
        - Top 10: peso 1.2 (cuenta 20% más - visible)
        - Posición > 10: peso 0.8 (cuenta 80% - baja visibilidad)
        - Sin posición (mención en texto): peso 1.0 (baseline)
        
        Args:
            results: Lista de resultados de análisis
            entity_key: Si se especifica, busca en competitors_mentioned[entity_key]
                       Si es None, usa mention_count de la marca principal
        
        Returns:
            float: Total de menciones ponderadas
        
        Example:
            >>> # Marca principal
            >>> weighted = service._calculate_weighted_mentions(llm_results)
            >>> # Competidor específico
            >>> weighted = service._calculate_weighted_mentions(llm_results, 'competitor.com')
        """
        weighted_total = 0.0
        
        for r in results:
            # Obtener número base de menciones
            if entity_key is None:
                # Marca principal: usar mention_count
                base_mentions = r.get('mention_count', 0)
            else:
                # Competidor: buscar en competitors_mentioned
                base_mentions = r.get('competitors_mentioned', {}).get(entity_key, 0)
            
            if base_mentions == 0:
                continue
            
            # Determinar peso según posición
            position = r.get('position_in_list')
            
            if position is None:
                # Mención en texto pero sin posición en lista = peso baseline
                weight = 1.0
            elif position <= 3:
                # Top 3 = peso 2.0 (MUY visible, cuenta doble)
                weight = 2.0
            elif position <= 5:
                # Top 5 = peso 1.5 (alta visibilidad)
                weight = 1.5
            elif position <= 10:
                # Top 10 = peso 1.2 (visible)
                weight = 1.2
            else:
                # Posición > 10 = peso 0.8 (baja visibilidad)
                weight = 0.8
            
            weighted_total += base_mentions * weight
        
        return weighted_total
    
    def _create_snapshot(
        self,
        cur,
        project_id: int,
        date: date,
        llm_provider: str,
        llm_results: List[Dict],
        competitors: List[str],
        total_queries_expected: int = None
    ):
        """
        Crea un snapshot con métricas agregadas para un LLM
        
        Métricas calculadas:
        - mention_rate: % de queries con mención
        - avg_position: Posición promedio en listas
        - top3/top5/top10: Cuántas veces en top X
        - share_of_voice: Tu marca / (tu marca + competidores)
        - sentiment_distribution: Positivo/neutral/negativo
        - total_cost: Suma de costes
        
        Args:
            cur: Cursor de BD
            project_id: ID del proyecto
            date: Fecha del snapshot
            llm_provider: Nombre del proveedor
            llm_results: Lista de resultados de este LLM
            competitors: Lista de competidores
            total_queries_expected: Total de queries que debería haber analizado (opcional)
        """
        total_queries = len(llm_results)
        
        if total_queries == 0:
            return
        
        # Métricas de menciones
        mentions = [r for r in llm_results if r['brand_mentioned']]
        total_mentions = len(mentions)
        mention_rate = (total_mentions / total_queries) * 100
        
        # Posicionamiento
        positions = [r['position_in_list'] for r in llm_results 
                    if r['position_in_list'] is not None]
        avg_position = sum(positions) / len(positions) if positions else None
        
        appeared_in_top3 = sum(1 for p in positions if p <= 3)
        appeared_in_top5 = sum(1 for p in positions if p <= 5)
        appeared_in_top10 = sum(1 for p in positions if p <= 10)
        
        # Share of Voice (normal - sin ponderar)
        total_brand_mentions = sum(r['mention_count'] for r in llm_results)
        total_competitor_mentions = 0
        competitor_breakdown = {}
        
        for competitor in competitors:
            comp_mentions = sum(
                r['competitors_mentioned'].get(competitor, 0)
                for r in llm_results
            )
            competitor_breakdown[competitor] = comp_mentions
            total_competitor_mentions += comp_mentions
        
        total_all_mentions = total_brand_mentions + total_competitor_mentions
        share_of_voice = (total_brand_mentions / total_all_mentions * 100) if total_all_mentions > 0 else 0
        
        # ✨ NUEVO: Share of Voice PONDERADO por posición
        weighted_brand_mentions = self._calculate_weighted_mentions(llm_results, entity_key=None)
        weighted_competitor_mentions = 0.0
        weighted_competitor_breakdown = {}
        
        for competitor in competitors:
            comp_weighted = self._calculate_weighted_mentions(llm_results, entity_key=competitor)
            weighted_competitor_breakdown[competitor] = round(comp_weighted, 2)
            weighted_competitor_mentions += comp_weighted
        
        total_weighted_mentions = weighted_brand_mentions + weighted_competitor_mentions
        weighted_share_of_voice = (weighted_brand_mentions / total_weighted_mentions * 100) if total_weighted_mentions > 0 else 0
        
        logger.debug(f"[SNAPSHOT] Share of Voice - Normal: {share_of_voice:.2f}% | Ponderado: {weighted_share_of_voice:.2f}%")
        
        # Sentimiento
        positive_mentions = sum(1 for r in llm_results if r['sentiment'] == 'positive')
        neutral_mentions = sum(1 for r in llm_results if r['sentiment'] == 'neutral')
        negative_mentions = sum(1 for r in llm_results if r['sentiment'] == 'negative')
        
        sentiment_scores = [r['sentiment_score'] for r in llm_results if r['sentiment_score']]
        avg_sentiment_score = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.5
        
        # Performance
        avg_response_time = sum(r['response_time_ms'] for r in llm_results) / total_queries
        total_cost = sum(r['cost_usd'] for r in llm_results)
        total_tokens = sum(r['tokens_used'] for r in llm_results)
        
        # Insertar snapshot (con métricas ponderadas y normales)
        cur.execute("""
            INSERT INTO llm_monitoring_snapshots (
                project_id, snapshot_date, llm_provider,
                total_queries, total_mentions, mention_rate,
                avg_position, appeared_in_top3, appeared_in_top5, appeared_in_top10,
                total_competitor_mentions, share_of_voice, competitor_breakdown,
                weighted_share_of_voice, weighted_competitor_breakdown,
                positive_mentions, neutral_mentions, negative_mentions, avg_sentiment_score,
                avg_response_time_ms, total_cost_usd, total_tokens
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (project_id, llm_provider, snapshot_date)
            DO UPDATE SET
                total_queries = EXCLUDED.total_queries,
                total_mentions = EXCLUDED.total_mentions,
                mention_rate = EXCLUDED.mention_rate,
                avg_position = EXCLUDED.avg_position,
                share_of_voice = EXCLUDED.share_of_voice,
                weighted_share_of_voice = EXCLUDED.weighted_share_of_voice,
                weighted_competitor_breakdown = EXCLUDED.weighted_competitor_breakdown,
                avg_sentiment_score = EXCLUDED.avg_sentiment_score,
                total_cost_usd = EXCLUDED.total_cost_usd,
                created_at = NOW()
        """, (
            project_id, date, llm_provider,
            total_queries, total_mentions, round(mention_rate, 2),
            round(avg_position, 2) if avg_position else None,
            appeared_in_top3, appeared_in_top5, appeared_in_top10,
            total_competitor_mentions, round(share_of_voice, 2),
            json.dumps(competitor_breakdown),
            round(weighted_share_of_voice, 2),
            json.dumps(weighted_competitor_breakdown),
            positive_mentions, neutral_mentions, negative_mentions,
            round(avg_sentiment_score, 2),
            int(avg_response_time), round(total_cost, 4), total_tokens
        ))
        
        # ✨ NUEVO: Log mejorado con completitud y métricas ponderadas
        completeness_info = ""
        if total_queries_expected and total_queries < total_queries_expected:
            completeness = (total_queries / total_queries_expected) * 100
            completeness_info = f" ({total_queries}/{total_queries_expected} queries - {completeness:.0f}% completo)"
        
        logger.info(f"   📊 Snapshot {llm_provider}: {total_mentions}/{total_queries} menciones ({mention_rate:.1f}%){completeness_info}")
        logger.info(f"      📈 Share of Voice: {share_of_voice:.1f}% (normal) | {weighted_share_of_voice:.1f}% (ponderado por posición)")


# =====================================================
# HELPER FUNCTION
# =====================================================

def analyze_all_active_projects(api_keys: Dict[str, str] = None, max_workers: int = 8) -> List[Dict]:
    """
    Analiza todos los proyectos activos
    
    OPTIMIZADO PARA CRON DIARIO:
    - Prioriza completitud al 100% sobre velocidad
    - Usa parámetros conservadores por defecto
    - Sistema de reintentos robusto
    
    Args:
        api_keys: Dict con API keys (opcional, usa env vars si es None)
        max_workers: Threads paralelos (default: 8, conservador para cron)
        
    Returns:
        Lista de resultados por proyecto con métricas de completitud
    """
    service = MultiLLMMonitoringService(api_keys)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, name FROM llm_monitoring_projects
        WHERE is_active = TRUE
        ORDER BY id
    """)
    
    projects = cur.fetchall()
    cur.close()
    conn.close()
    
    logger.info(f"🚀 Analizando {len(projects)} proyectos activos...")
    
    results = []
    
    for project in projects:
        try:
            result = service.analyze_project(
                project_id=project['id'],
                max_workers=max_workers
            )
            results.append(result)
        except Exception as e:
            logger.error(f"❌ Error analizando proyecto {project['id']}: {e}")
            results.append({
                'project_id': project['id'],
                'error': str(e)
            })
    
    return results


# =====================================================
# AI-POWERED QUERY SUGGESTIONS (NUEVO)
# =====================================================

def generate_query_suggestions_with_ai(
    brand_name: str,
    industry: str,
    language: str = 'es',
    existing_queries: List[str] = None,
    competitors: List[str] = None,
    count: int = 10
) -> List[str]:
    """
    Genera sugerencias de queries usando IA (Gemini Flash)
    
    Analiza el contexto del proyecto (marca, industria, queries existentes)
    y usa Gemini Flash para generar sugerencias contextuales y relevantes.
    
    Args:
        brand_name: Nombre de la marca
        industry: Industria/sector
        language: Idioma ('es' o 'en')
        existing_queries: Queries que el usuario ya tiene
        competitors: Lista de competidores
        count: Número de sugerencias a generar (max 20)
        
    Returns:
        Lista de queries sugeridas
        
    Example:
        >>> suggestions = generate_query_suggestions_with_ai(
        ...     brand_name="ClicAndSEO",
        ...     industry="SEO tools",
        ...     language="es",
        ...     existing_queries=["¿Qué es ClicAndSEO?", "Precio de ClicAndSEO"],
        ...     competitors=["Semrush", "Ahrefs"],
        ...     count=10
        ... )
    """
    import os
    
    existing_queries = existing_queries or []
    competitors = competitors or []
    count = min(count, 20)  # Máximo 20
    
    logger.info(f"🤖 Generando {count} sugerencias de queries con IA para {brand_name}...")
    
    # Verificar que tenemos Google API key
    google_api_key = os.getenv('GOOGLE_API_KEY')
    if not google_api_key:
        logger.error("❌ GOOGLE_API_KEY no configurada")
        logger.error("   Verifica que la variable de entorno esté configurada en Railway")
        return []
    
    logger.info(f"✅ GOOGLE_API_KEY encontrada (longitud: {len(google_api_key)})")
    
    try:
        # Crear proveedor de Gemini Flash
        from services.llm_providers import LLMProviderFactory
        
        logger.info("🔧 Creando proveedor de Gemini Flash...")
        gemini = LLMProviderFactory.create_provider('google', google_api_key)
        
        if not gemini:
            logger.error("❌ No se pudo crear proveedor de Gemini")
            logger.error("   Verifica que el módulo LLMProviderFactory esté funcionando correctamente")
            return []
        
        logger.info("✅ Proveedor de Gemini creado correctamente")
        
        # Construir prompt contextual
        lang_name = 'español' if language == 'es' else 'inglés'
        
        prompt = f"""Eres un experto en marketing digital y brand visibility en LLMs.

CONTEXTO:
- Marca: {brand_name}
- Industria: {industry}
- Idioma: {lang_name}
- Competidores: {', '.join(competitors) if competitors else 'ninguno especificado'}

QUERIES EXISTENTES ({len(existing_queries)}):
{chr(10).join('- ' + q for q in existing_queries[:10]) if existing_queries else '(ninguna todavía)'}

TAREA:
Genera {count} preguntas/prompts adicionales en {lang_name} que un usuario haría a un LLM (ChatGPT, Claude, Gemini, Perplexity) para buscar información sobre {industry}.

REQUISITOS:
1. Las preguntas deben ser diferentes a las existentes
2. Deben ser naturales y realistas
3. Algunas deben mencionar la marca directamente
4. Algunas deben ser generales sobre la industria
5. Algunas deben comparar con competidores
6. Mínimo 15 caracteres por pregunta
7. Variedad: preguntas básicas, técnicas, comparativas

FORMATO:
Responde SOLO con las preguntas, una por línea, sin numeración ni viñetas.

Ejemplo:
¿Cuál es la mejor herramienta de {industry}?
¿Cómo funciona {brand_name}?
{brand_name} vs {competitors[0] if competitors else 'alternativas'}

GENERA {count} PREGUNTAS:"""

        # Ejecutar query en Gemini
        logger.info("📤 Enviando prompt a Gemini Flash...")
        logger.debug(f"   Prompt length: {len(prompt)} caracteres")
        
        result = gemini.execute_query(prompt)
        
        logger.info(f"📥 Respuesta de Gemini recibida: success={result.get('success')}")
        
        if not result['success']:
            logger.error(f"❌ Gemini falló: {result.get('error')}")
            logger.error(f"   Detalles: {result}")
            return []
        
        logger.info(f"✅ Gemini respondió exitosamente")
        logger.debug(f"   Content length: {len(result.get('content', ''))} caracteres")
        
        # Parsear respuesta
        response_text = result['content'].strip()
        
        # Dividir por líneas y limpiar
        suggestions = []
        for line in response_text.split('\n'):
            line = line.strip()
            
            # Ignorar líneas vacías, numeraciones, viñetas
            if not line:
                continue
            if line[0].isdigit() and (line[1] == '.' or line[1] == ')'):
                line = line[2:].strip()
            if line.startswith('-') or line.startswith('•'):
                line = line[1:].strip()
            
            # Validar longitud
            if len(line) >= 15 and len(line) <= 500:
                # Evitar duplicados con existentes
                if line.lower() not in [q.lower() for q in existing_queries]:
                    suggestions.append(line)
        
        # Limitar a count
        suggestions = suggestions[:count]
        
        logger.info(f"✅ Generadas {len(suggestions)} sugerencias con IA")
        logger.info(f"   Coste: ${result.get('cost_usd', 0):.6f} USD")
        
        return suggestions
        
    except Exception as e:
        logger.error(f"❌ Error generando sugerencias con IA: {e}", exc_info=True)
        return []

