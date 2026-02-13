from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from .models import RoundWindow


@dataclass
class RoundScheduler:
    round_seconds: int
    activation_lead_seconds: int

    def current_round(self, now_ts: float | None = None) -> RoundWindow:
        now_ts = now_ts if now_ts is not None else time.time()
        round_id = int(now_ts // self.round_seconds)
        start_ts = round_id * self.round_seconds
        close_ts = start_ts + self.round_seconds
        activation_ts = close_ts - self.activation_lead_seconds
        return RoundWindow(
            round_id=round_id,
            start_ts=start_ts,
            close_ts=close_ts,
            activation_ts=activation_ts,
        )

    async def wait_until_activation(self) -> RoundWindow:
        while True:
            window = self.current_round()
            now_ts = time.time()
            if window.activation_ts <= now_ts < window.close_ts:
                return window

            if now_ts < window.activation_ts:
                sleep_for = max(0.2, window.activation_ts - now_ts)
            else:
                next_round_ts = window.start_ts + self.round_seconds
                sleep_for = max(0.2, next_round_ts - now_ts)

            await asyncio.sleep(min(sleep_for, 2.0))
