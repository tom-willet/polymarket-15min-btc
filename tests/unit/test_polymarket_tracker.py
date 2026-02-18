from src.polymarket_agent.polymarket import PolymarketOddsTracker


def test_polymarket_move_event_respects_cooldown() -> None:
    tracker = PolymarketOddsTracker(
        ws_url="wss://example.test/ws",
        move_threshold_pct=3.0,
        move_min_abs_delta=0.03,
        move_log_cooldown_seconds=5.0,
    )

    event1 = tracker._build_move_event(
        slug="mkt",
        yes_price=0.50,
        no_price=0.50,
        btc_price=65000.0,
        now_ts=100.0,
    )
    event2 = tracker._build_move_event(
        slug="mkt",
        yes_price=0.56,
        no_price=0.44,
        btc_price=65010.0,
        now_ts=102.0,
    )
    event3 = tracker._build_move_event(
        slug="mkt",
        yes_price=0.56,
        no_price=0.44,
        btc_price=65010.0,
        now_ts=106.0,
    )

    assert event1 is not None
    assert event2 is None
    assert event3 is not None


def test_polymarket_move_event_requires_material_change() -> None:
    tracker = PolymarketOddsTracker(
        ws_url="wss://example.test/ws",
        move_threshold_pct=3.0,
        move_min_abs_delta=0.03,
        move_log_cooldown_seconds=0.0,
    )

    first = tracker._build_move_event(
        slug="mkt",
        yes_price=0.50,
        no_price=0.50,
        btc_price=65000.0,
        now_ts=100.0,
    )
    small_move = tracker._build_move_event(
        slug="mkt",
        yes_price=0.51,
        no_price=0.49,
        btc_price=65005.0,
        now_ts=101.0,
    )
    big_move = tracker._build_move_event(
        slug="mkt",
        yes_price=0.55,
        no_price=0.45,
        btc_price=65020.0,
        now_ts=102.0,
    )

    assert first is not None
    assert small_move is None
    assert big_move is not None


def test_extract_ordered_token_ids_from_outcomes_and_clob_ids() -> None:
    tracker = PolymarketOddsTracker(ws_url="wss://example.test/ws")
    payload = {
        "slug": "btc-updown-15m-123",
        "outcomes": '["Yes", "No"]',
        "clobTokenIds": '["200", "100"]',
    }

    token_ids = tracker._extract_ordered_token_ids(payload)

    assert token_ids[:2] == ["200", "100"]


def test_extract_ordered_token_ids_from_up_down_outcomes() -> None:
    tracker = PolymarketOddsTracker(ws_url="wss://example.test/ws")
    payload = {
        "slug": "btc-updown-15m-123",
        "outcomes": '["Up", "Down"]',
        "clobTokenIds": '["up-token", "down-token"]',
    }

    token_ids = tracker._extract_ordered_token_ids(payload)

    assert token_ids[:2] == ["up-token", "down-token"]


def test_extract_ordered_token_ids_fallback_is_deterministic() -> None:
    tracker = PolymarketOddsTracker(ws_url="wss://example.test/ws")
    payload = {
        "slug": "btc-updown-15m-123",
        "tokens": ["300000000", "100000000", "200000000"],
    }

    token_ids = tracker._extract_ordered_token_ids(payload)

    assert token_ids == ["100000000", "200000000", "300000000"]
