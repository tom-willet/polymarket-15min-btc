from datetime import datetime, timezone
import asyncio

from src.polymarket_agent.review.repository import ReviewRepository
from src.polymarket_agent.review.service import ReviewService, ReviewServiceConfig
from src.polymarket_agent.state import AgentState


def test_market_close_trigger_creates_one_review(tmp_path, monkeypatch) -> None:
    async def _run() -> None:
        state = AgentState()
        state.set_decision({"score": 0.9})

        service = ReviewService(
            config=ReviewServiceConfig(
                enabled=True,
                provider="openai",
                model="gpt",
                timeout_seconds=5,
                max_retries=0,
                review_version="v1.0",
                min_abs_score=0.25,
                require_trade=False,
                save_input_payload=True,
                payload_retention_days=30,
            ),
            repository=ReviewRepository(db_path=str(tmp_path / "reviews.sqlite3")),
            state=state,
        )

        async def fake_run(*, system_prompt: str, user_prompt: str):
            from src.polymarket_agent.review.models import ProviderResult

            return ProviderResult(
                raw_text='{"summary":{"market_outcome":"yes","pnl_usd":1.0,"overall_grade":"A"},"decision_assessment":[],"risk_findings":[],"parameter_suggestions":[],"next_experiments":[]}',
            )

        monkeypatch.setattr(service._client, "run", fake_run)  # noqa: SLF001

        await service.start()
        try:
            accepted = await service.enqueue_from_snapshot(
                market_id="m1",
                market_slug="m1",
                round_id=1,
                round_open_ts=datetime(2026, 2, 18, 15, 0, tzinfo=timezone.utc),
                round_close_ts=datetime(2026, 2, 18, 15, 15, tzinfo=timezone.utc),
            )
            assert accepted is True
            await service._queue.join()  # noqa: SLF001

            rows = service.list_reviews(limit=10, status=None)
            assert len(rows) == 1
            assert rows[0].status == "succeeded"
        finally:
            await service.stop()

    asyncio.run(_run())
