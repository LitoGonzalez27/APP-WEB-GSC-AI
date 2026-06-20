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


class _EngineMixin:

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

        cur = None
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

            # Si el proyecto está pausado por cuota y la ventana paused_until aún no
            # expiró, bloquear el análisis. Si paused_until ya pasó, lo limpiamos y
            # seguimos (mismo patrón que Manual AI / AI Mode: auto-reanudación).
            if project.get('is_paused_by_quota'):
                paused_until = project.get('paused_until')
                now_cmp = None
                if paused_until is not None:
                    try:
                        now_cmp = datetime.now(paused_until.tzinfo) if paused_until.tzinfo else datetime.utcnow()
                    except Exception:
                        now_cmp = datetime.utcnow()

                if paused_until is None or paused_until > now_cmp:
                    return {
                        'success': False,
                        'error': 'project_paused_quota',
                        'message': 'Proyecto en pausa por agotamiento de cuota',
                        'paused_until': paused_until
                    }

                # paused_until expiró → limpiar el flag de este proyecto y continuar.
                # Conexión separada para no tocar la transacción del análisis en curso.
                try:
                    resume_conn = get_db_connection()
                    if resume_conn:
                        resume_cur = resume_conn.cursor()
                        try:
                            resume_cur.execute('''
                                UPDATE llm_monitoring_projects
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
                        finally:
                            resume_cur.close()
                            resume_conn.close()
                except Exception as resume_error:
                    logger.warning(
                        f"Error reanudando proyecto LLM {project_id} tras expiración de paused_until: {resume_error}"
                    )

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

            # Conjunto de providers que SE ESPERABA ejecutar (habilitados ∩
            # instanciados), capturado ANTES del health-check. Se usa abajo para
            # detectar providers que terminan con 0 resultados (p.ej. excluidos
            # por el health-check) — que de otro modo desaparecerían del run sin
            # contar como "incompletos" ni disparar la reconciliación.
            expected_provider_names = list(active_providers.keys())
            
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

            # ── Política de exclusión por health-check ──
            # Por defecto NO excluimos un provider por fallar el health-check
            # ligero. El "Hi" con timeout corto puede fallar puntualmente bajo
            # carga aunque el provider funcione, y excluirlo borra el provider
            # entero del run de forma silenciosa (causa del outage de Gemini de
            # may-2026). Las 5 capas de retry sobre las queries reales decidirán,
            # y cualquier fallo persistente quedará como filas de error visibles.
            # Comportamiento estricto opcional: LLM_HEALTHCHECK_EXCLUDE_ON_FAIL=true
            exclude_on_fail = os.getenv('LLM_HEALTHCHECK_EXCLUDE_ON_FAIL', 'false').lower() == 'true'
            if unhealthy_providers and exclude_on_fail:
                active_providers = healthy_providers
                logger.warning(f"⚠️  Excluidos del análisis (health-check estricto): {', '.join(unhealthy_providers)}")
            elif unhealthy_providers:
                logger.warning(f"⚠️  Health-check falló para: {', '.join(unhealthy_providers)}")
                logger.warning(f"   → NO se excluyen; se intentarán con el sistema de retry en las queries reales")
            # (si exclude_on_fail=False, active_providers conserva todos los habilitados)

            logger.info("")
            logger.info("=" * 70)
            logger.info(f"✅ PROVIDERS SALUDABLES: {len(active_providers)}/{len(enabled_llms)}")
            logger.info("=" * 70)
            logger.info(f"Activos: {', '.join(active_providers.keys())}")
            if unhealthy_providers and exclude_on_fail:
                logger.warning(f"⚠️  Excluidos: {', '.join(unhealthy_providers)}")
                logger.warning(f"   → El análisis continuará sin estos providers")
            logger.info("")
            
            if len(active_providers) == 0:
                logger.error("❌ NINGÚN PROVIDER ESTÁ DISPONIBLE")
                logger.error("   No se puede realizar el análisis")
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

        except Exception as e:
            logger.error(f"❌ Error obteniendo proyecto: {e}")
            raise
        finally:
            # Guarantee the connection returns to the pool on every path:
            # the success path, the early returns (paused, paywall,
            # no_active_queries, prompt_limit_exceeded, quota_exceeded,
            # no_providers_after_healthcheck), and the exception path.
            # Previously, the early returns inside this try block leaked
            # one connection each — over the daily cron with multiple
            # projects this drained the pool within ~8-13 days.
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass
        
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
        # Refactor 2026-05-25: null-check + cursor inside try.
        conn = get_db_connection()
        if not conn:
            logger.error("Snapshot save: no DB connection — skipping snapshot save")
            return {'completeness_by_llm': {}, 'incomplete_llms': []}

        # ✨ NUEVO: Usar nombres de competidores agrupados para el snapshot
        # En lugar de usar términos individuales, usamos los nombres agrupados
        # Esto hace que "orange.es" y "orange" se cuenten bajo "Orange"
        all_competitor_names = competitor_names if competitor_names else []

        # Guardar el mapeo para uso posterior
        self._competitor_term_to_name = competitor_term_to_name

        # ✨ NUEVO: Validar que todos los LLMs analicen todas las queries
        total_queries_expected = len(queries)

        try:
            cur = conn.cursor()
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
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass
        
        # ✨ NUEVO: Calcular completitud por LLM
        # Iteramos sobre los providers ESPERADOS (capturados antes del
        # health-check), no solo sobre los que devolvieron filas. Así un provider
        # que terminó con 0 resultados (p.ej. excluido por health-check o caído)
        # cuenta como incompleto (0/N) y la reconciliación (Capa 4) lo reintenta,
        # en vez de desaparecer silenciosamente del run.
        completeness_by_llm = {}
        incomplete_llms = []

        for llm_name in expected_provider_names:
            llm_results = results_by_llm.get(llm_name, [])
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
            # Refactor 2026-05-25: null-check + cursor inside try.
            conn = get_db_connection()
            if not conn:
                logger.error(f"Save analysis result: no DB connection (project={task['project_id']})")
                return {'success': False, 'error': 'no_db_connection'}
            try:
                cur = conn.cursor()
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
                try:
                    conn.close()
                except Exception:
                    pass

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
        # Refactor 2026-05-25: explicit conn=None + try/finally.
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                logger.error(f"_save_error_result: no DB connection (project={task.get('project_id')})")
                return
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

            except Exception as inner_e:
                logger.error(f"❌ Error in _save_error_result inner: {inner_e}")

        except Exception as e:
            logger.error(f"❌ Error guardando registro de error: {e}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    
    # =====================================================
    # CREACIÓN DE SNAPSHOTS
    # =====================================================
