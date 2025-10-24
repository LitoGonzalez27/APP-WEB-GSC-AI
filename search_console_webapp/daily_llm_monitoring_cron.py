#!/usr/bin/env python3
"""
Script para el cron job diario del Multi-LLM Brand Monitoring System
Este script debe ejecutarse diariamente para analizar todos los proyectos activos.

CONFIGURACIÓN CRON:
# Ejecutar todos los días a las 4:00 AM (después del AI Mode a las 3:00 AM)
0 4 * * * cd /path/to/your/app && python3 daily_llm_monitoring_cron.py >> /var/log/llm_monitoring_cron.log 2>&1

RAILWAY SETUP:
Se configura en railway.json como job separado

IMPORTANTE:
- Usa las API keys almacenadas en user_llm_api_keys (encriptadas)
- Respeta los límites de presupuesto (monthly_budget_usd)
- Envía alertas si se excede el threshold (80%)
"""

import sys
import os
import logging
from datetime import datetime
from decimal import Decimal

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('llm_monitoring_cron')


def check_budget_limits():
    """
    Verifica que no se haya excedido el presupuesto mensual
    
    Returns:
        tuple: (can_proceed: bool, budget_info: dict)
    """
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a BD para verificar presupuesto")
        return False, {}
    
    try:
        cur = conn.cursor()
        
        # Obtener usuarios con API keys y su gasto
        cur.execute("""
            SELECT 
                user_id,
                monthly_budget_usd,
                current_month_spend,
                spending_alert_threshold,
                last_spend_reset
            FROM user_llm_api_keys
            WHERE 
                (openai_api_key_encrypted IS NOT NULL OR
                 anthropic_api_key_encrypted IS NOT NULL OR
                 google_api_key_encrypted IS NOT NULL OR
                 perplexity_api_key_encrypted IS NOT NULL)
        """)
        
        users = cur.fetchall()
        
        if not users:
            logger.warning("⚠️ No hay usuarios con API keys configuradas")
            return False, {}
        
        # Verificar cada usuario
        users_over_budget = []
        users_near_limit = []
        
        for user in users:
            budget = float(user['monthly_budget_usd'] or 100.0)
            spent = float(user['current_month_spend'] or 0.0)
            threshold = float(user['spending_alert_threshold'] or 80.0)
            
            percent_spent = (spent / budget) * 100 if budget > 0 else 0
            
            if percent_spent >= 100:
                users_over_budget.append({
                    'user_id': user['user_id'],
                    'budget': budget,
                    'spent': spent,
                    'percent': percent_spent
                })
            elif percent_spent >= threshold:
                users_near_limit.append({
                    'user_id': user['user_id'],
                    'budget': budget,
                    'spent': spent,
                    'percent': percent_spent,
                    'threshold': threshold
                })
        
        budget_info = {
            'total_users': len(users),
            'users_over_budget': users_over_budget,
            'users_near_limit': users_near_limit
        }
        
        # Si hay usuarios sobre presupuesto, no continuar
        if users_over_budget:
            logger.warning(f"⚠️ {len(users_over_budget)} usuario(s) sobre presupuesto:")
            for u in users_over_budget:
                logger.warning(f"   User #{u['user_id']}: ${u['spent']:.2f} / ${u['budget']:.2f} ({u['percent']:.1f}%)")
            return False, budget_info
        
        # Si hay usuarios cerca del límite, alertar pero continuar
        if users_near_limit:
            logger.warning(f"⚠️ {len(users_near_limit)} usuario(s) cerca del límite:")
            for u in users_near_limit:
                logger.warning(f"   User #{u['user_id']}: ${u['spent']:.2f} / ${u['budget']:.2f} ({u['percent']:.1f}%)")
        
        return True, budget_info
        
    except Exception as e:
        logger.error(f"❌ Error verificando presupuesto: {e}")
        return False, {}
    finally:
        cur.close()
        conn.close()


def get_api_keys_from_db():
    """
    Obtiene API keys encriptadas de la BD y las desencripta
    
    IMPORTANTE: En producción, usar cryptography para desencriptar
    Por ahora, asumimos que hay un mecanismo de encriptación
    
    Returns:
        dict: API keys por proveedor
    """
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a BD para obtener API keys")
        return {}
    
    try:
        cur = conn.cursor()
        
        # Por ahora, obtener las keys del primer usuario activo
        # En producción, esto debería ser por usuario/proyecto
        cur.execute("""
            SELECT 
                openai_api_key_encrypted,
                anthropic_api_key_encrypted,
                google_api_key_encrypted,
                perplexity_api_key_encrypted
            FROM user_llm_api_keys
            WHERE 
                openai_api_key_encrypted IS NOT NULL OR
                anthropic_api_key_encrypted IS NOT NULL OR
                google_api_key_encrypted IS NOT NULL OR
                perplexity_api_key_encrypted IS NOT NULL
            LIMIT 1
        """)
        
        result = cur.fetchone()
        
        if not result:
            logger.error("❌ No se encontraron API keys en BD")
            return {}
        
        # TODO: Implementar desencriptación con cryptography
        # Por ahora, asumir que las keys están en variables de entorno
        api_keys = {}
        
        # Fallback a variables de entorno si no hay keys en BD
        if os.getenv('OPENAI_API_KEY'):
            api_keys['openai'] = os.getenv('OPENAI_API_KEY')
        if os.getenv('ANTHROPIC_API_KEY'):
            api_keys['anthropic'] = os.getenv('ANTHROPIC_API_KEY')
        if os.getenv('GOOGLE_API_KEY'):
            api_keys['google'] = os.getenv('GOOGLE_API_KEY')
        if os.getenv('PERPLEXITY_API_KEY'):
            api_keys['perplexity'] = os.getenv('PERPLEXITY_API_KEY')
        
        if not api_keys:
            logger.error("❌ No se encontraron API keys (ni en BD ni en env)")
            return {}
        
        logger.info(f"✅ API keys obtenidas: {list(api_keys.keys())}")
        return api_keys
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo API keys: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


