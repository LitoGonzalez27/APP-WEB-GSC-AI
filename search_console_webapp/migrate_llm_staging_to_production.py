#!/usr/bin/env python3
"""
Script para migrar proyectos de LLM Monitoring de Staging a Producción
SEGURO: Solo INSERT, no modifica datos existentes
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
import json

STAGING_URL = 'postgresql://postgres:XCkoyokCzfRlyPCFNGpfIhqteibfbojQ@caboose.proxy.rlwy.net:13631/railway'
PROD_URL = 'postgresql://postgres:HklXfIBgtSUXmaKMnOmkXSyTssdNXvwS@switchyard.proxy.rlwy.net:18167/railway'


def get_staging_data():
    """Obtiene todos los datos de LLM Monitoring de staging"""
    conn = psycopg2.connect(STAGING_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    data = {}
    
    cur.execute('SELECT * FROM llm_monitoring_projects ORDER BY id')
    data['projects'] = [dict(row) for row in cur.fetchall()]
    
    cur.execute('SELECT * FROM llm_monitoring_queries ORDER BY id')
    data['queries'] = [dict(row) for row in cur.fetchall()]
    
    cur.execute('SELECT * FROM llm_monitoring_results ORDER BY id')
    data['results'] = [dict(row) for row in cur.fetchall()]
    
    cur.execute('SELECT * FROM llm_monitoring_snapshots ORDER BY id')
    data['snapshots'] = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    return data


def verify_target_user(target_user_id):
    conn = psycopg2.connect(PROD_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT id, email, role FROM users WHERE id = %s', (target_user_id,))
    user = cur.fetchone()
    conn.close()
    return user


def migrate_data(data, target_user_id, dry_run=True):
    """Migra los datos a producción"""
    
    if dry_run:
        print("\n🔍 MODO DRY-RUN - No se modificará nada")
    else:
        print("\n🚀 MODO EJECUCIÓN - Se insertarán datos en producción")
    
    conn = psycopg2.connect(PROD_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    project_id_map = {}
    query_id_map = {}
    
    try:
        # 1. Migrar proyectos
        print("\n📁 Migrando proyectos...")
        for project in data['projects']:
            old_id = project['id']
            
            cur.execute(
                'SELECT id FROM llm_monitoring_projects WHERE user_id = %s AND name = %s',
                (target_user_id, project['name'])
            )
            existing = cur.fetchone()
            
            if existing:
                print(f"  ⚠️  Proyecto '{project['name']}' ya existe (ID: {existing['id']}) - saltando")
                project_id_map[old_id] = existing['id']
                continue
            
            if not dry_run:
                # Obtener columnas dinámicamente
                cols_to_insert = [
                    'user_id', 'name', 'brand_name', 'industry', 'enabled_llms', 
                    'competitors', 'language', 'queries_per_llm', 'is_active',
                    'last_analysis_date', 'created_at', 'updated_at', 'brand_domain',
                    'brand_keywords', 'competitor_domains', 'competitor_keywords',
                    'country_code', 'selected_competitors'
                ]
                
                values = [
                    target_user_id,
                    project['name'],
                    project.get('brand_name'),
                    project.get('industry', 'General'),
                    project.get('enabled_llms'),
                    json.dumps(project.get('competitors')) if project.get('competitors') else None,
                    project.get('language', 'es'),
                    project.get('queries_per_llm', 15),
                    project.get('is_active', True),
                    project.get('last_analysis_date'),
                    project.get('created_at'),
                    project.get('updated_at'),
                    project.get('brand_domain'),
                    json.dumps(project.get('brand_keywords')) if project.get('brand_keywords') else None,
                    json.dumps(project.get('competitor_domains')) if project.get('competitor_domains') else None,
                    json.dumps(project.get('competitor_keywords')) if project.get('competitor_keywords') else None,
                    project.get('country_code', 'ES'),
                    json.dumps(project.get('selected_competitors')) if project.get('selected_competitors') else None
                ]
                
                placeholders = ', '.join(['%s'] * len(cols_to_insert))
                cols_str = ', '.join(cols_to_insert)
                
                cur.execute(f'''
                    INSERT INTO llm_monitoring_projects ({cols_str})
                    VALUES ({placeholders})
                    RETURNING id
                ''', values)
                
                new_id = cur.fetchone()['id']
                project_id_map[old_id] = new_id
                print(f"  ✅ Proyecto '{project['name']}': staging ID {old_id} → producción ID {new_id}")
            else:
                project_id_map[old_id] = f"NEW_{old_id}"
                print(f"  📋 Proyecto '{project['name']}' se insertaría (staging ID: {old_id})")
        
        # 2. Migrar queries
        print("\n📝 Migrando queries...")
        queries_migrated = 0
        for query in data['queries']:
            old_query_id = query['id']
            old_project_id = query['project_id']
            
            if old_project_id not in project_id_map:
                continue
            
            new_project_id = project_id_map[old_project_id]
            
            if not dry_run and not str(new_project_id).startswith('NEW_'):
                cur.execute('''
                    INSERT INTO llm_monitoring_queries 
                    (project_id, query_text, is_active, added_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                ''', (
                    new_project_id,
                    query.get('query_text'),
                    query.get('is_active', True),
                    query.get('added_at')
                ))
                new_query_id = cur.fetchone()['id']
                query_id_map[old_query_id] = new_query_id
                queries_migrated += 1
            else:
                query_id_map[old_query_id] = f"NEW_{old_query_id}"
                queries_migrated += 1
        
        print(f"  {'📋' if dry_run else '✅'} {queries_migrated} queries {'se insertarían' if dry_run else 'migradas'}")
        
        # 3. Migrar results
        print("\n📊 Migrando results...")
        results_migrated = 0
        batch_size = 500
        batch = []
        
        for result in data['results']:
            old_project_id = result['project_id']
            old_query_id = result.get('query_id')
            
            if old_project_id not in project_id_map:
                continue
            
            new_project_id = project_id_map[old_project_id]
            new_query_id = query_id_map.get(old_query_id) if old_query_id else None
            
            if not dry_run and not str(new_project_id).startswith('NEW_'):
                actual_query_id = new_query_id if new_query_id and not str(new_query_id).startswith('NEW_') else None
                
                batch.append((
                    new_project_id,
                    actual_query_id,
                    result.get('analysis_date'),
                    result.get('llm_provider'),
                    result.get('model_used'),
                    result.get('query_text'),
                    result.get('brand_name'),
                    result.get('brand_mentioned'),
                    result.get('mention_count'),
                    result.get('mention_contexts'),
                    result.get('appears_in_numbered_list'),
                    result.get('position_in_list'),
                    result.get('total_items_in_list'),
                    result.get('sentiment'),
                    result.get('sentiment_score'),
                    json.dumps(result.get('competitors_mentioned')) if result.get('competitors_mentioned') else None,
                    result.get('full_response'),
                    result.get('response_length'),
                    result.get('tokens_used'),
                    result.get('input_tokens'),
                    result.get('output_tokens'),
                    result.get('cost_usd'),
                    result.get('response_time_ms'),
                    result.get('created_at'),
                    json.dumps(result.get('sources')) if result.get('sources') else None,
                    result.get('has_error', False),
                    result.get('error_message'),
                    result.get('updated_at'),
                    result.get('position_source')
                ))
                
                if len(batch) >= batch_size:
                    cur.executemany('''
                        INSERT INTO llm_monitoring_results 
                        (project_id, query_id, analysis_date, llm_provider, model_used,
                         query_text, brand_name, brand_mentioned, mention_count, mention_contexts,
                         appears_in_numbered_list, position_in_list, total_items_in_list,
                         sentiment, sentiment_score, competitors_mentioned, full_response,
                         response_length, tokens_used, input_tokens, output_tokens, cost_usd,
                         response_time_ms, created_at, sources, has_error, error_message,
                         updated_at, position_source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', batch)
                    results_migrated += len(batch)
                    print(f"    → {results_migrated} results procesados...")
                    batch = []
            else:
                results_migrated += 1
        
        # Insertar el último batch
        if batch and not dry_run:
            cur.executemany('''
                INSERT INTO llm_monitoring_results 
                (project_id, query_id, analysis_date, llm_provider, model_used,
                 query_text, brand_name, brand_mentioned, mention_count, mention_contexts,
                 appears_in_numbered_list, position_in_list, total_items_in_list,
                 sentiment, sentiment_score, competitors_mentioned, full_response,
                 response_length, tokens_used, input_tokens, output_tokens, cost_usd,
                 response_time_ms, created_at, sources, has_error, error_message,
                 updated_at, position_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', batch)
            results_migrated += len(batch)
        
        print(f"  {'📋' if dry_run else '✅'} {results_migrated} results {'se insertarían' if dry_run else 'migrados'}")
        
        # 4. Migrar snapshots
        print("\n📸 Migrando snapshots...")
        snapshots_migrated = 0
        for snapshot in data['snapshots']:
            old_project_id = snapshot['project_id']
            
            if old_project_id not in project_id_map:
                continue
            
            new_project_id = project_id_map[old_project_id]
            
            if not dry_run and not str(new_project_id).startswith('NEW_'):
                cur.execute('''
                    INSERT INTO llm_monitoring_snapshots 
                    (project_id, snapshot_date, llm_provider, total_queries, total_mentions,
                     mention_rate, avg_position, appeared_in_top3, appeared_in_top5, appeared_in_top10,
                     total_competitor_mentions, share_of_voice, competitor_breakdown,
                     positive_mentions, neutral_mentions, negative_mentions, avg_sentiment_score,
                     avg_response_time_ms, total_cost_usd, total_tokens, created_at,
                     weighted_share_of_voice, weighted_competitor_breakdown)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    new_project_id,
                    snapshot.get('snapshot_date'),
                    snapshot.get('llm_provider'),
                    snapshot.get('total_queries'),
                    snapshot.get('total_mentions'),
                    snapshot.get('mention_rate'),
                    snapshot.get('avg_position'),
                    snapshot.get('appeared_in_top3'),
                    snapshot.get('appeared_in_top5'),
                    snapshot.get('appeared_in_top10'),
                    snapshot.get('total_competitor_mentions'),
                    snapshot.get('share_of_voice'),
                    json.dumps(snapshot.get('competitor_breakdown')) if snapshot.get('competitor_breakdown') else None,
                    snapshot.get('positive_mentions'),
                    snapshot.get('neutral_mentions'),
                    snapshot.get('negative_mentions'),
                    snapshot.get('avg_sentiment_score'),
                    snapshot.get('avg_response_time_ms'),
                    snapshot.get('total_cost_usd'),
                    snapshot.get('total_tokens'),
                    snapshot.get('created_at'),
                    snapshot.get('weighted_share_of_voice'),
                    json.dumps(snapshot.get('weighted_competitor_breakdown')) if snapshot.get('weighted_competitor_breakdown') else None
                ))
                snapshots_migrated += 1
            else:
                snapshots_migrated += 1
        
        print(f"  {'📋' if dry_run else '✅'} {snapshots_migrated} snapshots {'se insertarían' if dry_run else 'migrados'}")
        
        if not dry_run:
            conn.commit()
            print("\n✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        else:
            print("\n📋 FIN DEL DRY-RUN - Ejecuta con --execute para realizar la migración")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Migrar LLM Monitoring de Staging a Producción')
    parser.add_argument('--target-user-id', type=int, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        print("❌ Debes especificar --dry-run o --execute")
        return
    
    print("=" * 70)
    print("🔄 MIGRACIÓN LLM MONITORING: STAGING → PRODUCCIÓN")
    print("=" * 70)
    
    print(f"\n🔍 Verificando usuario destino (ID: {args.target_user_id})...")
    user = verify_target_user(args.target_user_id)
    if not user:
        print(f"❌ Usuario con ID {args.target_user_id} no existe en producción")
        return
    print(f"✅ Usuario encontrado: {user['email']} (role: {user.get('role', 'user')})")
    
    print("\n📥 Obteniendo datos de staging...")
    data = get_staging_data()
    print(f"   - Proyectos: {len(data['projects'])}")
    print(f"   - Queries: {len(data['queries'])}")
    print(f"   - Results: {len(data['results'])}")
    print(f"   - Snapshots: {len(data['snapshots'])}")
    
    migrate_data(data, args.target_user_id, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
