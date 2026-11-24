import { expect, test } from "@playwright/test";

// Station Navigator: platforms with confidence, the walk between them, feasibility, platform change, facility search.
test.beforeEach(async ({ request, page }) => {
  for (const id of ["station_connection", "bhopal_delhi_chandigarh", "normal_journey"]) await request.post(`/api/demo/${id}/reset`);
  await page.addInitScript(() => window.localStorage.setItem("lang", "en"));
});

test("26. journey → Station Navigator: platforms, walk, feasibility, prepare-to-get-off", async ({ page }) => {
  await page.goto("/#/journey/station_connection");
  await page.getByTestId("open-station").click();
  await expect(page.getByTestId("sn-arr-pf")).toContainText("Platform 4");
  await expect(page.getByTestId("sn-arr-pf-status")).toHaveText("Reported");
  await expect(page.getByTestId("sn-dep-pf")).toContainText("Platform 12");
  await expect(page.getByTestId("sn-dep-pf-status")).toHaveText("Confirmed");
  await expect(page.getByTestId("sn-verdict")).toContainText("Possible but tight");
  await expect(page.getByTestId("sn-verdict")).toContainText("Not a guarantee");
  await expect(page.getByTestId("sn-walk")).toContainText("min");
  await expect(page.getByTestId("sn-steps")).toContainText("North foot overbridge");
  await expect(page.getByTestId("sn-prepare")).toContainText("Verify the platform before moving");
  await expect(page.getByTestId("station-map")).toBeVisible();
});

test("27. platform change and step-free route recalculate the connection", async ({ page, request }) => {
  await page.goto("/#/station/station_connection");
  await expect(page.getByTestId("sn-dep-pf")).toContainText("Platform 12");
  await request.post("/api/demo/station_connection/platform", { data: { train_no: "90821", station: "NDLS", kind: "DEPARTURE", platform: 16 } });
  await page.reload();
  await expect(page.getByTestId("sn-dep-pf")).toContainText("Platform 16");
  await expect(page.getByTestId("sn-dep-pf-changed")).toContainText("changed from 12");
  await page.getByTestId("sn-profile-step_free").click();
  await expect(page.getByTestId("sn-lift-unknown")).toBeVisible();
  await expect(page.getByTestId("sn-verdict")).toContainText("High risk");
});

test("28. passenger enters the platform from the board; manual location", async ({ page }) => {
  await page.goto("/#/station/bhopal_delhi_chandigarh");
  await expect(page.getByTestId("sn-dep-pf-status")).toHaveText("Scheduled");
  await expect(page.getByTestId("sn-capped")).toContainText("not confirmed");
  await page.getByTestId("sn-enter-pf").fill("9");
  await page.getByTestId("sn-enter-go").click();
  await expect(page.getByTestId("sn-dep-pf")).toContainText("Platform 9");
  await expect(page.getByTestId("sn-dep-pf")).toContainText("entered by you from the board");
  await page.getByTestId("sn-location").selectOption("SIDE_PAHARGANJ");
  await expect(page.getByTestId("sn-steps")).toContainText("Paharganj");
  await expect(page.getByTestId("sn-loc-note")).toContainText("not tracked");
});

test("29. no station map and no platform: honest unavailable state", async ({ page }) => {
  await page.goto("/#/station/normal_journey");
  await expect(page.getByTestId("sn-no-map")).toBeVisible();
  await expect(page.getByTestId("sn-live-unavailable")).toContainText("Live platform information is currently unavailable");
});

test("30. find mode: pick a station, QR-style location, search a facility, route with steps", async ({ page }) => {
  await page.goto("/#/stations");
  await page.getByTestId("sn-station-NDLS").click();
  await expect(page.getByTestId("sn-need-location")).toBeVisible();
  await page.goto("/#/stations/NDLS?at=PF2");
  await expect(page.getByTestId("sn-loc-note")).toContainText("QR code");
  await page.getByTestId("sn-search").fill("luggage");
  await page.getByTestId("sn-dest-CLOAK_PHG").click();
  await expect(page.getByTestId("sn-steps")).toContainText("Cloakroom");
  await page.getByTestId("sn-search").fill("");
  await page.getByTestId("sn-type-EXIT").click();
  await expect(page.getByTestId("sn-results")).toContainText("Ajmeri Gate");
  await page.getByTestId("sn-search").fill("helipad");
  await expect(page.getByTestId("sn-results-empty")).toBeVisible();
});
