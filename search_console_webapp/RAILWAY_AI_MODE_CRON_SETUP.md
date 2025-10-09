# 🚀 Configuración Cron AI Mode en Railway

## 📋 Instrucciones para crear Function Bun separado

### 1. Crear nuevo Function Bun en Railway

1. **Ve a Railway Dashboard**
2. **Click "New Project"** o añade al proyecto existente
3. **Selecciona "Function Bun"**
4. **Nombre**: `ai-mode-cron` (o similar)

### 2. Configurar Variables de Entorno

En el nuevo function bun, añade estas variables:

```
APP_URL = https://clicandseo.up.railway.app
CRON_TOKEN = K7r#92pQx!bZ4wLm
```

**Nota**: Usa las mismas variables que tu function bun de Manual AI

### 3. Código del Function Bun

Copia el contenido de `ai_mode_cron_function.js` en el editor de Railway:

```javascript
// AI Mode Daily Analysis Cron Function
// Para usar en Railway Function Bun separado

const appUrl = process.env.APP_URL ?? "https://clicandseo.up.railway.app";
const endpoint = `${appUrl}/ai-mode-projects/api/cron/daily-analysis?async=1`;

async function run() {
  console.log("🚀 AI Mode: Launching daily analysis:", endpoint);
  
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(process.env.CRON_TOKEN
          ? { Authorization: `Bearer ${process.env.CRON_TOKEN}` }
          : {}),
      },
      // Con async=1 debería responder 202 rápido
      signal: AbortSignal.timeout(60000),
    });

    const body = await res.text().catch(() => "");
    
    if (!res.ok) {
      throw new Error(`AI Mode Cron failed ${res.status}: ${body}`);
    }
    
    console.log("✅ AI Mode Cron OK:", body || "Accepted (async)");
    console.log(`📊 AI Mode analysis triggered successfully at ${new Date().toISOString()}`);
    
  } catch (error) {
    console.error("❌ AI Mode Cron Error:", error.message);
    throw error;
  }
}

// Ejecutar con manejo de errores
await run().catch((e) => {
  console.error("💥 AI Mode Cron failed:", e);
  process.exit(1);
});
```

### 4. Configurar Cron Schedule

En Railway, configura el cron para que se ejecute **diariamente a las 3:00 AM**:

**Cron Expression**: `0 3 * * *`

**Explicación**:
- `0` = minuto 0
- `3` = hora 3 (3:00 AM)
- `*` = cualquier día del mes
- `*` = cualquier mes
- `*` = cualquier día de la semana

### 5. Horarios Recomendados

Para evitar conflictos con Manual AI:

```
Manual AI Cron:  2:00 AM (ya configurado)
AI Mode Cron:    3:00 AM (nuevo)
```

**Diferencia**: 1 hora de separación para evitar sobrecarga

---

## 🔧 Configuración Alternativa: Mismo Function Bun

Si prefieres usar el **mismo function bun** para ambos sistemas, puedes modificar el código existente:

### Opción A: Ejecutar ambos en secuencia

```javascript
const appUrl = process.env.APP_URL ?? "https://clicandseo.up.railway.app";

async function runManualAI() {
  const endpoint = `${appUrl}/manual-ai/api/cron/daily-analysis?async=1`;
  console.log("🚀 Manual AI: Launching daily analysis:", endpoint);
  
  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(process.env.CRON_TOKEN
        ? { Authorization: `Bearer ${process.env.CRON_TOKEN}` }
        : {}),
    },
    signal: AbortSignal.timeout(60000),
  });

  const body = await res.text().catch(() => "");
  if (!res.ok) throw new Error(`Manual AI Cron failed ${res.status}: ${body}`);
  console.log("✅ Manual AI Cron OK:", body || "Accepted (async)");
}

async function runAIMode() {
  const endpoint = `${appUrl}/ai-mode-projects/api/cron/daily-analysis?async=1`;
  console.log("🚀 AI Mode: Launching daily analysis:", endpoint);
  
  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(process.env.CRON_TOKEN
        ? { Authorization: `Bearer ${process.env.CRON_TOKEN}` }
        : {}),
    },
    signal: AbortSignal.timeout(60000),
  });

  const body = await res.text().catch(() => "");
  if (!res.ok) throw new Error(`AI Mode Cron failed ${res.status}: ${body}`);
  console.log("✅ AI Mode Cron OK:", body || "Accepted (async)");
}

// Ejecutar ambos sistemas
async function run() {
  try {
    console.log("🔄 Starting daily analysis for both systems...");
    
    // Ejecutar Manual AI primero
    await runManualAI();
    
    // Esperar 30 segundos entre sistemas
    console.log("⏳ Waiting 30 seconds before AI Mode analysis...");
    await new Promise(resolve => setTimeout(resolve, 30000));
    
    // Ejecutar AI Mode después
    await runAIMode();
    
    console.log("🎉 Both systems analyzed successfully!");
    
  } catch (error) {
    console.error("💥 Cron failed:", error);
    throw error;
  }
}

await run().catch((e) => {
  console.error(e);
  process.exit(1);
});
```

