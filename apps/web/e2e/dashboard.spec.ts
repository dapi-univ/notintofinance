import { expect, test } from "@playwright/test";

test("critical Dashboard V0 workspace flow", async ({ page }) => {
  await page.goto("/app");

  await expect(page).toHaveTitle("KEJORA · Equity Research Tools");
  await expect(page.getByText("KEJORA", { exact: true })).toBeVisible();
  await expect(page.getByText("Equity Research Tools", { exact: true })).toBeVisible();
  await expect(page.getByLabel("KEJORA equity research tools").locator("path")).toHaveCount(3);
  await expect(page.getByTestId("active-ticker")).toHaveText("BBCA");
  await expect(page.getByTestId("market-chart")).toBeVisible();
  await expect(page.getByTestId("volume-pane")).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();

  const candlestickMode = page.getByRole("button", { name: "Candlestick", exact: true });
  const lineMode = page.getByRole("button", { name: "Line", exact: true });
  await expect(candlestickMode).toHaveAttribute("aria-pressed", "true");
  await lineMode.click();
  await expect(lineMode).toHaveAttribute("aria-pressed", "true");

  await page.locator('[data-ticker="ANTM"]').click();
  await expect(page.getByTestId("active-ticker")).toHaveText("ANTM");
  await expect(lineMode).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveURL(/ticker=ANTM/);
  await expect(page.getByRole("heading", { name: "Aneka Tambang Tbk." })).toBeVisible();

  await candlestickMode.click();
  await expect(candlestickMode).toHaveAttribute("aria-pressed", "true");

  await page.getByText("Indicators", { exact: true }).click();
  await page.getByLabel("Frequency Analyzer").check();
  await expect(page.getByTestId("frequency-analyzer-pane")).toBeVisible();
  await page.getByLabel("Frequency Analyzer").uncheck();
  await expect(page.getByTestId("frequency-analyzer-pane")).toBeHidden();
  await page.getByLabel("Frequency Analyzer").check();
  await expect(page.getByTestId("frequency-analyzer-pane")).toBeVisible();

  const volumeLabel = page.getByTestId("volume-pane");
  const volumeTopBeforeResize = await volumeLabel.evaluate((element) => element.getBoundingClientRect().top);
  const firstPaneSeparator = page.locator(
    '.market-chart__canvas div[style*="cursor: row-resize"][style*="height: 9px"]',
  ).first();
  const separatorBox = await firstPaneSeparator.boundingBox();
  expect(separatorBox).not.toBeNull();
  if (separatorBox) {
    await page.mouse.move(separatorBox.x + separatorBox.width / 2, separatorBox.y + separatorBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(separatorBox.x + separatorBox.width / 2, separatorBox.y + separatorBox.height / 2 + 48, { steps: 6 });
    await page.mouse.up();
  }
  await expect.poll(async () => volumeLabel.evaluate((element) => element.getBoundingClientRect().top)).toBeGreaterThan(
    volumeTopBeforeResize + 40,
  );

  const allHistoryRequest = page.waitForResponse((response) =>
    response.url().includes("/stocks/ANTM/history?timeframe=ALL"),
  );
  await page.getByRole("button", { name: "ALL", exact: true }).click();
  await expect(allHistoryRequest).resolves.toBeTruthy();

  const widthBefore = await page.getByTestId("market-chart").evaluate((element) => element.getBoundingClientRect().width);
  await page.getByRole("button", { name: "Collapse watchlist" }).click();
  const widthAfter = await page.getByTestId("market-chart").evaluate((element) => element.getBoundingClientRect().width);
  expect(widthAfter).toBeGreaterThan(widthBefore);

  await page.reload();
  await expect(page.getByTestId("active-ticker")).toHaveText("ANTM");
  await expect(page.getByTestId("market-chart")).toBeVisible();
});

test("narrow desktop watchlist keeps all quote columns within its panel", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.goto("/app");

  const watchlist = page.locator(".watchlist");
  await expect(watchlist).toBeVisible();
  const metrics = await watchlist.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
    rowOverflows: Array.from(element.querySelectorAll<HTMLElement>(".watchlist-item")).some(
      (row) => row.scrollWidth > row.clientWidth,
    ),
  }));

  expect(metrics.scrollWidth).toBe(metrics.clientWidth);
  expect(metrics.rowOverflows).toBe(false);
});
