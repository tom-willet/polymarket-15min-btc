from src.polymarket_agent.paper_trading import (
    PaperTradeSimulationConfig,
    apply_entry_execution,
    compute_effective_entry_slippage_bps,
    estimate_expected_edge_bps,
    estimate_total_cost_bps,
    evaluate_paper_trade,
)


def test_evaluate_paper_trade_buy_yes_win() -> None:
    result = evaluate_paper_trade(
        "BUY_YES",
        entry_price=0.4,
        market_outcome="yes",
        notional_usd=100.0,
        simulation=PaperTradeSimulationConfig(
            entry_slippage_bps=0.0,
            gas_fee_usd_per_side=0.0,
            adverse_selection_bps=0.0,
            min_notional_usd=1.0,
        ),
    )

    assert result.outcome == "win"
    assert round(result.return_pct, 4) == 150.0
    assert round(result.gross_pnl_usd, 4) == 150.0
    assert round(result.pnl_usd, 4) == 150.0


def test_evaluate_paper_trade_buy_no_win() -> None:
    result = evaluate_paper_trade(
        "BUY_NO",
        entry_price=0.35,
        market_outcome="no",
        notional_usd=100.0,
        simulation=PaperTradeSimulationConfig(
            entry_slippage_bps=0.0,
            gas_fee_usd_per_side=0.0,
            adverse_selection_bps=0.0,
            min_notional_usd=1.0,
        ),
    )

    assert result.outcome == "win"
    assert round(result.return_pct, 4) == 185.7143


def test_apply_entry_execution_worsens_fill_by_side() -> None:
    simulation = PaperTradeSimulationConfig(entry_slippage_bps=50.0)

    yes_price = apply_entry_execution("BUY_YES", 0.5, simulation)
    no_price = apply_entry_execution("BUY_NO", 0.5, simulation)

    assert round(yes_price, 4) == 0.5025
    assert round(no_price, 4) == 0.5025


def test_evaluate_paper_trade_applies_costs_and_adverse_selection() -> None:
    simulation = PaperTradeSimulationConfig(
        entry_slippage_bps=0.0,
        gas_fee_usd_per_side=0.05,
        adverse_selection_bps=30.0,
        min_notional_usd=1.0,
    )

    result = evaluate_paper_trade(
        "BUY_YES",
        entry_price=0.8,
        market_outcome="yes",
        notional_usd=25.0,
        simulation=simulation,
    )

    assert result.outcome == "win"
    assert round(result.gross_return_pct, 4) == 25.0
    assert round(result.total_cost_pct, 4) == 0.4
    assert round(result.return_pct, 4) == 24.6
    assert round(result.gas_fees_usd, 4) == 0.1
    assert round(result.gross_pnl_usd, 4) == 6.25
    assert round(result.pnl_usd, 4) == 6.15
    assert result.adverse_selection_bps_applied == 0.0


def test_evaluate_paper_trade_invalid_has_zero_pnl() -> None:
    result = evaluate_paper_trade(
        "BUY_YES",
        entry_price=1.0,
        market_outcome="yes",
        notional_usd=25.0,
        simulation=PaperTradeSimulationConfig(min_notional_usd=1.0),
    )

    assert result.outcome == "invalid"
    assert result.gross_pnl_usd == 0.0
    assert result.pnl_usd == 0.0


def test_compute_effective_entry_slippage_bps_dynamic_and_capped() -> None:
    simulation = PaperTradeSimulationConfig(
        entry_slippage_bps=50.0,
        dynamic_slippage_enabled=True,
        dynamic_slippage_edge_factor_bps=25.0,
        dynamic_slippage_confidence_factor_bps=20.0,
        dynamic_slippage_expiry_factor_bps=30.0,
        max_slippage_bps=120.0,
    )

    effective = compute_effective_entry_slippage_bps(
        simulation,
        edge_strength=1.0,
        confidence=0.9,
        seconds_to_close=0,
        round_seconds=900,
    )

    assert effective == 120.0


def test_apply_entry_execution_uses_effective_slippage_override() -> None:
    simulation = PaperTradeSimulationConfig(entry_slippage_bps=50.0)

    price = apply_entry_execution(
        "BUY_YES",
        0.5,
        simulation,
        slippage_bps=100.0,
    )

    assert round(price, 4) == 0.505


def test_estimate_expected_edge_bps_uses_edge_and_confidence_weight() -> None:
    expected = estimate_expected_edge_bps(
        edge_strength=0.8,
        confidence=0.6,
        edge_strength_to_bps=1000.0,
    )

    assert round(expected, 4) == 160.0


def test_estimate_total_cost_bps_includes_slippage_adverse_and_gas() -> None:
    simulation = PaperTradeSimulationConfig(
        entry_slippage_bps=50.0,
        gas_fee_usd_per_side=0.05,
        adverse_selection_bps=30.0,
        min_notional_usd=1.0,
    )

    cost_bps = estimate_total_cost_bps(
        notional_usd=25.0,
        simulation=simulation,
        effective_entry_slippage_bps=62.0,
    )

    assert round(cost_bps, 4) == 132.0
