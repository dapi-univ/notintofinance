export type Numberish = number | string;

export type StockListItem = {
  ticker: string;
  company_name: string;
  sector: string | null;
  subsector: string | null;
  latest_close: Numberish | null;
  change: Numberish | null;
  change_percent: Numberish | null;
  latest_trade_date: string | null;
  sparkline: Numberish[];
  has_history: boolean;
};

export type HistoryBar = {
  date: string;
  open: Numberish;
  high: Numberish;
  low: Numberish;
  close: Numberish;
  previous: Numberish;
  volume_shares: number;
  volume_lots: Numberish;
  value_idr: Numberish;
  frequency: number;
  frequency_analyzer_raw_shares: Numberish | null;
  frequency_analyzer_raw_lots: Numberish | null;
  foreign_buy_shares: number | null;
  foreign_sell_shares: number | null;
  foreign_net_shares: number | null;
  cumulative_foreign_net_shares: number | null;
};

export type HistoryResponse = {
  ticker: string;
  company_name: string;
  from: string | null;
  to: string | null;
  latest_trade_date: string | null;
  is_stale: boolean;
  is_mock: boolean;
  source: string;
  bars: HistoryBar[];
};

export type DataStatus = {
  latest_trade_date: string | null;
  expected_trade_date: string;
  is_stale: boolean;
  is_mock: boolean;
  provider: string;
  repository: string;
  ingestion: {
    provider: string;
    status: string;
    finished_at: string | null;
    rows_received: number;
  } | null;
  last_successful_ingestion: {
    provider: string;
    status: string;
    finished_at: string | null;
    rows_received: number;
  } | null;
};
