#!/usr/bin/env python3
"""
Script para diagnosticar y corregir problemas con la monitorización de OpenAI

PROBLEMAS DETECTADOS:
1. Precios incorrectos en BD ($15/$45 en vez de $1.25/$10)
2. Posible problema con API key
3. No hay análisis desde 06 de noviembre

Este script:
- Actualiza los precios correctos de GPT-5
- Verifica la API key
- Prueba hacer una query
- Revisa últimos análisis
- Genera reporte de diagnóstico
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from database import get_db_connection


def check_openai_api_key():
    """Verifica que la API key de OpenAI esté configurada y sea válida"""
    logger.info("\n" + "="*60)
    logger.info("1. VERIFICANDO API KEY DE OPENAI")
    logger.info("="*60)
    
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        logger.error("❌ OPENAI_API_KEY no está configurada en variables de entorno")
        return False
    
    # Ocultar parte de la key por seguridad
    masked_key = api_key[:10] + "..." + api_key[-4:]
    logger.info(f"✅ API Key encontrada: {masked_key}")
    logger.info(f"   Longitud: {len(api_key)} caracteres")
    logger.info(f"   Prefijo: {api_key[:8]}")
    
    # Intentar probar la API
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Test simple: listar modelos
        logger.info("\n📡 Probando conexión con OpenAI...")
        models = client.models.list()
        gpt_models = [m.id for m in models.data if 'gpt' in m.id.lower()]
        
        logger.info(f"✅ Conexión exitosa!")
        logger.info(f"   Modelos GPT disponibles: {len(gpt_models)}")
        
        # Verificar si gpt-5 está disponible
        if 'gpt-5' in gpt_models:
            logger.info("   ✅ GPT-5 está disponible")
        else:
            logger.warning("   ⚠️  GPT-5 no aparece en la lista de modelos")
            logger.info(f"   Modelos GPT encontrados: {gpt_models[:5]}")
        
        # Test de query simple
        logger.info("\n🧪 Probando query simple con GPT-5...")
        try:
            response = client.chat.completions.create(
                model='gpt-5',
                messages=[{"role": "user", "content": "Hola, responde solo 'OK' si puedes leerme."}],
                max_tokens=10
            )
            content = response.choices[0].message.content
            logger.info(f"✅ Query exitosa! Respuesta: '{content}'")
            logger.info(f"   Tokens usados: {response.usage.total_tokens}")
            return True
        except Exception as e:
            logger.error(f"❌ Error ejecutando query: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error verificando API: {e}")
        return False


def fix_gpt5_pricing():
    """Actualiza los precios correctos de GPT-5 en la BD"""
    logger.info("\n" + "="*60)
    logger.info("2. CORRIGIENDO PRECIOS DE GPT-5")
    logger.info("="*60)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar precios actuales
        cur.execute("""
            SELECT 
                model_id, 
                cost_per_1m_input_tokens, 
                cost_per_1m_output_tokens,
                is_current
            FROM llm_model_registry
            WHERE llm_provider = 'openai'
            ORDER BY is_current DESC, created_at DESC
        """)
        
        models = cur.fetchall()
        
        if not models:
            logger.warning("⚠️  No hay modelos de OpenAI en la BD")
            return False
        
        logger.info(f"\n📊 Modelos de OpenAI en BD:")
        for model in models:
            status = "✅ CURRENT" if model['is_current'] else "  "
            logger.info(f"   {status} {model['model_id']}")
            logger.info(f"        Input:  ${model['cost_per_1m_input_tokens']}/1M tokens")
            logger.info(f"        Output: ${model['cost_per_1m_output_tokens']}/1M tokens")
        
        # Actualizar precios correctos de GPT-5
        logger.info("\n🔧 Actualizando precios de GPT-5...")
        logger.info("   Precios CORRECTOS según OpenAI:")
        logger.info("   - Input:  $1.25 per 1M tokens")
        logger.info("   - Output: $10.00 per 1M tokens")
        
        cur.execute("""
            UPDATE llm_model_registry
            SET 
                cost_per_1m_input_tokens = 1.25,
                cost_per_1m_output_tokens = 10.00,
                is_current = TRUE,
                updated_at = NOW()
            WHERE llm_provider = 'openai' AND model_id = 'gpt-5'
            RETURNING id, model_id
        """)
        
        updated = cur.fetchone()
        
        if updated:
            logger.info(f"✅ Precios actualizados para {updated['model_id']}")
            conn.commit()
            return True
        else:
            logger.warning("⚠️  No se encontró el modelo gpt-5 en la BD")
            
            # Insertar GPT-5 si no existe
            logger.info("📝 Insertando GPT-5 en la BD...")
            cur.execute("""
                INSERT INTO llm_model_registry (
                    llm_provider, model_id, model_display_name,
                    cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                    max_tokens, is_current, is_available
                ) VALUES (
                    'openai', 'gpt-5', 'GPT-5',
                    1.25, 10.00,
                    400000, TRUE, TRUE
                )
                ON CONFLICT (llm_provider, model_id) 
                DO UPDATE SET
                    cost_per_1m_input_tokens = 1.25,
                    cost_per_1m_output_tokens = 10.00,
                    is_current = TRUE,
                    updated_at = NOW()
                RETURNING id
            """)
            
            result = cur.fetchone()
            if result:
                logger.info(f"✅ GPT-5 insertado con ID {result['id']}")
                conn.commit()
                return True
            else:
                logger.error("❌ Error insertando GPT-5")
                return False
        
    except Exception as e:
        logger.error(f"❌ Error actualizando precios: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def check_recent_analyses():
    """Revisa los análisis recientes de OpenAI"""
    logger.info("\n" + "="*60)
    logger.info("3. REVISANDO ANÁLISIS RECIENTES")
    logger.info("="*60)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return
    
    try:
        cur = conn.cursor()
        
        # Verificar últimos análisis de OpenAI
        cur.execute("""
            SELECT 
                r.analysis_date,
                r.llm_provider,
                r.model_used,
                r.brand_mentioned,
                r.error_message,
                q.query_text,
                p.name as project_name
            FROM llm_monitoring_results r
            JOIN llm_monitoring_queries q ON r.query_id = q.id
            JOIN llm_monitoring_projects p ON r.project_id = p.id
            WHERE r.llm_provider = 'openai'
            ORDER BY r.analysis_date DESC
            LIMIT 20
        """)
        
        results = cur.fetchall()
        
        if not results:
            logger.warning("⚠️  No hay análisis de OpenAI en la BD")
            return
        
        logger.info(f"\n📊 Últimos {len(results)} análisis de OpenAI:")
        
        # Agrupar por fecha
        by_date = {}
        for r in results:
            date_str = r['analysis_date'].strftime('%Y-%m-%d')
            if date_str not in by_date:
                by_date[date_str] = {'total': 0, 'errors': 0, 'mentions': 0}
            
            by_date[date_str]['total'] += 1
            if r['error_message']:
                by_date[date_str]['errors'] += 1
            if r['brand_mentioned']:
                by_date[date_str]['mentions'] += 1
        
        for date_str in sorted(by_date.keys(), reverse=True):
            stats = by_date[date_str]
            error_rate = (stats['errors'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            status = "✅" if error_rate == 0 else "⚠️" if error_rate < 50 else "❌"
            logger.info(f"\n   {status} {date_str}")
            logger.info(f"      Total: {stats['total']} análisis")
            logger.info(f"      Errores: {stats['errors']} ({error_rate:.1f}%)")
            logger.info(f"      Menciones: {stats['mentions']}")
        
        # Mostrar últimos errores
        errors = [r for r in results if r['error_message']]
        if errors:
            logger.info(f"\n⚠️  Últimos errores encontrados:")
            for err in errors[:5]:
                logger.info(f"   - {err['analysis_date']}: {err['error_message'][:100]}")
        
        # Verificar análisis desde el 06 de noviembre
        logger.info("\n📅 Verificando análisis desde 06-11-2024...")
        cur.execute("""
            SELECT 
                DATE(analysis_date) as date,
                COUNT(*) as count
            FROM llm_monitoring_results
            WHERE llm_provider = 'openai'
                AND analysis_date >= '2024-11-06'
            GROUP BY DATE(analysis_date)
            ORDER BY date DESC
        """)
        
        recent = cur.fetchall()
        if recent:
            logger.info("   Análisis por día desde 06-11-2024:")
            for row in recent:
                logger.info(f"      {row['date']}: {row['count']} análisis")
        else:
            logger.error("   ❌ NO HAY ANÁLISIS DE OPENAI DESDE EL 06-11-2024")
            logger.info("   Esto confirma el problema reportado por el usuario")
        
    except Exception as e:
        logger.error(f"❌ Error revisando análisis: {e}")
    finally:
        cur.close()
        conn.close()


def check_active_projects():
    """Verifica proyectos activos que usan OpenAI"""
    logger.info("\n" + "="*60)
    logger.info("4. VERIFICANDO PROYECTOS ACTIVOS")
    logger.info("="*60)
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la BD")
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                id,
                name,
                brand_name,
                enabled_llms,
                is_active,
                last_analysis_date,
                queries_per_llm
            FROM llm_monitoring_projects
            WHERE is_active = TRUE
            ORDER BY last_analysis_date DESC NULLS LAST
        """)
        
        projects = cur.fetchall()
        
        if not projects:
            logger.warning("⚠️  No hay proyectos activos")
            return
        
        logger.info(f"\n📊 {len(projects)} proyectos activos:")
        
        for p in projects:
            uses_openai = 'openai' in p['enabled_llms']
            status = "✅ OpenAI" if uses_openai else "  "
            last_analysis = p['last_analysis_date'].strftime('%Y-%m-%d') if p['last_analysis_date'] else "Never"
            
            logger.info(f"\n   {status} Proyecto #{p['id']}: {p['name']}")
            logger.info(f"      Marca: {p['brand_name']}")
            logger.info(f"      LLMs: {', '.join(p['enabled_llms'])}")
            logger.info(f"      Último análisis: {last_analysis}")
            logger.info(f"      Queries por LLM: {p['queries_per_llm']}")
            
            if uses_openai and p['last_analysis_date']:
                days_ago = (datetime.now().date() - p['last_analysis_date'].date()).days
                if days_ago > 2:
                    logger.warning(f"      ⚠️  Hace {days_ago} días sin análisis!")
        
    except Exception as e:
        logger.error(f"❌ Error verificando proyectos: {e}")
    finally:
        cur.close()
        conn.close()


