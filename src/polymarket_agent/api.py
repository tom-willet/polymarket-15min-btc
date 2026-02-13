from __future__ import annotations

import os
import sys
import threading
import time

from fastapi import FastAPI
from pydantic import BaseModel

from .state import agent_state

app = FastAPI(title="Polymarket Agent API", version="0.1.0")


def _schedule_process_restart(delay_seconds: float = 0.4) -> None:
    def _restart() -> None:
        time.sleep(delay_seconds)
        os.execv(sys.executable, [sys.executable, *sys.argv])

    threading.Thread(target=_restart, daemon=True).start()


class KillSwitchRequest(BaseModel):
    enabled: bool


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/status")
async def status() -> dict:
    return agent_state.snapshot()


@app.get("/paper-trades")
async def paper_trades() -> dict:
    return {"items": agent_state.get_paper_trade_entries()}


@app.post("/admin/kill-switch")
async def set_kill_switch(payload: KillSwitchRequest) -> dict:
    agent_state.set_kill_switch(payload.enabled)
    return {"ok": True, "kill_switch_enabled": agent_state.is_kill_switch_enabled()}


@app.post("/admin/restart")
async def restart_agent() -> dict:
    agent_state.add_event("warning", "agent_restart_requested", {})
    _schedule_process_restart()
    return {"ok": True, "restarting": True}
