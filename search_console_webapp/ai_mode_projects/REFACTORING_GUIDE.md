# 📚 Guía de Refactorización - Sistema Manual AI

## 🎯 Objetivo
Refactorizar `manual_ai_system.py` (4,275 líneas) en una arquitectura modular y escalable sin romper funcionalidad existente.

## 📊 Análisis del Sistema Original

### Archivo Monolítico: `manual_ai_system.py`
- **4,275 líneas** de código
- **30+ rutas** Flask (endpoints API)
- **60+ funciones** mezclando responsabilidades
- Generación de Excel embebida
- Jobs cron para análisis automático
- Gestión de competidores y dominios globales

### Problemas Identificados
1. ❌ **Violación del principio de responsabilidad única (SRP)**
2. ❌ **Difícil mantenimiento y testing**
3. ❌ **Alto acoplamiento** entre componentes
4. ❌ **Baja reutilización** de código
5. ❌ **Dificultad para escalar** nuevas funcionalidades

## 🏗️ Nueva Arquitectura Modular

```
manual_ai/
├── __init__.py                 # Punto de entrada del módulo
├── config.py                   # Configuración y constantes
├── REFACTORING_GUIDE.md        # Este archivo
│
├── utils/                      # Utilidades comunes
│   ├── __init__.py
│   ├── decorators.py          # @with_backoff
│   ├── validators.py          # check_manual_ai_access
│   ├── helpers.py             # now_utc_iso, extract_domain
│   └── country_utils.py       # convert_iso_to_internal_country
│
├── models/                     # Capa de datos (Repositorios)
│   ├── __init__.py
│   ├── project_repository.py  # CRUD de proyectos
│   ├── keyword_repository.py  # CRUD de keywords
│   ├── result_repository.py   # CRUD de resultados
│   └── event_repository.py    # CRUD de eventos
│
├── services/                   # Lógica de negocio
│   ├── __init__.py
│   ├── project_service.py     # Lógica de proyectos
│   ├── analysis_service.py    # Motor de análisis AI
│   ├── statistics_service.py  # Cálculo de métricas
│   ├── competitor_service.py  # Gestión de competidores
│   ├── export_service.py      # Generación de Excel
│   └── cron_service.py        # Jobs automáticos
│
└── routes/                     # Endpoints Flask
    ├── __init__.py
    ├── health.py              # Health checks
    ├── projects.py            # Rutas de proyectos
    ├── keywords.py            # Rutas de keywords
    ├── analysis.py            # Rutas de análisis
    ├── results.py             # Rutas de resultados
    ├── competitors.py         # Rutas de competidores
    └── exports.py             # Rutas de exportación
```

## ✅ Progreso de Refactorización

### ✓ Completado
- [x] Estructura de directorios
- [x] `config.py` - Constantes y configuración
- [x] `utils/` - Todas las utilidades comunes
- [x] `models/` - Todos los repositorios de datos

### 🚧 En Progreso
- [ ] `services/` - Servicios de lógica de negocio
- [ ] `routes/` - Endpoints Flask

### ⏳ Pendiente
- [ ] Migración del código restante
- [ ] Tests de integración
- [ ] Actualización de imports en `app.py`

## 📋 Plan de Migración (Paso a Paso)

### FASE 1: Servicios ✅ (Actual)

#### 1.1 Crear `services/analysis_service.py`
**Contenido a migrar:**
- `run_project_analysis()` - Motor principal de análisis
- Lógica de análisis de keywords con SERP
- Integración con cache AI
- Manejo de cuotas
- Almacenamiento de resultados

**Funciones origen (líneas aproximadas en original):**
- `run_project_analysis` (líneas 1622-1929)
- Lógica de análisis con backoff
- Integración con `detect_ai_overview_elements`
- Integración con `store_global_domains_detected`

#### 1.2 Crear `services/statistics_service.py`
**Contenido a migrar:**
- `get_project_statistics()` - Cálculo de métricas
- `get_project_ai_overview_keywords()` - Tabla de keywords con AI
- `get_project_ai_overview_keywords_latest()` - Último análisis
- `get_project_top_domains()` - Top dominios
- `get_project_global_domains_ranking()` - Ranking global
- `get_project_competitors_charts_data()` - Gráficas de competidores
- `get_project_comparative_charts_data()` - Gráficas comparativas

