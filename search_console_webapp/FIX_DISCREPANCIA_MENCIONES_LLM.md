# 🔧 Fix: Discrepancia en Conteo de Menciones - LLM Monitoring

**Fecha:** 21 de Noviembre, 2025  
**Problema Reportado:** Discrepancia entre menciones mostradas en tabla vs Brand Mentions Analysis

---

## 📋 Descripción del Problema

El usuario reportó que para un prompt específico:
- **Tabla de Prompts & Queries:** Mostraba **2 menciones** en los últimos 30 días
- **Brand Mentions Analysis:** Mostraba **1/4 LLMs mentioned**

### Causa Raíz

El sistema cuenta **dos tipos de menciones de marca**:

1. **📝 Menciones en Texto:** La marca aparece en el texto de la respuesta del LLM (`brand_mentioned = TRUE`)
2. **🔗 Menciones en URLs:** La marca aparece en las URLs/fuentes citadas por el LLM (`sources`)

**La discrepancia ocurría porque:**
- La tabla mostraba `total_mentions = text_mentions + url_citations` (suma de ambos tipos)
- El Brand Mentions Analysis solo mostraba menciones donde `brand_mentioned = TRUE` (solo texto)

### Ejemplo del Problema

Para el prompt: "¿Qué puedo esperar durante el proceso de transferencia embrionaria?"

**Perplexity:**
- Mención en texto: ❌ No
- Mención en URL: ✅ Sí (citó una URL de la marca)
- **Total:** 1 mención

**Otro LLM:**
- Mención en texto: ✅ Sí
- Mención en URL: ❌ No
- **Total:** 1 mención

**Resultado:**
- Tabla: 2 menciones ✅ (correcto)
- Brand Mentions Analysis: 1 LLM mentioned ❌ (solo contaba menciones en texto)

---

## ✅ Solución Implementada

### 1. Backend (`llm_monitoring_routes.py`)

**Cambios en el endpoint `/projects/<int:project_id>/queries`:**

```python
# ANTES (línea 1627)
r.brand_mentioned,

# AHORA (líneas 1627-1628)
r.brand_mentioned,
r.sources,  # ✨ NUEVO: Incluir sources para detectar menciones en URLs
```

**Lógica añadida (líneas 1638-1661):**
```python
# 🔧 FIX: Detectar menciones en URLs también
brand_in_text = row['brand_mentioned'] or False
brand_in_urls = False

# Verificar si la marca aparece en las URLs citadas
if brand_domain and row['sources']:
    sources = row['sources']
    if isinstance(sources, str):
        import json
        try:
            sources = json.loads(sources)
        except:
            sources = []
    
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict):
                url = source.get('url', '').lower()
                if brand_domain.lower() in url:
                    brand_in_urls = True
                    break

# La marca fue mencionada si apareció en texto O en URLs
brand_mentioned_total = brand_in_text or brand_in_urls

mentions_by_query[query_id][llm] = {
    'brand_mentioned': brand_mentioned_total,        # Total
    'brand_mentioned_in_text': brand_in_text,        # Desglose
    'brand_mentioned_in_urls': brand_in_urls,        # Desglose
    'position': row['position_in_list'],
    'competitors': row['competitors_mentioned'] or {}
}
```

### 2. Frontend (`static/js/llm_monitoring.js`)

**Cambios en `renderExpandedContent()` (líneas 1856-1873):**

```javascript
// 🔧 FIX: Mostrar badge de tipo de mención
let mentionBadge = '';
if (data.brand_mentioned) {
    const inText = data.brand_mentioned_in_text;
    const inUrls = data.brand_mentioned_in_urls;
    
    if (inText && inUrls) {
        mentionBadge = '<span ... title="Mentioned in text and URLs">📝🔗</span>';
    } else if (inText) {
        mentionBadge = '<span ... title="Mentioned in text">📝</span>';
    } else if (inUrls) {
        mentionBadge = '<span ... title="Mentioned in URLs only">🔗</span>';
    }
}
```

**Leyenda añadida (líneas 1887-1905):**
```html
<div>
    <i class="fas fa-info-circle"></i> Mention Types:
    
    📝 Text mention (in response)
    🔗 URL citation (in sources)
    📝🔗 Both text & URL
</div>
```

---

## 🎯 Resultado

Ahora **ambos lugares muestran el conteo total de menciones** (texto + URLs):

### Brand Mentions Analysis Actualizado:

```
┌─────────────────────────────────────────────┐
│ Brand Mentions Analysis                     │
├─────────────────────────────────────────────┤
│ Your Brand: 2/4 LLMs mentioned              │
│ Competitors: 6 Mentioned total              │
├─────────────────────────────────────────────┤
│ Perplexity    ✅ #15 🔗                      │
│ Claude        ❌ N/A                         │
│ Gemini        ❌ N/A                         │
│ ChatGPT       ❌ N/A                         │
├─────────────────────────────────────────────┤
│ 📝 Text mention (in response)               │
│ 🔗 URL citation (in sources)                │
│ 📝🔗 Both text & URL                         │
└─────────────────────────────────────────────┘
```

### Badges Explicados:

- **📝** - La marca fue mencionada en el **texto** de la respuesta
- **🔗** - La marca solo aparece en las **URLs citadas** (no en texto)
- **📝🔗** - La marca aparece **tanto en texto como en URLs**

