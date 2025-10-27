# 🤖 Nueva Funcionalidad: Sugerencias de Prompts con IA

## Resumen

Se ha implementado un sistema de **sugerencias inteligentes de prompts** que utiliza **Gemini Flash** (Google AI) para ayudar a los usuarios a generar ideas de prompts basándose en el contexto de su proyecto y prompts existentes.

## Motivación

Después de cambiar LLM Monitoring para que funcione con gestión manual de prompts (como Manual AI y AI Mode), surgió la necesidad de facilitar al usuario la creación de prompts proporcionándole:

1. **Ideas y sugerencias** contextuales
2. **Ahorro de tiempo** en la creación manual
3. **Inspiración** para diferentes tipos de preguntas
4. **Flexibilidad** - el usuario decide qué añadir

## Cómo Funciona

### 🎯 Flujo del Usuario

1. **Usuario entra a un proyecto** con algunos prompts ya existentes (o ninguno)
2. **Click en botón "AI Suggestions"** (🪄 icono de magia)
3. **Gemini Flash analiza** el contexto del proyecto:
   - Nombre de la marca
   - Industria/sector
   - Prompts ya existentes
   - Competidores
   - Idioma del proyecto
4. **IA genera 10 sugerencias** relevantes y contextuales
5. **Usuario selecciona** las que le gustan (checkboxes)
6. **Botones auxiliares:** "Select All" y "Deselect All"
7. **Click en "Add Selected"** → se añaden al proyecto

### 🧠 Inteligencia Contextual

La IA genera sugerencias **inteligentes** que:

- ✅ **Evitan duplicados** con prompts existentes
- ✅ **Son contextuales** al sector y marca
- ✅ **Variedad de tipos:**
  - Preguntas generales sobre la industria
  - Preguntas específicas sobre la marca
  - Comparativas con competidores
  - Preguntas técnicas y básicas
- ✅ **Idioma correcto** (español o inglés)
- ✅ **Longitud adecuada** (15-500 caracteres)
- ✅ **Naturales** - como las haría un usuario real

## Implementación Técnica

### Backend

#### Nuevo Endpoint: `POST /api/llm-monitoring/projects/<project_id>/queries/suggest`

**Descripción:** Genera sugerencias de queries usando Gemini Flash

**Autenticación:** Requiere login y ownership del proyecto

**Body (opcional):**
```json
{
    "count": 10  // Número de sugerencias (default: 10, max: 20)
}
```

**Response exitoso:**
```json
{
    "success": true,
    "suggestions": [
        "¿Cuáles son las mejores herramientas de SEO?",
        "¿Qué es ClicAndSEO y cómo funciona?",
        "ClicAndSEO vs Semrush: comparativa",
        ...
    ],
    "count": 10,
    "message": "10 sugerencias generadas por IA"
}
```

**Response con error:**
```json
{
    "error": "No se pudieron generar sugerencias",
    "hint": "Verifica que GOOGLE_API_KEY esté configurada"
}
```

#### Nueva Función en Servicio: `generate_query_suggestions_with_ai()`

**Ubicación:** `services/llm_monitoring_service.py`

**Características:**
- Usa **Gemini Flash** (más barato que otros modelos)
- Prompt estructurado con contexto completo
- Parsea respuesta de IA
- Valida longitud y formato
- Elimina duplicados
- Limpia numeraciones y viñetas
- Logging detallado con coste

**Prompt a Gemini:**
```
Eres un experto en marketing digital y brand visibility en LLMs.

CONTEXTO:
- Marca: {brand_name}
- Industria: {industry}
- Idioma: {language}
- Competidores: {competitors}

QUERIES EXISTENTES:
- {lista de prompts existentes}

TAREA:
Genera {count} preguntas adicionales en {language} que un usuario 
haría a un LLM para buscar información sobre {industry}.

REQUISITOS:
1. Diferentes a las existentes
2. Naturales y realistas
3. Algunas mencionen la marca
4. Algunas sean generales
5. Algunas comparen con competidores
6. Mínimo 15 caracteres
7. Variedad: básicas, técnicas, comparativas

FORMATO:
Una pregunta por línea, sin numeración.
```

**Coste:**
- ~$0.0001 - $0.0003 USD por llamada
- Gemini Flash: $0.075 per 1M input tokens, $0.30 per 1M output tokens
- Extremadamente económico

### Frontend

#### Nuevo Botón en Interfaz

**Ubicación:** Card de "Prompts Management"

**Botón:** 
```html
<button id="btnGetSuggestions" class="btn btn-success btn-sm">
    <i class="fas fa-magic"></i>
    AI Suggestions
</button>
```

**Estilo:** Verde con icono de varita mágica ✨

#### Nuevo Modal: "AI-Powered Prompt Suggestions"

**Elementos:**

