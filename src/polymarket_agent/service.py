from __future__ import annotations

import asyncio

import uvicorn

from .api import app
from .config import load_config
from .main import run


async def serve() -> None:
    config = load_config()

    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=config.agent_api_port,
            log_level="info",
        )
    )

    async with asyncio.TaskGroup() as tg:
        tg.create_task(run())
        tg.create_task(server.serve())


if __name__ == "__main__":
    asyncio.run(serve())
