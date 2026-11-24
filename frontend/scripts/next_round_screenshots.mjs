// Takes real screenshots of the running app (backend on :8000 serving the built frontend).
// Usage: cd frontend && npm run build && (start backend on :8000) && node scripts/next_round_screenshots.mjs
import { chromium } from "@playwright/test";
const B = process.env.BASE ?? "http://localhost:8000";
const OUT = "../submission/screenshots/next-round";
const BDC = "bhopal_delhi_chandigarh";
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const post = (p, d) => fetch(B + p, { method: "POST", headers: { "Content-Type": "application/json" }, body: d ? JSON.stringify(d) : undefined });

async function shoot(name, viewport, path, prep, full = true) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: viewport.width < 600 ? 2 : 1 });
  const page = await ctx.newPage();
  await page.addInitScript(() => { localStorage.setItem("lang", "en"); localStorage.setItem("aglaKadam.myJourneys", JSON.stringify(["bhopal_delhi_chandigarh", "missed_connection", "normal_journey"])); });
  await page.goto(B + "/#/" + path);
  if (prep) await prep(page);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  await ctx.close();
}
const desk = { width: 1366, height: 860 }, mob = { width: 390, height: 844 };
for (const id of [BDC, "missed_connection", "normal_journey"]) await post(`/api/demo/${id}/reset`);
await shoot("01_home_desktop", desk, "");
await shoot("02_journey_at_risk_desktop", desk, `journey/${BDC}`);
await post(`/api/demo/${BDC}/events`, { train_no: "90701", type: "DELAY", delay_minutes: 95 });
await shoot("03_journey_broken_desktop", desk, `journey/${BDC}`);
await shoot("04_disruption_centre_desktop", desk, `disruption/${BDC}`);
await shoot("05_whatif_compare_desktop", desk, `whatif/${BDC}`);
await shoot("06_copilot_desktop", desk, `copilot/${BDC}`, async (p) => {
  await p.getByTestId("cp-input").fill("What if I wait 45 minutes?"); await p.getByTestId("cp-send").click();
  await p.getByTestId("cp-reply").waitFor();
  await p.getByTestId("cp-input").fill("Explain my refund rights in simple Hindi"); await p.getByTestId("cp-send").click();
  await p.getByTestId("cp-reply").nth(1).waitFor();
}, false);
await shoot("07_wallet_desktop", desk, `wallet/${BDC}`);
await shoot("08_settings_desktop", desk, "settings");
await shoot("09_home_mobile", mob, "", null, false);
await shoot("10_disruption_mobile", mob, `disruption/${BDC}`, null, false);
await shoot("11_journey_hindi_mobile", mob, `journey/${BDC}`, async (p) => { await p.getByRole("button", { name: "हिं" }).click(); }, false);
await post(`/api/demo/${BDC}/reset`);
await browser.close();
console.log("saved to", OUT);
