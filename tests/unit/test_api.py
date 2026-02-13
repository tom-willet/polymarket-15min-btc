from fastapi.testclient import TestClient

from src.polymarket_agent.api import app
from src.polymarket_agent.state import agent_state

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_status_returns_state_snapshot() -> None:
    agent_state.set_round(round_id=42, close_ts=9999.0)
    agent_state.set_tick(price=123.45, tick_ts=1700.0)
    agent_state.set_decision({"action": "BUY_YES"})

    response = client.get("/status")

    assert response.status_code == 200
    body = response.json()
    assert body["active_round_id"] == 42
    assert body["latest_price"] == 123.45
    assert body["last_decision"] == {"action": "BUY_YES"}


def test_admin_kill_switch_toggle() -> None:
    response = client.post("/admin/kill-switch", json={"enabled": True})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "kill_switch_enabled": True}

    status_response = client.get("/status")
    assert status_response.status_code == 200
    assert status_response.json()["kill_switch_enabled"] is True

    reset_response = client.post("/admin/kill-switch", json={"enabled": False})
    assert reset_response.status_code == 200
    assert reset_response.json() == {"ok": True, "kill_switch_enabled": False}


def test_paper_trades_endpoint_returns_items() -> None:
    agent_state.add_paper_trade_entry({"type": "paper_trade_opened", "ts": 1700.0})

    response = client.get("/paper-trades")

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)
