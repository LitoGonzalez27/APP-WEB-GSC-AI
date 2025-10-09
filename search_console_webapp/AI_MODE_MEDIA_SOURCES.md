# 🎯 AI Mode: Competitors = Media Sources

## 📊 Diferencia Conceptual Clave

### Manual AI (AI Overview):
**"Competitors"** = Competidores comerciales
- Nike vs Adidas
- Coca-Cola vs Pepsi
- Apple vs Samsung
- **Objetivo**: Ver si tu dominio aparece vs competidores

### AI Mode:
**"Competitors"** = Fuentes/Medios citados
- TechCrunch
- Forbes
- BBC News
- The Verge
- SneakerNews
- **Objetivo**: Ver qué medios mencionan tu marca

---

## 🔍 Por Qué es Importante

### Para el usuario:
Cuando hace una búsqueda como "best nike shoes", AI Mode muestra resultados con fuentes/citas.

**Necesitas saber**:
1. ¿Tu marca (Nike) aparece?
2. ¿En qué posición?
3. ¿Qué sentimiento tiene? (positive/neutral/negative)
4. ⭐ **¿Qué medios/fuentes cita Google?**

### Valor para el negocio:
- **Relaciones públicas**: Saber qué medios te mencionan más
- **Content marketing**: Identificar fuentes relevantes
- **SEO/PR outreach**: Encontrar oportunidades de colaboración
- **Brand monitoring**: Ver qué medios ignoran tu marca
- **Competitive intelligence**: Comparar con qué medios mencionan a competidores

---

## ✅ Cambios Implementados

### 1. Backend (Config)
**Archivo**: `ai_mode_projects/config.py`

**Antes**:
```python
MAX_COMPETITORS_PER_PROJECT = 0  # AI Mode no usa competitors
```

**Después**:
```python
MAX_COMPETITORS_PER_PROJECT = 10  # AI Mode: Fuentes/medios citados (TechCrunch, Forbes, etc.)
```

---

### 2. Frontend (Labels)

#### Formulario de Crear Proyecto:

**Antes**:
```html
<label>Competitors</label>
<p>Benchmark against the domains that appear alongside you in AI Overview.</p>
<label>Let Manual AI auto-detect competitors for me</label>
```

**Después**:
```html
<label>Media Sources</label>
<p>Monitor which media outlets and sources cite your brand in AI Mode results.</p>
<label>Let AI Mode auto-detect sources for me</label>
```

#### Modal de Settings del Proyecto:

**Antes**:
```html
<label>Project Competitors</label>
<input placeholder="Enter competitor domain (e.g., example.com)">
<button>Add Competitor</button>
<p>No competitors added yet</p>
<small>Add competitor domains to compare performance in AI Overview</small>
<i class="fas fa-users"></i>
```

**Después**:
```html
<label>Media Sources to Monitor</label>
<p>Track which media outlets and sources mention your brand in AI Mode results</p>
<input placeholder="Enter media source domain (e.g., techcrunch.com, forbes.com)">
<button>Add Source</button>
<p>No media sources added yet</p>
<small>Add media outlets to track which sources cite your brand</small>
<i class="fas fa-newspaper"></i>
```

#### Sección de Analytics:

**Antes**:
```html
<h3>Competitive Analysis vs Selected Competitors</h3>
<p>Monitor how your brand appears in AI Mode search results</p>
<h3>Global AI Overview Domains Ranking</h3>
<p>Ranking of ALL domains detected in AI Overview for your keywords, 
   with highlighting for your domain and selected competitors</p>
```

**Después**:
```html
<h3>Media Source Analysis vs Selected Sources</h3>
<p>Monitor which media outlets and sources cite your brand in AI Mode results</p>
<h3>Global Media Sources Ranking</h3>
<p>Ranking of ALL media sources detected in AI Mode for your keywords, 
   with highlighting for your brand and selected sources</p>
```

---

## 🔧 Sistema Interno (Sin Cambios)

**Importante**: A nivel de código backend, seguimos usando `competitors`:
- Tabla: `ai_mode_competitors`
- Funciones: `add_competitor()`, `remove_competitor()`
- Variables: `competitor_id`, `competitor_domain`

**Por qué**: 
- ✅ Reutiliza toda la infraestructura de Manual AI
- ✅ No requiere crear nuevas tablas
- ✅ Solo cambian los labels en la UI
- ✅ El significado/contexto es diferente pero la funcionalidad es la misma

