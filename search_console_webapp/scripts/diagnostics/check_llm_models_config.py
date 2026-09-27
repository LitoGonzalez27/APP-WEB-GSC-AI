"""
Script para verificar la configuración de modelos LLM en la base de datos
"""

import sys
from database import get_db_connection

def check_current_models():
    """
    Verifica qué modelos están configurados como 'current' para cada provider
    """
    print("\n" + "="*80)
    print("🔍 VERIFICACIÓN DE MODELOS LLM CONFIGURADOS")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Obtener todos los modelos
        cur.execute("""
            SELECT 
                llm_provider,
                model_id,
                model_display_name,
                is_current,
                is_available,
                cost_per_1m_input_tokens,
                cost_per_1m_output_tokens
            FROM llm_model_registry
            ORDER BY llm_provider, is_current DESC, model_id
        """)
        
        models = cur.fetchall()
        
        if not models:
            print("⚠️ No hay modelos configurados en la base de datos")
            return False
        
        # Agrupar por provider
        by_provider = {}
        for model in models:
            provider = model['llm_provider']
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(model)
        
        # Mostrar información
        print()
        for provider, provider_models in sorted(by_provider.items()):
            print(f"\n{'='*80}")
            print(f"📊 {provider.upper()}")
            print(f"{'='*80}")
            
            current_found = False
            for model in provider_models:
                is_current = model['is_current']
                is_available = model['is_available']
                
                if is_current:
                    current_found = True
                    status = "✅ CURRENT"
                elif is_available:
                    status = "⚪ Available"
                else:
                    status = "❌ Unavailable"
                
                print(f"\n{status}")
                print(f"   Model ID: {model['model_id']}")
                print(f"   Display Name: {model['model_display_name']}")
                print(f"   Input: ${model['cost_per_1m_input_tokens']:.2f}/1M tokens")
                print(f"   Output: ${model['cost_per_1m_output_tokens']:.2f}/1M tokens")
            
            if not current_found:
                print(f"\n⚠️  ADVERTENCIA: No hay modelo marcado como 'current' para {provider}")
        
        # Verificar providers problemáticos
        print(f"\n\n{'='*80}")
        print("🔍 VERIFICACIÓN ESPECÍFICA: OpenAI y Google")
        print(f"{'='*80}\n")
        
        for provider in ['openai', 'google']:
            cur.execute("""
                SELECT model_id, model_display_name, is_available
                FROM llm_model_registry
                WHERE llm_provider = %s AND is_current = TRUE
                LIMIT 1
            """, (provider,))
            
            current_model = cur.fetchone()
            
            if current_model:
                status = "✅" if current_model['is_available'] else "❌"
                print(f"{provider.upper()}: {status} {current_model['model_id']} ({current_model['model_display_name']})")
                
                if not current_model['is_available']:
                    print(f"   ⚠️  PROBLEMA: Modelo marcado como no disponible")
            else:
                print(f"{provider.upper()}: ❌ NO HAY MODELO CONFIGURADO COMO CURRENT")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_failed_queries(project_id=None):
    """
    Verifica si hay queries que fallaron recientemente
    """
    print(f"\n\n{'='*80}")
    print("🔍 VERIFICACIÓN DE QUERIES RECIENTES")
    print(f"{'='*80}\n")
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Obtener resultados recientes agrupados por LLM
        query = """
            SELECT 
                llm_provider,
                COUNT(*) as total_queries,
                COUNT(CASE WHEN brand_mentioned THEN 1 END) as mentions,
                MAX(created_at) as last_query
            FROM llm_monitoring_results
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """
        
        if project_id:
            query += " AND project_id = %s"
            cur.execute(query + " GROUP BY llm_provider ORDER BY llm_provider", (project_id,))
        else:
            cur.execute(query + " GROUP BY llm_provider ORDER BY llm_provider")
        
        results = cur.fetchall()
        
        if not results:
            print("⚠️ No hay queries ejecutadas en los últimos 7 días")
            return True
        
        print("Queries ejecutadas en los últimos 7 días:\n")
        for row in results:
            print(f"{row['llm_provider'].ljust(15)} {row['total_queries']} queries, {row['mentions']} menciones")
            print(f"{''.ljust(15)} Última: {row['last_query']}")
        
        # Verificar si OpenAI y Google tienen queries
        providers_with_results = {row['llm_provider'] for row in results}
        
        print(f"\n{'='*40}")
        for provider in ['openai', 'google']:
            if provider in providers_with_results:
                print(f"✅ {provider.upper()}: Tiene resultados recientes")
            else:
                print(f"❌ {provider.upper()}: NO tiene resultados recientes")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == '__main__':
    success = check_current_models()
    if success:
        check_failed_queries()
    
    sys.exit(0 if success else 1)

