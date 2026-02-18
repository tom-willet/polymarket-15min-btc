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
    paper_trade_notional_usd: float
    paper_entry_slippage_bps: float
    paper_dynamic_slippage_enabled: bool
    paper_dynamic_slippage_edge_factor_bps: float
    paper_dynamic_slippage_confidence_factor_bps: float
    paper_dynamic_slippage_expiry_factor_bps: float
    paper_max_slippage_bps: float
    paper_gas_fee_usd_per_side: float
    paper_adverse_selection_bps: float
    paper_min_notional_usd: float
    paper_min_net_edge_bps: float
    paper_edge_strength_to_bps: float
    strategy_mode: str
    btc_updown_shadow_mode: bool
    btc_updown_live_enabled: bool
    btc_updown_min_confidence_to_trade: float
    btc_updown_min_score_to_trade: float
    btc_updown_max_entry_price: float
    btc_updown_kelly_fraction: float
    btc_updown_max_trade_size_usd: float
    btc_updown_min_trade_size_usd: float



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

    agent_test_mode = False
    test_mode_round_seconds = int(os.getenv("TEST_MODE_ROUND_SECONDS", "120"))
    test_mode_activation_lead_seconds = int(os.getenv("TEST_MODE_ACTIVATION_LEAD_SECONDS", "100"))
    round_seconds = int(os.getenv("ROUND_SECONDS", "900"))
    activation_lead_seconds = int(os.getenv("ACTIVATION_LEAD_SECONDS", "180"))

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
        paper_trade_notional_usd=float(
            os.getenv("PAPER_TRADE_NOTIONAL_USD", "25")
        ),
        paper_entry_slippage_bps=float(
            os.getenv("PAPER_ENTRY_SLIPPAGE_BPS", "50")
        ),
        paper_dynamic_slippage_enabled=_bool_from_env(
            os.getenv("PAPER_DYNAMIC_SLIPPAGE_ENABLED"),
            False,
        ),
        paper_dynamic_slippage_edge_factor_bps=float(
            os.getenv("PAPER_DYNAMIC_SLIPPAGE_EDGE_FACTOR_BPS", "25")
        ),
        paper_dynamic_slippage_confidence_factor_bps=float(
            os.getenv("PAPER_DYNAMIC_SLIPPAGE_CONFIDENCE_FACTOR_BPS", "20")
        ),
        paper_dynamic_slippage_expiry_factor_bps=float(
            os.getenv("PAPER_DYNAMIC_SLIPPAGE_EXPIRY_FACTOR_BPS", "30")
        ),
        paper_max_slippage_bps=float(
            os.getenv("PAPER_MAX_SLIPPAGE_BPS", "200")
        ),
        paper_gas_fee_usd_per_side=float(
            os.getenv("PAPER_GAS_FEE_USD_PER_SIDE", "0.05")
        ),
        paper_adverse_selection_bps=float(
            os.getenv("PAPER_ADVERSE_SELECTION_BPS", "30")
        ),
        paper_min_notional_usd=float(
            os.getenv("PAPER_MIN_NOTIONAL_USD", "1")
        ),
        paper_min_net_edge_bps=float(
            os.getenv("PAPER_MIN_NET_EDGE_BPS", "0")
        ),
        paper_edge_strength_to_bps=float(
            os.getenv("PAPER_EDGE_STRENGTH_TO_BPS", "1000")
        ),
        strategy_mode=os.getenv("STRATEGY_MODE", "classic").strip().lower(),
        btc_updown_shadow_mode=_bool_from_env(
            os.getenv("BTC_UPDOWN_SHADOW_MODE"),
            True,
        ),
        btc_updown_live_enabled=_bool_from_env(
            os.getenv("BTC_UPDOWN_LIVE_ENABLED"),
            False,
        ),
        btc_updown_min_confidence_to_trade=float(
            os.getenv("BTC_UPDOWN_MIN_CONFIDENCE_TO_TRADE", "0.35")
        ),
        btc_updown_min_score_to_trade=float(
            os.getenv("BTC_UPDOWN_MIN_SCORE_TO_TRADE", "0.2")
        ),
        btc_updown_max_entry_price=float(
            os.getenv("BTC_UPDOWN_MAX_ENTRY_PRICE", "0.85")
        ),
        btc_updown_kelly_fraction=float(
            os.getenv("BTC_UPDOWN_KELLY_FRACTION", "0.3")
        ),
        btc_updown_max_trade_size_usd=float(
            os.getenv("BTC_UPDOWN_MAX_TRADE_SIZE_USD", "100")
        ),
        btc_updown_min_trade_size_usd=float(
            os.getenv("BTC_UPDOWN_MIN_TRADE_SIZE_USD", "1")
        ),
    )
