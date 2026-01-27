// LLM Model Discovery Cron Function
// Para usar en Railway Function Bun
// Ejecutar cada 2 semanas para detectar nuevos modelos LLM
//
// Configuración CRON recomendada: 0 9 1,15 * * (días 1 y 15 de cada mes a las 9:00 AM)

const appUrl = process.env.APP_URL ?? "https://clicandseo.up.railway.app";
const endpoint = `${appUrl}/api/llm-monitoring/cron/model-discovery`;
const alertEndpoint = `${appUrl}/api/llm-monitoring/cron/alert`;

// Email de notificación
const notifyEmail = process.env.MODEL_DISCOVERY_EMAIL ?? "info@soycarlosgonzalez.com";
const alertEmail =
  process.env.CRON_ALERT_EMAIL ??
  process.env.MODEL_DISCOVERY_EMAIL ??
  "info@soycarlosgonzalez.com";

// Si true, activa automáticamente los nuevos modelos
const autoUpdate = process.env.AUTO_UPDATE_MODELS ?? "false";

async function run() {
    console.log("🔍 LLM Model Discovery: Starting...");
    console.log("   Endpoint:", endpoint);
    console.log("   Notify email:", notifyEmail);
    console.log("   Auto-update:", autoUpdate);

    let responseStatus = null;
    let responseBody = "";
    try {
        const url = `${endpoint}?notify_email=${encodeURIComponent(notifyEmail)}&auto_update=${autoUpdate}`;
        
        const res = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
                ...(process.env.CRON_TOKEN
                    ? { Authorization: `Bearer ${process.env.CRON_TOKEN}` }
                    : {}),
            },
        });

        responseStatus = res.status;
        responseBody = await res.text();
        console.log("📡 Response status:", res.status);

        if (!res.ok) {
            console.error("❌ Error response:", responseBody);
            throw new Error(`HTTP ${res.status}: ${responseBody}`);
        }

        let data;
        try {
            data = JSON.parse(responseBody);
        } catch {
            data = { raw: responseBody };
        }

        console.log("✅ Model Discovery completed!");
        console.log("   Discovered:", data.discovered_count || 0, "models");
        console.log("   New models:", data.new_models?.length || 0);
        console.log("   Added to DB:", data.models_added?.length || 0);
        console.log("   Email sent:", data.email_sent ? "Yes" : "No");
        
        if (data.new_models && data.new_models.length > 0) {
            console.log("\n🆕 New models found:");
            data.new_models.forEach(m => {
                console.log(`   • ${m.provider}: ${m.model_id}`);
            });
        }
        
        if (data.current_models) {
            console.log("\n📊 Current models in use:");
            Object.entries(data.current_models).forEach(([provider, model]) => {
                console.log(`   • ${provider}: ${model}`);
            });
        }

        if (data.errors && data.errors.length > 0) {
            console.log("\n⚠️ Errors during discovery:");
            data.errors.forEach(err => console.log(`   • ${err}`));
        }

        return data;

    } catch (error) {
        console.error("❌ Model Discovery failed:", error.message);
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
                    notify_email: alertEmail,
                    job_name: "LLM Model Discovery",
                    status: "failed",
                    message: error.message,
                    endpoint,
                    response_status: responseStatus,
                    response_body: responseBody,
                    run_at: new Date().toISOString(),
                }),
            });
        } catch (alertError) {
            console.error("⚠️ No se pudo enviar alerta por email:", alertError?.message);
        }
        throw error;
    }
}

run();

