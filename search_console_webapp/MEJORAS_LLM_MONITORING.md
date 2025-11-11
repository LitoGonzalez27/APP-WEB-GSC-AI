# 🎯 MEJORAS IMPLEMENTADAS: LLM MONITORING - SHARE OF VOICE

**Fecha**: 11 de Noviembre, 2025  
**Objetivo**: Mejorar la precisión de detección de marcas y calcular Share of Voice ponderado por posición

---

## ✅ **MEJORA 1: PONDERACIÓN DE MENCIONES POR POSICIÓN**

### **Problema Original**
El Share of Voice trataba todas las menciones por igual, independientemente de si aparecías en posición #1 o #15. Esto no reflejaba la realidad: **una mención en top 3 tiene MUCHO más valor que una al final**.

### **Solución Implementada**
Se implementó un sistema de ponderación que refleja la **visibilidad real**:

| Posición | Peso | Impacto |
|----------|------|---------|
| **Top 3** | 2.0x | Cuenta **doble** (máxima visibilidad) |
| **Top 5** | 1.5x | Cuenta **50% más** (alta visibilidad) |
| **Top 10** | 1.2x | Cuenta **20% más** (visible) |
| **> 10** | 0.8x | Cuenta **80%** (baja visibilidad) |
| **Sin posición** | 1.0x | Baseline (mención en texto) |

### **Ejemplo Real**
**Escenario:**
- Tu marca: 10 menciones (5 en top 3, 5 en posición 15)
- Competidor: 10 menciones (todas en posición 8-10)

**Share of Voice NORMAL (antiguo):**
- Tu marca: 50%
- Competidor: 50%
- ❌ **No refleja que tus menciones top 3 valen más**

**Share of Voice PONDERADO (nuevo):**
- Tu marca: **57.7%** ✨
  - 5 menciones × 2.0 (top 3) = 10 puntos
  - 5 menciones × 0.8 (pos 15) = 4 puntos
  - **Total: 14 puntos ponderados**
- Competidor: **42.3%**
  - 10 menciones × 1.2 (top 10) = 12 puntos
  - **Total: 12 puntos ponderados**

**Resultado:** Ahora tu métrica **refleja correctamente** que tus menciones top tienen más valor.

### **Código Implementado**
```python
# En services/llm_monitoring_service.py
def _calculate_weighted_mentions(self, results: List[Dict], entity_key: str = None) -> float:
    """
    Calcula menciones ponderadas según la posición en listas
    """
    weighted_total = 0.0
    
    for r in results:
        base_mentions = r.get('mention_count', 0)
        position = r.get('position_in_list')
        
        if position is None:
            weight = 1.0
        elif position <= 3:
            weight = 2.0  # Top 3 cuenta DOBLE
        elif position <= 5:
            weight = 1.5
        elif position <= 10:
            weight = 1.2
        else:
            weight = 0.8
        
        weighted_total += base_mentions * weight
    
    return weighted_total
```

### **Cambios en Base de Datos**
Se añadieron **2 columnas nuevas** a `llm_monitoring_snapshots`:
- `weighted_share_of_voice` (DECIMAL): Share of Voice ponderado
- `weighted_competitor_breakdown` (JSONB): Desglose ponderado por competidor

### **Migración**
```bash
python3 migrate_add_weighted_sov.py
```

---

## ✅ **MEJORA 2: DETECCIÓN MEJORADA EN SOURCES**

### **Problema Original**
La detección de dominios en sources (URLs citadas) era **demasiado permisiva**:
- Buscaba "kipu" en cualquier parte de la URL
- Detectaba falsos positivos como: `https://wikipedia.org/wiki/Kipuka` ❌

### **Solución Implementada**
Se implementó un sistema de **2 niveles de prioridad**:

#### **PRIORIDAD 1: Dominio completo (restrictivo)**
Busca el dominio COMPLETO como dominio válido usando regex:
```python
# Ejemplos que COINCIDEN:
✅ https://getkipu.com/pricing
✅ http://www.getkipu.com
✅ getkipu.com/about

# Ejemplos que NO coinciden:
❌ https://wikipedia.org/wiki/Kipuka  (kipuka ≠ kipu)
❌ https://blog.com/article-about-kipu  (kipu en path, no en dominio)
```

#### **PRIORIDAD 2: Variaciones (permisivo)**
Solo se ejecuta si no se encontró el dominio completo:
- Busca variaciones largas (≥5 caracteres)
- Usa word boundaries para evitar matches parciales
- Ejemplo: detecta "quipu" pero NO "quipus" ni "antiquipu"

### **Código Implementado**
```python
# En services/llm_monitoring_service.py (línea ~347)

# PRIORIDAD 1: Buscar dominio COMPLETO
if brand_domain:
    domain_clean = brand_domain.lower().replace('www.', '')
    domain_patterns = [
        r'://(?:www\.)?{}\.(?:com|es|net|org)(?:/|$)'.format(re.escape(domain_clean)),
        r'^(?:www\.)?{}\.(?:com|es|net|org)(?:/|$)'.format(re.escape(domain_clean)),
    ]
    
    for pattern in domain_patterns:
        if re.search(pattern, source_url):
            brand_found_in_sources = True
            logger.debug(f"✅ Domain match in source URL")
            break

# PRIORIDAD 2: Variaciones (solo si no encontró dominio completo)
if not brand_found_in_sources:
    for variation in brand_variations:
        if len(variation) >= 5:  # Solo variaciones largas
            var_pattern = r'\b{}\b'.format(re.escape(variation.lower()))
            if re.search(var_pattern, source_url):
                brand_found_in_sources = True
                break
```

