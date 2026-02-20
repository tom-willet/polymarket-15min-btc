from datetime import datetime, timezone

from src.polymarket_agent.review.repository import ReviewRepository


def test_repository_upsert_is_idempotent(tmp_path) -> None:
    repo = ReviewRepository(db_path=str(tmp_path / "reviews.sqlite3"))
    close_ts = datetime(2026, 2, 18, 15, 15, tzinfo=timezone.utc)
    open_ts = datetime(2026, 2, 18, 15, 0, tzinfo=timezone.utc)

    first = repo.upsert_review(
        market_id="m1",
        market_slug="m1",
        round_id=1,
        round_open_ts=open_ts,
        round_close_ts=close_ts,
        strategy_mode="classic",
        review_version="v1.0",
        provider="openai",
        model="gpt",
        prompt_hash="abc",
        input_payload_json={"x": 1},
        status="queued",
    )

    second = repo.upsert_review(
        market_id="m1",
        market_slug="m1",
        round_id=1,
        round_open_ts=open_ts,
        round_close_ts=close_ts,
        strategy_mode="classic",
        review_version="v1.0",
        provider="openai",
        model="gpt",
        prompt_hash="abc",
        input_payload_json={"x": 2},
        status="succeeded",
        analysis_json={"summary": {}},
        analysis_markdown="ok",
    )

    assert first.id == second.id
    latest = repo.latest_review()
    assert latest is not None
    assert latest.status == "succeeded"


def test_repository_list_filters_by_status(tmp_path) -> None:
    repo = ReviewRepository(db_path=str(tmp_path / "reviews.sqlite3"))
    now = datetime(2026, 2, 18, 15, 15, tzinfo=timezone.utc)

    repo.upsert_review(
        market_id="m1",
        market_slug="m1",
        round_id=1,
        round_open_ts=now,
        round_close_ts=now,
        strategy_mode="classic",
        review_version="v1",
        provider="openai",
        model="gpt",
        prompt_hash="a",
        input_payload_json={},
        status="failed",
        error_message="x",
    )
    repo.upsert_review(
        market_id="m2",
        market_slug="m2",
        round_id=2,
        round_open_ts=now,
        round_close_ts=now,
        strategy_mode="classic",
        review_version="v1",
        provider="openai",
        model="gpt",
        prompt_hash="b",
        input_payload_json={},
        status="succeeded",
        analysis_json={"ok": True},
        analysis_markdown="ok",
    )

    failed = repo.list_reviews(limit=50, status="failed")
    assert len(failed) == 1
    assert failed[0].market_id == "m1"
