// AI Mode Daily Analysis Cron Function
// Para usar en Railway Function Bun separado

const appUrl = process.env.APP_URL ?? "https://clicandseo.up.railway.app";
const endpoint = `${appUrl}/ai-mode-projects/api/cron/daily-analysis?async=1`;
const alertEndpoint = `${appUrl}/api/llm-monitoring/cron/alert`;
const notifyEmail =
  process.env.CRON_ALERT_EMAIL ??
  process.env.MODEL_DISCOVERY_EMAIL ??
  "info@soycarlosgonzalez.com";

async function sendCronAlert(payload) {
  try {
    await fetch(alertEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(process.env.CRON_TOKEN
          ? { Authorization: `Bearer ${process.env.CRON_TOKEN}` }
          : {}),
      },
      body: JSON.stringify({
        notify_email: notifyEmail,
        ...payload,
      }),
    });
  } catch (alertError) {
    console.error("⚠️ No se pudo enviar alerta por email:", alertError?.message);
  }
}

async function run() {
  console.log("🚀 AI Mode: Launching daily analysis:", endpoint);
  
  let responseStatus = null;
  let responseBody = "";
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

    responseStatus = res.status;
    responseBody = await res.text().catch(() => "");
    
    if (!res.ok) {
      throw new Error(`AI Mode Cron failed ${res.status}: ${responseBody}`);
    }
    
    console.log("✅ AI Mode Cron OK:", responseBody || "Accepted (async)");
    console.log(`📊 AI Mode analysis triggered successfully at ${new Date().toISOString()}`);
    
  } catch (error) {
    console.error("❌ AI Mode Cron Error:", error.message);
    await sendCronAlert({
      job_name: "AI Mode Daily Analysis",
      status: "failed",
      message: error.message,
      endpoint,
      response_status: responseStatus,
      response_body: responseBody,
      run_at: new Date().toISOString(),
    });
    throw error;
  }
}

// Ejecutar con manejo de errores
await run().catch((e) => {
  console.error("💥 AI Mode Cron failed:", e);
  process.exit(1);
});
