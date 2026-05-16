// LLM Monitoring Watchdog Cron Function
// Para usar en Railway Function Bun (servicio separado).
// Cron recomendado: 0 6 * * * (cada día a las 06:00 UTC, ~2h después del
// run habitual del cron LLM, para detectar si el L/J/S no se completó).
//
// Lo único que hace: golpear /api/llm-monitoring/cron/watchdog. El backend
// se encarga de decidir si toca mandar email crítico o si todo está al día.

const appUrl = (process.env.APP_URL ?? "https://app.clicandseo.com").replace(/\/+$/, "");
const endpoint = `${appUrl}/api/llm-monitoring/cron/watchdog`;
const alertEndpoint = `${appUrl}/api/llm-monitoring/cron/alert`;
const notifyEmail =
  process.env.CRON_ALERT_EMAIL ??
  process.env.CRON_ALERTS_EMAIL ??
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
  console.log("👀 LLM Monitoring Watchdog: probing", endpoint);

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
      signal: AbortSignal.timeout(60000),
    });

    responseStatus = res.status;
    responseBody = await res.text().catch(() => "");

    if (!res.ok) {
      throw new Error(`Watchdog probe failed ${res.status}: ${responseBody}`);
    }

    // El backend ya manda email crítico si state != 'ok'. Aquí solo logueamos.
    console.log("✅ Watchdog response:", responseBody);
  } catch (error) {
    // El probe en sí ha fallado (red, timeout, backend caído). Eso ya es señal
    // de que algo va mal — mandamos email manual de fallback.
    console.error("❌ Watchdog probe error:", error.message);
    await sendCronAlert({
      job_name: "LLM Monitoring Watchdog",
      status: "failed",
      message: `Watchdog probe failed — backend may be down: ${error.message}`,
      endpoint,
      response_status: responseStatus,
      response_body: responseBody,
      run_at: new Date().toISOString(),
    });
    throw error;
  }
}

await run().catch((e) => {
  console.error("💥 Watchdog failed:", e);
  process.exit(1);
});
