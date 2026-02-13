from src.polymarket_agent.risk import RiskGuard, RiskLimits


def test_risk_guard_allows_first_trade() -> None:
    guard = RiskGuard(RiskLimits(max_trades_per_round=2, trade_cooldown_seconds=8))

    result = guard.evaluate(round_id=100, now_ts=1000.0)

    assert result.allowed is True
    assert result.reason == "ok"


def test_risk_guard_blocks_trade_when_round_limit_reached() -> None:
    guard = RiskGuard(RiskLimits(max_trades_per_round=1, trade_cooldown_seconds=0))
    guard.record_execution(round_id=100, now_ts=1000.0)

    result = guard.evaluate(round_id=100, now_ts=1001.0)

    assert result.allowed is False
    assert result.reason == "max_trades_per_round"


def test_risk_guard_blocks_trade_during_cooldown() -> None:
    guard = RiskGuard(RiskLimits(max_trades_per_round=10, trade_cooldown_seconds=8))
    guard.record_execution(round_id=100, now_ts=1000.0)

    result = guard.evaluate(round_id=100, now_ts=1003.0)

    assert result.allowed is False
    assert result.reason.startswith("trade_cooldown:")