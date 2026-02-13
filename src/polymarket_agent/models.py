from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tick:
    ts: float
    symbol: str
    price: float
    size: float = 1.0


@dataclass(frozen=True)
class Candle:
    symbol: str
    window: str
    start_ts: float
    end_ts: float
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class RoundWindow:
    round_id: int
    start_ts: float
    close_ts: float
    activation_ts: float
