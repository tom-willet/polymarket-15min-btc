from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.polymarket_agent.api import app
from src.polymarket_agent.review.models import ReviewSummary
from src.polymarket_agent.review.runtime import get_or_create_review_service

client = TestClient(app)


def _seed_review() -> str:
    import asyncio

    async def _seed() -> str:
        service = await get_or_create_review_service()
        row = service._repository.upsert_review(  # noqa: SLF001
            market_id="seed-market",
            market_slug="seed-market",
            round_id=1,
            round_open_ts=datetime(2026, 2, 18, 15, 0, tzinfo=timezone.utc),
            round_close_ts=datetime(2026, 2, 18, 15, 15, tzinfo=timezone.utc),
            strategy_mode="classic",
            review_version="v1.0",
            provider="openai",
            model="gpt",
            prompt_hash="hash",
            input_payload_json={"x": 1},
            status="succeeded",
            analysis_json={
                "summary": {
                    "market_outcome": "yes",
                    "pnl_usd": 1.0,
                    "overall_grade": "A",
                },
                "decision_assessment": [],
                "risk_findings": [],
                "parameter_suggestions": [],
                "next_experiments": [],
            },
            analysis_markdown="analysis",
        )
        return row.id

    return asyncio.run(_seed())


def test_review_endpoints_latest_list_detail() -> None:
    review_id = _seed_review()

    latest = client.get("/reviews/latest")
    assert latest.status_code == 200
    assert latest.json()["id"]

    listed = client.get("/reviews?limit=20&status=succeeded")
    assert listed.status_code == 200
    assert isinstance(listed.json().get("items"), list)

    detail = client.get(f"/reviews/{review_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == review_id
