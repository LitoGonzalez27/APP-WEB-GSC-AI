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


class _SnapshotMixin:

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
