# 🔧 Verificación y Solución - Incoherencia de Rankings

## 📊 Queries de Verificación

### 1. Verificar datos en Manual AI

#### Ver dominios en tabla global_domains
```sql
SELECT 
    detected_domain,
    COUNT(DISTINCT keyword_id) as keywords_unicos,
    COUNT(*) as menciones_totales
FROM manual_ai_global_domains
WHERE project_id = <TU_PROJECT_ID>
    AND analysis_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY detected_domain
ORDER BY keywords_unicos DESC
LIMIT 10;
```

#### Ver menciones de URLs desde JSON
```sql
SELECT 
    r.id,
    r.keyword,
    jsonb_array_length(r.ai_analysis_data->'debug_info'->'references_found') as num_referencias,
    r.ai_analysis_data->'debug_info'->'references_found'
FROM manual_ai_results r
WHERE r.project_id = <TU_PROJECT_ID>
    AND r.analysis_date >= CURRENT_DATE - INTERVAL '30 days'
    AND r.has_ai_overview = true
    AND r.ai_analysis_data IS NOT NULL
ORDER BY r.analysis_date DESC
LIMIT 5;
```

#### Comparar conteos para un dominio específico
```sql
-- Método 1: Desde tabla global_domains (keywords únicos)
SELECT 
    'Tabla global_domains' as fuente,
    COUNT(DISTINCT keyword_id) as conteo,
    'keywords_unicos' as metrica
FROM manual_ai_global_domains
WHERE project_id = <TU_PROJECT_ID>
    AND detected_domain = 'eudona.com'
    AND analysis_date >= CURRENT_DATE - INTERVAL '30 days'

UNION ALL

-- Método 2: Menciones totales (simulado)
SELECT 
    'Conteo manual JSON' as fuente,
    COUNT(*) as conteo,
    'menciones_totales' as metrica
FROM manual_ai_global_domains
WHERE project_id = <TU_PROJECT_ID>
    AND detected_domain = 'eudona.com'
    AND analysis_date >= CURRENT_DATE - INTERVAL '30 days';
```

---

## 🛠️ Solución Implementada

### Opción 1: Modificar Ranking de Dominios en Manual AI

Aquí está el código corregido para `get_project_global_domains_ranking()`:

