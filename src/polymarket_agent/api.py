from __future__ import annotations

import os
import sys
import threading
import time
from datetime import timezone

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .review.models import ReplayRequest, ReviewListResponse
from .review.runtime import get_or_create_review_service
from .state import agent_state

app = FastAPI(title="Polymarket Agent API", version="0.1.0")


def _schedule_process_restart(delay_seconds: float = 0.4) -> None:
    def _restart() -> None:
        time.sleep(delay_seconds)
        os.execv(sys.executable, [sys.executable, *sys.argv])

    threading.Thread(target=_restart, daemon=True).start()


class KillSwitchRequest(BaseModel):
    enabled: bool


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/status")
async def status() -> dict:
    return agent_state.snapshot()


@app.get("/paper-trades")
async def paper_trades() -> dict:
    return {"items": agent_state.get_paper_trade_entries()}


@app.post("/admin/kill-switch")
async def set_kill_switch(payload: KillSwitchRequest) -> dict:
    agent_state.set_kill_switch(payload.enabled)
    return {"ok": True, "kill_switch_enabled": agent_state.is_kill_switch_enabled()}


@app.post("/admin/restart")
async def restart_agent() -> dict:
    agent_state.add_event("warning", "agent_restart_requested", {})
    _schedule_process_restart()
    return {"ok": True, "restarting": True}


@app.get("/reviews/latest")
async def get_latest_review() -> dict:
    review_service = await get_or_create_review_service()
    review = review_service.latest_review()
    if review is None:
        raise HTTPException(status_code=404, detail="no reviews found")
    return review.model_dump(mode="json")


@app.get("/reviews")
async def list_reviews(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
) -> dict:
    review_service = await get_or_create_review_service()
    items = review_service.list_reviews(limit=limit, status=status)
    response = ReviewListResponse(items=items, next_cursor=None)
    return response.model_dump(mode="json")


@app.get("/reviews/{review_id}")
async def get_review_detail(review_id: str) -> dict:
    review_service = await get_or_create_review_service()
    review = review_service.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="review not found")
    return review.model_dump(mode="json")


@app.post("/admin/reviews/replay", status_code=202)
async def replay_review(payload: ReplayRequest) -> dict:
    review_service = await get_or_create_review_service()
    await review_service.replay(
        market_id=payload.market_id,
        round_close_ts=payload.round_close_ts.astimezone(timezone.utc),
        review_version=payload.review_version,
    )
    return {
        "accepted": True,
        "review_key": {
            "market_id": payload.market_id,
            "round_close_ts": payload.round_close_ts.astimezone(timezone.utc).isoformat(),
            "review_version": payload.review_version,
        },
    }
