from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ActionExecutor:
    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    async def execute(self, action: str, context: dict) -> None:
        if self.dry_run:
            logger.info("[DRY_RUN] action=%s context=%s", action, context)
            return

        # TODO: wire in real order-placement logic here.
        logger.info("Executing action=%s context=%s", action, context)
