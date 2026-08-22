import { expect, test } from "@playwright/test";

test("critical Dashboard V0 workspace flow", async ({ page }) => {
  await page.goto("/app");

  await expect(page.getByTestId("active-ticker")).toHaveText("BBCA");
  await expect(page.getByTestId("market-chart")).toBeVisible();
  await expect(page.getByTestId("volume-pane")).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();

  await page.locator('[data-ticker="ANTM"]').click();
  await expect(page.getByTestId("active-ticker")).toHaveText("ANTM");
  await expect(page).toHaveURL(/ticker=ANTM/);
  await expect(page.getByRole("heading", { name: "Aneka Tambang Tbk." })).toBeVisible();

  await page.getByText("Indicators", { exact: true }).click();
  await page.getByLabel("Frequency Analyzer").check();
  await expect(page.getByTestId("frequency-analyzer-pane")).toBeVisible();

  const widthBefore = await page.getByTestId("market-chart").evaluate((element) => element.getBoundingClientRect().width);
  await page.getByRole("button", { name: "Collapse watchlist" }).click();
  const widthAfter = await page.getByTestId("market-chart").evaluate((element) => element.getBoundingClientRect().width);
  expect(widthAfter).toBeGreaterThan(widthBefore);

  await page.reload();
  await expect(page.getByTestId("active-ticker")).toHaveText("ANTM");
  await expect(page.getByTestId("market-chart")).toBeVisible();
});
