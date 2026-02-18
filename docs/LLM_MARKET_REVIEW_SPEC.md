# End-of-Market LLM Review Spec

## 1) Purpose

Add an asynchronous post-market review pipeline that submits complete market/trade/decision context to an LLM (example target: GPT-5.2) and stores a structured + markdown review artifact in durable storage.

The review is for analysis only in v1. It must not affect live trading decisions or execution.

## 2) Goals

1. Produce one high-quality review per completed market window.
2. Capture why actions were taken, what went well/poorly, and what to change.
3. Persist review outputs for operator visibility and later tuning analysis.
4. Keep runtime-safe behavior: no trade loop blocking and no hard dependency on LLM availability.

## 3) Non-Goals (v1)

1. No autonomous parameter updates.
2. No automatic strategy retraining.
3. No in-loop decision augmentation.
4. No hard requirement for vector search/RAG.

## 4) Scope and Trigger

### Trigger Event

`market_review_requested` is raised once at market close after settlement/logging is complete.

### Trigger Conditions

A review job is created when at least one is true:

1. One or more `paper_trade_opened` or `paper_trade_closed` events exist for the market.
2. A decision score with absolute value >= configured threshold was observed.
3. A risk block or kill-switch event occurred.

### Idempotency Rule

Uniqueness key: `(market_id, round_close_ts, review_version)`.

Re-running the same market with same `review_version` upserts the same record rather than duplicating.

## 5) Functional Requirements

1. Build a canonical review payload for a closed market containing:
   - market metadata (slug, round id/window, open/close timestamps, reference price, close result)
   - decision timeline (action, score, confidence, odds alignment, key signals)
   - trade lifecycle (entry/exit, slippage, fees, pnl, outcome)
   - risk events (filters, blocks, kill-switch interactions)
   - aggregate stats (count, win/loss, pnl summary, edge summary)
2. Submit payload to configured LLM provider with deterministic prompt template.
3. Parse model response into:
   - `analysis_json` (strict schema)
   - `analysis_markdown` (human-readable report)
4. Persist both artifacts in durable storage.
5. Expose review records to API for dashboard consumption.
6. Log review pipeline events and failures with clear status transitions.

## 6) Quality and Reliability Requirements

1. Non-blocking execution: review job must run off the main market loop.
2. Hard timeout per LLM request (default 20s; configurable).
3. Retry policy for transient failures (e.g., 2 retries with jittered backoff).
4. Final failure state is stored (with reason) instead of silent drop.
5. Redaction guard for secrets/credentials before payload submission.
6. Prompt + model version tracked for reproducibility.

## 7) Data Model (DB)

> Current repo primarily uses logs/in-memory state. This spec defines a durable review table; storage backend can be SQLite (local) or Postgres (prod).

### Table: `market_llm_reviews`

- `id` (uuid, pk)
- `market_id` (text, indexed)
- `market_slug` (text, indexed)
- `round_id` (bigint, nullable)
- `round_open_ts` (timestamptz)
- `round_close_ts` (timestamptz, indexed)
- `strategy_mode` (text)
- `review_version` (text)  
  Example: `v1.0`
- `provider` (text)  
  Example: `openai`
- `model` (text)  
  Example: `gpt-5.2`
- `prompt_hash` (text)
- `input_payload_json` (jsonb/text)
- `analysis_json` (jsonb/text)
- `analysis_markdown` (text)
- `status` (text)  
  Enum: `queued | running | succeeded | failed`
- `error_message` (text, nullable)
- `latency_ms` (int, nullable)
- `token_in` (int, nullable)
- `token_out` (int, nullable)
- `cost_usd_estimate` (numeric, nullable)
- `created_at` (timestamptz)
- `updated_at` (timestamptz)

Unique index: `(market_id, round_close_ts, review_version)`

## 8) LLM Prompt and Response Contract

### Prompting Principles

1. Use fixed, versioned system+user templates.
2. Require evidence-grounded analysis only from provided payload.
3. Require explicit uncertainty markers when data is missing.
4. Keep recommendation section separate from factual recap.

### Required `analysis_json` Shape

```json
{
  "summary": {
    "market_outcome": "yes|no|unknown",
    "pnl_usd": 0.0,
    "overall_grade": "A|B|C|D|F"
  },
  "decision_assessment": [
    {
      "decision_id": "string",
      "verdict": "good|neutral|bad",
      "reason": "string",
      "counterfactual": "string"
    }
  ],
  "risk_findings": ["string"],
  "parameter_suggestions": [
    {
      "name": "string",
      "suggested_value": "string|number|boolean",
      "rationale": "string",
      "confidence": 0.0
    }
  ],
  "next_experiments": ["string"]
}
```

