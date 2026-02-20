from src.polymarket_agent.review.repository import ReviewRepository
from src.polymarket_agent.review.service import ReviewService, ReviewServiceConfig


def test_advisory_guard_blocks_auto_apply(tmp_path) -> None:
    service = ReviewService(
        config=ReviewServiceConfig(
            enabled=True,
            provider="openai",
            model="gpt",
            timeout_seconds=10,
            max_retries=0,
            review_version="v1",
            min_abs_score=0.2,
            require_trade=False,
            save_input_payload=True,
            payload_retention_days=30,
            advisory_only=True,
        ),
        repository=ReviewRepository(db_path=str(tmp_path / "reviews.sqlite3")),
    )

    guarded = service._apply_advisory_guard({"parameter_suggestions": [{"name": "x"}]})  # noqa: SLF001
    assert guarded["auto_apply_blocked"] is True
