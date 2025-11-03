// LLM Monitoring Daily Analysis Cron Function
// Para usar en Railway Function Bun separado

const appUrl = process.env.APP_URL ?? "https://clicandseo.up.railway.app";
const endpoint = `${appUrl}/api/llm-monitoring/cron/daily-analysis?async=1`;

async function run() {
  console.log("🚀 LLM Monitoring: Launching daily analysis:", endpoint);
  
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
      throw new Error(`LLM Monitoring Cron failed ${res.status}: ${body}`);
    }
    
    console.log("✅ LLM Monitoring Cron OK:", body || "Accepted (async)");
    console.log(`📊 LLM Monitoring analysis triggered successfully at ${new Date().toISOString()}`);
    
  } catch (error) {
    console.error("❌ LLM Monitoring Cron Error:", error.message);
    throw error;
  }
}

// Ejecutar con manejo de errores
await run().catch((e) => {
  console.error("💥 LLM Monitoring Cron failed:", e);
  process.exit(1);
});


