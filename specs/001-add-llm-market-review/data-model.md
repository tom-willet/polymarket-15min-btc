# Data Model: End-of-Market LLM Review

## Entity: MarketLLMReview

- Purpose: Durable record for one logical review outcome for a market close window and review version.
- Primary Key: `id` (UUID string)
- Natural Uniqueness: `(market_id, round_close_ts, review_version)`

### Fields

- `id`: UUID, required
- `market_id`: string, required, indexed
- `market_slug`: string, required, indexed
- `round_id`: integer, nullable
- `round_open_ts`: timestamp, required
- `round_close_ts`: timestamp, required, indexed
- `strategy_mode`: string, required
- `review_version`: string, required
- `provider`: string, required
- `model`: string, required
- `prompt_hash`: string, required
- `input_payload_json`: JSON/text, required for retention window
- `analysis_json`: JSON/text, nullable until success
- `analysis_markdown`: text, nullable until success
- `status`: enum(`queued`,`running`,`succeeded`,`failed`), required
- `error_message`: text, nullable
- `latency_ms`: integer, nullable
- `token_in`: integer, nullable
- `token_out`: integer, nullable
- `cost_usd_estimate`: decimal, nullable
- `created_at`: timestamp, required
- `updated_at`: timestamp, required

### Validation Rules

- `status` must be one of the enum values.
- `analysis_json` and `analysis_markdown` must be present when `status = succeeded`.
- `error_message` must be present when `status = failed`.
- Upsert behavior must preserve uniqueness on natural key.

### State Transitions

- `queued -> running`
- `running -> succeeded`
- `running -> failed`
- Replay path: existing record re-enters `running` and terminates at `succeeded` or `failed`.

## Entity: ReviewJobRequest

- Purpose: Internal work item for asynchronous review execution.
- Fields:
  - `market_id` (required)
  - `market_slug` (required)
  - `round_close_ts` (required)
  - `review_version` (required)
  - `trigger_reasons` (non-empty list)
  - `requested_at` (timestamp)

## Entity: MarketReviewPayload

- Purpose: Canonical LLM input context for one closed market.
- Fields:
  - `market`: metadata (slug/window/open-close/reference/settlement outcome)
  - `decisions`: list of decision timeline points
  - `trades`: lifecycle records (entry/exit/slippage/fees/pnl)
  - `risk_events`: risk blocks, filters, kill-switch interactions
  - `aggregates`: counts, win/loss, pnl summary, edge summary

### Validation Rules

- Must include `market`, `decisions`, `trades`, `risk_events`, and `aggregates` sections.
- Must be redacted before provider submission.

## Entity: ReviewAnalysisJson

- Purpose: Structured parsed result from the LLM.
- Fields:
  - `summary.market_outcome`: enum(`yes`,`no`,`unknown`)
  - `summary.pnl_usd`: number
  - `summary.overall_grade`: enum(`A`,`B`,`C`,`D`,`F`)
  - `decision_assessment[]`: objects with `decision_id`, `verdict`, `reason`, `counterfactual`
  - `risk_findings[]`: list of strings
  - `parameter_suggestions[]`: objects with `name`, `suggested_value`, `rationale`, `confidence`
  - `next_experiments[]`: list of strings

### Validation Rules

- Missing required sections fail parsing.
- `confidence` values are bounded to `[0.0, 1.0]`.

## Entity: ReviewEvent

- Purpose: Observable lifecycle emission for operations and monitoring.
- Fields:
  - `event_name`: enum(`market_review_queued`,`market_review_started`,`market_review_succeeded`,`market_review_failed`)
  - `review_id`: UUID
  - `market_id`: string
  - `round_close_ts`: timestamp
  - `reason`: nullable string for failures
  - `emitted_at`: timestamp

## Retention Behavior

- Full `input_payload_json` is retained for configured retention period (default 30 days).
- After expiry, sensitive payload fields are redacted/pruned; aggregate metadata and analysis outputs are retained.
