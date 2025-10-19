# 🔍 Análisis de Incoherencia entre Rankings de Dominios y URLs

## 📋 Problema Identificado

Has detectado discrepancias entre dos rankings:

1. **Global AI Overview Domains Ranking**: hmfertilitycenter.com (2º, 12 menciones), ibi.es (5º, 5 menciones)
2. **Top Mentioned URLs in AI Overview**: hmfertilitycenter.com (2º, 12 menciones), eudona.com (3º, 12 menciones) ⚠️

**Anomalía**: eudona.com aparece con 12 menciones en URLs pero NO está visible en el ranking de dominios.

---

## 🔎 Análisis Técnico - CAUSA RAÍZ IDENTIFICADA

### ❌ INCOHERENCIA EN MANUAL AI ANALYSIS

En el sistema **Manual AI**, existe una **inconsistencia fundamental** en cómo se cuentan las menciones:

#### 1️⃣ Ranking de Dominios (`get_project_global_domains_ranking()`)

**Archivo**: `manual_ai/services/statistics_service.py` (líneas 349-420)

**Fuente de datos**: Tabla `manual_ai_global_domains`

**Lógica de conteo**:
```sql
COUNT(DISTINCT gd.keyword_id) as keywords_mentioned
```

**Métrica**: Cuenta **KEYWORDS ÚNICOS** donde aparece el dominio.

**Constraint importante**: La tabla tiene un UNIQUE en `(project_id, keyword_id, analysis_date, detected_domain)`, por lo que cada dominio solo puede aparecer **UNA VEZ por keyword**.

---

#### 2️⃣ Ranking de URLs (`get_project_urls_ranking()`)

**Archivo**: `manual_ai/services/statistics_service.py` (líneas 472-564)

**Fuente de datos**: Campo JSON `ai_analysis_data['debug_info']['references_found']` en `manual_ai_results`

**Lógica de conteo**:
```python
for ref in references_found:
    url = ref.get('link', '').strip()
    if url:
        url_mentions[url] += 1  # Cuenta CADA mención individual
        total_mentions += 1
```

**Métrica**: Cuenta **TODAS LAS MENCIONES** de URLs, incluyendo múltiples URLs del mismo dominio en una keyword.

---

### 🎯 Por qué ocurre la incoherencia

**Ejemplo real de tu caso:**

#### Keyword: "fertilidad madrid"

**En AI Overview references:**
```json
{
  "references_found": [
    {"index": 0, "link": "https://eudona.com/tratamientos/fiv"},
    {"index": 1, "link": "https://eudona.com/blog/consejos"},
    {"index": 2, "link": "https://hmfertilitycenter.com/servicios"},
    ...
  ]
}
```

**Resultado en Rankings:**

| Sistema | Dominio | Conteo | Explicación |
|---------|---------|--------|-------------|
| **Ranking Dominios** | eudona.com | 1 | Solo cuenta 1 vez porque es 1 keyword |
| **Ranking Dominios** | hmfertilitycenter.com | 1 | Solo cuenta 1 vez porque es 1 keyword |
| **Ranking URLs** | eudona.com/tratamientos/fiv | 1 | Cuenta esta URL |
| **Ranking URLs** | eudona.com/blog/consejos | 1 | Cuenta esta URL |
| **Ranking URLs** | hmfertilitycenter.com/servicios | 1 | Cuenta esta URL |

**Si esto se repite en 12 keywords:**
- **eudona.com** puede tener 2 URLs por keyword = 24 menciones en ranking de URLs
- **hmfertilitycenter.com** tiene 1 URL por keyword = 12 menciones en ranking de URLs
- Pero en **ranking de dominios**, ambos tendrían 12 (keywords únicos)

**Sin embargo**, si eudona.com no aparece en `manual_ai_global_domains` o tiene menos keywords únicos, NO aparecerá alto en el ranking de dominios.

---

### ✅ AI MODE MONITORING - ¿Tiene el mismo problema?

**Archivo**: `ai_mode_projects/services/statistics_service.py`

#### Ranking de Dominios (líneas 372-512)

**Fuente**: `raw_ai_mode_data['references']` - Procesa en memoria

**Conteo**:
```python
for ref in references:
    link = ref.get('link', '')
    if link:
        domain = urlparse(link).netloc
        domain_stats[domain]['mentions'] += 1  # Cuenta CADA referencia
```

**Métrica**: **TOTAL DE MENCIONES** (no keywords únicos)

#### Ranking de URLs (líneas 560-652)

**Fuente**: `raw_ai_mode_data['references']` - Procesa en memoria

**Conteo**:
```python
for ref in references:
    url = ref.get('link', '')
    if url:
        url_mentions[url] += 1  # Cuenta CADA referencia
```

