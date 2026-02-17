import json
import os
import pathlib
import time
import urllib.request
from collections import Counter

from dotenv import load_dotenv

DURATION_SECONDS = int(os.getenv("SOAK_DURATION_SECONDS", str(30 * 60)))
INTERVAL_SECONDS = int(os.getenv("SOAK_INTERVAL_SECONDS", "30"))
STATUS_URL = "http://127.0.0.1:8080/status"
PAPER_TRADES_URL = "http://127.0.0.1:8080/paper-trades"

RUN_METADATA = {
    "strategy_mode": os.getenv("STRATEGY_MODE"),
    "btc_updown_shadow_mode": os.getenv("BTC_UPDOWN_SHADOW_MODE"),
    "btc_updown_live_enabled": os.getenv("BTC_UPDOWN_LIVE_ENABLED"),
    "btc_updown_min_confidence_to_trade": os.getenv("BTC_UPDOWN_MIN_CONFIDENCE_TO_TRADE"),
    "btc_updown_min_score_to_trade": os.getenv("BTC_UPDOWN_MIN_SCORE_TO_TRADE"),
    "btc_updown_max_entry_price": os.getenv("BTC_UPDOWN_MAX_ENTRY_PRICE"),
    "paper_min_net_edge_bps": os.getenv("PAPER_MIN_NET_EDGE_BPS"),
}


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def snapshot() -> dict:
    status = fetch_json(STATUS_URL)
    trades = fetch_json(PAPER_TRADES_URL).get("items", [])
    events = status.get("events", [])

    opened = [t for t in trades if t.get("type") == "paper_trade_opened"]
    closed = [t for t in trades if t.get("type") == "paper_trade_closed"]
    opportunities = [t for t in trades if t.get("type") == "opportunity_detected"]

    wins = [t for t in closed if str(t.get("outcome")) == "win"]
    losses = [t for t in closed if str(t.get("outcome")) == "loss"]

    returns = [
        float(t.get("return_pct"))
        for t in closed
        if isinstance(t.get("return_pct"), (int, float))
    ]

    event_counts = Counter(e.get("message") for e in events)

    now = time.time()
    latest_tick_ts = status.get("latest_tick_ts")
    last_tick_age = (now - latest_tick_ts) if isinstance(latest_tick_ts, (int, float)) else None

    return {
        "ts": now,
        "last_tick_age_sec": round(last_tick_age, 2) if last_tick_age is not None else None,
        "paper_entries": len(trades),
        "opportunities": len(opportunities),
        "opened": len(opened),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "avg_return_pct": round(sum(returns) / len(returns), 6) if returns else None,
        "sum_return_pct": round(sum(returns), 6) if returns else None,
        "decision_events": event_counts.get("decision", 0),
        "risk_blocked_events": event_counts.get("risk_blocked", 0),
        "odds_filter_blocked_events": event_counts.get("odds_filter_blocked", 0),
        "net_edge_blocked_events": event_counts.get("net_edge_blocked", 0),
        "run_metadata": RUN_METADATA,
    }


def main() -> None:
    load_dotenv()
    for key in list(RUN_METADATA.keys()):
        RUN_METADATA[key] = os.getenv(key.upper()) if key.islower() else RUN_METADATA[key]

    start = time.time()
    output = pathlib.Path("logs") / f"soak_shadow_{int(start)}.jsonl"

    while time.time() < start + DURATION_SECONDS:
        try:
            payload = snapshot()
        except Exception as exc:  # noqa: BLE001
            payload = {"ts": time.time(), "error": str(exc)}

        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

        time.sleep(INTERVAL_SECONDS)

    print(output)


if __name__ == "__main__":
    main()
