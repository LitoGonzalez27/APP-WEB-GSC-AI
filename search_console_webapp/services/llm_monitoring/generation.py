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


class _GenerationMixin:

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