1. **Estado de Carga**
   - Spinner animado
   - Texto: "Generating AI suggestions..."
   - Subtexto: "This may take a few seconds"

2. **Lista de Sugerencias**
   - Cada sugerencia = checkbox + texto + badge "AI"
   - Scroll vertical si hay muchas
   - Botones "Select All" y "Deselect All"

3. **Estado de Error**
   - Icono de advertencia
   - Mensaje de error
   - Botón "Try Again"

4. **Footer**
   - Botón "Cancel"
   - Botón "Add Selected (N)" → muestra contador dinámico

#### Funciones JavaScript Añadidas

**En `llm_monitoring.js`:**

```javascript
// Mostrar modal y obtener sugerencias
showSuggestionsModal()

// Ocultar modal
hideSuggestionsModal()

// Llamar a API para obtener sugerencias
getSuggestions()

// Renderizar sugerencias con checkboxes
renderSuggestions(suggestions)

// Actualizar contador de seleccionadas
updateSuggestionsCounter()

// Seleccionar/deseleccionar todas
selectAllSuggestions()
deselectAllSuggestions()

// Añadir seleccionadas al proyecto
addSelectedSuggestions()
```

**Flujo de estados:**
1. Loading → Esperando respuesta de IA
2. List → Mostrando sugerencias
3. Error → Si algo falla

### CSS

**Nuevos estilos en `llm-monitoring.css`:**

- `.modal-large` - Modal más ancho para sugerencias
- `.suggestions-loading` - Estado de carga centrado
- `.suggestions-list` - Container de sugerencias
- `.suggestions-header` - Botones auxiliares
- `.suggestions-container` - Lista scrolleable
- `.suggestion-item` - Card de cada sugerencia
- `.suggestion-label` - Etiqueta clickeable
- `.suggestion-checkbox` - Checkbox grande (20x20px)
- `.suggestion-text` - Texto de la sugerencia
- `.suggestion-badge` - Badge "AI" con gradiente
- **Efectos hover y checked** - Feedback visual

**Características de diseño:**
- ✨ Gradientes modernos
- 🎨 Feedback visual claro
- ✅ Estado checked resalta en azul
- 📱 Responsive

## Ventajas de este Enfoque

### 🚀 Para el Usuario

1. **Facilita la creación** - No parte de cero
2. **Da ideas** - Descubre tipos de preguntas que no había considerado
3. **Ahorra tiempo** - 10 sugerencias en segundos
4. **Control total** - Selecciona solo las que quiere
5. **Aprende** - Ve ejemplos de buenos prompts
6. **Flexibilidad** - Puede editar después

### 💡 Para el Producto

1. **Mejor onboarding** - Usuarios nuevos no se atascan
2. **Mayor adoption** - Más fácil empezar
3. **Mejor UX** - Combina lo mejor de manual + automático
4. **Diferenciador** - Feature único vs competencia
5. **Bajo coste** - Gemini Flash es extremadamente barato
6. **Escalable** - Funciona con cualquier industria/marca

### 💰 Coste

**Por proyecto/sesión:**
- Generación de 10 sugerencias: ~$0.0001 - $0.0003 USD
- 1000 generaciones: ~$0.10 - $0.30 USD
- **Prácticamente gratis**

**Comparativa con otros LLMs:**
- GPT-5: ~15x más caro
- Claude 4.5: ~10x más caro
- Gemini Flash: ✅ **El más barato**
- Perplexity: ~3-10x más caro

## Ejemplo de Uso

### Escenario: Usuario crea proyecto de "ClicAndSEO"

**Datos del proyecto:**
- Marca: ClicAndSEO
- Industria: Herramientas de SEO y análisis de IA
- Competidores: Semrush, Ahrefs, Moz
- Idioma: Español

**Prompts existentes (2):**
1. "¿Qué es ClicAndSEO?"
2. "Precio de ClicAndSEO"

**Click en "AI Suggestions" →**

**Sugerencias generadas por Gemini:**
1. ☑️ ¿Cuáles son las mejores herramientas de SEO para principiantes?
2. ☑️ ClicAndSEO vs Semrush: ¿cuál es mejor?
3. ☐ ¿Cómo funciona el análisis de IA en ClicAndSEO?
4. ☑️ Alternativas a Semrush para análisis SEO
5. ☐ ¿ClicAndSEO tiene API para integraciones?
6. ☑️ Comparativa de herramientas SEO: ClicAndSEO, Ahrefs, Moz
7. ☐ Opiniones sobre ClicAndSEO de usuarios reales
8. ☑️ ¿Qué incluye el plan gratuito de ClicAndSEO?
9. ☐ Tutorial de ClicAndSEO para principiantes
10. ☑️ Top 10 herramientas de análisis SEO con IA

**Usuario selecciona 6 → Click "Add Selected (6)"**

**Resultado:** 6 prompts añadidos automáticamente al proyecto en 5 segundos

