# Frontend Modernization Plan

## 1) Purpose

This document defines the frontend modernization plan for the Polymarket BTC 15m agent dashboard.

Primary intent:

- Keep backend collection/trading workflows running in the background.
- Replace outdated frontend data assumptions with the **new trade schema** now used by the agent.
- Support continuous testing mode (multi-hour, one trade per market) while preserving full per-trade and per-market traceability.

---

## 2) Product Goals

1. Show live system state clearly (service health, market, kill switch, timing).
2. Display all trade records with full fidelity using the new schema.
3. Make each trade explainable (decision inputs, market context, price-to-beat provenance, outcome/PnL).
4. Support continuous run analysis across many markets without losing per-market detail.
5. Be resilient to schema growth via a typed normalization layer.

---

## 3) Non-Goals (v1)

- No strategy editing from UI.
- No direct execution controls beyond existing admin endpoints.
- No historical warehouse/OLAP backend redesign.
- No major visual design overhaul before data model alignment.

---

## 4) Current State Summary

- Existing Next.js dashboard is strongly tied to `/status` + event feed patterns and older assumptions.
- New trade lifecycle payloads are much richer than what current UI renders.
- Continuous run mode now exists (`logs/run_continuous_one_trade_per_market.py`) and emits full cycle-level records.

Conclusion: frontend should be refactored as a data-first read model around `paper_trade_opened` + `paper_trade_closed` records and continuous cycle artifacts.

---

## 5) Required Data Contract (Going Forward)

The UI must treat these fields as first-class data.

### 5.1 Open Record (paper_trade_opened)

Core identity/timing:

- `id`, `type`, `ts`, `entry_ts`, `entry_ts_iso_utc`
- `round_id`, `round_close_ts`, `round_close_ts_iso_utc`
- `open_seconds_to_close`, `open_minutes_to_close`

Trade intent:

- `action`, `strategy`
- `confidence`, `confidence_pct`
- `decision_score`, `decision_reason`, `decision_signals`

BTC/settlement reference context:

- `btc_price_at_decision`, `btc_price_at_entry`
- `btc_price_to_beat`
- `btc_price_to_beat_source`  
  Expected values:
  - `chainlink_history_rows` (preferred)
  - `binance_klines`
  - `live_tick_fallback`
  - `round_open_fallback` (close-time fallback)
- `expected_outcome_if_closed_now`

Market pricing context:

- `polymarket_slug`
- `polymarket_yes_price`, `polymarket_no_price`
- `polymarket_price_sum`, `polymarket_price_gap`
- `market_implied_prob_yes`
- `model_prob_yes_raw`, `model_prob_yes_adjusted`, `model_prob_no_adjusted`
- `edge_vs_market_implied_prob`

Execution/sizing:

- `signal_price`, `entry_price`
- `edge_strength`
- `notional_usd`, `stake_usd`
- `entry_slippage_bps`, `effective_entry_slippage_bps`
- `expected_edge_bps`, `estimated_total_cost_bps`, `estimated_net_edge_bps`
- `gas_fee_usd_per_side`, `adverse_selection_bps`
- `odds_alignment`
- `risk_assessment`

### 5.2 Close Record (paper_trade_closed)

Must preserve all relevant open context plus close outcomes:

- Identity/timing: `id`, `round_id`, `entry_ts*`, `exit_ts*`, `trade_duration_*`
- Market/BTC outcome fields:
  - `market_outcome`, `outcome`
  - `btc_round_open_price`, `btc_round_close_price`
  - `btc_price_at_close`
  - `btc_move_abs_vs_price_to_beat`, `btc_move_pct_vs_price_to_beat`
- Financials:
  - `stake_usd`
  - `return_pct`, `gross_return_pct`, `total_cost_pct`
  - `gas_fees_usd`, `adverse_selection_bps_applied`
  - `gross_pnl_usd`, `pnl_usd`
- Day rollups:
  - `day_utc`, `day_closed_trades`, `day_wins`, `day_losses`, `day_invalid`
  - `day_realized_pnl_usd`

### 5.3 Continuous Run Artifact

From `continuous_market_run_<ts>.json`:

- `run` metadata (start/end, requested duration, timeouts)
- `cycles[]` with
  - `cycle_index`, `cycle_started_ts`, `status_before`
  - `kill_switch_after_open`
  - `trade_id`, `opened_full`, `closed_full`
- `summary` (markets, wins/losses/invalid, net pnl)
- `errors[]`

---

## 6) Frontend Information Architecture

## 6.1 Pages

1. `/` Dashboard (high-level live status + latest trades)
2. `/trades` Trade explorer (table + filters + detail drawer)
3. `/runs` Continuous runs (cycle timeline + run summaries)
4. `/logs` Existing event timeline (retain, but not primary source of truth)

## 6.2 Key Panels

