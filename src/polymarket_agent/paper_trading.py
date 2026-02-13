from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PaperTradeResult:
    outcome: str
    return_pct: float


def evaluate_paper_trade(action: str, entry_price: float, exit_price: float) -> PaperTradeResult:
    if entry_price <= 0:
        return PaperTradeResult(outcome="invalid", return_pct=0.0)

    raw_return = (exit_price - entry_price) / entry_price
    if action == "BUY_NO":
        raw_return = -raw_return

    if raw_return > 0:
        outcome = "win"
    elif raw_return < 0:
        outcome = "loss"
    else:
        outcome = "flat"

    return PaperTradeResult(outcome=outcome, return_pct=raw_return * 100)


class PaperTradeLogger:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: dict[str, Any]) -> None:
        payload = {
            "logged_at": time.time(),
            **entry,
        }
        line = json.dumps(payload, separators=(",", ":"), default=str)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
