import { expect, test } from "@playwright/test";

// PREDICT -> DECIDE -> RECOVER: the decision screen on the six decision demo scenarios.
const IDS = ["decide_recover", "decide_worsening", "decide_fog", "decide_missed", "decide_refund", "decide_nextday"];

test.beforeEach(async ({ request, page }) => {
  for (const id of IDS) await request.post(`/api/demo/${id}/reset`);
  await page.addInitScript(() => window.localStorage.setItem("lang", "en"));
});

test("21. decide: every option card is filled, one is recommended, money compared", async ({ page }) => {
  await page.goto("/#/decide/decide_worsening");
  await expect(page.getByTestId("dz-head")).toContainText("Your connecting journey is at risk.");
  await expect(page.getByTestId("dz-risk")).toHaveText("High risk");
  for (const k of ["CONTINUE", "CANCEL", "OTHER_TRAIN", "UNRESERVED", "BUS", "NEXT_SERVICE"]) {
    const card = page.getByTestId(`card-${k}`);
    await expect(card).toBeVisible();
    await expect(card.getByTestId("card-status")).not.toHaveText("");
  }
  await expect(page.getByTestId("card-recommended")).toHaveCount(1);
  await expect(page.getByTestId("card-CONTINUE").getByTestId("card-recommended")).toBeVisible();
  await expect(page.getByTestId("dz-rec")).toContainText("Don't cancel your connecting ticket now");
  await expect(page.getByTestId("card-CANCEL").getByTestId("card-next")).toContainText("₹645");
  await expect(page.getByTestId("money-KEEP_AND_CLAIM")).toContainText("₹645");
  await expect(page.getByTestId("dz-congestion")).toContainText("90723");
  await expect(page.getByTestId("dz-congestion")).toContainText("other direction");
  await expect(page.getByTestId("dz-no-prob")).toBeVisible();
  await expect(page.getByTestId("card-OTHER_TRAIN")).toContainText("Seats: not checked");
});

test("22. decide: missed connection recommends another train and the TDR, without promising money", async ({ page }) => {
  await page.goto("/#/decide/decide_missed");
  await expect(page.getByTestId("dz-head")).toContainText("You will most likely miss your connecting train.");
  await expect(page.getByTestId("card-OTHER_TRAIN").getByTestId("card-recommended")).toBeVisible();
  await expect(page.getByTestId("dz-rec")).toContainText("file a TDR");
  await expect(page.getByTestId("dz-rec")).toContainText("if approved");
  await expect(page.getByTestId("card-BUS")).toContainText("not a real fare");
});

test("23. decide: fog warning shown as evidence, cancel-now vs later compared with the rule deadline", async ({ page }) => {
  await page.goto("/#/decide/decide_fog");
  await expect(page.getByTestId("dz-fog")).toContainText("dense fog warning on AGC-NDLS");
  await expect(page.getByTestId("dz-fog")).toContainText("expired");
  await page.goto("/#/decide/decide_refund");
  await expect(page.getByTestId("money-CANCEL_NOW")).toContainText("₹660");
  await expect(page.getByTestId("money-CANCEL_LATER")).toContainText("₹0");
  await expect(page.getByTestId("dz-rec")).toContainText("Decide by");
});

test("24. decide: next-day recovery shows Tatkal timing, never guaranteed; nothing-to-cancel is explained", async ({ page }) => {
  await page.goto("/#/decide/decide_nextday");
  await expect(page.getByTestId("card-NEXT_SERVICE").getByTestId("card-recommended")).toBeVisible();
  await expect(page.getByTestId("dz-rec")).toContainText("never guaranteed");
  await expect(page.getByTestId("card-CANCEL").getByTestId("card-reason")).toContainText("already left");
  await expect(page.getByTestId("card-OTHER_TRAIN").getByTestId("card-status")).toHaveText("None found");
});

test("25. decide in Hindi, and the journey alert leads to it", async ({ page, request }) => {
  await request.post("/api/demo/bhopal_delhi_chandigarh/reset");
  await request.post("/api/demo/bhopal_delhi_chandigarh/events", { data: { train_no: "90701", type: "DELAY", delay_minutes: 95 } });
  await page.goto("/#/journey/bhopal_delhi_chandigarh");
  await page.getByTestId("open-decide").click();
  await expect(page.getByTestId("dz-rec")).toContainText("90803");
  await page.getByRole("button", { name: "हिं" }).click();
  await expect(page.getByText("अब आप क्या कर सकते हैं?")).toBeVisible();
  await request.post("/api/demo/bhopal_delhi_chandigarh/reset");
});

test("31. screens agree: Journey and Disruption show the Decide outlook; What-If marks repeated results", async ({ page }) => {
  await page.goto("/#/journey/decide_worsening");
  await expect(page.getByTestId("outlook-warning")).toContainText("Your connecting journey is at risk.");
  await page.goto("/#/disruption/decide_worsening");
  await expect(page.getByTestId("dc-outlook")).toContainText("Your connecting journey is at risk.");
  await page.goto("/#/whatif/decide_worsening");
  await expect(page.getByTestId("wi-WAIT_30").getByTestId("wi-same")).toBeVisible();
  await expect(page.getByTestId("wi-BEST_NOW").getByTestId("wi-same")).toHaveCount(0);
});
