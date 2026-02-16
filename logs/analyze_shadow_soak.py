import ast
import glob
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

LATEST_SHADOW_LOG_PATH_FILE = Path("logs/latest_shadow_log_path.txt")


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_log_epoch(line: str) -> float | None:
    # Example prefix: 2026-02-13 01:03:20,001
    try:
        stamp = line[:23]
        dt = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S,%f")
        return dt.timestamp()
    except Exception:
        return None


def main() -> None:
    soak_candidates = sorted(glob.glob("logs/soak_shadow_*.jsonl"))
    if not soak_candidates:
        raise SystemExit("No soak_shadow files found")

    soak_path = Path(soak_candidates[-1])
    soak_rows = [r for r in load_jsonl(soak_path) if "error" not in r]
    if not soak_rows:
        raise SystemExit(f"No valid rows in {soak_path}")

    start_ts = float(soak_rows[0]["ts"])
    end_ts = float(soak_rows[-1]["ts"])

    shadow_log_rel = LATEST_SHADOW_LOG_PATH_FILE.read_text(encoding="utf-8").strip()
    shadow_log_path = Path(shadow_log_rel)

    candidates: list[dict] = []
    pattern = re.compile(r"Shadow strategy=btc_updown candidate=(\{.*\})")

    with shadow_log_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if "Shadow strategy=btc_updown candidate=" not in line:
                continue

            epoch = parse_log_epoch(line)
            if epoch is None or not (start_ts <= epoch <= end_ts):
                continue

            match = pattern.search(line)
            if not match:
                continue

            payload_str = match.group(1)
            try:
                payload = ast.literal_eval(payload_str)
            except Exception:
                continue

            if isinstance(payload, dict):
                payload["logged_ts"] = epoch
                candidates.append(payload)

    action_counts = Counter(c.get("action") for c in candidates)
    signal_reasons = Counter()
    for candidate in candidates:
        signals = candidate.get("signals")
        if isinstance(signals, dict):
            for signal_name, signal_data in signals.items():
                if isinstance(signal_data, dict) and signal_data.get("available"):
                    signal_reasons[signal_name] += 1

    confidences = [float(c["confidence"]) for c in candidates if isinstance(c.get("confidence"), (int, float))]
    scores = [float(c["score"]) for c in candidates if isinstance(c.get("score"), (int, float))]
    sizes = [float(c["size_usd"]) for c in candidates if isinstance(c.get("size_usd"), (int, float))]
    prices = [float(c["price"]) for c in candidates if isinstance(c.get("price"), (int, float))]

    start = soak_rows[0]
    end = soak_rows[-1]

    output = {
        "window": {
            "soak_file": str(soak_path),
            "shadow_log": str(shadow_log_path),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "duration_min": round((end_ts - start_ts) / 60, 2),
        },
        "run_metadata": start.get("run_metadata"),
        "runtime_delta": {
            "opportunities": end.get("opportunities", 0) - start.get("opportunities", 0),
            "opened": end.get("opened", 0) - start.get("opened", 0),
            "closed": end.get("closed", 0) - start.get("closed", 0),
            "wins": end.get("wins", 0) - start.get("wins", 0),
            "losses": end.get("losses", 0) - start.get("losses", 0),
            "decision_events": end.get("decision_events", 0) - start.get("decision_events", 0),
            "odds_filter_blocked_events": end.get("odds_filter_blocked_events", 0) - start.get("odds_filter_blocked_events", 0),
            "risk_blocked_events": end.get("risk_blocked_events", 0) - start.get("risk_blocked_events", 0),
            "net_edge_blocked_events": end.get("net_edge_blocked_events", 0) - start.get("net_edge_blocked_events", 0),
        },
        "shadow_candidates": {
            "count": len(candidates),
            "action_counts": dict(action_counts),
            "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
            "avg_score": round(sum(scores) / len(scores), 4) if scores else None,
            "avg_size_usd": round(sum(sizes) / len(sizes), 4) if sizes else None,
            "avg_entry_price": round(sum(prices) / len(prices), 4) if prices else None,
            "available_signal_counts": dict(signal_reasons),
        },
        "sample_candidates": candidates[:5],
    }

    print(json.dumps(output, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