**Funciones origen:**
- `get_project_statistics` (líneas 2332-2446)
- `get_project_ai_overview_keywords` (líneas 3617-3718)
- `get_project_ai_overview_keywords_latest` (líneas 3719-3797)
- `get_project_top_domains` (líneas 2446-2551)
- `get_project_global_domains_ranking` (líneas 3283-3437)
- `get_project_competitors_charts_data` (líneas 2683-3002)
- `get_project_comparative_charts_data` (líneas 3027-3282)

#### 1.3 Crear `services/competitor_service.py`
**Contenido a migrar:**
- Validación y normalización de competidores
- `sync_historical_competitor_flags()` - Sincronización histórica
- `get_competitors_for_date_range()` - Competidores en rango de fechas
- Detección de cambios en competidores

**Funciones origen:**
- `sync_historical_competitor_flags` (líneas 3551-3616)
- `get_competitors_for_date_range` (líneas 2552-2682)

#### 1.4 Crear `services/export_service.py`
**Contenido a migrar:**
- `generate_manual_ai_excel()` - Generación de Excel
- `create_summary_sheet()` - Hoja de resumen
- `create_domain_visibility_sheet()` - Hoja de visibilidad
- `create_competitive_analysis_sheet()` - Hoja de análisis competitivo
- `create_keywords_details_sheet()` - Hoja de detalles de keywords
- `create_global_domains_sheet()` - Hoja de dominios globales

**Funciones origen:**
- `generate_manual_ai_excel` (líneas 3824-3906)
- `create_summary_sheet` (líneas 3907-3944)
- `create_domain_visibility_sheet` (líneas 3945-4007)
- `create_competitive_analysis_sheet` (líneas 4008-4132)
- `create_keywords_details_sheet` (líneas 4133-4218)
- `create_global_domains_sheet` (líneas 4219-4267)

#### 1.5 Crear `services/cron_service.py`
**Contenido a migrar:**
- `run_daily_analysis_for_all_projects()` - Análisis diario automático
- Lógica de locks concurrentes
- Procesamiento por lotes
- Manejo de errores y reintentos

**Funciones origen:**
- `run_daily_analysis_for_all_projects` (líneas 1934-2176)
- `store_global_domains_detected` (líneas 3438-3537)
- `create_daily_snapshot` (líneas 2236-2279)

### FASE 2: Rutas (Endpoints)

#### 2.1 Crear `routes/__init__.py`
Registrar todas las rutas en el blueprint

#### 2.2 Crear `routes/health.py`
**Rutas a migrar:**
- `GET /api/health` - Health check

#### 2.3 Crear `routes/projects.py`
**Rutas a migrar:**
- `GET /` - Dashboard
- `GET /api/projects` - Listar proyectos
- `POST /api/projects` - Crear proyecto
- `GET /api/projects/<id>` - Detalles proyecto
- `PUT /api/projects/<id>` - Actualizar proyecto
- `DELETE /api/projects/<id>` - Eliminar proyecto

#### 2.4 Crear `routes/keywords.py`
**Rutas a migrar:**
- `GET /api/projects/<id>/keywords` - Listar keywords
- `POST /api/projects/<id>/keywords` - Agregar keywords
- `PUT /api/projects/<id>/keywords/<kid>` - Actualizar keyword
- `DELETE /api/projects/<id>/keywords/<kid>` - Eliminar keyword

#### 2.5 Crear `routes/analysis.py`
**Rutas a migrar:**
- `POST /api/projects/<id>/analyze` - Ejecutar análisis
- `POST /api/cron/daily-analysis` - Trigger cron

