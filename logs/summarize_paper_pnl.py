import argparse
import glob
import json
from pathlib import Path
from statistics import mean


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _ts(entry: dict) -> float | None:
    value = entry.get("logged_at", entry.get("ts"))
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _latest_soak_file() -> Path:
    candidates = sorted(glob.glob("logs/soak_shadow_*.jsonl"))
    if not candidates:
        raise SystemExit("No soak files found at logs/soak_shadow_*.jsonl")
    return Path(candidates[-1])


def _infer_window(start_ts_file: Path, soak_file: Path) -> tuple[float, float]:
    start_ts = float(start_ts_file.read_text(encoding="utf-8").strip())
    soak_rows = _load_jsonl(soak_file)
    if not soak_rows:
        raise SystemExit(f"No rows found in {soak_file}")
    end_ts_value = soak_rows[-1].get("ts")
    if not isinstance(end_ts_value, (int, float)):
        raise SystemExit(f"Missing numeric ts in last row of {soak_file}")
    return start_ts, float(end_ts_value)


def _daily_totals_from_closed(closed: list[dict]) -> dict[str, dict]:
    latest_by_day: dict[str, dict] = {}
    for row in closed:
        day_utc = row.get("day_utc")
        if isinstance(day_utc, str) and day_utc:
            latest_by_day[day_utc] = {
                "day_closed_trades": row.get("day_closed_trades"),
                "day_wins": row.get("day_wins"),
                "day_losses": row.get("day_losses"),
                "day_invalid": row.get("day_invalid"),
                "day_realized_pnl_usd": row.get("day_realized_pnl_usd"),
            }
    return dict(sorted(latest_by_day.items()))


