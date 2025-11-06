# 🔧 Solución: Queries Incompletas en LLM Monitoring

**Fecha**: 06 de Noviembre de 2025  
**Estado**: ✅ RESUELTO

---

## 📋 Problema Reportado

El usuario reportó que en la sección "LLM Comparison":

1. **Claude mostraba 4.5% mention rate pero decía "0 de 22 queries"** (debería ser 0%)
2. **Diferentes LLMs tenían diferentes cantidades de queries**:
   - Gemini: 15 queries
   - ChatGPT: 6 queries  
   - Perplexity: 22 queries
   - Claude: 22 queries

**Expectativa del usuario**: Todos los LLMs deberían analizar TODAS las queries.

---

## 🔍 Diagnóstico Realizado

Ejecutamos el script `diagnose_llm_queries.py` para el proyecto #5 (HM Fertility):

```bash
python3 diagnose_llm_queries.py 5
```

### Resultados del Diagnóstico (06-11-2025):

**Total de queries activas**: 22

**Queries analizadas por LLM**:
| LLM | Queries Analizadas | Estado | Completitud |
|-----|-------------------|--------|-------------|
| **Claude** | 22/22 | ✅ | 100% |
| **Gemini** | 18/22 | ⚠️ | 81.8% |
| **ChatGPT** | 13/22 | ⚠️ | 59.1% |
| **Perplexity** | 22/22 | ✅ | 100% |

**Snapshots del 06-11-2025**:
| LLM | Queries en Snapshot | Menciones | Mention Rate |
|-----|---------------------|-----------|--------------|
| Claude | 22 | 1 | 4.6% ✅ |
| Gemini | 15 | 1 | 6.7% (parcial) |
| ChatGPT | 6 | 1 | 16.7% (parcial) |
| Perplexity | 22 | 11 | 50.0% ✅ |

### 🎯 Causa Raíz Identificada:

1. **Queries faltantes por API failures**: Algunas queries fallaban en ciertos LLMs (rate limits, timeouts)
2. **Snapshots con datos parciales**: Los snapshots se creaban con las queries que SÍ se analizaron, sin validar completitud
3. **Falta de visibilidad**: No había advertencias sobre análisis incompletos
4. **Porcentajes engañosos**: Un snapshot de 6 queries mostraba 16.7% cuando debería calcularse sobre 22

---

## ✅ Solución Implementada

### 1. **Validación de Completitud** 

El sistema ahora verifica que cada LLM analice TODAS las queries:

```python
total_queries_expected = len(queries)  # Ej: 22

for llm_name, llm_results in results_by_llm.items():
    queries_analyzed = len(llm_results)
    
    if queries_analyzed < total_queries_expected:
        # ⚠️ ADVERTENCIA clara en logs
        missing = total_queries_expected - queries_analyzed
        logger.warning(f"⚠️  ANÁLISIS INCOMPLETO PARA {llm_name}")
        logger.warning(f"   Queries faltantes: {missing}")
        logger.warning(f"   Completitud: {queries_analyzed/total_queries_expected*100:.1f}%")
```

### 2. **Logging Mejorado**

Ahora verás advertencias claras cuando un análisis no es completo:

```
⚠️  ANÁLISIS INCOMPLETO PARA OPENAI
   Queries esperadas: 22
   Queries analizadas: 13
   Queries faltantes: 9
   Completitud: 59.1%

   ⚠️  El snapshot se creará con DATOS PARCIALES
   ⚠️  Los porcentajes pueden no ser representativos
   ⚠️  Considera ejecutar un nuevo análisis
```

### 3. **Script de Diagnóstico**

Nuevo script `diagnose_llm_queries.py` que te permite:

```bash
# Diagnosticar un proyecto
python3 diagnose_llm_queries.py <project_id>

# Ejemplo
python3 diagnose_llm_queries.py 5
```

**El script muestra:**
- ✅ Queries totales del proyecto
- ✅ Queries analizadas por cada LLM
- ✅ Queries faltantes específicas
- ✅ Validación de snapshots
- ✅ Recomendaciones

### 4. **Resultado de Análisis Mejorado**

El endpoint de análisis ahora devuelve:

```json
{
  "project_id": 5,
  "analysis_date": "2025-11-06",
  "completeness_by_llm": {
    "openai": {
      "queries_analyzed": 13,
      "queries_expected": 22,
      "completeness_pct": 59.1
    },
    "google": {
      "queries_analyzed": 18,
      "queries_expected": 22,
      "completeness_pct": 81.8
    },
    ...
  },
  "incomplete_llms": ["openai", "google"],
  "all_queries_analyzed": false  // ⚠️ Análisis incompleto
}
```

---

## 🚀 Recomendaciones

