# 🔧 Guía de Implementación del Sistema de Retry

## 📦 Archivos Creados

1. **`services/llm_providers/retry_handler.py`** - Sistema de retry inteligente
2. **`ANALISIS_RETRY_SYSTEM.md`** - Análisis completo del problema y solución

---

## 🚀 Cómo Aplicar a Cada Provider

### **Ejemplo: OpenAI Provider**

#### **Antes (Sin Retry):**

```python
def execute_query(self, query: str) -> Dict:
    start_time = time.time()
    
    try:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": query}],
            max_tokens=2000
        )
        # ... procesar respuesta ...
    except openai.RateLimitError as e:
        logger.error(f"❌ OpenAI Rate Limit: {e}")
        return {'success': False, 'error': "Rate limit exceeded"}
```

#### **Después (Con Retry):**

```python
from .retry_handler import with_retry

@with_retry  # ✨ Agregar decorator
def execute_query(self, query: str) -> Dict:
    start_time = time.time()
    
    try:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": query}],
            max_tokens=2000
        )
        # ... procesar respuesta ...
    except openai.RateLimitError as e:
        logger.error(f"❌ OpenAI Rate Limit: {e}")
        # ✨ El decorator detectará "rate limit" y reintentar automáticamente
        return {'success': False, 'error': "Rate limit exceeded"}
```

¡Eso es TODO! El decorator hace el resto automáticamente.

---

## 📝 Pasos de Implementación

### **Fase 1: OpenAI (Prioritario)**

```bash
# 1. Aplicar retry a OpenAI
# Editar: services/llm_providers/openai_provider.py

# Línea 10: Agregar import
from .retry_handler import with_retry

# Línea 75: Agregar decorator antes de execute_query
@with_retry
def execute_query(self, query: str) -> Dict:
    # ... código existente sin cambios ...
```

### **Fase 2: Google, Anthropic, Perplexity**

Mismo proceso para cada uno:
1. Agregar import de `with_retry`
2. Agregar decorator `@with_retry` antes de `execute_query`
3. Sin cambios en el código existente

### **Fase 3: Testing**

```python
# Test local con prompt que falló:
python3 -c "
from services.llm_monitoring_service import MultiLLMMonitoringService

service = MultiLLMMonitoringService()

# Analizar proyecto HM Fertility
result = service.analyze_project(project_id=5, max_workers=10)

print('✅ Resultado:', result)
"
```

### **Fase 4: Monitoreo**

```python
# Agregar endpoint para ver métricas de retry
@app.route('/api/llm-monitoring/retry-metrics')
def get_retry_metrics():
    from services.llm_providers.retry_handler import retry_metrics
    return jsonify(retry_metrics.get_summary())
```

---

## 🎯 Configuración Óptima por Provider

### **OpenAI (GPT-5)**
- **Max Retries**: 3 (rate limits frecuentes)
- **Timeout**: 60s (respuestas largas)
- **Priority**: ALTA (más caro)

### **Google (Gemini)**
- **Max Retries**: 2 (muy estable)
- **Timeout**: 30s (muy rápido)
- **Priority**: BAJA (muy barato)

### **Anthropic (Claude Sonnet 4.5)**
- **Max Retries**: 3 (respuestas largas)
- **Timeout**: 90s (reasoning extenso)
- **Priority**: MEDIA

### **Perplexity (Sonar)**
- **Max Retries**: 2 (búsqueda en tiempo real puede tardar)
- **Timeout**: 45s
- **Priority**: MEDIA

---

## 📊 Monitoreo Post-Implementación

### **Métricas a Trackear (Primera Semana):**

```sql
-- Queries con retry exitoso
SELECT 
    llm_provider,
    COUNT(*) as total_retries,
    AVG(response_time_ms) as avg_time
FROM llm_monitoring_results
WHERE has_error = FALSE
AND created_at >= NOW() - INTERVAL '7 days'
-- Filtrar solo los que tuvieron retry (agregar campo retry_count)
GROUP BY llm_provider;

-- Tasa de fallos antes/después
SELECT 
    llm_provider,
    DATE(analysis_date) as date,
    COUNT(*) as total_queries,
    SUM(CASE WHEN has_error THEN 1 ELSE 0 END) as errors,
    ROUND(SUM(CASE WHEN has_error THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as error_rate
FROM llm_monitoring_results
WHERE analysis_date >= CURRENT_DATE - 14
GROUP BY llm_provider, DATE(analysis_date)
ORDER BY date DESC, llm_provider;
```

### **Alertas a Configurar:**

```python
# Si error rate > 5% después de retry
if error_rate > 0.05:
    send_alert("Provider X tiene alta tasa de fallos")

# Si promedio de reintentos > 1
if avg_retries > 1:
    send_alert("Provider X requiere muchos reintentos")

# Si un provider falla completamente
if provider_queries == 0:
    send_alert("Provider X no está respondiendo")
```

---

## 🔧 Troubleshooting

### **Problema: Demasiados Reintentos**

```
Síntoma: Análisis tarda mucho tiempo
Solución: Reducir max_retries o delay_initial
```

### **Problema: Sigue Fallando Después de Retry**

```
Síntoma: Error rate sigue alto
Diagnóstico: 
1. Verificar tipo de error (¿es retriable?)
2. ¿API key válida?
3. ¿Rate limits del proveedor?
4. ¿Problema de red?
```

### **Problema: Costos Muy Altos**

```
Síntoma: Costo API aumentó >20%
Solución:
1. Reducir reintentos de providers caros (OpenAI)
2. Aumentar delay entre reintentos
3. Implementar circuit breaker
```

---

## ✅ Checklist de Implementación

- [ ] Revisar `retry_handler.py`
- [ ] Aplicar `@with_retry` a OpenAI
- [ ] Aplicar `@with_retry` a Google
- [ ] Aplicar `@with_retry` a Anthropic
- [ ] Aplicar `@with_retry` a Perplexity
- [ ] Testing local con proyecto de prueba
- [ ] Deploy a staging
- [ ] Monitorear métricas 24h
- [ ] Ajustar configuración si es necesario
- [ ] Deploy a producción
- [ ] Configurar alertas
- [ ] Documentar resultados

---

## 📈 Resultados Esperados

### **Antes:**
- Error rate: 2-5%
- Datos incompletos: ~3% del tiempo
- Tickets de soporte por datos faltantes: 2-3/semana

### **Después (Estimado):**
- Error rate: 0.5-1%
- Datos incompletos: <0.5% del tiempo
- Tickets de soporte: <1/mes
- Costo adicional: $10-15/mes
- ROI: Positivo en primera semana

---

## 🎓 Buenas Prácticas

1. **No reintentar errores permanentes** (API key inválida, contenido bloqueado)
2. **Usar exponential backoff** (no sobrecargar APIs)
3. **Timeout apropiado** (60s general, ajustar por provider)
4. **Logging detallado** (para debugging)
5. **Métricas de rendimiento** (para optimización continua)

---

**Próximo Review:** 1 semana después de implementación  
**Responsable:** Equipo de Desarrollo  
**Priority:** Alta
