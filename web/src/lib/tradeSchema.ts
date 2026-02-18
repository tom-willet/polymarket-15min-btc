export type Primitive = string | number | boolean | null;

export type JsonValue = Primitive | JsonValue[] | { [key: string]: JsonValue };

export type TradeRaw = {
  id?: string;
  type?: string;
  action?: string;
  strategy?: string;
  outcome?: string;
  market_outcome?: string;
  polymarket_slug?: string;
  round_id?: number;
  confidence_pct?: number;
  decision_score?: number;
  decision_reason?: string;
  decision_signals?: Record<string, JsonValue>;
  entry_price?: number;
  exit_price?: number;
  return_pct?: number;
  pnl_usd?: number;
  gross_pnl_usd?: number;
  stake_usd?: number;
  btc_price_to_beat_source?: string;
  btc_price_at_entry?: number;
  btc_price_to_beat?: number;
  btc_price_at_close?: number;
  open_minutes_to_close?: number;
  trade_duration_minutes?: number;
  ts?: number;
  logged_at?: number;
  entry_ts?: number;
  exit_ts?: number;
  round_close_ts?: number;
  entry_ts_iso_utc?: string;
  exit_ts_iso_utc?: string;
  round_close_ts_iso_utc?: string;
  [key: string]: JsonValue | undefined;
};

export type TradeLifecycle = "open" | "closed" | "orphaned_closed";

export type TradeRecord = {
  id: string;
  lifecycle: TradeLifecycle;
  opened: TradeRaw | null;
  closed: TradeRaw | null;
};

export type TradeTableRow = {
  id: string;
  lifecycle: TradeLifecycle;
  slug: string;
  roundId: number | null;
  action: string;
  outcome: string;
  marketOutcome: string;
  entryPrice: number | null;
  exitPrice: number | null;
  returnPct: number | null;
  pnlUsd: number | null;
  confidencePct: number | null;
  decisionScore: number | null;
  priceToBeat: number | null;
  priceToBeatSource: string;
  btcAtEntry: number | null;
  btcAtClose: number | null;
  entryTs: number | null;
  exitTs: number | null;
  openMinutesToClose: number | null;
};

export function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

export function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function tradeType(entry: TradeRaw): string {
  return asString(entry.type) ?? "";
}

export function isOpenedTrade(entry: TradeRaw): boolean {
  return tradeType(entry) === "paper_trade_opened";
}

export function isClosedTrade(entry: TradeRaw): boolean {
  return tradeType(entry) === "paper_trade_closed";
}

export function eventTs(entry: TradeRaw): number | null {
  const closedTs = asNumber(entry.exit_ts);
  if (closedTs !== null) return closedTs;

  const entryTs = asNumber(entry.entry_ts);
  if (entryTs !== null) return entryTs;

  const loggedAt = asNumber(entry.logged_at);
  if (loggedAt !== null) return loggedAt;

  const ts = asNumber(entry.ts);
  if (ts !== null) return ts;

  return null;
}