### Opción B: Ejecutar en paralelo

```javascript
const appUrl = process.env.APP_URL ?? "https://clicandseo.up.railway.app";

async function runSystem(systemName, endpoint) {
  console.log(`🚀 ${systemName}: Launching daily analysis:`, endpoint);
  
  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(process.env.CRON_TOKEN
        ? { Authorization: `Bearer ${process.env.CRON_TOKEN}` }
        : {}),
    },
    signal: AbortSignal.timeout(60000),
  });

  const body = await res.text().catch(() => "");
  if (!res.ok) throw new Error(`${systemName} Cron failed ${res.status}: ${body}`);
  console.log(`✅ ${systemName} Cron OK:`, body || "Accepted (async)");
}

// Ejecutar ambos sistemas en paralelo
async function run() {
  try {
    console.log("🔄 Starting parallel daily analysis...");
    
    const manualAIEndpoint = `${appUrl}/manual-ai/api/cron/daily-analysis?async=1`;
    const aiModeEndpoint = `${appUrl}/ai-mode-projects/api/cron/daily-analysis?async=1`;
    
    await Promise.all([
      runSystem("Manual AI", manualAIEndpoint),
      runSystem("AI Mode", aiModeEndpoint)
    ]);
    
    console.log("🎉 Both systems analyzed successfully in parallel!");
    
  } catch (error) {
    console.error("💥 Cron failed:", error);
    throw error;
  }
}

await run().catch((e) => {
  console.error(e);
  process.exit(1);
});
```

---

## 🎯 Recomendación

**Te recomiendo la Opción 1**: **Function Bun separado**

**Ventajas**:
- ✅ Separación completa de sistemas
- ✅ Logs independientes
- ✅ Horarios flexibles
- ✅ Fácil debugging
- ✅ No afecta Manual AI si hay problemas

**Configuración recomendada**:
- **Manual AI**: 2:00 AM (actual)
- **AI Mode**: 3:00 AM (nuevo function bun)

---

## 📊 Verificación Post-Setup

### 1. Logs de Railway Function Bun

Buscar en logs:
```
🚀 AI Mode: Launching daily analysis: https://clicandseo.up.railway.app/ai-mode-projects/api/cron/daily-analysis?async=1
✅ AI Mode Cron OK: Accepted (async)
📊 AI Mode analysis triggered successfully at 2025-01-08T03:00:00.000Z
```

### 2. Verificar en App Principal

En `https://clicandseo.up.railway.app/ai-mode-projects`:
- ✅ Ver proyectos analizados automáticamente
- ✅ Ver resultados de análisis diario
- ✅ Ver eventos en timeline

### 3. Endpoint de Verificación

Puedes probar manualmente:
```bash
curl -X POST "https://clicandseo.up.railway.app/ai-mode-projects/api/cron/daily-analysis?async=1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer K7r#92pQx!bZ4wLm"
```

---

## 🔄 Flujo Completo

```
3:00 AM → Railway Function Bun ejecuta
       → POST /ai-mode-projects/api/cron/daily-analysis
       → Flask procesa todos los proyectos AI Mode
       → SerpApi análisis de keywords
       → Detección de menciones de marca
       → Análisis de sentimiento
       → Guardado en BD (ai_mode_*)
       → Logs de eventos
```

**Resultado**: Todos los proyectos AI Mode analizados automáticamente cada día a las 3:00 AM 🚀