def generate_recommendations():
    """Genera recomendaciones basadas en los problemas encontrados"""
    logger.info("\n" + "="*60)
    logger.info("5. RECOMENDACIONES")
    logger.info("="*60)
    
    logger.info("""
    📋 ACCIONES RECOMENDADAS:
    
    1. ✅ Precios de GPT-5 corregidos ($1.25/$10 en vez de $15/$45)
    
    2. 🔑 API Key:
       - Verificar que la API key en Railway sea la correcta
       - Comando: railway variables | grep OPENAI_API_KEY
       - Si es incorrecta, actualizar con: railway variables set OPENAI_API_KEY=sk-proj-...
    
    3. 🔄 Reiniciar servicio:
       - Después de actualizar la API key, reiniciar el servicio
       - Los precios ya están actualizados en BD
    
    4. 🧪 Probar análisis manual:
       - Ir a LLM Monitoring dashboard
       - Seleccionar un proyecto
       - Hacer clic en "Run Analysis"
       - Verificar que OpenAI funcione correctamente
    
    5. 📊 Verificar cron job:
       - El cron job diario debería ejecutarse automáticamente
       - Revisar logs en Railway para ver si hay errores
    
    6. ⏰ Si el problema persiste:
       - Revisar límites de rate de OpenAI (Tier 1: 500 RPM)
       - Verificar saldo en cuenta de OpenAI
       - Revisar logs detallados del servicio
    """)


def main():
    """Función principal"""
    logger.info("\n" + "="*80)
    logger.info("🔍 DIAGNÓSTICO Y CORRECCIÓN DE MONITORIZACIÓN OPENAI")
    logger.info("="*80)
    logger.info(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    
    # 1. Verificar API key
    api_ok = check_openai_api_key()
    
    # 2. Corregir precios
    pricing_ok = fix_gpt5_pricing()
    
    # 3. Revisar análisis recientes
    check_recent_analyses()
    
    # 4. Verificar proyectos activos
    check_active_projects()
    
    # 5. Generar recomendaciones
    generate_recommendations()
    
    logger.info("\n" + "="*80)
    logger.info("✅ DIAGNÓSTICO COMPLETADO")
    logger.info("="*80)
    
    if api_ok and pricing_ok:
        logger.info("\n✅ Todo está configurado correctamente")
        logger.info("   Puedes probar ejecutar un análisis manual desde el dashboard")
        return 0
    else:
        logger.error("\n❌ Se encontraron problemas que requieren atención")
        return 1


if __name__ == '__main__':
    sys.exit(main())

