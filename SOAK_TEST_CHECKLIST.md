# Single-Market Validation Checklist

Use this runbook for all validation work unless explicitly told otherwise.

## Goal

Run exactly one market-style validation cycle:

1. Start now.
2. Allow one `$1` paper trade.
3. Lock trading immediately after the first open.
4. Wait for settlement.
5. Review full opened and closed records for that exact trade ID.

## 1) Start service in one-trade mode

From repo root:

```bash
pkill -f 'src.polymarket_agent.service|record_shadow_soak.py' || true
source .venv/bin/activate

ts=$(date +%s)
echo "$ts" > logs/latest_one_trade_real_start_ts.txt
LOG="logs/one_trade_real_${ts}.log"
echo "$LOG" > logs/latest_shadow_log_path.txt

AGENT_TEST_MODE=false \
STRATEGY_MODE=btc_updown \
BTC_UPDOWN_LIVE_ENABLED=true \
BTC_UPDOWN_SHADOW_MODE=false \
MAX_TRADES_PER_ROUND=1 \
PAPER_TRADE_NOTIONAL_USD=1 \
BTC_UPDOWN_MIN_CONFIDENCE_TO_TRADE=0 \
BTC_UPDOWN_MIN_SCORE_TO_TRADE=-1 \
BTC_UPDOWN_MAX_ENTRY_PRICE=0.99 \
python -m src.polymarket_agent.service >> "$LOG" 2>&1
```

## 2) Run canonical one-trade capture

In a separate terminal:

```bash
source .venv/bin/activate
python logs/run_one_trade_market_test.py
```

What this does:

- Waits for the first opened paper trade after `latest_one_trade_real_start_ts.txt`.
- Enables kill-switch immediately.
- Waits for that exact trade ID to close.
- Prints full open and close JSON records.

## 3) Required output for every report

Always include:

- `trade_id`
- Full `paper_trade_opened` record
- Full `paper_trade_closed` record
- `btc_price_to_beat` and `btc_price_to_beat_source` from both records

Never summarize with only counts when discussing a specific validation trade.

## 4) If it fails

- No trade opened in timeout:

```bash
curl -sS http://127.0.0.1:8080/status | python -m json.tool
```

- Service down:

```bash
pkill -f 'src.polymarket_agent.service' || true
source .venv/bin/activate
python -m src.polymarket_agent.service
```

- Reset kill-switch after test:

```bash
curl -X POST http://127.0.0.1:8080/admin/kill-switch \
  -H 'content-type: application/json' \
  -d '{"enabled": false}'
```
