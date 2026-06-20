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


class _SentimentMixin:

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
