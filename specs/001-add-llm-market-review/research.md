# Research: End-of-Market LLM Review

## Decision 1: Use in-process asynchronous queue + worker for v1

- Decision: Use an in-process FIFO queue and background worker thread/task for review execution.
- Rationale: Satisfies non-blocking requirement with minimal operational overhead and no new infrastructure.
- Alternatives considered:
  - External broker (Redis/Celery): stronger durability/scale but unnecessary complexity for v1.
  - Synchronous call in settlement path: rejected because it can block trading loop.

## Decision 2: SQLite as the durable backend for review records

- Decision: Persist `market_llm_reviews` in SQLite with unique index `(market_id, round_close_ts, review_version)`.
- Rationale: Matches clarified v1 scope, simple deployment model, and repo preference for lightweight dependencies.
- Alternatives considered:
  - Postgres: robust for horizontal scale but higher deployment complexity for current scope.
  - JSONL-only persistence: rejected due to poor queryability and weak idempotent upsert semantics.

## Decision 3: Idempotent upsert using natural uniqueness key

- Decision: Implement repository `upsert_review()` keyed by `(market_id, round_close_ts, review_version)`.
- Rationale: Guarantees replay safety and exactly-one logical record per market/version.
- Alternatives considered:
  - Insert-only with duplicate detection in application logic: more error-prone.
  - UUID-only identity: insufficient for replay deduplication.

## Decision 4: Deterministic prompt templates with prompt hash

- Decision: Version system/user prompt templates and persist SHA-256 prompt hash with each review.
- Rationale: Enables reproducibility and drift tracking across model/prompt changes.
- Alternatives considered:
  - Unversioned prompt strings: weak comparability and auditability.
  - Store only model/version: misses prompt-level variation.

## Decision 5: Strict response schema parsing before success state

- Decision: Parse LLM output into strict `analysis_json` schema and markdown sections; set status `failed` on validation errors.
- Rationale: Prevents malformed analysis from surfacing as successful output and supports deterministic downstream UI rendering.
- Alternatives considered:
  - Best-effort parsing with partial success: ambiguous quality guarantees.
  - Markdown-only output: loses machine-readable findings.

## Decision 6: Timeout + bounded retry with jitter

- Decision: Apply hard timeout (default 20s) and up to 2 retries with jittered backoff for transient failures.
- Rationale: Meets reliability requirement while bounding latency and avoiding retry storms.
- Alternatives considered:
  - No retry: lower success rates for transient provider/network issues.
  - Unlimited retry: risks backlog growth and delayed terminal visibility.

## Decision 7: Payload retention and redaction policy

- Decision: Keep full input payload for a configurable retention window (default 30 days), then redact/prune sensitive fields while keeping summary metadata.
- Rationale: Balances troubleshooting value with privacy and storage control.
- Alternatives considered:
  - Permanent full retention: elevated risk and storage growth.
  - No payload storage: reduced forensic/debug utility.

## Decision 8: Trusted-network-only access control for v1 review endpoints

- Decision: Keep review endpoints unauthenticated at app layer and require network-layer restrictions.
- Rationale: Aligns with clarified scope and current deployment posture; avoids introducing a new auth subsystem in v1.
- Alternatives considered:
  - Add app-layer auth now: stronger security but broader scope increase.
  - Fully open access: unacceptable exposure risk.

## Decision 9: No-trade review policy

- Decision: Run no-trade reviews only when high-signal conditions are present (abs(score) threshold or risk/kill-switch event).
- Rationale: Preserves signal quality and controls token/cost noise.
- Alternatives considered:
  - Review all no-trade markets: high cost/noise.
  - Never review no-trade markets: may miss meaningful blocked/high-confidence opportunities.
