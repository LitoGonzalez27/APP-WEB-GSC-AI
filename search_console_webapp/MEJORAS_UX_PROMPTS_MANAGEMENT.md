# Mejoras de UX en Prompts Management

## Objetivo
Mejorar la experiencia de usuario en la sección de gestión de prompts, haciéndola más compacta, navegable y user-friendly.

## Cambios Implementados

### 1. Toggle/Acordeón para la Sección de Prompts
- **Problema**: La sección de prompts ocupaba mucho espacio visual, especialmente cuando había muchos prompts.
- **Solución**: Implementado un sistema de toggle/acordeón que permite colapsar y expandir la sección.
- **Implementación**:
  - Añadido icono de chevron (▼/▶) en el header de la sección
  - Click en el header colapsa/expande el contenido
  - Animación suave de transición
  - Por defecto, la sección se muestra expandida

**Características**:
- Icono dinámico: `fa-chevron-down` (expandido) → `fa-chevron-right` (colapsado)
- Los botones de acción permanecen visibles incluso cuando la sección está colapsada
- Cursor pointer en el header para indicar que es clickable

### 2. Paginación de Prompts
- **Problema**: Con muchos prompts, el scroll era muy largo y difícil de navegar.
- **Solución**: Sistema de paginación que muestra 10 prompts por página.
- **Implementación**:
  - Controles de navegación: Anterior/Siguiente
  - Información de página actual y total de páginas
  - Contador de prompts mostrados (ej: "Showing 1-10 of 45 prompts")
  - Botones deshabilitados en primera/última página

**Características**:
- 10 prompts por página (configurable en `promptsPerPage`)
- Controles de navegación intuitivos con iconos
- Información clara sobre la posición actual
- Paginación solo se muestra si hay más de 10 prompts
- Diseño responsive

## Archivos Modificados

### 1. `templates/llm_monitoring.html`
**Cambios**:
- Envuelto el contenido de prompts en `<div class="prompts-content" id="promptsContent">`
- Añadido icono de toggle en el header: `<i class="fas fa-chevron-down" id="promptsToggleIcon">`
- Añadido `onclick="window.llmMonitoring.togglePromptsSection()"` al header
- Añadido `onclick="event.stopPropagation()"` a los botones de acción para evitar toggle accidental
- Añadido HTML de paginación: `<div class="prompts-pagination" id="promptsPagination">`

**Estructura de Paginación**:
```html
<div class="prompts-pagination" id="promptsPagination">
    <div class="pagination-info">
        <span id="paginationInfo">Showing 1-10 of 0 prompts</span>
    </div>
    <div class="pagination-controls">
        <button class="btn btn-icon btn-sm" id="btnPrevPage">
            <i class="fas fa-chevron-left"></i>
        </button>
        <span class="pagination-current">
            Page <span id="currentPage">1</span> of <span id="totalPages">1</span>
        </span>
        <button class="btn btn-icon btn-sm" id="btnNextPage">
            <i class="fas fa-chevron-right"></i>
        </button>
    </div>
</div>
```

### 2. `static/js/llm_monitoring.js`
**Cambios**:

#### Constructor
Añadidas propiedades para gestionar estado:
```javascript
// Pagination state
this.promptsPerPage = 10;
this.currentPromptsPage = 1;
this.allPrompts = [];
this.promptsSectionCollapsed = false;
```

#### Función `loadPrompts(projectId)`
Modificada para almacenar prompts y delegar renderizado:
- Guarda prompts en `this.allPrompts`
- Resetea `this.currentPromptsPage = 1`
- Llama a `this.renderPrompts()` en vez de renderizar directamente

#### Nueva Función: `renderPrompts()`
Renderiza solo los prompts de la página actual:
- Calcula paginación: `startIndex`, `endIndex`, `pagePrompts`
- Renderiza prompts con `slice(startIndex, endIndex)`
- Actualiza controles de paginación
- Muestra/oculta paginación según cantidad de prompts
- Maneja estado vacío

#### Nueva Función: `nextPage()`
Navega a la página siguiente:
- Verifica que no esté en la última página
- Incrementa `this.currentPromptsPage`
- Re-renderiza con `this.renderPrompts()`

#### Nueva Función: `prevPage()`
Navega a la página anterior:
- Verifica que no esté en la primera página
- Decrementa `this.currentPromptsPage`
- Re-renderiza con `this.renderPrompts()`

#### Nueva Función: `togglePromptsSection()`
Colapsa/expande la sección de prompts:
- Alterna `this.promptsSectionCollapsed`
- Cambia `display: none/block` del contenido
- Cambia icono entre `fa-chevron-down` y `fa-chevron-right`

### 3. `static/llm-monitoring.css`
**Nuevos Estilos**:

