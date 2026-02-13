from __future__ import annotations

from .base import Strategy, StrategyDecision


class MomentumStrategy(Strategy):
    name = "momentum"

    def evaluate(self, state: dict) -> StrategyDecision | None:
        short = state.get("return_short")
        if short is None:
            return None
        if short > 0.0012:
            return StrategyDecision(action="BUY_YES", confidence=0.62, reason="short momentum up")
        if short < -0.0012:
            return StrategyDecision(action="BUY_NO", confidence=0.62, reason="short momentum down")
        return None
