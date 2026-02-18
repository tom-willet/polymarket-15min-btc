"use client";

import { useEffect, useMemo, useState } from "react";
import {
  filterTradeRows,
  normalizeTradeItems,
  pairTrades,
  toTradeTableRows,
} from "../../lib/tradeAdapters";
import type { TradeRecord } from "../../lib/tradeSchema";

function fmtTs(ts: number | null): string {
  if (ts === null) return "-";
  return new Date(ts * 1000).toLocaleString();
}

function fmtNum(value: number | null, digits = 4): string {
  if (value === null) return "-";
  return value.toFixed(digits);
}

type SortKey =
  | "time"
  | "entryPrice"
  | "exitPrice"
  | "returnPct"
  | "pnlUsd"
  | "confidencePct"
  | "decisionScore";

type SortDirection = "asc" | "desc";

type PaperTradesResponse = {
  items?: unknown[];
};

function sortValue(
  row: ReturnType<typeof toTradeTableRows>[number],
  key: SortKey,
): number {
  switch (key) {
    case "time":
      return row.exitTs ?? row.entryTs ?? 0;
    case "entryPrice":
      return row.entryPrice ?? Number.NEGATIVE_INFINITY;
    case "exitPrice":
      return row.exitPrice ?? Number.NEGATIVE_INFINITY;
    case "returnPct":
      return row.returnPct ?? Number.NEGATIVE_INFINITY;
    case "pnlUsd":
      return row.pnlUsd ?? Number.NEGATIVE_INFINITY;
    case "confidencePct":
      return row.confidencePct ?? Number.NEGATIVE_INFINITY;
    case "decisionScore":
      return row.decisionScore ?? Number.NEGATIVE_INFINITY;
  }
}

function timeWindowSeconds(value: string): number | null {
  if (value === "15m") return 15 * 60;
  if (value === "1h") return 60 * 60;
  if (value === "6h") return 6 * 60 * 60;
  if (value === "24h") return 24 * 60 * 60;
  return null;
}

function fmtPct(value: number | null): string {
  if (value === null) return "-";
  return `${value.toFixed(2)}%`;
}

function fmtUsd(value: number | null): string {
  if (value === null) return "-";
  return `${value.toFixed(4)} USD`;
}

