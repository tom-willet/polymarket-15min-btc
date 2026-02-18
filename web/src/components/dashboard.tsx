"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

type EventRow = {
  ts: number;
  level: string;
  message: string;
  data: Record<string, unknown>;
};

type AgentStatus = {
  started_ts: number;
  kill_switch_enabled: boolean;
  latest_price: number | null;
  latest_tick_ts: number | null;
  last_decision: Record<string, unknown> | null;
  events: EventRow[];
};

type CandleData = {
  symbol: string;
  window: string;
  start_ts: number;
  end_ts: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type PolymarketMarketResponse = {
  ok: boolean;
  slug?: string;
  tokenIds?: string[];
  error?: string;
};

type PricePoint = {
  ts: number;
  price: number;
  tokenId: string | null;
};

type BtcPoint = {
  ts: number;
  price: number;
};

const MAX_PRICE_POINTS = 120;
const CHART_WIDTH = 720;
const CHART_HEIGHT = 180;
const CHART_PAD_LEFT = 44;
const CHART_PAD_RIGHT = 10;
const CHART_PAD_TOP = 8;
const CHART_PAD_BOTTOM = 20;
const PROBABILITY_MIN = 0;
const PROBABILITY_MAX = 1;
const MAX_BTC_POINTS = 240;

function shortTokenId(tokenId: string | null): string {
  if (!tokenId) return "-";
  if (tokenId.length <= 16) return tokenId;
  return `${tokenId.slice(0, 8)}...${tokenId.slice(-6)}`;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function parseCandle(data: Record<string, unknown>): CandleData | null {
  const symbol = typeof data.symbol === "string" ? data.symbol : null;
  const window = typeof data.window === "string" ? data.window : null;
  const startTs = asNumber(data.start_ts);
  const endTs = asNumber(data.end_ts);
  const open = asNumber(data.open);
  const high = asNumber(data.high);
  const low = asNumber(data.low);
  const close = asNumber(data.close);
  const volume = asNumber(data.volume);

  if (!symbol || !window || startTs === null || endTs === null) return null;
  if (
    open === null ||
    high === null ||
    low === null ||
    close === null ||
    volume === null
  )
    return null;

  return {
    symbol,
    window,
    start_ts: startTs,
    end_ts: endTs,
    open,
    high,
    low,
    close,
    volume,
  };
}

function fmtTs(ts: number | null): string {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString();
}

function extractPricePoint(
  payload: unknown,
  ts: number,
  allowedTokenIds: string[] = [],
): PricePoint | null {
  const updates: PricePoint[] = [];

  const visit = (value: unknown) => {
    if (value == null) return;

    if (Array.isArray(value)) {
      for (const item of value) visit(item);
      return;
    }

    if (typeof value !== "object") return;

    const record = value as Record<string, unknown>;
    const assetId =
      typeof record.asset_id === "string" ? record.asset_id : null;
    const priceValue = record.price ?? record.p;

    if (assetId && priceValue !== undefined) {
      const parsedPrice = asNumber(priceValue);
      if (parsedPrice !== null && parsedPrice >= 0 && parsedPrice <= 1) {
        updates.push({ ts, price: parsedPrice, tokenId: assetId });
      }
    }

    for (const child of Object.values(record)) {
      if (typeof child === "object" && child !== null) {
        visit(child);
      }
    }
  };

  visit(payload);

  if (!updates.length) return null;

  if (allowedTokenIds.length) {
    for (let index = updates.length - 1; index >= 0; index -= 1) {
      if (allowedTokenIds.includes(updates[index].tokenId ?? "")) {
        return updates[index];
      }
    }
  }

  return updates[updates.length - 1];
}

export function Dashboard() {
  const [data, setData] = useState<AgentStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [isTogglingKillSwitch, setIsTogglingKillSwitch] = useState(false);
  const [isRestartingBackend, setIsRestartingBackend] = useState(false);
  const [polymarketConnected, setPolymarketConnected] = useState(false);
  const [polymarketError, setPolymarketError] = useState<string | null>(null);
  const [polymarketSlug, setPolymarketSlug] = useState<string | null>(null);
  const [polymarketTokenIds, setPolymarketTokenIds] = useState<string[]>([]);
  const [polymarketLastMessage, setPolymarketLastMessage] = useState<
    string | null
  >(null);
  const [polymarketLastMessageTs, setPolymarketLastMessageTs] = useState<
    number | null
  >(null);
  const [polymarketPriceSeries, setPolymarketPriceSeries] = useState<
    PricePoint[]
  >([]);
  const [polymarketMessageCount, setPolymarketMessageCount] = useState(0);
  const [selectedTokenFilter, setSelectedTokenFilter] = useState<string>("all");
  const [btcPriceSeries, setBtcPriceSeries] = useState<BtcPoint[]>([]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;

    const load = async () => {
      try {
        const res = await fetch("/api/agent/status", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = (await res.json()) as AgentStatus;
        setData(payload);
        if (
          typeof payload.latest_tick_ts === "number" &&
          typeof payload.latest_price === "number"
        ) {
          const tickTs = payload.latest_tick_ts;
          const tickPrice = payload.latest_price;
          setBtcPriceSeries((previous) => {
            if (
              previous.length > 0 &&
              previous[previous.length - 1].ts === tickTs
            ) {
              return previous;
            }
            const next = [...previous, { ts: tickTs, price: tickPrice }];
            return next.length > MAX_BTC_POINTS
              ? next.slice(next.length - MAX_BTC_POINTS)
              : next;
          });
        }
        setErr(null);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Request failed");
      }
    };

    void load();
    timer = setInterval(() => void load(), 2500);

    return () => {
      if (timer) clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (selectedTokenFilter === "all") return;
    if (!polymarketTokenIds.includes(selectedTokenFilter)) {
      setSelectedTokenFilter("all");
    }
  }, [polymarketTokenIds, selectedTokenFilter]);

  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let flushTimer: ReturnType<typeof setInterval> | undefined;
    let marketRefreshTimer: ReturnType<typeof setInterval> | undefined;
    let totalMessages = 0;
    let pendingPreview: string | null = null;
    let pendingMessageTs: number | null = null;
    let pendingPoint: PricePoint | null = null;
    let currentMarket: { slug: string; tokenIds: string[] } | null = null;

    const sameMarket = (
      left: { slug: string; tokenIds: string[] } | null,
      right: { slug: string; tokenIds: string[] } | null,
    ): boolean => {
      if (!left || !right) return false;
      if (left.slug !== right.slug) return false;
      if (left.tokenIds.length !== right.tokenIds.length) return false;
      return left.tokenIds.every(
        (tokenId, index) => tokenId === right.tokenIds[index],
      );
    };

    const applyMarket = (market: { slug: string; tokenIds: string[] }) => {
      currentMarket = market;
      setPolymarketSlug(market.slug);
      setPolymarketTokenIds(market.tokenIds);
      setPolymarketPriceSeries([]);
      setPolymarketMessageCount(0);
      setPolymarketLastMessage(null);
      setPolymarketLastMessageTs(null);
      setSelectedTokenFilter("all");
      totalMessages = 0;
      pendingPreview = null;
      pendingMessageTs = null;
      pendingPoint = null;

      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(
          JSON.stringify({
            type: "market",
            assets_ids: market.tokenIds,
          }),
        );
      }
    };

    const fetchActiveMarket = async (): Promise<{
      slug: string;
      tokenIds: string[];
    } | null> => {
      const marketRes = await fetch("/api/polymarket/active-market", {
        cache: "no-store",
      });
      if (!marketRes.ok) return null;

      const market = (await marketRes.json()) as PolymarketMarketResponse;
      if (!market.ok || !market.slug || !market.tokenIds?.length) return null;

      return { slug: market.slug, tokenIds: market.tokenIds };
    };

    const connect = async () => {
      try {
        const market = await fetchActiveMarket();
        if (!market) throw new Error("active market not found");

        if (!active) return;

        currentMarket = market;
        setPolymarketSlug(market.slug);
        setPolymarketTokenIds(market.tokenIds);
        setPolymarketError(null);

        socket = new WebSocket(
          "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        );

        socket.onopen = () => {
          if (!active || !socket) return;
          setPolymarketConnected(true);
          setPolymarketError(null);
          setPolymarketPriceSeries([]);
          setPolymarketMessageCount(0);
          totalMessages = 0;
          if (currentMarket) {
            socket.send(
              JSON.stringify({
                type: "market",
                assets_ids: currentMarket.tokenIds,
              }),
            );
          }
        };

        socket.onmessage = (event) => {
          if (!active) return;

          totalMessages += 1;
          const nowTs = Math.floor(Date.now() / 1000);
          pendingMessageTs = nowTs;

          try {
            const parsed = JSON.parse(event.data as string) as unknown;
            const text = JSON.stringify(parsed);
            pendingPreview =
              text.length > 240 ? `${text.slice(0, 240)}...` : text;
            pendingPoint =
              extractPricePoint(parsed, nowTs, currentMarket?.tokenIds ?? []) ??
              pendingPoint;
          } catch {
            const text = String(event.data);
            pendingPreview =
              text.length > 240 ? `${text.slice(0, 240)}...` : text;
          }
        };

        socket.onerror = () => {
          if (!active) return;
          setPolymarketError("websocket error");
        };

        socket.onclose = () => {
          if (!active) return;
          setPolymarketConnected(false);
          reconnectTimer = setTimeout(() => void connect(), 2500);
        };
      } catch (e) {
        if (!active) return;
        setPolymarketConnected(false);
        setPolymarketError(
          e instanceof Error ? e.message : "stream setup failed",
        );
        reconnectTimer = setTimeout(() => void connect(), 2500);
      }
    };

    marketRefreshTimer = setInterval(() => {
      if (!active) return;

      void (async () => {
        try {
          const market = await fetchActiveMarket();
          if (!market || !active) return;

          if (!sameMarket(currentMarket, market)) {
            applyMarket(market);
          }
        } catch {
          return;
        }
      })();
    }, 12000);

    flushTimer = setInterval(() => {
      if (!active) return;

      if (pendingMessageTs !== null) {
        setPolymarketLastMessageTs(pendingMessageTs);
      }
      if (pendingPreview !== null) {
        setPolymarketLastMessage(pendingPreview);
      }
      setPolymarketMessageCount(totalMessages);

      if (pendingPoint !== null) {
        const point = pendingPoint;
        setPolymarketPriceSeries((previous) => {
          const next = [...previous, point];
          return next.length > MAX_PRICE_POINTS
            ? next.slice(next.length - MAX_PRICE_POINTS)
            : next;
        });
      }

      pendingMessageTs = null;
      pendingPreview = null;
      pendingPoint = null;
    }, 500);

    void connect();

    return () => {
      active = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (flushTimer) clearInterval(flushTimer);
      if (marketRefreshTimer) clearInterval(marketRefreshTimer);
      if (socket && socket.readyState < WebSocket.CLOSING) {
        socket.close();
      }
    };
  }, []);

  const latestCandle = useMemo(() => {
    if (!data?.events?.length) return null;
    const source = [...data.events]
      .reverse()
      .find((event) => event.message === "btc_candle_closed");
    if (!source) return null;
    return parseCandle(source.data);
  }, [data?.events]);

  const latestCandleAgeSeconds = useMemo(() => {
    if (!latestCandle) return null;
    return Math.max(0, Math.floor(Date.now() / 1000 - latestCandle.end_ts));
  }, [latestCandle, data?.events]);

  const filteredPriceSeries = useMemo(() => {
    if (selectedTokenFilter === "all") return polymarketPriceSeries;
    return polymarketPriceSeries.filter(
      (point) => point.tokenId === selectedTokenFilter,
    );
  }, [polymarketPriceSeries, selectedTokenFilter]);

  const yesTokenId = polymarketTokenIds[0] ?? null;
  const noTokenId = polymarketTokenIds[1] ?? null;

  const yesSeries = useMemo(
    () =>
      polymarketPriceSeries
        .filter((point) => point.tokenId === yesTokenId)
        .slice(-MAX_PRICE_POINTS),
    [polymarketPriceSeries, yesTokenId],
  );

  const noSeries = useMemo(
    () =>
      polymarketPriceSeries
        .filter((point) => point.tokenId === noTokenId)
        .slice(-MAX_PRICE_POINTS),
    [polymarketPriceSeries, noTokenId],
  );

  const chartSeries =
    selectedTokenFilter === "all" ? polymarketPriceSeries : filteredPriceSeries;

  const priceStats = useMemo(() => {
    if (!chartSeries.length) return null;
    const prices = chartSeries.map((point) => point.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const last = chartSeries[chartSeries.length - 1];
    return {
      min,
      max,
      last,
      points: chartSeries.length,
    };
  }, [chartSeries]);

  const buildPolyline = (
    series: PricePoint[],
    minValue: number,
    maxValue: number,
  ): string => {
    if (series.length < 2) return "";

    const spread = maxValue - minValue || 1;
    const plotWidth = CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT;
    const plotHeight = CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM;

    return series
      .map((point, index) => {
        const x =
          series.length === 1
            ? CHART_PAD_LEFT
            : CHART_PAD_LEFT + (index / (series.length - 1)) * plotWidth;
        const boundedPrice = Math.max(
          minValue,
          Math.min(maxValue, point.price),
        );
        const normalized = (boundedPrice - minValue) / spread;
        const y = CHART_PAD_TOP + (1 - normalized) * plotHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  };

  const chartPolyline = useMemo(() => {
    return buildPolyline(chartSeries, PROBABILITY_MIN, PROBABILITY_MAX);
  }, [chartSeries]);

  const yesPolyline = useMemo(
    () => buildPolyline(yesSeries, PROBABILITY_MIN, PROBABILITY_MAX),
    [yesSeries],
  );
  const noPolyline = useMemo(
    () => buildPolyline(noSeries, PROBABILITY_MIN, PROBABILITY_MAX),
    [noSeries],
  );

  const yAxisTicks = useMemo(() => [1, 0.75, 0.5, 0.25, 0], []);

  const oddsComparisonSeries = useMemo(() => {
    if (selectedTokenFilter !== "all") return filteredPriceSeries;
    if (yesSeries.length) return yesSeries;
    if (noSeries.length) return noSeries;
    return filteredPriceSeries;
  }, [selectedTokenFilter, filteredPriceSeries, yesSeries, noSeries]);

  const comparisonSeries = useMemo(() => {
    const btc = btcPriceSeries.slice(-60);
    const odds = oddsComparisonSeries.slice(-60);
    const n = Math.min(btc.length, odds.length);
    if (n < 2) return null;

    const btcTail = btc.slice(-n);
    const oddsTail = odds.slice(-n);
    const btcPrices = btcTail.map((point) => point.price);
    const oddsPrices = oddsTail.map((point) => point.price);
    const btcMin = Math.min(...btcPrices);
    const btcMax = Math.max(...btcPrices);
    const oddsMin = Math.min(...oddsPrices);
    const oddsMax = Math.max(...oddsPrices);
    const btcSpread = btcMax - btcMin || 1;
    const oddsSpread = oddsMax - oddsMin || 1;

    const normalize = (value: number, min: number, spread: number) =>
      (value - min) / spread;

    const series = {
      btc: btcTail.map((point, index) => ({
        x: index,
        y: normalize(point.price, btcMin, btcSpread),
      })),
      odds: oddsTail.map((point, index) => ({
        x: index,
        y: normalize(point.price, oddsMin, oddsSpread),
      })),
      btcMovePct:
        btcTail[0].price !== 0
          ? ((btcTail[btcTail.length - 1].price - btcTail[0].price) /
              btcTail[0].price) *
            100
          : 0,
      oddsMovePct:
        oddsTail[0].price !== 0
          ? ((oddsTail[oddsTail.length - 1].price - oddsTail[0].price) /
              oddsTail[0].price) *
            100
          : 0,
      points: n,
    };

    return series;
  }, [btcPriceSeries, oddsComparisonSeries]);

  const comparisonPolyline = (
    series: Array<{ x: number; y: number }> | undefined,
  ): string => {
    if (!series || series.length < 2) return "";

    const plotWidth = CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT;
    const plotHeight = CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM;

    return series
      .map((point, index) => {
        const x =
          series.length === 1
            ? CHART_PAD_LEFT
            : CHART_PAD_LEFT + (index / (series.length - 1)) * plotWidth;
        const y = CHART_PAD_TOP + (1 - point.y) * plotHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  };

  const btcComparisonPolyline = useMemo(
    () => comparisonPolyline(comparisonSeries?.btc),
    [comparisonSeries],
  );

  const oddsComparisonPolyline = useMemo(
    () => comparisonPolyline(comparisonSeries?.odds),
    [comparisonSeries],
  );

  const toggleKillSwitch = async () => {
    if (!data || isTogglingKillSwitch) return;

    setIsTogglingKillSwitch(true);
    try {
      const res = await fetch("/api/agent/kill-switch", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ enabled: !data.kill_switch_enabled }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      setData((previous) => {
        if (!previous) return previous;
        return {
          ...previous,
          kill_switch_enabled: !previous.kill_switch_enabled,
        };
      });
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Kill switch update failed");
    } finally {
      setIsTogglingKillSwitch(false);
    }
  };

  const restartBackend = async () => {
    if (isRestartingBackend) return;

    setIsRestartingBackend(true);
    try {
      const res = await fetch("/api/agent/restart", {
        method: "POST",
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setErr("backend restart requested; waiting to reconnect...");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Backend restart failed");
      setIsRestartingBackend(false);
      return;
    }

    setTimeout(() => {
      setIsRestartingBackend(false);
    }, 8000);
  };

  return (
    <main>
      <h1>Polymarket BTC 15m Agent</h1>
      <p>Live monitor for ticker updates and strategy decisions.</p>
      <p>
        <Link href="/logs">View live logs timeline</Link>
      </p>
      <p>
        <Link href="/trades">Open trades explorer</Link>
      </p>
      <p>
        <Link href="/runs">Open continuous runs</Link>
      </p>

      <div className="panel">
        <span className={`badge ${err ? "" : "ok"}`}>
          {err ? `disconnected: ${err}` : "connected"}
        </span>
        <div className="kv" style={{ marginTop: 12 }}>
          <div>Started</div>
          <div className="code">{fmtTs(data?.started_ts ?? null)}</div>
          <div>Kill switch</div>
          <div>
            <button
              className="badge"
              onClick={() => void toggleKillSwitch()}
              disabled={!data || isTogglingKillSwitch}
            >
              {isTogglingKillSwitch
                ? "updating..."
                : data?.kill_switch_enabled
                  ? "enabled (click to disable)"
                  : "disabled (click to enable)"}
            </button>
          </div>
          <div>Backend</div>
          <div>
            <button
              className="badge"
              onClick={() => void restartBackend()}
              disabled={isRestartingBackend}
            >
              {isRestartingBackend ? "restarting..." : "restart backend"}
            </button>
          </div>
          <div>Latest price</div>
          <div className="code">{data?.latest_price ?? "-"}</div>
          <div>Last tick</div>
          <div className="code">{fmtTs(data?.latest_tick_ts ?? null)}</div>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>BTC vs Polymarket Odds (Movement)</h3>
        <div className="code" style={{ marginBottom: 8 }}>
          Source A: BTC live feed from agent status • Source B: Polymarket odds
          ({selectedTokenFilter === "all" ? "YES" : "selected token"})
        </div>
        <div className="chartBox">
          {btcComparisonPolyline && oddsComparisonPolyline ? (
            <>
              <div className="chartLegend">
                <span className="chartLegendItem">
                  <span className="dot btc" /> BTC (normalized)
                </span>
                <span className="chartLegendItem">
                  <span className="dot odds" /> Polymarket odds (normalized)
                </span>
              </div>
              <svg
                viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
                className="chartSvg"
                role="img"
                aria-label="BTC versus Polymarket odds movement chart"
              >
                {yAxisTicks.map((tick) => {
                  const plotHeight =
                    CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM;
                  const y = CHART_PAD_TOP + (1 - tick) * plotHeight;
                  return (
                    <line
                      key={`cmp-tick-${tick}`}
                      x1={CHART_PAD_LEFT}
                      y1={y}
                      x2={CHART_WIDTH - CHART_PAD_RIGHT}
                      y2={y}
                      stroke="var(--line)"
                      strokeWidth="1"
                      opacity="0.4"
                    />
                  );
                })}
                <polyline
                  points={btcComparisonPolyline}
                  fill="none"
                  stroke="#ffd166"
                  strokeWidth="2"
                />
                <polyline
                  points={oddsComparisonPolyline}
                  fill="none"
                  stroke="#47b8ff"
                  strokeWidth="2"
                />
              </svg>
            </>
          ) : (
            <div className="code">
              Waiting for enough BTC and Polymarket points to compare...
            </div>
          )}
        </div>
        <div className="kv" style={{ marginTop: 12 }}>
          <div>Comparison points</div>
          <div className="code">{comparisonSeries?.points ?? 0}</div>
          <div>BTC move (window)</div>
          <div className="code">
            {comparisonSeries
              ? `${comparisonSeries.btcMovePct.toFixed(3)}%`
              : "-"}
          </div>
          <div>Odds move (window)</div>
          <div className="code">
            {comparisonSeries
              ? `${comparisonSeries.oddsMovePct.toFixed(3)}%`
              : "-"}
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Last decision</h3>
        <pre className="code" style={{ whiteSpace: "pre-wrap" }}>
          {JSON.stringify(data?.last_decision ?? {}, null, 2)}
        </pre>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Latest BTC 15m Candle</h3>
        {latestCandle ? (
          <div className="kv">
            <div>Symbol</div>
            <div className="code">{latestCandle.symbol}</div>
            <div>Window</div>
            <div className="code">{latestCandle.window}</div>
            <div>Start</div>
            <div className="code">{fmtTs(latestCandle.start_ts)}</div>
            <div>End</div>
            <div className="code">{fmtTs(latestCandle.end_ts)}</div>
            <div>Closed age</div>
            <div className="code">{latestCandleAgeSeconds ?? "-"}s</div>
            <div>Open</div>
            <div className="code">{latestCandle.open.toFixed(2)}</div>
            <div>High</div>
            <div className="code">{latestCandle.high.toFixed(2)}</div>
            <div>Low</div>
            <div className="code">{latestCandle.low.toFixed(2)}</div>
            <div>Close</div>
            <div className="code">{latestCandle.close.toFixed(2)}</div>
            <div>Volume</div>
            <div className="code">{latestCandle.volume.toFixed(6)}</div>
          </div>
        ) : (
          <div className="code">No closed candle yet.</div>
        )}
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Polymarket CLOB Stream</h3>
        <div className="kv">
          <div>Status</div>
          <div className="code">
            {polymarketConnected
              ? "connected"
              : polymarketError
                ? `error: ${polymarketError}`
                : "connecting..."}
          </div>
          <div>Active slug</div>
          <div className="code">{polymarketSlug ?? "-"}</div>
          <div>Subscribed tokens</div>
          <div className="code">
            {polymarketTokenIds.length ? polymarketTokenIds.join(", ") : "-"}
          </div>
          <div>Last update</div>
          <div className="code">{fmtTs(polymarketLastMessageTs)}</div>
          <div>Messages</div>
          <div className="code">{polymarketMessageCount}</div>
        </div>

        <div style={{ marginTop: 12 }}>
          <div className="code">Live odds chart (Polymarket probability)</div>
          <div
            style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}
          >
            <button
              className="badge"
              onClick={() => setSelectedTokenFilter("all")}
              disabled={selectedTokenFilter === "all"}
            >
              all
            </button>
            {polymarketTokenIds.map((tokenId, index) => (
              <button
                key={tokenId}
                className="badge"
                onClick={() => setSelectedTokenFilter(tokenId)}
                disabled={selectedTokenFilter === tokenId}
              >
                {index === 0
                  ? "YES"
                  : index === 1
                    ? "NO"
                    : `token ${index + 1}`}
              </button>
            ))}
          </div>
          <div className="chartBox">
            {selectedTokenFilter === "all" ? (
              yesPolyline || noPolyline ? (
                <>
                  <div className="chartLegend">
                    <span className="chartLegendItem">
                      <span className="dot yes" /> YES
                    </span>
                    <span className="chartLegendItem">
                      <span className="dot no" /> NO
                    </span>
                  </div>
                  <svg
                    viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
                    className="chartSvg"
                    role="img"
                    aria-label="Polymarket live price chart"
                  >
                    {yAxisTicks.map((tick) => {
                      const plotHeight =
                        CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM;
                      const y = CHART_PAD_TOP + (1 - tick) * plotHeight;
                      return (
                        <g key={`tick-${tick}`}>
                          <line
                            x1={CHART_PAD_LEFT}
                            y1={y}
                            x2={CHART_WIDTH - CHART_PAD_RIGHT}
                            y2={y}
                            stroke="var(--line)"
                            strokeWidth="1"
                            opacity="0.6"
                          />
                          <text
                            x={CHART_PAD_LEFT - 6}
                            y={y + 4}
                            textAnchor="end"
                            fill="var(--muted)"
                            fontSize="10"
                          >
                            {tick.toFixed(2)}
                          </text>
                        </g>
                      );
                    })}
                    <text
                      x={CHART_PAD_LEFT}
                      y={CHART_HEIGHT - 4}
                      fill="var(--muted)"
                      fontSize="10"
                    >
                      older
                    </text>
                    <text
                      x={CHART_WIDTH - CHART_PAD_RIGHT}
                      y={CHART_HEIGHT - 4}
                      textAnchor="end"
                      fill="var(--muted)"
                      fontSize="10"
                    >
                      now
                    </text>
                    {yesPolyline ? (
                      <polyline
                        points={yesPolyline}
                        fill="none"
                        stroke="#2fd784"
                        strokeWidth="2"
                      />
                    ) : null}
                    {noPolyline ? (
                      <polyline
                        points={noPolyline}
                        fill="none"
                        stroke="#ff7f7f"
                        strokeWidth="2"
                      />
                    ) : null}
                  </svg>
                </>
              ) : (
                <div className="code">Waiting for YES/NO price ticks...</div>
              )
            ) : chartPolyline ? (
              <svg
                viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
                className="chartSvg"
                role="img"
                aria-label="Polymarket live price chart"
              >
                {yAxisTicks.map((tick) => {
                  const plotHeight =
                    CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM;
                  const y = CHART_PAD_TOP + (1 - tick) * plotHeight;
                  return (
                    <g key={`single-tick-${tick}`}>
                      <line
                        x1={CHART_PAD_LEFT}
                        y1={y}
                        x2={CHART_WIDTH - CHART_PAD_RIGHT}
                        y2={y}
                        stroke="var(--line)"
                        strokeWidth="1"
                        opacity="0.6"
                      />
                      <text
                        x={CHART_PAD_LEFT - 6}
                        y={y + 4}
                        textAnchor="end"
                        fill="var(--muted)"
                        fontSize="10"
                      >
                        {tick.toFixed(2)}
                      </text>
                    </g>
                  );
                })}
                <text
                  x={CHART_PAD_LEFT}
                  y={CHART_HEIGHT - 4}
                  fill="var(--muted)"
                  fontSize="10"
                >
                  older
                </text>
                <text
                  x={CHART_WIDTH - CHART_PAD_RIGHT}
                  y={CHART_HEIGHT - 4}
                  textAnchor="end"
                  fill="var(--muted)"
                  fontSize="10"
                >
                  now
                </text>
                <polyline
                  points={chartPolyline}
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="2"
                />
              </svg>
            ) : (
              <div className="code">
                Waiting for price ticks for selected token...
              </div>
            )}
          </div>

          <div className="kv" style={{ marginTop: 12 }}>
            <div>Tracking</div>
            <div className="code">
              Polymarket YES/NO odds (0.00 to 1.00), not BTC spot
            </div>
            <div>Token filter</div>
            <div className="code">
              {selectedTokenFilter === "all"
                ? "all"
                : shortTokenId(selectedTokenFilter)}
            </div>
            <div>Last price</div>
            <div className="code">
              {priceStats ? priceStats.last.price.toFixed(4) : "-"}
            </div>
            <div>Price range</div>
            <div className="code">
              {priceStats
                ? `${priceStats.min.toFixed(4)} - ${priceStats.max.toFixed(4)}`
                : "-"}
            </div>
            <div>Chart points</div>
            <div className="code">{priceStats ? priceStats.points : 0}</div>
            <div>Last token</div>
            <div className="code">
              {shortTokenId(priceStats?.last.tokenId ?? null)}
            </div>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <div className="code">Latest message preview:</div>
          <pre
            className="code"
            style={{ whiteSpace: "pre-wrap", marginTop: 8 }}
          >
            {polymarketLastMessage ?? "-"}
          </pre>
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Recent events</h3>
        <ul className="events">
          {(data?.events ?? [])
            .slice()
            .reverse()
            .map((evt, idx) => (
              <li key={`${evt.ts}-${idx}`}>
                <div className="code">
                  {new Date(evt.ts * 1000).toLocaleTimeString()} [{evt.level}]{" "}
                  {evt.message}
                </div>
                <div className="code">{JSON.stringify(evt.data)}</div>
              </li>
            ))}
        </ul>
      </div>
    </main>
  );
}
