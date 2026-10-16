/** Shared API response types mirroring the FastAPI contract. */

export interface Paged<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface SystemStatus {
  app: string;
  engine_version: string;
  scoring_config_version: string;
  risk_rule_version: string;
  live_trading_enabled: boolean;
  auth_disabled: boolean;
  bot: BotState;
  counts: { analysis_runs: number; signals: number; orders: number; positions: number };
  server_time: string;
}

export interface BotState {
  mode: "ANALYSIS_ONLY" | "PAPER" | "LIVE";
  status: "STOPPED" | "RUNNING" | "PAUSED";
  kill_switch_active: boolean;
  active_run_id: string | null;
  last_loss_at: string | null;
}

export interface TokenItem {
  id: string;
  chain: string;
  mint_address: string;
  symbol: string | null;
  name: string | null;
  price_usd: number | null;
  liquidity_usd: number | null;
  volume_1h: number | null;
  volume_24h: number | null;
  price_change_1h: number | null;
  price_change_24h: number | null;
  market_cap: number | null;
  observed_at: string | null;
  data_age_seconds: number | null;
  stale: boolean;
}

export interface SignalItem {
  id: string;
  mint_address: string;
  signal_type: string;
  status: string;
  decision: string;
  reasons: string[];
  entry_reference: number | null;
  stop_reference: number | null;
  target_references: number[] | null;
  risk_reward: number | null;
  coverage: number | null;
  risk_flags: string[];
  expires_at: string | null;
  created_at: string | null;
  tradable: boolean;
}

export interface AnalysisRunItem {
  id: string;
  token_id: string;
  score: number | null;
  coverage: number | null;
  decision: string;
  reasons: string[];
  indicators: Record<string, unknown>;
  created_at: string | null;
}

export interface PositionItem {
  id: string;
  mint_address: string;
  status: string;
  quantity: number;
  average_entry_price: number;
  total_fees: number;
  realized_pnl: number;
  /** null = not valued (no/stale/unreadable mark). Never 0 by default. */
  unrealized_pnl: number | null;
  mark_price: number | null;
  valuation_status: "KNOWN" | "STALE" | "UNKNOWN";
  valuation_reason: string | null;
  valuation_as_of: string | null;
  exit_price: number | null;
  close_reason: string | null;
  opened_at: string | null;
  closed_at: string | null;
}

export interface PortfolioModes {
  modes: Record<
    string,
    {
      initial_capital: number;
      realized_pnl: number;
      /** null while any open position lacks a usable mark. */
      unrealized_pnl: number | null;
      external_cash_movements: number;
      equity: number | null;
      high_water_mark: number;
      current_drawdown_pct: number | null;
      /** Sum over valued positions only; present even when incomplete. */
      known_unrealized_pnl: number;
      known_equity: number;
      valuation_status: "COMPLETE" | "INCOMPLETE";
      unmarked_positions: number;
      available: boolean;
    }
  >;
  live_trading_enabled: boolean;
  note: string;
}

export interface AgentItem {
  id: string;
  agent_name: string;
  provider: string | null;
  model_id: string | null;
  routing_mode: string;
  enabled: boolean;
  version: string;
}

/** One performance metric as the UI renders it.
 *
 * The key is a field on the backend's `/performance/summary` response. Keeping
 * the list here - as the only place the UI names those fields - is what lets
 * `services/api/tests/test_ui_contract.py` prove every rendered field exists,
 * which is the drift that path-only contract checking cannot see.
 */
export interface PerformanceMetric {
  key: keyof PerformanceMode;
  label: string;
  kind: "usd" | "pct" | "count";
}

export interface PerformanceMode {
  mode: string;
  closed_positions: number;
  open_positions: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  expectancy: number | null;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number | null;
  total_fees: number;
  net_realized_pnl: number;
  equity: number | null;
  high_water_mark: number;
  max_drawdown_usd: number | null;
  current_drawdown_pct: number | null;
  valuation_status: "COMPLETE" | "INCOMPLETE";
  unmarked_positions: number;
  mae_avg: number | null;
  mfe_avg: number | null;
  unavailable_metrics: string[];
}

