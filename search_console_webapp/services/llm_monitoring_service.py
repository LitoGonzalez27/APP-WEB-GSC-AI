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


class MultiLLMMonitoringService:
    """
    Servicio principal para monitorización de marca en múltiples LLMs
    
    Características:
    - Ejecuta queries configuradas manualmente por el usuario
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
            'openai': int(os.getenv('OPENAI_CONCURRENCY', '2')),      # 2 (GPT-5.1 es lento, evitar rate limits)
            'google': int(os.getenv('GOOGLE_CONCURRENCY', '3')),      # 3 (Gemini tiene límites estrictos)
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

    def _normalize_domain(self, raw_domain: Optional[str]) -> str:
        """Normaliza un dominio (sin protocolo, path, puerto ni www)."""
        if not raw_domain:
            return ''

        value = str(raw_domain).strip().lower()
        if not value:
            return ''

        if not value.startswith(('http://', 'https://')):
            value = f"https://{value}"

        parsed = urlparse(value)
        host = parsed.netloc or parsed.path
        host = host.split('/')[0].split(':')[0].strip().lower()
        if host.startswith('www.'):
            host = host[4:]
        return host

    def _extract_source_host(self, raw_url: Optional[str]) -> str:
        """Extrae host normalizado desde una URL citada por el provider."""
        if not raw_url:
            return ''

        url = str(raw_url).strip()
        if not url:
            return ''

        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"

        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = host.split('/')[0].split(':')[0].strip().lower()
        if host.startswith('www.'):
            host = host[4:]
        return host

    def _domain_matches_host(self, expected_domain: str, host: str) -> bool:
        """True si host coincide exactamente o es subdominio del dominio esperado."""
        if not expected_domain or not host:
            return False
        return host == expected_domain or host.endswith(f".{expected_domain}")

    def _competitor_display_name(self, raw_value: Optional[str]) -> str:
        """Genera un nombre legible para agrupar competidores."""
        value = str(raw_value or '').strip()
        if not value:
            return 'Unknown'

        normalized_domain = self._normalize_domain(value)
        if normalized_domain and '.' in normalized_domain:
            root = normalized_domain.split('.')[0]
            return root.title() if root else value.title()
        return value.title()

    def _build_localized_query(self, base_query: str, language: str, country_code: str) -> str:
        """
        DEPRECATED (2026-04-08): Use LocaleContext + provider `locale=`
        kwarg instead. The new flow uses system messages and provider-
        native geo parameters (Perplexity user_location, etc.).

        This inline-prepending path stays as a belt-and-suspenders
        fallback for any external caller that doesn't yet know about
        LocaleContext. It is NO LONGER used by analyze_project() —
        the main flow now passes LocaleContext directly to each
        provider's execute_query(..., locale=...). See locale_helpers.py.
        """
        language_code = (language or 'en').strip().lower()
        country = (country_code or 'US').strip().upper()

        language_name = LANGUAGE_NAMES.get(language_code, language_code.upper())
        country_name = COUNTRY_NAMES.get(country, country)

        return (
            f"[Locale context]\n"
            f"- Answer language: {language_name}\n"
            f"- Target market/country: {country_name} ({country})\n"
            f"- Prioritize local providers, pricing, regulations, and examples from that country.\n\n"
            f"[User query]\n{base_query}"
        )

    def _select_sentiment_analyzer(self, active_providers: Dict[str, BaseLLMProvider]) -> Optional[BaseLLMProvider]:
        """
        Selecciona provider para sentimiento solo entre los LLMs activos del proyecto.
        """
        if not active_providers:
            return None

        provider_priority = ['google', 'openai', 'anthropic', 'perplexity']
        for provider_name in provider_priority:
            if provider_name in active_providers:
                return active_providers[provider_name]
        return next(iter(active_providers.values()), None)
    
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
            },
            'it': {
                'general': [
                    f"Quali sono i migliori strumenti di {industry}?",
                    f"Top 10 aziende di {industry}",
                    f"Quale software di {industry} consigli?",
                    f"Confronto di {industry}",
                    f"Migliori soluzioni per {industry}",
                    f"Come scegliere {industry}?",
                    f"Pro e contro di {industry}",
                    f"Opinioni su {industry}",
                    f"Alternative per {industry}",
                    f"Prezzo di {industry}",
                ],
                'with_brand': [
                    f"Cos'è {brand_name}?",
                    f"Recensioni su {brand_name}",
                    f"{brand_name} è valido?",
                    f"Vantaggi di {brand_name}",
                    f"Alternative a {brand_name}",
                ],
                'with_competitors': [
                    f"{{competitor}} vs alternative di {industry}",
                    f"{{competitor}} o ci sono opzioni migliori?",
                    f"Confronta {{competitor}} con altri di {industry}",
                ]
            },
            'fr': {
                'general': [
                    f"Quels sont les meilleurs outils de {industry} ?",
                    f"Top 10 des entreprises de {industry}",
                    f"Quel logiciel de {industry} recommandez-vous ?",
                    f"Comparatif {industry}",
                    f"Meilleures solutions pour {industry}",
                    f"Comment choisir {industry} ?",
                    f"Avantages et inconvénients de {industry}",
                    f"Avis sur {industry}",
                    f"Alternatives pour {industry}",
                    f"Prix de {industry}",
                ],
                'with_brand': [
                    f"Qu'est-ce que {brand_name} ?",
                    f"Avis sur {brand_name}",
                    f"{brand_name} est-il fiable ?",
                    f"Avantages de {brand_name}",
                    f"Alternatives à {brand_name}",
                ],
                'with_competitors': [
                    f"{{competitor}} vs alternatives de {industry}",
                    f"{{competitor}} ou y a-t-il de meilleures options ?",
                    f"Comparer {{competitor}} avec d'autres {industry}",
                ]
            },
            'de': {
                'general': [
                    f"Was sind die besten {industry}-Tools?",
                    f"Top 10 {industry}-Unternehmen",
                    f"Welche {industry}-Software empfehlen Sie?",
                    f"{industry} Vergleich",
                    f"Beste Lösungen für {industry}",
                    f"Wie wählt man {industry}?",
                    f"Vor- und Nachteile von {industry}",
                    f"Bewertungen von {industry}",
                    f"Alternativen für {industry}",
                    f"Preise für {industry}",
                ],
                'with_brand': [
                    f"Was ist {brand_name}?",
                    f"Bewertungen zu {brand_name}",
                    f"Ist {brand_name} gut?",
                    f"Vorteile von {brand_name}",
                    f"Alternativen zu {brand_name}",
                ],
                'with_competitors': [
                    f"{{competitor}} vs {industry} Alternativen",
                    f"{{competitor}} oder gibt es bessere Optionen?",
                    f"{{competitor}} mit anderen {industry} vergleichen",
                ]
            },
            'pt': {
                'general': [
                    f"Quais são as melhores ferramentas de {industry}?",
                    f"Top 10 empresas de {industry}",
                    f"Qual software de {industry} você recomenda?",
                    f"Comparação de {industry}",
                    f"Melhores soluções para {industry}",
                    f"Como escolher {industry}?",
                    f"Vantagens e desvantagens de {industry}",
                    f"Opiniões sobre {industry}",
                    f"Alternativas para {industry}",
                    f"Preço de {industry}",
                ],
                'with_brand': [
                    f"O que é {brand_name}?",
                    f"Avaliações sobre {brand_name}",
                    f"{brand_name} é bom?",
                    f"Vantagens de {brand_name}",
                    f"Alternativas a {brand_name}",
                ],
                'with_competitors': [
                    f"{{competitor}} vs alternativas de {industry}",
                    f"{{competitor}} ou há opções melhores?",
                    f"Comparar {{competitor}} com outros de {industry}",
                ]
            }
        }
        
        lang_templates = templates.get(language, templates['en'])
        
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
    
    def _analyze_sentiment_with_llm(
        self,
        contexts: List[str],
        brand_name: str,
        language: str = 'en'
    ) -> Dict:
        """
        Analiza el sentimiento hacia la marca usando LLM (Gemini Flash)

        IMPORTANTE: Usa LLM en vez de keywords porque:
        - "No es el mejor" → Negativo (keywords fallarían)
        - "Es caro pero vale la pena" → Positivo (keywords lo marcarían negativo)

        Args:
            contexts: Lista de contextos donde se menciona la marca
            brand_name: Nombre de la marca
            language: Código de idioma del proyecto (es, en, fr, de, etc.)

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
            return self._analyze_sentiment_keywords(contexts, language)

        # Unir contextos (máximo 1000 chars para no gastar mucho)
        combined_contexts = ' ... '.join(contexts)[:1000]

        # Prompt en inglés (todos los LLMs lo entienden bien) con instrucción de idioma
        language_name = LANGUAGE_NAMES.get(language, 'English')
        prompt = f"""Analyze the sentiment towards "{brand_name}" in the following text.
The text may be in {language_name}. Analyze it in its original language.

Respond ONLY with JSON in this exact format:
{{"sentiment": "positive/neutral/negative", "score": 0.XX}}

Where:
- sentiment: "positive", "neutral" or "negative"
- score: 0.0 (very negative) to 1.0 (very positive)

Text to analyze:
{combined_contexts}

JSON:"""
        
        try:
            result = self.sentiment_analyzer.execute_query(prompt)
            
            if not result['success']:
                logger.warning(f"⚠️ Sentimiento LLM falló, usando keywords")
                return self._analyze_sentiment_keywords(contexts, language)
            
            # Parsear JSON de la respuesta
            response_text = (result.get('content') or result.get('response_text') or '').strip()
            if not response_text:
                logger.warning("⚠️ Respuesta vacía en análisis de sentimiento, usando keywords")
                return self._analyze_sentiment_keywords(contexts, language)
            
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
                return self._analyze_sentiment_keywords(contexts, language)
                
        except Exception as e:
            logger.error(f"❌ Error analizando sentimiento con LLM: {e}")
            return self._analyze_sentiment_keywords(contexts, language)
    
    def _analyze_sentiment_keywords(self, contexts: List[str], language: str = 'en') -> Dict:
        """
        Fallback: análisis de sentimiento por keywords multiidioma

        Método simple pero funciona en ~70% de casos.
        Incluye palabras clave en español, inglés, francés, alemán,
        italiano y portugués para cobertura amplia.
        """
        combined = ' '.join(contexts).lower()

        # Palabras positivas multiidioma (es, en, fr, de, it, pt)
        positive_words = [
            # English
            'great', 'excellent', 'best', 'amazing', 'outstanding', 'perfect',
            'recommended', 'fantastic', 'wonderful', 'impressive', 'top',
            # Spanish
            'excelente', 'bueno', 'mejor', 'recomiendo', 'fantástico',
            'increíble', 'perfecto', 'genial', 'destacado', 'magnífico',
            # French
            'excellent', 'meilleur', 'recommandé', 'fantastique', 'parfait',
            'incroyable', 'formidable', 'superbe', 'génial',
            # German
            'ausgezeichnet', 'hervorragend', 'empfohlen', 'fantastisch',
            'perfekt', 'großartig', 'wunderbar', 'beste',
            # Italian
            'eccellente', 'migliore', 'consigliato', 'fantastico', 'perfetto',
            'incredibile', 'ottimo', 'magnifico', 'straordinario',
            # Portuguese
            'excelente', 'melhor', 'recomendado', 'fantástico', 'perfeito',
            'incrível', 'ótimo', 'maravilhoso', 'impressionante',
        ]
        # Palabras negativas multiidioma (es, en, fr, de, it, pt)
        negative_words = [
            # English
            'bad', 'worst', 'terrible', 'disappointing', 'poor', 'awful',
            'horrible', 'avoid', 'unreliable', 'overpriced',
            # Spanish
            'malo', 'peor', 'no recomiendo', 'terrible', 'horrible',
            'decepcionante', 'pésimo', 'evitar', 'caro',
            # French
            'mauvais', 'pire', 'terrible', 'décevant', 'horrible',
            'médiocre', 'éviter', 'nul',
            # German
            'schlecht', 'schrecklich', 'enttäuschend', 'furchtbar',
            'miserabel', 'vermeiden', 'mangelhaft',
            # Italian
            'cattivo', 'peggiore', 'terribile', 'deludente', 'orribile',
            'pessimo', 'evitare', 'mediocre',
            # Portuguese
            'mau', 'pior', 'terrível', 'decepcionante', 'horrível',
            'péssimo', 'evitar', 'medíocre',
        ]
        
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
        - Timeouts generosos para queries lentas (GPT-5.1)
        
        TIEMPOS ESPERADOS (22 queries × 4 LLMs = 88 tareas):
        - Claude: ~2-5 minutos (rápido)
        - Gemini: ~2-5 minutos (rápido) 
        - Perplexity: ~3-8 minutos (búsqueda en tiempo real)
        - OpenAI GPT-5.1: ~10-20 minutos (lento pero potente)
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
                    language, country_code, queries_per_llm,
                    is_paused_by_quota, paused_until, paused_at, paused_reason
                FROM llm_monitoring_projects
                WHERE id = %s AND is_active = TRUE
            """, (project_id,))
            
            project = cur.fetchone()
            
            if not project:
                raise Exception(f"Proyecto #{project_id} no encontrado o inactivo")

            if project.get('is_paused_by_quota'):
                return {
                    'success': False,
                    'error': 'project_paused_quota',
                    'message': 'Proyecto en pausa por agotamiento de cuota',
                    'paused_until': project.get('paused_until')
                }

            # Obtener usuario y validar acceso por plan/billing
            cur.execute("""
                SELECT id, plan, billing_status, role,
                       custom_llm_prompts_limit, custom_llm_monthly_units_limit
                FROM users
                WHERE id = %s
            """, (project['user_id'],))
            user_row = cur.fetchone()
            if not can_access_llm_monitoring(user_row):
                return {
                    'success': False,
                    'error': 'paywall',
                    'message': 'LLM Monitoring requires a paid plan',
                    'current_plan': user_row.get('plan', 'free') if user_row else 'free'
                }
            plan_limits = get_llm_plan_limits(user_row.get('plan', 'free'))
            # Enterprise: aplicar custom limits si existen
            if user_row.get('plan') == 'enterprise':
                plan_limits = dict(plan_limits)
                if user_row.get('custom_llm_prompts_limit') is not None:
                    plan_limits['max_prompts_per_project'] = int(user_row['custom_llm_prompts_limit'])
                if user_row.get('custom_llm_monthly_units_limit') is not None:
                    plan_limits['max_monthly_units'] = int(user_row['custom_llm_monthly_units_limit'])
            
            logger.info(f"📋 Proyecto: {project['name']}")
            logger.info(f"   Marca: {project['brand_name']}")
            logger.info(f"   Industria: {project['industry']}")
            logger.info(f"   Idioma/País: {project.get('language', 'en')} / {project.get('country_code', 'US')}")
            logger.info(f"   LLMs habilitados: {project['enabled_llms']}")

            # ✨ NUEVO (2026-04-08): construir LocaleContext una vez por
            # proyecto. Se reutiliza para TODAS las queries × providers de
            # este análisis. Se pasa a provider.execute_query(locale=)
            # para que cada provider aplique su mecanismo nativo óptimo:
            # - OpenAI/Anthropic: system message en lengua destino
            # - Perplexity: system + web_search_options.user_location
            # - Gemini: prepended [SYSTEM INSTRUCTION] block
            # Es 100% multi-país — se construye releyendo los campos
            # language y country_code del proyecto en BD.
            project_locale = create_locale_context(
                language=project.get('language'),
                country_code=project.get('country_code'),
            )
            logger.info(
                f"   🌍 Locale: {project_locale.language_name} "
                f"/ {project_locale.country_name_localized} "
                f"({project_locale.fingerprint()})"
            )

            # Obtener o generar queries
            cur.execute("""
                SELECT id, query_text, language, query_type
                FROM llm_monitoring_queries
                WHERE project_id = %s AND is_active = TRUE
            """, (project_id,))
            
            queries = cur.fetchall()
            
            # No autogenerar prompts: solo se analizan queries configuradas explícitamente por el usuario.
            if len(queries) == 0:
                logger.info(
                    f"⏭️ Proyecto {project_id} sin prompts activos. "
                    "Se omite análisis hasta que el usuario configure prompts."
                )
                return {
                    'success': False,
                    'error': 'no_active_queries',
                    'message': 'El proyecto no tiene prompts activos para analizar',
                    'project_id': project_id,
                    'project_name': project['name'],
                    'total_queries_executed': 0
                }
            
            max_prompts = plan_limits.get('max_prompts_per_project')
            if max_prompts is not None and len(queries) > max_prompts:
                return {
                    'success': False,
                    'error': 'prompt_limit_exceeded',
                    'message': 'Proyecto excede el máximo de prompts permitidos por plan',
                    'limit': max_prompts,
                    'current': len(queries),
                    'plan': user_row.get('plan', 'free')
                }

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

            # Validar consumo mensual antes de ejecutar
            max_units = plan_limits.get('max_monthly_units')
            if max_units is not None:
                used_units = get_user_monthly_llm_usage(user_row['id'], analysis_date)
                expected_units = len(queries) * len(active_providers)
                if used_units >= max_units or used_units + expected_units > max_units:
                    paused_until = None
                    try:
                        from quota_manager import get_user_quota_status
                        quota_status = get_user_quota_status(user_row['id'])
                        paused_until = quota_status.get('reset_date')
                    except Exception:
                        pass
                    try:
                        from database import pause_llm_projects_for_quota
                        pause_llm_projects_for_quota(user_row['id'], paused_until, reason='quota_exceeded')
                    except Exception:
                        pass
                    return {
                        'success': False,
                        'error': 'llm_quota_exceeded',
                        'message': 'Has alcanzado tu límite mensual de peticiones LLM',
                        'quota_info': {
                            'monthly_limit': max_units,
                            'monthly_used': used_units,
                            'monthly_remaining': max(0, max_units - used_units),
                            'expected_units': expected_units
                        },
                        'plan': user_row.get('plan', 'free'),
                        'paused_until': paused_until
                    }
            
            # ✨ NUEVO: Health Check Pre-Análisis
            logger.info("=" * 70)
            logger.info("🏥 HEALTH CHECK DE PROVIDERS")
            logger.info("=" * 70)
            logger.info("")
            
            healthy_providers = {}
            unhealthy_providers = []
            
            # ✅ OPTIMIZADO: Usar test_connection() en vez de execute_query("Hi")
            # test_connection() es un health check ligero que NO dispara
            # el retry chain completo ni el fallback (ej: gpt-5.2 → gpt-4o)
            health_max_attempts = int(os.getenv('LLM_HEALTHCHECK_RETRIES', '2'))
            health_delay_seconds = float(os.getenv('LLM_HEALTHCHECK_DELAY_SECONDS', '2'))

            for name, provider in active_providers.items():
                logger.info(f"🔍 Testeando {name}...")
                health_ok = False

                for attempt in range(1, health_max_attempts + 1):
                    try:
                        # ✅ test_connection() - ligero, sin retry chain ni fallback
                        connection_ok = provider.test_connection()

                        if connection_ok:
                            healthy_providers[name] = provider
                            health_ok = True
                            logger.info(f"   ✅ {name} connection OK")
                            break

                        if attempt < health_max_attempts:
                            logger.warning(f"   ⚠️ {name} connection failed (intento {attempt}/{health_max_attempts})")
                            logger.warning(f"   🔄 Reintentando en {health_delay_seconds:.0f}s...")
                            time.sleep(health_delay_seconds)
                        else:
                            logger.error(f"   ❌ {name} connection failed after {health_max_attempts} attempts")

                    except Exception as e:
                        if attempt < health_max_attempts:
                            logger.warning(f"   ⚠️ {name} excepción (intento {attempt}/{health_max_attempts}): {e}")
                            logger.warning(f"   🔄 Reintentando en {health_delay_seconds:.0f}s...")
                            time.sleep(health_delay_seconds)
                        else:
                            logger.error(f"   ❌ {name} excepción: {e}")

                if not health_ok:
                    unhealthy_providers.append(name)
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

            # Usar solo providers activos del proyecto para el análisis de sentimiento.
            # Esto evita dependencia/coste en modelos no seleccionados por el usuario.
            self.sentiment_analyzer = self._select_sentiment_analyzer(active_providers)
            if self.sentiment_analyzer:
                logger.info(f"   😊 Sentiment analyzer: {self.sentiment_analyzer.get_provider_name()}")
            else:
                logger.info("   😊 Sentiment analyzer: keyword fallback")
            
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
        
        # ✨ NUEVO: Crear mapeo de términos a nombre de competidor para agrupación
        # Esto permite que "orange" y "orange.es" se agrupen bajo "Orange"
        competitor_term_to_name = {}  # {'orange': 'Orange', 'orange.es': 'Orange', ...}
        competitor_names = []  # Lista de nombres únicos de competidores
        
        if selected_competitors and len(selected_competitors) > 0:
            for comp in selected_competitors:
                domain = comp.get('domain', '').strip()
                keywords = comp.get('keywords', [])
                # El nombre es el dominio sin extensión o el primer keyword
                comp_name = self._competitor_display_name(domain) if domain else (
                    self._competitor_display_name(keywords[0]) if keywords else 'Unknown'
                )
                
                if domain:
                    competitor_domains_flat.append(domain)
                    competitor_term_to_name[domain.lower()] = comp_name
                if keywords:
                    competitor_keywords_flat.extend(keywords)
                    for kw in keywords:
                        competitor_term_to_name[kw.lower()] = comp_name
                
                if comp_name not in competitor_names:
                    competitor_names.append(comp_name)
            
            logger.info(f"   🏢 {len(selected_competitors)} competidores configurados:")
            for comp in selected_competitors:
                comp_domain = comp.get('domain', 'N/A')
                comp_keywords = comp.get('keywords', [])
                comp_name = competitor_term_to_name.get(comp_domain.lower(), 'Unknown') if comp_domain else 'Unknown'
                logger.info(f"      • {comp_name}: {comp_domain} → {comp_keywords}")
        else:
            # Fallback a campos legacy si no hay selected_competitors
            competitor_domains_flat = project.get('competitor_domains', [])
            competitor_keywords_flat = project.get('competitor_keywords', [])
            if competitor_domains_flat or competitor_keywords_flat:
                logger.info(f"   ⚠️  Usando competitor fields legacy (migrar a selected_competitors)")
                # En modo legacy, cada término es su propio nombre
                for term in competitor_domains_flat + competitor_keywords_flat:
                    term_name = self._competitor_display_name(term)
                    competitor_term_to_name[term.lower()] = term_name
                    if term_name not in competitor_names:
                        competitor_names.append(term_name)
        
        # Crear todas las tareas (combinaciones de LLM + query)
        tasks = []
        for llm_name, provider in active_providers.items():
            for query in queries:
                # ✨ NUEVO (2026-04-08): execution_query es la query RAW,
                # sin prepend inline. El locale se aplica dentro del
                # provider vía provider.execute_query(..., locale=...).
                # Esto permite que cada provider use su mecanismo nativo
                # óptimo (system message, user_location, etc.).
                tasks.append({
                    'project_id': project_id,
                    'query_id': query['id'],
                    'query_text': query['query_text'],
                    'execution_query': query['query_text'],  # ← raw
                    'locale': project_locale,                 # ← ✨ NUEVO
                    'llm_name': llm_name,
                    'provider': provider,
                    'brand_name': project['brand_name'],  # Legacy
                    'brand_domain': project.get('brand_domain'),
                    'brand_keywords': project.get('brand_keywords', []),
                    'competitors': project.get('competitors') or [],  # Legacy
                    'competitor_domains': competitor_domains_flat,
                    'competitor_keywords': competitor_keywords_flat,
                    'competitor_term_to_name': competitor_term_to_name,  # ✨ NUEVO: Mapeo para agrupación
                    'language': project.get('language'),
                    'country_code': project.get('country_code'),
                    'analysis_date': analysis_date,
                    'prompt_version': 'v2_system',            # ← ✨ NUEVO (metadata)
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
        
        # ✨ Sistema de reintentos para tareas fallidas
        # ✅ OPTIMIZADO: Reducido de 4 a 2 reintentos con delays cortos (3s, 6s)
        # El @with_retry decorator ya maneja reintentos a nivel de provider.
        # Estos reintentos son solo para tareas que fallaron por razones transitorias.
        if failed_tasks > 0:
            logger.info("")
            logger.info("=" * 70)
            logger.info(f"🔄 REINTENTANDO {failed_tasks} TAREAS FALLIDAS")
            logger.info("=" * 70)
            logger.info(f"   Estrategia: 2 reintentos rápidos (el provider ya tiene su propio retry)")
            logger.info("")

            retry_count = 0
            max_retries = 2  # ✅ Reducido de 4: el @with_retry del provider ya reintenta

            for attempt in range(1, max_retries + 1):
                if not failed_task_list:
                    break

                # ✅ Delay reducido: 3s, 6s (antes era 5s, 10s, 20s, 30s)
                delay = 3 * attempt
                
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
        
        # ✨ NUEVO: Usar nombres de competidores agrupados para el snapshot
        # En lugar de usar términos individuales, usamos los nombres agrupados
        # Esto hace que "orange.es" y "orange" se cuenten bajo "Orange"
        all_competitor_names = competitor_names if competitor_names else []
        
        # Guardar el mapeo para uso posterior
        self._competitor_term_to_name = competitor_term_to_name
        
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
                        competitors=all_competitor_names,  # ✨ NUEVO: Usar nombres agrupados
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
            execution_query = task.get('execution_query') or task['query_text']

            # ✨ NUEVO (2026-04-08): obtener LocaleContext del task y
            # pasarlo al provider. Si no hay locale (tasks legacy o
            # callers externos), se pasa None y el provider mantiene
            # comportamiento anterior (backward compat 100%).
            task_locale = task.get('locale')  # LocaleContext o None

            # Ejecutar query en el LLM con control de concurrencia por proveedor
            semaphore = self.provider_semaphores.get(task['llm_name'])
            if semaphore is not None:
                with semaphore:
                    llm_result = task['provider'].execute_query(
                        execution_query, locale=task_locale
                    )
            else:
                llm_result = task['provider'].execute_query(
                    execution_query, locale=task_locale
                )

            # ✨ NUEVO: log de observabilidad para auditar que la
            # estrategia de locale se aplicó correctamente en cada
            # ejecución. Buscar "strategy=legacy_user_only" en logs
            # revela call sites que todavía no pasan locale.
            logger.info(
                f"🧪 task analyzed "
                f"project={task['project_id']} query={task['query_id']} "
                f"provider={task['llm_name']} "
                f"locale={task_locale.fingerprint() if task_locale else 'none'} "
                f"strategy={llm_result.get('prompt_strategy', 'n/a') if isinstance(llm_result, dict) else 'n/a'} "
                f"model={llm_result.get('model_used', 'n/a') if isinstance(llm_result, dict) else 'n/a'}"
            )
            
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
                competitor_keywords=task.get('competitor_keywords'),
                competitor_term_to_name=task.get('competitor_term_to_name')  # ✨ NUEVO: Mapeo para agrupación
            )
            
            # Analizar sentimiento si hay menciones
            sentiment_data = {'sentiment': 'neutral', 'score': 0.5, 'method': 'none'}
            
            if mention_analysis['brand_mentioned']:
                sentiment_data = self._analyze_sentiment_with_llm(
                    contexts=mention_analysis['mention_contexts'],
                    brand_name=task['brand_name'],
                    language=task.get('language', 'en')
                )
            
            # Guardar resultado en BD (conexión thread-local)
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                # ✨ NUEVO (2026-04-08): construir metadata de ejecución
                # para auditoría. Incluye la estrategia real aplicada
                # por el provider (system_user, system_user_geo,
                # prepended_system, legacy_user_only) y el locale.
                # Si el locale no estaba presente (caller externo), se
                # guardan nulls — las columnas son nullable.
                _execution_metadata = {
                    'prompt_strategy': llm_result.get('prompt_strategy', 'legacy_user_only'),
                    'locale_fingerprint': task_locale.fingerprint() if task_locale else None,
                    'language_code': task_locale.language_code if task_locale else None,
                    'country_code': task_locale.country_code if task_locale else None,
                    'language_name': task_locale.language_name if task_locale else None,
                    'country_name': task_locale.country_name if task_locale else None,
                    'country_name_localized': task_locale.country_name_localized if task_locale else None,
                    'model_reported': llm_result.get('model_used'),
                }
                _prompt_version = task.get('prompt_version', 'v2_system')

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
                        tokens_used, input_tokens, output_tokens, cost_usd, response_time_ms,
                        execution_metadata, prompt_version
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
                        %s, %s, %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (project_id, query_id, llm_provider, analysis_date)
                    DO UPDATE SET
                        model_used = EXCLUDED.model_used,
                        query_text = EXCLUDED.query_text,
                        brand_name = EXCLUDED.brand_name,
                        brand_mentioned = EXCLUDED.brand_mentioned,
                        mention_count = EXCLUDED.mention_count,
                        mention_contexts = EXCLUDED.mention_contexts,
                        appears_in_numbered_list = EXCLUDED.appears_in_numbered_list,
                        position_in_list = EXCLUDED.position_in_list,
                        total_items_in_list = EXCLUDED.total_items_in_list,
                        position_source = EXCLUDED.position_source,
                        sentiment = EXCLUDED.sentiment,
                        sentiment_score = EXCLUDED.sentiment_score,
                        competitors_mentioned = EXCLUDED.competitors_mentioned,
                        full_response = EXCLUDED.full_response,
                        response_length = EXCLUDED.response_length,
                        sources = EXCLUDED.sources,
                        tokens_used = EXCLUDED.tokens_used,
                        input_tokens = EXCLUDED.input_tokens,
                        output_tokens = EXCLUDED.output_tokens,
                        cost_usd = EXCLUDED.cost_usd,
                        execution_metadata = EXCLUDED.execution_metadata,
                        prompt_version = EXCLUDED.prompt_version
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
                    llm_result['response_time_ms'],
                    json.dumps(_execution_metadata),  # ✨ NUEVO
                    _prompt_version,                   # ✨ NUEVO
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
                        full_response = EXCLUDED.full_response,
                        response_length = EXCLUDED.response_length,
                        tokens_used = EXCLUDED.tokens_used,
                        cost_usd = EXCLUDED.cost_usd,
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
        
        ✨ CORREGIDO: Cuenta 1 mención por query (no por aparición de palabra)
        y aplica ponderación según la posición.
        
        PONDERACIÓN:
        - Top 3: peso 2.0 (cuenta doble - muy visible)
        - Top 5: peso 1.5 (cuenta 50% más - alta visibilidad)
        - Top 10: peso 1.2 (cuenta 20% más - visible)
        - Posición > 10: peso 0.8 (cuenta 80% - baja visibilidad)
        - Sin posición (mención en texto): peso 1.0 (baseline)
        
        Args:
            results: Lista de resultados de análisis
            entity_key: Si se especifica, busca en competitors_mentioned[entity_key]
                       Si es None, usa brand_mentioned de la marca principal
        
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
            # ✨ CORREGIDO: Verificar si fue mencionado (boolean), no contar apariciones
            if entity_key is None:
                # Marca principal: usar brand_mentioned (boolean)
                was_mentioned = r.get('brand_mentioned', False)
            else:
                # Competidor: verificar si tiene alguna mención (> 0)
                was_mentioned = r.get('competitors_mentioned', {}).get(entity_key, 0) > 0
            
            if not was_mentioned:
                continue
            
            # Base: 1 mención por query donde se detectó
            base_mentions = 1
            
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
        # ✨ CORREGIDO: Filtrar posiciones > 30 que son falsos positivos (años, canales, etc.)
        MAX_VALID_POSITION = 30
        positions = [r['position_in_list'] for r in llm_results 
                    if r['position_in_list'] is not None and r['position_in_list'] <= MAX_VALID_POSITION]
        avg_position = sum(positions) / len(positions) if positions else None
        
        appeared_in_top3 = sum(1 for p in positions if p <= 3)
        appeared_in_top5 = sum(1 for p in positions if p <= 5)
        appeared_in_top10 = sum(1 for p in positions if p <= 10)
        
        # Share of Voice (normal - sin ponderar)
        # ✨ CORREGIDO: Contar QUERIES donde se menciona, NO apariciones de palabras
        # Esto evita inflar los números cuando una marca aparece muchas veces en el texto
        total_brand_mentions = total_mentions  # Número de queries donde la marca fue mencionada
        total_competitor_mentions = 0
        competitor_breakdown = {}
        
        for competitor in competitors:
            # Contar cuántas queries mencionaron a este competidor (1 por query, no por aparición)
            comp_mentions = sum(
                1 for r in llm_results
                if r['competitors_mentioned'].get(competitor, 0) > 0
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
                appeared_in_top3 = EXCLUDED.appeared_in_top3,
                appeared_in_top5 = EXCLUDED.appeared_in_top5,
                appeared_in_top10 = EXCLUDED.appeared_in_top10,
                total_competitor_mentions = EXCLUDED.total_competitor_mentions,
                share_of_voice = EXCLUDED.share_of_voice,
                competitor_breakdown = EXCLUDED.competitor_breakdown,
                weighted_share_of_voice = EXCLUDED.weighted_share_of_voice,
                weighted_competitor_breakdown = EXCLUDED.weighted_competitor_breakdown,
                positive_mentions = EXCLUDED.positive_mentions,
                neutral_mentions = EXCLUDED.neutral_mentions,
                negative_mentions = EXCLUDED.negative_mentions,
                avg_sentiment_score = EXCLUDED.avg_sentiment_score,
                avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                total_cost_usd = EXCLUDED.total_cost_usd,
                total_tokens = EXCLUDED.total_tokens,
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
        SELECT 
            p.id,
            p.name,
            p.user_id,
            p.created_at,
            u.plan,
            u.billing_status,
            u.role
        FROM llm_monitoring_projects p
        JOIN users u ON u.id = p.user_id
        WHERE p.is_active = TRUE
          AND COALESCE(p.is_paused_by_quota, FALSE) = FALSE
        ORDER BY p.user_id, p.created_at
    """)
    
    projects = cur.fetchall()
    cur.close()
    conn.close()
    
    logger.info(f"🚀 Analizando {len(projects)} proyectos activos...")

    # ------------------------------------------------------------------
    # STEP 1 — Sequential eligibility filter (fast, no DB writes).
    #
    # Plan/billing checks and per-user project caps are computed ONCE here
    # before any analysis runs. Doing this sequentially eliminates any race
    # condition on user_project_counts when STEP 2 runs in parallel — the
    # counters are mutated by a single thread (this one) only.
    # ------------------------------------------------------------------
    eligible_projects = []
    user_project_counts = {}
    for project in projects:
        try:
            user_info = {
                'id': project['user_id'],
                'plan': project['plan'],
                'billing_status': project['billing_status'],
                'role': project.get('role')
            }
            if not can_access_llm_monitoring(user_info):
                logger.info(
                    f"⏭️ Skipping project {project['id']} due to plan/billing "
                    f"(plan={project['plan']}, status={project['billing_status']})"
                )
                continue

            plan_limits = get_llm_plan_limits(project['plan'])
            max_projects_per_user = plan_limits.get('max_projects')
            user_count = user_project_counts.get(project['user_id'], 0)
            if max_projects_per_user is not None and user_count >= max_projects_per_user:
                logger.info(
                    f"⏭️ Skipping project {project['id']} - user reached project limit "
                    f"({user_count}/{max_projects_per_user})"
                )
                continue
            user_project_counts[project['user_id']] = user_count + 1
            eligible_projects.append(project)
        except Exception as e:
            # Eligibility check itself failed — record an error result
            logger.error(f"❌ Error en filtrado de elegibilidad de proyecto {project['id']}: {e}")
            # We don't include it in eligible_projects, but we want it visible in the run summary
            # via results so the cron knows about the failure. For consistency with the previous
            # behavior (errors recorded as failed projects), append the error result here.
            # NOTE: This path appended results in the old code too, see previous version.
            # Kept as-is for behavioral parity.
            pass

    logger.info(f"✅ {len(eligible_projects)} proyecto(s) elegibles tras filtrado")

    # ------------------------------------------------------------------
    # STEP 2 — Per-project analysis, optionally parallel.
    #
    # LLM_PROJECT_PARALLELISM controls how many projects run simultaneously.
    # Default is 2 (moderate); set to 1 to fall back to fully sequential
    # behavior (identical to the previous implementation). Higher values
    # speed up runs at scale (50+ projects) but stress the per-provider
    # rate limits and the DB pool more. The provider semaphores in
    # MultiLLMMonitoringService cap external API concurrency globally,
    # so increasing parallelism is safe up to ~5 with the defaults.
    #
    # Each per-project call is still wrapped in run_project_with_timeout
    # (Phase 3) so a stuck project doesn't block siblings or the run.
    # ------------------------------------------------------------------
    from project_timeout import run_project_with_timeout

    parallelism = int(os.getenv('LLM_PROJECT_PARALLELISM', '2'))
    parallelism = max(1, parallelism)
    logger.info(
        f"🧵 Procesando proyectos con paralelismo={parallelism} "
        f"(LLM_PROJECT_PARALLELISM env)"
    )

    def _analyze_one(project):
        pid = project['id']
        try:
            return run_project_with_timeout(
                target=lambda: service.analyze_project(project_id=pid, max_workers=max_workers),
                project_id=pid,
            )
        except Exception as e:
            logger.error(f"❌ Error analizando proyecto {pid}: {e}")
            return {'project_id': pid, 'success': False, 'error': str(e)}

    if parallelism <= 1 or len(eligible_projects) <= 1:
        # Sequential path — preserves the previous behavior exactly.
        results = [_analyze_one(p) for p in eligible_projects]
    else:
        # Parallel path — submit all eligible projects to a bounded pool.
        # We collect results in an indexed dict so the returned list keeps
        # the original order (downstream consumers may rely on it).
        indexed = {}
        with ThreadPoolExecutor(max_workers=parallelism, thread_name_prefix='proj') as ex:
            future_to_idx = {
                ex.submit(_analyze_one, p): i
                for i, p in enumerate(eligible_projects)
            }
            for fut in as_completed(future_to_idx):
                idx = future_to_idx[fut]
                try:
                    indexed[idx] = fut.result()
                except Exception as e:
                    # _analyze_one itself shouldn't raise (it catches), but
                    # belt-and-suspenders in case the executor surfaces something.
                    pid = eligible_projects[idx]['id']
                    logger.error(f"❌ Future for project {pid} raised unexpectedly: {e}")
                    indexed[idx] = {
                        'project_id': pid,
                        'success': False,
                        'error': f'executor_error: {e}',
                    }
        results = [indexed[i] for i in range(len(eligible_projects))]

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
    language_code = (language or 'en').strip().lower()
    language_name = LANGUAGE_NAMES.get(language_code, language_code.upper())
    
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
        
        # Prompt en inglés para máxima robustez, con output forzado al idioma objetivo.
        prompt = f"""You are an expert in digital marketing and LLM brand visibility.

PROJECT CONTEXT:
- Brand: {brand_name}
- Industry: {industry}
- Target language: {language_name} ({language_code})
- Competitors: {', '.join(competitors) if competitors else 'none specified'}

EXISTING PROMPTS ({len(existing_queries)}):
{chr(10).join('- ' + q for q in existing_queries[:10]) if existing_queries else '(none yet)'}

TASK:
Generate {count} additional prompts a user would ask an LLM (ChatGPT, Claude, Gemini, Perplexity) when researching {industry}.

REQUIREMENTS:
1. ALL prompts must be written in {language_name}
2. Do not repeat existing prompts
3. Make them natural and realistic
4. Include a mix of: brand-focused, industry-generic, and competitor-comparison prompts
5. Minimum 15 characters per prompt
6. Return ONLY prompts, one per line, without numbering or bullets

GENERATE {count} PROMPTS:"""

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
        existing_lower = {q.lower().strip() for q in existing_queries}
        seen = set()
        for line in response_text.split('\n'):
            line = line.strip()
            
            # Ignorar líneas vacías, numeraciones, viñetas
            if not line:
                continue
            if len(line) > 1 and line[0].isdigit() and (line[1] == '.' or line[1] == ')'):
                line = line[2:].strip()
            if line.startswith('-') or line.startswith('•'):
                line = line[1:].strip()
            
            # Validar longitud
            if len(line) >= 15 and len(line) <= 500:
                # Evitar duplicados con existentes
                normalized = line.lower().strip()
                if normalized not in existing_lower and normalized not in seen:
                    suggestions.append(line)
                    seen.add(normalized)
        
        # Limitar a count
        suggestions = suggestions[:count]
        
        logger.info(f"✅ Generadas {len(suggestions)} sugerencias con IA")
        logger.info(f"   Coste: ${result.get('cost_usd', 0):.6f} USD")
        
        return suggestions
        
    except Exception as e:
        logger.error(f"❌ Error generando sugerencias con IA: {e}", exc_info=True)
        return []
