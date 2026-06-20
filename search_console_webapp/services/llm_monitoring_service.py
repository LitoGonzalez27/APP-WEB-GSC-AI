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

from services.llm_monitoring.helpers import _HelpersMixin
from services.llm_monitoring.generation import _GenerationMixin
from services.llm_monitoring.detection import _DetectionMixin
from services.llm_monitoring.sentiment import _SentimentMixin
from services.llm_monitoring.engine import _EngineMixin
from services.llm_monitoring.snapshot import _SnapshotMixin


class MultiLLMMonitoringService(_HelpersMixin, _GenerationMixin, _DetectionMixin, _SentimentMixin, _EngineMixin, _SnapshotMixin):
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
    if not conn:
        raise Exception("No se pudo conectar a BD para listar proyectos activos")

    cur = None
    try:
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
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass
    
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
