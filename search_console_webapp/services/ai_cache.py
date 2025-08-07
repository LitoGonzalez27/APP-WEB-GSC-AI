# services/ai_cache.py - Sistema de caché inteligente para análisis AI Overview

import redis
import json
import logging
import hashlib
from datetime import timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class AIOverviewCache:
    """Sistema de caché inteligente para análisis de AI Overview"""
    
    def __init__(self):
        """Inicializa el cliente Redis con configuración robusta"""
        try:
            # Configuración con fallback para desarrollo local
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Configuraciones de caché
            self.cache_duration = timedelta(hours=24)  # Caché de 24 horas
            self.short_cache_duration = timedelta(hours=6)  # Para errores/fallos
            
            # Verificar conexión
            self.redis_client.ping()
            self.cache_available = True
            logger.info("✅ Sistema de caché Redis conectado correctamente")
            
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"⚠️ Redis no disponible, funcionando sin caché: {e}")
            self.redis_client = None
            self.cache_available = False
        except Exception as e:
            logger.error(f"❌ Error configurando Redis: {e}")
            self.redis_client = None
            self.cache_available = False
    
    def _generate_cache_key(self, keyword: str, site_url: str, country: str) -> str:
        """Genera una clave única para el caché basada en los parámetros"""
        # Normalizar inputs para generar claves consistentes
        keyword_normalized = keyword.lower().strip()
        site_url_normalized = site_url.lower().strip()
        country_normalized = country.lower().strip()
        
        # Crear hash para evitar claves muy largas
        content = f"{keyword_normalized}:{site_url_normalized}:{country_normalized}"
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        
        return f"ai_analysis:{content_hash}:{keyword_normalized[:20]}"
    
    def get_cached_analysis(self, keyword: str, site_url: str, country: str) -> Optional[Dict[str, Any]]:
        """Obtiene un análisis desde el caché si existe y es válido"""
        if not self.cache_available:
            return None
            
        try:
            cache_key = self._generate_cache_key(keyword, site_url, country)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                logger.info(f"💾 Cache HIT para keyword: {keyword[:20]}...")
                return data
            else:
                logger.debug(f"💾 Cache MISS para keyword: {keyword[:20]}...")
                return None
                
        except (redis.ConnectionError, json.JSONDecodeError) as e:
            logger.warning(f"Error leyendo del caché: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado en caché: {e}")
            return None
    
    def cache_analysis(self, keyword: str, site_url: str, country: str, analysis: Dict[str, Any]) -> bool:
        """Guarda un análisis en el caché con metadatos adicionales"""
        if not self.cache_available:
            return False
            
        try:
            cache_key = self._generate_cache_key(keyword, site_url, country)
            
            # Añadir metadatos al análisis
            cached_data = {
                'analysis': analysis,
                'cached_at': str(timedelta(seconds=0)),  # Timestamp relativo
                'keyword': keyword,
                'site_url': site_url,
                'country': country,
                'cache_version': '1.0'
            }
            
            # Determinar duración del caché basada en el resultado
            if analysis.get('ai_analysis', {}).get('has_ai_overview', False):
                duration = self.cache_duration  # 24 horas para resultados positivos
            else:
                duration = self.short_cache_duration  # 6 horas para resultados negativos
            
            # Guardar en Redis
            self.redis_client.setex(
                cache_key,
                int(duration.total_seconds()),
                json.dumps(cached_data, ensure_ascii=False)
            )
            
            logger.info(f"💾 Análisis cacheado para {keyword[:20]}... por {duration.total_seconds()/3600:.1f}h")
            return True
            
        except (redis.ConnectionError, TypeError) as e:
            logger.warning(f"Error guardando en caché: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado guardando en caché: {e}")
            return False
    
    def cache_analysis_batch(self, analyses: list) -> int:
        """Guarda múltiples análisis en el caché de forma eficiente"""
        if not self.cache_available or not analyses:
            return 0
            
        try:
            pipe = self.redis_client.pipeline()
            cached_count = 0
            
            for analysis in analyses:
                keyword = analysis.get('keyword', '')
                site_url = analysis.get('site_url', '')
                country = analysis.get('country_analyzed', '')
                
                if not all([keyword, site_url]):
                    continue
                
                cache_key = self._generate_cache_key(keyword, site_url, country)
                
                cached_data = {
                    'analysis': analysis,
                    'cached_at': str(timedelta(seconds=0)),
                    'keyword': keyword,
                    'site_url': site_url,
                    'country': country,
                    'cache_version': '1.0'
                }
                
                # Duración basada en resultado
                if analysis.get('ai_analysis', {}).get('has_ai_overview', False):
                    duration = self.cache_duration
                else:
                    duration = self.short_cache_duration
                
                pipe.setex(
                    cache_key,
                    int(duration.total_seconds()),
                    json.dumps(cached_data, ensure_ascii=False)
                )
                cached_count += 1
            
            # Ejecutar pipeline
            pipe.execute()
            logger.info(f"💾 Lote de {cached_count} análisis guardados en caché")
            return cached_count
            
        except Exception as e:
            logger.error(f"Error en caché por lotes: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema de caché"""
        if not self.cache_available:
            return {'cache_available': False, 'message': 'Redis no disponible'}
        
        try:
            info = self.redis_client.info()
            
            # Contar claves específicas de AI Overview
            pattern = "ai_analysis:*"
            ai_keys = self.redis_client.keys(pattern)
            
            return {
                'cache_available': True,
                'redis_version': info.get('redis_version', 'unknown'),
                'used_memory': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'ai_analyses_cached': len(ai_keys),
                'total_keys': info.get('db0', {}).get('keys', 0) if 'db0' in info else 0,
                'uptime_seconds': info.get('uptime_in_seconds', 0)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de caché: {e}")
            return {'cache_available': False, 'error': str(e)}
    
    def clear_cache(self, pattern: str = "ai_analysis:*") -> int:
        """Limpia el caché de AI Overview (útil para mantenimiento)"""
        if not self.cache_available:
            return 0
            
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"💾 Limpiadas {deleted} entradas del caché")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Error limpiando caché: {e}")
            return 0
    
    def invalidate_site_cache(self, site_url: str) -> int:
        """Invalida todo el caché relacionado con un sitio específico"""
        if not self.cache_available:
            return 0
            
        try:
            # Buscar todas las claves que puedan contener el sitio
            # Nota: esto es una implementación simplificada
            # En producción sería mejor mantener un índice por sitio
            pattern = "ai_analysis:*"
            keys = self.redis_client.keys(pattern)
            
            deleted_count = 0
            for key in keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        cached_data = json.loads(data)
                        if cached_data.get('site_url', '').lower() == site_url.lower():
                            self.redis_client.delete(key)
                            deleted_count += 1
                except:
                    continue
            
            logger.info(f"💾 Invalidadas {deleted_count} entradas de caché para {site_url}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error invalidando caché del sitio: {e}")
            return 0

# Instancia global del caché
ai_cache = AIOverviewCache() 