def build_summary(
    *,
    start_ts: float,
    end_ts: float,
    soak_file: Path,
    paper_trades_file: Path,
    recent_count: int,
) -> dict:
    trades = _load_jsonl(paper_trades_file)
    window = [
        row
        for row in trades
        if (entry_ts := _ts(row)) is not None and start_ts <= entry_ts <= end_ts
    ]

    opened = [row for row in window if row.get("type") == "paper_trade_opened"]
    closed = [row for row in window if row.get("type") == "paper_trade_closed"]

    wins = sum(1 for row in closed if (row.get("outcome") or "").lower() == "win")
    losses = sum(1 for row in closed if (row.get("outcome") or "").lower() == "loss")
    invalid = sum(1 for row in closed if (row.get("outcome") or "").lower() == "invalid")

    return_pcts = [float(row["return_pct"]) for row in closed if isinstance(row.get("return_pct"), (int, float))]
    pnl_usd = [float(row["pnl_usd"]) for row in closed if isinstance(row.get("pnl_usd"), (int, float))]
    gross_pnl_usd = [float(row["gross_pnl_usd"]) for row in closed if isinstance(row.get("gross_pnl_usd"), (int, float))]

    resolved = wins + losses
    win_rate_pct = (wins / resolved * 100.0) if resolved > 0 else 0.0

    recent_trades = [
        {
            "id": row.get("id"),
            "action": row.get("action"),
            "polymarket_slug": row.get("polymarket_slug"),
            "entry_ts": row.get("entry_ts"),
            "entry_ts_iso_utc": row.get("entry_ts_iso_utc"),
            "exit_ts": row.get("exit_ts"),
            "exit_ts_iso_utc": row.get("exit_ts_iso_utc"),
            "market_close_ts": row.get("round_close_ts"),
            "market_close_ts_iso_utc": row.get("round_close_ts_iso_utc"),
            "open_minutes_to_market_close": row.get("open_minutes_to_close"),
            "trade_duration_minutes": row.get("trade_duration_minutes"),
            "confidence": row.get("confidence"),
            "confidence_pct": row.get("confidence_pct"),
            "decision_score": row.get("decision_score"),
            "decision_reason": row.get("decision_reason"),
            "btc_price_at_decision": row.get("btc_price_at_decision"),
            "btc_price_at_entry": row.get("btc_price_at_entry"),
            "btc_price_to_beat": row.get("btc_price_to_beat"),
            "btc_price_to_beat_source": row.get("btc_price_to_beat_source"),
            "btc_price_at_close": row.get("btc_price_at_close"),
            "btc_move_abs_vs_price_to_beat": row.get("btc_move_abs_vs_price_to_beat"),
            "btc_move_pct_vs_price_to_beat": row.get("btc_move_pct_vs_price_to_beat"),
            "expected_outcome_if_closed_now": row.get("expected_outcome_if_closed_now"),
            "entry_price": row.get("entry_price"),
            "exit_price": row.get("exit_price"),
            "stake_usd": row.get("stake_usd"),
            "polymarket_yes_price": row.get("polymarket_yes_price"),
            "polymarket_no_price": row.get("polymarket_no_price"),
            "market_implied_prob_yes": row.get("market_implied_prob_yes"),
            "model_prob_yes_raw": row.get("model_prob_yes_raw"),
            "model_prob_yes_adjusted": row.get("model_prob_yes_adjusted"),
            "model_prob_no_adjusted": row.get("model_prob_no_adjusted"),
            "edge_vs_market_implied_prob": row.get("edge_vs_market_implied_prob"),
            "polymarket_price_sum": row.get("polymarket_price_sum"),
            "polymarket_price_gap": row.get("polymarket_price_gap"),
            "outcome": row.get("outcome"),
            "return_pct": row.get("return_pct"),
            "pnl_usd": row.get("pnl_usd"),
            "day_utc": row.get("day_utc"),
            "day_realized_pnl_usd": row.get("day_realized_pnl_usd"),
        }
        for row in closed[-recent_count:]
    ]

    return {
        "window": {
            "soak_file": str(soak_file),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "duration_min": round((end_ts - start_ts) / 60.0, 2),
        },
        "summary": {
            "opened": len(opened),
            "closed": len(closed),
            "wins": wins,
            "losses": losses,
            "invalid": invalid,
            "win_rate_pct": round(win_rate_pct, 2),
            "avg_return_pct": round(mean(return_pcts), 4) if return_pcts else 0.0,
            "net_pnl_usd": round(sum(pnl_usd), 4),
            "gross_pnl_usd": round(sum(gross_pnl_usd), 4),
        },
        "daily_totals": _daily_totals_from_closed(closed),
        "recent_closed": recent_trades,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize paper trade PnL from JSONL logs")
    parser.add_argument(
        "--start-ts-file",
        default="logs/latest_simple_1h_start_ts.txt",
        help="Path to file containing soak start epoch seconds",
    )
    parser.add_argument(
        "--soak-file",
        default=None,
        help="Path to soak shadow jsonl file (default: latest logs/soak_shadow_*.jsonl)",
    )
    parser.add_argument(
        "--paper-trades-file",
        default="logs/paper_trades.jsonl",
        help="Path to paper trades jsonl",
    )
    parser.add_argument(
        "--recent-count",
        type=int,
        default=10,
        help="How many recent closed trades to include",
    )

    args = parser.parse_args()

    start_ts_file = Path(args.start_ts_file)
    paper_trades_file = Path(args.paper_trades_file)
    soak_file = Path(args.soak_file) if args.soak_file else _latest_soak_file()

    if not start_ts_file.exists():
        raise SystemExit(f"Missing start ts file: {start_ts_file}")
    if not soak_file.exists():
        raise SystemExit(f"Missing soak file: {soak_file}")
    if not paper_trades_file.exists():
        raise SystemExit(f"Missing paper trades file: {paper_trades_file}")

    start_ts, end_ts = _infer_window(start_ts_file, soak_file)
    report = build_summary(
        start_ts=start_ts,
        end_ts=end_ts,
        soak_file=soak_file,
        paper_trades_file=paper_trades_file,
        recent_count=args.recent_count,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