#### Toggle Icon
```css
#promptsToggleIcon {
    margin-right: 0.5rem;
    font-size: 0.875rem;
    color: #6b7280;
    transition: transform 0.3s ease;
}

.prompts-content {
    transition: all 0.3s ease;
    overflow: hidden;
}
```

#### Paginación
```css
.prompts-pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-top: 1px solid #e5e7eb;
    background: #f9fafb;
    border-radius: 0 0 0.5rem 0.5rem;
}

.pagination-info {
    font-size: 0.875rem;
    color: #6b7280;
}

.pagination-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.pagination-current {
    font-size: 0.875rem;
    color: #374151;
    font-weight: 500;
}

.pagination-controls .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background-color: #e5e7eb;
    color: #9ca3af;
}

.pagination-controls .btn:not(:disabled):hover {
    background-color: #3b82f6;
    color: white;
}
```

#### Responsive
```css
@media (max-width: 768px) {
    .prompts-pagination {
        flex-direction: column;
        gap: 0.75rem;
    }
    
    .pagination-info {
        text-align: center;
    }
}
```

## Flujo de Usuario

### Toggle de Sección
1. Usuario hace click en el header de "Prompts Management"
2. La sección se colapsa/expande con animación
3. El icono cambia para indicar el estado
4. Los botones de acción siguen siendo accesibles

### Navegación con Paginación
1. Usuario ve los primeros 10 prompts
2. Click en "Next" → muestra prompts 11-20
3. Click en "Previous" → vuelve a prompts 1-10
4. El botón "Previous" está deshabilitado en la primera página
5. El botón "Next" está deshabilitado en la última página

## Beneficios

### UX Mejorada
- **Menos Scroll**: Solo se muestran 10 prompts a la vez
- **Espacio Optimizado**: La sección se puede colapsar cuando no se necesita
- **Navegación Intuitiva**: Controles claros y familiares
- **Feedback Visual**: Iconos y estados indican la posición actual

### Performance
- **Renderizado Eficiente**: Solo se renderizan los prompts de la página actual
- **DOM Ligero**: Menos elementos en el DOM mejora el rendimiento

### Escalabilidad
- **Maneja Muchos Prompts**: Funciona bien con 10, 100 o 1000 prompts
- **Configurable**: `promptsPerPage` se puede ajustar fácilmente

## Casos de Uso

### Proyecto con Pocos Prompts (< 10)
- La paginación no se muestra
- Todos los prompts son visibles
- No hay cambios en la experiencia

### Proyecto con Muchos Prompts (> 10)
- Se muestra paginación automáticamente
- Usuario navega página por página
- Información clara sobre total de prompts
- Toggle permite ocultar la sección cuando no se necesita

## Testing

### Casos a Verificar
1. **Sin Prompts**: Estado vacío muestra botón "Add Your First Prompt"
2. **1-10 Prompts**: No se muestra paginación, todos visibles
3. **11+ Prompts**: Paginación visible y funcional
4. **Toggle**: Colapsa/expande correctamente
5. **Responsive**: Paginación se adapta a pantallas móviles
6. **Navegación**: Botones Previous/Next funcionan correctamente
7. **Estados Deshabilitados**: Botones se deshabilitan en límites

## Notas Técnicas

### Estado de Paginación
- `this.allPrompts`: Array completo de prompts
- `this.currentPromptsPage`: Página actual (1-indexed)
- `this.promptsPerPage`: Prompts por página (default: 10)

### Cálculo de Paginación
```javascript
const totalPages = Math.ceil(this.allPrompts.length / this.promptsPerPage);
const startIndex = (this.currentPromptsPage - 1) * this.promptsPerPage;
const endIndex = Math.min(startIndex + this.promptsPerPage, this.allPrompts.length);
const pagePrompts = this.allPrompts.slice(startIndex, endIndex);
```

### Event Propagation
- El header tiene `onclick` para toggle
- Los botones de acción tienen `onclick="event.stopPropagation()"` para evitar toggle accidental

## Compatibilidad

- ✅ Chrome/Edge (últimas versiones)
- ✅ Firefox (últimas versiones)
- ✅ Safari (últimas versiones)
- ✅ Móvil (iOS/Android)

## Próximas Mejoras Posibles

1. **Jump to Page**: Input para saltar a una página específica
2. **Items per Page**: Selector para cambiar prompts por página (10/25/50)
3. **Persistencia de Estado**: Recordar si la sección estaba colapsada
4. **Animación Suave**: Transición más fluida al cambiar de página
5. **Búsqueda/Filtrado**: Filtrar prompts por texto o tipo
6. **Ordenamiento**: Ordenar por fecha, tipo, o alfabéticamente

## Conclusión

Estas mejoras hacen que la gestión de prompts sea más escalable y user-friendly, especialmente para proyectos con muchos prompts. La interfaz es más limpia, la navegación es más intuitiva, y el sistema está preparado para manejar un gran volumen de datos sin comprometer la experiencia del usuario.

