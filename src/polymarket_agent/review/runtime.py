from __future__ import annotations

from datetime import datetime
import threading

from ..config import Config, load_config
from ..state import agent_state
from .repository import ReviewRepository
from .service import ReviewService, ReviewServiceConfig

_review_service: ReviewService | None = None
_lock = threading.Lock()


def _build_review_config(config: Config) -> ReviewServiceConfig:
    return ReviewServiceConfig(
        enabled=config.llm_review_enabled,
        provider=config.llm_review_provider,
        model=config.llm_review_model,
        timeout_seconds=config.llm_review_timeout_seconds,
        max_retries=config.llm_review_max_retries,
        review_version=config.llm_review_version,
        min_abs_score=config.llm_review_min_abs_score,
        require_trade=config.llm_review_require_trade,
        save_input_payload=config.llm_review_save_input_payload,
        payload_retention_days=config.llm_review_payload_retention_days,
        advisory_only=True,
    )


async def get_or_create_review_service(config: Config | None = None) -> ReviewService:
    global _review_service

    if _review_service is not None:
        return _review_service

    with _lock:
        if _review_service is not None:
            return _review_service

        cfg = config or load_config()
        service = ReviewService(
            config=_build_review_config(cfg),
            repository=ReviewRepository(),
            state=agent_state,
        )
    await service.start()
    _review_service = service
    return service


def get_review_service() -> ReviewService | None:
    return _review_service


async def enqueue_market_close_review(
    *,
    market_id: str,
    market_slug: str,
    round_id: int | None,
    round_open_ts: datetime,
    round_close_ts: datetime,
) -> bool:
    service = await get_or_create_review_service()
    return await service.enqueue_from_snapshot(
        market_id=market_id,
        market_slug=market_slug,
        round_id=round_id,
        round_open_ts=round_open_ts,
        round_close_ts=round_close_ts,
    )
