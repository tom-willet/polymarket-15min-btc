import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

STATUS_URL = "http://127.0.0.1:8080/status"
PAPER_TRADES_URL = "http://127.0.0.1:8080/paper-trades"
KILL_SWITCH_URL = "http://127.0.0.1:8080/admin/kill-switch"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def get_items() -> list[dict]:
    return fetch_json(PAPER_TRADES_URL).get("items", [])


def ts(entry: dict) -> float | None:
    value = entry.get("logged_at", entry.get("ts"))
    if isinstance(value, (int, float)):
        return float(value)
    return None


def latest_open_after(start_ts: float) -> dict | None:
    items = get_items()
    opened = [
        row
        for row in items
        if row.get("type") == "paper_trade_opened"
        and (row_ts := ts(row)) is not None
        and row_ts >= start_ts
    ]
    return opened[0] if opened else None


def latest_close_for_id(trade_id: str) -> dict | None:
    items = get_items()
    closed = [
        row
        for row in items
        if row.get("type") == "paper_trade_closed" and row.get("id") == trade_id
    ]
    return closed[-1] if closed else None


def wait_for_open(start_ts: float, timeout_seconds: int, poll_seconds: int) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        opened = latest_open_after(start_ts)
        if opened:
            return opened
        time.sleep(poll_seconds)
    raise TimeoutError("No paper_trade_opened found in timeout window")


def wait_for_close(trade_id: str, timeout_seconds: int, poll_seconds: int) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        closed = latest_close_for_id(trade_id)
        if closed:
            return closed
        time.sleep(poll_seconds)
    raise TimeoutError(f"No paper_trade_closed found for trade_id={trade_id}")


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_snapshot(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def summarize_cycles(cycles: list[dict]) -> dict:
    closed = [cycle.get("closed_full", {}) for cycle in cycles if isinstance(cycle.get("closed_full"), dict)]
    wins = sum(1 for row in closed if str(row.get("outcome", "")).lower() == "win")
    losses = sum(1 for row in closed if str(row.get("outcome", "")).lower() == "loss")
    invalid = sum(1 for row in closed if str(row.get("outcome", "")).lower() == "invalid")
    pnl_values = [float(row.get("pnl_usd")) for row in closed if isinstance(row.get("pnl_usd"), (int, float))]
    return {
        "markets_completed": len(closed),
        "wins": wins,
        "losses": losses,
        "invalid": invalid,
        "net_pnl_usd": round(sum(pnl_values), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Continuously run one-trade-per-market validation for several hours"
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=3.0,
        help="How many hours to keep running",
    )
    parser.add_argument(
        "--max-markets",
        type=int,
        default=0,
        help="Optional hard cap on markets (0 = no cap)",
    )
    parser.add_argument(
        "--start-ts-file",
        default="logs/latest_one_trade_real_start_ts.txt",
        help="Path to write the latest cycle start timestamp",
    )
    parser.add_argument(
        "--run-path-file",
        default="logs/latest_continuous_run_path.txt",
        help="Path to write the continuous output JSON path",
    )
    parser.add_argument(
        "--output-file",
        default="",
        help="Optional output file path (default: logs/continuous_market_run_<ts>.json)",
    )
    parser.add_argument(
        "--open-timeout-seconds",
        type=int,
        default=1200,
        help="Timeout waiting for each market open",
    )
    parser.add_argument(
        "--close-timeout-seconds",
        type=int,
        default=1200,
        help="Timeout waiting for each trade close",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=2,
        help="Polling interval",
    )

    args = parser.parse_args()

    run_started_ts = time.time()
    deadline_ts = run_started_ts + max(0.0, args.hours * 3600.0)

    output_file = Path(args.output_file) if args.output_file else Path("logs") / f"continuous_market_run_{int(run_started_ts)}.json"
    run_path_file = Path(args.run_path_file)
    start_ts_file = Path(args.start_ts_file)

    run_path_file.write_text(str(output_file), encoding="utf-8")

    payload: dict = {
        "run": {
            "started_at_utc": now_iso_utc(),
            "started_ts": run_started_ts,
            "deadline_ts": deadline_ts,
            "hours_requested": args.hours,
            "max_markets": args.max_markets,
            "open_timeout_seconds": args.open_timeout_seconds,
            "close_timeout_seconds": args.close_timeout_seconds,
            "poll_seconds": args.poll_seconds,
        },
        "cycles": [],
        "summary": {},
        "errors": [],
    }
    write_snapshot(output_file, payload)

    post_json(KILL_SWITCH_URL, {"enabled": False})

    cycle_index = 0
    while time.time() < deadline_ts:
        if args.max_markets > 0 and cycle_index >= args.max_markets:
            break

        cycle_started_ts = time.time()
        start_ts_file.write_text(str(cycle_started_ts), encoding="utf-8")

        status_before = fetch_json(STATUS_URL)

        try:
            opened = wait_for_open(
                cycle_started_ts,
                args.open_timeout_seconds,
                args.poll_seconds,
            )
            kill_switch_response = post_json(KILL_SWITCH_URL, {"enabled": True})
            trade_id = str(opened.get("id"))
            closed = wait_for_close(trade_id, args.close_timeout_seconds, args.poll_seconds)
        except Exception as exc:  # noqa: BLE001
            payload["errors"].append(
                {
                    "cycle_index": cycle_index,
                    "ts": time.time(),
                    "message": str(exc),
                }
            )
            break
        finally:
            post_json(KILL_SWITCH_URL, {"enabled": False})

        cycle_record = {
            "cycle_index": cycle_index,
            "cycle_started_ts": cycle_started_ts,
            "cycle_started_at_utc": datetime.fromtimestamp(cycle_started_ts, tz=timezone.utc).isoformat(),
            "status_before": {
                "active_round_id": status_before.get("active_round_id"),
                "round_close_ts": status_before.get("round_close_ts"),
                "kill_switch_enabled": status_before.get("kill_switch_enabled"),
                "polymarket_slug": status_before.get("polymarket_slug"),
            },
            "kill_switch_after_open": kill_switch_response,
            "trade_id": opened.get("id"),
            "opened_full": opened,
            "closed_full": closed,
        }
        payload["cycles"].append(cycle_record)
        cycle_index += 1

        payload["summary"] = summarize_cycles(payload["cycles"])
        write_snapshot(output_file, payload)

    payload["run"]["ended_at_utc"] = now_iso_utc()
    payload["run"]["ended_ts"] = time.time()
    payload["summary"] = summarize_cycles(payload["cycles"])
    write_snapshot(output_file, payload)

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
