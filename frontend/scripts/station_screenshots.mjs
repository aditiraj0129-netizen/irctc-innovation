// Real screenshots of the Station Navigator (backend on :8000 serving the build).
// Usage: cd frontend && npm run build && (start backend on :8000) && node scripts/station_screenshots.mjs
import { chromium } from "@playwright/test";
const B = process.env.BASE ?? "http://localhost:8000";
const OUT = "../submission/screenshots/station";
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const desk = { width: 1366, height: 900 }, mob = { width: 390, height: 844 };
async function shoot(name, path, viewport, lang = "en", act = async () => {}, full = true) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: viewport.width < 600 ? 2 : 1 });
  const page = await ctx.newPage();
  await page.addInitScript((l) => localStorage.setItem("lang", l), lang);
  await page.goto(B + "/#/" + path);
  await page.waitForTimeout(1200);
  await act(page);
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  await ctx.close();
}
const reset = (id) => fetch(`${B}/api/demo/${id}/reset`, { method: "POST" });
for (const id of ["station_connection", "bhopal_delhi_chandigarh", "normal_journey"]) await reset(id);

await shoot("01_ndls_journey_navigator_desktop", "station/station_connection", desk);
await shoot("02_ndls_journey_navigator_mobile", "station/station_connection", mob, "en", async () => {}, false);
await shoot("03_hwh_find_metro", "stations/HWH?at=PF1", desk, "en", async (p) => {
  await p.getByTestId("sn-type-METRO").click();
  await p.locator('[data-testid^="sn-dest-"]').first().click();
});
await shoot("04_csmt_find_exit_step_free", "stations/CSMT?at=PF2", desk, "en", async (p) => {
  await p.getByTestId("sn-type-EXIT").click();
  await p.locator('[data-testid^="sn-dest-"]').first().click();
  const sf = p.getByTestId("sn-profile-step_free");
  if (await sf.count()) await sf.first().click();
});
await fetch(`${B}/api/demo/station_connection/platform`, { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ train_no: "90821", station: "NDLS", kind: "DEPARTURE", platform: 16 }) });
await shoot("05_platform_change_step_free", "station/station_connection", desk, "en", async (p) => {
  await p.getByTestId("sn-profile-step_free").click();
});
await reset("station_connection");
await shoot("06_no_map_unavailable", "station/normal_journey", desk);
await shoot("07_hindi_mobile", "station/station_connection", mob, "hi", async () => {}, false);
await shoot("08_scheduled_only_capped", "station/bhopal_delhi_chandigarh", desk);
await browser.close();
console.log("saved to", OUT);
