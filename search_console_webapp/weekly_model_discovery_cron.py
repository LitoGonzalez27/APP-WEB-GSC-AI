#!/usr/bin/env python3
"""
🔍 Weekly LLM Model Discovery Cron

Este script se ejecuta semanalmente para:
1. Consultar las APIs de cada proveedor LLM
2. Detectar nuevos modelos disponibles
3. Enviar notificación si hay modelos nuevos
4. Opcionalmente, activar automáticamente los nuevos modelos

Configuración CRON recomendada (cada lunes a las 9:00 AM):
    0 9 * * 1 /usr/bin/python3 /path/to/weekly_model_discovery_cron.py

Variables de entorno necesarias:
    - OPENAI_API_KEY
    - GOOGLE_AI_API_KEY  
    - ANTHROPIC_API_KEY
    - PERPLEXITY_API_KEY
    - NOTIFICATION_EMAIL (opcional)
    - AUTO_UPDATE_MODELS=true/false (default: false)
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelDiscoveryService:
    """Servicio para descubrir modelos disponibles en cada proveedor."""
    
    def __init__(self):
        self.discovered_models = {}
        self.new_models = []
        
    def discover_openai_models(self) -> List[Dict]:
        """Descubre modelos disponibles en OpenAI."""
        try:
            import openai
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            models = client.models.list()
            
            # Filtrar modelos GPT relevantes
            gpt_models = []
            priority_patterns = ['gpt-5', 'gpt-4o', 'gpt-4-turbo', 'o1', 'o3']
            
            for model in models.data:
                model_id = model.id.lower()
                for pattern in priority_patterns:
                    if pattern in model_id:
                        gpt_models.append({
                            'model_id': model.id,
                            'provider': 'openai',
                            'created': getattr(model, 'created', None)
                        })
                        break
            
            # Ordenar por fecha de creación (más reciente primero)
            gpt_models.sort(key=lambda x: x.get('created', 0) or 0, reverse=True)
            
            logger.info(f"✅ OpenAI: {len(gpt_models)} modelos GPT encontrados")
            return gpt_models[:10]  # Top 10 más recientes
            
        except Exception as e:
            logger.error(f"❌ OpenAI discovery error: {e}")
            return []
    
    def discover_google_models(self) -> List[Dict]:
        """Descubre modelos disponibles en Google AI."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
            
            models = genai.list_models()
            
            gemini_models = []
            for model in models:
                if 'gemini' in model.name.lower():
                    # Extraer model_id del nombre completo
                    model_id = model.name.split('/')[-1] if '/' in model.name else model.name
                    gemini_models.append({
                        'model_id': model_id,
                        'provider': 'google',
                        'display_name': getattr(model, 'display_name', model_id),
                        'description': getattr(model, 'description', '')[:100] if hasattr(model, 'description') else ''
                    })
            
            logger.info(f"✅ Google: {len(gemini_models)} modelos Gemini encontrados")
            return gemini_models
            
        except Exception as e:
            logger.error(f"❌ Google discovery error: {e}")
            return []
    
    def discover_anthropic_models(self) -> List[Dict]:
        """
        Anthropic no tiene endpoint de listado de modelos.
        Usamos una lista conocida + verificación de disponibilidad.
        """
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            
            # Modelos conocidos de Claude (actualizar manualmente cuando haya nuevos)
            known_models = [
                'claude-sonnet-4-5-20250929',  # Claude Sonnet 4.5 (más reciente)
                'claude-3-7-sonnet-20250219',   # Claude 3.7 Sonnet
                'claude-3-5-sonnet-20241022',   # Claude 3.5 Sonnet
                'claude-3-5-haiku-20241022',    # Claude 3.5 Haiku
                'claude-3-opus-20240229',       # Claude 3 Opus
            ]
            
            available_models = []
            for model_id in known_models:
                try:
                    # Intentar una llamada mínima para verificar disponibilidad
                    response = client.messages.create(
                        model=model_id,
                        max_tokens=10,
                        messages=[{"role": "user", "content": "Hi"}]
                    )
                    available_models.append({
                        'model_id': model_id,
                        'provider': 'anthropic',
                        'verified': True
                    })
                    logger.debug(f"   ✓ {model_id} disponible")
                except Exception as e:
                    if 'model' in str(e).lower() and 'not found' in str(e).lower():
                        logger.debug(f"   ✗ {model_id} no disponible")
                    else:
                        # Otro error (rate limit, etc) - asumir disponible
                        available_models.append({
                            'model_id': model_id,
                            'provider': 'anthropic',
                            'verified': False
                        })
                    break  # No gastar créditos verificando todos
            
            logger.info(f"✅ Anthropic: {len(available_models)} modelos Claude verificados")
            return available_models
            
        except Exception as e:
            logger.error(f"❌ Anthropic discovery error: {e}")
            return []
    
    def discover_perplexity_models(self) -> List[Dict]:
        """
        Perplexity tiene pocos modelos. Lista conocida.
        """
        # Modelos conocidos de Perplexity
        known_models = [
            {'model_id': 'sonar', 'provider': 'perplexity', 'display_name': 'Sonar'},
            {'model_id': 'sonar-pro', 'provider': 'perplexity', 'display_name': 'Sonar Pro'},
            {'model_id': 'sonar-reasoning', 'provider': 'perplexity', 'display_name': 'Sonar Reasoning'},
        ]
        
        logger.info(f"✅ Perplexity: {len(known_models)} modelos conocidos")
        return known_models
    
    def get_current_models_from_db(self) -> Dict[str, str]:
        """Obtiene los modelos actuales de la BD."""
        conn = get_db_connection()
        if not conn:
            return {}
        
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT llm_provider, model_id 
                FROM llm_model_registry 
                WHERE is_current = TRUE
            """)
            
            current = {}
            for row in cur.fetchall():
                current[row['llm_provider']] = row['model_id']
            
            return current
        except Exception as e:
            logger.error(f"❌ DB error: {e}")
            return {}
        finally:
            cur.close()
            conn.close()
    
    def get_all_known_models_from_db(self) -> set:
        """Obtiene todos los model_ids conocidos en BD."""
        conn = get_db_connection()
        if not conn:
            return set()
        
        try:
            cur = conn.cursor()
            cur.execute("SELECT model_id FROM llm_model_registry")
            return {row['model_id'] for row in cur.fetchall()}
        except Exception as e:
            logger.error(f"❌ DB error: {e}")
            return set()
        finally:
            cur.close()
            conn.close()
    
    def detect_new_models(self, discovered: List[Dict], known: set) -> List[Dict]:
        """Detecta modelos nuevos que no están en BD."""
        new_models = []
        for model in discovered:
            if model['model_id'] not in known:
                new_models.append(model)
        return new_models
    
    def add_model_to_db(self, model: Dict) -> bool:
        """Añade un nuevo modelo a la BD."""
        conn = get_db_connection()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO llm_model_registry 
                (llm_provider, model_id, model_display_name, is_current, is_available)
                VALUES (%s, %s, %s, FALSE, TRUE)
                ON CONFLICT (llm_provider, model_id) DO NOTHING
            """, (
                model['provider'],
                model['model_id'],
                model.get('display_name', model['model_id'])
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error adding model: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    def set_model_as_current(self, provider: str, model_id: str) -> bool:
        """Establece un modelo como el actual para su proveedor."""
        conn = get_db_connection()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            # Quitar current de todos los del proveedor
            cur.execute("""
                UPDATE llm_model_registry SET is_current = FALSE 
                WHERE llm_provider = %s
            """, (provider,))
            
            # Marcar el nuevo como current
            cur.execute("""
                UPDATE llm_model_registry SET is_current = TRUE 
                WHERE llm_provider = %s AND model_id = %s
            """, (provider, model_id))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error setting current model: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            conn.close()
    
    def send_notification(self, new_models: List[Dict], subject: str = "🤖 Nuevos modelos LLM detectados"):
        """Envía notificación por email sobre nuevos modelos."""
        notification_email = os.getenv('NOTIFICATION_EMAIL')
        
        if not notification_email or not new_models:
            return
        
        try:
            # Importar servicio de email si existe
            from email_service import send_email
            
            body = f"""
            <h2>🔍 Nuevos modelos LLM detectados</h2>
            <p>Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            
            <h3>Modelos encontrados:</h3>
            <ul>
            """
            
            for model in new_models:
                body += f"<li><strong>{model['provider']}</strong>: {model['model_id']}</li>"
            
            body += """
            </ul>
            
            <p>Puedes activar estos modelos desde el panel de administración o ejecutando:</p>
            <pre>python update_models_now.py</pre>
            """
            
            send_email(notification_email, subject, body)
            logger.info(f"📧 Notificación enviada a {notification_email}")
            
        except Exception as e:
            logger.warning(f"⚠️ No se pudo enviar notificación: {e}")
    
    def run_discovery(self, auto_update: bool = False) -> Dict:
        """
        Ejecuta el proceso completo de descubrimiento.
        
        Args:
            auto_update: Si True, activa automáticamente los modelos más nuevos
            
        Returns:
            Diccionario con resultados del descubrimiento
        """
        logger.info("=" * 60)
        logger.info("🔍 Iniciando descubrimiento de modelos LLM...")
        logger.info("=" * 60)
        
        # 1. Obtener modelos conocidos de BD
        known_models = self.get_all_known_models_from_db()
        current_models = self.get_current_models_from_db()
        
        logger.info(f"\n📊 Modelos actuales en BD:")
        for provider, model in current_models.items():
            logger.info(f"   • {provider}: {model}")
        
        # 2. Descubrir modelos de cada proveedor
        logger.info(f"\n🔍 Consultando APIs de proveedores...")
        
        all_discovered = []
        all_discovered.extend(self.discover_openai_models())
        all_discovered.extend(self.discover_google_models())
        all_discovered.extend(self.discover_anthropic_models())
        all_discovered.extend(self.discover_perplexity_models())
        
        # 3. Detectar nuevos modelos
        new_models = self.detect_new_models(all_discovered, known_models)
        
        logger.info(f"\n📋 Resumen:")
        logger.info(f"   • Total modelos descubiertos: {len(all_discovered)}")
        logger.info(f"   • Nuevos modelos: {len(new_models)}")
        
        if new_models:
            logger.info(f"\n🆕 Nuevos modelos encontrados:")
            for model in new_models:
                logger.info(f"   • {model['provider']}: {model['model_id']}")
                
                # Añadir a BD
                if self.add_model_to_db(model):
                    logger.info(f"     ✅ Añadido a BD")
                    
                    # Auto-update si está habilitado
                    if auto_update:
                        if self.set_model_as_current(model['provider'], model['model_id']):
                            logger.info(f"     🔄 Activado como modelo actual")
            
            # Enviar notificación
            self.send_notification(new_models)
        else:
            logger.info("\n✅ No hay nuevos modelos. Todo actualizado.")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Descubrimiento completado")
        logger.info("=" * 60)
        
        return {
            'discovered': len(all_discovered),
            'new_models': new_models,
            'current_models': current_models
        }


def main():
    """Punto de entrada principal."""
    # Verificar si auto-update está habilitado
    auto_update = os.getenv('AUTO_UPDATE_MODELS', 'false').lower() == 'true'
    
    if auto_update:
        logger.warning("⚠️ AUTO_UPDATE_MODELS está habilitado. Los nuevos modelos se activarán automáticamente.")
    
    service = ModelDiscoveryService()
    result = service.run_discovery(auto_update=auto_update)
    
    # Exit code basado en si hay nuevos modelos
    if result['new_models']:
        sys.exit(1)  # Hay nuevos modelos (útil para CI/CD)
    else:
        sys.exit(0)  # Todo actualizado


if __name__ == '__main__':
    main()