## Comparación: Antes vs Ahora

### Antes (Solo Manual)

❌ Usuario debe pensar todos los prompts desde cero
❌ Puede bloquearse creativamente
❌ No sabe qué tipo de preguntas hacer
❌ Proceso lento y tedioso
❌ Puede olvidar ángulos importantes

### Ahora (Manual + IA)

✅ Usuario empieza con 2-3 prompts básicos
✅ Click en "AI Suggestions"
✅ Ve 10 ideas inteligentes en 3 segundos
✅ Selecciona las que le gustan
✅ Las añade con 1 click
✅ Puede editarlas o eliminarlas después
✅ **Resultado:** 12-13 prompts en 2 minutos

## Futuras Mejoras Posibles

### Corto Plazo

1. **Regenerar sugerencias** - Botón para pedir más
2. **Ajustar cantidad** - Slider para 5-20 sugerencias
3. **Filtros por tipo** - Solo generales, solo con marca, etc.
4. **Preview de análisis** - Estimar coste antes de analizar

### Medio Plazo

1. **Sugerencias personalizadas** - Basadas en industria específica
2. **Templates por sector** - Biblioteca de prompts por industria
3. **Sugerencias incrementales** - Añadir prompts similares a uno existente
4. **Análisis de gaps** - IA detecta qué ángulos faltan cubrir

### Largo Plazo

1. **Aprendizaje del usuario** - IA aprende qué prompts prefiere
2. **Sugerencias colaborativas** - Compartir prompts entre usuarios
3. **Benchmarking** - Comparar con prompts de industria similar
4. **Auto-optimization** - IA sugiere eliminar prompts poco útiles

## Documentación Técnica

### Requisitos

**Variables de entorno necesarias:**
```bash
GOOGLE_API_KEY=AIza...  # API Key de Google (Gemini)
```

**Dependencias Python:**
- `google-generativeai` (ya instalada)
- Proveedor LLM de Google ya implementado

**Permisos:**
- Usuario debe estar autenticado
- Usuario debe ser owner del proyecto

### Testing Recomendado

#### Test 1: Proyecto sin prompts
- ✅ Crear proyecto nuevo
- ✅ Click "AI Suggestions"
- ✅ Verificar 10 sugerencias generadas
- ✅ Seleccionar todas
- ✅ Añadir → verificar que se guardan

#### Test 2: Proyecto con prompts existentes
- ✅ Proyecto con 5 prompts
- ✅ Click "AI Suggestions"
- ✅ Verificar que NO sugiere duplicados
- ✅ Verificar contexto similar
- ✅ Añadir seleccionadas

#### Test 3: Manejo de errores
- ✅ Sin GOOGLE_API_KEY → mensaje de error claro
- ✅ API falla → botón "Try Again"
- ✅ Sin prompts seleccionados → mensaje de advertencia

#### Test 4: UX
- ✅ Loading spinner funciona
- ✅ Contador actualiza en tiempo real
- ✅ "Select All" / "Deselect All" funcionan
- ✅ Checkboxes visuales claros
- ✅ Modal cierra correctamente

### Logging

El sistema registra:
```
🤖 Generando 10 sugerencias de queries con IA para ClicAndSEO...
✅ Generadas 10 sugerencias con IA
   Coste: $0.000150 USD
```

### Monitoreo

Métricas a trackear:
- Número de veces que se usa "AI Suggestions"
- Promedio de sugerencias aceptadas por usuario
- Tasa de conversión (sugerencias → añadidas)
- Coste acumulado por usuario/proyecto

## Archivos Modificados

### Backend
- `llm_monitoring_routes.py` (+90 líneas) - Nuevo endpoint `/suggest`
- `services/llm_monitoring_service.py` (+140 líneas) - Función de IA

### Frontend HTML
- `templates/llm_monitoring.html` (+65 líneas) - Modal + botón

### Frontend JavaScript
- `static/js/llm_monitoring.js` (+250 líneas) - 7 nuevas funciones

### CSS
- `static/llm-monitoring.css` (+140 líneas) - Estilos del modal

**Total:** ~685 líneas de código añadidas

## Conclusión

Esta funcionalidad representa el **mejor balance** entre:

1. **Control del usuario** - No le forzamos nada
2. **Asistencia inteligente** - Le ayudamos activamente
3. **Coste** - Prácticamente gratis con Gemini Flash
4. **UX** - Proceso rápido y claro
5. **Flexibilidad** - Puede ignorarlas, editarlas o usarlas tal cual

Es un **diferenciador competitivo** que mejora significativamente el onboarding y la experiencia de uso, especialmente para usuarios nuevos que no saben por dónde empezar.

---

**Fecha:** 27 de Octubre, 2025  
**Autor:** Sistema de actualización automática  
**Versión:** 1.0  
**Coste promedio por generación:** ~$0.0002 USD

