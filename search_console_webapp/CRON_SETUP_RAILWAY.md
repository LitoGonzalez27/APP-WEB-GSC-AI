# 🔧 Configuración del Cron en Railway

## ⚠️ IMPORTANTE: Configuración Requerida

Tu cron **NO funcionará automáticamente** hasta que configures el scheduler en Railway. Aquí tienes las opciones:

## 🚀 **Opción 1: Railway Cron Addon (Recomendado)**

### Paso 1: Instalar Cron Addon
```bash
railway add cron
```

### Paso 2: Configurar en Railway Dashboard
1. Ve a tu proyecto en Railway
2. Settings → Services → Cron Jobs
3. Click "Add Cron Job"
4. Configurar:
   - **Schedule**: `0 2 * * *` (diario a las 2:00 AM UTC)
   - **Command**: `python3 daily_analysis_cron.py`
   - **Timezone**: UTC (recomendado)

## 🛠️ **Opción 2: Scheduled Jobs en Railway**

### En Railway Dashboard:
1. Proyecto → Settings → Environment
2. Agregar variables:
   ```
   RAILWAY_CRON_SCHEDULE = 0 2 * * *
   RAILWAY_CRON_COMMAND = python3 daily_analysis_cron.py
   ```

## ⏰ **Opción 3: Cron Externo (GitHub Actions)**

Si Railway no soporta cron, puedes usar GitHub Actions:

### `.github/workflows/daily-cron.yml`:
```yaml
name: Daily Manual AI Analysis
on:
  schedule:
    - cron: '0 2 * * *'  # 2:00 AM UTC daily

jobs:
  run-analysis:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Railway Cron
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RAILWAY_API_TOKEN }}" \
            "https://tu-app.railway.app/manual-ai/api/cron/daily-analysis"
```

## 🧪 **Testing del Cron**

### 1. Test Manual desde la Interfaz
- Ve a Manual AI → Settings
- Click "Run Daily Analysis Now"
- Verifica que funciona sin errores

### 2. Test via API
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://tu-app.railway.app/manual-ai/api/cron/daily-analysis
```

### 3. Verificar Logs
```bash
railway logs --filter="manual_ai_cron"
```

## 📊 **Monitoreo**

### Dashboard Web
- Manual AI → Settings → "Last Execution"
- Verifica timestamp y estado

### Logs Railway
- Buscar: "MANUAL AI CRON JOB STARTED"
- Verificar: "ANÁLISIS DIARIO COMPLETADO"

## ⚠️ **Troubleshooting**

### Cron no ejecuta:
- ✅ Verificar que Cron Addon está instalado
- ✅ Verificar schedule syntax: `0 2 * * *`
- ✅ Verificar que `daily_analysis_cron.py` existe
- ✅ Verificar variables de entorno (DATABASE_URL, SERPAPI_KEY)

### Error en ejecución:
- Ver logs con `railway logs`
- Probar trigger manual primero
- Verificar que hay proyectos activos con keywords

## 🎯 **Estado Actual**

✅ **Listo para configurar**:
- Código del cron: ✅ Implementado
- Endpoint manual: ✅ Funcionando
- Procfile: ✅ Actualizado
- Error handling: ✅ Mejorado

❌ **Falta configurar**:
- Railway Cron Scheduler: ⚠️ **REQUERIDO**
- Proyectos activos: ⚠️ Crear al menos uno para probar

---

**Una vez configures el cron en Railway, el análisis se ejecutará automáticamente cada día a las 2:00 AM UTC** 🕐