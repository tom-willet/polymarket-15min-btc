# Polymarket BTC Agent: Architecture and Project Structure Recommendation

## 1. Objectives

Primary goals:
- Run a continuously available decision agent for 15-minute BTC markets.
- Activate decisioning in the final 3 minutes of each round.
- Keep execution logic isolated and secure.
- Provide a clear operational dashboard with low coupling to trading core.
- Make deployment simple first (Lightsail), then evolvable.

Non-goals for phase 1:
- Multi-market portfolio optimization.
- Complex multi-region HA.
- Fully event-sourced architecture.

## 2. Recommended High-Level Architecture

Use a modular monorepo with two runtime services and one shared contract:

1. `agent` (Python)
- Round scheduling.
- Websocket market data intake.
- Strategy orchestration and risk checks.
- Execution adapter (exchange/order APIs).
- Internal read API for status and metrics.

2. `web` (Next.js)
- Authenticated operator console.
- Live operational status (health, round, ticks, decisions).
- Trade/audit views from backend API.

3. `shared contract` (schema docs + generated types optional)
- JSON response schemas for status, decision events, trade events.
- Keeps frontend/backend integration stable.

Why this split:
- Agent remains focused on low-latency deterministic decision flow.
- Web remains focused on operator UX.
- Independent deployment and restart behavior reduce operational risk.

## 3. Runtime/Data Flow

1. Scheduler computes current 15-minute window.
2. At T-180 seconds, agent enters active mode for that round.
3. Ticker client subscribes to websocket feed and normalizes ticks.
4. Decision router updates feature state and asks strategy modules in order.
5. Risk guard validates decision against limits.
6. Executor places order (or dry-run logs).
7. Agent records state + event for audit/monitoring.
8. Web polls backend status API (or later upgrades to SSE/WebSocket).

## 4. Recommended Repo Structure

```text
/Users/tomwillet/Documents/New project
  src/
    polymarket_agent/
      api.py
      config.py
      main.py
      service.py
      scheduler.py
      ticker.py
      decision.py
      executor.py
      state.py
      models.py
      strategies/
        base.py
        momentum.py
        mean_reversion.py
      risk/
        limits.py
        guard.py
      adapters/
        polymarket_ws.py
        polymarket_orders.py
      persistence/
        db.py
        repositories.py
      telemetry/
        logging.py
        metrics.py
  web/
    src/
      app/
      components/
      lib/
        api-client.ts
        types.ts
  deploy/
    systemd/
    nginx/
    scripts/
  tests/
    unit/
    integration/
    fixtures/
  docs/
    runbooks/
    api/
```

Notes:
- Keep exchange-specific code in `adapters/` only.
- Keep strategy code free of network and persistence concerns.
- Keep risk controls separate from strategy logic so strategy iteration does not weaken safety.

## 5. Agent Internals (Recommended Boundaries)

### 5.1 Scheduler
Responsibilities:
- Round boundary math.
- Activation window control.
- Clear emitted events (`round_activated`, `round_closed`).

### 5.2 Market Data Adapter
Responsibilities:
- Connect/reconnect policy.
- Subscription/auth handshake.
- Payload validation + normalization into internal `Tick` model.

Requirements:
- Reject malformed ticks early.
- Emit heartbeat metrics (last tick age, reconnect count).

### 5.3 Decision Engine
Responsibilities:
- Maintain short-horizon feature state.
- Ask strategies for candidate decisions.
- Resolve conflicts and confidence thresholds.

Recommendation:
- Standard strategy interface: `evaluate(state) -> StrategyDecision | None`.
- Add a `DecisionPolicy` layer for tie-breaking and rate-limiting.

### 5.4 Risk Guard (Must-have before live)
Minimum checks:
- Max position size.
- Max notional per trade.
- Max trades per round.
- Max losses per day.
- Cooldown after consecutive losses.
- Kill switch (manual + automatic).

### 5.5 Executor Adapter
Responsibilities:
- Auth/signing.
- Idempotent order submission.
- Retry policy with bounded attempts.
- Explicit error categories (transient vs fatal).

