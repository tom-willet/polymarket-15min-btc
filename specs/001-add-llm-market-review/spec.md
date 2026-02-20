# Feature Specification: End-of-Market LLM Review

**Feature Branch**: `001-add-llm-market-review`  
**Created**: 2026-02-18  
**Status**: Draft  
**Input**: User description: "Add an asynchronous post-market LLM review pipeline for closed markets with durable structured + markdown artifacts and read-only API access"

## Clarifications

### Session 2026-02-18

- Q: How long should full input payloads be retained? → A: Keep full payload for a fixed period, then redact/prune sensitive fields.
- Q: What access control should apply to review endpoints? → A: Keep review endpoints open on trusted network only (no app-level auth).
- Q: What should be the initial durable storage backend for v1? → A: SQLite as initial durable backend for v1.
- Q: Should reviews run for no-trade markets by default? → A: Run reviews for no-trade markets only when high-signal conditions are met.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Generate one review per closed market (Priority: P1)

As an operator, I want each eligible closed market window to produce exactly one structured review so I can evaluate decision quality and outcomes without manual reconstruction.

**Why this priority**: The feature’s primary value is dependable post-market analysis with no duplicate or missing records.

**Independent Test**: Can be fully tested by closing an eligible market window and verifying one persisted review record exists for that market close and review version.

**Acceptance Scenarios**:

1. **Given** a market window has closed and meets at least one review trigger condition, **When** post-settlement processing completes, **Then** a review job is queued and one review record is produced for that market close and review version.
2. **Given** a review for the same market close and review version already exists, **When** the review job is replayed, **Then** the existing record is updated rather than creating a duplicate.

---

### User Story 2 - Preserve trading loop safety under LLM outages (Priority: P2)

As an operator, I want review generation to run asynchronously and fail safely so analysis tooling never blocks or degrades live trading operations.

**Why this priority**: Runtime safety is critical; review generation is analysis-only and must not become an operational dependency.

**Independent Test**: Can be fully tested by forcing LLM timeouts/failures during market close and verifying trading flow completes while review status transitions to a visible failure.

**Acceptance Scenarios**:

1. **Given** a review job is started, **When** the LLM request exceeds the configured timeout, **Then** retry behavior is applied and the trading loop remains unblocked.
2. **Given** all retries are exhausted, **When** the review job terminates, **Then** the record is stored with a failed status and reason.

---

### User Story 3 - Access review outputs for dashboard and tuning (Priority: P3)

As an operator, I want to retrieve latest, list, and detailed review outputs so I can inspect structured findings and human-readable analysis in the dashboard.

**Why this priority**: Visibility and later tuning decisions require queryable review artifacts.

**Independent Test**: Can be fully tested by requesting latest/list/detail review endpoints and confirming structured metadata, JSON findings, and markdown analysis are returned.

**Acceptance Scenarios**:

1. **Given** one or more reviews exist, **When** the operator requests the latest review summary, **Then** the most recent persisted review is returned.
2. **Given** reviews exist in multiple states, **When** the operator queries reviews with filters and limits, **Then** matching paginated metadata is returned.
3. **Given** a valid review identifier, **When** the operator requests review detail, **Then** the full structured analysis and markdown report are returned.

### Edge Cases