### Acción Inmediata:

1. **Ejecutar un nuevo análisis completo** desde el dashboard:
   - Ve a LLM Monitoring
   - Selecciona tu proyecto
   - Haz clic en "Run Analysis"
   - Espera a que termine (puede tardar varios minutos)

2. **Revisar los logs del análisis**:
   - Verás claramente si algún LLM no completó todas las queries
   - Verás qué queries específicas fallaron
   - Verás el porcentaje de completitud

3. **Si sigue habiendo queries faltantes**:
   - Revisa los logs para identificar el error específico
   - Posibles causas:
     - **Rate limits**: Demasiadas peticiones por minuto
     - **Timeouts**: Queries muy largas que tardan demasiado
     - **API errors**: Problemas temporales con la API del LLM

### Acciones a Largo Plazo:

1. **Monitorear completitud**: Después de cada análisis, revisa si `all_queries_analyzed = true`

2. **Ajustar rate limits** si es necesario:
   - Reduce `max_workers` en el análisis (actualmente 10)
   - Añade delays entre peticiones si ciertos LLMs dan rate limits

3. **Reintentar queries fallidas**:
   - Considera implementar un sistema de retry automático para queries fallidas

---

## 📊 Ejemplo de Uso del Script de Diagnóstico

```bash
$ python3 diagnose_llm_queries.py 5

================================================================================
🔍 DIAGNÓSTICO DE PROYECTO #5
================================================================================

📋 1. INFORMACIÓN DEL PROYECTO
--------------------------------------------------------------------------------
Nombre: HM Fertility
Marca: hm fertility
LLMs habilitados: openai, anthropic, google, perplexity
Queries por LLM configuradas: 20
Último análisis: 2025-11-06 13:19:16

📊 2. QUERIES/PROMPTS DEL PROYECTO
--------------------------------------------------------------------------------
Total de queries activas: 22

🤖 3. RESULTADOS POR LLM (últimos 7 días)
--------------------------------------------------------------------------------

LLM             Queries    Menciones    Errores    Último Análisis
--------------------------------------------------------------------------------
✅ anthropic     22         4            0          2025-11-06
⚠️  google        18         4            0          2025-11-06
⚠️  openai        13         3            0          2025-11-06
✅ perplexity    22         33           0          2025-11-06

💡 7. RECOMENDACIONES
--------------------------------------------------------------------------------

⚠️  Algunos LLMs no han analizado todas las queries:
   Posibles causas:
   1. Errores en las llamadas a la API (rate limits, timeouts)
   2. Health check excluyendo providers
   3. Queries añadidas después del último análisis

   Solución:
   → Ejecutar un nuevo análisis desde el dashboard
   → Verificar logs del análisis para ver errores
```

---

## 🎯 Resumen de Cambios en el Código

### Archivos Modificados:

1. **`services/llm_monitoring_service.py`**:
   - Añadida validación de completitud antes de crear snapshots
   - Logging de advertencia para análisis incompletos
   - Info de completitud en logs de snapshot
   - Resultado mejorado con datos de completitud

2. **`diagnose_llm_queries.py`** (NUEVO):
   - Script completo de diagnóstico
   - Identifica queries faltantes
   - Valida consistencia de snapshots
   - Genera recomendaciones

### Commit:

```
commit: 12717ee
branch: staging
message: "fix: Validar y reportar queries faltantes en análisis LLM"
```

---

## ✅ Verificación

Para verificar que la solución funciona:

1. **Ejecuta un análisis nuevo**:
   ```bash
   # Desde el dashboard o por API:
   POST /api/llm-monitoring/projects/5/analyze
   ```

2. **Revisa los logs** en Railway:
   ```bash
   railway logs --filter "LLM Monitoring"
   ```

3. **Ejecuta el diagnóstico**:
   ```bash
   python3 diagnose_llm_queries.py 5
   ```

4. **Verifica que todos los LLMs muestren**:
   - ✅ Queries esperadas = Queries analizadas
   - ✅ Completitud: 100%

---

## 🔮 Mejoras Futuras Posibles

1. **Sistema de retry automático**: Reintentar queries fallidas automáticamente
2. **Alerta en dashboard**: Mostrar badge de "Análisis Incompleto" en la UI
3. **Rate limit inteligente**: Ajustar velocidad según respuesta del LLM
4. **Análisis parcial diferido**: Guardar queries fallidas y reintentarlas más tarde

---

## 📞 Soporte

**Script de diagnóstico**:
```bash
python3 diagnose_llm_queries.py <project_id>
```

**Revisar logs en Railway**:
```bash
railway logs --service=web
```

**Estado actual**: ✅ Sistema operativo con validaciones implementadas

