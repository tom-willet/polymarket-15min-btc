from __future__ import annotations

from dataclasses import dataclass

from .models import Candle, Tick


def parse_window_seconds(window: str) -> int:
    value = window.strip().lower()
    if not value:
        raise ValueError("window must not be empty")

    unit = value[-1]
    number = int(value[:-1])
    if number <= 0:
        raise ValueError("window must be > 0")

    factors = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }
    if unit not in factors:
        raise ValueError(f"unsupported window unit: {unit}")
    return number * factors[unit]


@dataclass
class CandleBuilder:
    symbol: str
    window: str
    window_seconds: int

    def __post_init__(self) -> None:
        self._current: Candle | None = None

    def add_tick(self, tick: Tick) -> Candle | None:
        bucket_start = float(int(tick.ts // self.window_seconds) * self.window_seconds)
        bucket_end = bucket_start + self.window_seconds

        if self._current is None:
            self._current = Candle(
                symbol=self.symbol,
                window=self.window,
                start_ts=bucket_start,
                end_ts=bucket_end,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.size,
            )
            return None

        if bucket_start == self._current.start_ts:
            self._current = Candle(
                symbol=self._current.symbol,
                window=self._current.window,
                start_ts=self._current.start_ts,
                end_ts=self._current.end_ts,
                open=self._current.open,
                high=max(self._current.high, tick.price),
                low=min(self._current.low, tick.price),
                close=tick.price,
                volume=self._current.volume + tick.size,
            )
            return None

        if bucket_start < self._current.start_ts:
            return None

        closed = self._current
        self._current = Candle(
            symbol=self.symbol,
            window=self.window,
            start_ts=bucket_start,
            end_ts=bucket_end,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=tick.size,
        )
        return closed