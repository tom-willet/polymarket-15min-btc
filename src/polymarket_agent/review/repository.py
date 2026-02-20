from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .models import ReviewDetail, ReviewStatus, ReviewSummary, ensure_utc, utc_now


@dataclass(frozen=True)
class ReviewRow:
    id: str
    market_id: str
    market_slug: str
    round_id: int | None
    round_open_ts: datetime
    round_close_ts: datetime
    strategy_mode: str
    review_version: str
    provider: str
    model: str
    prompt_hash: str
    input_payload_json: dict[str, Any] | None
    analysis_json: dict[str, Any] | None
    analysis_markdown: str | None
    status: ReviewStatus
    error_message: str | None
    latency_ms: int | None
    token_in: int | None
    token_out: int | None
    cost_usd_estimate: float | None
    created_at: datetime
    updated_at: datetime


class ReviewRepository:
    def __init__(self, db_path: str = "logs/reviews.sqlite3") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn

    def _bootstrap(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_llm_reviews (
                    id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    market_slug TEXT NOT NULL,
                    round_id INTEGER,
                    round_open_ts TEXT NOT NULL,
                    round_close_ts TEXT NOT NULL,
                    strategy_mode TEXT NOT NULL,
                    review_version TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    input_payload_json TEXT,
                    analysis_json TEXT,
                    analysis_markdown TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    latency_ms INTEGER,
                    token_in INTEGER,
                    token_out INTEGER,
                    cost_usd_estimate REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_market_llm_reviews_natural
                ON market_llm_reviews (market_id, round_close_ts, review_version)
                """
            )

    def _row_to_review_row(self, row: sqlite3.Row) -> ReviewRow:
        def _parse_json(raw: str | None) -> dict[str, Any] | None:
            if raw is None:
                return None
            return json.loads(raw)

        return ReviewRow(
            id=row["id"],
            market_id=row["market_id"],
            market_slug=row["market_slug"],
            round_id=row["round_id"],
            round_open_ts=datetime.fromisoformat(row["round_open_ts"]),
            round_close_ts=datetime.fromisoformat(row["round_close_ts"]),
            strategy_mode=row["strategy_mode"],
            review_version=row["review_version"],
            provider=row["provider"],
            model=row["model"],
            prompt_hash=row["prompt_hash"],
            input_payload_json=_parse_json(row["input_payload_json"]),
            analysis_json=_parse_json(row["analysis_json"]),
            analysis_markdown=row["analysis_markdown"],
            status=row["status"],
            error_message=row["error_message"],
            latency_ms=row["latency_ms"],
            token_in=row["token_in"],
            token_out=row["token_out"],
            cost_usd_estimate=row["cost_usd_estimate"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def upsert_review(
        self,
        *,
        market_id: str,
        market_slug: str,
        round_id: int | None,
        round_open_ts: datetime,
        round_close_ts: datetime,
        strategy_mode: str,
        review_version: str,
        provider: str,
        model: str,
        prompt_hash: str,
        input_payload_json: dict[str, Any] | None,
        status: ReviewStatus,
        analysis_json: dict[str, Any] | None = None,
        analysis_markdown: str | None = None,
        error_message: str | None = None,
        latency_ms: int | None = None,
        token_in: int | None = None,
        token_out: int | None = None,
        cost_usd_estimate: float | None = None,
    ) -> ReviewRow:
        now = utc_now().isoformat()
        round_open_iso = ensure_utc(round_open_ts).isoformat()
        round_close_iso = ensure_utc(round_close_ts).isoformat()
        payload_raw = json.dumps(input_payload_json) if input_payload_json is not None else None
        analysis_raw = json.dumps(analysis_json) if analysis_json is not None else None

        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT id, created_at
                FROM market_llm_reviews
                WHERE market_id = ? AND round_close_ts = ? AND review_version = ?
                """,
                (market_id, round_close_iso, review_version),
            ).fetchone()

            review_id = existing["id"] if existing else str(uuid4())
            created_at = existing["created_at"] if existing else now

            conn.execute(
                """
                INSERT INTO market_llm_reviews (
                    id, market_id, market_slug, round_id, round_open_ts, round_close_ts,
                    strategy_mode, review_version, provider, model, prompt_hash,
                    input_payload_json, analysis_json, analysis_markdown,
                    status, error_message, latency_ms, token_in, token_out, cost_usd_estimate,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id, round_close_ts, review_version) DO UPDATE SET
                    market_slug=excluded.market_slug,
                    round_id=excluded.round_id,
                    round_open_ts=excluded.round_open_ts,
                    strategy_mode=excluded.strategy_mode,
                    provider=excluded.provider,
                    model=excluded.model,
                    prompt_hash=excluded.prompt_hash,
                    input_payload_json=excluded.input_payload_json,
                    analysis_json=excluded.analysis_json,
                    analysis_markdown=excluded.analysis_markdown,
                    status=excluded.status,
                    error_message=excluded.error_message,
                    latency_ms=excluded.latency_ms,
                    token_in=excluded.token_in,
                    token_out=excluded.token_out,
                    cost_usd_estimate=excluded.cost_usd_estimate,
                    updated_at=excluded.updated_at
                """,
                (
                    review_id,
                    market_id,
                    market_slug,
                    round_id,
                    round_open_iso,
                    round_close_iso,
                    strategy_mode,
                    review_version,
                    provider,
                    model,
                    prompt_hash,
                    payload_raw,
                    analysis_raw,
                    analysis_markdown,
                    status,
                    error_message,
                    latency_ms,
                    token_in,
                    token_out,
                    cost_usd_estimate,
                    created_at,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM market_llm_reviews WHERE id = ?", (review_id,)).fetchone()
            if row is None:
                raise RuntimeError("failed to fetch upserted review")
            return self._row_to_review_row(row)

    def get_review(self, review_id: str) -> ReviewRow | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM market_llm_reviews WHERE id = ?", (review_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_review_row(row)

    def get_review_by_key(self, *, market_id: str, round_close_ts: datetime, review_version: str) -> ReviewRow | None:
        round_close_iso = ensure_utc(round_close_ts).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM market_llm_reviews
                WHERE market_id = ? AND round_close_ts = ? AND review_version = ?
                """,
                (market_id, round_close_iso, review_version),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_review_row(row)

    def latest_review(self) -> ReviewRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM market_llm_reviews ORDER BY round_close_ts DESC, updated_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return self._row_to_review_row(row)

    def list_reviews(self, *, limit: int = 50, status: ReviewStatus | None = None) -> list[ReviewRow]:
        limit = max(1, min(limit, 200))
        sql = "SELECT * FROM market_llm_reviews"
        params: list[Any] = []
        if status is not None:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY round_close_ts DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_review_row(row) for row in rows]

    def prune_payloads(self, *, retention_days: int) -> int:
        retention_days = max(1, retention_days)
        threshold = (utc_now() - timedelta(days=retention_days)).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE market_llm_reviews
                SET input_payload_json = NULL, updated_at = ?
                WHERE created_at < ? AND input_payload_json IS NOT NULL
                """,
                (utc_now().isoformat(), threshold),
            )
            return int(cursor.rowcount)


def row_to_summary(row: ReviewRow) -> ReviewSummary:
    return ReviewSummary(
        id=UUID(row.id),
        market_id=row.market_id,
        market_slug=row.market_slug,
        round_close_ts=ensure_utc(row.round_close_ts),
        review_version=row.review_version,
        status=row.status,
        provider=row.provider,
        model=row.model,
        created_at=ensure_utc(row.created_at),
        updated_at=ensure_utc(row.updated_at),
    )


def row_to_detail(row: ReviewRow) -> ReviewDetail:
    summary = row_to_summary(row)
    return ReviewDetail(
        **summary.model_dump(),
        analysis_json=row.analysis_json,
        analysis_markdown=row.analysis_markdown,
        error_message=row.error_message,
        latency_ms=row.latency_ms,
        token_in=row.token_in,
        token_out=row.token_out,
        cost_usd_estimate=row.cost_usd_estimate,
    )
