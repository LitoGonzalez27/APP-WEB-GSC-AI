# ✅ PASO 1 COMPLETADO: Base de Datos Multi-LLM Brand Monitoring

**Fecha:** 24 de octubre de 2025  
**Estado:** ✅ COMPLETADO EXITOSAMENTE  
**Base de Datos:** PostgreSQL Staging (Railway)

---

## 📊 Resumen de Ejecución

### ✅ Tablas Creadas (7)

| # | Tabla | Descripción | Estado |
|---|-------|-------------|--------|
| 1 | `llm_monitoring_projects` | Proyectos de monitorización de marca | ✅ Creada |
| 2 | `llm_monitoring_queries` | Queries por proyecto | ✅ Creada |
| 3 | `llm_monitoring_results` | Resultados individuales por query y LLM | ✅ Creada |
| 4 | `llm_monitoring_snapshots` | Métricas agregadas diarias por LLM | ✅ Creada |
| 5 | `user_llm_api_keys` | API keys encriptadas de usuario | ✅ Creada |
| 6 | `llm_model_registry` | Registro de modelos y precios (Single Source of Truth) | ✅ Creada |
| 7 | `llm_visibility_comparison` | Vista SQL para comparativas entre LLMs | ✅ Creada |

---

## 🤖 Modelos LLM Insertados (4)

| Proveedor | Modelo | ID API | Coste Input | Coste Output | Estado |
|-----------|--------|--------|-------------|--------------|--------|
| **OpenAI** | GPT-5 | `gpt-5` | $15/1M | $45/1M | ✅ Activo |
| **Anthropic** | Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | $3/1M | $15/1M | ✅ Activo |
| **Google** | Gemini 2.0 Flash | `gemini-2.0-flash` | $0.075/1M | $0.30/1M | ✅ Activo |
| **Perplexity** | Sonar Large | `llama-3.1-sonar-large-128k-online` | $1/1M | $1/1M | ✅ Activo |

---

## 🔧 Índices Creados (10)

Índices para optimización de queries:

```sql
✅ idx_llm_proj_user             -- Búsqueda por usuario
✅ idx_llm_proj_active           -- Proyectos activos
✅ idx_llm_queries_proj          -- Queries por proyecto
✅ idx_llm_results_proj_date     -- Resultados por fecha
✅ idx_llm_results_provider      -- Resultados por proveedor
✅ idx_llm_results_mentioned     -- Filtro de menciones
✅ idx_llm_snapshots_proj_date   -- Snapshots por fecha
✅ idx_llm_snapshots_provider    -- Snapshots por proveedor
✅ idx_llm_models_provider       -- Modelos por proveedor
✅ idx_llm_models_current        -- Modelos actuales
```

---

## 📐 Estructura de Datos Principal

### 1. **llm_monitoring_projects**
```sql
- Campos clave:
  • user_id (FK a users)
  • name, brand_name, industry
  • enabled_llms (ARRAY: openai, anthropic, google, perplexity)
  • competitors (JSONB)
  • queries_per_llm (5-50)
  • is_active
```

### 2. **llm_monitoring_results**
```sql
- Almacena cada respuesta individual
- Campos: brand_mentioned, mention_count, position_in_list
- Sentimiento: sentiment, sentiment_score
- Performance: tokens_used, cost_usd, response_time_ms
- Constraint: UNIQUE por (project_id, query_id, llm_provider, date)
```

### 3. **llm_monitoring_snapshots**
```sql
- Métricas agregadas por día y LLM
- Mention rate, Share of Voice, Sentimiento promedio
- Top 3/5/10 posicionamiento
- Costes totales y tokens consumidos
```

### 4. **llm_model_registry** (Single Source of Truth)
```sql
- Todos los precios vienen de aquí (NO hardcodeados)
- Detección automática de nuevos modelos
- Estadísticas de uso agregadas
```

---

## 📊 Vista SQL: llm_visibility_comparison

Vista pivoteada que muestra:
- Mention rate por LLM (ChatGPT, Claude, Gemini, Perplexity)
- Promedios cross-LLM
- Mejor y peor LLM por menciones
- Costes totales

```sql
SELECT * FROM llm_visibility_comparison 
WHERE project_id = 1 AND snapshot_date = '2025-10-24';
```

---

## 🗂️ Archivos Creados

| Archivo | Propósito | Estado |
|---------|-----------|--------|
| `create_llm_monitoring_tables.py` | Script de setup inicial | ✅ Creado |
| `verify_llm_monitoring_setup.py` | Verificación de tablas y modelos | ✅ Creado |
| `PASO_1_COMPLETADO_LLM_MONITORING.md` | Documentación | ✅ Este archivo |

---

## ✅ Checklist del Paso 1

- [x] Script `create_llm_monitoring_tables.py` creado
- [x] Script ejecutado sin errores
- [x] 6 tablas principales creadas en PostgreSQL
- [x] 1 vista SQL creada (`llm_visibility_comparison`)
- [x] 4 modelos LLM insertados con precios actuales
- [x] 10 índices creados correctamente
- [x] Verificación completa ejecutada exitosamente

---

## 🎯 Próximos Pasos: PASO 2 - Proveedores LLM

### Estructura a Crear:
```
services/
  └── llm_providers/
      ├── __init__.py
      ├── base_provider.py          # Clase abstracta
      ├── openai_provider.py        # GPT-5
      ├── anthropic_provider.py     # Claude Sonnet 4.5
      ├── google_provider.py        # Gemini 2.0 Flash
      └── perplexity_provider.py    # Sonar Large
```

### Dependencias a Instalar:
```bash
pip install openai anthropic google-generativeai requests
```

### Funcionalidades Clave:
- ✅ Interfaz unificada para todos los LLMs
- ✅ Manejo de rate limits
- ✅ Cálculo automático de costes desde BD
- ✅ Retry con exponential backoff
- ✅ ThreadPoolExecutor para paralelización

---

## 📝 Notas Importantes

1. **Idempotencia**: El script `create_llm_monitoring_tables.py` se puede ejecutar múltiples veces sin problemas (usa `CREATE TABLE IF NOT EXISTS`)

2. **Single Source of Truth**: Todos los precios están en `llm_model_registry`. NUNCA hardcodear precios en el código.

3. **Escalabilidad**: La estructura soporta:
   - Múltiples proyectos por usuario
   - Múltiples queries por proyecto
   - Múltiples LLMs por proyecto
   - Histórico completo de resultados

4. **Performance**: Índices optimizados para:
   - Búsquedas por usuario y fecha
   - Filtros por proveedor LLM
   - Agregaciones en snapshots

---

## 🔒 Seguridad

- API keys se almacenan **encriptadas** en `user_llm_api_keys`
- Control de presupuesto mensual por usuario
- Alertas de gasto al 80% del presupuesto
- Cascade deletes para mantener integridad referencial

---

## 📊 Métricas Clave Soportadas

| Métrica | Descripción | Tabla |
|---------|-------------|-------|
| **Mention Rate** | % de queries donde se menciona la marca | snapshots |
| **Share of Voice** | % de menciones vs competidores | snapshots |
| **Sentimiento Promedio** | Positivo/Neutral/Negativo | snapshots |
| **Posicionamiento** | Top 3/5/10 en listas numeradas | results |
| **Coste por Query** | USD por query individual | results |
| **Tiempo de Respuesta** | Milisegundos por query | results |

---

**✅ PASO 1 COMPLETADO - LISTO PARA PASO 2**

