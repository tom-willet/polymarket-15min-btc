import time

from fastapi.testclient import TestClient

from src.polymarket_agent.api import app

client = TestClient(app)


def test_review_api_latency_budget_smoke() -> None:
    start = time.perf_counter()
    response = client.get("/reviews?limit=20")
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 200
    # SC-005 budget approximation for local SQLite read path.
    assert elapsed_ms < 300


def test_replay_enqueue_is_fast_smoke() -> None:
    start = time.perf_counter()
    response = client.post(
        "/admin/reviews/replay",
        json={
            "market_id": "perf-market",
            "round_close_ts": "2026-02-18T15:15:00Z",
            "review_version": "v1.0",
        },
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 202
    # SC-002 enqueue path should be quick and non-blocking.
    assert elapsed_ms < 500
