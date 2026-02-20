from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


ReviewStatus = Literal["queued", "running", "succeeded", "failed"]


class DecisionAssessment(BaseModel):
    decision_id: str
    verdict: str
    reason: str
    counterfactual: str


class ParameterSuggestion(BaseModel):
    name: str
    suggested_value: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReviewSummarySection(BaseModel):
    market_outcome: Literal["yes", "no", "unknown"]
    pnl_usd: float
    overall_grade: Literal["A", "B", "C", "D", "F"]


class ReviewAnalysisJson(BaseModel):
    summary: ReviewSummarySection
    decision_assessment: list[DecisionAssessment]
    risk_findings: list[str]
    parameter_suggestions: list[ParameterSuggestion]
    next_experiments: list[str]


class ReplayRequest(BaseModel):
    market_id: str
    round_close_ts: datetime
    review_version: str = "v1.0"

    @field_validator("round_close_ts")
    @classmethod
    def _validate_ts(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ReviewKey(BaseModel):
    market_id: str
    round_close_ts: datetime
    review_version: str


class ReviewSummary(BaseModel):
    id: UUID
    market_id: str
    market_slug: str
    round_close_ts: datetime
    review_version: str
    status: ReviewStatus
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime


class ReviewDetail(ReviewSummary):
    analysis_json: dict[str, Any] | None = None
    analysis_markdown: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    token_in: int | None = None
    token_out: int | None = None
    cost_usd_estimate: float | None = None


class ReviewListResponse(BaseModel):
    items: list[ReviewSummary]
    next_cursor: str | None = None


class ReviewJobRequest(BaseModel):
    market_id: str
    market_slug: str
    round_id: int | None = None
    round_open_ts: datetime
    round_close_ts: datetime
    review_version: str
    trigger_reasons: list[str]
    requested_at: datetime


class ProviderResult(BaseModel):
    raw_text: str
    token_in: int | None = None
    token_out: int | None = None
    cost_usd_estimate: float | None = None


class ParsedReviewOutput(BaseModel):
    analysis_json: ReviewAnalysisJson
    analysis_markdown: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
