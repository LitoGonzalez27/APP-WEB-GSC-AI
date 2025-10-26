# 🔐 ARQUITECTURA DE API KEYS - MODELO DE NEGOCIO CORRECTO

## ✅ Modelo Implementado: API Keys Globales (Gestionadas por Ti)

### Cómo Funciona

```
Usuario paga suscripción → Accede a /llm-monitoring → 
Sistema usa TUS API keys → Usuario ve resultados
```

**Los usuarios NO necesitan**:
- ❌ Tener cuentas en OpenAI, Anthropic, Google, Perplexity
- ❌ Configurar sus propias API keys
- ❌ Preocuparse por costes de LLMs

**Tú como dueño del servicio**:
- ✅ Configuras API keys globales en Railway
- ✅ Los costes de LLMs son tu coste operativo
- ✅ Controlas el uso mediante quotas/límites
- ✅ Cobras suscripción que incluye este acceso

---

## 🎯 Beneficios de Este Modelo

### Para Usuarios
1. **Simplicidad**: Solo se registran, pagan, y usan
2. **Sin fricción**: No necesitan APIs de terceros
3. **Experiencia fluida**: Todo funciona out-of-the-box
4. **Sin preocupaciones**: No ven los costes de LLMs

### Para Ti (Dueño del Servicio)
1. **Control total**: Tú gestionas las APIs
2. **Monitoreo**: Ves todo el uso agregado
3. **Límites**: Puedes establecer quotas por plan
4. **Modelo predecible**: Costes operativos vs ingresos

---

## 📊 Modelo de Negocio Típico

### Ejemplo de Pricing

**Plan Basic** ($49/mes):
- 50 queries/mes
- 2 LLMs habilitados
- 1 proyecto

**Plan Premium** ($99/mes):
- 200 queries/mes
- 4 LLMs habilitados
- 5 proyectos

**Plan Business** ($199/mes):
- 1000 queries/mes
- 4 LLMs habilitados
- Proyectos ilimitados

### Costes Operativos (Estimación)

**Por 100 queries** (25 por LLM):
- OpenAI: ~$3.00
- Anthropic: ~$1.00
- Google: ~$0.15
- Perplexity: ~$0.50
- **Total: ~$4.65**

**Margen**:
- Plan Basic (50 queries): $49 - $2.33 = **$46.67 margen** (95%)
- Plan Premium (200 queries): $99 - $9.30 = **$89.70 margen** (90%)
- Plan Business (1000 queries): $199 - $46.50 = **$152.50 margen** (77%)

---

## 🔧 Configuración Actual (Perfecta para tu modelo)

### Variables en Railway

```bash
# API Keys Globales - Gestionadas por ti
OPENAI_API_KEY="sk-proj-gWks1Sax-Qq-Ra3OCQdFHG1oFnVPoe9f..."
ANTHROPIC_API_KEY="sk-ant-api03-p0TRRROJutRbh2PHQkBo6ea_..."
GOOGLE_API_KEY="AIzaSyCUX_AlC4aNwCU3hBFUhN2iK8X0itzSnXM"
PERPLEXITY_API_KEY="pplx-63ZFA4TLtQbO9D11nMENqaHdqCERGD1h..."

# Encriptación (para futuras features)
ENCRYPTION_KEY="lzbfGDUlihSQhDfQZ_rgjVYyZFswM_SqaUp4RN0nKpI="
```

### Flujo de Uso

```python
# El sistema automáticamente:
1. Usuario crea proyecto → OK (si tiene quota disponible)
2. Usuario ejecuta análisis → Sistema usa API keys globales
3. Sistema consume API de OpenAI, Anthropic, Google, Perplexity
4. Usuario ve resultados → No necesita configurar nada
```

---

## 💰 Control de Costes y Quotas

### Límites por Plan

Implementar en `llm_monitoring_projects`:

```python
# Verificar quota antes de análisis
def can_user_analyze(user_id):
    # Obtener plan del usuario
    user_plan = get_user_plan(user_id)  # 'basic', 'premium', 'business'
    
    # Límites por plan
    limits = {
        'basic': 50,      # 50 queries/mes
        'premium': 200,   # 200 queries/mes
        'business': 1000  # 1000 queries/mes
    }
    
    # Contar queries este mes
    queries_this_month = count_user_queries_this_month(user_id)
    
    return queries_this_month < limits[user_plan]
```

### Alertas de Presupuesto

En cada proveedor de LLM:

```python
# OpenAI Dashboard
Budget Alert: $500/mes → Email cuando llegues a $400

# Anthropic Dashboard
Budget Limit: $200/mes → Stop cuando llegue al límite

# Google Cloud
Budget Alert: $100/mes → Email + Dashboard warning
```

---

## 🗄️ Base de Datos Simplificada

### Tabla `user_llm_api_keys` (Opcional - Para Futuro)

Esta tabla **NO se usa actualmente** pero está creada por si en el futuro quieres ofrecer:

**Futuro Feature (Opcional)**:
- Plan "Enterprise Custom" donde empresas grandes pueden usar sus propias APIs
- Modo "BYOK" (Bring Your Own Key) para clientes con contratos especiales

**Actualmente**: 
- ✅ Tabla existe pero vacía
- ✅ No afecta funcionamiento
- ✅ Sistema siempre usa API keys globales

---

## 🚀 Implementación Actual

### Cómo el Sistema Obtiene las API Keys

```python
# En services/llm_providers/provider_factory.py

def create_all_providers(api_keys: Dict = None):
    """
    Si api_keys es None, usa variables de entorno (API keys globales)
    """
    if api_keys is None:
        # Usar API keys globales desde variables de entorno
        api_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'anthropic': os.getenv('ANTHROPIC_API_KEY'),
            'google': os.getenv('GOOGLE_API_KEY'),
            'perplexity': os.getenv('PERPLEXITY_API_KEY')
        }
    
    providers = {}
    for name, key in api_keys.items():
        if key:
            provider = create_provider(name, key)
            if provider and provider.test_connection():
                providers[name] = provider
    
    return providers
```

### Cómo se Usa en el Servicio

```python
# En services/llm_monitoring_service.py

class MultiLLMMonitoringService:
    def __init__(self, api_keys: Dict[str, str] = None):
        # Si no se pasan api_keys, usa las globales
        self.providers = LLMProviderFactory.create_all_providers(api_keys)
```

### Cómo se Usa en el Cron Job

```python
# En daily_llm_monitoring_cron.py

def main():
    # No pasa api_keys → usa las globales automáticamente
    service = MultiLLMMonitoringService()
    
    # Analizar todos los proyectos activos
    service.analyze_all_active_projects()
```

---

## ✅ Checklist de Configuración

### En Railway (Ya Hecho)
- [x] `OPENAI_API_KEY` configurada
- [x] `ANTHROPIC_API_KEY` configurada
- [x] `GOOGLE_API_KEY` configurada
- [x] `PERPLEXITY_API_KEY` configurada
- [x] `ENCRYPTION_KEY` configurada

### En la App (Ya Implementado)
- [x] Sistema usa API keys globales por defecto
- [x] No requiere configuración de usuario
- [x] Funciona out-of-the-box
- [x] Tabla `user_llm_api_keys` existe pero no se usa

### Control de Costes (Recomendado Implementar)
- [ ] Límites por plan de usuario
- [ ] Contador de queries por mes
- [ ] Alertas de presupuesto en dashboards de LLM
- [ ] Dashboard de costes para ti (admin)

---

## 📊 Dashboard de Admin (Recomendado)

Para que tú puedas monitorear el uso:

```sql
-- Costes totales por día
SELECT 
    analysis_date,
    SUM(total_cost) as daily_cost,
    COUNT(*) as snapshots_created
FROM llm_monitoring_snapshots
GROUP BY analysis_date
ORDER BY analysis_date DESC
LIMIT 30;

-- Uso por usuario
SELECT 
    u.email,
    u.subscription_plan,
    COUNT(r.id) as total_queries,
    SUM(s.total_cost) as total_spent
FROM users u
JOIN llm_monitoring_projects p ON u.id = p.user_id
JOIN llm_monitoring_results r ON p.id = r.project_id
LEFT JOIN llm_monitoring_snapshots s ON p.id = s.project_id
GROUP BY u.email, u.subscription_plan
ORDER BY total_spent DESC;

-- Queries por LLM (para optimizar costes)
SELECT 
    llm_provider,
    COUNT(*) as queries,
    AVG(total_cost) as avg_cost_per_snapshot
FROM llm_monitoring_snapshots
WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY llm_provider;
```

---

## 🎯 Resumen

### ✅ Configuración Actual (Correcta)

Tu sistema **YA está configurado correctamente** para tu modelo de negocio:

1. **API keys globales** en Railway
2. **Sistema las usa automáticamente**
3. **Usuarios no necesitan configurar nada**
4. **Funciona out-of-the-box**

### ❌ NO Necesitas

- ❌ Sistema de configuración de API keys por usuario
- ❌ UI para que usuarios añadan sus API keys
- ❌ Endpoints para gestionar API keys de usuarios
- ❌ Tabla `user_llm_api_keys` activa (existe pero no se usa)

### ✅ Sí Necesitas (Recomendado)

- ✅ **Control de quotas** por plan
- ✅ **Monitoreo de costes** (dashboard admin)
- ✅ **Alertas de presupuesto** en proveedores LLM
- ✅ **Límites por usuario** según su plan

---

## 🚀 Próximos Pasos

1. **Deployment actual**: Ya está perfecto, las API keys globales funcionarán
2. **Implementar quotas**: Limitar queries según plan del usuario
3. **Dashboard de costes**: Para ti (admin) monitorear uso
4. **Alertas**: Configurar en OpenAI, Anthropic, Google dashboards

---

**✅ TU MODELO DE NEGOCIO ES EL CORRECTO**

Usuarios pagan → Tú provees el servicio completo → Ellos solo usan

**Sistema ya configurado para esto** 🎉