### Required `analysis_markdown`

Markdown report with sections:

1. Market Summary
2. Decision Quality
3. Trade Outcome Analysis
4. Risk/Execution Notes
5. Suggested Parameter Experiments

## 9) Architecture / Component Plan

### New Module: `src/polymarket_agent/review/`

Suggested files:

1. `models.py`  
   Dataclasses / typed schemas for request/response payloads.
2. `collector.py`  
   Builds canonical market payload from state, events, trades.
3. `prompt.py`  
   Versioned prompt templates + hashing.
4. `client.py`  
   LLM provider adapter with timeout/retry.
5. `parser.py`  
   Validates/parses response into strict structure.
6. `repository.py`  
   DB writes/reads for review records.
7. `service.py`  
   Orchestration entrypoint: queue -> run -> persist.

### Integration Point

At end-of-market settlement path in `src/polymarket_agent/main.py`, enqueue review job with market key and close timestamp.

## 10) API Surface (v1)

Add read-only endpoints:

1. `GET /reviews/latest`  
   Returns most recent review summary.
2. `GET /reviews?limit=...&status=...`  
   Returns paginated review metadata.
3. `GET /reviews/{id}`  
   Returns full `analysis_json` + `analysis_markdown`.

Optional admin endpoint:

- `POST /admin/reviews/replay` to re-run review for a given market/round.

## 11) Configuration

New env vars (proposed):

- `LLM_REVIEW_ENABLED=true|false`
- `LLM_REVIEW_PROVIDER=openai`
- `LLM_REVIEW_MODEL=gpt-5.2`
- `LLM_REVIEW_TIMEOUT_SECONDS=20`
- `LLM_REVIEW_MAX_RETRIES=2`
- `LLM_REVIEW_VERSION=v1.0`
- `LLM_REVIEW_MIN_ABS_SCORE=0.25`
- `LLM_REVIEW_REQUIRE_TRADE=true`
- `LLM_REVIEW_SAVE_INPUT_PAYLOAD=true`

Secret handling (provider key) must use environment variable and never be logged.

## 12) Observability

Emit lifecycle events:

1. `market_review_queued`
2. `market_review_started`
3. `market_review_succeeded`
4. `market_review_failed`

Metrics:

- review success rate
- average latency
- failures by reason
- token/cost trends

## 13) Security and Compliance Notes

1. Payload must exclude secrets and account credentials.
2. Keep only operational trading metadata required for analysis.
3. Provide optional retention policy for review records.
4. Ensure markdown rendering in web UI is sanitized.

## 14) Rollout Plan

### Phase 0: Design + Contracts

- finalize payload schema
- finalize response schema
- select initial storage backend

### Phase 1: Local Async Pipeline

- queue + worker in-process
- mock LLM client for deterministic tests
- persist records locally

### Phase 2: Production Hardening

- provider integration + retries/timeouts
- metrics and dashboards
- replay endpoint

### Phase 3: Tuning Workflow

- compare review recommendations vs realized outcomes
- define manual acceptance workflow for parameter changes

## 15) Testing Requirements

1. Unit tests for payload collector with fixture markets.
2. Unit tests for parser validation and schema failures.
3. Integration test: simulated market close triggers exactly one review.
4. Failure-path test: LLM timeout -> retry -> failed status persisted.
5. API test coverage for list/detail endpoints.

## 16) Acceptance Criteria (Definition of Done for v1)

1. One closed market with trade activity produces one stored review record.
2. Record contains both `analysis_json` and `analysis_markdown`.
3. Review generation never blocks trading loop.
4. Failures are visible and queryable via API/logs.
5. Dashboard can view latest review markdown.

## 17) Open Decisions

1. Storage backend now: SQLite or Postgres?
2. Keep full input payload forever or prune/redact after N days?
3. Should `parameter_suggestions` be advisory only (default) or wired into a later approval workflow?
4. Should reviews run for no-trade markets by default?

## 18) Implementation Notes for This Repo

1. Current system uses in-memory status + jsonl logs; this feature introduces first-class durable review records.
2. Keep feature flag off by default until parser/tests are stable.
3. Start with advisory-only recommendations and no automatic config mutation.
4. Prefer minimal dependency footprint: existing FastAPI service + lightweight DB adapter.
5. Keep review versioned so future prompt/schema changes do not break historical comparability.
