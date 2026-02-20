"use client";

import { useEffect, useMemo, useState } from "react";
import {
  normalizeReviewDetail,
  normalizeReviewList,
  normalizeReviewSummary,
  type ReviewDetail,
  type ReviewSummary,
} from "../../lib/reviewAdapters";

export default function ReviewsPage() {
  const [latest, setLatest] = useState<ReviewSummary | null>(null);
  const [items, setItems] = useState<ReviewSummary[]>([]);
  const [selected, setSelected] = useState<ReviewDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;

    const load = async () => {
      try {
        const [latestRes, listRes] = await Promise.all([
          fetch("/api/agent/reviews/latest", { cache: "no-store" }),
          fetch("/api/agent/reviews?limit=50", { cache: "no-store" }),
        ]);

        if (latestRes.status === 404) {
          setLatest(null);
        } else if (latestRes.ok) {
          const latestPayload = normalizeReviewSummary(await latestRes.json());
          setLatest(latestPayload);
        }

        if (listRes.ok) {
          const listPayload = normalizeReviewList(await listRes.json());
          setItems(listPayload?.items ?? []);
        }

        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "request failed");
      }
    };

    void load();
    timer = setInterval(() => void load(), 6000);
    return () => {
      if (timer) clearInterval(timer);
    };
  }, []);

  const effectiveSelectedId =
    selectedId ?? selected?.id ?? items[0]?.id ?? null;

  useEffect(() => {
    if (!effectiveSelectedId) return;
    let cancelled = false;

    const loadDetail = async () => {
      try {
        const response = await fetch(
          `/api/agent/reviews/${effectiveSelectedId}`,
          {
            cache: "no-store",
          },
        );
        if (!response.ok) return;
        const body = normalizeReviewDetail(await response.json());
        if (!cancelled) setSelected(body);
      } catch {
        return;
      }
    };

    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [effectiveSelectedId]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {
      queued: 0,
      running: 0,
      succeeded: 0,
      failed: 0,
    };
    for (const item of items) counts[item.status] += 1;
    return counts;
  }, [items]);

  return (
    <main style={{ maxWidth: "1280px" }}>
      <h1>Market Reviews</h1>
      <p>
        Latest advisory LLM review artifacts with structured and markdown
        output.
      </p>

      <div className="panel">
        <span className={`badge ${error ? "" : "ok"}`}>
          {error ? `error: ${error}` : "live"}
        </span>
        <div className="kv" style={{ marginTop: 12 }}>
          <div>Latest review</div>
          <div className="code">{latest?.id ?? "-"}</div>
          <div>Latest status</div>
          <div className="code">{latest?.status ?? "-"}</div>
          <div>Total reviews</div>
          <div className="code">{items.length}</div>
          <div>Succeeded / Failed</div>
          <div className="code">
            {statusCounts.succeeded} / {statusCounts.failed}
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Review List</h3>
        <div className="tableWrap">
          <table className="logTable code">
            <thead>
              <tr>
                <th>id</th>
                <th>market</th>
                <th>status</th>
                <th>version</th>
                <th>model</th>
                <th>closed</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{item.id}</td>
                  <td>{item.market_slug}</td>
                  <td>{item.status}</td>
                  <td>{item.review_version}</td>
                  <td>{item.model}</td>
                  <td>{new Date(item.round_close_ts).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Review Detail</h3>
        <div className="kv" style={{ marginBottom: 12 }}>
          <div>ID</div>
          <div className="code">{selected?.id ?? "-"}</div>
          <div>Status</div>
          <div className="code">{selected?.status ?? "-"}</div>
          <div>Latency</div>
          <div className="code">{selected?.latency_ms ?? "-"} ms</div>
        </div>

        <h4>Structured Analysis</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(selected?.analysis_json ?? null, null, 2)}
        </pre>

        <h4>Markdown Analysis</h4>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {selected?.analysis_markdown ?? "-"}
        </pre>
      </div>
    </main>
  );
}