- Market closes with no trades, no high-confidence decisions, and no risk events; no review is created.
- A market is replayed multiple times with the same review version; only one logical record remains.
- Review response is missing required structured sections; record is marked failed with parse/validation reason.
- Sensitive values are present in source context; outbound payload excludes redacted secrets.
- Storage is temporarily unavailable at completion time; failure state is still observable via logs and retry outcome.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST evaluate closed-market trigger conditions and create a review job only when at least one configured trigger condition is met.
- **FR-002**: System MUST build a canonical review input payload that includes market context, decision timeline, trade lifecycle, risk events, and aggregate performance statistics for the closed market window.
- **FR-003**: System MUST execute review generation asynchronously from the live trading loop.
- **FR-004**: System MUST apply request timeout and retry behavior for transient LLM failures using configurable limits.
- **FR-005**: System MUST persist review records in durable storage with lifecycle status (`queued`, `running`, `succeeded`, `failed`) and timestamps.
- **FR-006**: System MUST enforce idempotency for each `(market_id, round_close_ts, review_version)` so replay updates existing records instead of duplicating them.
- **FR-007**: System MUST store both structured analysis output and human-readable markdown output for successful reviews.
- **FR-008**: System MUST validate structured analysis output against the required schema and mark the review failed when schema validation does not pass.
- **FR-009**: System MUST expose read-only retrieval for latest review, paginated review listings, and full review detail.
- **FR-010**: System MUST emit observable lifecycle events for queue/start/success/failure and include failure reasons when applicable.
- **FR-011**: System MUST track review reproducibility metadata, including review version, model identity, and prompt version fingerprint.
- **FR-012**: System MUST redact secrets and credentials from outbound review payloads and MUST NOT log secret values.
- **FR-013**: System MUST keep review recommendations advisory-only in this version and MUST NOT apply automatic trading parameter changes.
- **FR-014**: System MUST allow operators to re-run a review for a specific market close while maintaining idempotency rules.
- **FR-015**: System MUST retain full `input_payload_json` for a configurable retention window and, after expiry, redact or prune sensitive fields while preserving non-sensitive summary metadata needed for auditability.
- **FR-016**: System MUST treat review endpoints as unauthenticated at the application layer in v1 and rely on trusted-network controls for access restriction.
- **FR-017**: System MUST use SQLite as the default and required durable backend for v1 review records.
- **FR-018**: System MUST run no-trade market reviews only when high-signal conditions are present (for v1: absolute decision score threshold met or risk/kill-switch event occurred).

### Key Entities _(include if feature involves data)_

- **Review Job**: Represents an asynchronous analysis request for a single closed market window; includes trigger evidence, lifecycle status, retries, and latency.
- **Review Record**: Durable artifact keyed by market and close time/version; includes canonical input snapshot, structured findings, markdown report, status, and error context.
- **Market Review Payload**: Canonical analysis context containing market metadata, decisions, trades, risk events, and aggregate metrics.
- **Structured Analysis**: Machine-validated result with summary, decision assessment, risk findings, parameter suggestions, and next experiments.
- **Review Event**: Observable lifecycle signal indicating queue/start/success/failure transitions and reason categories.

## Assumptions

- Reviews are generated after market settlement and logging complete for the market window.
- Feature is disabled by default until explicitly enabled by operators.
- Default timeout is 20 seconds per LLM request with up to 2 retries for transient failures.
- Reviews remain analysis-only and are not used to alter live execution behavior in this version.
- Read-only review access is intended for operators and dashboard consumption.
- Default payload retention window is 30 days unless operator-configured otherwise.
- Deployment environments enforce network-layer access controls (private subnet, reverse proxy allowlist, or equivalent) for review endpoints.
- Migration to Postgres is out of scope for v1 and may be introduced in a later version without changing v1 behavior.
- No-trade markets are excluded from review generation unless high-signal trigger conditions are met.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: For eligible closed markets, 100% produce exactly one persisted review record per `(market_id, round_close_ts, review_version)` within 60 seconds of settlement completion.
- **SC-002**: During review generation (including timeout and retry conditions), trading loop cycle completion time does not degrade by more than 2% relative to baseline.
- **SC-003**: 100% of successful review records contain both structured analysis and markdown report sections required by this specification.
- **SC-004**: 100% of terminal review failures are queryable with an explicit failure reason within 10 seconds of job termination.
- **SC-005**: Operators can retrieve latest/list/detail review views with a successful response for at least 99% of requests measured over a rolling 24-hour window under normal operating conditions defined as up to 5 requests/second and no active infrastructure outage.
