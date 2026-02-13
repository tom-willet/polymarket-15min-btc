# Polymarket BTC 15m Agent + Next.js Dashboard

This repo now has two services:

1. `agent` (Python): continuously runs market-window logic and exposes status API.
2. `web` (Next.js): live dashboard for agent state and decisions.

## Architecture

- Python service:
  - Round scheduler activates only in final 3 minutes of every 15-minute round.
  - Websocket ticker stream feeds decision router.
  - Strategy router picks strategy modules (`momentum`, `mean_reversion`).
  - Executor currently logs actions (`DRY_RUN=true`).
  - FastAPI exposes:
    - `GET /healthz`
    - `GET /status`

- Next.js dashboard:
  - Polls `/api/agent/status` every 2.5s.
  - Next.js route proxies to Python API (`AGENT_API_BASE_URL`).
  - Displays round timing, latest tick, last decision, and recent events.

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
```

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
- `AGENT_TEST_MODE` default `false` (when true, uses test-mode round timings below).
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
- `ROUND_SECONDS` default `900`.
- `ACTIVATION_LEAD_SECONDS` default `180`.
- `WS_PING_INTERVAL_SECONDS` default `15`.
- `DRY_RUN` default `true`.
- `AGENT_API_PORT` default `8080`.
- `MAX_TRADES_PER_ROUND` default `2`.
- `TRADE_COOLDOWN_SECONDS` default `8`.

### Web (`web/.env.local`)

- `AGENT_API_BASE_URL` default `http://127.0.0.1:8080`.

## Soak Test Workflow

- Fast sanity profile: `cp deploy/env/agent.fast-test.env .env`
- Normal soak profile: `cp deploy/env/agent.normal.env .env`
- Add Chainlink credentials to `.env` after copying profile values.
- Start backend + web, then monitor `/status` and `/logs`.
- Full checklist: `SOAK_TEST_CHECKLIST.md`.

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
  - max trades per round
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
