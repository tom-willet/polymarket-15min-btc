from datetime import datetime, timezone

from src.polymarket_agent.review.collector import build_market_review_payload, redact_payload
from src.polymarket_agent.state import AgentState


def test_collector_builds_payload_sections() -> None:
    state = AgentState()
    state.set_decision({"action": "BUY_YES", "score": 0.4})
    state.add_event("info", "decision", {"score": 0.4})
    state.add_event("warning", "risk_blocked", {"reason": "cooldown"})
    state.add_paper_trade_entry({"type": "paper_trade_closed", "pnl_usd": 1.2})

    payload = build_market_review_payload(
        state=state,
        market_id="m1",
        market_slug="m1",
        round_id=1,
        round_open_ts=datetime(2026, 2, 18, 15, 0, tzinfo=timezone.utc),
        round_close_ts=datetime(2026, 2, 18, 15, 15, tzinfo=timezone.utc),
        strategy_mode="classic",
    )

    assert set(payload.keys()) == {"market", "decisions", "trades", "risk_events", "aggregates"}
    assert payload["aggregates"]["closed_trades"] == 1
    assert payload["aggregates"]["realized_pnl_usd"] == 1.2


def test_collector_redacts_sensitive_keys() -> None:
    payload = {
        "market": {"token": "abc", "market_id": "m1"},
        "risk_events": [
            {
                "data": {
                    "api_key": "x",
                    "secret_value": "y",
                    "safe": "ok",
                }
            }
        ],
    }

    redacted = redact_payload(payload)
    assert "token" not in redacted["market"]
    assert redacted["risk_events"][0]["data"]["api_key"] == "<redacted>"
    assert redacted["risk_events"][0]["data"]["secret_value"] == "<redacted>"
    assert redacted["risk_events"][0]["data"]["safe"] == "ok"
