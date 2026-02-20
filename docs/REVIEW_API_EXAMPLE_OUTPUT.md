# Review API Example Output

These are real example payloads from a successful local replay run on `2026-02-20`.

## Strategy Variable Snapshot (for Recommendation Context)

The values below are the current non-sensitive strategy and execution parameters from `.env`, included so recommendations can be tied to concrete settings.

```text
STRATEGY_MODE=btc_updown
BTC_UPDOWN_LIVE_ENABLED=true
BTC_UPDOWN_SHADOW_MODE=false

BTC_UPDOWN_MIN_CONFIDENCE_TO_TRADE=0.55
BTC_UPDOWN_MIN_SCORE_TO_TRADE=0.30
BTC_UPDOWN_MAX_ENTRY_PRICE=0.75
BTC_UPDOWN_KELLY_FRACTION=0.3
BTC_UPDOWN_MAX_TRADE_SIZE_USD=100
BTC_UPDOWN_MIN_TRADE_SIZE_USD=1

MAX_TRADES_PER_ROUND=1
TRADE_COOLDOWN_SECONDS=20

PAPER_TRADE_NOTIONAL_USD=10
PAPER_MIN_NET_EDGE_BPS=25
PAPER_EDGE_STRENGTH_TO_BPS=1000

PAPER_ENTRY_SLIPPAGE_BPS=50
PAPER_DYNAMIC_SLIPPAGE_ENABLED=true
PAPER_DYNAMIC_SLIPPAGE_EDGE_FACTOR_BPS=10
PAPER_DYNAMIC_SLIPPAGE_CONFIDENCE_FACTOR_BPS=8
PAPER_DYNAMIC_SLIPPAGE_EXPIRY_FACTOR_BPS=10
PAPER_MAX_SLIPPAGE_BPS=100
PAPER_GAS_FEE_USD_PER_SIDE=0.05
PAPER_ADVERSE_SELECTION_BPS=30
```

Note: historical runs may have used temporary runtime overrides (for validation), so exact per-run behavior can differ from this baseline snapshot.

## Replay Request Example

```bash
curl -X POST http://127.0.0.1:8080/admin/reviews/replay \
  -H "content-type: application/json" \
  -d '{"market_id":"btc-updown-15m-1771569000","round_close_ts":"2026-02-20T06:45:00+00:00","review_version":"v1.0"}'
```

## Replay Accepted (202)

```json
{
  "accepted": true,
  "review_key": {
    "market_id": "btc-updown-15m-1771569000",
    "round_close_ts": "2026-02-20T06:45:00+00:00",
    "review_version": "v1.0"
  }
}
```

## Review Detail (Succeeded, GPT-5.2)

`GET /reviews/1d1d64f5-1af0-4615-8228-7514bfb65b41`

```json
{
  "id": "1d1d64f5-1af0-4615-8228-7514bfb65b41",
  "market_id": "btc-updown-15m-1771569000",
  "market_slug": "btc-updown-15m-1771575300",
  "round_close_ts": "2026-02-20T06:45:00Z",
  "review_version": "v1.0",
  "status": "succeeded",
  "provider": "openai",
  "model": "gpt-5.2",
  "latency_ms": 23061,
  "token_in": 264,
  "token_out": 1182,
  "analysis_json": {
    "summary": {
      "market_outcome": "unknown",
      "pnl_usd": 0.0,
      "overall_grade": "C"
    },
    "decision_assessment": [],
    "risk_findings": [
      "operational_integrity",
      "high",
      "Round open_ts later than close_ts"
    ],
    "parameter_suggestions": [
      {
        "name": "suggestion_1",
        "suggested_value": "medium",
        "rationale": "Coerced from non-standard model output.",
        "confidence": 0.5
      }
    ],
    "next_experiments": [
      "No-trade attribution audit",
      "Timestamp/round mapping validation",
      "Shadow decision stream"
    ],
    "auto_apply_blocked": true
  },
  "analysis_markdown": "## Analysis\n\n- **No measurable trading performance**: ...\n- **Critical data integrity issue**: `round_open_ts` is after `round_close_ts`. ...",
  "error_message": null,
  "cost_usd_estimate": null
}
```

## Notes

- `status: succeeded` confirms end-to-end replay + provider + parser path is healthy.
- `auto_apply_blocked: true` confirms advisory-only guard is active.
- `parameter_suggestions` are normalized/coerced into strict schema for compatibility.

For market `btc-updown-15m-1771569000`, the strategy behavior was one-sided and execution-heavy: the `btc_updown` flow opened and closed 37 paper trades, all on `BUY_NO`, with an average confidence around 0.566 and average entry timing roughly 93 seconds before round close; performance in this window was poor, with 0 wins, 37 losses, and realized PnL of `-40.7` USD, which suggests that while the execution pipeline itself was active and consistently settling trades, the directional bias and trade-quality in this specific market close were unfavorable.

### Strategy, Timing, and Execution Evaluation

The observed behavior indicates overtrading with weak selectivity: the strategy repeatedly committed to the same direction (`BUY_NO`) despite a complete loss profile, which implies current confidence/score gates are not effectively filtering low-quality setups for this market regime. Timing was also likely suboptimal, with entries concentrated near the final ~90 seconds where noise and microstructure effects can dominate, reducing signal reliability and increasing adverse outcomes. Execution mechanics were operationally stable (trades opened/closed cleanly), but profitability suffered because risk/entry logic allowed too many similar bets without regime adaptation or directional diversity. To improve profitability, tighten entry criteria (raise minimum confidence and score thresholds), cap same-direction streak exposure per round, enforce stricter per-market trade count limits, and require confirmation from additional signals (for example, momentum + order book agreement) before entry. Add a no-trade fallback when conditions are ambiguous, and run targeted A/B paper tests on entry timing windows (for example, avoid final 60-90 seconds) to identify a higher edge zone before re-expanding trade frequency.

### Recommended Strategy Config Changes (Specific)

Apply these changes first for the next paper-trading soak window, then re-evaluate after at least 10-20 closed markets.

```text
# Selectivity and quality gates
BTC_UPDOWN_MIN_CONFIDENCE_TO_TRADE: 0.55 -> 0.68
BTC_UPDOWN_MIN_SCORE_TO_TRADE:      0.30 -> 0.50
PAPER_MIN_NET_EDGE_BPS:             25   -> 80

# Position sizing and risk compression
BTC_UPDOWN_KELLY_FRACTION:          0.30 -> 0.15
PAPER_TRADE_NOTIONAL_USD:           10   -> 5
BTC_UPDOWN_MAX_TRADE_SIZE_USD:      100  -> 25

# Reduce churn and late-window overtrading
MAX_TRADES_PER_ROUND:               1    -> 1
TRADE_COOLDOWN_SECONDS:             20   -> 90
BTC_UPDOWN_MAX_ENTRY_PRICE:         0.75 -> 0.65

# Cost realism guardrails (optional but recommended)
PAPER_ADVERSE_SELECTION_BPS:        30   -> 40
PAPER_MAX_SLIPPAGE_BPS:             100  -> 80
```

If the strategy becomes too inactive after these changes, relax only one lever at a time in this order: `BTC_UPDOWN_MIN_SCORE_TO_TRADE` (down by 0.05), then `BTC_UPDOWN_MIN_CONFIDENCE_TO_TRADE` (down by 0.03), while keeping `PAPER_MIN_NET_EDGE_BPS >= 60` and `TRADE_COOLDOWN_SECONDS >= 60`.
