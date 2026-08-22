// @vitest-environment node
import { PGlite } from "@electric-sql/pglite";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const migrationPath = fileURLToPath(
  new URL("../../../supabase/migrations/20260822154827_dashboard_v0.sql", import.meta.url),
);

describe("Supabase migration", () => {
  it("applies cleanly and enforces the stock/date uniqueness contract", async () => {
    const db = new PGlite();
    await db.exec("create role anon; create role authenticated;");
    await db.exec(await readFile(migrationPath, "utf8"));

    const tables = await db.query<{ table_name: string }>(
      "select table_name from information_schema.tables where table_schema = 'public' order by table_name",
    );
    expect(tables.rows.map((row) => row.table_name)).toEqual([
      "daily_market_data",
      "ingestion_runs",
      "stocks",
    ]);

    const stock = await db.query<{ id: number }>(
      "insert into public.stocks (ticker, company_name) values ('BBCA', 'Bank Central Asia Tbk.') returning id",
    );
    const id = stock.rows[0].id;
    const insertBar = `insert into public.daily_market_data
      (stock_id, trade_date, open, high, low, close, previous, volume_shares, value_idr, frequency, source)
      values (${id}, '2026-08-21', 8000, 8200, 7950, 8150, 8000, 25000000, 203750000000, 10000, 'test')`;
    await db.exec(insertBar);
    await expect(db.exec(insertBar)).rejects.toThrow();
    await db.close();
  });
});
