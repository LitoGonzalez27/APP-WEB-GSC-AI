# Fix: Grid.js Error en LLM Comparison

## 🐛 Problema Identificado

El frontend mostraba el siguiente error en la consola del navegador:

```
[Grid.js] [ERROR]: TypeError: Cannot read properties of undefined (reading 'length')
```

Este error aparecía 4 veces al cargar la sección de "LLM Comparison".

## 🔍 Causa Raíz

El endpoint `/api/llm-monitoring/projects/:id/comparison` estaba **leyendo** el campo `total_mentions` de la base de datos pero **NO lo estaba incluyendo** en el JSON de respuesta.

Sin embargo, el frontend (`llm_monitoring.js`, línea 1358) **sí esperaba** ese campo:

```javascript
`${item.mention_rate.toFixed(1)}% (${(item.total_mentions || 0)}/${(item.total_queries || 0)})`
```

Cuando Grid.js intentaba renderizar la tabla con `item.total_mentions` siendo `undefined`, lanzaba el error.

## ✅ Solución Implementada

### Cambios en Backend

**Archivo:** `llm_monitoring_routes.py`  
**Línea:** 1184

Agregamos el campo `total_mentions` al JSON de respuesta del endpoint de comparación:

```python
comparison_list.append({
    'llm_provider': c['llm_provider'],
    'snapshot_date': c['snapshot_date'].isoformat() if c['snapshot_date'] else None,
    'mention_rate': float(c['mention_rate']) if c['mention_rate'] is not None else 0,
    'total_mentions': c.get('total_mentions') or 0,  # 🔧 FIX: Campo faltante
    'avg_position': float(c['avg_position']) if c['avg_position'] is not None else None,
    'share_of_voice': float(c['share_of_voice']) if c['share_of_voice'] is not None else 0,
    # ... resto de campos
})
```

## 📊 Resultado Esperado

- ✅ Grid.js puede renderizar la tabla sin errores
- ✅ La columna "Mention Rate" muestra correctamente: "4.5% (1/22)"
- ✅ Los 4 errores de Grid.js desaparecen de la consola

## 🚀 Despliegue

Este fix está incluido en el siguiente commit y debe desplegarse a Railway staging.

```bash
git add llm_monitoring_routes.py FIX_GRIDJS_ERROR.md
git commit -m "fix: Agregar campo total_mentions a endpoint de comparación LLM"
git push origin staging
```

---

**Fecha:** 2025-11-06  
**Estado:** ✅ Implementado y testeado localmente

