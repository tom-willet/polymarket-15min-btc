import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def next_quarter(dt: datetime) -> datetime:
    minute_block = (dt.minute // 15 + 1) * 15
    if minute_block == 60:
        return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return dt.replace(minute=minute_block, second=0, microsecond=0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Wait until next ET market boundary, then run one-trade market test")
    parser.add_argument("--start-ts-file", default="logs/latest_one_trade_real_start_ts.txt")
    parser.add_argument("--open-timeout-seconds", type=int, default=1200)
    parser.add_argument("--close-timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=2)
    args = parser.parse_args()

    et = ZoneInfo("America/New_York")
    now_et = datetime.now(et)
    target_et = next_quarter(now_et)
    wait_seconds = max(0.0, (target_et - now_et).total_seconds())

    time.sleep(wait_seconds)

    start_ts = time.time()
    Path(args.start_ts_file).write_text(str(start_ts), encoding="utf-8")

    cmd = [
        "/Users/tomwillet/Documents/New project/.venv/bin/python",
        "logs/run_one_trade_market_test.py",
        "--start-ts-file",
        args.start_ts_file,
        "--open-timeout-seconds",
        str(args.open_timeout_seconds),
        "--close-timeout-seconds",
        str(args.close_timeout_seconds),
        "--poll-seconds",
        str(args.poll_seconds),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    output = {
        "prep_now_et": now_et.isoformat(),
        "market_start_target_et": target_et.isoformat(),
        "wait_seconds": round(wait_seconds, 3),
        "runner_returncode": result.returncode,
        "runner_stdout": result.stdout,
        "runner_stderr": result.stderr,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
