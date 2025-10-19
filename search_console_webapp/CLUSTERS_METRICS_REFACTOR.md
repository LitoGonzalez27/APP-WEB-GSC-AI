# Refactorización de Métricas de Clusters - AI Mode Projects

**Fecha:** 17 de octubre, 2025
**Objetivo:** Usar total de keywords como métrica base y eliminar referencias a AI Overview en el bloque de clusters

## 📋 Resumen de Cambios

### Métrica Base Nueva
- **Antes:** Keywords with AI Overview (barras) vs Keywords with Brand Mentions (línea)
- **Ahora:** Total Keywords (barras) vs Brand Mentions (línea)

### ✅ Cambios Implementados

#### 1. Backend - `ai_mode_projects/services/cluster_service.py`
- ✅ Eliminadas todas las referencias a `ai_overview_count` y `ai_overview_percentage`
- ✅ Modificado `chart_data` para usar `total_keywords` en lugar de `ai_overview`
- ✅ Ordenamiento descendente por `total_keywords` (no por nombre)
- ✅ Validación: `brand_mentions` nunca puede superar `total_keywords` (con warning en logs)
- ✅ Consolidación de duplicados por nombre de cluster (case-insensitive)
- ✅ Cálculo de `data_freshness` (timestamp del análisis más reciente)
- ✅ Estructura de retorno actualizada:
  ```python
  {
      'chart_data': {
          'labels': [...],
          'total_keywords': [...],  # Nueva
          'mentions': [...]
      },
      'table_data': [
          {
              'cluster_name': str,
              'total_keywords': int,
              'mentions_count': int,
              'mentions_percentage': float  # Redondeado a 1 decimal
          }
      ],
      'data_freshness': str  # ISO format
  }
  ```

#### 2. Frontend - `static/js/ai-mode-projects/ai-mode-clusters.js`

##### Gráfica (`renderClustersChart`)
- ✅ Cambio de dataset: `'Total Keywords'` (barras) en lugar de `'Keywords with AI Overview'`
- ✅ Uso de `chartData.total_keywords` en lugar de `chartData.ai_overview`
- ✅ Tooltips mejorados con formato especificado:
  - Título: Nombre del cluster
  - Total Keywords: [valor]
  - Brand Mentions: [valor]
  - % Mentions: [valor con 1 decimal]%

##### Tabla (`renderClustersTable`)
- ✅ Cambio de formato: tabla **normal** (no transpuesta)
- ✅ Estructura exacta: 4 columnas
  1. **Cluster** (texto, alineado izquierda)
  2. **Total Keywords** (número, alineado centro)
  3. **Brand Mentions** (número, alineado centro)
  4. **% Mentions** (porcentaje con 1 decimal, alineado centro)
- ✅ Filtro de búsqueda por cluster (input de texto)
- ✅ Aviso de "Data stale" cuando análisis > 24 horas
- ✅ Mensaje "No clusters match your search" cuando filtro no encuentra resultados

#### 3. Exportación - `ai_mode_projects/services/export_service.py`

##### Hoja "Thematic Clusters Summary"
- ✅ Eliminadas métricas: `'AI Overview'` y `'% AI Overview'`
- ✅ Métricas finales:
  1. Total Keywords
  2. Brand Mentions
  3. % Mentions

##### Hoja "Clusters Keywords Detail"
- ✅ Eliminada columna `'Has AI Overview'`
- ✅ Query SQL actualizada (eliminado `has_ai_overview`)
- ✅ Columnas finales:
  1. Cluster
  2. Keyword
  3. Brand Mentioned
  4. Last Analysis

#### 4. Template HTML - `templates/ai_mode_dashboard.html`
- ✅ Título de gráfica: `"Keywords & Brand Mentions by Cluster"`
- ✅ Comentario de tabla actualizado

## 🎯 Validaciones Implementadas

1. **Brand mentions ≤ Total keywords**: Si se detecta inconsistencia, se registra warning y se usa el total como límite
2. **Consolidación de duplicados**: Clusters con mismo nombre (case-insensitive) se consolidan automáticamente
3. **Data freshness**: Se calcula y retorna el timestamp del análisis más reciente
4. **Aviso visual**: Si datos > 24h, se muestra warning en UI

## 📊 Fórmula de % Mentions

```
% Mentions = (brand_mentions / total_keywords) * 100

Si total_keywords = 0 → % Mentions = 0.0%
Redondeo: 1 decimal
```

## 🔍 Orden Por Defecto

**Descendente por total_keywords** (mayor a menor)
- Excepción: Cluster "Unclassified" siempre va al final

## 🧪 Testing

No hay tests unitarios en el directorio `ai_mode_projects/tests/`.

## 📝 Criterios de Aceptación (DoD)

- ✅ La gráfica solo muestra total keywords (barras) y brand mentions (línea)
- ✅ La tabla solo tiene 4 columnas exactas indicadas
- ✅ No queda ninguna referencia a AI Overview en este bloque
- ✅ % redondeado a 1 decimal
- ✅ Tooltips correctos con formato especificado
- ✅ Orden descendente por total keywords funcional
- ✅ Filtro/búsqueda por cluster funcional
- ✅ Validaciones implementadas (brand mentions ≤ total, consolidación duplicados, data stale)

## 🚀 Archivos Modificados

1. `ai_mode_projects/services/cluster_service.py` - Backend principal
2. `static/js/ai-mode-projects/ai-mode-clusters.js` - Frontend (gráfica y tabla)
3. `ai_mode_projects/services/export_service.py` - Exportación Excel
4. `templates/ai_mode_dashboard.html` - Template HTML

## 📌 Notas Importantes

- El campo `data_freshness` se calcula en el backend y se pasa al frontend para validación de datos desactualizados
- El filtro de búsqueda es case-insensitive
- La consolidación de duplicados es case-insensitive pero preserva el primer nombre encontrado
- Los tooltips de la gráfica muestran automáticamente el % de menciones calculado dinámicamente

