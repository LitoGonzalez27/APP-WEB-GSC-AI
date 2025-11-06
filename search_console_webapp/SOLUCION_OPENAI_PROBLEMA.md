# 🔧 SOLUCIÓN: Problema con OpenAI en LLM Monitoring

## 📋 Diagnóstico del Problema

**Síntomas:**
- ❌ OpenAI no funciona desde el 5 de noviembre de 2025
- ✅ Otros LLMs (Anthropic, Google, Perplexity) funcionan correctamente
- ✅ La API key de OpenAI es válida

**Causa Raíz:**
El modelo configurado en la base de datos es **`gpt-5`** que **NO EXISTE** en OpenAI.

OpenAI solo tiene estos modelos disponibles:
- `gpt-4o` (el más potente actualmente)
- `gpt-4o-mini` (más rápido y económico)
- `gpt-4-turbo`
- `gpt-3.5-turbo`

OpenAI probablemente endureció sus validaciones el 5 de noviembre y ahora rechaza directamente el modelo inexistente.

---

## 🔧 Solución

### Opción 1: Ejecutar Script de Corrección (RECOMENDADA)

1. **En Railway**, ejecuta el script de corrección:

```bash
python3 fix_openai_model_config.py
```

Este script:
- ✅ Desmarca `gpt-5` como modelo actual
- ✅ Marca `gpt-4o` como modelo actual
- ✅ El próximo cron job usará el modelo correcto

---

### Opción 2: Corrección Manual en la Base de Datos

Si prefieres hacerlo manualmente, ejecuta estos SQL en la base de datos de Railway:

```sql
-- 1. Desmarcar gpt-5 como actual
UPDATE llm_model_registry
SET is_current = FALSE
WHERE llm_provider = 'openai' AND model_id = 'gpt-5';

-- 2. Marcar gpt-4o como actual
UPDATE llm_model_registry
SET is_current = TRUE
WHERE llm_provider = 'openai' AND model_id = 'gpt-4o';

-- 3. Verificar configuración
SELECT 
    model_id,
    model_display_name,
    is_current,
    is_available
FROM llm_model_registry
WHERE llm_provider = 'openai'
ORDER BY is_current DESC;
```

---

### Opción 3: Usar Variable de Entorno (TEMPORAL)

Como solución temporal, puedes configurar la variable de entorno en Railway:

```
OPENAI_PREFERRED_MODEL=gpt-4o
```

Esto sobrescribe el modelo de la BD. Pero es mejor corregir la BD.

---

## ✅ Verificación

Después de aplicar la solución, verifica:

1. **Ejecuta el diagnóstico:**
```bash
python3 check_openai_model.py
```

Deberías ver:
```
[⭐ ACTUAL] [✅] gpt-4o
   Display: GPT-4o
   Cost: $2.50/$10.00 per 1M tokens
```

2. **Ejecuta el chequeo de errores:**
```bash
python3 check_llm_errors.py
```

Deberías ver que OpenAI ya no falta en los análisis recientes.

3. **Ejecuta un análisis manual** desde el frontend de LLM Monitoring

4. **Espera al próximo cron job** (se ejecuta a las 4:00 AM)

---

## 📊 Costos

**Antes (gpt-5 inexistente):**
- Input: $15.00 / 1M tokens
- Output: $45.00 / 1M tokens

**Después (gpt-4o real):**
- Input: $2.50 / 1M tokens ⬇️ **83% más barato**
- Output: $10.00 / 1M tokens ⬇️ **78% más barato**

**Beneficio adicional:** ¡Usarás un modelo más barato y que funciona!

---

## 🚀 Aplicar en Railway

### Paso a Paso:

1. **SSH a Railway** o usa la consola web de Railway

2. **Navega al directorio del proyecto:**
```bash
cd /app
```

3. **Ejecuta el script de corrección:**
```bash
python3 fix_openai_model_config.py
```

4. **Verifica los logs:**
   - Deberías ver: ✅ CONFIGURACIÓN CORREGIDA EXITOSAMENTE
   - El próximo cron job usará gpt-4o automáticamente

5. **OPCIONAL - Ejecutar análisis manual inmediato:**
```bash
python3 -c "from services.llm_monitoring_service import analyze_all_active_projects; analyze_all_active_projects()"
```

---

## 📝 Notas

- **No es necesario reiniciar la aplicación** - Los cambios se aplican inmediatamente
- **El cron job automático** se ejecuta a las 4:00 AM todos los días
- **Los análisis manuales** desde el frontend también usarán el modelo correcto
- **La API key proporcionada es válida** - el problema era solo el modelo

---

## 🎉 Resultado Esperado

Después de aplicar la solución:
- ✅ OpenAI volverá a funcionar en los análisis automáticos
- ✅ Los snapshots incluirán datos de OpenAI (gpt-4o)
- ✅ El dashboard mostrará métricas de todos los LLMs
- ✅ Gastarás menos dinero por usar gpt-4o en lugar del inexistente gpt-5

---

**Fecha de diagnóstico:** 6 de noviembre de 2025  
**Problema identificado:** Modelo gpt-5 inexistente configurado en BD  
**Solución:** Cambiar a gpt-4o (modelo real disponible en OpenAI)

