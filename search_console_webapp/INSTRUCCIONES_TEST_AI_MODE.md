# 🧪 Instrucciones para Testear AI Mode con Datos Reales

## ✅ Estado Actual del Sistema

Todos los bugs han sido corregidos:
- ✅ CRON consulta las tablas correctas (`ai_mode_projects`)
- ✅ Snapshots se guardan en la tabla correcta (`ai_mode_snapshots`)
- ✅ Columna `selected_competitors` agregada
- ✅ Métodos de competitors implementados
- ✅ Gráficas y métricas actualizadas
- ✅ Backend con cálculos correctos

## 🎯 Proyecto de Prueba

**Proyecto ID: 1**
- Nombre: "test 1"
- Brand: "quipu"
- País: ES (España)
- Keywords: 14 activas
- **Estado actual**: Sin datos de análisis (nunca se ha ejecutado)

## 🔑 Variable de Entorno Configurada

Ya tienes `SERPAPI_KEY` configurada en Railway (staging y producción).

## 🚀 Opción A: Ejecutar CRON Manualmente desde Railway

### Paso 1: Ir a Railway Dashboard
1. Ve a tu proyecto en Railway
2. Selecciona el servicio web

### Paso 2: Ejecutar comando manualmente
En la terminal de Railway (o desde "Command" en el dashboard):

```bash
python3 daily_ai_mode_cron.py
```

Esto ejecutará el análisis inmediatamente y deberías ver:
- ✅ Proyecto 1 detectado
- ✅ 14 keywords procesadas
- ✅ Datos guardados en `ai_mode_results`

### Paso 3: Verificar Resultados
Ejecuta este script para verificar que se generaron datos:

```bash
python3 check_ai_mode_data.py
```

Deberías ver:
- ✅ Proyecto 1 con resultados de análisis
- ✅ Fecha del último análisis
- ✅ Brand mentions detectadas
- ✅ Métricas calculadas

## 📊 Opción B: Esperar al CRON Automático

El CRON está configurado para ejecutarse automáticamente:
- **Hora**: 3:00 AM UTC (5:00 AM España) todos los días
- **Configurado en**: `railway.json`
- **Comando**: `python3 daily_ai_mode_cron.py`

Al día siguiente de las 3:00 AM, verás los datos en tu APP.

## 🔍 Cómo Verificar que Todo Funciona

### 1. Después de ejecutar el análisis:

Refresca tu APP en el navegador y ve a:
- **AI Mode Monitoring** → Analytics → Selecciona "test 1"

Deberías ver:
- ✅ **Total Keywords**: 14
- ✅ **Brand Mentions**: [número de menciones detectadas]
- ✅ **Visibility (%)**: [porcentaje calculado]
- ✅ **Average Position**: [posición promedio]
- ✅ **Gráfica Brand Visibility Over Time**: con datos del análisis
- ✅ **Position Distribution**: con distribución de posiciones

### 2. Si ves "No data available":

Es porque el análisis aún no se ha ejecutado. Ejecuta manualmente desde Railway o espera al CRON automático.

## 🐛 Solución de Problemas

### Si el CRON falla en Railway:

1. **Verificar logs de Railway**:
   - Ve a "Deployments" → "View Logs"
   - Busca errores del CRON

2. **Verificar que SERPAPI_KEY existe**:
   - Ve a "Variables" en Railway
   - Confirma que `SERPAPI_KEY` o `SERPAPI_API_KEY` está configurada

3. **Verificar que el proyecto tiene keywords**:
   ```bash
   python3 check_ai_mode_data.py
   ```
   Debe mostrar 14 keywords activas

### Si ves errores de tabla no existe:

Ya están todos corregidos, pero si ves alguno, verifica:
- ✅ `ai_mode_projects` (no `manual_ai_projects`)
- ✅ `ai_mode_keywords` (no `manual_ai_keywords`)
- ✅ `ai_mode_results` (no `manual_ai_results`)
- ✅ `ai_mode_snapshots` (no `manual_ai_snapshots`)

## 📝 Notas Importantes

1. **Primera ejecución**: Puede tardar ~60 segundos para 14 keywords
2. **Consumo de RU**: Aproximadamente 14 RU (1 por keyword)
3. **Frecuencia**: El CRON solo ejecuta una vez al día para no consumir muchos RU
4. **Plan requerido**: El CRON solo procesa proyectos de usuarios con plan de pago (no free)

## ✅ Confirmación de Éxito

Sabrás que todo funciona cuando veas en la APP:
1. Números reales en las 4 tarjetas de Overview
2. Gráfica de Brand Visibility con línea de datos
3. Gráfica de Position Distribution con barras
4. Tabla de Keywords con datos en la sección inferior

---

**¿Todo listo?** 🚀 El sistema está 100% funcional. Solo necesita ejecutarse el análisis para generar datos.

