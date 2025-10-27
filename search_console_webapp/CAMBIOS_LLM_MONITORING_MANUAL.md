# Cambios en LLM Monitoring: Gestión Manual de Prompts

## Resumen

Se ha modificado el sistema de **LLM Monitoring** para que funcione de manera consistente con **Manual AI** y **AI Mode**, permitiendo que los usuarios añadan y gestionen sus propios prompts/queries manualmente en lugar de generarlos automáticamente basándose en el sector.

## Cambios Realizados

### 1. Backend - Nuevos Endpoints API

Se añadieron 3 nuevos endpoints en `llm_monitoring_routes.py`:

#### `GET /api/llm-monitoring/projects/<project_id>/queries`
- Obtiene todas las queries/prompts de un proyecto
- Retorna lista de prompts con su metadata (tipo, idioma, fecha)

#### `POST /api/llm-monitoring/projects/<project_id>/queries`
- Añade queries/prompts manualmente a un proyecto
- Acepta una lista de prompts en el body
- Valida longitud mínima (10 caracteres)
- Evita duplicados
- Permite especificar idioma y tipo de query

**Body esperado:**
```json
{
    "queries": ["¿Qué es X?", "¿Cómo funciona Y?", ...],
    "language": "es" (opcional, usa el del proyecto por defecto),
    "query_type": "manual" (opcional, default: "manual")
}
```

#### `DELETE /api/llm-monitoring/projects/<project_id>/queries/<query_id>`
- Elimina una query de un proyecto (soft delete)
- Marca `is_active = FALSE`

### 2. Backend - Modificación del Endpoint de Creación de Proyectos

**Antes:**
- Al crear un proyecto, se generaban automáticamente ~15 queries basadas en templates y el sector/industria especificado
- Usaba la función `generate_queries_for_project()` del servicio

**Ahora:**
- Al crear un proyecto, NO se generan queries automáticamente
- El usuario debe añadir sus propios prompts manualmente después de crear el proyecto
- Esto es consistente con Manual AI y AI Mode

**Respuesta actualizada:**
```json
{
    "success": true,
    "message": "Proyecto creado exitosamente. Ahora añade tus prompts manualmente.",
    "project": {
        "id": 1,
        "name": "Mi Proyecto",
        "total_queries": 0  // Sin queries todavía
    }
}
```

### 3. Frontend - Nueva Sección de Gestión de Prompts

Se añadió una sección completa para gestionar prompts en la vista de proyecto:

**Elementos añadidos en `llm_monitoring.html`:**

1. **Botón "Manage Prompts"** en el header de métricas
   - Hace scroll hasta la sección de prompts

2. **Card de Prompts Management**
   - Muestra contador de prompts totales
   - Lista de prompts con metadata (tipo, idioma, fecha)
   - Botón para añadir nuevos prompts
   - Botón de eliminación por prompt

3. **Modal "Add Prompts"**
   - Textarea para añadir múltiples prompts (uno por línea)
   - Selector de idioma (usa el del proyecto por defecto)
   - Selector de tipo de query (manual, general, with_brand, with_competitor)
   - Validación de longitud mínima (10 caracteres)

### 4. Frontend - JavaScript

Se añadieron las siguientes funciones en `llm_monitoring.js`:

#### Gestión de Prompts
- `loadPrompts(projectId)` - Carga y renderiza la lista de prompts
- `showPromptsModal()` - Muestra el modal para añadir prompts
- `hidePromptsModal()` - Oculta el modal
- `savePrompts()` - Guarda los prompts añadidos
- `deletePrompt(queryId)` - Elimina un prompt (con confirmación)
- `scrollToPrompts()` - Scroll automático a la sección de prompts

#### Integración
- Los prompts se cargan automáticamente al ver un proyecto
- El contador se actualiza en tiempo real
- Estados de carga y vacío bien definidos

### 5. Estilos CSS

Se añadieron estilos en `llm-monitoring.css`:

**Nuevos componentes:**
- `.prompts-list-container` - Contenedor de la lista
- `.prompt-item` - Card de cada prompt
- `.prompt-content` - Contenido del prompt
- `.prompt-meta` - Metadata (badges, fecha)
- `.badge-*` - Badges de colores por tipo
- `.btn-icon` - Botón de eliminar con hover en rojo

