import { expect, test } from "@playwright/test";

// E2E tests for the upgrade features. The original six tests live in journeys.spec.ts, unchanged.
const ALL = ["normal_journey", "edge_three_hours", "waitlisted_family", "missed_connection", "family_confirmed", "family_waitlisted"];

test.beforeEach(async ({ request, page }) => {
  for (const id of ALL) {
    await request.post(`/api/demo/${id}/reset`);
    await request.put(`/api/journeys/${id}/preferences`, { data: {} });
  }
  await page.addInitScript(() => window.localStorage.setItem("lang", "en"));
});

test("7. digital twin: connection not possible, then what-if and recommendation", async ({ page }) => {
  await page.goto("/#/journey/missed_connection");
  await expect(page.getByTestId("twin-status")).toHaveText("Journey broken: act now");
  await expect(page.getByTestId("leg-state-2")).toHaveText("Likely missed");
  await expect(page.getByTestId("transfer")).toContainText("Change not possible");
  await page.getByTestId("nav-options").click();
  await expect(page.getByTestId("recommendation")).toContainText("Arrives earlier");
  await expect(page.getByTestId("counterfactuals")).toContainText("If you wait 30 min");
  await page.getByTestId("nav-whatif").click();
  await expect(page.getByTestId("wi-BEST_NOW").getByTestId("wi-money")).toContainText("₹455");
  await expect(page.getByTestId("wi-CANCEL_NOW")).toBeVisible();
  // Waiting 7 hours makes the 09:45 train impossible to book: the simulator says options are lost.
  await page.getByTestId("wait-slider").fill("420");
  await expect(page.getByTestId("wi-WAIT_30").getByTestId("lost-options")).toBeVisible();
});

test("8. passenger rights wallet: stages, rule metadata, claim tracking, export", async ({ page }) => {
  await page.goto("/#/wallet/edge_three_hours");
  await expect(page.getByTestId("wallet-disclaimer")).toContainText("not guaranteed");
  const tdr = page.getByTestId("wallet-TDR_LATE_RUNNING");
  await expect(tdr.getByTestId("stage")).toHaveText("You can file");
  const cancel = page.getByTestId("wallet-CANCELLATION");
  await cancel.getByTestId("rule-details").locator("summary").click();
  await expect(cancel).toContainText("not yet officially notified");
  await expect(cancel).toContainText("2026-04-announced.1");
  await tdr.getByTestId("mark-FILED").click();
  await expect(tdr.getByTestId("stage")).toHaveText("Filed by you");
  await expect(page.getByTestId("wallet-history")).toContainText("Claim update");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("wallet-export").click()]);
  expect(dl.suggestedFilename()).toContain(".txt");
});

test("9. family group: divergence detected, together option first, split labelled", async ({ page }) => {
  await page.goto("/#/more/family_confirmed");
  await page.getByTestId("more-family").click();
  await expect(page.getByTestId("divergence")).toContainText("different ticket status");
  const first = page.getByTestId("group-options").locator("li").first();
  await expect(first.getByTestId("suitability")).toHaveText("Whole group");
  await expect(page.getByTestId("group-SPLIT_ALTERNATIVE").first().getByTestId("suitability")).toHaveText("Splits the group");
  await expect(page.getByTestId("family-timeline")).toContainText("Senior");
});

test("10. offline card: saved snapshot shown when offline, labelled not live", async ({ page, context }) => {
  await page.goto("/#/offline/missed_connection");
  await expect(page.getByTestId("off-label")).toContainText("not live");
  await expect(page.getByTestId("offline-card")).toContainText("81xxxxxx04");
  await expect(page.getByTestId("offline-card")).not.toContainText("8100000004");
  await page.getByTestId("off-save").click();
  await expect(page.getByTestId("off-saved-at")).toBeVisible();
  await context.setOffline(true);
  await expect(page.getByTestId("offline-banner")).toBeVisible();
  await expect(page.getByTestId("offline-card")).toContainText("90205");
  await expect(page.getByTestId("off-emergency")).toContainText("139");
  await context.setOffline(false);
});

test("11. assistant: Hinglish question answered from the rules engine, without any AI key", async ({ page }) => {
  await page.goto("/#/assistant/edge_three_hours");
  await page.getByTestId("ask-input").fill("Meri train teen ghante late hai, ab kya karun?");
  await page.getByTestId("ask-submit").click();
  const reply = page.getByTestId("ask-reply");
  await expect(reply).toContainText("₹1,180");
  await expect(reply).toContainText("TDR-LATE-3H");
  await expect(reply).toContainText("rules engine");
  await page.getByTestId("ask-as_q3").click();
  await expect(reply).toContainText("17:10");
});

test("12. community reports: unverified, personal data rejected, never change the options", async ({ page, request }) => {
  const before = await (await request.get("/api/journeys/missed_connection/assessment")).json();
  await page.goto("/#/community/missed_connection");
  await expect(page.getByTestId("cm-unverified")).toContainText("never change");
  await expect(page.getByTestId("reports")).toContainText("Reports disagree");
  await page.getByTestId("cm-station").fill("PNBE");
  await page.getByTestId("cm-note").fill("call 9876543210");
  await page.getByTestId("cm-send").click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByTestId("cm-note").fill("Lift not working");
  await page.getByTestId("cm-type").selectOption("ACCESS_PROBLEM");
  await page.getByTestId("cm-send").click();
  await expect(page.getByTestId("reports")).toContainText("Lift not working");
  const after = await (await request.get("/api/journeys/missed_connection/assessment")).json();
  expect(after.plans.map((p: any) => [p.id, p.money_back_paise])).toEqual(before.plans.map((p: any) => [p.id, p.money_back_paise]));
});

test("13. accessibility needs change the transfer analysis", async ({ page }) => {
  await page.goto("/#/prefs/missed_connection");
  await page.getByTestId("pf-step-free").check();
  await page.getByTestId("pf-senior").check();
  await page.getByTestId("pf-save").click();
  await expect(page.getByRole("status")).toContainText("Saved");
  await page.getByTestId("nav-options").click();
  await expect(page.getByTestId("transfer-badges").first()).toContainText("PNBE");
  await page.goto("/#/resilience/missed_connection");
  await expect(page.getByTestId("res-label")).toHaveText("Experimental");
  await expect(page.getByTestId("factor-CONNECTION_BUFFER")).toBeVisible();
});

test("14. Hindi works on the new screens", async ({ page }) => {
  await page.goto("/#/whatif/missed_connection");
  await page.getByRole("button", { name: "हिं" }).click();
  await expect(page.getByText("अगर-तो सिम्युलेटर")).toBeVisible();
  await page.getByTestId("nav-wallet").click();
  await expect(page.getByTestId("wallet-disclaimer")).toContainText("पक्के नहीं");
});
