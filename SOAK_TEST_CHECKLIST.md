# Soak Test Checklist

Use this runbook after changes to streaming, decisioning, risk, or logging.

## 1) Choose profile

- Fast sanity run (10-15 minutes):
  - `cp deploy/env/agent.fast-test.env .env`
- Normal soak run (30-60 minutes):
  - `cp deploy/env/agent.normal.env .env`

Then add your Chainlink credentials into `.env`:

- `CHAINLINK_CANDLESTICK_LOGIN`
- `CHAINLINK_CANDLESTICK_PASSWORD`
- `CHAINLINK_CANDLESTICK_BASE_URL`

## 2) Start services

From repo root:

```bash
source .venv/bin/activate
python -m src.polymarket_agent.service
```

In another terminal:

```bash
cd web
npm run dev
```

## 3) Live checks during soak

- Dashboard: `http://127.0.0.1:3000`
- Logs page: `http://127.0.0.1:3000/logs`
- API status: `http://127.0.0.1:8080/status`

Quick freshness probe (every 2 seconds):

```bash
python3 - <<'PY'
import json, time, urllib.request

def snap():
    s=json.load(urllib.request.urlopen('http://127.0.0.1:8080/status',timeout=5))
    return s.get('latest_price'), s.get('latest_tick_ts')

p1,t1=snap(); time.sleep(2); p2,t2=snap()
print('tick_live', p1!=p2 and t1!=t2)
print('p1',p1,'p2',p2)
PY
```

## 4) Pass/fail gates

All must pass:

1. Freshness: `Last updated` on `/logs` stays under ~10s behind wall clock.
2. Liveness: `latest_price` and `latest_tick_ts` keep changing.
3. Signal quality: no repeated decision spam for identical state.
4. Timeline quality: focused rows are informative (not empty; not flooded).
5. Trade lifecycle visibility: open/close rows appear with strategy/confidence/outcome.

## 5) If it fails

- Restart backend:

```bash
pkill -f 'src.polymarket_agent.service' || true
source .venv/bin/activate
python -m src.polymarket_agent.service
```

- If Next.js is stale/corrupt:

```bash
cd web
pkill -f 'next dev' || true
rm -rf .next
npm run dev
```

- Reduce noise (in `.env`):
  - Increase `POLYMARKET_MOVE_LOG_COOLDOWN_SECONDS` (e.g. `20 -> 30`)
  - Increase `POLYMARKET_MOVE_THRESHOLD_PCT` (e.g. `3.0 -> 4.0`)

## 6) Capture feedback snapshot

After soak, record:

- Profile used (`fast-test` or `normal`)
- Run duration
- Count of opportunities/opened/closed/wins/losses
- Any stale gaps and restart incidents
- Suggested new defaults for threshold/cooldown