---

## 🧪 Testing

Para probar el fix:

1. Ir a un proyecto de LLM Monitoring
2. Buscar un prompt con menciones
3. Expandir el acordeón "Brand Mentions Analysis"
4. Verificar que el conteo coincide con la tabla
5. Verificar que se muestran los badges correctos (📝/🔗/📝🔗)

---

## 📊 Impacto

- ✅ **Consistencia:** Ambos lugares ahora muestran el mismo conteo total
- ✅ **Transparencia:** Los usuarios pueden ver el **tipo** de mención (texto vs URL)
- ✅ **Precisión:** Se capturan todas las menciones, no solo las de texto
- ✅ **UX mejorada:** Leyenda explicativa clara en el acordeón

---

## 📝 Notas Técnicas

### Consideraciones:

1. **Performance:** El query añade `sources` pero no afecta significativamente el rendimiento
2. **Retrocompatibilidad:** Los proyectos antiguos sin `sources` funcionan correctamente (se asume `brand_in_urls = False`)
3. **Tipo de datos:** `sources` puede ser string JSON o dict/list, se maneja ambos casos

### Campos de BD utilizados:

- `llm_monitoring_results.brand_mentioned` - Mención en texto (booleano)
- `llm_monitoring_results.sources` - URLs citadas (JSONB array)
- `llm_monitoring_projects.brand_domain` - Dominio de marca para matching

---

## 🎨 Mejora de UX/UI (21 Nov 2025)

### Modal Profesional en lugar de Accordion

Se cambió el diseño de **accordion expandible** a un **modal profesional y elegante**:

#### Cambios Frontend Adicionales:

**1. Botón Mejorado en Tabla:**
```javascript
// ANTES: Botón simple con icono
<i class="fas fa-chevron-right"></i>

// AHORA: Botón con gradiente y hover effects
<button class="view-details-btn">
    <i class="fas fa-chart-bar"></i>
    <span>Details</span>
</button>
```

**2. Modal HTML (`templates/llm_monitoring.html`):**
```html
<div class="modal-overlay" id="brandMentionsModal">
    <div class="modal-content modal-large">
        <!-- Header con título dinámico -->
        <div class="modal-header">
            <h3>Brand Mentions Analysis</h3>
            <p id="brandMentionsModalPrompt">...</p>
        </div>
        
        <!-- Contenido dinámico -->
        <div class="modal-body" id="brandMentionsModalBody">
            ...
        </div>
        
        <!-- Footer con botón Close -->
        <div class="modal-footer">
            <button onclick="window.llmMonitoring.hideBrandMentionsModal()">Close</button>
        </div>
    </div>
</div>
```

**3. Diseño Moderno del Contenido:**
- **Cards con gradientes** para métricas principales
- **Iconos y colores** específicos por LLM (ChatGPT verde, Claude púrpura, etc.)
- **Sombras y efectos** para depth visual
- **Leyenda mejorada** con badges explicativos

**4. Funciones JavaScript Nuevas:**
```javascript
// Abrir modal
showBrandMentionsModal(rowIdx)

// Cerrar modal
hideBrandMentionsModal()

// Renderizar contenido profesional
renderBrandMentionsModalContent(query)

// Utilidades de diseño
getLLMIcon(llm)       // Devuelve icono Font Awesome
getLLMColor(llm)      // Devuelve color de marca del LLM
```

### Comparación Visual:

**ANTES (Accordion):**
```
┌────────────────────┐
│ Prompt Text        │ ▼
├────────────────────┤
│ [Content expands   │
│  inline in table]  │
└────────────────────┘
```

**AHORA (Modal):**
```
┌─────────────────────────────────────┐
│   📊 Brand Mentions Analysis        │
│   "Prompt text here..."       [X]   │
├─────────────────────────────────────┤
│                                     │
│  ┌─────────┐    ┌──────────┐       │
│  │ ✅ 2/4  │    │ ⚔️ 6     │       │
│  │ Brand   │    │ Competitors │     │
│  └─────────┘    └──────────┘       │
│                                     │
│  ┌─ Breakdown by LLM ─────────┐    │
│  │ 🤖 ChatGPT  ✅ #2   📝     │    │
│  │ 🧠 Claude   ❌ N/A         │    │
│  │ ⭐ Gemini   ❌ N/A         │    │
│  │ 🔍 Perplexity ✅ #15 🔗    │    │
│  └────────────────────────────┘    │
│                                     │
│  [Legend: 📝 Text | 🔗 URL]        │
├─────────────────────────────────────┤
│              [Close]                │
└─────────────────────────────────────┘
```

## 🔗 Archivos Modificados

### Backend:
- ✅ `llm_monitoring_routes.py` (líneas 1620-1678)

### Frontend:
- ✅ `templates/llm_monitoring.html` (modal HTML añadido)
- ✅ `static/js/llm_monitoring.js`:
  - Botón de tabla mejorado (líneas 1633-1652)
  - Funciones de modal (showBrandMentionsModal, hideBrandMentionsModal)
  - Diseño profesional del contenido (renderBrandMentionsModalContent)
  - Funciones helper (getLLMIcon, getLLMColor)

### Documentación:
- ✅ `FIX_DISCREPANCIA_MENCIONES_LLM.md` (este documento)

---

**Status:** ✅ Implementado y funcionando con UI/UX mejorada

