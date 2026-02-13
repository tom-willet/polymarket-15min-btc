import pytest

from src.polymarket_agent.candles import CandleBuilder, parse_window_seconds
from src.polymarket_agent.models import Tick


def test_parse_window_seconds_for_15m() -> None:
    assert parse_window_seconds("15m") == 900


def test_parse_window_seconds_rejects_invalid_unit() -> None:
    with pytest.raises(ValueError, match="unsupported window unit"):
        parse_window_seconds("10x")


def test_candle_builder_emits_closed_candle_on_next_bucket() -> None:
    builder = CandleBuilder(symbol="BTCUSDT", window="15m", window_seconds=900)

    assert builder.add_tick(Tick(ts=1000.0, symbol="BTCUSDT", price=100.0, size=1.0)) is None
    assert builder.add_tick(Tick(ts=1010.0, symbol="BTCUSDT", price=110.0, size=2.0)) is None
    closed = builder.add_tick(Tick(ts=1900.0, symbol="BTCUSDT", price=105.0, size=0.5))

    assert closed is not None
    assert closed.open == 100.0
    assert closed.high == 110.0
    assert closed.low == 100.0
    assert closed.close == 110.0
    assert closed.volume == 3.0
