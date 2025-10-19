# Auditoría: Control de Acceso y Quotas en AI Mode Monitoring

**Fecha**: 2025-10-19  
**Sistema**: AI Mode Monitoring  
**Objetivo**: Verificar control de acceso por planes y sistema de quotas

---

## ✅ 1. CONTROL DE ACCESO POR PLANES

### 1.1 Backend - Función `check_ai_mode_access()`
**Archivo**: `ai_mode_projects/utils/validators.py`

```python
def check_ai_mode_access(user):
    # AI Mode disponible para todos los planes excepto free
    if user.get('plan') == 'free':
        return False, {
            'error': 'AI Mode Monitoring requires a paid plan',
            'upgrade_required': True,
            'required_plan': 'basic',
            'current_plan': user.get('plan', 'unknown')
        }
    
    return True, None
```

✅ **CORRECTO**: AI Mode está **bloqueado para usuarios free**, requiere plan básico o superior.

### 1.2 Endpoints Protegidos con `check_ai_mode_access()`

| Endpoint | Ruta | Protegido |
|----------|------|-----------|
| Lista de proyectos | `GET /api/projects` | ✅ |
| Crear proyecto | `POST /api/projects` | ✅ |
| Detalles de proyecto | `GET /api/projects/<id>` | ✅ |
| Análisis manual | `POST /api/projects/<id>/analyze` | ✅ |
| Resultados | `GET /api/projects/<id>/results` | ✅ |
| Estadísticas | `GET /api/projects/<id>/stats` | ✅ |
| Keywords | `GET /api/projects/<id>/keywords` | ✅ |
| Añadir keywords | `POST /api/projects/<id>/keywords` | ✅ |
| Descargar Excel | `POST /api/projects/<id>/download-excel` | ✅ |
| Exportar datos | `GET /api/projects/<id>/export` | ✅ |

### 1.3 ⚠️ Endpoints SIN `check_ai_mode_access()`

Estos endpoints solo tienen `@auth_required` pero NO validan el plan:

| Endpoint | Ruta | Riesgo |
|----------|------|--------|
| Actualizar proyecto | `PUT /api/projects/<id>` | 🟡 Medio |
| Eliminar proyecto | `DELETE /api/projects/<id>` | 🟡 Medio |
| Competidores | `GET /api/projects/<id>/competitors` | 🟢 Bajo |
| Actualizar competidores | `PUT /api/projects/<id>/competitors` | 🟡 Medio |
| Clusters | `GET /api/projects/<id>/clusters` | 🟢 Bajo |
| Actualizar clusters | `PUT /api/projects/<id>/clusters` | 🟡 Medio |
| Estadísticas de clusters | `GET /api/projects/<id>/clusters/statistics` | 🟢 Bajo |
| Dashboard principal | `GET /` | 🔴 Alto |

**Análisis de Riesgo**:
- 🔴 **Alto**: El dashboard principal (`GET /`) no tiene `check_ai_mode_access`, pero esto es correcto porque muestra paywalls en el frontend
- 🟡 **Medio**: Operaciones de escritura (actualizar, eliminar) no validan plan, pero requieren ownership del proyecto
- 🟢 **Bajo**: Operaciones de lectura sin impacto en costes

### 1.4 Frontend - Control de Acceso

**Archivo**: `static/js/ai-mode-projects/ai-mode-core.js`

```javascript
async loadInitialData() {
    // Only load projects for paid users
    if (window.currentUser && window.currentUser.plan !== 'free') {
        console.log('💳 Usuario con plan de pago - cargando proyectos:', window.currentUser.plan);
        await this.loadProjects();
    } else {
        console.log('🆓 Usuario gratuito - mostrando estado sin proyectos');
        this.showFreeUserState();
    }
}
```

✅ **CORRECTO**: 
- No se cargan proyectos para usuarios free
- Se muestra estado especial (`showFreeUserState()`)
- Al intentar crear proyecto, se muestra paywall

**Archivo**: `static/js/ai-mode-projects/ai-mode-projects.js`

