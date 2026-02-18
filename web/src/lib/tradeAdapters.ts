import {
  asNumber,
  asString,
  eventTs,
  isClosedTrade,
  isOpenedTrade,
  type TradeRaw,
  type TradeRecord,
  type TradeTableRow,
} from "./tradeSchema";

export function normalizeTradeItems(input: unknown): TradeRaw[] {
  if (!Array.isArray(input)) return [];

  return input
    .filter(
      (row): row is Record<string, unknown> =>
        typeof row === "object" && row !== null,
    )
    .map((row) => row as TradeRaw);
}

export function pairTrades(items: TradeRaw[]): TradeRecord[] {
  const byId = new Map<string, TradeRecord>();

  for (const item of items) {
    const id = asString(item.id);
    if (!id) continue;

    const existing = byId.get(id) ?? {
      id,
      lifecycle: "open" as const,
      opened: null,
      closed: null,
    };

    if (isOpenedTrade(item)) {
      existing.opened = item;
    } else if (isClosedTrade(item)) {
      existing.closed = item;
    }

    if (existing.opened && existing.closed) {
      existing.lifecycle = "closed";
    } else if (!existing.opened && existing.closed) {
      existing.lifecycle = "orphaned_closed";
    } else {
      existing.lifecycle = "open";
    }

    byId.set(id, existing);
  }

  return [...byId.values()].sort((left, right) => {
    const lTs = eventTs(right.closed ?? right.opened ?? {}) ?? 0;
    const rTs = eventTs(left.closed ?? left.opened ?? {}) ?? 0;
    return lTs - rTs;
  });
}

export function toTradeTableRows(records: TradeRecord[]): TradeTableRow[] {
  return records.map((record) => {
    const opened = record.opened ?? {};
    const closed = record.closed ?? {};
    const merged = { ...opened, ...closed } as TradeRaw;

    return {
      id: record.id,
      lifecycle: record.lifecycle,
      slug: asString(merged.polymarket_slug) ?? "-",
      roundId: asNumber(merged.round_id),
      action: asString(merged.action) ?? "-",
      outcome: asString(merged.outcome) ?? "-",
      marketOutcome: asString(merged.market_outcome) ?? "-",
      entryPrice: asNumber(merged.entry_price),
      exitPrice: asNumber(merged.exit_price),
      returnPct: asNumber(merged.return_pct),
      pnlUsd: asNumber(merged.pnl_usd),
      confidencePct: asNumber(merged.confidence_pct),
      decisionScore: asNumber(merged.decision_score),
      priceToBeat: asNumber(merged.btc_price_to_beat),
      priceToBeatSource: asString(merged.btc_price_to_beat_source) ?? "-",
      btcAtEntry: asNumber(merged.btc_price_at_entry),
      btcAtClose: asNumber(merged.btc_price_at_close),
      entryTs: asNumber(merged.entry_ts),
      exitTs: asNumber(merged.exit_ts),
      openMinutesToClose: asNumber(merged.open_minutes_to_close),
    };
  });
}

export function filterTradeRows(
  rows: TradeTableRow[],
  {
    outcome,
    action,
    source,
    search,
  }: {
    outcome: string;
    action: string;
    source: string;
    search: string;
  },
): TradeTableRow[] {
  const query = search.trim().toLowerCase();

  return rows.filter((row) => {
    if (
      outcome !== "all" &&
      row.outcome.toLowerCase() !== outcome.toLowerCase()
    ) {
      return false;
    }
    if (action !== "all" && row.action !== action) {
      return false;
    }
    if (source !== "all" && row.priceToBeatSource !== source) {
      return false;
    }
    if (!query) return true;

    return (
      row.id.toLowerCase().includes(query) ||
      row.slug.toLowerCase().includes(query) ||
      String(row.roundId ?? "").includes(query)
    );
  });
}