#### 2.6 Crear `routes/results.py`
**Rutas a migrar:**
- `GET /api/projects/<id>/results` - Obtener resultados
- `GET /api/projects/<id>/stats` - Estadísticas
- `GET /api/projects/<id>/stats-latest` - Estadísticas últimas
- `GET /api/projects/<id>/ai-overview-table` - Tabla AI Overview
- `GET /api/projects/<id>/ai-overview-table-latest` - Tabla última
- `GET /api/projects/<id>/top-domains` - Top dominios
- `GET /api/projects/<id>/global-domains-ranking` - Ranking global
- `GET /api/projects/<id>/competitors-charts` - Gráficas competidores
- `GET /api/projects/<id>/comparative-charts` - Gráficas comparativas

#### 2.7 Crear `routes/competitors.py`
**Rutas a migrar:**
- `GET /api/projects/<id>/competitors` - Obtener competidores
- `PUT /api/projects/<id>/competitors` - Actualizar competidores

#### 2.8 Crear `routes/exports.py`
**Rutas a migrar:**
- `POST /api/projects/<id>/download-excel` - Descargar Excel
- `GET /api/projects/<id>/export` - Exportar datos

#### 2.9 Crear `routes/annotations.py` (nuevo archivo)
**Rutas a migrar:**
- `POST /api/annotations` - Crear anotación
- `POST /api/projects/<id>/notes` - Agregar nota

### FASE 3: Integración

#### 3.1 Actualizar `app.py`
**Cambiar:**
```python
# Antes
from manual_ai_system import manual_ai_bp

# Después
from manual_ai import manual_ai_bp
```

#### 3.2 Verificar imports en otros archivos
- `daily_analysis_cron.py`
- Cualquier script que importe del sistema Manual AI

### FASE 4: Testing y Validación

#### 4.1 Tests unitarios por módulo
- Crear tests para cada repositorio
- Crear tests para cada servicio
- Crear tests para cada ruta

#### 4.2 Tests de integración
- Verificar flujo completo de análisis
- Verificar generación de Excel
- Verificar cron jobs

#### 4.3 Tests de regresión
- Comparar resultados antes/después
- Verificar que no hay funcionalidad rota

## 🔧 Comandos Útiles

### Verificar imports rotos
```bash
python -m py_compile manual_ai/*.py manual_ai/**/*.py
```

### Ejecutar tests
```bash
pytest manual_ai/tests/
```

### Verificar linters
```bash
flake8 manual_ai/
pylint manual_ai/
```

## ⚠️ Precauciones

1. **NO eliminar** `manual_ai_system.py` hasta que todo esté migrado y probado
2. **Crear tests** para cada módulo antes de migrar
3. **Migrar gradualmente** - un módulo a la vez
4. **Mantener compatibilidad** con código existente durante la transición
5. **Documentar cambios** en cada commit

## 📝 Checklist Final

- [ ] Todos los servicios creados y probados
- [ ] Todas las rutas migradas y probadas
- [ ] `app.py` actualizado
- [ ] Tests de integración pasando
- [ ] Documentación actualizada
- [ ] `manual_ai_system.py` marcado como deprecated
- [ ] Desplegar en staging
- [ ] Validar en producción
- [ ] Eliminar `manual_ai_system.py`

## 🎓 Beneficios de la Nueva Arquitectura

### Mantenibilidad
- ✅ Archivos pequeños y enfocados (< 300 líneas)
- ✅ Responsabilidades claras y separadas
- ✅ Fácil de entender y modificar

### Escalabilidad
- ✅ Fácil agregar nuevos endpoints
- ✅ Fácil agregar nuevas métricas
- ✅ Servicios independientes y reutilizables

### Testing
- ✅ Tests unitarios por componente
- ✅ Mocks sencillos de repositorios
- ✅ Coverage mejorado

### Colaboración
- ✅ Múltiples desarrolladores sin conflictos
- ✅ Code reviews más efectivos
- ✅ Onboarding más rápido

## 📚 Recursos Adicionales

- [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Flask Application Factory Pattern](https://flask.palletsprojects.com/en/2.3.x/patterns/appfactories/)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Service Layer Pattern](https://martinfowler.com/eaaCatalog/serviceLayer.html)

---

**Última actualización:** 2 de octubre de 2025
**Autor:** Refactorización Sistema Manual AI
**Estado:** 🚧 En Progreso - Fase 1 (Modelos completados)

