from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PaperTradeResult:
    outcome: str
    market_outcome: str
    return_pct: float
    gross_return_pct: float
    total_cost_pct: float
    gas_fees_usd: float
    adverse_selection_bps_applied: float


@dataclass(frozen=True)
class PaperTradeSimulationConfig:
    entry_slippage_bps: float = 50.0
    dynamic_slippage_enabled: bool = False
    dynamic_slippage_edge_factor_bps: float = 25.0
    dynamic_slippage_confidence_factor_bps: float = 20.0
    dynamic_slippage_expiry_factor_bps: float = 30.0
    max_slippage_bps: float = 200.0
    gas_fee_usd_per_side: float = 0.05
    adverse_selection_bps: float = 30.0
    min_notional_usd: float = 1.0


def compute_effective_entry_slippage_bps(
    simulation: PaperTradeSimulationConfig,
    *,
    edge_strength: float | None,
    confidence: float | None,
    seconds_to_close: int | None,
    round_seconds: int | None,
) -> float:
    effective = simulation.entry_slippage_bps

    if not simulation.dynamic_slippage_enabled:
        return min(max(effective, 0.0), simulation.max_slippage_bps)

    edge_term = max(0.0, edge_strength or 0.0) * simulation.dynamic_slippage_edge_factor_bps

    conf = confidence if confidence is not None else 0.0
    conf_term = max(0.0, conf - 0.5) * 2.0 * simulation.dynamic_slippage_confidence_factor_bps

    expiry_term = 0.0
    if seconds_to_close is not None and round_seconds is not None and round_seconds > 0:
        bounded_seconds = min(max(seconds_to_close, 0), round_seconds)
        closeness = 1.0 - (bounded_seconds / round_seconds)
        expiry_term = closeness * simulation.dynamic_slippage_expiry_factor_bps

    effective = effective + edge_term + conf_term + expiry_term
    return min(max(effective, 0.0), simulation.max_slippage_bps)


def estimate_expected_edge_bps(
    *,
    edge_strength: float | None,
    confidence: float | None,
    edge_strength_to_bps: float,
) -> float:
    edge = max(0.0, edge_strength or 0.0)
    if edge <= 0:
        return 0.0

    conf = confidence if confidence is not None else 0.0
    conf = min(max(conf, 0.0), 1.0)
    confidence_weight = max(0.0, (conf - 0.5) * 2.0)

    return edge * max(0.0, edge_strength_to_bps) * confidence_weight


def estimate_total_cost_bps(
    *,
    notional_usd: float,
    simulation: PaperTradeSimulationConfig,
    effective_entry_slippage_bps: float,
) -> float:
    if notional_usd <= 0:
        return float("inf")

    gas_fees_usd = simulation.gas_fee_usd_per_side * 2.0
    gas_cost_bps = (gas_fees_usd / notional_usd) * 10_000.0

    return (
        max(0.0, effective_entry_slippage_bps)
        + max(0.0, simulation.adverse_selection_bps)
        + max(0.0, gas_cost_bps)
    )


def apply_entry_execution(
    action: str,
    reference_price: float,
    simulation: PaperTradeSimulationConfig,
    *,
    slippage_bps: float | None = None,
) -> float:
    if reference_price <= 0:
        return reference_price

    bps = slippage_bps if slippage_bps is not None else simulation.entry_slippage_bps
    slippage_ratio = bps / 10_000.0

    if action == "BUY_YES":
        return min(1.0, reference_price * (1.0 + slippage_ratio))
    if action == "BUY_NO":
        return max(0.0, reference_price * (1.0 + slippage_ratio))
    return reference_price


def evaluate_paper_trade(
    action: str,
    entry_price: float,
    market_outcome: str,
    *,
    notional_usd: float,
    simulation: PaperTradeSimulationConfig,
) -> PaperTradeResult:
    if entry_price <= 0 or entry_price >= 1:
        return PaperTradeResult(
            outcome="invalid",
            market_outcome=market_outcome,
            return_pct=0.0,
            gross_return_pct=0.0,
            total_cost_pct=0.0,
            gas_fees_usd=0.0,
            adverse_selection_bps_applied=0.0,
        )

    if notional_usd < simulation.min_notional_usd:
        return PaperTradeResult(
            outcome="invalid",
            market_outcome=market_outcome,
            return_pct=0.0,
            gross_return_pct=0.0,
            total_cost_pct=0.0,
            gas_fees_usd=0.0,
            adverse_selection_bps_applied=0.0,
        )

    normalized_outcome = market_outcome.strip().lower()
    if normalized_outcome not in {"yes", "no", "push"}:
        return PaperTradeResult(
            outcome="invalid",
            market_outcome=market_outcome,
            return_pct=0.0,
            gross_return_pct=0.0,
            total_cost_pct=0.0,
            gas_fees_usd=0.0,
            adverse_selection_bps_applied=0.0,
        )

    payout_per_share = 0.0
    if normalized_outcome == "push":
        payout_per_share = entry_price
    elif action == "BUY_YES":
        payout_per_share = 1.0 if normalized_outcome == "yes" else 0.0
    elif action == "BUY_NO":
        payout_per_share = 1.0 if normalized_outcome == "no" else 0.0
    else:
        return PaperTradeResult(
            outcome="invalid",
            market_outcome=market_outcome,
            return_pct=0.0,
            gross_return_pct=0.0,
            total_cost_pct=0.0,
            gas_fees_usd=0.0,
            adverse_selection_bps_applied=0.0,
        )

    raw_return = (payout_per_share - entry_price) / entry_price

    gross_return = raw_return

    gas_fees_usd = simulation.gas_fee_usd_per_side * 2.0
    gas_cost_pct = gas_fees_usd / max(notional_usd, 1e-9)

    adverse_selection_pct = 0.0
    adverse_selection_bps_applied = 0.0

    total_cost_pct = gas_cost_pct + adverse_selection_pct
    net_return = gross_return - total_cost_pct

    if net_return > 0:
        outcome = "win"
    elif net_return < 0:
        outcome = "loss"
    else:
        outcome = "flat"

    return PaperTradeResult(
        outcome=outcome,
        market_outcome=normalized_outcome,
        return_pct=net_return * 100,
        gross_return_pct=gross_return * 100,
        total_cost_pct=total_cost_pct * 100,
        gas_fees_usd=gas_fees_usd,
        adverse_selection_bps_applied=adverse_selection_bps_applied,
    )


class PaperTradeLogger:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: dict[str, Any]) -> None:
        payload = {
            "logged_at": time.time(),
            **entry,
        }
        line = json.dumps(payload, separators=(",", ":"), default=str)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
