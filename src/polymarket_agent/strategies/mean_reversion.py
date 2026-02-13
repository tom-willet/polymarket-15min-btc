from __future__ import annotations

from .base import Strategy, StrategyDecision


class MeanReversionStrategy(Strategy):
    name = "mean_reversion"

    def evaluate(self, state: dict) -> StrategyDecision | None:
        zscore = state.get("zscore")
        if zscore is None:
            return None
        if zscore > 1.75:
            return StrategyDecision(action="BUY_NO", confidence=0.57, reason="price stretched high")
        if zscore < -1.75:
            return StrategyDecision(action="BUY_YES", confidence=0.57, reason="price stretched low")
        return None
