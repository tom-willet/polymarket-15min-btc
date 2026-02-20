from fastapi.testclient import TestClient

from src.polymarket_agent.api import app

client = TestClient(app)


def test_replay_endpoint_accepts_request() -> None:
    response = client.post(
        "/admin/reviews/replay",
        json={
            "market_id": "manual-market",
            "round_close_ts": "2026-02-18T15:15:00Z",
            "review_version": "v1.0",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] is True
    assert body["review_key"]["market_id"] == "manual-market"
