from src.polymarket_agent.decision import DecisionRouter
from src.polymarket_agent.models import Tick


def test_decision_router_returns_none_with_insufficient_context() -> None:
    router = DecisionRouter()

    decision = router.on_tick(Tick(ts=1.0, symbol="BTC", price=100.0))

    assert decision is None


def test_decision_router_emits_momentum_buy_yes_on_short_uptrend() -> None:
    router = DecisionRouter()
    decision = None

    prices = [100.0, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7]
    for idx, price in enumerate(prices):
        decision = router.on_tick(Tick(ts=float(idx + 1), symbol="BTC", price=price))

    assert decision is not None
    action, payload = decision
    assert action == "BUY_YES"
    assert payload["strategy"] == "momentum"
