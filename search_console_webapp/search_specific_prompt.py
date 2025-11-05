"""
Script para buscar resultados de un prompt específico
"""

import sys
from database import get_db_connection

def search_prompt_results(search_text):
    """
    Busca resultados de un prompt que contenga el texto especificado
    """
    print("\n" + "="*80)
    print(f"🔍 BUSCANDO PROMPT: '{search_text}'")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # Buscar queries que contengan el texto
        cur.execute("""
            SELECT 
                q.id,
                q.query_text,
                q.project_id,
                p.name as project_name,
                q.language,
                q.query_type,
                q.added_at,
                q.is_active
            FROM llm_monitoring_queries q
            JOIN llm_monitoring_projects p ON q.project_id = p.id
            WHERE q.query_text ILIKE %s
            ORDER BY q.added_at DESC
            LIMIT 10
        """, (f'%{search_text}%',))
        
        queries = cur.fetchall()
        
        if not queries:
            print(f"\n❌ No se encontraron queries que contengan '{search_text}'")
            return False
        
        print(f"\n✅ Se encontraron {len(queries)} queries:\n")
        
        for query in queries:
            print(f"{'='*80}")
            print(f"Query ID: {query['id']}")
            print(f"Proyecto: {query['project_name']} (ID: {query['project_id']})")
            print(f"Texto: {query['query_text']}")
            print(f"Idioma: {query['language']}")
            print(f"Tipo: {query['query_type']}")
            print(f"Activo: {'Sí' if query['is_active'] else 'No'}")
            print(f"Agregado: {query['added_at']}")
            
            # Buscar resultados para esta query
            cur.execute("""
                SELECT 
                    llm_provider,
                    brand_mentioned,
                    position_in_list,
                    sentiment,
                    response_length,
                    analysis_date,
                    created_at,
                    LEFT(full_response, 150) as response_preview
                FROM llm_monitoring_results
                WHERE query_id = %s
                ORDER BY created_at DESC
                LIMIT 20
            """, (query['id'],))
            
            results = cur.fetchall()
            
            if results:
                print(f"\n📊 Resultados ({len(results)} encontrados):\n")
                
                # Agrupar por LLM provider
                by_provider = {}
                for result in results:
                    provider = result['llm_provider']
                    if provider not in by_provider:
                        by_provider[provider] = []
                    by_provider[provider].append(result)
                
                for provider in ['openai', 'google', 'anthropic', 'perplexity']:
                    if provider in by_provider:
                        provider_results = by_provider[provider]
                        latest = provider_results[0]  # Más reciente
                        
                        mention = "✅ Mencionado" if latest['brand_mentioned'] else "❌ No mencionado"
                        position = f"Posición {latest['position_in_list']}" if latest['position_in_list'] else "N/A"
                        sentiment = latest['sentiment'] or "neutral"
                        
                        print(f"  {provider.upper().ljust(15)} {mention}  {position}  Sentiment: {sentiment}")
                        print(f"  {''.ljust(15)} Última respuesta: {latest['created_at']}")
                        print(f"  {''.ljust(15)} Longitud: {latest['response_length']} chars")
                        if latest['response_preview']:
                            preview = latest['response_preview'].replace('\n', ' ')
                            print(f"  {''.ljust(15)} Preview: {preview}...")
                        print()
                    else:
                        print(f"  {provider.upper().ljust(15)} ❌ SIN RESULTADOS")
                        print()
            else:
                print("\n⚠️ No hay resultados para esta query aún")
            
            print()
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Buscar el prompt específico del usuario
    search_text = "alternativas a la FIV"
    
    if len(sys.argv) > 1:
        search_text = ' '.join(sys.argv[1:])
    
    success = search_prompt_results(search_text)
    sys.exit(0 if success else 1)