### **Beneficios**
- ✅ **Menos falsos positivos**: "kipu" no detecta "kipuka"
- ✅ **Mayor precisión**: prioriza coincidencias de dominio completo
- ✅ **Más robusto**: word boundaries evitan matches parciales

---

## 🎨 **MEJORA 3: EXPERIENCIA DE USUARIO (UX)**

### **Problema Original**
Dos métricas diferentes (normal y ponderada) sin explicación pueden confundir al usuario.

### **Solución Implementada**

#### **1. Toggle Selector Elegante**
- Selector visual con dos opciones:
  - **⭐ Weighted** (Recomendado) - Por defecto
  - **📊 Standard** - Para comparar
- Cambio instantáneo al hacer clic
- Badge "Recommended" en la opción ponderada

#### **2. Botón de Información Contextual**
- Icono de información (ℹ️) junto al título del gráfico
- Abre un modal educativo completo
- Diseño no intrusivo

#### **3. Modal Educativo Completo**
El modal incluye:

**Sección 1: Weighted Share of Voice**
- Explicación clara del concepto
- Tabla visual con los pesos por posición
- Badge "Recommended" destacado

**Sección 2: Standard Share of Voice**
- Explicación del método clásico
- Fórmula matemática visual
- Casos de uso

**Sección 3: Ejemplo Práctico**
- Escenario real con números
- Comparación lado a lado
- Resultado visual del impacto

**Sección 4: Cómo Interpretar**
- 3 tarjetas con consejos:
  - ✅ Weighted > Standard (excelente)
  - ⚠️ Weighted < Standard (alerta)
  - 📊 Diferencia > 20% (disparidad grande)

### **Archivos de UX Creados**
1. ✅ `templates/llm_monitoring.html` - Toggle y modal HTML
2. ✅ `static/sov-metrics-ui.css` - Estilos completos
3. ✅ `static/js/llm_monitoring.js` - Lógica del toggle y modal

### **Texto en Inglés (User-Friendly)**
Todo el contenido está en inglés profesional y claro:
- "Position-aware metric that gives more value to mentions in top positions"
- "Appearing #1 is much more valuable than appearing #15"
- "Your mentions are in top positions - excellent quality!"

---

## 📊 **CÓMO USAR LAS NUEVAS MÉTRICAS**

### **En el API**
El endpoint `/api/llm-monitoring/projects/{id}/share-of-voice-history` ahora acepta un parámetro `metric`:

```bash
# Share of Voice PONDERADO (recomendado - por defecto)
GET /api/llm-monitoring/projects/1/share-of-voice-history?metric=weighted&days=30

# Share of Voice NORMAL (para comparar)
GET /api/llm-monitoring/projects/1/share-of-voice-history?metric=normal&days=30
```

### **Respuesta del API**
```json
{
  "success": true,
  "metric_type": "weighted",
  "dates": ["2025-11-01", "2025-11-02", ...],
  "datasets": [
    {
      "label": "Tu Marca",
      "data": [52.3, 54.1, 56.7, ...],  // Share of Voice ponderado
      "borderColor": "#3b82f6"
    },
    {
      "label": "COMPETIDOR1",
      "data": [30.2, 28.5, 27.1, ...],
      "borderColor": "#ef4444"
    }
  ],
  "donut_data": { ... },
  "period": { ... }
}
```

### **En los Logs**
Ahora verás ambas métricas en los logs del análisis:
```
📊 Snapshot openai: 15/30 menciones (50.0%)
   📈 Share of Voice: 45.2% (normal) | 52.8% (ponderado por posición)
```

---

## 🔧 **ARCHIVOS MODIFICADOS**

### **Backend**
1. ✅ `services/llm_monitoring_service.py`
   - Nueva función `_calculate_weighted_mentions()`
   - Detección mejorada en sources (línea ~340-388)
   - Cálculo de Share of Voice ponderado en `_create_snapshot()`

2. ✅ `llm_monitoring_routes.py`
   - Endpoint `/share-of-voice-history` acepta parámetro `metric`
   - Devuelve `weighted_share_of_voice` en métricas

3. ✅ `migrate_add_weighted_sov.py` (NUEVO)
   - Script de migración para añadir columnas

### **Base de Datos**
```sql
-- Columnas añadidas a llm_monitoring_snapshots
ALTER TABLE llm_monitoring_snapshots
ADD COLUMN weighted_share_of_voice DECIMAL(5,2) DEFAULT 0.0;

ALTER TABLE llm_monitoring_snapshots
ADD COLUMN weighted_competitor_breakdown JSONB DEFAULT '{}'::jsonb;

-- Índice para consultas rápidas
CREATE INDEX idx_snapshots_weighted_sov 
ON llm_monitoring_snapshots(project_id, weighted_share_of_voice DESC);
```

