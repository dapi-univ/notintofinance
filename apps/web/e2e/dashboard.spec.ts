import { expect, test, type Page } from "@playwright/test";

function createLargeStockUniverse() {
  return [
    {
      ticker: "AADI",
      company_name: "Adaro Andalan Indonesia Tbk.",
      sector: "Energy",
      subsector: null,
      latest_close: 9800,
      change: -100,
      change_percent: -1.01,
      latest_trade_date: "2026-08-21",
      sparkline: [9400, 9550, 9700, 9800],
      has_history: true,
    },
    ...Array.from({ length: 960 }, (_, index) => ({
      ticker: `T${(index + 1).toString().padStart(3, "0")}`,
      company_name: `Test IDX Company ${index + 1}`,
      sector: null,
      subsector: null,
      latest_close: 1000 + index,
      change: 10,
      change_percent: 1,
      latest_trade_date: "2026-08-21",
      sparkline: [1000, 1010, 1020],
      has_history: true,
    })),
    {
      ticker: "ZYRX",
      company_name: "Zyrexindo Mandiri Buana Tbk.",
      sector: null,
      subsector: null,
      latest_close: 100,
      change: 0,
      change_percent: 0,
      latest_trade_date: "2026-08-21",
      sparkline: [100, 100, 100],
      has_history: true,
    },
  ];
}

function createAadiHistory() {
  const start = Date.UTC(2026, 3, 25);
  const bars = Array.from({ length: 119 }, (_, index) => {
    const close = Math.round(
      9000 + Math.sin(index / 10) * 1300 + index * 5,
    );
    const date = new Date(start + index * 86_400_000)
      .toISOString()
      .slice(0, 10);
    return {
      date,
      open: close - 50,
      high: close + 150,
      low: close - 150,
      close,
      previous: close - 25,
      volume_shares: 7_100_000,
      volume_lots: 71_000,
      value_idr: 69_580_000_000,
      frequency: 4800,
      frequency_analyzer_raw_shares: 0.0000642,
      frequency_analyzer_raw_lots: 0.000000642,
      foreign_buy_shares: 2_000_000,
      foreign_sell_shares: 1_800_000,
      foreign_net_shares: 200_000,
      cumulative_foreign_net_shares: index * 200_000,
    };
  });
  bars[0] = { ...bars[0], low: 6700 };
  bars[40] = { ...bars[40], high: 11800 };
  bars[bars.length - 1] = {
    ...bars[bars.length - 1],
    date: "2026-08-21",
    open: 9925,
    high: 9925,
    low: 9750,
    close: 9800,
    previous: 9900,
  };
  return {
    ticker: "AADI",
    company_name: "Adaro Andalan Indonesia Tbk.",
    from: bars[0].date,
    to: "2026-08-21",
    latest_trade_date: "2026-08-21",
    is_stale: false,
    is_mock: false,
    source: "zapi",
    bars,
  };
}

async function routeLargeAadiUniverse(page: Page) {
  await page.route("**/stocks/AADI/history?*", (route) =>
    route.fulfill({ json: createAadiHistory() }),
  );
  await page.route("**/stocks", (route) =>
    route.fulfill({ json: createLargeStockUniverse() }),
  );
  await page.route("**/data/status", (route) =>
    route.fulfill({
      json: {
        latest_trade_date: "2026-08-21",
        expected_trade_date: "2026-08-21",
        is_stale: false,
        is_mock: false,
        provider: "zapi",
        repository: "database",
        ingestion: null,
        last_successful_ingestion: null,
      },
    }),
  );
}

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

  await page.getByLabel("Foreign Analysis").check();
  await expect(page.getByTestId("foreign-analysis-pane")).toBeVisible();
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

test("ticker search selects another database-backed symbol", async ({ page }) => {
  await page.goto("/app");
  await page.getByPlaceholder("Search ticker or company").fill("BMRI");
  await page.locator('[data-ticker="BMRI"]').click();
  await expect(page.getByTestId("active-ticker")).toHaveText("BMRI");
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

for (const viewport of [
  { label: "desktop", width: 1440, height: 900 },
  { label: "narrow desktop", width: 1100, height: 800 },
]) {
  test(`large-universe AADI watchlist remains virtual and stable on ${viewport.label}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await routeLargeAadiUniverse(page);
    const historyRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/history")) historyRequests.push(request.url());
    });

    await page.goto("/app?ticker=AADI");
    await expect(page.getByTestId("active-ticker")).toHaveText("AADI");
    await expect(page.locator(".symbol-header__quote > strong")).toHaveText(
      "9.800",
    );
    await expect(page.getByTestId("market-chart")).toBeVisible();

    const scrollElement = page.getByTestId("watchlist-scroll");
    await expect
      .poll(() => scrollElement.locator(".watchlist-item").count())
      .toBeGreaterThan(0);
    expect(await scrollElement.locator(".watchlist-item").count()).toBeLessThan(50);
    const initialScrollTop = await scrollElement.evaluate(
      (element) => element.scrollTop,
    );
    await scrollElement.hover();
    await page.mouse.wheel(0, 5600);
    await expect
      .poll(() => scrollElement.evaluate((element) => element.scrollTop))
      .toBeGreaterThan(initialScrollTop);
    await expect(page.locator('[data-ticker="T090"]')).toBeVisible();
    expect(await scrollElement.locator(".watchlist-item").count()).toBeLessThan(
      50,
    );

    await scrollElement.evaluate((element) => {
      element.scrollTop = 0;
      element.dispatchEvent(new Event("scroll"));
    });
    await expect(page.locator('[data-ticker="AADI"]')).toBeVisible();
    for (let index = 0; index < 5; index += 1) {
      await page.getByRole("button", { name: "Collapse watchlist" }).click();
      await page.getByRole("button", { name: "Open watchlist" }).click();
    }

    await expect(page.getByTestId("active-ticker")).toHaveText("AADI");
    await expect(page.locator('[data-ticker="AADI"]')).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.locator(".symbol-header__quote > strong")).toHaveText(
      "9.800",
    );
    await expect(page.locator("canvas").first()).toBeVisible();
    expect(historyRequests).toHaveLength(1);
  });
}
