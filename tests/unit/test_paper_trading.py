from src.polymarket_agent.paper_trading import evaluate_paper_trade


def test_evaluate_paper_trade_buy_yes_win() -> None:
    result = evaluate_paper_trade("BUY_YES", entry_price=100.0, exit_price=103.0)

    assert result.outcome == "win"
    assert round(result.return_pct, 4) == 3.0


def test_evaluate_paper_trade_buy_no_win() -> None:
    result = evaluate_paper_trade("BUY_NO", entry_price=100.0, exit_price=97.0)

    assert result.outcome == "win"
    assert round(result.return_pct, 4) == 3.0
