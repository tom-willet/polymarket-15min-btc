# Implementation Plan: End-of-Market LLM Review

**Branch**: `001-add-llm-market-review` | **Date**: 2026-02-18 | **Spec**: `/Users/tomwillet/Documents/New project/specs/001-add-llm-market-review/spec.md`
**Input**: Feature specification from `/specs/001-add-llm-market-review/spec.md`

## Summary

Build a non-blocking, advisory-only post-market LLM review pipeline that triggers after market settlement, collects canonical market/decision/trade/risk context, calls an LLM with deterministic versioned prompts, validates structured output, and persists both structured and markdown artifacts in SQLite with replay and read-only retrieval endpoints.

## Technical Context

**Language/Version**: Python 3.11 (agent service), TypeScript 5.x (Next.js dashboard proxy)  
**Primary Dependencies**: FastAPI, Pydantic, sqlite3, pytest, Next.js route handlers  
**Storage**: SQLite (`market_llm_reviews` durable table) plus existing JSONL logs for legacy telemetry  
**Testing**: pytest unit/integration tests for collector/parser/retry + API endpoint coverage  
**Target Platform**: Linux containers / systemd deployment (single-host Lightsail class)  
**Project Type**: web (Python backend service + Next.js frontend proxy)  
**Performance Goals**: enqueue path completes without blocking trade loop; review terminal state within 60s of settlement for eligible markets; p95 review list/detail API <300ms on local SQLite  
**Constraints**: hard LLM timeout 20s default, max 2 retries with jitter, feature flag default OFF, trusted-network-only access for review endpoints, no autonomous parameter mutation, redaction-first payload handling  
**Scale/Scope**: one review per `(market_id, round_close_ts, review_version)`; dozens to low-hundreds of markets/day; advisory analysis only in v1

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- Constitution file at `/Users/tomwillet/Documents/New project/.specify/memory/constitution.md` is instantiated and enforceable.
- Principles for runtime safety, deterministic behavior, testing, security containment, and minimal complexity are directly applicable.
- Gate Status (Pre-Phase-0): **PASS** — plan and design satisfy current constitution principles.

## Project Structure

### Documentation (this feature)

```text
specs/001-add-llm-market-review/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── reviews.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
src/
└── polymarket_agent/
    ├── api.py
    ├── config.py
    ├── main.py
    ├── state.py
    ├── service.py
    └── review/
        ├── models.py
        ├── collector.py
        ├── prompt.py
        ├── client.py
        ├── parser.py
        ├── repository.py
        └── service.py

tests/
├── unit/
│   ├── test_review_collector.py
│   ├── test_review_parser.py
│   └── test_review_repository.py
└── integration/
    └── test_market_close_review_trigger.py

web/
└── src/app/api/
    └── agent/reviews/
        ├── latest/route.ts
        ├── route.ts
        └── [id]/route.ts

deploy/
└── nginx/
    └── README.md
```

**Structure Decision**: Extend the existing Python agent service as the source of truth for review orchestration/storage and expose review read/replay endpoints there; keep Next.js as a proxy/UI consumer with minimal additional business logic.

## Phase 0: Research & Decisions

- Resolved unknowns and selected concrete approaches in `/Users/tomwillet/Documents/New project/specs/001-add-llm-market-review/research.md`.
- No unresolved `NEEDS CLARIFICATION` items remain.

## Phase 1: Design & Contracts

- Data model specified in `/Users/tomwillet/Documents/New project/specs/001-add-llm-market-review/data-model.md`.
- API contracts specified in `/Users/tomwillet/Documents/New project/specs/001-add-llm-market-review/contracts/reviews.openapi.yaml`.
- Operator quickstart and validation flow documented in `/Users/tomwillet/Documents/New project/specs/001-add-llm-market-review/quickstart.md`.

## Constitution Check (Post-Design)

- Re-evaluated after Phase 1 artifact generation.
- Design remains advisory-only, non-blocking, reproducible, and testable.
- Post-design gate remains **PASS**; no constitution violations identified.

## Complexity Tracking

| Violation                                       | Why Needed                                                         | Simpler Alternative Rejected Because                                                 |
| ----------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| Dual-surface API exposure (backend + web proxy) | Existing architecture already proxies backend APIs through Next.js | Direct web-to-backend bypass would break current deployment and UI integration model |
