from datetime import datetime, timezone
import asyncio

from src.polymarket_agent.review.repository import ReviewRepository
from src.polymarket_agent.review.service import ReviewService, ReviewServiceConfig
from src.polymarket_agent.state import AgentState


def test_timeout_retry_failed_persistence(tmp_path, monkeypatch) -> None:
    async def _run() -> None:
        state = AgentState()
        state.set_decision({"score": 0.9})

        service = ReviewService(
            config=ReviewServiceConfig(
                enabled=True,
                provider="openai",
                model="gpt",
                timeout_seconds=1,
                max_retries=1,
                review_version="v1.0",
                min_abs_score=0.25,
                require_trade=False,
                save_input_payload=True,
                payload_retention_days=30,
            ),
            repository=ReviewRepository(db_path=str(tmp_path / "reviews.sqlite3")),
            state=state,
        )

        async def always_fail(*, system_prompt: str, user_prompt: str):
            raise RuntimeError("timeout")

        monkeypatch.setattr(service._client, "run", always_fail)  # noqa: SLF001

        await service.start()
        try:
            await service.enqueue_from_snapshot(
                market_id="m2",
                market_slug="m2",
                round_id=2,
                round_open_ts=datetime(2026, 2, 18, 16, 0, tzinfo=timezone.utc),
                round_close_ts=datetime(2026, 2, 18, 16, 15, tzinfo=timezone.utc),
            )
            await service._queue.join()  # noqa: SLF001

            rows = service.list_reviews(limit=10, status="failed")
            assert len(rows) == 1
        finally:
            await service.stop()

    asyncio.run(_run())