export default function TradesPage() {
  const [records, setRecords] = useState<TradeRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [outcomeFilter, setOutcomeFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("time");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;

    const load = async () => {
      try {
        const response = await fetch("/api/agent/paper-trades", {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const payload = (await response.json()) as PaperTradesResponse;
        const items = normalizeTradeItems(payload.items ?? []);
        const paired = pairTrades(items);
        setRecords(paired);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "request failed");
      } finally {
        setLoading(false);
      }
    };

    void load();
    timer = setInterval(() => void load(), 4000);
    return () => {
      if (timer) clearInterval(timer);
    };
  }, []);

  const rows = useMemo(() => toTradeTableRows(records), [records]);

  const sourceOptions = useMemo(() => {
    const unique = new Set(
      rows
        .map((row) => row.priceToBeatSource)
        .filter((source) => source && source !== "-"),
    );
    return ["all", ...[...unique].sort()];
  }, [rows]);

  const filtered = useMemo(
    () =>
      filterTradeRows(rows, {
        outcome: outcomeFilter,
        action: actionFilter,
        source: sourceFilter,
        search,
      }),
    [rows, outcomeFilter, actionFilter, sourceFilter, search],
  );

  const filteredByTime = useMemo(() => {
    const seconds = timeWindowSeconds(timeFilter);
    if (seconds === null) return filtered;
    const now = Date.now() / 1000;
    return filtered.filter((row) => {
      const rowTs = row.exitTs ?? row.entryTs;
      if (rowTs === null) return false;
      return now - rowTs <= seconds;
    });
  }, [filtered, timeFilter]);

  const sortedRows = useMemo(() => {
    const cloned = [...filteredByTime];
    cloned.sort((left, right) => {
      const leftValue = sortValue(left, sortKey);
      const rightValue = sortValue(right, sortKey);
      if (leftValue === rightValue) return 0;
      const direction = sortDirection === "asc" ? 1 : -1;
      return leftValue > rightValue ? direction : -direction;
    });
    return cloned;
  }, [filteredByTime, sortDirection, sortKey]);

  const selectedTrade =
    sortedRows.find((row) => row.id === selectedTradeId) ?? sortedRows[0];
  const selectedRecord = selectedTrade
    ? records.find((record) => record.id === selectedTrade.id)
    : null;

  function toggleSort(next: SortKey) {
    if (sortKey === next) {
      setSortDirection((value) => (value === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(next);
    setSortDirection("desc");
  }

  const opened = selectedRecord?.opened ?? null;
  const closed = selectedRecord?.closed ?? null;
  const merged = selectedRecord
    ? { ...(opened ?? {}), ...(closed ?? {}) }
    : null;

  return (
    <main style={{ maxWidth: "1280px" }}>
      <h1>Trades</h1>
      <p>Schema-first trade explorer using live paper trade records.</p>

      <div className="panel">
        <span className={`badge ${error ? "" : "ok"}`}>
          {error ? `error: ${error}` : loading ? "loading..." : "live"}
        </span>
        <div className="kv" style={{ marginTop: 12 }}>
          <div>Total paired trades</div>
          <div className="code">{rows.length}</div>
          <div>Visible rows</div>
          <div className="code">{sortedRows.length}</div>
          <div>Sort</div>
          <div className="code">
            {sortKey} ({sortDirection})
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Filters</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <select
            value={outcomeFilter}
            onChange={(event) => setOutcomeFilter(event.target.value)}
          >
            <option value="all">Outcome: all</option>
            <option value="win">Win</option>
            <option value="loss">Loss</option>
            <option value="invalid">Invalid</option>
            <option value="-">Open/Unknown</option>
          </select>

          <select
            value={actionFilter}
            onChange={(event) => setActionFilter(event.target.value)}
          >
            <option value="all">Action: all</option>
            <option value="BUY_YES">BUY_YES</option>
            <option value="BUY_NO">BUY_NO</option>
          </select>

          <select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value)}
          >
            {sourceOptions.map((source) => (
              <option key={source} value={source}>
                Source: {source}
              </option>
            ))}
          </select>

          <select
            value={timeFilter}
            onChange={(event) => setTimeFilter(event.target.value)}
          >
            <option value="all">Time: all</option>
            <option value="15m">Last 15m</option>
            <option value="1h">Last 1h</option>
            <option value="6h">Last 6h</option>
            <option value="24h">Last 24h</option>
          </select>

          <input
            placeholder="Search id / slug"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Trade Table</h3>
        <div className="tableWrap">
          <table className="logTable code">
            <thead>
              <tr>
                <th>
                  <button className="badge" onClick={() => toggleSort("time")}>
                    Close/Open Time
                  </button>
                </th>
                <th>trade_id</th>
                <th>slug</th>
                <th>action</th>
                <th>market_outcome</th>
                <th>outcome</th>
                <th>
                  <button
                    className="badge"
                    onClick={() => toggleSort("entryPrice")}
                  >
                    entry_price
                  </button>
                </th>
                <th>
                  <button
                    className="badge"
                    onClick={() => toggleSort("exitPrice")}
                  >
                    exit_price
                  </button>
                </th>
                <th>btc_price_to_beat</th>
                <th>price_to_beat_source</th>
                <th>btc_price_at_close</th>
                <th>
                  <button
                    className="badge"
                    onClick={() => toggleSort("returnPct")}
                  >
                    return_pct
                  </button>
                </th>
                <th>
                  <button
                    className="badge"
                    onClick={() => toggleSort("pnlUsd")}
                  >
                    pnl_usd
                  </button>
                </th>
                <th>
                  <button
                    className="badge"
                    onClick={() => toggleSort("confidencePct")}
                  >
                    confidence_pct
                  </button>
                </th>
                <th>
                  <button
                    className="badge"
                    onClick={() => toggleSort("decisionScore")}
                  >
                    decision_score
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => setSelectedTradeId(row.id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{fmtTs(row.exitTs ?? row.entryTs)}</td>
                  <td>{row.id}</td>
                  <td>{row.slug}</td>
                  <td>{row.action}</td>
                  <td>{row.marketOutcome}</td>
                  <td>{row.outcome}</td>
                  <td>{fmtNum(row.entryPrice)}</td>
                  <td>{fmtNum(row.exitPrice)}</td>
                  <td>{fmtNum(row.priceToBeat, 2)}</td>
                  <td>{row.priceToBeatSource}</td>
                  <td>{fmtNum(row.btcAtClose, 2)}</td>
                  <td>{fmtNum(row.returnPct, 2)}</td>
                  <td>{fmtNum(row.pnlUsd, 4)}</td>
                  <td>{fmtNum(row.confidencePct, 2)}</td>
                  <td>{fmtNum(row.decisionScore, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Trade Detail</h3>
        <div className="kv" style={{ marginBottom: 12 }}>
          <div>Selected trade</div>
          <div className="code">{selectedTrade?.id ?? "-"}</div>
          <div>Lifecycle</div>
          <div className="code">{selectedRecord?.lifecycle ?? "-"}</div>
          <div>Net PnL</div>
          <div className="code">{fmtUsd(selectedTrade?.pnlUsd ?? null)}</div>
          <div>Return</div>
          <div className="code">{fmtPct(selectedTrade?.returnPct ?? null)}</div>
        </div>

        <h4>Identity & timing</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(
            {
              id: merged?.id,
              entry_ts_iso_utc: merged?.entry_ts_iso_utc,
              exit_ts_iso_utc: merged?.exit_ts_iso_utc,
              open_minutes_to_close: merged?.open_minutes_to_close,
              trade_duration_minutes: merged?.trade_duration_minutes,
            },
            null,
            2,
          )}
        </pre>

        <h4>Decision context</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(
            {
              action: merged?.action,
              strategy: merged?.strategy,
              confidence_pct: merged?.confidence_pct,
              decision_score: merged?.decision_score,
              decision_reason: merged?.decision_reason,
              decision_signals: merged?.decision_signals,
            },
            null,
            2,
          )}
        </pre>

        <h4>Market & BTC context</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(
            {
              polymarket_slug: merged?.polymarket_slug,
              polymarket_yes_price: merged?.polymarket_yes_price,
              polymarket_no_price: merged?.polymarket_no_price,
              btc_price_at_entry: merged?.btc_price_at_entry,
              btc_price_at_close: merged?.btc_price_at_close,
              btc_price_to_beat: merged?.btc_price_to_beat,
              btc_price_to_beat_source: merged?.btc_price_to_beat_source,
            },
            null,
            2,
          )}
        </pre>

        <h4>Outcome & PnL</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(
            {
              market_outcome: merged?.market_outcome,
              outcome: merged?.outcome,
              entry_price: merged?.entry_price,
              exit_price: merged?.exit_price,
              return_pct: merged?.return_pct,
              gross_pnl_usd: merged?.gross_pnl_usd,
              pnl_usd: merged?.pnl_usd,
              day_utc: merged?.day_utc,
              day_realized_pnl_usd: merged?.day_realized_pnl_usd,
            },
            null,
            2,
          )}
        </pre>

        <h4>Raw opened / raw closed</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify({ opened, closed }, null, 2)}
        </pre>
      </div>
    </main>
  );
}
