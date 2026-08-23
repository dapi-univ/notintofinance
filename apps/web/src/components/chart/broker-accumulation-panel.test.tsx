import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { BrokerAccumulationResponse } from "@/lib/api/types";

import { BrokerAccumulationPanel } from "./broker-accumulation-panel";
import { IndicatorMenu } from "./indicator-menu";

const populated: BrokerAccumulationResponse = {
  ticker: "BBCA",
  from: "2026-08-20",
  to: "2026-08-21",
  source_scope: "top_n",
  source_top_n: 10,
  coverage_note: "TOP-10 OBSERVED · NOT FULL MARKET",
  gateway: "zapi",
  source_provider: "pluang",
  coverage: {
    expected_sessions: ["2026-08-20", "2026-08-21"],
    covered_sessions: ["2026-08-20"],
    missing_sessions: ["2026-08-21"],
    state: "partial",
  },
  brokers: [
    {
      broker_code: "AK",
      broker_name: "Verified Broker",
      classification: "FOREIGN",
      observed_top_n_buy_value: 1000,
      observed_top_n_sell_value: 400,
      observed_top_n_net_value: 600,
      observed_top_n_buy_lots: 10,
      observed_top_n_sell_lots: 4,
      observed_top_n_net_lots: 6,
      observed_top_n_buy_shares: 1000,
      observed_top_n_sell_shares: 400,
      observed_top_n_net_shares: 600,
      buy_appearances: 1,
      sell_appearances: 1,
      latest_buy_rank: 1,
      latest_sell_rank: 2,
      daily: [
        {
          trade_date: "2026-08-20",
          buy_observed: true,
          sell_observed: false,
          observed_top_n_buy_value: 1000,
          observed_top_n_sell_value: 0,
          observed_top_n_net_value: 1000,
          cumulative_observed_top_n_net_value: 1000,
          observed_top_n_buy_lots: 10,
          observed_top_n_sell_lots: 0,
          observed_top_n_net_lots: 10,
          cumulative_observed_top_n_net_lots: 10,
          observed_top_n_buy_shares: 1000,
          observed_top_n_sell_shares: 0,
          observed_top_n_net_shares: 1000,
          cumulative_observed_top_n_net_shares: 1000,
        },
      ],
    },
  ],
};

const baseProps = {
  range: 20 as const,
  onRange: vi.fn(),
  onRetry: vi.fn(),
};

describe("Broker Accumulation", () => {
  it("is default-off and toggleable from the tools menu", async () => {
    const onToggle = vi.fn();
    render(<IndicatorMenu enabled={new Set(["volume"])} onToggle={onToggle} />);

    await userEvent.click(screen.getByText("Indicators"));
    await userEvent.click(screen.getByText("Broker Accumulation"));

    expect(onToggle).toHaveBeenCalledWith("broker-accumulation");
  });

  it("renders loading, error, unavailable, partial, and populated states honestly", () => {
    const { rerender } = render(
      <BrokerAccumulationPanel {...baseProps} data={undefined} loading error={false} />,
    );
    expect(screen.getByText(/Loading broker observations/)).toBeInTheDocument();

    rerender(<BrokerAccumulationPanel {...baseProps} data={undefined} loading={false} error />);
    expect(screen.getByRole("alert")).toHaveTextContent("Broker history unavailable");

    rerender(
      <BrokerAccumulationPanel
        {...baseProps}
        data={{
          ...populated,
          coverage: { ...populated.coverage, state: "unavailable" },
          brokers: [],
        }}
        loading={false}
        error={false}
      />,
    );
    expect(screen.getByText(/No observed top-10 broker history/)).toBeInTheDocument();

    rerender(
      <BrokerAccumulationPanel {...baseProps} data={populated} loading={false} error={false} />,
    );
    expect(screen.getByText("TOP-10 OBSERVED · NOT FULL MARKET")).toBeInTheDocument();
    expect(screen.getByText("Verified Broker")).toBeInTheDocument();
    expect(screen.getByText(/1 missing/)).toBeInTheDocument();
  });
});
