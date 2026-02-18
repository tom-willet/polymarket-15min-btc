import { asNumber } from "./tradeSchema";

export type ContinuousRunCycle = {
  cycle_index?: number;
  trade_id?: string;
  opened_full?: Record<string, unknown>;
  closed_full?: Record<string, unknown>;
};

export type ContinuousRunPayload = {
  run?: {
    started_at_utc?: string;
    ended_at_utc?: string;
    started_ts?: number;
    ended_ts?: number;
    hours_requested?: number;
  };
  cycles?: ContinuousRunCycle[];
  summary?: {
    markets_completed?: number;
    wins?: number;
    losses?: number;
    invalid?: number;
    net_pnl_usd?: number;
  };
  errors?: Array<Record<string, unknown>>;
};

export function normalizeRunPayload(
  input: unknown,
): ContinuousRunPayload | null {
  if (!input || typeof input !== "object") return null;
  return input as ContinuousRunPayload;
}

export function runKpis(payload: ContinuousRunPayload): {
  marketsCompleted: number;
  wins: number;
  losses: number;
  invalid: number;
  netPnlUsd: number;
} {
  const summary = payload.summary ?? {};
  return {
    marketsCompleted: asNumber(summary.markets_completed) ?? 0,
    wins: asNumber(summary.wins) ?? 0,
    losses: asNumber(summary.losses) ?? 0,
    invalid: asNumber(summary.invalid) ?? 0,
    netPnlUsd: asNumber(summary.net_pnl_usd) ?? 0,
  };
}