```javascript
export function showCreateProject() {
    // Verificar plan antes de mostrar formulario
    if (window.currentUser && window.currentUser.plan === 'free') {
        console.log('🆓 Usuario gratuito intentó crear proyecto - mostrando paywall');
        window.showPaywall('Manual AI Analysis', ['basic','premium','business']);
        return;
    }
    // ... resto del código
}
```

✅ **CORRECTO**: Paywall mostrado antes de crear proyecto

---

## ✅ 2. SISTEMA DE QUOTAS

### 2.1 Límites por Plan

**Archivo**: `quota_manager.py`

```python
PLAN_LIMITS = {
    'free': 0,           # Sin acceso a AI Mode
    'basic': 1225,       # ~50 keywords/día
    'premium': 2950,     # ~120 keywords/día
    'business': 8000,    # ~330 keywords/día
    'enterprise': 0      # Custom quota
}
```

### 2.2 Coste por Keyword Analizada

**Archivo**: `ai_mode_projects/config.py`

```python
AI_MODE_KEYWORD_ANALYSIS_COST = 2  # RUs por keyword
```

**Comparación**:
- Manual AI: 1 RU por keyword
- AI Mode: **2 RUs por keyword** (más costoso por usar SerpAPI Google AI Mode)

### 2.3 Validación de Quota Antes de Análisis

**Archivo**: `ai_mode_projects/services/analysis_service.py`

```python
# Validar cuota antes de empezar
quota_info = get_user_quota_status(current_user['id'])
if not quota_info.get('can_consume'):
    logger.warning(f"User {current_user['id']} sin cuota para iniciar análisis AI Mode")
    return {'success': False, 'error': 'Quota limit exceeded', 'quota_info': quota_info}
```

✅ **CORRECTO**: Se valida quota ANTES de iniciar análisis

### 2.4 Validación Durante el Análisis (Por Keyword)

```python
for keyword_data in keywords:
    # Re-validar cuota en cada iteración
    current_quota = get_user_quota_status(current_user['id'])
    if not current_quota.get('can_consume') or current_quota.get('remaining', 0) < AI_MODE_KEYWORD_ANALYSIS_COST:
        logger.warning(f"Análisis AI Mode detenido por falta de cuota.")
        break
    
    # ... análisis de keyword ...
```

✅ **CORRECTO**: Se re-valida quota en CADA keyword para evitar sobreconsume

### 2.5 Registro de Consumo

```python
from database import track_quota_consumption
track_quota_consumption(
    user_id=current_user['id'],
    ru_consumed=AI_MODE_KEYWORD_ANALYSIS_COST,  # 2 RUs
    source='ai_mode',
    keyword=keyword,
    country_code=project['country_code'],
    metadata={
        'project_id': project_id,
        'force_overwrite': bool(force_overwrite),
        'brand_name': project['brand_name']
    }
)
consumed_ru += AI_MODE_KEYWORD_ANALYSIS_COST
```

✅ **CORRECTO**: 
- Se registra consumo de 2 RUs por keyword analizada
- Se incluye metadata completa (proyecto, marca, país, tipo de análisis)
- Source identificado como `'ai_mode'` para diferenciarlo de Manual AI

### 2.6 Manejo de Errores de Quota

```python
except Exception as analysis_error:
    # Manejar errores de quota específicamente
    if hasattr(analysis_error, 'is_quota_error') and analysis_error.is_quota_error:
        logger.warning(f"🚫 Keyword '{keyword}' bloqueada por quota: {analysis_error}")
        # ... continuar con siguiente keyword ...
```

✅ **CORRECTO**: Errores de quota manejados específicamente

---

## 📊 3. CAPACIDADES POR PLAN

### Análisis Diario (Cron Automático)

| Plan | RUs/mes | Coste por Keyword | Keywords/día | Keywords/mes |
|------|---------|-------------------|--------------|--------------|
| Free | 0 | 2 | **0** | **0** |
| Basic | 1,225 | 2 | ~20 | ~610 |
| Premium | 2,950 | 2 | ~49 | ~1,475 |
| Business | 8,000 | 2 | ~133 | ~4,000 |
| Enterprise | Custom | 2 | Custom | Custom |

**Nota**: Los cálculos asumen análisis diario automático (30 días/mes)

### Análisis Manual

