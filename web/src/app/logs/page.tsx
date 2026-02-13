"use client";

import { useEffect, useMemo, useState } from "react";

type PaperLogItem = {
  type: string;
  ts?: number;
  [key: string]: unknown;
};

type StatusEvent = {
  ts: number;
  level: string;
  message: string;
  data: Record<string, unknown>;
};

type StatusPayload = {
  events: StatusEvent[];
};

const FOCUS_PAPER_TYPES = new Set([
  "price_move_3pct",
  "opportunity_detected",
  "paper_trade_opened",
  "paper_trade_closed",
]);

const FOCUS_EVENT_TYPES = new Set([
  "decision",
  "odds_filter_blocked",
  "polymarket_move_3pct",
  "paper_trade_opened",
  "paper_trade_closed",
  "price_move_3pct",
]);

function fmtTs(ts: number | null): string {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString();
}

function num(value: unknown, digits = 4): string {
  if (typeof value === "number") return value.toFixed(digits);
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed.toFixed(digits);
  }
  return "-";
}

export default function LogsPage() {
  const [paperLogs, setPaperLogs] = useState<PaperLogItem[]>([]);
  const [events, setEvents] = useState<StatusEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchTs, setLastFetchTs] = useState<number | null>(null);
  const [lastResponseBytes, setLastResponseBytes] = useState<number>(0);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;

    const load = async () => {
      try {
        const [paperRes, statusRes] = await Promise.all([
          fetch("/api/agent/paper-trades", { cache: "no-store" }),
          fetch("/api/agent/status", { cache: "no-store" }),
        ]);

        if (!paperRes.ok) throw new Error(`paper logs HTTP ${paperRes.status}`);
        if (!statusRes.ok) throw new Error(`status HTTP ${statusRes.status}`);

        const paperText = await paperRes.text();
        const statusText = await statusRes.text();
        setLastResponseBytes(paperText.length + statusText.length);

        const paperBody = JSON.parse(paperText) as { items?: PaperLogItem[] };
        const statusBody = JSON.parse(statusText) as StatusPayload;

        setPaperLogs(paperBody.items ?? []);
        setEvents(statusBody.events ?? []);
        setLastFetchTs(Date.now() / 1000);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "request failed");
      }
    };
    void load();
    timer = setInterval(() => void load(), 2000);

    return () => {
      if (timer) clearInterval(timer);
    };
  }, []);

  const timeline = useMemo(() => {
    const timelineRows: Array<{
      ts: number;
      kind: string;
      item: PaperLogItem | StatusEvent;
    }> = [];

    for (const item of paperLogs) {
      if (!FOCUS_PAPER_TYPES.has(String(item.type ?? ""))) continue;
      const tsRaw = item.ts ?? item.logged_at;
      const ts = typeof tsRaw === "number" ? tsRaw : Number(tsRaw);
      if (!Number.isFinite(ts)) continue;
      timelineRows.push({ ts, kind: "paper", item });
    }

    for (const evt of events) {
      if (!FOCUS_EVENT_TYPES.has(evt.message)) continue;
      timelineRows.push({ ts: evt.ts, kind: "event", item: evt });
    }

    const focused = timelineRows.sort((a, b) => b.ts - a.ts).slice(0, 300);
    if (focused.length > 0) return focused;

    const fallback = paperLogs
      .map((item) => {
        const tsRaw = item.ts ?? item.logged_at;
        const ts = typeof tsRaw === "number" ? tsRaw : Number(tsRaw);
        if (!Number.isFinite(ts)) return null;
        return { ts, kind: "paper" as const, item };
      })
      .filter(
        (row): row is { ts: number; kind: "paper"; item: PaperLogItem } =>
          row !== null,
      )
      .sort((a, b) => b.ts - a.ts)
      .slice(0, 100);

    return fallback;
  }, [paperLogs, events]);

  const summary = useMemo(() => {
    const byType = new Map<string, number>();
    for (const item of paperLogs) {
      const type = String(item.type ?? "unknown");
      byType.set(type, (byType.get(type) ?? 0) + 1);
    }

    const closed = paperLogs.filter(
      (item) => item.type === "paper_trade_closed",
    );
    const wins = closed.filter(
      (item) => String(item.outcome ?? "") === "win",
    ).length;
    const losses = closed.filter(
      (item) => String(item.outcome ?? "") === "loss",
    ).length;
    const avgReturnPct =
      closed.length > 0
        ? closed
            .map((item) => Number(item.return_pct ?? 0))
            .filter((value) => Number.isFinite(value))
            .reduce((total, value) => total + value, 0) / closed.length
        : null;

    const latestTs = [...paperLogs, ...events]
      .map((item) => Number(item.ts ?? 0))
      .filter((value) => Number.isFinite(value) && value > 0)
      .reduce((maxTs, value) => Math.max(maxTs, value), 0);

    return {
      opportunities: byType.get("opportunity_detected") ?? 0,
      opened: byType.get("paper_trade_opened") ?? 0,
      closed: byType.get("paper_trade_closed") ?? 0,
      wins,
      losses,
      avgReturnPct,
      latestTs,
    };
  }, [paperLogs, events]);

  return (
    <main style={{ maxWidth: "1400px" }}>
      <h1>Agent Logs</h1>
      <p>
        Focused timeline: major BTC price changes and the agent reasoning trail.
      </p>

      <div className="panel">
        <span className={`badge ${error ? "" : "ok"}`}>
          {error ? `error: ${error}` : "live"}
        </span>
        <div className="kv" style={{ marginTop: 12 }}>
          <div>Paper log entries</div>
          <div className="code">{paperLogs.length}</div>
          <div>Total status events</div>
          <div className="code">{events.length}</div>
          <div>Reasoning events</div>
          <div className="code">
            {events.filter((evt) => FOCUS_EVENT_TYPES.has(evt.message)).length}
          </div>
          <div>Focused rows shown</div>
          <div className="code">{timeline.length}</div>
          <div>Last fetch</div>
          <div className="code">{fmtTs(lastFetchTs)}</div>
          <div>Payload bytes</div>
          <div className="code">{lastResponseBytes}</div>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Timeline</h3>
        <div className="kv" style={{ marginBottom: 12 }}>
          <div>Opportunities</div>
          <div className="code">{summary.opportunities}</div>
          <div>Opened / Closed</div>
          <div className="code">
            {summary.opened} / {summary.closed}
          </div>
          <div>Wins / Losses</div>
          <div className="code">
            {summary.wins} / {summary.losses}
          </div>
          <div>Avg return %</div>
          <div className="code">
            {summary.avgReturnPct === null
              ? "-"
              : summary.avgReturnPct.toFixed(3)}
          </div>
          <div>Last updated</div>
          <div className="code">
            {summary.latestTs > 0
              ? new Date(summary.latestTs * 1000).toLocaleTimeString()
              : "-"}
          </div>
        </div>
        <div className="tableWrap">
          <table className="logTable code">
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Action</th>
                <th>Strategy</th>
                <th>Confidence</th>
                <th>Price</th>
                <th>YES</th>
                <th>NO</th>
                <th>Edge</th>
                <th>Show Work</th>
              </tr>
            </thead>
            <tbody>
              {timeline.map((row, idx) => {
                if (row.kind === "paper") {
                  const item = row.item as PaperLogItem;
                  return (
                    <tr key={`paper-${idx}`}>
                      <td>{fmtTs(row.ts)}</td>
                      <td>{String(item.type ?? "paper")}</td>
                      <td>{String(item.action ?? "-")}</td>
                      <td>{String(item.strategy ?? "-")}</td>
                      <td>{num(item.confidence)}</td>
                      <td>{num(item.entry_price ?? item.price, 2)}</td>
                      <td>{num(item.polymarket_yes_price)}</td>
                      <td>{num(item.polymarket_no_price)}</td>
                      <td>{num(item.edge_strength)}</td>
                      <td>
                        {item.type === "price_move_3pct"
                          ? `${num(item.from_price, 2)} → ${num(item.to_price, 2)} (${num(item.pct_change, 2)}%)`
                          : item.type === "paper_trade_closed"
                            ? `${String(item.outcome ?? "-")} (${num(item.return_pct, 2)}%)`
                            : String(
                                (
                                  item.risk_assessment as
                                    | { risk_reason?: string }
                                    | undefined
                                )?.risk_reason ??
                                  item.odds_alignment ??
                                  "-",
                              )}
                      </td>
                    </tr>
                  );
                }

                const evt = row.item as StatusEvent;
                const data = evt.data ?? {};
                return (
                  <tr key={`event-${idx}`}>
                    <td>{fmtTs(row.ts)}</td>
                    <td>{evt.message}</td>
                    <td>{String(data.action ?? "-")}</td>
                    <td>{String(data.strategy ?? "-")}</td>
                    <td>{num(data.confidence)}</td>
                    <td>{num(data.entry_price ?? data.price, 2)}</td>
                    <td>{num(data.polymarket_yes_price)}</td>
                    <td>{num(data.polymarket_no_price)}</td>
                    <td>{num(data.edge_strength)}</td>
                    <td>
                      {evt.message === "decision"
                        ? `seconds_to_close=${String(data.seconds_to_close ?? "-")}`
                        : evt.message === "polymarket_move_3pct"
                          ? `YES ${num(data.yes_from)}→${num(data.yes_to)} | NO ${num(data.no_from)}→${num(data.no_to)}`
                          : String(data.reason ?? data.outcome ?? "-")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
