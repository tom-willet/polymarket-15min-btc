## Speckit

#### Add to a project

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init --here
```

#### Upgrade Speckit

```bash
uv tool install specify-cli --force --from git+https://github.com/github/spec-kit.git
specify init --here --force --ai copilot
```

#### Commands

````bash

/speckit.constitution    # Establish project principles
/speckit.specify         # Create baseline specification
/speckit.clarify         # Ask structured questions to de-risk ambiguous areas before planning
/speckit.plan            # Create implementation plan
# /speckit.checklist       # Generate quality checklists to validate requirements completeness, clarity, and consistency
/speckit.tasks           # Generate actionable tasks
/speckit.analyze         # Cross-artifact consistency & alignment report
/speckit.implement       # Execute implementation


# Polymarket BTC 15m Agent + Next.js Dashboard

This repo now has two services:

1. `agent` (Python): continuously runs market-window logic and exposes status API.
2. `web` (Next.js): live dashboard for agent state and decisions.

## Architecture

- Python service:
  - Scheduler activates near market close to evaluate a single binary YES/NO outcome.
  - Websocket ticker stream feeds decision router.
  - Strategy router picks strategy modules (`momentum`, `mean_reversion`).
  - Executor currently logs actions (`DRY_RUN=true`).
  - FastAPI exposes:
    - `GET /healthz`
    - `GET /status`

- Next.js dashboard:
  - Polls `/api/agent/status` every 2.5s.
  - Next.js route proxies to Python API (`AGENT_API_BASE_URL`).
  - Displays market timing, latest tick, last decision, and recent events.

## Repo Layout

- `src/polymarket_agent/` Python agent + API
- `web/` Next.js app
- `docker-compose.yml` two-service local/prod deployment
- `Dockerfile.agent` Python image
- `web/Dockerfile` Next.js image
- `deploy/systemd/` systemd unit templates

## Requirements

- Python 3.11+
- Node 20+
- npm 10+

## Local Development

### 1) Agent

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.polymarket_agent.service
````

Agent API will run on `http://127.0.0.1:8080` by default.

### Run tests

```bash
source .venv/bin/activate
pytest
```

### 2) Web

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Dashboard runs on `http://127.0.0.1:3000`.

## Environment Variables

### Agent (`.env`)

