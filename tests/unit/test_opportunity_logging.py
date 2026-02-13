from src.polymarket_agent.main import should_log_discrete_event, should_log_material_event


def test_should_log_opportunity_first_event() -> None:
    current = {
        "round_id": 1,
        "action": "BUY_YES",
        "price": 100.0,
        "polymarket_yes_price": 0.6,
        "polymarket_no_price": 0.4,
    }

    assert should_log_material_event(current, None) is True


def test_should_not_log_duplicate_under_3pct() -> None:
    previous = {
        "round_id": 1,
        "action": "BUY_YES",
        "price": 100.0,
        "polymarket_yes_price": 0.6,
        "polymarket_no_price": 0.4,
    }
    current = {
        "round_id": 1,
        "action": "BUY_YES",
        "price": 101.5,
        "polymarket_yes_price": 0.615,
        "polymarket_no_price": 0.395,
    }

    assert should_log_material_event(current, previous) is False


def test_should_log_when_any_metric_changes_by_3pct_or_more() -> None:
    previous = {
        "round_id": 1,
        "action": "BUY_YES",
        "price": 100.0,
        "polymarket_yes_price": 0.6,
        "polymarket_no_price": 0.4,
    }
    current = {
        "round_id": 1,
        "action": "BUY_YES",
        "price": 103.0,
        "polymarket_yes_price": 0.6,
        "polymarket_no_price": 0.4,
    }

    assert should_log_material_event(current, previous) is True


def test_should_log_when_round_or_action_changes() -> None:
    previous = {
        "round_id": 1,
        "action": "BUY_YES",
        "price": 100.0,
        "polymarket_yes_price": 0.6,
        "polymarket_no_price": 0.4,
    }
    current_round_change = {
        "round_id": 2,
        "action": "BUY_YES",
        "price": 100.0,
        "polymarket_yes_price": 0.6,
        "polymarket_no_price": 0.4,
    }
    current_action_change = {
        "round_id": 1,
        "action": "BUY_NO",
        "price": 100.0,
        "polymarket_yes_price": 0.6,
        "polymarket_no_price": 0.4,
    }

    assert should_log_material_event(current_round_change, previous) is True
    assert should_log_material_event(current_action_change, previous) is True


def test_should_log_material_event_with_custom_metric_keys() -> None:
    previous = {
        "round_id": 1,
        "action": "BUY_NO",
        "price": 100.0,
        "yes_price": 0.5,
        "no_price": 0.5,
    }
    current = {
        "round_id": 1,
        "action": "BUY_NO",
        "price": 100.0,
        "yes_price": 0.52,
        "no_price": 0.48,
    }

    assert (
        should_log_material_event(
            current,
            previous,
            metric_keys=("price", "yes_price", "no_price"),
        )
        is True
    )


def test_should_log_discrete_event_only_on_identity_change() -> None:
    previous = {"round_id": 1, "action": "BUY_YES", "reason": "kill_switch_enabled"}
    same = {"round_id": 1, "action": "BUY_YES", "reason": "kill_switch_enabled"}
    changed = {"round_id": 1, "action": "BUY_YES", "reason": "trade_cooldown:1.2s"}

    assert (
        should_log_discrete_event(
            same,
            previous,
            identity_keys=("round_id", "action", "reason"),
        )
        is False
    )
    assert (
        should_log_discrete_event(
            changed,
            previous,
            identity_keys=("round_id", "action", "reason"),
        )
        is True
    )