- **System Status Panel**: health, round, close countdown, kill switch state, latest tick.
- **Latest Trade Panel**: most recent open/close pair with outcome and provenance.
- **Trade Table**: dense view with sorting/filtering and expandable details.
- **Trade Detail Drawer**: full payload view (open + close), grouped by category.
- **Continuous Run Timeline**: one row/card per market cycle.

---

## 7) Technical Architecture Notes

## 7.1 Data Adapter Layer (Required)

Create a dedicated adapter module in `web/src/lib/` to:

- Parse raw API JSON into typed view models.
- Handle nulls/missing keys safely.
- Derive computed fields (e.g., time-to-close, edge deltas, net/gross comparisons).
- Version-guard schema expansion to avoid component breakage.

Recommended modules:

- `tradeSchema.ts` (types + zod/io-ts optional validators)
- `tradeAdapters.ts` (raw -> UI model)
- `runAdapters.ts` (continuous run JSON -> UI model)

## 7.2 API Surface (Web app API routes)

Keep existing route style under `web/src/app/api/agent/*` and add:

- `GET /api/agent/paper-trades` (existing)
- `GET /api/agent/status` (existing)
- `GET /api/agent/continuous-run/latest` (new; reads path pointer + file)
- `GET /api/agent/continuous-run/:id` (optional)

## 7.3 Refresh Strategy

- Status: poll every 2–3s.
- Trades: poll every 3–5s.
- Continuous run file: poll every 5–10s.
- Use client-side stale-while-revalidate pattern to avoid UI flicker.

---

## 8) UX/Display Requirements

## 8.1 Trade Table Default Columns

- Open/Close time (UTC localizable)
- `trade_id`
- `polymarket_slug`
- `action`
- `market_outcome`, `outcome`
- `entry_price`, `exit_price`
- `btc_price_to_beat`, `btc_price_to_beat_source`, `btc_price_at_close`
- `return_pct`, `pnl_usd`
- `confidence_pct`, `decision_score`

## 8.2 Required Filters

- Time window
- Outcome (win/loss/invalid)
- Action (BUY_YES/BUY_NO)
- Slug / round id
- Price-to-beat source

## 8.3 Trade Detail Sections

1. Identity & timing
2. Decision context
3. Market pricing context
4. BTC reference & movement
5. Execution/slippage/cost context
6. Outcome & PnL
7. Raw JSON payloads

---

## 9) Delivery Plan (Phased)

## Phase 1: Data Foundation

- Add adapter/types layer.
- Add/clean API routes for continuous run data.
- Build basic status + trades fetch hooks.

Exit criteria:

- Trade rows render from new schema without using old event parsing logic.

## Phase 2: Trades Explorer

- Build `/trades` with table, filters, and detail drawer.
- Include all required fields and source provenance.

Exit criteria:

- Any specific trade can be fully audited from UI alone.

## Phase 3: Continuous Runs

- Build `/runs` using `continuous_market_run_*.json` model.
- Show cycle-by-cycle cards and aggregate summary.

Exit criteria:

- User can inspect sequential market transitions and one-trade-per-market behavior.

## Phase 4: Dashboard Refresh

- Refactor `/` dashboard to use adapters and new cards.
- Keep old visual style cues where useful, but remove outdated assumptions.

Exit criteria:

- Home dashboard reflects current schema and continuous testing state.

---

## 10) Validation & QA Checklist

- Confirm `btc_price_to_beat_source` visible in both list and detail views.
- Confirm open/close pairing by `trade_id` is correct.
- Confirm continuous cycles preserve previous records while new cycles append.
- Confirm no data loss during market rollover boundaries.
- Confirm UI remains stable if optional fields are missing.
- Confirm net/gross/day values match logged records exactly.

---

## 11) Risks and Mitigations

1. **Schema drift risk**  
   Mitigation: centralized adapter + runtime validation guards.

2. **Large payload rendering risk**  
   Mitigation: virtualized table and lazy detail rendering.

3. **Polling pressure risk**  
   Mitigation: staggered polling intervals + request dedupe.

4. **Operator confusion from old/new mixed metrics**  
   Mitigation: explicit labels for source fields, gross vs net, and expected vs realized outcomes.

---

## 12) Immediate Build Order (Actionable)

1. Create `web/src/lib/tradeSchema.ts` and `tradeAdapters.ts`.
2. Add `continuous-run/latest` API route.
3. Build `/trades` read-only explorer first.
4. Build `/runs` page for continuous cycle visibility.
5. Refactor home dashboard last.

---

## 13) Definition of Done

Frontend modernization is complete when:

- New schema fields are first-class in UI (not hidden behind raw JSON only).
- One-trade-per-market continuous testing is fully visible cycle by cycle.
- Per-trade forensic analysis (why opened, why won/lost, source provenance) is possible from UI.
- Old event-centric assumptions are no longer required for core trade analysis.
