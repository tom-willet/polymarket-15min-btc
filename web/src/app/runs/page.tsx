"use client";

import { useEffect, useMemo, useState } from "react";
import {
  normalizeRunPayload,
  runKpis,
  type ContinuousRunPayload,
} from "../../lib/runAdapters";

type RunResponse = ContinuousRunPayload;

function fmtTs(value: string | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function fmtNum(value: number | undefined, digits = 4): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

export default function RunsPage() {
  const [payload, setPayload] = useState<RunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedCycleKey, setSelectedCycleKey] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;

    const load = async () => {
      try {
        const response = await fetch("/api/agent/continuous-run/latest", {
          cache: "no-store",
        });

        if (response.status === 404) {
          setPayload(null);
          setError("no continuous run artifact yet");
          return;
        }

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const body = (await response.json()) as unknown;
        setPayload(normalizeRunPayload(body));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "request failed");
      }
    };

    void load();
    timer = setInterval(() => void load(), 8000);
    return () => {
      if (timer) clearInterval(timer);
    };
  }, []);

  const kpis = useMemo(() => (payload ? runKpis(payload) : null), [payload]);
  const cycles = payload?.cycles ?? [];

  const normalizedCycles = useMemo(
    () =>
      cycles.map((cycle) => {
        const opened = cycle.opened_full ?? {};
        const closed = cycle.closed_full ?? {};
        const cycleRecord = cycle as Record<string, unknown>;
        const isClosed = Object.keys(closed).length > 0;
        const cycleError =
          cycleRecord.error_message ??
          cycleRecord.failure_reason ??
          cycleRecord.exception ??
          null;
        const status = cycleError ? "error" : isClosed ? "closed" : "open";
        const key = `${cycle.cycle_index ?? "-"}-${cycle.trade_id ?? "-"}`;

        return {
          key,
          cycle,
          opened,
          closed,
          status,
          cycleError,
          ts:
            (closed.exit_ts as number | undefined) ??
            (opened.entry_ts as number | undefined) ??
            null,
        };
      }),
    [cycles],
  );

  const visibleCycles = useMemo(() => {
    if (statusFilter === "all") return normalizedCycles;
    return normalizedCycles.filter((cycle) => cycle.status === statusFilter);
  }, [normalizedCycles, statusFilter]);

  const selectedCycle =
    visibleCycles.find((cycle) => cycle.key === selectedCycleKey) ??
    visibleCycles[0] ??
    null;

  const cycleCounts = useMemo(() => {
    let closed = 0;
    let open = 0;
    let errorCount = 0;
    for (const cycle of normalizedCycles) {
      if (cycle.status === "closed") closed += 1;
      if (cycle.status === "open") open += 1;
      if (cycle.status === "error") errorCount += 1;
    }
    return { closed, open, errorCount };
  }, [normalizedCycles]);

  return (
    <main style={{ maxWidth: "1280px" }}>
      <h1>Runs</h1>
      <p>Continuous run timeline and cycle-by-cycle outcomes.</p>

      <div className="panel">
        <span className={`badge ${error ? "" : "ok"}`}>
          {error ? `status: ${error}` : "live"}
        </span>
        <div className="kv" style={{ marginTop: 12 }}>
          <div>Started</div>
          <div className="code">{fmtTs(payload?.run?.started_at_utc)}</div>
          <div>Ended</div>
          <div className="code">{fmtTs(payload?.run?.ended_at_utc)}</div>
          <div>Hours requested</div>
          <div className="code">{payload?.run?.hours_requested ?? "-"}</div>
          <div>Markets completed</div>
          <div className="code">{kpis?.marketsCompleted ?? 0}</div>
          <div>Wins / Losses</div>
          <div className="code">
            {kpis?.wins ?? 0} / {kpis?.losses ?? 0}
          </div>
          <div>Net PnL</div>
          <div className="code">{kpis ? kpis.netPnlUsd.toFixed(4) : "-"}</div>
        </div>
      </div>

      <div
        className="panel"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4,minmax(0,1fr))",
          gap: 12,
        }}
      >
        <div className="panel" style={{ margin: 0 }}>
          <div className="muted">Total cycles</div>
          <div className="code" style={{ fontSize: 20 }}>
            {normalizedCycles.length}
          </div>
        </div>
        <div className="panel" style={{ margin: 0 }}>
          <div className="muted">Closed</div>
          <div className="code" style={{ fontSize: 20 }}>
            {cycleCounts.closed}
          </div>
        </div>
        <div className="panel" style={{ margin: 0 }}>
          <div className="muted">Open</div>
          <div className="code" style={{ fontSize: 20 }}>
            {cycleCounts.open}
          </div>
        </div>
        <div className="panel" style={{ margin: 0 }}>
          <div className="muted">Errors</div>
          <div className="code" style={{ fontSize: 20 }}>
            {cycleCounts.errorCount}
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Cycles</h3>
        <div style={{ marginBottom: 12 }}>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">Status: all</option>
            <option value="closed">Status: closed</option>
            <option value="open">Status: open</option>
            <option value="error">Status: error</option>
          </select>
        </div>
        <div className="tableWrap">
          <table className="logTable code">
            <thead>
              <tr>
                <th>cycle</th>
                <th>status</th>
                <th>trade_id</th>
                <th>action</th>
                <th>slug</th>
                <th>outcome</th>
                <th>entry_price</th>
                <th>exit_price</th>
                <th>pnl_usd</th>
                <th>return_pct</th>
              </tr>
            </thead>
            <tbody>
              {visibleCycles.map((row) => {
                const { cycle, opened, closed, status, key } = row;

                return (
                  <tr
                    key={key}
                    onClick={() => setSelectedCycleKey(key)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{cycle.cycle_index ?? "-"}</td>
                    <td>{status}</td>
                    <td>{cycle.trade_id ?? "-"}</td>
                    <td>{String(closed.action ?? opened.action ?? "-")}</td>
                    <td>
                      {String(
                        closed.polymarket_slug ?? opened.polymarket_slug ?? "-",
                      )}
                    </td>
                    <td>{String(closed.outcome ?? "-")}</td>
                    <td>
                      {String(closed.entry_price ?? opened.entry_price ?? "-")}
                    </td>
                    <td>{String(closed.exit_price ?? "-")}</td>
                    <td>{String(closed.pnl_usd ?? "-")}</td>
                    <td>{String(closed.return_pct ?? "-")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Cycle Detail</h3>
        <div className="kv" style={{ marginBottom: 12 }}>
          <div>Selected cycle</div>
          <div className="code">{selectedCycle?.cycle.cycle_index ?? "-"}</div>
          <div>Status</div>
          <div className="code">{selectedCycle?.status ?? "-"}</div>
          <div>Trade</div>
          <div className="code">{selectedCycle?.cycle.trade_id ?? "-"}</div>
          <div>PnL</div>
          <div className="code">
            {fmtNum(selectedCycle?.closed.pnl_usd as number | undefined)}
          </div>
        </div>
        <h4>Error</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(selectedCycle?.cycleError ?? null, null, 2)}
        </pre>
        <h4>Opened payload</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(selectedCycle?.opened ?? {}, null, 2)}
        </pre>
        <h4>Closed payload</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(selectedCycle?.closed ?? {}, null, 2)}
        </pre>
      </div>
    </main>
  );
}
