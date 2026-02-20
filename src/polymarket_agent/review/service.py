from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..state import AgentState, agent_state
from .client import ReviewClient, ReviewClientConfig
from .collector import build_market_review_payload, redact_payload
from .models import ReviewJobRequest
from .parser import parse_review_output
from .prompt import build_prompts, prompt_hash
from .repository import ReviewRepository
from .repository import row_to_detail, row_to_summary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewServiceConfig:
    enabled: bool
    provider: str
    model: str
    timeout_seconds: int
    max_retries: int
    review_version: str
    min_abs_score: float
    require_trade: bool
    save_input_payload: bool
    payload_retention_days: int
    advisory_only: bool = True


class ReviewService:
    def __init__(self, *, config: ReviewServiceConfig, repository: ReviewRepository, state: AgentState | None = None) -> None:
        self._config = config
        self._repository = repository
        self._state = state or agent_state
        self._queue: asyncio.Queue[ReviewJobRequest] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._client = ReviewClient(
            ReviewClientConfig(
                provider=config.provider,
                model=config.model,
                timeout_seconds=config.timeout_seconds,
                max_retries=config.max_retries,
            )
        )
        self._metrics = {
            "queued": 0,
            "started": 0,
            "succeeded": 0,
            "failed": 0,
            "total_latency_ms": 0,
        }

    def is_enabled(self) -> bool:
        return self._config.enabled

    def eligibility_reasons(self, *, latest_decision: dict | None, paper_trades: list[dict], events: list[dict]) -> list[str]:
        reasons: list[str] = []
        score = latest_decision.get("score") if isinstance(latest_decision, dict) else None
        if isinstance(score, (int, float)) and abs(float(score)) >= self._config.min_abs_score:
            reasons.append("high_abs_score")

        if paper_trades:
            reasons.append("trade_present")

        risky_events = {"risk_blocked", "odds_filter_blocked", "kill_switch"}
        if any(str(event.get("message")) in risky_events for event in events):
            reasons.append("risk_signal")

        return sorted(set(reasons))

    def should_generate_review(self, *, reasons: list[str], paper_trades: list[dict]) -> bool:
        if not reasons:
            return False
        if self._config.require_trade and not paper_trades:
            return False
        if not paper_trades and not any(reason in {"high_abs_score", "risk_signal"} for reason in reasons):
            return False
        return True

    async def start(self) -> None:
        if not self._config.enabled:
            logger.info("LLM review service disabled")
            return
        if self._worker_task is None or self._worker_task.done():
            self._stop_event.clear()
            self._worker_task = asyncio.create_task(self._worker(), name="llm-review-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def enqueue(self, request: ReviewJobRequest) -> None:
        if not self._config.enabled:
            return
        await self._queue.put(request)
        self._metrics["queued"] += 1
        self._state.add_event("info", "market_review_queued", request.model_dump(mode="json"))

    async def enqueue_from_snapshot(
        self,
        *,
        market_id: str,
        market_slug: str,
        round_id: int | None,
        round_open_ts: datetime,
        round_close_ts: datetime,
    ) -> bool:
        snapshot = self._state.snapshot()
        reasons = self.eligibility_reasons(
            latest_decision=snapshot.get("last_decision"),
            paper_trades=snapshot.get("paper_trades", []),
            events=snapshot.get("events", []),
        )
        if not self.should_generate_review(reasons=reasons, paper_trades=snapshot.get("paper_trades", [])):
            return False

        await self.enqueue(
            ReviewJobRequest(
                market_id=market_id,
                market_slug=market_slug,
                round_id=round_id,
                round_open_ts=round_open_ts.astimezone(timezone.utc),
                round_close_ts=round_close_ts.astimezone(timezone.utc),
                review_version=self._config.review_version,
                trigger_reasons=reasons,
                requested_at=datetime.now(timezone.utc),
            )
        )
        return True

    def _apply_advisory_guard(self, analysis_json: dict[str, Any]) -> dict[str, Any]:
        if not self._config.advisory_only:
            return analysis_json
        guarded = dict(analysis_json)
        guarded["auto_apply_blocked"] = True
        return guarded

    async def replay(self, *, market_id: str, round_close_ts: datetime, review_version: str | None = None) -> None:
        snapshot = self._state.snapshot()
        await self.enqueue(
            ReviewJobRequest(
                market_id=market_id,
                market_slug=str(snapshot.get("polymarket_slug") or market_id),
                round_id=snapshot.get("active_round_id"),
                round_open_ts=datetime.now(timezone.utc),
                round_close_ts=round_close_ts.astimezone(timezone.utc),
                review_version=review_version or self._config.review_version,
                trigger_reasons=["manual_replay"],
                requested_at=datetime.now(timezone.utc),
            )
        )

    def _log_lifecycle(self, event_name: str, payload: dict[str, Any]) -> None:
        self._state.add_event("info", event_name, payload)

    async def _worker(self) -> None:
        while not self._stop_event.is_set():
            request = await self._queue.get()
            try:
                await self._process(request)
            except Exception as exc:  # noqa: BLE001
                logger.exception("review worker failed: %s", exc)
            finally:
                self._queue.task_done()

    async def _process(self, request: ReviewJobRequest) -> None:
        started_at = time.perf_counter()
        self._metrics["started"] += 1

        payload = build_market_review_payload(
            state=self._state,
            market_id=request.market_id,
            market_slug=request.market_slug,
            round_id=request.round_id,
            round_open_ts=request.round_open_ts,
            round_close_ts=request.round_close_ts,
            strategy_mode="review",
        )
        payload = redact_payload(payload)

        system_prompt, user_prompt = build_prompts(
            review_version=request.review_version,
            market_id=request.market_id,
            market_slug=request.market_slug,
            round_close_ts=request.round_close_ts.isoformat(),
            payload=payload,
        )
        hashed_prompt = prompt_hash(system_prompt, user_prompt)

        base_kwargs = {
            "market_id": request.market_id,
            "market_slug": request.market_slug,
            "round_id": request.round_id,
            "round_open_ts": request.round_open_ts,
            "round_close_ts": request.round_close_ts,
            "strategy_mode": "review",
            "review_version": request.review_version,
            "provider": self._config.provider,
            "model": self._config.model,
            "prompt_hash": hashed_prompt,
            "input_payload_json": payload if self._config.save_input_payload else None,
        }

        queued_row = self._repository.upsert_review(**base_kwargs, status="queued")
        self._log_lifecycle("market_review_queued", {"review_id": queued_row.id, "market_id": request.market_id})

        running_row = self._repository.upsert_review(**base_kwargs, status="running")
        self._log_lifecycle("market_review_started", {"review_id": running_row.id, "market_id": request.market_id})

        try:
            provider_result = await self._client.run(system_prompt=system_prompt, user_prompt=user_prompt)
            parsed = parse_review_output(provider_result.raw_text)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            self._metrics["succeeded"] += 1
            self._metrics["total_latency_ms"] += latency_ms

            guarded = self._apply_advisory_guard(parsed.analysis_json.model_dump())
            success_row = self._repository.upsert_review(
                **base_kwargs,
                status="succeeded",
                analysis_json=guarded,
                analysis_markdown=parsed.analysis_markdown,
                latency_ms=latency_ms,
                token_in=provider_result.token_in,
                token_out=provider_result.token_out,
                cost_usd_estimate=provider_result.cost_usd_estimate,
            )
            self._log_lifecycle(
                "market_review_succeeded",
                {
                    "review_id": success_row.id,
                    "market_id": request.market_id,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            self._metrics["failed"] += 1
            error_message = str(exc)
            failed_row = self._repository.upsert_review(
                **base_kwargs,
                status="failed",
                error_message=error_message,
                latency_ms=latency_ms,
            )
            self._log_lifecycle(
                "market_review_failed",
                {
                    "review_id": failed_row.id,
                    "market_id": request.market_id,
                    "reason": error_message,
                },
            )

        self._repository.prune_payloads(retention_days=self._config.payload_retention_days)

    def get_metrics(self) -> dict[str, int]:
        avg_latency = 0
        if self._metrics["succeeded"] > 0:
            avg_latency = int(self._metrics["total_latency_ms"] / self._metrics["succeeded"])
        return {
            "queued": int(self._metrics["queued"]),
            "started": int(self._metrics["started"]),
            "succeeded": int(self._metrics["succeeded"]),
            "failed": int(self._metrics["failed"]),
            "avg_latency_ms": avg_latency,
        }

    def latest_review(self):
        row = self._repository.latest_review()
        if row is None:
            return None
        return row_to_summary(row)

    def list_reviews(self, *, limit: int, status: str | None):
        rows = self._repository.list_reviews(limit=limit, status=status)
        return [row_to_summary(row) for row in rows]

    def get_review(self, review_id: str):
        row = self._repository.get_review(review_id)
        if row is None:
            return None
        return row_to_detail(row)
