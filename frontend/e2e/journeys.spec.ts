import { expect, test } from "@playwright/test";

const ALL = ["normal_journey", "edge_three_hours", "waitlisted_family", "missed_connection"];

test.beforeEach(async ({ request, page }) => {
  for (const id of ALL) await request.post(`/api/demo/${id}/reset`);
  await page.addInitScript(() => window.localStorage.setItem("lang", "en"));
});

test("1. normal journey: calm, travel first, cancel preview from rules", async ({ page }) => {
  await page.goto("/#/");
  await page.getByTestId("demo-normal_journey").click();
  await expect(page.getByTestId("situation-calm")).toBeVisible();
  await page.getByRole("button", { name: "See my options" }).click();
  const plans = page.getByTestId("plans");
  await expect(plans.locator("li").first()).toHaveAttribute("data-testid", "plan-TRAVEL_AS_BOOKED");
  await expect(page.getByTestId("plan-CANCEL_NOW").getByTestId("amount")).toHaveText("₹1,960");
  await expect(page.getByTestId("rights-clock")).toBeVisible();
});

test("2. edge case: TDR right appears, then vanishes when the delay drops below 3h", async ({ page, request }) => {
  await page.goto("/#/journey/edge_three_hours");
  await expect(page.getByTestId("situation-alert")).toContainText("more than 3 hours");
  await page.getByTestId("see-options").click();
  await page.getByTestId("priority-money").click();
  const tdr = page.getByTestId("plan-FILE_TDR_LATE");
  await expect(tdr.getByTestId("amount")).toHaveText("₹1,180");
  await expect(tdr).toContainText("if approved");
  await request.post("/api/demo/edge_three_hours/events", { data: { train_no: "90501", type: "DELAY", delay_minutes: 170 } });
  await expect(page.getByTestId("plan-FILE_TDR_LATE")).toHaveCount(0, { timeout: 8000 });
});

test("3. waitlisted family: automatic refund + alternative, official steps, summary", async ({ page }) => {
  await page.goto("/#/options/waitlisted_family");
  const first = page.getByTestId("plans").locator("li").first();
  await expect(first).toHaveAttribute("data-testid", "plan-AUTO_REFUND_PLUS_ALTERNATIVE");
  await expect(first).toContainText("Seats not checked");
  await expect(page.getByTestId("plan-AUTO_REFUND_WAIT").getByTestId("amount")).toHaveText("₹2,140");
  await first.getByRole("button").click();
  await expect(page.getByTestId("steps")).toContainText("No need to cancel");
  await page.getByTestId("done").click();
  await expect(page.getByTestId("summary")).toContainText("not guaranteed");
});

test("4. missed connection in Hindi, deadline marked unverified", async ({ page }) => {
  await page.goto("/#/options/missed_connection");
  await page.getByRole("button", { name: "हिं" }).click();
  await expect(page.getByText("आपके विकल्प")).toBeVisible();
  const first = page.getByTestId("plans").locator("li").first();
  await expect(first).toHaveAttribute("data-testid", "plan-TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE");
  await expect(first).toContainText("90205");
  await expect(first).toContainText("पक्की नहीं");
});

test("5. invalid and unknown PNRs are rejected clearly", async ({ page }) => {
  await page.goto("/#/");
  await page.getByTestId("pnr-input").fill("123");
  await page.getByTestId("pnr-submit").click();
  await expect(page.getByRole("alert")).toContainText("exactly 10 digits");
  await page.getByTestId("pnr-input").fill("9999999999");
  await page.getByTestId("pnr-submit").click();
  await expect(page.getByRole("alert")).toContainText("not in the demo data");
});

test("6. stale data: no advice, official channel only", async ({ page, request }) => {
  await request.post("/api/demo/edge_three_hours/clock", { data: { advance_minutes: 40 } });
  await page.goto("/#/journey/edge_three_hours");
  await expect(page.getByTestId("situation-alert")).toContainText("out of date");
  await expect(page.getByTestId("see-options")).toHaveCount(0);
});
