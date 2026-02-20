# Polymarket BTC 15m Agent Constitution

## Core Principles

### I. Runtime Safety First

All new features MUST preserve live-loop safety. Advisory and analytics features MUST execute asynchronously and MUST NOT block trade decision or execution paths. Any failure mode MUST degrade safely and visibly.

### II. Deterministic, Versioned Behavior

Model-facing prompts, schemas, and review versions MUST be explicitly versioned. Any persisted analytical artifact MUST be reproducible through stored version metadata and deterministic parsing rules.

### III. Testable Acceptance Before Merge

Functional behavior, failure paths, and contract surfaces MUST be covered by automated tests at the appropriate layer (unit, integration, API). Changes that alter required acceptance behavior MUST include updated tests.

### IV. Security by Containment and Redaction

Secrets and credentials MUST never be logged or persisted in clear form. Network-access assumptions MUST be documented for exposed endpoints, and sensitive payloads MUST be redacted according to retention policy.

### V. Minimal Complexity for Current Scope

Implementation choices MUST prefer the smallest operational footprint that satisfies current requirements. Introduce additional infrastructure only when justified by explicit scale/reliability needs.

## Additional Constraints

- The production runtime remains Python agent service plus Next.js dashboard proxy.
- SQLite is an approved durable backend for v1 analytics/review storage.
- New functionality must remain advisory-only unless explicitly approved by a later specification.
- Feature flags MUST default to safe/off for newly introduced risky external integrations.

## Development Workflow

- Use Speckit flow in order: specify → clarify (if needed) → plan → tasks → analyze → implement.
- Every feature plan MUST include measurable success criteria and explicit failure-path behavior.
- Tasks MUST map to requirements with story-level traceability.
- Cross-artifact consistency checks SHOULD pass before implementation begins.

## Governance

This constitution supersedes ad-hoc development preferences for this repository. Any exception requires explicit rationale in the feature plan under complexity tracking. Amendments MUST include:

1. Version bump rationale (major/minor/patch).
2. Updated principle or section text.
3. Consistency updates to impacted Speckit artifacts.

Compliance checks occur during `/speckit.analyze` and before `/speckit.implement`.

**Version**: 1.0.0 | **Ratified**: 2026-02-18 | **Last Amended**: 2026-02-18
