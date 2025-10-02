# 🤖 Manual AI Analysis System - Arquitectura Modular

## 📖 Descripción

Sistema refactorizado de análisis manual de AI Overview para Google Search Console. 
Migrado desde un archivo monolítico de 4,275 líneas a una arquitectura modular y escalable.

## 🏗️ Arquitectura

```
manual_ai/
├── 📋 config.py                    # Configuración y constantes
├── 📚 REFACTORING_GUIDE.md         # Guía completa de refactorización
├── 📝 README.md                    # Este archivo
├── ✅ check_refactoring_status.py  # Script de verificación de progreso
│
├── 🔧 utils/                       # Utilidades comunes
│   ├── decorators.py               # @with_backoff decorator
│   ├── validators.py               # check_manual_ai_access
│   ├── helpers.py                  # now_utc_iso, extract_domain
│   └── country_utils.py            # convert_iso_to_internal_country
│
├── 💾 models/                      # Repositorios (Capa de datos)
│   ├── project_repository.py       # CRUD de proyectos
│   ├── keyword_repository.py       # CRUD de keywords
│   ├── result_repository.py        # CRUD de resultados
│   └── event_repository.py         # CRUD de eventos
│
├── ⚙️  services/                   # Lógica de negocio
│   ├── project_service.py          # Gestión de proyectos
│   ├── analysis_service.py         # Motor de análisis AI ⏳
│   ├── statistics_service.py       # Cálculo de métricas ⏳
│   ├── competitor_service.py       # Gestión de competidores ⏳
│   ├── export_service.py           # Generación de Excel ⏳
│   └── cron_service.py             # Jobs automáticos ⏳
│
└── 🌐 routes/                      # Endpoints Flask ⏳
    ├── health.py                   # Health checks
    ├── projects.py                 # Rutas de proyectos
    ├── keywords.py                 # Rutas de keywords
    ├── analysis.py                 # Rutas de análisis
    ├── results.py                  # Rutas de resultados
    ├── competitors.py              # Rutas de competidores
    └── exports.py                  # Rutas de exportación

Legend: ✅ Completado | ⏳ Pendiente
```

## 🚀 Inicio Rápido

### Ver estado de la refactorización

```bash
python3 manual_ai/check_refactoring_status.py
```

### Importar el sistema (con compatibilidad)

```python
# Opción 1: Usar bridge de compatibilidad (recomendado durante migración)
from manual_ai_system_bridge import manual_ai_bp, run_daily_analysis_for_all_projects

# Opción 2: Usar directamente el nuevo sistema (cuando esté completo)
from manual_ai import manual_ai_bp
from manual_ai.services.cron_service import CronService
```

## 📋 Progreso Actual

**Estado:** 🚧 En Progreso (45.5% completado)

### ✅ Completado
- [x] Estructura de directorios
- [x] Configuración y constantes
- [x] Utilidades (decorators, validators, helpers)
- [x] Todos los repositorios de datos
- [x] Servicio de proyectos
- [x] Guía de refactorización completa
- [x] Script de verificación de progreso

### 🚧 En Progreso
- [ ] Servicios restantes (analysis, statistics, competitors, export, cron)
- [ ] Rutas/Endpoints
- [ ] Tests

### ⏳ Pendiente
- [ ] Integración completa en app.py
- [ ] Tests de regresión
- [ ] Documentación de API
- [ ] Deprecar manual_ai_system.py original

## 🎯 Beneficios de la Nueva Arquitectura

### 📦 Modularidad
- Archivos pequeños y enfocados (< 300 líneas)
- Responsabilidades claras (Single Responsibility Principle)
- Bajo acoplamiento entre componentes

### 🧪 Testabilidad
- Tests unitarios por componente
- Mocks sencillos de repositorios
- Coverage mejorado

### 📈 Escalabilidad
- Fácil agregar nuevos endpoints
- Fácil agregar nuevas métricas
- Servicios independientes y reutilizables

### 👥 Colaboración
- Múltiples desarrolladores sin conflictos
- Code reviews más efectivos
- Onboarding más rápido

## 🔧 Uso de Componentes

### Repositorios (Acceso a Datos)

```python
from manual_ai.models import ProjectRepository, KeywordRepository

# Obtener proyectos de un usuario
repo = ProjectRepository()
projects = repo.get_user_projects(user_id=1)

# Agregar keywords a un proyecto
keyword_repo = KeywordRepository()
count = keyword_repo.add_keywords_to_project(
    project_id=1,
    keywords_list=['keyword 1', 'keyword 2']
)
```

### Servicios (Lógica de Negocio)

```python
from manual_ai.services import ProjectService

# Crear un proyecto
service = ProjectService()
result = service.create_project(
    user_id=1,
    name='Mi Proyecto',
    description='Análisis SEO',
    domain='example.com',
    country_code='ES'
)
```

### Utilidades

```python
from manual_ai.utils import with_backoff, convert_iso_to_internal_country

# Decorador para reintentos
@with_backoff(max_attempts=3, base_delay_sec=1.0)
def risky_operation():
    # código que puede fallar
    pass

# Conversión de códigos de país
internal_code = convert_iso_to_internal_country('ES')  # 'esp'
```

## 📚 Documentación

- **[REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)** - Guía completa de refactorización
- **[../manual_ai_system_bridge.py](../manual_ai_system_bridge.py)** - Bridge de compatibilidad

## 🛠️ Desarrollo

### Agregar un nuevo endpoint

1. Crear la función en el servicio apropiado
2. Agregar la ruta en el archivo de rutas correspondiente
3. Registrar la ruta en `routes/__init__.py`
4. Crear tests

### Agregar una nueva métrica

1. Agregar consulta SQL en el repositorio apropiado
2. Agregar lógica de cálculo en `statistics_service.py`
3. Exponer vía endpoint en `routes/results.py`

## ⚠️ Notas Importantes

1. **Durante la migración**, usar `manual_ai_system_bridge.py` para mantener compatibilidad
2. **NO eliminar** `manual_ai_system.py` hasta completar la migración
3. **Crear tests** para cada componente nuevo
4. **Verificar progreso** con `check_refactoring_status.py`

## 📞 Soporte

Para dudas sobre la refactorización:
1. Consultar [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md)
2. Ejecutar `python3 manual_ai/check_refactoring_status.py` para ver estado
3. Revisar logs y errores en la aplicación

---

**Versión:** 1.0 (Refactorización en progreso)  
**Última actualización:** 2 de octubre de 2025  
**Estado:** 🚧 45.5% completado

