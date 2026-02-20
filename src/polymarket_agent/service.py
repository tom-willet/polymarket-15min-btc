from __future__ import annotations

import asyncio

import uvicorn

from .api import app
from .config import load_config
from .main import run
from .review.runtime import get_or_create_review_service, get_review_service


async def serve() -> None:
    config = load_config()
    await get_or_create_review_service(config)

    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=config.agent_api_port,
            log_level="info",
        )
    )

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(run())
            tg.create_task(server.serve())
    finally:
        review_service = get_review_service()
        if review_service is not None:
            await review_service.stop()


if __name__ == "__main__":
    asyncio.run(serve())