## 6. Persistence Recommendation

Phase 1 (simple, reliable):
- PostgreSQL (Lightsail managed DB or self-hosted).
- Tables:
  - `agent_heartbeats`
  - `tick_samples` (optional downsampled)
  - `decisions`
  - `orders`
  - `fills`
  - `risk_events`

Phase 2:
- Add Redis for low-latency ephemeral state and rate limits.

Why not only in-memory:
- You need durable audit trail for debugging and risk review.

## 7. API Design Recommendation

Keep two classes of endpoints:

1. Operational (`/healthz`, `/status`, `/metrics`)
- Read-only and lightweight.

2. Admin (`/admin/*`)
- Strategy enable/disable.
- Kill switch toggle.
- Risk limit updates.

Security:
- Frontend only talks to authenticated backend routes.
- Never expose execution or secret-bearing endpoints publicly.

## 8. Frontend (Next.js) Recommendation

Use Next.js App Router as you already started.

Pages:
- `Overview`: health, round timer, latest decision.
- `Decisions`: stream/history with filters.
- `Orders/Fills`: execution audit.
- `Risk`: active limits + recent risk events.
- `Settings` (admin-only): feature flags and strategy toggles.

Data strategy:
- Start with polling every 2-5s.
- Move to SSE for event stream when needed.

## 9. Deployment Recommendation (AWS Lightsail)

### Phase 1: Single instance + Docker Compose
- Service A: `agent` container.
- Service B: `web` container.
- Reverse proxy (Nginx or Caddy) for TLS and routing.
- Private network rules so agent API is not publicly exposed.

### Phase 2: Hardening
- Managed Postgres.
- CloudWatch log forwarding.
- Automated backups.
- Blue/green deploy script.

### Phase 3: Scale/Resilience
- Separate instances for web and agent.
- Optional move to ECS/Fargate if needed.

## 10. CI/CD Recommendation

Pipeline stages:
1. Lint/type checks (`ruff`, `mypy`, `eslint`, `tsc`).
2. Unit tests.
3. Integration tests with mocked websocket/order adapter.
4. Build Docker images.
5. Deploy to staging.
6. Manual approval to production.

Branch strategy:
- `main`: production-ready.
- Short-lived feature branches.
- Tag releases with semantic versioning.

## 11. Testing Strategy

### Unit tests
- Scheduler boundary cases.
- Tick parser normalization.
- Strategy outputs for deterministic fixtures.
- Risk guard behavior.

### Integration tests
- Simulated websocket feed over full round lifecycle.
- Decision + risk + executor chain with mocked exchange responses.

### Replay tests (high value)
- Replay historical tick windows and compare expected decisions.

## 12. Observability and Runbooks

Metrics to collect:
- Tick latency, reconnect count, decision rate.
- Decision-to-order latency.
- Order success/failure rates.
- PnL by strategy/day.
- Round activation misses.

Runbooks to include:
- Feed disconnected.
- Order API degraded.
- Strategy runaway behavior.
- Emergency disable procedure.

## 13. Security Requirements

- Store secrets in environment variables or AWS Secrets Manager.
- Enforce least-privilege API keys.
- Restrict admin routes by auth + IP/network policy.
- Maintain immutable audit logs for trade-related events.

## 14. Suggested Implementation Roadmap

1. Complete exchange adapters (ws + orders).
2. Implement risk guard and kill switch.
3. Add Postgres persistence and audit tables.
4. Expand dashboard pages (decisions/orders/risk).
5. Add auth for dashboard/admin.
6. Add CI pipeline and integration test harness.
7. Run paper-trading soak test before live trading.

## 15. Definition of Production-Ready (Minimum)

The project should be considered production-ready only when all are true:
- Real execution adapter implemented and tested.
- Risk guard enforced before every order.
- Durable persistence of decisions/orders/fills.
- Alerting on feed/order failures.
- Authenticated dashboard + admin controls.
- Documented kill switch and incident runbook.
