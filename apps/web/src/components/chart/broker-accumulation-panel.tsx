"use client";

import type { BrokerAccumulationResponse } from "@/lib/api/types";
import { formatCompact, toNumber } from "@/lib/format/market";

export type BrokerRange = 5 | 10 | 20;

type Props = {
  data: BrokerAccumulationResponse | undefined;
  loading: boolean;
  error: boolean;
  range: BrokerRange;
  onRange: (range: BrokerRange) => void;
  onRetry: () => void;
};

function linePath(values: number[], max: number, width = 520, height = 108): string {
  if (!values.length) return "";
  return values
    .map((value, index) => {
      const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
      const y = height / 2 - (value / max) * (height * 0.42);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function BrokerAccumulationPanel({
  data,
  loading,
  error,
  range,
  onRange,
  onRetry,
}: Props) {
  const state = error
    ? "error"
    : loading
      ? "loading"
      : !data
        ? "empty"
        : data.coverage.state === "unavailable"
          ? "unavailable"
          : "populated";
  const visible = data?.brokers.slice(0, 6) ?? [];
  const scaleMax = Math.max(
    1,
    ...visible.flatMap((broker) =>
      broker.daily.map(
        (point) => Math.abs(toNumber(point.cumulative_observed_top_n_net_value) ?? 0),
      ),
    ),
  );
  return (
    <section className="broker-panel" data-testid="broker-accumulation-pane">
      <header className="broker-panel__header">
        <div>
          <strong>Broker Accumulation</strong>
          <span className="broker-panel__badge">TOP-10 OBSERVED · NOT FULL MARKET</span>
        </div>
        <div className="broker-range" role="group" aria-label="Broker accumulation range">
          {([5, 10, 20] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={range === item ? "is-active" : ""}
              aria-pressed={range === item}
              onClick={() => onRange(item)}
            >
              {item}D
            </button>
          ))}
        </div>
      </header>
      {state === "error" ? (
        <div className="broker-panel__state" role="alert">
          Broker history unavailable. <button type="button" onClick={onRetry}>Retry</button>
        </div>
      ) : null}
      {state === "loading" ? <div className="broker-panel__state" role="status">Loading broker observations…</div> : null}
      {state === "empty" ? (
        <div className="broker-panel__state">No confirmed EOD range is available.</div>
      ) : null}
      {state === "unavailable" ? (
        <div className="broker-panel__state">No observed top-10 broker history is stored for this ticker.</div>
      ) : null}
      {state === "populated" && data ? (
        <div className="broker-panel__content">
          <div className="broker-lines" aria-label="Cumulative observed broker net value lines">
            <svg viewBox="0 0 520 108" preserveAspectRatio="none" role="img">
              <line x1="0" y1="54" x2="520" y2="54" className="broker-lines__zero" />
              {visible.map((broker, index) => {
                const values = broker.daily.map((point) =>
                  toNumber(point.cumulative_observed_top_n_net_value) ?? 0,
                );
                const finalValue = toNumber(broker.observed_top_n_net_value) ?? 0;
                return (
                  <path
                    key={broker.broker_code}
                    d={linePath(values, scaleMax)}
                    className={finalValue >= 0 ? "broker-lines__up" : "broker-lines__down"}
                    style={{ opacity: 1 - index * 0.1 }}
                  />
                );
              })}
            </svg>
            <div className="broker-lines__legend">
              {visible.map((broker) => (
                <span key={broker.broker_code}>{broker.broker_code}</span>
              ))}
            </div>
          </div>
          <div className="broker-table-wrap">
            <table className="broker-table">
              <thead>
                <tr><th>Broker</th><th>Class</th><th>Buy</th><th>Sell</th><th>Observed net</th><th>Appear.</th></tr>
              </thead>
              <tbody>
                {data.brokers.map((broker) => {
                  const net = toNumber(broker.observed_top_n_net_value) ?? 0;
                  return (
                    <tr key={broker.broker_code}>
                      <td><strong>{broker.broker_code}</strong><span>{broker.broker_name ?? "Name unavailable"}</span></td>
                      <td>{broker.classification ?? "—"}</td>
                      <td>{formatCompact(broker.observed_top_n_buy_value)}</td>
                      <td>{formatCompact(broker.observed_top_n_sell_value)}</td>
                      <td className={net >= 0 ? "market-up" : "market-down"}>{formatCompact(net)}</td>
                      <td>{broker.buy_appearances}B / {broker.sell_appearances}S</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {(state === "unavailable" || state === "populated") && data ? (
        <footer className="broker-panel__coverage" data-state={data.coverage.state}>
          {data.coverage.covered_sessions.length}/{data.coverage.expected_sessions.length} sessions covered
          {data.coverage.missing_sessions.length ? ` · ${data.coverage.missing_sessions.length} missing` : ""}
        </footer>
      ) : null}
    </section>
  );
}
