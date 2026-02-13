from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_trades_per_round: int = 2
    trade_cooldown_seconds: int = 8