from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import httpx
import websockets

from .models import Tick

logger = logging.getLogger(__name__)


def _normalize_chainlink_price(value: float) -> float:
    if abs(value) >= 1e12:
        return value / 1e18
    return value


class TickerClient:
    def __init__(
        self,
        symbol: str,
        stream: str = "binance",
        ws_url: str | None = None,
        ping_interval_seconds: int = 15,
        chainlink_login: str | None = None,
        chainlink_password: str | None = None,
        chainlink_base_url: str | None = None,
    ) -> None:
        self.ws_url = ws_url
        self.symbol = symbol
        self.stream = stream
        self.ping_interval_seconds = ping_interval_seconds
        self.chainlink_login = chainlink_login
        self.chainlink_password = chainlink_password
        self.chainlink_base_url = chainlink_base_url.rstrip("/") if chainlink_base_url else None

    async def stream_ticks(self) -> AsyncIterator[Tick]:
        if self.stream == "chainlink":
            async for tick in self._stream_chainlink_ticks():
                yield tick
            return

        while True:
            try:
                target_url = self._resolve_ws_url()
                logger.info("[BTC WS] Connecting: %s %s", self.stream, self.symbol)
                async with websockets.connect(
                    target_url,
                    ping_interval=self.ping_interval_seconds,
                ) as ws:
                    logger.info("[BTC WS] Connected")
                    await self._send_subscribe(ws)
                    async for raw in ws:
                        tick = self._parse(raw)
                        if tick is None or tick.symbol != self.symbol:
                            continue
                        yield tick
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("[BTC WS] Error: %s; reconnecting in 1s", exc)
                await asyncio.sleep(1.0)

    async def _stream_chainlink_ticks(self) -> AsyncIterator[Tick]:
        while True:
            try:
                token = await self._authorize_chainlink()
                stream_url = f"{self.chainlink_base_url}/api/v1/streaming"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Connection": "keep-alive",
                }
                params = {"symbol": self.symbol}

                logger.info("[BTC WS] Connecting: chainlink %s", self.symbol)
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0)) as client:
                    async with client.stream("GET", stream_url, params=params, headers=headers) as response:
                        if not response.is_success:
                            logger.warning("[BTC WS] Chainlink streaming HTTP %s", response.status_code)
                            await asyncio.sleep(1.0)
                            continue

                        logger.info("[BTC WS] Connected")
                        async for line in response.aiter_lines():
                            if not line:
                                continue

                            tick = self._parse(line)
                            if tick is None:
                                continue

                            if tick.symbol != self.symbol:
                                continue

                            yield tick
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("[BTC WS] Error: %s; reconnecting in 1s", exc)
                await asyncio.sleep(1.0)

    async def _authorize_chainlink(self) -> str:
        if not self.chainlink_base_url:
            raise ValueError("CHAINLINK_CANDLESTICK_BASE_URL is required for chainlink stream")
        if not self.chainlink_login:
            raise ValueError("CHAINLINK_CANDLESTICK_LOGIN is required for chainlink stream")
        if not self.chainlink_password:
            raise ValueError("CHAINLINK_CANDLESTICK_PASSWORD is required for chainlink stream")

        authorize_url = f"{self.chainlink_base_url}/api/v1/authorize"
        payload = {
            "login": self.chainlink_login,
            "password": self.chainlink_password,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(authorize_url, data=payload)
            if not response.is_success:
                raise ValueError(f"chainlink authorize failed: HTTP {response.status_code}")

            body = response.json()
            token = body.get("d", {}).get("access_token")
            if not isinstance(token, str) or not token.strip():
                raise ValueError("chainlink authorize failed: missing access token")

            return token

    def _resolve_ws_url(self) -> str:
        if self.stream == "binance":
            return f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@trade"

        if self.ws_url:
            return self.ws_url

        raise ValueError(f"ws_url is required for stream '{self.stream}'")

    async def _send_subscribe(self, ws: websockets.WebSocketClientProtocol) -> None:
        if self.stream == "binance":
            return

        payload = {
            "type": "subscribe",
            "channel": "ticker",
            "symbol": self.symbol,
        }
        await ws.send(json.dumps(payload))

    def _parse(self, raw: str) -> Tick | None:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None

        if self.stream == "binance":
            symbol = str(data.get("s", "")).strip().upper()
            price = data.get("p")
            ts_ms = data.get("T") or data.get("E")
            size = data.get("q", 0.0)
            if not symbol or price is None or ts_ms is None:
                return None

            try:
                return Tick(
                    ts=float(ts_ms) / 1000.0,
                    symbol=symbol,
                    price=float(price),
                    size=float(size),
                )
            except (TypeError, ValueError):
                return None

        if self.stream == "chainlink":
            if data.get("heartbeat") is not None:
                return None

            msg_type = str(data.get("f", "")).strip().lower()
            symbol = str(data.get("i", "")).strip().upper()
            price = data.get("p")
            ts = data.get("t")
            size = data.get("s", 1.0)
            if msg_type != "t" or not symbol or price is None or ts is None:
                return None

            try:
                parsed_price = _normalize_chainlink_price(float(price))
                return Tick(ts=float(ts), symbol=symbol, price=parsed_price, size=float(size))
            except (TypeError, ValueError):
                return None

        symbol = str(data.get("symbol", "")).strip()
        price = data.get("price")
        ts = data.get("ts") or data.get("timestamp")
        size = data.get("size", 1.0)
        if not symbol or price is None or ts is None:
            return None

        try:
            return Tick(ts=float(ts), symbol=symbol, price=float(price), size=float(size))
        except (TypeError, ValueError):
            return None
