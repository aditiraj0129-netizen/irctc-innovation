// Real screenshots of the Decide screen for the six decision scenarios (backend on :8000 serving the build).
// Usage: cd frontend && npm run build && (start backend on :8000) && node scripts/decide_screenshots.mjs
import { chromium } from "@playwright/test";
const B = process.env.BASE ?? "http://localhost:8000";
const OUT = "../submission/screenshots/decide";
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
async function shoot(name, path, viewport, lang = "en", full = true) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: viewport.width < 600 ? 2 : 1 });
  const page = await ctx.newPage();
  await page.addInitScript((l) => localStorage.setItem("lang", l), lang);
  await page.goto(B + "/#/" + path);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  await ctx.close();
}
const desk = { width: 1366, height: 900 }, mob = { width: 390, height: 844 };
const ids = ["decide_recover", "decide_worsening", "decide_fog", "decide_missed", "decide_refund", "decide_nextday"];
for (const id of ids) await fetch(`${B}/api/demo/${id}/reset`, { method: "POST" });
let i = 1;
for (const id of ids) await shoot(`0${i++}_${id}_desktop`, `decide/${id}`, desk);
await shoot("07_decide_missed_mobile", "decide/decide_missed", mob, "en", false);
await shoot("08_decide_worsening_hindi_mobile", "decide/decide_worsening", mob, "hi", false);
await shoot("09_whatif_links_to_decide", "whatif/decide_worsening", desk, "en", false);
await browser.close();
console.log("saved to", OUT);