---

## 🚀 **PASOS PARA ACTIVAR**

### **1. Ejecutar Migración**
```bash
cd /Users/carlosgonzalez/Desktop/app/APP-WEB-GSC-AI/search_console_webapp
python3 migrate_add_weighted_sov.py
```

**Resultado esperado:**
```
🚀 MIGRACIÓN: Añadir campos de Share of Voice ponderado
➕ Añadiendo columna 'weighted_share_of_voice'...
   ✅ Columna 'weighted_share_of_voice' añadida
➕ Añadiendo columna 'weighted_competitor_breakdown'...
   ✅ Columna 'weighted_competitor_breakdown' añadida
📊 Creando índices para optimizar consultas...
   ✅ Índice creado
✅ MIGRACIÓN COMPLETADA EXITOSAMENTE
```

### **2. Ejecutar Análisis**
El próximo análisis (automático o manual) calculará automáticamente las métricas ponderadas:
```bash
# Opción 1: Esperar al cron diario (4:00 AM)
# Opción 2: Ejecutar manualmente
python3 daily_llm_monitoring_cron.py
```

### **3. Verificar en el Dashboard**
- Accede a tu proyecto en el dashboard de LLM Monitoring
- Las gráficas mostrarán automáticamente el Share of Voice ponderado
- En las métricas detalladas verás ambos valores (normal y ponderado)

---

## 📈 **IMPACTO ESPERADO**

### **Casos de Uso**
1. **Si estás en top 3 frecuentemente:**
   - Tu Share of Voice ponderado será **MAYOR** que el normal ✅
   - Refleja mejor tu dominancia real

2. **Si apareces en posiciones bajas:**
   - Tu Share of Voice ponderado será **MENOR** que el normal ⚠️
   - Te alerta de que necesitas mejorar posicionamiento

3. **Competidor con muchas menciones en posiciones bajas:**
   - Su Share of Voice ponderado será **menor** al tuyo
   - Aunque tenga más menciones totales, tú tienes más visibilidad real

### **Métricas Clave**
- **Diferencia típica**: 5-15% entre Share of Voice normal y ponderado
- **Diferencia alta (>20%)**: Indica gran disparidad en calidad de posiciones
- **Ponderado > Normal**: Excelente señal, estás en posiciones top ✅
- **Ponderado < Normal**: Señal de alerta, necesitas subir en rankings ⚠️

---

## 🐛 **TROUBLESHOOTING**

### **Las columnas no se crean**
```bash
# Verificar que la tabla existe
psql -d tu_database -c "\d llm_monitoring_snapshots"

# Ejecutar migración con más verbosidad
python3 migrate_add_weighted_sov.py 2>&1 | tee migration.log
```

### **No veo las métricas ponderadas**
1. Verifica que la migración se ejecutó correctamente
2. Ejecuta un nuevo análisis (los datos antiguos usarán Share of Voice normal)
3. Revisa los logs del snapshot:
   ```bash
   tail -f logs/llm_monitoring.log | grep "Share of Voice"
   ```

### **Errores en el análisis**
```bash
# Ver errores detallados
python3 daily_llm_monitoring_cron.py 2>&1 | grep -A 5 "ERROR"
```

---

## 📚 **DOCUMENTACIÓN ADICIONAL**

### **Algoritmo de Ponderación**
```
Share of Voice Ponderado = (Σ menciones_ponderadas_marca) / (Σ menciones_ponderadas_totales) × 100

Donde:
- menciones_ponderadas = menciones × peso_posición
- peso_posición = f(posición_en_lista)
```

### **Comparación con Competencia**
El sistema ahora puede identificar correctamente:
- Marcas con **calidad** (pocas menciones pero top)
- Marcas con **cantidad** (muchas menciones pero bajas)
- Tu estrategia óptima: **alta calidad Y alta cantidad**

---

## ✨ **PRÓXIMAS MEJORAS SUGERIDAS**

### **Alta Prioridad**
- [ ] Dashboard visual con comparación lado a lado (normal vs ponderado)
- [ ] Alertas automáticas cuando el Share of Voice ponderado cae >10%
- [ ] Export a Excel con ambas métricas

### **Media Prioridad**
- [ ] Análisis de tendencias: ¿estás mejorando posiciones con el tiempo?
- [ ] Benchmarking: comparar tu Share of Voice con promedios del sector
- [ ] Integración con Google Analytics para correlacionar con tráfico real

### **Baja Prioridad**
- [ ] Ponderación personalizable por usuario
- [ ] Machine Learning para predecir Share of Voice futuro
- [ ] A/B testing de estrategias de posicionamiento

---

## 📞 **SOPORTE**

Si tienes dudas o encuentras problemas:
1. Revisa los logs en `logs/llm_monitoring.log`
2. Ejecuta el script de diagnóstico: `python3 diagnose_llm_queries.py`
3. Consulta este documento para soluciones comunes

**Última actualización**: 11 de Noviembre, 2025

