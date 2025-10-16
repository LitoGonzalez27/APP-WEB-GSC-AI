#!/usr/bin/env python3
"""
Script para verificar coherencia entre rankings de dominios y URLs
Detecta incoherencias donde dominios aparecen en URLs pero no en ranking de dominios
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from manual_ai.services.statistics_service import StatisticsService
from ai_mode_projects.services.statistics_service import StatisticsService as AIModeStatsService
from urllib.parse import urlparse
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_domain(url: str) -> str:
    """Extraer dominio limpio de una URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return None

def verify_manual_ai_coherence(project_id: int, days: int = 30):
    """Verificar coherencia en Manual AI Analysis"""
    
    print("\n" + "="*100)
    print("🔍 VERIFICANDO COHERENCIA EN MANUAL AI ANALYSIS")
    print("="*100)
    
    try:
        # Obtener ambos rankings
        logger.info(f"Obteniendo ranking de dominios...")
        domains_ranking = StatisticsService.get_project_global_domains_ranking(project_id, days)
        
        logger.info(f"Obteniendo ranking de URLs...")
        urls_ranking = StatisticsService.get_project_urls_ranking(project_id, days, limit=100)
        
        if not domains_ranking and not urls_ranking:
            print("⚠️  No hay datos disponibles para este proyecto")
            return True
        
        # Agrupar URLs por dominio
        domain_from_urls = defaultdict(lambda: {'mentions': 0, 'urls': []})
        for url_data in urls_ranking:
            url = url_data['url']
            domain = extract_domain(url)
            if domain:
                domain_from_urls[domain]['mentions'] += url_data['mentions']
                domain_from_urls[domain]['urls'].append({
                    'url': url,
                    'mentions': url_data['mentions']
                })
        
        # Crear mapa de dominios del ranking
        domain_ranking_map = {d['detected_domain']: d for d in domains_ranking}
        
        # Comparar
        print(f"\n📊 Comparación de menciones (Top 20):")
        print(f"{'Rank':<6} {'Dominio':<35} {'Ranking Dom.':<15} {'Suma URLs':<15} {'Estado':<15}")
        print("-" * 100)
        
        # Obtener todos los dominios únicos
        all_domains = set(list(domain_from_urls.keys()) + list(domain_ranking_map.keys()))
        
        # Crear lista combinada con datos
        combined_data = []
        for domain in all_domains:
            domain_count = domain_ranking_map.get(domain, {}).get('appearances', 0)
            url_count = domain_from_urls.get(domain, {}).get('mentions', 0)
            rank_in_domains = domain_ranking_map.get(domain, {}).get('rank', None)
            
            combined_data.append({
                'domain': domain,
                'rank': rank_in_domains if rank_in_domains else 999,
                'domain_count': domain_count,
                'url_count': url_count,
                'coherent': domain_count == url_count
            })
        
        # Ordenar por ranking de dominios (o por suma de URLs si no está en ranking)
        combined_data.sort(key=lambda x: (x['rank'], -x['url_count']))
        
        incoherencias = []
        dominios_faltantes = []
        
        for i, data in enumerate(combined_data[:20], 1):
            domain = data['domain']
            domain_count = data['domain_count']
            url_count = data['url_count']
            coherent = data['coherent']
            
            if coherent:
                symbol = "✅ Coherente"
            elif domain_count == 0 and url_count > 0:
                symbol = "❌ FALTANTE"
                dominios_faltantes.append({
                    'domain': domain,
                    'url_mentions': url_count,
                    'urls': domain_from_urls[domain]['urls']
                })
            else:
                symbol = "⚠️  Diferencia"
                incoherencias.append({
                    'domain': domain,
                    'domain_count': domain_count,
                    'url_count': url_count,
                    'difference': url_count - domain_count
                })
            
            rank_display = str(data['rank']) if data['rank'] != 999 else "-"
            print(f"{rank_display:<6} {domain:<35} {domain_count:<15} {url_count:<15} {symbol:<15}")
        
        # Resumen de problemas
        print("\n" + "="*100)
        
        if not incoherencias and not dominios_faltantes:
            print("✅ TODOS LOS DOMINIOS SON COHERENTES")
            return True
        else:
            print(f"❌ ENCONTRADAS INCOHERENCIAS:")
            print(f"   - Dominios con diferencias: {len(incoherencias)}")
            print(f"   - Dominios faltantes en ranking: {len(dominios_faltantes)}")
            
            if dominios_faltantes:
                print(f"\n🚨 DOMINIOS FALTANTES (aparecen en URLs pero NO en ranking de dominios):")
                print("-" * 100)
                for item in dominios_faltantes:
                    print(f"\n   Dominio: {item['domain']}")
                    print(f"   Total menciones en URLs: {item['url_mentions']}")
                    print(f"   URLs detectadas:")
                    for url_info in item['urls'][:5]:  # Mostrar máximo 5 URLs
                        print(f"      - {url_info['url']} ({url_info['mentions']} menciones)")
                    if len(item['urls']) > 5:
                        print(f"      ... y {len(item['urls']) - 5} URLs más")
            
            if incoherencias:
                print(f"\n⚠️  DIFERENCIAS EN CONTEOS:")
                print("-" * 100)
                for item in incoherencias:
                    print(f"   {item['domain']}: Ranking={item['domain_count']}, URLs={item['url_count']} (diff: {item['difference']})")
            
            return False
    
    except Exception as e:
        logger.error(f"Error verificando Manual AI: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return False

def verify_ai_mode_coherence(project_id: int, days: int = 30):
    """Verificar coherencia en AI Mode Monitoring"""
    
    print("\n" + "="*100)
    print("🔍 VERIFICANDO COHERENCIA EN AI MODE MONITORING")
    print("="*100)
    
    try:
        # Obtener ambos rankings
        logger.info(f"Obteniendo ranking de dominios...")
        domains_ranking = AIModeStatsService.get_project_global_domains_ranking(project_id, days)
        
        logger.info(f"Obteniendo ranking de URLs...")
        urls_ranking = AIModeStatsService.get_project_urls_ranking(project_id, days, limit=100)
        
        if not domains_ranking and not urls_ranking:
            print("⚠️  No hay datos disponibles para este proyecto")
            return True
        
        # Agrupar URLs por dominio
        domain_from_urls = defaultdict(int)
        for url_data in urls_ranking:
            url = url_data['url']
            domain = extract_domain(url)
            if domain:
                domain_from_urls[domain] += url_data['mentions']
        
        # Crear mapa de dominios del ranking
        domain_ranking_map = {d['detected_domain']: d for d in domains_ranking}
        
        # Comparar
        print(f"\n📊 Comparación de menciones (Top 20):")
        print(f"{'Rank':<6} {'Dominio':<35} {'Ranking Dom.':<15} {'Suma URLs':<15} {'Estado':<15}")
        print("-" * 100)
        
        # Obtener todos los dominios únicos
        all_domains = set(list(domain_from_urls.keys()) + list(domain_ranking_map.keys()))
        
        # Crear lista combinada
        combined_data = []
        for domain in all_domains:
            domain_count = domain_ranking_map.get(domain, {}).get('appearances', 0)
            url_count = domain_from_urls.get(domain, 0)
            rank_in_domains = domain_ranking_map.get(domain, {}).get('rank', None)
            
            combined_data.append({
                'domain': domain,
                'rank': rank_in_domains if rank_in_domains else 999,
                'domain_count': domain_count,
                'url_count': url_count,
                'coherent': domain_count == url_count
            })
        
        # Ordenar
        combined_data.sort(key=lambda x: (x['rank'], -x['url_count']))
        
        incoherencias = 0
        for i, data in enumerate(combined_data[:20], 1):
            domain = data['domain']
            domain_count = data['domain_count']
            url_count = data['url_count']
            coherent = data['coherent']
            
            symbol = "✅ Coherente" if coherent else "❌ Diferencia"
            if not coherent:
                incoherencias += 1
            
            rank_display = str(data['rank']) if data['rank'] != 999 else "-"
            print(f"{rank_display:<6} {domain:<35} {domain_count:<15} {url_count:<15} {symbol:<15}")
        
        print("\n" + "="*100)
        if incoherencias == 0:
            print("✅ TODOS LOS DOMINIOS SON COHERENTES")
            return True
        else:
            print(f"❌ ENCONTRADAS {incoherencias} INCOHERENCIAS")
            return False
    
    except Exception as e:
        logger.error(f"Error verificando AI Mode: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("="*100)
        print("🔍 VERIFICADOR DE COHERENCIA DE RANKINGS")
        print("="*100)
        print("\nUso: python verificar_coherencia_rankings.py <project_id> [days] [system]")
        print("\nArgumentos:")
        print("  project_id    ID del proyecto a verificar (requerido)")
        print("  days          Días hacia atrás (opcional, default: 30)")
        print("  system        Sistema a verificar: 'manual', 'ai_mode', o 'both' (opcional, default: 'both')")
        print("\nEjemplos:")
        print("  python verificar_coherencia_rankings.py 123")
        print("  python verificar_coherencia_rankings.py 123 30 manual")
        print("  python verificar_coherencia_rankings.py 123 7 both")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    system = sys.argv[3] if len(sys.argv) > 3 else 'both'
    
    print("\n" + "="*100)
    print("🔍 VERIFICADOR DE COHERENCIA DE RANKINGS")
    print("="*100)
    print(f"\nProyecto ID: {project_id}")
    print(f"Período: Últimos {days} días")
    print(f"Sistema: {system.upper()}")
    
    results = []
    
    if system in ['manual', 'both']:
        manual_coherent = verify_manual_ai_coherence(project_id, days)
        results.append(('Manual AI', manual_coherent))
    
    if system in ['ai_mode', 'both']:
        ai_mode_coherent = verify_ai_mode_coherence(project_id, days)
        results.append(('AI Mode', ai_mode_coherent))
    
    # Resumen final
    print("\n" + "="*100)
    print("📋 RESUMEN FINAL")
    print("="*100)
    for system_name, coherent in results:
        status = "✅ COHERENTE" if coherent else "❌ INCOHERENTE"
        print(f"{system_name}: {status}")
    
    all_coherent = all(r[1] for r in results)
    
    if all_coherent:
        print("\n🎉 Todos los sistemas verificados son coherentes")
        sys.exit(0)
    else:
        print("\n⚠️  Se encontraron incoherencias. Revisa los detalles arriba.")
        print("\n💡 Consulta ANALISIS_INCOHERENCIA_RANKINGS.md para más información")
        sys.exit(1)

if __name__ == "__main__":
    main()