```python
@staticmethod
def get_project_global_domains_ranking(project_id: int, days: int = 30) -> List[Dict]:
    """
    Obtener ranking global de TODOS los dominios detectados en AI Overview
    MODIFICADO: Ahora cuenta MENCIONES TOTALES (igual que el ranking de URLs)
    
    Args:
        project_id: ID del proyecto
        days: Número de días hacia atrás
        
    Returns:
        Lista de dominios con ranking completo y formateado para el frontend
    """
    from urllib.parse import urlparse
    from collections import defaultdict
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Obtener proyecto para domain y competidores
    cur.execute("""
        SELECT domain, selected_competitors
        FROM manual_ai_projects
        WHERE id = %s
    """, (project_id,))
    
    project_row = cur.fetchone()
    if not project_row:
        cur.close()
        conn.close()
        return []
    
    project_domain = project_row['domain']
    competitor_domains = project_row['selected_competitors'] or []
    
    # Obtener todos los resultados con AI Overview del periodo
    cur.execute("""
        SELECT 
            r.id,
            r.keyword_id,
            r.keyword,
            r.ai_analysis_data,
            r.analysis_date
        FROM manual_ai_results r
        WHERE r.project_id = %s 
            AND r.analysis_date >= %s 
            AND r.analysis_date <= %s
            AND r.has_ai_overview = true
            AND r.ai_analysis_data IS NOT NULL
    """, (project_id, start_date, end_date))
    
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Contador de dominios: {domain: {mentions: int, positions: [], dates: set, keywords: set}}
    domain_stats = defaultdict(lambda: {
        'mentions': 0,
        'positions': [],
        'dates': set(),
        'keywords': set()
    })
    
    total_keywords_with_aio = 0
    keywords_seen = set()
    
    # Procesar cada resultado
    for row in results:
        try:
            ai_analysis = row['ai_analysis_data'] or {}
            debug_info = ai_analysis.get('debug_info', {})
            references_found = debug_info.get('references_found', [])
            
            keyword_id = row['keyword_id']
            analysis_date = str(row['analysis_date'])
            
            # Marcar keyword como analizado
            if keyword_id not in keywords_seen:
                keywords_seen.add(keyword_id)
                total_keywords_with_aio += 1
            
            # Procesar cada referencia
            for ref in references_found:
                url = ref.get('link', '').strip()
                position = ref.get('index')
                
                if url:
                    try:
                        # Extraer dominio limpio
                        parsed = urlparse(url)
                        domain = parsed.netloc.lower()
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        
                        if domain:
                            # Contar CADA mención (coherente con ranking de URLs)
                            domain_stats[domain]['mentions'] += 1
                            domain_stats[domain]['positions'].append(position + 1 if position is not None else 1)
                            domain_stats[domain]['dates'].add(analysis_date)
                            domain_stats[domain]['keywords'].add(keyword_id)
                    except:
                        continue
                        
        except Exception as e:
            logger.warning(f"Error parsing ai_analysis_data: {e}")
            continue
    
    if not domain_stats:
        return []
    
    # Transformar a lista y calcular métricas
    domains_list = []
    for domain, stats in domain_stats.items():
        avg_position = sum(stats['positions']) / len(stats['positions']) if stats['positions'] else None
        
        # Porcentaje basado en keywords únicos que mencionan este dominio
        keywords_count = len(stats['keywords'])
        visibility_pct = (keywords_count / total_keywords_with_aio * 100) if total_keywords_with_aio > 0 else 0
        
        # Determinar tipo de dominio
        domain_type = 'other'
        is_project_domain = False
        is_selected_competitor = False
        
        if project_domain and project_domain.lower() in domain:
            domain_type = 'project'
            is_project_domain = True
        elif any(comp and comp.lower() in domain for comp in competitor_domains):
            domain_type = 'competitor'
            is_selected_competitor = True
        
        domains_list.append({
            'rank': 0,  # Se asignará después de ordenar
            'detected_domain': domain,
            'domain_type': domain_type,
            'appearances': stats['mentions'],  # TOTAL DE MENCIONES (coherente con URLs)
            'days_appeared': len(stats['dates']),
            'avg_position': float(avg_position) if avg_position else None,
            'best_position': min(stats['positions']) if stats['positions'] else None,
            'worst_position': max(stats['positions']) if stats['positions'] else None,
            'total_mentions': stats['mentions'],
            'visibility_percentage': float(round(visibility_pct, 2)),
            'keywords_mentioned': keywords_count  # Añadido para referencia
        })
    
    # Ordenar por número de menciones totales (descendente)
    domains_list.sort(key=lambda x: x['appearances'], reverse=True)
    
    # Agregar rank
    for idx, domain in enumerate(domains_list, 1):
        domain['rank'] = idx
    
    return domains_list
```

---

## ✅ Ventajas de la Solución

### 1. Coherencia Total

```
Ejemplo con 1 keyword que tiene estas referencias:
- eudona.com/tratamientos/fiv
- eudona.com/blog/consejos  
- hmfertilitycenter.com/servicios

Ranking de URLs (antes y después):
✅ eudona.com/tratamientos/fiv: 1
✅ eudona.com/blog/consejos: 1
✅ hmfertilitycenter.com/servicios: 1

Ranking de Dominios:
ANTES ❌: 
- eudona.com: 1 (solo cuenta keyword único)
- hmfertilitycenter.com: 1

DESPUÉS ✅:
- eudona.com: 2 (suma ambas URLs)
- hmfertilitycenter.com: 1

SUMA DE URLs = TOTAL DEL DOMINIO ✅
```

### 2. Paridad con AI Mode

Ambos sistemas (Manual AI y AI Mode) ahora:
- ✅ Leen de JSON con referencias
- ✅ Cuentan menciones totales
- ✅ Usan la misma lógica de agregación
- ✅ Producen rankings coherentes

### 3. Métricas Adicionales

El nuevo código incluye:
- `appearances`: Menciones totales (métrica principal)
- `keywords_mentioned`: Número de keywords únicos (métrica secundaria)
- `visibility_percentage`: Basado en keywords únicos (más representativo)

---

## 🧪 Script de Verificación

Crea este script para verificar la coherencia antes y después:

```python
#!/usr/bin/env python3
"""
Script para verificar coherencia entre rankings de dominios y URLs
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from manual_ai.services.statistics_service import StatisticsService
from urllib.parse import urlparse
from collections import defaultdict

def verify_rankings_coherence(project_id: int, days: int = 30):
    """Verificar que las menciones de dominios coincidan con URLs"""
    
    print(f"🔍 Verificando coherencia para proyecto {project_id}...")
    
    # Obtener ambos rankings
    domains_ranking = StatisticsService.get_project_global_domains_ranking(project_id, days)
    urls_ranking = StatisticsService.get_project_urls_ranking(project_id, days, limit=100)
    
    # Agrupar URLs por dominio
    domain_from_urls = defaultdict(int)
    for url_data in urls_ranking:
        url = url_data['url']
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            domain_from_urls[domain] += url_data['mentions']
        except:
            continue
    
    # Comparar
    print(f"\n📊 Comparación de menciones:")
    print(f"{'Dominio':<40} {'Ranking Dominios':<20} {'Suma URLs':<20} {'¿Coherente?':<15}")
    print("-" * 95)
    
    all_domains = set(list(domain_from_urls.keys()) + [d['detected_domain'] for d in domains_ranking[:20]])
    
    incoherencias = 0
    for domain in sorted(all_domains):
        domain_count = next((d['appearances'] for d in domains_ranking if d['detected_domain'] == domain), 0)
        url_count = domain_from_urls.get(domain, 0)
        
        coherent = domain_count == url_count
        symbol = "✅" if coherent else "❌"
        
        if not coherent:
            incoherencias += 1
        
        print(f"{domain:<40} {domain_count:<20} {url_count:<20} {symbol:<15}")
    
    print("\n" + "=" * 95)
    if incoherencias == 0:
        print("✅ TODOS LOS DOMINIOS SON COHERENTES")
    else:
        print(f"❌ ENCONTRADAS {incoherencias} INCOHERENCIAS")
    
    return incoherencias == 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python verificar_coherencia_rankings.py <project_id>")
        sys.exit(1)
    
    project_id = int(sys.argv[1])
    coherent = verify_rankings_coherence(project_id)
    
    sys.exit(0 if coherent else 1)
```

---

## 🎯 Plan de Implementación

### Fase 1: Backup y Testing
1. ✅ Documentar el problema (completado)
2. ⏳ Hacer backup de la función actual
3. ⏳ Crear branch de testing
4. ⏳ Implementar nuevo código en dev

### Fase 2: Validación
5. ⏳ Ejecutar script de verificación con datos reales
6. ⏳ Comparar resultados antes/después
7. ⏳ Validar con casos de prueba conocidos

### Fase 3: Deployment
8. ⏳ Actualizar ambos sistemas (Manual AI + AI Mode)
9. ⏳ Desplegar a staging
10. ⏳ Validar en producción
11. ⏳ Monitorear métricas

### Fase 4: Documentación
12. ⏳ Actualizar documentación de usuario
13. ⏳ Comunicar cambio de métrica (si aplica)
14. ⏳ Crear guía de interpretación de rankings

---

## 📈 Cambios Esperados en los Datos

### Tu caso específico

**ANTES (con incoherencia):**
```
Ranking de Dominios:
1. (otro dominio)
2. hmfertilitycenter.com - 12 menciones
3. ...
5. ibi.es - 5 menciones
...
(eudona.com NO visible o muy abajo)

Ranking de URLs:
1. (otra URL)
2. hmfertilitycenter.com/... - 12 menciones
3. eudona.com/... - 12 menciones  ← ❌ Incoherencia
```

**DESPUÉS (coherente):**
```
Ranking de Dominios:
1. (otro dominio)
2. eudona.com - 12 menciones  ← ✅ Ahora visible
3. hmfertilitycenter.com - 12 menciones
4. ...
5. ibi.es - 5 menciones

Ranking de URLs:
1. (otra URL)
2. eudona.com/... - X menciones
3. eudona.com/... - Y menciones
   (suma X + Y = 12 total del dominio ✅)
```

---

## 🔔 Notas Importantes

1. **Los números pueden cambiar**: Dominios que aparecían con valores bajos (keywords únicos) pueden tener valores más altos (menciones totales).

2. **Orden puede cambiar**: Si un dominio tenía pocas keywords pero muchas URLs por keyword, subirá en el ranking.

3. **Es un cambio de métrica**: De "en cuántos temas aparezco" a "cuántas veces total me mencionan".

4. **Más preciso**: Refleja mejor la visibilidad real en AI Overview.

---

**Estado**: Solución documentada ✅  
**Próximo paso**: Implementar y validar 🚀

