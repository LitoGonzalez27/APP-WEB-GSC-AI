# Manual AI Analysis - Sistema Cron Diario

## 📋 Descripción

El sistema Manual AI Analysis incluye un **cron job diario** que automáticamente analiza todos los proyectos activos cada día. Esto es **fundamental** para generar datos históricos y tendencias de visibilidad en AI Overview.

## 🎯 ¿Por qué es Importante?

- **Datos Históricos**: Acumula datos día a día para mostrar tendencias
- **Automatización**: No requiere intervención manual diaria
- **Escalabilidad**: Maneja múltiples proyectos con hasta 200 keywords cada uno
- **Consistencia**: Análisis a la misma hora cada día

## ⚙️ Configuración del Cron

### 🔹 Opción 1: Cron System (Linux/macOS)

```bash
# Editar crontab
crontab -e

# Agregar línea para ejecutar diariamente a las 2:00 AM
0 2 * * * cd /path/to/your/app && python3 daily_analysis_cron.py >> /var/log/manual_ai_cron.log 2>&1
```

### 🔹 Opción 2: Railway Cron Addon

```bash
# Instalar Railway Cron addon
railway add cron

# Configurar en Railway Dashboard:
# Schedule: 0 2 * * * (diario a las 2:00 AM)
# Command: python3 daily_analysis_cron.py
```

### 🔹 Opción 3: Ejecución Manual/Testing

```bash
# Desde la aplicación web (endpoint)
POST /manual-ai/api/cron/daily-analysis

# Desde línea de comandos
python3 daily_analysis_cron.py
```

## 📊 Funcionamiento del Cron

### ✅ Lo que hace cada día:

1. **Busca proyectos activos** con keywords configuradas
2. **Verifica si ya se analizó hoy** (evita duplicados)
3. **Ejecuta análisis SERP** para cada keyword del proyecto
4. **Detecta AI Overview** usando el motor existente
5. **Guarda resultados** en base de datos
6. **Crea snapshots diarios** para métricas
7. **Registra eventos** de análisis completado/fallido

### 📋 Logs del Cron

```bash
🕒 === INICIANDO ANÁLISIS DIARIO AUTOMÁTICO ===
📊 Found 3 active projects for daily analysis
🚀 Starting daily analysis for project 1 (Quipu SEO) - 45 keywords
✅ Completed daily analysis for project 1: 45 keywords processed
🚀 Starting daily analysis for project 2 (CompetitorWatch) - 120 keywords  
✅ Completed daily analysis for project 2: 120 keywords processed
⏭️ Project 3 (TestProject) already analyzed today, skipping
🏁 === ANÁLISIS DIARIO COMPLETADO ===
📊 Total proyectos: 3
✅ Exitosos: 2
❌ Fallidos: 0
⏭️ Omitidos (ya analizados): 1
```

## 🛡️ Características de Seguridad

- **Prevención de duplicados**: No ejecuta el mismo proyecto múltiples veces en un día
- **Manejo de errores**: Continúa con otros proyectos si uno falla
- **Logging detallado**: Para debugging y monitoreo
- **Timeouts apropiados**: Maneja proyectos de hasta 200 keywords
- **Eventos de error**: Registra fallos en el dashboard

## ⏰ Timing Recomendado

- **2:00 AM - 4:00 AM**: Horas de menor tráfico
- **Consideración**: 200 keywords ≈ 30-45 minutos por proyecto
- **Múltiples proyectos**: Pueden tomar 2-3 horas en total

## 🔍 Monitoreo

### 📋 Dashboard Web
- Ver última ejecución del cron en cada proyecto
- Estadísticas de análisis diarios
- Eventos de éxito/error

### 📋 Logs del Sistema
```bash
# Ver logs en Railway
railway logs

# Logs locales
tail -f /var/log/manual_ai_cron.log
```

## 🚨 Troubleshooting

### ❌ Error: "ImportError"
```bash
# Asegurar que estás en el directorio correcto
cd /path/to/your/app
python3 daily_analysis_cron.py
```

### ❌ Error: "Database connection"
```bash
# Verificar variables de entorno
echo $DATABASE_URL
echo $SERPAPI_KEY
```

### ❌ Error: "SERP API rate limit"
```bash
# Verificar límites de SerpAPI
# Considerar distribuir análisis en horarios diferentes
```

## 📈 Escalabilidad

- **5 proyectos × 100 keywords** = ~2-3 horas diarias
- **10 proyectos × 200 keywords** = ~5-6 horas diarias
- **Recomendación**: Monitorear uso de SerpAPI y tiempo de ejecución

## 🔄 Actualización Manual

Si necesitas forzar un análisis:

```bash
# Opción 1: Script directo
python3 daily_analysis_cron.py

# Opción 2: Endpoint API
curl -X POST https://your-app.railway.app/manual-ai/api/cron/daily-analysis
```

---

**¡El cron diario es el corazón del sistema Manual AI Analysis!** 🎯