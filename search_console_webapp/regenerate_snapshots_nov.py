#!/usr/bin/env python3
"""
Script para regenerar snapshots de LLM Monitoring para fechas específicas.
Útil después de migraciones que afecten campos como position_in_list o position_source.

Uso:
    python regenerate_snapshots_nov.py --project-id 3 --dates 2025-11-14 2025-11-15 2025-11-16
"""

import sys
import argparse
import json
from datetime import date, datetime
from database import get_db_connection


def calculate_weighted_mentions(results, entity_key=None):
    """
    Calcula menciones ponderadas por posición.
    entity_key=None para brand, entity_key='competitor_name' para competidor.
    """
    total_weighted = 0.0
    
    for result in results:
        position = result.get('position_in_list')
        if position is None:
            continue
        
        # Calcular peso basado en posición (igual que en el servicio)
        if position <= 3:
            weight = 1.0
        elif position <= 5:
            weight = 0.7
        elif position <= 10:
            weight = 0.3
        else:
            weight = 0.1
        
        # Aplicar según entidad
        if entity_key is None:
            # Para la marca
            if result.get('brand_mentioned'):
                mention_count = result.get('mention_count', 0)
                total_weighted += mention_count * weight
        else:
            # Para un competidor
            competitors = result.get('competitors_mentioned', {})
            comp_mentions = competitors.get(entity_key, 0)
            if comp_mentions > 0:
                total_weighted += comp_mentions * weight
    
    return total_weighted


