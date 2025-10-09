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
