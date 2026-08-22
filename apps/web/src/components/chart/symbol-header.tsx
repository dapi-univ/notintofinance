import type { HistoryResponse } from "@/lib/api/types";
import { formatCompact, formatPrice, formatSigned, marketDirection } from "@/lib/format/market";

type Props = {
  ticker: string;
  history: HistoryResponse | undefined;
  loading: boolean;
};

export function SymbolHeader({ ticker, history, loading }: Props) {
  const latest = history?.bars.at(-1);
  const change = latest ? Number(latest.close) - Number(latest.previous) : null;
  const changePercent = latest && Number(latest.previous) !== 0 ? (Number(change) / Number(latest.previous)) * 100 : null;
  const direction = marketDirection(change);
  return (
    <header className="symbol-header">
      <div className="symbol-header__identity">
        <span className="symbol-header__ticker" data-testid="active-ticker">{ticker}</span>
        <span className="exchange-badge">IDX</span>
        <div>
          <h1>{history?.ticker === ticker ? history.company_name : loading ? "Loading symbol…" : "Unknown symbol"}</h1>
          <p>IDX · END-OF-DAY RESEARCH · IDR</p>
        </div>
      </div>
      <div className="symbol-header__quote" aria-label={`Active symbol ${ticker} market summary`}>
        <strong>{formatPrice(latest?.close)}</strong>
        <span className={`market-${direction}`}>
          <span aria-hidden="true">{direction === "up" ? "▲" : direction === "down" ? "▼" : "•"}</span>{" "}
          {formatSigned(change)} ({formatSigned(changePercent)}%)
        </span>
      </div>
      <dl className="symbol-header__stats">
        <div><dt>HIGH</dt><dd>{formatPrice(latest?.high)}</dd></div>
        <div><dt>LOW</dt><dd>{formatPrice(latest?.low)}</dd></div>
        <div><dt>VOLUME</dt><dd>{formatCompact(latest?.volume_shares)}</dd></div>
        <div><dt>FREQ</dt><dd>{formatCompact(latest?.frequency)}</dd></div>
      </dl>
    </header>
  );
}
