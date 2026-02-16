import json
import subprocess
import time
import urllib.request

STATUS_URL = "http://127.0.0.1:8080/status"
CHECKS = 3
PROCESS_PATTERNS = [
    "record_shadow_soak.py",
    "record_min_edge_soak.py",
    "record_tuned_soak.py",
    "soak_shadow_",
    "soak_tuned_",
    "soak_dynamic_",
]


def process_running(pattern: str) -> bool:
    result = subprocess.run(
        ["pgrep", "-af", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def fetch_status() -> dict:
    with urllib.request.urlopen(STATUS_URL, timeout=10) as response:
        return json.loads(response.read().decode())


def main() -> None:
    stale = [pattern for pattern in PROCESS_PATTERNS if process_running(pattern)]
    if stale:
        raise SystemExit(f"Preflight failed: stale recorder processes running: {stale}")

    last_tick_ages: list[float] = []
    for _ in range(CHECKS):
        payload = fetch_status()
        latest_tick_ts = payload.get("latest_tick_ts")
        now = time.time()
        if not isinstance(latest_tick_ts, (int, float)):
            raise SystemExit("Preflight failed: latest_tick_ts missing in /status")

        age = now - float(latest_tick_ts)
        last_tick_ages.append(age)
        if age > 15:
            raise SystemExit(f"Preflight failed: stale tick age {age:.2f}s")

        time.sleep(2)

    print(
        json.dumps(
            {
                "ok": True,
                "checks": CHECKS,
                "status_url": STATUS_URL,
                "tick_age_samples_sec": [round(x, 3) for x in last_tick_ages],
            }
        )
    )


if __name__ == "__main__":
    main()