---

## 📊 Ejemplo de Uso

### Proyecto: "Nike Brand Monitoring"
**Brand Name**: Nike

### Keywords:
- nike shoes
- best running shoes
- athletic footwear

### Media Sources to Monitor:
- techcrunch.com
- forbes.com
- sneakernews.com
- runrepeat.com
- runnersworld.com

### Después del Análisis:

**Keyword**: "nike shoes"
- ✅ Brand mentioned: true
- 📍 Position: 0 (AI Overview)
- 😊 Sentiment: positive
- 📰 **Sources detected**: 
  - ✅ SneakerNews (monitored)
  - ✅ RunRepeat (monitored)
  - ⚪ Complex (not monitored)
  - ⚪ GearJunkie (not monitored)

**Insights**:
- Nike aparece en posición 0 (AI Overview)
- 2 de 4 fuentes son medios que estás monitorizando
- Sentimiento positivo
- **Acción**: Considerar añadir Complex y GearJunkie a las fuentes monitorizadas

---

## 🎯 Flujo Completo

### 1. Crear Proyecto
```
Name: "Nike Brand Monitoring"
Brand: "Nike"
Country: US
Media Sources: techcrunch.com, forbes.com, sneakernews.com (opcional)
```

### 2. Añadir Keywords
```
nike shoes
best sneakers 2024
running shoes
```

### 3. Ejecutar Análisis
- AI Mode analiza cada keyword
- Detecta si "Nike" aparece
- Captura posición y sentimiento
- **Extrae todas las fuentes citadas**

### 4. Ver Resultados
- Ver keywords donde Nike aparece
- Ver posición de Nike en cada resultado
- Ver sentimiento de las menciones
- **Ver qué medios te mencionan más**

### 5. Añadir Nuevas Fuentes
- Basado en los resultados
- Añadir medios que aparecen frecuentemente
- Monitorizar rendimiento vs esas fuentes

---

## 🚀 Impacto en el Producto

### Para Marketing:
- "¿Qué medios hablan de nosotros?"
- "¿Dónde deberíamos buscar cobertura?"

### Para PR:
- "¿Qué outlets nos mencionan?"
- "¿Cuáles nos ignoran?"

### Para SEO:
- "¿Qué fuentes tienen mejor rendimiento?"
- "¿Dónde deberíamos conseguir enlaces?"

### Para Business Intelligence:
- "¿Qué medios menciona Google más frecuentemente?"
- "¿Cómo nos comparamos con nuestros competidores en esos medios?"

---

## 📝 Documentación para Usuarios

### Tooltip en la UI:
```
"Monitor which media outlets and sources cite your brand in AI Mode results. 

Examples: techcrunch.com, forbes.com, theverge.com

AI Mode will track how often these sources mention your brand and 
their visibility in AI-powered search results."
```

### Help Center:
```
**What are Media Sources in AI Mode?**

Media Sources are the news outlets, blogs, and websites that Google 
cites when generating AI Mode responses. 

By tracking specific sources, you can:
- See which media outlets mention your brand most
- Identify opportunities for PR and content partnerships
- Monitor your presence in key industry publications
- Compare your media coverage vs competitors

Unlike traditional SEO where you track your domain, AI Mode tracks 
your brand mentions across various trusted sources.
```

---

## ✅ Status

**Backend**: ✅ Funcional (usa sistema de competitors)  
**Frontend**: ✅ Labels actualizados a "Media Sources"  
**UI/UX**: ✅ Placeholders y tooltips actualizados  
**Documentación**: ✅ Completa  
**Testing**: ⏳ Pendiente de deploy  

---

## 🎯 Próximos Pasos

1. ✅ Config actualizado (MAX_COMPETITORS_PER_PROJECT = 10)
2. ✅ Labels del formulario actualizados
3. ✅ Labels del modal actualizados
4. ✅ Labels de analytics actualizados
5. ⏳ Deploy a staging
6. ⏳ Testing completo
7. ⏳ Documentación de usuario

---

**SISTEMA LISTO PARA TESTING** 🚀

**Diferencia clave entendida**:
- Manual AI: Competitors = Empresas competidoras
- AI Mode: Competitors = Medios/fuentes que citan tu marca

**Código mantiene el término "competitors"**  
**UI muestra "Media Sources" o "Sources"**  
**Funcionalidad idéntica, significado diferente** ✅

