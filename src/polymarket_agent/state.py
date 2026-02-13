from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass
class AgentEvent:
    ts: float
    level: str
    message: str
    data: dict = field(default_factory=dict)


class AgentState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_ts = time.time()
        self._kill_switch_enabled = False
        self._active_round_id: int | None = None
        self._round_close_ts: float | None = None
        self._latest_price: float | None = None
        self._latest_tick_ts: float | None = None
        self._polymarket_slug: str | None = None
        self._polymarket_token_ids: list[str] = []
        self._polymarket_yes_price: float | None = None
        self._polymarket_no_price: float | None = None
        self._polymarket_last_update_ts: float | None = None
        self._last_decision: dict | None = None
        self._events: Deque[AgentEvent] = deque(maxlen=200)
        self._paper_trades: Deque[dict] = deque(maxlen=500)

    def set_round(self, round_id: int, close_ts: float) -> None:
        with self._lock:
            self._active_round_id = round_id
            self._round_close_ts = close_ts

    def set_tick(self, price: float, tick_ts: float) -> None:
        with self._lock:
            self._latest_price = price
            self._latest_tick_ts = tick_ts

    def get_latest_price(self) -> float | None:
        with self._lock:
            return self._latest_price

    def set_decision(self, decision: dict) -> None:
        with self._lock:
            self._last_decision = decision

    def set_polymarket_market(self, slug: str, token_ids: list[str]) -> None:
        with self._lock:
            self._polymarket_slug = slug
            self._polymarket_token_ids = token_ids
            self._polymarket_yes_price = None
            self._polymarket_no_price = None
            self._polymarket_last_update_ts = None

    def set_polymarket_odds(
        self,
        *,
        yes_price: float | None,
        no_price: float | None,
        update_ts: float,
    ) -> None:
        with self._lock:
            self._polymarket_yes_price = yes_price
            self._polymarket_no_price = no_price
            self._polymarket_last_update_ts = update_ts

    def get_polymarket_odds_snapshot(self) -> dict:
        with self._lock:
            return {
                "slug": self._polymarket_slug,
                "token_ids": list(self._polymarket_token_ids),
                "yes_price": self._polymarket_yes_price,
                "no_price": self._polymarket_no_price,
                "last_update_ts": self._polymarket_last_update_ts,
            }

    def set_kill_switch(self, enabled: bool) -> None:
        with self._lock:
            self._kill_switch_enabled = enabled

    def is_kill_switch_enabled(self) -> bool:
        with self._lock:
            return self._kill_switch_enabled

    def add_event(self, level: str, message: str, data: dict | None = None) -> None:
        with self._lock:
            self._events.append(
                AgentEvent(
                    ts=time.time(),
                    level=level,
                    message=message,
                    data=data or {},
                )
            )

    def add_paper_trade_entry(self, entry: dict) -> None:
        with self._lock:
            self._paper_trades.append(entry)

    def get_paper_trade_entries(self) -> list[dict]:
        with self._lock:
            return list(self._paper_trades)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "started_ts": self._started_ts,
                "kill_switch_enabled": self._kill_switch_enabled,
                "active_round_id": self._active_round_id,
                "round_close_ts": self._round_close_ts,
                "latest_price": self._latest_price,
                "latest_tick_ts": self._latest_tick_ts,
                "polymarket_slug": self._polymarket_slug,
                "polymarket_token_ids": list(self._polymarket_token_ids),
                "polymarket_yes_price": self._polymarket_yes_price,
                "polymarket_no_price": self._polymarket_no_price,
                "polymarket_last_update_ts": self._polymarket_last_update_ts,
                "last_decision": self._last_decision,
                "paper_trades": list(self._paper_trades),
                "events": [
                    {
                        "ts": e.ts,
                        "level": e.level,
                        "message": e.message,
                        "data": e.data,
                    }
                    for e in list(self._events)
                ],
            }


agent_state = AgentState()
