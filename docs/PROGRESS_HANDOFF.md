# Progress Handoff (BTC Up/Down + Paper Settlement)

## Scope completed

- Added `btc_updown` strategy implementation and router integration for:
  - shadow logging mode
  - optional live routing mode
- Expanded config surface for:
  - paper simulation cost/slippage controls
  - strategy mode toggles and BTC up/down thresholds
- Reworked paper settlement flow toward binary-market semantics (YES/NO payout outcome) with close-event metadata.
- Added/updated unit coverage around config parsing and paper-trading behavior.
- Added soak utilities for preflight, recording, and summary analysis.

## Operational notes

- Use `.env.example` or `deploy/env/agent.*.env` as baseline profiles.
- For calibration runs, default flow:
  1. `python logs/soak_preflight.py`
  2. `SOAK_DURATION_SECONDS=<seconds> python logs/record_shadow_soak.py`
  3. `python logs/analyze_shadow_soak.py`

## Last soak snapshot summary

- High activity achieved with relaxed thresholds.
- Post-fix runs produced valid close outcomes (no unknown settlement for the analyzed clean window).
- Keep `PAPER_MIN_NET_EDGE_BPS` > 0 for less aggressive live-like filtering once calibration collection is complete.

## Suggested next pass

- Add explicit USD PnL fielding in close records for easier run-to-run comparisons.
- Promote one soak profile as the team default and lock it in `deploy/env`.
- Add one integration test around end-of-round settlement mapping (open/close price -> yes/no outcome).
