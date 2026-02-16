from src.polymarket_agent.strategies import BTCUpdownConfig, BTCUpdownStrategy


def test_btc_updown_returns_none_without_context() -> None:
    strategy = BTCUpdownStrategy(BTCUpdownConfig())

    result = strategy.evaluate_shadow({"last_price": 100.0})

    assert result is None


def test_btc_updown_emits_candidate_with_supported_inputs() -> None:
    strategy = BTCUpdownStrategy(
        BTCUpdownConfig(
            min_confidence_to_trade=0.2,
            min_score_to_trade=0.1,
            max_entry_price=0.95,
            kelly_fraction=0.3,
            max_trade_size_usd=100,
            min_trade_size_usd=1,
        )
    )

    result = strategy.evaluate_shadow(
        {
            "last_price": 100.0,
            "return_short": 0.01,
            "zscore": -2.5,
            "seconds_to_close": 20,
            "round_seconds": 90,
            "polymarket_yes_price": 0.35,
            "polymarket_no_price": 0.65,
        }
    )

    assert result is not None
    assert result["strategy"] == "btc_updown"
    assert result["action"] in {"BUY_YES", "BUY_NO"}
    assert result["confidence"] >= 0.2


def test_btc_updown_buy_no_imbalance_guard_requires_extra_score() -> None:
    strategy = BTCUpdownStrategy(
        BTCUpdownConfig(
            min_confidence_to_trade=0.2,
            min_score_to_trade=0.30,
            max_entry_price=0.95,
            kelly_fraction=0.3,
            max_trade_size_usd=100,
            min_trade_size_usd=1,
        )
    )

    strategy._recent_actions.extend(["BUY_NO"] * 31 + ["BUY_YES"] * 9)

    result = strategy.evaluate_shadow(
        {
            "last_price": 100.0,
            "return_short": -0.0004,
            "zscore": 2.0,
            "seconds_to_close": 20,
            "round_seconds": 90,
            "polymarket_yes_price": 0.60,
            "polymarket_no_price": 0.40,
            "orderbook_imbalance": 0.0,
            "trade_momentum": -0.5,
            "feed_divergence_bps": 0.0,
        }
    )

    assert result is None