def regenerate_snapshots_for_date(project_id: int, target_date: date):
    """
    Regenera los snapshots para un proyecto y fecha específica.
    
    Args:
        project_id: ID del proyecto
        target_date: Fecha para la que regenerar snapshots
    """
    print(f"\n{'='*70}")
    print(f"🔄 Regenerando snapshots para proyecto {project_id} - {target_date}")
    print(f"{'='*70}\n")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Error: No se pudo conectar a la base de datos")
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Obtener información del proyecto (brand y competidores)
        cur.execute("""
            SELECT brand_name, brand_domain, selected_competitors
            FROM llm_monitoring_projects
            WHERE id = %s
        """, (project_id,))
        
        project = cur.fetchone()
        if not project:
            print(f"❌ Error: Proyecto {project_id} no encontrado")
            return False
        
        brand_name = project['brand_name']
        brand_domain = project['brand_domain']
        selected_competitors_raw = project.get('selected_competitors') or []
        
        # Convertir competidores a lista plana de nombres/dominios
        selected_competitors = []
        if selected_competitors_raw:
            for comp in selected_competitors_raw:
                if isinstance(comp, dict):
                    # Si es dict, extraer domain o name
                    selected_competitors.append(comp.get('domain') or comp.get('name', ''))
                elif isinstance(comp, str):
                    selected_competitors.append(comp)
        
        print(f"   📊 Proyecto: {brand_name} ({brand_domain})")
        print(f"   🎯 Competidores: {len(selected_competitors)}")
        if selected_competitors:
            print(f"       {', '.join(selected_competitors)}")
        
        # 2. Obtener todos los resultados de análisis para esa fecha
        cur.execute("""
            SELECT 
                id, project_id, query_id, analysis_date,
                llm_provider, model_used,
                query_text, brand_name,
                brand_mentioned, mention_count, mention_contexts,
                appears_in_numbered_list, position_in_list, total_items_in_list, position_source,
                sentiment, sentiment_score,
                competitors_mentioned,
                full_response, response_length,
                sources,
                tokens_used, input_tokens, output_tokens, cost_usd, response_time_ms
            FROM llm_monitoring_results
            WHERE project_id = %s 
                AND analysis_date = %s
            ORDER BY llm_provider, query_id
        """, (project_id, target_date))
        
        results = cur.fetchall()
        
        if not results:
            print(f"   ⚠️  No hay resultados para regenerar en esta fecha")
            return False
        
        print(f"   📝 Resultados encontrados: {len(results)}")
        
        # 3. Agrupar por LLM provider
        results_by_llm = {}
        for r in results:
            llm_provider = r['llm_provider']
            if llm_provider not in results_by_llm:
                results_by_llm[llm_provider] = []
            
            # Convertir a formato dict compatible con _create_snapshot
            result_dict = {
                'brand_mentioned': r['brand_mentioned'],
                'mention_count': r['mention_count'] or 0,
                'position_in_list': r['position_in_list'],
                'position_source': r['position_source'],
                'sentiment': r['sentiment'] or 'neutral',
                'sentiment_score': r['sentiment_score'] or 0.5,
                'competitors_mentioned': r['competitors_mentioned'] or {},
                'response_time_ms': r['response_time_ms'] or 0,
                'cost_usd': r['cost_usd'] or 0.0,
                'tokens_used': r['tokens_used'] or 0
            }
            results_by_llm[llm_provider].append(result_dict)
        
        print(f"   🤖 LLMs encontrados: {', '.join(results_by_llm.keys())}")
        print()
        
        # 4. Regenerar snapshots
        for llm_provider, llm_results in results_by_llm.items():
            print(f"   🔄 Regenerando snapshot para {llm_provider}...")
            print(f"      - Resultados: {len(llm_results)}")
            
            total_queries = len(llm_results)
            
            # Métricas de menciones
            mentions = [r for r in llm_results if r['brand_mentioned']]
            total_mentions = len(mentions)
            mention_rate = (total_mentions / total_queries) * 100
            
            # Posicionamiento
            positions = [r['position_in_list'] for r in llm_results if r['position_in_list'] is not None]
            avg_position = sum(positions) / len(positions) if positions else None
            
            appeared_in_top3 = sum(1 for p in positions if p <= 3)
            appeared_in_top5 = sum(1 for p in positions if p <= 5)
            appeared_in_top10 = sum(1 for p in positions if p <= 10)
            
            print(f"      - Con posición: {len(positions)}/{total_queries}")
            if avg_position:
                print(f"      - Posición media: {avg_position:.1f}")
            
            # Share of Voice (normal)
            total_brand_mentions = sum(r['mention_count'] for r in llm_results)
            total_competitor_mentions = 0
            competitor_breakdown = {}
            
            for competitor in selected_competitors:
                comp_mentions = sum(
                    r['competitors_mentioned'].get(competitor, 0)
                    for r in llm_results
                )
                competitor_breakdown[competitor] = comp_mentions
                total_competitor_mentions += comp_mentions
            
            total_all_mentions = total_brand_mentions + total_competitor_mentions
            share_of_voice = (total_brand_mentions / total_all_mentions * 100) if total_all_mentions > 0 else 0
            
            # Share of Voice PONDERADO
            weighted_brand_mentions = calculate_weighted_mentions(llm_results, entity_key=None)
            weighted_competitor_mentions = 0.0
            weighted_competitor_breakdown = {}
            
            for competitor in selected_competitors:
                comp_weighted = calculate_weighted_mentions(llm_results, entity_key=competitor)
                weighted_competitor_breakdown[competitor] = round(comp_weighted, 2)
                weighted_competitor_mentions += comp_weighted
            
            total_weighted_mentions = weighted_brand_mentions + weighted_competitor_mentions
            weighted_share_of_voice = (weighted_brand_mentions / total_weighted_mentions * 100) if total_weighted_mentions > 0 else 0
            
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
                    weighted_share_of_voice, weighted_competitor_breakdown,
                    positive_mentions, neutral_mentions, negative_mentions, avg_sentiment_score,
                    avg_response_time_ms, total_cost_usd, total_tokens
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (project_id, llm_provider, snapshot_date)
                DO UPDATE SET
                    total_queries = EXCLUDED.total_queries,
                    total_mentions = EXCLUDED.total_mentions,
                    mention_rate = EXCLUDED.mention_rate,
                    avg_position = EXCLUDED.avg_position,
                    appeared_in_top3 = EXCLUDED.appeared_in_top3,
                    appeared_in_top5 = EXCLUDED.appeared_in_top5,
                    appeared_in_top10 = EXCLUDED.appeared_in_top10,
                    share_of_voice = EXCLUDED.share_of_voice,
                    weighted_share_of_voice = EXCLUDED.weighted_share_of_voice,
                    weighted_competitor_breakdown = EXCLUDED.weighted_competitor_breakdown,
                    positive_mentions = EXCLUDED.positive_mentions,
                    neutral_mentions = EXCLUDED.neutral_mentions,
                    negative_mentions = EXCLUDED.negative_mentions,
                    avg_sentiment_score = EXCLUDED.avg_sentiment_score,
                    total_cost_usd = EXCLUDED.total_cost_usd,
                    total_tokens = EXCLUDED.total_tokens,
                    created_at = NOW()
            """, (
                project_id, target_date, llm_provider,
                total_queries, total_mentions, mention_rate,
                avg_position, appeared_in_top3, appeared_in_top5, appeared_in_top10,
                total_competitor_mentions, share_of_voice, json.dumps(competitor_breakdown),
                weighted_share_of_voice, json.dumps(weighted_competitor_breakdown),
                positive_mentions, neutral_mentions, negative_mentions, avg_sentiment_score,
                avg_response_time, total_cost, total_tokens
            ))
            
            print(f"      ✅ Snapshot regenerado (SoV: {share_of_voice:.1f}% | Weighted: {weighted_share_of_voice:.1f}%)")
        
        conn.commit()
        print(f"\n✅ Snapshots regenerados exitosamente para {target_date}")
        return True
        
    except Exception as e:
        print(f"\n❌ Error regenerando snapshots: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Regenerar snapshots de LLM Monitoring para fechas específicas'
    )
    parser.add_argument(
        '--project-id',
        type=int,
        required=True,
        help='ID del proyecto LLM'
    )
    parser.add_argument(
        '--dates',
        nargs='+',
        required=True,
        help='Fechas a regenerar (formato: YYYY-MM-DD)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🔄 REGENERACIÓN DE SNAPSHOTS - LLM MONITORING")
    print("="*70)
    print(f"Proyecto: {args.project_id}")
    print(f"Fechas: {', '.join(args.dates)}")
    print()
    
    success_count = 0
    fail_count = 0
    
    for date_str in args.dates:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            success = regenerate_snapshots_for_date(args.project_id, target_date)
            if success:
                success_count += 1
            else:
                fail_count += 1
        except ValueError as e:
            print(f"❌ Error: Fecha inválida '{date_str}'. Usar formato YYYY-MM-DD")
            fail_count += 1
    
    print("\n" + "="*70)
    print("📊 RESUMEN")
    print("="*70)
    print(f"✅ Exitosos: {success_count}")
    print(f"❌ Fallidos: {fail_count}")
    print()


if __name__ == '__main__':
    main()

