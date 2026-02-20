---
description: "Task list for end-of-market LLM review implementation"
---

# Tasks: End-of-Market LLM Review

**Input**: Design documents from `/specs/001-add-llm-market-review/`  
**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/reviews.openapi.yaml`, `quickstart.md`

**Tests**: Included because the specification and plan require unit, integration, and API coverage for review collection, parsing, trigger behavior, failure handling, and read endpoints.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story?] Description`

- `[P]` = parallelizable task (different files, no dependency on incomplete tasks)
- `[US1]`, `[US2]`, `[US3]` labels are used only in user-story phases
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize review feature scaffolding and configuration surface.

- [X] T001 Create review package scaffold in src/polymarket_agent/review/**init**.py
- [X] T002 Add LLM review configuration fields and defaults in src/polymarket_agent/config.py
- [X] T003 [P] Add provider key and review env examples in .env.example
- [X] T004 [P] Add baseline review type aliases/util helpers in src/polymarket_agent/review/models.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required before any user story implementation.

**⚠️ CRITICAL**: No user story work starts until this phase is complete.

- [X] T005 Implement SQLite table creation and unique index bootstrap in src/polymarket_agent/review/repository.py
- [X] T006 [P] Implement deterministic prompt templates and prompt hash utility in src/polymarket_agent/review/prompt.py
- [X] T007 [P] Implement strict analysis schema models in src/polymarket_agent/review/models.py
- [X] T008 Implement base queue/worker orchestration skeleton in src/polymarket_agent/review/service.py
- [X] T009 Wire review service lifecycle initialization into application startup in src/polymarket_agent/service.py
- [X] T010 Implement review lifecycle event logger helpers in src/polymarket_agent/review/service.py
- [X] T011 Add shared review test fixtures for closed-market payloads in tests/unit/test_review_fixtures.py

**Checkpoint**: Foundation complete; user stories can proceed.

---

## Phase 3: User Story 1 - Generate one review per closed market (Priority: P1) 🎯 MVP

**Goal**: Produce exactly one durable review artifact per eligible closed market with idempotent replay behavior.

**Independent Test**: Simulate eligible market close and verify one persisted review record for `(market_id, round_close_ts, review_version)` with successful upsert on replay.

### Tests for User Story 1

- [X] T012 [P] [US1] Add collector payload assembly unit tests in tests/unit/test_review_collector.py
- [X] T013 [P] [US1] Add repository idempotent upsert unit tests in tests/unit/test_review_repository.py
- [X] T014 [US1] Add integration test for market-close trigger creating one review in tests/integration/test_market_close_review_trigger.py

### Implementation for User Story 1

- [X] T015 [US1] Implement canonical payload collector from state/events/trades in src/polymarket_agent/review/collector.py
- [X] T016 [US1] Implement review repository create/get/upsert methods in src/polymarket_agent/review/repository.py
- [X] T017 [US1] Implement eligibility trigger evaluation for trade/score/risk events in src/polymarket_agent/review/service.py
- [X] T018 [US1] Enqueue review job at settlement completion path in src/polymarket_agent/main.py
- [X] T019 [US1] Persist queued/running/succeeded transitions with timestamps in src/polymarket_agent/review/service.py
- [X] T020 [US1] Add admin replay request model and dispatch hook in src/polymarket_agent/api.py

**Checkpoint**: US1 produces one durable review per eligible market and replay updates existing logical record.

---

## Phase 4: User Story 2 - Preserve trading loop safety under LLM outages (Priority: P2)

**Goal**: Ensure review execution is non-blocking with deterministic timeout/retry/failure behavior and visible terminal failure state.

**Independent Test**: Force provider timeout and parser failure; confirm retries occur, trading loop remains unblocked, and final failure status is persisted with reason.

### Tests for User Story 2

- [X] T021 [P] [US2] Add client timeout and retry unit tests in tests/unit/test_review_client.py
- [X] T022 [P] [US2] Add parser schema validation failure tests in tests/unit/test_review_parser.py
- [X] T023 [US2] Add integration test for timeout->retry->failed persistence in tests/integration/test_review_failure_retry.py

### Implementation for User Story 2

- [X] T024 [US2] Implement provider client with timeout and jittered retry policy in src/polymarket_agent/review/client.py
- [X] T025 [US2] Implement strict parse/validation pipeline for analysis JSON+markdown in src/polymarket_agent/review/parser.py
- [X] T026 [US2] Implement failure-state persistence and error reasons in src/polymarket_agent/review/service.py
- [X] T027 [US2] Implement payload redaction guard before provider submission in src/polymarket_agent/review/collector.py
- [X] T028 [US2] Implement payload retention pruning/redaction job helper in src/polymarket_agent/review/repository.py
- [X] T029 [US2] Implement no-trade high-signal gating logic in src/polymarket_agent/review/service.py

**Checkpoint**: US2 guarantees bounded failure handling and non-blocking runtime behavior.

---

## Phase 5: User Story 3 - Access review outputs for dashboard and tuning (Priority: P3)

**Goal**: Expose latest/list/detail review APIs and dashboard consumption path for structured + markdown artifacts.

**Independent Test**: Query latest/list/detail endpoints against seeded review records and verify dashboard routes return expected payloads.

### Tests for User Story 3

- [X] T030 [P] [US3] Add API tests for latest/list/detail review endpoints in tests/unit/test_api_reviews.py
- [X] T031 [US3] Add replay endpoint API tests in tests/unit/test_api_review_replay.py

### Implementation for User Story 3

- [X] T032 [US3] Implement GET /reviews/latest, GET /reviews, GET /reviews/{id} handlers in src/polymarket_agent/api.py
- [X] T033 [US3] Implement POST /admin/reviews/replay handler in src/polymarket_agent/api.py
- [X] T034 [P] [US3] Implement web proxy route for latest review in web/src/app/api/agent/reviews/latest/route.ts
- [X] T035 [P] [US3] Implement web proxy route for review list in web/src/app/api/agent/reviews/route.ts
- [X] T036 [P] [US3] Implement web proxy route for review detail in web/src/app/api/agent/reviews/[id]/route.ts
- [X] T037 [US3] Add review response adapters and schema guards in web/src/lib/reviewAdapters.ts
- [X] T038 [US3] Add dashboard review page rendering latest markdown and structured summary in web/src/app/reviews/page.tsx

**Checkpoint**: US3 enables operator retrieval and dashboard visibility for review artifacts.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cross-story hardening, docs, and validation.

- [X] T039 [P] Update review API and env var documentation in README.md
- [X] T040 [P] Document trusted-network deployment guidance for review endpoints in deploy/nginx/README.md
- [X] T041 Add observability counters/log summaries for review success/failure/latency in src/polymarket_agent/review/service.py
- [X] T042 Run quickstart validation steps and record expected outputs in specs/001-add-llm-market-review/quickstart.md
- [X] T043 Validate contract/spec alignment and finalize task references in specs/001-add-llm-market-review/tasks.md
- [X] T044 Add explicit advisory-only guard that blocks parameter auto-apply paths in src/polymarket_agent/review/service.py
- [X] T045 Add tests asserting no automatic parameter mutation from review outputs in tests/unit/test_review_advisory_guard.py
- [X] T046 Add API and enqueue-path performance checks for SC-002/SC-005 thresholds in tests/integration/test_review_performance_baseline.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: starts immediately.
- **Phase 2 (Foundational)**: depends on Phase 1 and blocks all stories.
- **Phase 3 (US1)**: starts after Phase 2.
- **Phase 4 (US2)**: starts after Phase 2; may run in parallel with late US1 tasks if file ownership does not conflict.
- **Phase 5 (US3)**: starts after Phase 2 and after backend read/replay primitives from US1/US2 exist.
- **Phase 6 (Polish)**: starts after all target stories complete.

### User Story Dependency Graph

- **US1 (P1)** → foundational for persistence and trigger pipeline.
- **US2 (P2)** depends on US1 service/repository baseline.
- **US3 (P3)** depends on US1 repository and US2 terminal status behavior for complete API semantics.

Graph: `US1 -> US2 -> US3`

### Within Each Story

- Test tasks run before implementation tasks in that story.
- Data/repository work precedes service orchestration.
- Backend API handlers precede web proxy/dashboard tasks.

---

## Parallel Execution Examples

### User Story 1

- Run T012 and T013 in parallel (different test files).
- Run T015 and T016 sequentially before T017/T019.

### User Story 2

- Run T021 and T022 in parallel.
- Run T027 and T029 in parallel after T024/T025 baseline is in place.

### User Story 3

- Run T034, T035, and T036 in parallel (independent route files).
- Run T030 and T031 in parallel before API implementation checks.

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 and Phase 2.
2. Complete all US1 tasks (T012–T020).
3. Validate independent test criteria for US1 before proceeding.

### Incremental Delivery

1. Deliver US1 for deterministic, durable review generation.
2. Deliver US2 for reliability and non-blocking guarantees.
3. Deliver US3 for operator/dashboard retrieval and replay operations.
4. Finish with Phase 6 cross-cutting polish.