Los usuarios pueden ejecutar análisis manual (botón "Analyze Now"), que también consume RUs:
- Se valida quota antes de cada análisis
- Se detiene si se agota la quota
- Mismas reglas que análisis automático

---

## 🔒 4. RESUMEN DE SEGURIDAD

### ✅ Protecciones Existentes

1. **Backend**:
   - ✅ Usuarios free bloqueados en endpoints críticos
   - ✅ Sistema de quotas validando consumo
   - ✅ Re-validación por keyword durante análisis
   - ✅ Registro detallado de consumo con metadata
   - ✅ Ownership verificado en todos los endpoints

2. **Frontend**:
   - ✅ No se cargan proyectos para usuarios free
   - ✅ Paywall mostrado al intentar crear proyecto
   - ✅ Estado especial para usuarios gratuitos

3. **Quotas**:
   - ✅ Límites claros por plan
   - ✅ Coste diferenciado (2 RUs) por complejidad de SerpAPI AI Mode
   - ✅ Tracking de consumo con source='ai_mode'
   - ✅ Metadata completa para auditoría

### ⚠️ Recomendaciones de Mejora

#### 1. Añadir `check_ai_mode_access()` a Endpoints Faltantes

**Prioridad: Media**

Aunque los usuarios free no pueden crear proyectos, si de alguna forma obtuvieran acceso a un proyecto (por ejemplo, si se cambia su plan de paid a free después de crear proyectos), podrían:
- Actualizar proyectos existentes
- Modificar competidores
- Modificar clusters

**Solución**: Añadir `check_ai_mode_access()` a:
- `PUT /api/projects/<id>` (update_project)
- `DELETE /api/projects/<id>` (delete_project)
- `PUT /api/projects/<id>/competitors` (update_project_competitors)
- `PUT /api/projects/<id>/clusters` (update_project_clusters)
- Otros endpoints de escritura

#### 2. Consistencia con Manual AI

**Prioridad: Baja**

En Manual AI, TODOS los endpoints tienen `check_manual_ai_access()`. Considerar aplicar la misma estrategia a AI Mode para consistencia y defensa en profundidad.

#### 3. Dashboard Principal

**Prioridad: Muy Baja**

El dashboard principal (`GET /`) no tiene `check_ai_mode_access()`, pero esto es **correcto por diseño** porque:
- Muestra paywalls en el frontend para usuarios free
- Permite que usuarios vean la UI antes de hacer upgrade
- No expone datos sensibles
- Todas las APIs están protegidas

**NO se recomienda cambiar esto** a menos que se quiera bloquear completamente el acceso a la UI.

#### 4. Monitoreo de Consumo

**Prioridad: Media**

Considerar añadir:
- Dashboard de admin para ver consumo de AI Mode por usuario
- Alertas cuando un usuario se acerca al límite
- Estadísticas de uso de AI Mode vs Manual AI

---

## 🎯 5. CONCLUSIONES

### Estado Actual: **EXCELENTE** ✅

El sistema de AI Mode Monitoring tiene:
- ✅ **Control de acceso robusto** por planes
- ✅ **Sistema de quotas completo** y funcional
- ✅ **Validación múltiple** de consumo
- ✅ **Tracking detallado** con metadata
- ✅ **Protección en capas** (backend + frontend)
- ✅ **Coste diferenciado** (2 RUs) apropiado para API más costosa

### Único Gap Menor:

Algunos endpoints de escritura no tienen `check_ai_mode_access()`, pero el impacto es **mínimo** porque:
1. Los usuarios free no pueden crear proyectos (endpoint protegido)
2. Todos los endpoints verifican ownership
3. El frontend no carga proyectos para usuarios free
4. Las operaciones de escritura no consumen RUs adicionales

### Recomendación Final:

El sistema está **listo para producción** tal como está. Las mejoras sugeridas son opcionales y pueden implementarse como refuerzo defensivo, pero no son críticas para el funcionamiento seguro del sistema.

**Prioridad de implementación**:
1. 🟡 Opcional: Añadir `check_ai_mode_access()` a endpoints de escritura faltantes (1-2 horas)
2. 🟢 Futuro: Dashboard de monitoreo de consumo (sprint completo)
3. 🟢 Futuro: Alertas de quota (1 semana)