def update_monthly_spend(total_cost_usd: float):
    """
    Actualiza el gasto mensual de todos los usuarios
    
    Args:
        total_cost_usd: Coste total del análisis
    """
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Actualizar gasto mensual
        # En producción, esto debería ser por usuario
        cur.execute("""
            UPDATE user_llm_api_keys
            SET 
                current_month_spend = current_month_spend + %s,
                updated_at = NOW()
            WHERE 
                openai_api_key_encrypted IS NOT NULL OR
                anthropic_api_key_encrypted IS NOT NULL OR
                google_api_key_encrypted IS NOT NULL OR
                perplexity_api_key_encrypted IS NOT NULL
        """, (total_cost_usd,))
        
        conn.commit()
        logger.info(f"💰 Gasto actualizado: +${total_cost_usd:.4f}")
        
    except Exception as e:
        logger.error(f"❌ Error actualizando gasto: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def main():
    try:
        logger.info("")
        logger.info("=" * 70)
        logger.info("🕒 === MULTI-LLM BRAND MONITORING CRON JOB STARTED ===")
        logger.info("=" * 70)
        logger.info(f"⏰ Timestamp: {datetime.now().isoformat()}")
        logger.info("")
        
        # 1. Verificar presupuesto
        logger.info("💰 Verificando límites de presupuesto...")
        can_proceed, budget_info = check_budget_limits()
        
        if not can_proceed:
            logger.error("❌ No se puede continuar: presupuesto excedido")
            logger.error("💥 LLM MONITORING CRON JOB ABORTED DUE TO BUDGET")
            sys.exit(1)
        
        logger.info(f"✅ Presupuesto OK ({budget_info['total_users']} usuario(s))")
        logger.info("")
        
        # 2. Obtener API keys
        logger.info("🔑 Obteniendo API keys...")
        api_keys = get_api_keys_from_db()
        
        if not api_keys:
            logger.error("❌ No se pudieron obtener API keys")
            logger.error("💥 LLM MONITORING CRON JOB FAILED: NO API KEYS")
            sys.exit(1)
        
        logger.info("")
        
        # 3. Importar el servicio
        logger.info("📦 Importando servicio de monitorización...")
        try:
            from services.llm_monitoring_service import analyze_all_active_projects
            logger.info("✅ Servicio importado correctamente")
        except ImportError as e:
            logger.error(f"❌ Error importando servicio: {e}")
            logger.error("Sugerencia: verifica que services/llm_monitoring_service.py exista")
            sys.exit(1)
        
        logger.info("")
        
        # 4. Ejecutar análisis de todos los proyectos
        logger.info("🚀 Iniciando análisis de todos los proyectos activos...")
        logger.info("")
        
        results = analyze_all_active_projects(
            api_keys=api_keys,
            max_workers=10
        )
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 RESULTADOS DEL ANÁLISIS")
        logger.info("=" * 70)
        
        # 5. Procesar resultados
        successful = 0
        failed = 0
        total_cost = 0.0
        total_queries = 0
        
        for result in results:
            if 'error' in result:
                failed += 1
                logger.error(f"❌ Proyecto #{result['project_id']}: {result['error']}")
            else:
                successful += 1
                total_queries += result.get('total_queries_executed', 0)
                
                # Calcular coste (aproximado, se refinará con snapshots)
                # Por ahora, asumir coste promedio por query
                queries = result.get('total_queries_executed', 0)
                # Asumiendo coste promedio de $0.002 por query (mix de LLMs)
                estimated_cost = queries * 0.002
                total_cost += estimated_cost
                
                logger.info(f"✅ Proyecto #{result['project_id']}")
                logger.info(f"   Duración: {result.get('duration_seconds', 0):.1f}s")
                logger.info(f"   Queries: {queries}")
                logger.info(f"   LLMs: {result.get('llms_analyzed', 0)}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("📈 RESUMEN FINAL")
        logger.info("=" * 70)
        logger.info(f"   Total proyectos: {len(results)}")
        logger.info(f"   ✅ Exitosos: {successful}")
        logger.info(f"   ❌ Fallidos: {failed}")
        logger.info(f"   📊 Total queries: {total_queries}")
        logger.info(f"   💰 Coste estimado: ${total_cost:.4f}")
        logger.info("=" * 70)
        logger.info("")
        
        # 6. Actualizar gasto mensual
        if total_cost > 0:
            update_monthly_spend(total_cost)
        
        # 7. Determinar exit code
        if failed > 0:
            logger.warning(f"⚠️ {failed} proyecto(s) fallaron")
            logger.warning("🔔 LLM MONITORING CRON JOB COMPLETED WITH WARNINGS")
            # Exit 0 porque algunos proyectos sí funcionaron
            sys.exit(0)
        else:
            logger.info("🎉 LLM MONITORING CRON JOB COMPLETED SUCCESSFULLY")
            sys.exit(0)
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}", exc_info=True)
        logger.error("Sugerencia: verifica que services/llm_monitoring_service.py exista")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        logger.error("💥 LLM MONITORING CRON JOB CRASHED")
        sys.exit(1)


if __name__ == "__main__":
    main()

