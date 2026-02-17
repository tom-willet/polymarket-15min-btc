import argparse
import json
import time
import urllib.request
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict one-trade market test and print full trade records")
    parser.add_argument(
        "--start-ts-file",
        default="logs/latest_one_trade_real_start_ts.txt",
        help="Path to file with test start timestamp",
    )
    parser.add_argument(
        "--open-timeout-seconds",
        type=int,
        default=240,
        help="How long to wait for first open trade",
    )
    parser.add_argument(
        "--close-timeout-seconds",
        type=int,
        default=420,
        help="How long to wait for that trade to close",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=2,
        help="Polling interval",
    )

    args = parser.parse_args()

    start_ts_file = Path(args.start_ts_file)
    if not start_ts_file.exists():
        raise SystemExit(f"Missing start ts file: {start_ts_file}")

    start_ts = float(start_ts_file.read_text(encoding="utf-8").strip())

    status = fetch_json(STATUS_URL)
    opened = wait_for_open(start_ts, args.open_timeout_seconds, args.poll_seconds)

    kill_switch_response = post_json(KILL_SWITCH_URL, {"enabled": True})

    trade_id = str(opened.get("id"))
    close = wait_for_close(trade_id, args.close_timeout_seconds, args.poll_seconds)

    output = {
        "test": {
            "start_ts": start_ts,
            "status_strategy_mode": status.get("strategy_mode"),
            "status_test_mode": status.get("test_mode"),
            "status_live_enabled": status.get("btc_updown_live_enabled"),
        },
        "kill_switch": kill_switch_response,
        "trade_id": trade_id,
        "opened_full": opened,
        "closed_full": close,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