**Responsive:**
- Adaptación mobile de la lista de prompts
- Stack vertical en pantallas pequeñas

## Flujo de Usuario

### Antes (Generación Automática)
1. Usuario crea proyecto con nombre, marca, sector
2. Sistema genera automáticamente 15 queries basadas en templates
3. Usuario no tiene control sobre las queries generadas
4. Poco flexible

### Ahora (Gestión Manual)
1. Usuario crea proyecto con nombre, marca, sector
2. Usuario añade manualmente los prompts que desea analizar
3. Usuario puede añadir tantos prompts como quiera
4. Usuario puede eliminar prompts en cualquier momento
5. Total control y flexibilidad

## Consistencia con Otros Módulos

Este cambio hace que LLM Monitoring funcione de manera **consistente** con:

### Manual AI Analysis
- ✅ Usuario añade keywords manualmente
- ✅ Tabla `manual_ai_keywords` con soft delete
- ✅ Endpoints GET/POST/DELETE para keywords
- ✅ UI similar con lista + modal

### AI Mode Analysis
- ✅ Usuario añade keywords manualmente
- ✅ Gestión completa de keywords por proyecto
- ✅ Análisis basado en las keywords que el usuario especifica

### LLM Monitoring (Ahora)
- ✅ Usuario añade prompts manualmente
- ✅ Tabla `llm_monitoring_queries` con soft delete
- ✅ Endpoints GET/POST/DELETE para queries
- ✅ UI similar con lista + modal

## Migración de Proyectos Existentes

**Importante:** Los proyectos existentes que tenían queries generadas automáticamente:
- **Mantendrán sus queries existentes** (no se borran)
- Esas queries seguirán funcionando normalmente
- Los usuarios pueden eliminar las que no quieran
- Los usuarios pueden añadir nuevas queries manualmente

## Base de Datos

No se requieren cambios en la estructura de la base de datos:
- La tabla `llm_monitoring_queries` ya existía
- Ya tiene el campo `is_active` para soft delete
- Ya tiene los campos necesarios (query_text, language, query_type)

## Funcionalidad de Generación Automática

La función `generate_queries_for_project()` en `services/llm_monitoring_service.py`:
- **NO se ha eliminado**
- Sigue disponible si se necesita en el futuro
- Ya no se llama automáticamente al crear proyectos
- Podría usarse para features futuras (ej: "Suggest prompts" button)

## Testing Recomendado

1. ✅ Crear nuevo proyecto → verificar que NO genera queries automáticamente
2. ✅ Añadir prompts manualmente → verificar que se guardan correctamente
3. ✅ Ver lista de prompts → verificar que se cargan correctamente
4. ✅ Eliminar prompt → verificar soft delete
5. ✅ Analizar proyecto con prompts manuales → verificar que funciona
6. ✅ Proyectos existentes → verificar que mantienen sus queries

## Archivos Modificados

### Backend
- `llm_monitoring_routes.py` - 3 nuevos endpoints + modificación de create_project
- Líneas añadidas: ~200

### Frontend HTML
- `templates/llm_monitoring.html` - Nueva sección de prompts + modal
- Líneas añadidas: ~80

### Frontend JavaScript
- `static/js/llm_monitoring.js` - 6 nuevas funciones
- Líneas añadidas: ~270

### CSS
- `static/llm-monitoring.css` - Estilos para prompts management
- Líneas añadidas: ~180

## Próximos Pasos Sugeridos

1. **Sugerencias de Prompts (Opcional)**
   - Botón "Suggest Prompts" que use `generate_queries_for_project()`
   - Usuario puede revisar y seleccionar los que quiera añadir

2. **Importación Masiva**
   - Permitir importar prompts desde CSV/Excel
   - Similar a Manual AI

3. **Categorización**
   - Tags personalizados para organizar prompts
   - Filtros en la lista

4. **Análisis Parcial**
   - Permitir seleccionar qué prompts analizar
   - Checkbox por prompt

## Notas Importantes

- ⚠️ **No se requiere migración de datos**
- ✅ **Retrocompatible con proyectos existentes**
- ✅ **No rompe funcionalidad existente**
- ✅ **Mejora la experiencia de usuario**
- ✅ **Consistente con otros módulos del sistema**

---

**Fecha:** 27 de Octubre, 2025  
**Autor:** Sistema de actualización automática  
**Versión:** 1.0

