from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    poly_ws_url: str | None
    btc_stream: str
    btc_symbol: str
    btc_window: str
    chainlink_candlestick_login: str | None
    chainlink_candlestick_password: str | None
    chainlink_candlestick_base_url: str | None
    market_symbol: str
    round_seconds: int
    activation_lead_seconds: int
    agent_test_mode: bool
    test_mode_round_seconds: int
    test_mode_activation_lead_seconds: int
    ws_ping_interval_seconds: int
    dry_run: bool
    agent_api_port: int
    max_trades_per_round: int
    trade_cooldown_seconds: int
    polymarket_ws_enabled: bool
    polymarket_ws_url: str
    polymarket_market_refresh_seconds: int
    polymarket_move_threshold_pct: float
    polymarket_move_min_abs_delta: float
    polymarket_move_log_cooldown_seconds: float
    paper_trade_logging_enabled: bool
    paper_trade_log_path: str



def _bool_from_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}



def load_config() -> Config:
    load_dotenv()

    btc_stream = os.getenv("POLYMARKET_BTC_STREAM", "binance").strip().lower()
    btc_symbol = os.getenv("POLYMARKET_BTC_SYMBOL", "BTCUSDT").strip().upper()
    btc_window = os.getenv("POLYMARKET_BTC_WINDOW", "15m").strip().lower()
    chainlink_candlestick_login = os.getenv("CHAINLINK_CANDLESTICK_LOGIN", "").strip() or None
    chainlink_candlestick_password = os.getenv("CHAINLINK_CANDLESTICK_PASSWORD", "").strip() or None
    chainlink_candlestick_base_url = os.getenv("CHAINLINK_CANDLESTICK_BASE_URL", "").strip() or None

    poly_ws_url = os.getenv("POLY_WS_URL", "").strip() or None
    if btc_stream == "custom" and not poly_ws_url:
        raise ValueError("POLY_WS_URL is required when POLYMARKET_BTC_STREAM is 'custom'")

    if btc_stream == "chainlink":
        if not chainlink_candlestick_login:
            raise ValueError("CHAINLINK_CANDLESTICK_LOGIN is required when POLYMARKET_BTC_STREAM is 'chainlink'")
        if not chainlink_candlestick_password:
            raise ValueError("CHAINLINK_CANDLESTICK_PASSWORD is required when POLYMARKET_BTC_STREAM is 'chainlink'")
        if not chainlink_candlestick_base_url:
            raise ValueError("CHAINLINK_CANDLESTICK_BASE_URL is required when POLYMARKET_BTC_STREAM is 'chainlink'")

    agent_test_mode = _bool_from_env(os.getenv("AGENT_TEST_MODE"), False)
    test_mode_round_seconds = int(os.getenv("TEST_MODE_ROUND_SECONDS", "120"))
    test_mode_activation_lead_seconds = int(os.getenv("TEST_MODE_ACTIVATION_LEAD_SECONDS", "100"))
    round_seconds = int(os.getenv("ROUND_SECONDS", "900"))
    activation_lead_seconds = int(os.getenv("ACTIVATION_LEAD_SECONDS", "180"))

    if agent_test_mode:
        round_seconds = test_mode_round_seconds
        activation_lead_seconds = test_mode_activation_lead_seconds

    return Config(
        poly_ws_url=poly_ws_url,
        btc_stream=btc_stream,
        btc_symbol=btc_symbol,
        btc_window=btc_window,
        chainlink_candlestick_login=chainlink_candlestick_login,
        chainlink_candlestick_password=chainlink_candlestick_password,
        chainlink_candlestick_base_url=chainlink_candlestick_base_url,
        market_symbol=os.getenv("POLY_MARKET_SYMBOL", "BTC").strip(),
        round_seconds=round_seconds,
        activation_lead_seconds=activation_lead_seconds,
        agent_test_mode=agent_test_mode,
        test_mode_round_seconds=test_mode_round_seconds,
        test_mode_activation_lead_seconds=test_mode_activation_lead_seconds,
        ws_ping_interval_seconds=int(os.getenv("WS_PING_INTERVAL_SECONDS", "15")),
        dry_run=_bool_from_env(os.getenv("DRY_RUN"), True),
        agent_api_port=int(os.getenv("AGENT_API_PORT", "8080")),
        max_trades_per_round=int(os.getenv("MAX_TRADES_PER_ROUND", "2")),
        trade_cooldown_seconds=int(os.getenv("TRADE_COOLDOWN_SECONDS", "8")),
        polymarket_ws_enabled=_bool_from_env(os.getenv("POLYMARKET_WS_ENABLED"), True),
        polymarket_ws_url=os.getenv(
            "POLYMARKET_WS_URL",
            "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        ).strip(),
        polymarket_market_refresh_seconds=int(
            os.getenv("POLYMARKET_MARKET_REFRESH_SECONDS", "12")
        ),
        polymarket_move_threshold_pct=float(
            os.getenv("POLYMARKET_MOVE_THRESHOLD_PCT", "3.0")
        ),
        polymarket_move_min_abs_delta=float(
            os.getenv("POLYMARKET_MOVE_MIN_ABS_DELTA", "0.03")
        ),
        polymarket_move_log_cooldown_seconds=float(
            os.getenv("POLYMARKET_MOVE_LOG_COOLDOWN_SECONDS", "5.0")
        ),
        paper_trade_logging_enabled=_bool_from_env(
            os.getenv("PAPER_TRADE_LOGGING_ENABLED"),
            True,
        ),
        paper_trade_log_path=os.getenv(
            "PAPER_TRADE_LOG_PATH",
            "logs/paper_trades.jsonl",
        ).strip(),
    )
