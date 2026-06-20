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


class _HelpersMixin:

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
