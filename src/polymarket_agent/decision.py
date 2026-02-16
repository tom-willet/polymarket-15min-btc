from __future__ import annotations

import logging
from collections import deque
from statistics import fmean, pstdev

from .models import Tick
from .strategies import (
    BTCUpdownConfig,
    BTCUpdownStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    Strategy,
)

logger = logging.getLogger(__name__)


class DecisionRouter:
    def __init__(
        self,
        *,
        strategy_mode: str = "classic",
        btc_updown_shadow_mode: bool = True,
        btc_updown_live_enabled: bool = False,
        btc_updown_config: BTCUpdownConfig | None = None,
    ) -> None:
        self.prices: deque[float] = deque(maxlen=240)
        self._strategy_mode = strategy_mode
        self._btc_updown_shadow_mode = btc_updown_shadow_mode
        self._btc_updown_live_enabled = btc_updown_live_enabled
        self._btc_updown = BTCUpdownStrategy(btc_updown_config or BTCUpdownConfig())
        self.strategies: list[Strategy] = [
            MomentumStrategy(),
            MeanReversionStrategy(),
        ]

    def on_tick(self, tick: Tick, extra_state: dict | None = None) -> tuple[str, dict] | None:
        self.prices.append(tick.price)
        state = self._build_state(tick)
        if extra_state:
            state.update(extra_state)

        if self._btc_updown_shadow_mode or self._strategy_mode == "btc_updown":
            shadow = self._btc_updown.evaluate_shadow(state)
            if shadow is not None:
                logger.info("Shadow strategy=btc_updown candidate=%s", shadow)
                if self._strategy_mode == "btc_updown" and self._btc_updown_live_enabled:
                    return shadow["action"], shadow

        if self._strategy_mode == "btc_updown":
            return None

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
