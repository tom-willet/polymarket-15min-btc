from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import httpx
import websockets

from .state import AgentState

logger = logging.getLogger(__name__)

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
WINDOW_SECONDS = 15 * 60
BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"


@dataclass(frozen=True)
class ActiveMarket:
    slug: str
    token_ids: list[str]


class PolymarketOddsTracker:
    def __init__(
        self,
        *,
        ws_url: str,
        market_refresh_seconds: int = 12,
        move_threshold_pct: float = 3.0,
        move_min_abs_delta: float = 0.03,
        move_log_cooldown_seconds: float = 5.0,
    ) -> None:
        self.ws_url = ws_url
        self.market_refresh_seconds = market_refresh_seconds
        self.move_threshold_pct = move_threshold_pct
        self.move_min_abs_delta = move_min_abs_delta
        self.move_log_cooldown_seconds = move_log_cooldown_seconds
        self._last_logged_yes_price: float | None = None
        self._last_logged_no_price: float | None = None
        self._last_move_event_ts: float = 0.0
        self._last_known_btc_price: float | None = None
        self._last_btc_lookup_ts: float = 0.0

    async def run(self, state: AgentState) -> None:
        last_market_key: tuple[str, tuple[str, ...]] | None = None
        while True:
            try:
                market = await self._find_active_market()
                if market is None:
                    logger.warning("[Polymarket WS] No active market found; retrying in %ss", self.market_refresh_seconds)
                    await asyncio.sleep(float(self.market_refresh_seconds))
                    continue

                market_key = (market.slug, tuple(sorted(market.token_ids)))
                if market_key != last_market_key:
                    logger.info("[Polymarket WS] Active market: %s", market.slug)
                    state.set_polymarket_market(market.slug, market.token_ids)
                    state.add_event(
                        "info",
                        "polymarket_market_detected",
                        {"slug": market.slug, "token_ids": market.token_ids},
                    )
                    last_market_key = market_key

                await self._stream_market(market, state)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("[Polymarket WS] Tracker error: %s; reconnecting in 2s", exc)
                await asyncio.sleep(2.0)

    async def _stream_market(self, market: ActiveMarket, state: AgentState) -> None:
        yes_token = market.token_ids[0]
        no_token = market.token_ids[1]
        yes_price: float | None = None
        no_price: float | None = None

        logger.info("[Polymarket WS] Connecting")
        async with websockets.connect(self.ws_url, ping_interval=15) as ws:
            logger.info("[Polymarket WS] Connected")
            await ws.send(
                json.dumps(
                    {
                        "type": "market",
                        "assets_ids": market.token_ids,
                    }
                )
            )
            logger.info("[Polymarket WS] Subscribed to %s token(s)", len(market.token_ids))

            started_ts = time.time()
            while True:
                elapsed = time.time() - started_ts
                if elapsed >= self.market_refresh_seconds:
                    return

                timeout = max(0.5, self.market_refresh_seconds - elapsed)
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except TimeoutError:
                    return

                updates = self._extract_price_updates(raw)
                if not updates:
                    continue

                for asset_id, price in updates:
                    if asset_id == yes_token:
                        yes_price = price
                    elif asset_id == no_token:
                        no_price = price

                now_ts = time.time()
                state.set_polymarket_odds(
                    yes_price=yes_price,
                    no_price=no_price,
                    update_ts=now_ts,
                )

                btc_price = await self._resolve_btc_price(state)
                move_event = self._build_move_event(
                    slug=market.slug,
                    yes_price=yes_price,
                    no_price=no_price,
                    btc_price=btc_price,
                    now_ts=now_ts,
                )
                if move_event is not None:
                    move_event["ts"] = now_ts
                    state.add_event("info", "polymarket_move_3pct", move_event)

    async def _find_active_market(self) -> ActiveMarket | None:
        now_ts = int(time.time())
        aligned = (now_ts // WINDOW_SECONDS) * WINDOW_SECONDS
        candidates = [
            aligned,
            aligned - WINDOW_SECONDS,
            aligned - 2 * WINDOW_SECONDS,
            aligned + WINDOW_SECONDS,
        ]

        async with httpx.AsyncClient(timeout=5.0) as client:
            for ts_value in candidates:
                slug = f"btc-updown-15m-{ts_value}"
                token_ids = await self._lookup_slug(client, slug)
                if token_ids is None:
                    continue
                return ActiveMarket(slug=slug, token_ids=token_ids)

        return None

    async def _lookup_slug(self, client: httpx.AsyncClient, slug: str) -> list[str] | None:
        response = await client.get(f"{GAMMA_BASE_URL}/markets/slug/{slug}")
        if not response.is_success:
            return None

        payload = response.json()
        token_set: set[str] = set()
        self._collect_token_ids(payload, token_set)
        token_ids = list(token_set)
        if len(token_ids) < 2:
            return None

        return token_ids[:2]

    def _collect_token_ids(self, value: object, output: set[str]) -> None:
        if value is None:
            return

        if isinstance(value, str):
            trimmed = value.strip()

            if trimmed.isdigit() and len(trimmed) >= 8:
                output.add(trimmed)
                return

            if trimmed.startswith("[") and trimmed.endswith("]"):
                try:
                    parsed = json.loads(trimmed)
                except json.JSONDecodeError:
                    return
                self._collect_token_ids(parsed, output)
                return

            return

        if isinstance(value, list):
            for entry in value:
                self._collect_token_ids(entry, output)
            return

        if isinstance(value, dict):
            for key, entry in value.items():
                normalized = key.lower()
                if (
                    "token" in normalized
                    or "asset" in normalized
                    or normalized in {"clobtokenids", "clobtokenid"}
                ):
                    self._collect_token_ids(entry, output)
                if isinstance(entry, (dict, list)):
                    self._collect_token_ids(entry, output)

    def _extract_price_updates(self, raw: str) -> list[tuple[str, float]]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []

        updates: list[tuple[str, float]] = []

        def collect(value: object) -> None:
            if isinstance(value, list):
                for item in value:
                    collect(item)
                return

            if not isinstance(value, dict):
                return

            asset_id = value.get("asset_id")
            price_raw = value.get("price") or value.get("p")
            if isinstance(asset_id, str) and price_raw is not None:
                try:
                    updates.append((asset_id, float(price_raw)))
                except (TypeError, ValueError):
                    pass

            for child in value.values():
                if isinstance(child, (dict, list)):
                    collect(child)

        collect(payload)
        return updates

    def _build_move_event(
        self,
        *,
        slug: str,
        yes_price: float | None,
        no_price: float | None,
        btc_price: float | None,
        now_ts: float,
    ) -> dict | None:
        if now_ts - self._last_move_event_ts < self.move_log_cooldown_seconds:
            return None

        threshold_ratio = self.move_threshold_pct / 100.0

        yes_changed = False
        no_changed = False

        if isinstance(yes_price, float):
            if self._last_logged_yes_price is None:
                yes_changed = True
            elif self._last_logged_yes_price != 0:
                abs_delta = abs(yes_price - self._last_logged_yes_price)
                rel_delta = abs_delta / abs(self._last_logged_yes_price)
                yes_changed = rel_delta >= threshold_ratio or abs_delta >= self.move_min_abs_delta
            elif yes_price != 0:
                yes_changed = True

        if isinstance(no_price, float):
            if self._last_logged_no_price is None:
                no_changed = True
            elif self._last_logged_no_price != 0:
                abs_delta = abs(no_price - self._last_logged_no_price)
                rel_delta = abs_delta / abs(self._last_logged_no_price)
                no_changed = rel_delta >= threshold_ratio or abs_delta >= self.move_min_abs_delta
            elif no_price != 0:
                no_changed = True

        if not yes_changed and not no_changed:
            return None

        event = {
            "slug": slug,
            "price": btc_price,
            "polymarket_yes_price": yes_price,
            "polymarket_no_price": no_price,
            "yes_from": self._last_logged_yes_price,
            "yes_to": yes_price,
            "no_from": self._last_logged_no_price,
            "no_to": no_price,
        }

        if isinstance(yes_price, float):
            self._last_logged_yes_price = yes_price
        if isinstance(no_price, float):
            self._last_logged_no_price = no_price
        self._last_move_event_ts = now_ts

        return event

    async def _resolve_btc_price(self, state: AgentState) -> float | None:
        latest_price = state.get_latest_price()
        if isinstance(latest_price, (int, float)):
            self._last_known_btc_price = float(latest_price)
            return self._last_known_btc_price

        now_ts = time.time()
        if now_ts - self._last_btc_lookup_ts < 5.0:
            return self._last_known_btc_price

        self._last_btc_lookup_ts = now_ts
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.get(BINANCE_PRICE_URL)
                if not response.is_success:
                    return self._last_known_btc_price
                payload = response.json()
                value = payload.get("price")
                if isinstance(value, str):
                    self._last_known_btc_price = float(value)
                    state.set_binance_price(self._last_known_btc_price, now_ts)
                    return self._last_known_btc_price
        except (TypeError, ValueError, httpx.HTTPError):
            return self._last_known_btc_price

        return self._last_known_btc_price
