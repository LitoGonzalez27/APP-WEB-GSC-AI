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
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        brand_name: str,
        competitors: List[str] = None
    ) -> Dict:
        """
        Analiza si una respuesta menciona la marca y extrae contexto
        
        IMPORTANTE: Reutiliza extract_brand_variations() de ai_analysis.py
        
        Args:
            response_text: Respuesta del LLM
            brand_name: Nombre de la marca a buscar
            competitors: Lista de competidores a detectar
            
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
        competitors = competitors or []
        
        # Obtener variaciones de la marca
        brand_variations = extract_brand_variations(brand_name.lower())
        
        # Buscar menciones (case-insensitive)
        mentions_found = []
        mention_contexts = []
        
        text_lower = response_text.lower()
        
        for variation in brand_variations:
            # Usar word boundaries para evitar falsos positivos
            pattern = r'\b' + re.escape(variation.lower()) + r'\b'
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            
            for match in matches:
                start = match.start()
                end = match.end()
                mentions_found.append((start, end))
                
                # Extraer contexto (150 chars antes y después)
                context_start = max(0, start - 150)
                context_end = min(len(response_text), end + 150)
                context = response_text[context_start:context_end].strip()
                
                if context not in mention_contexts:
                    mention_contexts.append(context)
        
        brand_mentioned = len(mentions_found) > 0
        mention_count = len(mentions_found)
        
        # Detectar posición en listas numeradas
        list_info = self._detect_position_in_list(response_text, brand_variations)
        
        # Detectar competidores mencionados
        competitors_mentioned = {}
        for competitor in competitors:
            comp_variations = extract_brand_variations(competitor.lower())
            comp_count = 0
            
            for variation in comp_variations:
                pattern = r'\b' + re.escape(variation.lower()) + r'\b'
                comp_count += len(re.findall(pattern, text_lower, re.IGNORECASE))
            
            if comp_count > 0:
                competitors_mentioned[competitor] = comp_count
        
        return {
            'brand_mentioned': brand_mentioned,
            'mention_count': mention_count,
            'mention_contexts': mention_contexts[:5],  # Máximo 5 contextos
            'appears_in_numbered_list': list_info['appears_in_list'],
            'position_in_list': list_info['position'],
            'total_items_in_list': list_info['total_items'],
            'competitors_mentioned': competitors_mentioned
        }
    
    def _detect_position_in_list(
        self,
        text: str,
        brand_variations: List[str]
    ) -> Dict:
        """
        Detecta si la marca aparece en una lista numerada y su posición
        
        Patrones detectados:
        - "1. Brand name"
        - "1) Brand name"
        - "**1.** Brand name"
        
        Returns:
            Dict con appears_in_list, position, total_items
        """
        # Patrones de listas numeradas
        patterns = [
            r'(\d+)\.\s*[*_]*(.+?)(?:\n|$)',  # "1. Item\n"
            r'(\d+)\)\s*[*_]*(.+?)(?:\n|$)',  # "1) Item\n"
            r'\*\*(\d+)\.\*\*\s*(.+?)(?:\n|$)',  # "**1.** Item\n"
        ]
        
        for pattern in patterns:
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
                        
                        return {
                            'appears_in_list': True,
                            'position': position,
                            'total_items': total_items
                        }
        
        return {
            'appears_in_list': False,
            'position': None,
            'total_items': None
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
        max_workers: int = 10,
        analysis_date: date = None
    ) -> Dict:
        """
        Analiza un proyecto completo en todos los LLMs habilitados
        
        ⚡ OPTIMIZACIÓN CRÍTICA: Usa ThreadPoolExecutor
        
        Antes: 4 LLMs × 20 queries × 5s = 400 segundos (6.7 minutos)
        Después: 80 tareas / 10 workers = ~40 segundos
        Mejora: 10x más rápido 🚀
        
        Args:
            project_id: ID del proyecto a analizar
            max_workers: Número de threads paralelos
            analysis_date: Fecha del análisis (default: hoy)
            
        Returns:
            Dict con métricas globales
        """
        analysis_date = analysis_date or date.today()
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
            
            # Obtener datos del proyecto
            cur.execute("""
                SELECT 
                    id, user_id, name, brand_name, industry,
                    enabled_llms, competitors, language, queries_per_llm
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
            
            logger.info(f"   🤖 {len(active_providers)} proveedores activos")
            logger.info("")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo proyecto: {e}")
            cur.close()
            conn.close()
            raise
        
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
                    'brand_name': project['brand_name'],
                    'competitors': project['competitors'] or [],
                    'analysis_date': analysis_date
                })
        
        total_tasks = len(tasks)
        logger.info(f"⚡ Ejecutando {total_tasks} tareas en paralelo (max_workers={max_workers})...")
        logger.info("")
        
        # Ejecutar en paralelo con ThreadPoolExecutor
        results_by_llm = {name: [] for name in active_providers.keys()}
        completed_tasks = 0
        failed_tasks = 0
        
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
                        logger.warning(f"   ⚠️ Tarea fallida: {task['llm_name']} - {task['query_text'][:50]}...")
                        
                except Exception as e:
                    failed_tasks += 1
                    logger.error(f"   ❌ Excepción en tarea: {e}")
        
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
        
        try:
            for llm_name, llm_results in results_by_llm.items():
                if len(llm_results) > 0:
                    self._create_snapshot(
                        cur=cur,
                        project_id=project_id,
                        date=analysis_date,
                        llm_provider=llm_name,
                        llm_results=llm_results,
                        competitors=project['competitors'] or []
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
            }
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
            # Ejecutar query en el LLM
            llm_result = task['provider'].execute_query(task['query_text'])
            
            if not llm_result['success']:
                return {
                    'success': False,
                    'error': llm_result.get('error', 'Unknown error')
                }
            
            # Analizar menciones de marca
            mention_analysis = self.analyze_brand_mention(
                response_text=llm_result['content'],
                brand_name=task['brand_name'],
                competitors=task['competitors']
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
                        appears_in_numbered_list, position_in_list, total_items_in_list,
                        sentiment, sentiment_score,
                        competitors_mentioned,
                        full_response, response_length,
                        tokens_used, input_tokens, output_tokens, cost_usd, response_time_ms
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s,
                        %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (project_id, query_id, llm_provider, analysis_date) 
                    DO UPDATE SET
                        brand_mentioned = EXCLUDED.brand_mentioned,
                        mention_count = EXCLUDED.mention_count,
                        sentiment = EXCLUDED.sentiment,
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
                    sentiment_data['sentiment'],
                    sentiment_data['score'],
                    json.dumps(mention_analysis['competitors_mentioned']),
                    llm_result['content'],
                    len(llm_result['content']),
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
    
    # =====================================================
    # CREACIÓN DE SNAPSHOTS
    # =====================================================
    
    def _create_snapshot(
        self,
        cur,
        project_id: int,
        date: date,
        llm_provider: str,
        llm_results: List[Dict],
        competitors: List[str]
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
        
        # Share of Voice
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
        
        # Insertar snapshot
        cur.execute("""
            INSERT INTO llm_monitoring_snapshots (
                project_id, snapshot_date, llm_provider,
                total_queries, total_mentions, mention_rate,
                avg_position, appeared_in_top3, appeared_in_top5, appeared_in_top10,
                total_competitor_mentions, share_of_voice, competitor_breakdown,
                positive_mentions, neutral_mentions, negative_mentions, avg_sentiment_score,
                avg_response_time_ms, total_cost_usd, total_tokens
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
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
            positive_mentions, neutral_mentions, negative_mentions,
            round(avg_sentiment_score, 2),
            int(avg_response_time), round(total_cost, 4), total_tokens
        ))
        
        logger.info(f"   📊 Snapshot {llm_provider}: {total_mentions}/{total_queries} menciones ({mention_rate:.1f}%)")


# =====================================================
# HELPER FUNCTION
# =====================================================

def analyze_all_active_projects(api_keys: Dict[str, str] = None, max_workers: int = 10) -> List[Dict]:
    """
    Analiza todos los proyectos activos
    
    Útil para cron jobs que ejecutan análisis automáticos
    
    Args:
        api_keys: Dict con API keys (opcional, usa env vars si es None)
        max_workers: Threads paralelos
        
    Returns:
        Lista de resultados por proyecto
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