- `POLYMARKET_BTC_STREAM` default `binance`.
- `POLYMARKET_BTC_SYMBOL` default `BTCUSDT` (use `BTCUSD` for `chainlink` stream).
- `POLYMARKET_BTC_WINDOW` default `15m`.
- `AGENT_TEST_MODE` default `false` (when true, uses short test-mode market-cycle timings below).
- `TEST_MODE_ROUND_SECONDS` default `120`.
- `TEST_MODE_ACTIVATION_LEAD_SECONDS` default `100`.
- `CHAINLINK_CANDLESTICK_LOGIN` required when `POLYMARKET_BTC_STREAM=chainlink`.
- `CHAINLINK_CANDLESTICK_PASSWORD` required when `POLYMARKET_BTC_STREAM=chainlink`.
- `CHAINLINK_CANDLESTICK_BASE_URL` required when `POLYMARKET_BTC_STREAM=chainlink`.
- `POLYMARKET_WS_ENABLED` default `true`.
- `POLYMARKET_WS_URL` default `wss://ws-subscriptions-clob.polymarket.com/ws/market`.
- `POLYMARKET_MARKET_REFRESH_SECONDS` default `12`.
- `POLYMARKET_MOVE_THRESHOLD_PCT` default `3.0`.
- `POLYMARKET_MOVE_MIN_ABS_DELTA` default `0.03`.
- `POLYMARKET_MOVE_LOG_COOLDOWN_SECONDS` default `5.0`.
- `POLY_WS_URL` required only for `POLYMARKET_BTC_STREAM=custom`.
- `POLY_MARKET_SYMBOL` default `BTC`.
- `ROUND_SECONDS` default `900` (market-cycle length in seconds).
- `ACTIVATION_LEAD_SECONDS` default `180`.
- `WS_PING_INTERVAL_SECONDS` default `15`.
- `DRY_RUN` default `true`.
- `AGENT_API_PORT` default `8080`.
- `MAX_TRADES_PER_ROUND` default `2` (limit per market cycle).
- `TRADE_COOLDOWN_SECONDS` default `8`.
- `PAPER_TRADE_NOTIONAL_USD` default `25`.
- `PAPER_ENTRY_SLIPPAGE_BPS` default `50`.
- `PAPER_DYNAMIC_SLIPPAGE_ENABLED` default `false`.
- `PAPER_DYNAMIC_SLIPPAGE_EDGE_FACTOR_BPS` default `25`.
- `PAPER_DYNAMIC_SLIPPAGE_CONFIDENCE_FACTOR_BPS` default `20`.
- `PAPER_DYNAMIC_SLIPPAGE_EXPIRY_FACTOR_BPS` default `30`.
- `PAPER_MAX_SLIPPAGE_BPS` default `200`.
- `PAPER_GAS_FEE_USD_PER_SIDE` default `0.05`.
- `PAPER_ADVERSE_SELECTION_BPS` default `30`.
- `PAPER_MIN_NOTIONAL_USD` default `1`.
- `PAPER_MIN_NET_EDGE_BPS` default `0` (when > 0, blocks entries with estimated net edge below threshold).
- `PAPER_EDGE_STRENGTH_TO_BPS` default `1000` (conversion factor from odds edge strength to expected edge bps).
- `STRATEGY_MODE` default `classic` (set `btc_updown` to run only the BTC up/down strategy).
- `BTC_UPDOWN_SHADOW_MODE` default `true` (logs candidate decisions even when not live-routing).
- `BTC_UPDOWN_LIVE_ENABLED` default `false` (must be true to execute BTC up/down decisions when `STRATEGY_MODE=btc_updown`).
- `BTC_UPDOWN_MIN_CONFIDENCE_TO_TRADE` default `0.35`.
- `BTC_UPDOWN_MIN_SCORE_TO_TRADE` default `0.2`.
- `BTC_UPDOWN_MAX_ENTRY_PRICE` default `0.85`.
- `BTC_UPDOWN_KELLY_FRACTION` default `0.3`.
- `BTC_UPDOWN_MAX_TRADE_SIZE_USD` default `100`.
- `BTC_UPDOWN_MIN_TRADE_SIZE_USD` default `1`.

### Web (`web/.env.local`)

- `AGENT_API_BASE_URL` default `http://127.0.0.1:8080`.

### End-of-market LLM review (`.env`)

- `LLM_REVIEW_ENABLED` default `false`.
- `LLM_REVIEW_PROVIDER` default `openai`.
- `LLM_REVIEW_MODEL` default `gpt-5.2`.
- `LLM_REVIEW_TIMEOUT_SECONDS` default `20`.
- `LLM_REVIEW_MAX_RETRIES` default `2`.
- `LLM_REVIEW_VERSION` default `v1.0`.
- `LLM_REVIEW_MIN_ABS_SCORE` default `0.25`.
- `LLM_REVIEW_REQUIRE_TRADE` default `false`.
- `LLM_REVIEW_SAVE_INPUT_PAYLOAD` default `true`.
- `LLM_REVIEW_PAYLOAD_RETENTION_DAYS` default `30`.

### Review APIs

- `GET /reviews/latest`
- `GET /reviews?limit=50&status=succeeded`
- `GET /reviews/{id}`
- `POST /admin/reviews/replay`

Replay example:

```bash
curl -X POST http://127.0.0.1:8080/admin/reviews/replay \
  -H "content-type: application/json" \
  -d '{"market_id":"btc-up-15m","round_close_ts":"2026-02-18T15:15:00Z","review_version":"v1.0"}'
```

