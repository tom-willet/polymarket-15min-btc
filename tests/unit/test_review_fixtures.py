from datetime import datetime, timezone


def closed_market_payload() -> dict:
    return {
        "market_id": "btc-up-15m",
        "market_slug": "btc-up-15m",
        "round_id": 100,
        "round_open_ts": datetime(2026, 2, 18, 15, 0, tzinfo=timezone.utc),
        "round_close_ts": datetime(2026, 2, 18, 15, 15, tzinfo=timezone.utc),
    }


def test_closed_market_fixture_shape() -> None:
    payload = closed_market_payload()
    assert payload["market_id"] == "btc-up-15m"
    assert payload["round_close_ts"] > payload["round_open_ts"]
