// @vitest-environment node
import { PGlite } from "@electric-sql/pglite";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const dashboardMigrationPath = fileURLToPath(
  new URL("../../../supabase/migrations/20260822154827_dashboard_v0.sql", import.meta.url),
);
const securityMigrationPath = fileURLToPath(
  new URL(
    "../../../supabase/migrations/20260823043739_secure_alembic_version.sql",
    import.meta.url,
  ),
);
const checkpointMigrationPath = fileURLToPath(
  new URL(
    "../../../supabase/migrations/20260823043937_add_ingestion_checkpoints.sql",
    import.meta.url,
  ),
);

describe("Supabase migration", () => {
  it("applies cleanly and enforces the stock/date uniqueness contract", async () => {
    const db = new PGlite();
    await db.exec("create role anon; create role authenticated;");
    await db.exec("create table public.alembic_version (version_num text primary key);");
    await db.exec(await readFile(dashboardMigrationPath, "utf8"));
    await db.exec(await readFile(securityMigrationPath, "utf8"));
    await db.exec(await readFile(checkpointMigrationPath, "utf8"));

    const tables = await db.query<{ table_name: string }>(
      "select table_name from information_schema.tables where table_schema = 'public' order by table_name",
    );
    expect(tables.rows.map((row) => row.table_name)).toEqual([
      "alembic_version",
      "daily_market_data",
      "ingestion_checkpoints",
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

    const rls = await db.query<{ relname: string; relrowsecurity: boolean }>(
      `select relname, relrowsecurity
         from pg_class
        where relname in ('alembic_version', 'ingestion_checkpoints')
        order by relname`,
    );
    expect(rls.rows).toEqual([
      { relname: "alembic_version", relrowsecurity: true },
      { relname: "ingestion_checkpoints", relrowsecurity: true },
    ]);
    await db.close();
  });
});