export const PERFORMANCE_METRICS: PerformanceMetric[] = [
  { key: "closed_positions", label: "Closed trades", kind: "count" },
  { key: "open_positions", label: "Open positions", kind: "count" },
  { key: "wins", label: "Wins", kind: "count" },
  { key: "losses", label: "Losses", kind: "count" },
  { key: "win_rate", label: "Win rate", kind: "pct" },
  { key: "expectancy", label: "Expectancy", kind: "usd" },
  { key: "avg_win", label: "Avg win", kind: "usd" },
  { key: "avg_loss", label: "Avg loss", kind: "usd" },
  { key: "profit_factor", label: "Profit factor", kind: "count" },
  { key: "gross_profit", label: "Gross profit", kind: "usd" },
  { key: "gross_loss", label: "Gross loss", kind: "usd" },
  { key: "total_fees", label: "Total fees", kind: "usd" },
  { key: "net_realized_pnl", label: "Net realized PnL", kind: "usd" },
  { key: "equity", label: "Equity", kind: "usd" },
  { key: "max_drawdown_usd", label: "Max drawdown", kind: "usd" },
  { key: "current_drawdown_pct", label: "Current drawdown", kind: "pct" },
  { key: "mae_avg", label: "Avg MAE", kind: "usd" },
  { key: "mfe_avg", label: "Avg MFE", kind: "usd" },
];

export interface PerformanceSummary {
  paper: PerformanceMode;
  live: PerformanceMode;
  note: string;
}

export interface BacktestResult {
  pair_id: string;
  timeframe: string;
  engine_version: string;
  scoring_config_version: string;
  generated_at: string;
  candles: number;
  initial_capital: number;
  final_equity: number;
  net_pnl: number;
  net_pnl_pct: number | null;
  trades: number;
  win_rate: number | null;
  total_fees: number;
  max_drawdown_pct: number;
  assumptions: Record<string, number>;
}

export interface WalletItem {
  id: string;
  wallet_role: string;
  chain: string;
  public_address: string;
  is_allowlisted: boolean;
  status: string;
}

export interface WalletBalanceItem {
  asset: string;
  decimals: number;
  /** null when the balance could not be read. Never 0 for "unknown". */
  balance_atomic: number | null;
  spendable_atomic: number | null;
  status: "OK" | "UNAVAILABLE" | "UNKNOWN";
  age_seconds?: number;
  observed_at?: string | null;
  rpc_provider?: string | null;
  status_detail?: string | null;
}

export interface WalletTransferItem {
  id: string;
  withdrawal_intent_id: string;
  state: string;
  trigger_type: string;
  asset: string;
  amount_atomic: number;
  estimated_fee_atomic: number;
  destination_address_snapshot: string;
  source_wallet_id: string;
  created_at: string | null;
  expires_at: string | null;
  failure_reason: string | null;
  version: number;
  reserve_snapshot: Record<string, unknown>;
}

export interface WalletPolicy {
  version: number;
  sweep_percent: number;
  allowed_assets: string[];
  reserve_policy: string;
  min_sweep_atomic: number;
  per_transfer_cap_atomic: number | null;
  daily_cap_atomic: number | null;
  cooldown_seconds: number;
  destination_wallet_id: string | null;
  enabled: boolean;
}

export interface AlertItem {
  id: string;
  dedup_key: string;
  title: string | null;
  body: string | null;
  channel: string;
  delivery_status: string;
  attempt_count: number;
  reference_type: string | null;
  reference_id: string | null;
  sent_at: string | null;
  created_at: string | null;
}

export interface ProviderStatus {
  provider: string;
  status: string;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error_message: string | null;
  error_count: number;
  latency_ms: number | null;
}
