from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .base import Strategy, StrategyDecision


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class SignalScore:
    score: float
    confidence: float
    reason: str
    available: bool = True


@dataclass(frozen=True)
class BTCUpdownConfig:
    min_confidence_to_trade: float = 0.35
    min_score_to_trade: float = 0.2
    max_entry_price: float = 0.85
    kelly_fraction: float = 0.3
    max_trade_size_usd: float = 100.0
    min_trade_size_usd: float = 1.0
    weight_time_decay: float = 0.20
    weight_orderbook_imbalance: float = 0.20
    weight_trade_momentum: float = 0.15
    weight_btc_price_movement: float = 0.20
    weight_price_inefficiency: float = 0.20
    weight_feed_comparison: float = 0.05


class BTCUpdownStrategy(Strategy):
    name = "btc_updown"

    def __init__(self, config: BTCUpdownConfig | None = None) -> None:
        self._config = config or BTCUpdownConfig()
        self._recent_actions: deque[str] = deque(maxlen=40)

    def evaluate(self, state: dict) -> StrategyDecision | None:
        shadow = self.evaluate_shadow(state)
        if shadow is None:
            return None
        return StrategyDecision(
            action=shadow["action"],
            confidence=float(shadow["confidence"]),
            reason=str(shadow["reason"]),
        )

    def evaluate_shadow(self, state: dict) -> dict | None:
        signals = {
            "time_decay": self._signal_time_decay(state),
            "orderbook_imbalance": self._signal_orderbook_imbalance(state),
            "trade_momentum": self._signal_trade_momentum(state),
            "btc_price_movement": self._signal_btc_price_movement(state),
            "price_inefficiency": self._signal_price_inefficiency(state),
            "feed_comparison": self._signal_feed_comparison(state),
        }

        composite_score, composite_confidence = self._calculate_composite(signals)

        action = "BUY_YES" if composite_score > 0 else "BUY_NO"
        required_score = self._config.min_score_to_trade
        if action == "BUY_NO" and self._buy_no_share() > 0.75:
            required_score += 0.05

        if composite_confidence < self._config.min_confidence_to_trade:
            return None
        if abs(composite_score) < required_score:
            return None

        entry_price = state.get("polymarket_yes_price") if action == "BUY_YES" else state.get("polymarket_no_price")

        if isinstance(entry_price, (int, float)) and entry_price > self._config.max_entry_price:
            return None

        size_usd = self._calculate_position_size(
            confidence=composite_confidence,
            entry_price=float(entry_price) if isinstance(entry_price, (int, float)) else 0.5,
        )
        if size_usd < self._config.min_trade_size_usd:
            return None

        self._recent_actions.append(action)

        return {
            "strategy": self.name,
            "action": action,
            "confidence": round(composite_confidence, 4),
            "score": round(composite_score, 4),
            "price": entry_price,
            "size_usd": round(size_usd, 2),
            "reason": "composite_signal",
            "signals": {
                key: {
                    "score": round(value.score, 4),
                    "confidence": round(value.confidence, 4),
                    "reason": value.reason,
                    "available": value.available,
                }
                for key, value in signals.items()
            },
        }

    def _buy_no_share(self) -> float:
        if not self._recent_actions:
            return 0.0
        buy_no_count = sum(1 for action in self._recent_actions if action == "BUY_NO")
        return buy_no_count / len(self._recent_actions)

    def _calculate_position_size(self, *, confidence: float, entry_price: float) -> float:
        if entry_price <= 0 or entry_price >= 1:
            return 0.0

        p = _clamp(confidence, 0.01, 0.99)
        q = 1.0 - p
        b = (1.0 - entry_price) / entry_price
        if b <= 0:
            return 0.0

        kelly = ((p * b) - q) / b
        kelly = max(0.0, kelly) * self._config.kelly_fraction

        return min(self._config.max_trade_size_usd, kelly * self._config.max_trade_size_usd)

    def _calculate_composite(self, signals: dict[str, SignalScore]) -> tuple[float, float]:
        weights = {
            "time_decay": self._config.weight_time_decay,
            "orderbook_imbalance": self._config.weight_orderbook_imbalance,
            "trade_momentum": self._config.weight_trade_momentum,
            "btc_price_movement": self._config.weight_btc_price_movement,
            "price_inefficiency": self._config.weight_price_inefficiency,
            "feed_comparison": self._config.weight_feed_comparison,
        }

        weight_total = 0.0
        score_total = 0.0
        conf_total = 0.0
        directional = 0
        agreeing = 0

        for key, signal in signals.items():
            w = weights[key]
            score_total += signal.score * w
            conf_total += signal.confidence * w
            weight_total += w

            if signal.score > 0.1:
                directional += 1
                agreeing += 1
            elif signal.score < -0.1:
                directional += 1
                agreeing -= 1

        if weight_total <= 0:
            return 0.0, 0.0

        score = score_total / weight_total
        confidence = conf_total / weight_total

        if directional > 0:
            agreement_ratio = abs(agreeing) / directional
            confidence = _clamp(confidence + (0.15 * agreement_ratio), 0.0, 1.0)

        return _clamp(score, -1.0, 1.0), _clamp(confidence, 0.0, 1.0)

    def _signal_time_decay(self, state: dict) -> SignalScore:
        seconds_to_close = state.get("seconds_to_close")
        round_seconds = state.get("round_seconds")
        movement = state.get("return_short")
        if not isinstance(seconds_to_close, (int, float)) or not isinstance(round_seconds, (int, float)):
            return SignalScore(score=0.0, confidence=0.1, reason="missing_time_context", available=False)
        if not isinstance(movement, (int, float)):
            return SignalScore(score=0.0, confidence=0.1, reason="missing_btc_movement", available=False)

        closeness = 1.0 - _clamp(seconds_to_close / max(round_seconds, 1), 0.0, 1.0)
        if closeness < 0.6:
            return SignalScore(score=0.0, confidence=0.15, reason="outside_decay_window")

        score = _clamp(float(movement) * 80.0, -1.0, 1.0)
        confidence = _clamp(0.3 + (0.5 * closeness), 0.0, 1.0)
        return SignalScore(score=score, confidence=confidence, reason="time_decay_active")

    def _signal_orderbook_imbalance(self, state: dict) -> SignalScore:
        imbalance = state.get("orderbook_imbalance")
        if not isinstance(imbalance, (int, float)):
            return SignalScore(score=0.0, confidence=0.1, reason="orderbook_unavailable", available=False)
        score = _clamp(float(imbalance), -1.0, 1.0)
        confidence = _clamp(0.3 + abs(score) * 0.5, 0.0, 1.0)
        return SignalScore(score=score, confidence=confidence, reason="orderbook_imbalance")

    def _signal_trade_momentum(self, state: dict) -> SignalScore:
        momentum = state.get("trade_momentum")
        if not isinstance(momentum, (int, float)):
            return SignalScore(score=0.0, confidence=0.1, reason="trade_flow_unavailable", available=False)
        score = _clamp(float(momentum), -1.0, 1.0)
        confidence = _clamp(0.25 + abs(score) * 0.6, 0.0, 1.0)
        return SignalScore(score=score, confidence=confidence, reason="trade_momentum")

    def _signal_btc_price_movement(self, state: dict) -> SignalScore:
        short_return = state.get("return_short")
        if not isinstance(short_return, (int, float)):
            return SignalScore(score=0.0, confidence=0.1, reason="missing_return_short", available=False)
        if abs(short_return) < 0.0001:
            return SignalScore(score=0.0, confidence=0.15, reason="movement_noise")
        score = _clamp(float(short_return) * 50.0, -1.0, 1.0)
        confidence = _clamp(0.3 + abs(float(short_return)) * 250.0, 0.0, 0.95)
        return SignalScore(score=score, confidence=confidence, reason="btc_price_movement")

    def _signal_price_inefficiency(self, state: dict) -> SignalScore:
        zscore = state.get("zscore")
        yes_price = state.get("polymarket_yes_price")
        if not isinstance(zscore, (int, float)) or not isinstance(yes_price, (int, float)):
            return SignalScore(score=0.0, confidence=0.1, reason="missing_inefficiency_inputs", available=False)

        fair_yes = _clamp(0.5 - (float(zscore) * 0.08), 0.05, 0.95)
        mispricing = fair_yes - float(yes_price)
        if abs(mispricing) < 0.05:
            return SignalScore(score=0.0, confidence=0.15, reason="mispricing_small")

        score = _clamp(mispricing * 5.0, -1.0, 1.0)
        confidence = _clamp(0.25 + abs(mispricing) * 2.0, 0.0, 0.95)
        return SignalScore(score=score, confidence=confidence, reason="price_inefficiency")

    def _signal_feed_comparison(self, state: dict) -> SignalScore:
        divergence_bps = state.get("feed_divergence_bps")
        if not isinstance(divergence_bps, (int, float)):
            return SignalScore(score=0.0, confidence=0.2, reason="single_feed_mode", available=False)
        if float(divergence_bps) > 5.0:
            return SignalScore(score=0.0, confidence=0.05, reason="feeds_diverged")

        movement = state.get("return_short")
        if not isinstance(movement, (int, float)):
            return SignalScore(score=0.0, confidence=0.2, reason="missing_direction")

        score = 0.15 if movement > 0 else -0.15 if movement < 0 else 0.0
        return SignalScore(score=score, confidence=0.75, reason="feeds_agree")