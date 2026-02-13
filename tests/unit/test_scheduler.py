from src.polymarket_agent.scheduler import RoundScheduler


def test_current_round_computes_boundaries() -> None:
    scheduler = RoundScheduler(round_seconds=900, activation_lead_seconds=180)

    window = scheduler.current_round(now_ts=1000)

    assert window.round_id == 1
    assert window.start_ts == 900
    assert window.close_ts == 1800
    assert window.activation_ts == 1620


def test_current_round_changes_at_boundary() -> None:
    scheduler = RoundScheduler(round_seconds=900, activation_lead_seconds=180)

    before = scheduler.current_round(now_ts=1799.9)
    after = scheduler.current_round(now_ts=1800.0)

    assert before.round_id == 1
    assert after.round_id == 2