**Métrica**: **TOTAL DE MENCIONES**

#### ✅ Conclusión AI Mode

**AI Mode SÍ es coherente** porque:
- Ambos leen de la misma fuente (`raw_ai_mode_data['references']`)
- Ambos cuentan menciones totales (no keywords únicos)
- La suma de menciones de URLs de un dominio DEBE coincidir con las menciones del dominio

---

## 🚨 Resumen del Problema

### Manual AI Analysis ❌

| Aspecto | Ranking Dominios | Ranking URLs | ¿Coherente? |
|---------|-----------------|--------------|-------------|
| **Fuente de datos** | Tabla `manual_ai_global_domains` | JSON `ai_analysis_data` | ❌ Diferentes |
| **Métrica** | Keywords únicos | Menciones totales | ❌ Incompatibles |
| **Si un dominio tiene 3 URLs en 1 keyword** | Cuenta como 1 | Cuenta como 3 | ❌ Incoherente |

### AI Mode Monitoring ✅

| Aspecto | Ranking Dominios | Ranking URLs | ¿Coherente? |
|---------|-----------------|--------------|-------------|
| **Fuente de datos** | JSON `raw_ai_mode_data` | JSON `raw_ai_mode_data` | ✅ Idéntica |
| **Métrica** | Menciones totales | Menciones totales | ✅ Compatible |
| **Si un dominio tiene 3 URLs en 1 keyword** | Cuenta como 3 | Cuenta como 3 | ✅ Coherente |

---

## 💡 Soluciones Propuestas

### Opción 1: Modificar Ranking de Dominios (RECOMENDADA)

**Cambiar** `get_project_global_domains_ranking()` en **Manual AI** para que cuente **menciones totales** en lugar de keywords únicos.

**Ventaja**: Coherencia total con el ranking de URLs.

**Desventaja**: Cambia la métrica actual (pero es más precisa).

### Opción 2: Modificar Ranking de URLs

**Cambiar** `get_project_urls_ranking()` para que agrupe por dominio y solo cuente **keywords únicos**.

**Ventaja**: Mantiene la métrica actual de dominios.

**Desventaja**: El ranking de URLs pierde granularidad (ya no muestra URLs individuales).

### Opción 3: Unificar Fuente de Datos

**Ambos rankings** deberían leer de la misma fuente (o tabla `manual_ai_global_domains` o JSON `ai_analysis_data`).

**Ventaja**: Garantiza coherencia estructural.

**Desventaja**: Requiere más cambios en el código.

---

## 🔧 Recomendación Final

**OPCIÓN 1 + OPCIÓN 3**: 

1. **Modificar** `get_project_global_domains_ranking()` en Manual AI para que:
   - Lea directamente de `ai_analysis_data` (como AI Mode)
   - Cuente menciones totales (como el ranking de URLs)
   - Mantenga la misma lógica que AI Mode para coherencia

2. **Beneficios**:
   - ✅ Coherencia entre rankings de dominios y URLs
   - ✅ Paridad entre Manual AI y AI Mode
   - ✅ Métricas más precisas (menciones reales vs keywords únicos)
   - ✅ Una sola fuente de verdad (el JSON con referencias)

3. **Consideraciones**:
   - La tabla `manual_ai_global_domains` puede mantenerse para otras funcionalidades
   - Los números en el ranking de dominios pueden cambiar (aumentar)
   - Es necesario comunicar el cambio de métrica a los usuarios

---

## 📊 Ejemplo de Coherencia Esperada

### Datos de entrada (1 keyword)

```
Referencias en AI Overview:
1. eudona.com/tratamientos/fiv
2. eudona.com/blog/fertilidad
3. hmfertilitycenter.com/servicios
```

### Resultado esperado coherente

**Ranking de URLs:**
- eudona.com/tratamientos/fiv: 1 mención
- eudona.com/blog/fertilidad: 1 mención
- hmfertilitycenter.com/servicios: 1 mención

**Ranking de Dominios:**
- eudona.com: 2 menciones ✅ (suma de sus URLs)
- hmfertilitycenter.com: 1 mención ✅

---

## 🎯 Próximos Pasos

1. **Decidir** qué métrica prefieres:
   - Keywords únicos (actual en ranking de dominios)
   - Menciones totales (actual en ranking de URLs)

2. **Implementar** la opción elegida en ambos sistemas

3. **Validar** con datos reales de tu proyecto

4. **Documentar** el cambio de métrica si aplica

---

**Fecha de análisis**: 2025-10-16  
**Sistemas analizados**: Manual AI Analysis, AI Mode Monitoring  
**Estado**: Incoherencia identificada ✅, Solución propuesta ✅

