from __future__ import annotations

import logging
from collections import deque
from statistics import fmean, pstdev

from .models import Tick
from .strategies import MeanReversionStrategy, MomentumStrategy, Strategy

logger = logging.getLogger(__name__)


class DecisionRouter:
    def __init__(self) -> None:
        self.prices: deque[float] = deque(maxlen=240)
        self.strategies: list[Strategy] = [
            MomentumStrategy(),
            MeanReversionStrategy(),
        ]

    def on_tick(self, tick: Tick) -> tuple[str, dict] | None:
        self.prices.append(tick.price)
        state = self._build_state(tick)

        for strategy in self.strategies:
            decision = strategy.evaluate(state)
            if decision is None:
                continue
            payload = {
                "strategy": strategy.name,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "price": tick.price,
                "tick_ts": tick.ts,
            }
            logger.info("Selected strategy=%s action=%s payload=%s", strategy.name, decision.action, payload)
            return decision.action, payload

        return None

    def _build_state(self, tick: Tick) -> dict:
        state: dict = {
            "last_price": tick.price,
        }

        if len(self.prices) >= 8:
            p_now = self.prices[-1]
            p_then = self.prices[-8]
            if p_then != 0:
                state["return_short"] = (p_now / p_then) - 1.0

        if len(self.prices) >= 30:
            prices = list(self.prices)[-30:]
            mean = fmean(prices)
            sigma = pstdev(prices)
            if sigma > 0:
                state["zscore"] = (tick.price - mean) / sigma

        return state
