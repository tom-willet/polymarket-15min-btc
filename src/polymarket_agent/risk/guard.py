from __future__ import annotations

import threading
from dataclasses import dataclass

from .limits import RiskLimits


@dataclass(frozen=True)
class RiskCheckResult:
    allowed: bool
    reason: str


class RiskGuard:
    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits
        self._lock = threading.Lock()
        self._trade_count_by_round: dict[int, int] = {}
        self._last_trade_ts: float | None = None

    def evaluate(self, round_id: int, now_ts: float) -> RiskCheckResult:
        with self._lock:
            if self._last_trade_ts is not None:
                elapsed = now_ts - self._last_trade_ts
                if elapsed < self._limits.trade_cooldown_seconds:
                    remaining = self._limits.trade_cooldown_seconds - elapsed
                    return RiskCheckResult(False, f"trade_cooldown:{remaining:.2f}s")

            current_round_count = self._trade_count_by_round.get(round_id, 0)
            if current_round_count >= self._limits.max_trades_per_round:
                return RiskCheckResult(False, "max_trades_per_round")

            return RiskCheckResult(True, "ok")

    def record_execution(self, round_id: int, now_ts: float) -> None:
        with self._lock:
            self._trade_count_by_round[round_id] = self._trade_count_by_round.get(round_id, 0) + 1
            self._last_trade_ts = now_ts