from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..state import AgentState


def _to_iso(ts: float | None) -> str | None:
    if not isinstance(ts, (int, float)):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def build_market_review_payload(
    *,
    state: AgentState,
    market_id: str,
    market_slug: str,
    round_id: int | None,
    round_open_ts: datetime,
    round_close_ts: datetime,
    strategy_mode: str,
) -> dict[str, Any]:
    snapshot = state.snapshot()
    paper_trades = snapshot.get("paper_trades", [])
    events = snapshot.get("events", [])

    decisions = [
        {
            "ts": _to_iso(event.get("ts")),
            "event": event.get("message"),
            "data": event.get("data", {}),
        }
        for event in events
        if event.get("message") in {"decision", "odds_filter_blocked", "risk_blocked", "net_edge_blocked"}
    ]

    risk_events = [
        {
            "ts": _to_iso(event.get("ts")),
            "event": event.get("message"),
            "data": event.get("data", {}),
        }
        for event in events
        if "risk" in str(event.get("message", "")) or event.get("message") in {"odds_filter_blocked", "kill_switch"}
    ]

    realized_pnl = 0.0
    closed_count = 0
    for trade in paper_trades:
        if trade.get("type") == "paper_trade_closed":
            closed_count += 1
            pnl = trade.get("pnl_usd")
            if isinstance(pnl, (int, float)):
                realized_pnl += float(pnl)

    return {
        "market": {
            "market_id": market_id,
            "market_slug": market_slug,
            "round_id": round_id,
            "round_open_ts": round_open_ts.astimezone(timezone.utc).isoformat(),
            "round_close_ts": round_close_ts.astimezone(timezone.utc).isoformat(),
            "strategy_mode": strategy_mode,
        },
        "decisions": decisions,
        "trades": paper_trades,
        "risk_events": risk_events,
        "aggregates": {
            "total_trades": len(paper_trades),
            "closed_trades": closed_count,
            "realized_pnl_usd": round(realized_pnl, 6),
            "event_count": len(events),
        },
    }


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    redacted_market = dict(redacted.get("market", {}))
    redacted_market.pop("token", None)
    redacted["market"] = redacted_market

    sanitized_events: list[dict[str, Any]] = []
    for event in redacted.get("risk_events", []):
        clean_event = dict(event)
        data = dict(clean_event.get("data", {}))
        for key in list(data.keys()):
            if "key" in key.lower() or "secret" in key.lower() or "token" in key.lower():
                data[key] = "<redacted>"
        clean_event["data"] = data
        sanitized_events.append(clean_event)
    redacted["risk_events"] = sanitized_events
    return redacted