## Validation Workflow (Canonical)

Default validation mode is a single-market, single-trade test:

1. Start service in live paper mode with `$1` notional.
2. Wait for first opened trade.
3. Enable kill-switch immediately.
4. Wait for that exact trade to settle.
5. Report full open/close JSON records for that trade ID.

Full checklist: `SOAK_TEST_CHECKLIST.md`.

### Validation helper scripts

- `logs/soak_preflight.py`: verifies stale recorder processes are not running and checks tick freshness.
- `logs/run_one_trade_market_test.py`: canonical one-trade capture; waits for first open, enables kill-switch, waits for close, prints full trade records.
- `logs/run_next_market_one_trade.py`: waits for the next ET quarter-hour boundary, then runs the canonical one-trade capture.
- `logs/run_continuous_one_trade_per_market.py`: continuously runs one trade per market across consecutive markets for a configurable duration; captures full open/close records for each cycle and keeps kill-switch discipline per market.
- `logs/summarize_paper_pnl.py`: prints JSON PnL summary for a selected window with recent closed trade details, including BTC entry/close context and model-vs-market probability fields.

Trade records include `btc_price_to_beat_source` for reference provenance. Expected values are:

- `chainlink_history_rows` (preferred)
- `binance_klines` (fallback)
- `live_tick_fallback` (fallback)
- `round_open_fallback` (close-time fallback when older entries miss source)

Example:

```bash
source .venv/bin/activate
python logs/soak_preflight.py
python logs/run_one_trade_market_test.py
python logs/summarize_paper_pnl.py --start-ts-file logs/latest_one_trade_real_start_ts.txt --recent-count 1

# Continuous validation example: 4 hours, one trade per market
python logs/run_continuous_one_trade_per_market.py --hours 4
```

## Deploy on AWS Lightsail

Two good paths:

### Option A: Docker Compose (recommended for first deployment)

1. Create a Lightsail Ubuntu instance.
2. Install Docker + Compose plugin.
3. Clone this repo to `/opt/polymarket-agent`.
4. Create `/opt/polymarket-agent/.env` with production secrets/config.
5. Run:

```bash
cd /opt/polymarket-agent
docker compose up -d --build
```

6. Open firewall ports:

- `3000` for dashboard (or front with nginx on `80/443`).
- Keep `8080` private if possible.

### Option B: systemd processes

1. Set up Python venv and install deps.
2. Build Next.js app (`npm install && npm run build`).
3. Copy unit files from `deploy/systemd/` into `/etc/systemd/system/`.
4. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable polymarket-agent polymarket-web
sudo systemctl start polymarket-agent polymarket-web
```

## What Is Still Stubbed

- Real Polymarket auth/order execution in `src/polymarket_agent/executor.py`.
- Non-binance websocket payload parse/subscribe in `src/polymarket_agent/ticker.py`.
- Persistent DB, PnL accounting, and robust risk controls.

## Minimal Risk Controls Included

- In-memory kill switch and trade blocking is wired before execution.
- In-memory limits include:
  - max trades per market cycle
  - cooldown between trade executions
- Admin endpoint for kill switch:

```bash
curl -X POST http://127.0.0.1:8080/admin/kill-switch \
  -H "content-type: application/json" \
  -d '{"enabled": true}'
```

## Polymarket Odds in Decisions

- The backend now ingests Polymarket CLOB odds and tracks active YES/NO token prices.
- Decision confidence is adjusted by odds alignment:
  - supportive odds: confidence boost
  - opposing odds: confidence penalty
- Low-confidence signals after odds adjustment are filtered before execution.

## Production Checklist

- Implement authenticated order execution.
- Add strict risk limits (max position/trades/loss per round/day).
- Add structured logging + alerting.
- Restrict dashboard/API access with auth + network policy.
- Add integration tests for websocket parsing and strategy routing.
