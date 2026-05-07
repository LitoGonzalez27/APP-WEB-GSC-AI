// Quota Reset Cron Function
// To be deployed as a Railway Bun function service: function-bun-Quota-Reset
// Schedule: 30 1 * * *  (daily at 01:30 UTC, before all analysis crons)
//
// Why this exists:
//   Previously the daily quota reset was a Python cron declared under the
//   `crons` key of railway.json. Railway silently did not run it for ~50 days,
//   leaving paying customers with paused projects. The 4 cron jobs that
//   actually fire on Railway are dedicated Bun function services posting to
//   HTTP endpoints. This function follows the same proven pattern.

const appUrl = process.env.APP_URL ?? "https://app.clicandseo.com";
const endpoint = `${appUrl}/api/cron/quota-reset?async=1&triggered_by=bun_cron`;

async function run() {
  console.log("🚀 Quota Reset Cron: launching", endpoint);

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
      // Endpoint returns 202 quickly thanks to async=1
      signal: AbortSignal.timeout(60000),
    });

    const body = await res.text().catch(() => "");

    if (!res.ok) {
      throw new Error(`Quota Reset Cron failed ${res.status}: ${body}`);
    }

    console.log("✅ Quota Reset Cron OK:", body || "Accepted (async)");
    console.log(
      `📊 Quota reset triggered successfully at ${new Date().toISOString()}`
    );
  } catch (error) {
    console.error("❌ Quota Reset Cron Error:", error.message);
    throw error;
  }
}

await run().catch((e) => {
  console.error("💥 Quota Reset Cron failed:", e);
  process.exit(1);
});
